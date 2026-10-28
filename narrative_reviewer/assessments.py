"""Check source provenance and calculate bank flags / planning costs locally."""
from calendar import monthrange
from datetime import date,timedelta
import re
from finance_review import amount_in_quote

CURRENCY_PATTERNS={'EGP':r'\bEGP\b|جنيه\s+مصري|ج\.\s*م','EUR':r'\bEUR\b|€|يورو',
    'USD':r'\bUSD\b|US\s+dollars?|دولار\s+[أا]مريكي','GBP':r'\bGBP\b|pounds?\s+sterling|جنيه\s+[إا]سترليني'}


def _currency_present(currency,text):
    return bool(re.search(CURRENCY_PATTERNS.get(currency,r'\b'+re.escape(currency)+r'\b'),text,re.I))


def _date(value):
    try:return date.fromisoformat(value)
    except (TypeError,ValueError):return None


def _month_start(end,back=0):
    index=end.year*12+end.month-1-back
    return date(index//12,index%12+1,1)


def _has_date(value,text):
    from hr_extractor import normalize_date
    text=text.translate(str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹','01234567890123456789'))
    tokens=re.findall(r'\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[/.\-]\d{1,2}[/.\-]\d{4}',text)
    return any(normalize_date(token.replace('.','/'))==value for token in tokens)


def _local_salary_match(doc,month,amount,currency):
    from hr_extractor import normalize_money,normalize_date
    for page in doc['pages']:
        if page['provisional'] or page['method']=='pdf_visual':continue
        for line in page['text'].splitlines():
            match=re.search(r'(?:credit|إيداع|ايداع|دائن)\s*(?:'+re.escape(currency)+r')?\s*([0-9٠-٩۰-۹][0-9٠-٩۰-۹,.٬٫]*)',line,re.I)
            value=normalize_money(match.group(1)) if match else None
            if value is None or abs(float(value)-amount)>.01:continue
            for token in re.findall(r'\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[/.\-]\d{1,2}[/.\-]\d{4}',line):
                stamp=normalize_date(token.replace('.','/'))
                if stamp and stamp.startswith(month):
                    return stamp,dict(document_id=doc['id'],page=page['number'],quote=line,visual=False)
    return None


def assess(packet,bank_values,proposal,valid,covered,salary_reference=None,reported_coverage=None):
    docs={d['id']:d for d in packet['documents']};context=packet.get('financial_context',{})
    salary=context.get('salary');banks=[];flags=[];notes=[];seen=set()
    if (not salary or not salary.get('currency')) and salary_reference is not None:
        candidate=salary_reference.model_dump();source=candidate['source'];doc=docs.get(source['document_id'])
        if (doc and set(doc['categories'])&{'employment','supporting'} and valid(source) and
                not source.get('visual') and (source['document_id'],source['page']) in covered and
                re.search(r'salary|payroll|راتب|مرتب',source['quote'],re.I) and
                amount_in_quote(candidate['amount'],source['quote']) and _currency_present(candidate['currency'],
                ' '.join(p['text'] for p in doc['pages']))):
            salary=candidate
    expected_banks={d['id'] for d in packet['documents'] if 'bank_statement' in d['categories']}
    for raw in bank_values:
        bank=raw.model_dump();doc=docs.get(bank['document_id'])
        if not doc or doc['id'] not in expected_banks or doc['id'] in seen:
            notes.append('A bank assessment had an unknown or duplicate statement identity.');continue
        seen.add(doc['id'])
        start,end=_date(bank['period_start']),_date(bank['period_end'])
        source=bank['period_source']
        if not start or not end or start>end or source['document_id']!=doc['id'] or not valid(source):
            notes.append(doc['filename']+': statement period evidence could not be verified.');continue
        expected={(doc['id'],p['number']) for p in doc['pages']}
        readable=(expected<=covered and not source.get('visual') and
                  _has_date(bank['period_start'],source['quote']) and _has_date(bank['period_end'],source['quote']))
        text=' '.join(p['text'] for p in doc['pages'])
        visible_currency_text=text+' '+source['quote']+' '+(bank['balance_source'] or {}).get('quote','')
        currency=bank['currency']
        currency_known=_currency_present(currency,visible_currency_text)
        fully_read=readable and currency_known and bank['transaction_coverage']=='complete'
        window_start=_month_start(end,5)
        full_window=start<=window_start
        bank['analysis_complete']=fully_read and full_window
        bank['_document_complete']=fully_read
        bank['_credit_candidates']=[]
        bank['analysis_window_start']=max(start,window_start).isoformat()
        bank['analysis_window_end']=end.isoformat()
        bank['source_reading']='locally_traceable' if readable else 'needs_verification'
        bank['missing_months']=[]
        if not fully_read:notes.append(doc['filename']+': transaction coverage, period or currency needs verification.')
        if not full_window:
            flags.append(dict(code='bank_short_window',document_id=doc['id'],start=start.isoformat(),end=end.isoformat(),
                              citations=[source],verification=True))
            notes.append(doc['filename']+': the full six-month window is not available.')
        balance_source=bank['balance_source']
        balance_valid=(bank['closing_balance'] is not None and balance_source is not None and
            balance_source['document_id']==doc['id'] and valid(balance_source) and
            amount_in_quote(bank['closing_balance'],balance_source['quote']))
        bank['balance_verified']=bool(balance_valid and not balance_source.get('visual') and currency_known and
                                      (balance_source['document_id'],balance_source['page']) in covered and
                                      (source['document_id'],source['page']) in covered and
                                      _has_date(bank['period_end'],source['quote'])) if balance_source else False
        if not balance_valid:bank['closing_balance']=None
        if bank['owner_role']=='applicant':
            from validator import _names_match
            names=[context.get('applicant_name'),context.get('applicant_native_name')]
            holder=bank['holder_name']
            if (not holder or re.sub(r'\s+',' ',holder).casefold() not in re.sub(r'\s+',' ',text).casefold() or
                    not any(_names_match(name,holder) for name in names if name)):
                bank['owner_role']='unknown'
        business=bank['business_sources']
        if bank['income_basis']=='business':
            if len(business)<2 or not all(valid(c) for c in business):bank['income_basis']='unknown'
            # Business evidence explains why fixed payroll is not required; it does not authenticate money.
        checked_months=set();missing=[];uncertain=[];months=[];used_payments=set()
        for month in bank['salary_months']:
            month_date=_date(month['month']+'-01')
            if (not month_date or month['month'] in checked_months or
                    not window_start<=month_date<=_month_start(end)):continue
            checked_months.add(month['month'])
            last=month_date.replace(day=monthrange(month_date.year,month_date.month)[1])
            if last<start or month_date>end:continue
            full=bool(month['complete_month'] and start<=month_date and end>=last and fully_read)
            if salary and salary.get('currency')==currency:
                local=_local_salary_match(doc,month['month'],salary['amount'],currency)
                if local:
                    month.update(status='matched',matched_amount=salary['amount'],credited_date=local[0],citations=[local[1]])
            citations=month['citations']
            traced=all(valid(c) and c['document_id']==doc['id'] and not c.get('visual') for c in citations)
            match=(salary and salary.get('currency')==currency and month['matched_amount'] is not None and
                   abs(month['matched_amount']-salary['amount'])<=.01 and citations and traced and
                   any(amount_in_quote(month['matched_amount'],c['quote']) for c in citations))
            if month['status']=='matched' and not match:month['status']='uncertain'
            if month['status']=='matched':
                when=_date(month['credited_date'])
                if (not when or not month_date-timedelta(days=7)<=when<=last+timedelta(days=7) or
                        not _has_date(month['credited_date'],' '.join(c['quote'] for c in citations))):
                    month['status']='uncertain'
                key=(month['credited_date'],month['matched_amount'])
                if key in used_payments:month['status']='uncertain'
                used_payments.add(key)
            if month['status']=='not_found' and not full:month['status']='uncertain'
            if (salary and salary.get('currency')==currency and full and month['status']=='not_found' and
                    bank['owner_role']=='applicant'):missing.append(month['month'])
            if salary and month['status']=='uncertain':uncertain.append(month['month'])
            month['complete_month']=full;months.append(month)
        bank['salary_months']=months
        if salary and bank['owner_role']=='applicant':
            if salary.get('currency')!=currency:
                flags.append(dict(code='bank_salary_currency',document_id=doc['id'],amount=salary['amount'],
                    salary_currency=salary.get('currency'),currency=currency,citations=[salary['source'],source],verification=True))
            elif missing:
                flags.append(dict(code='bank_salary_missing',document_id=doc['id'],amount=salary['amount'],currency=currency,
                    months=missing,basis=salary.get('basis','unknown'),citations=[salary['source'],source],verification=True))
            if uncertain:
                flags.append(dict(code='bank_salary_uncertain',document_id=doc['id'],amount=salary['amount'],currency=currency,
                    months=uncertain,citations=[salary['source'],source],verification=True))
                notes.append(doc['filename']+': some salary matches need manual verification.')
            for offset in range(6):
                m=_month_start(end,offset)
                if m>=start.replace(day=1) and m.strftime('%Y-%m') not in checked_months:
                    bank['missing_months'].append(m.strftime('%Y-%m'))
            if bank['missing_months']:
                notes.append(doc['filename']+': some monthly salary checks were not completed.')
        candidates=[]
        for event in bank['large_credit_days']:
            when=_date(event['date']);citations=event['citations']
            if not when or not max(start,window_start)<=when<=end or not all(
                    valid(c) and c['document_id']==doc['id'] for c in citations):continue
            if not _has_date(event['date'],' '.join(c['quote'] for c in citations)):continue
            if not any(amount_in_quote(event['amount'],c['quote']) for c in citations):
                # A proposed sum is usable only when its constituent credit rows can be calculated.
                from hr_extractor import normalize_money
                amounts=[]
                lines=set(line for c in citations for line in c['quote'].splitlines())
                for line in lines:
                    if not _has_date(event['date'],line):continue
                    match=re.search(r'(?:credit|إيداع|ايداع|دائن)\s*(?:[A-Z]{3}|جنيه)?\s*([0-9٠-٩۰-۹][0-9٠-٩۰-۹,.٬٫]*)',line,re.I)
                    value=normalize_money(match.group(1)) if match else None
                    if value is not None:amounts.append(float(value))
                if not amounts or abs(sum(amounts)-event['amount'])>.01:
                    notes.append(doc['filename']+': a proposed daily credit amount could not be traced to source amounts.');continue
            bank['_credit_candidates'].append(event)
            total=bank['total_credits']
            reported_read=expected<=(reported_coverage or covered)
            comparative=(reported_read and currency_known and bank['transaction_coverage']=='complete' and full_window)
            share=event['amount']/total if comparative and total and event['amount']<=total else None
            absolute=currency=='EGP' and currency_known and event['amount']>=500000
            dominant=share is not None and share>.60
            if not (absolute or dominant):continue
            candidates.append(event)
            flags.append(dict(code='bank_large_credit',document_id=doc['id'],amount=event['amount'],currency=currency,
                date=event['date'],share=share,total_credits=total,absolute_threshold=absolute,
                share_threshold=dominant,citations=citations,verification=True,share_estimated=not fully_read))
        bank['large_credit_days']=candidates;banks.append(bank)
    flags,notes=_combine_monthly_statements(banks,flags,notes,docs,valid)
    for bank in banks:
        bank.pop('_document_complete',None);bank.pop('_credit_candidates',None)
    if expected_banks-seen:notes.append('Some bank statements have no structured account assessment.')
    budget=_budget(context,proposal,banks,docs,valid) if proposal is not None else None
    if proposal is None and any('travel_plan' in d['categories'] for d in packet['documents']):
        budget=dict(status='insufficient_data',missing=['city_cost_estimates'],estimated=True)
    return banks,flags,budget,notes


def _combine_monthly_statements(banks,flags,notes,docs,valid):
    """Join non-overlapping months only for a visibly identified identical account."""
    groups={}
    for bank in banks:
        source=bank.get('account_source');account=bank.get('account_id');name=bank.get('bank_name')
        if not account or not source or source.get('visual') or not valid(source) or source['document_id']!=bank['document_id']:continue
        canonical=lambda value:re.sub(r'[^A-Z0-9]','',value.upper())
        key=canonical(account)
        if len(key)<6 or '*' in account or key not in canonical(source['quote']):continue
        text=' '.join(p['text'] for p in docs[bank['document_id']]['pages'])
        iban=bool(re.fullmatch(r'[A-Z]{2}\d{2}[A-Z0-9]{11,30}',key))
        if not iban and (not name or name.casefold() not in text.casefold()):continue
        if bank['owner_role']!='applicant' or not bank['_document_complete']:continue
        groups.setdefault((key,canonical(name or ''),bank['currency']),[]).append(bank)
    for group in groups.values():
        if len(group)<2:continue
        ordered=sorted(group,key=lambda b:b['period_start']);latest=max(_date(b['period_end']) for b in group)
        window=_month_start(latest,5)
        relevant=[b for b in ordered if _date(b['period_end'])>=window]
        if (not relevant or _date(relevant[0]['period_start'])>window or
                any(_date(b['period_start'])!=_date(a['period_end'])+timedelta(days=1) for a,b in zip(relevant,relevant[1:]))):continue
        # An older partial document would require transaction-level allocation; do not guess.
        if _date(relevant[0]['period_start'])!=window:continue
        if any(b['total_credits'] is None for b in relevant):continue
        total=sum(b['total_credits'] for b in relevant);ids={b['document_id'] for b in relevant}
        flags=[f for f in flags if not (f['document_id'] in ids and f['code'] in ('bank_short_window','bank_large_credit'))]
        repaired={docs[i]['filename']+': the full six-month window is not available.' for i in ids}
        notes=[note for note in notes if note not in repaired]
        for bank in relevant:
            bank['analysis_complete']=True;bank['combined_total_credits']=total
            bank['large_credit_days']=[]
            bank['analysis_window_start']=window.isoformat();bank['analysis_window_end']=latest.isoformat()
            for event in bank['_credit_candidates']:
                share=event['amount']/total if total and event['amount']<=total else None
                absolute=bank['currency']=='EGP' and event['amount']>=500000
                dominant=share is not None and share>.6
                if absolute or dominant:
                    bank['large_credit_days'].append(event)
                    flags.append(dict(code='bank_large_credit',document_id=bank['document_id'],amount=event['amount'],
                        currency=bank['currency'],date=event['date'],share=share,total_credits=total,
                        absolute_threshold=absolute,share_threshold=dominant,verification=True,share_estimated=False,
                        citations=event['citations']+[b['period_source'] for b in relevant if b is not bank]))
    return flags,notes


def _budget(context,proposal,banks,docs,valid):
    budget=proposal.model_dump();missing=[];daily_low=0.;daily_high=0.;city_days=0
    def reliable(source):
        doc=docs.get(source['document_id'])
        page=next((p for p in doc['pages'] if p['number']==source['page']),None) if doc else None
        return bool(page and not page['provisional'] and not source.get('visual') and valid(source))
    for city in budget['cities']:
        source=city['source'];doc=docs.get(source['document_id'])
        if (not doc or not set(doc['categories'])&{'travel_plan','hotel'} or not reliable(source) or
                city['daily_high_eur']<city['daily_low_eur']):
            missing.append('city_evidence');continue
        city_days+=city['days'];daily_low+=city['days']*city['daily_low_eur'];daily_high+=city['days']*city['daily_high_eur']
    start,end=_date(context.get('trip_start')),_date(context.get('trip_end'))
    if not start or not end:
        dates=budget.get('dates_sources',[])
        if dates and all(reliable(c) and
                         set(docs[c['document_id']]['categories'])&{'visa_form','flight','travel_plan'} for c in dates):
            text=' '.join(c['quote'] for c in dates)
            if _has_date(budget.get('trip_start'),text) and _has_date(budget.get('trip_end'),text):
                start,end=_date(budget['trip_start']),_date(budget['trip_end'])
    expected_days=(end-start).days+1 if start and end and end>=start else None
    if expected_days is None or expected_days!=city_days:missing.append('trip_day_coverage')
    if budget['intercity_high_eur']<budget['intercity_low_eur']:missing.append('transport_range')
    rates=context.get('rates',{}).get('rates',{})
    def eur(amount,currency):
        rate=rates.get(currency)
        return amount/rate if rate and rate>0 else None
    reservations=[];quoted_total=0.;unpaid=0.;seen=set()
    for cost in context.get('reservation_costs',[]):
        key=(cost['category'],cost['source']['document_id'])
        if key in seen:continue
        seen.add(key)
        if not reliable(cost['source']):missing.append('reservation_evidence');continue
        value=eur(cost['amount'],cost['currency'])
        if value is None:missing.append('currency_conversion');continue
        quoted_total+=value
        if not cost['paid']:unpaid+=value
        reservations.append(dict(**cost,eur=round(value,2)))
    if not any(kind=='flight' for kind,_ in seen):missing.append('flight_price')
    expected_hotels=max(1,context.get('expected_hotels',0))
    if sum(kind=='hotel' for kind,_ in seen)<expected_hotels:missing.append('hotel_price')
    low=daily_low+budget['intercity_low_eur'];high=daily_high+budget['intercity_high_eur']
    checks=[]
    usable=[b for b in banks if b['closing_balance'] is not None and b['balance_verified'] and b['owner_role']=='applicant']
    if usable:
        latest=max(b['period_end'] for b in usable)
        for bank in usable:
            if bank['period_end']!=latest:continue
            balance=eur(bank['closing_balance'],bank['currency'])
            status='unknown' if balance is None else 'partial_estimate' if missing else 'below_estimate' if balance<unpaid+low else 'within_range' if balance<unpaid+high else 'covers_estimated_range'
            checks.append(dict(document_id=bank['document_id'],balance=bank['closing_balance'],currency=bank['currency'],
                balance_eur=round(balance,2) if balance is not None else None,statement_date=latest,status=status))
    if not checks:missing.append('verified_latest_applicant_balance')
    return dict(**budget,status='estimate' if not missing else 'insufficient_data',estimated=True,
        total_low_eur=round(quoted_total+low,2),total_high_eur=round(quoted_total+high,2),
        remaining_low_eur=round(unpaid+low,2),remaining_high_eur=round(unpaid+high,2),
        reservation_costs=reservations,days=expected_days,balance_checks=checks,missing=sorted(set(missing)),
        fx_date=context.get('rates',{}).get('date'))
