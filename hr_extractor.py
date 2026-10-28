"""Offline HR evidence: one combined letter or several complementary documents.

Scanned HR answers remain provisional: OCR confidence is not handwriting verification.
No personal sample answers, document instructions, or API requests drive extraction.
"""
from datetime import date
from hashlib import sha256
import re
import unicodedata

import pymupdf


FIELDS=('employee_name','company_name','job_title','leave_start','leave_end',
        'leave_approved','net_salary','gross_salary','salary_currency','company_address')
LABELS={
    'employee_name':'HR employee name','company_name':'HR company/employer name',
    'job_title':'HR job title','leave_start':'HR leave start date','leave_end':'HR leave end date',
    'leave_approved':'HR leave approval','net_salary':'HR net salary',
    'gross_salary':'HR gross salary','salary_currency':'HR salary currency',
    'company_address':'HR company address',
}
_DIGITS=str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹','01234567890123456789')


def canonical(text):
    text=unicodedata.normalize('NFKC',str(text)).translate(_DIGITS).casefold()
    text=text.translate(str.maketrans({'أ':'ا','إ':'ا','آ':'ا','ى':'ي','ة':'ه'}))
    text=re.sub(r'[\u064b-\u065f\u0670\u0640]','',text)
    return ' '.join(re.findall(r'[\w]+',text))


def normalize_date(value):
    value=str(value).translate(_DIGITS).strip()
    match=re.fullmatch(r'(\d{4})\s*[-/]\s*(\d{1,2})\s*[-/]\s*(\d{1,2})',value)
    if match:year,month,day=map(int,match.groups())
    else:
        match=re.fullmatch(r'(\d{1,2})\s*[-/]\s*(\d{1,2})\s*[-/]\s*(\d{4})',value)
        if not match:return None
        day,month,year=map(int,match.groups())
    try:return date(year,month,day).isoformat()
    except ValueError:return None


def normalize_money(value):
    text=str(value).translate(_DIGITS).strip().replace('٬',',').replace('٫','.')
    text=text.replace('،',',').replace(' ','')
    if re.fullmatch(r'\d{1,3}(?:,\d{3})+,\d{2}',text):
        whole,decimals=text.rsplit(',',1);text=whole.replace(',','')+'.'+decimals
    elif re.fullmatch(r'\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?',text):text=text.replace(',','')
    elif re.fullmatch(r'\d+,\d{2}',text):text=text.replace(',','.')
    if not re.fullmatch(r'\d+(?:\.\d{1,2})?',text):return None
    return text


def _field(key,value,sources,*,provisional=False,reason=None):
    normalized=value
    if key in ('leave_start','leave_end'):normalized=normalize_date(value)
    elif key in ('net_salary','gross_salary'):normalized=normalize_money(value)
    elif key=='leave_approved' and not isinstance(value,bool):normalized=None
    status='missing' if value is None else 'needs_verification' if provisional else 'extracted'
    if value is not None and normalized is None:status='needs_verification'
    return dict(key=key,value=value,normalized_value=normalized,status=status,sources=sources,
                reason=reason or ('Scanned/handwritten HR evidence requires confirmation.' if provisional else None))


def _sources(lines,filename):
    return [dict(source_file=filename,page=line['page'],text=line['text'],
                 method=line.get('method','pdf_text'),confidence=line.get('confidence'),
                 region_normalized=line.get('region_normalized')) for line in lines]


