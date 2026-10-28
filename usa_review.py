"""Offline, source-linked DS-160 comparisons. No model or network fallbacks."""
from calendar import monthrange
from collections import Counter
from difflib import SequenceMatcher
from datetime import date,datetime,timedelta
from hashlib import sha256
import re
import unicodedata

import pymupdf

from document_cache import cached_parse
from document_ingestion import normalize_uploads
from extractor import VisaDocumentExtraction
from i18n import field_label,t
from scorer import calculate_score
from uploads import USA_CATEGORIES,validate_uploads
from validator import Severity,ValidationIssue

VERSION='usa-labelled-v9-booking-dates'
NAMES={'ds160':'DS-160','passport':'Passport','hotel':'Hotel Reservation','client_form':'Client Form'}

# Exact labels only. In particular, passport BOOK number and a US CONTACT's
# address are not the applicant's passport number or intended place of stay.
LABELS={
    'full_name':('full name','applicant name','name as in passport','name provided','guest name','guest name(s)','reserved for','الاسم الكامل','اسم العميل','اسم النزيل'),
    'surname':('surnames','surname','last name','family name','اسم العائلة'),
    'given_names':('given names','given name','first name','الأسماء الأولى','الاسم الاول'),
    'date_of_birth':('date of birth','birth date','dob','تاريخ الميلاد'),
    'nationality':('nationality','country/region of origin (nationality)','country/region of nationality','الجنسية'),
    'gender':('sex','gender','الجنس'),
    'passport_number':('passport/travel document number','passport number','passport no.','passport no','رقم جواز السفر'),
    'passport_issue':('passport issue date','passport date of issue','date of issue','issuance date','passport/travel document date of issuance','تاريخ إصدار جواز السفر'),
    'passport_expiry':('passport expiry date','passport expiry','passport expiration date','passport date of expiry','expiration date','date of expiry','تاريخ انتهاء جواز السفر'),
    'arrival_date':('intended date of arrival','date of arrival in u.s.','date of arrival in the u.s.','arrival date','intended arrival date','travel start date','تاريخ الوصول'),
    'departure_date':('date of departure from u.s.','date of departure from the u.s.','departure date','intended departure date','intended date of departure','travel end date','تاريخ المغادرة'),
    'length_of_stay':('intended length of stay in u.s.','intended length of stay in the u.s.','intended length of stay','length of stay','مدة الإقامة'),
    'check_in_date':('check-in','check in','check-in date','check in date','تاريخ تسجيل الوصول'),
    'check_out_date':('check-out','check out','check-out date','check out date','تاريخ تسجيل المغادرة'),
    'hotel_name':('hotel name','hotel','property name','name of hotel','accommodation name','اسم الفندق'),
    'hotel_address':('hotel address','address where you will stay in the u.s.','address where you will stay in u.s.','address of stay','عنوان الفندق','عنوان الإقامة'),
    'hotel_phone':('hotel phone','hotel phone number','property phone','هاتف الفندق'),
    'hotel_email':('hotel email','property email','بريد الفندق الإلكتروني'),
    'us_contact_person':('contact person name in the u.s.',),
    'us_contact_organization':('organization name in the u.s.',),
    'us_contact_relationship':('relationship to you',),
    'us_contact_address':('u.s. contact address',),
    'stay_city':('hotel city','city of stay','destination city','مدينة الإقامة','مدينة الفندق'),
    'stay_state':('hotel state','state of stay','ولاية الإقامة'),
    'stay_zip':('hotel zip code','zip code of stay','الرمز البريدي للفندق'),
    'email':('email address','e-mail address','applicant email','البريد الإلكتروني'),
    'phone':('primary phone number','applicant phone','mobile number','رقم الهاتف'),
    'marital_status':('marital status','الحالة الاجتماعية'),
    'employer_name':('present employer or school name','current employer','employer name','اسم جهة العمل'),
    'occupation':('primary occupation','current occupation','occupation','المهنة'),
}


def _normal(value):
    value=unicodedata.normalize('NFKC',str(value or ''))
    value=''.join(str(unicodedata.decimal(c)) if c.isdecimal() else c for c in value)
    return re.sub(r'[^\w@]+',' ',value.casefold()).strip()


ALIASES={_normal(label):field for field,labels in LABELS.items() for label in labels}
OTHER_LABELS={_normal(label) for label in ('Passport Book Number','Passport/Travel Document Type','Other Names Used',
    'Full Name in Native Alphabet','Application ID','Do you have any other nationalities?','Country/Region of Birth')}
STAY_LABELS={_normal(label):field for field,labels in {
    'hotel_address':('street address (line 1)','street address line 1','street address','address'),
    'stay_city':('city',),'stay_state':('state',),'stay_zip':('zip code','zip/postal code','postal code'),
}.items() for label in labels}


