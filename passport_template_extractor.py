"""Local OCR pilot for the supplied Egyptian TD3 passport layout.

MRZ structure/check digits: ICAO Doc 9303 Parts 3 and 4.
https://www.icao.int/publications/doc-series/doc-9303
Check digits detect transcription inconsistencies; they do not establish authenticity.
"""
from datetime import datetime
from io import BytesIO
import re
import unicodedata

from PIL import Image
from offline_ocr import image_lines


def check_digit(text):
    if not re.fullmatch(r'[A-Z0-9<]*',text):return None
    values=[0 if char=='<' else int(char) if char.isdigit() else ord(char)-55 for char in text]
    return str(sum(value*(7,3,1)[index%3] for index,value in enumerate(values))%10)


def parse_td3(first,second):
    """No O/0, I/1, filler padding or spelling correction is permitted."""
    if len(first)!=44 or len(second)!=44 or not re.fullmatch(r'P<[A-Z<]{42}',first) or not re.fullmatch(r'[A-Z0-9<]{44}',second):
        return dict(status='unreadable_mrz',checks={},values={})
    if not re.fullmatch(r'\d{6}',second[13:19]) or not re.fullmatch(r'\d{6}',second[21:27]):
        return dict(status='unreadable_mrz',checks={},values={})
    checks=dict(passport_number=check_digit(second[:9])==second[9],date_of_birth=check_digit(second[13:19])==second[19],
                expiry_date=check_digit(second[21:27])==second[27],
                optional_data=check_digit(second[28:42])==second[42] or (second[28:42]=='<'*14 and second[42]=='<'),
                composite=check_digit(second[:10]+second[13:20]+second[21:43])==second[43])
    name=first[5:]
    if '<<' not in name:return dict(status='unreadable_mrz',checks=checks,values={})
    surname,given=name.split('<<',1)
    surname=' '.join(surname.replace('<',' ').split());given=' '.join(given.replace('<',' ').split())
    values=dict(surname=surname,given_names=given,full_name=(given+' '+surname).strip(),
                passport_number=second[:9].replace('<',''),issuing_country_code=first[2:5],
                nationality_code=second[10:13],date_of_birth_yymmdd=second[13:19],expiry_date_yymmdd=second[21:27])
    return dict(status='check_digits_valid' if all(checks.values()) and surname and given else 'mrz_check_failed',checks=checks,values=values)


def _normal(text):return ''.join(char for char in text.casefold() if char.isalnum())


def _center(line):
    x0,y0,x1,y1=line['region_normalized'];return ((x0+x1)/2,(y0+y1)/2)


NATIONAL_ID_REGION=(.625,.596,.835,.642)


def normalize_identifier(value):
    """Normalize digit scripts and spacing only; never repair or infer an identifier."""
    return ''.join(str(unicodedata.decimal(char)) if char.isdecimal() else char.upper()
                   for char in str(value or '') if not char.isspace() and char not in '\u200e\u200f\u061c')


def _national_id_reading(lines):
    candidates=[]
    for line in lines:
        x,y=_center(line)
        if not (.60<=x<=.995 and .585<=y<=.655):continue
        for match in re.finditer(r'(?<!\w)\d+(?:[ \t\u200e\u200f\u061c]+\d+)*(?!\w)',line['text']):
            value=normalize_identifier(match.group())
            if re.fullmatch(r'[0-9]{14}',value):candidates.append((value,line))
    values={value for value,_ in candidates}
    trusted=[line for _,line in candidates if (line.get('confidence') or 0)>=.92]
    if len(values)==1 and trusted:return next(iter(values)),trusted
    return None,[line for _,line in candidates]


