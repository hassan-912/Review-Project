"""MG's bilingual Schengen document-review workspace."""
from __future__ import annotations

from html import escape
import csv
from io import StringIO
import logging
import time
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st
from i18n import t, field_label, document_label, issue_text, isolated_value, STRINGS

st.set_page_config(page_title=t("brand", "en"), page_icon=":material/fact_check:", layout="wide")

import accounts
from accounts import AccountError
from settings import setting
from extractor import AVAILABLE_MODELS
from uploads import CATEGORIES, files_hash, validate_uploads, category_order, upload_thumbnail
from theme import inject_theme
from pdf_report import build_pdf_report, score_badge
from review_pipeline import review_documents
from validator import _parse_date, accommodation_window, _SCHENGEN_CITIES
from recovery import recovery_tokens
from writing_review import writing_recommendations
from evidence import render_source
from model_routing import ModelUnavailable
from finance_review import assess_budget

logger = logging.getLogger(__name__)


def _init_session_state():
    defaults = {"lang":"en", "auth_client":None, "supabase_session":None, "actor":None,
                "review_result":None, "review_cache":{}, "notice":None, "upload_generation":0,
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
    lang = st.session_state.get("lang", "en")
    for key in list(st.session_state):
        del st.session_state[key]
    st.session_state.lang = lang
    st.session_state.notice = notice
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


def _refresh_actor():
    client = get_auth_client()
    session = accounts.refresh_if_needed(client, st.session_state.supabase_session)
    st.session_state.supabase_session = session
    actor = accounts.verified_actor(client, session, require_approved=False)
    st.session_state.actor = actor
    return actor


@st.fragment(run_every="60s")
def session_watchdog():
    if not st.session_state.get("supabase_session"):
        return
    try:
        previous = st.session_state.actor
        actor = _refresh_actor()
        if previous and (previous.approved != actor.approved or previous.role != actor.role):
            st.session_state.review_result = None
            st.session_state.review_cache = {}
            st.rerun()
    except AccountError as exc:
        if str(exc) == "session_expired":
            _clear_local_session("session_expired")
        else:
            st.session_state.actor = None
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


def render_auth_screen():
    st.caption(t("internal"))
    st.title(t("access_title"))
    st.write(t("access_description"))
    left, right = st.columns([1.15,1], gap="large")
    with left, st.container(border=True,key="card_access"):
        mode = st.segmented_control(t("navigation"), ["sign_in","create_account","forgot_password"],
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
            if mode == "create_account" and (len(password) < 8 or password != confirm):
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
        render_pending_screen(standalone=True)
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
        if len(password) < 8 or password != confirm:
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


def _compute_upload_hash(uploaded_files, model_id, lang=None):
    return files_hash(uploaded_files, model_id, lang or st.session_state.lang)


def _compute_files_hash(uploaded_files, model_id=None, lang=None):
    return _compute_upload_hash(uploaded_files, model_id or AVAILABLE_MODELS[0], lang)


def render_pipeline_stepper(active_step=1):
    cells=[]
    for index,key in enumerate(("step_read","step_rules","step_business","step_score"),1):
        state="done" if index < active_step else "in_progress" if index == active_step else "waiting"
        active=' active' if state == "in_progress" else ''
        cells.append(f'<div class="step{active}"><span class="muted ltr">0{index}</span><h4>{escape(t(key))}</h4>{pill(state)}</div>')
    st.html('<div class="stepper">'+''.join(cells)+'</div>')


def render_upload_ui():
    st.title(t("review_title"))
    st.write(t("review_description"))
    client_name = st.text_input(t("client_name"), placeholder=t("client_placeholder"),max_chars=150,key="client_name")
    with st.expander(t("advanced")):
        st.caption(t("auto_models"))
        force = st.checkbox(t("force_refresh"),help=t("force_help"),key="force_refresh")
    st.subheader(t("upload_title"))
    st.caption(t("upload_hint"))
    st.caption(t("combined_hint"))
    uploaded={}
    icons=dict(zip(CATEGORIES,("badge","description","article","hotel","flight","health_and_safety","work","map","account_balance","folder")))
    order=current_category_order()
    for offset in range(0, len(order),3):
        columns=st.columns(3)
        for index, category in enumerate(order[offset:offset+3],offset):
            widget_key=f"upload_{st.session_state.upload_generation}_{category}"
            previous=st.session_state.get(widget_key)
            with columns[index % 3], st.container(border=True, key=("slot_filled_" if previous else "slot_empty_")+category):
                st.markdown(f':material/{icons[category]}: **{t("doc_"+category)}**')
                if category=='bank_statement':st.caption(t('bank_scope'))
                files=st.file_uploader(t("doc_"+category),type=["pdf","jpg","jpeg","png","webp"],
                                       accept_multiple_files=True,key=widget_key,max_upload_size=20,label_visibility="collapsed")
                if files:
                    uploaded[category]=[(f.name,f.getvalue()) for f in files]
                    st.html('<span class="pill added">'+escape(t("files_added",count=len(files)))+'</span>')
                    render_upload_thumbnails(uploaded[category],category)
                else:
                    st.caption(t("choose_files"))
    st.caption(t("privacy"))
    import hashlib
    active_previews={(category,hashlib.sha256(raw).hexdigest()) for category,group in uploaded.items() for _,raw in group}
    if 'upload_thumbnails' in st.session_state:
        st.session_state.upload_thumbnails={k:v for k,v in st.session_state.upload_thumbnails.items() if k in active_previews}
    st.caption(t("log_notice"))
    missing=[category for category in CATEGORIES if category not in uploaded]
    if missing:
        with st.expander(t("missing_documents")):
            st.write(", ".join(t("doc_"+category) for category in missing))
            st.caption(t("missing_hint"))
    return uploaded,"auto",client_name,force


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


def render_upload_thumbnails(files,category):
    import hashlib
    cache=st.session_state.setdefault('upload_thumbnails',{})
    for name,raw in files:
        digest=hashlib.sha256(raw).hexdigest();key=(category,digest)
        if key not in cache:
            if len(cache)>=30:cache.pop(next(iter(cache)))
            try:cache[key]=upload_thumbnail(name,raw,category)
            except ValueError:cache[key]=None
        if cache[key]:
            image,page,pages=cache[key]
            preview,label=st.columns([1,2],vertical_alignment='center')
            preview.image(image,width='stretch')
            label.text(name)
            label.caption(t('upload_preview',page=page,pages=pages,size=f'{len(raw)/1024:.0f}'))
        else:
            st.caption(name+' · '+t('preview_unavailable'))


def run_review(uploaded_files,model_id,client_name,force_refresh=False):
    st.session_state.review_result=None
    client_name=client_name.strip()
    if not client_name or len(client_name)>150:
        st.error(t("client_required")); return
    if model_id != "auto":
        st.error(t("config_missing")); return
    try:
        validate_uploads(uploaded_files)
    except ValueError as exc:
        st.error(t(str(exc) if str(exc) in STRINGS else "upload_invalid")); return
    if not setting("GEMINI_API_KEY"):
        st.error(t("config_missing")); return
    key=_compute_upload_hash(uploaded_files,model_id)
    now=time.monotonic()
    cache={k:v for k,v in st.session_state.review_cache.items() if now-v[0]<1800}
    st.session_state.review_cache=cache
    progress=st.empty(); skeleton=st.empty()
    attempt_id=None
    attempt_finished=False
    attempt_score=None
    try:
        _refresh_actor()
        client=get_auth_client(); session=st.session_state.supabase_session
        accounts.verified_actor(client,session)
        if key in cache and not force_refresh:
            result=cache[key][1].copy()
            st.info(t("cached"))
        else:
            attempt_id=str(uuid.uuid4())
            accounts.reserve_review(client,session,request_id=attempt_id,client_name=client_name)
            skeleton.html('<div class="skeleton"><i></i><i></i><i></i></div>')
            def update(step):
                with progress.container():
                    render_pipeline_stepper(step)
            router=accounts.model_router(client,session)
            result=review_documents(setting("GEMINI_API_KEY"),uploaded_files,model_id,st.session_state.lang,update,router=router)
            if len(cache)>=3:
                cache.pop(next(iter(cache)))
            cache[key]=(now,result.copy())
        result.update({"client_name":client_name,"hash":key})
        # Refresh again after a long model call, then verify approval before showing evidence.
        _refresh_actor()
        accounts.verified_actor(client,st.session_state.supabase_session)
        st.session_state.review_result=result
        attempt_score=result["score"].score
        if attempt_id:
            try:
                accounts.finish_attempt(client,st.session_state.supabase_session,attempt_id,result["score"].score)
                attempt_finished=True
            except Exception:
                st.warning(t("log_failed"))
        try:
            accounts.log_review(client,st.session_state.supabase_session,client_name,
                                result["extraction"].main_schengen_destination,result["score"].score)
        except Exception:
            st.warning(t("log_failed"))
        st.success(t("review_complete"))
    except AccountError as exc:
        st.error(t(str(exc)))
    except ModelUnavailable:
        st.error(t("models_unavailable"))
    except Exception:
        reference=uuid.uuid4().hex[:10]
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
    from validator import employment_applies
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
        if category=="hotel" and any(i.field_name in ("hotel_coverage_gap","hotel_date_order","check_in_date","check_out_date") for i in issues):
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
    st.subheader(t("checklist"))
    options=["all","critical","high","medium","low"]
    severity=st.pills(t("severity"),options,default="all",format_func=t,key="severity_filter") or "all"
    filtered=[i for i in issues if severity=="all" or i.severity.value.lower()==severity]
    if not filtered:
        st.info(t("no_issues") if not issues else t("no_results"))
    for index,issue in enumerate(filtered):
        title,fix=issue_text(issue,st.session_state.lang)
        with st.container(border=True,key=f"card_issue_{index}"):
            if issue.affects_score:
                st.html(pill(issue.severity.value.lower()))
            else:
                st.caption(t('review_limitation'))
            st.caption(document_label(issue.document_name,st.session_state.lang))
            st.markdown('**'+escape(title)+'**')
            st.text(fix)
            # Stable key follows the issue across severity filtering. Crops render only on demand.
            issue_index=next(i for i,v in enumerate(issues) if v is issue)
            with st.expander(t("evidence"),key=f'evidence_{(result or {}).get("hash", "report")}_{issue_index}',on_change="rerun") as panel:
                if panel.open:
                    st.caption(t("evidence_note"))
                    source,expected=st.columns(2)
                    with source:
                        st.markdown("**"+t("source_left")+"**")
                        st.text(t("found")+": "+isolated_value(issue.found_value or t("unknown"),st.session_state.lang))
                        render_evidence_images(issue.evidence,result or {},"source")
                    with expected:
                        st.markdown("**"+t("correction_right")+"**")
                        st.text(t("expected")+": "+isolated_value(issue.expected_value,st.session_state.lang))
                        render_evidence_images(issue.reference_evidence,result or {},"reference")


def render_report(result):
    data,issues,score=result["extraction"],result["issues"],result["score"]
    for booking in data.booking_statuses:
        st.info(t('doc_'+booking.category)+': '+t('booking_'+booking.status))
    if result.get('budget') is not None:
        render_bank_budget(result)
    findings = [issue for issue in issues if issue.affects_score]
    limitations = [issue for issue in issues if not issue.affects_score]
    left,right=st.columns([1,1.6],gap="large")
    with left:
        with st.container(border=True,key="card_score"):
            st.caption(t("score_title"))
            st.html(f'<div class="score-number ltr">{score.score:.0f}%</div>')
            badge='review_incomplete' if score.provisional else score_badge(score.score)
            color="success" if score.score>=85 else "medium" if score.score>=65 else "high"
            st.html(pill(badge,color))
            (st.error if score.readiness=="not_ready" else st.info if score.readiness in ("needs_attention",'review_incomplete') else st.success)(t(score.readiness))
            st.caption(t("score_note"))
        with st.container(border=True,key="card_urgent"):
            st.subheader(t("urgent"))
            if findings:
                for index,issue in enumerate(findings[:3],1):
                    title,fix=issue_text(issue,st.session_state.lang)
                    st.markdown(f'**{index}. {escape(title)}**')
                    st.text(fix)
            else:
                st.write(t("no_issues"))
        with st.container(border=True,key="card_timeline"):
            render_travel_date_timeline(data,issues)
    with right:
        with st.container(border=True,key="card_summary"):
            st.subheader(t("summary"))
            st.text(data.executive_summary or (t("summary_fallback",count=len(issues)) if issues else t("no_issues")))
            st.caption(result["client_name"])
            if result["biz_result"].is_business_visa:
                st.info(t("business_match" if result["biz_result"].fields_match else "business_check"))
            else:
                st.caption(t("tourism"))
                known=bool(data.travel_cities) and all(c.lower() in _SCHENGEN_CITIES for c in data.travel_cities)
                st.write(t("tourism_known" if known else "tourism_check"))
        render_fix_checklist(findings,result)
    if limitations:
        st.subheader(t('review_limitations'))
        st.caption(t('review_limitation'))
        for limitation in limitations:
            st.info(limitation.recommended_fix)
    if quality:=result.get("quality"):
        st.subheader(t("quality_title"))
        complete,pages,model=st.columns(3)
        complete.metric(t("completeness"),f'{quality["completeness"]}%')
        pages.metric(t("pages_read"),f'{quality["pages_reported_read"]} / {quality["pages_total"]}')
        model.caption(t("model_used")); model.text(result.get("model_used",t("unknown")))
        st.caption(t("quality_note"))
        with st.expander(t("source")):
            for item in quality["files"]:
                st.text(f'{item["file"]} · {item["pages_read"]} / {item["pages"]}')
                for uncertainty in item.get("uncertainties",[]): st.text(uncertainty)
    if data.supporting_documents:
        st.subheader(t("supporting_title")); st.caption(t("supporting_note"))
        for doc in data.supporting_documents:
            with st.expander(doc.source_file):
                st.text(doc.document_type); st.text(doc.summary)
                for claim in doc.claims:
                    st.markdown("**"+t(claim.assessment)+"**")
                    st.text(field_label(claim.field_name,st.session_state.lang)+": "+(claim.value or t("unknown")))
                    if claim.quote: st.text(claim.quote)
                    if claim.page: st.caption(t("page")+" "+str(claim.page))
                    if claim.reason: st.text(claim.reason)
                    if claim.compared_with: st.caption(t("source")+": "+claim.compared_with)
    writing=result.get("writing") or writing_recommendations(data,st.session_state.lang)
    st.subheader(t("writing_title"))
    st.caption(t("writing_note"))
    for column,key in zip(st.columns(2),("cover_letter","travel_plan")):
        with column,st.container(border=True,key="card_writing_"+key):
            st.subheader(t("doc_"+key))
            section=data.cover_letter_text if key=="cover_letter" else data.travel_plan
            if section.source_files:
                st.text(t("source")+": "+", ".join(section.source_files))
            if not writing[key]:
                st.write(t("writing_ok"))
            for edit in writing[key]:
                st.markdown("**"+t("edit_"+edit.action)+"**")
                if edit.day: st.text(t("day")+": "+edit.day)
                if edit.source_file:
                    st.text(edit.source_file+(f" · {edit.page}" if edit.page else ""))
                if edit.original_text:
                    st.text(t("original_text")+": "+edit.original_text)
                st.text(edit.reason)
                if edit.replacement:
                    st.text(t("replacement")+": "+edit.replacement)
    audit_left,audit_right=st.columns(2)
    with audit_left,st.expander(t("cover_audit")):
        for key in ("purpose_of_visit","funding_source","ties_to_home_country","attached_documents_listed","employer_mentioned"):
            status="present" if getattr(data.cover_letter,key) else "missing"
            st.write(field_label(key,st.session_state.lang)+": "+t(status))
    from validator import employment_applies
    if employment_applies(data):
        with audit_right,st.expander(t("employment_audit")):
            for key in ("employer_name","job_title","monthly_salary","approved_leave_start","approved_leave_end","leave_approval_confirmed"):
                value=getattr(data.employment,key)
                if isinstance(value,bool): value=t("yes" if value else "no")
                st.text(field_label(key,st.session_state.lang)+": "+isolated_value(value or t("unknown"),st.session_state.lang))
    with st.expander(t("extracted")):
        for key in ("full_name","given_names","surname","passport_number","date_of_birth","passport_issue","passport_expiry"):
            st.text(field_label(key,st.session_state.lang)+": "+isolated_value(getattr(data.passport,key) or t("unknown"),st.session_state.lang))
        if data.raw_extraction_notes: st.text(data.raw_extraction_notes)
    try:
        pdfs=result.setdefault("pdfs",{})
        if st.session_state.lang not in pdfs:
            pdfs[st.session_state.lang]=build_pdf_report(data,issues,score,result["biz_result"],st.session_state.lang,result["client_name"],writing,budget=result.get('budget'))
        pdf=pdfs[st.session_state.lang]
        st.download_button(t("download_pdf"),pdf,file_name="MG-review.pdf",mime="application/pdf",icon=":material/download:")
    except Exception:
        st.warning(t("pdf_failed"))


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
        st.download_button(t("export_csv"),buffer.getvalue().encode("utf-8-sig"),file_name="MG-reviews.csv",mime="text/csv",key=key_prefix+"_csv")


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
    try:
        client=get_auth_client(); session=st.session_state.supabase_session
        profiles=accounts.team_profiles(client,session)
        rows=normalized_logs(accounts.review_logs(client,session,team=True))
        attempts=normalized_logs(accounts.team_attempts(client,session))
    except Exception:
        st.error(t("history_failed")); return
    pending=sum(not p.get("is_approved") for p in profiles)
    columns=st.columns(3)
    for column,key,value in zip(columns,("total_reviews","pending_count","average_score"),
                                (len(rows),pending,f'{sum(r["latest_score"] for r in rows if isinstance(r["latest_score"],(int,float)))/len(rows):.0f}%' if rows else "—")):
        column.metric(t(key),value,border=True)
    st.caption(t("log_scope",count=len(rows)))
    st.subheader(t("approval_queue"))
    for profile in sorted(profiles,key=lambda p:bool(p.get("is_approved"))):
        with st.container(border=True,key="card_profile_"+profile["id"]):
            identity,action=st.columns([4,1])
            with identity:
                st.text(profile.get("username") or profile.get("email") or profile["id"])
                st.text(profile.get("email") or "")
                st.caption(t(profile.get("role","user")))
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
                with st.expander(t("role")+" / "+t("daily_limit")):
                    with st.form("permissions_"+profile["id"]):
                        roles=["user","admin","super_admin"]
                        role=st.selectbox(t("role"),roles,index=roles.index(profile.get("role","user")),format_func=t,key="role_"+profile["id"])
                        approved=st.checkbox(t("approved"),value=bool(profile.get("is_approved")),key="approved_"+profile["id"])
                        hour=st.number_input(t("hourly_limit"),1,100,value=profile.get("hourly_limit",5),key="hour_"+profile["id"])
                        day=st.number_input(t("daily_limit"),1,1000,value=profile.get("daily_limit",20),key="day_"+profile["id"])
                        if st.form_submit_button(t("save_changes")):
                            try:
                                accounts.super_update(client,session,profile["id"],role,approved,hour,day)
                                st.session_state.notice="access_updated"; st.rerun()
                            except AccountError as exc:
                                st.error(t(str(exc)))
    if st.session_state.actor.role=="super_admin":
        render_category_order_editor(client,session)
        render_model_dashboard(client,session)
    st.subheader(t("review_log"))
    render_logs(rows,team=True)
    with st.expander(t("attempts")):
        st.caption(t("attempts_hint"))
        render_logs(attempts,team=True,key_prefix="attempts")


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
    with st.container(border=True):
        st.subheader(t('bank_budget'))
        st.caption(t('bank_scope'))
        controls,note=st.columns([1,2],vertical_alignment='center')
        allowance=controls.number_input(t('daily_allowance'),min_value=0.0,max_value=2000.0,
            value=75.0,step=5.0,key='daily_budget_'+result.get('hash','report'),help=t('allowance_hint'))
        original=result['budget']
        # Reuse the exchange snapshot used for this review; no extra model call.
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


def render_model_dashboard(client,session):
    st.subheader(t("model_dashboard"))
    if st.button(t("refresh_usage")): st.rerun()
    try:
        snapshot=accounts.model_dashboard(client,session)
    except Exception:
        st.error(t("history_failed")); return
    st.caption(t("quota_note"))
    reset=datetime.fromisoformat(snapshot["day_resets_at"]).astimezone(ZoneInfo("Africa/Cairo"))
    st.caption(t("quota_reset",date=reset.strftime("%Y-%m-%d %H:%M")))
    with st.form("app_controls"):
        enabled=st.checkbox(t("reviews_enabled"),value=snapshot["reviews_enabled"])
        if st.form_submit_button(t("save_changes")):
            try:
                accounts.set_reviews_enabled(client,session,enabled)
                st.session_state.notice="access_updated"; st.rerun()
            except Exception:
                st.error(t("access_update_failed"))
    for model in snapshot["models"]:
        with st.container(border=True):
            st.markdown("**"+model["model"]+"**")
            used,left,errors=st.columns(3)
            used.metric(t("requests_today"),model["requests_today"])
            left.metric(t("remaining_today"),max(0,model["rpd"]-model["requests_today"]))
            errors.metric(t("errors_today"),model["errors_today"])
            st.caption(f'{t("requests_minute")}: {model["requests_minute"]} / {model["rpm"]} · {t("tokens_minute")}: {model["tokens_minute"]} / {model["tpm"]}')
            st.caption(f'{t("input_tokens_today")}: {model["input_tokens_today"]} · {t("output_tokens_today")}: {model["output_tokens_today"]} · {t("pending_today")}: {model["pending_today"]}')
            st.caption(t("quota_source")+": "+model["quota_source"]+" · "+model["quota_checked_at"][:10])
            if model.get("cooldown_until") and datetime.fromisoformat(model["cooldown_until"])>datetime.now(ZoneInfo("UTC")):
                st.info(t("cooldown",date=datetime.fromisoformat(model["cooldown_until"]).astimezone(ZoneInfo("Africa/Cairo")).strftime("%Y-%m-%d %H:%M")))
            with st.expander(t("advanced")):
                with st.form("model_"+model["model"]):
                    on=st.checkbox(t("enabled"),value=model["enabled"])
                    priority=st.number_input(t("priority"),1,100,value=model["priority"])
                    lite=model["model"].endswith("flash-lite")
                    rpm=st.number_input(t("rpm"),1,15 if lite else 5,value=model["rpm"])
                    tpm=st.number_input(t("tpm"),1,250000,value=model["tpm"])
                    rpd=st.number_input(t("rpd"),1,500 if lite else 20,value=model["rpd"])
                    if st.form_submit_button(t("save_changes")):
                        try:
                            accounts.configure_model(client,session,model["model"],on,priority,rpm,tpm,rpd)
                            st.session_state.notice="access_updated"; st.rerun()
                        except AccountError as exc:
                            st.error(t(str(exc)))
    with st.expander(t("admin_audit")):
        st.dataframe(snapshot["audit"],hide_index=True)


def render_how_it_works():
    st.title(t("how")); st.write(t("how_description"))
    for step,key in zip(("step_read","step_rules","step_business","step_score"),("how_read","how_rules","how_business","how_score")):
        with st.container(border=True,key="card_how_"+step):
            st.subheader(t(step)); st.write(t(key))
    st.caption(t("privacy")); st.caption(t("score_note"))


def main():
    _init_session_state()
    render_header()
    if not all(setting(key) for key in ("SUPABASE_URL","SUPABASE_ANON_KEY","SUPABASE_SERVICE_ROLE_KEY")):
        st.error(t("config_missing")); return
    if handle_recovery(): return
    _restore_session_from_params()
    notice=st.session_state.pop("notice",None)
    if notice: st.info(t(notice))
    if not st.session_state.supabase_session:
        render_auth_screen(); return
    try:
        actor=_refresh_actor()
    except AccountError as exc:
        if str(exc)=="session_expired":
            _clear_local_session("session_expired"); st.rerun()
        st.error(t(str(exc))); return
    session_watchdog()
    if not actor.approved:
        st.session_state.review_result=None
        st.session_state.review_cache={}
        render_pending_screen(); return
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
    if page=="history": render_my_history(); return
    if page=="admin": render_admin_dashboard(); return
    if page=="how": render_how_it_works(); return
    uploaded,model,client,force=render_upload_ui()
    run,clear=st.columns([3,1])
    if clear.button(t("clear_files"),width="stretch"):
        st.session_state.upload_generation+=1
        st.session_state.review_result=None
        st.session_state.review_cache={}
        st.rerun()
    if run.button(t("run_review"),type="primary",icon=":material/fact_check:",disabled=not uploaded,width="stretch"):
        run_review(uploaded,model,client,force)
    result=st.session_state.review_result
    if result:
        if result["hash"]!=_compute_upload_hash(uploaded,model) or result["client_name"]!=client.strip():
            st.info(t("stale_result"))
        else:
            render_report(result)


if __name__=="__main__":
    main()