def _date(value):
    value=str(value or '').strip()
    value=re.sub(r'^(?:Mon(?:day)?|Tue(?:sday)?|Wed(?:nesday)?|Thu(?:rsday)?|Fri(?:day)?|Sat(?:urday)?|Sun(?:day)?),?\s+','',value,flags=re.I)
    value=value.translate(str.maketrans('٠١٢٣٤٥٦٧٨٩','0123456789'))
    for fmt in ('%Y-%m-%d','%Y/%m/%d','%d-%b-%Y','%d %b %Y','%d %B %Y','%B %d, %Y','%b %d, %Y'):
        try:return datetime.strptime(value,fmt).date()
        except ValueError:pass
    # Numeric day/month vs month/day is genuinely ambiguous when both <= 12.
    match=re.fullmatch(r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})',value)
    if match:
        a,b,year=map(int,match.groups())
        try:
            if a>12 or a==b:return date(year,b,a)
            if b>12:return date(year,a,b)
        except ValueError:pass
    return None


def _canonical(field,value):
    if field.endswith(('_date','_date_of_birth')) or field in ('date_of_birth','passport_issue','passport_expiry'):
        parsed=_date(value)
        return parsed.isoformat() if parsed else None
    normalized=_normal(value)
    if not normalized or normalized in ('n a','unknown','not applicable','do not know','does not apply'):return None
    if field=='passport_number':return normalized.replace(' ','').upper()
    if field.endswith('full_name') or field in ('surname','given_names'):return tuple(sorted(normalized.split()))
    if field=='email':return str(value).strip().casefold()
    if field=='phone':return re.sub(r'\D','',str(value))
    if field=='gender':return {'m':'male','f':'female','male':'male','female':'female','ذكر':'male','انثى':'female','أنثى':'female'}.get(normalized)
    if field in ('nationality','birth_country','spouse_nationality'):
        return {'egy':'egypt','egyptian':'egypt','مصري':'egypt','مصرى':'egypt','مصرية':'egypt','مصر':'egypt',
                'usa':'united states','american':'united states','united states of america':'united states',
                'gbr':'united kingdom','british':'united kingdom','uk':'united kingdom'}.get(normalized,normalized)
    if field=='stay_city':return {'nyc':'new york','new york city':'new york','washington dc':'washington'}.get(normalized,normalized)
    if field=='birth_city':return {'سوهاج':'sohag','suhag':'sohag','القاهرة':'cairo','الجيزة':'giza','الإسكندرية':'alexandria','الغردقة':'hurghada'}.get(normalized,normalized)
    if field=='languages':return tuple(sorted(normalized.split()))
    if field=='trip_sponsor':return {'myself':'self','انا':'self','نفسي':'self'}.get(normalized,normalized)
    if field in ('monthly_salary','monthly_income'):
        compact=re.sub(r'[\s,]','',str(value))
        return format(float(compact),'.2f') if re.fullmatch(r'\d+(?:\.\d{1,2})?',compact) else None
    if field=='length_of_stay':
        match=re.fullmatch(r'(\d{1,3}) (day|week|month)s?(?: s)?',normalized)
        return (('months',int(match[1])) if match[2]=='month' else ('days',int(match[1])*(7 if match[2]=='week' else 1))) if match else None
    if field=='stay_zip':return normalized[:5] if re.fullmatch(r'\d{5}(?: \d{4})?',normalized) else normalized
    if field=='hotel_address':
        words={'st':'street','ave':'avenue','rd':'road','blvd':'boulevard','dr':'drive','ln':'lane','hwy':'highway'}
        return ' '.join(words.get(word,word) for word in normalized.split())
    return normalized


def _pdf_rows(raw):
    rows=[];limitations=[]
    with pymupdf.open(stream=raw,filetype='pdf') as pdf:
        for number,page in enumerate(pdf,1):
            if len(page.get_text().strip())>=20:
                for block in page.get_text('dict',sort=True)['blocks']:
                    for line in block.get('lines',[]):
                        text=''.join(span['text'] for span in line['spans']).strip()
                        if text:rows.append(dict(text=text,page=number,method='pdf_text',
                            box=[v/(page.rect.width if i%2==0 else page.rect.height) for i,v in enumerate(line['bbox'])]))
            else:
                from offline_ocr import pdf_lines
                try:
                    lines=pdf_lines(raw,pages=[number])
                    rows.extend(dict(text=line['text'],page=number,method='local_ocr',box=line.get('region_normalized'),confidence=line.get('confidence')) for line in lines)
                    limitations.append(f'Page {number}: OCR readings require verification against the original.')
                except Exception:
                    limitations.append(f'Page {number}: local OCR could not read this page.')
    return rows,limitations


