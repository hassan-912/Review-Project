"""USA-only findings and inspectable structured data; no narrative AI controls."""
import json
import streamlit as st
from i18n import t,field_label,issue_text


def document_sources(result,locations,lang,category=None,source_file=None):
    """Identify the actual supplied file and exact page/section for each value."""
    from report_view import _source_text
    manifest={doc['source_file']:doc for doc in result['usa_documents']}
    def filename(name):
        doc=manifest.get(name,{})
        conversion=result.get('converted_sources',{}).get(doc.get('sha256'),{})
        original=conversion.get('original_name')
        return name[:-4] if original and name.endswith(original+'.pdf') else name
    labels=[]
    for location in locations:
        name=location.get('source_file')
        if not name:continue
        role=location.get('document') or manifest.get(name,{}).get('category') or category
        label=(t('doc_'+role,lang)+' · ') if role else ''
        labels.append(label+_source_text([{**location,'source_file':filename(name)}],lang))
    if not labels and source_file:
        labels.append((t('doc_'+category,lang)+' · ' if category else '')+filename(source_file))
    if not labels and category:
        matches=[filename(name) for name,doc in manifest.items() if doc['category']==category]
        labels.append(t('doc_'+category,lang)+' · '+(', '.join(matches)+' ('+t('usa_value_not_extracted',lang)+')' if matches else t('usa_document_not_supplied',lang)))
    return ' · '.join(dict.fromkeys(labels)) or t('usa_no_comparison_value',lang)


def verification_rows(result,checks,lang):
    """Export values separately from document provenance and coverage notes."""
    return [{t('issue',lang):field_label(c['field'],lang),
        t('usa_checked_document',lang):document_sources(result,c['sources'],lang,c['target_category'],c.get('source_file')),
        t('usa_checked_value',lang):c.get('found') if c['sources'] else None,
        t('usa_comparison_document',lang):document_sources(result,c['references'],lang,c['reference_category']),
        t('usa_comparison_value',lang):c.get('expected') if c['references'] else None,
        ('Reason' if lang=='en' else 'السبب'):(('Translation requires verification; original values retained.' if lang=='en' else
            'تحتاج الترجمة إلى التحقق؛ تم الاحتفاظ بالقيم الأصلية.') if c.get('language_comparison') else '')} for c in checks]


def _comparison_evidence(issue,result,lang):
    from report_view import _error_screenshots,_reference_screenshots
    def native_images(locations):
        for location in locations[:2]:
            if not location.get('native_section'):continue
            st.caption(t('usa_converted_text_evidence',lang))
            if png:=_native_evidence_image(location,result):st.image(png,width='content')
            else:st.caption(t('error_region_unavailable',lang))
    wrong,right=st.columns(2)
    with wrong:
        st.caption(t('usa_checked_document',lang)+': '+document_sources(result,issue.evidence,lang))
        native_images(issue.evidence)
        if issue.field_name=='hotel_coverage_gap':
            # Coverage is calculated from dates; show their real source crops
            # without suggesting that a particular printed date is itself wrong.
            from evidence import render_source
            cache=result.setdefault('usa_coverage_images_v1',{})
            for location in issue.evidence[:2]:
                key=repr(sorted(location.items()))
                if key not in cache:cache[key]=render_source(location,result.get('source_files',{}))
                if image:=cache[key]:st.image(image[0],width='content')
        elif any(not location.get('native_section') for location in issue.evidence):
            _error_screenshots(issue,result,lang)
    with right:
        st.caption(t('usa_comparison_document',lang)+': '+document_sources(result,issue.reference_evidence,lang))
        native_images(issue.reference_evidence)
        # A grouped or derived comparison is not a literal source quotation.
        # Render the individual printed fields behind it, without fabricating
        # a screenshot of the combined/normalized expected-value summary.
        for location in issue.reference_evidence[:2]:
            if location.get('native_section') or not location.get('value'):continue
            if issue.field_name=='us_contact_hotel' and (location.get('document')!='hotel' or
                    location.get('field_name') not in ('hotel_name','hotel_address','hotel_phone','hotel_email')):continue
            part=issue.model_copy(update={'expected_value':str(location['value']),'reference_evidence':[location]})
            _reference_screenshots(part,result,lang)


