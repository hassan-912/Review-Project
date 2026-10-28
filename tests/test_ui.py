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


def test_uploaded_bank_file_has_no_thumbnail(monkeypatch):
    import streamlit as st
    import pymupdf
    with pymupdf.open() as doc:
        doc.new_page().insert_text((50,60),'First page')
        doc.new_page().insert_text((50,60),'Final available balance EUR 5000')
        raw=doc.tobytes()
    upload=SimpleNamespace(name='bank.pdf',getvalue=lambda:raw)
    monkeypatch.setattr(st,'file_uploader',lambda *a,**kw:[upload] if kw['key'].endswith('bank_statement') else [])
    app=AppTest.from_string('''
import app,streamlit as st
app._init_session_state()
st.session_state.upload_result=app.render_upload_ui()
''',default_timeout=30).run()
    assert not app.exception
    assert not app.get('image')
    assert app.session_state.upload_result[0]['bank_statement'][0][0]=='bank.pdf'


@pytest.mark.parametrize('lang',['en','ar'])
def test_spain_shows_separate_id_translation_and_bank_declaration_upload_cards(lang):
    ui=AppTest.from_string('''
import app
app._init_session_state()
app.render_upload_ui()
''',default_timeout=30)
    ui.session_state.lang=lang;ui.run()
    labels=[uploader.proto.label for uploader in ui.get('file_uploader')]
    assert not ui.exception
    assert t('doc_national_id_translation',lang) in labels
    assert t('doc_bank_declaration',lang) in labels
    assert labels.index(t('doc_bank_declaration',lang))!=labels.index(t('doc_bank_statement',lang))
    ui.selectbox(key='schengen_country').set_value('france').run()
    labels=[uploader.proto.label for uploader in ui.get('file_uploader')]
    assert not ui.exception and len(labels)==11
    assert t('doc_national_id_translation',lang) not in labels
    assert t('doc_bank_declaration',lang) not in labels
    assert any(caption.value==t('combined_hint_schengen',lang) for caption in ui.caption)


def test_dedicated_spain_uploads_and_general_supporting_files_are_all_retained(monkeypatch):
    import streamlit as st
    files={slot:SimpleNamespace(name=name,getvalue=lambda: b'local upload bytes') for slot,name in
           [('national_id_translation','id-translation.pdf'),('bank_declaration','declaration.pdf'),
            ('supporting','other.pdf')]}
    monkeypatch.setattr(st,'file_uploader',lambda *a,**kw:
        [files[kw['key'].removeprefix('upload_0_')]] if kw['key'].removeprefix('upload_0_') in files else [])
    ui=AppTest.from_string('''
import app,streamlit as st
app._init_session_state()
st.session_state.upload_result=app.render_upload_ui()
''',default_timeout=30).run()
    assert not ui.exception
    uploaded=ui.session_state.upload_result[0]
    assert {name for name,_ in uploaded['supporting']}=={'id-translation.pdf','declaration.pdf','other.pdf'}


@pytest.mark.parametrize('lang',['en','ar'])
def test_non_scoring_id_note_does_not_appear_as_a_correction(complete_extraction,lang):
    from extractor import IdentityEvidence
    from validator import run_validation
    from scorer import calculate_score
    from business_checker import check_business_alignment
    data=complete_extraction
    data.identity_evidence=[IdentityEvidence(document='passport',source_file='passport.pdf',
        national_id_number='30001011234567')]
    issues=run_validation(data)
    result={'extraction':data,'issues':issues,'score':calculate_score(issues),
        'biz_result':check_business_alignment(data),'writing':{},'client_name':'Synthetic note test','hash':'id-note'}
    ui=AppTest.from_string('''
import app,streamlit as st
app._init_session_state()
app.render_report(st.session_state.test_result)
''',default_timeout=30)
    ui.session_state.lang=lang
    ui.session_state.test_result=result
    ui.run()
    assert not ui.exception
    assert not any('30001011234567' in item.value for item in ui.info)
    assert not ui.warning
    assert result['score'].score==100 and not result['score'].provisional


@pytest.fixture(autouse=True)
def no_browser_recovery_token(monkeypatch):
    # AppTest has no browser JS and replaces its component registry between app instances.
    from uploads import CATEGORIES
    monkeypatch.setattr(accounts,"upload_category_order",lambda *a:list(CATEGORIES))
    monkeypatch.setattr(accounts,'service_controls',lambda:dict(maintenance_enabled=False,reviews_enabled=True))
    import recovery
    monkeypatch.setattr(recovery,"recovery_tokens",lambda:None)
    import session_resume
    monkeypatch.setattr(session_resume,'browser_state',lambda *args,**kw:dict(ready=True,handle=None))


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
        from uploads import upload_slot_order
        assert len(app.get('file_uploader'))==len(upload_slot_order())


