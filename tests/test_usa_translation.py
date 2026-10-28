"""Local bilingual checks use synthetic values and preserve original evidence."""
import pymupdf
import pytest
from usa_translation import assess
from usa_review import _same,compare,_issues,extract_fields
from usa_templates import ds_fields
from tests.test_usa_review import files,DS,CLIENT,PASSPORT


@pytest.mark.parametrize('field,left,right',[
    ('occupation','DISTRIBUTION SUPERVISOR','مشرف توزيع'),
    ('employer_name','AHMED HASSAN FOR TRADING AND DISTRIBUTION OF PHARMACEUTICALS','احمد حسن لتجاره و لتوزريع الادويه'),
    ('education_name','ALEXANDRIA UNIVERSITY','كليه تربيه رياضيه جامعه الاسكندريه'),
    ('education_course','BACHELOR OF PHYSICAL EDUCATION','تدريب وتدريس كره يد'),
    ('languages','ARABIC / ENGLISH','English'),
    ('languages','Arabic / English','الإنجليزية'),
    ('nationality','مصري','EGY'),
    ('birth_country','EGY','مصر'),
])
def test_compatible_language_and_translation_values(field,left,right):
    assert _same(field,left,right) is True
    assert assess(field,left,right)['equivalent'] is True


@pytest.mark.parametrize('field,left,right',[
    ('occupation','DOCTOR','مشرف توزيع'),
    ('education_course','BACHELOR OF ACCOUNTING','تربية رياضية'),
    ('education_course','FOOTBALL TRAINING','تدريب كره يد'),
    ('education_course','MASTERS OF PHYSICAL EDUCATION','بكالوريوس تربيه رياضيه'),
    ('education_name','Faculty of Medicine Cairo University','كليه هندسه جامعه القاهره'),
    ('education_name','CAIRO UNIVERSITY','جامعه الاسكندريه'),
    ('languages','Arabic','English'),
])
def test_known_semantic_differences_remain_differences(field,left,right):
    assert _same(field,left,right) is False


@pytest.mark.parametrize('field,left,right',[
    ('occupation','SPECIALIST CONSULTANT','استشاري متخصص'),
    ('employer_name','SYNTHETIC INDUSTRIES','شركة تجريبية'),
    ('languages','ARABIC / ENGLISH YES','English'),
    ('languages','English / Unsupported','English'),
])
def test_unknown_wording_is_verification_not_confirmed_error(field,left,right):
    assert _same(field,left,right) is None


def test_identity_never_uses_organization_phonetics():
    assert assess('full_name','AHMED HASSAN','احمد حسن') is None
    assert _same('full_name','AHMED HASSAN','احمد حسن') is None
    assert _same('passport_number','A12345678','A12345679') is False
    assert _same('occupation','استشاري متخصص','استشاري متخصص') is True


def test_unrecognized_translation_has_audit_basis_and_original_quotes():
    def document(category,value):
        source=dict(document=category,source_file=category+'.docx',text=value,page=None,native_section=1)
        return dict(category=category,source_file=source['source_file'],sha256=category,limitations=[],
                    fields={'occupation':dict(value=value,status='extracted',sources=[source])})
    docs=[document('ds160','SPECIALIST CONSULTANT'),document('client_form','استشاري متخصص')]
    checks=compare(docs)
    check=next(c for c in checks if c['field']=='occupation')
    assert check['status']=='needs_verification'
    assert check['found']=='SPECIALIST CONSULTANT' and check['expected']=='استشاري متخصص'
    assert check['language_comparison']['method'] and check['language_comparison']['basis']
    issue=next(i for i in _issues(checks) if i.field_name=='occupation')
    assert not issue.affects_score and 'translation' in issue.recommended_fix


def test_ds_languages_exclude_next_question_answer_with_different_baselines():
    with pymupdf.open() as doc:
        page=doc.new_page()
        page.insert_text((28,60),'Online Nonimmigrant Visa Application',fontsize=10)
        for y,label,value in [(110,'Name Provided:','DOE, JANE'),(134,'Sex:','FEMALE'),
                              (158,'Language Name (1):','ARABIC'),(182,'Language Name (2):','ENGLISH')]:
            page.insert_text((38,y),label,fontsize=8)
            page.insert_text((335,y),value,fontsize=8)
        page.insert_text((38,212),'Have you traveled to any countries within five years?',fontsize=8)
        page.insert_text((335,210.6),'YES',fontsize=8)
        raw=doc.tobytes()
    assert ds_fields(raw,'ds.pdf')['languages']['value']=='ARABIC / ENGLISH'


def test_client_identity_always_uses_passport_even_when_missing():
    uploaded=files(passport=None)
    documents=[extract_fields(category,name,raw) for category,group in uploaded.items() for name,raw in group]
    identity={'full_name','surname','given_names','passport_number','passport_issue','passport_expiry','date_of_birth'}
    checks=[c for c in compare(documents) if c['field'] in identity]
    assert checks and all(c['reference_category']=='passport' for c in checks)
    assert all(c['status']=='needs_verification' for c in checks)


def test_client_passport_dates_are_checked_against_passport():
    uploaded=files(client=CLIENT+'Passport Issue Date: 2021-03-15\nPassport Expiry Date: 2031-03-15\n')
    documents=[extract_fields(category,name,raw) for category,group in uploaded.items() for name,raw in group]
    checks=[c for c in compare(documents) if c['target_category']=='client_form' and c['field'] in ('passport_issue','passport_expiry')]
    assert len(checks)==2
    assert all(c['reference_category']=='passport' and c['status']=='mismatch' for c in checks)


def test_year_only_derivation_cannot_disprove_month_detail():
    assert _same('education_period','2016-2022','September 2016 - November 2022') is None
    assert _same('education_period','2016-2022','2016 - 2022') is True
    assert _same('education_period','2016-2022','September 2016 - November 2023') is False
    assert _same('education_period','2016-2022','unreadable') is None
