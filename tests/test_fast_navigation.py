"""Network polling must never hold the page rendering thread."""
from concurrent.futures import Future
from types import SimpleNamespace
from unittest.mock import Mock
import subprocess
import sys
import time

from streamlit.testing.v1 import AppTest
import accounts
import session_poll
from uploads import CATEGORIES


ACTOR=accounts.Actor('synthetic-user','synthetic@example.com',True,'user')
CONTROLS=dict(maintenance_enabled=False,reviews_enabled=True)


def watchdog_ui():
    ui=AppTest.from_string('''
import app,streamlit as st
app._init_session_state()
if st.session_state.actor and st.session_state.actor.approved:
    app.session_watchdog()
else:
    st.text('Access check required')
''')
    ui.session_state.auth_client=object()
    ui.session_state.supabase_session=SimpleNamespace(access_token='synthetic-token',expires_at=time.time()+1000)
    ui.session_state.actor=ACTOR
    return ui


def test_pending_status_read_never_blocks_or_starts_duplicate_requests(monkeypatch):
    pending=Future()
    start=Mock(return_value=pending)
    monkeypatch.setattr(session_poll,'start',start)
    monkeypatch.setattr(accounts,'refresh_if_needed',lambda client,session:session)
    ui=watchdog_ui();ui.run();ui.run()
    assert not ui.exception and start.call_count==1
    assert ui.session_state.actor==ACTOR and not pending.done()


def test_unchanged_poll_updates_snapshots_without_clearing_the_review():
    future=Future();future.set_result((CONTROLS,ACTOR))
    ui=watchdog_ui()
    ui.session_state.watchdog_pending=('synthetic-token',time.monotonic(),future)
    ui.session_state.watchdog_next_check=time.monotonic()+15
    ui.session_state.review_result={'synthetic':'kept'}
    ui.run()
    assert not ui.exception and ui.session_state.review_result=={'synthetic':'kept'}
    assert ui.session_state.actor_snapshot[2]==ACTOR
    assert ui.session_state.service_snapshot[1]==CONTROLS


def test_revocation_clears_private_results_and_reroutes_immediately():
    future=Future();future.set_result((CONTROLS,accounts.Actor(ACTOR.user_id,ACTOR.email,False,'user')))
    ui=watchdog_ui()
    ui.session_state.watchdog_pending=('synthetic-token',time.monotonic(),future)
    ui.session_state.review_result={'synthetic':'private'}
    ui.session_state.review_cache={'synthetic':(0,object())}
    ui.session_state.document_cache=object()
    ui.run()
    assert not ui.exception and not ui.session_state.review_result and not ui.session_state.review_cache
    assert 'document_cache' not in ui.session_state
    assert ui.text[0].value=='Access check required'


def test_status_from_a_replaced_token_cannot_restore_old_permissions():
    future=Future();future.set_exception(accounts.AccountError('session_expired'))
    ui=watchdog_ui()
    ui.session_state.watchdog_pending=('replaced-token',time.monotonic(),future)
    ui.run()
    assert not ui.exception and ui.session_state.actor==ACTOR
    assert ui.session_state.supabase_session.access_token=='synthetic-token'
    assert ui.session_state.watchdog_next_check==0


def test_poll_failure_invalidates_authorization_snapshot_before_rerouting():
    future=Future();future.set_exception(accounts.AccountError('auth_unavailable'))
    ui=watchdog_ui()
    ui.session_state.actor_snapshot=(time.monotonic(),'synthetic-token',ACTOR)
    ui.session_state.watchdog_pending=('synthetic-token',time.monotonic(),future)
    ui.run()
    assert not ui.exception and 'actor_snapshot' not in ui.session_state
    assert ui.session_state.actor is None
    assert ui.text[0].value=='Access check required'


def test_inflight_poll_cannot_override_a_more_recent_action_check():
    future=Future();future.set_exception(accounts.AccountError('session_expired'))
    ui=watchdog_ui()
    ui.session_state.watchdog_pending=('synthetic-token',time.monotonic()-1,future)
    ui.session_state.actor_snapshot=(time.monotonic(),'synthetic-token',ACTOR)
    ui.run()
    assert not ui.exception and ui.session_state.actor==ACTOR
    assert ui.session_state.watchdog_next_check==0


def test_poll_worker_uses_only_explicit_token_and_live_checks(monkeypatch):
    verify=Mock(return_value=ACTOR)
    controls=Mock(return_value=CONTROLS)
    monkeypatch.setattr(accounts,'verified_actor',verify)
    monkeypatch.setattr(accounts,'service_controls',controls)
    client=object()
    assert session_poll._read(client,'synthetic-token')==(CONTROLS,ACTOR)
    verify.assert_called_once()
    assert verify.call_args.args[0] is client
    assert vars(verify.call_args.args[1])=={'access_token':'synthetic-token'}
    assert verify.call_args.kwargs=={'require_approved':False}


def test_service_settings_also_supply_card_order_without_extra_queries(monkeypatch):
    controls=Mock(return_value={**CONTROLS,'upload_category_order':list(reversed(CATEGORIES))})
    order=Mock(side_effect=AssertionError('Extra settings/auth query'))
    monkeypatch.setattr(accounts,'service_controls',controls)
    monkeypatch.setattr(accounts,'upload_category_order',order)
    ui=AppTest.from_string('''
import app,streamlit as st
app._init_session_state()
app._service_controls()
st.session_state.order=app.current_category_order()
''').run()
    assert not ui.exception and ui.session_state.order==list(reversed(CATEGORIES))
    controls.assert_called_once();order.assert_not_called()


def test_page_import_does_not_load_document_or_ocr_engines():
    subprocess.run([sys.executable,'-c',
        "import app,sys; assert not {'review_pipeline','pdf_report','extractor','offline_ocr'} & sys.modules.keys()"],
        check=True,capture_output=True,timeout=15)
