"""Read review context locally, in memory, without silently omitting oversized files."""
from hashlib import sha256

import pymupdf

from . import VERSION
from .contracts import Packet, packet_digest

MAX_TOTAL_CHARS = 240000
MAX_PAGES = 180


def _bilingual_lines(raw):
    from offline_ocr import image_lines,arabic_image_lines
    lines=image_lines(raw)
    try:
        arabic=[line for line in arabic_image_lines(raw) if any('\u0600'<=char<='\u06ff' for char in line['text'])]
        # Keep both scripts; OCR readings remain provisional source evidence.
        lines+=arabic
    except Exception:pass
    return list({line['text']:line for line in lines}.values())


def _read_pages(name, raw, category, ocr):
    pages = []
    if name.lower().endswith('.pdf'):
        with pymupdf.open(stream=raw, filetype='pdf') as pdf:
            total = len(pdf)
            numbers = range(1, total + 1)
            for number in numbers:
                if len(pages) >= MAX_PAGES:
                    break
                page = pdf[number - 1]
                text = page.get_text(sort=True).strip()
                for annot in page.annots() or []:
                    if annot.type[1] == 'FreeText' and not annot.flags & (1 | 2 | 32):
                        text += '\n' + annot.get_text()
                if len(text) >= 30:
                    pages.append(dict(number=number, text=text[:18000], method='pdf_text', provisional=len(text)>18000))
                elif ocr:
                    from offline_ocr import image_lines
                    image=page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False).tobytes('png')
                    lines = _bilingual_lines(image)
                    text = '\n'.join(line['text'] for line in lines)
                    pages.append(dict(number=number, text=text[:18000], method='local_ocr',
                                      provisional=not text.strip() or len(text)>18000 or any(line['confidence'] < .90 for line in lines)))
                else:
                    pages.append(dict(number=number, text='', method='unreadable', provisional=True))
        return total, pages
    if ocr:
        from offline_ocr import image_lines
        lines = _bilingual_lines(raw)
        text = '\n'.join(line['text'] for line in lines)
        return 1, [dict(number=1, text=text[:18000], method='local_ocr',
                        provisional=not text or len(text)>18000 or any(line['confidence'] < .90 for line in lines))]
    return 1, [dict(number=1, text='', method='unreadable', provisional=True)]


# Reference files are never opened here. Their context comes from the local extractors.
REFERENCE_CATEGORIES = {'passport', 'visa_form', 'hotel', 'flight', 'employment',
                        'insurance', 'national_id', 'appointment'}


def _extracted_pages(name, categories, data):
    import json
    fields = {}
    for source in getattr(data, 'evidence_locations', []):
        if source.source_file == name and source.local_source and source.value is not None:
            fields.setdefault(source.page, {})[source.field_name] = source.value
    for report in getattr(data, 'local_results', []):
        if report.get('source_file') != name or report.get('category') not in categories:
            continue
        rows = report.get('fields', {})
        rows = {r['key']:r for r in rows} if isinstance(rows, list) else rows
        for key, row in rows.items():
            value = row.get('normalized_value', row.get('value'))
            # Never turn uncertain or conflicting OCR into a confirmed fact.
            if value is None or row.get('status') not in ('extracted', 'confirmed'):
                continue
            sources = row.get('sources') or []
            number = row.get('page') or (sources[0].get('page') if sources else None) or 1
            fields.setdefault(number, {})[key] = value
    for category, attr in (('bank_statement','bank_statements'), ('appointment','appointments')):
        if category in categories:
            for item in getattr(data, attr, []):
                if item.source_file == name:
                    fields.setdefault(item.page or 1, {}).update(item.model_dump(exclude={'source_file','text'}, exclude_none=True))
    for cost in getattr(data,'trip_costs',[]):
        if cost.source_file==name:
            fields.setdefault(cost.page,{})['reservation_total']=cost.amount
            fields[cost.page]['reservation_currency']=cost.currency
            fields[cost.page]['reservation_paid']=cost.paid
    pages=[]
    for number, values in sorted(fields.items()):
        text='\n'.join(f'{key}: {json.dumps(value, ensure_ascii=False)}' for key,value in sorted(values.items()))
        if len(text)>18000:
            raise ValueError('Extracted facts exceed the review size')
        pages.append(dict(number=number,text=text,method='extracted_fields',provisional=False))
    return pages or [dict(number=1,text='',method='unreadable',provisional=True)]


