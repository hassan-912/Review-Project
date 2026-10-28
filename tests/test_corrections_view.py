"""Corrections-only output, escaped values and a traceable engine receipt."""
import json

import pymupdf
import pytest
from streamlit.testing.v1 import AppTest

from extractor import VisaDocumentExtraction
from i18n import t
from pdf_report import build_pdf_report
from report_view import _value_html,check_receipt
from scorer import calculate_score
from validator import ValidationIssue,Severity


def issue(**kwargs):
    return ValidationIssue(document_name='Visa Application Form',field_name='passport_number',
        found_value='X00001230',expected_value='X00001234',severity=Severity.CRITICAL,
        recommended_fix='Copy the passport number from the passport.',check_origin='local_key_value',**kwargs)


def test_values_are_highlighted_and_untrusted_html_is_escaped():
    wrong=_value_html('<img src=x onerror=alert(1)>','incorrect','en')
    right=_value_html('X00001234','correct','en')
    assert 'comparison-value incorrect' in wrong and '&lt;img' in wrong
    assert '<img' not in wrong
    assert 'comparison-value correct' in right and 'X00001234' in right


def test_receipt_retains_exact_failed_keys_values_and_sources_without_successes():
    data=VisaDocumentExtraction(review_provenance={'factual_engine':'local_python_ocr','external_ai_requests':0,
        'sources':[]})
    row=issue()
    row.evidence=[dict(source_file='application.pdf',page=1,text='X00001230')]
    row.reference_evidence=[dict(source_file='passport.pdf',page=1,text='X00001234')]
    receipt=check_receipt({'extraction':data,'issues':[row]})
    assert receipt['external_ai_requests']==0
    assert receipt['corrections'][0]['field']=='passport_number'
    assert receipt['corrections'][0]['found']=='X00001230'
    assert receipt['corrections'][0]['references'][0]['source_file']=='passport.pdf'
    json.dumps(receipt)


@pytest.mark.parametrize('lang',['en','ar'])
def test_pdf_exports_only_corrections_without_successful_applicant_fields(lang):
    data=VisaDocumentExtraction(passport={'full_name':'DO NOT SHOW SUCCESSFUL NAME'},
        review_provenance={'factual_engine':'local_python_ocr','external_ai_requests':0})
    rows=[issue()]
    raw=build_pdf_report(data,rows,calculate_score(rows),lang=lang,corrections_only=True)
    with pymupdf.open(stream=raw,filetype='pdf') as pdf:
        text=''.join(page.get_text() for page in pdf)
        colors=[drawing['fill'] for page in pdf for drawing in page.get_drawings() if drawing.get('fill')]
    assert 'X00001230' in text and 'X00001234' in text
    assert 'DO NOT SHOW SUCCESSFUL NAME' not in text
    assert colors and any(color[0]>.9 and color[1]<.95 for color in colors)
    assert any(color[1]>color[0] and color[2]>color[0] for color in colors)


@pytest.mark.parametrize('lang',['en','ar'])
def test_uncertain_readings_are_not_rendered_as_false_values(lang):
    data=VisaDocumentExtraction(extraction_mode='local',review_provenance={
        'factual_engine':'local_python_ocr','external_ai_requests':0})
    uncertain=issue(affects_score=False)
    result=dict(extraction=data,issues=[uncertain],score=calculate_score([uncertain]),client_name='Synthetic',writing={})
    ui=AppTest.from_string('''
import app,streamlit as st
app._init_session_state()
app.render_report(st.session_state.test_result)
''',default_timeout=30)
    ui.session_state.lang=lang;ui.session_state.test_result=result;ui.run()
    assert not ui.exception
    assert not ui.warning
    assert not any(item.label in (t('verification_details',lang),t('how_checked',lang)) for item in ui.expander)
    assert not ui.get('image') and not ui.metric
    assert not ui.caption


@pytest.mark.parametrize('lang',['en','ar'])
def test_missing_passport_is_an_upload_instruction_without_fake_red_green_fields(lang):
    row=ValidationIssue(document_name='Passport',field_name='passport_upload',found_value=None,
        expected_value='Upload the passport',severity=Severity.CRITICAL,
        recommended_fix='Upload the passport.',message_key='document.not_uploaded')
    data=VisaDocumentExtraction(extraction_mode='local')
    result=dict(extraction=data,issues=[row],score=calculate_score([row]),writing={})
    ui=AppTest.from_string('''
import streamlit as st
from report_view import render_findings
render_findings(st.session_state.test_result['issues'],st.session_state.test_result,st.session_state.lang)
''',default_timeout=30)
    ui.session_state.lang=lang;ui.session_state.test_result=result;ui.run()
    assert not ui.exception
    assert len(ui.error)==1 and ui.error[0].value==t('passport_upload_missing',lang)
    assert not any('comparison-value' in item.value for item in ui.get('html'))
    raw=build_pdf_report(data,[row],result['score'],lang=lang,corrections_only=True)
    with pymupdf.open(stream=raw,filetype='pdf') as pdf:
        assert not any(drawing.get('fill') in ((251/255,233/255,231/255),(225/255,242/255,236/255))
                       for page in pdf for drawing in page.get_drawings())


def test_reference_preview_never_marks_a_different_printed_date_as_a_calculated_expected_date(monkeypatch):
    import report_view
    from unittest.mock import Mock
    row=issue()
    row.expected_value='2027-02-01 or later'
    row.reference_evidence=[dict(source_file='appointment.pdf',page=1,value='2026-12-03',text='03/12/2026')]
    render=Mock(side_effect=AssertionError('A calculated date is not printed in this reference field.'))
    monkeypatch.setattr(report_view,'render_error_region',render)
    assert report_view._reference_screenshots(row,{'source_files':{'appointment':[('appointment.pdf',b'local bytes')]}},'en')==[]
    render.assert_not_called()
