"""MG's bilingual visa document-review workspace."""
from __future__ import annotations

from html import escape
import csv
from io import StringIO
import logging
import time
import uuid
from datetime import datetime, date, time as datetime_time, timedelta
from zoneinfo import ZoneInfo

import streamlit as st
from i18n import t, field_label, document_label, issue_text, isolated_value, STRINGS

st.set_page_config(page_title=t("brand", "en"), page_icon=":material/fact_check:", layout="wide")

import accounts
import session_resume
from accounts import AccountError
from settings import setting
from uploads import CATEGORIES, USA_CATEGORIES, files_hash, validate_uploads, category_order, upload_slot_order, upload_slot_category,UPLOAD_EXTENSIONS
from theme import inject_theme
from recovery import recovery_tokens
from monitoring import capture_error, initialize_monitoring

logger = logging.getLogger(__name__)

VISA_PROGRAMS = ('schengen', 'canada', 'usa', 'uk')
SCHENGEN_COUNTRIES = ('spain', 'france', 'germany', 'italy', 'netherlands', 'sweden', 'belgium', 'greece')
TRIP_TYPES = ('tourism','business')
LOCAL_ENGINE_VERSION = 'local-v20-usa-booking-dates'
# Display snapshots are refreshed every 15 seconds by the background watchdog.
# Submitted work still bypasses them and checks live access/service controls.
DISPLAY_SNAPSHOT_SECONDS = 30


def review_scope_available():
    return (st.session_state.get('visa_program')=='usa' or
            st.session_state.get('visa_program', 'schengen') == 'schengen'
            and st.session_state.get('schengen_country', 'spain') in SCHENGEN_COUNTRIES
            and st.session_state.get('trip_type','tourism')=='tourism')


def current_review_scope():
    program=st.session_state.get('visa_program','schengen')
    return (program,st.session_state.get('schengen_country','spain') if program=='schengen' else None,
            st.session_state.get('trip_type','tourism') if program=='schengen' else None)


def render_review_scope():
    lang = st.session_state.lang
    program = st.segmented_control(t('visa_program'), VISA_PROGRAMS, default='schengen', required=True,
        format_func=lambda key: t('program_'+key, lang) + ('' if key in ('schengen','usa') else ' · '+t('under_processing', lang)),
        key='visa_program')
    country = None
    trip_type=None
    if program == 'schengen':
        country = st.selectbox(t('schengen_country'), SCHENGEN_COUNTRIES,
            format_func=lambda key: t('country_'+key, lang),
            key='schengen_country')
        trip_type=st.segmented_control(t('trip_type'),TRIP_TYPES,default='tourism',required=True,
            format_func=lambda key:t('trip_'+key,lang)+(' · '+t('under_processing',lang) if key=='business' else ''),
            key='trip_type')
    scope = (program, country, trip_type)
    previous = st.session_state.get('active_review_scope')
    if previous is not None and previous != scope:
        # Files and reports belong to their selected destination, never to a new workspace.
        st.session_state.upload_generation += 1
        st.session_state.review_result = None
        st.session_state.review_requested = False
        st.session_state.pop('upload_thumbnails', None)
        st.session_state.pop('document_cache',None)
    st.session_state.active_review_scope = scope
    if not review_scope_available():
        name = t('trip_business') if trip_type=='business' else t('country_'+country) if country else t('program_'+program)
        st.info(t('destination_processing', destination=name))
        return False
    st.caption(t('usa_workspace') if program=='usa' else t('schengen_workspace',destination=t('country_'+country,lang)))
    return True


def _init_session_state():
    pending=st.session_state.get('review_requested')
    if isinstance(pending,dict) and pending.get('generation')==st.session_state.get('upload_generation',0):
        # An early rerun can discard widgets that have not been drawn yet. Keep
        # the already submitted inputs independent of their widget lifecycle.
        st.session_state.client_name=pending['client_name']
        st.session_state.setdefault('lang',pending['lang'])
        for key,value in zip(('visa_program','schengen_country','trip_type'),pending['scope']):
            if value is not None:st.session_state.setdefault(key,value)
    defaults = {"lang":"en", "auth_client":None, "supabase_session":None, "actor":None,
                "review_result":None, "review_cache":{}, "review_requested":False, "notice":None, "upload_generation":0,
                "recovery_client":None, "recovery_session":None}
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)
    if st.session_state.lang not in ("en", "ar"):
        st.session_state.lang = "en"


def get_auth_client():
    if st.session_state.auth_client is None:
        st.session_state.auth_client = accounts.auth_client()
    return st.session_state.auth_client


def _clear_local_session(notice=None):
    session_resume.forget()
    lang = st.session_state.get("lang", "en")
    for key in list(st.session_state):
        del st.session_state[key]
    st.session_state.lang = lang
    st.session_state.notice = notice
    st.session_state.resume_clear_pending=True
    for key in ("_t", "_r", "_ma", "token_hash", "type"):
        if key in st.query_params:
            del st.query_params[key]


def _supabase_sign_out():
    try:
        get_auth_client().auth.sign_out({"scope":"local"})
    except Exception:
        pass
    _clear_local_session()


def _restore_session_from_params():
    access = st.query_params.get("_t")
    refresh = st.query_params.get("_r")
    for key in ("_t", "_r", "_ma"):
        if key in st.query_params:
            del st.query_params[key]
    if not access and not refresh:
        return
    try:
        st.session_state.supabase_session = accounts.restore_session(get_auth_client(), access, refresh)
    except Exception:
        st.session_state.notice = "session_expired"


