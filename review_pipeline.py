"""UI-independent orchestration; extraction caching stays in the browser session."""
from extractor import extract_documents, _extract_pdf_text
from writing_review import writing_recommendations
from validator import run_validation
from business_checker import check_business_alignment
from scorer import calculate_score, _cover_letter_is_complete, _leave_is_confirmed
from supporting_review import check_supporting, extraction_quality
from evidence import attach_evidence


def review_documents(api_key, uploaded_files, model_id="auto", lang="en", progress=None, router=None):
    def step(number):
        if progress:
            progress(number)
    step(1)
    extraction = extract_documents(api_key, uploaded_files, model_id=model_id, lang=lang,router=router)
    step(2)
    issues = run_validation(extraction)
    step(3)
    business = check_business_alignment(extraction)
    issues += business.issues
    issues += check_supporting(extraction,uploaded_files)
    quality,quality_issues=extraction_quality(extraction,uploaded_files)
    issues += quality_issues
    attach_evidence(issues,extraction,uploaded_files)
    step(4)
    score = calculate_score(issues, _cover_letter_is_complete(extraction), _leave_is_confirmed(extraction))
    order = {"CRITICAL":0,"HIGH":1,"MEDIUM":2,"LOW":3}
    issues.sort(key=lambda x: order[x.severity.value])
    texts = {name:text for group in uploaded_files.values() for name,raw in group
             if (text := _extract_pdf_text(name,raw)) is not None}
    writing = writing_recommendations(extraction,lang,texts)
    step(5)
    return {"extraction":extraction, "issues":issues, "biz_result":business, "score":score,
            "lang":lang, "model_used":extraction.model_used or model_id, "writing":writing,
            "quality":quality,"source_files":uploaded_files}
