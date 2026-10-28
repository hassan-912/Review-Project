"""Synthetic cropped-passport OCR and clear wrong/expected presentation."""
from copy import deepcopy
from io import BytesIO

from PIL import Image
import pytest
from streamlit.testing.v1 import AppTest

from tests.test_usa_review import files
from usa_passport_visual import visual_fields
from usa_review import review_documents,_same
from i18n import t


def rows():
    data=[
        ('Full Name',.37,.20,.46,.24,.95),('ALICE MARIA OTHER',.37,.23,.86,.31,.98),
        ('FAMILY',.37,.27,.48,.31,.99),('Passport No',.69,.13,.78,.17,.9),
        ('Z99999999',.69,.16,.83,.20,.99),('Date Of Birth',.36,.31,.49,.35,.98),
        ('20/03/1980',.36,.34,.49,.38,.99),('Nationality',.36,.37,.47,.41,.99),
        ('EGYPTIAN',.36,.40,.47,.44,.99),('Sex',.50,.38,.54,.41,.99),
        ('F',.50,.41,.52,.44,.99),('Date of Issue',.36,.44,.49,.48,.98),
        ('Date of Expiry',.50,.45,.64,.49,.98),('16/08/2020',.36,.47,.49,.51,.99),
        ('15/08/2030',.50,.48,.64,.53,.99),
    ]
    return [dict(text=text,box=[x0,y0,x1,y1],confidence=confidence,page=1,method='local_ocr')
            for text,x0,y0,x1,y1,confidence in data]


def wrong_passport(monkeypatch):
    import offline_ocr
    records=[dict(row,region_normalized=row['box']) for row in rows()]
    monkeypatch.setattr(offline_ocr,'image_lines',lambda raw:deepcopy(records))
    buffer=BytesIO();Image.new('RGB',(1600,900),'white').save(buffer,format='JPEG')
    uploaded=files();uploaded['passport']=[('cropped.jpeg',buffer.getvalue())]
    return review_documents(uploaded)


def test_visual_rows_keep_columns_dates_and_multiline_name_separate():
    fields=visual_fields(rows(),'passport.jpeg')
    assert fields['full_name']['value']=='ALICE MARIA OTHER FAMILY'
    assert len(fields['full_name']['sources'])==2
    assert fields['gender']['value']=='F'
    assert fields['passport_issue']['value']=='16/08/2020'
    assert fields['passport_expiry']['value']=='15/08/2030'
    assert fields['date_of_birth']['value']=='20/03/1980'
    assert all(field['status']=='needs_verification' for field in fields.values())


def test_invalid_sex_value_cannot_be_accepted_as_nationality():
    from usa_review import _canonical
    assert _canonical('gender','EGYPTIAN') is None
    assert _canonical('gender','F')=='female'


def test_incomplete_names_are_distinct_from_clearly_different_people():
    assert _same('full_name','JOHN MICHAEL DOE','JOHN DOE') is None
    assert _same('full_name','JOHN MICHAEL DOE','ALICE MARIA OTHER FAMILY') is False


def test_wrong_passport_is_one_warning_without_rewriting_the_application(monkeypatch):
    result=wrong_passport(monkeypatch)
    conflicts=[c for c in result['usa_checks'] if c.get('identity_conflict')]
    assert len(conflicts)==1
    check=conflicts[0]
    assert check['status']=='needs_verification'
    assert check['target_category']=='passport' and check['reference_category']=='ds160'
    assert 'ALICE MARIA OTHER FAMILY' in check['found'] and 'Z99999999' in check['found']
    assert 'JOHN MICHAEL DOE' in check['expected'] and 'A12345678' in check['expected']
    assert not any(c['field'] in ('full_name','passport_number','gender','passport_expiry') and
        c['reference_category']=='passport' for c in result['usa_checks'])
    assert result['incomplete'] and result['provenance']['external_ai_requests']==0
    assert not next(i for i in result['issues'] if i.field_name=='passport_identity').affects_score


def test_verified_wrong_passport_is_a_confirmed_file_problem():
    from tests.test_usa_review import PASSPORT
    text=PASSPORT.replace('JOHN MICHAEL','ALICE MARIA OTHER').replace('DOE','FAMILY').replace('A12345678','Z99999999')
    result=review_documents(files(passport=text))
    check=next(c for c in result['usa_checks'] if c.get('identity_conflict'))
    assert check['status']=='mismatch'
    assert next(i for i in result['issues'] if i.field_name=='passport_identity').affects_score
    assert check['target_category']=='passport'


@pytest.mark.parametrize('lang',['en','ar'])
def test_wrong_is_in_left_column_and_expected_in_right_column(monkeypatch,lang):
    result=wrong_passport(monkeypatch)
    ui=AppTest.from_string('''
import streamlit as st
from usa_ui import render_usa_report
render_usa_report(st.session_state.result,st.session_state.lang)
''',default_timeout=30)
    ui.session_state.lang=lang;ui.session_state.result=result;ui.run()
    assert not ui.exception
    columns=ui.get('column')
    assert columns[0].get('image') and columns[1].get('image')
    assert not columns[0].get('html') and not columns[1].get('html')
    assert any('cropped.jpeg' in c.value and t('usa_checked_document',lang) in c.value for c in columns[0].caption)
    assert any('ds160.pdf' in c.value and t('usa_comparison_document',lang) in c.value for c in columns[1].caption)
    assert any(h.value==t('usa_wrong_passport_possible',lang) for h in ui.subheader)
    assert not any(c.value==t('usa_field_unavailable',lang) for c in ui.caption)
