"""Native PDF layout adapters inspected against the supplied USA form layouts.

Only whitelisted applicant fields are returned. Appointment passwords/security
answers, booking PINs and unrelated content are never added to extraction JSON.
"""
from datetime import date
import re

import pymupdf


def _key(text):return re.sub(r'[^a-z0-9]+',' ',text.casefold()).strip()


def _source(name,page,field,value,text,box,method='pdf_text'):
    return dict(document='',source_file=name,page=page,field_name=field,value=value,text=text.strip(),
        box=list(box) if box else None,local_source=True,method=method)


def _put(fields,category,name,page,key,value,text,box,status='extracted',basis=None):
    value=re.sub(r'\s+',' ',str(value or '')).strip()
    if not value or not re.search(r'\w',value) or (_key(value) in ('does not apply','do not know') and not key.startswith('us_contact_')):return
    source=_source(name,page,key,value,text,box);source['document']=category
    entry=dict(value=value,status=status,sources=[source],alternatives=[value])
    if basis:entry['basis']=basis
    old=fields.get(key)
    if old:
        if _key(old['value'] or '')!=_key(value):
            entry.update(value=None,status='needs_verification',alternatives=list(dict.fromkeys(old['alternatives']+[value])))
        entry['sources']=old['sources']+entry['sources']
    fields[key]=entry


CLIENT_LABELS={
    'full name as in passport':'full_name','gender':'gender','date of birth':'date_of_birth',
    'place of birth city governorate':'birth_city','country of birth':'birth_country',
    'current nationality':'nationality','national id number':'national_id_number','marital status':'marital_status',
    'current address':'home_address','city and country of residence':'home_city_country',
    'mobile number':'phone','personal email':'email','current job title':'occupation',
    'company employer name':'employer_name','company address':'employer_address',
    'company phone number':'employer_phone','monthly salary':'monthly_salary',
    'employment start date':'employment_start_date','college university name':'education_name',
    'major':'education_course','study period from to':'education_period',
    'father full name':'father_full_name','father date of birth':'father_date_of_birth',
    'mother full name':'mother_full_name','mother date of birth':'mother_date_of_birth',
    'spouse full name if married':'spouse_full_name','spouse date of birth':'spouse_date_of_birth',
    'spouse nationality':'spouse_nationality','languages you speak':'languages',
    'average monthly income':'monthly_income','who will sponsor the trip':'trip_sponsor',
    'facebook link or username':'social_facebook','instagram link or username':'social_instagram',
    'linkedin link or username':'social_linkedin','twitter x link or username':'social_twitter',
    'have you ever been refused a u s visa':'prior_refusal',
    'have you ever travelled to the u s':'prior_us_visit',
    'did you serve in the military':'military_service',
    'do you have any relatives in the u s whether first degree relatives or any other relatives':'relatives_us',
}
CHOICES={'gender':('male','female'),'marital_status':('single','married','divorced','widowed'),
         'prior_refusal':('yes','no'),'prior_us_visit':('yes','no'),'military_service':('yes','no'),
         'relatives_us':('yes','no')}