def parse_egypt_passport_lines(lines,filename='passport.jpeg'):
    report=dict(template_id='egypt_passport.v1',source_file=filename,ai_requests=0,fields={},values={},limitations=[])
    labels=['dateofbirth','placeofbirth','dateofissue','dateofexpiry']
    if not all(any(label in _normal(line['text']) for line in lines) for label in labels):
        return dict(report,status='unsupported_or_unreadable',limitations=['Passport visual labels could not be recognized; no identity reference established.'])
    mrz=[line for line in lines if _center(line)[1]>0.8]
    first=[line for line in mrz if line['text'].startswith('P<')]
    second=[line for line in mrz if re.fullmatch(r'[A-Z0-9<]{44}',line['text']) and not line['text'].startswith('P<')]
    if len(first)!=1 or len(second)!=1:
        return dict(report,status='needs_verification',limitations=['Both exact 44-character MRZ lines are required; no characters were repaired.'])
    parsed=parse_td3(first[0]['text'],second[0]['text']);report['mrz_checks']=parsed['checks']
    if parsed.get('values',{}).get('issuing_country_code') not in (None,'EGY'):
        return dict(report,status='unsupported_or_unreadable',limitations=['This layout pilot supports Egyptian-issued passports only.'])
    if parsed['status']!='check_digits_valid':
        return dict(report,status='needs_verification',limitations=['MRZ transcription failed its check digits; no authoritative identity values accepted.'])
    if first[0].get('confidence',0)<0.90:
        return dict(report,status='needs_verification',limitations=['Name OCR confidence is too low. MRZ names have no check digit.'])
    def put(key,value,source,status='extracted'):
        report['fields'][key]=dict(value=value,status=status,sources=[dict(line,source_file=filename) for line in source])
        report['values'][key]=value
    for key in ('surname','given_names','full_name','passport_number'):
        put(key,parsed['values'][key],[first[0] if 'name' in key else second[0]])
    def within(region):
        return [line for line in lines if region[0]<=_center(line)[0]<=region[2] and region[1]<=_center(line)[1]<=region[3]]
    birthday=[line for line in within([0.34,0.36,0.50,0.42]) if re.search(r'\d{2}/\d{2}/\d{4}',line['text'])]
    birth_raw=re.findall(r'\d{2}/\d{2}/\d{4}',birthday[0]['text']) if len(birthday)==1 else []
    date_rows=[line for line in within([0.34,0.49,0.68,0.54]) if re.search(r'\d{2}/\d{2}/\d{4}',line['text'])]
    # OCR may join two adjacent date cells into one text run. The two fixed-width
    # printed dates remain separate substrings, ordered by their original columns.
    dates=[(value,line) for line in sorted(date_rows,key=lambda line:line['region_normalized'][0])
           for value in re.findall(r'\d{2}/\d{2}/\d{4}',line['text'])]
    visual={}
    if len(birth_raw)==1:visual['date_of_birth']=(birth_raw[0],birthday[0])
    if len(dates)==2:
        visual['issue_date']=dates[0];visual['expiry_date']=dates[1]
    for key in ('date_of_birth','issue_date','expiry_date'):
        value,source=visual.get(key,(None,None));iso=None
        if value:
            try:iso=datetime.strptime(value,'%d/%m/%Y').date().isoformat()
            except ValueError:pass
        if key!='issue_date' and iso:
            mrz_date=parsed['values']['date_of_birth_yymmdd' if key=='date_of_birth' else 'expiry_date_yymmdd']
            if datetime.fromisoformat(iso).strftime('%y%m%d')!=mrz_date:
                report['limitations'].append(f'{key}: visual date and MRZ disagree; no date accepted.');iso=None
        if iso and source.get('confidence',0)<0.90:
            report['limitations'].append(f'{key}: visual OCR confidence is too low.');iso=None
        put(key,iso,[source] if source else [],status='extracted' if iso else 'unverified')
    places=[line for line in within([0.50,0.37,0.68,0.42]) if re.fullmatch(r'[A-Z][A-Z .-]+',line['text'].strip())]
    place=places[0] if len(places)==1 and places[0].get('confidence',0)>=0.90 else None
    put('place_of_birth',place['text'].strip() if place else None,[place] if place else [],status='extracted' if place else 'unverified')
    # Independently read the visible passport number, rather than treating a valid
    # checksum as proof that OCR selected the correct document field.
    numbers=[line for line in within([0.70,0.12,0.95,0.19]) if re.fullmatch(r'[A-Z0-9]{6,12}',line['text'])]
    if len(numbers)!=1 or numbers[0]['text']!=parsed['values']['passport_number']:
        report['limitations'].append('Visual passport number could not be confirmed against the MRZ.')
        put('passport_number',None,numbers,status='unverified')
    else:report['fields']['passport_number']['sources'].append(dict(numbers[0],source_file=filename))
    if any(value is None for value in report['values'].values()):
        report['limitations'].append('One or more identity reference fields remain unverified.')
    # This is the separate printed Egyptian civil ID field, not the passport
    # number, MRZ optional data, or a number reconstructed from a birth date.
    # It is optional: an unreadable civil ID does not invalidate other fields.
    national_id,sources=_national_id_reading(lines)
    put('national_id_number',national_id,sources,status='extracted' if national_id else 'unverified')
    report['status']='needs_verification' if report['limitations'] else 'extracted'
    report['notes']=['MRZ birth/expiry centuries are established from the printed four-digit years, never guessed.',
                     'Issue date and place of birth are visual-page values, not MRZ fields.',
                     'National ID is read independently from its printed visual-page field; unreadable digits are not guessed.',
                     'The accepted short booking name is the first given name plus the full surname.',
                     'This is transcription/consistency checking, not passport authentication.']
    return report


def extract_egypt_passport(raw,filename='passport.jpeg'):
    image=Image.open(BytesIO(raw))
    if not 1.2<=image.width/image.height<=1.6:
        return dict(template_id='egypt_passport.v1',source_file=filename,ai_requests=0,status='needs_verification',values={},fields={},limitations=['Passport page crop/orientation differs from the inspected layout.'])
    lines=image_lines(raw)
    report=parse_egypt_passport_lines(lines,filename)
    if report.get('values') and not report['values'].get('national_id_number'):
        # The full-page English OCR cannot reliably transcribe Arabic digits.
        # The verified layout and MRZ establish the crop; no other document is
        # consulted to choose, repair or confirm the OCR reading.
        try:
            from offline_ocr import arabic_image_line
            box=tuple(round(value*(image.width if index%2==0 else image.height))
                      for index,value in enumerate(NATIONAL_ID_REGION))
            crop=image.convert('RGB').crop(box);output=BytesIO();crop.save(output,format='PNG')
            extra=[]
            for line in arabic_image_line(output.getvalue()):
                x0,y0,x1,y1=line['region_normalized']
                extra.append(dict(line,region_normalized=[
                    (box[0]+x0*crop.width)/image.width,(box[1]+y0*crop.height)/image.height,
                    (box[0]+x1*crop.width)/image.width,(box[1]+y1*crop.height)/image.height]))
            report=parse_egypt_passport_lines(lines+extra,filename)
        except Exception as exc:
            from monitoring import capture_error
            capture_error(exc,'passport_national_id_ocr')
    return report
