from types import SimpleNamespace
from unittest.mock import Mock
import time
import pytest
import accounts
from accounts import AccountError


def test_auth_clients_are_not_shared(monkeypatch):
    monkeypatch.setattr(accounts,'setting',lambda name:'fake')
    factory=Mock(side_effect=[object(),object()]); monkeypatch.setattr(accounts,'create_client',factory)
    assert accounts.auth_client() is not accounts.auth_client()
    assert factory.call_args.kwargs['options'].auto_refresh_token is False


def test_refresh_before_expiry():
    client=Mock(); session=SimpleNamespace(expires_at=time.time()+60,refresh_token='old')
    renewed=SimpleNamespace(access_token='new')
    client.auth.refresh_session.return_value=SimpleNamespace(session=renewed,user=object())
    assert accounts.refresh_if_needed(client,session) is renewed
    client.auth.refresh_session.assert_called_once_with('old')


def test_restore_tries_refresh_before_failing():
    client=Mock(); client.auth.set_session.side_effect=RuntimeError('expired')
    client.auth.refresh_session.return_value=SimpleNamespace(session=object(),user=object())
    assert accounts.restore_session(client,'expired','refresh')
    client.auth.refresh_session.assert_called_once_with('refresh')


def test_restore_failure_is_explicit():
    client=Mock(); client.auth.set_session.side_effect=RuntimeError();client.auth.refresh_session.side_effect=RuntimeError()
    with pytest.raises(AccountError,match='session_expired'):accounts.restore_session(client,'bad','bad')


def test_revocation_blocks_review_even_with_existing_token(monkeypatch):
    client=Mock(); client.auth.get_user.return_value.user=SimpleNamespace(id='id',email='test@example.com')
    database=Mock(); database.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data=[{'is_approved':False,'role':'user'}]
    monkeypatch.setattr(accounts,'admin_client',lambda:database)
    with pytest.raises(AccountError,match='access_revoked'):
        accounts.verified_actor(client,SimpleNamespace(access_token='token'))


def test_non_admin_cannot_approve(monkeypatch):
    monkeypatch.setattr(accounts,'verified_actor',Mock(side_effect=AccountError('access_revoked')))
    database=Mock();monkeypatch.setattr(accounts,'admin_client',lambda:database)
    with pytest.raises(AccountError):accounts.set_approval(Mock(),object(),'00000000-0000-0000-0000-000000000001',True)
    database.table.assert_not_called()


@pytest.mark.parametrize('allowed',[False,None])
def test_quota_denial_fails_closed(monkeypatch,allowed):
    monkeypatch.setattr(accounts,'verified_actor',lambda *args,**kw:accounts.Actor('id','test@example.com',True,'user'))
    database=Mock();database.rpc.return_value.execute.return_value.data=allowed
    monkeypatch.setattr(accounts,'admin_client',lambda:database)
    with pytest.raises(AccountError,match='rate_limited'):accounts.reserve_review(Mock(),object())


def test_quota_service_error_fails_closed(monkeypatch):
    monkeypatch.setattr(accounts,'verified_actor',lambda *args,**kw:accounts.Actor('id','test@example.com',True,'user'))
    monkeypatch.setattr(accounts,'admin_client',Mock(side_effect=RuntimeError()))
    with pytest.raises(AccountError,match='quota_unavailable'):accounts.reserve_review(Mock(),object())


def test_review_log_uses_verified_profile_username(monkeypatch):
    monkeypatch.setattr(accounts,'verified_actor',lambda *a,**kw:accounts.Actor('uid','reviewer@example.com',True,'user','trusted.reviewer'))
    db=Mock();monkeypatch.setattr(accounts,'admin_client',lambda:db)
    accounts.log_review(Mock(),object(),'FICTIONAL','France',65)
    row=db.table.return_value.insert.call_args.args[0]
    assert row['submitted_username']=='trusted.reviewer' and row['user_id']=='uid' and row['score']==65


def test_failed_attempt_has_no_invented_score(monkeypatch):
    monkeypatch.setattr(accounts,'verified_actor',lambda *a,**kw:accounts.Actor('uid','reviewer@example.com',True,'user','trusted.reviewer'))
    db=Mock();monkeypatch.setattr(accounts,'admin_client',lambda:db)
    accounts.finish_attempt(Mock(),object(),'request')
    assert db.table.return_value.update.call_args.args[0]=={'status':'failed','score':None}
