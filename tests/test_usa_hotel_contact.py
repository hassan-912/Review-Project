"""Hotel-contact workflow and explicit document provenance; synthetic inputs."""
from io import BytesIO
import json

import pymupdf
import pytest
from streamlit.testing.v1 import AppTest

from i18n import t
from tests.test_usa_review import files
from tests.test_usa_templates import columns,booking
from usa_review import review_documents
from usa_templates import client_text_fields
from usa_ui import document_sources,verification_rows


def packet(person='DOE, JANE',organization='DO NOT KNOW',relationship='RELATIVE',hotel_email=False):
    rows=[('Contact Person Name in the U.S.:',person),('Organization Name in the U.S.:',organization),
          ('Relationship to You:',relationship),('U.S. Contact Address:','SOME PERSONAL ADDRESS'),
          ('Phone Number:','5555555555555'),('Email Address:','relative@example.test')]
    with pymupdf.open(stream=columns(rows),filetype='pdf') as contact:
        contact[0].insert_text((28,85),'U.S. Contact Information',fontsize=12)
        uploaded=files()
        with pymupdf.open(stream=uploaded['ds160'][0][1],filetype='pdf') as doc:
            doc.insert_pdf(contact);uploaded['ds160']=[('ds160.pdf',doc.tobytes())]
    with pymupdf.open(stream=booking(),filetype='pdf') as doc:
        page=doc[0]
        page.insert_text((110,94),'Address: 77 Example Road, Example City',fontsize=7)
        page.insert_text((110,115),'Phone: +1 212 555 0100',fontsize=7)
        if hotel_email:page.insert_text((110,134),'Email: hotel@example.test',fontsize=7)
        page.insert_text((80,650),'Confirmation sent to traveler@example.test',fontsize=8)
        uploaded['hotel']=[('hotel.pdf',doc.tobytes())]
    return uploaded


def test_relative_contact_is_flagged_against_printed_hotel_details():
    result=review_documents(packet())
    check=next(c for c in result['usa_checks'] if c['field']=='us_contact_hotel')
    assert check['status']=='mismatch'
    assert 'DOE, JANE' in check['found'] and 'RELATIVE' in check['found']
    assert 'Synthetic Riverside Hotel' in check['expected']
    assert '77 Example Road, Example City' in check['expected'] and '+1 212 555 0100' in check['expected']
    assert 'relative@example.test' not in check['expected'] and 'traveler@example.test' not in check['expected']
    assert check['unavailable_contact_fields']==['hotel_email']
    assert all(s['document']=='ds160' and s['source_file']=='ds160.pdf' and s['page']==2 for s in check['sources'])
    assert all(s['document']=='hotel' and s['source_file']=='hotel.pdf' and s['page']==1 for s in check['references'])
    assert check['rule_basis']=='configured_hotel_contact_workflow'
    assert next(i for i in result['issues'] if i.field_name=='us_contact_hotel').check_origin=='local_workflow_rule'


def test_printed_hotel_email_can_be_used_but_guest_email_cannot():
    result=review_documents(packet(hotel_email=True))
    check=next(c for c in result['usa_checks'] if c['field']=='us_contact_hotel')
    assert 'hotel@example.test' in check['expected'] and not check['unavailable_contact_fields']
    assert 'traveler@example.test' not in check['expected']


def test_hotel_contact_not_reclassified_as_applicant_email_or_name():
    result=review_documents(packet())
    ds=next(d for d in result['usa_documents'] if d['category']=='ds160')['fields']
    assert ds['full_name']['value']=='JOHN MICHAEL DOE'
    assert ds['us_contact_person']['value']=='DOE, JANE'
    assert ds['us_contact_email']['value']=='relative@example.test'
    assert 'email' not in ds


def test_named_hotel_staff_and_matching_organization_are_not_assumed_to_be_a_relative():
    result=review_documents(packet(organization='Synthetic Riverside Hotel',relationship='OTHER'))
    assert not any(c['field']=='us_contact_hotel' and c['status']=='mismatch' for c in result['usa_checks'])


def test_rule_does_not_run_without_a_supplied_hotel():
    uploaded=packet();uploaded.pop('hotel')
    assert not any(c['field']=='us_contact_hotel' for c in review_documents(uploaded)['usa_checks'])


@pytest.mark.parametrize('lang',['en','ar'])
def test_reference_value_and_its_file_page_are_separate_columns(lang):
    result=review_documents(packet())
    check=next(c for c in result['usa_checks'] if c['field']=='us_contact_hotel')
    row=verification_rows(result,[check],lang)[0]
    assert row[t('usa_checked_value',lang)]==check['found']
    assert row[t('usa_comparison_value',lang)]==check['expected']
    assert 'ds160.pdf' in row[t('usa_checked_document',lang)]
    assert t('page',lang)+' 2' in row[t('usa_checked_document',lang)]
    assert 'hotel.pdf' in row[t('usa_comparison_document',lang)]
    assert t('page',lang)+' 1' in row[t('usa_comparison_document',lang)]
    missing=dict(field='document_coverage',target_category='passport',reference_category='passport',found=None,
        expected='Verify document readability',sources=[],references=[],source_file='passport.jpeg')
    row=verification_rows(result,[missing],lang)[0]
    assert row[t('usa_comparison_value',lang)] is None
    assert 'passport.jpeg' in row[t('usa_checked_document',lang)]
    assert 'Verify document readability' not in str(row)


def test_reference_screenshots_render_the_hotel_file_in_the_right_column():
    result=review_documents(packet())
    ui=AppTest.from_string('''
import streamlit as st
from usa_ui import _comparison_evidence
result=st.session_state.result
issue=next(i for i in result['issues'] if i.field_name=='us_contact_hotel')
_comparison_evidence(issue,result,'en')
''',default_timeout=30)
    ui.session_state.result=result;ui.run()
    assert not ui.exception
    cache=ui.session_state.result.get('reference_images_v1')
    assert cache and all('hotel.pdf' in key and 'ds160.pdf' not in key for key in cache)
    assert all(value is not None for value in cache.values())
    assert all('ds160.pdf' in key for key in ui.session_state.result['correction_images_v3'])


def test_bilingual_word_client_table_has_native_section_provenance_and_no_secrets():
    text='''U.S. Visa Client Information Form
الاسم Full name as in passport / | JOHN MICHAEL DOE
تاريخ الميلاد Date of birth / | 1990/01/15
Company / employer name / جهة العمل | SAMPLE COMPANY
U.S. visa appointment account password / | DO_NOT_EXPORT
Security question 1 / | PRIVATE_QUESTION
Answer 1 / | PRIVATE_ANSWER
'''
    fields=client_text_fields(text,'client.docx.pdf')
    assert fields['full_name']['value']=='JOHN MICHAEL DOE'
    assert fields['employer_name']['value']=='SAMPLE COMPANY'
    assert all(s['page'] is None and s['native_section'] for field in fields.values() for s in field['sources'])
    assert 'PRIVATE' not in json.dumps(fields) and 'DO_NOT_EXPORT' not in json.dumps(fields)
    source=fields['full_name']['sources'][0]
    label=document_sources({'usa_documents':[]},[source],'en')
    assert 'client.docx.pdf' in label and 'Text section 2' in label
