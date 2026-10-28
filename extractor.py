"""Shared local document schemas and deterministic extraction entry point."""
from __future__ import annotations
import json
import re
from typing import Optional, Literal
import pymupdf as fitz
from pydantic import BaseModel, Field, field_validator
from finance_review import BankStatement, TripCost, BookingStatus

class PassportInfo(BaseModel):
    """Fields extracted from the passport document."""
    passport_number: Optional[str] = Field(None, description="Machine-readable passport number")
    full_name: Optional[str] = Field(None, description="Full name as printed on passport")
    date_of_birth: Optional[str] = Field(None, description="DOB in YYYY-MM-DD format")
    place_of_birth: Optional[str] = None
    nationality: Optional[str] = Field(None, description="Nationality / issuing country")
    passport_expiry: Optional[str] = Field(None, description="Passport expiry date YYYY-MM-DD")
    gender: Optional[str] = None
    given_names: Optional[str] = None
    surname: Optional[str] = None
    passport_issue: Optional[str] = Field(None, description="Date of issue on passport visual page, not MRZ; YYYY-MM-DD")
    native_name: Optional[str] = Field(None, description="Full name in Arabic/native script copied from passport visual page only; no transliteration")
    national_id_number: Optional[str] = Field(None, description="National ID number printed on passport visual page, separate from passport number")


class FlightInfo(BaseModel):
    """Fields extracted from the flight reservation."""
    departure_date: Optional[str] = Field(None, description="Outbound flight date YYYY-MM-DD")
    return_date: Optional[str] = Field(None, description="Return flight date YYYY-MM-DD")
    departure_city: Optional[str] = None
    destination_city: Optional[str] = None
    booking_reference: Optional[str] = None
    passenger_name: Optional[str] = None
    passport_number: Optional[str] = None
    passport_issue: Optional[str] = None
    passport_expiry: Optional[str] = None
    arrival_time: Optional[str] = Field(None, description="Arrival at final destination, local HH:MM; not departure or connection arrival")
    return_departure_time: Optional[str] = Field(None, description="Return departure from destination, local HH:MM")


class HotelInfo(BaseModel):
    """Fields extracted from the hotel reservation."""
    check_in_date: Optional[str] = Field(None, description="Hotel check-in YYYY-MM-DD")
    check_out_date: Optional[str] = Field(None, description="Hotel check-out YYYY-MM-DD")
    hotel_name: Optional[str] = None
    city: Optional[str] = None
    guest_name: Optional[str] = None
    passport_number: Optional[str] = None
    passport_issue: Optional[str] = None
    passport_expiry: Optional[str] = None
    booking_reference: Optional[str] = None


class InsuranceInfo(BaseModel):
    """Fields extracted from the travel insurance policy."""
    coverage_amount_eur: Optional[float] = Field(None, description="Medical coverage in EUR")
    valid_from: Optional[str] = Field(None, description="Policy start date YYYY-MM-DD")
    valid_until: Optional[str] = Field(None, description="Policy end date YYYY-MM-DD")
    insured_name: Optional[str] = None
    policy_number: Optional[str] = None
    insured_passport_number: Optional[str] = Field(
        None,
        description=(
            "The PASSPORT number printed on the insurance policy in a field labeled "
            "'Insured Passport No.' or 'Passport No.' — e.g. A35616219. "
            "Do NOT extract the 14-digit National ID / Civil ID number here."
        )
    )
    covered_countries: Optional[str] = None


class CoverLetterInfo(BaseModel):
    """Key sections detected inside the cover letter."""
    purpose_of_visit: Optional[str] = None
    funding_source: Optional[str] = None
    ties_to_home_country: Optional[str] = None
    attached_documents_listed: Optional[bool] = None
    applicant_name_mentioned: Optional[bool] = None
    dates_mentioned: Optional[bool] = None
    destination_country_mentioned: Optional[bool] = None
    employer_mentioned: Optional[bool] = Field(
        None, description="Whether the cover letter mentions the employer or company name"
    )


class BusinessInfo(BaseModel):
    """Fields from commercial registry, tax card, or invitation."""
    company_name: Optional[str] = None
    field_of_work: Optional[str] = None
    invitation_topic: Optional[str] = None
    inviting_organization: Optional[str] = None
    conference_or_meeting_subject: Optional[str] = None


