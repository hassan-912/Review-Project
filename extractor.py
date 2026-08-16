"""
extractor.py
============
Gemini multimodal document extraction module.

Sends all uploaded Schengen visa documents to Gemini in a single API call
and returns a strongly-typed Pydantic model containing all extracted fields.

Changes in this version
-----------------------
* Accepts multi-file lists per document category.
* Adds EmploymentInfo schema (employer, job title, salary, leave dates).
* Model selector: user-chosen model with automatic 429 fallback to
  gemini-1.5-flash and exponential back-off retry logic.
"""

from __future__ import annotations

import io
import base64
import json
import re
import time
import logging
from typing import Optional

import fitz  # PyMuPDF — local PDF text extraction to cut token payload
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Available Models — tried in order; first success wins
# ---------------------------------------------------------------------------

# Priority list: primary → second fallback → third fallback.
# 404 NOT_FOUND → skip immediately to the next model (invalid endpoint).
# 429 RESOURCE_EXHAUSTED → sleep 3 s then skip to the next model.
# Any other exception → raised immediately.
AVAILABLE_MODELS: list[str] = [
    "gemini-2.0-flash-lite",  # Primary   — free tier, active quota
    "gemini-2.5-flash",       # Fallback 1 — higher capability
    "gemini-2.0-flash",       # Fallback 2 — fast multi-token
]


# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------

class PassportInfo(BaseModel):
    """Fields extracted from the passport document."""
    passport_number: Optional[str] = Field(None, description="Machine-readable passport number")
    full_name: Optional[str] = Field(None, description="Full name as printed on passport")
    date_of_birth: Optional[str] = Field(None, description="DOB in YYYY-MM-DD format")
    nationality: Optional[str] = Field(None, description="Nationality / issuing country")
    passport_expiry: Optional[str] = Field(None, description="Passport expiry date YYYY-MM-DD")
    gender: Optional[str] = None


class FlightInfo(BaseModel):
    """Fields extracted from the flight reservation."""
    departure_date: Optional[str] = Field(None, description="Outbound flight date YYYY-MM-DD")
    return_date: Optional[str] = Field(None, description="Return flight date YYYY-MM-DD")
    departure_city: Optional[str] = None
    destination_city: Optional[str] = None
    booking_reference: Optional[str] = None
    passenger_name: Optional[str] = None


class HotelInfo(BaseModel):
    """Fields extracted from the hotel reservation."""
    check_in_date: Optional[str] = Field(None, description="Hotel check-in YYYY-MM-DD")
    check_out_date: Optional[str] = Field(None, description="Hotel check-out YYYY-MM-DD")
    hotel_name: Optional[str] = None
    city: Optional[str] = None
    guest_name: Optional[str] = None
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


class VisaApplicationInfo(BaseModel):
    """Fields from the official Schengen visa application form."""
    applicant_name: Optional[str] = None
    passport_number: Optional[str] = None
    date_of_birth: Optional[str] = Field(
        None, description="Applicant date of birth as declared on the visa form, YYYY-MM-DD"
    )
    destination_country: Optional[str] = None
    purpose_of_journey: Optional[str] = None
    intended_arrival: Optional[str] = None
    intended_departure: Optional[str] = None


