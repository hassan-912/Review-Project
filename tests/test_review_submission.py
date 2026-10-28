"""A single submission commits draft inputs and executes at most one review."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import time

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

import accounts
import session_resume
import recovery
import review_pipeline
import settings
from i18n import t
from scorer import calculate_score
from tests.test_production_review import pdf_bytes
from uploads import CATEGORIES

APP_PATH=Path(__file__).resolve().parents[1]/'app.py'


@pytest.fixture
def submission(monkeypatch,complete_extraction):
    # AppTest has no frontend JS; browser restoration is covered separately.
    monkeypatch.setattr(session_resume,'browser_state',lambda *a,**kw:dict(ready=True,handle=None))
    actor=accounts.Actor('00000000-0000-0000-0000-000000000001','reviewer@example.com',True,'user')
    monkeypatch.setattr(accounts,'verified_actor',lambda *a,**kw:actor)
    monkeypatch.setattr(accounts,'refresh_if_needed',lambda client,session:session)
    monkeypatch.setattr(accounts,'service_controls',lambda:dict(maintenance_enabled=False,reviews_enabled=True))
    monkeypatch.setattr(accounts,'upload_category_order',lambda *a:list(CATEGORIES))
    monkeypatch.setattr(accounts,'ensure_service_available',Mock())
    reserve=Mock();monkeypatch.setattr(accounts,'reserve_review',reserve)
    monkeypatch.setattr(accounts,'finish_attempt',Mock())
    monkeypatch.setattr(accounts,'log_review',Mock())
    monkeypatch.setattr(settings,'setting',lambda key:'test' if key.startswith('SUPABASE_') else None)
    monkeypatch.setattr(recovery,'recovery_tokens',lambda:None)
    pipeline=Mock(return_value=dict(extraction=complete_extraction,issues=[],score=calculate_score([]),writing={}))
    monkeypatch.setattr(review_pipeline,'review_documents',pipeline)
    upload=SimpleNamespace(name='passport.pdf',getvalue=lambda:pdf_bytes('Synthetic passport evidence.'))
    files={'ready':False}
    monkeypatch.setattr(st,'file_uploader',lambda *a,**kw:[upload] if files['ready'] and kw['key']=='upload_0_passport' else [])
    ui=AppTest.from_file(APP_PATH,default_timeout=30)
    ui.session_state.auth_client=object()
    ui.session_state.supabase_session=SimpleNamespace(expires_at=time.time()+1000,access_token='test',refresh_token='test')
    def add_files():
        files['ready']=True
        # Simulate the uploader's committed form value. AppTest does not expose
        # a file-upload action, so its return value alone cannot populate state.
        ui.session_state['upload_0_passport']=[upload]
    return SimpleNamespace(ui=ui,files=files,pipeline=pipeline,reserve=reserve,upload=upload,add_files=add_files)


@pytest.mark.parametrize('lang',['en','ar'])
def test_first_click_submits_new_uploads_and_uncommitted_client_name_exactly_once(submission,lang):
    ui=submission.ui;ui.session_state.lang=lang;ui.run()
    assert not ui.exception and not ui.button(key='run_review_submit').disabled
    assert not any(item.label==t('advanced',lang) for item in ui.expander)
    assert not ui.checkbox
    submission.add_files()
    # Deliberately do not rerun after typing: the first click must submit both inputs.
    ui.text_input(key='client_name').set_value('Synthetic latest client')
    ui.button(key='run_review_submit').click().run()
    assert not ui.exception and not ui.error
    submission.pipeline.assert_called_once()
    submission.reserve.assert_called_once()
    assert submission.pipeline.call_args.args[0]['passport'][0][0]=='passport.pdf'
    assert ui.session_state.review_result['client_name']=='Synthetic latest client'
    assert 'review_requested' not in ui.session_state
    ui.run()
    assert not ui.exception
    submission.pipeline.assert_called_once()
    submission.reserve.assert_called_once()


def test_submit_survives_an_intervening_rerun_before_the_form_is_rendered(submission,monkeypatch):
    ui=submission.ui;ui.run()
    state={'interrupt':True}
    def controls():
        if state['interrupt']:
            state['interrupt']=False
            st.rerun()
        return dict(maintenance_enabled=False,reviews_enabled=True)
    monkeypatch.setattr(accounts,'service_controls',controls)
    submission.add_files()
    ui.text_input(key='client_name').set_value('Synthetic rerun test')
    ui.button(key='run_review_submit').click().run()
    assert not ui.exception and not ui.error
    submission.pipeline.assert_called_once()
    submission.reserve.assert_called_once()
    assert ui.session_state.review_result['client_name']=='Synthetic rerun test'


def test_clear_works_on_its_first_click_without_starting_a_review(submission):
    ui=submission.ui;submission.add_files();ui.run()
    ui.session_state.review_cache={'old':(0,dict())}
    ui.session_state.document_cache=object()
    ui.button(key='clear_review_submit').click().run()
    assert not ui.exception
    assert ui.session_state.upload_generation==1
    assert not ui.session_state.review_cache and not ui.session_state.review_result
    assert 'review_requested' not in ui.session_state
    assert 'document_cache' not in ui.session_state
    submission.pipeline.assert_not_called()
    submission.reserve.assert_not_called()


def test_empty_submit_is_validated_without_spending_a_review_attempt(submission):
    ui=submission.ui;ui.run()
    ui.text_input(key='client_name').set_value('Synthetic empty file test')
    ui.button(key='run_review_submit').click().run()
    assert not ui.exception
    assert any(item.value==t('upload_invalid','en') for item in ui.error)
    submission.pipeline.assert_not_called()
    submission.reserve.assert_not_called()


def test_first_click_includes_both_spain_upload_slots_and_other_supporting_documents(submission):
    ui=submission.ui;ui.run();submission.add_files()
    expected=set()
    for slot in ('national_id_translation','bank_declaration','supporting'):
        name=slot+'.pdf';raw=pdf_bytes('Synthetic document for '+slot)
        upload=SimpleNamespace(name=name,getvalue=lambda raw=raw:raw)
        ui.session_state['upload_0_'+slot]=[upload]
        expected.add(name)
    ui.text_input(key='client_name').set_value('Synthetic Spain dedicated uploads')
    ui.button(key='run_review_submit').click().run()
    assert not ui.exception and not ui.error
    submission.pipeline.assert_called_once()
    submission.reserve.assert_called_once()
    uploaded=submission.pipeline.call_args.args[0]
    assert {name for name,_ in uploaded['supporting']}==expected
    assert 'passport' in uploaded


def test_scope_change_discards_a_pending_review(submission):
    ui=submission.ui;ui.run()
    ui.session_state.review_requested=True
    ui.segmented_control(key='trip_type').set_value('business').run()
    assert not ui.exception and not ui.session_state.review_requested
    assert not any(button.key=='run_review_submit' for button in ui.button)
    submission.pipeline.assert_not_called()
    submission.reserve.assert_not_called()


@pytest.mark.parametrize('country',['france','germany','italy','netherlands','sweden','belgium','greece'])
def test_additional_schengen_country_submits_once_and_labels_its_own_report(submission,country):
    ui=submission.ui;ui.run()
    ui.selectbox(key='schengen_country').set_value(country).run()
    generation=ui.session_state.upload_generation
    raw=pdf_bytes('Synthetic passport upload')
    ui.session_state[f'upload_{generation}_passport']=[SimpleNamespace(name='passport.pdf',getvalue=lambda:raw)]
    ui.text_input(key='client_name').set_value('Synthetic Schengen review')
    ui.button(key='run_review_submit').click().run()
    assert not ui.exception and not ui.error
    submission.pipeline.assert_called_once()
    submission.reserve.assert_called_once()
    assert ui.session_state.review_result['review_country']==country
    assert submission.pipeline.call_args.kwargs['review_country']==country


def test_revoked_approval_is_checked_again_after_warm_page_load(submission,monkeypatch):
    ui=submission.ui;ui.run();submission.add_files()
    monkeypatch.setattr(accounts,'verified_actor',lambda *a,**kw:
        accounts.Actor('test','reviewer@example.com',False,'user'))
    ui.text_input(key='client_name').set_value('Synthetic revoked user')
    ui.button(key='run_review_submit').click().run()
    assert not ui.exception and any(item.value==t('access_revoked','en') for item in ui.error)
    submission.pipeline.assert_not_called()
    submission.reserve.assert_not_called()
    assert not ui.session_state.review_result


def test_live_maintenance_check_blocks_review_with_cached_page_status(submission,monkeypatch):
    ui=submission.ui;ui.run();submission.add_files()
    monkeypatch.setattr(accounts,'ensure_service_available',Mock(side_effect=accounts.AccountError('maintenance_message')))
    ui.text_input(key='client_name').set_value('Synthetic maintenance test')
    ui.button(key='run_review_submit').click().run()
    assert not ui.exception and any(item.value==t('maintenance_message','en') for item in ui.error)
    submission.pipeline.assert_not_called()
    submission.reserve.assert_not_called()


def test_initial_gemini_review_shares_the_factual_review_quota_and_reruns_do_not_call_api(submission,monkeypatch):
    import narrative_reviewer.ui as narrative_ui
    import narrative_reviewer.service as service
    monkeypatch.setattr(narrative_ui,'prepare',lambda result,lang:{'request_id':'synthetic'})
    runner=Mock(return_value=dict(status='complete',findings=[],limitations=[]))
    monkeypatch.setattr(service,'run_review',runner)
    submission.pipeline.return_value['narrative_requested']=True
    # Keep rendering out of this orchestration test; its source-aware UI is tested separately.
    monkeypatch.setattr(narrative_ui,'render_narrative_review',lambda *args:None)
    ui=submission.ui;ui.run();submission.add_files()
    ui.text_input(key='client_name').set_value('Synthetic Gemini submission')
    ui.button(key='run_review_submit').click().run()
    assert not ui.exception
    submission.reserve.assert_called_once();runner.assert_called_once()
    assert runner.call_args.args[-1]==submission.reserve.call_args.kwargs['request_id']
    assert ui.session_state.review_result['narrative_review']['status']=='complete'
    ui.run();runner.assert_called_once();submission.reserve.assert_called_once()