def _refresh_actor(force=False):
    client = get_auth_client()
    session = accounts.refresh_if_needed(client, st.session_state.supabase_session)
    st.session_state.supabase_session = session
    session_resume.remember(session)
    cached=st.session_state.get('actor_snapshot')
    if not force and cached and cached[1]==session.access_token and time.monotonic()-cached[0]<DISPLAY_SNAPSHOT_SECONDS:
        return cached[2]
    actor = accounts.verified_actor(client, session, require_approved=False)
    st.session_state.actor_snapshot=(time.monotonic(),session.access_token,actor)
    st.session_state.actor = actor
    return actor


def _service_controls(force=False):
    cached=st.session_state.get('service_snapshot')
    if not force and cached and time.monotonic()-cached[0]<DISPLAY_SNAPSHOT_SECONDS:
        return cached[1]
    controls=accounts.service_controls()
    st.session_state.service_snapshot=(time.monotonic(),controls)
    # The public settings arrive in the same query as the service status. Avoid
    # another Auth + profile + settings round trip just to order upload cards.
    if isinstance(controls.get('upload_category_order'),list):
        st.session_state.category_order_cache=(time.monotonic(),controls['upload_category_order'])
    return controls


@st.fragment(run_every="1s")
def session_watchdog():
    if not st.session_state.get("supabase_session"):
        return
    if st.session_state.pop('watchdog_full_run',False):
        st.session_state.setdefault('watchdog_next_check',time.monotonic()+15)
        return
    try:
        # Only a completed, token-matching read may update this browser's state.
        # Polling the future is cheap; slow network requests run off the UI thread.
        session=st.session_state.supabase_session
        pending=st.session_state.get('watchdog_pending')
        if pending is None:
            if time.monotonic()<st.session_state.get('watchdog_next_check',0):
                return
            from session_poll import start
            session=accounts.refresh_if_needed(get_auth_client(),session)
            st.session_state.supabase_session=session
            session_resume.remember(session)
            st.session_state.watchdog_pending=(session.access_token,time.monotonic(),start(get_auth_client(),session.access_token))
            st.session_state.watchdog_next_check=time.monotonic()+15
            return
        token,started,future=pending
        if not future.done():
            return
        del st.session_state.watchdog_pending
        latest=max(st.session_state.get('actor_snapshot',(0,))[0],st.session_state.get('service_snapshot',(0,))[0])
        if token!=session.access_token or latest>started:
            # An intervening action/full render may already have fresher access
            # information. An older in-flight read must not overwrite it.
            st.session_state.watchdog_next_check=0
            return
        controls,actor=future.result()
        previous = st.session_state.actor
        st.session_state.service_snapshot=(time.monotonic(),controls)
        st.session_state.actor_snapshot=(time.monotonic(),token,actor)
        st.session_state.actor=actor
        if isinstance(controls.get('upload_category_order'),list):
            st.session_state.category_order_cache=(time.monotonic(),controls['upload_category_order'])
        if controls['maintenance_enabled'] != st.session_state.get('maintenance_active',False):
            st.rerun()
        if previous and (previous.approved != actor.approved or previous.role != actor.role):
            st.session_state.review_result = None
            st.session_state.review_cache = {}
            st.session_state.pop('document_cache',None)
            st.rerun()
    except AccountError as exc:
        if str(exc) == "session_expired":
            _clear_local_session("session_expired")
        else:
            st.session_state.actor = None
            st.session_state.pop('actor_snapshot',None)
        st.rerun()


def pill(key, css=None, lang=None):
    return f'<span class="pill {escape(css or key)}">{escape(t(key, lang))}</span>'


def render_header():
    brand, language = st.columns([5,1.25], vertical_alignment="center")
    with brand:
        st.html(f'<div style="display:flex;align-items:center;gap:12px"><span class="brand-mark">MG</span><strong>{escape(t("brand"))}</strong></div>')
    with language:
        st.segmented_control(t("language"), ["en","ar"], key="lang", required=True,
                             format_func=lambda x: "EN" if x == "en" else "عربي",
                             label_visibility="collapsed", width="stretch")
    inject_theme(st.session_state.lang)


def render_pending_screen(standalone=False):
    with st.container(border=True,key="card_pending"):
        st.subheader(t("pending_title"))
        st.write(t("pending_text"))
        for index, key in enumerate(("created","approval","unlocked")):
            state = "done" if index == 0 else "waiting"
            st.html(f'<p>{pill(state)} &nbsp; {escape(t(key))}</p>')
        if st.button(t("check_status"), key="check_status", width="stretch"):
            if standalone:
                st.info(t("check_status_hint"))
            else:
                try:
                    _refresh_actor()
                    st.rerun()
                except AccountError as exc:
                    st.error(t(str(exc)))
        if not standalone and st.button(t("sign_out"), key="pending_signout", width="stretch"):
            _supabase_sign_out()
            st.rerun()


