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
        # With no actual letter, unconstrained generated prose can fabricate a sponsor,
        # funding arrangement or return obligation. Build factual templates below instead.
        suggestions = [] if key=='cover_letter' and not section.present else section.recommendations
        for edit in suggestions:
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
            if edit.action=='verify' and any(word in edit.reason.casefold() for word in
                    ('holiday','opening hours','عطلة','عطل','ساعات العمل','مواعيد العمل')):
                edit=edit.model_copy(update={'reason':t('write_calendar_verify',lang),
                                            'replacement':t('write_calendar_action',lang)})
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
                    if field=='ties_to_home_country' and data.employment.evidence_type=='education':
                        advice='write_student_ties'
                    replacement=None
                    if not section.present:
                        if field=='purpose_of_visit':
                            replacement=t('write_purpose_grounded',lang,country=data.main_schengen_destination or '[country]',
                                start=data.visa_form.intended_arrival or '[arrival]',end=data.visa_form.intended_departure or '[departure]')
                        elif field=='funding_source':replacement=t('write_funding_placeholder',lang)
                        elif field=='ties_to_home_country':replacement=t('write_ties_placeholder',lang)
                    edits.append(WritingRecommendation(action="add",reason=t(advice,lang),replacement=replacement))
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
            from validator import application_window
            from datetime import timedelta
            start,end=application_window(data)
            dates={_parse_date(day.date) for day in section.days}
            dates.discard(None)
            if start and end and start<=end and section.days:
                covered={day for day in dates if start<=day<=end}
                if len(covered)!=(end-start).days+1 or any(day<start or day>end for day in dates):
                    edits.append(WritingRecommendation(action="verify",reason=t("write_plan_dates",lang)))
            if section.start_date and start and _parse_date(section.start_date)!=start or section.end_date and end and _parse_date(section.end_date)!=end:
                edits.append(WritingRecommendation(action="verify",reason=t("write_plan_dates",lang)))
            if start and end and 0<=(end-start).days<=366:
                for day,time,kind in [(start,data.flight.arrival_time,'arrival'),(end,data.flight.return_departure_time,'departure')]:
                    if time and not any(edit.day==str(day) for edit in edits):
                        edits.append(WritingRecommendation(action='verify',day=str(day),
                            reason=t('write_flight_day_'+kind,lang,time=time),
                            replacement=t('write_flight_day_'+kind+'_fix',lang,time=time)))
                by_date={_parse_date(day.date):day for day in section.days if _parse_date(day.date)}
                advice_count=0
                for offset in range((end-start).days+1):
                    if advice_count>=14: break
                    current=start+timedelta(days=offset)
                    day=by_date.get(current)
                    hotels=[h for h in data.hotel if (a:=_parse_date(h.check_in_date)) and (b:=_parse_date(h.check_out_date)) and a<=current<b]
                    stay="; ".join(" · ".join(v for v in (h.city,h.hotel_name) if v) for h in hotels)
                    if day is None or not day.activities or not day.city:
                        advice_count+=1
                        edits.append(WritingRecommendation(action="add",day=str(current),reason=t("write_specific_day",lang,day=str(current)),
                            replacement=t("write_day_structure",lang,day=str(current),stay=stay or t("unknown",lang))))
                    previous=by_date.get(current-timedelta(days=1))
                    if day and previous and day.city and previous.city and day.city.casefold()!=previous.city.casefold() and not day.transport:
                        advice_count+=1
                        edits.append(WritingRecommendation(action="verify",day=str(current),reason=t("write_transfer",lang,day=str(current),origin=previous.city,destination=day.city)))
        result[key] = edits
    return result
