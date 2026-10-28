from copy import deepcopy
from types import SimpleNamespace
import json
import pymupdf
import pytest
from extractor import VisaDocumentExtraction,SourceField
from finance_review import TripCost,extract_booking_costs
from narrative_reviewer.packet import build_packet
from narrative_reviewer.contracts import BankAssessment,BudgetProposal
from narrative_reviewer.grounding import validate_review


def pdf(text):
    with pymupdf.open() as doc:
        doc.new_page().insert_textbox(pymupdf.Rect(35,35,560,800),text,fontsize=10)
        return doc.tobytes()


@pytest.fixture
def case():
    text='Holder: MG TEST APPLICANT\nCurrency EGP\nStatement period 2026-01-01 to 2026-06-30\n2026-06-01 Credit EGP 500001\nClosing balance EGP 100000\nTotal credits EGP 1000000'
    data=VisaDocumentExtraction(passport={'full_name':'MG TEST APPLICANT'},
        evidence_locations=[SourceField(document='passport',source_file='passport.pdf',page=1,field_name='full_name',
            value='MG TEST APPLICANT',text='MG TEST APPLICANT',local_source=True)],
        local_results=[dict(category='employment',source_file='hr.pdf',fields={
            'net_salary':dict(status='extracted',normalized_value='20000',page=1),
            'salary_currency':dict(status='extracted',normalized_value='EGP',page=1)})],
        local_hr=dict(fields={'net_salary':dict(status='extracted',normalized_value='20000',sources=[dict(source_file='hr.pdf',page=1)]),
            'salary_currency':dict(status='extracted')},values={'net_salary':'20000','salary_currency':'EGP'}))
    packet=build_packet({'passport':[('passport.pdf',b'not opened passport')],'employment':[('hr.pdf',b'not opened HR')],
                         'bank_statement':[('bank.pdf',pdf(text))]},data,ocr=False,
                        rates={'rates':{'EUR':1,'EGP':50},'date':'2026-10-27'})
    bank_doc=packet['documents'][-1]
    source=dict(document_id=bank_doc['id'],page=1,quote=bank_doc['pages'][0]['text'])
    bank=dict(document_id=bank_doc['id'],currency='EGP',period_start='2026-01-01',period_end='2026-06-30',period_source=source,
        holder_name='MG TEST APPLICANT',owner_role='applicant',income_basis='employment',business_sources=[],
        total_credits=1000000,total_debits=500000,transaction_coverage='complete',closing_balance=100000,balance_source=source,
        salary_months=[dict(month=f'2026-{m:02d}',complete_month=True,status='not_found',citations=[]) for m in range(1,7)],
        large_credit_days=[dict(date='2026-06-01',amount=500001,citations=[source])])
    return SimpleNamespace(packet=packet,bank=bank,data=data,source=source)


def review(case,**kwargs):
    value=dict(version=case.packet['version'],request_id=case.packet['request_id'],status='complete',findings=[],
        coverage=[dict(document_id=d['id'],page=p['number'],status='reviewed') for d in case.packet['documents'] for p in d['pages']],
        limitations=[],bank_assessments=[case.bank])
    value.update(kwargs);return validate_review(case.packet,value)


def test_salary_absence_lists_only_completely_read_months_and_keeps_gross_net_basis(case):
    result=review(case)
    flag=next(f for f in result['bank_flags'] if f['code']=='bank_salary_missing')
    assert flag['amount']==20000 and flag['currency']=='EGP' and flag['basis']=='net'
    assert flag['months']==[f'2026-{m:02d}' for m in range(1,7)]


def test_absolute_500k_flag_does_not_require_60_percent(case):
    flag=next(f for f in review(case)['bank_flags'] if f['code']=='bank_large_credit')
    assert flag['absolute_threshold'] and not flag['share_threshold'] and flag['share']==pytest.approx(.500001)


def test_share_rule_is_more_than_60_percent_of_total_not_median(case):
    case.bank['total_credits']=700000
    flag=next(f for f in review(case)['bank_flags'] if f['code']=='bank_large_credit')
    assert flag['share_threshold'] and flag['share']==pytest.approx(500001/700000)
    case.bank['currency']='USD';case.bank['total_credits']=500001/.6
    case.packet['documents'][-1]['pages'][0]['text']=case.packet['documents'][-1]['pages'][0]['text'].replace('EGP','USD')
    case.source['quote']=case.source['quote'].replace('EGP','USD')
    from narrative_reviewer.contracts import packet_digest
    case.packet['request_id']=packet_digest(case.packet)
    assert not any(f['code']=='bank_large_credit' for f in review(case)['bank_flags'])


