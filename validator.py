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

from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel

from extractor import VisaDocumentExtraction


# ---------------------------------------------------------------------------
# Severity Levels
# ---------------------------------------------------------------------------

class Severity(str, Enum):
    CRITICAL = "CRITICAL"   # Likely rejection
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

def _names_match(name_a: Optional[str], name_b: Optional[str]) -> bool:
    """
    Fuzzy case-insensitive name match.

    Returns True if the two names are considered the same person by checking:
    1. Full string equality (after normalisation)
    2. Whether all tokens in the shorter name are present in the longer name
       (handles middle-name omissions and re-ordered name parts).
    """
    if not name_a or not name_b:
        return True   # Cannot flag a mismatch if either side is missing
    a = name_a.strip().upper()
    b = name_b.strip().upper()
    if a == b:
        return True
    tokens_a = set(a.replace(",", "").split())
    tokens_b = set(b.replace(",", "").split())
    shorter = tokens_a if len(tokens_a) <= len(tokens_b) else tokens_b
    longer  = tokens_b if len(tokens_a) <= len(tokens_b) else tokens_a
    # At least surname AND one given-name token must match
    common = shorter & longer
    return len(common) >= min(2, len(shorter))


def _check_passport_number_crosscheck(data: VisaDocumentExtraction) -> list[ValidationIssue]:
    """
    Rule 1 — Passport Number Cross-Check (CRITICAL).
    """
    issues: list[ValidationIssue] = []
    reference_num = data.passport.passport_number

    if not reference_num:
        issues.append(ValidationIssue(
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
            issues.append(ValidationIssue(
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
    """
    Rule 2 — Applicant Full Name Cross-Check (CRITICAL for wrong passport).

    Compares the full name on the PASSPORT IMAGE against:
      - The Visa Application Form (applicant_name)
      - Employment docs (employer_name is not the same; skip)

    A mismatch here indicates the wrong passport was attached, which is a
    CRITICAL rejection reason.
    """
    issues: list[ValidationIssue] = []
    passport_name = data.passport.full_name

    if not passport_name:
        return issues  # Cannot flag without a reference

    visa_form_name = data.visa_form.applicant_name if data.visa_form else None

    if visa_form_name and not _names_match(passport_name, visa_form_name):
        issues.append(ValidationIssue(
            document_name="Visa Application Form",
            field_name="applicant_name",
            found_value=visa_form_name,
            expected_value=passport_name,
            severity=Severity.CRITICAL,
            recommended_fix=(
                f"CRITICAL: Wrong Passport Attached! "
                f"Passport document belongs to '{passport_name}', "
                f"but Visa Application Form belongs to '{visa_form_name}'. "
                "Ensure the correct passport is scanned for this application."
            ),
        ))

    # Cross-check against booking names (HIGH severity — name order / typo issues)
    booking_candidates = {
        "Flight Reservation": data.flight.passenger_name,
        "Hotel Reservation":  data.hotel.guest_name,
        "Travel Insurance":   data.insurance.insured_name,
    }
    for doc_name, found_name in booking_candidates.items():
        if not found_name:
            continue
        if not _names_match(passport_name, found_name):
            issues.append(ValidationIssue(
                document_name=doc_name,
                field_name="applicant_name",
                found_value=found_name,
                expected_value=passport_name,
                severity=Severity.HIGH,
                recommended_fix=(
                    f"Name '{found_name}' in {doc_name} does not clearly match "
                    f"passport name '{passport_name}'. "
                    "Ensure all bookings use the exact name as printed on the passport."
                ),
            ))
    return issues


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
        issues.append(ValidationIssue(
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


def _check_date_alignment(data: VisaDocumentExtraction) -> list[ValidationIssue]:
    """
    Complete Date Alignment Matrix — cross-checks all 5 key travel dates.

    Departure cluster (must all be consistent with flight departure):
      Flight dep ≤ Hotel first check-in ≤ Insurance start ≤ Visa Form entry

    Return cluster (must all be consistent with flight return):
      Flight return ≥ Hotel last check-out ≥ Insurance end ≥ Visa Form exit
    """
    issues: list[ValidationIssue] = []

    flight_dep  = _parse_date(data.flight.departure_date)
    flight_ret  = _parse_date(data.flight.return_date)
    hotel_in    = _parse_date(data.hotel.check_in_date)
    hotel_out   = _parse_date(data.hotel.check_out_date)
    ins_start   = _parse_date(data.insurance.valid_from)
    ins_end     = _parse_date(data.insurance.valid_until)
    visa_entry  = _parse_date(getattr(data.visa_form, "intended_arrival", None))
    visa_exit   = _parse_date(getattr(data.visa_form, "intended_departure", None))

    def _flag(doc: str, field: str, found: str, expected: str, fix: str,
               sev: Severity = Severity.HIGH) -> None:
        issues.append(ValidationIssue(
            document_name=doc, field_name=field,
            found_value=found, expected_value=expected,
            severity=sev, recommended_fix=fix,
        ))

    # ── Departure cluster ───────────────────────────────────────────────────────────────
    if flight_dep and hotel_in and flight_dep > hotel_in:
        _flag("Flight / Hotel", "departure_date vs check_in_date",
              f"Flight dep: {data.flight.departure_date}, Hotel in: {data.hotel.check_in_date}",
              "Flight departure ≤ Hotel check-in",
              "Flight departs AFTER hotel check-in. Align the outbound flight to arrive before check-in.")

    if flight_dep and ins_start and ins_start > flight_dep:
        _flag("Travel Insurance", "valid_from vs departure_date",
              f"Insurance starts: {data.insurance.valid_from}, Flight dep: {data.flight.departure_date}",
              "Insurance start ≤ Flight departure",
              "Insurance must be valid from the departure date. Obtain a revised policy.",
              Severity.CRITICAL)

    if flight_dep and visa_entry:
        if abs((flight_dep - visa_entry).days) > 3:
            _flag("Visa Application Form / Flight", "intended_arrival vs departure_date",
                  f"Visa form entry: {data.visa_form.intended_arrival}, Flight dep: {data.flight.departure_date}",
                  "Visa entry date within 3 days of flight departure",
                  "The intended entry date on the Visa Form differs significantly from the flight departure. "
                  "Update the Visa Form to reflect the actual travel dates.")

    # ── Return cluster ────────────────────────────────────────────────────────────────
    if flight_ret and hotel_out and flight_ret < hotel_out:
        _flag("Flight / Hotel", "return_date vs check_out_date",
              f"Flight ret: {data.flight.return_date}, Hotel out: {data.hotel.check_out_date}",
              "Flight return ≥ Hotel check-out",
              "Return flight is before hotel check-out. Update either the flight or hotel dates.")

    if flight_ret and ins_end and ins_end < flight_ret:
        _flag("Travel Insurance", "valid_until vs return_date",
              f"Insurance ends: {data.insurance.valid_until}, Flight ret: {data.flight.return_date}",
              "Insurance end ≥ Flight return",
              "Insurance expires before the return flight. Extend the policy to cover the full trip.",
              Severity.CRITICAL)

    if flight_ret and visa_exit:
        if abs((flight_ret - visa_exit).days) > 3:
            _flag("Visa Application Form / Flight", "intended_departure vs return_date",
                  f"Visa form exit: {data.visa_form.intended_departure}, Flight ret: {data.flight.return_date}",
                  "Visa exit date within 3 days of flight return",
                  "The intended departure date on the Visa Form differs significantly from the return flight. "
                  "Update the Visa Form to reflect the actual return date.")

    # ── Departure before return ─────────────────────────────────────────────────────
    if flight_dep and flight_ret and flight_dep >= flight_ret:
        _flag("Flight Reservation", "departure_date / return_date",
              f"Dep: {data.flight.departure_date}, Ret: {data.flight.return_date}",
              "Departure must be before return",
              "Departure date is on or after the return date. Verify the flight reservation.",
              Severity.CRITICAL)

    return issues


def _check_insurance_coverage(data: VisaDocumentExtraction) -> list[ValidationIssue]:
    """
    Rule: Schengen regulations mandate minimum €30,000 medical insurance coverage.
    """
    issues: list[ValidationIssue] = []
    min_coverage = 30_000.0

    if data.insurance.coverage_amount_eur is None:
        issues.append(ValidationIssue(
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
        issues.append(ValidationIssue(
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
        issues.append(ValidationIssue(
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
            actual_main = max(nights, key=lambda k: nights[k])
            declared = data.main_schengen_destination.strip().lower()
            if actual_main.lower() != declared:
                issues.append(ValidationIssue(
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

    return issues


def _check_passport_expiry(data: VisaDocumentExtraction) -> list[ValidationIssue]:
    """
    Rule: Passport must be valid for at least 3 months beyond the return date.
    """
    issues: list[ValidationIssue] = []

    expiry = _parse_date(data.passport.passport_expiry)
    flight_ret = _parse_date(data.flight.return_date)

    if not expiry:
        issues.append(ValidationIssue(
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
        issues.append(ValidationIssue(
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
            flight_ret.day,
        )
        if expiry < months_3_after_return:
            issues.append(ValidationIssue(
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


def _check_employment_leave_dates(data: VisaDocumentExtraction) -> list[ValidationIssue]:
    """
    Rule: Approved leave period must completely cover the travel period
    (flight departure → flight return).
    If no employment documents were uploaded, skip silently.
    """
    issues: list[ValidationIssue] = []
    emp = data.employment

    # If no employment data at all, skip this check
    if not emp.employer_name and not emp.approved_leave_start and not emp.approved_leave_end:
        return issues

    flight_dep = _parse_date(data.flight.departure_date)
    flight_ret = _parse_date(data.flight.return_date)
    leave_start = _parse_date(emp.approved_leave_start)
    leave_end   = _parse_date(emp.approved_leave_end)

    # Check that leave approval letter exists
    if emp.leave_approval_confirmed is False:
        issues.append(ValidationIssue(
            document_name="Employment Documents",
            field_name="leave_approval_confirmed",
            found_value="Not found",
            expected_value="An explicit leave approval letter or stamp",
            severity=Severity.MEDIUM,
            recommended_fix=(
                "No leave approval letter or HR confirmation stamp was detected. "
                "Many consulates require formal leave approval from the employer. "
                "Obtain a signed HR leave approval letter and include it in the package."
            ),
        ))

    # Leave start must be on or before flight departure
    if flight_dep and leave_start:
        if leave_start > flight_dep:
            issues.append(ValidationIssue(
                document_name="Employment Documents",
                field_name="approved_leave_start vs flight departure",
                found_value=f"Leave start: {emp.approved_leave_start}, Flight dep: {data.flight.departure_date}",
                expected_value="Approved leave must start on or before the departure date",
                severity=Severity.HIGH,
                recommended_fix=(
                    f"Leave approval starts ({emp.approved_leave_start}) AFTER the flight departure "
                    f"({data.flight.departure_date}). The approved leave period must cover the entire trip. "
                    "Request an updated leave letter from HR with the correct start date."
                ),
            ))

    # Leave end must be on or after flight return
    if flight_ret and leave_end:
        if leave_end < flight_ret:
            issues.append(ValidationIssue(
                document_name="Employment Documents",
                field_name="approved_leave_end vs flight return",
                found_value=f"Leave end: {emp.approved_leave_end}, Flight ret: {data.flight.return_date}",
                expected_value="Approved leave must end on or after the return date",
                severity=Severity.HIGH,
                recommended_fix=(
                    f"Leave approval ends ({emp.approved_leave_end}) BEFORE the flight return "
                    f"({data.flight.return_date}). The approved leave must cover the full trip duration. "
                    "Request an updated leave letter from HR covering the complete travel period."
                ),
            ))

    return issues


def _check_employment_consistency(data: VisaDocumentExtraction) -> list[ValidationIssue]:
    """
    Rule: Employer name and job title in employment documents should be
    consistent with what is stated in the cover letter and business registry.
    """
    issues: list[ValidationIssue] = []
    emp = data.employment

    # Skip if no employment data uploaded
    if not emp.employer_name and not emp.job_title:
        return issues

    # --- Cross-check employer name against cover letter ---
    if emp.employer_name and data.cover_letter.employer_mentioned is False:
        issues.append(ValidationIssue(
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
            issues.append(ValidationIssue(
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
        ("Cover Letter",       "purpose_of_visit",    data.cover_letter.purpose_of_visit,    "A clear statement of visit purpose"),
        ("Cover Letter",       "funding_source",       data.cover_letter.funding_source,       "Statement of how the trip is funded"),
        ("Cover Letter",       "ties_to_home_country", data.cover_letter.ties_to_home_country, "Evidence of ties to home country"),
        ("Flight Reservation", "departure_date",       data.flight.departure_date,             "Outbound flight date"),
        ("Flight Reservation", "return_date",          data.flight.return_date,                "Return flight date"),
        ("Hotel Reservation",  "check_in_date",        data.hotel.check_in_date,               "Hotel check-in date"),
        ("Hotel Reservation",  "check_out_date",       data.hotel.check_out_date,              "Hotel check-out date"),
        ("Travel Insurance",   "valid_from",           data.insurance.valid_from,              "Policy start date"),
        ("Travel Insurance",   "valid_until",          data.insurance.valid_until,             "Policy end date"),
    ]

    for doc, field, value, expected in critical_checks:
        if not value:
            issues.append(ValidationIssue(
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

        issues.append(ValidationIssue(
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
    all_issues.extend(_check_schengen_city_validity(data))        # Geography engine
    all_issues.extend(_check_insurance_coverage(data))
    all_issues.extend(_check_schengen_destination_rule(data))
    all_issues.extend(_check_passport_expiry(data))
    all_issues.extend(_check_employment_leave_dates(data))
    all_issues.extend(_check_employment_consistency(data))
    all_issues.extend(_check_missing_fields(data))

    # Sort: CRITICAL → HIGH → MEDIUM → LOW
    severity_order = {
        Severity.CRITICAL: 0,
        Severity.HIGH:     1,
        Severity.MEDIUM:   2,
        Severity.LOW:      3,
    }
    all_issues.sort(key=lambda i: severity_order.get(i.severity, 99))

    return all_issues
