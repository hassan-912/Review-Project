# MG Visa File Review — production release

## ID reference notes and signup - 2026-10-17

A national ID number extracted from a document without an independent readable ID-number
reference stays visible as a manual-verification note. This specific note neither deducts
points nor makes the score provisional. Confirmed mismatches, missing required fields and
other unresolved identity checks retain their scoring behavior. The cache schema changes
so future reviews do not reuse the previous deduction.

Signup and password reset accept six or more characters with no character-mix rules.
Supabase Auth enforces a hard minimum of six; four is unsupported. The production email
provider minimum was reduced from eight to six after explicit user confirmation; the
provider already had no required character classes. Existing credentials are preserved.

## Bank balance and upload workspace - 2026-10-16

Flight and hotel holds are informational booking statuses, without a score deduction
or a ticket/prepayment demand. A clearly issued e-ticket takes precedence over hold text.
Downloaded reports omit document source filenames/pages; the interactive evidence view
remains available in the app.

The bank-statement category sends only the final original page to both model passes,
including for scanned PDFs. Earlier pages are neither sent nor analysed. Page-coverage
counts use this explicit scope. The final available or closing balance, its printed
currency/date and any final-page holder name are source-grounded before use.

Budget comparisons are non-scoring planning aids. They use explicit remaining booking
prices and an editable EUR 75/day starting allowance for food, local transport and activities;
this is not a consular minimum. Paid costs require explicit evidence. Missing prices,
unknown ownership and unavailable conversions prevent a complete affordability conclusion.
Statements are assessed separately, not summed. Public indicative EUR exchange rates are
cached daily from the free ExchangeRate-API endpoint, dated and attributed in the app;
no applicant data is sent to that endpoint. No paid inference provider is added.

Upload cards show bounded, session-only PDF/image thumbnails, with final-page thumbnails
for bank statements. Category IDs and file hashes stay stable when the super admin changes
the team's shared display order. Apply `supabase/upload_categories.sql` before deploying:
the settings table stays server-only and the save RPC rechecks the approved super-admin
role, validates the complete category list and records the setting change.

Verification: 204 offline tests pass. A tracked live review of fictional documents
read the final bank page only, recovered the correct balance/currency, extracted both
booking totals and reported both holds without deductions. Both PDF languages were
rendered and checked with no source filenames/page references in the export. Database
authorization/payload/grant assertions passed in a rolled-back transaction. Existing
server-only RLS tables intentionally have no client policies; no new public access was added.

## Context review correction — 2026-10-16

Reviews now use an extraction pass followed by an independent contextual read of the
original sources. Both passes use the existing free-model router and quota accounting;
fallback attempts and the extra inference consume the configured free quotas. The second
pass must account for every supplied filename, page and review criterion. Identical uploads
are read once; same-named files with different contents receive distinct source identifiers.
Small scanned cards receive supplementary crops from their original pages in memory.

Student enrollment is classified separately from employment. Native-script names are
compared to the passport's native name, and ID dates retain their printed precision.
Supporting claims preserve the subject's role and first-name-only register columns.
Application destination is compared directly with the booked main destination; country
language/code aliases and equal-night ties are handled without selecting an arbitrary winner.

Readable PDF form cells supply blank contact/identity findings. Booking hold statuses
and numeric-versus-written translation dates are checked against source text.
Contextual findings require traceable quotes; actual source lines can repair an imprecise
model quotation only when the asserted literal value is located unambiguously. Missing page
audits and unresolved evidence are review limitations, not deductions from the applicant's
file. Incomplete reviews display a provisional score. Neutral unverified descriptive claims
remain marked unverified without becoming invented document defects.

Missing cover-letter sections are grouped into one finding. When no letter exists, writing
templates use grounded trip details and explicit placeholders rather than invented funding
or return obligations. Flight-day advice uses final-destination arrival and return departure
times. Source references remain attached to the actual file/page. The PDF exporter resets
fallback fonts between scripts so an Arabic run cannot hide subsequent English references.

Regression tests use synthetic identities/documents. Private live-case review artifacts
remain under ignored local directories and are never committed.
The corrected release passes 181 offline regression/UI tests. A private live two-pass
review was checked against the original pages, including the side-by-side evidence view
and a rendered three-page PDF; the source documents are not part of the repository.

