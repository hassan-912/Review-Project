"""Internal cross-document evidence checks, never external document authentication."""
from collections import Counter
from validator import ValidationIssue, Severity, _parse_date, name_issue
from document_sources import source_is_grounded
import re
import pymupdf


def _normal(value):
    return re.sub(r"[\s,]+","",str(value or "")).casefold()


def check_supporting(data,uploaded_files=None):
    issues=[]
    references={"full_name":data.passport.full_name,"passport_number":data.passport.passport_number,
        "date_of_birth":data.passport.date_of_birth,"employer_name":data.employment.employer_name,
        "job_title":data.employment.job_title,"passport_issue":data.passport.passport_issue,"passport_expiry":data.passport.passport_expiry,
        "national_id_number":data.national_id.id_number,"national_id_issue":data.national_id.issue_date,"national_id_expiry":data.national_id.expiry_date,
        "approved_leave_start":data.employment.approved_leave_start,"approved_leave_end":data.employment.approved_leave_end,
        "intended_arrival":data.visa_form.intended_arrival,"intended_departure":data.visa_form.intended_departure}
    files={name:raw for group in (uploaded_files or {}).values() for name,raw in group}
    counts=Counter(name for group in (uploaded_files or {}).values() for name,_ in group)
    for document in data.supporting_documents:
        label=f"Supporting Documents ({document.source_file})"
        for claim in document.claims:
            kinds = [document.document_type] + [kind for audit in data.document_audits if
                audit.source_file == document.source_file for kind in audit.document_types]
            is_id = any('nationalid' in _normal(kind).replace('_','') or 'بطاقة' in kind for kind in kinds)
            if is_id and claim.field_name == 'passport_number':
                # Correct a known extraction-type confusion, never compare the civil ID
                # printed on an ID card with the passport's separate document number.
                claim.field_name = 'national_id_number'
            grounded=True
            if uploaded_files is not None:
                grounded=counts[document.source_file]==1 and bool(claim.quote and claim.page)
                if grounded and document.source_file.lower().endswith('.pdf'):
                    with pymupdf.open(stream=files[document.source_file],filetype='pdf') as pdf:
                        grounded=1<=claim.page<=len(pdf)
                        if grounded:
                            text=pdf[claim.page-1].get_text(sort=True)
                            if len(text.strip())>=20:
                                grounded=source_is_grounded({'source_file':document.source_file,'page':claim.page,'text':claim.quote},uploaded_files)
                                # Recover a real verbatim line when the model joined table
                                # columns or used an ellipsis. The asserted literal value
                                # must occur exactly once; never fabricate a quotation.
                                if not grounded and claim.value:
                                    matches=list(re.finditer(r'(?<!\w)'+re.escape(claim.value)+r'(?!\w)',text,re.I))
                                    if len(matches)==1:
                                        start=text.rfind('\n',0,matches[0].start())+1
                                        end=text.find('\n',matches[0].end())
                                        claim.quote=text[start:end if end!=-1 else len(text)].strip()
                                        grounded=True
            if not grounded:
                needs_resolution=claim.assessment=='conflicts' or claim.field_name in {
                    'full_name','passport_number','date_of_birth','passport_issue','passport_expiry',
                    'national_id_number','national_id_issue','national_id_expiry'}
                claim.assessment="unverified"
                # Neutral descriptive metadata remains visibly unverified. It was not
                # used for a finding and must not invalidate the entire file review.
                if not needs_resolution:
                    continue
                issues.append(ValidationIssue(document_name=label,field_name=claim.field_name,found_value=claim.value,
                    expected_value="Traceable quote on the supplied source page",severity=Severity.HIGH,message_key="evidence.incomplete",
                    recommended_fix="The quoted evidence could not be located on its stated page. Verify the original before accepting this claim.", affects_score=False))
                continue
            # A parent's data and a first-name-only civil-register column are not a
            # competing applicant travel identity. Retain them for context, without
            # treating absent corroboration as a defect in the file.
            if claim.subject_role != 'applicant' or claim.field_name == 'full_name' and claim.name_scope == 'first_only':
                continue
            reference=references.get(claim.field_name)
            if claim.field_name=="full_name" and claim.value:
                issue=name_issue(data.passport,claim.value,label)
                claim.assessment="conflicts" if issue and issue.severity==Severity.CRITICAL else "unverified" if issue else "consistent"
                if issue:
                    issue.evidence=[{'source_file':document.source_file,'page':claim.page,'text':claim.quote or claim.value}]
                    issues.append(issue)
                continue
            if reference and claim.value:
                if claim.field_name=="date_of_birth" or claim.field_name.endswith(("issue","expiry","start","end","arrival","departure")):
                    a,b=_parse_date(reference),_parse_date(claim.value)
                    match=a is not None and b is not None and a==b
                else:
                    match=_normal(reference)==_normal(claim.value)
                claim.assessment="consistent" if match else "conflicts"
                if match:
                    continue
                severity=Severity.CRITICAL if claim.field_name in ("passport_number","date_of_birth","passport_issue","passport_expiry","national_id_number","national_id_issue","national_id_expiry") else Severity.HIGH
                issues.append(ValidationIssue(document_name=label,field_name=claim.field_name,found_value=claim.value,
                    expected_value=str(reference),severity=severity,message_key="support.conflict",
                    recommended_fix="Compare the quoted supporting evidence with the passport/HR original and resolve the discrepancy before submission."))
            elif claim.assessment=="conflicts" and claim.compared_with and claim.reason and (uploaded_files is None or counts[claim.compared_with]==1):
                issues.append(ValidationIssue(document_name=label,field_name=claim.field_name,found_value=claim.value,
                    expected_value=claim.compared_with,severity=Severity.HIGH,message_key="support.conflict",
                    recommended_fix=claim.reason))
            else:
                claim.assessment="unverified"
    return issues


