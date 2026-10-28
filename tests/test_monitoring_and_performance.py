"""Privacy boundaries and remote work avoided during ordinary UI reruns."""
import json
import time
from types import SimpleNamespace
from unittest.mock import Mock

from streamlit.testing.v1 import AppTest
import accounts
import monitoring
from extractor import VisaDocumentExtraction,extract_documents
from local_extraction import guard_local_issues
from tests.test_local_review_pipeline import pdf
from validator import ValidationIssue,Severity


def test_event_payload_never_contains_client_evidence_or_credentials():
    secret='PRIVATE_PASSPORT_AND_TOKEN'
    event=dict(event_id='a'*32,platform='python',level='error',
        user={'email':secret},request={'data':secret},extra={'files':secret},
        message=secret,breadcrumbs={'values':[{'message':secret}]},attachments=[secret],
        contexts={'trace':{'data':secret}},tags={'operation':'review','support_reference':'safe','client':secret},
        exception={'values':[dict(type='ValueError',value=secret,stacktrace={'frames':[
            dict(filename=r'C:\Users\PRIVATE_PASSPORT_AND_TOKEN\app.py',abs_path=secret,
                 function='run_review',lineno=47,vars={'raw':secret},pre_context=[secret],context_line=secret)]})]})
    clean=monitoring.scrub_event(event)
    assert secret not in json.dumps(clean)
    frame=clean['exception']['values'][0]['stacktrace']['frames'][0]
    assert frame['filename']=='app.py' and frame['lineno']==47
    assert clean['tags']=={'operation':'review','support_reference':'safe'}


def test_sdk_transport_receives_only_scrubbed_errors(monkeypatch):
    import sentry_sdk
    from sentry_sdk.transport import Transport
    captured=[]
    class MemoryTransport(Transport):
        def capture_envelope(self,envelope):captured.append(envelope)
    monitoring._initialize.cache_clear()
    real_init=sentry_sdk.init
    def init(**kwargs):return real_init(**kwargs,transport=MemoryTransport)
    monkeypatch.setattr(sentry_sdk,'init',init)
    monkeypatch.setattr(monitoring,'setting',lambda name,default='':
        {'SENTRY_DSN':'https://public@example.invalid/1','SENTRY_ENVIRONMENT':'test'}.get(name,default))
    try:
        raise ValueError('PRIVATE_VALUE_NEVER_SENT')
    except ValueError as exc:
        reference=monitoring.capture_error(exc,'review')
    events=[item.payload.json for envelope in captured for item in envelope.items if item.type=='event']
    assert len(events)==1 and events[0]['tags']['support_reference']==reference
    assert 'PRIVATE_VALUE_NEVER_SENT' not in json.dumps(events)
    assert not sentry_sdk.get_client().integrations
    sentry_sdk.get_client().close()
    monitoring._initialize.cache_clear()


def test_disabled_or_broken_monitoring_does_not_break_the_app(monkeypatch):
    monkeypatch.setattr(monitoring,'setting',lambda *a:'')
    assert not monitoring.initialize_monitoring()
    assert len(monitoring.capture_error(ValueError('Synthetic'),'review'))==10
    monkeypatch.setattr(monitoring,'_initialize',Mock(side_effect=RuntimeError('Synthetic outage')))
    assert len(monitoring.capture_error(ValueError('Synthetic'),'page'))==10


def test_service_connection_pool_reused_without_sharing_browser_auth(monkeypatch):
    monkeypatch.setattr(accounts,'setting',lambda name:'configured-'+name)
    create=Mock();monkeypatch.setattr(accounts,'create_client',create)
    accounts._service_client.cache_clear()
    accounts.admin_client();accounts.admin_client()
    assert create.call_count==1
    accounts.auth_client();accounts.auth_client()
    assert create.call_count==3
    accounts._service_client.cache_clear()


def test_warm_ui_reuses_status_and_actor_but_expiry_and_actions_recheck(monkeypatch):
    actor=accounts.Actor('test','reviewer@example.com',True,'user')
    verified=Mock(return_value=actor);controls=Mock(return_value={'maintenance_enabled':False,'reviews_enabled':True})
    monkeypatch.setattr(accounts,'verified_actor',verified)
    monkeypatch.setattr(accounts,'service_controls',controls)
    monkeypatch.setattr(accounts,'refresh_if_needed',lambda client,session:session)
    ui=AppTest.from_string('''
import app,streamlit as st
app._init_session_state()
app._service_controls()
app._refresh_actor()
''')
    ui.session_state.auth_client=object()
    ui.session_state.supabase_session=SimpleNamespace(access_token='first',expires_at=time.time()+1000)
    ui.run();ui.run();ui.run()
    assert not ui.exception and verified.call_count==controls.call_count==1
    ui.session_state.actor_snapshot=(0,'first',actor)
    ui.session_state.service_snapshot=(0,controls.return_value)
    ui.run()
    assert verified.call_count==controls.call_count==2
    ui.session_state.supabase_session=SimpleNamespace(access_token='changed',expires_at=time.time()+1000)
    ui.run()
    assert verified.call_count==3


def test_narratives_remain_manual_without_any_network(monkeypatch):
    import socket
    monkeypatch.setattr(socket,'create_connection',Mock(side_effect=AssertionError('No external requests allowed')))
    files={'cover_letter':[('letter.pdf',pdf('Synthetic cover letter.'))],
           'travel_plan':[('plan.pdf',pdf('Synthetic travel plan.'))]}
    data=extract_documents(files)
    assert data.review_provenance['external_ai_requests']==0
    assert len(data.local_results)==2 and data.review_limitations
    issue=ValidationIssue(document_name='Cover Letter',field_name='purpose_of_visit',found_value=None,
        expected_value='Verified narrative content',severity=Severity.HIGH,recommended_fix='Read the letter.')
    assert not guard_local_issues([issue],data,files)[0].affects_score
    socket.create_connection.assert_not_called()


def test_download_does_not_generate_pdf_during_render(monkeypatch,complete_extraction):
    import report_view
    from scorer import calculate_score
    builder=Mock(return_value=b'%PDF-synthetic');download=Mock()
    monkeypatch.setattr(report_view,'build_pdf_report',builder)
    monkeypatch.setattr(report_view.st,'download_button',download)
    result=dict(extraction=complete_extraction,issues=[],score=calculate_score([]))
    ui=AppTest.from_string('''
from report_view import render_report_view
import streamlit as st
render_report_view(st.session_state.result)
''')
    ui.session_state.result=result;ui.run()
    assert not ui.exception
    builder.assert_not_called()
    callback=download.call_args.args[1]
    assert download.call_args.kwargs['on_click']=='ignore'
    assert callback()==callback()==b'%PDF-synthetic'
    builder.assert_called_once()


def test_upload_category_admin_page_does_not_fetch_team_tables(monkeypatch):
    from uploads import CATEGORIES
    readers=[]
    for name in ('team_profiles','team_attempts','review_logs'):
        reader=Mock(side_effect=AssertionError('Unrelated section was queried'))
        monkeypatch.setattr(accounts,name,reader);readers.append(reader)
    ui=AppTest.from_string('''
import app
app._init_session_state()
app.render_admin_dashboard()
''')
    ui.session_state.actor=accounts.Actor('test','owner@example.com',True,'super_admin')
    ui.session_state.auth_client=object()
    ui.session_state.admin_section='admin_uploads'
    ui.session_state.category_order_cache=(time.monotonic(),list(CATEGORIES))
    ui.run()
    assert not ui.exception
    for reader in readers:reader.assert_not_called()
