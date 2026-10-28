"""Small, source-bound salary, reservation and currency context for a single AI call."""
from datetime import datetime
from zoneinfo import ZoneInfo
import re


def make_financial_context(data,documents,rates=None):
    lookup={d['filename']:d for d in documents}
    def reference(name,page=1,field=None):
        doc=lookup.get(name)
        if not doc:return None
        pages=doc['pages']
        target=next((p for p in pages if p['number']==page),pages[0] if pages else None)
        if not target:return None
        lines=target['text'].splitlines()
        quote=next((line for line in lines if field and field in line),target['text'][:1400])
        return dict(document_id=doc['id'],page=target['number'],quote=quote) if len(quote)>=4 else None
    hr=getattr(data,'local_hr',{}) or {};fields=hr.get('fields',{});salary=None
    for key,basis in (('net_salary','net'),('gross_salary','gross')):
        row=fields.get(key,{})
        value=row.get('normalized_value')
        if value is None:value=(hr.get('values') or {}).get(key)
        if row.get('status') not in ('extracted','confirmed') or value is None:continue
        currency=(hr.get('values') or {}).get('salary_currency')
        currency_row=fields.get('salary_currency',{})
        if currency_row.get('status') not in ('extracted','confirmed'):currency=None
        sources=row.get('sources') or []
        ref=reference(sources[0]['source_file'],sources[0].get('page',1),key) if sources else None
        if ref:
            try:amount=float(value)
            except (ValueError,TypeError):continue
            if amount>0:salary=dict(amount=amount,currency=currency,basis=basis,source=ref)
        break
    costs=[]
    for cost in getattr(data,'trip_costs',[]):
        ref=reference(cost.source_file,cost.page)
        if ref:costs.append(dict(category=cost.category,amount=cost.amount,currency=cost.currency,paid=cost.paid,source=ref))
    visa=getattr(data,'visa_form',None);flight=getattr(data,'flight',None);passport=getattr(data,'passport',None)
    return dict(hr_present=any('employment' in d['categories'] for d in documents),salary=salary,
        applicant_name=getattr(passport,'full_name',None),
        applicant_native_name=getattr(passport,'native_name',None),
        trip_start=getattr(visa,'intended_arrival',None) or getattr(flight,'departure_date',None),
        trip_end=getattr(visa,'intended_departure',None) or getattr(flight,'return_date',None),
        expected_hotels=len(getattr(data,'hotel',[])),reservation_costs=costs,
        rates={'date':(rates or {}).get('date'),'rates':{key:value for key,value in (rates or {}).get('rates',{'EUR':1}).items()
               if key in ('EUR','EGP','USD','GBP','CHF','SEK','NOK','DKK','PLN','CZK','HUF','RON')}},
        bank_window_months=6,large_credit_share=.60,large_credit_egp=500000,
        reference_date=datetime.now(ZoneInfo('Africa/Cairo')).date().isoformat())
