"""Admin-only Gemini cost dashboard backed by the durable request ledger."""
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
import streamlit as st
import accounts
from i18n import t
from gemini_usage import MODELS,exchange_snapshot,pricing_snapshot,provider_usage,cost_snapshot
from settings import setting


@st.cache_data(ttl=3600,show_spinner=False)
def dashboard_exchange(day,override):
    # Public FX only. Never cache account records, file names or document data.
    return exchange_snapshot()


def average(rows,key):
    values=[float(row[key]) for row in rows if row.get(key) is not None]
    return sum(values)/len(values) if values else None


def file_rows(rows):
    files=[]
    for row in rows:
        for item in row.get('files') or []:
            output=item.get('billable_output_tokens')
            if output is None and item.get('output_tokens') is not None and item.get('thinking_tokens') is not None:
                output=item['output_tokens']+item['thinking_tokens']
            files.append({**item,'user':row['username'] or row['user_id'],'model':row['model'],
                'date':row['created_at'],'review_id':row['review_id'],'billable_output_tokens':output})
    return files


def category_averages(files):
    groups={}
    for item in files:
        key=tuple(sorted(item.get('categories') or ['other']))
        groups.setdefault(key,[]).append(item)
    return [dict(categories=key,files=len(items),avg_input_tokens=average(items,'input_tokens'),
        avg_output_tokens=average(items,'billable_output_tokens'),avg_cost_egp=average(items,'cost_egp'),
        unknown=sum(item.get('cost_egp') is None for item in items)) for key,items in sorted(groups.items())]


@st.fragment
def render_estimator(lang,fx):
    st.subheader(t('cost_calculator',lang))
    st.caption(t('cost_calculator_note',lang))
    # Widget keys may be cleaned up when leaving this fragment's page. Keep
    # defaults in a non-widget state entry so remounting shows the same values
    # that the calculation uses, instead of new inputs with an old total.
    saved=st.session_state.setdefault('cost_estimate_values',dict(
        model=st.session_state.get('cost_estimate_model',MODELS[0]),
        incoming=st.session_state.get('cost_estimate_input',1000),
        outgoing=st.session_state.get('cost_estimate_output',300)))
    model_column,input_column,output_column=st.columns(3)
    model=model_column.selectbox(t('cost_col_model',lang),MODELS,index=MODELS.index(saved['model']),key='cost_estimate_model')
    incoming=input_column.number_input(t('cost_input',lang),min_value=0,value=saved['incoming'],step=100,key='cost_estimate_input')
    outgoing=output_column.number_input(t('cost_output',lang),min_value=0,value=saved['outgoing'],step=100,key='cost_estimate_output')
    saved.update(model=model,incoming=incoming,outgoing=outgoing)
    rates={**pricing_snapshot(model=model),**fx}
    usage=provider_usage(dict(promptTokenCount=incoming,candidatesTokenCount=outgoing))
    cost=cost_snapshot(usage,rates)
    usd,egp=st.columns(2)
    usd.metric(t('cost_estimated_usd',lang),f"{cost['cost_usd']:.6f}",border=True)
    egp.metric(t('cost_estimated_egp',lang),f"{cost['cost_egp']:.4f}" if cost['cost_egp'] is not None else '—',border=True)
    st.caption(t('cost_formula',lang,input=rates['input_rate'],output=rates['output_rate']))
    if fx.get('usd_egp'):
        st.caption(t('cost_fx_snapshot',lang,rate=f"{fx['usd_egp']:.4f}",date=fx.get('fx_date') or '—'))
    else:st.warning(t('cost_fx_unavailable',lang))


def render_cost_dashboard(client,session,lang='en'):
    st.subheader(t('admin_costs',lang))
    now=datetime.now(ZoneInfo('Africa/Cairo'))
    periods=['cost_today','cost_month','cost_30_days']
    period=st.selectbox(t('cost_period',lang),periods,index=1,
                        format_func=lambda key:t(key,lang),key='cost_period')
    start=now.replace(hour=0,minute=0,second=0,microsecond=0)
    if period=='cost_month':start=start.replace(day=1)
    elif period=='cost_30_days':start-=timedelta(days=29)
    fx=dashboard_exchange(now.date().isoformat(),setting('USD_EGP_RATE',''))
    render_estimator(lang,fx)
    try:
        rows=accounts.gemini_usage_rows(client,session,start.isoformat(),now.isoformat())
    except Exception:
        st.error(t('cost_unavailable',lang));return
    if not rows:
        st.info(t('cost_empty',lang))
    render_cost_rows(rows,lang)


