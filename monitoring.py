"""Opt-in error reporting without document text, credentials or user identity."""
from functools import lru_cache
from pathlib import PureWindowsPath
import uuid

from settings import setting


def scrub_event(event,hint=None):
    # Allowlist rather than trying to recognise every possible personal field.
    clean={key:event[key] for key in ('event_id','timestamp','platform','level','release','environment') if key in event}
    tags=event.get('tags') or {}
    clean['tags']={key:value for key,value in tags.items() if key in ('operation','support_reference')}
    exceptions=[]
    for error in (event.get('exception') or {}).get('values',[]):
        frames=[]
        for frame in (error.get('stacktrace') or {}).get('frames',[]):
            frames.append(dict(filename=PureWindowsPath(frame.get('filename') or '').name,
                function=frame.get('function'),lineno=frame.get('lineno'),in_app=frame.get('in_app',False)))
        exceptions.append(dict(type=error.get('type','Error'),value='Error details withheld for document privacy.',
            stacktrace=dict(frames=frames)))
    clean['exception']={'values':exceptions}
    return clean


@lru_cache(maxsize=1)
def _initialize(dsn,environment,release):
    if not dsn:return False
    import sentry_sdk
    sentry_sdk.init(dsn=dsn,environment=environment,release=release or None,
        data_collection={'user_info':False,'cookies':{'mode':'off'},
            'http_headers':{'request':{'mode':'off'}},'http_bodies':[],
            'url_query_params':{'mode':'off'},'database_query_data':False,'queues':False,
            'stack_frame_variables':False,'frame_context_lines':0,
            'gen_ai':{'inputs':False,'outputs':False}},
        include_local_variables=False,include_source_context=False,
        max_request_body_size='never',default_integrations=False,auto_enabling_integrations=False,
        traces_sample_rate=0,profiles_sample_rate=0,before_send=scrub_event,
        max_breadcrumbs=0,attach_stacktrace=False)
    return True


def initialize_monitoring():
    try:
        return _initialize(setting('SENTRY_DSN'),setting('SENTRY_ENVIRONMENT','development'),setting('SENTRY_RELEASE'))
    except Exception:
        # A monitoring outage must never stop a review or reveal configuration.
        return False


def capture_error(error,operation):
    reference=uuid.uuid4().hex[:10]
    if initialize_monitoring():
        try:
            import sentry_sdk
            with sentry_sdk.new_scope() as scope:
                scope.set_tag('operation',operation)
                scope.set_tag('support_reference',reference)
                sentry_sdk.capture_exception(error)
        except Exception:
            pass
    return reference
