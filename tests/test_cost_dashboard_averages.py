"""Per-request measurements, labelled per-document estimates and an empty-ledger calculator."""
from datetime import datetime,timezone
from unittest.mock import Mock
import pytest
from streamlit.testing.v1 import AppTest
import accounts
import cost_dashboard as dashboard
from gemini_usage import allocate_files
from i18n import t


def sample_rows():
    rows=[]
    for index,multiplier in enumerate((1,2)):
        usage=dict(input_tokens=1000*multiplier,output_tokens=100*multiplier,thinking_tokens=50*multiplier,
                   billable_output_tokens=150*multiplier,cached_input_tokens=0,usage_known=True)
        cost=dict(cost_usd=.002*multiplier,cost_egp=.1*multiplier)
        documents=[dict(filename='letter.pdf',categories=['cover_letter'],context_mode='full_text',weight=1),
                   dict(filename='hotel.pdf',categories=['hotel'],context_mode='extracted_fields',weight=3)] if index==0 else [
                   dict(filename='bank.pdf',categories=['bank_statement'],context_mode='pdf_visual',weight=1)]
        rows.append(dict(id=str(index),review_id=str(index),user_id='user',username='Synthetic user',
            created_at=datetime.now(timezone.utc).isoformat(),model='gemini-3.8-flash',status='completed',
            **usage,**cost,usd_egp=50,fx_date='2026-10-28',files=allocate_files(documents,usage,cost)))
    return rows


def test_averages_use_document_denominators_and_billable_output():
    rows=sample_rows();files=dashboard.file_rows(rows)
    assert len(files)==3
    assert dashboard.average(rows,'cost_egp')==pytest.approx(.15)
    assert dashboard.average(files,'input_tokens')==1000
    assert dashboard.average(files,'billable_output_tokens')==150
    assert dashboard.average(files,'cost_egp')==pytest.approx(.1)
    groups={group['categories']:group for group in dashboard.category_averages(files)}
    assert groups[('hotel',)]['avg_input_tokens']==750
    assert groups[('hotel',)]['avg_output_tokens']==112.5
    assert groups[('hotel',)]['avg_cost_egp']==pytest.approx(.075)


def test_unknown_values_are_not_zero_samples_and_old_allocations_still_work():
    rows=sample_rows()
    for file in rows[0]['files']:file.pop('billable_output_tokens')
    rows[0]['files'].append(dict(filename='unknown.pdf',categories=['hotel'],context_mode='pdf_visual'))
    files=dashboard.file_rows(rows)
    assert dashboard.average(files,'cost_egp')==pytest.approx(.1)
    assert dashboard.average(files,'billable_output_tokens')==150
    assert dashboard.average([], 'cost_egp') is None
    assert next(g for g in dashboard.category_averages(files) if g['categories']==('hotel',))['unknown']==1


@pytest.mark.parametrize('lang',['en','ar'])
def test_empty_ledger_still_has_working_cost_calculator_without_gemini(monkeypatch,lang):
    monkeypatch.setattr(dashboard,'dashboard_exchange',lambda *a:dict(usd_egp=50,fx_date='2026-10-28',fx_source='test'))
    read=Mock(return_value=[]);monkeypatch.setattr(accounts,'gemini_usage_rows',read)
    ui=AppTest.from_string('from cost_dashboard import render_cost_dashboard\nimport streamlit as st\nrender_cost_dashboard(object(),object(),st.session_state.lang)')
    ui.session_state.lang=lang;ui.run()
    assert not ui.exception
    assert next(m for m in ui.metric if m.label==t('cost_estimated_egp',lang)).value=='0.0938'
    assert any(m.value=='—' for m in ui.metric)
    ui.number_input(key='cost_estimate_input').set_value(2000).run()
    assert not ui.exception
    assert next(m for m in ui.metric if m.label==t('cost_estimated_egp',lang)).value=='0.1313'
    ui.selectbox(key='cost_estimate_model').set_value('gemini-3.6-flash').run()
    assert not ui.exception
    assert next(m for m in ui.metric if m.label==t('cost_estimated_egp',lang)).value=='0.1313'


def test_missing_fx_does_not_invent_egp_price():
    ui=AppTest.from_string("from cost_dashboard import render_estimator\nrender_estimator('en',{'usd_egp':None})")
    ui.run()
    assert not ui.exception
    assert ui.metric[0].value=='0.001875' and ui.metric[1].value=='—'
    assert ui.warning


def test_calculator_values_and_total_survive_page_navigation():
    ui=AppTest.from_string('''
import streamlit as st
from cost_dashboard import render_estimator
page=st.selectbox('Page',['cost','other'],key='page')
if page=='cost':render_estimator('en',{'usd_egp':50,'fx_date':'2026-10-28'})
else:st.text('Other page')
''')
    ui.run()
    ui.number_input(key='cost_estimate_input').set_value(1000000)
    ui.number_input(key='cost_estimate_output').set_value(1750000)
    ui.run()
    assert ui.metric[0].value=='7.312500'
    ui.selectbox(key='page').set_value('other').run()
    ui.selectbox(key='page').set_value('cost').run()
    assert not ui.exception
    assert ui.number_input(key='cost_estimate_input').value==1000000
    assert ui.number_input(key='cost_estimate_output').value==1750000
    assert ui.metric[0].value=='7.312500' and ui.metric[1].value=='365.6250'