@st.fragment
def render_cost_rows(rows,lang):
    """Filter an already authorised snapshot without re-querying the ledger."""
    agents=sorted({row['username'] or row['user_id'] for row in rows})
    selected=st.multiselect(t('cost_users',lang),agents,key='cost_users')
    if selected:rows=[row for row in rows if (row['username'] or row['user_id']) in selected]
    unknown=sum(not row['usage_known'] for row in rows)
    missing_fx=sum(row.get('cost_usd') is not None and row.get('cost_egp') is None for row in rows)
    with st.container(horizontal=True):
        st.metric(t('cost_requests',lang),len(rows),border=True)
        st.metric(t('cost_input',lang),sum(row.get('input_tokens') or 0 for row in rows),border=True)
        st.metric(t('cost_output',lang),sum(row.get('billable_output_tokens') or 0 for row in rows),border=True)
        st.metric(t('cost_total_egp',lang),f"{sum(float(row.get('cost_egp') or 0) for row in rows):.4f}",border=True)
    if unknown or missing_fx:
        st.warning(t('cost_unknown',lang,usage=unknown,fx=missing_fx))
    st.caption(t('cost_rates_note',lang))
    allocations=file_rows(rows)
    files_by_review={}
    for item in allocations:files_by_review.setdefault(item['review_id'],[]).append(item)
    for label,data in (('cost_avg_review',rows),('cost_avg_file',allocations)):
        st.subheader(t(label,lang))
        with st.container(horizontal=True):
            for metric,key,digits in (('cost_avg_input','input_tokens',1),('cost_avg_output','billable_output_tokens',1),('cost_avg_egp','cost_egp',4)):
                value=average(data,key)
                st.metric(t(metric,lang),'—' if value is None else f'{value:.{digits}f}',border=True)
    st.caption(t('cost_averages_note',lang))
    displayed=[];files=[];users={}
    for row in rows:
        user=row['username'] or row['user_id']
        stats=users.setdefault(user,dict(requests=0,input_tokens=0,billable_output_tokens=0,cost_egp=0,unknown=0))
        stats['requests']+=1
        for key in ('input_tokens','billable_output_tokens','cost_egp'):stats[key]+=float(row.get(key) or 0)
        stats['unknown']+=int(not row['usage_known'] or row.get('cost_egp') is None)
        stamp=datetime.fromisoformat(row['created_at'].replace('Z','+00:00')).astimezone(ZoneInfo('Africa/Cairo')).strftime('%Y-%m-%d %H:%M')
        displayed.append(dict(user=user,date=stamp,review_id=row['review_id'],status=t(row['status'],lang),
            model=row['model'],input_tokens=row.get('input_tokens'),output_tokens=row.get('output_tokens'),
            thinking_tokens=row.get('thinking_tokens'),cached_input_tokens=row.get('cached_input_tokens'),
            cost_usd=row.get('cost_usd'),cost_egp=row.get('cost_egp'),usd_egp=row.get('usd_egp'),fx_date=row.get('fx_date')))
        for item in files_by_review.get(row['review_id'],[]):
            files.append(dict(user=user,date=stamp,review_id=row['review_id'],filename=item['filename'],
                model=row['model'],fallback_from=item.get('fallback_from'),
                context_mode=t('cost_context_'+item['context_mode'],lang),input_tokens=item.get('input_tokens'),output_tokens=item.get('output_tokens'),
                thinking_tokens=item.get('thinking_tokens'),billable_output_tokens=item.get('billable_output_tokens'),cost_egp=item.get('cost_egp')))
    def show(data):
        # Native display escapes file/user strings. Costs retain sub-piastre precision.
        st.dataframe([{t('cost_col_'+key,lang):value for key,value in row.items()} for row in data],
                     hide_index=True,width='stretch')
    st.subheader(t('cost_by_category',lang))
    show([{**{key:value for key,value in group.items() if key!='categories'},
           'category':' + '.join(t('doc_'+key,lang) if key!='other' else t('cost_other',lang) for key in group['categories'])}
          for group in category_averages(allocations)])
    st.subheader(t('cost_by_user',lang));show([dict(user=user,**values) for user,values in users.items()])
    st.subheader(t('cost_actual',lang));show(displayed)
    st.subheader(t('cost_files',lang));st.caption(t('cost_allocation_note',lang))
    show(files)