def _read(name,raw,conversion=None):
    if conversion:
        rows=[dict(text=line.strip(),page=None,method='native_text',box=None,native_section=index)
              for index,line in enumerate(conversion['text'].splitlines(),1) if line.strip()]
        return rows,['Word/HTML text is read in its original order; evidence pages are reflowed.'] if conversion.get('has_images') else []
    if name.lower().endswith('.pdf'):return _pdf_rows(raw)
    from offline_ocr import image_lines
    lines=image_lines(raw)
    return [dict(text=line['text'],page=1,method='local_ocr',box=line.get('region_normalized'),confidence=line.get('confidence')) for line in lines],['Image OCR readings require verification against the original.']


def _label(text,category,section):
    # Accept labelled table cells as well as a colon-separated line.
    pieces=re.split(r'[:：]|\s*\|\s*|\t+',text,maxsplit=1)
    label=_normal(pieces[0])
    field=ALIASES.get(label)
    if category=='ds160' and section=='contact':
        field={'email':'us_contact_email','phone':'us_contact_phone'}.get(field,field)
        if label=='phone number':field='us_contact_phone'
    if label=='name' and category=='client_form' and section=='personal':field='full_name'
    if field is None and (category=='hotel' or section=='stay'):
        field=STAY_LABELS.get(label)
    if category=='hotel':field={'arrival_date':'check_in_date','departure_date':'check_out_date'}.get(field,field)
    if category in ('ds160','client_form') and section in ('other_person','contact','previous_work') and not (category=='ds160' and field and field.startswith('us_contact_')):
        return None,None
    if category=='ds160' and field in ('full_name','surname','given_names','date_of_birth','nationality','gender') and section not in ('personal','passport'):
        return None,None
    if category=='hotel' and field not in ('full_name','passport_number','hotel_name','hotel_address','hotel_phone','hotel_email','stay_city','stay_state','stay_zip','check_in_date','check_out_date'):
        return None,None
    return field,pieces[1].strip() if len(pieces)>1 else ''


def _section(text,current):
    normal=_normal(text.split(':',1)[0])
    if normal.startswith('address where you will stay'):return 'stay'
    if normal in ('hotel information','hotel details','accommodation details'):return 'stay'
    if normal.startswith(('u s contact','us contact','contact person','point of contact')):return 'contact'
    if normal.startswith(('father','mother','spouse','travel companions','other persons traveling','family information')):return 'other_person'
    if normal.startswith(('previous employer','previous work','previous employment')):return 'previous_work'
    if normal.startswith(('personal information','personal address')):return 'personal'
    if normal.startswith('passport information'):return 'passport'
    if normal.startswith(('travel information','person entity paying','person paying')):return 'travel'
    if normal.startswith(('address and phone','home address')):return 'personal_address'
    if normal.startswith(('work education','present work','present employer')):return 'work'
    return current