## Free hosting

Live deployment: **https://mg-visa-review.streamlit.app/** (2026-10-12).
Production health returned `ok`, and English and Arabic sign-in screens were verified.
Supabase's Site URL and exact redirect allowlist now point to the production domain.

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
probability. The October 16 release preserves severity deduction amounts and tier caps, disables completeness bonuses when critical findings exist, and caps a critically unresolved file at 64 with an explicit not-ready status. The 11-rule
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
- `extractor.py`: all hotels, language-aware summaries, stable category routing, automatic
  free-model routing, actual model reporting and File API cleanup.
- `validator.py`: per-booking identity/missing-date checks, union of accommodation coverage,
  month-end date handling and stable bilingual issue metadata.
- `business_checker.py`: stable issue message IDs; sector matching logic unchanged.
- `scorer.py`: critical-finding readiness gate and bonus protection.
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

### October 12 follow-up release

- Visible native borders for signup, login, password recovery and client-name inputs;
  all interface animations and transitions disabled. PDF bytes are reused per browser
  session/report/language rather than rebuilt on every report interaction.
- Signup requires a unique lowercase username (3–32 ASCII letters/numbers/dot/hyphen/
  underscore, starting with a letter/number). Signup and password recovery require eight
  characters without composition rules; the matching Auth setting was saved in Supabase.
  Existing login remains email and password. Existing profiles have usernames derived
  from their email; no account role or approval changed.
- Applied `review_usernames_and_attempt_attribution` from `supabase/usernames.sql`.
  Reviews retain verified profile usernames and reviewer emails. Admin attempts include
  running/interrupted, completed, failed and legacy rows. Failed/legacy reviews show no
  invented score; quotas still count failed analyses. Cache hits appear in completed
  review history and do not consume another model-analysis allowance.
- Added exact identity comparisons (including every booking/page), passport issue/expiry
  and national-ID number/issue/expiry comparisons against their own source documents.
  This earlier release rejected short names; the October 16 policy below supersedes it. Typography
  and ordering may differ. Missing/unreadable required data and uncertain cross-script
  names need manual verification. AI extraction is not an absolute OCR guarantee.
- Combined cover-letter/travel-plan files are classified by content. Specific proposed
  add/remove/replace/verify edits appear in the interface and both-language PDFs. Quotes
  are checked against their section and, for text PDFs, the actual uploaded text.
  Advice is separate from scoring, includes daily-plan gaps, and never invents facts.
- Database signup/uniqueness/authorization/attempt assertions passed inside a rolled-back
  transaction. Review-log client writes were revoked to prevent forged attribution.
  The score formula is unchanged; the newly critical discrepancies affect its inputs.

The username migration requires username-aware signup code. If reverting to an earlier
app release, keep a compatible username-generating signup trigger or temporarily disable
new signup during rollback. Do not drop usernames or existing review data.

The pre-release redesign is preserved in commit `47f662d`. Local source backup:
`C:\Users\Menna\Documents\projects\Review_pre_production_20261012`.
To roll back the app, deploy a known working Git commit or branch through Community Cloud.
The additive quota table can remain in the database during rollback; no user or review
data was deleted. Restoring old code also restores its old session-security limitations.


## October 16: source evidence, review policy and super administration

Apply `supabase/model_usage.sql` using Supabase migrations before deploying this code.
The additive migration enables model accounting, super-admin controls and profile-based
review quotas. The owner is promoted separately after code supporting `super_admin`
is deployed. Keep the existing owner login; do not create a shared administrator password.
A super administrator inherits the team dashboard and can change roles, approvals,
per-user quotas, free-model priorities/caps and whether new reviews are enabled.
The last approved super administrator and self-revocation are protected atomically.
All configuration changes are recorded in `admin_audit` (90-day retention).
Public/ordinary authenticated clients have no access to these control tables or RPCs.

