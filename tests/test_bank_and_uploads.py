"""Synthetic bank balances, booking policies and upload preferences."""
from io import BytesIO
from unittest.mock import Mock
import json
import pymupdf
import pytest
from PIL import Image
import accounts
from uploads import CATEGORIES, category_order, upload_thumbnail, files_hash, upload_slot_order, SPAIN_UPLOAD_SLOTS
from extractor import DocumentAudit
from finance_review import BankStatement, TripCost, grounded_financial_data, assess_budget, amount_in_quote
from document_sources import source_manifest, unique_uploads
from supporting_review import extraction_quality


def pdf(*pages):
    with pymupdf.open() as doc:
        for text in pages:
            page=doc.new_page();page.insert_text((50,70),text)
        return doc.tobytes()




def test_bank_audit_counts_only_in_scope_final_page(complete_extraction):
    raw=pdf('Earlier page','Closing balance EGP 120000.00')
    files={'bank_statement':[('bank.pdf',raw)]}
    assert source_manifest(files)['bank.pdf']['review_pages']==[2]
    d=complete_extraction;d.document_audits=[DocumentAudit(source_file='bank.pdf',pages_read=[2],readability='readable')]
    quality,issues=extraction_quality(d,files)
    assert (quality['pages_reported_read'],quality['pages_total'])==(1,1)
    assert quality['files'][0]['original_pages']==2 and not issues




def test_previous_page_balance_and_fabricated_amount_are_rejected(complete_extraction):
    d=complete_extraction;raw=pdf('Closing balance EGP 999999.00','Closing balance EGP 1000.00')
    files={'bank_statement':[('bank.pdf',raw)]}
    for page,balance,quote in [(1,999999,'Closing balance EGP 999999.00'),(2,999999,'Closing balance EGP 1000.00')]:
        d.bank_statements=[BankStatement(source_file='bank.pdf',page=page,balance=balance,quote=quote)]
        grounded_financial_data(d,files)
        assert not d.bank_statements


@pytest.mark.parametrize('amount,quote',[(120000.5,'EGP 120,000.50'),(120000.5,'EUR 120.000,50'),(1000,'EGP 1,000'),(-50.5,'EUR -50.50')])
def test_printed_amount_formats(amount,quote):
    assert amount_in_quote(amount,quote)
    assert not amount_in_quote(amount+1,quote)


def funded_case(d):
    d.bank_statements=[BankStatement(source_file='bank.pdf',page=3,holder_name=d.passport.full_name,
        owner_role='applicant',balance=100000,currency='EGP',balance_type='closing',quote='Closing EGP 100000.00')]
    d.trip_costs=[TripCost(category=kind,source_file=kind+'.pdf',page=1,amount=amount,currency='EUR',quote=f'Total EUR {amount}')
                  for kind,amount in [('hotel',500),('flight',400)]]
    d.hotel=d.hotel[:1]
    return d


def test_budget_uses_conversion_and_inclusive_travel_days(complete_extraction):
    d=funded_case(complete_extraction)
    rates={'rates':{'EUR':1,'EGP':50},'date':'2026-10-16'}
    result=assess_budget(d,75,rates)
    assert result['balances'][0]['eur']==2000
    assert result['allowance_eur']==result['days']*75
    assert result['known_budget_eur']==900+result['days']*75
    assert result['balances'][0]['status']=='covers_budget'


def test_missing_price_never_becomes_whole_trip_approval(complete_extraction):
    d=funded_case(complete_extraction);d.trip_costs=d.trip_costs[:1]
    result=assess_budget(d,rates={'rates':{'EUR':1,'EGP':50}})
    assert 'flight_price' in result['missing'] and result['balances'][0]['status']=='partial_budget'


def test_no_fx_or_other_owner_never_becomes_affordable(complete_extraction):
    d=funded_case(complete_extraction)
    assert assess_budget(d)['balances'][0]['status']=='conversion_unknown'
    d.bank_statements[0].owner_role='other'
    assert assess_budget(d,rates={'rates':{'EUR':1,'EGP':50}})['balances'][0]['status']=='ownership_unknown'


def test_low_balance_and_prepaid_costs(complete_extraction):
    d=funded_case(complete_extraction);d.bank_statements[0].balance=5
    result=assess_budget(d,rates={'rates':{'EUR':1,'EGP':50}})
    assert result['balances'][0]['status']=='below_budget'
    d.trip_costs[0].paid=True
    assert assess_budget(d,rates={'rates':{'EUR':1,'EGP':50}})['known_budget_eur']==result['known_budget_eur']-500


def test_reorder_preserves_ids_hash_and_bank_scope():
    raw=pdf('Final bank page balance 1000')
    files={'supporting':[('bank.pdf',raw)],'bank_statement':[('bank.pdf',raw)]}
    assert list(unique_uploads(files))==['bank_statement']
    assert unique_uploads(files)==unique_uploads(dict(reversed(list(files.items()))))
    assert files_hash(files,'auto')==files_hash(dict(reversed(list(files.items()))),'auto')
    assert category_order(list(reversed(CATEGORIES)))==list(reversed(CATEGORIES))
    assert set(category_order(['flight','flight','invalid']))==set(CATEGORIES)


