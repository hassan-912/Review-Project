"""Validate model claims against this exact request, never another customer's file."""
import re
import unicodedata

from .contracts import ModelReview, Packet


def normalized(text):
    # Preserve letters, numbers and negations; tolerate only whitespace/Unicode layout.
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', text)).strip()


def validate_review(packet, response):
    packet = Packet.model_validate(packet) if not isinstance(packet, Packet) else packet
    response = ModelReview.model_validate(response)
    if response.request_id != packet.request_id:
        raise ValueError('Review belongs to another document set')
    docs = {doc.id: doc for doc in packet.documents}
    pages = {(doc.id, page.number): page for doc in packet.documents for page in doc.pages}
    attached={a.document_id for a in packet.attachments}
    def valid_source(citation):
        value=citation.model_dump() if hasattr(citation,'model_dump') else citation
        key=value['document_id'],value['page']
        return bool(key in pages and (value.get('visual') and key[0] in attached or
            not value.get('visual') and normalized(value['quote']) in normalized(pages[key].text)))
    notes = list(dict.fromkeys(packet.limitations + response.limitations))
    accepted = []
    rejected = 0
    seen = set()
    for finding in response.findings:
        citations = finding.citations
        valid = all(valid_source(citation) for citation in citations)
        # A narrative finding must quote the actual letter/plan, not just a passport.
        target = any(finding.section in docs[c.document_id].categories for c in citations if c.document_id in docs)
        if not valid or not target:
            rejected += 1
            continue
        provisional = any(c.visual or pages[c.document_id, c.page].provisional or pages[c.document_id, c.page].method == 'unreadable'
                          for c in citations)
        if finding.kind=='translation_error':
            arabic=[c for c in citations if re.search(r'[\u0621-\u064a]',c.quote)]
            english=[c for c in citations if len(re.findall(r'[A-Za-z]',c.quote))>=4]
            if finding.section!='supporting' or not any(a.quote!=e.quote for a in arabic for e in english):
                provisional=True
        distinct = {(c.document_id, c.page, normalized(c.quote)) for c in citations}
        if provisional or finding.kind == 'contradiction' and len(distinct) < 2:
            finding = finding.model_copy(update={'kind': 'needs_verification'})
        key = (finding.section, finding.kind, tuple(sorted(distinct)))
        if key in seen:
            continue
        seen.add(key)
        accepted.append(finding.model_dump())
    if rejected:
        notes.append(f'{rejected} proposed findings were rejected because their source quotes or section assignments could not be verified.')
    reported = {(item.document_id, item.page): item.status for item in response.coverage}
    expected = {(doc.id, number) for doc in packet.documents for number in
                ([p.number for p in doc.pages] if doc.context_mode == 'extracted_fields' else range(1, doc.total_pages + 1))}
    covered = {key for key, page in pages.items() if reported.get(key) == 'reviewed'
               and page.text.strip() and page.method != 'unreadable' and not page.provisional}
    from .assessments import assess
    banks,bank_flags,budget,financial_notes=assess(packet.model_dump(),response.bank_assessments,
                                                response.budget_proposal,valid_source,covered,response.salary_reference,
                                                {key for key,status in reported.items() if status=='reviewed'})
    notes.extend(financial_notes)
    complete = (response.status == 'complete' and expected <= covered and not packet.limitations and not rejected and not financial_notes
                and not any(f['kind']=='needs_verification' for f in accepted))
    if expected - covered:
        notes.append('Some in-scope pages were not read confidently. This review cannot establish that the complete file is consistent.')
    # No AI finding changes the deterministic score. Grounding checks establish
    # source provenance, not that a language model's semantic judgement is correct.
    return dict(version=response.version, request_id=response.request_id,
                status='complete' if complete else 'incomplete', findings=accepted,
                coverage=[dict(document_id=key[0], page=key[1], status=reported.get(key, 'not_reviewed'))
                          for key in sorted(expected)], limitations=list(dict.fromkeys(notes)),
                rejected_findings=rejected, scored=False,bank_assessments=banks,bank_flags=bank_flags,trip_budget=budget)
