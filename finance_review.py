"""Final-page balances and an explicit, non-scoring trip budget comparison."""
from datetime import datetime, timezone
from functools import lru_cache
import math
import re
import time
import requests
from pydantic import BaseModel, Field
from typing import Literal
from document_sources import source_manifest, source_is_grounded


class BankStatement(BaseModel):
    source_file: str
    page: int = Field(ge=1, description='Original final page number, not page 1 of the supplied excerpt')
    holder_name: str | None = None
    owner_role: Literal['applicant','other','unknown'] = 'unknown'
    balance: float | None = Field(None, allow_inf_nan=False)
    currency: str | None = Field(None, description='Printed ISO currency code; never infer from nationality')
    balance_type: Literal['available','closing','unknown'] = 'unknown'
    statement_date: str | None = None
    quote: str = Field('', description='Exact final-page balance label, amount and currency; no transaction analysis')


class TripCost(BaseModel):
    category: Literal['flight','hotel','other']
    source_file: str
    page: int = Field(ge=1)
    amount: float = Field(ge=0, allow_inf_nan=False)
    currency: str
    paid: bool = Field(False, description='True only if source explicitly confirms payment, not just confirmed/held')
    quote: str


class BookingStatus(BaseModel):
    category: Literal['flight','hotel']
    source_file: str
    page: int = Field(ge=1)
    status: Literal['held','confirmed','cancelled','unknown']
    quote: str


