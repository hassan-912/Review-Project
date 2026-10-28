# MG Visa File Review

## Gemini narrative review — 27 October 2026

Apply `supabase/migrations/202610270001_gemini_review.sql` to the existing Supabase
project. Add `GEMINI_API_KEY` from a billing-enabled Google project to server secrets,
with `GEMINI_MODEL=gemini-3.8-flash` and optional
`GEMINI_FALLBACK_MODEL=gemini-3.6-flash` (the default fallback). Optionally set a positive `USD_EGP_RATE`; otherwise
a dated public exchange-rate feed is used. Configure hosted secrets separately.

Letters, plans, bank statements and supporting documents are reviewed after local extraction. Passport,
application, hotel, flight, HR and insurance use local fields/text; their PDFs are
never sent to Gemini. Bank/supporting PDFs may be attached for visual fallback. Word, HTML and image uploads are normalized locally. The admin
cost section records actual per-request tokens and EGP costs, with clearly labelled
per-file allocations. Read `docs/NARRATIVE_REVIEW.md` for scope, billing and validation.
The dashboard includes averages per AI review/document, document-type averages,
individual file estimates and an interactive EGP calculator even with no usage.
Quota rejection before generation may switch once to 3.6 Flash. Other errors,
reported usage and generated/invalid results never trigger an automatic repeat.

These local changes do not deploy the hosted website or apply the database migration.

## Current factual review flow

The website uses local Python/PDF/OCR parsers and deterministic key/value comparisons.
Gemini now performs motivation-letter/travel-plan review from extracted reference facts;
see `docs/NARRATIVE_REVIEW.md`. There is no AI extraction fallback for unsupported
reference templates. Unsupported or uncertain
readings cannot become confirmed applicant errors. Initial local OCR use can still take longer
while loading its models; subsequent page interactions do not repeat review extraction.

Tourism workspaces are available for all eight listed Schengen countries. Business,
Canada and UK remain under processing. USA has a separate, fully local DS-160 route
with exactly DS-160, hotel, passport and client-form uploads; it does not require or
call Gemini. Read `docs/USA_REVIEW.md` for its template and comparison coverage.
Supported Schengen source templates, HR comparisons,
passport references and the 60-day appointment planning buffer remain in place. The latter
is this service's planning rule, not an embassy processing guarantee.

The Schengen selector contains only Spain and the seven requested additional destinations:
France, Germany, Netherlands, Italy, Sweden, Belgium and Greece. Each country opens the shared
upload/review flow and reports its selected destination. Country selection does not authorize
new PDF layouts: application extraction still requires the existing label, page and alignment
checks until additional templates are mapped. See `templates/schengen/README.md` for the contract.
Company-address comparisons use the application employer section and explicit HR company
address, never applicant home address. Ambiguous or provisional readings remain unverified.

Spain has dedicated National ID translation and Bank declaration upload cards immediately
after the visa application form. They feed the existing local supporting-template parsers;
general supporting uploads are preserved alongside them. Shared category-order preferences
keep their existing IDs, so no database migration is required for these Spain-only cards.

The customer report shows confirmed corrections only, with the wrong value in red, the
expected value in green and a screenshot of the entire source field. Uploaded thumbnails
and review settings stay removed. Unverified checks remain limitations internally; a report
with no confirmed corrections does not mean unsupported documents were verified.

Hotel-date corrections use the labelled check-in/check-out fields. Cancellation-policy
dates cannot substitute for missing field evidence. A late first check-in or early final
check-out produces one boundary correction, without a duplicate gap comparing derived dates.
Accommodation coverage and internal missing-night checks are disabled. Source screenshots
use version 3 and review identities use local engine version 7 so older misleading results
are not reused; rerun an existing review after the validation update.

Direct comparison references also show the actual source field with a green marker. A
calculated threshold is not highlighted as if printed in a reference document. An empty
Passport slot produces one upload instruction instead of separate missing-number/expiry
cards. Narrative upload presence is checked before duplicate bytes are removed, so a
combined cover letter/travel plan retains both Gemini review roles rather than a false missing file.

## Faster page updates

Client name and uploads share a form. Run review submits a committed snapshot once; clearing
works on its first click. Results are cached per browser for 30 minutes with at most three
reviews, keyed by content, language, country, trip type and the local engine version.

Independent passport, Spain form, hotel, flight and HR readings are also reused within the
same browser session. This bounded metadata cache holds at most 32 parser results for 30
minutes; it stores no uploaded bytes. Its keys include the parser version, filename and
content digest. Changing a file invalidates its reading; comparisons and evidence assembly
run again against the current upload set. Mutable readings are copied before reuse. Clearing
the file, changing review scope, losing access, maintenance or signing out removes this cache.
An explicit forced review resets it as well. Nothing is shared between customer sessions.

The shared OCR models prepare in a background thread while an approved user chooses files.
Preparation uses generated text, never customer documents. Uploading does not run extraction;
the first review of scans can still take tens of seconds depending on pages and image size.
Native upload progress animations remain enabled, upload captions target only the Browse
button, and the page no longer imports a remote font stylesheet. Native upload transfer
time still depends on file size and the connection; no framework upload handler is patched.

Ordinary page reruns reuse per-browser authorization and service-status snapshots for at
most 15 and 10 seconds respectively. A separate 15-second watchdog refreshes access and
maintenance status. Review execution bypasses the display snapshots, checks approval and
maintenance again, reserves its attempt atomically, and rechecks access before showing results.
Administrative writes retain live role checks. Sign-out clears browser state. Supabase's
server-only service client reuses its HTTP pool; user auth clients remain isolated per browser.

