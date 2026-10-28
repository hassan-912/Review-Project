"""Corrections-only website output and verifiable review provenance."""
from html import escape

import streamlit as st

from i18n import t,issue_text,document_label
from pdf_report import build_pdf_report
from evidence import render_error_region
from monitoring import capture_error


def _value_html(value,kind,lang,label=None):
    value=t('missing_value',lang) if value is None or value=='' else str(value)
    label=label or t('incorrect_value' if kind=='incorrect' else 'correct_value',lang)
    return '<div class="comparison-value '+kind+'"><div class="comparison-label">'+escape(label)+'</div><bdi dir="auto">'+escape(value)+'</bdi></div>'


def _source_text(locations,lang):
    return ' · '.join(dict.fromkeys(f"{location['source_file']} ({t('text_section' if location.get('native_section') else 'page',lang)} {location.get('native_section') or location.get('page',1)})"
        for location in locations if location.get('source_file')))


def _document_heading(issue,lang):
    st.subheader(document_label(issue.document_name.split(' (')[0],lang),anchor=False)
    names=list(dict.fromkeys(location['source_file'] for location in issue.evidence if location.get('source_file')))
    if names:
        st.html('<div class="correction-files">'+''.join('<div><bdi dir="auto">'+escape(name)+'</bdi></div>' for name in names)+'</div>')


def _error_screenshots(issue,result,lang):
    # A missing night has no incorrect printed value to mark in a screenshot.
    if issue.field_name=='hotel_coverage_gap':return []
    if not result or not result.get('source_files') or not issue.evidence:return []
    cache=result.setdefault('correction_images_v3',{})
    shown=[]
    for location in issue.evidence[:2]:
        if location.get('native_section'):continue
        key=repr(sorted(location.items()))
        if key not in cache:
            if len(cache)>=24:cache.pop(next(iter(cache)))
            try:cache[key]=render_error_region(location,result['source_files'])
            except Exception as exc:
                capture_error(exc,'field_screenshot')
                cache[key]=None
        if image:=cache[key]:
            png,page,_=image
            st.image(png,width='content')
            shown.append(dict(location,page=page))
    if not shown:st.caption(t('error_region_unavailable',lang))
    return shown


def _reference_screenshots(issue,result,lang):
    """Show only the actual printed reference value, never a calculated threshold."""
    if not result or not result.get('source_files'):return []
    locations=[location for location in issue.reference_evidence
               if not location.get('preview') and not location.get('native_section') and location.get('value')==issue.expected_value]
    cache=result.setdefault('reference_images_v1',{})
    shown=[]
    for location in locations[:2]:
        key=repr(sorted(location.items()))
        if key not in cache:
            if len(cache)>=24:cache.pop(next(iter(cache)))
            try:cache[key]=render_error_region(location,result['source_files'],kind='correct')
            except Exception as exc:
                capture_error(exc,'reference_screenshot');cache[key]=None
        if image:=cache[key]:
            png,page,_=image
            st.text(t('reference_source',lang)+': '+_source_text([dict(location,page=page)],lang))
            st.image(png,width='content')
            shown.append(dict(location,page=page))
    return shown


def render_findings(issues,result=None,lang='en'):
    findings=[issue for issue in issues if issue.affects_score]
    st.subheader(t('corrections_title',lang,count=len(findings)))
    if not findings:
        st.info(t('no_confirmed_mismatches',lang))
        return
    for index,issue in enumerate(findings):
        title,_=issue_text(issue,lang)
        with st.container(border=True,key=f'card_correction_{index}'):
            _document_heading(issue,lang)
            if issue.field_name=='passport_upload':
                st.error(t('passport_upload_missing',lang))
                continue
            st.html('<h4>'+escape(title)+'</h4>')
            wrong,right=st.columns(2)
            with wrong:
                st.html(_value_html(issue.found_value,'incorrect',lang))
            with right:
                label=t('gap_required_coverage',lang) if issue.field_name=='hotel_coverage_gap' else None
                st.html(_value_html(issue.expected_value,'correct',lang,label))
                if source:=_source_text(issue.reference_evidence,lang):st.text(t('reference_source',lang)+': '+source)
            shown=_error_screenshots(issue,result,lang)
            if source:=_source_text(shown or issue.evidence,lang):st.text(t('source',lang)+': '+source)
            _reference_screenshots(issue,result,lang)


def check_receipt(result):
    data=result['extraction']
    provenance=result.get('provenance') or data.review_provenance
    return dict(provenance,corrections=[dict(document=issue.document_name,field=issue.field_name,
        rule=issue.message_key,check_origin=issue.check_origin,found=issue.found_value,expected=issue.expected_value,
        sources=issue.evidence,references=issue.reference_evidence,explanation=issue.recommended_fix)
        for issue in result['issues'] if issue.affects_score],
        unverified_checks=sum(not issue.affects_score and issue.message_key!='identity.id_reference_note' for issue in result['issues']))


def render_report_view(result,lang='en',authorize_narrative=None,run_narrative=None):
    data,issues=result['extraction'],result['issues']
    render_findings(issues,result,lang)
    if result.get('converted_sources'):st.caption(t('converted_copy_note',lang))
    from narrative_reviewer.ui import render_narrative_review
    render_narrative_review(result,lang,authorize_narrative,run_narrative)
    writing=result.get('writing') or {}
    pdfs=result.setdefault('correction_pdfs_v3',{})
    def download():
        # Streamlit calls this only when downloading, on its download worker.
        try:
            if lang not in pdfs:
                pdfs[lang]=build_pdf_report(data,issues,result['score'],result.get('biz_result'),lang,
                    result.get('client_name',''),writing,corrections_only=True)
            return pdfs[lang]
        except Exception as exc:
            capture_error(exc,'pdf_download')
            raise RuntimeError('Correction PDF could not be generated.') from None
    st.download_button(t('download_corrections',lang),download,file_name='MG-corrections.pdf',
        mime='application/pdf',on_click='ignore')