def _choice(text,choices):
    # Support both leading boxes and ticks trailing an English/Arabic label.
    # Never transfer a trailing tick to the next option just because it occurs
    # before that option in the text stream. Ambiguous placement is not a choice.
    clean=re.sub(r'[\u200e\u200f\u202a-\u202e\u2066-\u2069]','',text).replace('\xa0',' ')
    matches=list(re.finditer(r'\b('+'|'.join(choices)+r')\b',clean,re.I))
    if not matches:return text,'needs_verification'
    if len(matches)==1 and _key(clean) in choices and not re.search(r'[☐□]',clean):
        return matches[0][1].lower(),'extracted'
    bounds=[]
    for i,match in enumerate(matches):
        end=matches[i+1].start() if i+1<len(matches) else len(clean)
        arabic=list(re.finditer(r'[\u0600-\u06ff]+',clean[match.end():end]))
        bounds.append((match.start(),match.end()+arabic[-1].end() if arabic else match.end(),match[1].lower()))
    ticks=list(re.finditer(r'[☑✅✓✔]',clean));selected=[];ambiguous=False
    for tick in ticks:
        previous=next((i for i in range(len(bounds)-1,-1,-1) if bounds[i][0]<tick.start()),None)
        following=next((i for i,bound in enumerate(bounds) if bound[0]>tick.start()),None)
        if previous is None:chosen=following
        elif following is None or tick.start()<bounds[previous][1]:chosen=previous
        else:
            suffix=tick.start()-bounds[previous][1]
            prefix=bounds[following][0]-tick.end()
            if tick[0] in '✓✔' and suffix==0 and prefix>0:chosen=previous
            elif tick[0] in '✓✔' and prefix==0 and suffix>0:chosen=following
            elif suffix<=1 and prefix>=2:chosen=previous
            elif prefix<=1 and (suffix>=2 or tick[0] in '☑✅'):chosen=following
            else:chosen=None
        if chosen is None:ambiguous=True
        else:selected.append(bounds[chosen][2])
    if ticks:
        if not ambiguous and len(set(selected))==1:return selected[0],'extracted'
        return text,'needs_verification'
    unboxed=[]
    for i,match in enumerate(matches):
        prefix=clean[matches[i-1].end() if i else 0:match.start()]
        if not re.search(r'[☐□]',prefix):unboxed.append(match[1].lower())
    if len(unboxed)==1 and len(matches)>1:return unboxed[0],'needs_verification'
    return text,'needs_verification'


def client_fields(raw,name):
    fields={};section=''
    with pymupdf.open(stream=raw,filetype='pdf') as doc:
        if 'U.S. Visa Client Information Form' not in doc[0].get_text():return {}
        for page_number,page in enumerate(doc,1):
            for table in page.find_tables().tables:
                for row in table.rows:
                    cells=[]
                    for box in row.cells:
                        if box:
                            text=page.get_text('text',clip=pymupdf.Rect(box),sort=True).strip()
                            if text:cells.append((box,text))
                    if not cells:continue
                    joined=_key(' '.join(text for _,text in cells))
                    if len(cells)==1:
                        if 'previous employment' in joined:section='previous_work'
                        elif 'current employment' in joined:section='current_work'
                        elif 'education' in joined:section='education'
                        continue
                    label=_key(cells[0][1])
                    key=next((field for phrase,field in sorted(CLIENT_LABELS.items(),key=lambda x:-len(x[0]))
                              if phrase in label),None)
                    if not key or (section=='previous_work' and key=='employment_start_date'):continue
                    box,value=cells[1]
                    if not re.search(r'[^_\s☐□/]',value):continue
                    status='extracted'
                    if key in CHOICES:value,status=_choice(value,CHOICES[key])
                    if key in ('monthly_salary','monthly_income') and not re.fullmatch(r'[\d, .]+',value):status='needs_verification'
                    rect=[v/(page.rect.width if i%2==0 else page.rect.height) for i,v in enumerate(box)]
                    # Quote only the answer cell; its bounding box excludes labels
                    # and neighbouring rows, including private account credentials.
                    _put(fields,'client_form',name,page_number,key,value,cells[1][1],rect,status)
    return fields


def client_text_fields(text,name):
    """Read the same bilingual client-form table from native Word/HTML text."""
    fields={};section=''
    for number,line in enumerate(text.splitlines(),1):
        normal=_key(line)
        if 'previous employment' in normal:section='previous_work'
        elif 'current employment' in normal:section='current_work'
        elif 'education' in normal:section='education'
        if '|' not in line:continue
        label,value=line.split('|',1);label=_key(label);value=value.strip()
        key=next((field for phrase,field in sorted(CLIENT_LABELS.items(),key=lambda x:-len(x[0])) if phrase in label),None)
        if not key or not value or (section=='previous_work' and key=='employment_start_date'):continue
        if not re.search(r'[^_\s☐□/]',value):continue
        status='extracted'
        if key in CHOICES:value,status=_choice(value,CHOICES[key])
        _put(fields,'client_form',name,None,key,value,line,None,status)
        if key in fields:
            for source in fields[key]['sources']:
                source.update(method='native_text',native_section=number)
    return fields