def test_failed_legacy_restore_clears_url_and_explains(monkeypatch):
    monkeypatch.setattr(accounts,'restore_session',lambda *a:(_ for _ in ()).throw(accounts.AccountError('session_expired')))
    app=AppTest.from_file(APP_PATH,default_timeout=30)
    app.query_params={'_t':'expired','_r':'bad'}
    app.run()
    assert not app.exception and not app.query_params
    assert any(t('session_expired','en')==x.value for x in app.info)


@pytest.mark.parametrize('lang',['en','ar'])
def test_signup_has_username_and_accepts_six_characters(monkeypatch,lang):
    from unittest.mock import Mock
    signup=Mock();monkeypatch.setattr(accounts,'signup',signup)
    app=AppTest.from_file(APP_PATH,default_timeout=30)
    app.session_state.lang=lang
    app.session_state.access_mode='create_account'
    app.session_state.auth_client=object()
    app.run()
    app.text_input(key='signup_username').set_value('reviewer.one')
    app.text_input(key='email').set_value('reviewer@example.com')
    app.text_input(key='password').set_value('abcdef')
    app.text_input(key='confirm_password').set_value('abcdef')
    next(b for b in app.button if b.label==t('create_account',lang)).click().run()
    assert not app.exception and signup.call_count==1
    assert signup.call_args.args[1:]==('reviewer.one','reviewer@example.com','abcdef')
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
    assert any(s.value==t('corrections_title',lang,count=len(issues)) for s in app.subheader)
    assert not any(s.value==t('summary',lang) for s in app.subheader)
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
    app=AppTest.from_file(APP_PATH,default_timeout=30)
    app.session_state.lang=lang;app.session_state.auth_client=object()
    app.session_state.supabase_session=SimpleNamespace(expires_at=time.time()+1000,access_token='test',refresh_token='test')
    app.session_state.current_page='admin';app.run()
    assert not app.exception
    assert any(c.label==t('reviews_enabled',lang) for c in app.checkbox)
    assert t('admin_costs',lang) in app.selectbox(key='admin_section').options
    assert 'admin_models' not in app.selectbox(key='admin_section').options


def test_corrections_show_error_and_reference_crops_with_prominent_document_names(complete_extraction):
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
    assert not app.session_state.test_result.get('evidence_images')
    assert len(app.get('image'))==2
    assert app.session_state.test_result.get('reference_images_v1')
    assert any(item.value=='Flight Reservation' for item in app.subheader)
    assert app.session_state.test_result.get('correction_images_v3')
    assert any('flight.pdf' in item.value for item in app.text)
    assert any('passport.pdf' in item.value for item in app.text)




@pytest.mark.parametrize('role',['user','admin','super_admin'])
def test_maintenance_blocks_customer_pages_but_owner_can_resume(monkeypatch,role):
    state=dict(maintenance_enabled=True,reviews_enabled=True)
    monkeypatch.setattr(accounts,'service_controls',lambda:state.copy())
    def update(*args):state['maintenance_enabled']=args[-1]
    monkeypatch.setattr(accounts,'set_maintenance',update)
    actor=accounts.Actor('00000000-0000-0000-0000-000000000001','test@example.com',True,role,'owner')
    monkeypatch.setattr(accounts,'verified_actor',lambda *a,**kw:actor)
    monkeypatch.setattr(accounts,'refresh_if_needed',lambda client,session:session)
    monkeypatch.setattr(accounts,'team_profiles',lambda *a:[])
    monkeypatch.setattr(accounts,'team_attempts',lambda *a:[])
    monkeypatch.setattr(accounts,'review_logs',lambda *a,**kw:[])
    ui=AppTest.from_file(APP_PATH,default_timeout=30)
    ui.session_state.auth_client=object()
    ui.session_state.supabase_session=SimpleNamespace(expires_at=time.time()+1000,access_token='test',refresh_token='test')
    ui.session_state.current_page='history'
    ui.session_state.admin_section='admin_maintenance'
    ui.run()
    assert not ui.exception
    assert not ui.get('file_uploader')
    if role=='super_admin':
        next(b for b in ui.button if b.label==t('resume_website','en')).click().run()
        assert not state['maintenance_enabled'] and state['reviews_enabled']
    else:
        assert ui.title[0].value==t('maintenance_title','en')
        assert not ui.selectbox


