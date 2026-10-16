"""UI-independent orchestration; extraction caching stays in the browser session."""
from extractor import extract_documents, _extract_pdf_text
from writing_review import writing_recommendations
from validator import run_validation
from business_checker import check_business_alignment
from scorer import calculate_score, _cover_letter_is_complete, _leave_is_confirmed
from supporting_review import check_supporting, extraction_quality
from evidence import attach_evidence
from context_review import context_issues
from document_sources import unique_uploads
from source_checks import printed_form_checks, translation_date_checks, reservation_and_title_checks
from finance_review import grounded_financial_data, assess_budget, exchange_rates


def review_documents(api_key, uploaded_files, model_id="auto", lang="en", progress=None, router=None):
    uploaded_files = unique_uploads(uploaded_files)
    def step(number):
        if progress:
            progress(number)
    step(1)
    extraction = extract_documents(api_key, uploaded_files, model_id=model_id, lang=lang,router=router)
    grounded_financial_data(extraction,uploaded_files)
    source_issues = (printed_form_checks(extraction, uploaded_files) + translation_date_checks(uploaded_files)
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
    contextual = context_issues(extraction)
    # Prefer the context finding's exact source quotes for the same deterministic rule.
    for finding in contextual:
        duplicates = [issue for issue in issues if issue.field_name == finding.field_name and
                      issue.document_name == finding.document_name]
        if duplicates:
            # Keep the deterministic/layout finding and enrich it with verified context.
            for issue in duplicates:
                issue.evidence += [loc for loc in finding.evidence if loc not in issue.evidence]
                issue.reference_evidence += finding.reference_evidence
        else:
            issues.append(finding)
    attach_evidence(issues,extraction,uploaded_files)
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
            "lang":lang, "model_used":extraction.model_used or model_id, "writing":writing,
            "quality":quality,"source_files":uploaded_files,"budget":budget,"exchange_snapshot":rates}
