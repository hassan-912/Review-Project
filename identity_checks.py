"""Exact identity comparisons. Missing/ambiguous evidence can never be a clean match."""
import re
import unicodedata
from validator import ValidationIssue, Severity, _names_match, _parse_date, name_issue, _name_parts


def strict_identity_checks(data, existing=()):
    issues = []
    labels = {"visa_form":"Visa Application Form", "hotel":"Hotel Reservation", "flight":"Flight Reservation",
              "insurance":"Travel Insurance", "cover_letter":"Cover Letter", "travel_plan":"Travel Itinerary",
              "national_id":"National ID", "passport":"Passport", "supporting":"Supporting Documents", "employment":"Employment Documents"}
    refs = {"full_name":data.passport.full_name, "given_names":data.passport.given_names,
            "surname":data.passport.surname, "passport_number":data.passport.passport_number,"date_of_birth":data.passport.date_of_birth,
            "passport_issue":data.passport.passport_issue, "passport_expiry":data.passport.passport_expiry,
            "national_id_number":data.national_id.id_number, "national_id_issue":data.national_id.issue_date,
            "national_id_expiry":data.national_id.expiry_date}
    seen = set()

    def flag(doc, field, found, expected, reason="mismatch", scored=True):
        key = (doc, field, found, expected, reason)
        if key in seen:
            return
        seen.add(key)
        fix = ("Verify the original document and reissue/correct the application or reservation. "
               "Copy the identity field exactly; do not guess unreadable characters or change an official identity document.")
        if reason != "mismatch":
            fix = "Manual verification required: obtain a clear original or official transcription before submission. This field is unresolved."
        issues.append(ValidationIssue(document_name=doc,field_name=field,found_value=found,
            expected_value=str(expected or "Readable authoritative identity evidence"),severity=Severity.CRITICAL if scored else Severity.HIGH,
            recommended_fix=fix,message_key="identity."+reason,affects_score=scored))

    def native_name(value):
        value = re.sub(r'[\u064b-\u065f\u0670\u0640]', '', value or '')
        return value.translate(str.maketrans({'أ':'ا', 'إ':'ا', 'آ':'ا', 'ى':'ي'}))

    def date_parts(value):
        if parsed := _parse_date(value):
            return parsed.year, parsed.month, parsed.day
        if re.fullmatch(r'\d{4}-\d{2}', value or ''):
            year, month = map(int, value.split('-'))
            if 1 <= month <= 12:
                return year, month
        return None

    def check(doc, field, found):
        if not found:
            return  # Optional fields not printed on a booking must not be invented.
        ref = refs[field]
        if not ref:
            flag(doc,field,found,None,"reference")
        elif field in ("full_name", "given_names", "surname"):
            # Different scripts cannot be resolved by speculative transliteration.
            if bool(re.search(r"[\u0600-\u06ff]",found)) != bool(re.search(r"[\u0600-\u06ff]",ref)):
                native = data.passport.native_name
                if field == 'full_name' and native and re.search(r'[\u0600-\u06ff]', found):
                    from extractor import PassportInfo
                    issue = name_issue(PassportInfo(full_name=native_name(native)), native_name(found), doc)
                    if issue:
                        issue.field_name = field
                        issues.append(issue)
                else:
                    # Different writing systems are not a spelling error. No speculative
                    # transliteration and no identity deduction for a missing script bridge.
                    flag(doc,field,found,ref,"unreadable",scored=False)
            elif field=="full_name":
                issue=name_issue(data.passport,found,doc)
                if issue:
                    issue.field_name="full_name"
                    issues.append(issue)
            elif field=="given_names" and _name_parts(found)==_name_parts(ref)[:1]:
                pass
            elif not _names_match(ref,found,allow_short=False):
                flag(doc,field,found,ref)
        elif field.endswith(("issue", "expiry")) or field=="date_of_birth":
            a,b = date_parts(ref),date_parts(found)
            if not a or not b:
                flag(doc,field,found,ref,"unreadable")
            elif a[:min(len(a),len(b))] != b[:min(len(a),len(b))]:
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
        if not (data.national_id.full_name or "").strip():
            flag("National ID","full_name",None,refs["full_name"],"unreadable")
        if not data.national_id.id_number:
            flag("National ID","national_id_number",None,None,"unreadable")
        if data.passport.national_id_number and data.national_id.id_number and data.passport.national_id_number != data.national_id.id_number:
            flag('National ID','national_id_number',data.national_id.id_number,data.passport.national_id_number)
    for row in data.identity_evidence:
        if getattr(row,'subject_role','applicant') != 'applicant' or row.document == 'supporting' and getattr(row,'name_scope','full') == 'first_only':
            continue
        doc = labels[row.document]+f" ({row.source_file}"+(f", p. {row.page}" if row.page else "")+")"
        for field in row.unreadable_fields:
            flag(doc,field,None,refs.get(field),"unreadable")
        for field in refs:
            check(doc,field,getattr(row,field,None))
        if row.document in ("visa_form","hotel","flight") and not (row.full_name or "").strip() and not (row.given_names and row.surname):
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
        if ref and field.endswith(("issue","expiry")) and not date_parts(ref):
            flag("National ID" if field.startswith("national_id") else "Passport",field,ref,None,"unreadable")
    for doc,obj,start,end in [("Passport",data.passport,"passport_issue","passport_expiry"),
                             ("National ID",data.national_id,"issue_date","expiry_date")]:
        a,b = _parse_date(getattr(obj,start)),_parse_date(getattr(obj,end))
        if a and b and a >= b:
            flag(doc,"identity_date_order",f"{a} / {b}","Issue date before expiry date")
    return issues
