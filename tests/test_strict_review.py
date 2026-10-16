from unittest.mock import Mock
import pytest
from extractor import IdentityEvidence, NarrativeSection, WritingRecommendation
from validator import run_validation, _names_match, Severity
from writing_review import writing_recommendations
import accounts


@pytest.mark.parametrize('other',['ANNA MARIA ERIKSON','ANNA MARIE ERIKSSON','ANNA MARIA SMITH','ANNA MARIA MARIA ERIKSSON','A MARIA ERIKSSON'])
def test_name_subsets_initials_and_single_character_changes_never_pass(other):
    assert not _names_match('ANNA MARIA ERIKSSON',other)


@pytest.mark.parametrize('other',['ERIKSSON, ANNA MARIA','anna   maria eriksson','ERIKSSON<<ANNA<MARIA'])
def test_typography_and_name_order_are_not_spelling_errors(other):
    assert _names_match('ANNA MARIA ERIKSSON',other)


@pytest.mark.parametrize('doc',['visa_form','flight','hotel'])
def test_booking_and_application_name_typo_is_critical(complete_extraction,doc):
    if doc=='visa_form':complete_extraction.visa_form.applicant_name='MG TEST APPLICANX'
    elif doc=='flight':complete_extraction.flight.passenger_name='MG TEST APPLICANX'
    else:complete_extraction.hotel[0].guest_name='MG TEST APPLICANX'
    assert any(i.field_name=='applicant_name' and i.severity==Severity.CRITICAL for i in run_validation(complete_extraction))


@pytest.mark.parametrize('doc',['visa_form','flight','hotel'])
@pytest.mark.parametrize('field',['passport_issue','passport_expiry'])
def test_identity_dates_are_exact_and_critical(complete_extraction,doc,field):
    complete_extraction.passport.passport_issue='2020-01-01'
    target=complete_extraction.hotel[0] if doc=='hotel' else getattr(complete_extraction,doc)
    setattr(target,field,'2025-01-01')
    assert any(i.field_name==field and i.severity==Severity.CRITICAL for i in run_validation(complete_extraction))


def test_second_flight_identity_is_not_lost(complete_extraction):
    complete_extraction.identity_evidence=[IdentityEvidence(document='flight',source_file='second.pdf',page=2,
        full_name='MG TEST APPLICANT',passport_number='TESX12345')]
    assert any('second.pdf' in i.document_name and i.field_name=='passport_number' for i in run_validation(complete_extraction))


def test_national_id_dates_use_national_id_reference(complete_extraction):
    complete_extraction.national_id.present=True
    complete_extraction.national_id.id_number='TEST-ID'
    complete_extraction.national_id.issue_date='2022-01-01'
    complete_extraction.national_id.expiry_date='2032-01-01'
    complete_extraction.visa_form.national_id_issue='2022-01-01'
    complete_extraction.visa_form.national_id_expiry='2032-01-02'
    issues=run_validation(complete_extraction)
    assert any(i.field_name=='national_id_expiry' and i.severity==Severity.CRITICAL for i in issues)
    assert not any(i.field_name=='national_id_issue' for i in issues)


def test_unreadable_identity_is_unresolved_critical(complete_extraction):
    complete_extraction.identity_evidence=[IdentityEvidence(document='hotel',source_file='booking.pdf',
        full_name='MG TEST APPLICANT',unreadable_fields=['passport_number'])]
    assert any(i.message_key=='identity.unreadable' for i in run_validation(complete_extraction))


def test_missing_unprinted_booking_passport_fields_are_not_invented(complete_extraction):
    assert not run_validation(complete_extraction)


def test_cross_script_names_require_manual_verification(complete_extraction):
    complete_extraction.national_id.present=True
    complete_extraction.national_id.id_number='TEST-ID'
    complete_extraction.national_id.full_name='أحمد محمد'
    assert any(i.message_key=='identity.unreadable' for i in run_validation(complete_extraction))


def test_combined_sections_accept_grounded_edit_and_reject_invented_quote(complete_extraction):
    section=NarrativeSection(present=True,source_files=['combined.pdf'],source_text='Dear Sir. TEMPLATE PLACEHOLDER.',
        recommendations=[WritingRecommendation(action='remove',source_file='combined.pdf',original_text='TEMPLATE PLACEHOLDER.',reason='Delete unused template text.'),
                         WritingRecommendation(action='remove',source_file='combined.pdf',original_text='I will stay forever',reason='Invented')])
    complete_extraction.cover_letter_text=section
    complete_extraction.travel_plan=NarrativeSection(present=True,source_files=['combined.pdf'],source_text='Paris visit.',start_date='2027-01-01',end_date='2027-01-10',cities=['Paris'])
    edits=writing_recommendations(complete_extraction,source_texts={'combined.pdf':'Dear Sir. TEMPLATE PLACEHOLDER. Paris visit.'})
    assert len(edits['cover_letter'])==1
    assert edits['travel_plan'][0].action=='add'
    assert any(edit.day=='2027-01-01' for edit in edits['travel_plan'])


