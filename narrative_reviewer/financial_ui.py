"""Problem-only bank feedback and an explicit, approximate tourism budget."""
import streamlit as st
from i18n import t


def source_quotes(citations,docs,lang):
    for citation in citations:
        doc=docs.get(citation['document_id'],{})
        label='text_section' if any(p['method']=='native_text' for p in doc.get('pages',[])) else 'page'
        st.caption(f"{doc.get('filename','')} · {t(label,lang)} {citation['page']}")
        if citation.get('visual'):st.caption(t('review_visual_quote',lang))
        st.text(citation['quote'])


def render_financial(review,packet,lang):
    docs={d['id']:d for d in packet['documents']}
    flags=review.get('bank_flags',[])
    if flags:
        st.subheader(t('review_bank_problems',lang))
        for flag in flags:
            values={key:value for key,value in flag.items() if key not in ('citations','code')}
            values['amount']=f"{flag.get('amount',0):,.2f}"
            values['months']=', '.join(flag.get('months',[]))
            values['share']=f"{100*flag['share']:.1f}" if flag.get('share') is not None else t('unknown',lang)
            values['salary_currency']=flag.get('salary_currency') or t('unknown',lang)
            values['basis']=t('salary_'+flag.get('basis','unknown'),lang)
            with st.container(border=True):
                code='bank_large_credit_absolute' if flag['code']=='bank_large_credit' and flag.get('share') is None else flag['code']
                st.text(t(code,lang,**values))
                st.caption(t('bank_flag_explanation',lang))
                with st.expander(t('review_sources',lang)):
                    source_quotes(flag['citations'],docs,lang)
    budget=review.get('trip_budget')
    if not budget:return
    st.subheader(t('review_trip_budget',lang))
    st.caption(t('budget_estimate_note',lang))
    st.caption(t('budget_payment_assumption',lang))
    if budget.get('total_low_eur') is not None:
        with st.container(horizontal=True):
            st.metric(t('budget_total_trip',lang),f"EUR {budget['total_low_eur']:,.0f}–{budget['total_high_eur']:,.0f}",border=True)
            st.metric(t('budget_remaining_trip',lang),f"EUR {budget['remaining_low_eur']:,.0f}–{budget['remaining_high_eur']:,.0f}",border=True)
        rate=packet.get('financial_context',{}).get('rates',{}).get('rates',{}).get('EGP')
        if rate:
            st.caption(t('budget_egp_estimate',lang,low=f"{rate*budget['total_low_eur']:,.0f}",high=f"{rate*budget['total_high_eur']:,.0f}",date=budget.get('fx_date') or t('unknown',lang)))
        for city in budget.get('cities',[]):
            st.text(t('budget_city_estimate',lang,city=city['city'],days=city['days'],low=city['daily_low_eur'],high=city['daily_high_eur']))
        for cost in budget.get('reservation_costs',[]):
            st.caption(f"{t('doc_'+cost['category'],lang)} · {docs[cost['source']['document_id']]['filename']} · {cost['amount']:,.2f} {cost['currency']}")
        for check in budget.get('balance_checks',[]):
            st.text(t('budget_latest_balance',lang,amount=f"{check['balance']:,.2f}",currency=check['currency'],date=check['statement_date']))
            st.caption(t('budget_result_'+check['status'],lang))
        if budget.get('assumptions'):st.caption(budget['assumptions'])
    if budget.get('missing'):
        st.warning(t('budget_missing_data',lang,items=', '.join(t('budget_missing_'+key,lang) for key in budget['missing'])))
