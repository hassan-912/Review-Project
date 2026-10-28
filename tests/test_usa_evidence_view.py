"""Bookings supply hotel/stay facts; correction cards open directly on evidence."""
import pytest
from streamlit.testing.v1 import AppTest

from i18n import t
from tests.test_usa_review import files,CLIENT,DS,HOTEL
from tests.test_usa_hotel_contact import packet
from usa_review import review_documents
from usa_ui import _native_evidence_image
from document_ingestion import normalize_uploads


def test_client_form_does_not_need_hotel_or_stay_dates():
    client='\n'.join(line for line in CLIENT.splitlines() if not line.startswith(('Arrival','Departure','Hotel')))
    result=review_documents(files(client=client))
    assert not result['incomplete']
    assert all(c['status']=='match' for c in result['usa_checks'])
    assert not any(c['field'] in ('arrival_date','departure_date','check_in_date','check_out_date','hotel_name') and
        'client_form' in (c['target_category'],c['reference_category']) for c in result['usa_checks'])


def test_hotel_and_stay_date_comparisons_use_booking_instead_of_client_data():
    client=CLIENT.replace('2027-05-10','2035-01-01').replace('2027-05-20','2035-02-01')+'Hotel Name: Another hotel\n'
    result=review_documents(files(client=client,ds=DS.replace('2027-05-10','2027-05-11'),
                                  hotel=HOTEL.replace('2027-05-20','2027-05-18')))
    checks=result['usa_checks']
    assert any(c['field']=='arrival_date' and c['status']=='mismatch' and c['reference_category']=='hotel' for c in checks)
    assert any(c['field']=='check_out_date' and c['status']=='mismatch' and c['target_category']=='hotel' for c in checks)
    assert not any(c['field'] in ('arrival_date','departure_date','hotel_name') and
        'client_form' in (c['target_category'],c['reference_category']) for c in checks)


@pytest.mark.parametrize('lang',['en','ar'])
def test_default_correction_view_has_source_images_not_value_cards(lang):
    result=review_documents(packet())
    ui=AppTest.from_string('import streamlit as st\nfrom usa_ui import render_usa_report\nrender_usa_report(st.session_state.report,st.session_state.lang)',default_timeout=30)
    ui.session_state.report=result;ui.session_state.lang=lang;ui.run()
    assert not ui.exception and ui.get('image')
    assert any(h.value==t('usa_evidence_title',lang) for h in ui.subheader)
    assert not any(h.value==t('usa_problem_title',lang) for h in ui.subheader)
    assert not any(panel.label==t('usa_source_details',lang) for panel in ui.expander)
    assert not ui.get('html')
    assert not any(c.value==t('usa_contact_hotel_workflow',lang) for c in ui.caption)
    cache=ui.session_state.report
    assert any('hotel.pdf' in key for key in cache['reference_images_v1'])
    assert any('ds160.pdf' in key for key in cache['correction_images_v3'])


def native_result():
    text='Full name as in passport | ANNA EXAMPLE\nPassword | PRIVATE_PASSWORD\n'
    sources,conversions=normalize_uploads({'client_form':[('client.txt',text.encode())]})
    location=dict(source_file='client.txt.pdf',native_section=1,text=text.splitlines()[0])
    return dict(source_files=sources,converted_sources=conversions),location


def test_converted_text_image_is_grounded_cached_and_has_no_other_sections():
    result,location=native_result()
    png=_native_evidence_image(location,result)
    assert png and png.startswith(b'\x89PNG')
    assert _native_evidence_image(location,result)==png
    assert len(result['usa_native_evidence_images_v1'])==1
    # A quote from a different section or fabricated text must not render.
    assert _native_evidence_image({**location,'native_section':2},result) is None
    assert _native_evidence_image({**location,'text':'Invented text'},result) is None
    assert _native_evidence_image({**location,'source_file':'missing.pdf'},result) is None