def _native_evidence_image(location,result):
    """Render only a verified native-text section, never unrelated private rows.

    The image is labelled converted text; it does not pretend to preserve the
    original Word/HTML page layout or invent a PDF page for its citation.
    """
    from hashlib import sha256
    import pymupdf
    from document_ingestion import text_pdf
    matches=[raw for group in result.get('source_files',{}).values() for name,raw in group
             if name==location.get('source_file')]
    if len(matches)!=1:return None
    conversion=result.get('converted_sources',{}).get(sha256(matches[0]).hexdigest(),{})
    lines=conversion.get('text','').splitlines();section=location.get('native_section')
    quote=location.get('text')
    if not isinstance(section,int) or not 1<=section<=len(lines) or not isinstance(quote,str):return None
    if lines[section-1].strip()!=quote.strip() or not quote.strip() or len(quote)>4000:return None
    key=(location['source_file'],section,sha256(quote.encode()).hexdigest())
    cache=result.setdefault('usa_native_evidence_images_v1',{})
    if key not in cache:
        with pymupdf.open(stream=text_pdf(quote),filetype='pdf') as pdf:
            page=pdf[0];blocks=[block for block in page.get_text('blocks') if block[6]==0]
            if not blocks or len(pdf)!=1:return None
            rect=pymupdf.Rect(blocks[0][:4])
            for block in blocks[1:]:rect|=pymupdf.Rect(block[:4])
            rect=(rect+(-8,-8,8,8))&page.rect
            cache[key]=page.get_pixmap(matrix=pymupdf.Matrix(2,2),clip=rect,alpha=False).tobytes('png')
        if len(cache)>48:cache.pop(next(iter(cache)))
    return cache[key]


def _problems(result,lang):
    """Wrong on the left; correct/expected on the right, including RTL pages."""
    problems=[issue for issue in result['issues'] if issue.affects_score or issue.field_name=='passport_identity']
    st.subheader(t('usa_evidence_title',lang))
    if not problems:st.info(t('no_confirmed_mismatches',lang))
    for index,issue in enumerate(problems):
        title,_=issue_text(issue,lang)
        if issue.field_name=='passport_identity':
            title=t('usa_wrong_passport_title' if issue.affects_score else 'usa_wrong_passport_possible',lang)
        with st.container(border=True,key=f'usa_comparison_{index}'):
            st.subheader(title,anchor=False)
            _comparison_evidence(issue,result,lang)
    return problems


def render_usa_report(result,lang='en'):
    st.subheader(t('usa_results',lang))
    st.caption(t('usa_privacy',lang))
    st.caption(t('usa_source_explainer',lang))
    checks=result['usa_checks']
    identity=any(check.get('identity_conflict') for check in checks)
    verification=[c for c in checks if c['status']=='needs_verification' and not c.get('identity_conflict')
                  and not (identity and c['target_category']=='passport' and c['field']=='document_coverage')]
    with st.container(horizontal=True):
        st.metric(t('usa_coverage',lang),sum(c['status']=='match' for c in checks),border=True)
        st.metric(t('corrections_title',lang,count=sum(c['status']=='mismatch' for c in checks)),
            sum(c['status']=='mismatch' for c in checks),border=True)
        st.metric(t('usa_verification',lang),len(verification),border=True)
    if result.get('incomplete'):st.warning(t('usa_incomplete',lang))
    _problems(result,lang)
    if verification:
        notes=st.expander(t('usa_verification',lang),on_change='rerun')
        if notes.open:
            with notes:
                st.caption(t('usa_field_unavailable',lang))
                st.dataframe(verification_rows(result,verification,lang),hide_index=True,width='stretch')
    if result.get('converted_sources'):st.caption(t('converted_copy_note',lang))
    # No documents or extracted answers are added to the shared usage ledger.
    data=dict(engine=result['engine'],external_ai_requests=0,incomplete=result['incomplete'],
        documents=result['usa_documents'],checks=checks)
    with st.expander(t('usa_fields',lang),on_change='rerun') as details:
        if details.open:st.json(data,expanded=2)
    st.download_button(t('usa_download_json',lang),json.dumps(data,ensure_ascii=False,indent=2).encode(),
        file_name='MG-USA-review.json',mime='application/json',on_click='ignore')
    from pdf_report import build_pdf_report
    pdfs=result.setdefault('usa_pdfs',{})
    def download():
        if lang not in pdfs:
            pdfs[lang]=build_pdf_report(result['extraction'],result['issues'],result['score'],lang=lang,
                client_name=result.get('client_name',''),corrections_only=True)
        return pdfs[lang]
    st.download_button(t('download_corrections',lang),download,file_name='MG-USA-corrections.pdf',
        mime='application/pdf',on_click='ignore')
    st.caption(t('usa_not_eligibility',lang))
