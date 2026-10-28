"""Portable synthetic regressions. No completed customer PDFs or values are committed."""
import copy
from pathlib import Path
import re

import pymupdf
import pytest

import spain_pdf_extractor as forms
from booking_template_extractor import name_matches,extract_hotel_v1,parse_flight_v1_lines,extract_flight_v1
from passport_template_extractor import check_digit,parse_td3,parse_egypt_passport_lines

FONT=Path(__file__).resolve().parents[1]/'assets/fonts/NotoSans-Regular.ttf'


def _page_data(page,number):
    lines=[];boxes=[]
    for block in page.get_text('rawdict')['blocks']:
        for line in block.get('lines',[]):
            chars=[char for span in line['spans'] for char in span['chars']]
            text=''.join(char['c'] for char in chars)
            if text:lines.append(dict(text=text,region_pdf_points=list(line['bbox'])))
            starts=[index for index,char in enumerate(chars) if char['c']=='□']
            for offset,start in enumerate(starts):
                end=starts[offset+1] if offset+1<len(starts) else len(chars)
                boxes.append(dict(label=''.join(char['c'] for char in chars[start+1:end]).strip(),
                                  region_pdf_points=list(chars[start]['bbox'])))
    return dict(page=number,width=page.rect.width,height=page.rect.height,lines=lines,checkboxes=boxes,
                words=[dict(text=word[4],region_pdf_points=list(word[:4])) for word in page.get_text('words')],
                printed_text=page.get_text(),images=[],drawings=[])


@pytest.fixture
def blank_factory(monkeypatch):
    """Reconstruct public blank labels so tests do not depend on private local PDFs."""
    original=forms._load
    def factory(template_id):
        template=copy.deepcopy(original(template_id));doc=pymupdf.open();font=pymupdf.Font(fontfile=str(FONT))
        reference_checkboxes=[copy.deepcopy(page['checkboxes']) for page in template['baseline_pages']]
        for baseline in template['baseline_pages']:
            page=doc.new_page(width=baseline['width'],height=baseline['height'])
            for line in baseline['lines']:
                x0,y0,x1,y1=line['region_pdf_points'];text=line['text']
                width=font.text_length(text,fontsize=1)
                size=min(6.0,(x1-x0)/max(width,1))
                page.insert_text((x0,y1-2),text,fontsize=size,fontname='reference',fontfile=str(FONT))
        template['baseline_pages']=[_page_data(page,index) for index,page in enumerate(doc,1)]
        # Noto Sans omits U+25A1. Keep the independently inspected checkbox geometry
        # rather than deriving choice positions from its missing-glyph substitute.
        for page,checkboxes in zip(template['baseline_pages'],reference_checkboxes):
            page['checkboxes']=checkboxes
        monkeypatch.setattr(forms,'_load',lambda key:copy.deepcopy(template) if key==template_id else original(key))
        return doc,template
    return factory


def add_answer(page,rect,text):
    page.add_freetext_annot(pymupdf.Rect(rect),text,fontsize=10,fontname='Helv',text_color=(0,0,0))


def test_actual_added_identifier_preserves_leading_zero_and_missing_fields(blank_factory):
    doc,_=blank_factory('schengen_application')
    add_answer(doc[0],[73,603,159,620],'X00001234')
    result=forms.extract_spain_pdf(doc.tobytes(),'schengen_application')
    assert result['filled_values']['travel_document.number']=='X00001234'
    assert result['values']['applicant.national_id_number'] is None
    assert result['values']['applicant.surname_at_birth'] is None
    assert not any(key.startswith('official.') for key in result['filled_values'])
    doc.close()


@pytest.mark.parametrize('template_id',['schengen_application','bank_declaration','national_id_translation'])
def test_blank_labels_and_preprinted_defaults_never_become_entered_answers(blank_factory,template_id):
    doc,_=blank_factory(template_id)
    result=forms.extract_spain_pdf(doc.tobytes(),template_id)
    assert result['status']=='extracted' and result['filled_values']=={}
    if template_id=='bank_declaration':
        assert result['preprinted_values']=={'declaration.place':'CAIRO'}
        assert result['values']['declaration.place'] is None
    doc.close()


