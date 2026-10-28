"""Three independently read national ID numbers; no customer data or OCR network calls."""
from io import BytesIO
from types import SimpleNamespace

from PIL import Image
import pymupdf
import pytest

from extractor import NationalIDInfo,SourceField
from validator import run_validation
from evidence import attach_evidence
from local_extraction import extract_local_documents


def id_issues(data):
    return [issue for issue in run_validation(data) if issue.field_name=='national_id_number']


def set_ids(data,passport,translation,application):
    data.passport.national_id_number=passport
    data.national_id=NationalIDInfo(present=bool(translation),full_name=data.passport.full_name,id_number=translation)
    data.visa_form.national_id_number=application


def test_matching_application_and_translation_cannot_override_the_passport(complete_extraction):
    set_ids(complete_extraction,'01234567890123','01234567890124','01234567890124')
    issues=id_issues(complete_extraction)
    assert {issue.document_name for issue in issues}=={'Visa Application Form','National ID'}
    assert all(issue.expected_value=='01234567890123' and issue.affects_score for issue in issues)


@pytest.mark.parametrize('bad_document',['application','translation'])
def test_only_the_conflicting_document_is_flagged(complete_extraction,bad_document):
    set_ids(complete_extraction,'01234567890123',
            '01234567890124' if bad_document=='translation' else '01234567890123',
            '01234567890124' if bad_document=='application' else '01234567890123')
    issues=id_issues(complete_extraction)
    assert len(issues)==1
    assert issues[0].document_name==('Visa Application Form' if bad_document=='application' else 'National ID')


def test_digit_scripts_match_without_changing_identifier_digits(complete_extraction):
    set_ids(complete_extraction,'01234567890123','٠١٢٣٤٥٦٧٨٩٠١٢٣','۰۱۲۳۴۵۶۷۸۹۰۱۲۳')
    assert id_issues(complete_extraction)==[]


def test_readable_passport_id_can_check_application_without_id_translation(complete_extraction):
    set_ids(complete_extraction,'01234567890123',None,'01234567890124')
    issue,=id_issues(complete_extraction)
    assert issue.document_name=='Visa Application Form' and issue.expected_value=='01234567890123'


def test_translation_is_a_fallback_when_passport_id_is_unreadable(complete_extraction):
    set_ids(complete_extraction,None,'01234567890123','01234567890124')
    issue,=id_issues(complete_extraction)
    assert issue.document_name=='Visa Application Form' and issue.expected_value=='01234567890123'


def test_missing_independent_id_reference_is_not_a_confirmed_error(complete_extraction):
    set_ids(complete_extraction,None,None,'01234567890123')
    issue,=id_issues(complete_extraction)
    assert not issue.affects_score and issue.message_key=='identity.id_reference_note'


def test_unrelated_unreadable_translation_field_does_not_hide_a_readable_id_mismatch(complete_extraction):
    from local_extraction import guard_local_issues
    data=complete_extraction;data.extraction_mode='local'
    set_ids(data,'01234567890123','01234567890124','01234567890123')
    data.local_results=[dict(category='national_id',source_file='translation.pdf',status='needs_verification',
                             target_states={'id_number':'extracted','issue_date':'unverified'})]
    issue,=id_issues(data)
    guard_local_issues([issue],data,{'national_id':[('translation.pdf',b'local bytes')]})
    assert issue.affects_score and issue.expected_value=='01234567890123'


def test_passport_id_is_mapped_with_its_actual_image_region(monkeypatch):
    import local_extraction
    number='01234567890123';box=[.625,.596,.835,.642]
    monkeypatch.setattr(local_extraction,'extract_egypt_passport',lambda raw,name:dict(
        source_file=name,template_id='egypt_passport.v1',status='extracted',limitations=[],
        fields={'national_id_number':dict(value=number,status='extracted',sources=[
            dict(text='٠١٢٣٤٥٦٧٨٩٠١٢٣',page=1,region_normalized=box)])}))
    data=extract_local_documents({'passport':[('passport.png',b'local image bytes')]})
    assert data.passport.national_id_number==number
    assert data.identity_evidence[0].national_id_number==number
    source=data.evidence_locations[0]
    assert source.field_name=='national_id_number' and source.box==box and source.local_source


def test_id_mismatch_evidence_references_the_passport_not_the_conflicting_translation(complete_extraction):
    data=complete_extraction
    set_ids(data,'01234567890123','01234567890124','01234567890124')
    image=BytesIO();Image.new('RGB',(600,400),'white').save(image,format='PNG')
    uploads={'passport':[('passport.png',image.getvalue())]}
    for category,filename,number in [('visa_form','application.pdf',data.visa_form.national_id_number),
                                      ('national_id','translation.pdf',data.national_id.id_number)]:
        with pymupdf.open() as doc:
            doc.new_page().insert_text((50,80),'National identity number: '+number)
            uploads[category]=[(filename,doc.tobytes())]
    data.evidence_locations=[SourceField(document=category,source_file=filename,page=1,
        field_name='national_id_number',value=number,text=number,box=[.1,.1,.5,.2],local_source=True)
        for category,filename,number in [('passport','passport.png',data.passport.national_id_number),
                                          ('visa_form','application.pdf',data.visa_form.national_id_number),
                                          ('national_id','translation.pdf',data.national_id.id_number)]]
    issues=id_issues(data);attach_evidence(issues,data,uploads)
    assert len(issues)==2
    assert all(issue.reference_evidence[0]['source_file']=='passport.png' for issue in issues)
    assert {issue.evidence[0]['source_file'] for issue in issues}=={'application.pdf','translation.pdf'}


def test_shared_arabic_recognizer_resets_detection_before_reading_hr(monkeypatch):
    import offline_ocr
    calls=[]
    def engine(image,**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(txts=['01234567890123'],scores=[.99],boxes=[[[0,0],[10,0],[10,10],[0,10]]])
    monkeypatch.setattr(offline_ocr,'_arabic_engine',lambda:engine)
    image=BytesIO();Image.new('RGB',(100,20),'white').save(image,format='PNG')
    offline_ocr.arabic_image_line(image.getvalue())
    offline_ocr.arabic_image_lines(image.getvalue())
    assert [call['use_det'] for call in calls]==[False,True]