@pytest.mark.parametrize('program,country',[('schengen','france'),('schengen','germany'),
    ('schengen','italy'),('schengen','netherlands'),('schengen','sweden'),('schengen','belgium'),
    ('schengen','greece'),('canada','spain'),('usa','spain'),('uk','spain')])
def test_spain_only_upload_slots_are_not_added_to_other_destinations(program,country):
    assert not set(SPAIN_UPLOAD_SLOTS).intersection(upload_slot_order(program=program,country=country))


def test_spain_slots_follow_the_application_without_changing_saved_shared_order():
    saved=list(reversed(CATEGORIES))
    slots=upload_slot_order(saved)
    index=slots.index('visa_form')+1
    assert slots[index:index+2]==list(SPAIN_UPLOAD_SLOTS)
    assert [slot for slot in slots if slot not in SPAIN_UPLOAD_SLOTS]==saved


def test_thumbnail_uses_final_bank_page_and_keeps_bounded_size():
    raw=pdf('Earlier page','Final balance')
    png,page,total=upload_thumbnail('statement.pdf',raw,'bank_statement')
    assert (page,total)==(2,2) and max(Image.open(BytesIO(png)).size)<=420


def test_order_mutation_rechecks_super_admin_and_rejects_bad_payload(monkeypatch):
    check=Mock(return_value=accounts.Actor('test','test@example.com',True,'super_admin'))
    db=Mock();monkeypatch.setattr(accounts,'verified_actor',check);monkeypatch.setattr(accounts,'admin_client',lambda:db)
    accounts.save_upload_category_order(Mock(),object(),list(reversed(CATEGORIES)))
    assert check.call_args.kwargs=={'require_super':True}
    db.rpc.assert_called_once()
    with pytest.raises(accounts.AccountError):accounts.save_upload_category_order(Mock(),object(),['flight'])


@pytest.mark.parametrize('lang',['en','ar'])
def test_pdf_omits_source_filenames_and_page_references(complete_extraction,lang):
    from validator import ValidationIssue,Severity
    from extractor import WritingRecommendation
    from scorer import calculate_score
    from pdf_report import build_pdf_report
    source='PRIVATE-AUDIT-SOURCE-ONLY.pdf'
    issue=ValidationIssue(document_name=f'Supporting Documents ({source})',field_name='translation_honorific',
        found_value='Ms. TEST',expected_value='Mr. TEST',severity=Severity.LOW,recommended_fix='Correct the honorific.',
        evidence=[{'source_file':source,'page':9,'text':'Ms. TEST'}])
    writing={'cover_letter':[WritingRecommendation(action='add',reason='Explain the trip purpose.',source_file=source,page=9)]}
    data=build_pdf_report(complete_extraction,[issue],calculate_score([issue]),lang=lang,writing=writing)
    with pymupdf.open(stream=data,filetype='pdf') as doc:
        text='\n'.join(page.get_text() for page in doc)
    assert source not in text and 'Source:' not in text


def test_missing_or_unknown_balance_type_does_not_pass_budget(complete_extraction):
    d=funded_case(complete_extraction);d.bank_statements[0].balance_type='unknown'
    result=assess_budget(d,rates={'rates':{'EUR':1,'EGP':50}})
    assert result['balances'][0]['status']!='covers_budget'


def test_held_hotels_do_not_lose_points_and_issued_tickets_take_precedence(complete_extraction):
    from source_checks import reservation_and_title_checks
    files={'hotel':[('hotel.pdf',pdf('BOOKING IS ON HOLD'))],
           'flight':[('flight.pdf',pdf('BOOKING ON HOLD','E-ticket number: 1234567890123'))]}
    assert not reservation_and_title_checks(complete_extraction,files)
    assert any(row.category=='hotel' and row.status=='held' for row in complete_extraction.booking_statuses)
    assert any(row.category=='flight' and row.status=='confirmed' for row in complete_extraction.booking_statuses)


def test_pipeline_does_not_read_bank_pages_for_writing_or_form_checks(complete_extraction,monkeypatch):
    import review_pipeline
    d=complete_extraction
    d.document_audits=[DocumentAudit(source_file='bank.pdf',document_types=['visa_form'],pages_read=[2],readability='readable')]
    parse_text=Mock()
    monkeypatch.setattr(review_pipeline,'extract_documents',lambda *a,**kw:d)
    monkeypatch.setattr(review_pipeline,'_extract_pdf_text',parse_text)
    monkeypatch.setattr(review_pipeline,'exchange_rates',lambda:None)
    review_pipeline.review_documents({'bank_statement':[('bank.pdf',pdf('Private earlier page','Final balance EUR 5000.00'))]})
    parse_text.assert_not_called()
