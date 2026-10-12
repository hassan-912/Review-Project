"""Server configuration shared by local development and Community Cloud."""
from __future__ import annotations

import os
from dotenv import load_dotenv

load_dotenv()


def setting(name: str, default: str = "") -> str:
    value = os.environ.get(name)
    if value:
        return value
    import streamlit as st
    try:
        return str(st.secrets.get(name, default))
    except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
        return default


def positive_int(name: str, default: int) -> int:
    value = int(setting(name, str(default)))
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value