def extract_fields(category,name,raw,conversion=None):
    try:rows,limitations=_read(name,raw,conversion)
    except Exception:rows,limitations=[],['This document could not be read locally.']
    if sum(len(row['text']) for row in rows)>400000:
        rows=[];limitations.append('This document exceeds the local text review limit.')
    fields={};section='personal';candidates={}
    for index,row in enumerate(rows):
        section=_section(row['text'],section) if category in ('ds160','client_form') else section
        field,value=_label(row['text'],category,section)
        if not field:continue
        sources=[row]
        if not value and index+1<len(rows):
            following=rows[index+1]
            next_section=_section(following['text'],section)
            next_field,_=_label(following['text'],category,next_section)
            if (following['page']==row['page'] and not next_field and next_section==section and ':' not in following['text']
                    and _normal(following['text']) not in OTHER_LABELS):
                value=following['text'];sources.append(following)
        if not value or re.search(r'[:：|]',value) or _normal(value) in OTHER_LABELS or _normal(value) in ALIASES:continue
        # The address block heading often has no value. Never treat a following
        # label or a footer as an address simply because it follows the heading.
        if len(value)>500:continue
        evidence=[]
        for source in sources:
            evidence.append(dict(document=category,source_file=name,page=source['page'],field_name=field,
                value=value,text=source['text'],box=source['box'],local_source=True,method=source['method'],
                **({'native_section':source['native_section']} if 'native_section' in source else {})))
        candidates.setdefault(field,[]).append(dict(value=value,sources=evidence,
            provisional=any(source['method']=='local_ocr' for source in sources)))
    for field,values in candidates.items():
        canonical={repr(_canonical(field,v['value'])) for v in values}
        same=len(canonical)==1 and _canonical(field,values[0]['value']) is not None
        fields[field]=dict(value=values[0]['value'] if same else None,
            status='extracted' if same and not any(v['provisional'] for v in values) else 'needs_verification',
            sources=[source for item in values for source in item['sources']],
            alternatives=list(dict.fromkeys(item['value'] for item in values)))
    if 'full_name' not in fields and all(key in fields for key in ('surname','given_names')):
        first,last=fields['given_names'],fields['surname']
        fields['full_name']=dict(value=f"{first['value']} {last['value']}" if first['value'] and last['value'] else None,
            status='extracted' if first['status']==last['status']=='extracted' else 'needs_verification',
            sources=first['sources']+last['sources'],alternatives=[])
    if category=='passport' and any(row['method']=='local_ocr' for row in rows):
        from usa_passport_visual import read_fields
        image=raw
        if name.lower().endswith('.pdf'):
            with pymupdf.open(stream=raw,filetype='pdf') as pdf:
                image=pdf[0].get_pixmap(matrix=pymupdf.Matrix(2,2),alpha=False).tobytes('png')
        visual=read_fields([row for row in rows if row['page']==1],name,image,limitations)
        if visual:fields=visual
        if all(fields.get(k,{}).get('status')=='extracted' for k in
               ('full_name','passport_number','date_of_birth','passport_issue','passport_expiry')):
            limitations=[note for note in limitations if note!='Image OCR readings require verification against the original.']
    if category=='passport' and any(fields.get(key,{}).get('status')!='extracted' for key in ('full_name','passport_number','date_of_birth','passport_expiry')):
        _passport_template(name,raw,fields,limitations)
    if conversion and category=='client_form':
        from usa_templates import client_text_fields
        native=client_text_fields(conversion['text'],name)
        if native:fields=native
    if name.lower().endswith('.pdf') and conversion is None and category in ('ds160','client_form','hotel'):
        from usa_templates import ds_fields,client_fields,booking_fields
        native=booking_fields(raw,name,include_contact=True) if category=='hotel' else {'ds160':ds_fields,'client_form':client_fields}[category](raw,name)
        if native:
            if category=='hotel':fields.update(native)
            else:fields=native
            for key,entry in fields.items():
                for source in entry['sources']:source['document']=category
    contact={key:value for key,value in fields.items() if category=='hotel' and key in ('hotel_address','hotel_phone','hotel_email')}
    if category=='hotel':fields={key:value for key,value in fields.items() if key in ('hotel_name','check_in_date','check_out_date')}
    if not fields:limitations.append('No supported labelled fields were found. Supply a readable application/review printout or labelled client form.')
    text='\n'.join(row['text'] for row in rows)
    if category=='ds160' and not re.search(r'DS[ -]?160|Online Nonimmigrant Visa Application',text,re.I):
        limitations.append('The DS-160 document heading could not be verified.')
        for field in fields.values():field['status']='needs_verification'
    return dict(category=category,source_file=name,fields=fields,limitations=limitations,
        pages_read=sorted({r['page'] for r in rows if r['page'] is not None}),
        text_sections_read=[r['native_section'] for r in rows if 'native_section' in r],sha256=sha256(raw).hexdigest(),
        **({'hotel_contact':contact} if category=='hotel' else {}))


def _passport_template(name,raw,fields,limitations):
    """Reuse the inspected passport layout/MRZ checks, without guessing centuries."""
    try:
        from passport_template_extractor import extract_egypt_passport
        image=raw
        if name.lower().endswith('.pdf'):
            with pymupdf.open(stream=raw,filetype='pdf') as pdf:
                image=pdf[0].get_pixmap(matrix=pymupdf.Matrix(2,2),alpha=False).tobytes('png')
        report=extract_egypt_passport(image,name)
        mapping={'issue_date':'passport_issue','expiry_date':'passport_expiry','nationality_code':'nationality'}
        for key,row in report.get('fields',{}).items():
            target=mapping.get(key,key)
            value=row.get('normalized_value',row.get('value'))
            if row.get('status')!='extracted' or value is None or target not in LABELS:continue
            evidence=[dict(document='passport',source_file=name,page=1,field_name=target,value=str(value),
                text=source.get('text',''),box=source.get('region_normalized'),local_source=True,method='verified_passport_template')
                for source in row.get('sources',[])]
            if not evidence:continue
            previous=fields.get(target)
            if previous and previous['status']=='extracted' and _same(target,previous['value'],str(value)) is not True:
                fields[target]=dict(value=None,status='needs_verification',sources=previous['sources']+evidence,
                    alternatives=[previous['value'],str(value)])
            else:fields[target]=dict(value=str(value),status='extracted',sources=evidence,alternatives=[str(value)])
    except Exception:
        limitations.append('The supported passport layout could not verify additional fields.')


def _aggregate(documents,category,field):
    entries=[doc['fields'][field] for doc in documents if doc['category']==category and field in doc['fields']]
    usable=[entry for entry in entries if entry['status']=='extracted' and entry['value'] is not None]
    values={repr(_canonical(field,entry['value'])) for entry in usable}
    good=bool(usable) and len(values)==1 and len(usable)==len(entries)
    tentative=[entry['value'] for entry in entries if entry.get('value') is not None]
    value=usable[0]['value'] if good else tentative[0] if tentative and len(set(tentative))==1 else None
    return dict(value=value,status='extracted' if good else 'needs_verification',
        sources=[source for entry in entries for source in entry['sources']])


