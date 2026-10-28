"""Browser refresh restores only the ticket's session and rechecks live access."""
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from streamlit.testing.v1 import AppTest
import accounts
import session_resume as resume


def session(name='one',expiry=100):
    return SimpleNamespace(access_token='access-'+name,refresh_token='refresh-'+name,expires_at=expiry)


def test_tickets_are_opaque_and_browser_sessions_are_isolated(monkeypatch):
    vault=resume.ResumeVault()
    one=vault.save(None,session('one'));two=vault.save(None,session('two'))
    assert one!=two and vault.valid(one) and 'access' not in one and 'refresh' not in one
    calls=[]
    def restore(client,access,refresh):calls.append((client,access,refresh));return session('restored',200)
    monkeypatch.setattr(accounts,'restore_session',restore)
    client=object();vault.restore(one,client)
    assert calls==[(client,'access-one','refresh-one')]
    assert vault.entries[two].tokens['refresh']=='refresh-two'


def test_rotation_is_saved_and_stale_connections_cannot_overwrite_it(monkeypatch):
    vault=resume.ResumeVault();ticket=vault.save(None,session())
    restore=Mock(return_value=session('rotated',200));monkeypatch.setattr(accounts,'restore_session',restore)
    vault.restore(ticket,object())
    vault.save(ticket,session('stale',100))
    vault.restore(ticket,object())
    assert restore.call_args.args[1:]==('access-rotated','refresh-rotated')


@pytest.mark.parametrize('ticket',[None,'','bad','x'*43,{'forged':'ticket'},'x'*10000])
def test_invalid_ticket_never_calls_auth(monkeypatch,ticket):
    restore=Mock();monkeypatch.setattr(accounts,'restore_session',restore)
    with pytest.raises(accounts.AccountError,match='session_expired'):resume.ResumeVault().restore(ticket,object())
    restore.assert_not_called()


def test_expired_and_signed_out_tickets_are_rejected(monkeypatch):
    now=[0];vault=resume.ResumeVault(ttl=10,clock=lambda:now[0])
    expired=vault.save(None,session());now[0]=11
    with pytest.raises(accounts.AccountError):vault.restore(expired,object())
    ticket=vault.save(None,session());vault.discard(ticket)
    with pytest.raises(accounts.AccountError):vault.restore(ticket,object())


def test_logout_during_restore_cannot_resurrect_ticket(monkeypatch):
    vault=resume.ResumeVault();ticket=vault.save(None,session())
    def restoring(*args):vault.discard(ticket);return session('new',200)
    monkeypatch.setattr(accounts,'restore_session',restoring)
    with pytest.raises(accounts.AccountError):vault.restore(ticket,object())


def test_vault_is_bounded_and_removes_old_tickets():
    now=[0];vault=resume.ResumeVault(capacity=2,clock=lambda:now[0])
    first=vault.save(None,session('one'));now[0]=1
    second=vault.save(None,session('two'));now[0]=2
    third=vault.save(None,session('three'))
    assert len(vault.entries)==2 and first not in vault.entries and second in vault.entries and third in vault.entries


def test_browser_bridge_contains_no_credentials_or_url_storage():
    from pathlib import Path
    source=Path(resume.__file__).read_text(encoding='utf-8').split('_bridge=components.component',1)[1].split('def browser_state',1)[0]
    assert 'sessionStorage' in source
    assert all(word not in source for word in ('access_token','refresh_token','localStorage','location.search','location.hash'))


def test_browser_bridge_supports_shadow_roots_and_restores_only_opaque_handle():
    import ast,json,shutil,subprocess
    from pathlib import Path
    node=shutil.which('node')
    if not node:pytest.skip('Node is required to execute the frontend regression')
    tree=ast.parse(Path(resume.__file__).read_text(encoding='utf-8'))
    declaration=next(item.value for item in tree.body if isinstance(item,ast.Assign) and
                     any(isinstance(target,ast.Name) and target.id=='_bridge' for target in item.targets))
    js=next(keyword.value.value for keyword in declaration.keywords if keyword.arg=='js')
    script='const run = '+js.replace('export default','',1)+''';
const saved=new Map();
const window={location:{pathname:'/'},sessionStorage:{
 setItem:(k,v)=>saved.set(k,v),getItem:k=>saved.get(k)??null,removeItem:k=>saved.delete(k)}};
let marker={dataset:{}};const changes=[];
const root={querySelector:()=>marker}; // ShadowRoot itself has no dataset.
const invoke=data=>run({data,parentElement:root,setStateValue:(key,state)=>changes.push(state)});
invoke({action:'set',handle:'A'.repeat(43)});
invoke({action:'set',handle:'A'.repeat(43)});
marker={dataset:{}};invoke({action:'read'});
invoke({action:'clear'});
console.log(JSON.stringify(changes));
'''
    result=subprocess.run([node,'--input-type=module','-e',script],capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr
    changes=json.loads(result.stdout)
    assert len(changes)==3 and changes[0]['handle']==changes[1]['handle']=='A'*43
    assert changes[2]['handle'] is None and all(value['ready'] for value in changes)


def test_new_streamlit_connection_restores_then_checks_current_role(monkeypatch):
    import recovery
    vault=resume.ResumeVault();ticket=vault.save(None,session())
    monkeypatch.setattr(resume,'vault',lambda:vault)
    monkeypatch.setattr(resume,'browser_state',lambda *args,**kw:dict(ready=True,handle=ticket))
    monkeypatch.setattr(accounts,'restore_session',lambda *args:session('restored',200))
    actor=accounts.Actor('synthetic','user@example.com',False,'user')
    check=Mock(return_value=actor);monkeypatch.setattr(accounts,'verified_actor',check)
    monkeypatch.setattr(accounts,'refresh_if_needed',lambda client,value:value)
    monkeypatch.setattr(accounts,'service_controls',lambda:dict(maintenance_enabled=False,reviews_enabled=True))
    monkeypatch.setattr(accounts,'auth_client',lambda:object())
    monkeypatch.setattr(recovery,'recovery_tokens',lambda:None)
    from pathlib import Path
    ui=AppTest.from_file(Path(__file__).resolve().parents[1]/'app.py',default_timeout=30).run()
    assert not ui.exception
    assert ui.session_state.supabase_session.access_token=='access-restored'
    assert any(h.value=='Account pending approval' for h in ui.subheader)
    assert not ui.get('file_uploader')
    check.assert_called_once()


def test_clear_session_forgets_ticket_and_requests_browser_clear(monkeypatch):
    vault=resume.ResumeVault();ticket=vault.save(None,session())
    monkeypatch.setattr(resume,'vault',lambda:vault)
    ui=AppTest.from_string('import app\napp._init_session_state()\napp._clear_local_session()')
    ui.session_state.resume_handle=ticket;ui.session_state.supabase_session=session()
    ui.run()
    assert not ui.exception and ticket not in vault.entries
    assert ui.session_state.resume_clear_pending and 'supabase_session' not in ui.session_state
