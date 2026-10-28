# Belgium portal application

This adapter is enabled only when the selected review country is `belgium` and
the upload category is `visa_form`. The country travels from `app.py` through
`review_pipeline.py` and `extractor.py`; neither a filename nor a printed
destination can enable this adapter in another workspace. Other countries retain
their existing extraction path. Belgium application uploads do not fall back to
Spain coordinates when the portal layout cannot be recognized.

`portal_application.json` maps the structure inspected in the user's seven-page
image-based application and separate question 22 screenshot. No customer answers,
images or source PDFs are included in the map. The screenshot describes structure,
not completed employment data.

The reader verifies distinctive numbered labels and portal section headings,
then locates visible input rectangles. It does not require seven pages or fixed
field coordinates, so the conditional employer section can expand onto another
page. Native PDF text and local OCR use the same positioned field mapping. No
external AI service receives the uploaded documents.

## Occupation and employer details

- Question 21 maps to `occupation.current`.
- Question 22 maps type, name, street, separate house number, postal code, city,
  country, email and telephone under `employment_or_education`.
- Employer address is composed only from question 22 address components. Home
  address (19), host/accommodation (30), inviting organisation (31), and financing
  applicant (32) remain separate.
- Type retains the selected employer/education role. It does not mean a job title.
- `Enter`, `Choose` and the phone placeholder are not applicant answers.

Identity, passport dates, travel dates, destination, occupation and employer
name/address feed the existing canonical application model and review rules.
Additional mapped fields and their original page/rectangle/read method remain in
the local extraction report. Split birth dates normalize from day, month and
four-digit year; no character repair or guessed dates are allowed.

Low-confidence OCR, invalid dates, duplicate labels, missing controls and incomplete
address readings remain unverified. In image controls, no recognized text alone
does not prove an empty answer. Radio/checkbox selections are mapped as requiring
visual verification; printed options do not become selected answers. Collapsed
or absent conditional controls are `not_present`, not extracted values.

The supplied PDF and the employer screenshot were checked locally. Completed
employer values are covered by fictional regression examples, since the supplied
question 22 screenshot is blank. Real filled employer samples remain useful for
validating more portal render/export variants.

Run the regressions:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_belgium_extraction.py tests/test_local_review_pipeline.py tests/test_review_submission.py
```