def amount_in_quote(amount, quote):
    # Tolerate printed thousands/decimal separators, without accepting another amount.
    quote=quote.translate(str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹','01234567890123456789')).replace('٬',',').replace('٫','.').replace('،',',')
    candidates=re.findall(r'-?\d[\d ,.\u00a0]*\d|-?\d',quote)
    for candidate in candidates:
        raw=candidate.replace(' ','').replace('\u00a0','').rstrip('.,')
        if ',' in raw and '.' in raw:
            raw=raw.replace(',','') if raw.rfind('.')>raw.rfind(',') else raw.replace('.','').replace(',','.')
        elif ',' in raw:
            raw=raw.replace(',','.') if len(raw.rsplit(',',1)[1])==2 else raw.replace(',','')
        try:
            if math.isclose(float(raw),amount,abs_tol=.005):return True
        except ValueError:pass
    return False


def grounded_financial_data(data,uploaded):
    manifest=source_manifest(uploaded)
    bank_names={name for name,entry in manifest.items() if entry['category_hint']=='bank_statement'}
    data.identity_evidence=[row for row in data.identity_evidence if row.source_file not in bank_names]
    data.supporting_documents=[row for row in data.supporting_documents if row.source_file not in bank_names]
    data.contextual_findings=[row for row in data.contextual_findings if row.get('field_name')!='reservation_validity'
        and not any(source.get('source_file') in bank_names for source in row.get('sources',[]))]
    data.unverified_findings=[row for row in data.unverified_findings if row.get('field_name')!='reservation_validity'
        and not any(source.get('source_file') in bank_names for source in row.get('sources',[]))]
    verified=[]
    seen_banks=set()
    for bank in data.bank_statements:
        entry=manifest.get(bank.source_file,{})
        if (entry.get('category_hint')=='bank_statement' and bank.page==entry['pages'] and
                source_is_grounded({'source_file':bank.source_file,'page':bank.page,'text':bank.quote},uploaded)
                and bank.balance is not None and amount_in_quote(bank.balance,bank.quote)
                and bank.source_file not in seen_banks):
            seen_banks.add(bank.source_file)
            from validator import _names_match
            if bank.owner_role=='applicant' and (not bank.holder_name or not _names_match(
                    data.passport.full_name,bank.holder_name,data.passport.given_names,data.passport.surname)):
                bank.owner_role='unknown'
            verified.append(bank)
    data.bank_statements=verified
    data.trip_costs=[cost for cost in data.trip_costs if
        manifest.get(cost.source_file,{}).get('category_hint')!='bank_statement' and
        source_is_grounded({'source_file':cost.source_file,'page':cost.page,'text':cost.quote},uploaded)
        and amount_in_quote(cost.amount,cost.quote)]
    unique={}
    from document_sources import normalized_quote
    for cost in data.trip_costs:
        key=(cost.category,cost.amount,cost.currency,normalized_quote(cost.quote))
        unique.setdefault(key,cost)
    data.trip_costs=list(unique.values())
    data.booking_statuses=[row for row in data.booking_statuses if
        source_is_grounded({'source_file':row.source_file,'page':row.page,'text':row.quote},uploaded)]


@lru_cache(maxsize=2)
def _daily_rates(day):
    # This request contains no client data. Cache only public exchange rates.
    response=requests.get('https://open.er-api.com/v6/latest/EUR',timeout=6)
    response.raise_for_status()
    payload=response.json()
    stamp=payload.get('time_last_update_unix',0)
    if payload.get('result')!='success' or payload.get('base_code')!='EUR' or not 0<=time.time()-stamp<=3*86400:
        raise ValueError('Rates unavailable or stale')
    rates=payload['rates']
    if not all(isinstance(v,(int,float)) and math.isfinite(v) and v>0 for v in rates.values()):
        raise ValueError('Invalid rates')
    return {'rates':rates,'date':datetime.fromtimestamp(stamp,timezone.utc).date().isoformat()}


def exchange_rates():
    try:return _daily_rates(datetime.now(timezone.utc).date().isoformat())
    except (requests.RequestException,ValueError,KeyError,TypeError):return None


def assess_budget(data,daily_eur=75.0,rates=None):
    from validator import _parse_date
    start=_parse_date(data.visa_form.intended_arrival or data.flight.departure_date)
    end=_parse_date(data.visa_form.intended_departure or data.flight.return_date)
    days=(end-start).days+1 if start and end and end>=start else None
    rates=rates or {'rates':{'EUR':1.0},'date':None}
    def eur(amount,currency):
        rate=rates['rates'].get((currency or '').upper())
        return round(amount/rate,2) if rate and amount is not None else None
    missing=[];costs=[]
    for cost in data.trip_costs:
        value=eur(cost.amount,cost.currency)
        if value is None:missing.append('currency_conversion')
        costs.append({**cost.model_dump(),'eur':value})
    for category in ('flight','hotel'):
        # Every hotel needs its own price. No invented fare or free accommodation.
        needed=max(1,len(data.hotel)) if category=='hotel' else 1
        sources={(c.source_file,c.page) for c in data.trip_costs if c.category==category}
        if len(sources)<needed:missing.append(category+'_price')
    if not days:missing.append('travel_dates')
    allowance=round(days*daily_eur,2) if days else None
    known=round(sum(c['eur'] for c in costs if c['eur'] is not None and not c['paid'])+(allowance or 0),2)
    balances=[]
    for bank in data.bank_statements:
        value=eur(bank.balance,bank.currency)
        usable=bank.owner_role=='applicant' and bank.balance_type in ('available','closing')
        status=('ownership_unknown' if not usable else 'conversion_unknown' if value is None else
                'below_budget' if value<known else 'partial_budget' if missing else 'covers_budget')
        balances.append({**bank.model_dump(),'eur':value,'status':status,
                         'remaining_eur':round(value-known,2) if usable and value is not None else None})
    return {'days':days,'daily_eur':daily_eur,'allowance_eur':allowance,'known_budget_eur':known,
            'missing':sorted(set(missing)),'balances':balances,'costs':costs,'rate_date':rates.get('date')}


def extract_booking_costs(data,uploaded):
    """Accept one unambiguous, labelled total per reservation, with explicit currency."""
    import pymupdf
    from hr_extractor import normalize_money
    label=r'(?:grand\s+total|total\s+(?:price|amount|fare|cost)|total|المبلغ\s+الإجمالي|السعر\s+الإجمالي|الإجمالي)'
    currency=r'(EUR|EGP|USD|GBP|CHF|SEK|NOK|DKK|PLN|CZK|HUF|RON|€|جنيه\s+مصري)'
    amount=r'([0-9٠-٩۰-۹][0-9٠-٩۰-۹.,،٬٫ ]*)'
    pattern=re.compile(label+r'\s*[:=：-]?\s*(?:'+currency+r'\s*'+amount+r'|'+amount+r'\s*'+currency+r')',re.I)
    existing={(c.category,c.source_file) for c in data.trip_costs}
    for category in ('hotel','flight'):
        for name,raw in uploaded.get(category,[]):
            if (category,name) in existing or not name.lower().endswith('.pdf'):continue
            try:
                with pymupdf.open(stream=raw,filetype='pdf') as pdf:
                    candidates=[]
                    for number,page in enumerate(pdf,1):
                        text=page.get_text(sort=True)
                        for match in pattern.finditer(text):
                            first_currency,first_amount,last_amount,last_currency=match.groups()
                            value=normalize_money(first_amount or last_amount)
                            unit=(first_currency or last_currency).upper()
                            unit='EUR' if unit=='€' else 'EGP' if 'جنيه' in unit else unit
                            if value is not None:candidates.append((float(value),unit,number,match.group()))
                    if len({(v,c) for v,c,_,_ in candidates})!=1:continue
                    value,unit,page,quote=candidates[0]
                    # Payment is a separate explicit assertion, never inferred from a reservation.
                    data.trip_costs.append(TripCost(category=category,source_file=name,page=page,
                        amount=value,currency=unit,paid=False,quote=quote))
            except Exception:continue