def test_partial_statement_never_establishes_missing_salary_or_share_threshold(case):
    case.bank['transaction_coverage']='partial'
    result=review(case)
    assert not any(f['code']=='bank_salary_missing' for f in result['bank_flags'])
    assert all(f.get('share') is None for f in result['bank_flags'] if f['code']=='bank_large_credit')


def test_no_hr_never_demands_monthly_payroll_even_with_business_income(case):
    case.packet['financial_context']['salary']=None;case.packet['financial_context']['hr_present']=False
    from narrative_reviewer.contracts import packet_digest
    case.packet['request_id']=packet_digest(case.packet)
    case.bank['income_basis']='business'
    assert not any(f['code'].startswith('bank_salary') for f in review(case)['bank_flags'])


def test_wrong_account_owner_never_establishes_salary_absence_or_spendable_funds(case):
    case.bank['holder_name']='ANOTHER PERSON'
    result=review(case)
    assert result['bank_assessments'][0]['owner_role']=='unknown'
    assert not any(f['code']=='bank_salary_missing' for f in result['bank_flags'])


def test_bank_statement_all_pages_are_in_scope():
    with pymupdf.open() as doc:
        for text in ('January credits and debits EGP 20000 on the first page.','Closing balance EGP 100000 on the last page.'):
            doc.new_page().insert_textbox(pymupdf.Rect(35,35,560,800),text)
        packet=build_packet({'bank_statement':[('bank.pdf',doc.tobytes())]},ocr=False)
    assert len(packet['documents'][0]['pages'])==2
    assert 'January credits' in json.dumps(packet)


def test_booking_price_extraction_requires_explicit_currency_and_unambiguous_total():
    data=VisaDocumentExtraction()
    extract_booking_costs(data,{'hotel':[('hotel.pdf',pdf('Total price EUR 500.00'))],
                               'flight':[('flight.pdf',pdf('Total amount 400.00 EUR'))]})
    assert sorted((c.category,c.amount,c.currency) for c in data.trip_costs)==[('flight',400,'EUR'),('hotel',500,'EUR')]
    other=VisaDocumentExtraction()
    extract_booking_costs(other,{'hotel':[('hotel.pdf',pdf('Total 4 nights\nTotal EUR 100\nTotal EUR 200'))]})
    assert not other.trip_costs


def add_doc(case,category,name,text,mode='full_text'):
    from hashlib import sha256
    doc=dict(id=f"d{len(case.packet['documents'])+1}",filename=name,categories=[category],sha256=sha256(text.encode()).hexdigest(),
        total_pages=1,pages=[dict(number=1,text=text,method='pdf_text',provisional=False)],context_mode=mode)
    case.packet['documents'].append(doc)
    return dict(document_id=doc['id'],page=1,quote=text)


def test_budget_adds_quotes_and_city_costs_once_and_uses_latest_owned_balance(case):
    from narrative_reviewer.contracts import packet_digest
    plan=add_doc(case,'travel_plan','plan.pdf','Paris tourism 2027-01-01 to 2027-01-02.')
    hotel=add_doc(case,'hotel','hotel.pdf','Total price EUR 500.')
    flight=add_doc(case,'flight','flight.pdf','Total price EUR 400.')
    context=case.packet['financial_context'];context.update(trip_start='2027-01-01',trip_end='2027-01-02',expected_hotels=1,
        reservation_costs=[dict(category='hotel',amount=500,currency='EUR',paid=False,source=hotel),
                           dict(category='flight',amount=400,currency='EUR',paid=False,source=flight)])
    case.packet['request_id']=packet_digest(case.packet)
    proposal=dict(cities=[dict(city='Paris',days=2,daily_low_eur=50,daily_high_eur=75,source=plan)],
        intercity_low_eur=20,intercity_high_eur=30,assumptions='Planning estimates, not live prices.')
    budget=review(case,budget_proposal=proposal)['trip_budget']
    assert budget['status']=='estimate' and budget['total_low_eur']==1020 and budget['total_high_eur']==1080
    assert budget['balance_checks'][0]['balance_eur']==2000
    assert budget['balance_checks'][0]['status']=='covers_estimated_range'
    context['reservation_costs']=context['reservation_costs'][:1];case.packet['request_id']=packet_digest(case.packet)
    budget=review(case,budget_proposal=proposal)['trip_budget']
    assert 'flight_price' in budget['missing'] and budget['balance_checks'][0]['status']=='partial_estimate'


