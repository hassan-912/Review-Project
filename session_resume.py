"""Tab-scoped login restoration; Supabase credentials stay on the server."""
from dataclasses import dataclass,field
from threading import RLock
import re
import secrets
import time

import streamlit as st
import streamlit.components.v2 as components
import accounts


@dataclass
class Entry:
    tokens: dict
    touched: float
    lock: RLock=field(default_factory=RLock)


class ResumeVault:
    def __init__(self,ttl=8*3600,capacity=2000,clock=time.monotonic):
        self.ttl,self.capacity,self.clock=ttl,capacity,clock
        self.entries={};self.lock=RLock()

    @staticmethod
    def valid(handle):return isinstance(handle,str) and bool(re.fullmatch(r'[A-Za-z0-9_-]{43}',handle))

    @staticmethod
    def tokens(session):
        access=getattr(session,'access_token',None);refresh=getattr(session,'refresh_token',None)
        if not isinstance(access,str) or not isinstance(refresh,str) or not access or not refresh:return None
        expiry=getattr(session,'expires_at',0) or 0
        return dict(access=access,refresh=refresh,expiry=expiry if isinstance(expiry,(int,float)) else 0)

    def save(self,handle,session):
        tokens=self.tokens(session)
        if tokens is None:return None
        now=self.clock()
        with self.lock:
            for key,entry in list(self.entries.items()):
                if now-entry.touched>=self.ttl:self.entries.pop(key,None)
            entry=self.entries.get(handle) if self.valid(handle) else None
            if entry is None:
                if len(self.entries)>=self.capacity:
                    self.entries.pop(min(self.entries,key=lambda key:self.entries[key].touched))
                handle=secrets.token_urlsafe(32);entry=Entry(tokens,now);self.entries[handle]=entry
        with entry.lock:
            # A stale tab must not replace a newer rotated refresh token.
            if tokens['expiry']>entry.tokens['expiry'] or tokens==entry.tokens:entry.tokens=tokens
            entry.touched=now
        return handle

    def discard(self,handle):
        if self.valid(handle):
            with self.lock:self.entries.pop(handle,None)

    def restore(self,handle,client):
        with self.lock:
            entry=self.entries.get(handle) if self.valid(handle) else None
            if entry is None or self.clock()-entry.touched>=self.ttl:
                self.entries.pop(handle,None) if self.valid(handle) else None
                raise accounts.AccountError('session_expired')
        with entry.lock:
            session=accounts.restore_session(client,entry.tokens['access'],entry.tokens['refresh'])
            tokens=self.tokens(session)
            if tokens is None:raise accounts.AccountError('session_expired')
            with self.lock:
                if self.entries.get(handle) is not entry:raise accounts.AccountError('session_expired')
                entry.tokens=tokens;entry.touched=self.clock()
            return session


@st.cache_resource
def vault():
    # Store no SDK clients or role/approval snapshots here. Every restored
    # connection creates its own client and runs the normal live access checks.
    return ResumeVault()


_bridge=components.component('mg_session_resume',html='<span></span>',js="""
export default function({data,parentElement,setStateValue}) {
  const key = 'mg-review-resume-v1:' + window.location.pathname;
  let handle = null, available = true;
  try {
    if (data.action === 'clear') window.sessionStorage.removeItem(key);
    else if (data.action === 'set') window.sessionStorage.setItem(key, data.handle);
    handle = window.sessionStorage.getItem(key);
  } catch (_) { available = false; }
  const next = {ready:true,handle,available};
  const encoded = JSON.stringify(next);
  // CCv2 may pass a ShadowRoot, which has no dataset of its own.
  const marker = parentElement.querySelector('span');
  if (!marker || marker.dataset.lastResume !== encoded) {
    if (marker) marker.dataset.lastResume = encoded;
    setStateValue('state',next);
  }
}
""")


def browser_state(action,handle=None):
    result=_bridge(key='session_resume_bridge',data=dict(action=action,handle=handle),
        default={'state':{'ready':False,'handle':None}},on_state_change=lambda:None,height=0)
    return result.state or {}


def remember(session):
    handle=vault().save(st.session_state.get('resume_handle'),session)
    if handle:st.session_state.resume_handle=handle
    return handle


def forget():
    vault().discard(st.session_state.get('resume_handle'))


def hydrate(get_client):
    """Return false only while the browser is loading its opaque resume handle."""
    if st.session_state.get('resume_clear_pending'):
        state=browser_state('clear')
        if state.get('ready') and not state.get('handle'):st.session_state.pop('resume_clear_pending',None)
        return True
    session=st.session_state.get('supabase_session')
    if session:
        browser_state('set',remember(session))
        return True
    state=browser_state('read')
    if not state.get('ready'):return False
    handle=state.get('handle')
    if not handle:return True
    try:
        st.session_state.supabase_session=vault().restore(handle,get_client())
        st.session_state.resume_handle=handle
    except accounts.AccountError:
        vault().discard(handle)
        st.session_state.resume_clear_pending=True
        st.session_state.notice='session_expired'
        st.rerun()
    return True