def test_flattened_answers_keep_punctuation_and_date_values(blank_factory):
    doc,_=blank_factory('national_id_translation')
    add_answer(doc[0],[165,500,500,520],'Lab Technician - Example Hospital')
    add_answer(doc[0],[450,473,530,491],'02/01/2021')
    before=forms.extract_spain_pdf(doc.tobytes(),'national_id_translation')
    doc.bake(annots=True,widgets=True)
    after=forms.extract_spain_pdf(doc.tobytes(),'national_id_translation')
    assert before['normalized_values']==after['normalized_values']
    assert after['values']['holder.current_job']=='Lab Technician - Example Hospital'
    assert after['normalized_values']['holder.issue_date']=='2021-01-02'
    doc.close()


def test_checkmark_maps_only_one_choice_and_a_typo_is_not_corrected(blank_factory):
    doc,template=blank_factory('schengen_application')
    box=next(box for box in template['baseline_pages'][0]['checkboxes'] if box['label']=='Male')
    x0,y0,x1,y1=box['region_pdf_points']
    add_answer(doc[0],[x0-3,y0-2,x0+9,y0+10],'/')
    add_answer(doc[0],[160,276,230,294],'ANNX')
    result=forms.extract_spain_pdf(doc.tobytes(),'schengen_application')
    assert result['filled_values']['applicant.sex']=='Male'
    assert result['values']['applicant.marital_status'] is None
    assert result['filled_values']['applicant.given_names']=='ANNX'
    doc.close()


def test_unlabelled_employer_split_is_provisional_not_silently_authoritative(blank_factory):
    doc,_=blank_factory('schengen_application')
    add_answer(doc[1],[58,204,535,220],'Example Hospital, 12 Sample Street, City, +20 50 1234567')
    result=forms.extract_spain_pdf(doc.tobytes(),'schengen_application')
    fields={row['key']:row for row in result['fields']}
    assert fields['employment_or_education.name']['value']=='Example Hospital'
    assert fields['employment_or_education.name']['status']=='needs_verification'
    assert result['shared_answers']
    doc.close()


def test_wrong_or_scanned_form_fails_closed_instead_of_reporting_blank():
    doc=pymupdf.open();doc.new_page()
    report=forms.extract_spain_pdf(doc.tobytes(),'bank_declaration')
    assert report['status']=='needs_verification' and report['filled_values']=={}
    assert all(row['status']=='template_not_verified' for row in report['fields'])
    doc.close()


def test_invalid_iso_date_keeps_raw_text_but_cannot_be_used_as_a_normalized_date(blank_factory):
    doc,_=blank_factory('schengen_application')
    add_answer(doc[0],[188,604,249,622],'2030-99-99')
    result=forms.extract_spain_pdf(doc.tobytes(),'schengen_application')
    row=next(row for row in result['fields'] if row['key']=='travel_document.issue_date')
    assert row['value']=='2030-99-99' and row['normalized_value'] is None
    assert row['status']=='invalid_or_ambiguous_date'
    doc.close()


def test_short_unknown_flight_template_is_rejected_before_ocr():
    doc=pymupdf.open();doc.new_page()
    assert extract_flight_v1(doc.tobytes())['status']=='unsupported_template'
    doc.close()


@pytest.mark.parametrize('found,expected',[
    ('Anna Tester',True),('ANNA MARIA TESTER',True),('Anna Maria',False),
    ('Anna Testxr',False),('AnnaTester',False),('Tester Anna',False),
    ('Anna Tester123',False),('Anna+Tester',False),('',None)])
def test_exact_short_name_rule_never_fuzzy_repairs_a_booking(found,expected):
    assert name_matches(found,'ANNA MARIA','TESTER') is expected


def test_compound_surname_must_remain_complete():
    assert name_matches('Anna Van Tester','ANNA MARIA','VAN TESTER')
    assert not name_matches('Anna Tester','ANNA MARIA','VAN TESTER')


def synthetic_mrz():
    first='P<EGYTESTER<<ANNA<MARIA'.ljust(44,'<')
    passport='X00001234';birth='900101';expiry='310101';optional='<'*14
    second=passport+check_digit(passport)+'EGY'+birth+check_digit(birth)+'F'+expiry+check_digit(expiry)+optional+check_digit(optional)
    return first,second+check_digit(second[:10]+second[13:20]+second[21:43])


