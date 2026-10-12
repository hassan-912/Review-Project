# MG Visa File Review — production release

## Free hosting

Deploy `app.py` from the `codex/production-ready` branch of `hassan-912/Review-Project`
on Streamlit Community Cloud. Select Python **3.12** in Advanced settings. Dependencies
are pinned in `requirements.txt`; `requirements.in` records the direct dependencies.

Copy the variables from `.streamlit/secrets.example.toml` into the hosting dashboard's
Secrets field using the current values from the local `.env`. Do not put real values in
GitHub. Both `.env` and `.streamlit/secrets.toml` are gitignored. Set `APP_URL` to the
final HTTPS app address. Environment variables continue to work for local deployments.

The application still requires Supabase login, email confirmation and administrator
approval. Restrict Community Cloud sharing to the MG team where available; keep the
application approval gate enabled. Free hosting can sleep when idle and has shared
resource limits; it does not provide a paid availability guarantee. Hosting being free
does not remove Google Gemini API usage charges or quotas.

## Database

The production guardrails in `supabase/production.sql` were applied to the connected
`mgvisa-reviewer` project. They preserve the existing profile and review log schemas,
protect the signup trigger, and add a server-only atomic review-attempt reservation.
The app fails closed if this reservation cannot be checked. Defaults are 5 fresh
analyses per rolling hour and 20 per rolling 24 hours per approved user. Failed AI
requests consume an attempt. Reusing an existing session result does not call Gemini.

Approval is checked against the live profile before each protected action. Admins can
approve and revoke other users; they cannot revoke their own access through the UI.
The watchdog rechecks sessions every minute while connected. Revocation blocks the next
protected action, including reading history, running reviews and writing review logs.

## Password reset

In Supabase Authentication -> URL Configuration, set Site URL and allowlisted redirect
URLs to the final `APP_URL`. Password reset uses the standard recovery email link;
its URL fragment is consumed once by a minimal Streamlit component and immediately
removed from the browser URL. The callback verifies it through Supabase before enabling
a password change. Email delivery requires correctly configured Supabase email settings.
No approval notification email is sent by this release; admins should notify the team
through their normal process. Automated approval notifications are a later integration.

## Sessions and data

Auth clients and document caches belong to each Streamlit browser session. Admin database
clients never sign in as users. Service-role keys remain on the server. New sessions
never put access or refresh tokens in URLs. Legacy `_t`/`_r` links are consumed once,
then cleared; failed restoration shows a translated expiry message. Active sessions
refresh their tokens. A browser reload or server restart requires signing in again.
Persistent browser login with secure HTTP-only cookies is a separate future feature.

Documents are bounded to 20 MB each, 75 MB total, 30 files, and 150 pages per PDF.
Files are checked server-side, stay in memory, and are sent to Google Gemini. Binary
uploads are deleted from Gemini's File API after analysis or partial upload failures
where deletion succeeds. Google's own retention terms still apply; the UI explains
this. No client document files are written to application disk or Supabase storage.
History stores client name, destination, agent, score and timestamp. It retains the
existing `Client:::Country` format for compatibility.

The score is labelled as an internal file-review score rather than an approval
probability. Existing severity deductions, caps and bonuses are unchanged. The 11-rule
engine is preserved, with accommodation checks extended across all bookings and a
calendar-safe fix for three-month passport-validity calculations.

## Verification

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python -m streamlit run app.py
```

`scripts/smoke_gemini.py en` and `scripts/smoke_gemini.py ar` run live smoke tests with
fictional in-memory documents. They incur model usage, never use real client files,
and do not create review-log records. Each verifies identity extraction and two hotels.
The CI workflow runs offline tests without real credentials.

Release checks: **57 automated tests passed in a clean Python 3.12 environment**,
with no dependency conflicts. Live Gemini reviews passed in both English and Arabic,
each extracting two hotel bookings with matching identity evidence. English and Arabic
Unicode PDFs were rendered and visually inspected, including an Arabic client name
and correctly ordered ISO dates. Database quota grant/denial assertions passed inside
a rolled-back transaction, and public execution privileges were confirmed disabled.

Before team use, sign in with an existing approved admin account on the deployed app,
check both languages, run a representative review, download the PDF, and confirm
history and revoke/restore controls. Password reset email delivery must be verified
after the production redirect URL is configured. Existing users and reviews are preserved.

## Changes by file

- `app.py`: bilingual access, upload, processing, report, history and admin views; active
  session watchdog; safe cache invalidation; translated errors; working revoke controls.
- `accounts.py`: isolated Auth clients, server-verified authorisation, live profile checks,
  atomic quota requests and review logging; no shared user session.
- `extractor.py`: all hotels, language-aware summaries, stable category routing, configurable
  model chain, honoured selected model, actual model reporting and File API cleanup.
- `validator.py`: per-booking identity/missing-date checks, union of accommodation coverage,
  month-end date handling and stable bilingual issue metadata.
- `business_checker.py`: stable issue message IDs; sector matching logic unchanged.
- `scorer.py`: unchanged.
- `i18n.py`: English/Arabic interface, field names and rule explanations.
- `theme.py` / `.streamlit/config.toml`: MG brand colours, accessible native controls, RTL
  support, upload states, white bordered cards and production server settings.
- `pdf_report.py` / `assets/fonts`: shaped Arabic and Unicode fonts, left-to-right technical
  values, in-memory generation and bundled font licences.
- `uploads.py`: canonical hashes incorporating model/language/schema; server-side file limits.
- `review_pipeline.py`: testable orchestration independent of the UI.
- `recovery.py`: one-time password-recovery fragment bridge.
- `settings.py`: local environment and hosted secret configuration.
- `tests/`, pinned requirements and `.github/workflows/checks.yml`: reproducible release checks.

## Rollback

The pre-release redesign is preserved in commit `47f662d`. Local source backup:
`C:\Users\Menna\Documents\projects\Review_pre_production_20261012`.
To roll back the app, deploy a known working Git commit or branch through Community Cloud.
The additive quota table can remain in the database during rollback; no user or review
data was deleted. Restoring old code also restores its old session-security limitations.
