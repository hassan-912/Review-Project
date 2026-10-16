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
    return re.sub(r"[\U0001F000-\U0001FFFF\u2600-\u27BF\uFE0F]", "", str(text)).replace("\x00", "").replace('≥','>=').replace('≤','<=')


def _ltr(text):
    return str(text)


def build_pdf_report(extraction, issues, score_result, biz_result=None, lang="en", client_name="", writing=None, budget=None) -> bytes:
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
        if re.search(r'[\u0600-\u06ff]',text):
            pdf.set_text_shaping(True,direction='rtl')
        else:
            # Reset HarfBuzz between scripts. Keeping it enabled for a Latin row
            # after an Arabic fallback run can drop the reference value entirely.
            pdf.set_text_shaping(False)
        # A fallback run can leave current_font changed while font_family still names
        # the primary family. Force a switch before resetting the primary font.
        pdf.set_font(fallback, "B" if bold else "", size)
        pdf.set_font(primary, "B" if bold else "", size)
        pdf.set_text_color(*color)
        pdf.multi_cell(0, 7 if size < 14 else 10, text, align=alignment,
                       new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def field_row(label,value,size=10):
        if pdf.will_page_break(21):
            pdf.add_page()
        if lang=='ar' or re.search(r'[\u0600-\u06ff]',str(value)):
            # Separate Arabic labels from Latin values: the pinned fallback-font shaper
            # can otherwise drop labels and reorder numeric dates in mixed lines.
            row(label,size,True)
            row(value,size)
        else:
            row(f'{label}: {value}',size)

    row(t("pdf_title", lang), 20, True, (0,103,218))
    row(t("pdf_subtitle", lang), color=(80,96,122))
    pdf.ln(4)
    badge = 'review_incomplete' if score_result.provisional else score_badge(score_result.score)
    row(f'{t("score_title", lang)}: {score_result.score:.0f}% · {t(badge, lang)}', 14, True)
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
    for booking in extraction.booking_statuses:
        row(t('doc_'+booking.category,lang)+': '+t('booking_'+booking.status,lang),10)
    if budget is not None:
        row(t('bank_budget',lang),13,True)
        row(t('budget_scope',lang),9)
        if not budget['balances']:
            row(t('balance_unreadable',lang),10)
        for bank in budget['balances']:
            value=f"{bank['balance']:,.2f} {bank['currency'] or ''}"
            field_row(t('balance_'+bank['balance_type'],lang),value)
            if bank['eur'] is not None:
                field_row(t('balance_eur',lang),f"EUR {bank['eur']:,.2f}",9)
            row(t('budget_'+bank['status'],lang),10)
        for cost in budget['costs']:
            field_row(t('doc_'+cost['category'],lang),f"{cost['amount']:,.2f} {cost['currency']}"+
                (' - '+t('paid_excluded',lang) if cost['paid'] else ''),9)
        field_row(t('budget_total',lang),f"EUR {budget['known_budget_eur']:,.2f}")
        field_row(t('daily_allowance',lang),f"EUR {budget['daily_eur']:,.2f} x {budget['days'] or '?'}")
        if budget['missing']:
            row(t('budget_missing',lang)+': '+', '.join(t('budget_missing_'+key,lang) for key in budget['missing']),9)
        if budget.get('rate_date'):
            row(t('budget_rate_date',lang,date=budget['rate_date']),9)
    findings = [issue for issue in issues if issue.affects_score]
    limitations = [issue for issue in issues if not issue.affects_score]
    if findings and pdf.will_page_break(75):
        pdf.add_page()
    row(t("findings_count", lang, count=len(findings)), 13, True)
    if not findings:
        row(t("no_issues", lang))
    order = {"CRITICAL":0, "HIGH":1, "MEDIUM":2, "LOW":3}
    for issue in sorted(findings, key=lambda x: order[x.severity.value]):
        title, fix = issue_text(issue, lang)
        if pdf.will_page_break(65):
            pdf.add_page()
        pdf.ln(3)
        # Keep source filenames out of the downloaded report.
        label=issue.document_name.split(' (')[0]
        severity_label = t(issue.severity.value.lower(), lang) if issue.affects_score else t('review_limitation', lang)
        row(f'[{severity_label}] {document_label(label, lang)} · {title}', 11, True)
        if issue.found_value:
            field_row(t("found",lang),issue.found_value,9)
        field_row(t("expected",lang),issue.expected_value,9)
        field_row(t("fix",lang),fix,10)
    if limitations:
        pdf.ln(4)
        row(t('review_limitations',lang),13,True)
        row(t('review_limitation',lang),9)
        for issue in limitations:
            row(issue_text(issue,lang)[1],9)
    from writing_review import writing_recommendations
    writing = writing if writing is not None else writing_recommendations(extraction,lang)
    if not any(writing.values()):
        pdf.ln(6)
        row(t('score_note',lang),8,color=(80,96,122))
        return bytes(pdf.output())
    if pdf.will_page_break(80):
        pdf.add_page()
    pdf.ln(4)
    row(t("writing_title",lang),13,True)
    row(t("writing_note",lang),9)
    for category,edits in writing.items():
        row(t("doc_"+category,lang),11,True)
        if not edits:
            row(t("writing_ok",lang))
        for edit in edits:
            if pdf.will_page_break(45):
                pdf.add_page()
            row(t("edit_"+edit.action,lang)+": "+edit.reason)
            if edit.day: field_row(t("day",lang),edit.day,9)
            if edit.original_text:
                field_row(t("original_text",lang),edit.original_text,9)
            if edit.replacement:
                field_row(t("replacement",lang),edit.replacement)
    pdf.ln(6)
    row(t("score_note", lang), 8, color=(80,96,122))
    return bytes(pdf.output())
