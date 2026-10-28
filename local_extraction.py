"""Production bridge for the verified offline parsers. No document AI fallback."""
import re
from hashlib import sha256

import pymupdf

from extractor import (VisaDocumentExtraction,PassportInfo,VisaApplicationInfo,FlightInfo,HotelInfo,
    EmploymentInfo,NationalIDInfo,IdentityEvidence,DocumentAudit,SourceField,SupportingDocument,
    SupportingClaim,AppointmentInfo)
from spain_pdf_extractor import extract_spain_pdf
from belgium_pdf_extractor import extract_belgium_pdf
from booking_template_extractor import extract_hotel_v1,extract_flight_v1
from passport_template_extractor import extract_egypt_passport
from hr_extractor import extract_hr_documents,compare_hr_with_application
from document_cache import cached_parse


APP_MAP={'applicant.surname':'surname','applicant.given_names':'given_names',
    'applicant.date_of_birth':'date_of_birth','applicant.place_of_birth':'place_of_birth','applicant.national_id_number':'national_id_number',
    'travel_document.number':'passport_number','travel_document.issue_date':'passport_issue',
    'travel_document.expiry_date':'passport_expiry','occupation.current':'occupation',
    'employment_or_education.name':'employer_name','employment_or_education.address':'employer_address',
    'journey.destination_member_states':'destination_country','journey.first_entry_member_state':'first_entry_country',
    'journey.purposes':'purpose_of_journey','journey.intended_arrival':'intended_arrival',
    'journey.intended_departure':'intended_departure'}
PASS_MAP={'passport_number':'passport_number','full_name':'full_name','surname':'surname',
    'given_names':'given_names','date_of_birth':'date_of_birth','place_of_birth':'place_of_birth','issue_date':'passport_issue','expiry_date':'passport_expiry',
    'national_id_number':'national_id_number'}
FLIGHT_MAP={'origin_city':'departure_city','destination_city':'destination_city',
    'outbound_departure_date':'departure_date','return_departure_date':'return_date',
    'traveller_name':'passenger_name','outbound_arrival_time':'arrival_time','return_departure_time':'return_departure_time'}
HOTEL_MAP={'hotel_name':'hotel_name','check_in_date':'check_in_date','check_out_date':'check_out_date',
    'reserved_for':'guest_name','location':'city'}
ID_MAP={'holder.full_name':'full_name','holder.full_id_number':'id_number','holder.issue_date':'issue_date','holder.expiry_date':'expiry_date'}


def _text(value):
    return '; '.join(str(item) for item in value) if isinstance(value,list) else str(value) if value is not None else None


def _fields(report):
    fields=report.get('fields',{})
    return {field['key']:field for field in fields} if isinstance(fields,list) else fields


def _value(report,key):
    row=_fields(report).get(key)
    if row is not None:
        return row.get('normalized_value',row.get('value')) if row.get('status') in ('extracted','confirmed') else None
    # The flight parser validates the full itinerary before accepting its derived keys.
    return report.get('values',{}).get(key) if report.get('status')=='extracted' else None


def _model(report,mapping,cls):
    return cls(**{target:_text(_value(report,key)) for key,target in mapping.items()})


def _page_count(name,raw):
    if name.lower().endswith('.pdf'):
        with pymupdf.open(stream=raw,filetype='pdf') as pdf:return len(pdf)
    return 1


