"""MG visual system. Native controls retain keyboard and screen-reader support."""
from __future__ import annotations
import json
import streamlit as st
from i18n import t

CSS = """
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Sans+Arabic:wght@400;500;600;700&display=swap');
:root {
 --brand:#0067DA; --ink:#0B1F3A; --page:#F3F7FC; --muted:#50607A; --border:#D9E2EF; --surface:#FFFFFF;
 --critical-bg:#FBE9E7; --critical:#8C1D18; --high-bg:#FFF0DC; --high:#8A4300;
 --medium-bg:#FFF6CC; --medium:#6B5400; --low-bg:#E8EEF2; --low:#34454F; --success-bg:#E1F2EC; --success:#0B4A3E;
}
.stApp {background:var(--page); color:var(--ink);}
.stMainBlockContainer {max-width:1250px; padding-top:2rem; padding-bottom:3rem;}
.stApp,.stApp input,.stApp textarea,.stApp button,.stApp h1,.stApp h2,.stApp h3,.stApp [data-testid="stMarkdownContainer"] {font-family:'IBM Plex Sans',sans-serif;}
header[data-testid="stHeader"] {display:none;}
[class*="st-key-card_"],[class*="st-key-slot_"] {background:var(--surface); border-color:var(--border); border-radius:12px;}
h1,h2,h3 {color:var(--ink);}
h1 {font-size:2.2rem !important; line-height:1.2;}
.stCaption,[data-testid="stCaptionContainer"] {color:var(--muted);}
[data-testid="stVerticalBlockBorderWrapper"]>div {background:var(--surface); border-color:var(--border); border-radius:12px;}
[data-testid="stTextInput"] input,button,[role="checkbox"],[role="radio"] {min-height:44px;}
.stTextInput [data-baseweb="input"] {border:1px solid var(--border); border-radius:8px;}
button:focus-visible,input:focus-visible {outline:3px solid var(--brand); outline-offset:3px;}
.brand-mark {display:inline-flex; align-items:center; justify-content:center; border-radius:10px; background:var(--brand); color:var(--surface); width:46px; height:46px; font-weight:700;}
.eyebrow {color:var(--brand); font-weight:600; font-size:.82rem;}
.muted {color:var(--muted);}
.pill {display:inline-block; border-radius:999px; padding:.25rem .65rem; font-weight:600; font-size:.8rem;}
.pill.critical {background:var(--critical-bg); color:var(--critical);}
.pill.high,.pill.gap {background:var(--high-bg); color:var(--high);}
.pill.medium,.pill.check {background:var(--medium-bg); color:var(--medium);}
.pill.low,.pill.waiting {background:var(--low-bg); color:var(--low);}
.pill.success,.pill.aligned,.pill.done {background:var(--success-bg); color:var(--success);}
.pill.in_progress,.pill.added {background:var(--page); color:var(--brand);}
.score-number {font-size:4rem; font-weight:700; line-height:1.2; color:var(--ink);}
.stepper {display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; margin:1rem 0;}
.step {border:1px solid var(--border); border-radius:12px; background:var(--surface); padding:1rem;}
.step.active {border-color:var(--brand);}
.step h4 {margin:.45rem 0; font-size:1rem;}
.skeleton {padding:1.5rem; border:1px solid var(--border); border-radius:12px; background:var(--surface);}
.skeleton i {display:block; height:16px; margin:14px 0; border-radius:6px; background:linear-gradient(90deg,var(--page),var(--border),var(--page)); background-size:200% 100%; animation:shimmer 1.5s infinite;}
@keyframes shimmer {to {background-position:-200% 0;}}
.timeline {width:100%; border-collapse:collapse; font-size:.9rem;}
.timeline td,.timeline th {border-bottom:1px solid var(--border); padding:.7rem .3rem; text-align:start;}
.timeline th {color:var(--muted); font-weight:500;}
.ltr {direction:ltr; unicode-bidi:isolate; display:inline-block;}
.st-key-email input,.st-key-login_email input,.st-key-signup_email input,.st-key-reset_email input,[data-testid="stNumberInput"] input {direction:ltr; text-align:left;}
[data-testid="stFileUploaderDropzone"] {border:1px dashed var(--border); border-radius:10px;}
[class*="st-key-slot_filled"] [data-testid="stFileUploaderDropzone"] {border:1px solid var(--brand);}
[data-testid="stFileUploaderDropzoneInstructions"] {display:none;}
[data-testid="stFileUploaderDropzone"] button {font-size:0;}
[data-testid="stFileUploaderDropzone"] button::after {font-size:.9rem;}
@media(max-width:640px) {.stepper {grid-template-columns:1fr 1fr;} h1 {font-size:1.8rem !important;}}
@media(prefers-reduced-motion:reduce) {.skeleton i {animation:none;}}
"""


def direction_css(lang):
    if lang == "ar":
        return """
        .stMain {direction:rtl; text-align:right;}
        .stApp,.stApp input,.stApp textarea,.stApp button,.stApp h1,.stApp h2,.stApp h3,.stApp [data-testid="stMarkdownContainer"] {font-family:'IBM Plex Sans Arabic',sans-serif; letter-spacing:0 !important;}
        [data-testid="stHorizontalBlock"] {direction:rtl; flex-direction:row;}
        .stepper {direction:rtl;}
        .stMain h1,.stMain h2,.stMain h3 {text-align:right; letter-spacing:0 !important;}
        [data-testid="stDataFrame"] {direction:rtl;}
        """
    return ".stMain {direction:ltr; text-align:left;}"


def inject_theme(lang="en"):
    caption = json.dumps(t("choose_files", lang), ensure_ascii=False)
    st.html("<style>" + CSS + direction_css(lang) +
            '[data-testid="stFileUploaderDropzone"] button::after {content:' + caption + ';}</style>')