def _same(field,left,right):
    if field=='education_period':
        # The DS comparison currently derives a year range. Month/day detail
        # in the client form cannot be disproved by that coarser representation.
        years=lambda value:re.findall(r'\b(?:19|20)\d{2}\b',str(value or ''))
        a,b=years(left),years(right)
        if len(a)!=2 or len(b)!=2:return None
        if a!=b:return False
        year_only=r'\s*\d{4}\s*(?:[-–—/]|to)\s*\d{4}\s*'
        return True if all(re.fullmatch(year_only,str(v),re.I) for v in (left,right)) else None
    from usa_translation import assess
    translation=assess(field,left,right)
    if translation is not None:return translation['equivalent']
    a,b=_canonical(field,left),_canonical(field,right)
    if a is None or b is None:return None
    if field.endswith('full_name') or field in ('surname','given_names'):
        if bool(re.search('[\u0600-\u06ff]',str(left)))!=bool(re.search('[\u0600-\u06ff]',str(right))):return None
        if a!=b and any(len(word)==1 for word in a+b):return None
        if a!=b and len(a)!=len(b) and (Counter(a)<=Counter(b) or Counter(b)<=Counter(a)):return None
    if field=='phone' and a!=b and (a.endswith(b) or b.endswith(a)):return None
    if field in ('occupation','employer_address','education_name') and a!=b:
        if field=='employer_address' or a in ('other','business','student') or b in ('other','business','student'):return None
        if SequenceMatcher(None,a,b).ratio()>.65:return None
    if field=='hotel_name' and a!=b and (a.startswith(b+' ') or b.startswith(a+' ')):return None
    if field=='birth_city' and a!=b and bool(re.search('[\u0600-\u06ff]',a))!=bool(re.search('[\u0600-\u06ff]',b)):return None
    if field=='stay_state' and a!=b and (len(a)==2 or len(b)==2):return None
    if field=='hotel_address' and a!=b:
        address=re.compile(r'^(\d+[a-z]?) (.+ (?:street|avenue|road|boulevard|drive|lane|highway))$')
        x,y=address.fullmatch(a),address.fullmatch(b)
        if x and y and x[2]==y[2] and x[1]!=y[1]:return False
        return None  # Other formatting/room lines need a person.
    if field=='nationality' and a!=b and (len(a)==3 or len(b)==3):return None
    return a==b


