"""
app.py
======
Schengen Visa File Review Bot — Streamlit Main Dashboard

Entry point for the application. Handles:
  - Gemini API key input (securely stored in session state)
  - Model Selection dropdown (with 429 fallback handled in extractor.py)
  - Multi-file upload for all 9 Schengen document categories
  - Review trigger → orchestrates extractor → validator → business_checker → scorer
  - Styled results dashboard with score badge, error table, and cover letter audit

Changes in this version
-----------------------
* Model selector dropdown (sidebar) — default gemini-1.5-flash.
* All file uploaders now accept_multiple_files=True.
* New "Employment Documents" uploader category.
* Pipeline now passes leave_confirmed flag to scorer.
"""

from __future__ import annotations

import traceback

# pyrefly: ignore [missing-import]
import streamlit as st

# ---------------------------------------------------------------------------
# Page configuration — MUST be the first Streamlit call
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Schengen Visa File Review Bot",
    page_icon="🇪🇺",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS — Premium dark-glass aesthetic
# ---------------------------------------------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

.stApp {
    background: linear-gradient(135deg, #0D1117 0%, #0f1923 50%, #0D1117 100%);
}
[data-testid="stSidebar"] {
    background: rgba(22, 27, 34, 0.95);
    border-right: 1px solid rgba(79, 142, 247, 0.15);
}
.hero-banner {
    background: linear-gradient(135deg, rgba(79,142,247,0.15) 0%, rgba(103,58,183,0.15) 100%);
    border: 1px solid rgba(79,142,247,0.25);
    border-radius: 16px;
    padding: 2.5rem 2rem;
    margin-bottom: 2rem;
    backdrop-filter: blur(10px);
}
.hero-title {
    font-size: 2.2rem; font-weight: 700;
    background: linear-gradient(135deg, #4F8EF7, #a78bfa);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text; margin: 0;
}
.hero-subtitle { color: #8b949e; font-size: 1rem; margin-top: 0.5rem; }

.score-card { border-radius: 16px; padding: 2rem; text-align: center; border: 1px solid; backdrop-filter: blur(10px); }
.score-card.green  { background: rgba(35,134,54,0.15);  border-color: rgba(35,134,54,0.5); }
.score-card.yellow { background: rgba(187,128,9,0.15);  border-color: rgba(187,128,9,0.5); }
.score-card.red    { background: rgba(218,54,51,0.15);  border-color: rgba(218,54,51,0.5); }
.score-number { font-size: 4rem; font-weight: 700; line-height: 1; }
.score-card.green  .score-number { color: #3fb950; }
.score-card.yellow .score-number { color: #d29922; }
.score-card.red    .score-number { color: #f85149; }
.score-label { font-size: 1rem; font-weight: 500; margin-top: 0.5rem; }
.score-card.green  .score-label { color: #3fb950; }
.score-card.yellow .score-label { color: #d29922; }
.score-card.red    .score-label { color: #f85149; }

.section-header {
    font-size: 1.1rem; font-weight: 600; color: #e6edf3;
    border-left: 3px solid #4F8EF7;
    padding-left: 0.75rem; margin: 1.5rem 0 1rem;
}

.sev-critical { background: rgba(218,54,51,0.2);  color: #f85149; border-radius:6px; padding: 2px 8px; font-size:0.8rem; font-weight:600; }
.sev-high     { background: rgba(210,153,34,0.2); color: #d29922; border-radius:6px; padding: 2px 8px; font-size:0.8rem; font-weight:600; }
.sev-medium   { background: rgba(79,142,247,0.2); color: #4F8EF7; border-radius:6px; padding: 2px 8px; font-size:0.8rem; font-weight:600; }
.sev-low      { background: rgba(63,185,80,0.2);  color: #3fb950; border-radius:6px; padding: 2px 8px; font-size:0.8rem; font-weight:600; }

.stat-card { background: rgba(22,27,34,0.8); border: 1px solid rgba(79,142,247,0.15); border-radius: 12px; padding: 1rem; text-align: center; }
.stat-number { font-size: 2rem; font-weight: 700; color: #4F8EF7; }
.stat-label  { font-size: 0.8rem; color: #8b949e; margin-top: 0.25rem; }

.styled-table { width: 100%; border-collapse: collapse; font-size: 0.875rem; border-radius: 12px; overflow: hidden; }
.styled-table th { background: rgba(79,142,247,0.15); color: #4F8EF7; padding: 10px 14px; text-align: left; font-weight: 600; border-bottom: 1px solid rgba(79,142,247,0.2); }
.styled-table td { padding: 10px 14px; border-bottom: 1px solid rgba(255,255,255,0.05); color: #e6edf3; vertical-align: top; }
.styled-table tr:hover td { background: rgba(79,142,247,0.05); }
.styled-table .fix-col { color: #8b949e; font-size: 0.82rem; }

.model-badge {
    display: inline-block; background: rgba(79,142,247,0.15); color: #4F8EF7;
    border: 1px solid rgba(79,142,247,0.3); border-radius: 20px;
    padding: 2px 10px; font-size: 0.78rem; font-weight: 600; margin-left: 6px;
}

[data-testid="stFileUploader"] {
    background: rgba(22,27,34,0.6); border: 1px solid rgba(79,142,247,0.2);
    border-radius: 12px; padding: 0.5rem;
}
.info-box {
    background: rgba(79,142,247,0.08); border: 1px solid rgba(79,142,247,0.2);
    border-radius: 10px; padding: 1rem 1.25rem; margin: 0.75rem 0;
    color: #8b949e; font-size: 0.875rem;
}
.stSpinner > div { border-top-color: #4F8EF7 !important; }
.stButton > button {
    background: linear-gradient(135deg, #4F8EF7, #673ab7);
    color: white; border: none; border-radius: 10px;
    font-weight: 600; font-size: 1rem; padding: 0.6rem 2rem;
    transition: opacity 0.2s;
}
.stButton > button:hover { opacity: 0.85; }

/* Status Cards */
.status-card {
    border-radius: 20px; padding: 2.5rem 2rem;
    text-align: center; border: 2px solid;
    backdrop-filter: blur(10px); margin-bottom: 1.5rem;
}
.status-card.green  { background: rgba(35,134,54,0.12);  border-color: #3fb950; }
.status-card.yellow { background: rgba(187,128,9,0.12);  border-color: #d29922; }
.status-card.red    { background: rgba(218,54,51,0.12);  border-color: #f85149; }
.status-icon { font-size: 3.5rem; margin-bottom: 0.5rem; }
.status-title { font-size: 1.6rem; font-weight: 700; margin-bottom: 0.25rem; }
.status-card.green  .status-title { color: #3fb950; }
.status-card.yellow .status-title { color: #d29922; }
.status-card.red    .status-title { color: #f85149; }
.status-score { font-size: 3.5rem; font-weight: 800; line-height: 1; }
.status-card.green  .status-score { color: #3fb950; }
.status-card.yellow .status-score { color: #d29922; }
.status-card.red    .status-score { color: #f85149; }
.status-sub { font-size: 0.95rem; color: #8b949e; margin-top: 0.5rem; }

/* Fix Checklist */
.fix-card {
    background: rgba(22,27,34,0.85); border-radius: 14px;
    border: 1px solid rgba(255,255,255,0.08); padding: 1.25rem 1.5rem;
    margin-bottom: 0.75rem;
}
.fix-card.critical { border-left: 4px solid #f85149; }
.fix-card.high     { border-left: 4px solid #d29922; }
.fix-card.medium   { border-left: 4px solid #4F8EF7; }
.fix-card.low      { border-left: 4px solid #3fb950; }
.fix-badge { display:inline-block; border-radius:6px; padding:2px 10px; font-size:0.75rem; font-weight:700; margin-bottom:0.4rem; }
.fix-badge.critical { background:rgba(218,54,51,0.2); color:#f85149; }
.fix-badge.high     { background:rgba(210,153,34,0.2); color:#d29922; }
.fix-badge.medium   { background:rgba(79,142,247,0.2); color:#4F8EF7; }
.fix-badge.low      { background:rgba(63,185,80,0.2);  color:#3fb950; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Lazy imports (after st.set_page_config)
# ---------------------------------------------------------------------------
from extractor import (
    extract_documents,
    VisaDocumentExtraction,
    AVAILABLE_MODELS,
)
from validator import run_validation, ValidationIssue, Severity
from business_checker import check_business_alignment
from scorer import calculate_score, ScoreResult, _cover_letter_is_complete, _leave_is_confirmed
try:
    from fpdf import FPDF  # fpdf2
    _PDF_AVAILABLE = True
except ImportError:
    _PDF_AVAILABLE = False


# ---------------------------------------------------------------------------
# Document Slots — (key, label, help_text)
# All uploaders accept multiple files.
# ---------------------------------------------------------------------------

DOCUMENT_SLOTS: list[tuple[str, str, str]] = [
    (
        "passport",
        "🛂 Passport",
        "Biographical data page(s) or full scan. Supports multiple pages.",
    ),
    (
        "visa_form",
        "📋 Visa Application Form",
        "Official Schengen application form (signed). Multiple pages accepted.",
    ),
    (
        "cover_letter",
        "✉️ Cover Letter",
        "Personal statement addressed to the consulate.",
    ),
    (
        "travel_plan",
        "🗺️ Travel Plan / Itinerary",
        "Day-by-day itinerary with country/night breakdown.",
    ),
    (
        "hotel_reservation",
        "🏨 Hotel Reservations",
        "All confirmed hotel bookings for the entire stay (multiple files OK).",
    ),
    (
        "flight_reservation",
        "✈️ Flight Tickets / Reservations",
        "Round-trip flight confirmation(s). Upload all legs.",
    ),
    (
        "travel_insurance",
        "🛡️ Travel Insurance Policy",
        "Policy with coverage amount, dates, and territory.",
    ),
    (
        "employment_docs",
        "💼 Employment Documents",
        "HR letter, payslips, leave approval, employment contract. Multiple files OK.",
    ),
    (
        "supporting_docs",
        "📁 Supporting / Translated Documents",
        "Commercial Registry, Tax Card, Bank/Employment statements, translations.",
    ),
]

# Map category key → display label (used to build uploaded_files dict for extractor)
_KEY_TO_LABEL = {key: label for key, label, _ in DOCUMENT_SLOTS}


# ---------------------------------------------------------------------------
# Session State Initialization
# ---------------------------------------------------------------------------

def _init_session_state():
    defaults = {
        "api_key": "",
        # Default to the first model in the fallback list (gemini-1.5-flash)
        "selected_model": AVAILABLE_MODELS[0],
        "review_result": None,
        "review_error": None,
        "review_traceback": None,
        "status_log": [],
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

def render_sidebar() -> tuple[dict[str, list[tuple[str, bytes]]], str]:
    """
    Render the sidebar with API key input, model selector, and file uploaders.

    Returns
    -------
    tuple[dict[str, list[tuple[str, bytes]]], str]
        - {display_label: [(filename, bytes), ...]} for every non-empty category.
        - selected model id string.
    """
    with st.sidebar:
        st.markdown("## ⚙️ Configuration")

        # ── API Key ──────────────────────────────────────────────────
        api_key = st.text_input(
            "Gemini API Key",
            type="password",
            value=st.session_state.api_key,
            placeholder="AIza...",
            help="Your Google Gemini API key. Never shared or stored.",
        )
        st.session_state.api_key = api_key

        if api_key:
            st.success("✓ API key set", icon="🔑")
        else:
            st.warning("Enter your Gemini API key to begin", icon="⚠️")

        # ── Model Selector ───────────────────────────────────────────
        st.markdown("### 🤖 Model Selection")

        # Human-readable labels for each model in the fallback list
        _MODEL_LABELS = {
            "gemini-2.0-flash-lite": "gemini-2.0-flash-lite  ✦ Primary — Free tier, active quota",
            "gemini-2.5-flash":      "gemini-2.5-flash  — Higher capability (Fallback 1)",
            "gemini-2.0-flash":      "gemini-2.0-flash  — Fast multi-token (Fallback 2)",
        }
        model_options = AVAILABLE_MODELS  # list[str]
        model_display = [_MODEL_LABELS.get(m, m) for m in model_options]

        current_idx = (
            model_options.index(st.session_state.selected_model)
            if st.session_state.selected_model in model_options
            else 0
        )
        selected_display = st.selectbox(
            "Gemini Model",
            options=model_display,
            index=current_idx,
            help=(
                "The app tries models in priority order and auto-skips on errors:\n\n"
                "• **404 NOT_FOUND** → skip to next model immediately\n"
                "• **429 RESOURCE_EXHAUSTED** → wait 3 s then skip\n\n"
                f"Priority: {' → '.join(AVAILABLE_MODELS)}"
            ),
        )
        # Map display label back to the actual model ID
        selected_model_id = model_options[model_display.index(selected_display)]
        st.session_state.selected_model = selected_model_id

        fallback_chain = " → ".join(AVAILABLE_MODELS)
        st.markdown(
            f'<div class="info-box">'
            f'Active: <span class="model-badge">{selected_model_id}</span><br>'
            f'Fallback chain: <code style="color:#8b949e; font-size:0.77rem">{fallback_chain}</code>'
            f'</div>',
            unsafe_allow_html=True,
        )

        st.divider()

        # ── File Uploaders ───────────────────────────────────────────
        st.markdown("## 📎 Upload Documents")
        st.markdown(
            '<div class="info-box">Upload all applicable documents. '
            'Each slot accepts <strong>multiple files</strong>.</div>',
            unsafe_allow_html=True,
        )

        uploaded_files: dict[str, list[tuple[str, bytes]]] = {}

        for key, label, help_text in DOCUMENT_SLOTS:
            files = st.file_uploader(
                label,
                type=["pdf", "jpg", "jpeg", "png", "webp"],
                key=f"upload_{key}",
                help=help_text,
                accept_multiple_files=True,  # ← multi-file enabled
            )
            if files:
                uploaded_files[label] = [(f.name, f.getvalue()) for f in files]

        st.divider()
        file_count = sum(len(v) for v in uploaded_files.values())
        st.markdown(
            f'<div style="color:#8b949e; font-size:0.75rem;">'
            f'{file_count} file(s) loaded across {len(uploaded_files)} categories.<br>'
            f'Files processed in-memory — never stored on disk.<br>'
            f'© 2024 Schengen Visa Review Bot</div>',
            unsafe_allow_html=True,
        )

    return uploaded_files, selected_model_id


# ---------------------------------------------------------------------------
# Rendering Helpers
# ---------------------------------------------------------------------------

def _severity_badge(severity: Severity) -> str:
    cls_map = {
        Severity.CRITICAL: "sev-critical",
        Severity.HIGH:     "sev-high",
        Severity.MEDIUM:   "sev-medium",
        Severity.LOW:      "sev-low",
    }
    return f'<span class="{cls_map.get(severity, "sev-low")}">{severity.value}</span>'


def render_score_card(score: float, badge_label: str, badge_color: str):
    st.markdown(
        f"""<div class="score-card {badge_color}">
            <div class="score-number">{score:.0f}%</div>
            <div class="score-label">{badge_label}</div>
            <div style="color:#8b949e; font-size:0.85rem; margin-top:0.5rem;">
                Acceptance Likelihood
            </div>
        </div>""",
        unsafe_allow_html=True,
    )


def render_issue_counts(result_score):
    cols = st.columns(4)
    stats = [
        (result_score.critical_count, "CRITICAL", "#f85149"),
        (result_score.high_count,     "HIGH",     "#d29922"),
        (result_score.medium_count,   "MEDIUM",   "#4F8EF7"),
        (result_score.low_count,      "LOW",      "#3fb950"),
    ]
    for col, (count, label, color) in zip(cols, stats):
        with col:
            st.markdown(
                f'<div class="stat-card">'
                f'<div class="stat-number" style="color:{color}">{count}</div>'
                f'<div class="stat-label">{label} Issues</div></div>',
                unsafe_allow_html=True,
            )


def render_error_table(issues: list[ValidationIssue]):
    if not issues:
        st.success("✅ No validation issues detected!", icon="🎉")
        return

    rows = ""
    for issue in issues:
        found = issue.found_value or "—"
        rows += (
            f"<tr>"
            f"<td>{issue.document_name}</td>"
            f"<td><code>{issue.field_name}</code></td>"
            f"<td style='color:#e6edf3'>{found}</td>"
            f"<td style='color:#8b949e'>{issue.expected_value}</td>"
            f"<td>{_severity_badge(issue.severity)}</td>"
            f"<td class='fix-col'>{issue.recommended_fix}</td>"
            f"</tr>"
        )

    st.markdown(
        f"""<table class="styled-table">
            <thead><tr>
                <th>Document</th><th>Field</th><th>Found Value</th>
                <th>Expected Value</th><th>Severity</th><th>Recommended Fix</th>
            </tr></thead>
            <tbody>{rows}</tbody>
        </table>""",
        unsafe_allow_html=True,
    )


def render_cover_letter_audit(data: VisaDocumentExtraction):
    cl = data.cover_letter

    def _icon(value) -> str:
        if value is None:
            return "🔘"
        if isinstance(value, bool):
            return "✅" if value else "❌"
        return "✅" if value else "❌"

    checklist = [
        ("Purpose of Visit",         cl.purpose_of_visit,              cl.purpose_of_visit),
        ("Funding Source",            cl.funding_source,                cl.funding_source),
        ("Ties to Home Country",      cl.ties_to_home_country,          cl.ties_to_home_country),
        ("Attached Documents List",   cl.attached_documents_listed,     cl.attached_documents_listed),
        ("Applicant Name Mentioned",  cl.applicant_name_mentioned,      cl.applicant_name_mentioned),
        ("Travel Dates Mentioned",    cl.dates_mentioned,               cl.dates_mentioned),
        ("Destination Country",       cl.destination_country_mentioned, cl.destination_country_mentioned),
        ("Employer Mentioned",        cl.employer_mentioned,            cl.employer_mentioned),
    ]

    for section_name, value, detail in checklist:
        icon = _icon(value)
        detail_str = ""
        if isinstance(detail, str) and detail:
            detail_str = (
                f'<span style="color:#8b949e; font-size:0.83rem"> — '
                f'{detail[:120]}{"..." if len(detail) > 120 else ""}</span>'
            )
        st.markdown(
            f'<div style="padding:0.4rem 0; border-bottom:1px solid rgba(255,255,255,0.05);">'
            f'{icon} <strong style="color:#e6edf3">{section_name}</strong>{detail_str}</div>',
            unsafe_allow_html=True,
        )


def render_employment_audit(data: VisaDocumentExtraction):
    """Render a summary card for extracted employment document fields."""
    emp = data.employment

    # If no employment data at all, show a tip
    if not any([emp.employer_name, emp.job_title, emp.monthly_salary,
                emp.approved_leave_start, emp.approved_leave_end]):
        st.info(
            "No employment document data extracted. "
            "If this is an employment visa, upload HR letter, payslips, "
            "leave approval, or employment contract.",
            icon="💼",
        )
        return

    rows = [
        ("Employer Name",         emp.employer_name),
        ("Job Title",             emp.job_title),
        ("Monthly Salary",        emp.monthly_salary),
        ("Contract Type",         emp.contract_type),
        ("Approved Leave Start",  emp.approved_leave_start),
        ("Approved Leave End",    emp.approved_leave_end),
        ("Leave Approval Confirmed",
         "✅ Yes" if emp.leave_approval_confirmed is True
         else ("❌ Not found" if emp.leave_approval_confirmed is False else "🔘 Unknown")),
    ]

    col1, col2 = st.columns(2)
    half = len(rows) // 2
    for i, (label, value) in enumerate(rows):
        target_col = col1 if i < half else col2
        with target_col:
            display_val = value if value else "—"
            color = "#e6edf3" if value else "#8b949e"
            st.markdown(
                f'<div style="padding:0.35rem 0; border-bottom:1px solid rgba(255,255,255,0.05);">'
                f'<span style="color:#8b949e; font-size:0.82rem">{label}</span><br>'
                f'<span style="color:{color}; font-weight:500">{display_val}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )


def render_missing_documents(uploaded_files: dict):
    """Flag which of the 9 document slots were not uploaded."""
    all_labels = {label for _, label, _ in DOCUMENT_SLOTS}
    missing = all_labels - set(uploaded_files.keys())

    if not missing:
        st.success("✅ All 9 document categories were uploaded.")
        return
    for label in sorted(missing):
        st.warning(f"⚠️ Not uploaded: **{label}**")


def render_extracted_summary(data: VisaDocumentExtraction):
    rows = [
        ("Applicant Name",       data.passport.full_name or data.visa_form.applicant_name),
        ("Passport Number",      data.passport.passport_number),
        ("Date of Birth",        data.passport.date_of_birth),
        ("Passport Expiry",      data.passport.passport_expiry),
        ("Nationality",          data.passport.nationality),
        ("Employer",             data.employment.employer_name),
        ("Job Title",            data.employment.job_title),
        ("Monthly Salary",       data.employment.monthly_salary),
        ("Flight Departure",     data.flight.departure_date),
        ("Flight Return",        data.flight.return_date),
        ("Destination",          data.flight.destination_city or data.main_schengen_destination),
        ("Hotel Check-In",       data.hotel.check_in_date),
        ("Hotel Check-Out",      data.hotel.check_out_date),
        ("Hotel",                data.hotel.hotel_name),
        ("Insurance Coverage",   f"€{data.insurance.coverage_amount_eur:,.0f}"
                                 if data.insurance.coverage_amount_eur else None),
        ("Insurance Period",     f"{data.insurance.valid_from} → {data.insurance.valid_until}"
                                 if data.insurance.valid_from and data.insurance.valid_until else None),
    ]

    col1, col2 = st.columns(2)
    half = len(rows) // 2
    for i, (label, value) in enumerate(rows):
        target_col = col1 if i < half else col2
        with target_col:
            display_val = value if value else "—"
            color = "#e6edf3" if value else "#8b949e"
            st.markdown(
                f'<div style="padding:0.35rem 0; border-bottom:1px solid rgba(255,255,255,0.05);">'
                f'<span style="color:#8b949e; font-size:0.82rem">{label}</span><br>'
                f'<span style="color:{color}; font-weight:500">{display_val}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )


def render_deduction_breakdown(score_result):
    if not score_result.deductions_detail and not score_result.bonus_detail:
        return

    rows = ""
    for d in score_result.deductions_detail:
        capped = " (capped)" if d["was_capped"] else ""
        rows += (
            f"<tr><td>{_severity_badge(Severity(d['severity']))}</td>"
            f"<td>{d['issue_count']}</td>"
            f"<td>−{d['points_per_issue']:.0f} pts</td>"
            f"<td style='color:#f85149'>−{d['total_deducted']:.0f} pts{capped}</td></tr>"
        )
    for b in score_result.bonus_detail:
        rows += (
            f"<tr><td colspan='3' style='color:#3fb950'>✓ {b['reason']}</td>"
            f"<td style='color:#3fb950'>+{b['points_added']:.0f} pts</td></tr>"
        )

    st.markdown(
        f"""<table class="styled-table">
        <thead><tr>
            <th>Severity</th><th>Count</th><th>Per Issue</th><th>Total Impact</th>
        </tr></thead>
        <tbody>{rows}</tbody>
        </table>""",
        unsafe_allow_html=True,
    )


def render_status_log():
    """Show the live extraction status log in a collapsible section."""
    log = st.session_state.get("status_log", [])
    if not log:
        return
    with st.expander("📡 API Call Log", expanded=False):
        for entry in log:
            st.markdown(
                f'<div style="font-family:monospace; font-size:0.8rem; '
                f'color:#8b949e; padding:2px 0">{entry}</div>',
                unsafe_allow_html=True,
            )


# ---------------------------------------------------------------------------
# Main Review Orchestration
# ---------------------------------------------------------------------------

def run_review(
    api_key: str,
    uploaded_files: dict[str, list[tuple[str, bytes]]],
    model_id: str,
):
    """Orchestrate the full review pipeline and store results in session state."""
    st.session_state.review_result = None
    st.session_state.review_error = None
    st.session_state.review_traceback = None
    st.session_state.status_log = []

    status_log = st.session_state.status_log

    def _status(msg: str):
        status_log.append(msg)

    try:
        # Step 1 — Extract (all files, selected model, with fallback)
        with st.spinner("🔍 Analyzing documents with Gemini…"):
            extraction: VisaDocumentExtraction = extract_documents(
                api_key=api_key,
                uploaded_files=uploaded_files,
                model_id=model_id,
                max_retries=2,
                status_callback=_status,
            )

        # Step 2 — Validate
        with st.spinner("✅ Running deterministic validation checks…"):
            validation_issues: list[ValidationIssue] = run_validation(extraction)

        # Step 3 — Business check
        with st.spinner("🏢 Checking business purpose alignment…"):
            biz_result = check_business_alignment(extraction)

        # Step 4 — Combine issues & score
        all_issues = validation_issues + biz_result.issues
        cover_complete = _cover_letter_is_complete(extraction)
        leave_confirmed = _leave_is_confirmed(extraction)
        score_result = calculate_score(
            all_issues,
            cover_letter_complete=cover_complete,
            leave_confirmed=leave_confirmed,
        )

        st.session_state.review_result = {
            "extraction":     extraction,
            "issues":         all_issues,
            "biz_result":     biz_result,
            "score":          score_result,
            "uploaded_files": uploaded_files,
            "model_used":     model_id,
        }

    except Exception as exc:
        tb = traceback.format_exc()
        st.session_state.review_error = str(exc)
        # Store the full traceback separately so we can render it
        st.session_state.review_traceback = tb


# ---------------------------------------------------------------------------
# Main App Layout
# ---------------------------------------------------------------------------

def main():
    _init_session_state()

    # Sidebar — returns (files_dict, selected_model_id)
    uploaded_files, selected_model_id = render_sidebar()

    # Hero Banner
    st.markdown(
        """<div class="hero-banner">
            <div class="hero-title">🇪🇺 Schengen Visa File Review Bot</div>
            <div class="hero-subtitle">
                AI-powered document analysis · Cross-verification · Acceptance Likelihood Scoring
            </div>
        </div>""",
        unsafe_allow_html=True,
    )

    # Quick-status bar
    col_a, col_b, col_c = st.columns(3)
    total_files = sum(len(v) for v in uploaded_files.values())
    with col_a:
        api_ok = bool(st.session_state.api_key)
        st.markdown(
            f'<div class="stat-card">{"🟢" if api_ok else "🔴"} '
            f'<span style="color:#8b949e">API Key</span><br>'
            f'<strong style="color:{("#3fb950" if api_ok else "#f85149")}">'
            f'{"Configured" if api_ok else "Not Set"}</strong></div>',
            unsafe_allow_html=True,
        )
    with col_b:
        color = "#3fb950" if total_files >= 5 else ("#d29922" if total_files > 0 else "#f85149")
        st.markdown(
            f'<div class="stat-card">📎 '
            f'<span style="color:#8b949e">Files Uploaded</span><br>'
            f'<strong style="color:{color}">{total_files} file(s) '
            f'in {len(uploaded_files)} categories</strong></div>',
            unsafe_allow_html=True,
        )
    with col_c:
        result = st.session_state.review_result
        if result:
            score = result["score"].score
            color = "#3fb950" if score >= 85 else ("#d29922" if score >= 65 else "#f85149")
            model_used = result.get("model_used", "")
            st.markdown(
                f'<div class="stat-card">📊 '
                f'<span style="color:#8b949e">Last Score</span><br>'
                f'<strong style="color:{color}">{score:.0f}%</strong>'
                f'<span class="model-badge">{model_used}</span></div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div class="stat-card">📊 '
                '<span style="color:#8b949e">Last Score</span><br>'
                '<strong style="color:#8b949e">Pending</strong></div>',
                unsafe_allow_html=True,
            )

    st.markdown("<br>", unsafe_allow_html=True)

    # Run Review Button
    can_run = bool(st.session_state.api_key) and total_files >= 1
    run_col, _ = st.columns([1, 3])
    with run_col:
        if st.button(
            "🚀 Run Full Review",
            disabled=not can_run,
            use_container_width=True,
            type="primary",
        ):
            run_review(st.session_state.api_key, uploaded_files, selected_model_id)

    if not can_run:
        if not st.session_state.api_key:
            st.info("👈 Enter your Gemini API key in the sidebar to begin.", icon="🔑")
        elif total_files == 0:
            st.info("👈 Upload at least one document in the sidebar to begin.", icon="📎")

    # Status log (API call trace)
    render_status_log()

    # Error display — friendly, no raw traceback shown to the user
    if st.session_state.review_error:
        err_msg = str(st.session_state.review_error)
        # Shorten extremely long error strings
        display_msg = err_msg.split("\n")[0][:300] if err_msg else "Unknown error"
        st.error(
            "❌ **Review could not be completed.**\n\n"
            f"{display_msg}\n\n"
            "**Please try again.** If the problem persists, check your API key and quota in the sidebar.",
            icon="❌",
        )

    if not st.session_state.review_result:
        return

    result = st.session_state.review_result
    extraction: VisaDocumentExtraction = result["extraction"]
    issues: list[ValidationIssue] = result["issues"]
    score_result: ScoreResult = result["score"]
    biz_result = result["biz_result"]
    score = score_result.score

    st.divider()

    # ── SECTION 1: Big Status Card ─────────────────────────────────────
    if score >= 85:
        card_cls  = "green"
        card_icon = "🟢"
        card_title = "File Ready to Submit"
        card_sub   = "Your documents are well-prepared. Review the minor notes below before submission."
    elif score >= 65:
        card_cls  = "yellow"
        card_icon = "🟡"
        card_title = "Minor Corrections Needed"
        card_sub   = "A few issues were detected. Fix them before submitting your application."
    else:
        card_cls  = "red"
        card_icon = "🔴"
        card_title = "High Rejection Risk"
        card_sub   = "Serious problems were found. Resolving them is essential before applying."

    st.markdown(
        f'<div class="status-card {card_cls}">'  
        f'<div class="status-icon">{card_icon}</div>'
        f'<div class="status-title">{card_title}</div>'
        f'<div class="status-score">{score:.0f}%</div>'
        f'<div class="status-sub">{card_sub}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Issue count summary
    c1, c2, c3, c4 = st.columns(4)
    for col, label, count, color in [
        (c1, "🔴 Critical", score_result.critical_count, "#f85149"),
        (c2, "🟠 High",     score_result.high_count,     "#d29922"),
        (c3, "🔵 Medium",   score_result.medium_count,   "#4F8EF7"),
        (c4, "🟢 Low",       score_result.low_count,      "#3fb950"),
    ]:
        col.markdown(
            f'<div class="stat-card"><div class="stat-number" style="color:{color}">{count}</div>'
            f'<div class="stat-label">{label}</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── SECTION 2: Actionable Fix Checklist ────────────────────────────
    if issues:
        st.markdown('<div class="section-header">📋 How to Fix — Action Checklist</div>',
                    unsafe_allow_html=True)
        _sev_order = {Severity.CRITICAL: 0, Severity.HIGH: 1, Severity.MEDIUM: 2, Severity.LOW: 3}
        for issue in sorted(issues, key=lambda i: _sev_order.get(i.severity, 9)):
            sev_cls  = issue.severity.value.lower()
            sev_label = {
                "critical": "🔴 Critical — Must Fix / ضروري",
                "high":     "🟠 High Priority / مهم",
                "medium":   "🔵 Moderate / متوسط",
                "low":      "🟢 Minor / ثانوي",
            }.get(sev_cls, sev_cls)
            doc_hint = f" — <em>{issue.document_name}</em>" if issue.document_name else ""
            st.markdown(
                f'<div class="fix-card {sev_cls}">'
                f'<span class="fix-badge {sev_cls}">{sev_label}</span>{doc_hint}<br>'
                f'<strong style="color:#e6edf3">{issue.field_name.replace("_", " ").title()}</strong><br>'
                f'<span style="color:#8b949e; font-size:0.9rem">{issue.recommended_fix}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
    else:
        st.success("✅ No issues detected — your file looks great!")

    st.divider()

    # ── SECTION 3: PDF Download ───────────────────────────────────────
    if _PDF_AVAILABLE:
        pdf_bytes = _build_pdf_report(extraction, issues, score_result, biz_result)
        st.download_button(
            label="📥 Download Audit Summary PDF",
            data=pdf_bytes,
            file_name="schengen_visa_audit.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
    else:
        st.info("📥 Install `fpdf2` to enable PDF download: `pip install fpdf2`", icon="ℹ️")

    st.divider()

    # ── SECTION 4: Document Completeness ─────────────────────────────
    st.markdown('<div class="section-header">📎 Document Completeness Check</div>',
                unsafe_allow_html=True)
    render_missing_documents(result["uploaded_files"])

    st.divider()

    # ── SECTION 5: Extracted Data (collapsed) ────────────────────────
    with st.expander("🔍 Extracted Data Summary", expanded=False):
        render_extracted_summary(extraction)
        if extraction.raw_extraction_notes:
            st.info(extraction.raw_extraction_notes, icon="ℹ️")

    # ── SECTION 6: Detailed Issues Table (collapsed) ─────────────────
    with st.expander("⚠️ Full Validation Issues Table", expanded=False):
        render_error_table(issues)

    st.divider()

    # ── SECTION 7: Cover Letter ───────────────────────────────────
    st.markdown('<div class="section-header">✉️ Cover Letter Audit</div>',
                unsafe_allow_html=True)
    render_cover_letter_audit(extraction)

    st.divider()

    # ── SECTION 8: Employment ─────────────────────────────────────
    st.markdown('<div class="section-header">💼 Employment Documents Audit</div>',
                unsafe_allow_html=True)
    render_employment_audit(extraction)

    # ── SECTION 9: Business Alignment ───────────────────────────
    if biz_result.is_business_visa:
        st.divider()
        st.markdown('<div class="section-header">🏢 Business Purpose Alignment</div>',
                    unsafe_allow_html=True)
        b_col1, b_col2 = st.columns(2)
        with b_col1:
            st.markdown("**Field of Work (Commercial Registry / Tax Card)**")
            st.info(biz_result.declared_field_of_work or "— Not found —")
        with b_col2:
            st.markdown("**Trip Purpose (Invitation / Cover Letter)**")
            st.info(biz_result.invitation_topic or "— Not found —")
        if biz_result.fields_match:
            st.success("✅ Business purpose aligns with applicant's professional sector.")
        else:
            st.error(f"❌ Sector mismatch: {biz_result.mismatch_description}", icon="⚠️")

    # ── Footer ────────────────────────────────────────────────────────────
    st.markdown(
        '<div style="text-align:center; color:#8b949e; font-size:0.8rem; margin-top:3rem; '
        'padding-top:2rem; border-top:1px solid rgba(255,255,255,0.07);">'
        'Schengen Visa File Review Bot · Powered by Gemini · '
        'Results are advisory only and do not constitute legal advice.'
        '</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# PDF Report Builder (module-level so main() can call it)
# ---------------------------------------------------------------------------

def _build_pdf_report(
    extraction: VisaDocumentExtraction,
    issues: list[ValidationIssue],
    score_result: ScoreResult,
    biz_result,
) -> bytes:
    """
    Build a plain, printable PDF audit summary using fpdf2.
    Returns raw PDF bytes ready for st.download_button.
    """
    from fpdf import FPDF  # type: ignore[import]

    def _row(p: FPDF, h: float, txt: str) -> None:  # type: ignore[type-arg]
        """Write one line using multi_cell so cursor always advances."""
        p.multi_cell(0, h, txt)

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 18)
    _row(pdf, 10, "Schengen Visa Application - Audit Summary")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(100, 100, 100)
    _row(pdf, 6, "Generated by Schengen Visa File Review Bot | Advisory only")
    pdf.ln(4)

    # Score line
    score_label = f"{score_result.score:.0f}% - {score_result.badge_label}"
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(0, 0, 0)
    _row(pdf, 8, f"Acceptance Likelihood Score: {score_label}")
    pdf.ln(3)

    # Applicant info
    pdf.set_font("Helvetica", "B", 12)
    _row(pdf, 7, "Applicant Information")
    pdf.set_font("Helvetica", "", 10)
    name = extraction.passport.full_name or extraction.visa_form.applicant_name or "N/A"
    passport_num = extraction.passport.passport_number or "N/A"
    _row(pdf, 6, f"Name: {name}")
    _row(pdf, 6, f"Passport No.: {passport_num}")
    pdf.ln(4)

    # Issues
    pdf.set_font("Helvetica", "B", 12)
    _row(pdf, 7, f"Issues Found: {len(issues)}")
    _sev_order = {Severity.CRITICAL: 0, Severity.HIGH: 1, Severity.MEDIUM: 2, Severity.LOW: 3}
    for issue in sorted(issues, key=lambda i: _sev_order.get(i.severity, 9)):
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(180, 50, 50)
        heading = f"[{issue.severity.value}] {issue.document_name} - {issue.field_name}"
        _row(pdf, 6, heading[:120])
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(50, 50, 50)
        _row(pdf, 5, f"   Fix: {issue.recommended_fix}")
        pdf.ln(1)

    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)
    pdf.set_font("Helvetica", "I", 8)
    _row(pdf, 5, "Results are advisory only and do not constitute legal or immigration advice.")

    return bytes(pdf.output())




if __name__ == "__main__":
    main()

