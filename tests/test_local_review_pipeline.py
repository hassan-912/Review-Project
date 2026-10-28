"""Production routing boundaries and source-state regressions; synthetic data only."""
import json
from unittest.mock import Mock

import pymupdf
import pytest

import local_extraction
from document_sources import unique_uploads
from extractor import VisaDocumentExtraction,PassportInfo,extract_documents
from local_extraction import extract_local_documents,guard_local_issues
from review_pipeline import review_documents
from validator import ValidationIssue,Severity


def pdf(text):
    with pymupdf.open() as doc:
        doc.new_page().insert_text((50,70),text)
        return doc.tobytes()












def test_duplicate_factual_file_in_narrative_slot_stays_local():
    raw=pdf('Factual source duplicated into narrative slot.')
    files={'cover_letter':[('letter.pdf',raw)],'passport':[('passport.pdf',raw)]}
    dedup=unique_uploads(files)
    assert set(dedup)=={'passport'}




def test_form_bridge_maps_exact_template_keys_and_preserves_field_status(monkeypatch):
    source={key:dict(key=key,value=value,normalized_value=value,status=status,page=1,sources=[])
            for key,value,status in [
                ('applicant.given_names','Anna','extracted'),('applicant.surname','Tester','extracted'),
                ('applicant.national_id_number','00001234567890','extracted'),
                ('travel_document.number','X00001230','extracted'),
                ('journey.destination_member_states',['Spain'],'extracted'),
                ('journey.first_entry_member_state','Spain','extracted'),('journey.purposes',['Tourism'],'extracted'),
                ('employment_or_education.name','Example Hospital','needs_verification')]}
    def parse(raw,template,name):
        return dict(source_file=name,template_id=template,status='needs_verification',fields=list(source.values()),limitations=['Shared employer cell needs confirmation.'])
    monkeypatch.setattr(local_extraction,'extract_spain_pdf',parse)
    result=extract_local_documents({'visa_form':[('form.pdf',pdf('Synthetic form.'))]})
    assert result.visa_form.passport_number=='X00001230'
    assert result.visa_form.national_id_number=='00001234567890'
    assert result.visa_form.destination_country=='Spain'
    assert result.visa_form.purpose_of_journey=='Tourism'
    assert result.visa_form.applicant_name=='Anna Tester'
    result.passport.passport_number='X00001234'
    issue=ValidationIssue(document_name='Visa Application Form',field_name='passport_number',found_value='X00001230',
        expected_value='X00001234',severity=Severity.CRITICAL,recommended_fix='Compare source values.')
    guarded=guard_local_issues([issue],result,{'visa_form':[('form.pdf',b'')]})
    assert guarded[0].affects_score  # An unrelated provisional employer does not hide this mismatch.


def test_employer_address_mapping_keeps_applicant_home_address_separate(monkeypatch):
    source=[dict(key=key,value=value,normalized_value=value,status='extracted',page=2,sources=[])
            for key,value in [('employment_or_education.name','Example Company'),
                              ('employment_or_education.address','12 Company Street'),
                              ('applicant.contact.home_address','99 Applicant Home Road')]]
    monkeypatch.setattr(local_extraction,'_form_report',lambda raw,category,name:('schengen_application',
        dict(source_file=name,template_id='schengen_application',status='extracted',fields=source,limitations=[])))
    data=extract_local_documents({'visa_form':[('form.pdf',pdf('Synthetic application'))]})
    assert data.visa_form.employer_name=='Example Company'
    assert data.visa_form.employer_address=='12 Company Street'


