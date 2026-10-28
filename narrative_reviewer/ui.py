"""Gemini findings are advisory, source checked and isolated to the current session."""
import streamlit as st
from i18n import t
from settings import setting
from .packet import build_packet


def prepare(result,lang):
    if 'narrative_packet' not in result or result['narrative_packet']['language']!=lang:
        result['narrative_packet']=build_packet(result['source_files'],result['extraction'],
            result.get('review_country','unknown'),lang,original_uploads=result.get('narrative_original_roles'),rates=result.get('exchange_snapshot'),converted_sources=result.get('converted_sources'))
        result.pop('narrative_review',None)
    return result['narrative_packet']


def render_narrative_review(result,lang='en',authorize=None,run_remote=None):
    if not result.get('narrative_requested'):return
    st.subheader(t('reasoning_title',lang))
    st.caption(t('reasoning_scope',lang))
    if not setting('GEMINI_API_KEY'):
        st.warning(t('gemini_config_missing',lang))
        return
    if authorize:authorize()
    packet=result.get('narrative_packet')
    review=result.get('narrative_review')
    stale=packet and packet['language']!=lang
    if not review or review.get('status')=='unavailable' or stale:
        st.caption(t('reasoning_retry_quota',lang))
        if st.button(t('reasoning_run',lang),key='reasoning_run',disabled=run_remote is None):
            if authorize:authorize()
            try:
                with st.spinner(t('reasoning_running',lang)):
                    packet=prepare(result,lang)
                    result['narrative_review']=run_remote(packet)
            except Exception as exc:
                from accounts import AccountError,ReviewLimitError
                if isinstance(exc,ReviewLimitError):
                    st.error(t('rate_limited_details',lang,period=t(exc.period,lang),**exc.details))
                elif isinstance(exc,AccountError):raise
                else:
                    result['narrative_review']=dict(status='unavailable',findings=[],limitations=[])
    if stale and (not packet or packet['language']!=lang):return
    packet=result.get('narrative_packet')
    review = result.get('narrative_review')
    if not review:
        return
    if review['status'] == 'unavailable':
        st.warning(t('reasoning_unavailable', lang))
        return
    if review.get('fallback_used'):st.caption(t('reasoning_fallback_used',lang))
    if review['status'] != 'complete':
        st.warning(t('reasoning_partial', lang))
    if not review['findings'] and not review.get('bank_flags'):
        st.info(t('reasoning_no_findings', lang))
    docs = {doc['id']:doc for doc in packet['documents']}
    current_section=None
    for finding in review['findings']:
        if finding['section']!=current_section:
            current_section=finding['section'];st.subheader(t('doc_'+current_section,lang))
        with st.container(border=True):
            st.text(finding['title'])
            st.text(t('reasoning_kind_'+finding['kind'], lang))
            st.text(finding['explanation'])
            for citation in finding['citations']:
                doc = docs[citation['document_id']]
                label='text_section' if any(p['method']=='native_text' for p in doc['pages']) else 'page'
                st.text(f'{doc["filename"]} · {t(label, lang)} {citation["page"]}')
                if doc.get('context_mode')=='extracted_fields':
                    st.caption(t('reasoning_extracted',lang))
                if citation.get('visual'):st.caption(t('review_visual_quote',lang))
                st.text(citation['quote'])
            st.text(t('review_action_'+finding.get('action','verify'),lang)+': '+finding['suggestion'])
    from .financial_ui import render_financial
    render_financial(review,packet,lang)
    if review['limitations']:
        with st.expander(t('reasoning_limitations', lang)):
            for note in review['limitations']:
                st.text(note)