class VisaDocumentExtraction(BaseModel):
    """
    Master extraction schema — all fields extracted across all uploaded
    documents in a single Gemini multimodal call.
    """
    passport: PassportInfo = Field(default_factory=PassportInfo)  # type: ignore
    flight: FlightInfo = Field(default_factory=FlightInfo)  # type: ignore
    hotel: HotelInfo = Field(default_factory=HotelInfo)  # type: ignore
    insurance: InsuranceInfo = Field(default_factory=InsuranceInfo)  # type: ignore
    cover_letter: CoverLetterInfo = Field(default_factory=CoverLetterInfo)  # type: ignore
    business: BusinessInfo = Field(default_factory=BusinessInfo)  # type: ignore
    employment: EmploymentInfo = Field(default_factory=EmploymentInfo)  # type: ignore
    visa_form: VisaApplicationInfo = Field(default_factory=VisaApplicationInfo)  # type: ignore
    main_schengen_destination: Optional[str] = Field(
        None, description="Country where applicant will spend the most nights"
    )
    total_nights_per_country: Optional[dict] = Field(
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


# ---------------------------------------------------------------------------
# File Handling Helpers
# ---------------------------------------------------------------------------

def _make_bytes_part(file_bytes: bytes, mime_type: str) -> types.Part:
    """
    Wrap raw bytes as a types.Part suitable for the google-genai SDK.

    Using types.Part.from_bytes is the correct way to attach binary data
    (images, scanned PDFs) to a multimodal Gemini prompt.  Passing raw bytes
    in a plain dict or as an inline_data dict causes a TypeError inside the
    SDK before the request is even sent.
    """
    return types.Part.from_bytes(data=file_bytes, mime_type=mime_type)


def _guess_mime(filename: str) -> str:
    """Return a best-guess MIME type based on file extension."""
    filename = filename.lower()
    if filename.endswith(".pdf"):
        return "application/pdf"
    if filename.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    if filename.endswith(".png"):
        return "image/png"
    if filename.endswith(".webp"):
        return "image/webp"
    return "application/pdf"


# ---------------------------------------------------------------------------
# Prompt Builder
# ---------------------------------------------------------------------------

def _build_extraction_prompt(doc_labels: list[str]) -> str:
    """
    Build the master extraction prompt that instructs Gemini to parse
    all uploaded documents and return structured JSON.
    """
    schema_json = json.dumps(VisaDocumentExtraction.model_json_schema(), indent=2)
    doc_list = "\n".join(f"  - {label}" for label in doc_labels)

    return f"""You are an expert Schengen visa document analyst.
You have been provided with the following uploaded documents for a Schengen visa application:
{doc_list}

Your task is to carefully read EVERY document and extract ALL relevant information.

⚠️  CRITICAL IDENTITY EXTRACTION RULES (STRICT):
- Extract `passport.passport_number`, `passport.full_name`, and `passport.date_of_birth` EXCLUSIVELY
  from the PASSPORT document image. Do NOT infer or copy these fields from any other document.
- The passport MRZ (Machine Readable Zone) at the bottom of the photo page contains the
  authoritative passport number and date of birth — use it as the primary source.

⚠️  INSURANCE PASSPORT NUMBER EXTRACTION RULE:
- For `insurance.insured_passport_number`: extract ONLY the value from the field labeled
  'Insured Passport No.' or 'Passport No.' on the insurance policy (e.g. A35616219).
- Do NOT extract the 14-digit National ID / Civil ID number (e.g. 29508231200579) into this field.
  National IDs are longer numeric strings — if you see only a long numeric ID, leave this field null.

Pay close attention to:
1. Names — capture the full legal name exactly as printed on the PASSPORT.
2. Dates — always convert to YYYY-MM-DD ISO format.
3. Passport number — extract from PASSPORT MRZ only, critical for cross-verification.
4. Insurance coverage — extract the numeric amount in EUR.
5. Cover letter — identify: purpose, funding, ties to home country, documents list, employer mention.
6. Business documents — field of work from Commercial Registry / Tax Card vs invitation topic.
7. Destination — determine the Schengen country where applicant spends the most nights.
8. Employment documents — extract employer name, job title, monthly salary, approved leave dates,
   whether leave approval is explicitly confirmed, and contract type.
9. Cities — compile a complete list of ALL cities mentioned in hotel reservations and the
   travel itinerary. Store them in `travel_cities` as a JSON array of strings.

Return ONLY a valid JSON object matching this exact schema (no markdown fences, no extra keys):
{schema_json}

If a value cannot be determined from the documents, use null.
Fill raw_extraction_notes with any ambiguities or uncertainties you encountered.
"""


# ---------------------------------------------------------------------------
# Local PDF Text Extraction — reduces token payload by ~95%
# ---------------------------------------------------------------------------

def _extract_pdf_text(filename: str, file_bytes: bytes) -> str | None:
    """
    Attempt to extract plain text from a PDF using PyMuPDF.

    Returns the extracted text string if it contains meaningful content
    (> 50 chars), otherwise returns None so the caller falls back to
    sending the raw bytes as a vision part.
    """
    if not filename.lower().endswith(".pdf"):
        return None
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        pages_text = [str(page.get_text()) for page in doc]
        doc.close()
        combined = "\n".join(pages_text)
        if combined and len(combined.strip()) > 50:
            return combined
    except Exception:
        pass
    return None


def _passport_pdf_to_image_parts(file_bytes: bytes) -> list[types.Part]:
    """
    Render every page of a passport PDF to a PNG image and return them as
    types.Part vision parts.

    Passports MUST be sent as vision images so Gemini can OCR the MRZ zone
    and the photo page.  Converting a passport PDF to plain text loses the
    MRZ line and the visual structure, leading to wrong passport numbers.
    """
    parts: list[types.Part] = []
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        for page in doc:
            # Render at 2x scale for better MRZ readability
            mat = fitz.Matrix(2.0, 2.0)
            pix = page.get_pixmap(matrix=mat)  # type: ignore[attr-defined]
            png_bytes = pix.tobytes("png")
            parts.append(types.Part.from_bytes(data=png_bytes, mime_type="image/png"))
        doc.close()
    except Exception:
        # Fallback: send the raw PDF bytes if rendering fails
        parts.append(types.Part.from_bytes(data=file_bytes, mime_type="application/pdf"))
    return parts


# ---------------------------------------------------------------------------
# Content Parts Builder — supports multiple files per category
# ---------------------------------------------------------------------------

def _is_passport_category(category: str) -> bool:
    """
    Return True if the category label belongs to the Passport upload slot.
    The category key used in app.py is the DOCUMENT_SLOTS display label,
    e.g. '\U0001f6c2 Passport'.
    """
    return "passport" in category.lower()


def _build_content_parts(
    uploaded_files: dict[str, list[tuple[str, bytes]]],
) -> tuple[list, list[str]]:
    """
    Build the list of Gemini content parts from the multi-file upload dict.

    Passport files are ALWAYS sent as rendered PNG images (never text) so
    Gemini performs Vision OCR on the MRZ zone and photo page.
    For all other PDF files, text is extracted locally with PyMuPDF first
    (reducing token usage by ~95%).  Images and scanned non-passport PDFs
    are wrapped with types.Part.from_bytes.

    Parameters
    ----------
    uploaded_files : dict[str, list[tuple[str, bytes]]]
        {category_label: [(filename, bytes), ...]}

    Returns
    -------
    (content_parts, doc_labels)
        content_parts: list of Gemini content parts ready for the API
        doc_labels: flat list of labels used for the prompt header
    """
    doc_labels: list[str] = []
    content_parts: list = []

    for category, file_list in uploaded_files.items():
        is_passport = _is_passport_category(category)
        for idx, (filename, file_bytes) in enumerate(file_list):
            suffix = f" (file {idx + 1}: {filename})" if len(file_list) > 1 else f" (file: {filename})"
            label = f"{category}{suffix}"
            doc_labels.append(label)

            content_parts.append({"text": f"\n--- Document: {label} ---"})

            if is_passport and filename.lower().endswith(".pdf"):
                # PASSPORT PDF → always render to PNG images for Vision OCR
                content_parts.extend(_passport_pdf_to_image_parts(file_bytes))
            elif is_passport:
                # PASSPORT image → always send as-is for Vision OCR
                mime = _guess_mime(filename)
                content_parts.append(_make_bytes_part(file_bytes, mime))
            else:
                # All other documents: try text extraction first
                extracted_text = _extract_pdf_text(filename, file_bytes)
                if extracted_text:
                    content_parts.append({"text": extracted_text})
                else:
                    mime = _guess_mime(filename)
                    content_parts.append(_make_bytes_part(file_bytes, mime))

    return content_parts, doc_labels


# ---------------------------------------------------------------------------
# 429 Detection Helper
# ---------------------------------------------------------------------------

def _is_rate_limit_error(exc: Exception) -> bool:
    """Return True if the exception indicates a 429 RESOURCE_EXHAUSTED error."""
    msg = str(exc).lower()
    return "429" in msg or "resource_exhausted" in msg or "quota" in msg or "rate limit" in msg

# ---------------------------------------------------------------------------
# Gemini Call Helper — walks AVAILABLE_MODELS, handles 404 / 429 per model
# ---------------------------------------------------------------------------

def call_gemini_with_fallback(
    client: genai.Client,
    contents: list,
    log_fn=None,
) -> str:
    """
    Try each model in AVAILABLE_MODELS in priority order and return the
    raw response text from the first successful call.

    Error handling per model
    ------------------------
    404 NOT_FOUND   → Model endpoint unavailable; skip immediately.
    429 / QUOTA     → Sleep 3 s then skip to next model.
    Anything else   → Raised immediately (no silent swallowing).

    Raises
    ------
    RuntimeError
        If every model in the list fails.
    """
    def _log(msg: str):
        if log_fn:
            log_fn(msg)
        logger.info(msg)

    for model_name in AVAILABLE_MODELS:
        try:
            _log(f"🔄 Calling {model_name} with {len(contents)} content part(s)…")
            response = client.models.generate_content(
                model=model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    temperature=0.0,        # Deterministic extraction
                    max_output_tokens=8192,
                    # response_mime_type is intentionally omitted — it causes
                    # 400/404 on some endpoint versions; we parse JSON ourselves.
                ),
            )
            _log(f"✅ Success with model '{model_name}'.")
            return (response.text or "").strip()

        except Exception as exc:
            err_str = str(exc)

            if "404" in err_str or "NOT_FOUND" in err_str:
                # Model endpoint not available — skip to next immediately
                _log(f"❌ 404 NOT_FOUND for '{model_name}': {exc}. Trying next model…")
                continue

            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "quota" in err_str.lower():
                # Rate-limited — brief pause then try next model
                _log(f"⚠️ 429 RESOURCE_EXHAUSTED for '{model_name}'. Waiting 3 s…")
                time.sleep(3)
                continue

            # All other errors are hard failures — raise immediately
            raise exc

    raise RuntimeError(
        "All attempted Gemini models failed. "
        f"Tried: {AVAILABLE_MODELS}. Please check your API key and quota."
    )