def test_mrz_known_check_digit_examples_and_no_character_repair():
    assert check_digit('L898902C3')=='6'
    assert check_digit('740812')=='2'
    first,second=synthetic_mrz()
    result=parse_td3(first,second)
    assert result['status']=='check_digits_valid'
    assert result['values']['surname']=='TESTER' and result['values']['given_names']=='ANNA MARIA'
    changed=second[:2]+'1'+second[3:]
    assert parse_td3(first,changed)['status']=='mrz_check_failed'
    assert parse_td3(first,second[:-1])['status']=='unreadable_mrz'


def line(text,page=2,y=0.1,x=0.2,confidence=0.99):
    return dict(text=text,page=page,region_normalized=[x-0.04,y-0.01,x+0.04,y+0.01],confidence=confidence,method='local_ocr')


def passport_lines():
    first,second=synthetic_mrz()
    return [line('Date of Birth',y=.34),line('Place of Birth',y=.35),line('Date of Issue',y=.46),line('Date of Expiry',y=.47),
            line('01/01/1990',x=.42,y=.386),line('02/01/202001/01/2031',x=.50,y=.51),
            line('TEST CITY',x=.57,y=.39),line('X00001234',x=.81,y=.15),
            line(first,x=.50,y=.86),line(second,x=.50,y=.94,confidence=.72)]


def test_passport_printed_dates_establish_century_and_visual_fields():
    result=parse_egypt_passport_lines(passport_lines())
    assert result['status']=='extracted'
    assert result['values']['date_of_birth']=='1990-01-01'
    assert result['values']['issue_date']=='2020-01-02'
    assert result['values']['expiry_date']=='2031-01-01'
    assert result['values']['place_of_birth']=='TEST CITY'


def test_passport_visual_mrz_disagreement_is_not_guessed_or_repaired():
    rows=passport_lines();rows[4]['text']='01/01/1991'
    result=parse_egypt_passport_lines(rows)
    assert result['status']=='needs_verification' and result['values']['date_of_birth'] is None
    rows=passport_lines();rows[-2]['confidence']=.70
    result=parse_egypt_passport_lines(rows)
    assert result['values']=={} and result['status']=='needs_verification'


@pytest.mark.parametrize('digits',[
    '01234567890123','٠١٢٣٤٥٦٧٨٩٠١٢٣','۰۱۲۳۴۵۶۷۸۹۰۱۲۳',
])
def test_passport_reads_the_separate_printed_national_id_with_digit_script_normalization(digits):
    rows=passport_lines()+[line('الرقم القومي '+digits,x=.75,y=.62)]
    result=parse_egypt_passport_lines(rows)
    assert result['values']['national_id_number']=='01234567890123'
    assert result['values']['passport_number']=='X00001234'
    assert result['fields']['national_id_number']['sources'][0]['text'].endswith(digits)


@pytest.mark.parametrize('text,y,confidence',[
    ('0123456789012',.62,.99),('012345678901234',.62,.99),
    ('01234567890123',.74,.99),('01234567890123',.62,.70),
    ('012345678O0123',.62,.99),
])
def test_passport_never_repairs_or_guesses_an_uncertain_national_id(text,y,confidence):
    result=parse_egypt_passport_lines(passport_lines()+[line(text,x=.75,y=y,confidence=confidence)])
    assert result['values']['national_id_number'] is None
    assert result['fields']['national_id_number']['status']=='unverified'
    assert result['status']=='extracted'  # Other verified passport fields remain usable.


def test_two_conflicting_passport_id_readings_require_verification():
    rows=passport_lines()+[line(value,x=.75,y=.62) for value in ('01234567890123','01234567890124')]
    assert parse_egypt_passport_lines(rows)['values']['national_id_number'] is None


def test_mrz_optional_data_is_not_assumed_to_be_the_printed_national_id():
    rows=passport_lines();optional='01234567890123'
    second=rows[-1]['text'][:28]+optional+check_digit(optional)
    rows[-1]['text']=second+check_digit(second[:10]+second[13:20]+second[21:43])
    assert parse_egypt_passport_lines(rows)['values']['national_id_number'] is None


