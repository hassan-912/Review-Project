"""Provisional, label-anchored reads of an Egyptian passport's visual zone.

This does not turn an incomplete MRZ or OCR confidence into verified identity.
It keeps neighbouring columns separate and retains complete multi-line names.
"""
import re


def _key(value):return ''.join(c for c in value.casefold() if c.isalnum())


LABELS={'fullname':'full_name','fullnane':'full_name','passportno':'passport_number','passportnumber':'passport_number',
        'dateofbirth':'date_of_birth','dateofissue':'passport_issue','dateofexpiry':'passport_expiry',
        'nationality':'nationality','sex':'gender','placeofbirth':'birth_city'}


def visual_fields(rows,name):
    anchors={}
    for row in rows:
        key=LABELS.get(_key(row['text']))
        if key and row.get('box') and (row.get('confidence') or 0)>=.75:
            anchors.setdefault(key,[]).append(row)
    # A partial photo can be read provisionally only when these distinct labels
    # establish its visual layout. No applicant/application values are consulted.
    if sum(len(anchors.get(key,[]))==1 for key in ('full_name','date_of_birth','passport_issue','passport_expiry'))<3:
        return {}
    if not anchors.get('passport_number'):
        for row in rows:
            if row.get('box') and 'passportno' in _key(row['text']) and (row.get('confidence') or 0)>=.7:
                # The English passport-number label can share one OCR run with
                # Type and Country Code; its answer is in the rightmost column.
                box=list(row['box']);box[0]+=2*(box[2]-box[0])/3
                anchors.setdefault('passport_number',[]).append(dict(row,box=box))
    fields={}
    for key,choices in anchors.items():
        if len(choices)!=1:continue
        anchor=choices[0];x=anchor['box'][0];y=sum(anchor['box'][1::2])/2
        stop=min((sum(other['box'][1::2])/2 for group in anchors.values() for other in group
                  if sum(other['box'][1::2])/2>y+.015 and (key=='full_name' or abs(other['box'][0]-x)<.06)),default=y+.095)
        candidates=[]
        for row in rows:
            if row is anchor or not row.get('box') or (row.get('confidence') or 0)<.90:continue
            center=sum(row['box'][1::2])/2
            aligned=(x-.045<=row['box'][0]<.98) if key=='full_name' else abs(row['box'][0]-x)<(.08 if key=='passport_number' else .045)
            if not (y+.005<center<stop and aligned):continue
            value=row['text'].strip()
            if key in ('passport_issue','passport_expiry','date_of_birth'):
                valid=bool(re.fullmatch(r'\d{2}/\d{2}/\d{4}',value))
            elif key=='gender':valid=value.upper() in ('M','F','MALE','FEMALE')
            elif key=='passport_number':valid=bool(re.fullmatch(r'[A-Z0-9]{6,12}',value))
            else:valid=bool(re.fullmatch(r"[A-Z][A-Z .'-]{2,}",value)) and _key(value) not in LABELS
            if valid:candidates.append(row)
        candidates.sort(key=lambda row:sum(row['box'][1::2])/2)
        if key=='full_name':
            # Read separate OCR runs on the same baseline left to right, while
            # preserving genuine second name lines. Do not guess word spacing.
            groups=[]
            for row in candidates:
                center=sum(row['box'][1::2])/2
                if not groups or abs(center-groups[-1][0])>.012:groups.append((center,[]))
                groups[-1][1].append(row)
            candidates=[row for _,group in groups for row in sorted(group,key=lambda r:r['box'][0])]
        if not candidates or key!='full_name' and len(candidates)!=1:continue
        value=' '.join(row['text'].strip() for row in candidates)
        fields[key]=dict(value=value,status='needs_verification',alternatives=[value],
            basis='Label-anchored visual OCR; a complete MRZ has not verified this reading.',
            sources=[dict(document='passport',source_file=name,page=row['page'],field_name=key,value=value,
                text=row['text'],box=row['box'],local_source=True,method='local_visual_ocr',confidence=row['confidence']) for row in candidates])
    return fields