def _evidence(data,report,category,mapping,raw=None,obj=None):
    sizes={}
    if raw is not None and report['source_file'].lower().endswith('.pdf'):
        with pymupdf.open(stream=raw,filetype='pdf') as pdf:
            sizes={number:(page.rect.width,page.rect.height) for number,page in enumerate(pdf,1)}
    for key,target in mapping.items():
        row=_fields(report).get(key,{})
        value=_value(report,key)
        if obj is not None and target=='city':value=obj.city
        for source in row.get('sources',[]):
            if value is None:continue
            rect=source.get('region_normalized')
            page=source.get('page',row.get('page',1))
            if rect is None and source.get('region_pdf_points') and page in sizes:
                width,height=sizes[page]
                rect=[coordinate/(width if index%2==0 else height) for index,coordinate in enumerate(source['region_pdf_points'])]
                rect=[max(0,min(1,value)) for value in rect]
            data.evidence_locations.append(SourceField(document=category,source_file=report['source_file'],
                page=page,field_name=target,value=_text(value),
                text=source.get('text') or _text(value),box=rect,local_source=True))
    if category=='flight':
        from booking_template_extractor import _date
        for index,segment in enumerate(report.get('segments',[])):
            for source in segment.get('sources',[]):
                key='departure_date' if index==0 else 'return_date'
                value=_value(report,'outbound_departure_date' if index==0 else 'return_departure_date')
                if value and _date(source['text'])==value:
                    data.evidence_locations.append(SourceField(document=category,source_file=report['source_file'],
                        page=source.get('page',2),field_name=key,value=value,text=source['text'],box=source.get('region_normalized'),local_source=True))


def _target_states(report,mapping,obj=None):
    fields=_fields(report)
    result={target:fields.get(key,{'status':report.get('status','unverified')})['status'] for key,target in mapping.items()}
    if isinstance(obj,VisaApplicationInfo):
        states=[result.get(key) for key in ('given_names','surname')]
        result['applicant_name']='extracted' if all(state=='extracted' for state in states) else 'blank' if all(state in ('blank','extracted') for state in states) else 'unverified'
    return result


def _audit(data,category,name,raw,report):
    count=_page_count(name,raw)
    complete=report.get('status')=='extracted'
    pages=list(range(1,count+1))
    if category=='flight':pages=[number for number in (1,2,3) if number<=count]
    if category=='passport' and count>1:pages=[1]
    if not _fields(report) and not report.get('segments'):pages=[]
    uncertainty=list(report.get('limitations',[]))
    if pages!=list(range(1,count+1)):uncertainty.append('The local parser covers only the supported identity/booking pages; other pages require verification.')
    data.document_audits.append(DocumentAudit(source_file=name,document_types=[category],pages_read=pages,
        readability='readable' if complete and len(pages)==count else 'partial' if pages else 'unreadable',
        uncertainties=uncertainty,summary=f'Local Python extraction: {report.get("template_id",category)}; {report.get("status","unverified")}.'))


def _unsupported(data,category,name,raw,reason):
    data.local_results.append(dict(category=category,source_file=name,status='unsupported_template',fields={},limitations=[reason]))
    data.document_audits.append(DocumentAudit(source_file=name,document_types=[category],pages_read=[],
        readability='unreadable',summary='Local extraction could not verify this template.',uncertainties=[reason]))
    data.review_limitations.append(f'{name}: {reason}')


def _form_report(raw,category,name):
    choices=('schengen_application','national_id_translation','bank_declaration') if category=='visa_form' else ('national_id_translation','bank_declaration','schengen_application')
    for template in choices:
        result=extract_spain_pdf(raw,template,name)
        if any(field['status']!='template_not_verified' for field in result['fields']):return template,result
    return None,None


def _appointment_report(name,raw):
    from validator import _parse_date
    values=[]
    with pymupdf.open(stream=raw,filetype='pdf') as pdf:
        for number,page in enumerate(pdf,1):
            for line in page.get_text().splitlines():
                if not re.search(r'appointment\s+(?:date|is\s+on)|تاريخ\s+الموعد|موعد\s+السفار[ةه]',line,re.I):continue
                if re.search(r'issue|print|تاريخ\s+الاصدار|تاريخ\s+الطباعة',line,re.I):continue
                for token in re.findall(r'\b(?:\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[/.-]\d{1,2}[/.-]\d{4})\b',line):
                    parsed=_parse_date(token.replace('.','/'))
                    if parsed:values.append(AppointmentInfo(source_file=name,page=number,appointment_date=parsed.isoformat(),text=line))
    return values if len({value.appointment_date for value in values})==1 else [AppointmentInfo(source_file=name)]


