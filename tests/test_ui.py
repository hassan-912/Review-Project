from types import SimpleNamespace
from pathlib import Path
import time
from streamlit.testing.v1 import AppTest
import pytest
import accounts
from i18n import t

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def test_category_reorder_and_save_keeps_stable_ids(monkeypatch):
    from unittest.mock import Mock
    from uploads import CATEGORIES
    save=Mock();monkeypatch.setattr(accounts,'save_upload_category_order',save)
    app=AppTest.from_string('''
import app
app._init_session_state()
app.render_category_order_editor(object(),object())
''',default_timeout=30).run()
    app.selectbox(key='category_to_move').select('bank_statement').run()
    next(b for b in app.button if b.label==t('move_up','en')).click().run()
    next(b for b in app.button if b.label==t('save_order','en')).click().run()
    assert not app.exception
    saved=save.call_args.args[2]
    assert saved.index('bank_statement')==CATEGORIES.index('bank_statement')-1
    assert set(saved)==set(CATEGORIES)


def test_bank_upload_thumbnail_is_visible():
    import pymupdf
    with pymupdf.open() as doc:
        doc.new_page().insert_text((50,60),'First page')
        doc.new_page().insert_text((50,60),'Final available balance EUR 5000')
        raw=doc.tobytes().hex()
    app=AppTest.from_string(f'''
import app
app._init_session_state()
app.render_upload_thumbnails([('bank.pdf',bytes.fromhex('{raw}'))],'bank_statement')
''',default_timeout=30).run()
    assert not app.exception
    assert len(app.get('image'))==1
    assert any('Page 2 of 2' in item.value for item in app.caption)


@pytest.fixture(autouse=True)
def no_browser_recovery_token(monkeypatch):
    # AppTest has no browser JS and replaces its component registry between app instances.
    from uploads import CATEGORIES
    monkeypatch.setattr(accounts,"upload_category_order",lambda *a:list(CATEGORIES))
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
        assert len(app.get('file_uploader'))==10


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


def test_student_timeline_omits_inapplicable_hr_warning(complete_extraction):
    import runpy
    ui=runpy.run_path(str(APP_PATH))
    complete_extraction.employment.evidence_type='education'
    rows=ui['timeline_rows'](complete_extraction,[],'en')
    assert not any(row[0]==t('doc_employment','en') for row in rows)


@pytest.mark.parametrize('lang',['en','ar'])
def test_super_admin_dashboard_and_controls(monkeypatch,lang):
    actor=accounts.Actor('00000000-0000-0000-0000-000000000001','owner@example.com',True,'super_admin','owner')
    monkeypatch.setattr(accounts,'verified_actor',lambda *a,**kw:actor)
    monkeypatch.setattr(accounts,'refresh_if_needed',lambda client,session:session)
    monkeypatch.setattr(accounts,'review_logs',lambda *a,**kw:[])
    monkeypatch.setattr(accounts,'team_profiles',lambda *a,**kw:[dict(id=actor.user_id,email=actor.email,username=actor.username,
        is_approved=True,role='super_admin',hourly_limit=5,daily_limit=20)])
    monkeypatch.setattr(accounts,'team_attempts',lambda *a,**kw:[])
    from model_routing import FREE_MODELS
    models=[dict(model=name,priority=index+1,enabled=True,rpm=5,tpm=250000,rpd=20,requests_today=2,requests_minute=0,
        tokens_minute=0,input_tokens_today=50,output_tokens_today=40,errors_today=1,pending_today=0,
        quota_source='AI Studio Free tier',quota_checked_at='2026-10-16T00:00:00Z',cooldown_until=None) for index,name in enumerate(FREE_MODELS)]
    monkeypatch.setattr(accounts,'model_dashboard',lambda *a,**kw:dict(day_resets_at='2026-10-17T07:00:00Z',reviews_enabled=True,models=models,audit=[]))
    app=AppTest.from_file(APP_PATH,default_timeout=30)
    app.session_state.lang=lang;app.session_state.auth_client=object()
    app.session_state.supabase_session=SimpleNamespace(expires_at=time.time()+1000,access_token='test',refresh_token='test')
    app.session_state.current_page='admin';app.run()
    assert not app.exception
    assert len([m for m in app.metric if m.label==t('remaining_today',lang) and m.value=='18'])==4
    assert any(c.label==t('reviews_enabled',lang) for c in app.checkbox)
    assert any(t('quota_note',lang)==c.value for c in app.caption)


def test_evidence_renders_real_source_left_and_reference_right(complete_extraction):
    from tests.test_production_review import pdf_bytes
    from extractor import SourceField
    from validator import ValidationIssue,Severity
    from evidence import attach_evidence
    data=complete_extraction
    data.evidence_locations=[SourceField(document='flight',source_file='flight.pdf',page=1,field_name='full_name',value='MG TEST APPLICANX',text='MG TEST APPLICANX'),
        SourceField(document='passport',source_file='passport.pdf',page=1,field_name='full_name',value=data.passport.full_name,text=data.passport.full_name)]
    issue=ValidationIssue(document_name='Flight Reservation',field_name='full_name',found_value='MG TEST APPLICANX',expected_value=data.passport.full_name,
        severity=Severity.CRITICAL,recommended_fix='Correct the booking name')
    files={'flight':[('flight.pdf',pdf_bytes('FICTIONAL FLIGHT: MG TEST APPLICANX'))],
        'passport':[('passport.pdf',pdf_bytes('FICTIONAL PASSPORT: MG TEST APPLICANT'))]}
    attach_evidence([issue],data,files)
    source=f"""
import runpy,streamlit as st
ui=runpy.run_path({str(APP_PATH)!r})
ui['_init_session_state']()
ui['render_fix_checklist'](st.session_state.test_result['issues'],st.session_state.test_result)
"""
    app=AppTest.from_string(source,default_timeout=30)
    app.session_state.test_result={'issues':[issue],'source_files':files}
    app.session_state['evidence_report_0']=True
    app.run()
    assert not app.exception
    assert len(app.session_state.test_result.get('evidence_images',{}))==2
    assert len(app.get('image'))==2
