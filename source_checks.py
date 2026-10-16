"""Source-layout checks for printed blanks and contradictory translation dates.

These supplement contextual AI review with observations from the actual PDF cells/text.
No applicant-specific names, dates or outcomes are encoded here.
"""
import re
from datetime import date, datetime, timedelta
import pymupdf
from validator import ValidationIssue, Severity, _names_match


def printed_form_checks(data, uploaded):
    issues = []
    audited = {a.source_file for a in data.document_audits if 'visa_form' in a.document_types}
    for category, group in uploaded.items():
        for name, raw in group:
            if (category != 'visa_form' and name not in audited) or not name.lower().endswith('.pdf'):
                continue
            missing, evidence = [], []
            with pymupdf.open(stream=raw,filetype='pdf') as doc:
                for number, page in enumerate(doc,1):
                    for table in page.find_tables().tables:
                        for index, row in enumerate(table.extract()):
                            if len(row) != 2 or not row[0]:
                                continue
                            label, value = row[0], (row[1] or '').strip()
                            field = None
                            if re.search(r'^11\b',label) and 'national identity number' in label.casefold():
                                field='national_id_number'
                                data.visa_form.national_id_number=value or None
                                if not value:
                                    data.visa_form.national_id_issue=data.visa_form.national_id_expiry=None
                                blank=not value and bool(data.national_id.id_number or data.passport.national_id_number)
                            elif re.search(r'^19\b',label) and 'email address' in label.casefold():
                                field='email';blank=not re.search(r'\S+@\S+',value)
                            elif re.search(r'^19a\b',label) and 'telephone' in label.casefold():
                                field='telephone';blank=not value
                            elif re.search(r'^25\b',label) and 'main destination' in label.casefold():
                                # The form prints both languages; retain the actual English
                                # country instead of silently substituting the booked country.
                                if value:
                                    data.visa_form.destination_country=value.splitlines()[-1].strip()
                            if not field or not blank:
                                continue
                            missing.append(field)
                            cells=[pymupdf.Rect(cell) for cell in table.rows[index].cells if cell]
                            rect=cells[0]
                            for cell in cells[1:]:rect |= cell
                            quote=label.splitlines()[-1]
                            evidence.append({'source_file':name,'page':number,'text':quote,'field_name':field,
                                'value':None,'box':[rect.x0/page.rect.width,rect.y0/page.rect.height,
                                    rect.x1/page.rect.width,rect.y1/page.rect.height],'layout':True})
            if missing:
                issues.append(ValidationIssue(document_name='Visa Application Form',field_name='application_completeness',
                    found_value='Blank: '+', '.join(missing),expected_value='Complete applicable applicant contact and identity fields',
                    severity=Severity.MEDIUM,title_en='Applicant fields are blank',message_key='context.application_completeness',
                    recommended_fix='Complete '+', '.join(missing)+' using the applicant’s verified details. These blanks were read from the actual form cells.',
                    evidence=evidence))
    return issues


def translation_date_checks(uploaded):
    issues=[]
    months={name:index for index,name in enumerate(('january','february','march','april','may','june','july','august','september','october','november','december'),1)}
    pattern=re.compile(r'(?:date\s+of\s+birth|birth\s+date)\s*:?\s*(\d{1,2})/(\d{1,2})/(\d{4})\s+in\s+words\s*:\s*([^\n]+)',re.I)
    for group in uploaded.values():
        for name,raw in group:
            if not name.lower().endswith('.pdf'):continue
            with pymupdf.open(stream=raw,filetype='pdf') as doc:
                for number,page in enumerate(doc,1):
                    for match in pattern.finditer(page.get_text(sort=True)):
                        written=next((value for month,value in months.items() if re.search(r'\b'+month+r'\b',match[4],re.I)),None)
                        # If neither D/M nor M/D can agree with the written month, this is
                        # a definite internal contradiction without guessing a date locale.
                        if written and written not in (int(match[1]),int(match[2])):
                            issues.append(ValidationIssue(document_name=f'Supporting Documents ({name})',field_name='translation_dob',
                                found_value=match.group(),expected_value='Numeric and written dates must agree with the original',
                                severity=Severity.LOW,title_en='Numeric and written birth dates disagree',message_key='context.translation_dob',
                                recommended_fix='Have the certified translator reconcile the numeric date and written month against the original. Preserve whose birth date is being described; this is not automatically an applicant passport mismatch.',
                                evidence=[{'source_file':name,'page':number,'text':match.group()}]))
    return issues


def reservation_and_title_checks(data, uploaded, review_date=None):
    """Read explicit hold conditions and applicant honorifics; no live-status claims."""
    issues=[];today=review_date or date.today()
    audits={audit.source_file:audit.document_types for audit in data.document_audits}
    for category,group in uploaded.items():
        for name,raw in group:
            if not name.lower().endswith('.pdf'):continue
            with pymupdf.open(stream=raw,filetype='pdf') as doc:
                pages=[page.get_text(sort=True) for page in doc]
            text='\n'.join(pages)
            if category=='flight' or 'flight' in audits.get(name,[]):
                hours=re.search(r'payment\s+within\s+(\d+)\s+hours',text,re.I)
                issued=re.search(r'Date\s+of\s+issue\s*:\s*(\d{1,2}\s+[A-Za-z]+\s+\d{4})',text,re.I)
                ticket=re.search(r'(?:e-?ticket|ticket)\s*(?:number|no\.?)\s*:?\s*\d{13}\b',text,re.I)
                if hours and issued and not ticket and re.search(r'ON\s+HOLD',text,re.I):
                    try:day=datetime.strptime(issued[1],'%d %b %Y').date()
                    except ValueError:day=None
                    if day and today>day+timedelta(days=(int(hours[1])+23)//24):
                        page_number=next(i for i,p in enumerate(pages,1) if re.search(r'payment\s+within',p,re.I))
                        quote=re.search(r'The fare quoted.*?cancelled\s*\.',pages[page_number-1],re.I|re.S)
                        quote=quote.group() if quote else hours.group()
                        issues.append(ValidationIssue(document_name='Flight Reservation',field_name='reservation_validity',
                            found_value=f'Payment hold: {hours[1]} hours; issued {day}',
                            expected_value='Evidence of a currently valid reservation or subsequent renewal/issuance',severity=Severity.HIGH,
                            message_key='context.reservation_validity',title_en='Payment-hold validity needs confirmation',
                            recommended_fix='The payment window printed on this copy has elapsed. Obtain current airline confirmation or a fresh valid reservation. This copy alone does not establish cancellation or require purchasing a ticket.',
                            evidence=[{'source_file':name,'page':page_number,'text':quote}]))
            gender=(data.passport.gender or '').casefold()
            wrong=r'\b(?:Ms|Mrs)\.' if gender in ('m','male','ذكر') else r'\bMr\.' if gender in ('f','female','أنثى') else None
            if wrong:
                for number,page in enumerate(pages,1):
                    for match in re.finditer(wrong+r'\s+([A-Z][A-Z \-]+)',page):
                        if _names_match(data.passport.full_name,match[1].strip(),data.passport.given_names,data.passport.surname):
                            issues.append(ValidationIssue(document_name=f'Supporting Documents ({name})',field_name='translation_honorific',
                                found_value=match.group(),expected_value='An honorific consistent with the applicant, or no honorific',
                                severity=Severity.LOW,message_key='context.translation_honorific',title_en='Applicant honorific is inconsistent',
                                recommended_fix='Ask the translator to correct the applicant honorific against the passport. This is a wording error, not a different applicant identity.',
                                evidence=[{'source_file':name,'page':number,'text':match.group()}]))
    return issues
