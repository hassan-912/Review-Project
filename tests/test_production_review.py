"""Regression cases use synthetic identities and documents only."""
from datetime import date
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock
import json
import pytest
import pymupdf
from PIL import Image
from extractor import (PassportInfo, NarrativeSection, TravelDay, SourceField, IdentityEvidence,
    SupportingDocument, SupportingClaim, DocumentAudit, _extract_pdf_text, _parse_response)
from validator import (_check_employment_leave_dates, _check_date_alignment, _names_match,
    name_issue, Severity, ValidationIssue)
from model_routing import generate_automatically, FREE_MODELS, ModelUnavailable
from evidence import attach_evidence, render_source
from supporting_review import check_supporting, extraction_quality
import accounts


def test_evidence_crop_includes_value_in_separate_table_column():
    doc=pymupdf.open()
    page=doc.new_page(width=600,height=300)
    page.insert_text((40,100),'Main destination')
    page.insert_text((430,100),'Greece')
    raw=doc.tobytes()
    png,number,method=render_source(
        {'source_file':'form.pdf','page':1,'text':'Main destination Greece'},
        {'visa_form':[('form.pdf',raw)]})
    assert number==1 and method=='matched_region'
    assert Image.open(BytesIO(png)).width>900


def pdf_bytes(*pages):
    with pymupdf.open() as pdf:
        for text in pages:
            page=pdf.new_page()
            if text: page.insert_text((70,90),text)
        return pdf.tobytes()


@pytest.mark.parametrize('start',['2026-11-25','2026-11-26'])
@pytest.mark.parametrize('end',['2026-11-28','2026-11-29'])
def test_hr_exact_inward_allowance(complete_extraction,start,end):
    d=complete_extraction
    d.employment.approved_leave_start='2026-11-25';d.employment.approved_leave_end='2026-11-29'
    d.visa_form.intended_arrival=d.flight.departure_date=start
    d.visa_form.intended_departure=d.flight.return_date=end
    d.hotel=d.hotel[:1];d.hotel[0].check_in_date=start;d.hotel[0].check_out_date=end
    assert not _check_employment_leave_dates(d)


@pytest.mark.parametrize('start,end',[('2026-11-24','2026-11-29'),('2026-11-25','2026-11-30'),('2026-11-27','2026-11-29'),('2026-11-25','2026-11-27')])
def test_hr_outward_dates_and_large_inward_gaps_fail(complete_extraction,start,end):
    d=complete_extraction
    d.employment.approved_leave_start='2026-11-25';d.employment.approved_leave_end='2026-11-29'
    d.visa_form.intended_arrival=start;d.visa_form.intended_departure=end
    issues=_check_employment_leave_dates(d)
    assert any(i.document_name=='Visa Application Form' and i.message_key=='hr.window' for i in issues)


def test_travel_documents_have_no_one_day_or_three_day_tolerance(complete_extraction):
    d=complete_extraction; d.flight.departure_date='2027-01-02'
    assert any(i.document_name=='Flight Reservation' and i.expected_value=='2027-01-01' for i in _check_date_alignment(d))


@pytest.mark.parametrize('other',['ANNA MARIA VAN DER BERG','ANNA VAN DER BERG','VAN DER BERG, ANNA'])
def test_full_or_first_with_complete_compound_surname(other):
    assert _names_match('ANNA MARIA VAN DER BERG',other,'ANNA MARIA','VAN DER BERG')


@pytest.mark.parametrize('other',['ANNA MARIA','ANNA BERG','MARIA VAN DER BERG'])
def test_other_partial_names_are_format_notes(other):
    p=PassportInfo(full_name='ANNA MARIA VAN DER BERG',given_names='ANNA MARIA',surname='VAN DER BERG')
    issue=name_issue(p,other,'Hotel')
    assert issue.message_key=='identity.name_format' and issue.severity==Severity.LOW