def verified_fields(rows,name,previous_fields=None):
    """Verify each readable visual value against this passport's complete MRZ."""
    from datetime import datetime
    from passport_template_extractor import parse_td3
    fields={**(previous_fields or {}),**visual_fields(rows,name)}
    first=[r for r in rows if re.fullmatch(r'P<EGY[A-Z<]{39}',r['text']) and r.get('box')]
    second=[r for r in rows if re.fullmatch(r'[A-Z0-9<]{44}',r['text']) and not r['text'].startswith('P<') and r.get('box')]
    if len(first)!=1 or len(second)!=1:return fields
    a,b=first[0],second[0]
    # Lines must belong to one adjacent machine-readable zone on this page.
    if a['page']!=b['page'] or not 0<b['box'][1]-a['box'][1]<.12:return fields
    if min(a.get('confidence') or 0,b.get('confidence') or 0)<.90:return fields
    parsed=parse_td3(a['text'],b['text'])
    if parsed['status']!='check_digits_valid':return fields
    values=parsed['values']
    def put(key,value,source,visual=None):
        locations=list(visual.get('sources',[])) if visual else []
        locations.append(dict(document='passport',source_file=name,page=source['page'],field_name=key,value=value,
            text=source['text'],box=source['box'],local_source=True,method='verified_passport_mrz',confidence=source['confidence']))
        fields[key]=dict(value=value,status='extracted',alternatives=[value],sources=locations,
            basis='Complete MRZ passed all check digits; visual fields corroborate the transcription where available.')
    visible=fields.get('full_name')
    # The name line has no checksum: require an independent visual-zone read,
    # not a DS-160/client name, before accepting its surname/given-name split.
    if visible and _key(visible['value'])==_key(values['full_name']):
        for key in ('full_name','surname','given_names'):put(key,values[key],a,visible)
    number=fields.get('passport_number')
    if number and number['value']==values['passport_number']:put('passport_number',number['value'],b,number)
    for key,mrz_key in (('date_of_birth','date_of_birth_yymmdd'),('passport_expiry','expiry_date_yymmdd')):
        visual=fields.get(key)
        if not visual:continue
        try:day=datetime.strptime(visual['value'],'%d/%m/%Y').date()
        except ValueError:continue
        if day.strftime('%y%m%d')==values[mrz_key]:put(key,day.isoformat(),b,visual)
    # Issue date has no MRZ field. Keep its original high-confidence labelled
    # source and require verified birth/expiry dates and a coherent ordering.
    issued=fields.get('passport_issue')
    if issued and all(fields.get(k,{}).get('status')=='extracted' for k in ('date_of_birth','passport_expiry')):
        try:
            day=datetime.strptime(issued['value'],'%d/%m/%Y').date().isoformat()
            if fields['date_of_birth']['value']<day<fields['passport_expiry']['value']:
                fields['passport_issue']={**issued,'value':day,'status':'extracted',
                    'basis':'High-confidence label-anchored issue date in a passport with verified birth/expiry dates. Issue date is not in the MRZ.'}
        except ValueError:pass
    for key,value in (('nationality',values['nationality_code']),('gender',b['text'][20])):
        visual=fields.get(key)
        aliases={'EGYPTIAN':'EGY','EGYPT':'EGY','MALE':'M','FEMALE':'F'}
        if visual and aliases.get(visual['value'],visual['value'])!=value:continue
        if key=='gender' and value not in ('M','F'):continue
        put(key,value,b,visual)
    return fields


def read_fields(rows,name,raw,limitations=None):
    """Locate a photographed spread's identity section and retry it once locally.

    All returned coordinates remain on the original upload. The original image
    is never modified and application/client answers are never consulted.
    """
    fields=verified_fields(rows,name)
    core=('full_name','passport_number','date_of_birth','passport_issue','passport_expiry')
    if all(fields.get(k,{}).get('status')=='extracted' for k in core):return fields
    headers=[r for r in rows if r.get('box') and 'passportno' in _key(r['text']) and
             (r.get('confidence') or 0)>=.7]
    labels={LABELS.get(_key(r['text'])) for r in rows if (r.get('confidence') or 0)>=.75}
    mrz=[r for r in rows if r.get('box') and r['text'].startswith('P<EGY')]
    if len(headers)!=1 or len(mrz)!=1 or not {'date_of_birth','passport_issue','passport_expiry'}<=labels:return fields
    top=max(0,headers[0]['box'][1]-.025)
    if mrz[0]['box'][1]<=top:return fields
    from io import BytesIO
    from PIL import Image
    from offline_ocr import image_lines
    with Image.open(BytesIO(raw)) as image:
        # Small photographs benefit from a larger text recognition pass.
        box=(0,max(0,int(top*image.height)),image.width,image.height)
        crop=image.convert('RGB').crop(box)
        scale=min(2,2400/max(crop.size))
        crop=crop.resize((round(crop.width*scale),round(crop.height*scale)),Image.Resampling.LANCZOS)
        stream=BytesIO();crop.save(stream,format='PNG')
        retry=[]
        try:readings=image_lines(stream.getvalue())
        except Exception:
            if limitations is not None:limitations.append('The local passport detail re-read failed; provisional original readings were retained.')
            return fields
        for row in readings:
            x0,y0,x1,y1=row['region_normalized']
            retry.append(dict(text=row['text'],page=1,confidence=row['confidence'],method='local_ocr',
                box=[x0,(box[1]+y0*(image.height-box[1]))/image.height,x1,(box[1]+y1*(image.height-box[1]))/image.height]))
    better=verified_fields(retry,name,fields)
    for key,value in better.items():
        if value['status']=='extracted' or key not in fields:fields[key]=value
    return fields