@st.fragment
def render_auth_screen(management_only=False):
    st.caption(t("internal"))
    st.title(t("access_title"))
    st.write(t("access_description"))
    left, right = st.columns([1.15,1], gap="large")
    with left, st.container(border=True,key="card_access"):
        mode = 'sign_in' if management_only else st.segmented_control(t("navigation"), ["sign_in","create_account","forgot_password"],
                                    default="sign_in", required=True, format_func=t, key="access_mode")
        with st.form("auth_form"):
            username = st.text_input(t("username"),key="signup_username",max_chars=32,help=t("username_hint")).strip() if mode == "create_account" else ""
            email = st.text_input(t("email"), key="email", max_chars=254).strip()
            password = st.text_input(t("password"), type="password", key="password") if mode != "forgot_password" else ""
            if mode == "create_account":
                st.caption(t("password_short"))
            confirm = st.text_input(t("confirm_password"), type="password", key="confirm_password") if mode == "create_account" else ""
            submitted = st.form_submit_button(t("reset_send" if mode == "forgot_password" else mode), type="primary", width="stretch")
        if submitted:
            if not accounts.valid_email(email):
                st.error(t("email_invalid"))
                return
            if mode == "create_account" and len(password) < accounts.MIN_PASSWORD_LENGTH:
                st.error(t("password_short"))
                return
            if mode == "create_account" and password != confirm:
                st.error(t("password_mismatch"))
                return
            try:
                client = get_auth_client()
                if mode == "sign_in":
                    result = client.auth.sign_in_with_password({"email":email,"password":password})
                    if not result.session:
                        st.error(t("login_failed"))
                        return
                    st.session_state.supabase_session = result.session
                    _refresh_actor()
                    st.rerun()
                elif mode == "create_account":
                    accounts.signup(client,username,email,password)
                    # Signup can auto-create an SDK session; it must never grant app access.
                    st.session_state.auth_client = None
                    st.success(t("signup_success"))
                else:
                    app_url = setting("APP_URL")
                    if not app_url:
                        st.info(t("reset_unavailable"))
                        return
                    client.auth.reset_password_email(email, {"redirect_to":app_url})
                    st.success(t("reset_sent"))
            except AccountError as exc:
                st.error(t(str(exc)))
            except Exception:
                st.error(t("login_failed" if mode == "sign_in" else "signup_failed" if mode == "create_account" else "auth_unavailable"))
    with right:
        if not management_only:
            render_pending_screen(standalone=True)
    st.caption(t("upload_formats"))
    st.caption(t("privacy"))


def handle_recovery():
    tokens = recovery_tokens()
    token_hash = st.query_params.get("token_hash")
    recovery_type = st.query_params.get("type")
    if token_hash:
        for key in ("token_hash","type"):
            if key in st.query_params:
                del st.query_params[key]
    if tokens or token_hash and recovery_type == "recovery":
        try:
            client = accounts.auth_client()
            if tokens:
                result = client.auth.set_session(tokens["access_token"],tokens["refresh_token"])
            else:
                result = client.auth.verify_otp({"token_hash":token_hash,"type":"recovery"})
            if not result.session:
                raise AccountError("session_expired")
            st.session_state.recovery_client = client
            st.session_state.recovery_session = result.session
        except Exception:
            st.error(t("session_expired"))
    if st.session_state.recovery_client is None:
        return False
    st.title(t("reset_title"))
    with st.form("new_password_form"):
        password = st.text_input(t("new_password"),type="password")
        confirm = st.text_input(t("confirm_password"),type="password")
        submit = st.form_submit_button(t("save_password"),type="primary")
    if submit:
        if len(password) < accounts.MIN_PASSWORD_LENGTH:
            st.error(t("password_short"))
        elif password != confirm:
            st.error(t("password_mismatch"))
        else:
            try:
                client = st.session_state.recovery_client
                client.auth.update_user({"password":password})
                client.auth.sign_out({"scope":"global"})
                _clear_local_session("password_changed")
                st.rerun()
            except Exception:
                st.error(t("session_expired"))
    return True


def _compute_upload_hash(uploaded_files, lang=None):
    scope = '/'.join(str(value) for value in current_review_scope())
    return files_hash(uploaded_files, f'{LOCAL_ENGINE_VERSION}|{scope}', lang or st.session_state.lang)


def _compute_files_hash(uploaded_files, lang=None):
    return _compute_upload_hash(uploaded_files, lang)


def render_pipeline_stepper(active_step=1):
    cells=[]
    for index,key in enumerate(("step_read","step_rules","step_business","step_score"),1):
        state="done" if index < active_step else "in_progress" if index == active_step else "waiting"
        active=' active' if state == "in_progress" else ''
        cells.append(f'<div class="step{active}"><span class="muted ltr">0{index}</span><h4>{escape(t(key))}</h4>{pill(state)}</div>')
    st.html('<div class="stepper">'+''.join(cells)+'</div>')


def render_upload_ui():
    st.title(t("review_title"))
    st.write(t('usa_review_description') if st.session_state.get('visa_program')=='usa' else t('review_description'))
    if not render_review_scope():
        st.session_state.review_requested=False
        return None
    with st.form('review_input',clear_on_submit=False,enter_to_submit=False,border=False):
        values=_render_upload_fields()
        run,clear=st.columns([3,1])
        with run:
            # Form uploads are committed on submit. A disabled check based on
            # the previous run's files would prevent the first submission.
            st.form_submit_button(t('run_review'),key='run_review_submit',type='primary',
                icon=':material/fact_check:',on_click=_request_review,width='stretch')
        with clear:
            st.form_submit_button(t('clear_files'),key='clear_review_submit',on_click=_clear_review_files,width='stretch')
    return values


def _request_review():
    # The callback sees all committed form values together. Save bytes and the
    # client name now, before another rerun can clear unrendered widgets.
    generation=st.session_state.upload_generation
    files={}
    slots=upload_slot_order(program=st.session_state.get('visa_program','schengen'),
                            country=st.session_state.get('schengen_country','spain'))
    for slot in slots:
        uploads=st.session_state.get(f'upload_{generation}_{slot}') or []
        if uploads:
            files.setdefault(upload_slot_category(slot),[]).extend((file.name,file.getvalue()) for file in uploads)
    st.session_state.review_requested=dict(uploaded_files=files,
        client_name=st.session_state.get('client_name',''),generation=generation,lang=st.session_state.lang,
        scope=current_review_scope())


def _clear_review_files():
    st.session_state.upload_generation+=1
    st.session_state.review_result=None
    st.session_state.review_cache={}
    st.session_state.review_requested=False
    st.session_state.pop('document_cache',None)