class EmploymentInfo(BaseModel):
    """
    Fields extracted from employment documents:
    HR letter, payslips, leave approval, employment contract.
    """
    employer_name: Optional[str] = Field(
        None, description="Name of the employing organisation as shown on HR letter or contract"
    )
    job_title: Optional[str] = Field(
        None, description="Applicant's job title / position"
    )
    employer_address: Optional[str] = Field(None, description="Company/workplace address explicitly printed in HR, not employee home address")
    monthly_salary: Optional[str] = Field(
        None, description="Monthly gross salary with currency as stated in payslip or HR letter"
    )
    approved_leave_start: Optional[str] = Field(
        None, description="Start date of approved annual leave YYYY-MM-DD"
    )
    approved_leave_end: Optional[str] = Field(
        None, description="End date of approved annual leave YYYY-MM-DD"
    )
    leave_approval_confirmed: Optional[bool] = Field(
        None, description="True if an explicit leave approval letter/stamp is present"
    )
    contract_type: Optional[str] = Field(
        None, description="Employment contract type e.g. permanent, fixed-term, part-time"
    )
    evidence_type: Literal["employment", "education", "none", "unknown"] = "unknown"


class VisaApplicationInfo(BaseModel):
    """Fields from the official Schengen visa application form."""
    applicant_name: Optional[str] = None
    passport_number: Optional[str] = None
    date_of_birth: Optional[str] = Field(
        None, description="Applicant date of birth as declared on the visa form, YYYY-MM-DD"
    )
    place_of_birth: Optional[str] = None
    destination_country: Optional[str] = None
    purpose_of_journey: Optional[str] = None
    intended_arrival: Optional[str] = None
    intended_departure: Optional[str] = None
    given_names: Optional[str] = None
    surname: Optional[str] = None
    passport_issue: Optional[str] = None
    passport_expiry: Optional[str] = None
    national_id_number: Optional[str] = None
    national_id_issue: Optional[str] = None
    national_id_expiry: Optional[str] = None
    occupation: Optional[str] = None
    employer_name: Optional[str] = None
    employer_address: Optional[str] = Field(None, description="Employer/company address from the application employer section, not applicant home address")
    first_entry_country: Optional[str] = None


class AppointmentInfo(BaseModel):
    """An applicant's actual appointment, never the letter's issue/print date."""
    source_file: str
    page: int = Field(1, ge=1)
    appointment_date: Optional[str] = Field(None, description="Actual embassy/visa-centre appointment date YYYY-MM-DD; null when ambiguous")
    appointment_time: Optional[str] = Field(None, description="Printed appointment local time HH:MM; do not invent a timezone")
    applicant_name: Optional[str] = None
    embassy: Optional[str] = None
    text: Optional[str] = Field(None, description="Verbatim quote containing the appointment date/time and its appointment label")


class NationalIDInfo(BaseModel):
    present: bool = False
    full_name: Optional[str] = None
    id_number: Optional[str] = None
    issue_date: Optional[str] = None
    expiry_date: Optional[str] = None


class IdentityEvidence(BaseModel):
    """One applicant identity block per source/page; no merged conflicting values."""
    document: Literal["visa_form", "hotel", "flight", "insurance", "cover_letter", "travel_plan", "supporting", "passport", "national_id", "employment"]
    source_file: str
    subject_role: Literal["applicant", "mother", "father", "relative", "other", "unknown"] = "applicant"
    name_scope: Literal["full", "first_only", "not_applicable"] = "full"
    page: Optional[int] = Field(None, ge=1)
    full_name: Optional[str] = None
    given_names: Optional[str] = None
    surname: Optional[str] = None
    passport_number: Optional[str] = None
    date_of_birth: Optional[str] = None
    passport_issue: Optional[str] = None
    passport_expiry: Optional[str] = None
    national_id_number: Optional[str] = None
    national_id_issue: Optional[str] = None
    national_id_expiry: Optional[str] = None
    unreadable_fields: list[str] = Field(default_factory=list, description="Fields visibly present but unclear; never guess characters or ambiguous dates")


