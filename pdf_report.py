"""Unicode reports generated entirely in memory; Arabic text uses HarfBuzz shaping."""
from __future__ import annotations
from pathlib import Path
import re
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from i18n import t, issue_text, document_label

FONT_ROOT = Path(__file__).parent / "assets" / "fonts"


def score_badge(score: float) -> str:
    return "score_strong" if score >= 85 else "score_moderate" if score >= 65 else "score_weak"


def _plain(text):
    return re.sub(r"[\U0001F000-\U0001FFFF\u2600-\u27BF\uFE0F]", "", str(text)).replace("\x00", "")


def _ltr(text):
    return str(text)


def build_pdf_report(extraction, issues, score_result, biz_result=None, lang="en", client_name="", writing=None) -> bytes:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    for family in ("NotoSans", "NotoNaskhArabic"):
        for weight, style in (("Regular", ""), ("Bold", "B")):
            pdf.add_font(family, style=style, fname=str(FONT_ROOT / f"{family}-{weight}.ttf"))
    primary = "NotoNaskhArabic" if lang == "ar" else "NotoSans"
    fallback = "NotoSans" if lang == "ar" else "NotoNaskhArabic"
    pdf.set_fallback_fonts([fallback])
    pdf.set_text_shaping(True)
    pdf.add_page()
    alignment = "R" if lang == "ar" else "L"

    def row(text, size=10, bold=False, color=(11,31,58)):
        text=_plain(text)
        # Keep ISO dates in their original order within Arabic sentences.
        if lang=='ar':
            text=re.sub(r'\b\d{4}-\d{2}-\d{2}\b',lambda m:'\u200e'+m.group()+'\u200e',text)
        pdf.set_text_shaping(True,direction='rtl' if re.search(r'[\u0600-\u06ff]',text) else 'ltr')
        pdf.set_font(primary, "B" if bold else "", size)
        pdf.set_text_color(*color)
        pdf.multi_cell(0, 7 if size < 14 else 10, text, align=alignment,
                       new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def field_row(label,value,size=10):
        if lang=='ar':
            # Separate Arabic labels from Latin values: the pinned fallback-font shaper
            # can otherwise drop labels and reorder numeric dates in mixed lines.
            row(label,size,True)
            row(value,size)
        else:
            row(f'{label}: {value}',size)

    row(t("pdf_title", lang), 20, True, (0,103,218))
    row(t("pdf_subtitle", lang), color=(80,96,122))
    pdf.ln(4)
    row(f'{t("score_title", lang)}: {score_result.score:.0f}% · {t(score_badge(score_result.score), lang)}', 14, True)
    row(t(score_result.readiness,lang),11,True)
    row(t("score_note", lang), 9, color=(80,96,122))
    pdf.ln(4)
    row(t("applicant_info", lang), 13, True)
    field_row(t("client_name",lang),client_name or extraction.passport.full_name or extraction.visa_form.applicant_name or t("unknown",lang))
    field_row(t("field_passport_number",lang),extraction.passport.passport_number or t("unknown",lang))
    field_row(t("country",lang),extraction.main_schengen_destination or t("unknown",lang))
    field_row(t("field_departure_date",lang),extraction.visa_form.intended_arrival or extraction.flight.departure_date or t("unknown",lang))
    field_row(t("field_return_date",lang),extraction.visa_form.intended_departure or extraction.flight.return_date or t("unknown",lang))
    pdf.ln(4)
    if extraction.executive_summary:
        row(t("summary", lang), 13, True)
        row(extraction.executive_summary)
        pdf.ln(3)
    row(t("findings_count", lang, count=len(issues)), 13, True)
    if not issues:
        row(t("no_issues", lang))
    order = {"CRITICAL":0, "HIGH":1, "MEDIUM":2, "LOW":3}
    for issue in sorted(issues, key=lambda x: order[x.severity.value]):
        title, fix = issue_text(issue, lang)
        pdf.ln(3)
        label=issue.document_name.split(' (')[0] if lang=='ar' else issue.document_name
        row(f'[{t(issue.severity.value.lower(), lang)}] {document_label(label, lang)} · {title}', 11, True)
        if issue.found_value:
            field_row(t("found",lang),issue.found_value,9)
        field_row(t("expected",lang),issue.expected_value,9)
        field_row(t("fix",lang),fix,10)
        for location in issue.evidence:
            field_row(t("source",lang),location["source_file"]+" · "+str(location["page"]),9)
    from writing_review import writing_recommendations
    writing = writing if writing is not None else writing_recommendations(extraction,lang)
    pdf.ln(4)
    row(t("writing_title",lang),13,True)
    row(t("writing_note",lang),9)
    for category,edits in writing.items():
        row(t("doc_"+category,lang),11,True)
        if not edits:
            row(t("writing_ok",lang))
        for edit in edits:
            row(t("edit_"+edit.action,lang)+": "+edit.reason)
            if edit.day: field_row(t("day",lang),edit.day,9)
            if edit.source_file:
                field_row(t("source",lang),edit.source_file+(f" · {edit.page}" if edit.page else ""),9)
            if edit.original_text:
                field_row(t("original_text",lang),edit.original_text,9)
            if edit.replacement:
                field_row(t("replacement",lang),edit.replacement)
    pdf.ln(6)
    row(t("score_note", lang), 8, color=(80,96,122))
    return bytes(pdf.output())
