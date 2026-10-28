"""Local reader for the inspected Belgium portal application layout.

Labels locate input rectangles rather than fixed page coordinates. Blank controls,
unrecognized layouts and uncertain OCR never become invented applicant answers.
This adapter is selected explicitly by the Belgium workspace, never by filename.
"""
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import re
import unicodedata

import pymupdf

from offline_ocr import pdf_lines


TEMPLATE = Path(__file__).resolve().parent / 'templates' / 'belgium' / 'portal_application.json'
MIN_CONFIDENCE = .90


def _normal(value):
    return ''.join(c for c in unicodedata.normalize('NFKC', str(value)).casefold() if c.isalnum())


def _label_text(value):
    # Help icons can be OCR'd as punctuation or circled digits.
    return re.sub(r'\s*[?@\u2460-\u2473]+\s*$', '', value.strip()).strip(' *?@')


def _matches(line, field):
    text = _label_text(line['text'])
    number = field.get('question_number')
    if number is not None:
        match = re.match(r'^(\d{1,2})\s*[.:]?\s*(.*)$', text)
        if not match or int(match[1]) != number:
            return False
        text = match[2]
    return _normal(text) in {_normal(label) for label in field['labels']}


def _rectangles(page):
    """Locate visible input borders in native PDFs and raster portal captures."""
    import cv2
    import numpy as np
    pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
    pixels = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    gray = cv2.cvtColor(pixels, cv2.COLOR_RGB2GRAY)
    ink = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)[1]
    horizontal = cv2.morphologyEx(ink, cv2.MORPH_OPEN,
                                cv2.getStructuringElement(cv2.MORPH_RECT, (max(20, pix.width // 30), 1)))
    vertical = cv2.morphologyEx(ink, cv2.MORPH_OPEN,
                              cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(10, pix.height // 120))))
    borders = cv2.morphologyEx(horizontal | vertical, cv2.MORPH_CLOSE,
                              cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)))
    contours, _ = cv2.findContours(borders, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    boxes = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if not (.055 <= w / pix.width <= .92 and .018 <= h / pix.width <= .085):
            continue
        # Open table rules and text strokes must not masquerade as closed controls.
        if cv2.contourArea(contour) < .80 * w * h:
            continue
        rect = [x / pix.width, y / pix.height, (x + w) / pix.width, (y + h) / pix.height]
        if not any(max(abs(a-b) for a, b in zip(rect, old)) < .005 for old in boxes):
            boxes.append(rect)
    # Dropdown arrow and search icon cells sometimes split a larger control.
    return sorted(boxes, key=lambda box: (box[1], box[0]))


def _control(anchor, boxes, split=False):
    x0, y0, x1, y1 = anchor['region_normalized']
    cy = (y0 + y1) / 2
    inline = [box for box in boxes if box[0] >= x1 - .008
              and box[1] - .003 <= cy <= box[3] + .003]
    if inline:
        best = min(inline, key=lambda box: box[0] - x1)
        return [best]
    below = [box for box in boxes if -.003 <= box[1] - y1 <= .045
             and box[0] >= x0 - .035 and box[0] <= x0 + (.65 if split else .12)]
    if split:
        # A browser focus outline can enclose each of the three date controls.
        # Prefer the inner input borders consistently across all components.
        below = [box for box in below if not any(other is not box
                 and box[0] <= other[0] and box[1] <= other[1]
                 and box[2] >= other[2] and box[3] >= other[3] for other in below)]
    if not below:
        return []
    top = min(box[1] for box in below)
    row = sorted((box for box in below if abs(box[1] - top) < .006), key=lambda box: box[0])
    return row if split else row[:1]


def _inside(line, box):
    x0, y0, x1, y1 = line['region_normalized']
    return box[0] < (x0+x1)/2 < box[2] and box[1] < (y0+y1)/2 < box[3]


def _placeholder(text):
    return _normal(text) in {'', 'enter', 'choose', 'select', 'notyetavailable', 'xxxxxx'}


def _date(text, split=False):
    try:
        if split:
            parts = re.findall(r'\d+', text)
            if len(parts) != 3 or len(parts[2]) != 4:
                return None
            return datetime(int(parts[2]), int(parts[1]), int(parts[0])).date().isoformat()
        for fmt in ('%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d'):
            try:
                return datetime.strptime(text, fmt).date().isoformat()
            except ValueError:
                pass
    except (ValueError, TypeError):
        pass
    return None


def _read(field, anchor, lines, boxes, filename):
    row = dict(key=field['key'], label=field['labels'][0], question_number=field.get('question_number'),
               subject_role=field.get('subject_role', 'applicant'), value_type=field.get('value_type', 'text'),
               page=anchor['page'] if anchor else None, value=None, normalized_value=None,
               status='not_present', sources=[])
    if anchor is None:
        return row
    if row['value_type'] == 'selection_mark':
        row.update(status='needs_visual_verification', sources=[dict(anchor, source_file=filename)])
        return row
    controls = _control(anchor, boxes, split=row['value_type'] == 'split_date')
    if not controls:
        row['status'] = 'unverified'
        return row
    sources = []
    parts = []
    for box in controls:
        found = sorted((line for line in lines if line is not anchor and _inside(line, box)),
                       key=lambda line: (round(line['region_normalized'][1], 2), line['region_normalized'][0]))
        # Exclude tiny search/calendar glyphs outside the text-entry portion.
        found = [line for line in found if not (_normal(line['text']) == 'q'
                 and line['region_normalized'][2] - line['region_normalized'][0] < .03)]
        sources.extend(dict(line, source_file=filename) for line in found)
        parts.append(' '.join(line['text'].strip() for line in found))
    text = ' '.join(parts).strip()
    row.update(sources=sources, answer_regions=controls)
    if not text or all(_placeholder(part) for part in parts):
        # No OCR reading in an image control is not proof that the control is blank.
        row['status'] = 'blank' if text or anchor['method'] == 'pdf_text' else 'unverified'
        return row
    row.update(value=text, normalized_value=text, status='extracted')
    if row['value_type'] in ('date', 'split_date'):
        row['normalized_value'] = _date(text, row['value_type'] == 'split_date')
        if row['normalized_value'] is None:
            row['status'] = 'needs_verification'
    if any(line.get('confidence') is not None and line['confidence'] < MIN_CONFIDENCE
           for line in [anchor, *sources]):
        row['status'] = 'needs_verification'
    return row


def parse_belgium_lines(lines, controls, filename='application.pdf', source_sha256=None):
    """Parse positioned local readings; also used by synthetic regression tests."""
    template = json.loads(TEMPLATE.read_text(encoding='utf-8'))
    fields = template['fields']
    anchors = {field['key']: [line for line in lines if _matches(line, field)] for field in fields
               if not field.get('derived_from') and not field.get('street_number_for')}
    # Verify the portal's distinctive numbered labels; a Belgium destination or
    # filename alone cannot enable the parser on an arbitrary Schengen PDF.
    required = template['verification_keys']
    verified = all(len(anchors.get(key, [])) == 1 for key in required)
    headings = {_normal(_label_text(line['text'])) for line in lines}
    verified = verified and all(_normal(label) in headings for label in template['verification_headings'])
    report = dict(template_id=template['template_id'], source_file=filename, source_sha256=source_sha256,
                  extraction_method='local_python_portal_controls', ai_requests=0, fields=[], limitations=[])
    if not verified:
        return dict(report, status='unsupported_template',
                    limitations=['Belgium portal labels/sections were not verified; no answers were assigned.'],
                    values={}, normalized_values={}, filled_values={})
    for field in fields:
        if field.get('derived_from'):
            continue
        matches = anchors.get(field['key'], [])
        if field.get('street_number_for'):
            streets = anchors.get(field['street_number_for'], [])
            if len(streets) == 1:
                street = streets[0]
                # The unnumbered "no" label belongs only to the nearby street
                # control in this section, including the screenshot's second column.
                matches = [line for line in lines if line['page'] == street['page']
                           and _normal(line['text']) == 'no'
                           and -.008 <= line['region_normalized'][1] - street['region_normalized'][1] <= .065]
        anchor = matches[0] if len(matches) == 1 else None
        row = _read(field, anchor, [line for line in lines if anchor and line['page'] == anchor['page']],
                    controls.get(anchor['page'], []) if anchor else [], filename)
        if len(matches) > 1:
            row.update(status='conflicting_labels', sources=[dict(line, source_file=filename) for line in matches])
        report['fields'].append(row)
    lookup = {row['key']: row for row in report['fields']}
    for field in fields:
        if not field.get('derived_from'):
            continue
        components = [lookup[key] for key in field['derived_from']]
        entered = [row for row in components if row['value'] is not None]
        # Postal code/house number are optional. Street/city/country establish
        # the address; an unread field must not silently produce a partial match.
        complete = all(lookup[key]['status'] == 'extracted' for key in field['required_components'])
        uncertain = any(row['status'] not in ('extracted', 'blank', 'not_present') for row in components)
        value = ', '.join(row['value'] for row in entered) or None
        status = 'extracted' if complete and not uncertain else 'unverified'
        if all(row['status'] == 'not_present' for row in components):
            status = 'not_present'
        elif all(row['status'] in ('blank', 'not_present') for row in components):
            status = 'blank'
        lookup[field['key']] = dict(key=field['key'], label=field['labels'][0], question_number=field['question_number'],
            subject_role=field.get('subject_role', 'applicant'), value_type='address', page=components[0]['page'],
            value=value, normalized_value=value, status=status,
            sources=[source for row in components for source in row['sources']])
        report['fields'].append(lookup[field['key']])
    if any(row['status'] not in ('extracted', 'blank', 'not_present') for row in report['fields']):
        report['limitations'].append('Some controls, selections or OCR readings need verification; source locations are retained.')
    report['status'] = 'needs_verification' if report['limitations'] else 'extracted'
    report['values'] = {row['key']: row['value'] for row in report['fields']}
    # HR comparisons consume this dictionary directly. Keep uncertain candidates
    # on their field rows, but never expose them as authoritative comparison data.
    report['normalized_values'] = {row['key']: row['normalized_value'] if row['status']=='extracted' else None
                                   for row in report['fields']}
    report['filled_values'] = {row['key']: row['value'] for row in report['fields'] if row['value'] is not None}
    return report


def extract_belgium_pdf(raw, filename='application.pdf'):
    lines = pdf_lines(raw)
    with pymupdf.open(stream=raw, filetype='pdf') as pdf:
        controls = {number: _rectangles(page) for number, page in enumerate(pdf, 1)}
    return parse_belgium_lines(lines, controls, filename, sha256(raw).hexdigest())
