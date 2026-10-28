"""Layout regressions use invented values; no supplied customer PDF is a fixture."""
import json
import pymupdf
import pytest

from usa_templates import ds_fields,client_fields,booking_fields,_choice
from usa_review import review_documents,extract_fields
from tests.test_usa_review import files,DS,CLIENT


def columns(rows):
    with pymupdf.open() as doc:
        page=doc.new_page(width=612,height=792)
        page.insert_text((28,60),'Online Nonimmigrant Visa Application (DS-160)',fontsize=10)
        for index,(label,value) in enumerate(rows):
            y=110+index*24
            page.insert_text((38,y),label,fontsize=8)
            if value:page.insert_text((335,y),value,fontsize=8)
        return doc.tobytes()


def client_table(rows):
    with pymupdf.open() as doc:
        page=doc.new_page(width=612,height=792)
        page.insert_text((60,60),'U.S. Visa Client Information Form',fontsize=12)
        for x in (70,270,550):page.draw_line((x,90),(x,90+35*len(rows)))
        for i in range(len(rows)+1):page.draw_line((70,90+i*35),(550,90+i*35))
        for index,(label,value) in enumerate(rows):
            page.insert_text((76,111+index*35),label,fontsize=9)
            if value:page.insert_text((278,111+index*35),value,fontsize=9)
        return doc.tobytes()


def booking(policy=True,weekday='Friday',nights=9,property_name='Synthetic Riverside Hotel'):
    with pymupdf.open() as doc:
        page=doc.new_page(width=612,height=792)
        page.insert_text((400,25),'Booking Confirmation',fontsize=12)
        page.insert_text((400,43),'CONFIRMATION NUMBER: 111.222',fontsize=8)
        page.insert_text((110,78),property_name,fontname='hebo',fontsize=10)
        for x,label,day,month,week in [(360,'CHECK-IN','25','DECEMBER',weekday),(445,'CHECK-OUT','3','JANUARY','Sunday')]:
            page.insert_text((x,78),label,fontsize=7)
            page.insert_text((x+4,99),day,fontsize=24)
            page.insert_text((x-4,113),month,fontsize=8)
            page.insert_text((x,126),week,fontsize=7)
        page.insert_text((542,78),'NIGHTS',fontsize=7)
        page.insert_text((547,99),str(nights),fontsize=24)
        if policy:page.insert_text((390,420),'from December 25, 2026 12:00 AM',fontsize=8)
        page.insert_text((80,600),'Unrelated closure: December 25, 2025',fontsize=8)
        page.insert_text((400,55),'PIN CODE: DO_NOT_EXTRACT_PIN',fontsize=7)
        return doc.tobytes()


def test_ceac_answer_columns_do_not_absorb_next_questions_or_contact_email():
    raw=columns([
        ('Name Provided:','DOE, JOHN MICHAEL'),('Date of Birth:','15 JAN 1990'),
        ('Country/Region of Origin (Nationality):','EGYPT'),
        ('Do you hold any other nationality','NO'),('indicated above?',''),
        ('Passport/Travel Document Number:','A12345678'),('Email Address:','synthetic@example.com'),
    ])
    fields=ds_fields(raw,'test.pdf')
    assert fields['nationality']['value']=='EGYPT'
    assert fields['full_name']['value']=='DOE, JOHN MICHAEL'
    assert fields['given_names']['value']=='JOHN MICHAEL'
    assert fields['passport_number']['value']=='A12345678'
    assert all(source['page']==1 and source['box'] for field in fields.values() for source in field['sources'])