def parse_hr_lines(lines,filename):
    """Parse independent source lines; never fill a value from the visa form."""
    fields=[]
    text=' '.join(canonical(line['text']) for line in lines)
    salary=('رواتب' in text or 'الراتب' in text or 'salary' in text or 'pay slip' in text)
    leave_request=('طلب اجازه' in text or 'leave request' in text)
    employment=('بيان حاله وظيف' in text or 'employment status' in text)
    kind='salary' if salary else 'leave_request' if leave_request else 'employment_status' if employment else 'combined_or_unknown'
    def add(key,value,selected,reason=None):
        provisional=any(line.get('method')!='pdf_text' for line in selected)
        fields.append(_field(key,value,_sources(selected,filename),provisional=provisional,reason=reason))

    # Fixed handwritten form regions are used only after its heading is recognized.
    # All readings from these scanned regions stay provisional, even at high OCR scores.
    region_fields={
        'employment_status':{
            'employee_name':(.20,.18,.78,.235),'job_title':(.25,.35,.75,.405),
        },
        'leave_request':{
            'leave_start':(.55,.18,.80,.222),'leave_end':(.15,.18,.41,.225),
        },
    }
    for key,region in region_fields.get(kind,{}).items():
        selected=[line for line in lines if line['page']==1 and line.get('region_normalized') and
                  region[0]<=sum(line['region_normalized'][::2])/2<=region[2] and
                  region[1]<=sum(line['region_normalized'][1::2])/2<=region[3]]
        if selected:add(key,' '.join(line['text'] for line in selected),selected)

    salary_unit=r'(?:EGP|USD|EUR|GBP|جنيه\s+مصري|جنيه\s+[إا]سترليني|دولار\s+[أا]مريكي|يورو|ج\.\s*م)'
    def unit_code(value):
        value=value.strip()
        if value.upper() in ('EGP','USD','EUR','GBP'):return value.upper()
        if 'مصري' in value or re.fullmatch(r'ج\.\s*م',value):return 'EGP'
        if 'سترليني' in value:return 'GBP'
        if 'دولار' in value:return 'USD'
        if 'يورو' in value:return 'EUR'
        return value
    patterns={
        'employee_name':r'^(?:employee(?:\s+full)?\s+name|name\s+of\s+employee|اسم\s+الموظف)\s*[:：\-/]?\s*(.+)$',
        'company_name':r'^(?:company(?:\s+name)?|employer(?:\s+name)?|organization|اسم\s+الشرك[ةه]|جه[ةه]\s+العمل|الادار[ةه])\s*[:：\-/]\s*(.+)$',
        'company_address':r'^(?:company\s+address|employer(?:\x27s)?\s+address|workplace\s+address|عنوان\s+(?:الشرك[ةه]|جه[ةه]\s+العمل|العمل))\s*[:：\-/]\s*(.+)$',
        'job_title':r'^(?:job\s+title|position|occupation|الوظيف[ةه]|المسمي\s+الوظيفي)\s*[:：\-/]\s*(.+)$',
        'leave_start':r'^(?:approved\s+leave\s+start(?:\s+date)?|leave\s+start(?:\s+date)?|بداي[ةه]\s+الاجاز[ةه])\s*[:：]\s*(.+)$',
        'leave_end':r'^(?:approved\s+leave\s+end(?:\s+date)?|leave\s+end(?:\s+date)?|نهاي[ةه]\s+الاجاز[ةه])\s*[:：]\s*(.+)$',
        'net_salary':r'^(?:net\s+(?:monthly\s+)?salary|صافي\s+الراتب|الصافي)\s*[:：]\s*([\d٠-٩۰-۹.,،٬٫ ]+)(?:\s*'+salary_unit+r')?$',
        'gross_salary':r'^(?:gross\s+(?:monthly\s+)?salary|[إا]جمالي\s+الراتب)\s*[:：]\s*([\d٠-٩۰-۹.,،٬٫ ]+)(?:\s*'+salary_unit+r')?$',
        'salary_currency':r'^(?:salary\s+currency|currency|عمل[ةه]\s+الراتب)\s*[:：]\s*('+salary_unit+r')$',
    }
    for line in lines:
        value=line['text'].strip()
        for key,pattern in patterns.items():
            match=re.match(pattern,value,re.I)
            if match:
                add(key,unit_code(match[1]) if key=='salary_currency' else match[1].strip(),[line])
                if key in ('net_salary','gross_salary'):
                    unit=re.search(salary_unit+r'$',value,re.I)
                    if unit:add('salary_currency',unit_code(unit.group()),[line])
        # Printed organization header/administration is evidence, not a bank or signer name.
        if kind=='employment_status' and line.get('region_normalized',[0,1,0,1])[1]<.14 and canonical(value).startswith('مستشفي '):
            add('company_name',value,[line])
        if kind=='salary' and canonical(value).startswith('الاداره '):
            add('company_name',re.sub(r'^الادار[ةه]\s*[:：]?\s*','',value),[line])
        negated=bool(re.search(r'\b(?:not approved|not authorized|denied|rejected|pending approval)\b',value,re.I) or
                     re.search(r'(?:لم\s+تتم\s+الموافق[ةه]|غير\s+موافق|مرفوض|قيد\s+الموافق[ةه])',value))
        native=canonical(value)
        positive=bool(re.search(r'\bleave\s+(?:(?:is|has\s+been)\s+)?(?:approved|authorized)\b',value,re.I) or
                      re.search(r'\bapproved\s+(?:annual\s+)?leave\b.*\bfrom\b.*\b(?:to|until|through)\b',value,re.I) or
                      re.search(r'تمت\s+الموافقه\s+علي\s+الاجازه',native) or
                      ('لا مانع' in native and (leave_request or 'اجازه' in native)))
        # A title like "Leave approval" or a signature/stamp is insufficient.
        if negated:add('leave_approved',False,[line])
        elif positive:add('leave_approved',True,[line])
        if not leave_request:
            period=re.search(r'(?:approved\s+(?:annual\s+)?leave|leave\s+(?:is\s+)?approved).*?\bfrom\s+(\d{1,4}[-/]\d{1,2}[-/]\d{1,4})\s+(?:to|until|through)\s+(\d{1,4}[-/]\d{1,2}[-/]\d{1,4})',value,re.I)
            if period:
                add('leave_start',period[1],[line]);add('leave_end',period[2],[line])

    # Salary-table values are paired spatially with the net label, never with a random amount.
    if kind=='salary':
        for label in lines:
            if canonical(label['text']) not in ('الصافي','صافي الراتب'):continue
            rect=label.get('region_normalized')
            if not rect:continue
            selected=[line for line in lines if line['page']==label['page'] and line.get('region_normalized') and
                      line['region_normalized'][2]<rect[0] and
                      abs(sum(line['region_normalized'][1::2])/2-sum(rect[1::2])/2)<.018 and
                      normalize_money(line['text']) is not None]
            if len(selected)==1:add('net_salary',selected[0]['text'],[label,*selected])
    return dict(source_file=filename,kind=kind,fields=fields,
                notes=['Leave request dates and signature boxes do not prove approval.'] if leave_request else [])


