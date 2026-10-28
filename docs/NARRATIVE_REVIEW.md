# Gemini motivation-letter and travel-plan review

Updated 27 October 2026. Local GPU inference and manual notebook exchange have
been removed. Extraction and deterministic factual scoring still run locally.

## Context sent to Gemini

One bounded request reviews letter/plan problems, six-month bank activity and
Arabic-original/English-translation discrepancies. Passports, applications,
hotels, flights, HR and insurance are always JSON or locally extracted text,
never PDF API parts. Verified local fields are preferred. An unsupported layout
can supply native text/OCR context without claiming verified local extraction.
Only bank/supporting documents can attach PDFs when native reading/OCR is
insufficient. A file also assigned to a letter, plan or factual-reference slot
cannot use PDF attachment fallback. Inline PDFs are limited to 12 MiB total and
must match their declared source hashes. No remote file-upload API is used.

All bank pages are now in AI review scope, not just the final-page balance.
Context is capped at 30 documents, 180 text/visual sections and 240,000 characters.
Oversize input fails explicitly; it cannot silently truncate a six-month review.
Scanned evidence uses English and Arabic local OCR; visual-only quotations remain
unverified and cannot establish a completely source-verified review.

PDF, DOCX, Word 97+ DOC, HTML/HTM, TXT and PNG/JPEG/WebP/TIFF are accepted.
Word/HTML processing runs offline: no Office launch, macros, scripts or remote
resources. DOCX tables preserve rows; text-native Arabic is retained directly
rather than round-tripping its order through PDF. Local PDF copies support the
existing evidence pipeline. Native text citations use text-section numbers;
converted-PDF citations refer to the converted copy. Embedded DOCX images and all
TIFF frames are retained. Encrypted/malformed or image-only legacy DOC files that
cannot be read completely require a clearer DOCX/PDF copy; no clean pass is issued.

The response schema uses the current responseFormat text/JSON configuration,
Gemini's supported schema subset and LOW thinking. Strict local string, numeric,
source and coverage checks remain mandatory. A 12-finding limit bounds prose;
reaching it marks the result incomplete. Structured bank/budget data is returned
only when applicable. Customer outputs contain problems/actions, not a rewritten
letter, praise or generic stylistic advice. Remove/correct/verify actions retain
source quotations. No model finding changes deterministic factual scoring.

## Bank rules

Each account's analysis uses the latest six calendar months ending at its printed
statement period end. Model-read totals remain advisory; code calculates ratios,
checks candidate amounts against cited values and can sum explicitly labelled
same-day credit rows. A daily EGP credit >=500,000 OR a credit exceeding 60% of
TOTAL incoming money in the same six-month account/currency window is flagged for
explanation. This is NOT a 60% increase over a median. Foreign currency is never
silently treated as EGP. Partial coverage cannot establish a definite salary
absence; visual-only totals and flags require manual verification.

HR net/gross salary, amount and currency are bound to their local source where
available. Otherwise a cited, explicitly stated HR salary can be read from text.
The code checks matched amounts and dates, can recover explicitly labelled salary
credits locally, and rejects untraceable matches or reusing one payment for two
months. Missing exact matching credits are reported only for completely read,
full months and the applicant's own same-currency account. Gross/net deductions,
split payments and payroll dates need explanation. Early-month pay is a pattern,
not an absolute rule unless the HR specifies it. No HR means no fixed-payroll demand.
Commercial registry and tax-card evidence can explain business income; it does not
authenticate documents or certify every deposit legitimate. Overall cash-flow
coherence remains source-cited advisory analysis, without fraud allegations.

Separate statements are joined only for a visibly identified identical full
account/IBAN, bank, owner and currency, with contiguous, non-overlapping periods.
Masked accounts and gaps cannot be joined by guesswork. Duplicate bytes are read
once; different accounts/currencies and overlapping periods are not summed.

## Tourism costs and translations

Gemini checks current dates, arrival/departure times, cities/accommodation,
transfers and tourism activities. Its daily city ranges cover food, local
transport and tourist activities; intercity transport is separate. Local code
adds unambiguous labelled hotel/flight totals, computes full vs remaining costs,
checks inclusive trip-day coverage and uses dated FX. Missing prices stay missing.
These are approximate planning allowances, not live quotes or embassy minimums.
The latest verified applicant-owned balance is compared separately by account;
multiple accounts are never automatically added together.

