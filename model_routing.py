"""Free-model routing with database reservations shared across all app sessions.

Counts are this app's recorded requests, never a claim of provider-wide remaining quota.
No documents, prompts, credentials or provider error bodies are stored here.
"""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import time

FREE_MODELS = (
    "gemini-3.8-flash", "gemini-3.6-flash",
    "gemini-3.5-flash-lite", "gemini-3.1-flash-lite",
)


class ModelUnavailable(RuntimeError):
    pass


def quota_cooldown(exc):
    text = str(exc).lower()
    if any(word in text for word in ("perday", "per_day", "per day", "requestsperday")):
        now = datetime.now(ZoneInfo("America/Los_Angeles"))
        midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        return max(60, int(midnight.timestamp() - now.timestamp()) + 2)
    return 60


class ModelRouter:
    def __init__(self, database, user_id):
        self.db, self.user_id = database, user_id
        rows = database.table("model_catalog").select("model,priority,enabled").order("priority").execute().data or []
        self.models = [r["model"] for r in rows if r["enabled"] and r["model"] in FREE_MODELS]

    def reserve(self, model, input_tokens):
        event = self.db.rpc("reserve_model_request", {
            "p_user_id": self.user_id, "p_model": model, "p_tokens": input_tokens,
        }).execute().data
        return event

    def finish(self, event, status, response=None, elapsed=0, cooldown=0):
        usage = getattr(response, "usage_metadata", None)
        def token_count(name):
            value=getattr(usage,name,None)
            return value if isinstance(value,int) and value>=0 else None
        input_tokens=token_count("prompt_token_count")
        total=token_count("total_token_count")
        output_tokens=(max(0,total-input_tokens) if total is not None and input_tokens is not None else
                       (token_count("candidates_token_count") or 0)+(token_count("thoughts_token_count") or 0) if usage else None)
        self.db.rpc("finish_model_request", {
            "p_event": event, "p_user_id": self.user_id, "p_status": status,
            "p_input": input_tokens, "p_output": output_tokens,
            "p_latency": max(0, int(elapsed * 1000)), "p_cooldown": cooldown,
        }).execute()


def generate_automatically(client, contents, config, router=None, validate=None, log_fn=None, model_callback=None):
    """Try each eligible model once; never wait through repeated quota failures."""
    models = router.models if router else FREE_MODELS
    for model in models:
        event = None
        if router:
            # CountTokens is free and consumes no inference quota. Fail closed on accounting errors.
            try:
                # This pinned Gemini Developer API SDK rejects CountTokensConfig.system_instruction.
                # Count the system text as a separate part and reserve a conservative protocol margin.
                count = client.models.count_tokens(model=model,
                    contents=[{"text":config.system_instruction},*contents]).total_tokens
            except Exception as exc:
                # No inference was made. Unavailable endpoints need no model reservation.
                if any(code in str(exc).lower() for code in ("404","not_found","503","500","timeout")):
                    continue
                raise ModelUnavailable("Token accounting unavailable") from exc
            if not isinstance(count, int) or count < 1:
                raise ModelUnavailable("Token accounting unavailable")
            event = router.reserve(model, count+32)
            if not event:
                continue
        started = time.monotonic()
        response = None
        try:
            response = client.models.generate_content(model=model, contents=contents, config=config)
            text = (response.text or "").strip()
            if validate:
                validate(text)
        except Exception as exc:
            message = str(exc).lower()
            if "429" in message or "resource_exhausted" in message:
                status, cooldown = "rate_limited", quota_cooldown(exc)
            elif "404" in message or "not_found" in message:
                status, cooldown = "unavailable", 3600
            elif response is not None:
                status, cooldown = "invalid_response", 0
            elif any(code in message for code in ("503", "500", "502", "504", "timeout", "connection")):
                status, cooldown = "failed", 30
            else:
                if router:
                    router.finish(event, "failed", elapsed=time.monotonic()-started)
                raise
            if router:
                router.finish(event, status, response, time.monotonic()-started, cooldown)
            if log_fn:
                log_fn(f"{model}: {status}; trying the next available model")
            continue
        if router:
            router.finish(event, "success", response, time.monotonic()-started)
        if model_callback:
            model_callback(model)
        return text
    raise ModelUnavailable("models_unavailable")