def compare(documents):
    checks=[]
    def add(field,target,reference,required=False,target_category='ds160',reference_category='passport'):
        if not required and not (target['sources'] and reference['sources']):return
        status='needs_verification'
        if target['status']==reference['status']=='extracted':
            equal=_same(field,target['value'],reference['value'])
            if equal is not None:status='match' if equal else 'mismatch'
        if required or target['sources'] or reference['sources']:
            check=dict(field=field,status=status,target_category=target_category,reference_category=reference_category,
                found=target['value'],expected=reference['value'],sources=target['sources'],references=reference['sources'])
            from usa_translation import assess
            translation=assess(field,target['value'],reference['value'])
            if translation is not None:check['language_comparison']=translation
            checks.append(check)
    for category in USA_CATEGORIES:
        if not any(doc['category']==category for doc in documents):
            checks.append(dict(field='document_coverage',status='needs_verification',target_category=category,
                reference_category=category,found=None,expected='Readable '+NAMES[category],sources=[],references=[]))
    for document in documents:
        if document['limitations']:
            checks.append(dict(field='document_coverage',status='needs_verification',target_category=document['category'],
                reference_category=document['category'],found=None,expected='Verify document readability and extraction coverage',
                sources=[],references=[],source_file=document['source_file'],limitations=document['limitations']))
    identity=('full_name','surname','given_names','passport_number','date_of_birth','passport_issue','passport_expiry','nationality','gender')
    for field in identity:
        ds=_aggregate(documents,'ds160',field);passport=_aggregate(documents,'passport',field)
        client=_aggregate(documents,'client_form',field)
        if field not in ('surname','given_names') or not any(c['field']=='full_name' and c['status']=='match' and
                c['target_category']=='ds160' and c['reference_category']=='passport' for c in checks):
            add(field,ds,passport,required=bool(ds['sources']) or field in ('full_name','passport_number','date_of_birth','passport_expiry'))
        # Identity corrections always point to the passport. The client form
        # cannot supply an authoritative replacement when the passport is unreadable.
        if client['sources']:
            add(field,client,passport,required=True,target_category='client_form')
    for field in ('length_of_stay','hotel_address','stay_city','stay_state','stay_zip',
                  'email','phone','marital_status','employer_name','occupation','national_id_number','birth_city','birth_country',
                  'employment_start_date','monthly_salary','employer_address','employer_phone','education_name','education_course',
                  'father_full_name','father_date_of_birth','mother_full_name','mother_date_of_birth','spouse_full_name','spouse_date_of_birth',
                  'spouse_nationality','languages','trip_sponsor','social_facebook','social_instagram','social_linkedin','social_twitter',
                  'prior_refusal','prior_us_visit','military_service','relatives_us'):
        add(field,_aggregate(documents,'ds160',field),_aggregate(documents,'client_form',field),
            reference_category='client_form')
    hotels=[doc for doc in documents if doc['category']=='hotel']
    def hotel_date(doc,key):return _date(doc['fields'].get(key,{}).get('value'))
    ordered=sorted(hotels,key=lambda doc:hotel_date(doc,'check_in_date') or date.max)
    first=ordered[:1] if len(ordered)==1 or all(hotel_date(doc,'check_in_date') for doc in ordered) else []
    reference=_aggregate(first,'hotel','hotel_name');ds=_aggregate(documents,'ds160','hotel_name')
    if not ds['sources']:
        ds=_aggregate(documents,'ds160','us_contact_organization')
        if ds['sources'] and _same('hotel_name',ds['value'],reference['value']) is not True:ds={**ds,'status':'needs_verification'}
    add('hotel_name',ds,reference,required=True,reference_category='hotel')
    if ds['sources'] and any(doc['fields'].get('us_contact_organization') for doc in documents if doc['category']=='ds160'):
        checks[-1]['note_key']='usa_hotel_contact_name'
    contact_check=_hotel_contact_check(documents,first)
    if contact_check:
        # One contact-section correction replaces the weaker organization-name
        # advisory; neither the person's name nor personal email is a hotel fact.
        checks=[c for c in checks if not (c['field']=='hotel_name' and c['target_category']=='ds160' and c['reference_category']=='hotel')]
        checks.append(contact_check)
    if first:
        add('arrival_date',_aggregate(documents,'ds160','arrival_date'),_aggregate(first,'hotel','check_in_date'),
            required=True,reference_category='hotel')
    salary,income=_aggregate(documents,'ds160','monthly_salary'),_aggregate(documents,'client_form','monthly_income')
    if salary['sources'] and income['sources']:
        add('monthly_salary',salary,income,reference_category='client_form')
        checks[-1]['note_key']='usa_salary_basis'
        if checks[-1]['status']=='mismatch':checks[-1]['status']='needs_verification'
    education_start=_aggregate(documents,'ds160','education_start_date');education_end=_aggregate(documents,'ds160','education_end_date')
    period=_aggregate(documents,'client_form','education_period')
    a,b=_date(education_start['value']),_date(education_end['value'])
    if a and b and period['sources']:
        year_range=f'{a.year}-{b.year}'
        add('education_period',dict(value=year_range,status='extracted',sources=education_start['sources']+education_end['sources']),
            period,reference_category='client_form')
    # Preserve competing reference evidence instead of instructing the user to
    # copy a value when the passport and client form disagree.
    for check in checks:
        if check['target_category']=='ds160' and check['status']=='mismatch':
            references=[c for c in checks if c['field']==check['field'] and c['target_category']=='client_form' and c['reference_category']=='passport']
            if any(c['status']=='mismatch' for c in references) and check['reference_category']=='client_form':
                check['status']='needs_verification';check['reference_conflict']=True
    _stay_checks(documents,checks,ordered)
    hashes={doc['source_file']:doc['sha256'] for doc in documents}
    for check in checks:
        if {hashes.get(s['source_file']) for s in check['sources']} & {hashes.get(s['source_file']) for s in check['references']}:
            check['status']='needs_verification';check['duplicate_source']=True
    return _group_passport_identity(documents,checks)


def _hotel_contact_check(documents,hotels):
    if not any(doc['category']=='hotel' for doc in documents):return None
    contact={key:_aggregate(documents,'ds160','us_contact_'+key) for key in
             ('person','organization','relationship','address','phone','email')}
    if not any(value['sources'] for value in contact.values()):return None
    def present(item):
        return bool(item['value']) and _normal(item['value']) not in ('do not know','does not apply','n a','unknown')
    hotel=_aggregate(hotels,'hotel','hotel_name')
    organization=contact['organization'];relation=_normal(contact['relationship']['value'])
    person=present(contact['person']);org=present(organization)
    matches=_same('hotel_name',organization['value'],hotel['value']) if org and hotel['value'] else None
    personal=relation in ('relative','friend','parent','spouse','family') or person and not org
    missing=not org and not person
    different=org and matches is False
    if not (personal or missing or different):return None
    relevant=[contact[key] for key in ('person','organization','relationship') if contact[key]['sources']]
    trusted=bool(relevant) and all(item['status']=='extracted' for item in relevant) and hotel['status']=='extracted'
    found='\n'.join(label+': '+str(contact[key]['value']) for key,label in
                    (('person','Contact person'),('organization','Organization'),('relationship','Relationship')) if contact[key]['value'])
    expected=['Hotel: '+str(hotel['value'])] if hotel['value'] else []
    references=list(hotel['sources']);unavailable=[]
    for key,label in (('hotel_address','Address'),('hotel_phone','Phone'),('hotel_email','Email')):
        records=[{**doc,'fields':doc.get('hotel_contact',{})} for doc in hotels]
        item=_aggregate(records,'hotel',key)
        if item['status']=='extracted' and item['value']:
            expected.append(label+': '+item['value']);references+=item['sources']
        else:unavailable.append(key)
    return dict(field='us_contact_hotel',status='mismatch' if trusted else 'needs_verification',
        target_category='ds160',reference_category='hotel',found=found or None,expected='\n'.join(expected) or None,
        sources=[s for item in relevant for s in item['sources']],references=references,
        note_key='usa_contact_hotel_workflow',rule_basis='configured_hotel_contact_workflow',
        unavailable_contact_fields=unavailable)


