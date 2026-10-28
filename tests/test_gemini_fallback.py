"""One quota-only fallback, with source isolation and durable model accounting."""
from unittest.mock import Mock
import httpx
import pytest

import accounts
import gemini_usage
import narrative_reviewer.client as api
from tests.test_narrative_reviewer import packet,response_payload
from tests.test_gemini_usage import setup_service


@pytest.fixture(autouse=True)
def model_settings(monkeypatch):
    monkeypatch.setattr(api,'setting',lambda key:'test-key')
    monkeypatch.setattr(api,'configured_models',lambda:('gemini-3.8-flash','gemini-3.6-flash'))


def test_quota_switches_once_and_returns_actual_model(monkeypatch,packet):
    sent=[];usage=[];starts=[]
    def handler(request):
        sent.append(request)
        if len(sent)==1:return httpx.Response(429,json={'error':{'status':'RESOURCE_EXHAUSTED'}})
        return httpx.Response(200,json=response_payload(packet))
    result=api.review_gemini(packet,usage.append,httpx.MockTransport(handler),before_model=lambda *args:starts.append(args))
    assert [request.url.path.split('/')[-1] for request in sent]==['gemini-3.8-flash:generateContent','gemini-3.6-flash:generateContent']
    assert sent[0].content==sent[1].content
    assert result['fallback_used'] and result['model']=='gemini-3.6-flash'
    assert result['models_attempted']==['gemini-3.8-flash','gemini-3.6-flash']
    assert len(usage)==1 and usage[0]['input_tokens']==1000
    assert starts==[('gemini-3.8-flash',0),('gemini-3.6-flash',1)]


@pytest.mark.parametrize('status',[400,401,402,403,404,500,503])
def test_other_failures_never_trigger_model_switch(status,packet):
    calls=[]
    def handler(request):calls.append(request);return httpx.Response(status,json={'error':{}})
    with pytest.raises(ValueError):api.review_gemini(packet,Mock(),httpx.MockTransport(handler))
    assert len(calls)==1


def test_both_models_exhausted_stops_after_two_calls(packet):
    calls=[]
    def handler(request):calls.append(request);return httpx.Response(429,json={'error':{}})
    with pytest.raises(ValueError):api.review_gemini(packet,Mock(),httpx.MockTransport(handler))
    assert len(calls)==2


def test_reported_usage_is_preserved_without_a_second_chargeable_request(packet):
    calls=[];usage=[]
    def handler(request):calls.append(request);return httpx.Response(429,json=response_payload(packet))
    with pytest.raises(ValueError):api.review_gemini(packet,usage.append,httpx.MockTransport(handler))
    assert len(calls)==1 and usage[0]['billable_output_tokens']==150


def test_same_primary_and_fallback_is_not_a_retry(monkeypatch):
    monkeypatch.setattr(gemini_usage,'setting',lambda key,default='': 'gemini-3.6-flash')
    assert gemini_usage.configured_models()==('gemini-3.6-flash',)


def test_fallback_model_is_saved_before_http_and_costs_use_its_snapshot(monkeypatch,packet):
    service,reserve,save,check=setup_service(monkeypatch)
    actor=accounts.Actor('user','test@example.com',True,'user');check.return_value=actor
    monkeypatch.setattr(service,'request_context',lambda p:{'documents':packet['documents']})
    requests=[]
    def handler(request):
        requests.append(request)
        if len(requests)==1:return httpx.Response(429,json={'error':{'status':'RESOURCE_EXHAUSTED'}})
        prior=save.call_args.args[-1]
        assert prior['model']=='gemini-3.6-flash' and prior['input_rate']==.75
        assert all(file['fallback_from']=='gemini-3.8-flash' for file in prior['files'])
        return httpx.Response(200,json=response_payload(packet))
    monkeypatch.setattr(service,'review_gemini',lambda p,sink,**kw:api.review_gemini(p,sink,httpx.MockTransport(handler),**kw))
    response=service.run_review(packet,object(),object(),'review')
    assert response['model']=='gemini-3.6-flash' and len(requests)==2
    reserve.assert_called_once()
    final=save.call_args.args[-1]
    assert final['status']=='completed' and final['usage_known']
    assert sum(file['cost_egp'] for file in final['files'])==pytest.approx(final['cost_egp'])
    assert all(file['models_attempted']==['gemini-3.8-flash','gemini-3.6-flash'] for file in final['files'])
    assert not any(key in final for key in ('prompt','response','document_text'))


def test_access_revoked_before_fallback_prevents_second_http_call(monkeypatch,packet):
    service,reserve,save,check=setup_service(monkeypatch)
    check.side_effect=accounts.AccountError('access_revoked')
    requests=[]
    def handler(request):requests.append(request);return httpx.Response(429,json={'error':{}})
    monkeypatch.setattr(service,'review_gemini',lambda p,sink,**kw:api.review_gemini(p,sink,httpx.MockTransport(handler),**kw))
    with pytest.raises(accounts.AccountError,match='access_revoked'):service.run_review(packet,object(),object(),'review')
    assert len(requests)==1 and save.call_args.args[-1]['status']=='failed'