def hr_pdf_lines(raw,language='ar'):
    """Native text first; optional Arabic model reads scans locally."""
    from offline_ocr import pdf_lines
    if language=='en':return pdf_lines(raw)
    result=[]
    with pymupdf.open(stream=raw,filetype='pdf') as pdf:
        for number,page in enumerate(pdf,1):
            if len(page.get_text().strip())>=30:
                for block in page.get_text('dict')['blocks']:
                    for line in block.get('lines',[]):
                        text=''.join(span['text'] for span in line['spans']).strip()
                        if text:result.append(dict(text=text,page=number,confidence=None,method='pdf_text',
                            region_normalized=[line['bbox'][0]/page.rect.width,line['bbox'][1]/page.rect.height,
                                               line['bbox'][2]/page.rect.width,line['bbox'][3]/page.rect.height]))
            else:
                from offline_ocr import arabic_image_lines
                pix=page.get_pixmap(matrix=pymupdf.Matrix(2,2),alpha=False)
                result.extend(dict(line,page=number) for line in arabic_image_lines(pix.tobytes('png')))
    return result


def extract_hr_documents(documents,language='ar',reviewed=None):
    """documents is [(filename, pdf_bytes)]; all fragments remain independent evidence."""
    names=[name for name,_ in documents]
    if len(set(names))!=len(names):raise ValueError('HR source filenames must be unique.')
    records=[]
    for filename,raw in documents:
        lines=hr_pdf_lines(raw,language)
        record=parse_hr_lines(lines,filename)
        with pymupdf.open(stream=raw,filetype='pdf') as pdf:page_count=len(pdf)
        record.update(source_sha256=sha256(raw).hexdigest(),pages=page_count,lines=lines)
        records.append(record)
    result=merge_hr_records(records)
    if reviewed is not None:apply_hr_review(result,reviewed)
    return result