def _group_passport_identity(documents,checks):
    """Point to the uploaded passport, rather than rewriting an agreed applicant."""
    ds_name=_aggregate(documents,'ds160','full_name');client_name=_aggregate(documents,'client_form','full_name')
    ds_number=_aggregate(documents,'ds160','passport_number')
    name=_aggregate(documents,'passport','full_name');number=_aggregate(documents,'passport','passport_number')
    expected=[ds_name,client_name,ds_number]
    passport_hashes={d['sha256'] for d in documents if d['category']=='passport'}
    application_hashes={d['sha256'] for d in documents if d['category'] in ('ds160','client_form')}
    if passport_hashes & application_hashes:return checks
    if not all(item['status']=='extracted' for item in expected):return checks
    if _same('full_name',ds_name['value'],client_name['value']) is not True:return checks
    if _same('full_name',ds_name['value'],name['value']) is not False:return checks
    if _same('passport_number',ds_number['value'],number['value']) is not False:return checks
    if not name['sources'] or not number['sources']:return checks
    verified=name['status']==number['status']=='extracted'
    identity={'full_name','surname','given_names','passport_number','date_of_birth','passport_issue','passport_expiry','nationality','gender'}
    # The original field readings remain in usa_documents. These dependent
    # comparisons are consolidated so one wrong file does not create many fixes.
    checks=[c for c in checks if not (c['field'] in identity and 'passport' in (c['target_category'],c['reference_category']))]
    checks.insert(0,dict(field='passport_identity',status='mismatch' if verified else 'needs_verification',
        target_category='passport',reference_category='ds160',found=f"{name['value']}\n{number['value']}",
        expected=f"{ds_name['value']}\n{ds_number['value']}",sources=name['sources']+number['sources'],
        references=ds_name['sources']+ds_number['sources']+client_name['sources'],identity_conflict=True,
        note_key='usa_wrong_passport_verified' if verified else 'usa_wrong_passport_provisional'))
    return checks


def _stay_checks(documents,checks,hotels):
    arrival=_aggregate(documents,'ds160','arrival_date');departure=_aggregate(documents,'ds160','departure_date')
    start=_date(arrival['value']) if arrival['status']=='extracted' else None
    end=_date(departure['value']) if departure['status']=='extracted' else None
    ends=[end] if end else []
    sources=arrival['sources']+departure['sources']
    if start and not end:
        length=_aggregate(documents,'ds160','length_of_stay')
        match=re.fullmatch(r'\s*(\d{1,3})\s*(day|week|month)s?(?:\(s\))?\s*',str(length['value'] or ''),re.I)
        if match and length['status']=='extracted' and int(match[1])>0:
            count=int(match[1]);unit=match[2].lower()
            if unit in ('day','week'):end=start+timedelta(days=count*(7 if unit=='week' else 1))
            else:
                month=start.month-1+count;year=start.year+month//12;month=month%12+1
                if year<=9999:end=date(year,month,min(start.day,monthrange(year,month)[1]))
            sources+=length['sources']
            if end:
                # A stated number of days may count both arrival/departure days.
                # Do not invent a one-night gap from an unstated day convention.
                ends=[end-timedelta(days=1),end] if unit in ('day','week') else [end]
    intervals=[];references=[]
    for hotel in hotels:
        a,b=hotel['fields'].get('check_in_date',{}),hotel['fields'].get('check_out_date',{})
        x,y=_date(a.get('value')),_date(b.get('value'))
        if x and y and x<y and a.get('status')==b.get('status')=='extracted':intervals.append((x,y))
        references+=a.get('sources',[])+b.get('sources',[])
    status='needs_verification';found=None
    if start and end and start>=end:
        checks.append(dict(field='departure_date',status='mismatch',target_category='ds160',reference_category='ds160',
            found=end.isoformat(),expected='After '+start.isoformat(),sources=departure['sources'],references=arrival['sources']))
    if start and ends and start<max(ends) and intervals and len(intervals)==len(hotels):
        cursor=start
        for x,y in sorted(intervals):
            if x<=cursor<y:cursor=y
        status='match' if cursor>=min(ends) else 'mismatch'
        found='; '.join(f'{x.isoformat()} → {y.isoformat()}' for x,y in intervals)
    checks.append(dict(field='hotel_coverage_gap',status=status,target_category='hotel',reference_category='ds160',
        found=found,expected=f'{start.isoformat()} → {end.isoformat()}' if start and end else 'Readable DS-160 arrival and departure / length of stay',
        sources=references,references=sources,possible_departure_dates=[day.isoformat() for day in ends],
        **({'note_key':'usa_duration_basis'} if len(ends)>1 else {})))
    if ends and intervals and len(intervals)==len(hotels):
        checkout=max(y for _,y in intervals)
        checks.append(dict(field='check_out_date',status='match' if checkout in ends else 'mismatch',
            target_category='hotel',reference_category='ds160',found=checkout.isoformat(),
            expected=' / '.join(day.isoformat() for day in ends),sources=references,references=sources,
            possible_departure_dates=[day.isoformat() for day in ends],
            **({'note_key':'usa_duration_basis'} if len(ends)>1 else {})))


