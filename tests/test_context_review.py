"""Context regressions from a failed report; all identities and PDFs are synthetic."""
from types import SimpleNamespace
from unittest.mock import Mock
import json
import pytest
import pymupdf
from extractor import (VisaDocumentExtraction, SupportingDocument, SupportingClaim,
                       DocumentAudit, PassportInfo, NarrativeSection)
from context_review import CHECKS, parse_context, review_context
from validator import (run_validation, _check_schengen_destination_rule,
                       _check_employment_leave_dates, _check_missing_fields, ValidationIssue, Severity)
from supporting_review import check_supporting, extraction_quality
from scorer import calculate_score
from document_sources import unique_uploads, source_is_grounded
from evidence import attach_evidence


def pdf(*pages):
    with pymupdf.open() as doc:
        for text in pages:
            page=doc.new_page()
            if text:page.insert_text((50,60),text)
        return doc.tobytes()


def context_payload(names=('letter.pdf',)):
    return dict(checks=[{'check':key,'status':'clear','explanation':'Reviewed synthetic source'} for key in CHECKS],
        document_audits=[dict(source_file=name,document_types=['education'],pages_read=[1],readability='readable',summary='Synthetic university enrollment record') for name in names],
        applicant_status='student',employment_evidence_present=False,cover_letter_present=False,
        cover_letter_sources=[],passport_native_name=None,passport_national_id_number=None,findings=[],
        visa_form={},national_id={},verified_fields=[],
        cover_letter_recommendations=[],travel_plan_recommendations=[],executive_summary='Synthetic student case')


def test_actual_form_destination_is_compared_with_booked_country(complete_extraction):
    complete_extraction.visa_form.destination_country='Austria'
    issues=_check_schengen_destination_rule(complete_extraction)
    assert any(i.field_name=='destination_country' and i.found_value=='Austria' and i.expected_value=='France' for i in issues)


def test_equal_nights_do_not_pick_dictionary_first_country(complete_extraction):
    d=complete_extraction;d.total_nights_per_country={'France':5,'Italy':5}
    d.main_schengen_destination=d.visa_form.destination_country='Italy'
    assert not _check_schengen_destination_rule(d)


@pytest.mark.parametrize('country',['Frankreich','FRA','France'])
def test_destination_language_aliases_are_not_country_mismatches(complete_extraction,country):
    complete_extraction.visa_form.destination_country=country
    assert not _check_schengen_destination_rule(complete_extraction)


@pytest.mark.parametrize('status',['Student, trainee','student','طالب'])
def test_student_is_not_an_employee_due_to_university_in_employer_field(complete_extraction,status):
    d=complete_extraction;d.visa_form.occupation=status
    d.employment.employer_name='Fictional University';d.employment.job_title=None
    d.employment.approved_leave_start=d.employment.approved_leave_end=None
    assert not _check_employment_leave_dates(d)


def test_a_student_with_real_employment_still_gets_hr_checks(complete_extraction):
    d=complete_extraction;d.visa_form.occupation='Student'
    d.employment.evidence_type='employment';d.employment.approved_leave_start=None
    assert _check_employment_leave_dates(d)


def test_arabic_id_matches_independent_native_passport_name(complete_extraction):
    d=complete_extraction;d.passport.native_name='يوسف أحمد علي';d.passport.national_id_number='TEST-ID-123'
    d.national_id.present=True;d.national_id.full_name='يوسف احمد على';d.national_id.id_number='TEST-ID-123'
    d.national_id.issue_date='2020-02';d.national_id.expiry_date='2030-02-15'
    assert not [i for i in run_validation(d) if i.document_name=='National ID']


def test_missing_script_bridge_is_a_review_limit_not_identity_failure(complete_extraction):
    d=complete_extraction;d.national_id.present=True;d.national_id.full_name='يوسف أحمد علي';d.national_id.id_number='SYNTHETIC-ID'
    issues=[i for i in run_validation(d) if i.document_name=='National ID']
    assert len(issues)==1 and not issues[0].affects_score
    result=calculate_score(issues)
    assert result.score==100 and result.provisional and result.readiness=='review_incomplete'


def test_native_name_typo_and_wrong_shared_id_are_still_critical(complete_extraction):
    d=complete_extraction;d.passport.native_name='يوسف أحمد علي';d.passport.national_id_number='ID-1'
    d.national_id.present=True;d.national_id.full_name='يوسف أحمد عمر';d.national_id.id_number='ID-2'
    assert len([i for i in run_validation(d) if i.document_name=='National ID' and i.severity==Severity.CRITICAL])==2


