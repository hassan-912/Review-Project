# Spain blank PDF reference maps

These maps describe the **three blank PDF references supplied on 2026-10-21**.
All five source pages were rendered and visually inspected. The source PDF files are
not copied into the repository. Fingerprints identify these exact reference versions;
they are not a promise that every Spain/Schengen form revision has the same layout.

- `blank_values.json`: the complete key/value inventory across all three references.
- `schengen_application.json`: all 32 questions expanded into 95 keys, including 15
  separate official-use keys and the unnumbered photo/place/date/signature areas.
  The additional key beside question 32 preserves a typed funding note without treating
  it as a printed label, balance or inferred booking price.
- `bank_declaration.json`: 7 keys, preserving applicant and bank-holder roles separately.
- `national_id_translation.json`: 11 keys, preserving front ID and full ID independently.

Each field records its canonical key, label, question number when applicable, subject
role, value type, options/conditions, 1-based page, PDF-point and normalized region,
and exact baseline region text. Composite fields deliberately share answer regions;
they cannot be reliably split until the completed examples are inspected. Full original
page text is retained in `baseline_pages`; its instructions and declarations are source
content, never instructions to the extraction program.

All entered values in these blank references are `null`. Checkbox options are available
choices, not selected answers; `null` does not mean an answered "No". The bank declaration
contains preprinted **CAIRO**, recorded as `declaration.place` with `value_status=preprinted`.
Photo and signatures are mapped as presence checks, not transcribed text or authenticity.
In particular, the bank declaration has no account-number, balance, bank-name or phone/email
entry fields, and the ID translation has no passport-number field. Those are not invented.

Important question mappings in this exact application:

- 11: applicant national identity number.
- 13: travel document/passport number.
- 14 / 15: travel document issue / expiry.
- 19: applicant home address, email and telephone.
- 21 / 22: occupation and employer OR educational establishment details.
- 25 / 26: destination Member States / first entry.
- 27: entries requested, intended arrival AND intended departure.
- 30 / 31: inviting person/accommodation and inviting company/contact details.
- 32: funding, continuing onto page 3 with applicant and sponsor options separated.

The conditional EU/EEA/CH family-member exemption printed on the template is retained for
questions 21, 22, 30, 31 and 32. These maps are not a new legal requirements checklist.

## Reproduce the mapping

From the project root, using the existing environment:

```powershell
.\.venv\Scripts\python.exe scripts/map_spain_templates.py --source-dir 'C:\Users\Menna\Downloads' --output-dir templates/spain
```

This command accepts only the fingerprinted blank references. It intentionally rejects
filled or replaced PDFs so an entered answer cannot accidentally be exported as `null`.

## Offline extraction pilot

`spain_pdf_extractor.py` now reads the supplied completed forms independently using their
visible FreeText annotations or flattened text additions. Baseline labels and preprinted
defaults are excluded from `filled_values`; `all_values` retains nulls for blank answers.
Marked choices are assigned by their original checkbox positions. Dates gain separate ISO
normalized values; original text, page, location and method remain attached as evidence.
New image/vector content overlapping an answer is marked for OCR/visual verification.
Different layouts and scanned forms fail closed rather than returning a false blank/pass.
Company/guardian answers that cannot be reliably split remain explicitly provisional.

Extract only the three forms:

```powershell
.\.venv\Scripts\python.exe scripts/extract_spain_forms.py --source-dir '<filled-forms-folder>'
```