def _issues(checks):
    issues=[]
    for check in checks:
        if check['status']=='match':continue
        mismatch=check['status']=='mismatch';field=check['field'];reference=NAMES[check['reference_category']]
        en=f'{field_label(field,"en")}: compare with {reference}.'
        ar=f'{field_label(field,"ar")}: قارن بالمستند المرجعي {t("doc_"+check["reference_category"],"ar")}.'
        if field=='us_contact_hotel':
            en=t('usa_contact_hotel_workflow','en');ar=t('usa_contact_hotel_workflow','ar')
        elif check.get('identity_conflict'):
            en=t(check['note_key'],'en');ar=t(check['note_key'],'ar')
        elif check.get('reference_conflict'):
            en=t('usa_reference_conflict','en');ar=t('usa_reference_conflict','ar')
        elif not mismatch and check.get('language_comparison',{}).get('equivalent') is None and check.get('language_comparison'):
            en='Verify the translation in the original documents. The local language check cannot establish equivalence; this is not a confirmed mismatch.'
            ar='تحقق من الترجمة في المستندات الأصلية. لم يتمكن الفحص المحلي من تأكيد تطابق المعنى؛ هذا ليس اختلافاً مؤكداً.'
        elif not mismatch:
            en=t('usa_field_unavailable','en');ar=t('usa_field_unavailable','ar')
        issues.append(ValidationIssue(document_name=NAMES[check['target_category']],field_name=field,
            found_value=check['found'],expected_value=check['expected'] or 'Verify the original source',
            severity=Severity.CRITICAL if field in ('passport_identity','passport_number','full_name','date_of_birth') else Severity.HIGH,
            recommended_fix=en,fix_ar=ar,title_en=field_label(field,'en'),title_ar=field_label(field,'ar'),
            message_key='usa.'+field,evidence=check['sources'],reference_evidence=check['references'],
            affects_score=mismatch,check_origin='local_workflow_rule' if field=='us_contact_hotel' else
                'local_bilingual_comparison' if check.get('language_comparison') else 'local_text_comparison'))
    return issues


def review_documents(uploaded_files,lang='en',progress=None,extraction_cache=None):
    validate_uploads(uploaded_files,allowed_categories=USA_CATEGORIES)
    files,conversions=normalize_uploads(uploaded_files)
    # Identical filenames must never point screenshots/quotes at another upload.
    names=Counter(name for group in files.values() for name,_ in group)
    files={category:[(f'{category}/{index}/{name}' if names[name]>1 else name,raw)
                     for index,(name,raw) in enumerate(group,1)] for category,group in files.items()}
    total=0
    for group in files.values():
        for name,raw in group:
            if name.lower().endswith('.pdf'):
                with pymupdf.open(stream=raw,filetype='pdf') as pdf:total+=len(pdf)
            else:total+=1
    if total>180:raise ValueError('upload_limit')
    if progress:progress(1)
    documents=[]
    for category,group in files.items():
        for name,raw in group:
            conversion=conversions.get(sha256(raw).hexdigest())
            report=cached_parse(extraction_cache,VERSION+':'+category,[(name,raw)],
                lambda category=category,name=name,raw=raw,conversion=conversion:extract_fields(category,name,raw,conversion))
            documents.append(report)
    if progress:progress(2)
    checks=compare(documents);issues=_issues(checks)
    if progress:progress(3)
    provenance=dict(engine=VERSION,external_ai_requests=0,documents=documents,checks=checks)
    extraction=VisaDocumentExtraction(extraction_mode='local',review_provenance=provenance)
    if progress:progress(4)
    return dict(extraction=extraction,issues=issues,score=calculate_score(issues),lang=lang,
        engine=VERSION,visa_program='usa',source_files=files,converted_sources=conversions,provenance=provenance,
        usa_documents=documents,usa_checks=checks,narrative_requested=False,
        incomplete=any(check['status']=='needs_verification' for check in checks) or any(doc['limitations'] for doc in documents))
