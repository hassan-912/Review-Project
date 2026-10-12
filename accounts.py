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


@dataclass(frozen=True)
class Actor:
    user_id: str
    email: str
    approved: bool
    role: str


def verified_actor(client, session, require_admin=False, require_approved=True):
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
        rows = admin_client().table("profiles").select("is_approved,role").eq("id", user.id).limit(1).execute().data
    except Exception as exc:
        raise AccountError("auth_unavailable") from exc
    profile = rows[0] if rows else {}
    actor = Actor(user.id, user.email or "", profile.get("is_approved") is True, profile.get("role", "user"))
    if require_approved and not actor.approved or require_admin and actor.role != "admin":
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


def reserve_review(client, session):
    actor = verified_actor(client, session)
    try:
        allowed = admin_client().rpc("reserve_review_attempt", {
            "p_user_id": actor.user_id,
            "p_request_id": str(uuid.uuid4()),
            "p_hourly_limit": positive_int("REVIEWS_PER_HOUR", 5),
            "p_daily_limit": positive_int("REVIEWS_PER_DAY", 20),
        }).execute().data
    except Exception as exc:
        raise AccountError("quota_unavailable") from exc
    if allowed is not True:
        raise AccountError("rate_limited")
    return actor


def set_approval(client, session, target_id: str, approved: bool):
    actor = verified_actor(client, session, require_admin=True)
    uuid.UUID(target_id)
    if target_id == actor.user_id:
        raise AccountError("access_update_failed")
    try:
        result = admin_client().table("profiles").update({"is_approved": approved}).eq("id", target_id).execute()
        if not result.data:
            raise AccountError("access_update_failed")
    except Exception as exc:
        raise AccountError("access_update_failed") from exc


def team_profiles(client, session):
    verified_actor(client, session, require_admin=True)
    return admin_client().table("profiles").select("id,email,is_approved,role").order("email").limit(1000).execute().data or []


def review_logs(client, session, team=False):
    actor = verified_actor(client, session, require_admin=team)
    query = admin_client().table("review_logs").select("client_name,submitted_by,score,timestamp")
    if not team:
        query = query.eq("user_id", actor.user_id)
    return query.order("timestamp", desc=True).limit(1000).execute().data or []


def log_review(client, session, client_name, country, score):
    actor = verified_actor(client, session)
    admin_client().table("review_logs").insert({
        "client_name": client_name.replace(":::", " ").strip() + ":::" + (country or ""),
        "submitted_by": actor.email,
        "user_id": actor.user_id,
        "score": round(score, 1),
    }).execute()