def test_month_only_id_issue_date_compares_at_printed_precision(complete_extraction):
    d=complete_extraction;d.national_id.issue_date='2020-02';d.visa_form.national_id_issue='2020-02-10'
    assert not [i for i in run_validation(d) if i.field_name=='national_id_issue']
    d.visa_form.national_id_issue='2020-03-10'
    assert any(i.field_name=='national_id_issue' and i.severity==Severity.CRITICAL for i in run_validation(d))


def test_unread_pages_never_reduce_the_client_document_score(complete_extraction):
    quality,issues=extraction_quality(complete_extraction,{'supporting':[('paper.pdf',pdf('Synthetic supporting record'))]})
    assert issues and all(not i.affects_score for i in issues)
    score=calculate_score(issues)
    assert score.score==100 and score.provisional and score.readiness=='review_incomplete'


def test_one_missing_cover_letter_is_one_deduction():
    issues=[i for i in _check_missing_fields(VisaDocumentExtraction()) if i.document_name=='Cover Letter']
    assert len(issues)==1 and calculate_score(issues).score==85
    assert all(word in issues[0].found_value for word in ('purpose','funding','ties'))


def test_combined_file_uploaded_twice_is_read_once():
    raw=pdf('Synthetic letter and itinerary content')
    files=unique_uploads({'cover_letter':[('combined.pdf',raw)],'travel_plan':[('combined.pdf',raw)]})
    assert sum(map(len,files.values()))==1


def test_distinct_same_named_sources_remain_unambiguous():
    files=unique_uploads({'supporting':[('record.pdf',pdf('First source')),('record.pdf',pdf('Second source'))]})
    assert len({name for name,_ in files['supporting']})==2


@pytest.mark.parametrize('role',['mother','father','relative','other','unknown'])
def test_other_subjects_identity_is_not_compared_to_applicant(complete_extraction,role):
    d=complete_extraction
    d.supporting_documents=[SupportingDocument(source_file='family.pdf',document_type='Family register',summary='Synthetic family record',
        claims=[SupportingClaim(field_name='date_of_birth',value='1960-01-01',subject_role=role,page=1,quote='Parent born 1960-01-01')])]
    assert not check_supporting(d,{'supporting':[('family.pdf',pdf('Parent born 1960-01-01'))]})


def test_first_name_column_is_not_an_incomplete_booking_name(complete_extraction):
    d=complete_extraction
    d.supporting_documents=[SupportingDocument(source_file='family.pdf',document_type='Family register',summary='Synthetic family record',
        claims=[SupportingClaim(field_name='full_name',value='MG',name_scope='first_only',page=1,quote='Child first name MG')])]
    assert not check_supporting(d,{'supporting':[('family.pdf',pdf('Child first name MG'))]})


def test_non_corroborated_neutral_claim_is_not_automatically_a_document_error(complete_extraction):
    d=complete_extraction
    d.supporting_documents=[SupportingDocument(source_file='bank.pdf',document_type='Bank',summary='Synthetic account',
        claims=[SupportingClaim(field_name='balance',value='10000',page=1,quote='Closing balance 10000')])]
    assert not check_supporting(d,{'supporting':[('bank.pdf',pdf('Closing balance 10000'))]})
    d.supporting_documents[0].claims[0].quote='Model summary, not a verbatim quotation'
    d.supporting_documents[0].claims[0].value='Unconfirmed descriptive summary'
    assert not check_supporting(d,{'supporting':[('bank.pdf',pdf('Closing balance 10000'))]})
    assert d.supporting_documents[0].claims[0].assessment=='unverified'


def test_national_id_claim_is_not_compared_with_passport_number(complete_extraction):
    d=complete_extraction;d.national_id.id_number='SYNTHETIC-CIVIL-ID'
    d.supporting_documents=[SupportingDocument(source_file='id.pdf',document_type='National ID',summary='Synthetic ID',
        claims=[SupportingClaim(field_name='passport_number',value='SYNTHETIC-CIVIL-ID',page=1,quote='SYNTHETIC-CIVIL-ID')])]
    assert not check_supporting(d,{'supporting':[('id.pdf',pdf('SYNTHETIC-CIVIL-ID'))]})
    assert d.supporting_documents[0].claims[0].field_name=='national_id_number'


def test_named_source_coverage_error_does_not_show_other_supporting_files(complete_extraction):
    issue=ValidationIssue(document_name='Supporting Documents (third.pdf)',field_name='document_readability',
        found_value='0 / 1',expected_value='Every page accounted for',severity=Severity.HIGH,recommended_fix='Review again',affects_score=False)
    files={'supporting':[(name,pdf('Synthetic source '+name)) for name in ('first.pdf','second.pdf','third.pdf')]}
    attach_evidence([issue],complete_extraction,files)
    assert [loc['source_file'] for loc in issue.evidence]==['third.pdf']
    assert not issue.reference_evidence