def _render_upload_fields():
    usa=st.session_state.get('visa_program')=='usa'
    client_name = st.text_input(t("client_name"), placeholder=t("client_placeholder"),max_chars=150,key="client_name")
    st.subheader(t("upload_title"))
    st.caption(t("upload_hint"))
    st.caption(t('usa_upload_hint') if usa else t('combined_hint' if st.session_state.get('schengen_country','spain')=='spain' else 'combined_hint_schengen'))
    uploaded={}
    icons=dict(zip(CATEGORIES,("badge","description","article","hotel","flight","health_and_safety","work","map","account_balance","event","folder")))
    icons.update(national_id_translation='translate',bank_declaration='account_balance',ds160='description',client_form='assignment_ind')
    order=upload_slot_order(None if usa else current_category_order(),program=st.session_state.get('visa_program','schengen'),
                            country=st.session_state.get('schengen_country','spain'))
    for offset in range(0, len(order),3):
        columns=st.columns(3)
        for index, category in enumerate(order[offset:offset+3],offset):
            widget_key=f"upload_{st.session_state.upload_generation}_{category}"
            with columns[index % 3], st.container(border=True, key='slot_'+category):
                st.markdown(f':material/{icons[category]}: **{t("doc_"+category)}**')
                if category=='bank_statement':st.caption(t('bank_scope'))
                if category=='appointment':st.caption(t('appointment_hint'))
                if category in ('supporting','national_id_translation'):st.caption(t('supporting_translation_hint'))
                if category in ('insurance','supporting','employment'):st.caption(t('local_template_hint'))
                files=st.file_uploader(t("doc_"+category),type=UPLOAD_EXTENSIONS,
                                       accept_multiple_files=True,key=widget_key,max_upload_size=20,label_visibility="collapsed")
                if files:
                    uploaded.setdefault(upload_slot_category(category),[]).extend((f.name,f.getvalue()) for f in files)
                elif category=='passport':
                    st.caption(t('passport_upload_missing'))
    st.caption(t("upload_formats"))
    st.caption(t('usa_privacy' if usa else 'privacy'))
    st.session_state.pop('upload_thumbnails',None)
    st.caption(t("log_notice"))
    return uploaded,client_name


def current_category_order():
    cached=st.session_state.get('category_order_cache')
    if cached and time.monotonic()-cached[0]<60:
        return category_order(cached[1])
    try:
        order=accounts.upload_category_order(get_auth_client(),st.session_state.supabase_session)
    except Exception:
        order=category_order()
    st.session_state.category_order_cache=(time.monotonic(),order)
    return order


def review_documents(*args,**kwargs):
    # Keep document/OCR/report imports off the sign-in and navigation paths.
    if st.session_state.get('visa_program')=='usa':
        from usa_review import review_documents as run
        kwargs.pop('review_country',None)
    else:
        from review_pipeline import review_documents as run
    return run(*args,**kwargs)


def run_review(uploaded_files,client_name,force_refresh=False):
    st.session_state.review_result=None
    if not review_scope_available():
        st.info(t('review_scope_unavailable')); return
    client_name=client_name.strip()
    if not client_name or len(client_name)>150:
        st.error(t("client_required")); return
    try:
        validate_uploads(uploaded_files,allowed_categories=USA_CATEGORIES if st.session_state.get('visa_program')=='usa' else CATEGORIES)
    except ValueError as exc:
        st.error(t(str(exc) if str(exc) in STRINGS else "upload_invalid")); return
    key=_compute_upload_hash(uploaded_files)
    now=time.monotonic()
    cache={k:v for k,v in st.session_state.review_cache.items() if now-v[0]<1800}
    st.session_state.review_cache=cache
    progress=st.empty(); skeleton=st.empty()
    attempt_id=None
    attempt_finished=False
    attempt_score=None
    try:
        actor=_refresh_actor(force=True)
        if not actor.approved:raise AccountError('access_revoked')
        client=get_auth_client(); session=st.session_state.supabase_session
        accounts.ensure_service_available()
        if key in cache and not force_refresh:
            result=cache[key][1].copy()
            st.info(t("cached"))
        else:
            from document_cache import DocumentCache
            attempt_id=str(uuid.uuid4())
            accounts.reserve_review(client,session,request_id=attempt_id,client_name=client_name)
            skeleton.html('<div class="skeleton"><i></i><i></i><i></i></div>')
            def update(step):
                with progress.container():
                    render_pipeline_stepper(step)
            document_cache=st.session_state.get('document_cache')
            if force_refresh or not isinstance(document_cache,DocumentCache) or document_cache.version!=LOCAL_ENGINE_VERSION:
                st.session_state.document_cache=DocumentCache(version=LOCAL_ENGINE_VERSION)
            result=review_documents(uploaded_files,lang=st.session_state.lang,progress=update,
                                    extraction_cache=st.session_state.document_cache,
                                    review_country=st.session_state.get('schengen_country','spain'))
            if len(cache)>=3:
                cache.pop(next(iter(cache)))
            cache[key]=(now,result.copy())
        program=st.session_state.get('visa_program','schengen')
        result.update({"client_name":client_name,"hash":key,"visa_program":program,
                       "review_country":'usa' if program=='usa' else st.session_state.get('schengen_country','spain'),
                       "trip_type":None if program=='usa' else 'tourism'})
        if program=='schengen' and attempt_id and result.get('narrative_requested'):
            try:
                from narrative_reviewer.ui import prepare
                from narrative_reviewer.service import run_review as run_gemini
                with st.spinner(t('reasoning_running')):
                    packet=prepare(result,st.session_state.lang)
                    result['narrative_review']=run_gemini(packet,client,session,attempt_id)
            except AccountError:
                raise
            except Exception as exc:
                capture_error(exc,'gemini_review')
                result['narrative_review']=dict(status='unavailable',findings=[],limitations=[])
            cache[key]=(now,result.copy())
        # Recheck approval after extraction before showing private evidence.
        actor=_refresh_actor(force=True)
        if not actor.approved:raise AccountError('access_revoked')
        accounts.ensure_service_available()
        st.session_state.review_result=result
        attempt_score=result["score"].score
        if attempt_id:
            try:
                accounts.finish_attempt(client,st.session_state.supabase_session,attempt_id,result["score"].score)
                attempt_finished=True
            except Exception as exc:
                capture_error(exc,'review_attempt_log')
                st.warning(t("log_failed"))
        try:
            accounts.log_review(client,st.session_state.supabase_session,client_name,
                                'USA' if program=='usa' else result["extraction"].main_schengen_destination,result["score"].score)
        except Exception as exc:
            capture_error(exc,'review_history')
            st.warning(t("log_failed"))
        st.success(t("review_complete"))
    except AccountError as exc:
        if str(exc) in ('auth_unavailable','quota_unavailable','service_unavailable'):
            capture_error(exc,'review_access')
        if isinstance(exc,accounts.ReviewLimitError):
            st.error(t('rate_limited_details',period=t(exc.period),**exc.details))
            st.caption(t('review_attempts_hint'))
        else:
            st.error(t(str(exc)))
    except Exception as exc:
        reference=capture_error(exc,'review')
        # Exception messages and tracebacks can contain extracted client evidence or tokens.
        logger.error("Review failed; reference=%s",reference)
        st.error(t("review_failed",reference=reference))
    finally:
        if attempt_id and not attempt_finished:
            try:
                accounts.finish_attempt(get_auth_client(),st.session_state.supabase_session,attempt_id,attempt_score)
            except Exception:
                logger.warning("Attempt status update unavailable")
        skeleton.empty()