def test_hr_company_address_reference_points_to_the_application_employer_field():
    from extractor import SourceField
    from evidence import attach_evidence
    from local_extraction import hr_validation_issues
    data=VisaDocumentExtraction(local_hr_checks=[dict(check='hr.company_address',status='mismatch',
        found='99 Different Street',expected='12 Company Street',message='Company addresses differ.',
        sources=[dict(source_file='hr.pdf',page=1,text='Company address: 99 Different Street')])])
    data.evidence_locations=[SourceField(document='visa_form',source_file='application.pdf',page=1,
        field_name='employer_address',value='12 Company Street',text='12 Company Street')]
    files={'visa_form':[('application.pdf',pdf('Employer address: 12 Company Street'))],
           'employment':[('hr.pdf',pdf('Company address: 99 Different Street'))]}
    issues=hr_validation_issues(data);attach_evidence(issues,data,files)
    assert issues[0].reference_evidence[0]['source_file']=='application.pdf'
    assert issues[0].reference_evidence[0]['field_name']=='employer_address'


def test_unknown_template_cannot_turn_into_a_scored_identity_error():
    result=VisaDocumentExtraction(extraction_mode='local',passport={'passport_number':'X00001234'},
        local_results=[dict(category='visa_form',source_file='unknown.pdf',status='unsupported_template',fields={})])
    issue=ValidationIssue(document_name='Visa Application Form',field_name='full_name',found_value=None,
        expected_value='Anna Tester',severity=Severity.CRITICAL,recommended_fix='Read source.')
    guarded=guard_local_issues([issue],result,{'visa_form':[('unknown.pdf',b'')]})
    assert not guarded[0].affects_score
    assert 'not a confirmed document mismatch' in guarded[0].recommended_fix


def test_two_authoritative_forms_are_not_silently_selected(monkeypatch):
    monkeypatch.setattr(local_extraction,'_form_report',lambda raw,category,name:('schengen_application',
        dict(source_file=name,template_id='schengen_application',status='extracted',fields=[],limitations=[])))
    result=extract_local_documents({'visa_form':[('one.pdf',pdf('One form.')),('two.pdf',pdf('Other form.'))]})
    assert result.visa_form.applicant_name is None
    assert any('Multiple visa_form' in note for note in result.review_limitations)


def test_website_pipeline_finishes_without_key_and_marks_unsupported_files_provisional(monkeypatch):
    steps=[]
    result=review_documents({'visa_form':[('unknown.pdf',pdf('Unsupported official form layout, synthetic source.'))]},progress=steps.append)
    assert steps==[1,2,3,4,5]
    assert result['extraction'].extraction_mode=='local'
    assert result['score'].provisional
    assert not any(issue.affects_score and issue.document_name=='Visa Application Form' for issue in result['issues'])


def test_visible_annotation_evidence_is_grounded_and_hidden_metadata_is_not():
    from document_sources import source_is_grounded
    with pymupdf.open() as document:
        page=document.new_page();page.insert_text((50,50),'Printed form labels with sufficient native text.')
        page.add_freetext_annot(pymupdf.Rect(50,80,250,110),'VISIBLE123',fontsize=12)
        hidden=page.add_freetext_annot(pymupdf.Rect(50,120,250,150),'HIDDEN999',fontsize=12)
        hidden.set_flags(2)
        raw=document.tobytes()
    uploaded={'visa_form':[('form.pdf',raw)]}
    assert source_is_grounded(dict(source_file='form.pdf',page=1,text='VISIBLE123'),uploaded)
    assert not source_is_grounded(dict(source_file='form.pdf',page=1,text='HIDDEN999'),uploaded)


def test_local_annotation_box_is_preserved_and_not_labelled_as_ai():
    from evidence import render_source
    raw=pdf('Printed form with a locally located value.')
    report=dict(source_file='form.pdf',fields=[dict(key='travel_document.number',value='X00001234',
        normalized_value='X00001234',status='extracted',page=1,sources=[dict(text='X00001234',page=1,
        region_pdf_points=[50,80,250,110])])])
    data=VisaDocumentExtraction()
    local_extraction._evidence(data,report,'visa_form',{'travel_document.number':'passport_number'},raw)
    field=data.evidence_locations[0]
    assert field.local_source and field.box
    assert render_source(field.model_dump(),{'visa_form':[('form.pdf',raw)]})[2]=='matched_region'