class WritingRecommendation(BaseModel):
    action: Literal["add", "remove", "replace", "verify"]
    source_file: Optional[str] = None
    page: Optional[int] = Field(None, ge=1)
    original_text: Optional[str] = Field(None, description="Exact verbatim words from this section only. Required for remove/replace.")
    reason: str
    replacement: Optional[str] = Field(None, description="Concrete proposed wording grounded in evidence; bracketed placeholders for missing facts")
    day: Optional[str] = Field(None, description="Specific itinerary date YYYY-MM-DD when advice relates to one day")


class TravelDay(BaseModel):
    date: Optional[str] = None
    city: Optional[str] = None
    accommodation: Optional[str] = None
    activities: list[str] = Field(default_factory=list)
    transport: Optional[str] = None

    @field_validator("activities",mode="before")
    @classmethod
    def empty_activities(cls,value):
        return [] if value is None else value


class NarrativeSection(BaseModel):
    present: bool = False
    source_files: list[str] = Field(default_factory=list)
    source_text: Optional[str] = Field(None, description="Verbatim section text only, excluding other sections in a combined file")
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    cities: list[str] = Field(default_factory=list)
    days: list[TravelDay] = Field(default_factory=list)
    recommendations: list[WritingRecommendation] = Field(default_factory=list, max_length=10)

    @field_validator("source_files","cities","days","recommendations",mode="before")
    @classmethod
    def empty_lists(cls,value):
        return [] if value is None else value


class SourceField(BaseModel):
    document: str
    source_file: str
    page: int = Field(ge=1)
    field_name: str
    value: Optional[str] = None
    text: str = Field(description="Exact original words around this field; never translate or silently correct")
    box: Optional[list[float]] = Field(None, min_length=4, max_length=4, description="Optional [x0,y0,x1,y1] coordinates normalized 0..1; only when visible and confidently located")
    local_source: bool = Field(False,description='Reserved for server-side local extraction; narrative reviewers must leave false.')


class SupportingClaim(BaseModel):
    field_name: str = Field(description="Canonical field: full_name, passport_number, date_of_birth, employer_name, job_title, monthly_salary, funding_source, or other clear field name")
    value: Optional[str] = None
    page: Optional[int] = Field(None,ge=1)
    quote: Optional[str] = None
    assessment: Literal["consistent","conflicts","unverified"] = "unverified"
    reason: Optional[str] = None
    compared_with: Optional[str] = Field(None, description="Filename of another supplied document supporting the assessment; not an external authenticity claim")
    subject_role: Literal["applicant", "mother", "father", "relative", "other", "unknown"] = "applicant"
    name_scope: Literal["full", "first_only", "not_applicable"] = "full"


class SupportingDocument(BaseModel):
    source_file: str
    document_type: str
    summary: str
    claims: list[SupportingClaim] = Field(default_factory=list)

    @field_validator("claims",mode="before")
    @classmethod
    def empty_claims(cls,value):
        return [] if value is None else value


class DocumentAudit(BaseModel):
    source_file: str
    document_types: list[str] = Field(default_factory=list)
    pages_read: list[int] = Field(default_factory=list)
    readability: Literal["readable","partial","unreadable"] = "partial"
    uncertainties: list[str] = Field(default_factory=list)
    summary: Optional[str] = None

    @field_validator("document_types","pages_read","uncertainties",mode="before")
    @classmethod
    def empty_audit_lists(cls,value):
        return [] if value is None else value