def timeline_rows(extraction,issues,lang):
    from validator import employment_applies, _parse_date, accommodation_window
    flight_start=_parse_date(extraction.flight.departure_date)
    flight_end=_parse_date(extraction.flight.return_date)
    rows=[]
    records=[("flight",extraction.flight.departure_date,extraction.flight.return_date),
             ("visa_form",extraction.visa_form.intended_arrival,extraction.visa_form.intended_departure)]
    hotel_start,hotel_end=accommodation_window(extraction)
    records.append(("hotel",str(hotel_start) if hotel_start else None,str(hotel_end) if hotel_end else None))
    records.extend([
        ("cover_letter",None,None),
        ("employment",extraction.employment.approved_leave_start,extraction.employment.approved_leave_end),
        ("insurance",extraction.insurance.valid_from,extraction.insurance.valid_until),
    ])
    for category,start,end in records:
        if category=='employment' and not employment_applies(extraction):
            continue
        a,b=_parse_date(start),_parse_date(end)
        status="check"
        if flight_start and flight_end and flight_start<flight_end and a and b and a<b:
            if category in ("insurance","employment","hotel"):
                status="aligned" if a<=flight_start and b>=flight_end else "gap"
            else:
                status="aligned" if a==flight_start and b==flight_end else "check"
        if category=="hotel" and any(i.field_name in ("check_in_date","check_out_date") for i in issues):
            status="gap"
        rows.append((t("doc_"+category,lang),start,end,status))
    return rows


def render_travel_date_timeline(extraction,issues):
    lang=st.session_state.lang
    st.subheader(t("timeline"))
    headers=''.join('<th>'+escape(t(key))+'</th>' for key in ("document","start_date","end_date","status"))
    body=[]
    for name,start,end,status in timeline_rows(extraction,issues,lang):
        body.append('<tr><td>'+escape(name)+'</td><td><span class="ltr">'+escape(start or t("unknown"))+'</span></td><td><span class="ltr">'+escape(end or t("unknown"))+'</span></td><td>'+pill(status)+'</td></tr>')
    st.html('<table class="timeline"><thead><tr>'+headers+'</tr></thead><tbody>'+''.join(body)+'</tbody></table>')
    for hotel in extraction.hotel:
        st.caption(" · ".join(str(x) for x in (hotel.hotel_name,hotel.city,hotel.check_in_date,hotel.check_out_date) if x))


def render_evidence_images(locations,result,prefix):
    from evidence import render_source
    if not locations or not result.get("source_files"):
        st.caption(t("evidence_unavailable")); return
    cache=result.setdefault("evidence_images",{})
    for index,location in enumerate(locations[:2]):
        key=repr(sorted(location.items()))
        if key not in cache:
            if len(cache)>=16: cache.pop(next(iter(cache)))
            try:
                cache[key]=render_source(location,result["source_files"])
            except Exception:
                cache[key]=None
        source=cache[key]
        if source:
            png,page,method=source
            st.image(png,caption=f'{location["source_file"]} · {t("page")} {page}',width="stretch")
            st.caption(t(method))
        else:
            st.caption(t("evidence_unavailable"))


def render_fix_checklist(issues,result=None):
    from report_view import render_findings
    render_findings(issues,result,st.session_state.lang)


def render_report(result):
    if result.get('visa_program')=='usa':
        from usa_ui import render_usa_report
        render_usa_report(result,st.session_state.lang)
        return
    from report_view import render_report_view
    def authorize():
        actor=_refresh_actor(force=True)
        if not actor.approved:raise AccountError('access_revoked')
        accounts.ensure_service_available()
    def reason(packet):
        from narrative_reviewer.service import run_review as run_gemini
        authorize()
        attempt=str(uuid.uuid4())
        client=get_auth_client();session=st.session_state.supabase_session
        accounts.reserve_review(client,session,request_id=attempt,client_name=result.get('client_name',''))
        completed=False
        try:
            response=run_gemini(packet,client,session,attempt)
            authorize()
            completed=True
            return response
        finally:
            try:
                accounts.finish_attempt(client,session,attempt,result['score'].score if completed else None)
            except Exception as exc:
                capture_error(exc,'narrative_attempt_log')
    render_report_view(result,st.session_state.lang,authorize,reason)


