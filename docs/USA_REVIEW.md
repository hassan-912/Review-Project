# USA review

Select USA to upload exactly DS-160, hotel booking(s), passport and client form.
Canada and UK remain unavailable. USA has its own local pipeline and results UI;
it never calls Gemini, requests FX rates, or runs Schengen validation/narrative rules.
Regular accounts retain the server-side five-review daily quota; approved Admin
and Super Admin accounts have no hourly or daily cap. Live action checks still apply.
There is no additional database migration or dependency to install.

## Reading

- DS-160: full native CEAC application/review printouts, including separate answer
  columns and numbered social-media/language answers. A confirmation page alone
  cannot establish the application answers.
- Client form: the inspected bilingual U.S. Visa Client Information Form tables,
  plus explicit labelled text. Answer cells are read separately from labels.
  Appointment-account passwords and security answers are outside the whitelist.
  Checked boxes are read; missing/ambiguous checkmarks remain unverified. A list
  of unchecked Yes/No choices must never become a claimed answer.
  Both leading boxes and trailing ticks are supported, including ticks after an
  Arabic translation. The mark is associated with that bilingual label rather
  than the next English option. Conflicting or ambiguous marks remain unverified.
- Passport: explicit labelled text and the existing inspected Egyptian passport
  layout/MRZ reader. Unsupported images/OCR-only readings require verification;
  passport dates/centuries are never inferred from the application.
- Hotel: core booking checks use hotel name, check-in and check-out. Explicit labelled text is
  supported, along with the inspected Booking.com and Hotels.com layouts.
  Guest names, prices and cities are not hotel checks for USA. Separately, the
  configured hotel-contact workflow compares a DS-160 personal/relative contact
  with the supplied hotel's organization/contact details. Its expected hotel name,
  address, phone and email come only from printed property details on the booking;
  missing details remain unverified. Guest/confirmation-recipient emails are never
  used as hotel emails. This is an application workflow rule, not a quoted visa rule.
  Missing header years are accepted only when same-booking cancellation dates,
  both printed weekdays and the nights count establish one consistent interval.
  Years are never borrowed from DS-160, other documents or the current date.

PDF, Word, HTML, text and existing image formats use the shared local ingestion.
Native Word/HTML citations point to text sections, not invented PDF page numbers.
Unreadable/ambiguous fields cannot establish a confirmed mismatch. Unknown
templates remain incomplete rather than silently passing. There is a 180-page
USA packet limit and a 400,000-character text limit per document.

## Comparisons and output

DS-160 identity/passport fields are checked against the passport and readable
client fields. Supported client comparisons include personal/contact details,
national ID, birth location, employment and salary/income, education, parents,
languages, sponsor, social accounts and overlapping travel/family/history answers.
These are source-text comparisons, not verification of authenticity or eligibility.
Different salary/income bases and possible spelling/transliteration variants are
flagged for verification rather than automatically corrected.

Hotel names and stay dates are checked against the booking, not required from the
client form. Client-form hotel names and arrival/departure dates are excluded from
these comparisons. A U.S. contact organization
may be abbreviated or may be a different entity; this is not automatically a hotel
name error. Hotel coverage handles multiple stays and year rollover. An explicit
DS-160 departure is used directly. For a stated number of days without departure,
inclusive calendar days and nights are both considered; a one-night discrepancy
must not be invented from an unstated counting convention. The JSON records the
possible departure dates and source of the derivation.

Confirmed differences show source evidence; incomplete checks have
separate verification notes. Downloads provide the structured JSON review and a
corrections-only PDF. Parsed data remains in the browser session's bounded cache,
not the shared database. Duplicate filenames are disambiguated; identical source
bytes cannot count as independent corroboration. No actual customer documents
or values are committed as fixtures; regression documents use synthetic data.

The website displays source images by default, with the document being checked
on the left and the comparison document on the right in both languages. Text
value cards and the evidence expander are removed. When DS-160 and the client form agree on
the applicant but the passport name and number identify someone else, show one
wrong-passport problem instead of recommending changes to the agreed application.
If the photo's MRZ is incomplete, this remains a prominent **possible wrong
passport** warning, not a confirmed OCR finding. Visual labels/columns keep sex,
nationality, DOB and issue/expiry dates separate and preserve multi-line names.
Other uncertain comparisons remain in a collapsed table instead of repeated
generic explanations. Source screenshots are displayed directly in each finding.
The table/export separates the checked value, comparison value, checked document
and comparison document. Document columns identify filenames plus page or native
text section. Coverage instructions are not presented as quoted comparison values.
Hotel-contact evidence shows the DS-160 section on the left and hotel-booking
evidence on the right. The bilingual client form is read from native Word/HTML
table rows as well as PDF table cells, with the same credential-field exclusions.
Native Word/HTML evidence is shown as an image of the exact original text section,
labelled as converted text evidence. It does not claim to preserve the original
page layout. The source bytes and section must corroborate the quote before an
image is rendered.

Run `python -m pytest tests/test_usa_review.py tests/test_usa_templates.py -q`.
