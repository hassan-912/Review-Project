"""Offline pilot: Hotels.com reservation v1 and Egyptair itinerary v1 only."""
from datetime import datetime
import re
import unicodedata
import pymupdf

from offline_ocr import pdf_lines,pdf_region_lines

MONTHS={name:index for index,name in enumerate(('January','February','March','April','May','June',
    'July','August','September','October','November','December'),1)}


def compact(text):
    return ''.join(char for char in text.casefold() if char.isalnum())


def _date(text):
    pattern=r'(\d{1,2})\s*('+'|'.join(MONTHS)+r'|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s*(20\d{2})'
    match=re.search(pattern,text,re.I)
    if not match:return None
    day,month,year=match.groups()
    number=next((value for name,value in MONTHS.items() if name.casefold().startswith(month.casefold())),None)
    try:return datetime(int(year),number,int(day)).date().isoformat()
    except (ValueError,TypeError):return None


def _field(value,lines,filename):
    return dict(value=value,sources=[dict(line,source_file=filename) for line in lines],
                status='extracted' if value is not None else 'unverified')


def extract_hotel_v1(raw,filename='hotel.pdf'):
    lines=pdf_lines(raw)
    first=sorted((line for line in lines if line['page']==1),key=lambda line:line['region_normalized'][1])
    result=dict(template_id='hotels_com.v1',source_file=filename,ai_requests=0,fields={},limitations=[])
    if not all(any(label in compact(line['text']) for line in first) for label in ('hotelscomitinerary','reservationdetails','reservedfor','location')):
        return dict(result,status='unsupported_template',limitations=['Hotels.com reservation labels were not recognized.'])
    def next_line(label):
        matches=[line for line in first if compact(line['text'])==compact(label)]
        if len(matches)!=1:return None
        anchor=matches[0]['region_normalized']
        candidates=[line for line in first if line['region_normalized'][1]>=anchor[3]-0.002
                    and abs(line['region_normalized'][0]-anchor[0])<0.06]
        return min(candidates,key=lambda line:line['region_normalized'][1]) if candidates else None
    itinerary=next(i for i,line in enumerate(first) if 'hotelscomitinerary' in compact(line['text']))
    name=first[itinerary-1] if itinerary else None
    date_rows=[line for line in first if re.search(r'\d{1,2}\s+[A-Za-z]+\s+20\d{2}\s*[-–]\s*\d{1,2}\s+[A-Za-z]+\s+20\d{2}',line['text'])]
    dates=[]
    if len(date_rows)==1:
        dates=[_date(part) for part in re.split(r'\s*[-–]\s*',date_rows[0]['text'])]
    checkin,checkout=next_line('Check in'),next_line('Check out')
    # The full-year header and the separately labelled check-in/out must agree.
    for index,labelled in enumerate((checkin,checkout)):
        if len(dates)==2 and dates[index] and labelled:
            parsed=datetime.fromisoformat(dates[index])
            month_name=next(name for name,number in MONTHS.items() if number==parsed.month)
            expected=(str(parsed.day)+month_name[:3]).casefold()
            if expected not in compact(labelled['text']):
                dates[index]=None
    location=next_line('Location');guest=next_line('Reserved for')
    guest_name=re.sub(r',\s*\d+\s+adults?.*$','',guest['text'],flags=re.I).strip() if guest else None
    values={
        'hotel_name':(name['text'] if name else None,[name] if name else []),
        'check_in_date':(dates[0] if len(dates)==2 else None,([checkin,date_rows[0]] if date_rows and checkin else [])),
        'check_out_date':(dates[1] if len(dates)==2 else None,([checkout,date_rows[0]] if date_rows and checkout else [])),
        'location':(location['text'] if location else None,[location] if location else []),
        'reserved_for':(guest_name,[guest] if guest else []),
    }
    result['fields']={key:_field(value,sources,filename) for key,(value,sources) in values.items()}
    result['values']={key:field['value'] for key,field in result['fields'].items()}
    result['status']='extracted' if all(value is not None for value in result['values'].values()) else 'needs_verification'
    if len(dates)==2 and all(dates) and dates[1]<=dates[0]:
        result['status']='needs_verification'
        result['limitations'].append('Hotel check-out does not follow check-in; preserve the values and verify the booking.')
    if result['status']!='extracted':result['limitations'].append('One or more required labelled fields could not be read consistently.')
    return result


def _route(text):
    text=re.sub(r'^[^A-Za-z]+','',text).strip()
    text=re.sub(r'^[xX]\s+','',text)
    match=re.fullmatch(r"([A-Za-z][A-Za-z .'-]+?)\s+-\s+([A-Za-z][A-Za-z .'-]+)",text)
    return tuple(part.strip() for part in match.groups()) if match else None


