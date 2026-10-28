"""Isolated browser sessions and server-only, explicitly authorised database access."""
from __future__ import annotations

import re
import time
import uuid
from functools import lru_cache
from dataclasses import dataclass
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
from supabase import ClientOptions, create_client
from settings import setting


class AccountError(RuntimeError):
    pass


class ReviewLimitError(AccountError):
    def __init__(self,period,details):
        super().__init__('rate_limited')
        self.period=period
        self.details=details


# Supabase Auth clamps configured minimums below six to six.
MIN_PASSWORD_LENGTH = 6


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
    return _service_client(url,key)


@lru_cache(maxsize=1)
def _service_client(url,key):
    # Reuse the connection pool. User auth clients remain isolated per browser.
    return create_client(url, key, options=ClientOptions(auto_refresh_token=False, persist_session=False))


def valid_email(value: str) -> bool:
    return bool(len(value) <= 254 and re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value))


def valid_username(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{2,31}", value))


def signup(client, username, email, password):
    username = username.strip().lower()
    if not valid_username(username):
        raise AccountError("username_invalid")
    if len(password) < MIN_PASSWORD_LENGTH:
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
    hourly_limit: int = 5
    daily_limit: int = 5

    @property
    def unlimited_reviews(self):
        return self.approved and self.role in ('admin','super_admin')


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
        rows = admin_client().table("profiles").select("is_approved,role,username,hourly_limit,daily_limit").eq("id", user.id).limit(1).execute().data
    except Exception as exc:
        raise AccountError("auth_unavailable") from exc
    profile = rows[0] if rows else {}
    actor = Actor(user.id, user.email or "", profile.get("is_approved") is True, profile.get("role", "user"), profile.get("username") or "",
                  profile.get('hourly_limit',5),min(5,profile.get('daily_limit',5)))
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
        ensure_service_available()
        if actor.unlimited_reviews:
            # The role comes from the live server-verified profile, never session
            # claims or UI state. A real ledger row is still required for history,
            # completion and Gemini usage; duplicate request IDs fail closed.
            admin_client().table('review_attempts').insert({
                'user_id':actor.user_id,'request_id':request_id or str(uuid.uuid4()),
                'client_name':client_name,'submitted_username':actor.username,
                'submitted_by':actor.email,'status':'running',
            }).execute()
            allowed=True
        else:
            allowed = admin_client().rpc("reserve_review_attempt", {
                "p_user_id": actor.user_id,
                "p_request_id": request_id or str(uuid.uuid4()),
                "p_hourly_limit": actor.hourly_limit,
                "p_daily_limit": min(5,actor.daily_limit),
            }).execute().data
    except AccountError:
        raise
    except Exception as exc:
        raise AccountError("quota_unavailable") from exc
    if allowed is not True:
        raise _review_limit_error(actor) or AccountError("rate_limited")
    if request_id and not actor.unlimited_reviews:
        admin_client().table("review_attempts").update({"client_name":client_name,"submitted_username":actor.username,"submitted_by":actor.email,"status":"running"}).eq("request_id",request_id).eq("user_id",actor.user_id).execute()
    return actor


def _review_limit_error(actor,now=None):
    """Explain a denied reservation without replacing the atomic database guard."""
    if actor.unlimited_reviews:return None
    now=now or datetime.now(timezone.utc)
    try:
        rows=admin_client().table('review_attempts').select('requested_at').eq('user_id',actor.user_id).gt(
            'requested_at',(now-timedelta(hours=24)).isoformat()).order('requested_at').limit(1000).execute().data
        stamps=sorted(datetime.fromisoformat(row['requested_at'].replace('Z','+00:00')) for row in rows)
        midnight=now.astimezone(ZoneInfo('Africa/Cairo')).replace(hour=0,minute=0,second=0,microsecond=0)
        daily=[stamp for stamp in stamps if stamp>=midnight]
        hourly=[stamp for stamp in stamps if stamp>now-timedelta(hours=1)]
        resets=[];periods=[]
        for label,items,limit,window in (('hourly',hourly,actor.hourly_limit,1),('daily',daily,min(5,actor.daily_limit),24)):
            if len(items)>=limit:
                resets.append(midnight+timedelta(days=1) if label=='daily' else items[len(items)-limit]+timedelta(hours=window))
                periods.append(label)
        if not resets:return None
        return ReviewLimitError('limit_both' if len(periods)==2 else 'limit_'+periods[0],dict(
            hour_used=len(hourly),hour_limit=actor.hourly_limit,day_used=len(daily),day_limit=min(5,actor.daily_limit),
            retry_at=max(resets).astimezone(ZoneInfo('Africa/Cairo')).strftime('%d/%m/%Y %H:%M:%S')))
    except Exception:
        # Missing diagnostics must never turn a denied reservation into an allowance.
        return None


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
    return admin_client().table("review_attempts").select("request_id,client_name,submitted_username,submitted_by,score,requested_at,status").order("requested_at",desc=True).limit(1000).execute().data or []


def super_update(client, session, target_id, role, approved, hourly, daily):
    actor=verified_actor(client,session,require_super=True)
    if role not in ("user","admin","super_admin") or not 1<=hourly<=100 or not 1<=daily<=5:
        raise AccountError("access_update_failed")
    try:
        admin_client().rpc("super_admin_update",{"p_actor":actor.user_id,"p_target":str(uuid.UUID(target_id)),
            "p_role":role,"p_approved":bool(approved),"p_hourly":hourly,"p_daily":daily}).execute()
    except Exception as exc:
        raise AccountError("access_update_failed") from exc








def set_reviews_enabled(client,session,enabled):
    actor=verified_actor(client,session,require_super=True)
    admin_client().rpc("set_reviews_enabled",{"p_actor":actor.user_id,"p_enabled":bool(enabled)}).execute()


def upload_category_order(client,session):
    from uploads import category_order
    verified_actor(client,session)
    rows=admin_client().table('app_controls').select('upload_category_order').eq('id',True).limit(1).execute().data
    return category_order(rows[0].get('upload_category_order') if rows else None)


def save_upload_category_order(client,session,order):
    from uploads import CATEGORIES
    actor=verified_actor(client,session,require_super=True)
    if len(order)!=len(CATEGORIES) or set(order)!=set(CATEGORIES):
        raise AccountError('access_update_failed')
    admin_client().rpc('set_upload_category_order',{'p_actor':actor.user_id,'p_order':list(order)}).execute()


def service_controls():
    """Server-only read; no credential or applicant information is returned."""
    try:
        rows = admin_client().table('app_controls').select('maintenance_enabled,reviews_enabled,upload_category_order').eq('id',True).limit(1).execute().data
        if not rows or not isinstance(rows[0].get('maintenance_enabled'),bool):
            raise ValueError('Missing service controls')
        return rows[0]
    except Exception as exc:
        raise AccountError('service_unavailable') from exc


def ensure_service_available():
    controls = service_controls()
    if controls['maintenance_enabled']:
        raise AccountError('maintenance_message')
    if not controls['reviews_enabled']:
        raise AccountError('reviews_closed')
    return controls


def set_maintenance(client,session,enabled):
    actor = verified_actor(client,session,require_super=True)
    admin_client().rpc('set_maintenance_mode',{'p_actor':actor.user_id,'p_enabled':bool(enabled)}).execute()


def reserve_gemini_usage(client,session,attempt_id,event):
    actor=verified_actor(client,session)
    ensure_service_available()
    allowed=admin_client().rpc('reserve_gemini_usage',dict(
        p_user_id=actor.user_id,p_review_id=attempt_id,p_event=event)).execute().data
    if allowed is not True:raise AccountError('quota_unavailable')
    return actor


def finish_gemini_usage(event_id,user_id,values):
    # The request was authorized at reservation. Record its bill even if access was revoked
    # during generation; private findings are independently reauthorized before display.
    from tenacity import retry,stop_after_attempt,wait_fixed
    @retry(stop=stop_after_attempt(3),wait=wait_fixed(.2),reraise=True)
    def save():
        admin_client().table('gemini_review_usage').update(values).eq('id',event_id).eq('user_id',user_id).execute()
    save()


def gemini_usage_rows(client,session,start,end):
    verified_actor(client,session,require_admin=True)
    rows=[];offset=0
    while True:
        page=admin_client().table('gemini_review_usage').select('*').gte('created_at',start).lt(
            'created_at',end).order('created_at',desc=True).order('id').range(offset,offset+499).execute().data or []
        rows.extend(page)
        if len(page)<500:return rows
        offset+=500
