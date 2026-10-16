"""Isolated browser sessions and server-only, explicitly authorised database access."""
from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass
from supabase import ClientOptions, create_client
from settings import setting, positive_int


class AccountError(RuntimeError):
    pass


def auth_client():
    url, key = setting("SUPABASE_URL"), setting("SUPABASE_ANON_KEY")
    if not url or not key:
        raise AccountError("config_missing")
    # Never cache or share this client: its auth storage belongs to one browser session.
    return create_client(url, key, options=ClientOptions(auto_refresh_token=False, persist_session=True, flow_type="implicit"))


def admin_client():
    url, key = setting("SUPABASE_URL"), setting("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise AccountError("config_missing")
    # This client never signs in as a user; its service-role headers remain server-side.
    return create_client(url, key, options=ClientOptions(auto_refresh_token=False, persist_session=False))


def valid_email(value: str) -> bool:
    return bool(len(value) <= 254 and re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value))


def valid_username(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{2,31}", value))


def signup(client, username, email, password):
    username = username.strip().lower()
    if not valid_username(username):
        raise AccountError("username_invalid")
    if len(password) < 8:
        raise AccountError("password_short")
    if not valid_email(email):
        raise AccountError("email_invalid")
    existing = admin_client().table("profiles").select("id").eq("username", username).limit(1).execute().data
    if existing:
        raise AccountError("username_taken")
    return client.auth.sign_up({"email":email,"password":password,"options":{"data":{"username":username},"email_redirect_to":setting("APP_URL")}})


@dataclass(frozen=True)
class Actor:
    user_id: str
    email: str
    approved: bool
    role: str
    username: str = ""


def verified_actor(client, session, require_admin=False, require_approved=True, require_super=False):
    """Verify the token against Auth, then read live authorisation from profiles."""
    if session is None:
        raise AccountError("session_expired")
    try:
        user = client.auth.get_user(session.access_token).user
    except Exception as exc:
        raise AccountError("session_expired") from exc
    if user is None:
        raise AccountError("session_expired")
    try:
        rows = admin_client().table("profiles").select("is_approved,role,username").eq("id", user.id).limit(1).execute().data
    except Exception as exc:
        raise AccountError("auth_unavailable") from exc
    profile = rows[0] if rows else {}
    actor = Actor(user.id, user.email or "", profile.get("is_approved") is True, profile.get("role", "user"), profile.get("username") or "")
    if (require_approved and not actor.approved or require_admin and (not actor.approved or actor.role not in ("admin","super_admin"))
            or require_super and (not actor.approved or actor.role != "super_admin")):
        raise AccountError("access_revoked")
    return actor


def refresh_if_needed(client, session, force=False):
    if not session:
        raise AccountError("session_expired")
    if force or (session.expires_at or 0) <= time.time() + 120:
        try:
            response = client.auth.refresh_session(session.refresh_token)
            if not response.session or not response.user:
                raise AccountError("session_expired")
            return response.session
        except Exception as exc:
            raise AccountError("session_expired") from exc
    return session


def restore_session(client, access_token, refresh_token):
    """Consume legacy URL tokens once; the app immediately removes them from the URL."""
    try:
        response = client.auth.set_session(access_token, refresh_token)
        if response.session and response.user:
            return response.session
    except Exception:
        pass
    try:
        response = client.auth.refresh_session(refresh_token)
        if response.session and response.user:
            return response.session
    except Exception:
        pass
    raise AccountError("session_expired")


def reserve_review(client, session, request_id=None, client_name=""):
    actor = verified_actor(client, session)
    try:
        allowed = admin_client().rpc("reserve_review_attempt", {
            "p_user_id": actor.user_id,
            "p_request_id": request_id or str(uuid.uuid4()),
            "p_hourly_limit": positive_int("REVIEWS_PER_HOUR", 5),
            "p_daily_limit": positive_int("REVIEWS_PER_DAY", 20),
        }).execute().data
    except Exception as exc:
        raise AccountError("quota_unavailable") from exc
    if allowed is not True:
        raise AccountError("rate_limited")
    if request_id:
        admin_client().table("review_attempts").update({"client_name":client_name,"submitted_username":actor.username,"submitted_by":actor.email,"status":"running"}).eq("request_id",request_id).eq("user_id",actor.user_id).execute()
    return actor


def set_approval(client, session, target_id: str, approved: bool):
    actor = verified_actor(client, session, require_admin=True)
    uuid.UUID(target_id)
    if target_id == actor.user_id:
        raise AccountError("access_update_failed")
    try:
        admin_client().rpc("set_team_approval", {"p_actor":actor.user_id,"p_target":target_id,"p_approved":approved}).execute()
    except Exception as exc:
        raise AccountError("access_update_failed") from exc


def team_profiles(client, session):
    verified_actor(client, session, require_admin=True)
    return admin_client().table("profiles").select("id,email,username,is_approved,role,hourly_limit,daily_limit").order("username").limit(1000).execute().data or []


def review_logs(client, session, team=False):
    actor = verified_actor(client, session, require_admin=team)
    query = admin_client().table("review_logs").select("client_name,submitted_by,submitted_username,score,timestamp")
    if not team:
        query = query.eq("user_id", actor.user_id)
    return query.order("timestamp", desc=True).limit(1000).execute().data or []


def log_review(client, session, client_name, country, score):
    actor = verified_actor(client, session)
    admin_client().table("review_logs").insert({
        "client_name": client_name.replace(":::", " ").strip() + ":::" + (country or ""),
        "submitted_by": actor.email,
        "submitted_username": actor.username,
        "user_id": actor.user_id,
        "score": round(score, 1),
    }).execute()


def finish_attempt(client, session, request_id, score=None):
    actor = verified_actor(client, session)
    admin_client().table("review_attempts").update({"status":"completed" if score is not None else "failed","score":score}).eq("request_id",request_id).eq("user_id",actor.user_id).execute()


def team_attempts(client, session):
    verified_actor(client, session, require_admin=True)
    return admin_client().table("review_attempts").select("client_name,submitted_username,submitted_by,score,requested_at,status").order("requested_at",desc=True).limit(1000).execute().data or []


def super_update(client, session, target_id, role, approved, hourly, daily):
    actor=verified_actor(client,session,require_super=True)
    if role not in ("user","admin","super_admin") or not 1<=hourly<=100 or not 1<=daily<=1000:
        raise AccountError("access_update_failed")
    try:
        admin_client().rpc("super_admin_update",{"p_actor":actor.user_id,"p_target":str(uuid.UUID(target_id)),
            "p_role":role,"p_approved":bool(approved),"p_hourly":hourly,"p_daily":daily}).execute()
    except Exception as exc:
        raise AccountError("access_update_failed") from exc


def model_router(client,session):
    from model_routing import ModelRouter
    actor=verified_actor(client,session)
    return ModelRouter(admin_client(),actor.user_id)


def model_dashboard(client,session):
    actor=verified_actor(client,session,require_super=True)
    return admin_client().rpc("model_usage_overview",{"p_actor":actor.user_id}).execute().data


def configure_model(client,session,model,enabled,priority,rpm,tpm,rpd):
    from model_routing import FREE_MODELS
    actor=verified_actor(client,session,require_super=True)
    if model not in FREE_MODELS:
        raise AccountError("access_update_failed")
    try:
        admin_client().rpc("configure_free_model",{"p_actor":actor.user_id,"p_model":model,"p_enabled":enabled,
            "p_priority":priority,"p_rpm":rpm,"p_tpm":tpm,"p_rpd":rpd}).execute()
    except Exception as exc:
        raise AccountError("access_update_failed") from exc


def set_reviews_enabled(client,session,enabled):
    actor=verified_actor(client,session,require_super=True)
    admin_client().rpc("set_reviews_enabled",{"p_actor":actor.user_id,"p_enabled":bool(enabled)}).execute()
