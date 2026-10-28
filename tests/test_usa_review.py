"""USA comparisons use only source-linked local data, never Schengen rules or AI."""
from types import SimpleNamespace
from unittest.mock import Mock
import socket
import time

import pytest
from streamlit.testing.v1 import AppTest
import accounts
import recovery
import settings
import usa_review as usa
from document_cache import DocumentCache
from i18n import t
from tests.test_production_review import pdf_bytes
from uploads import USA_CATEGORIES,upload_slot_order,validate_uploads


DS='''DS-160 Online Nonimmigrant Visa Application
Personal Information
Surnames: DOE
Given Names: JOHN MICHAEL
Date of Birth: 15 JAN 1990
Nationality: EGYPT
Passport Information
Passport/Travel Document Number: A12345678
Issuance Date: 2020-03-15
Expiration Date: 2030-03-15
Travel Information
Intended Date of Arrival: 2027-05-10
Intended Length of Stay in U.S.: 10 DAY(S)
Hotel Name: Synthetic Central Hotel
Address Where You Will Stay in the U.S.:
Street Address (Line 1): 100 Main Street
City: NEW YORK
State: NY
ZIP Code: 10001
'''
PASSPORT='''PASSPORT
Surname: DOE
Given Names: JOHN MICHAEL
Date of Birth: 1990-01-15
Passport Number: A12345678
Nationality: Egyptian
Passport Issue Date: 2020-03-15
Passport Expiry Date: 2030-03-15
'''
HOTEL='''Hotel Name: Synthetic Central Hotel
Guest Name: JOHN MICHAEL DOE
Hotel Address: 100 Main St.
Hotel City: New York City
Hotel State: NY
Hotel ZIP Code: 10001
Check-in Date: 2027-05-10
Check-out Date: 2027-05-20
'''
CLIENT='''Client Form
Full Name: JOHN MICHAEL DOE
Passport Number: A12345678
Date of Birth: 1990-01-15
Arrival Date: 2027-05-10
Departure Date: 2027-05-20
Hotel City: New York
Hotel Address: 100 Main Street
'''


def files(ds=DS,passport=PASSPORT,hotel=HOTEL,client=CLIENT):
    return {key:[(key+'.pdf',pdf_bytes(text))] for key,text in
        (('ds160',ds),('passport',passport),('hotel',hotel),('client_form',client)) if text is not None}


def test_complete_native_text_file_matches_without_network(monkeypatch):
    monkeypatch.setattr(socket,'create_connection',Mock(side_effect=AssertionError('Network forbidden')))
    result=usa.review_documents(files())
    assert not result['narrative_requested'] and not result['incomplete']
    assert result['provenance']['external_ai_requests']==0
    assert all(check['status']=='match' for check in result['usa_checks'])
    assert any(c['field']=='hotel_coverage_gap' for c in result['usa_checks'])
    socket.create_connection.assert_not_called()


@pytest.mark.parametrize('field,old,new',[
    ('passport_number','A12345678','A12345679'),('date_of_birth','15 JAN 1990','16 JAN 1990'),
    ('passport_expiry','2030-03-15','2031-03-15'),('surname','DOE','DOX'),
    ('arrival_date','2027-05-10','2027-05-11'),('stay_city','NEW YORK','BOSTON'),
])
def test_ds160_mismatches_are_grounded_in_both_sources(field,old,new):
    result=usa.review_documents(files(ds=DS.replace(old,new)))
    check=next(c for c in result['usa_checks'] if c['field']==field and c['status']=='mismatch')
    assert check['sources'] and check['references']
    assert all(s['text'] and s['page']>=1 and s['source_file'] for s in check['sources']+check['references'])
    assert any(issue.affects_score and issue.field_name==field for issue in result['issues'])


def test_client_errors_are_compared_to_passport_and_do_not_overrule_it():
    result=usa.review_documents(files(client=CLIENT.replace('A12345678','A99999999')))
    checks=[c for c in result['usa_checks'] if c['field']=='passport_number']
    assert any(c['target_category']=='client_form' and c['reference_category']=='passport' and c['status']=='mismatch' for c in checks)
    assert all(c['reference_category']=='passport' for c in checks)
    assert any(c['target_category']=='ds160' and c['status']=='match' for c in checks)
    assert not any(c['target_category']=='ds160' and c['reference_category']=='passport' and c['status']=='mismatch' for c in checks)


def test_confirmation_only_and_missing_documents_are_incomplete_not_a_clean_review(monkeypatch):
    monkeypatch.setattr(usa,'_passport_template',lambda *a:None)
    result=usa.review_documents(files(ds='DS-160 CONFIRMATION\nApplication ID: AA00000000',passport=None,hotel=None))
    assert result['incomplete']
    assert not any(issue.affects_score for issue in result['issues'])
    assert {c['target_category'] for c in result['usa_checks'] if c['field']=='document_coverage' and not c.get('source_file')}=={'passport','hotel'}