def merge_hr_records(records):
    fields={}
    for key in FIELDS:
        candidates=[field for record in records for field in record['fields'] if field['key']==key]
        if not candidates:fields[key]=_field(key,None,[]);continue
        distinct={canonical(field['normalized_value'] if field['normalized_value'] is not None else field['value']) for field in candidates}
        row=dict(candidates[0],sources=[source for field in candidates for source in field['sources']],candidates=candidates)
        if len(distinct)>1:
            row.update(value=None,normalized_value=None,status='conflict',reason='HR files contain different readings for this field; confirm the originals.')
        elif any(field['status']!='extracted' for field in candidates):row['status']='needs_verification'
        fields[key]=row
    return dict(documents=records,fields=fields,values={key:field['normalized_value'] for key,field in fields.items()},
                ai_requests=0,status='extracted' if all(fields[key]['status']=='extracted' for key in FIELDS[:6]) else 'needs_verification')


def make_hr_review_template(hr):
    return dict(documents={doc['source_file']:doc['source_sha256'] for doc in hr['documents']},
                instructions='Confirm values by reading the original HR PDF. Fill value, source_file, page and confirmed=true. OCR suggestions remain unconfirmed.',
                fields={key:dict(value=field.get('normalized_value'),source_file=field['sources'][0]['source_file'] if field['sources'] else None,
                                 page=field['sources'][0]['page'] if field['sources'] else None,confirmed=False)
                        for key,field in hr['fields'].items()})


def apply_hr_review(hr,review):
    hashes={doc['source_file']:doc['source_sha256'] for doc in hr['documents']}
    pages={doc['source_file']:doc['pages'] for doc in hr['documents']}
    for key,answer in review.get('fields',{}).items():
        if answer.get('confirmed') is not True:continue
        if key not in FIELDS:raise ValueError('Unknown reviewed HR field: '+key)
        source=answer.get('source_file');page=answer.get('page');value=answer.get('value')
        if source not in hashes or review.get('documents',{}).get(source)!=hashes[source]:
            raise ValueError('Reviewed HR source is missing or changed: '+str(source))
        if not isinstance(page,int) or isinstance(page,bool) or not 1<=page<=pages[source]:raise ValueError('Invalid HR source page.')
        if key=='leave_approved':
            if not isinstance(value,bool):raise ValueError('Leave approval must be true or false.')
        elif not isinstance(value,str) or not value.strip():raise ValueError('Reviewed HR values must be non-empty text.')
        field=_field(key,value,[dict(source_file=source,page=page,method='manual_confirmation',text=value)])
        if field['normalized_value'] is None:raise ValueError('Invalid reviewed value for '+key)
        field['ocr_candidates']=hr['fields'][key]
        field['status']='confirmed'
        hr['fields'][key]=field;hr['values'][key]=field['normalized_value']
    hr['status']='extracted' if all(hr['fields'][key]['status'] in ('extracted','confirmed') for key in FIELDS[:6]) else 'needs_verification'


