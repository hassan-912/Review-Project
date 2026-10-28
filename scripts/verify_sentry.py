"""Send one synthetic setup error using the application's privacy filter."""
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from monitoring import capture_error,initialize_monitoring


class SentrySetupVerification(RuntimeError):
    pass


def main():
    if not initialize_monitoring():
        raise SystemExit('Sentry is not configured. Set SENTRY_DSN first.')
    try:
        raise SentrySetupVerification('Synthetic setup verification; no customer data.')
    except SentrySetupVerification as exc:
        reference=capture_error(exc,'setup_verification')
    import sentry_sdk
    sentry_sdk.flush(timeout=10)
    print('Synthetic event submitted; support reference: '+reference)


if __name__=='__main__':main()