def test_home_and_us_contact_addresses_cannot_become_the_stay_address():
    ds=DS+'''Address and Phone Information
Home Address:
Street Address: 99 Home Street
City: CAIRO
U.S. Contact Information
Street Address: 55 Contact Street
City: BOSTON
'''
    result=usa.review_documents(files(ds=ds))
    document=next(d for d in result['usa_documents'] if d['category']=='ds160')
    assert document['fields']['stay_city']['value']=='NEW YORK'
    assert document['fields']['hotel_address']['value']=='100 Main Street'
    assert not any(c['status']=='mismatch' for c in result['usa_checks'])


def test_passport_book_number_is_never_used_as_the_passport_number():
    ds=DS.replace('Passport/Travel Document Number: A12345678','Passport/Travel Document Number:\nPassport Book Number\n1234567')
    result=usa.review_documents(files(ds=ds))
    check=next(c for c in result['usa_checks'] if c['field']=='passport_number' and c['reference_category']=='passport')
    assert check['status']=='needs_verification' and check['found'] is None


def test_multiple_hotels_cover_the_whole_trip_and_use_first_hotel_city():
    uploaded=files(hotel=HOTEL.replace('2027-05-20','2027-05-15'))
    uploaded['hotel'].append(('second.pdf',pdf_bytes(HOTEL.replace('2027-05-10','2027-05-15').replace('New York City','Boston'))))
    result=usa.review_documents(uploaded)
    assert next(c for c in result['usa_checks'] if c['field']=='hotel_coverage_gap')['status']=='match'
    assert not any(c['field']=='stay_city' and c['status']=='mismatch' for c in result['usa_checks'])


def test_hotel_scope_ignores_guests_prices_city_and_address():
    hotel=HOTEL.replace('JOHN MICHAEL DOE','OTHER GUEST').replace('New York City','Boston').replace('100 Main St.','999 Different Road')
    result=usa.review_documents(files(hotel=hotel))
    hotel_fields=next(d['fields'] for d in result['usa_documents'] if d['category']=='hotel')
    assert set(hotel_fields)=={'hotel_name','check_in_date','check_out_date'}
    assert not any(c['status']=='mismatch' and (c['target_category']=='hotel' or c['reference_category']=='hotel') for c in result['usa_checks'])


def test_ten_travel_days_can_include_both_arrival_and_departure_days():
    result=usa.review_documents(files(hotel=HOTEL.replace('2027-05-20','2027-05-19'),client=CLIENT.replace('2027-05-20','2027-05-19')))
    assert not any(c['status']=='mismatch' and c['field'] in ('hotel_coverage_gap','check_out_date','departure_date') for c in result['usa_checks'])
    assert any(len(c.get('possible_departure_dates',[]))==2 for c in result['usa_checks'])


def test_a_gap_between_hotels_is_a_confirmed_coverage_problem():
    uploaded=files(hotel=HOTEL.replace('2027-05-20','2027-05-14'))
    uploaded['hotel'].append(('second.pdf',pdf_bytes(HOTEL.replace('2027-05-10','2027-05-15'))))
    result=usa.review_documents(uploaded)
    assert next(c for c in result['usa_checks'] if c['field']=='hotel_coverage_gap')['status']=='mismatch'


def test_ambiguous_numeric_dates_and_ocr_are_not_confirmed_errors(monkeypatch):
    result=usa.review_documents(files(ds=DS.replace('15 JAN 1990','05/06/1990')))
    assert next(c for c in result['usa_checks'] if c['field']=='date_of_birth' and c['reference_category']=='passport')['status']=='needs_verification'
    original=usa._read
    def read(name,raw,conversion=None):
        rows,notes=original(name,raw,conversion)
        if name=='ds160.pdf':
            for row in rows:row['method']='local_ocr'
        return rows,notes
    monkeypatch.setattr(usa,'_read',read)
    result=usa.review_documents(files(ds=DS.replace('A12345678','A99999999')))
    assert result['incomplete'] and not any(c['status']=='mismatch' for c in result['usa_checks'])


def test_duplicate_upload_cannot_count_as_an_independent_reference():
    uploaded=files();uploaded['client_form']=[('duplicate.pdf',uploaded['ds160'][0][1])]
    result=usa.review_documents(uploaded)
    assert any(c.get('duplicate_source') and c['status']=='needs_verification' for c in result['usa_checks'])