def test_quote_must_also_exist_in_actual_text_pdf(complete_extraction):
    complete_extraction.cover_letter_text=NarrativeSection(present=True,source_files=['a.pdf'],source_text='invented',
        recommendations=[WritingRecommendation(action='remove',source_file='a.pdf',original_text='invented',reason='No')])
    assert not writing_recommendations(complete_extraction,source_texts={'a.pdf':'actual'})['cover_letter']


def test_combined_heading_quotes_use_actual_source_not_incomplete_model_transcript(complete_extraction):
    complete_extraction.cover_letter_text=NarrativeSection(present=True,source_files=['combined.pdf'],source_text='Letter summary')
    complete_extraction.travel_plan=NarrativeSection(present=True,source_files=['combined.pdf'],source_text='Plan summary')
    raw='COVER LETTER\nLetter summary\nINSERT CLIENT NAME HERE\nTRAVEL PLAN\nPlan summary\n[DATE]'
    edits=writing_recommendations(complete_extraction,'ar',{'combined.pdf':raw})
    assert any(e.original_text=='INSERT CLIENT NAME HERE' for e in edits['cover_letter'])
    assert not any(e.original_text=='[DATE]' for e in edits['cover_letter'])
    assert any(e.original_text=='[DATE]' for e in edits['travel_plan'])


@pytest.mark.parametrize('lang',['en','ar'])
def test_missing_writing_has_specific_advice(lang):
    from extractor import VisaDocumentExtraction
    edits=writing_recommendations(VisaDocumentExtraction(),lang)
    assert len(edits['cover_letter'])==4 and len(edits['travel_plan'])==1
    assert all(e.reason for e in edits['cover_letter'])


@pytest.mark.parametrize('name',['ab','has spaces','_bad','a'*33,'أحمد'])
def test_invalid_username_rejected_without_network(name):
    assert not accounts.valid_username(name)


@pytest.mark.parametrize('password',['abcdef','123456','!!!!!!'])
def test_signup_six_character_password_without_character_rules(monkeypatch,password):
    db=Mock();db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data=[]
    monkeypatch.setattr(accounts,'admin_client',lambda:db)
    client=Mock();accounts.signup(client,'Test.User','test@example.com',password)
    request=client.auth.sign_up.call_args.args[0]
    assert request['options']['data']=={'username':'test.user'} and request['password']==password


def test_short_password_rejected_before_signup():
    client=Mock()
    with pytest.raises(accounts.AccountError,match='password_short'):
        accounts.signup(client,'testuser','test@example.com','abcde')
    client.auth.sign_up.assert_not_called()


def test_id_number_without_reference_is_visible_without_deduction(complete_extraction):
    from scorer import calculate_score
    d=complete_extraction
    baseline=calculate_score(run_validation(d)).score
    d.identity_evidence=[IdentityEvidence(document='passport',source_file='passport.pdf',page=1,
        national_id_number='30001011234567')]
    issues=run_validation(d)
    notes=[i for i in issues if i.message_key=='identity.id_reference_note']
    assert len(notes)==1 and not notes[0].affects_score
    assert notes[0].found_value=='30001011234567' and 'does not deduct points' in notes[0].recommended_fix
    result=calculate_score(issues)
    assert result.score==baseline and result.critical_count==0 and not result.provisional
    assert result.readiness=='checks_passed'


def test_readable_id_number_mismatch_still_deducts(complete_extraction):
    from extractor import NationalIDInfo
    from scorer import calculate_score
    d=complete_extraction
    d.national_id=NationalIDInfo(present=True,full_name=d.passport.full_name,id_number='30001011234567')
    d.passport.national_id_number='30001011234568'
    issues=run_validation(d)
    assert any(i.field_name=='national_id_number' and i.message_key=='identity.mismatch'
               and i.affects_score and i.severity==Severity.CRITICAL for i in issues)
    assert calculate_score(issues).score<100


def test_other_unresolved_identity_fields_remain_scored(complete_extraction):
    d=complete_extraction
    d.identity_evidence=[IdentityEvidence(document='hotel',source_file='hotel.pdf',
        unreadable_fields=['passport_number'])]
    issues=run_validation(d)
    assert any(i.field_name=='passport_number' and i.message_key=='identity.unreadable'
               and i.affects_score and i.severity==Severity.CRITICAL for i in issues)


def test_null_absent_sections_preserve_missing_evidence():
    from extractor import VisaDocumentExtraction
    data=VisaDocumentExtraction.model_validate({'business':None,'passport':None,'travel_plan':None,'identity_evidence':None})
    assert data.business.company_name is None and data.passport.passport_number is None
    assert not data.travel_plan.present and data.identity_evidence==[]
    assert any(i.severity==Severity.CRITICAL for i in run_validation(data))


def test_duplicate_username_is_explicit(monkeypatch):
    db=Mock();db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data=[{'id':'existing'}]
    monkeypatch.setattr(accounts,'admin_client',lambda:db)
    with pytest.raises(accounts.AccountError,match='username_taken'):
        accounts.signup(Mock(),'existing','test@example.com','abcdefgh')