DS_LABELS={
    'name provided':'full_name','surnames':'surname','given names':'given_names',
    'date of birth':'date_of_birth','sex':'gender','marital status':'marital_status',
    'country region of origin nationality':'nationality','national identification number':'national_id_number',
    'country region of birth':'birth_place','home address':'home_address','primary phone number':'phone','email address':'email',
    'passport travel document number':'passport_number','issuance date':'passport_issue','expiration date':'passport_expiry',
    'intended date of arrival':'arrival_date','date of arrival in u s':'arrival_date',
    'date of departure from u s':'departure_date','intended length of stay in u s':'length_of_stay',
    'address where you will stay in the u s':'hotel_address','person entity paying for your trip':'trip_sponsor',
    'organization name in the u s':'us_contact_organization','u s contact address':'us_contact_address',
    'contact person name in the u s':'us_contact_person','relationship to you':'us_contact_relationship',
    'phone number':'us_contact_phone',
    'primary occupation':'occupation','specify other':'occupation_detail',
    'present employer or school name':'employer_name','present employer or school address':'employer_address',
    'start date':'employment_start_date','work phone number':'employer_phone',
    'monthly salary in local currency if employed':'monthly_salary',
    'name of institution 1':'education_name','course of study':'education_course',
    'date of attendance from':'education_start_date','date of attendance to':'education_end_date',
    'father s surnames':'father_surname','father s given names':'father_given_names','father s date of birth':'father_date_of_birth',
    'mother s surnames':'mother_surname','mother s given names':'mother_given_names','mother s date of birth':'mother_date_of_birth',
    'have you ever been in the u s':'prior_us_visit',
    'have you ever served in the military':'military_service',
    'is your father in the u s':'father_us','is your mother in the u s':'mother_us',
    'do you have any immediate relatives not including parents in the u s':'immediate_relatives_us',
    'do you have any other relatives in the united states':'other_relatives_us',
}


def _lines(page):
    result=[]
    for block in page.get_text('dict')['blocks']:
        for line in block.get('lines',[]):
            text=''.join(s['text'] for s in line['spans']).strip()
            if text:result.append(dict(text=text,box=line['bbox'],size=max(s['size'] for s in line['spans']),
                                      bold=any(s['flags']&16 for s in line['spans'])))
    return sorted(result,key=lambda line:(round(line['box'][1],1),line['box'][0]))


