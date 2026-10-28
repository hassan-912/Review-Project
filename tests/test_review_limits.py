"""Saved allowances, rolling windows and the two independent admin controls."""
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from streamlit.testing.v1 import AppTest

import accounts
from i18n import t


def limit_database(monkeypatch,stamps):
    database=Mock()
    database.table.return_value.select.return_value.eq.return_value.gt.return_value.order.return_value.limit.return_value.execute.return_value.data=[
        {'requested_at':stamp.isoformat()} for stamp in stamps]
    monkeypatch.setattr(accounts,'admin_client',lambda:database)
    return database


def test_regular_user_daily_limit_cannot_exceed_five(monkeypatch):
    profile=dict(is_approved=True,role='user',username='synthetic',hourly_limit=40,daily_limit=40)
    client=Mock();client.auth.get_user.return_value.user=SimpleNamespace(id='test',email='test@example.com')
    database=Mock();database.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data=[profile]
    database.rpc.return_value.execute.return_value.data=True
    monkeypatch.setattr(accounts,'admin_client',lambda:database)
    monkeypatch.setattr(accounts,'ensure_service_available',lambda:None)
    session=SimpleNamespace(access_token='synthetic')
    actor=accounts.reserve_review(client,session)
    assert actor.daily_limit==5
    assert database.rpc.call_args.args[1]['p_daily_limit']==5


def test_regular_user_limit_settings_cannot_exceed_five(monkeypatch):
    monkeypatch.setattr(accounts,'verified_actor',lambda *a,**kw:accounts.Actor('test','test@example.com',True,'super_admin'))
    with pytest.raises(accounts.AccountError):accounts.super_update(Mock(),object(),'test','user',True,40,6)


@pytest.mark.parametrize('role',['admin','super_admin'])
def test_admin_reservations_have_no_cap_and_still_record_usage(monkeypatch,role):
    client=Mock();client.auth.get_user.return_value.user=SimpleNamespace(id='test',email='test@example.com')
    database=Mock()
    database.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data=[
        dict(is_approved=True,role=role,username='trusted.admin',hourly_limit=1,daily_limit=1)]
    database.rpc.return_value.execute.return_value.data=False
    monkeypatch.setattr(accounts,'admin_client',lambda:database)
    monkeypatch.setattr(accounts,'ensure_service_available',lambda:None)
    session=SimpleNamespace(access_token='synthetic')
    for index in range(7):
        actor=accounts.reserve_review(client,session,request_id=str(index),client_name='Synthetic client')
        assert actor.unlimited_reviews
    database.rpc.assert_not_called()
    assert database.table.return_value.insert.call_count==7
    row=database.table.return_value.insert.call_args.args[0]
    assert row==dict(user_id='test',request_id='6',client_name='Synthetic client',
                     submitted_username='trusted.admin',submitted_by='test@example.com',status='running')
    database.reset_mock()
    assert accounts._review_limit_error(actor) is None
    database.table.assert_not_called()


@pytest.mark.parametrize('role',['admin','super_admin'])
def test_unapproved_admin_cannot_reserve(monkeypatch,role):
    client=Mock();client.auth.get_user.return_value.user=SimpleNamespace(id='test',email='test@example.com')
    database=Mock()
    database.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data=[
        dict(is_approved=False,role=role)]
    monkeypatch.setattr(accounts,'admin_client',lambda:database)
    with pytest.raises(accounts.AccountError,match='access_revoked'):
        accounts.reserve_review(client,SimpleNamespace(access_token='synthetic'))
    database.table.return_value.insert.assert_not_called()
    database.rpc.assert_not_called()


def test_session_admin_claim_does_not_override_live_regular_user_profile(monkeypatch):
    client=Mock();client.auth.get_user.return_value.user=SimpleNamespace(id='test',email='test@example.com')
    database=Mock()
    database.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data=[
        dict(is_approved=True,role='user')]
    database.rpc.return_value.execute.return_value.data=False
    monkeypatch.setattr(accounts,'admin_client',lambda:database)
    monkeypatch.setattr(accounts,'ensure_service_available',lambda:None)
    monkeypatch.setattr(accounts,'_review_limit_error',lambda *a:None)
    with pytest.raises(accounts.AccountError,match='rate_limited'):
        accounts.reserve_review(client,SimpleNamespace(access_token='synthetic',role='super_admin'))
    database.table.return_value.insert.assert_not_called()
    database.rpc.assert_called_once()


def test_admin_attempt_write_failure_and_global_pause_still_block_review(monkeypatch):
    monkeypatch.setattr(accounts,'verified_actor',lambda *a,**kw:accounts.Actor('test','test@example.com',True,'admin'))
    database=Mock();database.table.return_value.insert.return_value.execute.side_effect=RuntimeError('write failed')
    monkeypatch.setattr(accounts,'admin_client',lambda:database)
    monkeypatch.setattr(accounts,'ensure_service_available',lambda:None)
    with pytest.raises(accounts.AccountError,match='quota_unavailable'):accounts.reserve_review(Mock(),object())
    database.reset_mock()
    monkeypatch.setattr(accounts,'ensure_service_available',Mock(side_effect=accounts.AccountError('reviews_closed')))
    with pytest.raises(accounts.AccountError,match='reviews_closed'):accounts.reserve_review(Mock(),object())
    database.table.assert_not_called()