The optional full pilot additionally reads Hotels.com hotel template 1, Egyptair flight
template 1, and the supplied Egyptian passport layout. Install `requirements-ocr.txt` to
enable local CPU OCR; the live app's dependency list and review pipeline are not changed.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-ocr.txt
.\.venv\Scripts\python.exe scripts/run_spain_pilot.py --source-dir '<filled-forms-folder>' --passport '<passport-image>'
```

Output goes to ignored `output/spain_extraction/` or `output/spain_pilot/`. Completed
customer values, OCR text and images must remain out of version control. Only blank
reference maps and synthetic regression tests belong in this folder/repository.

The full pilot prints each mismatch and unverified comparison with both document/field
names and their extracted values. It also saves this explanation as `review_report.txt`;
`comparisons.json` includes the same readable labels/messages for future UI integration.
Input paths are validated and all files are read before OCR starts, so a missing passport
does not waste a completed PDF/OCR run.

Hotel dates are taken from the stay header and checked against the labelled check-in/out;
cancellation deadlines and price dates are excluded. Hotel guest names come from Reserved
for. Flight routes/dates/times come from Itinerary, and names come from Traveller, not
Reservation name. The first Egyptair pilot supports a direct Cairo round trip for one adult;
overnight, multi-leg and multi-traveller cases require further validation. Barcelona/Madrid
country mapping is explicitly a city-reference inference, not printed ticket data.

Passport name, number, birth and expiry are read from the MRZ; check digits and printed
number/dates are cross-checked. Issue date and place of birth come from visual fields.
No O/0 or I/1 correction, name expansion or century guessing is allowed. Booking names
must match exact full given names plus surname OR first given name plus the full surname.
An OCR confidence or checksum pass is not document authentication. Arabic visual passport
names, signatures and other booking layouts are not yet supported by the pilot. The printed
national-ID number on the supported Egyptian passport is read separately with local Arabic
OCR; unreadable/conflicting readings remain unverified.

The website review entry point now uses these local parsers. Unknown templates and uncertain
fields remain unverified. Cover-letter/travel-plan content requires manual review; no
uploads are sent to an external AI service. Spain provides separate National ID translation
and Bank declaration upload cards, connected to these local template readers.

## HR evidence: one letter or separate files

`hr_extractor.py` combines employee name, company/employer organization, job title,
leave start/end and explicit leave approval from one combined letter or multiple PDFs.
Net/gross salary and currency are recorded only where supplied, not compared to invented
visa-form salary fields. Employee, employer organization and approver/signer remain separate.
Leave must cover the entire travel period; it may begin earlier and end later.
Each value keeps its original file, page, location, raw text, reading method and confidence.
Conflicting readings across files remain unresolved rather than taking the first answer.

Native text is read directly. Arabic scans use optional local RapidOCR PP-OCRv5 Arabic
recognition; public OCR weights download during first setup, with document reading on the
local computer and zero Gemini/API inference requests. English scans can use `--language en`.
The existing passport/flight OCR engine is unchanged.

The supplied Arabic salary sheet, handwritten leave request and handwritten employment
status sheet were rendered and inspected. Printed organization/salary readings are useful,
but the handwritten leave dates, job title and approval are not reliably read by this OCR
model. **Scanned HR readings remain provisional and cannot silently pass validation.**
A leave-request title, a signature box or a stamp alone does not prove approval.
Arabic/English names, occupations and companies require a confirmed translation/reference;
there is no fuzzy transliteration or customer-specific alias that forces a match.

Test HR alone without repeating flight/passport OCR:

```powershell
.\.venv\Scripts\python.exe scripts/extract_hr.py --application '<visa-application.pdf>' --hr '<salary.pdf>' '<leave.pdf>' '<employment-status.pdf>' --output-dir output/hr_pilot
```

For a single letter, pass just one path after `--hr`. Generic labelled native-text letters
are covered by synthetic tests; an additional real combined-letter layout still needs its
own sample validation. The full `run_spain_pilot.py` also accepts `--hr` and `--hr-language`.
HR is optional so existing runs without HR retain their original checks.

Outputs include `hr_evidence.json`, `hr_values.json`, `hr_comparisons.json` and a readable
`review_report.txt`. `hr_review_template.json` provides an optional confirmation workflow:
copy it to a separate private file, read the originals, enter each confirmed value and its
source filename/page, and set that field's `confirmed` to `true`. Dates accept ISO or
unambiguous four-digit-year day/month/year formats; approval must be JSON `true` or `false`.
Rerun HR-only with `--reviewed-values '<confirmed.json>'`, or the full pilot with
`--hr-reviewed-values '<confirmed.json>'`. The original input hashes must match, and the
unconfirmed OCR candidates remain attached as evidence. This is manual confirmation, not
an automatic OCR success. Do not reuse a confirmation file after changing source PDFs.

The website now includes these local OCR dependencies. The same HR uncertainty and provenance
rules apply in website reports; there is no Gemini fallback for HR or other factual documents.