def ds_fields(raw,name):
    fields={};providers={};identifiers={};languages=[];column_answers=0
    with pymupdf.open(stream=raw,filetype='pdf') as doc:
        if not any('Online Nonimmigrant Visa Application' in page.get_text() for page in doc):return {}
        for number,page in enumerate(doc,1):
            lines=_lines(page)
            contact_page=any('U.S. Contact Information' in line['text'] or 'U.S. Point of Contact' in line['text'] for line in lines)
            # Native CEAC printouts put answer blocks in a separate right column.
            # All left-column labels are boundaries, even unsupported questions.
            anchors=[line for line in lines if line['box'][0]<page.rect.width*.5 and
                     (':' in line['text'] or '?' in line['text'] or line['text'].startswith('Have you ever been refused a U.S. Visa')) and line['size']<12]
            left_lines=[line for line in lines if line['box'][0]<page.rect.width*.5 and line['size']<12]
            for i,anchor in enumerate(anchors):
                pieces=re.split(r'[:?]',anchor['text'],maxsplit=1)
                label=_key(pieces[0])
                key=DS_LABELS.get(label)
                if anchor['text'].startswith('Have you ever been refused a U.S. Visa'):key='prior_refusal'
                dynamic=re.fullmatch(r'(social media provider platform|social media identifier|language name) (\d+)',label)
                if not key and not dynamic:continue
                next_y=min((line['box'][1] for line in left_lines if line['box'][1]>anchor['box'][1]+2),default=page.rect.height)
                values=[line for line in lines if line['box'][0]>=page.rect.width*.52 and
                        anchor['box'][1]-1<=line['box'][1]<next_y-1 and not line['text'].startswith(('Edit ','DO NOT BRING','Application ID'))]
                if dynamic and dynamic[1]=='language name':
                    # Language answers occupy one row. A following YES/NO can
                    # sit slightly above its question's baseline in CEAC PDFs.
                    values=[line for line in values if abs(line['box'][1]-anchor['box'][1])<=2]
                inline=pieces[1].strip() if len(pieces)>1 else ''
                if inline:values=[anchor]
                if not values:continue
                if not inline:column_answers+=1
                value=inline or ' '.join(line['text'] for line in values)
                box=[min(l['box'][0] for l in values)/page.rect.width,min(l['box'][1] for l in values)/page.rect.height,
                     max(l['box'][2] for l in values)/page.rect.width,max(l['box'][3] for l in values)/page.rect.height]
                if key=='email' and contact_page:key='us_contact_email'
                if key in ('us_contact_person','us_contact_relationship','us_contact_phone','us_contact_email') and not contact_page:continue
                if key=='employer_phone' and not any('Present Work' in line['text'] for line in lines):continue
                if dynamic:
                    kind,index=dynamic.groups()
                    if kind=='social media provider platform':providers[index]=_key(value)
                    elif kind=='social media identifier':identifiers[index]=(value,number,box)
                    else:languages.append((value,number,box))
                    continue
                _put(fields,'ds160',name,number,key,value,'\n'.join(l['text'] for l in values),box)
    if column_answers<3:return {}  # Explicit inline-label documents use the generic reader.
    def derived(key,value,source_keys,basis):
        sources=[s for k in source_keys if k in fields for s in fields[k]['sources']]
        fields[key]=dict(value=value,status='extracted',sources=sources,alternatives=[value],basis=basis)
    if (fields.get('full_name',{}).get('value') or '').count(',')==1:
        surname,given=fields['full_name']['value'].split(',',1)
        derived('surname',surname.strip(),['full_name'],'Name Provided uses SURNAME, GIVEN NAMES.')
        derived('given_names',given.strip(),['full_name'],'Name Provided uses SURNAME, GIVEN NAMES.')
    if 'full_name' not in fields and all(fields.get(k,{}).get('value') for k in ('given_names','surname')):
        derived('full_name',fields['given_names']['value']+' '+fields['surname']['value'],['given_names','surname'],
                'Printed given names and surname.')
    if (fields.get('birth_place',{}).get('value') or '').count(',')==1:
        city,country=fields['birth_place']['value'].split(',',1)
        derived('birth_city',city.strip(),['birth_place'],'Printed city, country of birth.')
        derived('birth_country',country.strip(),['birth_place'],'Printed city, country of birth.')
    for person in ('father','mother'):
        keys=[person+'_given_names',person+'_surname']
        if all(k in fields and fields[k]['value'] for k in keys):
            derived(person+'_full_name',' '.join(fields[k]['value'] for k in keys),keys,'Printed parent given names and surname.')
    if fields.get('occupation',{}).get('value','').casefold()=='other' and fields.get('occupation_detail',{}).get('value'):
        derived('occupation',fields['occupation_detail']['value'],['occupation','occupation_detail'],'OTHER occupation with its printed Specify Other answer.')
    for index,(value,number,box) in identifiers.items():
        platform=providers.get(index)
        if platform in ('facebook','instagram','linkedin','twitter','x'):
            _put(fields,'ds160',name,number,'social_'+('twitter' if platform=='x' else platform),value,value,box)
    if languages:
        fields['languages']=dict(value=' / '.join(item[0] for item in languages),status='extracted',
            sources=[_source(name,n,'languages',v,v,box) for v,n,box in languages],alternatives=[])
    relatives=('father_us','mother_us','immediate_relatives_us','other_relatives_us')
    known=[fields[k]['value'].casefold() for k in relatives if k in fields and fields[k]['value']]
    if 'yes' in known or len(known)==4 and set(known)=={'no'}:
        derived('relatives_us','yes' if 'yes' in known else 'no',[k for k in relatives if k in fields],
                'Combines parent, immediate-relative and other-relative answers; unknown answers never become NO.')
    return fields