def test_daily_limit_resets_at_cairo_midnight(monkeypatch):
    now=datetime(2030,1,1,12,tzinfo=timezone.utc)
    stamps=[now-timedelta(hours=i+2) for i in range(5)]
    limit_database(monkeypatch,stamps)
    actor=accounts.Actor('test','test@example.com',True,'user',hourly_limit=40,daily_limit=5)
    error=accounts._review_limit_error(actor,now)
    assert error.period=='limit_daily' and error.details['day_used']==5
    assert error.details['retry_at']=='02/01/2030 00:00:00'


def test_previous_cairo_day_does_not_consume_today_allowance(monkeypatch):
    now=datetime(2030,1,1,22,5,tzinfo=timezone.utc) # 00:05 Cairo, 2 January
    limit_database(monkeypatch,[now-timedelta(minutes=10)]*5)
    actor=accounts.Actor('test','test@example.com',True,'user',hourly_limit=10,daily_limit=5)
    assert accounts._review_limit_error(actor,now) is None


def test_both_windows_report_later_hourly_reset_across_midnight(monkeypatch):
    now=datetime(2030,1,1,21,50,tzinfo=timezone.utc)
    limit_database(monkeypatch,[now-timedelta(minutes=10),now-timedelta(minutes=5)])
    actor=accounts.Actor('test','test@example.com',True,'user',hourly_limit=2,daily_limit=2)
    error=accounts._review_limit_error(actor,now)
    assert error.period=='limit_both'
    assert error.details['retry_at']=='02/01/2030 00:40:00'


def test_expired_attempts_do_not_create_an_hourly_limit_error(monkeypatch):
    now=datetime(2030,1,1,12,tzinfo=timezone.utc)
    limit_database(monkeypatch,[now-timedelta(hours=2)])
    actor=accounts.Actor('test','test@example.com',True,'user',hourly_limit=1,daily_limit=5)
    assert accounts._review_limit_error(actor,now) is None


def test_paused_reviews_do_not_masquerade_as_a_personal_quota(monkeypatch):
    monkeypatch.setattr(accounts,'service_controls',lambda:dict(maintenance_enabled=False,reviews_enabled=False))
    with pytest.raises(accounts.AccountError,match='reviews_closed'):accounts.ensure_service_available()


@pytest.mark.parametrize('lang',['en','ar'])
def test_quota_error_contains_both_counts_and_cairo_reset(lang):
    text=t('rate_limited_details',lang,period=t('limit_daily',lang),hour_used=1,hour_limit=40,
        day_used=10,day_limit=10,retry_at='01/01/2030 23:00:00')
    assert '1/40' in text and '10/10' in text and '01/01/2030 23:00:00' in text


@pytest.mark.parametrize('lang',['en','ar'])
def test_admin_editor_shows_independent_limits_and_refreshes_external_changes(monkeypatch,lang):
    actor=accounts.Actor('00000000-0000-0000-0000-000000000001','owner@example.com',True,'super_admin')
    profile=dict(id='00000000-0000-0000-0000-000000000002',username='synthetic.user',email='user@example.com',role='user',
        is_approved=True,hourly_limit=40,daily_limit=5)
    save=Mock();monkeypatch.setattr(accounts,'super_update',save)
    ui=AppTest.from_string('''
import app,streamlit as st
app._init_session_state()
app.render_access_management(object(),object(),st.session_state.profiles)
''')
    ui.session_state.lang=lang;ui.session_state.actor=actor;ui.session_state.profiles=[profile]
    ui.run()
    assert not ui.exception
    assert ui.number_input(key='hour_'+profile['id']).value==40
    assert ui.number_input(key='day_'+profile['id']).value==5
    assert any(item.value==t('review_limits_summary',lang,hour=40,day=5) for item in ui.caption)
    profile['daily_limit']=3
    ui.session_state.profiles=[profile];ui.run()
    assert not ui.exception
    assert ui.number_input(key='day_'+profile['id']).value==3
    next(button for button in ui.button if button.label==t('save_changes',lang)).click().run()
    assert not ui.exception
    assert save.call_args.args[-2:]==(40,3)


@pytest.mark.parametrize('lang',['en','ar'])
@pytest.mark.parametrize('role',['admin','super_admin'])
def test_admin_editor_shows_unlimited_instead_of_applied_caps(lang,role):
    actor=accounts.Actor('00000000-0000-0000-0000-000000000001','owner@example.com',True,'super_admin')
    profile=dict(id=actor.user_id,username='synthetic.admin',email=actor.email,role=role,
                 is_approved=True,hourly_limit=5,daily_limit=5)
    ui=AppTest.from_string('import app,streamlit as st\napp._init_session_state()\napp.render_access_management(object(),object(),st.session_state.profiles)')
    ui.session_state.lang=lang;ui.session_state.actor=actor;ui.session_state.profiles=[profile]
    ui.run()
    assert not ui.exception
    assert any(c.value==t('admin_reviews_unlimited',lang) for c in ui.caption)
    assert ui.number_input(key='hour_'+actor.user_id).disabled
    assert ui.number_input(key='day_'+actor.user_id).disabled