def build_packet(uploaded, data=None, country='unknown', language='en', original_uploads=None, ocr=True, rates=None, converted_sources=None):
    documents=[]; attachments=[]; notes=[]; roles={}; total_chars=0; total_pages=0
    for category,group in (original_uploads or uploaded).items():
        for _,raw in group:
            roles.setdefault(sha256(raw).hexdigest(),set()).add(category)
    for category,group in uploaded.items():
        for name,raw in group:
            digest=sha256(raw).hexdigest()
            if any(doc['sha256']==digest for doc in documents):
                continue
            if len(documents)>=30:
                raise ValueError('Too many context documents')
            detected={r.get('category') for r in getattr(data,'local_results',[]) if r.get('source_file')==name}
            categories=sorted(roles.get(digest,{category}) | (detected & REFERENCE_CATEGORIES))
            converted=(converted_sources or {}).get(digest)
            def read_source():
                if converted and converted['text'] and not converted['has_images']:
                    text=converted['text'];parts=[]
                    while text:
                        end=len(text) if len(text)<=14000 else text.rfind('\n',0,14000)
                        if end<=0:end=min(14000,len(text))
                        parts.append(dict(number=len(parts)+1,text=text[:end],method='native_text',provisional=False))
                        text=text[end:].lstrip('\n')
                    return len(parts),parts
                return _read_pages(name,raw,category,ocr)
            extracted=bool(set(categories)&REFERENCE_CATEGORIES) and not ('supporting' in categories and not set(categories)&{'passport','visa_form','hotel','flight','insurance','employment'})
            mode='extracted_fields' if extracted else 'full_text'
            if extracted:
                pages=_extracted_pages(name,categories,data)
                # No PDF parsing, OCR, raw text, image or base64 transfer for references.
                count=max(page['number'] for page in pages)
                if set(categories)&{'cover_letter','travel_plan'}:
                    notes.append(f'{name}: upload the letter or plan separately from a reference document.')
                if not any(p['text'] for p in pages):
                    try:
                        count,pages=read_source()
                        mode='extracted_text'
                    except Exception:
                        notes.append(f'{name}: no reliable extracted reference fields or text are available.')
                audits=[a for a in getattr(data,'document_audits',[]) if a.source_file==name]
                if any(a.readability!='readable' for a in audits):
                    notes.append(f'{name}: local extraction has incomplete or uncertain reference fields.')
            else:
                try:
                    count,pages=read_source()
                except Exception:
                    count,pages=1,[dict(number=1,text='',method='unreadable',provisional=True)]
                if len(pages)!=count:
                    notes.append(f'{name}: not every narrative/supporting page could be included.')
            visual_allowed=bool(set(categories)&{'bank_statement','supporting'}) and not bool(set(categories)&{'passport','visa_form','hotel','flight','insurance','employment','cover_letter','travel_plan'})
            visual_needed=any(p['provisional'] or not p['text'].strip() for p in pages)
            if visual_allowed and visual_needed:
                import base64
                if not name.lower().endswith('.pdf'):
                    from document_ingestion import text_pdf
                    raw=text_pdf('',[raw]);digest=sha256(raw).hexdigest()
                    count=1
                attachments.append(dict(document_id=f'd{len(documents)+1}',data=base64.b64encode(raw).decode()))
                for page in pages:
                    if not page['text'].strip():page['method']='pdf_visual'
                mode='pdf_visual'
            for page in pages:
                total_chars+=len(page['text']); total_pages+=1
                if total_chars>MAX_TOTAL_CHARS or total_pages>MAX_PAGES:
                    raise ValueError('Context exceeds the safe review size; select a smaller document set')
                if page['provisional']:
                    notes.append(f'{name}, page {page["number"]}: missing, clipped or uncertain text.')
            documents.append(dict(id=f'd{len(documents)+1}',filename=name,categories=categories,
                                  sha256=digest,total_pages=count,pages=pages,
                                  context_mode=mode))
    supporting=[d for d in documents if 'supporting' in d['categories']]
    supporting_text=' '.join(p['text'] for d in supporting for p in d['pages'])
    import re
    if re.search(r'translat|family\s+(?:register|registry|record)|civil\s+registry|قيد\s+(?:عائلي|فردي)|سجل\s+عائلي|ترجم',supporting_text,re.I):
        if len(re.findall(r'[\u0621-\u064a]',supporting_text))<15:
            notes.append('The Arabic original is missing or unreadable for the supplied supporting translation.')
        if len(re.findall(r'[A-Za-z]',supporting_text))<15:
            notes.append('The English translation is missing or unreadable for the supplied supporting original.')
    from .financial_context import make_financial_context
    payload=dict(version=VERSION,country=country or 'unknown',language=language,documents=documents,
                 verified_facts=[],limitations=list(dict.fromkeys(notes)),attachments=attachments,
                 financial_context=make_financial_context(data,documents,rates))
    payload['request_id']=packet_digest(payload)
    return Packet.model_validate(payload).model_dump()
