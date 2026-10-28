from datetime import date
from unittest.mock import Mock
from types import SimpleNamespace
import pytest
from extractor import VisaDocumentExtraction, HotelInfo, _is_passport_category
from validator import run_validation, Severity, _check_date_alignment, _check_identity_name_crosscheck, _check_passport_expiry, _check_missing_fields
from scorer import calculate_score
from business_checker import check_business_alignment
from uploads import files_hash, validate_uploads
from i18n import ISSUE_AR, issue_text
from pdf_report import build_pdf_report
from review_pipeline import review_documents


def test_complete_multi_hotel_file_has_no_findings(complete_extraction):
    assert run_validation(complete_extraction)==[]
    assert calculate_score([],True,True).score==100


def test_legacy_single_hotel_is_migrated():
    data=VisaDocumentExtraction.model_validate({"hotel":{"hotel_name":"A","check_in_date":"2027-01-01"}})
    assert len(data.hotel)==1 and data.hotel[0].hotel_name=="A"


@pytest.mark.parametrize("value",[None,{},[]])
def test_missing_hotels_are_an_empty_list(value):
    assert VisaDocumentExtraction.model_validate({"hotel":value}).hotel==[]


def test_internal_hotel_gap_is_not_a_review_rule(complete_extraction):
    complete_extraction.hotel[1].check_in_date="2027-01-07"
    gaps=[i for i in run_validation(complete_extraction) if i.field_name=="hotel_coverage_gap"]
    assert gaps==[]
    assert not _check_date_alignment(complete_extraction)


def test_overlapping_hotel_bookings_cover_trip(complete_extraction):
    complete_extraction.hotel[1].check_in_date="2027-01-05"
    assert not _check_date_alignment(complete_extraction)


def test_late_first_hotel_leaves_gap(complete_extraction):
    complete_extraction.hotel[0].check_in_date="2027-01-02"
    issues=_check_date_alignment(complete_extraction)
    checkin=[issue for issue in issues if issue.field_name=='check_in_date']
    assert len(checkin)==1 and checkin[0].found_value=='2027-01-02' and checkin[0].expected_value=='2027-01-01'
    assert not any(issue.field_name=='hotel_coverage_gap' for issue in issues)


def test_short_last_hotel_leaves_gap(complete_extraction):
    complete_extraction.hotel[-1].check_out_date="2027-01-09"
    issues=_check_date_alignment(complete_extraction)
    checkout=[issue for issue in issues if issue.field_name=='check_out_date']
    assert len(checkout)==1 and checkout[0].found_value=='2027-01-09' and checkout[0].expected_value=='2027-01-10'
    assert not any(issue.field_name=='hotel_coverage_gap' for issue in issues)


def test_each_hotel_guest_is_checked(complete_extraction):
    complete_extraction.hotel[1].guest_name="SOMEONE ELSE"
    issues=_check_identity_name_crosscheck(complete_extraction)
    assert len(issues)==1 and issues[0].document_name=="Hotel Reservation (2)"


def test_each_hotel_requires_dates(complete_extraction):
    complete_extraction.hotel[1].check_in_date=None
    assert any(i.field_name=="check_in_date" for i in _check_missing_fields(complete_extraction))


def test_per_stay_hotel_order_is_not_a_separate_review_rule(complete_extraction):
    complete_extraction.hotel[1].check_out_date="2027-01-04"
    assert not any(i.field_name=="hotel_date_order" for i in _check_date_alignment(complete_extraction))


@pytest.mark.parametrize("returned",["2027-01-31","2027-03-31","2027-08-31","2027-11-30"])
def test_passport_expiry_does_not_crash_at_month_end(complete_extraction,returned):
    complete_extraction.flight.return_date=returned
    _check_passport_expiry(complete_extraction)


@pytest.mark.parametrize("field",["passport_number","date_of_birth","applicant_name"])
def test_identity_mismatches_keep_severity(complete_extraction,field):
    setattr(complete_extraction.visa_form,field,"WRONG")
    assert any(i.field_name==field and i.severity==(Severity.HIGH if field=="date_of_birth" else Severity.CRITICAL) for i in run_validation(complete_extraction))


def test_critical_findings_gate_readiness_and_disable_bonuses(complete_extraction):
    complete_extraction.visa_form.passport_number="WRONG"
    issue=run_validation(complete_extraction)[0]
    assert calculate_score([issue]).score==64
    assert calculate_score([issue]*3).score==0
    result=calculate_score([issue],True,True)
    assert result.score==64 and result.readiness=='not_ready' and not result.bonus_detail


def test_every_finding_has_bilingual_messages():
    for issue in run_validation(VisaDocumentExtraction()):
        assert issue.message_key in ISSUE_AR
        assert issue.title_en and issue.title_ar and issue.fix_ar
        assert issue_text(issue,"ar")[1]==issue.fix_ar


def test_passport_routing_is_category_based():
    assert _is_passport_category("passport")
    assert not _is_passport_category("🛂 Passport")
    assert not _is_passport_category("passport_translation")


def test_cache_changes_with_model_language_and_content():
    files={"passport":[("a.pdf",b"1")],"hotel":[("b.pdf",b"2")]}
    baseline=files_hash(files,"model","en")
    assert baseline==files_hash(dict(reversed(list(files.items()))),"model","en")
    assert baseline!=files_hash(files,"other","en")
    assert baseline!=files_hash(files,"model","ar")
    files["hotel"][0]=("b.pdf",b"3")
    assert baseline!=files_hash(files,"model","en")


@pytest.mark.parametrize("files",[{}, {"unknown":[("a.pdf",b"%PDF-foo")]}, {"passport":[("a.pdf",b"executable")]}, {"passport":[("a.exe",b"xx")]}, {"passport":[("a.png",b"%PDF-not-image")]}])
def test_invalid_uploads_are_rejected(files):
    with pytest.raises(ValueError):validate_uploads(files)










def test_pipeline_in_both_languages(monkeypatch,complete_extraction):
    import review_pipeline
    mocked=Mock(return_value=complete_extraction)
    monkeypatch.setattr(review_pipeline,'extract_documents',mocked)
    for lang in ('en','ar'):
        steps=[]
        result=review_documents({'passport':[]},lang=lang,progress=steps.append)
        assert steps==[1,2,3,4,5] and result['score'].score==100
        assert mocked.call_args.args[0]=={}


@pytest.mark.parametrize('lang',['en','ar'])
def test_pdf_has_unicode_client_name(complete_extraction,lang):
    import pymupdf
    complete_extraction.visa_form.passport_number="WRONG"
    issues=run_validation(complete_extraction)
    pdf=build_pdf_report(complete_extraction,issues,calculate_score(issues),lang=lang,client_name="أحمد محمد")
    assert pdf.startswith(b'%PDF-')
    with pymupdf.open(stream=pdf,filetype='pdf') as document:
        extracted=''.join(page.get_text() for page in document)
        assert 'TEST12345' in extracted
        assert any('\u0600'<=char<='\u06ff' for char in extracted)