def test_shared_local_ocr_does_not_mix_concurrent_reviews(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from io import BytesIO
    import time
    import offline_ocr
    from PIL import Image
    active=[];overlap=[]
    def engine(image,**kwargs):
        if active:overlap.append(True)
        active.append(True)
        time.sleep(.02)
        value=str(int(image[0,0,0]))
        active.pop()
        return [([[0,0],[10,0],[10,10],[0,10]],value,.99)],None
    monkeypatch.setattr(offline_ocr,'_engine',lambda:engine)
    inputs=[]
    for color in (10,200):
        output=BytesIO();Image.new('RGB',(20,20),(color,0,0)).save(output,format='PNG');inputs.append(output.getvalue())
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(offline_ocr.image_lines,inputs))
    assert not overlap
    assert [lines[0]['text'] for lines in results]==['10','200']




def test_place_of_birth_is_compared_without_spelling_repair():
    from local_extraction import local_identity_issues
    data=VisaDocumentExtraction(passport={'place_of_birth':'Example Town'},visa_form={'place_of_birth':'EXAMPLE TOWN'})
    assert not local_identity_issues(data)
    data.visa_form.place_of_birth='Other Town'
    issue=local_identity_issues(data)[0]
    assert issue.found_value=='Other Town' and issue.expected_value=='Example Town'
    assert issue.affects_score


def test_confirmed_absence_of_passport_is_not_a_parser_uncertainty():
    data=VisaDocumentExtraction(extraction_mode='local')
    issue=ValidationIssue(document_name='Passport',field_name='passport_number',found_value=None,
        expected_value='Readable passport',severity=Severity.CRITICAL,recommended_fix='Supply the passport.')
    assert guard_local_issues([issue],data,{})[0].affects_score


def test_absent_passport_is_one_upload_action_not_two_missing_field_claims():
    result=review_documents({'visa_form':[('form.pdf',pdf('Unsupported synthetic application'))]})
    issues=[issue for issue in result['issues'] if issue.document_name=='Passport' and issue.affects_score]
    assert len(issues)==1
    assert issues[0].field_name=='passport_upload'
    assert issues[0].message_key=='document.not_uploaded'


def test_unreadable_uploaded_passport_is_not_treated_as_an_absent_passport(monkeypatch):
    monkeypatch.setattr(local_extraction,'extract_egypt_passport',lambda raw,name:dict(
        source_file=name,status='needs_verification',fields={},values={},limitations=['Unreadable MRZ.']))
    result=review_documents({'passport':[('passport.png',b'synthetic image bytes')]})
    issues=[issue for issue in result['issues'] if issue.document_name=='Passport']
    assert issues and all(not issue.affects_score for issue in issues)
    assert not any(issue.field_name=='passport_upload' for issue in issues)


@pytest.mark.parametrize('slots',[('cover_letter',),('travel_plan',),('cover_letter','travel_plan')])
def test_supplied_combined_narrative_is_manual_review_never_a_missing_document(slots):
    raw=pdf('Synthetic combined cover letter and travel plan')
    result=review_documents({slot:[('combined.pdf',raw)] for slot in slots})
    issues=[issue for issue in result['issues'] if issue.document_name in ('Cover Letter','Travel Itinerary')]
    assert issues and all(not issue.affects_score for issue in issues)
    assert sum(len(group) for group in result['source_files'].values())==1


def test_passport_deduplicated_into_another_slot_does_not_become_a_confirmed_absent_upload():
    raw=pdf('An unsupported synthetic file supplied in two factual slots')
    result=review_documents({'passport':[('passport.pdf',raw)],'hotel':[('booking.pdf',raw)]})
    issues=[issue for issue in result['issues'] if issue.document_name=='Passport']
    assert issues and all(not issue.affects_score for issue in issues)
    assert not any(issue.field_name=='passport_upload' for issue in issues)