def test_bilingual_client_table_cells_and_private_account_whitelist():
    raw=client_table([
        ('Full name as in passport /','JOHN MICHAEL DOE'),('Date of birth /','1990/01/15'),
        ('Current nationality /','EGYPTIAN'),('Company / employer name /','SYNTHETIC TRAVEL'),
        ('U.S. visa appointment account password /','DO_NOT_EXTRACT_PASSWORD'),
        ('Security question 1 /','DO_NOT_EXTRACT_QUESTION'),('Answer 1 /','DO_NOT_EXTRACT_ANSWER'),
    ])
    fields=client_fields(raw,'client.pdf')
    assert fields['full_name']['value']=='JOHN MICHAEL DOE'
    assert fields['date_of_birth']['value']=='1990/01/15'
    assert fields['employer_name']['value']=='SYNTHETIC TRAVEL'
    assert 'DO_NOT_EXTRACT' not in json.dumps(fields)


@pytest.mark.parametrize('answer,expected,status',[
    ('☑ Yes / نعم ☐ No / لا','yes','extracted'),
    ('☐ Yes / نعم ☑ No / لا','no','extracted'),
    ('☐ Yes / نعم No / لا','no','needs_verification'),
    ('☐ Yes / نعم ☐ No / لا',None,'needs_verification'),
])
def test_unchecked_or_deleted_checkboxes_never_become_confirmed_answers(answer,expected,status):
    value,actual=_choice(answer,('yes','no'))
    assert actual==status
    if expected:assert value==expected
    else:assert value not in ('yes','no')


def test_booking_year_rollover_is_established_from_its_own_evidence():
    fields=booking_fields(booking(),'hotel.pdf')
    assert fields['check_in_date']['value']=='2026-12-25'
    assert fields['check_out_date']['value']=='2027-01-03'
    assert fields['hotel_name']['value']=='Synthetic Riverside Hotel'
    assert set(fields)=={'hotel_name','check_in_date','check_out_date'}
    assert 'DO_NOT_EXTRACT_PIN' not in json.dumps(fields)


@pytest.mark.parametrize('kwargs',[dict(policy=False),dict(weekday='Thursday'),dict(nights=8)])
def test_missing_or_contradictory_hotel_year_is_not_guessed_from_ds160(kwargs):
    raw=booking(**kwargs)
    fields=booking_fields(raw,'hotel.pdf')
    assert 'check_in_date' not in fields and 'check_out_date' not in fields
    assert fields['hotel_name']['value']=='Synthetic Riverside Hotel'
    uploaded=files();uploaded['hotel']=[('hotel.pdf',raw)]
    result=review_documents(uploaded)
    assert next(c for c in result['usa_checks'] if c['field']=='hotel_coverage_gap')['status']=='needs_verification'


def test_different_booking_property_name_is_read_from_the_document():
    fields=booking_fields(booking(property_name='Different Synthetic Inn'),'hotel.pdf')
    assert fields['hotel_name']['value']=='Different Synthetic Inn'


def test_word_and_html_use_native_text_sections_and_do_not_send_documents(monkeypatch):
    from tests.test_document_ingestion import docx
    from xml.sax.saxutils import escape
    uploaded=files()
    body=''.join('<w:p><w:r><w:t>'+escape(line)+'</w:t></w:r></w:p>' for line in DS.splitlines())
    raw=docx(('<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'+body+'</w:body></w:document>').encode())
    uploaded['ds160']=[('ds.docx',raw)]
    uploaded['client_form']=[('client.html',('<html><body>'+''.join('<p>'+escape(line)+'</p>' for line in CLIENT.splitlines())+'</body></html>').encode())]
    result=review_documents(uploaded)
    assert not any(c['status']=='mismatch' for c in result['usa_checks'])
    assert result['provenance']['external_ai_requests']==0
    sources=[s for c in result['usa_checks'] for s in c['sources'] if s.get('native_section')]
    assert sources and all(s['page'] is None for s in sources)


def test_repeated_filenames_have_unambiguous_source_references():
    uploaded={key:[('same.pdf',group[0][1])] for key,group in files().items()}
    result=review_documents(uploaded)
    sources=[name for group in result['source_files'].values() for name,_ in group]
    assert len(sources)==len(set(sources))==4
    assert all(s['source_file'] in sources for c in result['usa_checks'] for s in c['sources']+c['references'])