def test_bank_cannot_invent_a_large_amount_in_real_source_quotes(case):
    case.bank['large_credit_days'][0]['amount']=900000
    result=review(case)
    assert not any(f['code']=='bank_large_credit' for f in result['bank_flags'])
    assert result['status']=='incomplete'


def test_identified_contiguous_monthly_statements_share_one_six_month_denominator(case):
    from narrative_reviewer.contracts import packet_digest
    account='EG120000000000000000000000000'
    first_text=f'Holder: MG TEST APPLICANT\nSynthetic Bank Account {account}\nEGP statement period 2026-01-01 to 2026-03-31\n2026-03-01 Credit EGP 100000\nClosing balance EGP 100000'
    case.packet['documents'][-1]['pages'][0]['text']=first_text
    case.source['quote']=first_text
    case.bank.update(period_end='2026-03-31',account_id=account,account_source=case.source,bank_name='Synthetic Bank',total_credits=100000,
        large_credit_days=[dict(date='2026-03-01',amount=100000,citations=[case.source])])
    second_source=add_doc(case,'bank_statement','bank-april-june.pdf',
        f'Holder: MG TEST APPLICANT\nSynthetic Bank Account {account}\nEGP statement period 2026-04-01 to 2026-06-30\n2026-06-01 Credit EGP 400001\nClosing balance EGP 100000')
    second=deepcopy(case.bank)
    second.update(document_id=second_source['document_id'],period_start='2026-04-01',period_end='2026-06-30',
        period_source=second_source,account_source=second_source,balance_source=second_source,total_credits=500001,
        large_credit_days=[dict(date='2026-06-01',amount=400001,citations=[second_source])])
    case.packet['request_id']=packet_digest(case.packet)
    result=review(case,bank_assessments=[case.bank,second])
    assert not any(f['code']=='bank_short_window' for f in result['bank_flags'])
    flag=next(f for f in result['bank_flags'] if f['code']=='bank_large_credit')
    assert flag['amount']==400001 and flag['total_credits']==600001
    assert flag['share_threshold'] and not flag['absolute_threshold']


@pytest.mark.parametrize('lang',['en','ar'])
def test_structured_bank_problem_messages_render_in_both_languages(case,lang):
    from streamlit.testing.v1 import AppTest
    ui=AppTest.from_string("""
import streamlit as st
from narrative_reviewer.financial_ui import render_financial
render_financial(st.session_state.review,st.session_state.packet,st.session_state.lang)
""")
    ui.session_state.review=review(case);ui.session_state.packet=case.packet;ui.session_state.lang=lang
    ui.run()
    assert not ui.exception
    values=' '.join(item.value for item in ui.text)
    assert '20,000.00' in values and '500,001.00' in values


def test_local_explicit_credits_prevent_a_false_missing_salary_warning(case):
    from narrative_reviewer.contracts import packet_digest
    lines=['Holder: MG TEST APPLICANT','EGP statement period 2026-01-01 to 2026-06-30']
    lines.extend(f'2026-{m:02d}-02 Credit EGP 20000' for m in range(1,7))
    lines.append('Closing balance EGP 100000')
    text='\n'.join(lines)
    case.packet['documents'][-1]['pages'][0]['text']=text;case.source['quote']=text
    case.bank['large_credit_days']=[];case.bank['total_credits']=120000
    case.packet['request_id']=packet_digest(case.packet)
    result=review(case)
    assert not any(f['code'].startswith('bank_salary') for f in result['bank_flags'])
    assert all(m['status']=='matched' for m in result['bank_assessments'][0]['salary_months'])


def test_untraceable_claimed_salary_match_requires_verification(case):
    month=case.bank['salary_months'][0]
    month.update(status='matched',matched_amount=20000,credited_date='2026-01-02',citations=[case.source])
    result=review(case)
    assert result['bank_assessments'][0]['salary_months'][0]['status']=='uncertain'
    assert any(f['code']=='bank_salary_uncertain' for f in result['bank_flags'])
    assert result['status']=='incomplete'


def test_arabic_money_and_unambiguous_currency_are_supported():
    from finance_review import amount_in_quote
    from narrative_reviewer.assessments import _currency_present
    assert amount_in_quote(20000,'صافي الراتب ٢٠٬٠٠٠٫٠٠ جنيه مصري')
    assert _currency_present('EGP','العملة جنيه مصري')
    assert not _currency_present('EGP','جنيه إسترليني')
    assert not _currency_present('USD','CAD $ 20000')
