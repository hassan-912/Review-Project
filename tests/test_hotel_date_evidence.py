"""Stay dates, missing nights and cancellation deadlines have different meanings."""
import pymupdf
import pytest

from booking_template_extractor import extract_hotel_v1
from evidence import attach_evidence,render_error_region
from local_extraction import extract_local_documents
from validator import _check_date_alignment


def hotel_pdf():
    with pymupdf.open() as doc:
        page=doc.new_page(width=612,height=792)
        for x,y,text in [
            (108,60,'Stay in Madrid'),(108,90,'21 Nov 2026 - 23 Nov 2026'),
            (108,125,'Example Hotel'),(108,150,'Hotels.com itinerary: SYNTHETIC'),
            (108,180,'Reservation details'),(108,255,'Check in'),(309,255,'Check out'),
            (108,280,'Sat, 21 Nov'),(309,280,'Mon, 23 Nov'),
            (108,500,'Location'),(108,530,'12 Sample Street, Madrid, Spain'),
            (108,630,'Reserved for'),(108,650,'Anna Tester, 1 adult')]:
            page.insert_text((x,y),text,fontsize=10)
        doc.new_page().insert_text((50,80),'Free cancellation until 20 Nov 2026. Charges apply after check-in.')
        return doc.tobytes()


def test_november_20_arrival_corrects_the_actual_checkin_and_never_the_cancellation_date():
    raw=hotel_pdf()
    data=extract_local_documents({'hotel':[('hotel.pdf',raw)]})
    assert data.hotel[0].check_in_date=='2026-11-21'
    assert data.hotel[0].check_out_date=='2026-11-23'
    data.visa_form.intended_arrival='2026-11-20'
    data.visa_form.intended_departure='2026-11-23'
    issues=_check_date_alignment(data)
    assert len(issues)==1
    issue=issues[0]
    assert (issue.field_name,issue.found_value,issue.expected_value)==('check_in_date','2026-11-21','2026-11-20')
    attach_evidence(issues,data,{'hotel':[('hotel.pdf',raw)]})
    location=issue.evidence[0]
    assert location['page']==1 and location['text']=='Sat, 21 Nov'
    assert location['box'][1]>.3
    image=render_error_region(location,{'hotel':[('hotel.pdf',raw)]})
    assert image is not None and image[1]==1


def test_hotel_parser_prefers_the_labelled_field_over_the_shared_range():
    data=extract_hotel_v1(hotel_pdf())
    assert data['fields']['check_in_date']['sources'][0]['text']=='Sat, 21 Nov'
    assert data['fields']['check_out_date']['sources'][0]['text']=='Mon, 23 Nov'


@pytest.mark.parametrize('field',['check_in_date','check_out_date','departure_date',None])
def test_unlocated_date_cannot_be_highlighted_in_cancellation_terms(field):
    location=dict(source_file='hotel.pdf',page=1,field_name=field,value='2026-11-20',preview=True)
    assert render_error_region(location,{'hotel':[('hotel.pdf',hotel_pdf())]}) is None


def test_preview_search_requires_the_correct_date_label_and_skips_policy_pages():
    with pymupdf.open() as doc:
        doc.new_page().insert_text((50,80),'Free cancellation until 20 Nov 2026. Check-in rules apply.')
        doc.new_page().insert_text((50,80),'Check out: 20 Nov 2026')
        doc.new_page().insert_text((50,80),'Check in: 20 Nov 2026')
        raw=doc.tobytes()
    image=render_error_region(dict(source_file='hotel.pdf',page=1,field_name='check_in_date',
        value='2026-11-20',preview=True),{'hotel':[('hotel.pdf',raw)]})
    assert image is not None and image[1]==3


def test_internal_gaps_do_not_create_findings(complete_extraction):
    complete_extraction.hotel[1].check_in_date='2027-01-07'
    assert _check_date_alignment(complete_extraction)==[]


def test_old_computed_gap_values_cannot_generate_a_false_screenshot():
    assert render_error_region(dict(source_file='hotel.pdf',page=1,field_name='hotel_coverage_gap',
        value='2026-11-20',preview=True),{'hotel':[('hotel.pdf',hotel_pdf())]}) is None
