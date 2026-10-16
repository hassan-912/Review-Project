"""Stable document categories, bounded in-memory uploads, and review identities."""
from __future__ import annotations

import hashlib
import json
from pathlib import PurePath
import pymupdf as fitz
from PIL import Image
from io import BytesIO

CATEGORIES = (
    "passport", "visa_form", "cover_letter", "hotel", "flight",
    "insurance", "employment", "travel_plan", "supporting",
)
SCHEMA_VERSION = "review-v5-context-audit"


def files_hash(files: dict, model: str, lang: str = "en") -> str:
    """Length-independent canonical representation; file order cannot alter identity."""
    records = []
    for category in sorted(files):
        for name, data in files[category]:
            records.append((category, name, hashlib.sha256(data).hexdigest()))
    payload = json.dumps([SCHEMA_VERSION, model, lang, sorted(records)], ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def validate_uploads(files: dict, max_files: int = 30, max_total_mb: int = 75) -> None:
    if not files or any(category not in CATEGORIES for category in files):
        raise ValueError("upload_invalid")
    entries = [entry for group in files.values() for entry in group]
    if len(entries) > max_files or sum(len(data) for _, data in entries) > max_total_mb * 1024**2:
        raise ValueError("upload_limit")
    for name, data in entries:
        if not data or len(data) > 20 * 1024**2:
            raise ValueError("upload_limit")
        extension = PurePath(name).suffix.lower()
        try:
            if extension == ".pdf":
                if not data.startswith(b"%PDF-"):
                    raise ValueError("upload_invalid")
                with fitz.open(stream=data, filetype="pdf") as pdf:
                    if pdf.needs_pass or not 0 < pdf.page_count <= 150:
                        raise ValueError("upload_invalid")
            elif extension in {".png", ".jpg", ".jpeg", ".webp"}:
                with Image.open(BytesIO(data)) as image:
                    if image.width * image.height > 25_000_000:
                        raise ValueError("upload_limit")
                    formats = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG", ".webp": "WEBP"}
                    if image.format != formats[extension]:
                        raise ValueError("upload_invalid")
                    image.verify()
            else:
                raise ValueError("upload_invalid")
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError("upload_invalid") from exc
