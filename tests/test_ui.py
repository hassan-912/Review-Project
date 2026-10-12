from types import SimpleNamespace
from pathlib import Path
import time
from streamlit.testing.v1 import AppTest
import pytest
import accounts
from i18n import t

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


@pytest.fixture(autouse=True)
def no_browser_recovery_token(monkeypatch):
    # AppTest has no browser JS and replaces its component registry between app instances.
    import recovery
    monkeypatch.setattr(recovery,"recovery_tokens",lambda:None)


@pytest.mark.parametrize('lang',['en','ar'])
def test_access_screen_in_each_language(lang):
    app=AppTest.from_file(APP_PATH,default_timeout=30)
    app.session_state.lang=lang
    app.run()
    assert not app.exception
    assert app.title[0].value==t('access_title',lang)
    assert any(button.label==t('sign_in',lang) for button in app.button)
    assert not app.query_params


@pytest.mark.parametrize('lang',['en','ar'])
@pytest.mark.parametrize('page',['review','history','admin','how'])
def test_approved_pages_are_bilingual(monkeypatch,lang,page):
    actor=accounts.Actor('00000000-0000-0000-0000-000000000001','test@example.com',True,'admin')
    monkeypatch.setattr(accounts,'verified_actor',lambda *a,**kw:actor)
    monkeypatch.setattr(accounts,'refresh_if_needed',lambda client,session:session)
    monkeypatch.setattr(accounts,'review_logs',lambda *a,**kw:[])
    monkeypatch.setattr(accounts,'team_profiles',lambda *a,**kw:[])
    monkeypatch.setattr(accounts,'team_attempts',lambda *a,**kw:[])
    app=AppTest.from_file(APP_PATH,default_timeout=30)
    app.session_state.lang=lang
    app.session_state.auth_client=object()
    app.session_state.supabase_session=SimpleNamespace(expires_at=time.time()+1000,access_token='test',refresh_token='test')
    app.session_state.current_page=page
    app.run()
    assert not app.exception
    assert app.title[0].value==t('review_title' if page=='review' else page,lang)
    if page=='review':
        assert len(app.get('file_uploader'))==9


def test_failed_legacy_restore_clears_url_and_explains(monkeypatch):
    monkeypatch.setattr(accounts,'restore_session',lambda *a:(_ for _ in ()).throw(accounts.AccountError('session_expired')))
    app=AppTest.from_file(APP_PATH,default_timeout=30)
    app.query_params={'_t':'expired','_r':'bad'}
    app.run()
    assert not app.exception and not app.query_params
    assert any(t('session_expired','en')==x.value for x in app.info)


@pytest.mark.parametrize('lang',['en','ar'])
def test_signup_has_username_and_accepts_eight_characters(monkeypatch,lang):
    from unittest.mock import Mock
    signup=Mock();monkeypatch.setattr(accounts,'signup',signup)
    app=AppTest.from_file(APP_PATH,default_timeout=30)
    app.session_state.lang=lang
    app.session_state.access_mode='create_account'
    app.session_state.auth_client=object()
    app.run()
    app.text_input(key='signup_username').set_value('reviewer.one')
    app.text_input(key='email').set_value('reviewer@example.com')
    app.text_input(key='password').set_value('abcdefgh')
    app.text_input(key='confirm_password').set_value('abcdefgh')
    next(b for b in app.button if b.label==t('create_account',lang)).click().run()
    assert not app.exception and signup.call_count==1
    assert signup.call_args.args[1:]==('reviewer.one','reviewer@example.com','abcdefgh')
    assert any(x.value==t('signup_success',lang) for x in app.success)


def test_admin_attempts_show_username_failed_status_and_no_fake_zero(monkeypatch):
    actor=accounts.Actor('00000000-0000-0000-0000-000000000001','test@example.com',True,'admin','admin')
    monkeypatch.setattr(accounts,'verified_actor',lambda *a,**kw:actor)
    monkeypatch.setattr(accounts,'refresh_if_needed',lambda client,session:session)
    monkeypatch.setattr(accounts,'review_logs',lambda *a,**kw:[])
    monkeypatch.setattr(accounts,'team_profiles',lambda *a,**kw:[])
    monkeypatch.setattr(accounts,'team_attempts',lambda *a,**kw:[{'client_name':'FICTIONAL','submitted_username':'reviewer.one','submitted_by':'test@example.com','score':None,'status':'failed','requested_at':'2026-10-12T06:00:00Z'}])
    app=AppTest.from_file(APP_PATH,default_timeout=30)
    app.session_state.auth_client=object()
    app.session_state.supabase_session=SimpleNamespace(expires_at=time.time()+1000,access_token='test',refresh_token='test')
    app.session_state.current_page='admin'
    app.run()
    assert not app.exception
    table=app.dataframe[0].value
    assert table.iloc[0][t('agent','en')]=='reviewer.one'
    assert table.iloc[0][t('latest_score','en')]=='—'
    assert table.iloc[0][t('status','en')]==t('failed','en')


@pytest.mark.parametrize('lang',['en','ar'])
def test_report_and_download_in_both_languages(complete_extraction,lang):
    from validator import run_validation
    from scorer import calculate_score
    from business_checker import check_business_alignment
    complete_extraction.visa_form.passport_number='WRONG'
    issues=run_validation(complete_extraction)
    result={'extraction':complete_extraction,'issues':issues,'score':calculate_score(issues),
            'biz_result':check_business_alignment(complete_extraction),'client_name':'أحمد محمد'}
    source=f"""
import runpy,streamlit as st
ui=runpy.run_path({str(APP_PATH)!r})
ui['_init_session_state']()
ui['render_header']()
ui['render_report'](st.session_state.test_result)
"""
    app=AppTest.from_string(source,default_timeout=30)
    app.session_state.lang=lang
    app.session_state.test_result=result
    app.run()
    assert not app.exception
    assert not app.warning
    assert any(s.value==t('summary',lang) for s in app.subheader)
    assert len(app.get('download_button'))==1