def extract_local_documents(uploaded,cache=None,review_country=None):
    data=VisaDocumentExtraction(extraction_mode='local')
    data.review_provenance={'factual_engine':'local_python_ocr','external_ai_requests':0,'sources':[]}
    collected={};hr_inputs=[]
    for category,group in uploaded.items():
        for name,raw in group:
            if category in ('cover_letter','travel_plan'):
                _unsupported(data,category,name,raw,'Cover-letter and travel-plan content requires manual review.')
                continue
            report=None;kind=category;mapping={};obj=None
            try:
                if category=='passport':
                    def passport_report():
                        image=raw
                        if name.lower().endswith('.pdf'):
                            with pymupdf.open(stream=raw,filetype='pdf') as pdf:image=pdf[0].get_pixmap(matrix=pymupdf.Matrix(2,2),alpha=False).tobytes('png')
                        return extract_egypt_passport(image,name)
                    report=cached_parse(cache,'passport-v2',[(name,raw)],passport_report)
                    mapping=PASS_MAP;obj=_model(report,mapping,PassportInfo)
                elif category in ('visa_form','supporting') and name.lower().endswith('.pdf'):
                    if review_country=='belgium' and category=='visa_form':
                        report=cached_parse(cache,'belgium-portal-v1/visa_form',[(name,raw)],lambda:extract_belgium_pdf(raw,name))
                        template='belgium_portal' if report['status']!='unsupported_template' else None
                        if template is None:
                            _unsupported(data,category,name,raw,'The Belgium portal application layout could not be verified.')
                            continue
                    else:
                        template,report=cached_parse(cache,'spain-form-v1/'+category,[(name,raw)],lambda:_form_report(raw,category,name))
                    if template in ('schengen_application','belgium_portal'):
                        kind='visa_form';mapping=APP_MAP;obj=_model(report,mapping,VisaApplicationInfo)
                        obj.applicant_name=' '.join(value for value in (obj.given_names,obj.surname) if value) or None
                    elif template=='national_id_translation':
                        kind='national_id';mapping=ID_MAP;obj=_model(report,mapping,NationalIDInfo);obj.present=True
                    elif template=='bank_declaration':
                        kind='supporting'
                        claims=[]
                        for key in ('applicant.full_name','bank_holder.full_name','bank_holder.passport_number','bank_holder.national_id_number'):
                            value=_value(report,key);row=_fields(report).get(key,{})
                            if value:
                                claims.append(SupportingClaim(field_name='full_name' if key.endswith('full_name') else key.rsplit('.',1)[-1],
                                    value=value,page=row['page'],quote=row['sources'][0]['text'] if row['sources'] else value,
                                    subject_role='applicant' if key.startswith('applicant.') else 'other',reason='Bank holder and applicant remain independent subjects.'))
                        data.supporting_documents.append(SupportingDocument(source_file=name,document_type='Bank declaration',
                            summary='Local template extraction; account-holder identity is not assumed to be the applicant.',claims=claims))
                elif category=='hotel' and name.lower().endswith('.pdf'):
                    report=cached_parse(cache,'hotel-v1',[(name,raw)],lambda:extract_hotel_v1(raw,name))
                    mapping=HOTEL_MAP;obj=_model(report,mapping,HotelInfo)
                    from validator import _SCHENGEN_CITIES
                    location=_value(report,'location') or ''
                    cities=[city for city in _SCHENGEN_CITIES if re.search(r'\b'+re.escape(city)+r'\b',location,re.I)]
                    obj.city=cities[0].title() if len(cities)==1 else None
                elif category=='flight' and name.lower().endswith('.pdf'):
                    report=cached_parse(cache,'flight-v1',[(name,raw)],lambda:extract_flight_v1(raw,name))
                    mapping=FLIGHT_MAP;obj=_model(report,mapping,FlightInfo)
                elif category=='employment' and name.lower().endswith('.pdf'):
                    hr_inputs.append((name,raw));continue
                elif category=='appointment' and name.lower().endswith('.pdf'):
                    appointments=_appointment_report(name,raw);data.appointments.extend(appointments)
                    data.local_results.append(dict(category='appointment',source_file=name,
                        status='extracted' if appointments and all(item.appointment_date for item in appointments) else 'needs_verification',
                        fields={'appointment_date':dict(status='extracted' if appointments and all(item.appointment_date for item in appointments) else 'unverified')}))
                    data.document_audits.append(DocumentAudit(source_file=name,document_types=['appointment'],
                        pages_read=list(range(1,_page_count(name,raw)+1)),readability='partial',
                        summary='Local extraction of explicitly labelled appointment dates.',uncertainties=['Appointment layout has not yet been validated against a reference sample.']))
                    data.detected_documents.append(kind);continue
            except Exception as exc:
                from monitoring import capture_error
                capture_error(exc,'local_extraction')
                # Malformed/unsupported inputs and optional OCR failures never trigger document AI.
                _unsupported(data,category,name,raw,'Local extraction could not verify this file. Check the template, orientation and local OCR installation.')
                continue
            if report is None:
                _unsupported(data,category,name,raw,'No verified local parser is available for this document/template.')
                continue
            report['category']=kind;report['target_states']=_target_states(report,mapping,obj);data.local_results.append(report)
            _audit(data,kind,name,raw,report);_evidence(data,report,kind,mapping,raw,obj)
            data.detected_documents.extend([kind] if kind not in data.detected_documents else [])
            if obj is not None:collected.setdefault(kind,[]).append((name,obj,report))
    for category,attribute in [('passport','passport'),('visa_form','visa_form'),('flight','flight'),('national_id','national_id')]:
        entries=collected.get(category,[])
        if len(entries)==1:setattr(data,attribute,entries[0][1])
        elif len(entries)>1:data.review_limitations.append(f'Multiple {category} documents were supplied; confirm the current authoritative version. No summary version was selected.')
    data.hotel=[entry[1] for entry in collected.get('hotel',[])]
    for category,entries in collected.items():
        for name,obj,report in entries:
            identity=dict(document=category,source_file=name,page=None if report.get('template_id')=='belgium.portal_application.v1' else 1)
            identity['full_name']=getattr(obj,{'visa_form':'applicant_name','flight':'passenger_name','hotel':'guest_name'}.get(category,'full_name'),None)
            for field in ('given_names','surname','passport_number','date_of_birth','passport_issue','passport_expiry','national_id_number'):
                identity[field]=getattr(obj,field,None)
            if category=='national_id':
                identity.update(national_id_number=obj.id_number,national_id_issue=obj.issue_date,national_id_expiry=obj.expiry_date)
                identity['date_of_birth']=_value(report,'holder.date_of_birth')
            data.identity_evidence.append(IdentityEvidence(**identity))
    if hr_inputs:
        try:
            hr=cached_parse(cache,'hr-v2',hr_inputs,lambda:extract_hr_documents(hr_inputs))
            data.local_hr=hr
            good=lambda key:_text(hr['values'].get(key)) if hr['fields'][key]['status'] in ('extracted','confirmed') else None
            approved=hr['values'].get('leave_approved') if hr['fields']['leave_approved']['status'] in ('extracted','confirmed') else None
            salary=good('net_salary') or good('gross_salary')
            salary_currency=good('salary_currency')
            data.employment=EmploymentInfo(employer_name=good('company_name'),job_title=good('job_title'),
                monthly_salary=' '.join(value for value in (salary,salary_currency) if value) or None,
                employer_address=good('company_address'),
                approved_leave_start=good('leave_start'),approved_leave_end=good('leave_end'),leave_approval_confirmed=approved,evidence_type='employment')
            for doc,(name,raw) in zip(hr['documents'],hr_inputs):
                fields={field['key']:field for field in doc['fields']}
                report=dict(category='employment',source_file=name,fields=fields,template_id='local_hr',
                    status='extracted' if fields and all(field['status']=='extracted' for field in fields.values()) else 'needs_verification',
                    limitations=['Scanned HR fields remain provisional until confirmed.'] if any(field['status']!='extracted' for field in fields.values()) else [])
                data.local_results.append(report);_audit(data,'employment',name,raw,report)
            if len(collected.get('visa_form',[]))==1:
                data.local_hr_checks=compare_hr_with_application(hr,collected['visa_form'][0][2])['checks']
            else:data.review_limitations.append('HR comparison requires one verified current visa application; confirm the application template/version.')
            data.detected_documents.append('employment')
        except Exception as exc:
            from monitoring import capture_error
            capture_error(exc,'hr_extraction')
            for name,raw in hr_inputs:_unsupported(data,'employment',name,raw,'Local HR extraction is unavailable or this template needs verification.')
    data.travel_cities=list(dict.fromkeys([f.destination_city for _,f,_ in collected.get('flight',[]) if f.destination_city]+[hotel.city for hotel in data.hotel if hotel.city]))
    from validator import _SCHENGEN_CITIES,_parse_date
    nights={}
    for hotel in data.hotel:
        country=_SCHENGEN_CITIES.get((hotel.city or '').casefold())
        start,end=_parse_date(hotel.check_in_date),_parse_date(hotel.check_out_date)
        if country and start and end and end>start:nights[country]=nights.get(country,0)+(end-start).days
    data.total_nights_per_country=nights or None
    winners=[country for country,count in nights.items() if count==max(nights.values())]
    data.main_schengen_destination=winners[0] if len(winners)==1 else None
    data.executive_summary='Document fields were extracted locally and compared using deterministic rules. Narrative content requires manual review.'
    for record in data.local_results:
        original=next((raw for group in uploaded.values() for name,raw in group if name==record['source_file']),None)
        data.review_provenance['sources'].append(dict(source_file=record['source_file'],category=record['category'],
            sha256=sha256(original).hexdigest() if original is not None else None,
            parser=record.get('template_id','unsupported'),status=record['status']))
    return data


