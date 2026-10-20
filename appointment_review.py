"""Agency planning buffer after an evidenced appointment; not a consular rule."""
from datetime import timedelta
import re

from document_sources import source_is_grounded

APPOINTMENT_BUFFER_DAYS = 60


def ground_appointments(data, uploaded):
    """Discard invented sources/quotes and make unreadable supplied letters visible."""
    from extractor import AppointmentInfo
    from validator import _parse_date
    valid = []
    supplied = {name for name, _ in uploaded.get('appointment', [])}
    for item in data.appointments:
        source = item.model_dump()
        parsed = _parse_date(item.appointment_date)
        # A quoted issue date must not be relabelled as a different appointment date.
        dates = re.findall(r'\b(?:\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[/.-]\d{1,2}[/.-]\d{4})\b', item.text or '')
        quoted = {_parse_date(value.replace('.', '/')) for value in dates}
        if source_is_grounded(source, uploaded) and parsed and (not dates or parsed in quoted):
            valid.append(item)
        elif item.source_file in supplied:
            valid.append(item.model_copy(update={'appointment_date': None}))
    known = {item.source_file for item in valid}
    valid.extend(AppointmentInfo(source_file=name) for name in sorted(supplied - known))
    data.appointments = valid


def appointment_issues(data):
    from validator import ValidationIssue, Severity, _parse_date
    if not data.appointments:
        return []
    issues = []
    dated = [(item, _parse_date(item.appointment_date)) for item in data.appointments]
    if any(day is None for _, day in dated) or len({day for _, day in dated if day}) > 1:
        issues.append(ValidationIssue(document_name='Embassy Appointment', field_name='appointment_date',
            found_value=', '.join(item.appointment_date or 'Unreadable' for item, _ in dated),
            expected_value='One verified current appointment date', severity=Severity.HIGH, affects_score=False,
            message_key='appointment.unverified', title_en='Verify the embassy appointment date',
            title_ar='تحقق من تاريخ موعد السفارة',
            recommended_fix='Confirm the current appointment date from a readable letter before accepting the travel-date buffer.',
            fix_ar='أكد تاريخ الموعد الحالي من خطاب واضح قبل اعتماد المدة الفاصلة بين الموعد والسفر.'))
        # Conflicting appointments do not establish a date on which to base a deduction.
        return issues
    appointment, day = dated[0]
    earliest = day + timedelta(days=APPOINTMENT_BUFFER_DAYS)
    starts = [('Visa Application Form', 'intended_arrival', data.visa_form.intended_arrival),
              ('Flight Reservation', 'departure_date', data.flight.departure_date)]
    starts.extend((f'Hotel Reservation ({i + 1})', 'check_in_date', hotel.check_in_date)
                  for i, hotel in enumerate(data.hotel))
    for document, field, value in starts:
        start = _parse_date(value)
        if start is None or start >= earliest:
            continue
        gap = (start - day).days
        reference = dict(source_file=appointment.source_file, page=appointment.page,
                         field_name='appointment_date', value=appointment.appointment_date,
                         text=appointment.text or appointment.appointment_date)
        issues.append(ValidationIssue(document_name=document, field_name=field, found_value=value,
            expected_value=f'{earliest.isoformat()} or later', severity=Severity.HIGH,
            message_key='appointment.buffer', title_en='Travel starts too soon after the appointment',
            title_ar='بداية السفر قريبة جداً من موعد السفارة', reference_evidence=[reference],
            recommended_fix=f'You should pick a later travel date: {earliest:%d/%m/%Y} or later. '
                f'This start is {gap} days after the appointment on {day:%d/%m/%Y}; '
                f'our service requires at least {APPOINTMENT_BUFFER_DAYS} calendar days. '
                'Update the visa form, flight and hotel dates together. This is our planning rule, not an embassy guarantee.',
            fix_ar=f'يجب اختيار موعد سفر أبعد: {earliest:%d/%m/%Y} أو بعده. '
                f'هذه البداية بعد الموعد بتاريخ {day:%d/%m/%Y} بمقدار {gap} يوماً؛ '
                f'تشترط خدمتنا {APPOINTMENT_BUFFER_DAYS} يوماً تقويمياً على الأقل. '
                'حدّث تواريخ نموذج التأشيرة والطيران والفندق معاً. هذه قاعدة تخطيط لخدمتنا وليست ضماناً من السفارة.'))
    return issues
