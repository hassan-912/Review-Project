"""Belgium-only routing and portal controls, with fictional applicant data."""
from copy import deepcopy
from unittest.mock import Mock

import pymupdf
import pytest

import belgium_pdf_extractor as belgium
import local_extraction
import review_pipeline
from document_cache import DocumentCache
from extractor import extract_documents


def portal_pdf(employer=True, blank=False, shift=0):
    doc = pymupdf.open()

    def label(page, text, x, y):
        page.insert_text((x, y+shift), text, fontsize=9)

    def control(page, text, rect):
        rect = pymupdf.Rect(rect) + (0, shift, 0, shift)
        page.draw_rect(rect, color=(.7, .7, .7), width=.8)
        if text:
            page.insert_text((rect.x0+8, rect.y0+19), text, fontsize=10)

    first = doc.new_page()
    label(first, 'Visa application', 50, 30)
    label(first, 'Applicant information', 50, 55)
    for text, value, y in [('1. Surname','TESTER',90), ('3. First name','ANNA',155),
                           ('5. Place of birth','Example Town',350),
                           ('11. National identity number, where applicable','00001234567890',415),
                           ('13. Document number','X00001234',480),
                           ('14. Date of issue','01/02/2020',545), ('15. Valid until','31/01/2030',610)]:
        label(first, text, 50, y)
        control(first, 'Enter' if blank else value, (50,y+10,545,y+40))
    label(first, '4. Date of birth', 50, 220)
    for x,value in [(50,'17'),(220,'08'),(390,'1993')]:
        control(first,'Choose' if blank else value,(x,230,x+150,260))
    second = doc.new_page()
    label(second, 'Travel information', 50, 30)
    label(second, '21. Current occupation',50,90)
    control(second,'Choose' if blank else 'Engineer',(300,75,545,105))
    label(second, '23. Purpose(s) of the journey',50,155)
    control(second,'Enter' if blank else 'Tourism',(50,165,545,195))
    for text,y in [('25. Member State(s) of destination',235),('26. Member State of first entry',300)]:
        label(second,text,50,y)
        control(second,'Choose' if blank else 'BELGIUM',(350,y-15,545,y+15))
    for text,value,y in [('27. Intended date of arrival of the first intended stay in the Schengen area','20/04/2027',365),
                          ('27. Intended date of departure from the Schengen area after the first intended stay','27/04/2027',430)]:
        label(second,text,50,y)
        control(second,'Enter' if blank else value,(50,y+10,545,y+40))
    label(second,'Financing of stay',50,530)
    label(second,'32. Surname',50,570)
    control(second,'SPONSOR',(50,580,545,610))
    if employer:
        third = doc.new_page()
        for text,value,y in [('22. Type','Employer',60),('22. Name','Example Works',125),
                             ('22. Country/region','EGYPT',320),('22. e-mail','hr@example.com',385),
                             ('22. Telephone number','+20255550123',450)]:
            label(third,text,50,y)
            control(third,'Enter' if blank else value,(210,y-15,545,y+15))
        label(third,'22. Street',50,190)
        control(third,'Enter' if blank else 'Company Road',(210,175,390,205))
        label(third,'no',430,190)
        control(third,'Enter' if blank else '12',(460,175,545,205))
        label(third,'22. Postal code',50,255)
        control(third,'Enter' if blank else '12345',(210,240,300,270))
        label(third,'22. City',320,255)
        control(third,'Enter' if blank else 'Cairo',(400,240,545,270))
        label(third,'19. Street',50,530)
        control(third,'Home Road',(210,515,545,545))
    raw = doc.tobytes()
    doc.close()
    return raw


@pytest.fixture
def readings():
    raw=portal_pdf()
    from offline_ocr import pdf_lines
    with pymupdf.open(stream=raw,filetype='pdf') as doc:
        controls={n:belgium._rectangles(page) for n,page in enumerate(doc,1)}
    return pdf_lines(raw),controls


def row(report,key):
    return next(field for field in report['fields'] if field['key']==key)