Application travel dates anchor bookings and itinerary checks with no three-day allowance.
HR leave alone allows one day inward at each edge: leave November 25–29 permits trip
starts November 25/26 and trip ends November 28/29. Travel outside leave is critical.
All hotel stays must remain inside leave; only overall accommodation edges use the
one-day rule. Itinerary rows must cover every application travel day.

Names accept the full passport name or first given name plus the complete surname.
Compound surnames use the separately extracted passport surname. Other exact-token
partial formats produce a format note; spelling errors, initials and blank names do
not pass. Passport/national-ID issue/expiry discrepancies remain critical.

Every supporting upload needs a classification, page audit and quoted claim assessment.
Checks compare passport, identity, employment and date references supplied in the file.
Text-PDF quotations are checked on the stated page; untraceable claims remain unresolved.
A claim's consistency never establishes authenticity or confirms facts with an issuer.
Mixed scanned/text PDFs use vision for the whole file, so scanned pages cannot disappear
behind a text-only extraction. Completeness is a populated-field ratio, not measured
accuracy; page coverage is model-reported, with uncertainties displayed separately.

Evidence expanders show real uploaded page/crop bytes on the left and the expected
value plus available reference on the right. Exact text matches and approximate
AI-located regions have distinct labels; an unlocated finding falls back to a labelled
page preview or an explicit unavailable message. Corrected official documents are never
fabricated. Crops are generated lazily, bounded in size and cached only in that browser
session. Source files and crops are not written to the database or application disk.
Logout, revocation and clear-files actions remove the active report/session cache.
The PDF includes readiness, expected values, evidence filenames/pages and dated advice.

The free catalog is Gemini 3.8 Flash, 3.6 Flash, 3.5 Flash-Lite and 3.1 Flash-Lite, in that
priority order. These model IDs and the connected project's free quotas were verified
on October 16 in AI Studio. The old GEMINI_MODELS setting is ignored. Users cannot pick
models. The router reserves project-wide RPM/RPD/input-TPM capacity atomically, calls
each eligible model once, validates its JSON/schema before accepting it, and falls back
on quota/unavailable/transient/invalid-output failures. CountTokens counts all prompt parts,
including system text, with a conservative 32-token protocol allowance for reservations;
provider output usage includes reasoning tokens where reported. Provider 429s trigger
cooldowns, and identifiable daily quota errors wait until the next Pacific midnight.
The SDK's default five HTTP attempts are disabled so routing owns retries, usage
reservations track individual inference requests, and unavailable models fail over promptly.

Model usage events contain only model/user IDs, counters, timing and coarse status;
no prompts, documents, keys or raw provider exceptions are retained. Events remain for
32 days. Requests since tracking began, including failed/reserved attempts, are counted.
Dashboard remaining figures are app estimates against configured caps, exclude usage
outside this app, and are not the provider's exact remaining quota. Provider-wide
remaining is unavailable to this integration. Google usage displays can lag 15 minutes.
Daily counters follow Pacific midnight and display their reset time in Cairo.

Google AI Pro includes higher limits inside AI Studio and eligible monthly Cloud credits;
it does not automatically change this project's API billing tier. The connected project
was verified as Free tier. Activating credits can require billing/prepayment. No billing
upgrade or paid fallback is enabled. ChatGPT Plus usage and OpenAI API billing are
separate, so OpenAI inference is not enabled under the zero-extra-spend requirement.

The migration leaves original profiles, approval state and review history intact.
Rollback to the pre-October-16 app requires restoring the owner's role to admin, or
backporting super-admin role recognition; keep the additive tables and existing data.


October 16 verification: 136 offline regression/UI tests cover both interface languages,
HR boundary cases, full/short/compound names, document coverage, real in-memory crops,
supporting-quote grounding, automatic routing and privileged-action authorization.
Database assertions for quota grants/denials, pause, role escalation protection, last-super
protection and RPC privileges passed in a rolled-back transaction. One tracked live review
of eight fictional files succeeded via fallback to Gemini 3.5 Flash-Lite, with all eight
page audits, combined-section detection, supporting classification and critical readiness.
The evidence view was checked in the browser using those real extraction results, and
both PDF languages were rendered. The Arabic PDF now separates labels and technical
values to preserve visible labels and ISO date order with the pinned font shaper.
