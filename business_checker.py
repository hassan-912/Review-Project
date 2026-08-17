"""
business_checker.py
===================
Business purpose alignment checker for Schengen visa applications.

Compares the applicant's field of work (from Commercial Registry / Tax Card)
against the stated purpose of the trip (invitation letter, conference topic)
to detect sector or activity mismatches.

Changes in this version
-----------------------
* Compatible with updated VisaDocumentExtraction that now includes
  EmploymentInfo (employer name, job title, salary, leave dates).
* No additional logic changes — employment cross-checks live in validator.py.
"""

from __future__ import annotations

from pydantic import BaseModel

from extractor import VisaDocumentExtraction
from validator import Severity, ValidationIssue


# ---------------------------------------------------------------------------
# Business Check Result Model
# ---------------------------------------------------------------------------

class BusinessCheckResult(BaseModel):
    """Summary result from the business purpose alignment check."""
    is_business_visa: bool
    fields_match: bool
    declared_field_of_work: str | None
    invitation_topic: str | None
    mismatch_description: str | None
    issues: list[ValidationIssue]


# ---------------------------------------------------------------------------
# Sector Keyword Mapping
# ---------------------------------------------------------------------------

# Map of broad sector labels to related keyword sets.
# If extracted field_of_work and invitation_topic share at least one sector
# they will be considered aligned.
SECTOR_KEYWORDS: dict[str, set[str]] = {
    "technology": {
        "tech", "technology", "software", "it", "digital", "ai", "cloud",
        "cyber", "data", "developer", "engineering", "hardware", "saas",
        "startup", "innovation", "ict", "machine learning", "blockchain",
    },
    "finance": {
        "finance", "financial", "banking", "investment", "capital", "fund",
        "accounting", "audit", "tax", "insurance", "fintech", "trading",
        "economics", "fiscal", "budget", "revenue",
    },
    "medicine": {
        "medical", "medicine", "health", "healthcare", "hospital", "pharma",
        "pharmaceutical", "clinic", "therapy", "nursing", "surgery", "dental",
        "biotech", "genomics", "research", "clinical",
    },
    "education": {
        "education", "university", "academic", "research", "conference",
        "teaching", "school", "learning", "training", "workshop", "seminar",
        "scholar", "faculty", "professor", "student", "curriculum",
    },
    "construction": {
        "construction", "engineering", "architecture", "building", "infrastructure",
        "civil", "structural", "contractor", "real estate", "property",
    },
    "trade": {
        "trade", "import", "export", "commerce", "wholesale", "retail",
        "distribution", "supply chain", "logistics", "procurement",
        "merchandise", "goods", "business",
    },
    "legal": {
        "legal", "law", "attorney", "lawyer", "counsel", "arbitration",
        "compliance", "regulatory", "judicial", "notary",
    },
    "arts_media": {
        "arts", "media", "film", "photography", "design", "creative",
        "advertising", "marketing", "journalism", "broadcasting", "art",
        "entertainment", "music", "fashion",
    },
    "energy": {
        "energy", "oil", "gas", "petroleum", "renewable", "solar", "wind",
        "power", "electricity", "utilities", "mining",
    },
    "agriculture": {
        "agriculture", "farming", "food", "agribusiness", "crop",
        "livestock", "horticulture", "fisheries",
    },
}

# Business-trip keywords that signal this is a business visa
BUSINESS_TRIP_INDICATORS = {
    "conference", "meeting", "exhibition", "fair", "summit", "forum",
    "workshop", "seminar", "training", "negotiation", "business", "b2b",
    "trade mission", "delegation", "partnership", "collaboration",
    "client", "supplier", "contract",
}


def _tokenize(text: str | None) -> set[str]:
    """Lower-case and split text into individual tokens."""
    if not text:
        return set()
    return set(text.lower().replace(",", " ").replace("-", " ").split())


def _get_sectors(tokens: set[str]) -> set[str]:
    """Return the set of sector labels whose keywords appear in the token set."""
    matched: set[str] = set()
    for sector, keywords in SECTOR_KEYWORDS.items():
        if tokens & keywords:
            matched.add(sector)
    return matched


def _is_business_trip(data: VisaDocumentExtraction) -> bool:
    """
    Determine if the visa application is for a business purpose.
    Returns True if business indicators appear in cover letter, invitation,
    or visa form purpose fields.
    """
    combined_text = " ".join(filter(None, [
        data.cover_letter.purpose_of_visit,
        data.business.invitation_topic,
        data.business.conference_or_meeting_subject,
        data.visa_form.purpose_of_journey,
    ])).lower()
    tokens = _tokenize(combined_text)
    return bool(tokens & BUSINESS_TRIP_INDICATORS)