def test_context_quotes_and_exact_pages_survive_evidence_attachment(complete_extraction):
    issue=ValidationIssue(document_name='Visa Application Form',field_name='application_completeness',found_value='Blank email',
        expected_value='Applicant email',severity=Severity.MEDIUM,recommended_fix='Fill email',
        evidence=[dict(source_file='form.pdf',page=2,text='Email address')])
    files={'visa_form':[('form.pdf',pdf('Synthetic first page','Email address'))]}
    attach_evidence([issue],complete_extraction,files)
    assert issue.evidence==[dict(source_file='form.pdf',page=2,text='Email address')]


def test_context_contract_rejects_omitted_audits_and_false_readable_coverage():
    payload=context_payload();manifest={'letter.pdf':{'pages':2}}
    with pytest.raises(ValueError):parse_context(json.dumps(payload),manifest)
    payload['document_audits'][0]['pages_read']=[1,2]
    assert parse_context(json.dumps(payload),manifest)
    payload['document_audits']=[]
    with pytest.raises(ValueError):parse_context(json.dumps(payload),manifest)


def test_context_contract_requires_every_review_criterion():
    payload=context_payload();payload['checks'].pop()
    with pytest.raises(ValueError):parse_context(json.dumps(payload),{'letter.pdf':{'pages':1}})


def test_context_review_clears_hallucinated_letter_and_hr_for_student(monkeypatch,complete_extraction):
    monkeypatch.setattr('context_review.generate_automatically',lambda *a,**kw:json.dumps(context_payload()))
    result=review_context(Mock(),[],{'employment':[('letter.pdf',pdf('Synthetic university enrollment'))]},complete_extraction)
    assert result.cover_letter.purpose_of_visit is None and not result.cover_letter_text.present
    assert result.employment.evidence_type=='education'
    assert not _check_employment_leave_dates(result)


def test_context_unavailability_makes_result_provisional_without_zeroing_score(monkeypatch,complete_extraction):
    from model_routing import ModelUnavailable
    def unavailable(*args,**kwargs):raise ModelUnavailable('models_unavailable')
    monkeypatch.setattr('context_review.generate_automatically',unavailable)
    result=review_context(Mock(),[],{'supporting':[('letter.pdf',pdf('Synthetic source'))]},complete_extraction)
    assert result.review_limitations
    _,issues=extraction_quality(result,{})
    assert calculate_score(issues).provisional and calculate_score(issues).score==100


def test_context_with_fabricated_quote_is_withheld(monkeypatch,complete_extraction):
    payload=context_payload()
    payload['findings']=[dict(document='Supporting Documents',field_name='translation_title',severity='LOW',
        title='Wrong honorific',found='Ms',expected='Mr',fix='Correct title',
        sources=[dict(source_file='letter.pdf',page=1,text='Fabricated quotation')],references=[])]
    monkeypatch.setattr('context_review.generate_automatically',lambda *a,**kw:json.dumps(payload))
    result=review_context(Mock(),[],{'supporting':[('letter.pdf',pdf('Actual synthetic source'))]},complete_extraction)
    assert result.contextual_findings==[] and result.unverified_findings


def test_actual_form_table_blanks_and_country_are_read_independently(complete_extraction):
    from source_checks import printed_form_checks
    with pymupdf.open() as doc:
        page=doc.new_page()
        rows=[('11 National identity number, where applicable',''),
              ("19 Applicant's home address and email address",'Fictional street'),
              ('19a Telephone number(s)',''),
              ('25 Member State of main destination','Italy')]
        for i,(label,value) in enumerate(rows):
            y=50+i*60
            for x in (40,300,550):page.draw_line((x,y),(x,y+60))
            page.draw_line((40,y),(550,y));page.draw_line((40,y+60),(550,y+60))
            page.insert_textbox(pymupdf.Rect(45,y+5,295,y+55),label,fontsize=8)
            if value:page.insert_text((305,y+18),value,fontsize=8)
        raw=doc.tobytes()
    d=complete_extraction;d.national_id.id_number='SYNTHETIC-ID';d.visa_form.national_id_number='COPIED-FROM-OTHER-SOURCE'
    issues=printed_form_checks(d,{'visa_form':[('form.pdf',raw)]})
    assert len(issues)==1 and issues[0].severity==Severity.MEDIUM
    assert all(field in issues[0].found_value for field in ('email','telephone','national_id_number'))
    assert d.visa_form.national_id_number is None and d.visa_form.destination_country=='Italy'
    assert all(loc['layout'] for loc in issues[0].evidence)


def test_numeric_and_written_translation_months_are_compared_without_subject_mixup():
    from source_checks import translation_date_checks
    raw=pdf('Father\nDate of Birth: 14/07/1980 In Words: The fourteenth of June, nineteen eighty')
    issues=translation_date_checks({'supporting':[('family.pdf',raw)]})
    assert len(issues)==1 and issues[0].severity==Severity.LOW
    assert issues[0].field_name=='translation_dob'
    assert not translation_date_checks({'supporting':[('family.pdf',pdf('Date of Birth: 14/06/1980 In Words: The fourteenth of June, nineteen eighty'))]})