MONTHS={name.casefold():index for index,name in enumerate(('January','February','March','April','May','June','July','August','September','October','November','December'),1)}


def booking_fields(raw,name,*,include_contact=False):
    """Read just property name/check-in/check-out; never prices, guest IDs or PINs."""
    fields={}
    with pymupdf.open(stream=raw,filetype='pdf') as doc:
        page=doc[0];lines=_lines(page);text=page.get_text()
        if 'Booking Confirmation' not in text or 'CONFIRMATION NUMBER' not in text:
            if 'hotelscomitinerary' in re.sub(r'\W','',text.casefold()):return _hotels_com(raw,name,include_contact=include_contact)
            return {}
        if include_contact:
            # Only the property's labelled header. A confirmation-email recipient
            # or guest/contact detail elsewhere must not become the hotel's email.
            header=[l for l in lines if l['box'][0]<page.rect.width*.56 and l['box'][1]<page.rect.height*.2]
            for line in header:
                match=re.match(r'^(Address|Phone|E-?mail)\s*:\s*(.+)$',line['text'],re.I)
                if not match:continue
                key={'address':'hotel_address','phone':'hotel_phone','email':'hotel_email','e-mail':'hotel_email'}[match[1].lower()]
                selected=[line]
                if key=='hotel_address':
                    selected+=[l for l in header if l is not line and abs(l['box'][0]-line['box'][0])<5 and
                               line['box'][1]<l['box'][1]<line['box'][1]+25 and ':' not in l['text']]
                value=' '.join([match[2],*[l['text'] for l in selected[1:]]])
                box=[min(l['box'][0] for l in selected)/page.rect.width,min(l['box'][1] for l in selected)/page.rect.height,
                     max(l['box'][2] for l in selected)/page.rect.width,max(l['box'][3] for l in selected)/page.rect.height]
                _put(fields,'hotel',name,1,key,value,'\n'.join(l['text'] for l in selected),box)
        headers={key:[l for l in lines if re.fullmatch(pattern,l['text'],re.I)] for key,pattern in
                 (('check_in_date',r'CHECK[ -]?IN'),('check_out_date',r'CHECK[ -]?OUT'))}
        if any(len(value)!=1 for value in headers.values()):return {}
        parts={}
        for key,head in headers.items():
            anchor=head[0];center=(anchor['box'][0]+anchor['box'][2])/2
            block=[l for l in lines if abs((l['box'][0]+l['box'][2])/2-center)<page.rect.width*.05 and
                   anchor['box'][1]<=l['box'][1]<anchor['box'][1]+page.rect.height*.085]
            day=[l for l in block if re.fullmatch(r'\d{1,2}',l['text'])]
            month=[l for l in block if l['text'].casefold() in MONTHS]
            weekday=[l for l in block if l['text'].casefold() in ('monday','tuesday','wednesday','thursday','friday','saturday','sunday')]
            years=[l for l in block if re.fullmatch(r'20\d{2}',l['text'])]
            if len(day)==len(month)==1:
                parts[key]=(int(day[0]['text']),MONTHS[month[0]['text'].casefold()],weekday[0]['text'].casefold() if len(weekday)==1 else None,
                            int(years[0]['text']) if len(years)==1 else None,[anchor,day[0],month[0],*weekday,*years])
        property_candidates=[l for l in lines if l['bold'] and l['box'][2]<headers['check_in_date'][0]['box'][0]-10 and
            abs(l['box'][1]-headers['check_in_date'][0]['box'][1])<15 and l['size']>=9 and ':' not in l['text']]
        if len(property_candidates)==1:
            line=property_candidates[0]
            _put(fields,'hotel',name,1,'hotel_name',line['text'],line['text'],
                [v/(page.rect.width if i%2==0 else page.rect.height) for i,v in enumerate(line['box'])])
        if len(parts)!=2:return fields
        incoming,outgoing=parts['check_in_date'],parts['check_out_date']
        # A year is never borrowed from DS-160, the client form or today's date.
        # When the header omits years, a same-booking explicit cancellation date
        # on the check-in day plus both weekdays and printed nights must agree.
        anchors=[]
        for line in lines:
            for match in re.finditer(r'\b('+'|'.join(MONTHS)+r')\s+(\d{1,2}),?\s+(20\d{2})\b',line['text'],re.I):
                month,day,year=MONTHS[match[1].casefold()],int(match[2]),int(match[3])
                if (day,month)==incoming[:2] and re.search(r'\bfrom\b',line['text'],re.I):anchors.append((year,line))
        years={incoming[3]} if incoming[3] else {year for year,_ in anchors}
        end_anchor=headers['check_out_date'][0]
        nights_labels=[l for l in lines if l['text'].upper()=='NIGHTS' and abs(l['box'][1]-end_anchor['box'][1])<5]
        nights=None
        if len(nights_labels)==1:
            center=sum((nights_labels[0]['box'][0],nights_labels[0]['box'][2]))/2
            numbers=[l for l in lines if re.fullmatch(r'\d{1,3}',l['text']) and abs(sum((l['box'][0],l['box'][2]))/2-center)<12 and
                     nights_labels[0]['box'][1]<l['box'][1]<nights_labels[0]['box'][1]+35]
            if len(numbers)==1:nights=int(numbers[0]['text'])
        valid=[]
        for year in years:
            try:
                start=date(year,incoming[1],incoming[0])
                end_year=outgoing[3] or year+int((outgoing[1],outgoing[0])<(incoming[1],incoming[0]))
                end=date(end_year,outgoing[1],outgoing[0])
            except ValueError:continue
            own_years=bool(incoming[3] and outgoing[3])
            if not own_years and (not incoming[2] or not outgoing[2] or nights is None):continue
            if incoming[2] and start.strftime('%A').casefold()!=incoming[2]:continue
            if outgoing[2] and end.strftime('%A').casefold()!=outgoing[2]:continue
            if nights is not None and (end-start).days!=nights:continue
            if end>start:valid.append((start,end))
        if len(valid)==1:
            for key,parsed in zip(('check_in_date','check_out_date'),valid[0]):
                evidence=parts[key][4]+[line for _,line in anchors]
                fields[key]=dict(value=parsed.isoformat(),status='extracted',alternatives=[parsed.isoformat()],
                    basis='Printed header dates; missing year verified against same-booking cancellation date, both weekdays and nights.',
                    sources=[_source(name,1,key,parsed.isoformat(),line['text'],[v/(page.rect.width if i%2==0 else page.rect.height) for i,v in enumerate(line['box'])]) for line in evidence])
    return fields


def _hotels_com(raw,name,*,include_contact=False):
    from booking_template_extractor import extract_hotel_v1
    report=extract_hotel_v1(raw,name);fields={}
    for key in ('hotel_name','check_in_date','check_out_date'):
        row=report.get('fields',{}).get(key,{})
        if row.get('value') is None:continue
        fields[key]=dict(value=row['value'],status=row['status'],alternatives=[row['value']],
            sources=[_source(name,line.get('page',1),key,row['value'],line['text'],line.get('region_normalized')) for line in row.get('sources',[])])
    if include_contact:
        row=report.get('fields',{}).get('location',{})
        if row.get('value'):
            fields['hotel_address']=dict(value=row['value'],status=row['status'],alternatives=[row['value']],
                sources=[_source(name,line.get('page',1),'hotel_address',row['value'],line['text'],line.get('region_normalized')) for line in row.get('sources',[])])
    return fields