For translated supporting evidence, the Arabic original is the comparison
reference. Translation errors need both original Arabic and English passages
for the same document/person/event; missing languages/unreadable text means
verification, not a confirmed translation error. Normal transliteration variants
alone are not defects. Visual quotations are explicitly labelled for manual checking.

## Configuration

Apply `supabase/migrations/202610270001_gemini_review.sql` to the existing project
before enabling Gemini. It preserves customer review history and adds a separate
metadata-only ledger. Do not rerun historical schema files on an existing database.

Set server-only `GEMINI_API_KEY` from a billing-enabled Google project in `.env`
or Streamlit secrets. The primary model is `gemini-3.8-flash`, with
`gemini-3.6-flash` as the default `GEMINI_FALLBACK_MODEL`. Both have verified
standard pricing snapshots. `USD_EGP_RATE` is optional. If blank, a
cached public EUR-based exchange feed supplies EGP/USD with its rate date. If the
feed is unavailable the USD cost is retained and EGP is unknown, never zero.
Google paid-service data terms apply to sent content; the application does not
promise zero provider retention. No key is sent to the user's browser.

A submitted review runs extraction, then Gemini automatically when a letter, plan, bank statement or supporting document is present, using the same review allowance. Pure factual-reference file sets make no
Gemini request. If Gemini fails, local findings remain available. A deliberate
AI retry uses a new quota slot; rendering, downloads and cached-result reuse do
not generate another request. The API has a bounded timeout. A primary HTTP 429
without generated candidates or usage metadata can switch once to the fallback.
Before fallback, live access/service status is rechecked and the chosen model and
rates are recorded. The file metadata preserves the attempted models and quota
fallback reason. Other errors, generated/invalid results, and reported usage do
not trigger another request. Two exhausted models stop without a retry loop.

## Allowance

Regular users have at most five review attempts per Cairo
calendar day, resetting at Cairo midnight (including daylight-saving changes).
A smaller saved daily or hourly allowance still applies. Failed attempts count.
The database serializes reservations per user, so multiple tabs/workers cannot
race past the limit. One initial factual+Gemini review consumes one attempt.
Approved Admin and Super Admin accounts have no hourly or daily review cap;
each submission still verifies live access and records an attempt. One reserved
AI review allows one accepted generation, with a bounded quota-only fallback
after a rejected primary request. No additional migration is needed.

## Cost dashboard

Administrators have a dedicated Gemini usage and cost section, filtered by Cairo
date range and user. It shows actual provider input, visible output, thinking,
cached input and USD/EGP cost per request, totals by user and allocations by file.
It also shows average tokens/cost per review and per document, averages by
document type, and individual file rows with the actual model. A calculator
computes input/output cost in USD and EGP from current prices and dated FX even
when the ledger is empty. It never sends a Gemini request or adds fake usage.
Missing figures are excluded from average denominators and remain unknown.
Thinking tokens are charged at output pricing. Cached tokens use their discounted
input rate. Prices and the dated exchange rate are snapshotted with every request,
so later changes never reprice historical usage. Costs exclude tax and card fees.

Gemini meters the combined request, not each document. Per-file input/output and
cost shares are ESTIMATES allocated by UTF-8 byte size of the actual sent document
context; shared instructions and generated output are distributed proportionally.
They reconcile with actual request totals but are not provider measurements.
No per-file token count is represented as an exact Google bill.

The durable ledger is reserved before any paid request. Usage is recorded before
parsing/validating findings, including blocked, truncated or malformed responses.
A network timeout with no provider metadata stays unknown; it is not a zero-cost
request. Revoking a user during generation blocks their private result while
retaining the incurred usage. Metadata includes filenames, user/review IDs,
tokens, status and rate snapshots; no prompts, extracted text, model responses or
API keys are stored there. Existing historical provider ledgers remain separate.

## Verification

Run `python -m pytest tests -q` and `python -m pip check`.
Contract/HTTP tests use synthetic documents and mock Gemini transport; they do
not measure model reasoning accuracy. A live integration check requires the paid
API key and applied database migration. No real customer documents are used in
smoke checks. Development smoke calls run outside the per-user application ledger.
The latest synthetic generation checks still timed out; live end-to-end operation
is not yet validated. The observed Google project was on Free tier; configure a
billing-enabled project before sending real customer information.

Provider references:
- https://ai.google.dev/api/generate-content
- https://ai.google.dev/gemini-api/docs/structured-output
- https://ai.google.dev/gemini-api/docs/pricing
- https://ai.google.dev/gemini-api/terms
