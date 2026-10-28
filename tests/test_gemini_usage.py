from datetime import datetime,timezone
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from streamlit.testing.v1 import AppTest
import accounts
import gemini_usage as usage


def test_cost_includes_thinking_and_discounts_cached_input():
    tokens=usage.provider_usage(dict(promptTokenCount=1000,candidatesTokenCount=100,
                                    thoughtsTokenCount=50,cachedContentTokenCount=200))
    rates={**usage.pricing_snapshot(datetime(2026,10,27,tzinfo=timezone.utc)),'usd_egp':50}
    cost=usage.cost_snapshot(tokens,rates)
    assert cost['cost_usd']==pytest.approx(.0011775)
    assert cost['cost_egp']==pytest.approx(.058875)
    files=usage.allocate_files([dict(filename='letter',weight=1),dict(filename='hotel',weight=3)],tokens,cost)
    for field in ('input_tokens','output_tokens','thinking_tokens'):
        assert sum(item[field] for item in files)==tokens[field]
    assert sum(item['cost_egp'] for item in files)==pytest.approx(cost['cost_egp'])
    assert all('estimated' in item['allocation'] for item in files)


@pytest.mark.parametrize('metadata',[{},dict(promptTokenCount=100),dict(promptTokenCount=100,candidatesTokenCount=5,cachedContentTokenCount=101)])
def test_unknown_usage_never_becomes_zero_cost(metadata):
    value=usage.provider_usage(metadata)
    assert not value['usage_known']
    assert usage.cost_snapshot(value,dict())==dict(cost_usd=None,cost_egp=None)


def test_saved_prices_are_time_bound_and_no_egp_rate_is_invented(monkeypatch):
    assert usage.pricing_snapshot(datetime(2026,12,31,tzinfo=timezone.utc))['input_rate']==.75
    assert usage.pricing_snapshot(datetime(2027,1,1,tzinfo=timezone.utc))['input_rate']==1.5
    monkeypatch.setattr(usage,'setting',lambda key:None)
    import finance_review
    monkeypatch.setattr(finance_review,'exchange_rates',lambda:None)
    assert usage.exchange_snapshot()['usd_egp'] is None
    monkeypatch.setattr(finance_review,'exchange_rates',lambda:dict(rates={'USD':2,'EGP':100},date='2026-10-27'))
    assert usage.exchange_snapshot()['usd_egp']==50


def setup_service(monkeypatch):
    import narrative_reviewer.service as service
    monkeypatch.setattr(service,'setting',lambda key:'test')
    monkeypatch.setattr(service,'request_context',lambda packet:dict(documents=[]))
    monkeypatch.setattr(service,'exchange_snapshot',lambda:dict(usd_egp=50,fx_date='2026-10-27',fx_source='test'))
    reserve=Mock(return_value=accounts.Actor('user','test@example.com',True,'user'))
    save=Mock();check=Mock()
    monkeypatch.setattr(accounts,'reserve_gemini_usage',reserve)
    monkeypatch.setattr(accounts,'finish_gemini_usage',save)
    monkeypatch.setattr(accounts,'verified_actor',check)
    monkeypatch.setattr(accounts,'ensure_service_available',Mock())
    return service,reserve,save,check


def test_durable_reservation_precedes_generation_and_failed_output_still_has_cost(monkeypatch):
    service,reserve,save,check=setup_service(monkeypatch)
    def generate(packet,sink,**kwargs):
        reserve.assert_called_once()
        sink(usage.provider_usage(dict(promptTokenCount=1000,candidatesTokenCount=200,thoughtsTokenCount=50)))
        raise ValueError('Malformed generated output')
    monkeypatch.setattr(service,'review_gemini',generate)
    with pytest.raises(ValueError):service.run_review({},object(),object(),'review-id')
    values=save.call_args.args[-1]
    assert values['status']=='failed' and values['cost_egp']>0
    assert values['usage_known'] and values['billable_output_tokens']==250
    assert not any(key in values for key in ('prompt','response','document_text'))


def test_reservation_failure_cannot_make_a_chargeable_request(monkeypatch):
    service,reserve,save,check=setup_service(monkeypatch)
    reserve.side_effect=accounts.AccountError('quota_unavailable');generate=Mock()
    monkeypatch.setattr(service,'review_gemini',generate)
    with pytest.raises(accounts.AccountError):service.run_review({},object(),object(),'review')
    generate.assert_not_called()


def test_revocation_after_generation_preserves_bill_and_blocks_private_results(monkeypatch):
    service,reserve,save,check=setup_service(monkeypatch)
    check.side_effect=accounts.AccountError('access_revoked')
    def generate(packet,sink,**kwargs):
        sink(usage.provider_usage(dict(promptTokenCount=1000,candidatesTokenCount=200)))
        return {'findings':['PRIVATE RESULT']}
    monkeypatch.setattr(service,'review_gemini',generate)
    with pytest.raises(accounts.AccountError):service.run_review({},object(),object(),'review')
    assert save.call_args.args[-1]['cost_usd']>0


def test_usage_reader_checks_admin_access_before_database(monkeypatch):
    monkeypatch.setattr(accounts,'verified_actor',Mock(side_effect=accounts.AccountError('access_revoked')))
    db=Mock();monkeypatch.setattr(accounts,'admin_client',db)
    with pytest.raises(accounts.AccountError):accounts.gemini_usage_rows(object(),object(),'start','end')
    db.assert_not_called()


@pytest.mark.parametrize('lang',['en','ar'])
def test_admin_cost_dashboard_displays_actual_and_allocated_usage(monkeypatch,lang):
    import cost_dashboard
    monkeypatch.setattr(cost_dashboard,'dashboard_exchange',lambda *args:dict(usd_egp=50,fx_date='2026-10-27',fx_source='test'))
    now=datetime.now(timezone.utc).isoformat()
    rows=[dict(id='event',review_id='review',user_id='user',username='Reviewer',created_at=now,
        model='gemini-3.8-flash',status='completed',usage_known=True,input_tokens=1000,output_tokens=100,
        thinking_tokens=50,billable_output_tokens=150,cached_input_tokens=0,cost_usd=.0013125,
        cost_egp=.065625,usd_egp=50,fx_date='2026-10-27',files=[dict(filename='hotel.pdf',
        context_mode='extracted_fields',input_tokens=250,output_tokens=25,thinking_tokens=12.5,cost_egp=.01640625)])]
    read=Mock(return_value=rows);monkeypatch.setattr(accounts,'gemini_usage_rows',read)
    ui=AppTest.from_string("""
import streamlit as st
from cost_dashboard import render_cost_dashboard
render_cost_dashboard(object(),object(),st.session_state.lang)
""")
    ui.session_state.lang=lang;ui.run()
    assert not ui.exception
    assert len(ui.metric)==12 and len(ui.dataframe)==4
    assert any('0.0656'==item.value for item in ui.metric)
    assert read.call_count==1