@pytest.mark.parametrize('other',[None,'','   ','ANNA VAN DER BORG','A VAN DER BERG'])
def test_blank_or_misspelt_names_are_critical(other):
    p=PassportInfo(full_name='ANNA MARIA VAN DER BERG',given_names='ANNA MARIA',surname='VAN DER BERG')
    assert name_issue(p,other,'Flight').severity==Severity.CRITICAL
    assert not _names_match(' ',other)


def test_plan_day_coverage_uses_application_not_flight(complete_extraction):
    d=complete_extraction;d.flight.departure_date='2027-01-02'
    d.travel_plan=NarrativeSection(present=True,start_date='2027-01-02',end_date='2027-01-10',
        days=[TravelDay(date=f'2027-01-{i:02d}',city='Paris',activities=['Museum']) for i in range(2,11)])
    assert any(i.field_name=='travel_plan_coverage' for i in _check_date_alignment(d))


def test_mixed_scanned_pdf_goes_to_vision_and_text_pages_keep_page_numbers():
    text='FICTIONAL applicant: ANNA MARIA ERIKSSON. Passport: TEST12345.'
    assert _extract_pdf_text('mixed.pdf',pdf_bytes(text,'')) is None
    extracted=_extract_pdf_text('text.pdf',pdf_bytes(text,text))
    assert '[Page 1]' in extracted and '[Page 2]' in extracted


def test_supporting_passport_conflict_is_grounded_in_original(complete_extraction):
    d=complete_extraction; raw=pdf_bytes('Passport number TEST99999. This is a fictional test.')
    d.supporting_documents=[SupportingDocument(source_file='support.pdf',document_type='Employment',summary='Test',
        claims=[SupportingClaim(field_name='passport_number',value='TEST99999',quote='Passport number TEST99999.',page=1)])]
    assert check_supporting(d,{'supporting':[('support.pdf',raw)]})[0].severity==Severity.CRITICAL
    assert d.supporting_documents[0].claims[0].assessment=='conflicts'
    d.supporting_documents[0].claims[0].quote='Invented quotation'
    issues=check_supporting(d,{'supporting':[('support.pdf',raw)]})
    assert issues[0].severity==Severity.CRITICAL
    assert d.supporting_documents[0].claims[0].quote=='Passport number TEST99999. This is a fictional test.'
    d.supporting_documents[0].claims[0].quote='Invented quotation'
    d.supporting_documents[0].claims[0].value='TEST_NOT_ON_PAGE'
    issues=check_supporting(d,{'supporting':[('support.pdf',raw)]})
    assert issues[0].message_key=='evidence.incomplete'
    assert d.supporting_documents[0].claims[0].assessment=='unverified'


def test_unread_and_unclassified_supporting_file_is_never_clean(complete_extraction):
    quality,issues=extraction_quality(complete_extraction,{'supporting':[('evidence.pdf',pdf_bytes('Fictional supporting evidence document.'))]})
    assert quality['pages_reported_read']==0 and quality['pages_total']==1
    assert len(issues)==2 and all(i.severity==Severity.HIGH for i in issues)


def test_source_images_use_real_bytes_and_unambiguous_filenames(complete_extraction):
    d=complete_extraction
    d.identity_evidence=[IdentityEvidence(document='flight',source_file='booking.pdf',page=2,full_name='ANNA ERIKSON')]
    issue=ValidationIssue(document_name='Flight Reservation',field_name='full_name',found_value='ANNA ERIKSON',
        expected_value=d.passport.full_name,severity=Severity.CRITICAL,recommended_fix='Correct the spelling')
    raw=pdf_bytes('Fictional booking introductory page.','Guest name: ANNA ERIKSON')
    files={'flight':[('booking.pdf',raw)]}
    attach_evidence([issue],d,files)
    rendered,page,method=render_source(issue.evidence[0],files)
    assert rendered.startswith(b'\x89PNG') and page==2 and method=='matched_region'
    assert render_source(issue.evidence[0],{'flight':[('booking.pdf',raw),('booking.pdf',raw)]}) is None
    assert render_source({'source_file':'C:/secret.env','page':1},files) is None


