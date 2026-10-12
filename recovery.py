"""One-time password-recovery bridge; credentials are removed from browser URLs."""
import streamlit.components.v2 as components

_bridge = components.component(
    "mg_password_recovery",
    html="<span></span>",
    js="""
export default function({setTriggerValue}) {
  // Community Cloud embeds the app in a same-origin frame. Clear the recovery
  // fragment in both the app and its hosting window; never access other origins.
  const windows = [window];
  try {
    if (window.parent !== window && window.parent.location.origin === window.location.origin) {
      windows.push(window.parent);
    }
  } catch (_) { /* Cross-origin embeds retain the normal app-only callback. */ }
  const source = windows.find(w => new URLSearchParams(w.location.hash.slice(1)).get('type') === 'recovery');
  if (!source) return;
  const params = new URLSearchParams(source.location.hash.slice(1));
  if (params.get('type') === 'recovery' && params.get('access_token') && params.get('refresh_token')) {
    const value = {access_token: params.get('access_token'), refresh_token: params.get('refresh_token')};
    for (const target of windows) {
      if (new URLSearchParams(target.location.hash.slice(1)).get('type') === 'recovery') {
        target.history.replaceState(null, '', target.location.pathname + target.location.search);
      }
    }
    setTriggerValue('recovery', value);
  }
}
""",
)


def recovery_tokens():
    result = _bridge(key="recovery_bridge", on_recovery_change=lambda: None, height=0)
    return result.recovery