def compare_hr_with_application(hr,application):
    values=application.get('normalized_values',{})
    app_fields={field['key']:field for field in application.get('fields',[])}
    checks=[]
    def check(key,keys,found,expected,left,right,matched,reason=None):
        if any(hr['fields'][field]['status'] not in ('extracted','confirmed') for field in keys):
            matched=None;reason='Read and confirm the HR source: the value is missing, provisional or conflicting.'
        checks.append(dict(check=key,status='unverified' if matched is None else 'match' if matched else 'mismatch',
                           found=found,expected=expected,found_label=left,expected_label=right,
                           message=reason if matched is None and reason else f'{left} '+('matches ' if matched else 'does not match ')+right[0].lower()+right[1:]+'.',
                           sources=[source for field in keys for source in hr['fields'][field]['sources']]))
    for key,app_key,right in [('company_name','employment_or_education.name','Visa application employer name'),
                               ('job_title','occupation.current','Visa application occupation'),
                               ('company_address','employment_or_education.address','Visa application company address')]:
        found=hr['values'].get(key);expected=values.get(app_key)
        if key=='company_address' and found is None and expected is None:continue
        matched=None if found is None or expected is None else canonical(found)==canonical(expected)
        reason=None
        if found and expected and bool(re.search('[\u0600-\u06ff]',str(found)))!=bool(re.search('[\u0600-\u06ff]',str(expected))):
            matched=None;reason='HR and visa application use different languages. Confirm the translation/equivalence; it is not a spelling mismatch.'
        if app_key in app_fields and app_fields[app_key].get('status') not in ('extracted','confirmed','blank'):
            matched=None;reason='The visa application employer field also needs verification before comparison.'
        check('hr.'+key,[key],found,expected,LABELS[key],right,matched,reason)
    given=values.get('applicant.given_names');surname=values.get('applicant.surname')
    name=' '.join(str(value) for value in (given,surname) if value) or None
    employee=hr['values'].get('employee_name')
    from booking_template_extractor import name_matches
    matched=name_matches(employee,given,surname)
    reason=None
    if employee and name and bool(re.search('[\u0600-\u06ff]',str(employee)))!=bool(re.search('[\u0600-\u06ff]',name)):
        matched=None;reason='HR employee name and visa application name use different scripts; a confirmed native-name/translation reference is required.'
    check('hr.employee_name',['employee_name'],employee,name,LABELS['employee_name'],'Visa application applicant name',matched,reason)
    approved=hr['values'].get('leave_approved')
    check('hr.leave_approval',['leave_approved'],approved,True,LABELS['leave_approved'],'Explicit approval of leave',None if approved is None else approved is True,
          'An explicit leave approval could not be verified; a request heading or stamp alone is insufficient.')
    start=hr['values'].get('leave_start');end=hr['values'].get('leave_end')
    arrival=values.get('journey.intended_arrival');departure=values.get('journey.intended_departure')
    dates=[normalize_date(value) if value else None for value in (start,end,arrival,departure)]
    matched=None;reason='Valid HR leave and application travel dates are required.'
    if all(dates):
        start,end,arrival,departure=dates
        if start>end or arrival>departure:reason='The leave or travel date range is reversed; confirm the dates.'
        else:matched=start<=arrival and end>=departure;reason=None
    check('hr.leave_covers_trip',['leave_start','leave_end'],f'{start or "?"} to {end or "?"}',
          f'{arrival or "?"} to {departure or "?"}','HR leave period','Visa application travel period',matched,reason)
    for row in checks:
        if row['check']=='hr.leave_covers_trip' and row['status']!='unverified':
            row['message']='HR leave dates cover the full application travel period.' if row['status']=='match' else 'HR leave dates do not cover the full application travel period.'
    return dict(checks=checks,notes=['Salary is recorded as HR evidence; the supplied visa form has no salary field, so no salary-match check is invented.',
                                  'Company/employer means the employing organization. Signer/approver names are not substituted for the employee.'])