def parse_flight_v1_lines(lines,traveller_lines,filename='flight.pdf'):
    itinerary=sorted((line for line in lines if line['page']==2),key=lambda line:line['region_normalized'][1])
    headers=[(index,_route(line['text'])) for index,line in enumerate(itinerary) if _route(line['text'])]
    result=dict(template_id='egyptair.v1',source_file=filename,ai_requests=0,segments=[],fields={},limitations=[],
                scope='Itinerary and traveller sections on pages 2-3; booking status on page 1. Other pages are not audited.')
    if not any('itinerary' in compact(line['text']) for line in itinerary) or len(headers)!=2:
        return dict(result,status='unsupported_template',limitations=['Expected a direct outbound and return itinerary in the first Egyptair template.'])
    for position,(index,(origin,destination)) in enumerate(headers):
        end=headers[position+1][0] if position+1<len(headers) else len(itinerary)
        block=itinerary[index:end]
        day=next((_date(line['text']) for line in block[1:4] if _date(line['text'])),None)
        timed=[]
        for line in block:
            match=re.match(r'^(\d{1,2}:\d{2})\s+(.+)$',line['text'].strip())
            if match:
                try:datetime.strptime(match.group(1),'%H:%M')
                except ValueError:
                    result['limitations'].append('An itinerary time is invalid; do not use it for planning.')
                    continue
                timed.append((match.group(1),match.group(2).strip(),line))
        if len(timed)!=2 or compact(timed[0][1])!=compact(origin) or compact(timed[1][1])!=compact(destination):
            result['limitations'].append('A segment time/city pair could not be verified against its route heading.')
        date_source=next((line for line in block[1:4] if _date(line['text'])),None)
        result['segments'].append(dict(origin_city=origin,destination_city=destination,departure_date=day,
            departure_time=timed[0][0] if len(timed)==2 else None,arrival_time=timed[1][0] if len(timed)==2 else None,
            sources=[dict(line,source_file=filename) for line in [block[0],date_source,*[value[2] for value in timed]] if line]))
    outbound,returning=result['segments']
    if compact(outbound['origin_city'])!='cairo' or compact(returning['destination_city'])!='cairo' or compact(outbound['destination_city'])!=compact(returning['origin_city']):
        result['limitations'].append('This pilot expects Cairo -> destination -> Cairo; verify the route manually.')
    if any(re.search(r'\+\s*\d+\s*(?:day|d\b)',line['text'],re.I) for line in itinerary):
        result['limitations'].append('An overnight arrival marker needs explicit day-offset handling.')
    names=[line for line in traveller_lines if line['text'].strip()]
    name=' '.join(line['text'].strip() for line in names) if names else None
    if name and (len(name.split())<2 or 'contact' in compact(name) or any(char.isdigit() for char in name)):
        result['limitations'].append('The traveller name is merged/unreadable; no passport-based correction was made.')
        name=None
    if any(line.get('confidence') is not None and line['confidence']<0.9 for line in names):
        result['limitations'].append('Traveller-name OCR is below the acceptance threshold.')
        name=None
    if not any(re.fullmatch(r'1travell?er1adult',compact(line['text'])) for line in itinerary):
        result['limitations'].append('This template pilot supports one adult traveller only.')
    country={'barcelona':'Spain','madrid':'Spain'}.get(compact(outbound['destination_city']))
    if country is None:result['limitations'].append('Destination country is not in the explicit city reference; verify it.')
    status='held' if any('bookingonhold' in compact(line['text']) for line in lines if line['page']==1) else 'unknown'
    result['values']=dict(origin_city=outbound['origin_city'],destination_city=outbound['destination_city'],
        destination_country=country,outbound_departure_date=outbound['departure_date'],
        outbound_arrival_date=outbound['departure_date'] if not any('overnight' in note for note in result['limitations']) else None,
        return_departure_date=returning['departure_date'],outbound_departure_time=outbound['departure_time'],
        return_arrival_date=returning['departure_date'] if not any('overnight' in note for note in result['limitations']) else None,
        outbound_arrival_time=outbound['arrival_time'],return_departure_time=returning['departure_time'],
        return_arrival_time=returning['arrival_time'],traveller_name=name,booking_status=status)
    result['fields']['traveller_name']=_field(name,names,filename)
    result['destination_country_basis']='Explicit city reference (Barcelona/Madrid -> Spain); country is not printed in the route heading.'
    result['arrival_date_basis']='Same itinerary date for the inspected direct-flight layout, provided no overnight day-offset marker is present. Local times are not converted between time zones.'
    if any(value is None for key,value in result['values'].items() if key!='destination_country'):
        result['limitations'].append('One or more required itinerary/traveller values are missing.')
    result['status']='needs_verification' if result['limitations'] else 'extracted'
    return result


def extract_flight_v1(raw,filename='flight.pdf'):
    with pymupdf.open(stream=raw,filetype='pdf') as pdf:
        if len(pdf)<3:
            return dict(template_id='egyptair.v1',source_file=filename,ai_requests=0,status='unsupported_template',
                        values={},fields={},segments=[],limitations=['This template requires itinerary/traveller pages 2-3.'])
    lines=pdf_lines(raw,pages=(1,2,3))
    # This inspected template places the traveller name immediately left of CONTACT INFORMATION.
    traveller=pdf_region_lines(raw,3,[115,38,190,65])
    return parse_flight_v1_lines(lines,traveller,filename)


def _name_tokens(value):
    return re.findall(r"[^\W\d_]+(?:['’-][^\W\d_]+)*",unicodedata.normalize('NFKC',value or '').casefold())


def name_matches(found,given_names,surname):
    """Exact spelling; full given names OR first given name plus the FULL surname."""
    if found and any(not (char.isalpha() or char.isspace() or char in "'-’.,") for char in found):
        return False
    actual,given,family=_name_tokens(found),_name_tokens(given_names),_name_tokens(surname)
    if not actual or not given or not family:return None
    return actual in (given+family,given[:1]+family)