@pytest.mark.parametrize('shift',[0,30])
def test_reads_core_fields_and_expanded_two_column_employer_without_fixed_pages(shift):
    report=belgium.extract_belgium_pdf(portal_pdf(shift=shift),'synthetic.pdf')
    values=report['normalized_values']
    assert values['applicant.surname']=='TESTER'
    assert values['applicant.given_names']=='ANNA'  # not the financing applicant
    assert values['applicant.date_of_birth']=='1993-08-17'
    assert values['travel_document.number']=='X00001234'
    assert values['travel_document.issue_date']=='2020-02-01'
    assert values['journey.intended_arrival']=='2027-04-20'
    assert values['journey.intended_departure']=='2027-04-27'
    assert values['occupation.current']=='Engineer'
    assert values['employment_or_education.name']=='Example Works'
    assert values['employment_or_education.address']=='Company Road, 12, 12345, Cairo, EGYPT'
    assert values['employment_or_education.email']=='hr@example.com'
    assert values['employment_or_education.telephone']=='+20255550123'
    assert values['applicant.contact.street']=='Home Road'
    address=row(report,'employment_or_education.address')
    assert address['status']=='extracted'
    assert {source['page'] for source in address['sources']}=={3}
    assert all(source['source_file']=='synthetic.pdf' and source['region_normalized'] for source in address['sources'])
    assert report['ai_requests']==0


def test_empty_controls_and_placeholders_never_become_answers():
    report=belgium.extract_belgium_pdf(portal_pdf(blank=True))
    for key in ('occupation.current','employment_or_education.name','employment_or_education.address',
                'employment_or_education.email','applicant.date_of_birth'):
        assert row(report,key)['status']=='blank'
        assert report['normalized_values'][key] is None


def test_raster_portal_retains_ocr_method_and_detects_image_input_borders(readings,monkeypatch):
    lines,_=deepcopy(readings)
    for line in lines:line.update(method='local_ocr',confidence=.99)
    raster=pymupdf.open()
    with pymupdf.open(stream=portal_pdf(),filetype='pdf') as original:
        for source in original:
            page=raster.new_page(width=source.rect.width,height=source.rect.height)
            page.insert_image(page.rect,stream=source.get_pixmap(matrix=pymupdf.Matrix(2,2)).tobytes('png'))
    reader=Mock(return_value=lines)
    monkeypatch.setattr(belgium,'pdf_lines',reader)
    raw=raster.tobytes();raster.close()
    report=belgium.extract_belgium_pdf(raw,'scan.pdf')
    reader.assert_called_once_with(raw)
    assert report['normalized_values']['applicant.date_of_birth']=='1993-08-17'
    assert row(report,'employment_or_education.address')['status']=='extracted'
    assert all(source['method']=='local_ocr' for source in row(report,'employment_or_education.name')['sources'])


def test_empty_ocr_control_does_not_prove_a_blank_answer(readings):
    lines,controls=deepcopy(readings)
    for line in lines:line.update(method='local_ocr',confidence=.99)
    lines=[line for line in lines if line['text']!='Example Works']
    report=belgium.parse_belgium_lines(lines,controls)
    assert row(report,'employment_or_education.name')['status']=='unverified'


def test_absent_conditional_employer_is_not_read_from_home_or_host():
    report=belgium.extract_belgium_pdf(portal_pdf(employer=False))
    assert row(report,'employment_or_education.name')['status']=='not_present'
    assert row(report,'employment_or_education.address')['status']=='not_present'


def test_low_confidence_ocr_is_preserved_as_candidate_but_not_used_by_bridge(readings,monkeypatch):
    lines,controls=deepcopy(readings)
    for line in lines:
        line.update(method='local_ocr',confidence=.99)
        if line['text']=='X00001234':line['confidence']=.65
    report=belgium.parse_belgium_lines(lines,controls,'scan.pdf')
    assert row(report,'travel_document.number')['status']=='needs_verification'
    monkeypatch.setattr(local_extraction,'extract_belgium_pdf',lambda *a:report)
    data=extract_documents({'visa_form':[('scan.pdf',portal_pdf())]},review_country='belgium')
    assert data.visa_form.passport_number is None
    assert data.visa_form.surname=='TESTER'