def hr_validation_issues(data):
    from validator import ValidationIssue,Severity
    issues=[]
    for check in data.local_hr_checks:
        if check['status']=='match':continue
        verified=check['status']=='mismatch'
        issues.append(ValidationIssue(document_name='Employment Documents',field_name=check['check'],
            found_value=_text(check.get('found')),expected_value=_text(check.get('expected')) or 'Verified application/HR evidence',
            severity=Severity.CRITICAL if verified and check['check']=='hr.employee_name' else Severity.HIGH,
            affects_score=verified,message_key='support.conflict' if verified else 'evidence.incomplete',
            title_en=check['message'],title_ar='مراجعة بيانات العمل والإجازة',
            recommended_fix=check['message']+' Check the quoted original HR/application fields and correct the inconsistent document or confirm an unreadable value.',
            evidence=[dict(source_file=source['source_file'],page=source.get('page',1),text=source.get('text') or '',
                           box=source.get('region_normalized')) for source in check.get('sources',[])]))
    return issues


def local_identity_issues(data):
    from validator import ValidationIssue,Severity
    found,expected=data.visa_form.place_of_birth,data.passport.place_of_birth
    normalize=lambda value:' '.join(value.casefold().split())
    if found and expected and normalize(found)!=normalize(expected):
        return [ValidationIssue(document_name='Visa Application Form',field_name='place_of_birth',
            found_value=found,expected_value=expected,severity=Severity.HIGH,message_key='support.conflict',
            title_en='Place of birth does not match the passport',
            recommended_fix='Copy the place of birth from the passport into the visa application using the exact printed spelling.')]
    return []