def test_quote_punctuation_changes_do_not_hide_an_actual_field_label():
    assert source_is_grounded({'source_file':'form.pdf','page':1,'text':'Telephone number(s):'},
        {'visa_form':[('form.pdf',pdf('Telephone number(s)'))]})


def test_context_hold_cannot_create_a_scored_finding(complete_extraction):
    from context_review import context_issues
    complete_extraction.contextual_findings=[dict(document='flight',field_name='reservation_validity',severity='MEDIUM',
        title='Payment hold needs rechecking',found='On hold',expected='Current validity',fix='Obtain a fresh reservation',
        sources=[dict(source_file='flight.pdf',page=1,text='On hold')],references=[])]
    assert not context_issues(complete_extraction)


def test_flight_day_recommendations_use_final_arrival_and_return_departure(complete_extraction):
    from writing_review import writing_recommendations
    d=complete_extraction;d.flight.arrival_time='19:15';d.flight.return_departure_time='11:40'
    edits=writing_recommendations(d)['travel_plan']
    assert any(e.day=='2027-01-01' and '19:15' in e.reason for e in edits)
    assert any(e.day=='2027-01-10' and '11:40' in e.reason for e in edits)


def test_absent_cover_letter_never_invents_a_sponsor(complete_extraction):
    from writing_review import writing_recommendations
    from extractor import CoverLetterInfo, WritingRecommendation
    d=complete_extraction;d.cover_letter=CoverLetterInfo()
    d.cover_letter_text=NarrativeSection(present=False,recommendations=[WritingRecommendation(action='add',
        reason='Add a letter',replacement='My mother will pay all costs from her business income.')])
    edits=writing_recommendations(d)['cover_letter']
    assert len(edits)==4 and not any('My mother' in (e.replacement or '') for e in edits)
    assert any('[Actual payer]' in (e.replacement or '') for e in edits)


def test_elapsed_flight_hold_is_an_informational_booking_status(complete_extraction):
    from datetime import date
    from source_checks import reservation_and_title_checks
    raw=pdf('BOOKING ON HOLD\nThe fare quoted will be secured for payment within 12 hours. If payment not received reservation will be cancelled.',
            'Date of issue: 01 Oct 2026\nA fictional flight reservation')
    issues=reservation_and_title_checks(complete_extraction,{'flight':[('flight.pdf',raw)]},date(2026,10,3))
    assert not issues
    assert complete_extraction.booking_statuses[0].status=='held'
    assert not reservation_and_title_checks(complete_extraction,{'flight':[('flight.pdf',raw)]},date(2026,10,1))


def test_issued_ticket_is_not_treated_as_unresolved_payment_hold(complete_extraction):
    from datetime import date
    from source_checks import reservation_and_title_checks
    raw=pdf('BOOKING ON HOLD\npayment within 12 hours\nDate of issue: 01 Oct 2026\nE-ticket number: 1234567890123')
    assert not reservation_and_title_checks(complete_extraction,{'flight':[('flight.pdf',raw)]},date(2026,10,3))


def test_translation_honorific_is_checked_for_applicant_only(complete_extraction):
    from source_checks import reservation_and_title_checks
    d=complete_extraction;d.passport.gender='M'
    issues=reservation_and_title_checks(d,{'supporting':[('movement.pdf',pdf('Ms. MG TEST APPLICANT, fictional nationality\nMr. UNRELATED PERSON'))]})
    assert len(issues)==1 and issues[0].field_name=='translation_honorific' and issues[0].severity==Severity.LOW


def test_readable_document_notes_are_not_unread_page_failures(complete_extraction):
    d=complete_extraction;d.document_audits=[DocumentAudit(source_file='form.pdf',pages_read=[1],readability='readable',uncertainties=['Blank signature field'])]
    _,issues=extraction_quality(d,{'visa_form':[('form.pdf',pdf('Fictional legible application'))]})
    assert not issues


def test_pdf_keeps_english_reference_after_arabic_source_name(complete_extraction):
    from pdf_report import build_pdf_report
    issue=ValidationIssue(document_name='National ID',field_name='full_name',found_value='يوسف أحمد علي',
        expected_value='SYNTHETIC EXPECTED PASSPORT NAME',severity=Severity.LOW,recommended_fix='Verify native-script identity')
    raw=build_pdf_report(complete_extraction,[issue],calculate_score([issue]))
    with pymupdf.open(stream=raw,filetype='pdf') as doc:text=''.join(p.get_text() for p in doc)
    assert 'SYNTHETIC EXPECTED PASSPORT NAME' in text
