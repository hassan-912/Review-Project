"""Read-only session polling without holding up Streamlit's UI thread."""
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from types import SimpleNamespace

import accounts


@lru_cache(maxsize=1)
def _workers():
    return ThreadPoolExecutor(max_workers=4,thread_name_prefix='session-status')


def _read(client,access_token):
    # get_user(explicit_token) only performs a GET; it never changes the browser
    # client's auth storage. No session-state access or UI rendering happens here.
    controls=accounts.service_controls()
    actor=accounts.verified_actor(client,SimpleNamespace(access_token=access_token),require_approved=False)
    return controls,actor


def start(client,access_token):
    return _workers().submit(_read,client,access_token)