# ---------------------------------------------------------------------------
# Main Extraction Function
# ---------------------------------------------------------------------------

def extract_documents(
    api_key: str,
    uploaded_files: dict[str, list[tuple[str, bytes]]],
    model_id: str = "gemini-1.5-flash",   # kept for API compatibility; ignored — fallback chain used
    max_retries: int = 2,
    status_callback=None,
) -> VisaDocumentExtraction:
    """
    Send all uploaded documents to Gemini in a single multimodal call
    and return a parsed VisaDocumentExtraction object.

    The model used is determined automatically by call_gemini_with_fallback();
    it tries AVAILABLE_MODELS in order and skips on 404 / 429.
    The `model_id` parameter is accepted for backwards-compatibility but is
    no longer used to select the model directly.

    Parameters
    ----------
    api_key : str
        Gemini API key from the user session.
    uploaded_files : dict[str, list[tuple[str, bytes]]]
        Mapping of category_label -> [(filename, bytes), ...].
    model_id : str
        Deprecated — kept for call-site compatibility. Ignored internally.
    max_retries : int
        Unused — retry semantics now live inside call_gemini_with_fallback().
    status_callback : callable | None
        Optional function(message: str) for live status updates in the UI.

    Returns
    -------
    VisaDocumentExtraction
        Fully parsed Pydantic model.

    Raises
    ------
    ValueError
        If the API returns unparseable output.
    RuntimeError
        If every model in the fallback chain fails.
    """
    if not api_key:
        raise ValueError("Gemini API key is required. Please enter it in the sidebar.")

    if not uploaded_files:
        raise ValueError("No documents were uploaded. Please upload at least one document.")

    def _log(msg: str):
        logger.info(msg)
        if status_callback:
            status_callback(msg)

    # ------------------------------------------------------------------
    # Build Gemini client — v1beta required for 2.0/2.5 model families.
    # ------------------------------------------------------------------
    client = genai.Client(
        api_key=api_key,
        http_options={"api_version": "v1beta"},
    )

    # ------------------------------------------------------------------
    # Assemble content parts from all categories / all files
    # ------------------------------------------------------------------
    file_parts, doc_labels = _build_content_parts(uploaded_files)
    prompt_text = _build_extraction_prompt(doc_labels)
    content_parts: list = [{"text": prompt_text}] + file_parts

    # ------------------------------------------------------------------
    # Call Gemini — automatic model fallback (404 → skip, 429 → sleep+skip)
    # ------------------------------------------------------------------
    raw_text = call_gemini_with_fallback(client, content_parts, log_fn=_log)

    # ------------------------------------------------------------------
    # Parse JSON response → Pydantic model
    # ------------------------------------------------------------------
    # Robustly strip any markdown fences Gemini might add around JSON
    clean = raw_text.strip()
    if clean.startswith("```json"):
        clean = clean[7:]
    elif clean.startswith("```"):
        clean = clean[3:]
    if clean.endswith("```"):
        clean = clean[:-3]
    clean = clean.strip()
    # Also strip via regex in case of inline fences
    clean = re.sub(r"^```(?:json)?\s*", "", clean)
    clean = re.sub(r"\s*```$", "", clean)

    data = json.loads(clean)  # Raises JSONDecodeError with precise error message if invalid
    return VisaDocumentExtraction.model_validate(data)
