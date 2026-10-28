"""Authorize one AI review, with a durably recorded quota fallback when needed."""
import time
import uuid

import accounts
from settings import setting
from gemini_usage import configured_model,pricing_snapshot,exchange_snapshot,file_weights,cost_snapshot,allocate_files
from .client import review_gemini
from .prompt import request_context


def run_review(packet,client,session,attempt_id):
    if not setting('GEMINI_API_KEY'):
        raise ValueError('gemini_config_missing')
    model=configured_model()
    files=file_weights(request_context(packet),packet.get('attachments',[]))
    rates={**pricing_snapshot(model=model),**exchange_snapshot()}
    event_id=str(uuid.uuid4())
    actor=accounts.reserve_gemini_usage(client,session,attempt_id,
        dict(id=event_id,model=model,files=files,**rates))
    start=time.monotonic();saved_usage={};cost=dict(cost_usd=None,cost_egp=None);complete=False
    attempted=[]
    def before_model(actual,index):
        nonlocal rates,files
        attempted.append(actual)
        if index==0:return
        # A quota rejection is not another user review. Recheck live access and
        # save the actual model/rates before allowing the fallback HTTP request.
        current=accounts.verified_actor(client,session)
        if current.user_id!=actor.user_id:raise accounts.AccountError('access_revoked')
        accounts.ensure_service_available()
        rates={**rates,**pricing_snapshot(model=actual)}
        files=[{**file,'model':actual,'models_attempted':list(attempted),
                'fallback_from':model,'fallback_reason':'quota_exhausted'} for file in files]
        accounts.finish_gemini_usage(event_id,actor.user_id,dict(model=actual,**rates,files=files))
    def record(usage):
        nonlocal saved_usage,cost
        saved_usage=usage;cost=cost_snapshot(usage,rates)
        accounts.finish_gemini_usage(event_id,actor.user_id,{**usage,**cost,
            'files':allocate_files(files,usage,cost)})
    try:
        response=review_gemini(packet,record,before_model=before_model)
        accounts.verified_actor(client,session)
        accounts.ensure_service_available()
        complete=True
        return response
    finally:
        accounts.finish_gemini_usage(event_id,actor.user_id,dict(status='completed' if complete else 'failed',
            latency_ms=round((time.monotonic()-start)*1000),**saved_usage,**cost,
            files=allocate_files(files,saved_usage,cost)))