def extraction_quality(data,uploaded_files):
    """Separate observable completeness from a fictional model-confidence percentage."""
    audits={audit.source_file:audit for audit in data.document_audits}
    names=Counter(name for group in uploaded_files.values() for name,_ in group)
    issues=[]; files=[]; total=read=0
    for category,group in uploaded_files.items():
        for name,raw in group:
            pages=1
            if name.lower().endswith('.pdf'):
                with pymupdf.open(stream=raw,filetype='pdf') as pdf: pages=len(pdf)
            audit=audits.get(name) if names[name]==1 else None
            expected={pages} if category=='bank_statement' else set(range(1,pages+1))
            reported=set(audit.pages_read)&expected if audit else set()
            total+=len(expected);read+=len(reported)
            # Legibility/coverage is separate from notes about problems in readable text.
            unresolved=names[name]!=1 or not audit or audit.readability!='readable' or reported!=expected
            files.append({"file":name,"pages":len(expected),"original_pages":pages,"scope":"final_page" if category=='bank_statement' else 'all_pages',"pages_read":len(reported),"readability":audit.readability if audit else 'unreviewed',
                          "uncertainties":audit.uncertainties if audit else ["No page audit returned"]})
            if unresolved:
                issues.append(ValidationIssue(document_name=f"Supporting Documents ({name})" if category=='supporting' else f"Document ({name})",
                    field_name="document_readability",found_value=f"{len(reported)} / {len(expected)}",expected_value="Every in-scope page read and legible",
                    severity=Severity.HIGH,message_key="evidence.incomplete",affects_score=False,
                    title_en="Source review is incomplete",
                    recommended_fix="The automated review did not account for every source page. Rerun or inspect the original before accepting this result. This is a review limitation, not a confirmed document error."))
            if category=='supporting' and not any(d.source_file==name for d in data.supporting_documents):
                issues.append(ValidationIssue(document_name=f"Supporting Documents ({name})",field_name="supporting_review",
                    found_value=None,expected_value="Document classification and evidence assessment",severity=Severity.HIGH,
                    message_key="evidence.incomplete",affects_score=False, recommended_fix="The supporting file has no traceable assessment. Verify its content before relying on it."))
    for limitation in data.review_limitations:
        issues.append(ValidationIssue(document_name='Review limitations',field_name='review_coverage',found_value=None,
            expected_value='A complete source-grounded review',severity=Severity.HIGH,affects_score=False,
            title_en='Review could not be completed',recommended_fix=limitation))
    required=[data.passport.full_name,data.passport.passport_number,data.passport.date_of_birth,data.passport.passport_issue,data.passport.passport_expiry,
              data.visa_form.applicant_name,data.visa_form.passport_number,data.visa_form.intended_arrival,data.visa_form.intended_departure,
              data.flight.passenger_name,data.flight.departure_date,data.flight.return_date,data.insurance.insured_name,
              data.insurance.insured_passport_number,data.insurance.valid_from,data.insurance.valid_until,
              data.insurance.coverage_amount_eur is not None,data.cover_letter.purpose_of_visit,data.cover_letter.funding_source,
              data.cover_letter.ties_to_home_country,data.cover_letter.attached_documents_listed,data.travel_plan.present]
    for h in data.hotel: required.extend([h.guest_name,h.check_in_date,h.check_out_date,h.hotel_name,h.city])
    known=sum(bool(v) for v in required)
    return {"fields_present":known,"fields_required":len(required),"completeness":round(100*known/len(required)),
            "pages_reported_read":read,"pages_total":total,"files":files,
            "accuracy":"Not independently measured; verify source evidence"},issues