Each user has at most five review attempts per Cairo calendar day (midnight reset).
Lower saved daily/hourly limits still apply to regular accounts. Approved Admin
and Super Admin accounts have no hourly or daily cap. Failed attempts
count. The database atomically enforces these limits. Initial factual+Gemini review uses
one attempt; an explicit AI retry uses a new attempt. Paused reviews have a separate message.

Admin sections load only their own data. Corrections PDFs are built on demand in Streamlit's
download worker, rather than during report rendering; downloads do not rerun the page.
Rendered field screenshots and PDFs stay in the browser session's server memory.

## Local run

Use Python 3.12 and install the compiled dependencies:

```powershell
cd "C:\Users\Menna\Documents\projects\Review"
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
```

Copy `.env.example` to `.env` when setting up another machine. Configure SUPABASE_URL,
SUPABASE_ANON_KEY and SUPABASE_SERVICE_ROLE_KEY. Keep the service key server-side.
Existing profile approvals, review-attempt quotas, maintenance controls and history remain
in Supabase. Historical database migrations/data are preserved; historical model-usage tables remain untouched. Apply the new Gemini migration
for its separate usage ledger and five-review calendar-day limit. Do not drop customer history during an upgrade.

## Sentry errors

The `mg-review` organization has a Python project named `visa-review`. Local configuration
is in the ignored `.env`; the Codex Sentry plugin is installed and its connection authorized.
The setup error was confirmed as VISA-REVIEW-1 with a filename/function/line stack frame:
https://mg-review.sentry.io/issues/155437635/

Set these server secrets on the hosted deployment as well:

- SENTRY_DSN: copy the project's Client Keys (DSN) value.
- SENTRY_ENVIRONMENT: production for the hosted app, development locally.
- SENTRY_RELEASE: a version identifier or Git commit for the deployed code.

Leaving SENTRY_DSN empty disables reporting. Errors in page rendering, review execution and
PDF downloading use `monitoring.py`. Unexpected local parser errors also report through
this filter. Customer-facing review/page failures show a support reference that matches
the event's support_reference tag. Monitoring failures never block a review.

Error reports allow only exception type, sanitized stack filename/function/line, environment,
release, operation and a random support reference. Exception messages, document contents,
user identity, request bodies, credentials, local variables, source context, breadcrumbs and
attachments are excluded. Automatic integrations, replay, tracing, profiling and logs are off.
Sentry receives requests from the application server, not customer browsers. Automatic fixes
or paid debugging features are not enabled; captured issues can be investigated before a fix
is tested and released.

To submit another synthetic verification event deliberately:

```powershell
.\.venv\Scripts\python.exe scripts/verify_sentry.py
```

## Checks and release

National ID numbers are read separately from the supported passport's printed Arabic-digit
field using local OCR. The passport is the primary national-ID reference; a readable ID
translation is the fallback when that passport field is unavailable. Application and ID
translation values are compared independently. Low-confidence/conflicting readings are not
accepted as references. This field is separate from the passport number and MRZ optional data.

Hotel date checks retain first check-in / last check-out comparisons against the application.
Accommodation coverage, internal missing-night gaps and per-booking date-order rules are
disabled. Existing hotel identity and appointment-buffer checks remain active. The review
cache version changed, so run a fresh review to apply these rules to previously uploaded files.

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe -m pip check
```

The suite covers local extraction, mismatches and uncertainty, HR/appointment dates, evidence
screenshots, both languages, first-click submission, session isolation, fresh action checks,
reused page snapshots, lazy admin reads, deferred downloads and actual SDK payload filtering.
Tests disable real Sentry delivery. Gemini HTTP contract tests use synthetic source text and mocked provider responses. The verification script is an explicit one-event opt-in.

For Community Cloud, update the repository/dependency lock and server secrets, then redeploy.
`packages.txt` includes the native libraries required by CPU OCR. Hosted restart/cold-start
time still depends on the host. These local edits do not publish or deploy the hosted site.

Routine navigation, sign-in mode changes, history search/pagination and cost-user
filters use Streamlit fragments. Read-only access/service polling runs in a bounded
background pool every 15 seconds; its small UI fragment checks completion once a
second. Poll results are scoped to the browser's token and cannot overwrite a newer
action check. Review submissions and admin changes still verify live permissions.
Service status and upload-card order share one database read. Document engines load
on demand; visiting the upload page no longer warms both OCR models. Large scans and
Gemini generation still take time and show progress when a review is submitted.

## Financial and translation review — 27 October 2026

Bank AI scope now includes all transaction pages and the latest six-month window.
Large-credit rules use EGP 500,000 or more than 60% of the comparable incoming total.
Missing salary checks preserve net/gross and account/currency/coverage uncertainty.
Daily city estimates plus quoted bookings form an explicitly approximate budget.
Arabic supporting originals anchor English translation comparisons. Read
`docs/NARRATIVE_REVIEW.md` for detailed provenance and limitations. No additional
database migration is needed for these session-only review outputs.

Approved Admin and Super Admin accounts have unlimited reviews, with no hourly
or daily cap. Each submission verifies the live database role and records a
review attempt through the server-only service client. Regular accounts retain
the atomic database quota and maximum five reviews per Cairo calendar day.
No database migration is needed for the admin exemption.

Browser refresh restores login in the same tab using an opaque, random resume
handle in sessionStorage. Supabase tokens stay in a bounded server-memory vault;
SDK clients and authorization snapshots are never shared between sessions.
Restoration validates Supabase credentials and reads live profile permissions.
Logout removes the server ticket and clears the browser handle. Inactive tickets
expire after eight hours. Server restarts/worker replacement require sign-in;
multi-worker hosting needs sticky sessions or a shared session store.