# ---------------------------------------------------------------------------
# Main Business Check Function
# ---------------------------------------------------------------------------

def check_business_alignment(data: VisaDocumentExtraction) -> BusinessCheckResult:
    """
    Analyze whether the applicant's professional background aligns with
    the stated business purpose of the Schengen visit.

    Parameters
    ----------
    data : VisaDocumentExtraction
        Parsed extraction result from extractor.py

    Returns
    -------
    BusinessCheckResult
        Alignment verdict, mismatch description, and any ValidationIssues raised.
    """
    issues: list[ValidationIssue] = []
    is_business = _is_business_trip(data)

    field_of_work = data.business.field_of_work
    invitation_topic = (
        data.business.invitation_topic
        or data.business.conference_or_meeting_subject
        or data.cover_letter.purpose_of_visit
    )

    # ------------------------------------------------------------------
    # Non-business visa: no further sector check needed
    # ------------------------------------------------------------------
    if not is_business:
        return BusinessCheckResult(
            is_business_visa=False,
            fields_match=True,  # Not applicable
            declared_field_of_work=field_of_work,
            invitation_topic=invitation_topic,
            mismatch_description=None,
            issues=[],
        )

    # ------------------------------------------------------------------
    # Business visa: check if business docs were provided
    # ------------------------------------------------------------------
    if not field_of_work:
        issues.append(ValidationIssue(
            document_name="Commercial Registry / Tax Card",
            field_name="field_of_work",
            found_value=None,
            expected_value="Applicant's registered business sector",
            severity=Severity.MEDIUM,
            recommended_fix=(
                "Field of work could not be extracted from Commercial Registry or Tax Card. "
                "Ensure these translated documents are clearly uploaded and legible. "
                "The business field must be visible for sector alignment checks."
            ),
        ))

    if not invitation_topic:
        issues.append(ValidationIssue(
            document_name="Invitation Letter / Cover Letter",
            field_name="invitation_topic",
            found_value=None,
            expected_value="Conference topic or meeting purpose",
            severity=Severity.MEDIUM,
            recommended_fix=(
                "The purpose or topic of the business trip could not be determined "
                "from the invitation letter or cover letter. "
                "Include an explicit statement of the conference or meeting subject."
            ),
        ))

    # ------------------------------------------------------------------
    # Sector alignment check
    # ------------------------------------------------------------------
    if not field_of_work or not invitation_topic:
        return BusinessCheckResult(
            is_business_visa=True,
            fields_match=False,
            declared_field_of_work=field_of_work,
            invitation_topic=invitation_topic,
            mismatch_description="Cannot verify alignment — one or both fields are missing.",
            issues=issues,
        )

    work_tokens = _tokenize(field_of_work)
    trip_tokens = _tokenize(invitation_topic)

    work_sectors = _get_sectors(work_tokens)
    trip_sectors = _get_sectors(trip_tokens)

    # Check for direct token overlap (e.g., "software" appears in both)
    direct_overlap = bool(work_tokens & trip_tokens)
    # Check for sector-level alignment
    sector_overlap = bool(work_sectors & trip_sectors)

    fields_match = direct_overlap or sector_overlap

    if not fields_match:
        mismatch_desc = (
            f"Applicant's registered field of work ('{field_of_work}') "
            f"appears unrelated to the trip purpose ('{invitation_topic}'). "
            f"Work sectors detected: {work_sectors or {'unknown'}}. "
            f"Trip sectors detected: {trip_sectors or {'unknown'}}."
        )
        issues.append(ValidationIssue(
            document_name="Commercial Registry / Invitation Letter",
            field_name="field_of_work vs invitation_topic",
            found_value=f"Work: {field_of_work} | Trip: {invitation_topic}",
            expected_value="Same or closely related business sector",
            severity=Severity.MEDIUM,
            recommended_fix=(
                "The applicant's stated business sector does not align with the "
                "conference or meeting topic. For business visas, the invitation must "
                "relate to the applicant's professional field. Include an explanatory "
                "cover letter paragraph addressing this connection."
            ),
        ))
    else:
        mismatch_desc = None

    return BusinessCheckResult(
        is_business_visa=True,
        fields_match=fields_match,
        declared_field_of_work=field_of_work,
        invitation_topic=invitation_topic,
        mismatch_description=mismatch_desc,
        issues=issues,
    )