@pytest.mark.parametrize('available',[True,False])
def test_optional_arabic_id_crop_preserves_other_identity_fields(monkeypatch,available):
    from io import BytesIO
    from PIL import Image
    import offline_ocr,passport_template_extractor as passport
    output=BytesIO();Image.new('RGB',(600,400),'white').save(output,format='PNG')
    monkeypatch.setattr(passport,'image_lines',lambda raw:passport_lines())
    def read(raw):
        if not available:raise ImportError('Optional Arabic OCR unavailable')
        return [dict(text='٠١٢٣٤٥٦٧٨٩٠١٢٣',confidence=.99,region_normalized=[0,0,1,1],method='local_arabic_ocr')]
    monkeypatch.setattr(offline_ocr,'arabic_image_line',read)
    result=passport.extract_egypt_passport(output.getvalue(),'passport.png')
    assert result['values']['passport_number']=='X00001234'
    assert result['values']['national_id_number']==('01234567890123' if available else None)
    if available:
        source=result['fields']['national_id_number']['sources'][0]
        assert source['region_normalized']==pytest.approx(passport.NATIONAL_ID_REGION,abs=.002)


def flight_lines():
    return [line('BOOKING ON HOLD',page=1),line('Itinerary',y=.05),line('Cairo - Madrid',y=.10),
            line('Monday1February2027',y=.12),line('07:40 Cairo',y=.16),line('10:15 Madrid',y=.21),
            line('Madrid - Cairo',y=.50),line('Wednesday3February2027',y=.52),
            line('15:25 Madrid',y=.56),line('20:40 Cairo',y=.61),line('1 Traveller (1 Adult)',y=.80)]


def test_flight_itinerary_scopes_routes_dates_and_actual_traveller_not_reservation_surname():
    result=parse_flight_v1_lines(flight_lines(),[line('Anna Tester',page=3)])
    assert result['status']=='extracted'
    assert result['values']['destination_country']=='Spain' and result['values']['origin_city']=='Cairo'
    assert result['values']['outbound_departure_date']=='2027-02-01'
    assert result['values']['return_departure_date']=='2027-02-03'
    assert result['values']['traveller_name']=='Anna Tester'
    assert result['values']['booking_status']=='held'


def test_merged_or_uncertain_ocr_name_is_not_split_using_passport_name():
    for name in ['AnnaTester','AnnaTester CONTACT INFORMATION']:
        result=parse_flight_v1_lines(flight_lines(),[line(name,page=3)])
        assert result['values']['traveller_name'] is None and result['status']=='needs_verification'


def test_invalid_itinerary_time_is_not_used_for_planning():
    rows=flight_lines();rows[4]['text']='99:99 Cairo'
    result=parse_flight_v1_lines(rows,[line('Anna Tester',page=3)])
    assert result['status']=='needs_verification'
    assert result['values']['outbound_departure_time'] is None


def test_hotel_labelled_dates_ignore_cancellation_deadline_and_price():
    doc=pymupdf.open();page=doc.new_page(width=612,height=792)
    items=[(108,60,'Stay in Madrid'),(108,90,'1 Feb 2027 - 3 Feb 2027'),(108,125,'Example Hotel'),
           (108,150,'Hotels.com itinerary: TEST-REF'),(108,180,'Reservation details'),
           (108,255,'Check in'),(309,255,'Check out'),(108,280,'Mon, 1 Feb'),(309,280,'Wed, 3 Feb'),
           (108,500,'Location'),(108,530,'12 Sample Street, Madrid, Spain'),(108,630,'Reserved for'),
           (108,650,'Anna Tester, 1 adult'),(108,700,'Free cancellation until 31 Jan 2027')]
    for x,y,text in items:page.insert_text((x,y),text,fontsize=10)
    result=extract_hotel_v1(doc.tobytes())
    assert result['status']=='extracted'
    assert result['values']['check_in_date']=='2027-02-01' and result['values']['check_out_date']=='2027-02-03'
    assert result['values']['reserved_for']=='Anna Tester'
    doc.close()
