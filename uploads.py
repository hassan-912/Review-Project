"""Stable document categories, bounded in-memory uploads, and review identities."""
from __future__ import annotations

import hashlib
import json
from pathlib import PurePath
import pymupdf as fitz
from PIL import Image
from io import BytesIO
from document_ingestion import UPLOAD_EXTENSIONS,TEXT_EXTENSIONS,native_text

CATEGORIES = (
    "passport", "visa_form", "cover_letter", "hotel", "flight",
    "insurance", "employment", "travel_plan", "bank_statement", "appointment", "supporting",
)
SCHEMA_VERSION = "review-v11-multiformat-financial"
SPAIN_UPLOAD_SLOTS = ("national_id_translation", "bank_declaration")
USA_CATEGORIES = ('ds160','hotel','passport','client_form')


def category_order(order=None):
    """Keep stable category IDs even when the display order is customized."""
    known=list(dict.fromkeys(x for x in (order or []) if x in CATEGORIES))
    return known+[x for x in CATEGORIES if x not in known]


def upload_slot_order(order=None,program='schengen',country='spain'):
    """Add Spain's dedicated form slots without changing saved shared category IDs."""
    if program=='usa':return list(USA_CATEGORIES)
    slots=category_order(order)
    if program=='schengen' and country=='spain':
        position=slots.index('visa_form')+1
        slots[position:position]=SPAIN_UPLOAD_SLOTS
    return slots


def upload_slot_category(slot):
    """Dedicated Spain form cards use the existing supporting-template parsers."""
    return 'supporting' if slot in SPAIN_UPLOAD_SLOTS else slot


def upload_thumbnail(name,data,category='supporting'):
    """Bounded preview generated in memory; bank previews show only the final page."""
    validate_uploads({category:[(name,data)]})
    if PurePath(name).suffix.lower() in TEXT_EXTENSIONS:
        from document_ingestion import normalize_uploads
        converted,_=normalize_uploads({category:[(name,data)]})
        name,data=converted[category][0]
    if name.lower().endswith('.pdf'):
        with fitz.open(stream=data,filetype='pdf') as doc:
            index=len(doc)-1 if category=='bank_statement' else 0
            page=doc[index]
            scale=min(1,420/max(page.rect.width,page.rect.height))
            return page.get_pixmap(matrix=fitz.Matrix(scale,scale),alpha=False).tobytes('png'),index+1,len(doc)
    with Image.open(BytesIO(data)) as image:
        image.thumbnail((420,420))
        output=BytesIO();image.convert('RGB').save(output,format='PNG')
        return output.getvalue(),1,1


def files_hash(files: dict, model: str, lang: str = "en") -> str:
    """Length-independent canonical representation; file order cannot alter identity."""
    records = []
    for category in sorted(files):
        for name, data in files[category]:
            records.append((category, name, hashlib.sha256(data).hexdigest()))
    payload = json.dumps([SCHEMA_VERSION, model, lang, sorted(records)], ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def validate_uploads(files: dict, max_files: int = 30, max_total_mb: int = 75, *, allowed_categories=None) -> None:
    allowed=CATEGORIES if allowed_categories is None else allowed_categories
    if not files or any(category not in allowed for category in files):
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
            elif extension in TEXT_EXTENSIONS:
                native_text(name,data)
            elif extension in {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"}:
                with Image.open(BytesIO(data)) as image:
                    if image.width * image.height > 25_000_000:
                        raise ValueError("upload_limit")
                    formats = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG", ".webp": "WEBP",'.tif':'TIFF','.tiff':'TIFF'}
                    if image.format != formats[extension]:
                        raise ValueError("upload_invalid")
                    image.verify()
            else:
                raise ValueError("upload_invalid")
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError("upload_invalid") from exc