def normalized_logs(logs):
    rows=[]
    for row in logs:
        client,_,country=(row.get("client_name") or "").partition(":::")
        timestamp=row.get("timestamp") or row.get("requested_at") or ""
        try:
            timestamp=datetime.fromisoformat(timestamp.replace("Z","+00:00")).astimezone(ZoneInfo("Africa/Cairo")).strftime("%Y-%m-%d %H:%M")
        except ValueError:
            pass
        entry={"client_name":client,"country":country or t("unknown"),"agent":row.get("submitted_username") or row.get("submitted_by") or "",
               "agent_email":row.get("submitted_by") or "", "latest_score":float(row["score"]) if row.get("score") is not None else "—","date":timestamp}
        if "status" in row:
            entry["status"]=t(row.get("status") or "legacy")
        rows.append(entry)
    return rows


@st.fragment
def render_logs(rows,team=False,key_prefix="log"):
    search=st.text_input(t("search"),key=key_prefix+"_search").strip().casefold()
    filtered=[r for r in rows if search in ' '.join(str(v) for v in r.values()).casefold()]
    if not filtered:
        st.info(t("no_results")); return
    pages=max(1,(len(filtered)+24)//25)
    page=st.number_input(t("page"),min_value=1,max_value=pages,value=1,step=1,key=key_prefix+"_page")
    shown=filtered[(int(page)-1)*25:int(page)*25]
    displayed=[]
    for row in shown:
        items=list(row.items())
        if st.session_state.lang=="ar": items.reverse()
        displayed.append({t(key):value for key,value in items})
    st.dataframe(displayed,hide_index=True,width="stretch")
    if team:
        buffer=StringIO(); writer=csv.writer(buffer)
        fields=list(filtered[0])
        writer.writerow([t(key) for key in fields])
        for row in filtered:
            values=[row[key] for key in fields]
            # Spreadsheet formula injection can originate from client names or agent emails.
            writer.writerow(["'"+v if isinstance(v,str) and v.lstrip().startswith(("=","+","-","@")) else v for v in values])
        st.download_button(t("export_csv"),buffer.getvalue().encode("utf-8-sig"),file_name="MG-reviews.csv",mime="text/csv",key=key_prefix+"_csv",on_click='ignore')


def render_my_history():
    st.title(t("history")); st.write(t("history_description"))
    try:
        rows=normalized_logs(accounts.review_logs(get_auth_client(),st.session_state.supabase_session))
    except Exception:
        st.error(t("history_failed")); return
    if not rows:
        st.info(t("history_empty")); return
    grouped={}
    counts={}
    for row in rows:
        name=row["client_name"]
        counts[name]=counts.get(name,0)+1
        grouped.setdefault(name,{k:v for k,v in row.items() if k not in ("agent","agent_email")})
    for name,row in grouped.items():
        row["edits_done"]=t("yes" if counts[name]>1 else "no")
    st.caption(t("log_scope",count=len(rows)))
    render_logs(list(grouped.values()))


def render_admin_dashboard():
    st.title(t("admin")); st.write(t("admin_description"))
    client=get_auth_client(); session=st.session_state.supabase_session
    sections=['admin_reviews','admin_access','admin_uploads','admin_team_log','admin_costs','admin_maintenance']
    if st.session_state.get('admin_section') not in sections:
        st.session_state.admin_section=sections[0]
    section=st.selectbox(t('admin_section'),sections,format_func=lambda key,lang=st.session_state.lang:t(key,lang),key='admin_section')
    try:
        profiles=accounts.team_profiles(client,session) if section=='admin_access' else []
        rows=normalized_logs(accounts.review_logs(client,session,team=True)) if section=='admin_team_log' else []
        attempts=normalized_logs(accounts.team_attempts(client,session)) if section in ('admin_reviews','admin_team_log') else []
    except Exception:
        st.error(t("history_failed")); return
    st.divider()
    is_super=st.session_state.actor.role=='super_admin'
    if section=='admin_reviews':
        st.subheader(t('admin_reviews'))
        render_review_controls(client,session,is_super)
        st.caption(t('attempts_hint'))
        render_logs(attempts,team=True,key_prefix='overview_attempts')
    elif section=='admin_access':
        render_access_management(client,session,profiles)
    elif section=='admin_team_log':
        st.subheader(t('admin_team_log'))
        render_logs(rows,team=True)
        with st.expander(t('attempts')):
            st.caption(t('attempts_hint'))
            render_logs(attempts,team=True,key_prefix='attempts')
    elif section=='admin_costs':
        from cost_dashboard import render_cost_dashboard
        render_cost_dashboard(client,session,st.session_state.lang)
    elif not is_super:
        st.info(t('super_admin_section'))
    elif section=='admin_uploads':
        render_category_order_editor(client,session)
    elif section=='admin_maintenance':
        render_maintenance_controls(client,session)


def render_access_management(client,session,profiles):
    st.subheader(t("approval_queue"))
    for original in sorted(profiles,key=lambda p:bool(p.get("is_approved"))):
        profile={**original,"daily_limit":min(5,original.get("daily_limit",5))}
        with st.container(border=True,key="card_profile_"+profile["id"]):
            identity,action=st.columns([4,1])
            with identity:
                st.text(profile.get("username") or profile.get("email") or profile["id"])
                st.text(profile.get("email") or "")
                st.caption(t(profile.get("role","user")))
                st.caption(t('admin_reviews_unlimited') if profile.get('role') in ('admin','super_admin') else
                    t('review_limits_summary',hour=profile.get('hourly_limit',5),day=min(5,profile.get('daily_limit',5))))
                st.html(pill("approved" if profile.get("is_approved") else "pending", "success" if profile.get("is_approved") else "waiting"))
            with action:
                approved=bool(profile.get("is_approved"))
                if st.button(t("revoke" if approved else "approve"),key="approval_"+profile["id"],
                             disabled=profile["id"]==st.session_state.actor.user_id or profile.get("role")!="user",width="stretch"):
                    try:
                        accounts.set_approval(client,session,profile["id"],not approved)
                        st.session_state.notice="access_updated"
                        st.rerun()
                    except AccountError as exc:
                        st.error(t(str(exc)))
            if st.session_state.actor.role=="super_admin":
                snapshot=tuple(profile.get(key,default) for key,default in
                    (('role','user'),('is_approved',False),('hourly_limit',5),('daily_limit',5)))
                saved=st.session_state.setdefault('profile_editor_saved',{})
                if profile['id'] in saved and saved[profile['id']]!=snapshot:
                    for prefix,value in zip(('role_','approved_','hour_','day_'),snapshot):
                        st.session_state[prefix+profile['id']]=value
                saved[profile['id']]=snapshot
                with st.expander(t('permissions_and_limits')):
                    unlimited=profile.get('role') in ('admin','super_admin')
                    st.caption(t('admin_reviews_unlimited') if unlimited else t('review_limits_hint'))
                    with st.form("permissions_"+profile["id"]):
                        roles=["user","admin","super_admin"]
                        role=st.selectbox(t("role"),roles,index=roles.index(profile.get("role","user")),
                            format_func=lambda key,lang=st.session_state.lang:t(key,lang),key="role_"+profile["id"])
                        approved=st.checkbox(t("approved"),value=bool(profile.get("is_approved")),key="approved_"+profile["id"])
                        hour_column,day_column=st.columns(2)
                        hour=hour_column.number_input(t("hourly_limit"),1,100,value=profile.get("hourly_limit",5),key="hour_"+profile["id"],disabled=unlimited)
                        day=day_column.number_input(t("daily_limit"),1,5,value=min(5,profile.get("daily_limit",5)),key="day_"+profile["id"],disabled=unlimited)
                        if st.form_submit_button(t("save_changes")):
                            try:
                                accounts.super_update(client,session,profile["id"],role,approved,hour,day)
                                st.session_state.notice="permissions_updated"; st.rerun()
                            except AccountError as exc:
                                st.error(t(str(exc)))


def render_review_controls(client,session,is_super):
    try:
        controls=_service_controls()
        st.info(t('reviews_open' if controls['reviews_enabled'] else 'reviews_closed'))
        if is_super:
            with st.form('review_controls'):
                enabled=st.checkbox(t('reviews_enabled'),value=controls['reviews_enabled'])
                if st.form_submit_button(t('save_changes')):
                    accounts.set_reviews_enabled(client,session,enabled)
                    st.session_state.pop('service_snapshot',None)
                    st.rerun()
    except Exception:
        st.error(t('service_unavailable'))


def render_maintenance_controls(client,session):
    st.subheader(t('admin_maintenance'))
    st.caption(t('maintenance_hint'))
    try:
        active=_service_controls()['maintenance_enabled']
        st.warning(t('maintenance_message')) if active else st.success(t('website_live'))
        if st.button(t('resume_website' if active else 'pause_website'),type='primary',icon=':material/build:',key='maintenance_switch'):
            accounts.set_maintenance(client,session,not active)
            st.session_state.pop('service_snapshot',None)
            st.rerun()
    except Exception:
        st.error(t('access_update_failed'))


def render_category_order_editor(client,session):
    st.subheader(t('category_order'))
    st.caption(t('category_order_hint'))
    order=st.session_state.setdefault('category_order_draft',list(current_category_order()))
    order=category_order(order)
    selected=st.selectbox(t('category_to_move'),order,format_func=lambda c:t('doc_'+c),key='category_to_move')
    index=order.index(selected)
    up,down,save=st.columns(3)
    for column,delta,label in ((up,-1,'move_up'),(down,1,'move_down')):
        if column.button(t(label),disabled=not 0<=index+delta<len(order),width='stretch'):
            order[index],order[index+delta]=order[index+delta],order[index]
            st.session_state.category_order_draft=order
            st.rerun()
    if save.button(t('save_order'),type='primary',width='stretch'):
        try:
            accounts.save_upload_category_order(client,session,order)
            st.session_state.category_order_cache=(time.monotonic(),order)
            st.success(t('order_saved'))
        except Exception:st.error(t('access_update_failed'))
    st.caption(' → '.join(f'{i+1}. {t("doc_"+category)}' for i,category in enumerate(order)))


def render_bank_budget(result):
    from finance_review import assess_budget
    with st.container(border=True):
        st.subheader(t('bank_budget'))
        st.caption(t('bank_scope'))
        controls,note=st.columns([1,2],vertical_alignment='center')
        allowance=controls.number_input(t('daily_allowance'),min_value=0.0,max_value=2000.0,
            value=75.0,step=5.0,key='daily_budget_'+result.get('hash','report'),help=t('allowance_hint'))
        original=result['budget']
        # Reuse the exchange snapshot used for this review.
        budget=assess_budget(result['extraction'],allowance,rates=result.get('exchange_snapshot'))
        if budget!=original:result.pop('pdfs',None)
        result['budget']=budget
        note.caption(t('budget_scope'))
        balances,trip=st.columns(2,gap='large')
        if not budget['balances']:balances.warning(t('balance_unreadable'))
        for bank in budget['balances']:
            value=f"{bank['balance']:,.2f} {bank['currency'] or ''}"
            balances.metric(t('balance_'+bank['balance_type']),value)
            if bank['eur'] is not None:balances.caption(f"≈ EUR {bank['eur']:,.2f}")
            if bank['statement_date']:balances.caption(t('statement_date')+': '+bank['statement_date'])
            if bank['holder_name']:balances.caption(bank['holder_name'])
            balances.write(t('budget_'+bank['status']))
        trip.metric(t('budget_total'),f"EUR {budget['known_budget_eur']:,.2f}")
        for cost in budget['costs']:
            trip.text(t('doc_'+cost['category'])+f": {cost['amount']:,.2f} {cost['currency']}"+(' · '+t('paid_excluded') if cost['paid'] else ''))
        trip.caption(t('allowance_total',days=budget['days'] or '?',amount=f"{budget['allowance_eur'] or 0:,.2f}"))
        if budget['missing']:
            trip.warning(t('budget_missing')+': '+', '.join(t('budget_missing_'+key) for key in budget['missing']))
        if budget.get('rate_date'):
            st.caption(t('budget_rate_date',date=budget['rate_date']))
            st.markdown('[Rates By Exchange Rate API](https://www.exchangerate-api.com)')




@st.fragment(run_every='15s')
def maintenance_refresh():
    try:
        if not _service_controls(force=True)['maintenance_enabled']:
            st.rerun()
    except AccountError:
        pass


def render_maintenance_page():
    st.title(t('maintenance_title'))
    st.info(t('maintenance_message'))
    maintenance_refresh()
    if st.button(t('check_service'),key='check_service'):
        st.session_state.pop('service_snapshot',None)
        st.rerun()




def render_how_it_works():
    st.title(t("how")); st.write(t("how_description"))
    for step,key in zip(("step_read","step_rules","step_business","step_score"),("how_read","how_rules","how_business","how_score")):
        with st.container(border=True,key="card_how_"+step):
            st.subheader(t(step)); st.write(t(key))
    st.caption(t("upload_formats"))
    st.caption(t("privacy")); st.caption(t("score_note"))


def main():
    _init_session_state()
    initialize_monitoring()
    render_header()
    if not all(setting(key) for key in ("SUPABASE_URL","SUPABASE_ANON_KEY","SUPABASE_SERVICE_ROLE_KEY")):
        st.error(t("config_missing")); return
    try:
        controls=_service_controls()
    except AccountError:
        st.error(t('service_unavailable')); return
    maintenance=controls['maintenance_enabled']
    st.session_state.maintenance_active=maintenance
    if not maintenance and handle_recovery(): return
    _restore_session_from_params()
    if not session_resume.hydrate(get_auth_client):
        st.caption(t('restoring_session'))
        return
    notice=st.session_state.pop("notice",None)
    if notice: st.info(t(notice))
    if not st.session_state.supabase_session:
        if maintenance:
            render_maintenance_page()
            with st.expander(t('management_sign_in')):
                render_auth_screen(management_only=True)
        else:
            render_auth_screen()
        return
    try:
        actor=_refresh_actor()
    except AccountError as exc:
        if str(exc)=="session_expired":
            _clear_local_session("session_expired"); st.rerun()
        st.error(t(str(exc))); return
    st.session_state.watchdog_full_run=True
    session_watchdog()
    if maintenance:
        st.session_state.review_requested=False
        st.session_state.review_result=None
        st.session_state.review_cache={}
        st.session_state.pop('document_cache',None)
        if not (actor.approved and actor.role=='super_admin'):
            render_maintenance_page()
            if st.button(t('sign_out')):
                _supabase_sign_out(); st.rerun()
            return
        st.warning(t('maintenance_message'))
        render_admin_dashboard()
        return
    if not actor.approved:
        st.session_state.review_requested=False
        st.session_state.review_result=None
        st.session_state.review_cache={}
        st.session_state.pop('document_cache',None)
        render_pending_screen(); return
    render_workspace()


@st.fragment
def render_workspace():
    """Keep navigation and document controls independent of session polling."""
    actor=st.session_state.get('actor')
    if not actor or not actor.approved or st.session_state.get('maintenance_active'):
        st.rerun()
    try:
        _render_workspace(actor)
    except Exception as exc:
        reference=capture_error(exc,'page')
        logger.error('Page failed; reference=%s',reference)
        st.error(t('review_failed',reference=reference))


def _render_workspace(actor):
    nav,out=st.columns([5,1])
    pages=["review","history","how"]+(["admin"] if actor.role in ("admin","super_admin") else [])
    if st.session_state.get("current_page") not in pages:
        st.session_state.current_page="review"
    with nav:
        page=st.segmented_control(t("navigation"),pages,format_func=t,key="current_page",required=True)
    with out:
        if st.button(t("sign_out"),width="stretch"):
            _supabase_sign_out(); st.rerun()
    st.html('<span class="muted ltr">'+escape((actor.username+" · " if actor.username else "")+actor.email)+'</span>')
    if page!='review':st.session_state.review_requested=False
    if page=="history": render_my_history(); return
    if page=="admin": render_admin_dashboard(); return
    if page=="how": render_how_it_works(); return
    upload_form=render_upload_ui()
    if upload_form is None:
        return
    uploaded,client=upload_form
    request=st.session_state.pop('review_requested',None)
    scope=current_review_scope()
    if (isinstance(request,dict) and request['scope']==scope and request['lang']==st.session_state.lang
            and request['generation']==st.session_state.upload_generation):
        uploaded,client=request['uploaded_files'],request['client_name']
        with st.spinner(t('review_starting'),show_time=True):
            run_review(uploaded,client)
    result=st.session_state.review_result
    if result:
        if result["hash"]!=_compute_upload_hash(uploaded) or result["client_name"]!=client.strip():
            st.info(t("stale_result"))
        else:
            render_report(result)


if __name__=="__main__":
    try:
        main()
    except Exception as exc:
        reference=capture_error(exc,'page')
        logger.error('Page failed; reference=%s',reference)
        st.error(t('review_failed',reference=reference))