def test_uncertain_application_candidates_cannot_reach_direct_hr_comparisons(readings):
    lines,controls=deepcopy(readings)
    for line in lines:
        line.update(method='local_ocr',confidence=.99)
        if line['text'] in ('ANNA','Example Works','20/04/2027'):line['confidence']=.60
    report=belgium.parse_belgium_lines(lines,controls)
    for key in ('applicant.given_names','employment_or_education.name','journey.intended_arrival'):
        assert row(report,key)['value'] is not None
        assert row(report,key)['status']=='needs_verification'
        assert report['normalized_values'][key] is None


def test_bad_dates_are_not_repaired_and_duplicate_labels_are_not_selected(readings):
    lines,controls=deepcopy(readings)
    for line in lines:
        if line['text']=='20/04/2027':line['text']='31/02/2027'
    duplicate=next(line for line in lines if line['text']=='22. Name')
    lines.append(dict(duplicate))
    report=belgium.parse_belgium_lines(lines,controls)
    assert row(report,'journey.intended_arrival')['status']=='needs_verification'
    assert row(report,'journey.intended_arrival')['normalized_value'] is None
    assert row(report,'employment_or_education.name')['status']=='conflicting_labels'


def test_required_layout_labels_fail_closed_before_mapping(readings):
    lines,controls=readings
    lines=[line for line in lines if line['text']!='Visa application']
    report=belgium.parse_belgium_lines(lines,controls,'belgium.pdf')
    assert report['status']=='unsupported_template' and not report['filled_values']


@pytest.mark.parametrize('country',[None,'spain','france','germany','netherlands','italy','sweden','greece'])
def test_belgium_reader_never_runs_for_other_categories(country,monkeypatch):
    reader=Mock(side_effect=AssertionError('Belgium reader must not run'))
    monkeypatch.setattr(local_extraction,'extract_belgium_pdf',reader)
    data=extract_documents({'visa_form':[('belgium.pdf',portal_pdf())]},review_country=country)
    reader.assert_not_called()
    assert data.local_results[0]['status']=='unsupported_template'


def test_belgium_reader_does_not_reclassify_supporting_uploads(monkeypatch):
    reader=Mock(side_effect=AssertionError('Only the Belgium visa_form slot enables this reader'))
    monkeypatch.setattr(local_extraction,'extract_belgium_pdf',reader)
    extract_documents({'supporting':[('belgium.pdf',portal_pdf())]},review_country='belgium')
    reader.assert_not_called()


def test_belgium_bridge_and_cache_are_scoped_and_preserve_employer_evidence():
    raw=portal_pdf();files={'visa_form':[('form.pdf',raw)]};cache=DocumentCache()
    belgian=extract_documents(files,cache=cache,review_country='belgium')
    assert belgian.visa_form.applicant_name=='ANNA TESTER'
    assert belgian.visa_form.employer_name=='Example Works'
    assert belgian.visa_form.employer_address=='Company Road, 12, 12345, Cairo, EGYPT'
    assert belgian.visa_form.date_of_birth=='1993-08-17'
    assert any(source.field_name=='employer_address' and source.page==3 and source.local_source
               for source in belgian.evidence_locations)
    assert belgian.identity_evidence[0].page is None
    other=extract_documents(files,cache=cache,review_country='france')
    assert other.visa_form.applicant_name is None
    assert other.local_results[0]['status']=='unsupported_template'
    before=cache.hits
    extract_documents(files,cache=cache,review_country='belgium')
    assert cache.hits==before+1


def test_pipeline_passes_selected_country_to_extractor(monkeypatch,complete_extraction):
    reader=Mock(return_value=complete_extraction)
    monkeypatch.setattr(review_pipeline,'extract_documents',reader)
    review_pipeline.review_documents({},review_country='belgium')
    assert reader.call_args.kwargs['review_country']=='belgium'
