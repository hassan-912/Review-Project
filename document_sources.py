"""In-memory source identity and quote checks shared by the audit stages."""
from collections import Counter
from hashlib import sha256
import re
import unicodedata
import pymupdf


def unique_uploads(uploaded):
    """Read identical bytes once, including combined files uploaded to two slots."""
    result, seen = {}, set()
    names = Counter(name for group in uploaded.values() for name, _ in group)
    for category, group in uploaded.items():
        for name, raw in group:
            digest = sha256(raw).hexdigest()
            if digest in seen:
                continue
            seen.add(digest)
            source = f"{category}/{digest[:8]}/{name}" if names[name] > 1 else name
            result.setdefault(category, []).append((source, raw))
    return result


def source_manifest(uploaded):
    result = {}
    for category, group in uploaded.items():
        for name, raw in group:
            pages = 1
            if name.lower().endswith('.pdf'):
                with pymupdf.open(stream=raw, filetype='pdf') as pdf:
                    pages = len(pdf)
            result[name] = {"category_hint": category, "pages": pages}
    return result


def normalized_quote(text):
    text = unicodedata.normalize('NFKC', str(text or '')).casefold()
    # PDF extraction often changes punctuation/line wrapping. Keep every letter and
    # digit, including negations and date digits, while tolerating punctuation only.
    return ''.join(char for char in text if char.isalnum())


def source_is_grounded(source, uploaded):
    matches = [raw for group in uploaded.values() for name, raw in group if name == source.get('source_file')]
    page = source.get('page')
    quote = source.get('text') or source.get('quote')
    if len(matches) != 1 or not isinstance(page, int) or page < 1 or not quote:
        return False
    if not source['source_file'].lower().endswith('.pdf'):
        return page == 1
    with pymupdf.open(stream=matches[0], filetype='pdf') as pdf:
        if page > len(pdf):
            return False
        text = pdf[page - 1].get_text()
        # Scans rely on visual transcription; show the actual page to the reviewer.
        return len(text.strip()) < 20 or normalized_quote(quote) in normalized_quote(text)
