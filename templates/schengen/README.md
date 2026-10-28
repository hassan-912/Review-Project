# Additional Schengen application templates

Requested destinations: France, Germany, Netherlands, Italy, Sweden, Belgium and Greece.
All requested destinations have tourism upload/review workspaces. Spain keeps its existing
verified templates. Belgium additionally has a category-specific portal reader documented
in `templates/belgium/README.md`, mapped from the supplied application and employer section.
Other country-named blank and completed application PDFs still need
inspection and independent extraction verification. The shared pipeline accepts only mapped
layouts that pass page, label and alignment verification; unfamiliar forms remain unverified.
Do not apply Spain's coordinates to another layout or select a parser from its filename alone.

All application adapters must return the same canonical fields:

- `applicant.given_names`, `applicant.surname`, `applicant.place_of_birth`, `applicant.date_of_birth`.
- `travel_document.number`, `travel_document.issue_date`, `travel_document.expiry_date`.
- `journey.intended_arrival`, `journey.intended_departure`.
- `occupation.current`, `employment_or_education.name`, `employment_or_education.address`.

Independently read the application and compare identity fields with the passport. Compare
hotel guest and flight traveller names with the passport/application. Compare hotel check-in
and check-out and flight dates with application arrival/departure and with one another.
For overnight/transit flights, establish the actual destination arrival date rather than
assuming it is the outbound departure date; unsupported itineraries need manual verification.
Do not reintroduce accommodation coverage or internal missing-night rules.

Compare application occupation and company address with HR evidence. Company address means
the employer address only: never compare it with the applicant's home address. Explicit HR
company-address labels are supported locally; ambiguous shared application cells, scans,
conflicts and unconfirmed cross-language equivalences remain unverified.

National ID translation and Bank declaration are Spain-only upload sections and are not
requirements for the seven additional destinations in this workflow. Other shared document
slots and the existing local-only review process remain unchanged.