class VisaDocumentExtraction(BaseModel):
    """
    Master evidence schema for local document parsing and validation.
    """
    passport: PassportInfo = Field(default_factory=PassportInfo)  # type: ignore
    flight: FlightInfo = Field(default_factory=FlightInfo)  # type: ignore
    hotel: list[HotelInfo] = Field(default_factory=list)
    insurance: InsuranceInfo = Field(default_factory=InsuranceInfo)  # type: ignore
    cover_letter: CoverLetterInfo = Field(default_factory=CoverLetterInfo)  # type: ignore
    business: BusinessInfo = Field(default_factory=BusinessInfo)  # type: ignore
    employment: EmploymentInfo = Field(default_factory=EmploymentInfo)  # type: ignore
    visa_form: VisaApplicationInfo = Field(default_factory=VisaApplicationInfo)  # type: ignore
    national_id: NationalIDInfo = Field(default_factory=NationalIDInfo)
    appointments: list[AppointmentInfo] = Field(default_factory=list)
    identity_evidence: list[IdentityEvidence] = Field(default_factory=list)
    cover_letter_text: NarrativeSection = Field(default_factory=NarrativeSection)
    travel_plan: NarrativeSection = Field(default_factory=NarrativeSection)
    detected_documents: list[str] = Field(default_factory=list)
    evidence_locations: list[SourceField] = Field(default_factory=list)
    supporting_documents: list[SupportingDocument] = Field(default_factory=list)
    document_audits: list[DocumentAudit] = Field(default_factory=list)
    bank_statements: list[BankStatement] = Field(default_factory=list)
    trip_costs: list[TripCost] = Field(default_factory=list)
    booking_statuses: list[BookingStatus] = Field(default_factory=list)
    main_schengen_destination: Optional[str] = Field(
        None, description="Country where applicant will spend the most nights"
    )
    total_nights_per_country: Optional[dict[str,int]] = Field(
        None, description="Mapping of country -> number of nights planned"
    )
    travel_cities: Optional[list[str]] = Field(
        None,
        description=(
            "Complete list of city names visited according to the hotel reservations and "
            "travel itinerary. Include ALL cities, e.g. ['Amsterdam', 'Paris', 'Rome']."
        )
    )
    raw_extraction_notes: Optional[str] = Field(
        None, description="Any notes or uncertainties flagged during extraction"
    )
    executive_summary: Optional[str] = None
    urgent_actions: list[str] = Field(default_factory=list)
    contextual_findings: list[dict] = Field(default_factory=list)
    review_limitations: list[str] = Field(default_factory=list)
    unverified_findings: list[dict] = Field(default_factory=list)
    context_checks: list[dict] = Field(default_factory=list)
    extraction_mode: str = Field('legacy',exclude=True)
    local_results: list[dict] = Field(default_factory=list,exclude=True)
    local_hr: dict = Field(default_factory=dict,exclude=True)
    local_hr_checks: list[dict] = Field(default_factory=list,exclude=True)
    review_provenance: dict = Field(default_factory=dict)

    @field_validator("passport","flight","insurance","cover_letter","business","employment","visa_form","national_id","cover_letter_text","travel_plan",mode="before")
    @classmethod
    def absent_sections(cls,value):
        # Accept null for an absent document. Preserve missing evidence
        # as an empty model so validation can flag it, without inventing any fields.
        return {} if value is None else value

    @field_validator("appointments","identity_evidence","detected_documents","urgent_actions","evidence_locations","supporting_documents","document_audits","bank_statements","trip_costs","booking_statuses",mode="before")
    @classmethod
    def absent_arrays(cls,value):
        return [] if value is None else value

    @field_validator("hotel", mode="before")
    @classmethod
    def accept_legacy_hotel(cls, value):
        if isinstance(value, dict):
            return [value] if any(value.values()) else []
        return value or []


def _extract_pdf_text(filename: str, file_bytes: bytes) -> str | None:
    """Read native PDF text locally; uncertain scanned pages remain unverified."""
    if not filename.lower().endswith('.pdf'):return None
    try:
        with fitz.open(stream=file_bytes,filetype='pdf') as document:
            pages=[page.get_text() for page in document]
        if not pages or any(len(text.strip())<20 for text in pages):return None
        combined='\n'.join(f'[Page {index}]\n{text}' for index,text in enumerate(pages,1))
        return combined if len(combined.strip())>50 else None
    except Exception:return None


def _is_passport_category(category):
    return category=='passport'


def _parse_response(raw_text):
    """Validate previously saved JSON evidence without any external service."""
    clean=re.sub(r'^```(?:json)?\s*|\s*```$','',raw_text.strip())
    return VisaDocumentExtraction.model_validate(json.loads(clean))


def extract_documents(uploaded_files,cache=None,review_country=None):
    """Extract supported uploads locally. No API key or remote model is used."""
    if not uploaded_files:raise ValueError('No documents were uploaded.')
    from local_extraction import extract_local_documents
    return extract_local_documents(uploaded_files,cache=cache,review_country=review_country)