def test_bad_image_box_falls_back_to_actual_page():
    output=BytesIO();Image.new('RGB',(100,100),'white').save(output,'PNG')
    png,page,method=render_source({'source_file':'scan.png','page':1,'box':[.8,.8,.1,.1]}, {'flight':[('scan.png',output.getvalue())]})
    assert method=='page_preview' and Image.open(BytesIO(png)).size==(100,100)


def test_national_id_uses_own_reference_and_insurance_label_does_not_select_passport(complete_extraction):
    d=complete_extraction
    d.document_audits=[DocumentAudit(source_file='id.pdf',document_types=['national_id'],pages_read=[1],readability='readable')]
    issue=ValidationIssue(document_name='Visa Application Form',field_name='national_id_issue',found_value='2022-02-03',
        expected_value='2022-02-02',severity=Severity.CRITICAL,recommended_fix='Use ID reference')
    files={'supporting':[('id.pdf',pdf_bytes('Fictional National ID. Issued 2022-02-02'))]}
    attach_evidence([issue],d,files)
    assert issue.reference_evidence[0]['source_file']=='id.pdf'
    from evidence import _category
    assert _category('Travel Insurance (Insured Passport No.)')=='insurance'


def test_arabic_pdf_keeps_labels_and_iso_dates(complete_extraction):
    from pdf_report import build_pdf_report
    from scorer import calculate_score
    from i18n import t
    raw=build_pdf_report(complete_extraction,[],calculate_score([]),lang='ar')
    with pymupdf.open(stream=raw,filetype='pdf') as pdf:
        text=''.join(p.get_text() for p in pdf)
    assert '2027-01-01' in text and '2027-01-10' in text
    # HarfBuzz encodes visual RTL runs; accept either logical or visual text extraction.
    for key in ('field_passport_number','country','field_departure_date'):
        label=t(key,'ar')
        assert label in text or label[::-1] in text


def test_automatic_routing_skips_quota_retries_and_validates_json():
    client=Mock()
    client.models.generate_content.side_effect=[RuntimeError('429 RESOURCE_EXHAUSTED'),SimpleNamespace(text='not json'),SimpleNamespace(text='{}')]
    used=[]
    assert generate_automatically(client,[],object(),validate=_parse_response,model_callback=used.append)=='{}'
    assert used==[FREE_MODELS[2]]
    assert [call.kwargs['model'] for call in client.models.generate_content.call_args_list]==list(FREE_MODELS[:3])


def test_no_quota_means_no_generation_and_no_paid_fallback():
    client=Mock();client.models.count_tokens.return_value.total_tokens=25
    router=Mock();router.models=list(FREE_MODELS);router.reserve.return_value=None
    with pytest.raises(ModelUnavailable):
        generate_automatically(client,[],SimpleNamespace(system_instruction='Extract'),router=router)
    client.models.generate_content.assert_not_called()
    assert router.reserve.call_count==4


@pytest.mark.parametrize('function,args',[(accounts.super_update,('00000000-0000-0000-0000-000000000001','super_admin',True,5,20)),
    (accounts.configure_model,(FREE_MODELS[0],True,1,5,250000,20)),(accounts.set_reviews_enabled,(False,)),(accounts.model_dashboard,())])
def test_super_admin_operations_require_live_authorization(monkeypatch,function,args):
    verified=Mock(side_effect=accounts.AccountError('access_revoked'));monkeypatch.setattr(accounts,'verified_actor',verified)
    database=Mock();monkeypatch.setattr(accounts,'admin_client',database)
    with pytest.raises(accounts.AccountError):function(object(),object(),*args)
    assert verified.call_args.kwargs['require_super'] is True
    database.assert_not_called()


def test_nullable_new_extraction_lists_do_not_break_parsing():
    data=_parse_response(json.dumps({'document_audits':[{'source_file':'a.pdf','pages_read':None,'uncertainties':None}],
        'supporting_documents':[{'source_file':'a.pdf','document_type':'Other','summary':'Test','claims':None}]}))
    assert data.document_audits[0].pages_read==[] and data.supporting_documents[0].claims==[]
