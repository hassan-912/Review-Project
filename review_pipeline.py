"""UI-independent orchestration; extraction caching stays in the browser session."""
from extractor import extract_documents
from validator import run_validation
from business_checker import check_business_alignment
from scorer import calculate_score, _cover_letter_is_complete, _leave_is_confirmed


def review_documents(api_key, uploaded_files, model_id, lang="en", progress=None):
    def step(number):
        if progress:
            progress(number)
    step(1)
    extraction = extract_documents(api_key, uploaded_files, model_id=model_id, lang=lang)
    step(2)
    issues = run_validation(extraction)
    step(3)
    business = check_business_alignment(extraction)
    issues += business.issues
    step(4)
    score = calculate_score(issues, _cover_letter_is_complete(extraction), _leave_is_confirmed(extraction))
    order = {"CRITICAL":0,"HIGH":1,"MEDIUM":2,"LOW":3}
    issues.sort(key=lambda x: order[x.severity.value])
    step(5)
    return {"extraction":extraction, "issues":issues, "biz_result":business, "score":score,
            "lang":lang, "model_used":extraction.model_used or model_id}
