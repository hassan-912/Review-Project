"""
validator.py
============
Deterministic rule-based validation engine for Schengen visa documents.

All checks are purely logic-based (no LLM involved) and operate on the
VisaDocumentExtraction Pydantic model returned by extractor.py.

Changes in this version
-----------------------
* New rule: Approved leave dates must bracket the flight travel period.
* New rule: Job title / employer name cross-checked against cover letter
  and Commercial Registry / Tax Card.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from calendar import monthrange
from enum import Enum
from typing import Optional
from collections import Counter
import re
import unicodedata

from pydantic import BaseModel, model_validator, Field

from extractor import VisaDocumentExtraction


# ---------------------------------------------------------------------------
# Severity Levels
# ---------------------------------------------------------------------------

class Severity(str, Enum):
    CRITICAL = "CRITICAL"   # Unresolved blocking correction
    HIGH     = "HIGH"       # Strong negative signal
    MEDIUM   = "MEDIUM"     # Notable concern
    LOW      = "LOW"        # Minor issue / advisory


# ---------------------------------------------------------------------------
# Validation Error Model
# ---------------------------------------------------------------------------

class ValidationIssue(BaseModel):
    """Represents a single detected inconsistency or rule violation."""
    document_name: str
    field_name: str
    found_value: Optional[str]
    expected_value: str
    severity: Severity
    recommended_fix: str
    message_key: str = ""
    title_en: str = ""
    title_ar: str = ""
    fix_ar: str = ""
    evidence: list[dict] = Field(default_factory=list)
    reference_evidence: list[dict] = Field(default_factory=list)
    affects_score: bool = True

    @model_validator(mode="after")
    def localized_messages(self):
        from i18n import issue_translation, field_label
        self.message_key = self.message_key or "field." + self.field_name
        self.title_en = self.title_en or field_label(self.field_name, "en")
        title_ar, fix_ar = issue_translation(self.message_key, self.field_name)
        self.title_ar = self.title_ar or title_ar
        self.fix_ar = self.fix_ar or fix_ar
        return self


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d %b %Y", "%B %d, %Y"]


def _parse_date(value: Optional[str]) -> Optional[date]:
    """
    Attempt to parse a date string using multiple common formats.
    Returns None if value is None or unparseable.
    """
    if not value:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _fmt(value: Optional[str]) -> str:
    """Format an optional string for display in issues table."""
    return str(value) if value else "—"


def _tokens(text: Optional[str]) -> set[str]:
    """Lower-case token set for fuzzy keyword matching."""
    if not text:
        return set()
    return set(text.lower().replace(",", " ").replace("-", " ").split())


# ---------------------------------------------------------------------------
# Individual Rule Checks
# ---------------------------------------------------------------------------

def _name_parts(value):
    value = unicodedata.normalize("NFC", value or "").upper()
    return re.sub(r"[<,\-/]+", " ", value).split()


def _names_match(name_a: Optional[str], name_b: Optional[str], given_names=None, surname=None, allow_short=True) -> bool:
    """Only full passport name or first given name plus full surname; exact spelling."""
    if not name_a or not name_b:
        return False
    reference,found=_name_parts(name_a),_name_parts(name_b)
    if not reference or not found:
        return False
    if Counter(reference)==Counter(found):
        return True
    if not allow_short or len(reference)<2:
        return False
    if given_names and surname:
        short=_name_parts(given_names)[:1]+_name_parts(surname)
    elif "<<" in name_a:
        family,given=name_a.split("<<",1)
        short=_name_parts(given)[:1]+_name_parts(family)
    else:
        short=[reference[0],reference[-1]]
    return len(short)>=2 and Counter(found)==Counter(short)


def name_issue(passport, found, document):
    """Known partial-name formats get a note; wrong spellings and blanks are critical."""
    reference=passport.full_name
    if found and reference and bool(re.search(r'[\u0600-\u06ff]',found)) != bool(re.search(r'[\u0600-\u06ff]',reference)):
        native = getattr(passport,'native_name',None)
        if native and re.search(r'[\u0600-\u06ff]', found):
            def normalize_native(text):
                text = re.sub(r'[\u064b-\u065f\u0670\u0640]','',text)
                return text.translate(str.maketrans({'أ':'ا','إ':'ا','آ':'ا','ى':'ي'}))
            return name_issue(passport.model_copy(update={'full_name':normalize_native(native), 'given_names':None, 'surname':None}), normalize_native(found), document)
        return ValidationIssue(document_name=document,field_name='applicant_name',found_value=found,
            expected_value=reference,severity=Severity.HIGH,affects_score=False,message_key='identity.unreadable',
            recommended_fix='Compare the native-script passport name and independently printed ID number. Different scripts alone do not establish a spelling mismatch.')
    if reference and found and _names_match(reference,found,passport.given_names,passport.surname):
        return None
    partial=bool(_name_parts(reference) and _name_parts(found) and not (Counter(_name_parts(found))-Counter(_name_parts(reference))))
    return ValidationIssue(document_name=document,field_name="applicant_name",found_value=found,
        expected_value=reference or "Readable passport name",severity=Severity.LOW if partial else Severity.CRITICAL,
        message_key="identity.name_format" if partial else "identity.unreadable" if not found or not reference else "identity.mismatch",
        recommended_fix="Use either the full passport name or the first given name and full surname, with exact passport spelling. Blank names are not accepted.")


def accommodation_window(data):
    starts = [_parse_date(h.check_in_date) for h in data.hotel]
    ends = [_parse_date(h.check_out_date) for h in data.hotel]
    return (min((d for d in starts if d), default=None),
            max((d for d in ends if d), default=None))


def country_key(value):
    """Normalize language/code aliases, never turn a genuinely different country into a match."""
    value=re.sub(r'\s+',' ',str(value or '').strip().casefold())
    aliases={
        'germany':('de','deu','deutschland'), 'greece':('gr','grc','griechenland'),
        'france':('fr','fra','frankreich'), 'italy':('it','ita','italien'),
        'spain':('es','esp','spanien'), 'netherlands':('nl','nld','niederlande','the netherlands'),
        'belgium':('be','bel','belgien'), 'austria':('at','aut','österreich'),
        'switzerland':('ch','che','schweiz'), 'sweden':('se','swe','schweden'),
        'denmark':('dk','dnk','dänemark'), 'norway':('no','nor','norwegen'),
        'iceland':('is','isl','island'), 'czech republic':('cz','cze','czechia','tschechien'),
        'hungary':('hu','hun','ungarn'), 'poland':('pl','pol','polen'),
        'portugal':('pt','prt'), 'finland':('fi','fin','finnland'),
        'estonia':('ee','est','estland'), 'latvia':('lv','lva','lettland'),
        'lithuania':('lt','ltu','litauen'), 'luxembourg':('lu','lux','luxemburg'),
        'malta':('mt','mlt'), 'slovenia':('si','svn','slowenien'),
        'slovakia':('sk','svk','slowakei'), 'croatia':('hr','hrv','kroatien'),
        'romania':('ro','rou','rumänien'), 'bulgaria':('bg','bgr','bulgarien'),
        'liechtenstein':('li','lie')}
    return next((country for country,words in aliases.items() if value==country or value in words),value)


def _check_passport_number_crosscheck(data: VisaDocumentExtraction) -> list[ValidationIssue]:
    """
    Rule 1 — Passport Number Cross-Check (CRITICAL).
    """
    issues: list[ValidationIssue] = []
    reference_num = data.passport.passport_number

    if not reference_num:
        issues.append(ValidationIssue(message_key='validation.01',
            document_name="Passport",
            field_name="passport_number",
            found_value=None,
            expected_value="A valid passport number (from MRZ)",
            severity=Severity.CRITICAL,
            recommended_fix=(
                "Passport number could not be extracted from the passport image/MRZ. "
                "Ensure the passport scan is clear, unobstructed, and the full MRZ zone is visible."
            ),
        ))
        return issues

    cross_check: dict[str, Optional[str]] = {
        "Visa Application Form": getattr(data.visa_form, "passport_number", None),
        "Travel Insurance (Insured Passport No.)": getattr(data.insurance, "insured_passport_number", None),
    }

    for doc_name, found in cross_check.items():
        if not found:
            continue
        if found.strip().upper() != reference_num.strip().upper():
            issues.append(ValidationIssue(message_key='validation.02',
                document_name=doc_name,
                field_name="passport_number",
                found_value=found,
                expected_value=reference_num,
                severity=Severity.CRITICAL,
                recommended_fix=(
                    f"CRITICAL: Passport Number Mismatch! "
                    f"Passport image shows '{reference_num}', "
                    f"but {doc_name} shows '{found}'. "
                    "Recheck all documents and ensure the correct passport is used throughout."
                ),
            ))
    return issues


def _check_identity_name_crosscheck(data: VisaDocumentExtraction) -> list[ValidationIssue]:
    candidates=[]
    if data.visa_form.applicant_name or data.visa_form.passport_number or "visa_form" in data.detected_documents:
        candidates.append(("Visa Application Form",data.visa_form.applicant_name))
    if data.flight.passenger_name or data.flight.departure_date or "flight" in data.detected_documents:
        candidates.append(("Flight Reservation",data.flight.passenger_name))
    if data.insurance.insured_name or data.insurance.valid_from or data.insurance.coverage_amount_eur is not None:
        candidates.append(("Travel Insurance",data.insurance.insured_name))
    candidates.extend((f"Hotel Reservation ({idx+1})",h.guest_name) for idx,h in enumerate(data.hotel))
    return [issue for document,name in candidates if (issue:=name_issue(data.passport,name,document))]


def _check_dob_crosscheck(data: VisaDocumentExtraction) -> list[ValidationIssue]:
    """
    Rule 3 — Date of Birth Cross-Check (HIGH).

    The DOB on the passport must match the DOB declared on the Visa Application Form.
    A mismatch is a strong signal of data entry error or document fraud.
    """
    issues: list[ValidationIssue] = []
    passport_dob = data.passport.date_of_birth
    form_dob     = getattr(data.visa_form, "date_of_birth", None)

    if not passport_dob or not form_dob:
        return issues  # Cannot compare

    if passport_dob.strip() != form_dob.strip():
        issues.append(ValidationIssue(message_key='validation.05',
            document_name="Visa Application Form",
            field_name="date_of_birth",
            found_value=form_dob,
            expected_value=passport_dob,
            severity=Severity.HIGH,
            recommended_fix=(
                f"Date of birth mismatch: Passport shows '{passport_dob}', "
                f"but Visa Application Form shows '{form_dob}'. "
                "Correct the application form to match the passport exactly."
            ),
        ))
    return issues


def application_window(data):
    """The application is authoritative; flight fallback is explicitly incomplete evidence."""
    return (_parse_date(data.visa_form.intended_arrival) or _parse_date(data.flight.departure_date),
            _parse_date(data.visa_form.intended_departure) or _parse_date(data.flight.return_date))


def _check_date_alignment(data: VisaDocumentExtraction) -> list[ValidationIssue]:
    issues=[]
    start,end=application_window(data)
    def flag(doc,field,found,expected,fix,critical=False):
        issues.append(ValidationIssue(document_name=doc,field_name=field,found_value=found,
            expected_value=expected,severity=Severity.CRITICAL if critical else Severity.HIGH,
            recommended_fix=fix,message_key="dates.exact" if not critical else "dates.boundary"))
    if start and end and start>=end:
        flag("Visa Application Form","travel_date_order",f"{start} / {end}","Arrival before departure",
             "Verify the application travel dates before aligning other documents.",True)
        return issues
    for field,value in (("intended_arrival",data.visa_form.intended_arrival),("intended_departure",data.visa_form.intended_departure)):
        if not _parse_date(value):
            flag("Visa Application Form",field,value,"A readable application travel date",
                 "Read the original application and supply the exact travel dates.")
    records=[("Flight Reservation",data.flight.departure_date,data.flight.return_date),
             ("Cover Letter",data.cover_letter_text.start_date,data.cover_letter_text.end_date),
             ("Travel Itinerary",data.travel_plan.start_date,data.travel_plan.end_date)]
    for doc,raw_start,raw_end in records:
        a,b=_parse_date(raw_start),_parse_date(raw_end)
        for field,raw,actual,expected in (("departure_date",raw_start,a,start),("return_date",raw_end,b,end)):
            if raw and not actual or actual and expected and actual!=expected:
                flag(doc,field,raw,str(expected),"Match the application travel dates exactly; no three-day tolerance.")
        if a and b and a>=b:
            flag(doc,"departure_date / return_date",f"{a} / {b}","Departure before return",
                 "Correct reversed or identical travel dates.",True)
    if start and end:
        a,b=accommodation_window(data)
        if a and a!=start:
            flag("Hotel Reservation","check_in_date",str(a),str(start),"First check-in must match application arrival.")
        if b and b!=end:
            flag("Hotel Reservation","check_out_date",str(b),str(end),"Last check-out must match application departure.")
        cursor=start
        intervals=[]
        for hotel in data.hotel:
            a,b=_parse_date(hotel.check_in_date),_parse_date(hotel.check_out_date)
            if a and b and a>=b:
                flag("Hotel Reservation","hotel_date_order",f"{a} / {b}","Check-in before check-out","Correct the booking dates.")
            elif a and b:
                intervals.append((a,b))
            if a and a<start or b and b>end:
                flag("Hotel Reservation","hotel_outside_trip",f"{a} / {b}",f"{start} / {end}",
                     "Keep all accommodation dates inside the application's travel window.")
        for a,b in sorted(intervals):
            if a>cursor:
                break
            cursor=max(cursor,b)
        if cursor<end:
            flag("Hotel Reservation","hotel_coverage_gap",str(cursor),str(end),
                 "Provide bookings covering every night of the application's travel dates.")
        ins_start,ins_end=_parse_date(data.insurance.valid_from),_parse_date(data.insurance.valid_until)
        if ins_start and ins_start>start:
            flag("Travel Insurance","valid_from vs departure_date",str(ins_start),str(start),
                 "Insurance must cover the application travel window from its first day.",True)
        if ins_end and ins_end<end:
            flag("Travel Insurance","valid_until vs return_date",str(ins_end),str(end),
                 "Extend insurance through the application's final travel day.",True)
        plan=data.travel_plan
        if plan.present:
            days={_parse_date(day.date) for day in plan.days}
            days.discard(None)
            expected_days=(end-start).days+1
            inside={day for day in days if start<=day<=end}
            if len(inside)!=expected_days or len(days)!=len(inside):
                flag("Travel Itinerary","travel_plan_coverage",f"{len(inside)} / {expected_days}",f"{start} / {end}",
                     "Include a dated plan for every application travel day, including arrival and departure. Remove days outside the application window.")
    return issues


def _check_insurance_coverage(data: VisaDocumentExtraction) -> list[ValidationIssue]:
    """
    Rule: Schengen regulations mandate minimum €30,000 medical insurance coverage.
    """
    issues: list[ValidationIssue] = []
    min_coverage = 30_000.0

    if data.insurance.coverage_amount_eur is None:
        issues.append(ValidationIssue(message_key='validation.07',
            document_name="Travel Insurance Policy",
            field_name="coverage_amount_eur",
            found_value=None,
            expected_value="≥ €30,000",
            severity=Severity.CRITICAL,
            recommended_fix=(
                "Insurance coverage amount could not be determined. "
                "Ensure the policy clearly states the medical coverage amount in EUR. "
                "Schengen regulations require a minimum of €30,000."
            ),
        ))
    elif data.insurance.coverage_amount_eur < min_coverage:
        issues.append(ValidationIssue(message_key='validation.08',
            document_name="Travel Insurance Policy",
            field_name="coverage_amount_eur",
            found_value=f"€{data.insurance.coverage_amount_eur:,.0f}",
            expected_value="≥ €30,000",
            severity=Severity.CRITICAL,
            recommended_fix=(
                f"Detected coverage of €{data.insurance.coverage_amount_eur:,.0f} is below "
                "the mandatory Schengen minimum of €30,000. "
                "Purchase a policy with adequate coverage before applying."
            ),
        ))
    return issues


def _check_schengen_destination_rule(data: VisaDocumentExtraction) -> list[ValidationIssue]:
    """
    Rule: Visa must be applied at the consulate of the country with the most
    overnight stays. Flag if main destination is ambiguous or not declared.
    """
    issues: list[ValidationIssue] = []

    if not data.main_schengen_destination:
        issues.append(ValidationIssue(message_key='validation.09',
            document_name="Travel Plan / Itinerary",
            field_name="main_schengen_destination",
            found_value=None,
            expected_value="A clearly identified main Schengen country",
            severity=Severity.MEDIUM,
            recommended_fix=(
                "Main Schengen destination country could not be identified. "
                "The itinerary should clearly show which Schengen country gets the most overnight stays. "
                "Specify a night-by-night breakdown in the travel plan."
            ),
        ))

    if data.total_nights_per_country and data.main_schengen_destination:
        nights = data.total_nights_per_country
        if nights:
            winners = [country for country, count in nights.items() if count == max(nights.values())]
            # Equal nights do not establish one winning country by dictionary order.
            actual_main = winners[0] if len(winners) == 1 else None
            declared = data.main_schengen_destination.strip().lower()
            if actual_main and country_key(actual_main) != country_key(declared):
                issues.append(ValidationIssue(message_key='validation.10',
                    document_name="Travel Plan / Itinerary",
                    field_name="main_schengen_destination",
                    found_value=data.main_schengen_destination,
                    expected_value=actual_main,
                    severity=Severity.HIGH,
                    recommended_fix=(
                        f"Declared main destination is '{data.main_schengen_destination}', "
                        f"but itinerary shows more nights in '{actual_main}'. "
                        "Apply at the consulate of the country with the most overnight stays."
                    ),
                ))

    winners = []
    if data.total_nights_per_country:
        largest = max(data.total_nights_per_country.values())
        winners = [country for country, count in data.total_nights_per_country.items() if count == largest]
    actual = winners[0] if len(winners) == 1 else data.main_schengen_destination if not winners else None
    declared = data.visa_form.destination_country
    if actual and declared and country_key(actual) != country_key(declared):
        issues.append(ValidationIssue(document_name='Visa Application Form', field_name='destination_country',
            found_value=declared, expected_value=actual, severity=Severity.HIGH,
            message_key='context.destination_country', title_en='Main destination conflicts with the trip',
            recommended_fix=f"Correct the application's main destination to {actual}, consistent with the actual itinerary and accommodation. First entry is a separate field."))
    return issues


def _check_passport_expiry(data: VisaDocumentExtraction) -> list[ValidationIssue]:
    """
    Rule: Passport must be valid for at least 3 months beyond the return date.
    """
    issues: list[ValidationIssue] = []

    expiry = _parse_date(data.passport.passport_expiry)
    flight_ret = _parse_date(data.flight.return_date)

    if not expiry:
        issues.append(ValidationIssue(message_key='validation.11',
            document_name="Passport",
            field_name="passport_expiry",
            found_value=None,
            expected_value="Valid expiry date at least 3 months after return",
            severity=Severity.CRITICAL,
            recommended_fix=(
                "Passport expiry date could not be extracted. "
                "Ensure the passport scan is complete and legible."
            ),
        ))
        return issues

    today = date.today()
    if expiry < today:
        issues.append(ValidationIssue(message_key='validation.12',
            document_name="Passport",
            field_name="passport_expiry",
            found_value=str(expiry),
            expected_value="Future date",
            severity=Severity.CRITICAL,
            recommended_fix=(
                "Passport has already expired. A valid passport is mandatory. "
                "Renew the passport before submitting the visa application."
            ),
        ))

    if flight_ret:
        months_3_after_return = date(
            flight_ret.year + (1 if flight_ret.month + 3 > 12 else 0),
            ((flight_ret.month + 3 - 1) % 12) + 1,
            min(flight_ret.day, monthrange(
                flight_ret.year + (1 if flight_ret.month + 3 > 12 else 0),
                ((flight_ret.month + 3 - 1) % 12) + 1)[1]),
        )
        if expiry < months_3_after_return:
            issues.append(ValidationIssue(message_key='validation.13',
                document_name="Passport",
                field_name="passport_expiry",
                found_value=str(expiry),
                expected_value=f"At least {months_3_after_return} (3 months after return)",
                severity=Severity.HIGH,
                recommended_fix=(
                    "Passport expires within 3 months of the return date. "
                    "Schengen consulates typically require the passport to be valid for "
                    "at least 3 months beyond the intended stay. Renew the passport."
                ),
            ))

    return issues


def employment_applies(data):
    emp = data.employment
    if emp.evidence_type == 'employment':
        return True
    if emp.evidence_type in ('education', 'none'):
        return False
    # Legacy/draft extraction may place a university in employer_name. An occupation
    # of student without any actual employment particulars is not employment evidence.
    student = bool(re.search(r'\bstudent\b|trainee|طالب|طالبة', data.visa_form.occupation or emp.job_title or '', re.I))
    return not (student and not emp.monthly_salary and not emp.contract_type and not emp.approved_leave_start and not emp.approved_leave_end)


def _check_employment_leave_dates(data: VisaDocumentExtraction) -> list[ValidationIssue]:
    issues=[]
    emp=data.employment
    if not employment_applies(data):
        return issues
    if not emp.employer_name and not emp.approved_leave_start and not emp.approved_leave_end:
        return issues
    a,b=_parse_date(emp.approved_leave_start),_parse_date(emp.approved_leave_end)
    def flag(doc,field,found,expected,fix,critical=False):
        issues.append(ValidationIssue(document_name=doc,field_name=field,found_value=found,
            expected_value=expected,severity=Severity.CRITICAL if critical else Severity.HIGH,
            recommended_fix=fix,message_key="hr.window"))
    if emp.leave_approval_confirmed is not True:
        flag("Employment Documents","leave_approval_confirmed",None,"Explicit HR leave approval",
             "Obtain clear signed/stamped leave approval; missing approval is unresolved.")
    if not a or not b or a>b:
        flag("Employment Documents","approved_leave_dates",f"{emp.approved_leave_start} / {emp.approved_leave_end}",
             "Readable, ordered approved leave dates","Verify the original HR letter.",True)
        return issues
    first,last=accommodation_window(data)
    records=[("Visa Application Form",_parse_date(data.visa_form.intended_arrival),_parse_date(data.visa_form.intended_departure)),
             ("Flight Reservation",_parse_date(data.flight.departure_date),_parse_date(data.flight.return_date)),
             ("Hotel Reservation",first,last)]
    for doc,start,end in records:
        if start and not a<=start<=min(a+timedelta(days=1),b):
            flag(doc,"approved_leave_start vs flight departure",str(start),f"{a} / {min(a+timedelta(days=1),b)}",
                 "Travel must start on the HR leave start date or the following day, never before leave begins.",start<a or start>b)
        if end and not max(a,b-timedelta(days=1))<=end<=b:
            flag(doc,"approved_leave_end vs flight return",str(end),f"{max(a,b-timedelta(days=1))} / {b}",
                 "Travel must end on the HR leave end date or the previous day, never after leave ends.",end>b or end<a)
    for index,hotel in enumerate(data.hotel,1):
        start,end=_parse_date(hotel.check_in_date),_parse_date(hotel.check_out_date)
        if start and start<a or end and end>b:
            flag(f"Hotel Reservation ({index})","hotel_outside_leave",f"{start} / {end}",f"{a} / {b}",
                 "Every hotel booking must stay inside the approved HR leave period.",True)
    return issues


def _check_employment_consistency(data: VisaDocumentExtraction) -> list[ValidationIssue]:
    """
    Rule: Employer name and job title in employment documents should be
    consistent with what is stated in the cover letter and business registry.
    """
    issues: list[ValidationIssue] = []
    emp = data.employment
    if not employment_applies(data):
        return issues

    # Skip if no employment data uploaded
    if not emp.employer_name and not emp.job_title:
        return issues

    # --- Cross-check employer name against cover letter ---
    if emp.employer_name and data.cover_letter.employer_mentioned is False:
        issues.append(ValidationIssue(message_key='validation.17',
            document_name="Cover Letter / Employment Documents",
            field_name="employer_name in cover letter",
            found_value="Employer not mentioned in cover letter",
            expected_value=f"Employer '{emp.employer_name}' referenced in cover letter",
            severity=Severity.MEDIUM,
            recommended_fix=(
                f"The cover letter does not appear to mention the employer '{emp.employer_name}'. "
                "The cover letter should reference the applicant's employer and confirm employment status. "
                "Update the cover letter to include the employer name."
            ),
        ))

    # --- Cross-check employer name against commercial registry / tax card ---
    biz_company = data.business.company_name
    if emp.employer_name and biz_company:
        emp_tokens = _tokens(emp.employer_name)
        biz_tokens = _tokens(biz_company)
        # If no common meaningful tokens, flag a potential mismatch
        common = emp_tokens & biz_tokens
        # Filter out single-character tokens and very common words
        stopwords = {"co", "ltd", "llc", "inc", "for", "the", "and", "of", "a", "an"}
        meaningful_common = common - stopwords
        if not meaningful_common:
            issues.append(ValidationIssue(message_key='validation.18',
                document_name="Employment Documents / Commercial Registry",
                field_name="employer_name vs company_name",
                found_value=f"HR letter: '{emp.employer_name}' | Registry: '{biz_company}'",
                expected_value="Same or clearly related organisation name",
                severity=Severity.LOW,
                recommended_fix=(
                    f"The employer on the HR letter ('{emp.employer_name}') and the company on "
                    f"the Commercial Registry ('{biz_company}') do not share obvious name tokens. "
                    "If these are different entities, provide an explanatory letter clarifying the relationship."
                ),
            ))

    return issues


def _check_missing_fields(data: VisaDocumentExtraction) -> list[ValidationIssue]:
    """
    Check for critical fields that are completely absent across all documents.
    """
    issues: list[ValidationIssue] = []

    critical_checks = [
        ("Flight Reservation", "departure_date",       data.flight.departure_date,             "Outbound flight date"),
        ("Flight Reservation", "return_date",          data.flight.return_date,                "Return flight date"),
        ("Travel Insurance",   "valid_from",           data.insurance.valid_from,              "Policy start date"),
        ("Travel Insurance",   "valid_until",          data.insurance.valid_until,             "Policy end date"),
        ("Travel Itinerary",   "travel_plan_coverage", data.travel_plan.present,                "A dated travel plan covering the application dates"),
    ]
    missing = [label for field, label in [('purpose_of_visit','visit purpose'), ('funding_source','funding'),
                                         ('ties_to_home_country','home ties')] if not getattr(data.cover_letter,field)]
    if missing:
        issues.append(ValidationIssue(document_name='Cover Letter',field_name='cover_letter_completeness',
            found_value='Missing: ' + ', '.join(missing), expected_value='A factual cover letter explaining purpose, funding and home ties',
            severity=Severity.HIGH, message_key='context.cover_letter_completeness', title_en='Cover letter is missing or incomplete',
            recommended_fix='Add or complete the applicant cover letter, explaining ' + ', '.join(missing) +
                '. Use supported facts and list the supplied attachments. A hotel description or itinerary is not a cover letter.'))
    if not data.hotel:
        critical_checks.append(("Hotel Reservation", "hotel", None, "Accommodation bookings"))
    for index, hotel in enumerate(data.hotel):
        critical_checks.extend([
            (f"Hotel Reservation ({index + 1})", "check_in_date", hotel.check_in_date, "Hotel check-in date"),
            (f"Hotel Reservation ({index + 1})", "check_out_date", hotel.check_out_date, "Hotel check-out date"),
        ])

    for doc, field, value, expected in critical_checks:
        if not value:
            issues.append(ValidationIssue(message_key='validation.19',
                document_name=doc,
                field_name=field,
                found_value=None,
                expected_value=expected,
                severity=Severity.HIGH,
                recommended_fix=(
                    f"'{field}' could not be found in the {doc}. "
                    "Ensure the document is complete and legible before uploading."
                ),
            ))

    return issues


# Schengen Area city → country lookup
# Covers the most commonly visited/booked cities.
_SCHENGEN_CITIES: dict[str, str] = {
    # Austria
    "vienna": "Austria", "salzburg": "Austria", "innsbruck": "Austria", "graz": "Austria",
    # Belgium
    "brussels": "Belgium", "bruges": "Belgium", "ghent": "Belgium", "antwerp": "Belgium",
    # Czech Republic
    "prague": "Czech Republic", "brno": "Czech Republic",
    # Denmark
    "copenhagen": "Denmark",
    # Estonia
    "tallinn": "Estonia",
    # Finland
    "helsinki": "Finland",
    # France
    "paris": "France", "nice": "France", "lyon": "France", "marseille": "France",
    "bordeaux": "France", "toulouse": "France", "strasbourg": "France",
    # Germany
    "berlin": "Germany", "munich": "Germany", "frankfurt": "Germany", "hamburg": "Germany",
    "cologne": "Germany", "dusseldorf": "Germany", "stuttgart": "Germany", "dresden": "Germany",
    # Greece
    "athens": "Greece", "thessaloniki": "Greece", "santorini": "Greece", "mykonos": "Greece",
    "heraklion": "Greece", "rhodes": "Greece",
    # Hungary
    "budapest": "Hungary",
    # Iceland
    "reykjavik": "Iceland",
    # Italy
    "rome": "Italy", "milan": "Italy", "venice": "Italy", "florence": "Italy",
    "naples": "Italy", "bologna": "Italy", "turin": "Italy", "palermo": "Italy",
    # Latvia
    "riga": "Latvia",
    # Lithuania
    "vilnius": "Lithuania",
    # Luxembourg
    "luxembourg": "Luxembourg",
    # Malta
    "valletta": "Malta",
    # Netherlands
    "amsterdam": "Netherlands", "rotterdam": "Netherlands", "the hague": "Netherlands",
    "hague": "Netherlands", "utrecht": "Netherlands",
    # Norway
    "oslo": "Norway", "bergen": "Norway",
    # Poland
    "warsaw": "Poland", "krakow": "Poland", "gdansk": "Poland", "wroclaw": "Poland",
    # Portugal
    "lisbon": "Portugal", "porto": "Portugal", "faro": "Portugal",
    # Slovakia
    "bratislava": "Slovakia",
    # Slovenia
    "ljubljana": "Slovenia",
    # Spain
    "madrid": "Spain", "barcelona": "Spain", "seville": "Spain", "valencia": "Spain",
    "malaga": "Spain", "bilbao": "Spain", "granada": "Spain", "palma": "Spain",
    "ibiza": "Spain", "tenerife": "Spain",
    # Sweden
    "stockholm": "Sweden", "gothenburg": "Sweden", "malmo": "Sweden",
    # Switzerland
    "zurich": "Switzerland", "geneva": "Switzerland", "bern": "Switzerland", "basel": "Switzerland",
    "lucerne": "Switzerland", "lausanne": "Switzerland",
    # Liechtenstein
    "vaduz": "Liechtenstein",
}

# Known NON-Schengen cities (common false positives to catch explicitly)
_NON_SCHENGEN_CITIES: set[str] = {
    "london", "manchester", "edinburgh", "glasgow",  # UK
    "dublin",  # Ireland
    "cairo", "alexandria", "hurghada", "sharm el sheikh",  # Egypt
    "dubai", "abu dhabi", "sharjah",  # UAE
    "istanbul", "ankara", "antalya",  # Turkey
    "new york", "los angeles", "chicago", "miami",  # USA
    "toronto", "montreal",  # Canada
    "moscow", "st petersburg",  # Russia
    "beijing", "shanghai", "hong kong",  # China
    "bangkok", "phuket",  # Thailand
    "doha",  # Qatar
    "riyadh", "jeddah",  # Saudi Arabia
    "amman",  # Jordan
    "beirut",  # Lebanon
    "casablanca", "marrakech",  # Morocco
    "tunis",  # Tunisia
}


def _check_schengen_city_validity(data: VisaDocumentExtraction) -> list[ValidationIssue]:
    """
    Geography & Schengen City Match Engine.

    Validates that all cities in the hotel reservations / travel itinerary
    belong to the Schengen Area. Cities outside the Schengen Area are flagged
    as CRITICAL (a Schengen visa cannot be used for stays in non-Schengen countries).
    """
    issues: list[ValidationIssue] = []
    cities = getattr(data, "travel_cities", None) or []

    if not cities:
        return issues  # No city data extracted — cannot validate

    for city in cities:
        city_key = city.strip().lower()
        if city_key in _SCHENGEN_CITIES:
            continue  # Valid Schengen city ✔️

        if city_key in _NON_SCHENGEN_CITIES:
            severity = Severity.CRITICAL
            msg = (
                f"CRITICAL: Hotel / Itinerary includes non-Schengen city '{city}'. "
                "A Schengen visa does not permit stays in this country. "
                "Remove this destination or apply for the correct visa type."
            )
        else:
            # City not in our lookup — flag as MEDIUM (unrecognised, not necessarily invalid)
            severity = Severity.MEDIUM
            msg = (
                f"City '{city}' in the itinerary/hotel booking could not be verified as a "
                "Schengen Area city. Confirm this city is within the Schengen Zone."
            )

        issues.append(ValidationIssue(message_key="city.non_schengen" if severity == Severity.CRITICAL else "city.unknown",
            document_name="Hotel Reservation / Travel Itinerary",
            field_name="travel_cities",
            found_value=city,
            expected_value="A city within the Schengen Area",
            severity=severity,
            recommended_fix=msg,
        ))

    return issues


# ---------------------------------------------------------------------------
# Main Validation Entry Point
# ---------------------------------------------------------------------------

def run_validation(data: VisaDocumentExtraction) -> list[ValidationIssue]:
    """
    Execute all deterministic validation rules against the extracted data.

    Parameters
    ----------
    data : VisaDocumentExtraction
        Parsed extraction result from extractor.py

    Returns
    -------
    list[ValidationIssue]
        All detected issues, sorted by severity (CRITICAL first).
    """
    all_issues: list[ValidationIssue] = []

    all_issues.extend(_check_passport_number_crosscheck(data))   # Rule 1 — CRITICAL
    all_issues.extend(_check_identity_name_crosscheck(data))      # Rule 2 — CRITICAL / HIGH
    all_issues.extend(_check_dob_crosscheck(data))                # Rule 3 — HIGH
    all_issues.extend(_check_date_alignment(data))                # 5-date matrix
    from appointment_review import appointment_issues
    all_issues.extend(appointment_issues(data))
    all_issues.extend(_check_schengen_city_validity(data))        # Geography engine
    all_issues.extend(_check_insurance_coverage(data))
    all_issues.extend(_check_schengen_destination_rule(data))
    all_issues.extend(_check_passport_expiry(data))
    all_issues.extend(_check_employment_leave_dates(data))
    all_issues.extend(_check_employment_consistency(data))
    all_issues.extend(_check_missing_fields(data))
    from identity_checks import strict_identity_checks
    all_issues.extend(strict_identity_checks(data, all_issues))

    # Summary fields and source-level identity rows can report the same typo. Keep the
    # detailed source row and deduct once per distinct discrepancy, not twice.
    deduped={}
    for issue in all_issues:
        identity=issue.message_key.startswith("identity.") or issue.message_key in ("validation.02","validation.03","validation.04")
        if identity:
            doc=issue.document_name.split(" (")[0]
            field="full_name" if issue.field_name=="applicant_name" else issue.field_name
            key=(doc,field,issue.found_value,issue.expected_value)
            if key not in deduped or issue.message_key.startswith("identity."):
                deduped[key]=issue
        else:
            deduped[("rule",len(deduped))]=issue
    all_issues=list(deduped.values())

    # Sort: CRITICAL → HIGH → MEDIUM → LOW
    severity_order = {
        Severity.CRITICAL: 0,
        Severity.HIGH:     1,
        Severity.MEDIUM:   2,
        Severity.LOW:      3,
    }
    all_issues.sort(key=lambda i: severity_order.get(i.severity, 99))

    return all_issues
