"""
scorer.py
=========
Acceptance likelihood scoring engine for Schengen visa applications.

Starts from 100% and applies severity-based deductions for each
detected ValidationIssue. Returns a final percentage and a color-coded
badge label for the Streamlit dashboard.

Changes in this version
-----------------------
* Added BONUS_LEAVE_APPROVAL_CONFIRMED: +3 pts if leave approval is present.
* calculate_score() now accepts leave_confirmed flag.
* _cover_letter_is_complete() updated to also check employer_mentioned.
"""

from __future__ import annotations

from dataclasses import dataclass

from validator import Severity, ValidationIssue


# ---------------------------------------------------------------------------
# Deduction Table (points deducted per issue at each severity level)
# ---------------------------------------------------------------------------

SEVERITY_DEDUCTIONS: dict[Severity, float] = {
    Severity.CRITICAL: 35.0,   # Identity mismatch / passport fraud indicators
    Severity.HIGH:     15.0,   # Date gaps, coverage below €30k
    Severity.MEDIUM:    8.0,   # Sector mismatch, missing fields
    Severity.LOW:       3.0,   # Minor inconsistencies
}

# Maximum deduction per severity tier — prevents a single tier from zeroing the score alone
# (unless there are truly catastrophic identity-level failures)
MAX_DEDUCTION_PER_SEVERITY: dict[Severity, float] = {
    Severity.CRITICAL: 100.0,  # 3 identity-critical issues can fully zero the score
    Severity.HIGH:      45.0,
    Severity.MEDIUM:    24.0,
    Severity.LOW:       12.0,
}

# Bonus points for explicitly good signals
BONUS_COVER_LETTER_COMPLETE: float = 5.0     # Cover letter has all 4 required sections
BONUS_LEAVE_APPROVAL_CONFIRMED: float = 3.0  # HR leave approval letter explicitly present


# ---------------------------------------------------------------------------
# Score Result Model
# ---------------------------------------------------------------------------

@dataclass
class ScoreResult:
    """Final scoring output."""
    score: float               # 0.0 – 100.0
    badge_label: str           # "Strong", "Moderate", "Weak"
    badge_color: str           # "green", "yellow", "red" (for Streamlit)
    deductions_detail: list[dict]   # Per-issue breakdown for display
    bonus_detail: list[dict]        # Per-bonus breakdown for display
    total_issues: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int


# ---------------------------------------------------------------------------
# Main Scoring Function
# ---------------------------------------------------------------------------

def calculate_score(
    issues: list[ValidationIssue],
    cover_letter_complete: bool = False,
    leave_confirmed: bool = False,
) -> ScoreResult:
    """
    Calculate the Schengen visa acceptance likelihood score.

    Parameters
    ----------
    issues : list[ValidationIssue]
        Combined list of issues from validator.py and business_checker.py.
    cover_letter_complete : bool
        True if all 4 cover letter sections are present.
    leave_confirmed : bool
        True if an explicit HR leave approval letter was detected.

    Returns
    -------
    ScoreResult
        Detailed scoring breakdown with final percentage and badge info.
    """
    score = 100.0
    deductions_detail: list[dict] = []
    bonus_detail: list[dict] = []

    # ------------------------------------------------------------------
    # Tally issues by severity
    # ------------------------------------------------------------------
    counts: dict[Severity, int] = {
        Severity.CRITICAL: 0,
        Severity.HIGH: 0,
        Severity.MEDIUM: 0,
        Severity.LOW: 0,
    }
    for issue in issues:
        counts[issue.severity] = counts.get(issue.severity, 0) + 1

    # ------------------------------------------------------------------
    # Apply deductions per severity tier (capped per tier)
    # ------------------------------------------------------------------
    for severity in [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW]:
        count = counts.get(severity, 0)
        if count == 0:
            continue

        raw_deduction = count * SEVERITY_DEDUCTIONS[severity]
        capped_deduction = min(raw_deduction, MAX_DEDUCTION_PER_SEVERITY[severity])
        score -= capped_deduction

        deductions_detail.append({
            "severity": severity.value,
            "issue_count": count,
            "points_per_issue": SEVERITY_DEDUCTIONS[severity],
            "total_deducted": capped_deduction,
            "was_capped": raw_deduction > MAX_DEDUCTION_PER_SEVERITY[severity],
        })

    # ------------------------------------------------------------------
    # Apply bonuses
    # ------------------------------------------------------------------
    if cover_letter_complete:
        bonus = BONUS_COVER_LETTER_COMPLETE
        score += bonus
        bonus_detail.append({
            "reason": "Cover letter complete (all 4 required sections present)",
            "points_added": bonus,
        })

    if leave_confirmed:
        bonus = BONUS_LEAVE_APPROVAL_CONFIRMED
        score += bonus
        bonus_detail.append({
            "reason": "HR leave approval letter explicitly confirmed",
            "points_added": bonus,
        })

    # Clamp score to [0, 100]
    score = max(0.0, min(100.0, score))

    # ------------------------------------------------------------------
    # Determine badge
    # ------------------------------------------------------------------
    if score >= 85.0:
        badge_label = "Strong — Likely Approved"
        badge_color = "green"
    elif score >= 65.0:
        badge_label = "Moderate — Needs Attention"
        badge_color = "yellow"
    else:
        badge_label = "Weak — High Risk of Rejection"
        badge_color = "red"

    return ScoreResult(
        score=round(score, 1),
        badge_label=badge_label,
        badge_color=badge_color,
        deductions_detail=deductions_detail,
        bonus_detail=bonus_detail,
        total_issues=len(issues),
        critical_count=counts[Severity.CRITICAL],
        high_count=counts[Severity.HIGH],
        medium_count=counts[Severity.MEDIUM],
        low_count=counts[Severity.LOW],
    )


def _cover_letter_is_complete(data) -> bool:
    """
    Helper: check if all 4 cover letter sections are present in the extraction.
    Import-safe — accepts any object with a cover_letter attribute.
    """
    cl = data.cover_letter
    return all([
        cl.purpose_of_visit,
        cl.funding_source,
        cl.ties_to_home_country,
        cl.attached_documents_listed,
    ])


def _leave_is_confirmed(data) -> bool:
    """
    Helper: return True if employment docs confirm an approved leave letter.
    """
    return bool(
        hasattr(data, "employment")
        and data.employment.leave_approval_confirmed is True
    )
