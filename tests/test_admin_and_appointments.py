from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock
import pytest

import accounts
from appointment_review import appointment_issues, ground_appointments
from extractor import AppointmentInfo, SourceField


def appointment(**values):
    return AppointmentInfo(source_file='appointment.pdf',appointment_date='2026-12-01',
                           appointment_time='10:00',text='Embassy appointment: 01/12/2026 at 10 AM',**values)


def test_requested_example_rejects_50_days_and_recommends_january_30(complete_extraction):
    data=complete_extraction
    data.appointments=[appointment()]
    data.visa_form.intended_arrival=data.flight.departure_date='2027-01-20'
    data.hotel=data.hotel[:1];data.hotel[0].check_in_date='2027-01-20'
    issues=appointment_issues(data)
    assert len(issues)==3
    assert all('2027-01-30' in item.expected_value and '50 days' in item.recommended_fix for item in issues)
    assert all(item.reference_evidence[0]['source_file']=='appointment.pdf' for item in issues)
    assert all('30/01/2027' in item.fix_ar for item in issues)


@pytest.mark.parametrize('gap,expected',[(0,True),(-1,True),(49,True),(50,True),(59,True),(60,False),(61,False),(120,False)])
def test_appointment_buffer_boundaries(complete_extraction,gap,expected):
    data=complete_extraction;data.appointments=[appointment()]
    value=(date(2026,12,1)+timedelta(days=gap)).isoformat()
    data.visa_form.intended_arrival=data.flight.departure_date=value
    for hotel in data.hotel:hotel.check_in_date=value
    assert bool(appointment_issues(data)) is expected


def test_no_appointment_is_optional_but_conflicting_letters_need_verification(complete_extraction):
    assert appointment_issues(complete_extraction)==[]
    complete_extraction.appointments=[appointment(),appointment().model_copy(update={'appointment_date':'2026-12-02'})]
    issues=appointment_issues(complete_extraction)
    assert len(issues)==1 and not issues[0].affects_score and issues[0].message_key=='appointment.unverified'


def test_every_hotel_checked_and_valid_starts_do_not_hide_early_hotel(complete_extraction):
    data=complete_extraction;data.appointments=[appointment()]
    data.visa_form.intended_arrival=data.flight.departure_date='2027-02-01'
    data.hotel[0].check_in_date='2027-02-01';data.hotel[1].check_in_date='2027-01-20'
    issues=appointment_issues(data)
    assert len(issues)==1 and issues[0].document_name=='Hotel Reservation (2)'


def test_invented_appointment_is_discarded_and_unreadable_letter_is_visible(complete_extraction):
    import pymupdf
    with pymupdf.open() as pdf:
        pdf.new_page().insert_text((50,60),'Embassy appointment: 01/12/2026 at 10 AM')
        raw=pdf.tobytes()
    files={'appointment':[('appointment.pdf',raw)]}
    data=complete_extraction;data.appointments=[appointment()]
    ground_appointments(data,files)
    assert data.appointments[0].appointment_date=='2026-12-01'
    data.appointments=[appointment().model_copy(update={'appointment_date':'2026-12-10'})]
    ground_appointments(data,files)
    assert data.appointments[0].appointment_date is None
    assert not appointment_issues(data)[0].affects_score
    data.appointments=[appointment().model_copy(update={'source_file':'invented.pdf'})]
    ground_appointments(data,files)
    assert len(data.appointments)==1 and data.appointments[0].appointment_date is None












def test_maintenance_rejects_reservation_before_quota_or_ai(monkeypatch):
    monkeypatch.setattr(accounts,'verified_actor',lambda *a,**k:accounts.Actor('id','a@example.com',True,'user'))
    monkeypatch.setattr(accounts,'service_controls',lambda:dict(maintenance_enabled=True,reviews_enabled=True))
    db=Mock();monkeypatch.setattr(accounts,'admin_client',lambda:db)
    with pytest.raises(accounts.AccountError,match='maintenance_message'):
        accounts.reserve_review(object(),object())
    db.rpc.assert_not_called()


@pytest.mark.parametrize('function,args',[(accounts.set_maintenance,(True,))])
def test_sensitive_admin_functions_recheck_super_role(monkeypatch,function,args):
    check=Mock(side_effect=accounts.AccountError('access_revoked'));monkeypatch.setattr(accounts,'verified_actor',check)
    db=Mock();monkeypatch.setattr(accounts,'admin_client',db)
    with pytest.raises(accounts.AccountError):function(object(),object(),*args)
    assert check.call_args.kwargs['require_super']
    db.assert_not_called()
