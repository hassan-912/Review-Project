"""Red error markers must come from the actual upload and a reliable field location."""
from io import BytesIO

from PIL import Image
import pymupdf
import pytest
from streamlit.testing.v1 import AppTest

from evidence import render_error_region,_pdf_field_context
from extractor import VisaDocumentExtraction
from i18n import t
from scorer import calculate_score
from validator import ValidationIssue,Severity


def sample_pdf(*texts):
    with pymupdf.open() as document:
        for text in texts:
            page=document.new_page(width=600,height=400)
            page.insert_text((60,100),text,fontsize=16)
        return document.tobytes()


def red_pixels(raw):
    with Image.open(BytesIO(raw)) as image:
        pixels=memoryview(image.convert('RGB').tobytes())
        return sum(red>140 and red>green*2 and red>blue*2 for red,green,blue in zip(pixels[::3],pixels[1::3],pixels[2::3]))


def test_native_pdf_date_is_highlighted_and_original_bytes_are_unchanged():
    raw=sample_pdf('Departure: 21 Jun 2030')
    location=dict(source_file='flight.pdf',page=1,value='2030-06-21',text='Departure: 21 Jun 2030')
    png,page,method=render_error_region(location,{'flight':[('flight.pdf',raw)]})
    assert page==1 and method=='matched_region' and red_pixels(png)>100
    with pymupdf.open(stream=raw,filetype='pdf') as document:
        assert not list(document[0].annots() or [])
        assert not document[0].get_drawings()


def test_local_annotation_and_image_boxes_are_marked_with_context():
    with pymupdf.open() as document:
        page=document.new_page(width=600,height=400)
        page.add_freetext_annot(pymupdf.Rect(60,100,220,125),'X00001230',fontsize=16)
        raw=document.tobytes()
    location=dict(source_file='form.pdf',page=1,value='X00001230',text='X00001230',
                  box=[.1,.25,220/600,125/400],local_source=True)
    png,_,_=render_error_region(location,{'visa_form':[('form.pdf',raw)]})
    assert red_pixels(png)>100
    output=BytesIO();Image.new('RGB',(600,400),'white').save(output,format='PNG')
    location.update(source_file='passport.png')
    png,_,_=render_error_region(location,{'passport':[('passport.png',output.getvalue())]})
    assert red_pixels(png)>100
    assert Image.open(BytesIO(png)).width>160


def test_reference_field_is_marked_green_without_a_red_error_marker():
    with pymupdf.open() as document:
        page=document.new_page(width=600,height=400)
        page.insert_text((50,100),'Intended arrival: 20/11/2026',fontsize=16)
        raw=document.tobytes()
    location=dict(source_file='application.pdf',page=1,value='2026-11-20',text='20/11/2026',
                  field_name='intended_arrival',box=[.07,.18,.6,.28],local_source=True)
    png,_,_=render_error_region(location,{'visa_form':[('application.pdf',raw)]},kind='correct')
    with Image.open(BytesIO(png)) as image:
        green=sum(g>r+30 and g>b+15 for r,g,b in image.convert('RGB').get_flattened_data())
    assert green>100 and red_pixels(png)==0


def test_repeated_value_marks_only_its_locally_identified_field():
    with pymupdf.open() as document:
        page=document.new_page(width=600,height=400)
        page.insert_text((60,100),'21 Jun 2030',fontsize=16)
        page.insert_text((60,300),'21 Jun 2030',fontsize=16)
        raw=document.tobytes()
    location=dict(source_file='hotel.pdf',page=1,value='2030-06-21',
                  box=[.08,.65,.5,.8],local_source=True)
    png,_,_=render_error_region(location,{'hotel':[('hotel.pdf',raw)]})
    with Image.open(BytesIO(png)) as image:
        assert image.height<450  # Does not include both dates, 200 PDF points apart.
    assert red_pixels(png)>100


def test_screenshot_contains_the_whole_bordered_field_including_its_distant_label():
    with pymupdf.open() as document:
        page=document.new_page(width=600,height=400)
        page.draw_rect(pymupdf.Rect(35,55,565,160),color=(0,0,0))
        page.insert_text((45,85),'13. Number of travel document:',fontsize=13)
        page.insert_text((420,135),'X00001230',fontsize=16)
        context=_pdf_field_context(page,page.search_for('X00001230'))
        assert tuple(context)==(35,55,565,160)
        raw=document.tobytes()
    png,_,_=render_error_region(dict(source_file='form.pdf',page=1,value='X00001230'),
                               {'visa_form':[('form.pdf',raw)]})
    with Image.open(BytesIO(png)) as image:
        assert image.width>1250 and image.height>250
    assert red_pixels(png)>100