def test_local_parse_cache_is_reused_and_isolated_from_returned_changes():
    cache=DocumentCache(version='usa-test');uploaded=files()
    result=usa.review_documents(uploaded,extraction_cache=cache)
    result['usa_documents'][0]['fields'].clear()
    again=usa.review_documents(uploaded,extraction_cache=cache)
    assert cache.hits==4 and cache.misses==4
    assert again['usa_documents'][0]['fields']


def test_usa_has_exactly_four_slots_and_schengen_upload_validation_stays_separate():
    assert upload_slot_order(program='usa')==list(USA_CATEGORIES)
    validate_uploads(files(),allowed_categories=USA_CATEGORIES)
    with pytest.raises(ValueError):validate_uploads(files())
    with pytest.raises(ValueError):validate_uploads({'flight':[('a.pdf',pdf_bytes('test'))]},allowed_categories=USA_CATEGORIES)


@pytest.mark.parametrize('lang',['en','ar'])
def test_usa_upload_ui_is_bilingual_and_has_no_other_categories(monkeypatch,lang):
    monkeypatch.setattr(accounts,'upload_category_order',Mock(side_effect=AssertionError('Unrelated order query')))
    ui=AppTest.from_string('''
import app
app._init_session_state()
app.render_upload_ui()
''',default_timeout=30)
    ui.session_state.lang=lang;ui.session_state.visa_program='usa';ui.run()
    assert not ui.exception
    assert [u.proto.label for u in ui.get('file_uploader')]==[t('doc_'+key,lang) for key in USA_CATEGORIES]
    assert not ui.selectbox
    assert any(c.value==t('usa_privacy',lang) for c in ui.caption)
    assert not any(t('program_usa',lang) in option and t('under_processing',lang) in option for option in ui.segmented_control(key='visa_program').options)
    ui.segmented_control(key='visa_program').set_value('schengen').run()
    assert not ui.exception and ui.session_state.upload_generation==1
    assert len(ui.get('file_uploader'))==13


def test_first_usa_submit_uses_only_local_pipeline_and_shared_quota(monkeypatch):
    import session_resume
    monkeypatch.setattr(session_resume,'browser_state',lambda *a,**kw:dict(ready=True,handle=None))
    import streamlit as st
    from pathlib import Path
    actor=accounts.Actor('synthetic','synthetic@example.com',True,'user')
    monkeypatch.setattr(accounts,'verified_actor',lambda *a,**kw:actor)
    monkeypatch.setattr(accounts,'refresh_if_needed',lambda client,session:session)
    monkeypatch.setattr(accounts,'service_controls',lambda:dict(maintenance_enabled=False,reviews_enabled=True))
    monkeypatch.setattr(accounts,'ensure_service_available',Mock())
    reserve=Mock();monkeypatch.setattr(accounts,'reserve_review',reserve)
    monkeypatch.setattr(accounts,'finish_attempt',Mock())
    log=Mock();monkeypatch.setattr(accounts,'log_review',log)
    monkeypatch.setattr(settings,'setting',lambda key:'test' if key.startswith('SUPABASE_') else '')
    monkeypatch.setattr(recovery,'recovery_tokens',lambda:None)
    import narrative_reviewer.service as service
    gemini=Mock(side_effect=AssertionError('USA must not call Gemini'));monkeypatch.setattr(service,'run_review',gemini)
    uploaded=files()
    widgets={category:[SimpleNamespace(name=name,getvalue=lambda raw=raw:raw) for name,raw in group] for category,group in uploaded.items()}
    monkeypatch.setattr(st,'file_uploader',lambda *a,**kw:widgets.get(kw['key'].removeprefix('upload_0_'),[]))
    ui=AppTest.from_file(Path(__file__).resolve().parents[1]/'app.py',default_timeout=30)
    ui.session_state.auth_client=object();ui.session_state.actor=actor
    ui.session_state.supabase_session=SimpleNamespace(expires_at=time.time()+1000,access_token='test',refresh_token='test')
    ui.session_state.visa_program='usa';ui.run()
    for key,values in widgets.items():ui.session_state['upload_0_'+key]=values
    ui.text_input(key='client_name').set_value('Synthetic USA Client')
    ui.button(key='run_review_submit').click().run()
    assert not ui.exception and not ui.error
    result=ui.session_state.review_result
    assert result['visa_program']=='usa' and result['engine']==usa.VERSION
    assert result['client_name']=='Synthetic USA Client'
    assert not result['incomplete'] and not result['narrative_requested']
    assert 'narrative_review' not in result
    reserve.assert_called_once();gemini.assert_not_called()
    assert log.call_args.args[3]=='USA'
    assert any(d.label==t('usa_download_json','en') for d in ui.get('download_button'))
