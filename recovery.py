"""One-time password-recovery bridge; credentials are removed from browser URLs."""
import streamlit.components.v2 as components

_bridge = components.component(
    "mg_password_recovery",
    html="<span></span>",
    js="""
export default function({setTriggerValue}) {
  const params = new URLSearchParams(window.location.hash.slice(1));
  if (params.get('type') === 'recovery' && params.get('access_token') && params.get('refresh_token')) {
    const value = {access_token: params.get('access_token'), refresh_token: params.get('refresh_token')};
    window.history.replaceState(null, '', window.location.pathname + window.location.search);
    setTriggerValue('recovery', value);
  }
}
""",
)


def recovery_tokens():
    result = _bridge(key="recovery_bridge", on_recovery_change=lambda: None, height=0)
    return result.recovery
