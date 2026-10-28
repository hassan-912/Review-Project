"""UI-independent orchestration; extraction caching stays in the browser session."""
from extractor import extract_documents, _extract_pdf_text
from writing_review import writing_recommendations
from validator import run_validation
from business_checker import check_business_alignment
from scorer import calculate_score, _cover_letter_is_complete, _leave_is_confirmed
from supporting_review import check_supporting, extraction_quality
from evidence import attach_evidence
from document_sources import unique_uploads
from source_checks import printed_form_checks, translation_date_checks, reservation_and_title_checks
from finance_review import grounded_financial_data, assess_budget, exchange_rates,extract_booking_costs


def review_documents(uploaded_files, lang="en", progress=None,extraction_cache=None,review_country=None):
    from document_ingestion import normalize_uploads
    uploaded_files,conversions=normalize_uploads(uploaded_files)
    submitted_files=uploaded_files
    uploaded_files = unique_uploads(uploaded_files)
    def step(number):
        if progress:
            progress(number)
    step(1)
    extraction_options={}
    if extraction_cache is not None:extraction_options['cache']=extraction_cache
    if review_country is not None:extraction_options['review_country']=review_country
    extraction = extract_documents(uploaded_files,**extraction_options)
    from appointment_review import ground_appointments
    ground_appointments(extraction, uploaded_files)
    extract_booking_costs(extraction,uploaded_files)
    grounded_financial_data(extraction,uploaded_files)
    source_issues = (([] if extraction.extraction_mode=='local' else printed_form_checks(extraction, uploaded_files)) + translation_date_checks(uploaded_files)
                     + reservation_and_title_checks(extraction, uploaded_files))
    step(2)
    issues = run_validation(extraction) + source_issues
    step(3)
    business = check_business_alignment(extraction)
    issues += business.issues
    issues += check_supporting(extraction,uploaded_files)
    attach_evidence(issues,extraction,uploaded_files)
    for unverified in extraction.unverified_findings:
        sources={source['source_file'] for source in unverified['sources']}
        confirmed=any(issue.affects_score and issue.field_name==unverified['field_name'] and
                      any(loc['source_file'] in sources for loc in issue.evidence) for issue in issues)
        if not confirmed:
            extraction.review_limitations.append('A proposed finding lacked a traceable quote and needs verification: '+unverified['title'])
    quality,quality_issues=extraction_quality(extraction,uploaded_files)
    issues += quality_issues
    if extraction.extraction_mode=='local':
        from local_extraction import guard_local_issues,hr_validation_issues,local_identity_issues
        # HR coverage uses the tested containment rule rather than the legacy one-day allowance.
        issues=[issue for issue in issues if issue.message_key!='hr.window']
        issues+=hr_validation_issues(extraction)
        issues+=local_identity_issues(extraction)
        issues=guard_local_issues(issues,extraction,submitted_files)
    attach_evidence(issues,extraction,uploaded_files)
    if extraction.extraction_mode=='local':
        for issue in issues:
            direct_reference=issue.found_value is not None and any(
                loc.get('value')==issue.expected_value and not loc.get('preview') for loc in issue.reference_evidence)
            issue.check_origin='local_key_value' if direct_reference else 'local_rule'
    step(4)
    score = calculate_score(issues, _cover_letter_is_complete(extraction), _leave_is_confirmed(extraction))
    order = {"CRITICAL":0,"HIGH":1,"MEDIUM":2,"LOW":3}
    issues.sort(key=lambda x: (not x.affects_score, order[x.severity.value]))
    texts = {name:text for category,group in uploaded_files.items() if category!='bank_statement' for name,raw in group
             if (text := _extract_pdf_text(name,raw)) is not None}
    writing = writing_recommendations(extraction,lang,texts)
    rates=exchange_rates() if 'bank_statement' in uploaded_files else None
    budget=assess_budget(extraction,rates=rates) if 'bank_statement' in uploaded_files else None
    step(5)
    return {"extraction":extraction, "issues":issues, "biz_result":business, "score":score,
            "lang":lang, "engine":"local_python_ocr", "writing":writing,
            "quality":quality,"source_files":uploaded_files,"budget":budget,"exchange_snapshot":rates,
            "provenance":extraction.review_provenance,
            "converted_sources":conversions,
            "narrative_requested":any(submitted_files.get(key) for key in ('cover_letter','travel_plan','bank_statement','supporting')),
            "narrative_original_roles":submitted_files}
