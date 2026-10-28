"""Provider usage, immutable pricing snapshots and labelled file allocations."""
from datetime import datetime, timezone
from decimal import Decimal
import json
import math
from settings import setting


MODELS=('gemini-3.8-flash','gemini-3.6-flash')


def configured_model():
    model=setting('GEMINI_MODEL','gemini-3.8-flash')
    if model not in MODELS:
        raise ValueError('Configure verified pricing before changing the Gemini model')
    return model


def configured_models():
    primary=configured_model()
    fallback=setting('GEMINI_FALLBACK_MODEL','gemini-3.6-flash')
    if fallback not in MODELS:raise ValueError('Configure verified pricing before changing the Gemini fallback model')
    return tuple(dict.fromkeys((primary,fallback)))


def pricing_snapshot(now=None,model=None):
    now=now or datetime.now(timezone.utc)
    if model is not None and model not in MODELS:raise ValueError('Unverified Gemini model price')
    # Both Flash models use these standard paid rates, checked 2026-10-28.
    # Never reprice saved events when changing the active/fallback model.
    later=now>=datetime(2027,1,1,tzinfo=timezone.utc)
    return dict(input_rate=1.5 if later else .75,cached_rate=.15 if later else .075,
                output_rate=7.5 if later else 3.75,
                price_source='https://ai.google.dev/gemini-api/docs/pricing')


def exchange_snapshot():
    override=setting('USD_EGP_RATE')
    if override:
        value=float(override)
        if not math.isfinite(value) or value<=0:raise ValueError('Invalid USD_EGP_RATE')
        return dict(usd_egp=value,fx_date=datetime.now(timezone.utc).date().isoformat(),fx_source='server setting')
    from finance_review import exchange_rates
    snapshot=exchange_rates()
    if snapshot and snapshot['rates'].get('USD') and snapshot['rates'].get('EGP'):
        return dict(usd_egp=snapshot['rates']['EGP']/snapshot['rates']['USD'],
                    fx_date=snapshot['date'],fx_source='open.er-api.com cross rate')
    return dict(usd_egp=None,fx_date=None,fx_source='unavailable')


def file_weights(context,attachments=()):
    sizes={item['document_id']:len(item['data'])*3//4 for item in attachments}
    return [dict(document_id=d['id'],filename=d['filename'],categories=d['categories'],
                 context_mode=d['context_mode'],
                 weight=len(json.dumps(d,ensure_ascii=False,separators=(',',':')).encode('utf-8'))+sizes.get(d['id'],0))
            for d in context['documents']]


def provider_usage(metadata):
    def count(key,default=None):
        value=metadata.get(key,default)
        return value if type(value) is int and value>=0 else None
    prompt=count('promptTokenCount');visible=count('candidatesTokenCount')
    thoughts=count('thoughtsTokenCount',0);cached=count('cachedContentTokenCount',0)
    known=prompt is not None and visible is not None and thoughts is not None and cached is not None and cached<=prompt
    return dict(input_tokens=prompt,output_tokens=visible,thinking_tokens=thoughts,cached_input_tokens=cached,
                billable_output_tokens=visible+thoughts if visible is not None and thoughts is not None else None,
                usage_known=known)


def cost_snapshot(usage,rates):
    if not usage.get('usage_known'):return dict(cost_usd=None,cost_egp=None)
    d=lambda value:Decimal(str(value))
    usd=((usage['input_tokens']-usage['cached_input_tokens'])*d(rates['input_rate'])+
         usage['cached_input_tokens']*d(rates['cached_rate'])+
         usage['billable_output_tokens']*d(rates['output_rate']))/d(1000000)
    return dict(cost_usd=float(usd),cost_egp=float(usd*d(rates['usd_egp'])) if rates.get('usd_egp') else None)


def allocate_files(files,usage,cost):
    """Shared prompt and output cannot be measured per file. Allocate by context bytes."""
    total=sum(f['weight'] for f in files) or 1
    return [{**{k:v for k,v in f.items() if k!='weight'},'allocation':'estimated by context byte share',
             **{key:(usage.get(key)*f['weight']/total if usage.get(key) is not None else None)
                for key in ('input_tokens','output_tokens','thinking_tokens','billable_output_tokens','cached_input_tokens')},
             **{key:(cost[key]*f['weight']/total if cost.get(key) is not None else None)
                for key in ('cost_usd','cost_egp')}} for f in files]
