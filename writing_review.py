"""Practical writing advice kept separate from deterministic scoring."""
import re
from extractor import WritingRecommendation
from i18n import t


def _text(value):
    return re.sub(r"\s+", " ", value or "").strip()


def _section_text(text, key):
    """Use explicit section headings when available, never infer a type from filename."""
    headings=re.compile(r"(?im)^\s*(cover(?:ing)? letter|motivation letter|travel plan|travel itinerary|day[- ]by[- ]day itinerary|itinerary|الخطاب التوضيحي|خطاب توضيحي|خطاب تغطية|خطة الرحلة|خطة السفر|برنامج الرحلة)\s*[:\-]?\s*$")
    matches=list(headings.finditer(text))
    if not matches:
        return None
    cover={'cover letter','covering letter','motivation letter','الخطاب التوضيحي','خطاب توضيحي','خطاب تغطية'}
    chunks=[]
    for index,match in enumerate(matches):
        kind='cover_letter' if match.group(1).lower() in cover else 'travel_plan'
        if kind==key:
            chunks.append(text[match.end():matches[index+1].start() if index+1<len(matches) else len(text)])
    return '\n'.join(chunks) if chunks else ''


def writing_recommendations(data, lang="en", source_texts=None):
    result = {}
    for key,section in (("cover_letter",data.cover_letter_text),("travel_plan",data.travel_plan)):
        edits = []
        sources={}
        for name in section.source_files:
            raw=(source_texts or {}).get(name)
            chunk=_section_text(raw,key) if raw is not None else None
            sources[name]=chunk if chunk is not None else section.source_text or ''
        for edit in section.recommendations:
            if edit.source_file and edit.source_file not in section.source_files:
                continue
            if edit.action in ("replace","remove"):
                quote = _text(edit.original_text)
                # Reject invented/cross-section quotes. For text PDFs verify against the
                # actual uploaded text too. Vision-only quotations still need human review.
                if not quote or quote not in _text(sources.get(edit.source_file,section.source_text)):
                    continue
                if source_texts is not None and edit.source_file in source_texts:
                    if quote not in _text(source_texts[edit.source_file]):
                        continue
            edits.append(edit)
        # Catch literal unfinished template markers even if the model overlooks them.
        # For combined text PDFs the marker must belong to this heading-delimited section.
        placeholder=re.compile(r"\bINSERT(?: YOUR)? [A-Z][A-Z ]{1,60} HERE\b|\[(?:APPLICANT NAME|CLIENT NAME|NAME|DATE|COUNTRY|CITY)\]")
        for name,text in sources.items():
            for match in placeholder.finditer(text):
                quote=match.group()
                if any(e.original_text and quote in e.original_text for e in edits):
                    continue
                if source_texts is not None and name in source_texts and quote not in source_texts[name]:
                    continue
                edits.append(WritingRecommendation(action='replace',source_file=name,original_text=quote,
                    reason=t('write_template',lang),replacement=data.passport.full_name if 'NAME' in quote and data.passport.full_name else None))
        if key == "cover_letter":
            for field,advice in (("purpose_of_visit","write_purpose"),("funding_source","write_funding"),
                                 ("ties_to_home_country","write_ties"),("attached_documents_listed","write_attachments")):
                if not getattr(data.cover_letter,field):
                    edits.append(WritingRecommendation(action="add",reason=t(advice,lang)))
        elif not section.present:
            edits.append(WritingRecommendation(action="add",reason=t("write_itinerary",lang)))
        else:
            if not section.start_date or not section.end_date:
                edits.append(WritingRecommendation(action="add",reason=t("write_plan_dates",lang)))
            if not section.cities:
                edits.append(WritingRecommendation(action="add",reason=t("write_plan_cities",lang)))
            if not section.days:
                edits.append(WritingRecommendation(action="add",reason=t("write_itinerary",lang)))
            elif any(not day.date or not day.city or not day.activities for day in section.days):
                edits.append(WritingRecommendation(action="add",reason=t("write_plan_activities",lang)))
            from validator import _parse_date
            start,end=_parse_date(data.flight.departure_date),_parse_date(data.flight.return_date)
            dates={_parse_date(day.date) for day in section.days}
            dates.discard(None)
            if start and end and start<=end and section.days:
                covered={day for day in dates if start<=day<=end}
                if len(covered)!=(end-start).days+1 or any(day<start or day>end for day in dates):
                    edits.append(WritingRecommendation(action="verify",reason=t("write_plan_dates",lang)))
            if section.start_date and start and _parse_date(section.start_date)!=start or section.end_date and end and _parse_date(section.end_date)!=end:
                edits.append(WritingRecommendation(action="verify",reason=t("write_plan_dates",lang)))
        result[key] = edits
    return result
