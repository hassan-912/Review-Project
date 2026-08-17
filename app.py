"""
app.py
======
Schengen Visa File Review Bot — Streamlit Main Dashboard

Entry point for the application. Handles:
  - Gemini API key input (securely stored in session state)
  - Model Selection dropdown (with 429 fallback handled in extractor.py)
  - Multi-file upload for all 9 Schengen document categories
  - Fast MD5 hash caching of uploaded files & Force Refresh escape hatch
  - Live execution pipeline with single st.status & pure CSS shimmer skeleton
  - 4-step horizontal visual progress stepper
  - Human-readable executive summary without technical jargon
  - Pinned top-3 urgent action checklist ("What to do next")
  - Document-grouped actionable fix checklist with bilingual severity filter pills
  - Precision Travel Date Cross-Check Matrix & Timeline Audit across Hotel, Flight, Visa Form, Cover Letter, Leave & Insurance
  - Collapsed technical details & PDF report download
"""

from __future__ import annotations

import hashlib
import traceback
import textwrap
from datetime import date, datetime
from typing import Optional, Any

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
# Custom CSS — Premium dark-glass aesthetic, Stepper, Shimmer & Precision Cards
# ---------------------------------------------------------------------------
st.html(
"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

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
    padding: 2.2rem 2rem;
    margin-bottom: 1.5rem;
    backdrop-filter: blur(10px);
}
.hero-title {
    font-size: 2.2rem; font-weight: 800;
    background: linear-gradient(135deg, #4F8EF7, #a78bfa);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text; margin: 0;
}
.hero-subtitle { color: #8b949e; font-size: 1rem; margin-top: 0.4rem; }

/* Status Cards */
.status-card {
    border-radius: 20px; padding: 2.2rem 2rem;
    text-align: center; border: 2px solid;
    backdrop-filter: blur(10px); margin-bottom: 1.5rem;
}
.status-card.green  { background: rgba(35,134,54,0.12);  border-color: #3fb950; }
.status-card.yellow { background: rgba(187,128,9,0.12);  border-color: #d29922; }
.status-card.red    { background: rgba(218,54,51,0.12);  border-color: #f85149; }
.status-icon { font-size: 3.2rem; margin-bottom: 0.4rem; }
.status-title { font-size: 1.6rem; font-weight: 700; margin-bottom: 0.25rem; }
.status-card.green  .status-title { color: #3fb950; }
.status-card.yellow .status-title { color: #d29922; }
.status-card.red    .status-title { color: #f85149; }
.status-score { font-size: 3.6rem; font-weight: 800; line-height: 1; }
.status-card.green  .status-score { color: #3fb950; }
.status-card.yellow .status-score { color: #d29922; }
.status-card.red    .status-score { color: #f85149; }
.status-sub { font-size: 0.95rem; color: #8b949e; margin-top: 0.5rem; }

/* Stepper Component */
.stepper-container {
    display: flex;
    justify-content: space-between;
    align-items: center;
    position: relative;
    margin: 1rem 0 1.75rem 0;
    padding: 1.2rem 1.8rem;
    background: rgba(22, 27, 34, 0.9);
    border: 1px solid rgba(79, 142, 247, 0.2);
    border-radius: 16px;
    backdrop-filter: blur(10px);
}
.stepper-track {
    position: absolute;
    top: 38px;
    left: 8%;
    right: 8%;
    height: 3px;
    background: rgba(255, 255, 255, 0.1);
    z-index: 1;
}
.stepper-track-progress {
    position: absolute;
    top: 38px;
    left: 8%;
    height: 3px;
    background: linear-gradient(90deg, #4F8EF7, #3fb950);
    z-index: 2;
    transition: width 0.4s ease;
}
.step-node {
    position: relative;
    z-index: 3;
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    min-width: 90px;
}
.step-circle {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 700;
    font-size: 0.9rem;
    transition: all 0.3s ease;
    margin-bottom: 0.4rem;
}
.step-node.completed .step-circle {
    background: #238636;
    color: #ffffff;
    box-shadow: 0 0 12px rgba(35, 134, 54, 0.6);
    border: 2px solid #3fb950;
}
.step-node.active .step-circle {
    background: #1f6feb;
    color: #ffffff;
    box-shadow: 0 0 15px rgba(79, 142, 247, 0.7);
    border: 2px solid #58a6ff;
    animation: pulse-ring 1.6s infinite;
}
.step-node.pending .step-circle {
    background: rgba(33, 38, 45, 0.9);
    color: #8b949e;
    border: 2px solid rgba(255, 255, 255, 0.15);
}
.step-title {
    font-size: 0.8rem;
    font-weight: 600;
    color: #e6edf3;
    white-space: nowrap;
}
.step-node.pending .step-title { color: #8b949e; }
.step-node.active .step-title { color: #58a6ff; font-weight: 700; }
.step-node.completed .step-title { color: #3fb950; }

@keyframes pulse-ring {
    0% { transform: scale(0.96); box-shadow: 0 0 0 0 rgba(79, 142, 247, 0.7); }
    70% { transform: scale(1.04); box-shadow: 0 0 0 8px rgba(79, 142, 247, 0); }
    100% { transform: scale(0.96); box-shadow: 0 0 0 0 rgba(79, 142, 247, 0); }
}

/* Skeleton Shimmer Loading */
@keyframes shimmer {
    0% { background-position: -200% 0; }
    100% { background-position: 200% 0; }
}
.skeleton-card {
    background: linear-gradient(90deg, rgba(22, 27, 34, 0.8) 25%, rgba(79, 142, 247, 0.15) 50%, rgba(22, 27, 34, 0.8) 75%);
    background-size: 200% 100%;
    animation: shimmer 1.8s infinite;
    border-radius: 16px;
    border: 1px solid rgba(79, 142, 247, 0.2);
    padding: 2rem;
    margin: 1.5rem 0;
}
.skeleton-line {
    height: 14px;
    margin-bottom: 12px;
    border-radius: 6px;
    background: rgba(255, 255, 255, 0.07);
}

/* Natural Language Summary Card */
.nl-summary-card {
    background: linear-gradient(135deg, rgba(22, 27, 34, 0.95) 0%, rgba(28, 38, 54, 0.9) 100%);
    border: 1px solid rgba(79, 142, 247, 0.3);
    border-radius: 16px;
    padding: 1.6rem 1.8rem;
    margin-bottom: 1.5rem;
    backdrop-filter: blur(12px);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25);
}
.nl-lead {
    font-size: 1.05rem;
    line-height: 1.65;
    color: #f0f6fc;
    margin-bottom: 1rem;
}
.nl-highlight {
    background: rgba(79, 142, 247, 0.15);
    color: #58a6ff;
    padding: 2px 8px;
    border-radius: 6px;
    font-weight: 600;
}
.nl-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 0.75rem;
    margin-top: 1.2rem;
    padding-top: 1rem;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
}
.nl-grid-item {
    background: rgba(13, 17, 23, 0.6);
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 10px;
    padding: 0.75rem 1rem;
}
.nl-grid-label {
    font-size: 0.75rem;
    color: #8b949e;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 2px;
}
.nl-grid-val {
    font-size: 0.95rem;
    font-weight: 600;
    color: #f0f6fc;
}

/* Urgent Action Items ("What to do next") */
.urgent-container {
    background: rgba(22, 27, 34, 0.9);
    border: 1px solid rgba(248, 81, 73, 0.35);
    border-radius: 16px;
    padding: 1.4rem 1.6rem;
    margin-bottom: 1.5rem;
}
.urgent-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 1rem;
}
.urgent-title {
    font-size: 1.15rem;
    font-weight: 700;
    color: #f85149;
    display: flex;
    align-items: center;
    gap: 8px;
}
.urgent-item {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    background: rgba(13, 17, 23, 0.7);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-left: 4px solid #f85149;
    border-radius: 10px;
    padding: 0.9rem 1.1rem;
    margin-bottom: 0.6rem;
}
.urgent-item.high { border-left-color: #d29922; }
.urgent-item.medium { border-left-color: #4F8EF7; }
.urgent-item.low { border-left-color: #3fb950; }
.urgent-num {
    background: rgba(248, 81, 73, 0.15);
    color: #f85149;
    width: 26px;
    height: 26px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 700;
    font-size: 0.85rem;
    flex-shrink: 0;
}
.urgent-item.high .urgent-num { background: rgba(210, 153, 34, 0.15); color: #d29922; }
.urgent-item.medium .urgent-num { background: rgba(79, 142, 247, 0.15); color: #4F8EF7; }
.urgent-item.low .urgent-num { background: rgba(63, 185, 80, 0.15); color: #3fb950; }
.urgent-text-title {
    font-weight: 600;
    font-size: 0.95rem;
    color: #f0f6fc;
}
.urgent-text-desc {
    font-size: 0.86rem;
    color: #8b949e;
    margin-top: 3px;
    line-height: 1.4;
}

/* Travel Dates Precision Matrix */
.timeline-card {
    background: rgba(22, 27, 34, 0.85);
    border: 1px solid rgba(79, 142, 247, 0.2);
    border-radius: 14px;
    padding: 1.25rem 1.5rem;
    margin-bottom: 1.25rem;
}
.timeline-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    gap: 0.9rem;
    margin-top: 0.8rem;
}
.timeline-doc-box {
    background: rgba(13, 17, 23, 0.7);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    padding: 0.9rem 1.1rem;
}
.timeline-doc-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-weight: 600;
    font-size: 0.88rem;
    color: #e6edf3;
    margin-bottom: 0.5rem;
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    padding-bottom: 0.4rem;
}
.timeline-dates {
    font-family: monospace;
    font-size: 0.92rem;
    color: #58a6ff;
    font-weight: 600;
}
.timeline-detail {
    font-size: 0.8rem;
    color: #8b949e;
    margin-top: 0.3rem;
}
.sync-pill {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 0.72rem;
    font-weight: 700;
}
.sync-pill.synced   { background: rgba(63, 185, 80, 0.2);  color: #3fb950; }
.sync-pill.gap      { background: rgba(210, 153, 34, 0.2); color: #d29922; }
.sync-pill.conflict { background: rgba(218, 54, 51, 0.2);  color: #f85149; }
.sync-pill.missing  { background: rgba(139, 148, 158, 0.2); color: #8b949e; }

/* Cached badge */
.cached-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(56, 139, 253, 0.15);
    border: 1px solid rgba(56, 139, 253, 0.35);
    color: #58a6ff;
    border-radius: 20px;
    padding: 4px 12px;
    font-size: 0.82rem;
    font-weight: 600;
    margin-left: 8px;
}

/* Fix Cards */
.fix-card {
    background: rgba(22,27,34,0.85); border-radius: 12px;
    border: 1px solid rgba(255,255,255,0.08); padding: 1.1rem 1.4rem;
    margin-bottom: 0.75rem;
}
.fix-card.critical { border-left: 4px solid #f85149; }
.fix-card.high     { border-left: 4px solid #d29922; }
.fix-card.medium   { border-left: 4px solid #4F8EF7; }
.fix-card.low      { border-left: 4px solid #3fb950; }
.fix-badge { display:inline-block; border-radius:6px; padding:2px 9px; font-size:0.75rem; font-weight:700; margin-bottom:0.4rem; }
.fix-badge.critical { background:rgba(218,54,51,0.2); color:#f85149; }
.fix-badge.high     { background:rgba(210,153,34,0.2); color:#d29922; }
.fix-badge.medium   { background:rgba(79,142,247,0.2); color:#4F8EF7; }
.fix-badge.low      { background:rgba(63,185,80,0.2);  color:#3fb950; }

.section-header {
    font-size: 1.15rem; font-weight: 700; color: #e6edf3;
    border-left: 3px solid #4F8EF7;
    padding-left: 0.75rem; margin: 1.6rem 0 1rem;
}
.stat-card { background: rgba(22,27,34,0.8); border: 1px solid rgba(79,142,247,0.15); border-radius: 12px; padding: 1rem; text-align: center; }
.stat-number { font-size: 2rem; font-weight: 700; color: #4F8EF7; }
.stat-label  { font-size: 0.8rem; color: #8b949e; margin-top: 0.25rem; }

.styled-table { width: 100%; border-collapse: collapse; font-size: 0.875rem; border-radius: 12px; overflow: hidden; }
.styled-table th { background: rgba(79,142,247,0.15); color: #4F8EF7; padding: 10px 14px; text-align: left; font-weight: 600; border-bottom: 1px solid rgba(79,142,247,0.2); }
.styled-table td { padding: 10px 14px; border-bottom: 1px solid rgba(255,255,255,0.05); color: #e6edf3; vertical-align: top; }
.styled-table tr:hover td { background: rgba(79,142,247,0.05); }

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
    border-radius: 10px; padding: 0.9rem 1.1rem; margin: 0.75rem 0;
    color: #8b949e; font-size: 0.875rem;
}
.stButton > button {
    background: linear-gradient(135deg, #4F8EF7, #673ab7);
    color: white; border: none; border-radius: 10px;
    font-weight: 600; font-size: 1rem; padding: 0.6rem 1.8rem;
    transition: opacity 0.2s;
}
.stButton > button:hover { opacity: 0.88; }
</style>
"""
)

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

_KEY_TO_LABEL = {key: label for key, label, _ in DOCUMENT_SLOTS}


# ---------------------------------------------------------------------------
# Session State & Caching Initialization
# ---------------------------------------------------------------------------
def _init_session_state():
    defaults = {
        "api_key": "",
        "selected_model": AVAILABLE_MODELS[0],
        "review_result": None,
        "review_error": None,
        "review_traceback": None,
        "status_log": [],
        "review_cache": {},      # { md5_hash: result_dict }
        "is_cached_result": False,
        "active_filter": "All | الكل",
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def _compute_upload_hash(uploaded_files: dict[str, list[tuple[str, bytes]]], model_id: str) -> str:
    """
    Compute a deterministic MD5 hash across all uploaded file contents,
    file names, and selected model ID for fast instant caching.
    """
    hasher = hashlib.md5()
    hasher.update(model_id.encode("utf-8"))
    for category in sorted(uploaded_files.keys()):
        hasher.update(category.encode("utf-8"))
        file_list = uploaded_files[category]
        for fname, fbytes in sorted(file_list, key=lambda x: x[0]):
            hasher.update(fname.encode("utf-8"))
            hasher.update(fbytes)
    return hasher.hexdigest()


# ---------------------------------------------------------------------------
# Visual Stepper & Skeleton Shimmer Helpers
# ---------------------------------------------------------------------------
def render_pipeline_stepper(active_step: int = 1):
    """
    Render a horizontal 4-step visual progress stepper.
    active_step: 1 (Extract), 2 (Validate), 3 (Business), 4 (Score), 5 (Done)
    """
    steps = [
        ("1", "🔍 Extract AI", "Multimodal Analysis"),
        ("2", "⚖️ Validate", "Deterministic Rules"),
        ("3", "🏢 Purpose", "Business & Leave"),
        ("4", "🎯 Scoring", "Likelihood & Fixes"),
    ]

    progress_pct = max(0, min(100, int(((active_step - 1) / (len(steps) - 1)) * 84))) if active_step <= 4 else 84

    nodes_html = ""
    for i, (num, title, subtitle) in enumerate(steps, start=1):
        if i < active_step or active_step > 4:
            state_cls = "completed"
            icon = "✓"
        elif i == active_step:
            state_cls = "active"
            icon = num
        else:
            state_cls = "pending"
            icon = num

        nodes_html += f"""
        <div class="step-node {state_cls}">
            <div class="step-circle">{icon}</div>
            <div class="step-title">{title}</div>
            <div style="font-size:0.68rem; color:#8b949e;">{subtitle}</div>
        </div>
        """

    stepper_html = f"""
    <div class="stepper-container">
        <div class="stepper-track"></div>
        <div class="stepper-track-progress" style="width: {progress_pct}%;"></div>
        {nodes_html}
    </div>
    """
    st.html(stepper_html)


def render_skeleton_loader() -> str:
    """Return pure CSS shimmer animation placeholder block."""
    return """
    <div class="skeleton-card">
        <div class="skeleton-line" style="width: 35%; height: 26px; margin-bottom: 18px;"></div>
        <div class="skeleton-line" style="width: 90%;"></div>
        <div class="skeleton-line" style="width: 75%;"></div>
        <div class="skeleton-line" style="width: 82%;"></div>
        <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-top: 24px;">
            <div class="skeleton-line" style="height: 65px;"></div>
            <div class="skeleton-line" style="height: 65px;"></div>
            <div class="skeleton-line" style="height: 65px;"></div>
            <div class="skeleton-line" style="height: 65px;"></div>
        </div>
    </div>
    """


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
def render_sidebar() -> tuple[dict[str, list[tuple[str, bytes]]], str]:
    with st.sidebar:
        st.html(
"## ⚙️ Configuration")

        # API Key
        api_key = st.text_input(
            "Gemini API Key",
            type="password",
            value=st.session_state.api_key,
            placeholder="AIza...",
            help="Your Google Gemini API key. Never shared or stored.",
        )
        st.session_state.api_key = api_key

        if api_key:
            st.success("✓ API key configured", icon="🔑")
        else:
            st.warning("Enter your Gemini API key to begin", icon="⚠️")

        # Model Selector
        st.markdown("### 🤖 Model Selection")
        _MODEL_LABELS = {
            "gemini-2.0-flash-lite": "gemini-2.0-flash-lite  ✦ Primary — Free tier",
            "gemini-2.5-flash":      "gemini-2.5-flash  — Higher capability (Fallback 1)",
            "gemini-2.0-flash":      "gemini-2.0-flash  — Fast multi-token (Fallback 2)",
        }
        model_options = AVAILABLE_MODELS
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
            help="The app tries models in priority order and auto-skips on 404/429.",
        )
        selected_model_id = model_options[model_display.index(selected_display)]
        st.session_state.selected_model = selected_model_id

        fallback_chain = " → ".join(AVAILABLE_MODELS)
        st.html(
            f'<div class="info-box">'
            f'Active: <span class="model-badge">{selected_model_id}</span><br>'
            f'Fallback chain: <code style="color:#8b949e; font-size:0.77rem">{fallback_chain}</code>'
            f'</div>'
)

        st.divider()

        # File Uploaders
        st.html(
"## 📎 Upload Documents")
        st.html(
            '<div class="info-box">Upload all applicable documents. '
            'Each slot accepts <strong>multiple files</strong>.</div>'
)

        uploaded_files: dict[str, list[tuple[str, bytes]]] = {}

        for key, label, help_text in DOCUMENT_SLOTS:
            files = st.file_uploader(
                label,
                type=["pdf", "jpg", "jpeg", "png", "webp"],
                key=f"upload_{key}",
                help=help_text,
                accept_multiple_files=True,
            )
            if files:
                uploaded_files[label] = [(f.name, f.getvalue()) for f in files]

        st.divider()
        file_count = sum(len(v) for v in uploaded_files.values())
        st.html(
f'<div style="color:#8b949e; font-size:0.75rem;">'
            f'{file_count} file(s) loaded across {len(uploaded_files)} categories.<br>'
            f'Files processed in-memory — never stored on disk.<br>'
            f'© 2024 Schengen Visa Review Bot</div>'
)

    return uploaded_files, selected_model_id


# ---------------------------------------------------------------------------
# Natural Language Summary & Non-Technical Executive Briefing
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Field Name Humanization Map
# Converts raw Pydantic field identifiers to readable audit labels.
# Used in every user-facing issues table and action card.
# ---------------------------------------------------------------------------
_FIELD_LABELS: dict[str, str] = {
    "passport_number":                    "Passport Number",
    "full_name":                          "Applicant Full Name",
    "date_of_birth":                      "Date of Birth",
    "passport_expiry":                    "Passport Expiry Date",
    "applicant_name":                     "Applicant Name",
    "departure_date":                     "Departure Date",
    "return_date":                        "Return Date",
    "departure_date / return_date":       "Departure / Return Dates",
    "check_in_date":                      "Hotel Check-In Date",
    "check_out_date":                     "Hotel Check-Out Date",
    "valid_from":                         "Insurance Start Date",
    "valid_until":                        "Insurance End Date",
    "coverage_amount_eur":                "Medical Coverage Amount",
    "insured_passport_number":            "Insured Passport Number (Insurance)",
    "purpose_of_visit":                   "Purpose of Visit (Cover Letter)",
    "funding_source":                     "Funding Source (Cover Letter)",
    "ties_to_home_country":               "Ties to Home Country (Cover Letter)",
    "attached_documents_listed":          "Documents List (Cover Letter)",
    "employer_name in cover letter":      "Employer Referenced in Cover Letter",
    "employer_name vs company_name":      "Employer / Company Name Alignment",
    "main_schengen_destination":          "Main Schengen Destination",
    "travel_cities":                      "Itinerary / Hotel City",
    "leave_approval_confirmed":           "Leave Approval Letter",
    "approved_leave_start vs flight departure": "Approved Leave Start vs Departure",
    "approved_leave_end vs flight return":      "Approved Leave End vs Return",
    "departure_date vs check_in_date":    "Flight Departure vs Hotel Check-In",
    "return_date vs check_out_date":      "Flight Return vs Hotel Check-Out",
    "valid_from vs departure_date":       "Insurance Start vs Departure Date",
    "valid_until vs return_date":         "Insurance End vs Return Date",
    "intended_arrival vs departure_date": "Visa Entry Date vs Flight Departure",
    "intended_departure vs return_date":  "Visa Exit Date vs Flight Return",
}


def _humanize_field(field_name: str) -> str:
    """Return a user-friendly label for a raw Pydantic field identifier."""
    return _FIELD_LABELS.get(field_name, field_name.replace("_", " ").title())


def render_natural_language_summary(
    extraction: VisaDocumentExtraction,
    score_result: ScoreResult,
    biz_result: Any,
    issues: list[ValidationIssue],
    uploaded_files: dict,
):
    """
    Generate an empathetic, crystal-clear, plain-English summary of the visa file.
    Zero technical jargon, database column names, or raw schemas.
    """
    name = (
        extraction.passport.full_name
        or (extraction.visa_form.applicant_name if extraction.visa_form else None)
        or "The applicant"
    )
    destination = (
        extraction.main_schengen_destination
        or extraction.flight.destination_city
        or (extraction.visa_form.destination_country if extraction.visa_form else None)
        or "the Schengen Area"
    )
    purpose = (
        (extraction.visa_form.purpose_of_journey if extraction.visa_form else None)
        or extraction.cover_letter.purpose_of_visit
        or ("Business" if getattr(biz_result, "is_business_visa", False) else "Tourism / General Visit")
    )

    dep_date = extraction.flight.departure_date or "an upcoming departure date"
    ret_date = extraction.flight.return_date or "scheduled return date"

    # Trip duration
    duration_str = ""
    if extraction.flight.departure_date and extraction.flight.return_date:
        try:
            d1 = datetime.strptime(extraction.flight.departure_date, "%Y-%m-%d")
            d2 = datetime.strptime(extraction.flight.return_date, "%Y-%m-%d")
            days = (d2 - d1).days
            if days > 0:
                duration_str = f" for a planned duration of **{days} days** ({dep_date} to {ret_date})"
        except Exception:
            duration_str = f" from **{dep_date}** to **{ret_date}**"
    elif extraction.flight.departure_date:
        duration_str = f" starting on **{dep_date}**"

    # Cities
    cities = extraction.travel_cities or []
    if not cities and extraction.hotel.city:
        cities = [extraction.hotel.city]
    cities_str = f" with planned stops in **{', '.join(cities[:4])}**" if cities else ""

    # Score narrative
    score = score_result.score
    if score >= 85:
        verdict_text = (
            f"Your application file is in **strong shape** with an estimated "
            f"acceptance likelihood of <span class='nl-highlight'>{score:.0f}% ({score_result.badge_label})</span>. "
            f"Your documents show strong consistency across identity and travel bookings."
        )
    elif score >= 65:
        verdict_text = (
            f"Your application file has a **moderate likelihood score of <span class='nl-highlight'>{score:.0f}% ({score_result.badge_label})</span>**. "
            f"While the core itinerary is present, a few document adjustments should be made prior to submission."
        )
    else:
        verdict_text = (
            f"Your file currently has a **high risk of refusal with a score of <span class='nl-highlight'>{score:.0f}% ({score_result.badge_label})</span>**. "
            f"Critical document mismatches were detected that need immediate correction before booking an appointment."
        )

    # Key highlights
    total_docs = sum(len(v) for v in uploaded_files.values())
    insurance_val = (
        f"€{extraction.insurance.coverage_amount_eur:,.0f}"
        if extraction.insurance.coverage_amount_eur
        else "Missing/Unverified"
    )
    hotel_name = extraction.hotel.hotel_name or "Confirmed Booking"
    employer = extraction.employment.employer_name or "Declared"

    st.html(
f"""
        <div class="nl-summary-card">
            <div style="font-size: 0.8rem; font-weight: 700; color: #58a6ff; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 0.5rem;">
                📋 Executive Summary & File Overview
            </div>
            <div class="nl-lead">
                <strong>{name}</strong> is applying for a <strong>{purpose}</strong> visa to <strong>{destination}</strong>{duration_str}{cities_str}.
                <br><br>
                {verdict_text}
            </div>
            <div class="nl-grid">
                <div class="nl-grid-item">
                    <div class="nl-grid-label">Primary Destination</div>
                    <div class="nl-grid-val">🇪🇺 {destination}</div>
                </div>
                <div class="nl-grid-item">
                    <div class="nl-grid-label">Medical Insurance</div>
                    <div class="nl-grid-val">🛡️ {insurance_val}</div>
                </div>
                <div class="nl-grid-item">
                    <div class="nl-grid-label">Accommodation</div>
                    <div class="nl-grid-val">🏨 {hotel_name[:20]}</div>
                </div>
                <div class="nl-grid-item">
                    <div class="nl-grid-label">Documents Analyzed</div>
                    <div class="nl-grid-val">📎 {total_docs} File(s) in {len(uploaded_files)} Categories</div>
                </div>
            </div>
        </div>
        """)


    # Tourism & Destination Assessment block
    _TOURISM_TIERS = {
        # Major world-class tourist cities
        "paris", "rome", "barcelona", "amsterdam", "vienna", "prague", "berlin",
        "lisbon", "athens", "budapest", "florence", "venice", "madrid", "milan",
        "munich", "zurich", "geneva", "brussels", "stockholm", "copenhagen",
        "santorini", "mykonos", "dubrovnik", "dubrovnik", "salzburg", "innsbruck",
        "nice", "lyon", "strasbourg", "porto", "krakow", "warsaw", "reykjavik",
        "luxembourg",
    }
    dest_lower = (destination or "").lower().strip()
    hotel_city_lower = (extraction.hotel.city or "").lower().strip()
    check_city = dest_lower or hotel_city_lower

    if check_city in _TOURISM_TIERS:
        tourism_icon = "✅"
        tourism_verdict = (
            f"**{destination}** is a well-established, high-traffic Schengen tourist destination "
            f"with strong consular infrastructure. Visa officers are experienced with this itinerary type. "
            f"No destination-related concerns were detected."
        )
        tourism_color = "#3fb950"
    elif check_city:
        tourism_icon = "🔵"
        tourism_verdict = (
            f"**{destination}** is a valid Schengen destination. Ensure your itinerary and hotel "
            f"reservation clearly justify the choice of this city. Consider adding a day-by-day "
            f"travel plan if not already included to strengthen the application."
        )
        tourism_color = "#58a6ff"
    else:
        tourism_icon = "🔘"
        tourism_verdict = (
            "Destination city could not be determined from the uploaded documents. "
            "Ensure the hotel reservation and flight booking clearly state the destination city."
        )
        tourism_color = "#8b949e"

    # Hotel-in-cover-letter advisory
    hotel_in_cl = extraction.cover_letter.attached_documents_listed
    hotel_name_cl = extraction.hotel.hotel_name or ""
    # We check whether the cover letter mentions accommodation
    cl_mentions_hotel = bool(
        extraction.cover_letter.destination_country_mentioned
        and hotel_name_cl
    )
    hotel_advisory_html = ""
    if hotel_name_cl and not cl_mentions_hotel:
        hotel_advisory_html = (
            f'<div style="margin-top:0.75rem; padding:0.6rem 0.9rem; border-left:3px solid #d29922; '
            f'background:rgba(210,153,34,0.08); border-radius:0 6px 6px 0; font-size:0.88rem; color:#e3b341;">'
            f'<strong>Advisory:</strong> The hotel reservation ({hotel_name_cl}) is not explicitly '
            f'referenced in your Cover Letter. It is recommended to mention your accommodation details '
            f'to maintain full consistency across documents.'
            f'</div>'
        )

    st.html(
f"""
        <div style="margin-top:1.25rem; padding:1rem 1.2rem;
                    background:rgba(22,27,34,0.7; border:1px solid rgba(48,54,61,0.8);
                    border-radius:10px;">
            <div style="font-size:0.78rem; font-weight:700; color:#8b949e;
                        text-transform:uppercase; letter-spacing:0.7px; margin-bottom:0.6rem;">
                🗺️ Tourism &amp; Destination Assessment
            </div>
            <div style="font-size:0.92rem; color:{tourism_color}; margin-bottom:0.3rem;">
                {tourism_icon} {tourism_verdict}
            </div>
            {hotel_advisory_html}
        </div>
        """)


# ---------------------------------------------------------------------------
# Pinned Top Priority Action Steps
# ---------------------------------------------------------------------------
def render_urgent_action_plan(issues: list[ValidationIssue]):
    """
    Spotlight the top 3 most critical and actionable fixes required before
    embassy submission, in MG Assistant Bot voice.
    """
    if not issues:
        st.html(
"""
            <div class="urgent-container" style="border-color: rgba(63, 185, 80, 0.4;">
                <div class="urgent-header">
                    <div class="urgent-title" style="color: #3fb950;">
                        🎉 All Systems Clear — Ready to Submit!
                    </div>
                </div>
                <div style="color: #8b949e; font-size: 0.9rem;">
                    No validation issues or inconsistencies were found across your uploaded documents.
                    Make sure to bring original printed copies of all files to your visa appointment.
                </div>
            </div>
            """)
        return

    _sev_order = {Severity.CRITICAL: 0, Severity.HIGH: 1, Severity.MEDIUM: 2, Severity.LOW: 3}
    sorted_issues = sorted(issues, key=lambda i: _sev_order.get(i.severity, 9))
    top_3 = sorted_issues[:3]

    items_html = ""
    for idx, issue in enumerate(top_3, start=1):
        sev_cls = issue.severity.value.lower()
        title = _humanize_field(issue.field_name)   # human-readable — no raw identifiers
        doc = f" ({issue.document_name})" if issue.document_name else ""
        items_html += f"""
        <div class="urgent-item {sev_cls}">
            <div class="urgent-num">{idx}</div>
            <div style="flex-grow: 1;">
                <div class="urgent-text-title">{title}{doc}</div>
                <div class="urgent-text-desc">{issue.recommended_fix}</div>
            </div>
        </div>
        """

    st.html(
f"""
        <div class="urgent-container">
            <div class="urgent-header">
                <div class="urgent-title">
                    ⚡ Top Priority Action Steps — Before Embassy Submission
                </div>
                <div style="font-size: 0.8rem; color: #8b949e; font-weight: 500;">
                    {len(issues)} total issue(s) detected · Top {len(top_3)} urgent shown
                </div>
            </div>
            {items_html}
        </div>
        """)


# ---------------------------------------------------------------------------
# Precision Travel Date Cross-Check Matrix & Timeline Audit
# ---------------------------------------------------------------------------
def _parse_dt(d_str: Optional[str]) -> Optional[date]:
    if not d_str:
        return None
    for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d %b %Y"]:
        try:
            return datetime.strptime(d_str.strip(), fmt).date()
        except ValueError:
            continue
    return None


def render_travel_date_timeline(extraction: VisaDocumentExtraction, issues: list[ValidationIssue]):
    """
    A dedicated, highly visual Travel Date Precision & Timeline Alignment component.
    Cross-verifies exact dates from:
      - ✈️ Flight Reservation (Departure & Return)
      - 🏨 Hotel Reservation (Check-in & Check-out + Nights + Hotel Name)
      - 📋 Visa Application Form (Intended Arrival & Departure)
      - ✉️ Cover Letter (Dates Mentioned)
      - 💼 Employment Documents (Approved Leave Start & End)
      - 🛡️ Travel Insurance (Valid From & Valid Until)
    """
    st.html('<div class="section-header">📅 Travel Dates & Timeline Alignment Audit</div>')

    flight_dep = _parse_dt(extraction.flight.departure_date)
    flight_ret = _parse_dt(extraction.flight.return_date)
    hotel_in   = _parse_dt(extraction.hotel.check_in_date)
    hotel_out  = _parse_dt(extraction.hotel.check_out_date)
    visa_arr   = _parse_dt(getattr(extraction.visa_form, "intended_arrival", None))
    visa_dep   = _parse_dt(getattr(extraction.visa_form, "intended_departure", None))
    ins_from   = _parse_dt(extraction.insurance.valid_from)
    ins_until  = _parse_dt(extraction.insurance.valid_until)
    leave_from = _parse_dt(extraction.employment.approved_leave_start)
    leave_to   = _parse_dt(extraction.employment.approved_leave_end)

    # 1. Flight status
    flight_dates_str = f"{extraction.flight.departure_date or 'Not Found'} → {extraction.flight.return_date or 'Not Found'}"
    flight_nights = (flight_ret - flight_dep).days if (flight_dep and flight_ret) else None
    flight_detail = f"Duration: {flight_nights} days" if flight_nights is not None else "Round-trip dates"
    flight_sync = '<span class="sync-pill synced">Reference Trip</span>' if (flight_dep and flight_ret) else '<span class="sync-pill gap">Incomplete</span>'

    # 2. Hotel status
    hotel_dates_str = f"{extraction.hotel.check_in_date or 'Not Found'} → {extraction.hotel.check_out_date or 'Not Found'}"
    hotel_nights = (hotel_out - hotel_in).days if (hotel_in and hotel_out) else None
    hotel_name_city = f"{extraction.hotel.hotel_name or 'Hotel'}" + (f", {extraction.hotel.city}" if extraction.hotel.city else "")

    if not hotel_in or not hotel_out:
        hotel_sync = '<span class="sync-pill missing">Not Extracted</span>'
    elif flight_dep and flight_ret:
        if hotel_in >= flight_dep and hotel_out <= flight_ret:
            hotel_sync = '<span class="sync-pill synced">✓ Covers Flights</span>'
        else:
            hotel_sync = '<span class="sync-pill conflict">⚠️ Mismatch</span>'
    else:
        hotel_sync = '<span class="sync-pill synced">Extracted</span>'

    hotel_detail = f"{hotel_nights} nights in {hotel_name_city[:24]}" if hotel_nights else hotel_name_city[:28]

    # 3. Visa Form status
    visa_dates_str = f"{getattr(extraction.visa_form, 'intended_arrival', None) or 'Not Found'} → {getattr(extraction.visa_form, 'intended_departure', None) or 'Not Found'}"
    if not visa_arr or not visa_dep:
        visa_sync = '<span class="sync-pill missing">Not Extracted</span>'
        visa_detail = "Application form dates"
    elif flight_dep and flight_ret:
        diff_arr = abs((visa_arr - flight_dep).days)
        diff_dep = abs((visa_dep - flight_ret).days)
        if diff_arr <= 1 and diff_dep <= 1:
            visa_sync = '<span class="sync-pill synced">✓ Matches Flights</span>'
            visa_detail = "Exact match with flight tickets"
        else:
            visa_sync = '<span class="sync-pill gap">⚠️ Differs</span>'
            visa_detail = f"Arrival diff: {diff_arr}d, Exit diff: {diff_dep}d"
    else:
        visa_sync = '<span class="sync-pill synced">Extracted</span>'
        visa_detail = "Application form declared stay"

    # 4. Insurance status
    ins_dates_str = f"{extraction.insurance.valid_from or 'Not Found'} → {extraction.insurance.valid_until or 'Not Found'}"
    if not ins_from or not ins_until:
        ins_sync = '<span class="sync-pill missing">Not Extracted</span>'
        ins_detail = "Coverage validity window"
    elif flight_dep and flight_ret:
        if ins_from <= flight_dep and ins_until >= flight_ret:
            buffer_days = (ins_until - flight_ret).days
            ins_sync = '<span class="sync-pill synced">✓ Full Trip Protected</span>'
            ins_detail = f"Active during travel (+{buffer_days}d buffer)"
        else:
            ins_sync = '<span class="sync-pill conflict">🚨 Coverage Gap</span>'
            ins_detail = "Policy does not cover full trip!"
    else:
        ins_sync = '<span class="sync-pill synced">Policy Active</span>'
        ins_detail = "Insurance period recorded"

    # 5. Employment Leave status
    leave_dates_str = f"{extraction.employment.approved_leave_start or 'Not Found'} → {extraction.employment.approved_leave_end or 'Not Found'}"
    if not leave_from or not leave_to:
        leave_sync = '<span class="sync-pill missing">No Leave Dates</span>'
        leave_detail = "Optional for tourists / business owners"
    elif flight_dep and flight_ret:
        if leave_from <= flight_dep and leave_to >= flight_ret:
            leave_sync = '<span class="sync-pill synced">✓ Brackets Travel</span>'
            leave_detail = "Approved leave covers flight window"
        else:
            leave_sync = '<span class="sync-pill conflict">⚠️ Leave Gap</span>'
            leave_detail = "Leave ends before return or starts after departure"
    else:
        leave_sync = '<span class="sync-pill synced">Leave Recorded</span>'
        leave_detail = "HR leave dates"

    # 6. Cover Letter Mention status
    cl_mentioned = extraction.cover_letter.dates_mentioned
    cl_dates_str = "Confirmed in Letter" if cl_mentioned is True else ("Not Mentioned" if cl_mentioned is False else "—")
    cl_sync = '<span class="sync-pill synced">✓ Explicit</span>' if cl_mentioned else '<span class="sync-pill gap">⚠️ Review</span>'
    cl_detail = "Personal statement dates cross-referenced"

    # Render Cards
    st.html(
f"""
        <div class="timeline-card">
            <div style="color: #8b949e; font-size: 0.88rem; margin-bottom: 0.5rem;">
                Cross-document verification between hotel reservations, flight itineraries, official visa forms, and insurance policies.
            </div>
            <div class="timeline-grid">
                <div class="timeline-doc-box">
                    <div class="timeline-doc-header">
                        <span>✈️ Flight Reservation</span>
                        {flight_sync}
                    </div>
                    <div class="timeline-dates">{flight_dates_str}</div>
                    <div class="timeline-detail">{flight_detail}</div>
                </div>

                <div class="timeline-doc-box">
                    <div class="timeline-doc-header">
                        <span>🏨 Hotel Booking</span>
                        {hotel_sync}
                    </div>
                    <div class="timeline-dates">{hotel_dates_str}</div>
                    <div class="timeline-detail">{hotel_detail}</div>
                </div>

                <div class="timeline-doc-box">
                    <div class="timeline-doc-header">
                        <span>📋 Visa Application Form</span>
                        {visa_sync}
                    </div>
                    <div class="timeline-dates">{visa_dates_str}</div>
                    <div class="timeline-detail">{visa_detail}</div>
                </div>

                <div class="timeline-doc-box">
                    <div class="timeline-doc-header">
                        <span>🛡️ Travel Insurance</span>
                        {ins_sync}
                    </div>
                    <div class="timeline-dates">{ins_dates_str}</div>
                    <div class="timeline-detail">{ins_detail}</div>
                </div>

                <div class="timeline-doc-box">
                    <div class="timeline-doc-header">
                        <span>💼 Approved Leave</span>
                        {leave_sync}
                    </div>
                    <div class="timeline-dates">{leave_dates_str}</div>
                    <div class="timeline-detail">{leave_detail}</div>
                </div>

                <div class="timeline-doc-box">
                    <div class="timeline-doc-header">
                        <span>✉️ Cover Letter Dates</span>
                        {cl_sync}
                    </div>
                    <div class="timeline-dates">{cl_dates_str}</div>
                    <div class="timeline-detail">{cl_detail}</div>
                </div>
            </div>
        </div>
        """
)


# ---------------------------------------------------------------------------
# Document-Grouped Fix Checklist with Bilingual Filter Bar
# ---------------------------------------------------------------------------
def render_fix_checklist(issues: list[ValidationIssue], score_result: ScoreResult):
    """
    Render issues grouped by document with expanders and persistent severity filter pills.
    """
    st.html('<div class="section-header">🛠️ Discrepancy &amp; Correction Audit — Document-by-Document</div>')

    if not issues:
        st.success("✅ No issues detected across your documents — everything looks consistent!", icon="🎉")
        return

    # Filter Bar
    filter_options = [
        f"All | الكل ({len(issues)})",
        f"🔴 Critical | حرج ({score_result.critical_count})",
        f"🟠 High | مهم ({score_result.high_count})",
        f"🔵 Medium | متوسط ({score_result.medium_count})",
        f"🟢 Low | ثانوي ({score_result.low_count})",
    ]

    # Use st.pills if available, else fallback to radio
    if hasattr(st, "pills"):
        selected_pill = st.pills(
            "Filter by severity",
            options=filter_options,
            default=filter_options[0],
            label_visibility="collapsed",
        )
    elif hasattr(st, "segmented_control"):
        selected_pill = st.segmented_control(
            "Filter by severity",
            options=filter_options,
            default=filter_options[0],
            label_visibility="collapsed",
        )
    else:
        selected_pill = st.radio(
            "Filter by severity",
            options=filter_options,
            index=0,
            horizontal=True,
            label_visibility="collapsed",
        )

    # Determine filter severity
    target_sev: Optional[Severity] = None
    if selected_pill:
        if "Critical" in selected_pill:
            target_sev = Severity.CRITICAL
        elif "High" in selected_pill:
            target_sev = Severity.HIGH
        elif "Medium" in selected_pill:
            target_sev = Severity.MEDIUM
        elif "Low" in selected_pill:
            target_sev = Severity.LOW

    # Filter issues
    filtered_issues = [i for i in issues if target_sev is None or i.severity == target_sev]

    if not filtered_issues:
        st.info(f"No issues found under the '{selected_pill}' severity filter.", icon="ℹ️")
        return

    # Group by document name
    grouped: dict[str, list[ValidationIssue]] = {}
    for issue in filtered_issues:
        doc_key = issue.document_name or "General / Multi-Document"
        grouped.setdefault(doc_key, []).append(issue)

    _sev_order = {Severity.CRITICAL: 0, Severity.HIGH: 1, Severity.MEDIUM: 2, Severity.LOW: 3}

    # Render an expander for each document group
    for doc_name, doc_issues in grouped.items():
        doc_issues.sort(key=lambda i: _sev_order.get(i.severity, 9))
        highest_sev = doc_issues[0].severity
        sev_tag = {
            Severity.CRITICAL: "🔴 Critical",
            Severity.HIGH:     "🟠 High",
            Severity.MEDIUM:   "🔵 Medium",
            Severity.LOW:      "🟢 Low",
        }.get(highest_sev, "")

        # Auto-expand if critical or high
        should_expand = highest_sev in [Severity.CRITICAL, Severity.HIGH]

        with st.expander(f"📁 {doc_name}  ·  {len(doc_issues)} issue(s) [{sev_tag}]", expanded=should_expand):
            for issue in doc_issues:
                sev_cls = issue.severity.value.lower()
                sev_label = {
                    "critical": "🔴 Critical — Must Fix / ضروري",
                    "high":     "🟠 High Priority / مهم",
                    "medium":   "🔵 Moderate / متوسط",
                    "low":      "🟢 Minor Advisory / ثانوي",
                }.get(sev_cls, sev_cls)

                field_title = _humanize_field(issue.field_name)  # no raw identifiers shown

                st.html(
f"""
                    <div class="fix-card {sev_cls}">
                        <span class="fix-badge {sev_cls}">{sev_label}</span>
                        <div style="font-weight:700; color:#f0f6fc; font-size:0.95rem; margin-top:2px;">
                            {field_title}
                        </div>
                        <div style="color:#8b949e; font-size:0.88rem; margin: 4px 0 6px 0; line-height:1.45;">
                            {issue.recommended_fix}
                        </div>
                    </div>
                    """)


# ---------------------------------------------------------------------------
# Collapsed Full Technical Issues Table & Extracted Data
# ---------------------------------------------------------------------------
def _severity_badge(severity: Severity) -> str:
    cls_map = {
        Severity.CRITICAL: "sev-critical",
        Severity.HIGH:     "sev-high",
        Severity.MEDIUM:   "sev-medium",
        Severity.LOW:      "sev-low",
    }
    return f'<span class="{cls_map.get(severity, "sev-low")}">{severity.value}</span>'


def render_error_table(issues: list[ValidationIssue]):
    if not issues:
        st.success("✅ No validation issues detected!", icon="🎉")
        return

    rows = ""
    for issue in issues:
        found = str(issue.found_value) if issue.found_value else "❌ Missing Data (Not Extracted)"
        issue_desc = _humanize_field(issue.field_name)   # human-readable, no raw identifiers
        rows += (
            f"<tr>"
            f"<td>{issue.document_name}</td>"
            f"<td>{issue_desc}</td>"
            f"<td style='color:#e6edf3'>{found}</td>"
            f"<td style='color:#8b949e'>{issue.expected_value}</td>"
            f"<td>{_severity_badge(issue.severity)}</td>"
            f"</tr>"
        )

    st.html(
f"""<table class="styled-table">
            <thead><tr>
                <th>Document</th><th>Issue / Discrepancy Detected</th><th>Found Value</th>
                <th>Expected / Correct Value</th><th>Severity</th>
            </tr></thead>
            <tbody>{rows}</tbody>
        </table>""")


def render_cover_letter_audit(data: VisaDocumentExtraction):
    cl = data.cover_letter

    def _icon(value) -> str:
        if value is None:
            return "🔘"
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
        st.html(
f'<div style="padding:0.4rem 0; border-bottom:1px solid rgba(255,255,255,0.05);">'
            f'{icon} <strong style="color:#e6edf3">{section_name}</strong>{detail_str}</div>'
)


def render_employment_audit(data: VisaDocumentExtraction):
    emp = data.employment
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
            st.html(
f'<div style="padding:0.35rem 0; border-bottom:1px solid rgba(255,255,255,0.05);">'
                f'<span style="color:#8b949e; font-size:0.82rem">{label}</span><br>'
                f'<span style="color:{color}; font-weight:500">{display_val}</span>'
                f'</div>'
)


def render_missing_documents(uploaded_files: dict):
    all_labels = {label for _, label, _ in DOCUMENT_SLOTS}
    missing = all_labels - set(uploaded_files.keys())

    if not missing:
        st.success("✅ All 9 document categories were uploaded.")
        return
    for label in sorted(missing):
        st.warning(f"⚠️ Not uploaded: **{label}**")


def render_extracted_summary(data: VisaDocumentExtraction):
    rows = [
        ("Applicant Name",       data.passport.full_name or (data.visa_form.applicant_name if data.visa_form else None)),
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
            st.html(
f'<div style="padding:0.35rem 0; border-bottom:1px solid rgba(255,255,255,0.05);">'
                f'<span style="color:#8b949e; font-size:0.82rem">{label}</span><br>'
                f'<span style="color:{color}; font-weight:500">{display_val}</span>'
                f'</div>'
)


def render_status_log():
    log = st.session_state.get("status_log", [])
    if not log:
        return
    with st.expander("📡 API Call Log", expanded=False):
        for entry in log:
            st.html(
f'<div style="font-family:monospace; font-size:0.8rem; '
                f'color:#8b949e; padding:2px 0">{entry}</div>'
)


# ---------------------------------------------------------------------------
# Main Review Pipeline Execution with st.status & Caching
# ---------------------------------------------------------------------------
def run_review(
    api_key: str,
    uploaded_files: dict[str, list[tuple[str, bytes]]],
    model_id: str,
    force_refresh: bool = False,
):
    """
    Execute the review pipeline with instant MD5 caching, single st.status context manager,
    and CSS skeleton placeholder animations.
    """
    current_hash = _compute_upload_hash(uploaded_files, model_id)
    cache = st.session_state.get("review_cache", {})

    # 1. Instant Cache Check
    if not force_refresh and current_hash in cache:
        st.session_state.review_result = cache[current_hash]
        st.session_state.is_cached_result = True
        st.session_state.review_error = None
        st.session_state.review_traceback = None
        return

    # 2. Fresh Run
    st.session_state.is_cached_result = False
    st.session_state.review_result = None
    st.session_state.review_error = None
    st.session_state.review_traceback = None
    st.session_state.status_log = []

    status_log = st.session_state.status_log

    def _status(msg: str):
        status_log.append(msg)

    # Skeleton placeholder during computation
    skeleton_placeholder = st.empty()
    skeleton_placeholder.markdown(render_skeleton_loader(), unsafe_allow_html=True)

    try:
        with st.status("🔍 Reviewing your visa file...", expanded=True) as status:
            # Step 1: Multimodal Extraction
            status.update(label="📄 Step 1/4: Analyzing documents...", state="running")
            extraction: VisaDocumentExtraction = extract_documents(
                api_key=api_key,
                uploaded_files=uploaded_files,
                model_id=model_id,
                max_retries=2,
                status_callback=_status,
            )
            st.write("✓ Extracted applicant, itinerary, hotel, flight, insurance, and employment data.")

            # Step 2: Deterministic Validation
            status.update(label="⚖️ Step 2/4: Cross-verifying passport & travel dates...", state="running")
            validation_issues: list[ValidationIssue] = run_validation(extraction)
            st.write(f"✓ Checked 11 deterministic validation rules ({len(validation_issues)} issue(s) flagged).")

            # Step 3: Business Purpose Check
            status.update(label="🏢 Step 3/4: Assessing trip purpose & employment alignment...", state="running")
            biz_result = check_business_alignment(extraction)
            st.write("✓ Professional sector and trip purpose evaluated.")

            # Step 4: Combine Issues & Score
            status.update(label="🎯 Step 4/4: Calculating acceptance likelihood score...", state="running")
            all_issues = validation_issues + biz_result.issues
            cover_complete = _cover_letter_is_complete(extraction)
            leave_confirmed = _leave_is_confirmed(extraction)
            score_result = calculate_score(
                all_issues,
                cover_letter_complete=cover_complete,
                leave_confirmed=leave_confirmed,
            )
            st.write(f"✓ Acceptance score calculated: {score_result.score:.0f}% ({score_result.badge_label}).")

            status.update(label="✅ Visa file review completed successfully!", state="complete", expanded=False)

        # Clear skeleton loader
        skeleton_placeholder.empty()

        # Save to session & cache
        result_payload = {
            "extraction":     extraction,
            "issues":         all_issues,
            "biz_result":     biz_result,
            "score":          score_result,
            "uploaded_files": uploaded_files,
            "model_used":     model_id,
        }
        st.session_state.review_result = result_payload
        cache[current_hash] = result_payload
        st.session_state.review_cache = cache

    except Exception as exc:
        skeleton_placeholder.empty()
        tb = traceback.format_exc()
        st.session_state.review_error = str(exc)
        st.session_state.review_traceback = tb


# ---------------------------------------------------------------------------
# Main App Layout
# ---------------------------------------------------------------------------
def main():
    _init_session_state()

    # Sidebar — returns (files_dict, selected_model_id)
    uploaded_files, selected_model_id = render_sidebar()

    # Hero Banner
    st.html(
"""<div class="hero-banner">
            <div class="hero-title">🇪🇺 Schengen Visa File Review Bot</div>
            <div class="hero-subtitle">
                MG-powered document analysis · 
            </div>
        </div>"""
)

    # Quick-status bar
    col_a, col_b, col_c = st.columns(3)
    total_files = sum(len(v) for v in uploaded_files.values())
    with col_a:
        api_ok = bool(st.session_state.api_key)
        st.html(
f'<div class="stat-card">{"🟢" if api_ok else "🔴"} '
            f'<span style="color:#8b949e">API Key</span><br>'
            f'<strong style="color:{("#3fb950" if api_ok else "#f85149")}">'
            f'{"Configured" if api_ok else "Not Set"}</strong></div>'
)
    with col_b:
        color = "#3fb950" if total_files >= 5 else ("#d29922" if total_files > 0 else "#f85149")
        st.html(
f'<div class="stat-card">📎 '
            f'<span style="color:#8b949e">Files Uploaded</span><br>'
            f'<strong style="color:{color}">{total_files} file(s) '
            f'in {len(uploaded_files)} categories</strong></div>'
)
    with col_c:
        result = st.session_state.review_result
        if result:
            score = result["score"].score
            color = "#3fb950" if score >= 85 else ("#d29922" if score >= 65 else "#f85149")
            model_used = result.get("model_used", "")
            cached_indicator = " ⚡" if st.session_state.is_cached_result else ""
            st.html(
f'<div class="stat-card">📊 '
                f'<span style="color:#8b949e">Last Score</span><br>'
                f'<strong style="color:{color}">{score:.0f}%{cached_indicator}</strong>'
                f'<span class="model-badge">{model_used}</span></div>'
)
        else:
            st.html(
'<div class="stat-card">📊 '
                '<span style="color:#8b949e">Last Score</span><br>'
                '<strong style="color:#8b949e">Pending</strong></div>'
)

    st.html("<br>")

    # Review Action Buttons with Caching Badges
    can_run = bool(st.session_state.api_key) and total_files >= 1

    btn_col1, btn_col2, _ = st.columns([1.5, 1.2, 2.5])
    with btn_col1:
        run_clicked = st.button(
            "🚀 Run Full Review",
            disabled=not can_run,
            use_container_width=True,
            type="primary",
        )
    with btn_col2:
        refresh_clicked = st.button(
            "🔄 Force Refresh",
            disabled=not can_run,
            use_container_width=True,
            help="Ignore cached results and perform a fresh Gemini API analysis.",
        )

    if run_clicked:
        run_review(st.session_state.api_key, uploaded_files, selected_model_id, force_refresh=False)
    elif refresh_clicked:
        run_review(st.session_state.api_key, uploaded_files, selected_model_id, force_refresh=True)

    if not can_run:
        if not st.session_state.api_key:
            st.info("👈 Enter your Gemini API key in the sidebar to begin.", icon="🔑")
        elif total_files == 0:
            st.info("👈 Upload at least one document in the sidebar to begin.", icon="📎")

    # Render API status log if any
    render_status_log()

    # Friendly Error Handling
    if st.session_state.review_error:
        err_msg = str(st.session_state.review_error)
        display_msg = err_msg.split("\n")[0][:300] if err_msg else "Unknown error"
        st.error(
            "❌ **Review could not be completed.**\n\n"
            f"{display_msg}\n\n"
            "**Please try again.** If the problem persists, verify your API key and quotas in the sidebar.",
            icon="❌",
        )

    if not st.session_state.review_result:
        return

    # Extract state payload
    result = st.session_state.review_result
    extraction: VisaDocumentExtraction = result["extraction"]
    issues: list[ValidationIssue] = result["issues"]
    score_result: ScoreResult = result["score"]
    biz_result = result["biz_result"]
    score = score_result.score

    # Visual Pipeline Stepper (Completed state = 5)
    render_pipeline_stepper(active_step=5)

    # Cached notification badge
    if st.session_state.is_cached_result:
        st.html(
'<div style="margin-bottom: 1rem;">'
            '<span class="cached-badge">⚡ Serving cached result (Instant)</span>'
            '<span style="color:#8b949e; font-size:0.8rem; margin-left:8px;">'
            'Identical files detected. Click "Force Refresh" above to re-query Gemini.</span>'
            '</div>'
)

    # ── SECTION 1: Status & Likelihood Score ───────────────────────────
    if score >= 85:
        card_cls   = "green"
        card_icon  = "🟢"
        card_title = "File Ready to Submit"
        card_sub   = "Your documents are well-prepared. Review the minor notes below before final submission."
    elif score >= 65:
        card_cls   = "yellow"
        card_icon  = "🟡"
        card_title = "Minor Corrections Needed"
        card_sub   = "A few inconsistencies were detected. Resolve them to maximize your approval chances."
    else:
        card_cls   = "red"
        card_icon  = "🔴"
        card_title = "High Rejection Risk"
        card_sub   = "Critical problems or date conflicts were found. Resolving them is essential before applying."

    st.html(
f'<div class="status-card {card_cls}">'
        f'<div class="status-icon">{card_icon}</div>'
        f'<div class="status-title">{card_title}</div>'
        f'<div class="status-score">{score:.0f}%</div>'
        f'<div class="status-sub">{card_sub}</div>'
        f'</div>'
)

    # ── SECTION 2: Natural Language Summary ────────────────────────────
    render_natural_language_summary(extraction, score_result, biz_result, issues, result["uploaded_files"])

    # ── SECTION 3: Pinned Top-3 Urgent Actions ─────────────────────────
    render_urgent_action_plan(issues)

    # ── SECTION 4: Precision Travel Date Cross-Check Matrix ────────────
    render_travel_date_timeline(extraction, issues)

    # ── SECTION 5: Document-Grouped Fix Checklist with Filter Pills ───
    render_fix_checklist(issues, score_result)

    st.divider()

    # ── SECTION 6: PDF Download ───────────────────────────────────────
    if _PDF_AVAILABLE:
        pdf_bytes = _build_pdf_report(extraction, issues, score_result, biz_result)
        st.download_button(
            label="📥 Download Comprehensive Audit Summary PDF",
            data=pdf_bytes,
            file_name="schengen_visa_audit.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
    else:
        st.info("📥 Install `fpdf2` to enable PDF download: `pip install fpdf2`", icon="ℹ️")

    st.divider()

    # ── SECTION 7: Document Completeness ──────────────────────────────
    st.html('<div class="section-header">📎 Document Completeness Check</div>')
    render_missing_documents(result["uploaded_files"])

    st.divider()

    # ── SECTION 8: Cover Letter & Employment Audits ───────────────────
    c_col1, c_col2 = st.columns(2)
    with c_col1:
        st.html('<div class="section-header">✉️ Cover Letter Audit</div>')
        render_cover_letter_audit(extraction)
    with c_col2:
        st.html('<div class="section-header">💼 Employment Documents Audit</div>')
        render_employment_audit(extraction)

    # Business Alignment if applicable
    if getattr(biz_result, "is_business_visa", False):
        st.divider()
        st.html('<div class="section-header">🏢 Business Purpose Alignment</div>')
        b_col1, b_col2 = st.columns(2)
        with b_col1:
            st.html(
"**Field of Work (Commercial Registry / Tax Card)**")
            st.info(biz_result.declared_field_of_work or "— Not found —")
        with b_col2:
            st.markdown("**Trip Purpose (Invitation / Cover Letter)**")
            st.info(biz_result.invitation_topic or "— Not found —")
        if biz_result.fields_match:
            st.success("✅ Business purpose aligns with applicant's professional sector.")
        else:
            st.error(f"❌ Sector mismatch: {biz_result.mismatch_description}", icon="⚠️")

    st.divider()

    # ── SECTION 9: Advanced Technical Details (Collapsed for Power Users)
    with st.expander("🔍 Extracted Data Summary (Detailed)", expanded=False):
        render_extracted_summary(extraction)
        if extraction.raw_extraction_notes:
            st.info(extraction.raw_extraction_notes, icon="ℹ️")

    with st.expander("🛠️ Advanced Technical Details (Full Issues Table)", expanded=False):
        render_error_table(issues)

    # ── Footer ────────────────────────────────────────────────────────
    st.html(
        '<div style="text-align:center; color:#8b949e; font-size:0.8rem; margin-top:3rem; '
        'padding-top:2rem; border-top:1px solid rgba(255,255,255,0.07);">'
        'Schengen Visa File Review Bot · Powered by Gemini · '
        'Results are advisory only and do not constitute legal or consular advice.'
        '</div>'
)


# ---------------------------------------------------------------------------
# PDF Report Builder
# ---------------------------------------------------------------------------
def _build_pdf_report(
    extraction: VisaDocumentExtraction,
    issues: list[ValidationIssue],
    score_result: ScoreResult,
    biz_result: Any,
) -> bytes:
    """
    Build a clean, printable PDF audit summary using fpdf2.
    """
    from fpdf import FPDF

    def _row(p: FPDF, h: float, txt: str) -> None:
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
    name = extraction.passport.full_name or (extraction.visa_form.applicant_name if extraction.visa_form else None) or "N/A"
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
