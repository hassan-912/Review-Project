"""Checkmark placement and complete multi-finding report regressions."""
import pytest
from streamlit.testing.v1 import AppTest

from i18n import t
from tests.test_usa_hotel_contact import packet
from usa_templates import _choice,client_text_fields
from usa_review import review_documents


@pytest.mark.parametrize('text,options,expected',[
    ('Male / ذكر ✔     Female / أنثى',('male','female'),'male'),
    ('Single / أعزب✔      Married / متزوج      Divorced / مطلق      Widowed / أرمل',('single','married','divorced','widowed'),'single'),
    ('Male / ذكر     Female / أنثى✔',('male','female'),'female'),
    ('Single / أعزب     Married / متزوج✔     Divorced / مطلق     Widowed / أرمل',('single','married','divorced','widowed'),'married'),
    ('✔ Male / ذكر     Female / أنثى',('male','female'),'male'),
    ('☐ Male / ذكر ☑ Female / أنثى',('male','female'),'female'),
    ('☑ Male / ذكر ☐ Female / أنثى',('male','female'),'male'),
    ('Yes / نعم✔      No / لا',('yes','no'),'yes'),
    ('Yes / نعم      No / لا✔',('yes','no'),'no'),
    ('Male✔ Female',('male','female'),'male'),
    ('Male ✔Female',('male','female'),'female'),
    ('Male / ذكر\u200f✔\u200e     Female / أنثى',('male','female'),'male'),
])
def test_checks_attach_to_the_label_they_mark(text,options,expected):
    assert _choice(text,options)==(expected,'extracted')


@pytest.mark.parametrize('text,options',[
    ('Male / ذكر Female / أنثى',('male','female')),
    ('☐ Male / ذكر ☐ Female / أنثى',('male','female')),
    ('☐ Male',('male','female')),
    ('Male / ذكر ✔ Female / أنثى',('male','female')),
    ('✔ Male / ذكر ✔ Female / أنثى',('male','female')),
])
def test_unmarked_conflicting_and_ambiguous_checks_do_not_establish_an_answer(text,options):
    assert _choice(text,options)[1]=='needs_verification'


def test_native_bilingual_table_preserves_trailing_ticks_and_their_source_quotes():
    text='''U.S. Visa Client Information Form
Gender / النوع | Male / ذكر ✔     Female / أنثى
Marital status / الحالة الاجتماعية | Single / أعزب✔      Married / متزوج      Divorced / مطلق      Widowed / أرمل
'''
    fields=client_text_fields(text,'client.docx.pdf')
    assert fields['gender']['value']=='male' and fields['marital_status']['value']=='single'
    assert 'ذكر ✔' in fields['gender']['sources'][0]['text']
    assert 'أعزب✔' in fields['marital_status']['sources'][0]['text']
    assert all(fields[k]['status']=='extracted' for k in ('gender','marital_status'))


def test_native_word_evidence_shows_the_original_marked_text_in_the_comparison_column():
    from document_ingestion import normalize_uploads
    from validator import ValidationIssue,Severity
    quote='Gender / النوع | Male / ذكر     Female / أنثى✔'
    source_files,converted=normalize_uploads({'client_form':[('client.txt',('Header\n\n\n\n'+quote).encode())]})
    section=next(iter(converted.values()))['text'].splitlines().index(quote)+1
    location=dict(document='client_form',source_file='client.txt.pdf',page=None,native_section=section,
                  field_name='gender',value='female',text=quote,method='native_text')
    issue=ValidationIssue(document_name='DS-160',field_name='gender',found_value='MALE',expected_value='female',
        severity=Severity.HIGH,recommended_fix='Compare the supplied forms.',reference_evidence=[location])
    ui=AppTest.from_string('''
import streamlit as st
from usa_ui import _comparison_evidence
_comparison_evidence(st.session_state.issue,st.session_state.result,'en')
''')
    ui.session_state.issue=issue
    ui.session_state.result={'usa_documents':[],'source_files':source_files,'converted_sources':converted}
    ui.run()
    assert not ui.exception
    assert ui.get('column')[1].get('image')
    assert not ui.get('column')[1].text
    assert any(c.value==t('usa_converted_text_evidence','en') for c in ui.get('column')[1].caption)
    assert not ui.session_state.result.get('reference_images_v1')


@pytest.mark.parametrize('lang',['en','ar'])
def test_multiple_problems_and_hotel_contact_all_render_without_duplicate_controls(lang):
    result=review_documents(packet())
    assert len([i for i in result['issues'] if i.affects_score])>1
    assert any(i.field_name=='us_contact_hotel' and i.affects_score for i in result['issues'])
    ui=AppTest.from_string('''
import streamlit as st
from usa_ui import render_usa_report
render_usa_report(st.session_state.result,st.session_state.lang)
''',default_timeout=30)
    ui.session_state.result=result;ui.session_state.lang=lang;ui.run()
    assert not ui.exception
    assert any(h.value==t('field_us_contact_hotel',lang) for h in ui.subheader)
    panels=[panel for panel in ui.expander if panel.label==t('usa_source_details',lang)]
    assert not panels
    assert ui.get('image')
    assert not ui.get('html')
    # Screenshots remain visible on reruns without opening any evidence panel.
    ui.run()
    assert not ui.exception
    assert any(h.value==t('field_us_contact_hotel',lang) for h in ui.subheader)