def test_appointment_report_shows_specific_recommendation_in_both_languages(complete_extraction):
    from appointment_review import appointment_issues
    from extractor import AppointmentInfo
    complete_extraction.appointments=[AppointmentInfo(source_file='appointment.pdf',appointment_date='2026-12-01')]
    issues=appointment_issues(complete_extraction)
    for lang in ('en','ar'):
        ui=AppTest.from_string('''
import app,streamlit as st
app._init_session_state()
app.render_fix_checklist(st.session_state.issues)
''',default_timeout=30)
        ui.session_state.lang=lang;ui.session_state.issues=issues;ui.run()
        assert not ui.exception
        from i18n import issue_text
        assert '30/01/2027' in issue_text(issues[0],lang)[1]


def test_maintenance_guest_has_only_management_sign_in(monkeypatch):
    monkeypatch.setattr(accounts,'service_controls',lambda:dict(maintenance_enabled=True,reviews_enabled=True))
    ui=AppTest.from_file(APP_PATH,default_timeout=30)
    ui.session_state.access_mode='create_account'
    ui.run()
    assert not ui.exception
    assert ui.title[0].value==t('maintenance_title','en')
    assert not ui.get('file_uploader') and not ui.get('segmented_control')
    assert not any(button.label==t('create_account','en') for button in ui.button)


@pytest.mark.parametrize('lang',['en','ar'])
def test_destination_navigation_starts_with_spain_and_blocks_pending_programs(monkeypatch,lang):
    from uploads import upload_slot_order
    ui=AppTest.from_string('''
import app,streamlit as st
app._init_session_state()
app.render_upload_ui()
''',default_timeout=30)
    ui.session_state.lang=lang;ui.run()
    assert not ui.exception
    assert ui.session_state.visa_program=='schengen' and ui.session_state.schengen_country=='spain'
    assert len(ui.get('file_uploader'))==len(upload_slot_order())
    ui.session_state.review_result={'old':'report'}
    ui.segmented_control(key='visa_program').set_value('canada').run()
    assert not ui.exception and not ui.get('file_uploader')
    assert ui.session_state.review_result is None
    assert any(t('under_processing',lang) in option for option in ui.segmented_control(key='visa_program').options)
    assert any(t('program_canada',lang) in note.value for note in ui.info)


@pytest.mark.parametrize('program,country',[('canada','spain'),('uk','spain')])
def test_unavailable_program_cannot_start_a_review(monkeypatch,program,country):
    from unittest.mock import Mock
    reserve=Mock();monkeypatch.setattr(accounts,'reserve_review',reserve)
    ui=AppTest.from_string('''
import app,streamlit as st
app._init_session_state()
app.render_upload_ui()
app.run_review({},'Test')
''',default_timeout=30)
    ui.session_state.visa_program=program;ui.session_state.schengen_country=country;ui.run()
    assert not ui.exception and not ui.get('file_uploader')
    reserve.assert_not_called()


def test_review_cache_identity_includes_destination():
    ui=AppTest.from_string('''
import app,streamlit as st
app._init_session_state()
st.session_state.visa_program='schengen'
st.session_state.schengen_country='spain'
first=app._compute_upload_hash({})
st.session_state.schengen_country='france'
st.session_state.hashes_differ=first != app._compute_upload_hash({})
''',default_timeout=30).run()
    assert not ui.exception and ui.session_state.hashes_differ


def test_document_only_review_does_not_require_key_or_reserve_model_usage(monkeypatch,complete_extraction):
    from unittest.mock import Mock
    import app as module
    from scorer import calculate_score
    from business_checker import check_business_alignment
    from tests.test_local_review_pipeline import pdf
    actor=accounts.Actor('00000000-0000-0000-0000-000000000001','test@example.com',True,'user')
    monkeypatch.setattr(accounts,'verified_actor',lambda *a,**kw:actor)
    monkeypatch.setattr(accounts,'refresh_if_needed',lambda client,session:session)
    monkeypatch.setattr(accounts,'ensure_service_available',lambda:None)
    for name in ('reserve_review','finish_attempt','log_review'):monkeypatch.setattr(accounts,name,Mock())
    result=dict(extraction=complete_extraction,score=calculate_score([]),issues=[],
                biz_result=check_business_alignment(complete_extraction),writing={})
    review=Mock(return_value=result);monkeypatch.setattr(module,'review_documents',review)
    ui=AppTest.from_string('''
import app,streamlit as st
app._init_session_state()
app.run_review(st.session_state.test_uploads,'Synthetic applicant')
''',default_timeout=30)
    ui.session_state.auth_client=object()
    ui.session_state.supabase_session=SimpleNamespace(expires_at=time.time()+1000,access_token='test',refresh_token='test')
    ui.session_state.test_uploads={'visa_form':[('synthetic.pdf',pdf('Synthetic application sample with unsupported layout.'))]}
    ui.run()
    assert not ui.exception and not ui.error
    assert review.call_args.args[0]==ui.session_state.test_uploads
    accounts.reserve_review.assert_called_once()