def test_borderless_field_keeps_the_full_row_width_and_label_above():
    with pymupdf.open() as document:
        page=document.new_page(width=600,height=400)
        page.insert_text((40,90),'Departure date',fontsize=16)
        page.insert_text((430,130),'21 Jun 2030',fontsize=16)
        context=_pdf_field_context(page,page.search_for('21 Jun 2030'))
        assert context.x0==0 and context.x1==600
        assert context.y0<70 and context.y1>130


@pytest.mark.parametrize('rotation',[90,180,270])
def test_red_marker_stays_on_the_value_when_the_pdf_page_is_rotated(rotation):
    with pymupdf.open() as document:
        page=document.new_page(width=600,height=400)
        page.insert_text((60,100),'Departure: 21 Jun 2030',fontsize=16)
        page.set_rotation(rotation)
        raw=document.tobytes()
    png,_,_=render_error_region(dict(source_file='flight.pdf',page=1,value='2030-06-21'),
                               {'flight':[('flight.pdf',raw)]})
    assert red_pixels(png)>100


@pytest.mark.parametrize('location',[
    dict(source_file='file.pdf',page=1,value='NOT ON PAGE',preview=True),
    dict(source_file='file.pdf',page=9,value='21 Jun 2030'),
    dict(source_file='file.pdf',page=1,box=[.8,.8,.1,.1],local_source=True),
    dict(source_file='file.pdf',page=1,box=[.1,.1,.3,.3]),
    dict(source_file='C:/secret.env',page=1,value='21 Jun 2030'),
])
def test_unknown_or_invalid_locations_never_get_an_invented_red_marker(location):
    assert render_error_region(location,{'flight':[('file.pdf',sample_pdf('21 Jun 2030'))]}) is None


def test_ambiguous_names_are_rejected_and_preview_search_reports_actual_page():
    raw=sample_pdf('Fictional flight introduction','Departure: 21 Jun 2030')
    location=dict(source_file='flight.pdf',page=1,value='2030-06-21',preview=True)
    assert render_error_region(location,{'flight':[('flight.pdf',raw),('flight.pdf',raw)]}) is None
    png,page,_=render_error_region(location,{'flight':[('flight.pdf',raw)]})
    assert page==2 and red_pixels(png)>100


@pytest.mark.parametrize('lang',['en','ar'])
@pytest.mark.parametrize('document,filename',[
    ('Visa Application Form','application.pdf'),('Hotel Reservation','hotel.pdf'),
    ('Flight Reservation','flight.pdf'),('Employment Documents','hr.pdf'),
])
def test_each_document_has_a_heading_filename_crop_and_no_processing_panels(lang,document,filename):
    from i18n import document_label
    data=VisaDocumentExtraction(review_provenance={'factual_engine':'local_python_ocr','external_ai_requests':0})
    issue=ValidationIssue(document_name=document,field_name='passport_number',found_value='X00001230',
        expected_value='X00001234',severity=Severity.CRITICAL,recommended_fix='Use the passport value.',
        check_origin='local_key_value',evidence=[dict(source_file=filename,page=1,text='X00001230')])
    result=dict(extraction=data,issues=[issue],score=calculate_score([issue]),writing={},
                source_files={'supporting':[(filename,sample_pdf('Passport number: X00001230'))]})
    ui=AppTest.from_string('''
import app,streamlit as st
app._init_session_state()
app.render_report(st.session_state.test_result)
''',default_timeout=30)
    ui.session_state.lang=lang;ui.session_state.test_result=result;ui.run()
    assert not ui.exception
    assert any(item.value==document_label(document,lang) for item in ui.subheader)
    assert len(ui.get('image'))==1
    assert any(filename in item.proto.body for item in ui.get('html'))
    assert not ui.warning and not ui.expander and not ui.caption
    assert len(ui.get('download_button'))==1
    # Provenance is preserved internally although the customer-facing panels are removed.
    assert result['extraction'].review_provenance['external_ai_requests']==0