def guard_local_issues(issues,data,uploaded):
    """Extraction uncertainty is a limitation, never a proven applicant error."""
    if data.extraction_mode!='local':return issues
    from evidence import _category
    if not uploaded.get('passport'):
        missing=[issue for issue in issues if _category(issue.document_name)=='passport'
                 and issue.found_value is None and issue.field_name in
                 ('passport_number','passport_expiry','passport_issue','full_name')]
        if missing:
            from validator import ValidationIssue,Severity
            issues=[issue for issue in issues if issue not in missing]+[ValidationIssue(
                document_name='Passport',field_name='passport_upload',found_value=None,
                expected_value='Upload the passport in the Passport section',severity=Severity.CRITICAL,
                recommended_fix='No file was uploaded in the Passport section. Upload the passport image or PDF, then run a fresh review.',
                message_key='document.not_uploaded',title_en='Passport not uploaded',title_ar='لم يتم رفع جواز السفر')]
    records=data.local_results
    aliases={'full_name':('full_name','applicant_name','guest_name','passenger_name'),
             'applicant_name':('full_name','applicant_name','guest_name','passenger_name'),
             'national_id_number':('national_id_number','id_number'),
             'departure_date':('departure_date','intended_arrival'),
             'return_date':('return_date','intended_departure')}
    good={'extracted','confirmed','blank'}
    for issue in issues:
        category=_category(issue.document_name)
        related=[record for record in records if record['category']==category]
        uncertain=any(record.get('status')!='extracted' for record in related)
        target=aliases.get(issue.field_name,(issue.field_name,))
        states=[record['target_states'][key] for record in related for key in target if key in record.get('target_states',{})]
        if states:uncertain=any(state not in good for state in states)
        if category in ('passport','visa_form','flight','national_id') and len(related)>1 and not any(record['source_file'] in issue.document_name for record in related):
            uncertain=True
        if issue.field_name.startswith('hr.'):
            # HR checks already distinguish confirmed conflicts from provisional OCR.
            continue
        if issue.message_key.startswith('business.') and any(record.get('status')=='unsupported_template' for record in records if record['category']=='supporting'):
            uncertain=True
        if category in ('cover_letter','travel_plan'):
            related_audits=[audit for audit in data.document_audits if category in audit.document_types]
            # A combined letter/plan may be supplied in either slot. Deduplication
            # reads its bytes once; it must not make the other document "missing".
            uncertain=uncertain or any(uploaded.get(slot) for slot in ('cover_letter','travel_plan')) or any(
                audit.readability!='readable' for audit in related_audits)
        elif category not in ('supporting',None) and not related:
            # A genuinely absent mandatory document remains a missing-document finding.
            uncertain=bool(uploaded.get(category))
        if issue.field_name in ('full_name','applicant_name','passport_number','date_of_birth','place_of_birth','passport_issue','passport_expiry','given_names','surname'):
            reference={'full_name':'full_name','applicant_name':'full_name'}.get(issue.field_name,issue.field_name)
            if not getattr(data.passport,reference,None) and (category!='passport' or uploaded.get('passport')):uncertain=True
        if any(word in issue.field_name for word in ('departure','arrival','check_in','check_out','coverage','hotel_date')):
            if not data.visa_form.intended_arrival or not data.visa_form.intended_departure:uncertain=True
        if uncertain and issue.affects_score:
            issue.affects_score=False;issue.message_key='evidence.incomplete'
            issue.title_en='Local extraction needs verification'
            issue.title_ar='تحتاج القراءة المحلية إلى التحقق'
            issue.recommended_fix='Local parsing could not verify the source/template for this check. Inspect the original and confirm its values; this is not a confirmed document mismatch. '+issue.recommended_fix
    return issues