@pytest.mark.parametrize('lang',['en','ar'])
def test_successful_local_values_are_hidden_in_corrections_only_output(complete_extraction,lang):
    from scorer import calculate_score
    from business_checker import check_business_alignment
    complete_extraction.local_results=[dict(source_file='synthetic.pdf',category='visa_form',status='needs_verification',
        fields=[dict(key='travel_document.number',label='Passport number',value='X00001234',status='extracted',sources=[]),
                dict(key='occupation.current',label='Occupation',value='Unreadable OCR',status='needs_verification',sources=[])])]
    result=dict(extraction=complete_extraction,issues=[],score=calculate_score([]),
                biz_result=check_business_alignment(complete_extraction),writing={},client_name='Synthetic',hash='local-values')
    ui=AppTest.from_string('''
import app,streamlit as st
app._init_session_state()
app.render_report(st.session_state.test_result)
''',default_timeout=30)
    ui.session_state.lang=lang;ui.session_state.test_result=result;ui.run()
    assert not ui.exception
    assert not any('X00001234' in item.value for item in ui.text)
    assert not any(item.value==t('local_field_verify',lang) for item in ui.caption)
    assert not any(item.label==t('download_receipt',lang) for item in ui.get('download_button'))
    assert not ui.metric and not ui.get('image')


@pytest.mark.parametrize('lang',['en','ar'])
def test_all_schengen_countries_offer_tourism_and_business_with_business_pending(lang):
    from app import SCHENGEN_COUNTRIES
    ui=AppTest.from_string('''
import app
app._init_session_state()
app.render_upload_ui()
''',default_timeout=30)
    ui.session_state.lang=lang;ui.run()
    assert set(SCHENGEN_COUNTRIES)=={'spain','france','germany','italy','netherlands','sweden','belgium','greece'}
    for country in SCHENGEN_COUNTRIES:
        ui.selectbox(key='schengen_country').set_value(country).run()
        assert all(t('under_processing',lang) not in label for label in ui.selectbox(key='schengen_country').options)
        assert len(ui.get('file_uploader'))==(13 if country=='spain' else 11)
        assert any(t('schengen_workspace',lang,destination=t('country_'+country,lang))==caption.value for caption in ui.caption)
        control=ui.segmented_control(key='trip_type')
        assert any(t('trip_tourism',lang) in label for label in control.options)
        assert any(t('trip_business',lang) in label and t('under_processing',lang) in label for label in control.options)
    assert not ui.exception


@pytest.mark.parametrize('trip_type',['business','tampered'])
def test_business_and_invalid_trip_type_cannot_start_a_review(monkeypatch,trip_type):
    from unittest.mock import Mock
    reserve=Mock();monkeypatch.setattr(accounts,'reserve_review',reserve)
    ui=AppTest.from_string('''
import app
app._init_session_state()
app.run_review({},'Synthetic')
''',default_timeout=30)
    ui.session_state.trip_type=trip_type;ui.run()
    assert not ui.exception
    reserve.assert_not_called()


def test_trip_type_changes_the_result_cache_identity():
    ui=AppTest.from_string('''
import app,streamlit as st
app._init_session_state()
st.session_state.trip_type='tourism'
first=app._compute_upload_hash({})
st.session_state.trip_type='business'
st.session_state.hashes_differ=first!=app._compute_upload_hash({})
''',default_timeout=30).run()
    assert not ui.exception and ui.session_state.hashes_differ


def test_language_switch_preserves_the_selected_review_scope():
    ui=AppTest.from_string('''
import app,streamlit as st
app._init_session_state()
app.render_header()
app.render_upload_ui()
''',default_timeout=30).run()
    original=ui.session_state.active_review_scope
    generation=ui.session_state.upload_generation
    for lang in ('ar','en'):
        ui.segmented_control(key='lang').set_value(lang).run()
        assert not ui.exception
        assert ui.session_state.active_review_scope==original
        assert ui.session_state.upload_generation==generation
        assert ui.get('file_uploader')
