"""Offline pilot for the exact Spain references: entered PDF text -> traced values.

This module never calls an AI service or fills a missing answer from another file.
Text annotations and flattened text additions are supported. Image-only/scanned
variants and ambiguous shared answers are returned for verification, never guessed.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import re
import unicodedata

import pymupdf

TEMPLATE_DIR = Path(__file__).resolve().parent/'templates'/'spain'
MARKS = {'/', '\\', 'x', 'X', '✓', '✔', '☑', '✗', '✘'}
ANCHORS = {
    'schengen_application': {
        1:['Application for Schengen Visa','Number of travel document','Date of issue','Nationality at birth'],
        2:["Applicant's home address and e-mail address",'Current occupation','Member State of first entry',
           'Intended date of arrival of the first intended stay in the Schengen area'],
        3:['Means of support','I am aware that the visa fee is not refunded','Place and date'],
    },
    'bank_declaration': {1:['EMBAJADA DE ESPAÑA EN EGIPTO','NAME OF THE VISA APPLICANT',
                              'PASSPORT NUMBER','ID NUMBER','BANK SIGNATURE']},
    'national_id_translation': {1:['Arab Republic of Egypt','Personal ID Card','Full Name',
                                     'Full ID Number','Date of Birth','Current Job','Expiry Date']},
}
EMAIL = re.compile(r'[A-Z0-9.!#$%&\x27*+/=?^_`{|}~-]+@[A-Z0-9.-]+\.[A-Z]{2,}',re.I)
PHONE = re.compile(r'\+?\d[\d ()-]{6,}\d')
DATE = re.compile(r'(?<!\d)(?:\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{4})(?!\d)')


def _normal(text):
    return ''.join(char for char in unicodedata.normalize('NFKC',str(text)).casefold() if char.isalnum())


def _center(rect):
    return pymupdf.Point((rect[0]+rect[2])/2,(rect[1]+rect[3])/2)


def _inside(rect,point,margin=0):
    return rect[0]-margin<=point.x<=rect[2]+margin and rect[1]-margin<=point.y<=rect[3]+margin


def _load(template_id):
    if template_id not in ANCHORS:
        raise ValueError('Unsupported Spain template')
    return json.loads((TEMPLATE_DIR/(template_id+'.json')).read_text(encoding='utf-8'))


def _verify(pdf,template,template_id):
    problems=[]
    if len(pdf)!=template['pages']:
        return ['Page count does not match this reference template.']
    for index,page in enumerate(pdf):
        baseline=template['baseline_pages'][index]
        if abs(page.rect.width-baseline['width'])>2 or abs(page.rect.height-baseline['height'])>2 or page.rotation:
            problems.append(f'Page {index+1}: page size/orientation differs from the mapped reference.')
        text=_normal(page.get_text())
        if not text:
            problems.append(f'Page {index+1}: no readable text layer; OCR/visual verification is required.')
        elif any(_normal(anchor) not in text for anchor in ANCHORS[template_id][index+1]):
            problems.append(f'Page {index+1}: reference labels were not recognized; do not apply fixed field regions.')
        # Verify the printed labels at their original locations, not merely somewhere in a PDF.
        candidates=[line for line in baseline['lines'] if len(_normal(line['text']))>=14]
        matching=0
        for line in candidates:
            x0,y0,x1,y1=line['region_pdf_points']
            visible=page.get_text(clip=pymupdf.Rect(max(0,x0-3),max(0,y0-3),min(page.rect.width,x1+3),min(page.rect.height,y1+3)))
            if _normal(line['text']) in _normal(visible):
                matching+=1
        if candidates and matching/len(candidates)<0.80:
            problems.append(f'Page {index+1}: printed-label alignment is uncertain; manual verification is required.')
    return problems


def _is_baseline(word,baseline_words):
    text=_normal(word[4])
    if not text:
        return any(word[4] in old['text'] and
            _inside(old['region_pdf_points'],_center(word[:4]),margin=1) for old in baseline_words)
    center=_center(word[:4])
    for old in baseline_words:
        if _normal(old['text'])==text and _inside(old['region_pdf_points'],center,margin=3):
            return True
    return False


def _units(page,baseline,number):
    """Prefer visible FreeText answer objects; also find additions flattened into text."""
    result=[]
    for annotation in page.annots() or []:
        if annotation.type[0]!=pymupdf.PDF_ANNOT_FREE_TEXT or annotation.flags & (1|2|32):
            continue
        visible=(annotation.get_text() or '').strip()
        declared=(annotation.info.get('content') or '').strip()
        if not visible:
            continue
        # Appearance text is authoritative; a stale annotation metadata value is not.
        result.append(dict(text=visible,source_declared_text=declared,page=number,
                           region_pdf_points=list(annotation.rect),method='pdf_free_text_annotation',
                           appearance_matches_metadata=_normal(visible)==_normal(declared)))
    lines=defaultdict(list)
    for word in page.get_text('words'):
        if any(_inside(unit['region_pdf_points'],_center(word[:4]),margin=2) for unit in result):
            continue
        if _is_baseline(word,baseline.get('words',[])):
            continue
        lines[(word[5],word[6])].append(word)
    for words in lines.values():
        words.sort(key=lambda word:word[0])
        rect=pymupdf.Rect(words[0][:4])
        for word in words[1:]:rect|=pymupdf.Rect(word[:4])
        result.append(dict(text=' '.join(word[4] for word in words).strip(),page=number,
                           region_pdf_points=list(rect),method='pdf_text_addition',appearance_matches_metadata=True))
    return result


def _source(unit,filename):
    return dict(source_file=filename,page=unit['page'],text=unit['text'],
                region_pdf_points=[round(v,3) for v in unit['region_pdf_points']],method=unit['method'])


def _normal_value(value,kind):
    if not isinstance(value,str):return value
    if kind=='date':
        for pattern in ('%d/%m/%Y','%d-%m-%Y','%Y-%m-%d','%Y/%m/%d'):
            try:return datetime.strptime(value.strip(),pattern).date().isoformat()
            except ValueError:pass
    if kind=='date_or_year_month':
        for pattern in ('%d/%m/%Y','%d-%m-%Y','%Y-%m-%d','%Y/%m/%d'):
            try:return datetime.strptime(value.strip(),pattern).date().isoformat()
            except ValueError:pass
        if re.fullmatch(r'\d{4}[-/]\d{2}',value.strip()):return value.strip().replace('/','-')
    # Identifiers are strings. Never infer a date/identity from their digits.
    return ' '.join(value.split())


def _set(row,value,units,filename,*,status='extracted'):
    if row['value_type']=='text_list' and isinstance(value,str):
        value=[value]
    row.update(value=value,normalized_value=_normal_value(value,row['value_type']),status=status,
               sources=[_source(unit,filename) for unit in units])
    if row['value_type'] in ('date','date_or_year_month'):
        allowed=r'\d{4}-\d{2}-\d{2}' if row['value_type']=='date' else r'\d{4}-\d{2}(?:-\d{2})?'
        if not isinstance(row['normalized_value'],str) or not re.fullmatch(allowed,row['normalized_value']):
            row.update(normalized_value=None,status='invalid_or_ambiguous_date')
        else:
            try:datetime.strptime(row['normalized_value'],'%Y-%m' if len(row['normalized_value'])==7 else '%Y-%m-%d')
            except ValueError:row.update(normalized_value=None,status='invalid_or_ambiguous_date')


def _join(units):
    return ' '.join(unit['text'].strip() for unit in sorted(units,key=lambda unit:(unit['page'],unit['region_pdf_points'][1],unit['region_pdf_points'][0]))).strip()


def _visual_additions(page,baseline):
    result=[]
    for image in page.get_image_info(hashes=True):
        if not any(image['digest'].hex()==old['digest'] and
                   max(abs(a-b) for a,b in zip(image['bbox'],old['region_pdf_points']))<2
                   for old in baseline.get('images',[])):
            result.append(dict(region_pdf_points=list(image['bbox']),method='new_image'))
    known={item['signature'] for item in baseline.get('drawings',[])}
    for drawing in page.get_drawings():
        if sha256(repr(drawing['items']).encode()).hexdigest() not in known:
            result.append(dict(region_pdf_points=list(drawing['rect']),method='new_vector_ink'))
    return result


def _split_shared(rows,group,units,filename):
    text=_join(units)
    keys={row['key']:row for row in group}
    if 'applicant.contact.email' in keys or 'host.email' in keys:
        prefix='applicant.contact' if 'applicant.contact.email' in keys else 'host'
        emails=EMAIL.findall(text)
        address=EMAIL.sub('',text).strip(' ,;\n')
        if emails:_set(keys[prefix+'.email'],'; '.join(emails),units,filename)
        address_key=prefix+('.home_address' if prefix=='applicant.contact' else '.address')
        if address:_set(keys[address_key],address,units,filename)
        return
    if 'employment_or_education.name' in keys:
        # These components are unlabelled within a shared answer. Preserve the full
        # row and make the comma-based name/address split explicitly provisional.
        phones=PHONE.findall(text)
        body=PHONE.sub('',text).strip(' ,;') if phones else text
        if phones:_set(keys['employment_or_education.telephone'],'; '.join(phones),units,filename)
        name,separator,address=body.partition(',')
        if separator:
            _set(keys['employment_or_education.name'],name.strip(),units,filename,status='needs_verification')
            _set(keys['employment_or_education.address'],address.strip(),units,filename,status='needs_verification')
        else:
            for key in ('employment_or_education.name','employment_or_education.address'):
                keys[key].update(status='ambiguous_shared_answer',sources=[_source(unit,filename) for unit in units])
        return
    if set(keys)=={'declaration.place','declaration.date'}:
        dates=DATE.findall(text)
        if len(dates)==1:_set(keys['declaration.date'],dates[0],units,filename)
        place=DATE.sub('',text).strip(' ,;')
        if place:_set(keys['declaration.place'],place,units,filename)
        return
    # Never duplicate an entire guardian/company answer into several distinct fields.
    for row in group:
        row.update(status='ambiguous_shared_answer',sources=[_source(unit,filename) for unit in units])


def extract_spain_pdf(raw,template_id,filename='document.pdf'):
    template=_load(template_id)
    rows=[dict(key=field['key'],label=field['label'],question_number=field['question_number'],
               subject_role=field['subject_role'],value_type=field['value_type'],options=field['options'],
               page=field['page'],value=None,normalized_value=None,status='blank',sources=[],
               preprinted_default=field['value'] if field['value_status']=='preprinted' else None)
          for field in template['fields']]
    report=dict(template_id=template['template_id'],source_file=filename,source_sha256=sha256(raw).hexdigest(),
                extraction_method='local_python_pymupdf',ai_requests=0,fields=rows,unassigned_answers=[],
                shared_answers=[],limitations=[])
    with pymupdf.open(stream=raw,filetype='pdf') as pdf:
        problems=_verify(pdf,template,template_id)
        if problems:
            for row in rows:row['status']='template_not_verified'
            report.update(status='needs_verification',limitations=problems,filled_values={},values={row['key']:None for row in rows})
            return report
        matched=defaultdict(list)
        all_units=[]
        for number,page in enumerate(pdf,1):
            units=_units(page,template['baseline_pages'][number-1],number)
            all_units.extend(units)
            boxes=template['baseline_pages'][number-1].get('checkboxes',[])
            for unit in units:
                rect=unit['region_pdf_points'];center=_center(rect)
                if unit['text'].strip() in MARKS:
                    near=[]
                    for box in boxes:
                        point=_center(box['region_pdf_points'])
                        distance=abs(point.x-center.x)+abs(point.y-center.y)
                        if distance<9:near.append((distance,box))
                    near.sort(key=lambda item:item[0])
                    if not near or (len(near)>1 and near[1][0]-near[0][0]<2):
                        report['unassigned_answers'].append(_source(unit,filename));continue
                    box=near[0][1];option_matches=[]
                    for field in template['fields']:
                        if field['page']!=number or not field['options'] or not _inside(field['region_pdf_points'],_center(box['region_pdf_points'])):
                            continue
                        label=_normal(box['label'])
                        for option in field['options']:
                            if label.startswith(_normal(option)):
                                option_matches.append((field['key'],option))
                    if len(option_matches)!=1:
                        report['unassigned_answers'].append(_source(unit,filename));continue
                    key,option=option_matches[0]
                    matched[key].append(dict(unit,selected_option=option))
                    continue
                candidates=[field for field in template['fields'] if field['page']==number and not field['options']
                            and _inside(field['region_pdf_points'],center)]
                if not candidates:
                    report['unassigned_answers'].append(_source(unit,filename));continue
                # Specific nested answer cells win over their broad explanatory heading.
                area=lambda field:(field['region_pdf_points'][2]-field['region_pdf_points'][0])*(field['region_pdf_points'][3]-field['region_pdf_points'][1])
                smallest=min(area(field) for field in candidates)
                candidates=[field for field in candidates if abs(area(field)-smallest)<1]
                for field in candidates:matched[field['key']].append(unit)
        lookup={row['key']:row for row in rows}
        done=set()
        for field in template['fields']:
            key=field['key'];row=lookup[key];units=matched.get(key,[])
            if not units or key in done:continue
            if field['options']:
                options=list(dict.fromkeys(unit['selected_option'] for unit in units))
                value=options if field['value_type']=='multiple_choice' else options[0] if len(options)==1 else options
                _set(row,value,units,filename,status='extracted' if field['value_type']=='multiple_choice' or len(options)==1 else 'conflicting_selections')
            elif field['value_type'] in ('image_presence','signature_presence'):
                # Typed text is not proof of an attached photo or a handwritten signature.
                row.update(status='needs_visual_verification',sources=[_source(unit,filename) for unit in units])
            elif field['shared_answer_region']:
                group=[lookup[other['key']] for other in template['fields'] if other['page']==field['page']
                       and other['region_pdf_points']==field['region_pdf_points'] and not other['options'] and other['shared_answer_region']]
                if len(group)>1:
                    report['shared_answers'].append(dict(keys=[item['key'] for item in group],raw_text=_join(units),
                                                         sources=[_source(unit,filename) for unit in units]))
                    _split_shared(rows,group,units,filename)
                    done.update(item['key'] for item in group)
                else:_set(row,_join(units),units,filename)
            else:_set(row,_join(units),units,filename)
            done.add(key)
        report['visual_additions']=[]
        for number,page in enumerate(pdf,1):
            for addition in _visual_additions(page,template['baseline_pages'][number-1]):
                rect=pymupdf.Rect(addition['region_pdf_points'])
                if rect.is_empty:
                    rect=pymupdf.Rect(rect.x0-1,rect.y0-1,rect.x1+1,rect.y1+1)
                affected=[lookup[field['key']] for field in template['fields'] if field['page']==number
                          and rect.intersects(pymupdf.Rect(field['region_pdf_points']))]
                if affected:
                    report['visual_additions'].append(dict(addition,page=number,keys=[row['key'] for row in affected]))
                    for row in affected:
                        row['status']='needs_ocr_or_visual_verification'
        if report['visual_additions']:
            report['limitations'].append('New image/vector content overlaps answer regions and needs OCR or visual verification; text alone is insufficient.')
        if report['unassigned_answers']:
            report['limitations'].append('Some entered content could not be assigned safely; inspect unassigned_answers.')
        provisional=[row for row in rows if row['status'] not in ('blank','extracted')]
        if provisional:report['limitations'].append('Some shared/visual/contradictory answers need verification; their raw source is retained.')
        if any(not unit['appearance_matches_metadata'] for unit in all_units):
            report['limitations'].append('Some annotation metadata differs from its visible appearance. Visible text was used.')
        report['status']='needs_verification' if report['limitations'] else 'extracted'
        report['values']={row['key']:row['value'] for row in rows}
        report['normalized_values']={row['key']:row['normalized_value'] for row in rows}
        report['filled_values']={key:value for key,value in report['values'].items() if value is not None}
        report['preprinted_values']={row['key']:row['preprinted_default'] for row in rows if row['preprinted_default'] is not None}
        report['entered_answer_objects']=len(all_units)
        return report


def compare_spain_values(reports):
    """Only actual matching identifiers/DOB; no passport reference has been supplied."""
    checks=[]
    comparisons={
        'passport_number': [('schengen_application','travel_document.number'),('bank_declaration','bank_holder.passport_number')],
        'national_id_number': [('schengen_application','applicant.national_id_number'),('bank_declaration','bank_holder.national_id_number'),
                               ('national_id_translation','holder.front_id_number'),('national_id_translation','holder.full_id_number')],
        'date_of_birth': [('schengen_application','applicant.date_of_birth'),('national_id_translation','holder.date_of_birth')],
    }
    for name,fields in comparisons.items():
        present=[dict(document=document,key=key,value=reports.get(document,{}).get('normalized_values',{}).get(key)) for document,key in fields]
        known=[entry['value'] for entry in present if entry['value'] is not None]
        status='unverified' if len(known)!=len(fields) else 'match' if len(set(known))==1 else 'mismatch'
        checks.append(dict(field=name,status=status,sources=present,
                           note='Bank-holder details belong to the bank holder. Equality does not establish applicant ownership or authenticity.' if name in ('passport_number','national_id_number') else 'Compared independently entered dates only.'))
    return dict(checks=checks,limitations=['No original passport was supplied; these are cross-document consistency checks, not validation against the passport.',
                                         'Do not compare ID issue/expiry dates to passport issue/expiry dates: they are different documents.',
                                         'Name and employment equivalence require their own explicit rules; no name expansion or company equivalence is inferred.'])
