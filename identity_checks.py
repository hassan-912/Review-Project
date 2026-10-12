"""Exact identity comparisons. Missing/ambiguous evidence can never be a clean match."""
import re
from validator import ValidationIssue, Severity, _names_match, _parse_date


def strict_identity_checks(data, existing=()):
    issues = []
    labels = {"visa_form":"Visa Application Form", "hotel":"Hotel Reservation", "flight":"Flight Reservation",
              "insurance":"Travel Insurance", "cover_letter":"Cover Letter", "travel_plan":"Travel Itinerary",
              "national_id":"National ID", "passport":"Passport", "supporting":"Supporting Documents", "employment":"Employment Documents"}
    refs = {"full_name":data.passport.full_name, "given_names":data.passport.given_names,
            "surname":data.passport.surname, "passport_number":data.passport.passport_number,
            "passport_issue":data.passport.passport_issue, "passport_expiry":data.passport.passport_expiry,
            "national_id_number":data.national_id.id_number, "national_id_issue":data.national_id.issue_date,
            "national_id_expiry":data.national_id.expiry_date}
    seen = set()

    def flag(doc, field, found, expected, reason="mismatch"):
        key = (doc, field, found, expected, reason)
        if key in seen:
            return
        seen.add(key)
        fix = ("Verify the original document and reissue/correct the application or reservation. "
               "Copy the identity field exactly; do not guess unreadable characters or change an official identity document.")
        if reason != "mismatch":
            fix = "Manual verification required: obtain a clear original or official transcription before submission. This field is unresolved."
        issues.append(ValidationIssue(document_name=doc,field_name=field,found_value=found,
            expected_value=str(expected or "Readable authoritative identity evidence"),severity=Severity.CRITICAL,
            recommended_fix=fix,message_key="identity."+reason))

    def check(doc, field, found):
        if not found:
            return  # Optional fields not printed on a booking must not be invented.
        ref = refs[field]
        if not ref:
            flag(doc,field,found,None,"reference")
        elif field in ("full_name", "given_names", "surname"):
            # Different scripts cannot be resolved by speculative transliteration.
            if bool(re.search(r"[\u0600-\u06ff]",found)) != bool(re.search(r"[\u0600-\u06ff]",ref)):
                flag(doc,field,found,ref,"unreadable")
            elif not _names_match(ref,found):
                flag(doc,field,found,ref)
        elif field.endswith(("issue", "expiry")):
            a,b = _parse_date(ref),_parse_date(found)
            if not a or not b:
                flag(doc,field,found,ref,"unreadable")
            elif a != b:
                flag(doc,field,found,ref)
        elif re.sub(r"\s+","",found).upper() != re.sub(r"\s+","",ref).upper():
            flag(doc,field,found,ref)

    # Preserve legacy summary checks, and add newly supported fields even if evidence rows
    # are omitted. The page-level rows below catch conflicting secondary reservations.
    for category,obj in [("visa_form",data.visa_form),("flight",data.flight)]+[("hotel",h) for h in data.hotel]:
        doc = labels[category]
        for field in ("passport_issue","passport_expiry","national_id_number","national_id_issue","national_id_expiry","given_names","surname"):
            check(doc,field,getattr(obj,field,None))
        if category != "visa_form":
            check(doc,"passport_number",obj.passport_number)
    if data.national_id.present:
        check("National ID","full_name",data.national_id.full_name)
        if not data.national_id.id_number:
            flag("National ID","national_id_number",None,None,"unreadable")
    for row in data.identity_evidence:
        doc = labels[row.document]+f" ({row.source_file}"+(f", p. {row.page}" if row.page else "")+")"
        for field in row.unreadable_fields:
            flag(doc,field,None,refs.get(field),"unreadable")
        for field in refs:
            check(doc,field,getattr(row,field,None))
        if row.document in ("visa_form","hotel","flight") and not row.full_name and not (row.given_names and row.surname):
            flag(doc,"full_name",None,refs["full_name"],"unreadable")
    # Missing authoritative mandatory fields are critical when document detection confirms
    # the document exists. No national-ID expiry requirement if it isn't printed.
    if "passport" in data.detected_documents:
        for field in ("full_name","passport_issue","passport_expiry"):
            if not refs[field]:
                flag("Passport",field,None,None,"unreadable")
    if "visa_form" in data.detected_documents:
        for field,value in (("full_name",data.visa_form.applicant_name),("passport_number",data.visa_form.passport_number),
                            ("passport_issue",data.visa_form.passport_issue),("passport_expiry",data.visa_form.passport_expiry)):
            if not value:
                flag("Visa Application Form",field,None,refs[field],"unreadable")
    if "flight" in data.detected_documents and not data.flight.passenger_name:
        flag("Flight Reservation","full_name",None,refs["full_name"],"unreadable")
    if "hotel" in data.detected_documents:
        for index,hotel in enumerate(data.hotel or [None],1):
            if hotel is None or not hotel.guest_name:
                flag(f"Hotel Reservation ({index})","full_name",None,refs["full_name"],"unreadable")
    for field,ref in refs.items():
        if ref and field.endswith(("issue","expiry")) and not _parse_date(ref):
            flag("National ID" if field.startswith("national_id") else "Passport",field,ref,None,"unreadable")
    for doc,obj,start,end in [("Passport",data.passport,"passport_issue","passport_expiry"),
                             ("National ID",data.national_id,"issue_date","expiry_date")]:
        a,b = _parse_date(getattr(obj,start)),_parse_date(getattr(obj,end))
        if a and b and a >= b:
            flag(doc,"identity_date_order",f"{a} / {b}","Issue date before expiry date")
    return issues
