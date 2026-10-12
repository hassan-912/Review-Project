"""English and Modern Standard Arabic copy for the entire interface."""
from __future__ import annotations

STRINGS = {}


def _add(key, en, ar):
    STRINGS[key] = {"en": en, "ar": ar}


_COPY = [
    ("brand", "MG · Visa File Review", "MG · مراجعة ملفات التأشيرات"),
    ("language", "Language", "اللغة"),
    ("review", "Review", "المراجعة"),
    ("history", "My history", "سجلي"),
    ("admin", "Admin dashboard", "لوحة الإدارة"),
    ("how", "How it works", "كيف تعمل الأداة"),
    ("navigation", "Navigation", "التنقل"),
    ("sign_out", "Sign out", "تسجيل الخروج"),
    ("sign_in", "Sign in", "تسجيل الدخول"),
    ("create_account", "Create account", "إنشاء حساب"),
    ("forgot_password", "Forgot password", "نسيت كلمة المرور"),
    ("email", "Email address", "البريد الإلكتروني"),
    ("password", "Password", "كلمة المرور"),
    ("confirm_password", "Confirm password", "تأكيد كلمة المرور"),
    ("new_password", "New password", "كلمة المرور الجديدة"),
    ("save_password", "Update password", "تحديث كلمة المرور"),
    ("password_changed", "Password updated. Sign in with your new password.", "تم تحديث كلمة المرور. سجّل الدخول بكلمة المرور الجديدة."),
    ("password_mismatch", "Passwords must match and contain at least 10 characters.", "يجب أن تتطابق كلمتا المرور وأن تتكونا من 10 أحرف على الأقل."),
    ("access_title", "A clearer file. A confident next step.", "ملف أكثر وضوحاً، وخطوة تالية بثقة."),
    ("access_description", "Check identities, travel dates and supporting evidence in one place.", "راجع بيانات الهوية ومواعيد السفر والمستندات الداعمة في مكان واحد."),
    ("internal", "For approved MG team members", "لأعضاء فريق MG المعتمدين"),
    ("pending_title", "Account pending approval", "الحساب بانتظار الموافقة"),
    ("pending_text", "Confirm your email, then an administrator can approve your access.", "أكّد بريدك الإلكتروني، ثم ينتظر حسابك موافقة مسؤول النظام."),
    ("created", "Account created", "تم إنشاء الحساب"),
    ("approval", "Administrator approval", "موافقة المسؤول"),
    ("unlocked", "Review tool unlocked", "إتاحة أداة المراجعة"),
    ("check_status", "Check status", "التحقق من الحالة"),
    ("check_status_hint", "Sign in after email confirmation to check your approval status.", "سجّل الدخول بعد تأكيد البريد الإلكتروني للتحقق من الموافقة."),
    ("signup_success", "Account created. Confirm your email and wait for administrator approval.", "تم إنشاء الحساب. أكّد بريدك الإلكتروني وانتظر موافقة المسؤول."),
    ("login_failed", "Incorrect email or password, or your email is not confirmed.", "البريد الإلكتروني أو كلمة المرور غير صحيحة، أو لم يتم تأكيد البريد بعد."),
    ("auth_unavailable", "Unable to connect to the account service. Please try again shortly.", "تعذّر الاتصال بخدمة الحسابات. يُرجى المحاولة بعد قليل."),
    ("signup_failed", "Unable to create the account. Check your details or try signing in.", "تعذّر إنشاء الحساب. تحقّق من البيانات أو جرّب تسجيل الدخول."),
    ("email_invalid", "Enter a valid email address.", "أدخل عنوان بريد إلكتروني صحيحاً."),
    ("session_expired", "Your session expired — please sign in again.", "انتهت صلاحية الجلسة. يُرجى تسجيل الدخول مجدداً."),
    ("access_revoked", "Your access is pending or has been revoked. Contact your administrator.", "حسابك بانتظار الموافقة أو تم سحب صلاحية الوصول. تواصل مع المسؤول."),
    ("reset_send", "Send reset link", "إرسال رابط إعادة التعيين"),
    ("reset_sent", "If an account exists, you will receive a password reset email.", "إذا كان البريد مرتبطاً بحساب، فستصلك رسالة لإعادة تعيين كلمة المرور."),
    ("reset_unavailable", "Password reset is not configured yet. Contact your administrator.", "إعادة تعيين كلمة المرور غير متاحة حالياً. تواصل مع المسؤول."),
    ("reset_title", "Choose a new password", "اختر كلمة مرور جديدة"),
    ("config_missing", "The service is not configured. Ask the administrator to complete deployment settings.", "لم يكتمل إعداد الخدمة. اطلب من المسؤول استكمال إعدادات التشغيل."),
    ("review_title", "Prepare every detail before submission", "راجع كل التفاصيل قبل تقديم الطلب"),
    ("review_description", "Upload the application package. Get a clear, prioritised fix checklist.", "ارفع مستندات الطلب لتحصل على قائمة واضحة بالتعديلات مرتبة حسب الأولوية."),
    ("client_name", "Client name", "اسم العميل"),
    ("client_placeholder", "Applicant's full name", "الاسم الكامل لمقدم الطلب"),
    ("client_required", "Enter a client name before running the review.", "أدخل اسم العميل قبل بدء المراجعة."),
    ("model", "Analysis model", "نموذج التحليل"),
    ("advanced", "Review settings", "إعدادات المراجعة"),
    ("upload_title", "Application documents", "مستندات الطلب"),
    ("upload_hint", "PDF, JPG, PNG or WebP · 20 MB per file · 75 MB per review · up to 30 files", "PDF أو JPG أو PNG أو WebP · 20 ميجابايت للملف · 75 ميجابايت للمراجعة · حتى 30 ملفاً"),
    ("files_added", "{count} files added", "تمت إضافة {count} ملفات"),
    ("choose_files", "Drop or choose files", "اسحب الملفات أو اخترها"),
    ("privacy", "Documents stay in application memory and are sent to Google Gemini for analysis. We do not save document files to disk or the database. Provider retention terms apply.", "تُعالج المستندات في ذاكرة التطبيق وتُرسل إلى Google Gemini للتحليل. لا نحفظ ملفات المستندات على القرص أو في قاعدة البيانات. تسري شروط الاحتفاظ بالبيانات لدى مزود الخدمة."),
    ("log_notice", "Review history stores the client name, destination, agent and score.", "يحفظ سجل المراجعة اسم العميل والوجهة وموظف المراجعة والدرجة."),
    ("run_review", "Run review", "بدء المراجعة"),
    ("force_refresh", "Reanalyse these documents", "إعادة تحليل المستندات"),
    ("force_help", "Skip this session's saved extraction and run a new analysis.", "تجاوز نتيجة التحليل المحفوظة في الجلسة وإجراء تحليل جديد."),
    ("clear_files", "Clear this file", "مسح هذا الملف"),
    ("upload_invalid", "A file is unsupported, unreadable, password-protected or has too many pages. Upload a readable PDF or image.", "أحد الملفات غير مدعوم أو غير قابل للقراءة أو محمي بكلمة مرور أو يتجاوز حد الصفحات. ارفع ملف PDF أو صورة واضحة."),
    ("upload_limit", "The upload exceeds the file, size or image resolution limits.", "تتجاوز الملفات حدود العدد أو الحجم أو دقة الصورة المسموح بها."),
    ("missing_documents", "Documents not added", "مستندات لم تُرفق"),
    ("missing_hint", "Checks use the supplied evidence. Missing documents can reduce the score.", "تعتمد المراجعة على المستندات المرفقة. قد يؤدي نقص المستندات إلى خفض الدرجة."),
    ("step_read", "Read documents", "قراءة المستندات"),
    ("step_rules", "Rule checks", "فحص الاتساق"),
    ("step_business", "Business alignment", "توافق غرض رحلة العمل"),
    ("step_score", "Review score", "درجة المراجعة"),
    ("done", "Done", "مكتمل"),
    ("in_progress", "In progress", "جارٍ التنفيذ"),
    ("waiting", "Waiting", "بانتظار التنفيذ"),
    ("review_failed", "Review could not be completed.\n\nPlease try again. Reference: {reference}", "تعذّر إكمال المراجعة.\n\nيُرجى المحاولة مجدداً. رقم المرجع: {reference}"),
    ("review_complete", "Review complete", "اكتملت المراجعة"),
    ("cached", "Using the saved result for these documents in this session.", "تُعرض النتيجة المحفوظة لهذه المستندات في الجلسة الحالية."),
    ("stale_result", "The documents or report language have changed. Run a review to update this report.", "تغيّرت المستندات أو لغة التقرير. شغّل المراجعة لتحديث التقرير."),
    ("rate_limited", "Your review allowance has been reached. Try again later or contact your administrator.", "وصلت إلى الحد المسموح للمراجعات. حاول لاحقاً أو تواصل مع المسؤول."),
    ("quota_unavailable", "Review limits could not be verified. Please try again shortly.", "تعذّر التحقق من الحد المسموح للمراجعات. يُرجى المحاولة بعد قليل."),
    ("score_title", "File review score", "درجة مراجعة الملف"),
    ("score_note", "An internal measure of document consistency and completeness. It is not an approval probability.", "مقياس داخلي لاتساق المستندات واكتمالها، وليس احتمالاً للموافقة على التأشيرة."),
    ("score_strong", "Strong file", "ملف قوي"),
    ("score_moderate", "Needs attention", "يحتاج إلى مراجعة"),
    ("score_weak", "Major corrections needed", "يحتاج إلى تعديلات جوهرية"),
    ("urgent", "Your next three actions", "أهم ثلاث خطوات تالية"),
    ("summary", "Executive summary", "ملخص المراجعة"),
    ("summary_fallback", "{count} findings require attention. Review the prioritised checklist before submission.", "توجد {count} ملاحظات تستدعي الانتباه. راجع قائمة التعديلات حسب الأولوية قبل التقديم."),
    ("no_issues", "No inconsistencies were detected in the extracted evidence. Verify the original documents before submission.", "لم يُرصد تعارض في البيانات المستخرجة. تحقّق من المستندات الأصلية قبل التقديم."),
    ("timeline", "Travel date cross-check", "مطابقة مواعيد السفر"),
    ("document", "Document", "المستند"),
    ("start_date", "Start date", "تاريخ البداية"),
    ("end_date", "End date", "تاريخ النهاية"),
    ("status", "Status", "الحالة"),
    ("aligned", "Aligned", "متطابق"),
    ("check", "Check", "يحتاج للتحقق"),
    ("gap", "Gap", "فجوة"),
    ("unknown", "Not available", "غير متاح"),
    ("checklist", "Document fix checklist", "قائمة تعديلات المستندات"),
    ("all", "All findings", "جميع الملاحظات"),
    ("severity", "Severity", "مستوى الأهمية"),
    ("critical", "Critical", "حرج"),
    ("high", "High", "مرتفع"),
    ("medium", "Medium", "متوسط"),
    ("low", "Low", "منخفض"),
    ("issue", "Issue", "الملاحظة"),
    ("fix", "Recommended fix", "التعديل المطلوب"),
    ("found", "Found", "البيانات الموجودة"),
    ("expected", "Reference / requirement", "البيانات المرجعية أو المطلوبة"),
    ("evidence", "Evidence comparison", "مقارنة البيانات"),
    ("download_pdf", "Download PDF", "تنزيل تقرير PDF"),
    ("pdf_failed", "Unable to generate the PDF. Please contact your administrator.", "تعذّر إنشاء تقرير PDF. يُرجى التواصل مع المسؤول."),
    ("pdf_title", "Schengen visa file review", "مراجعة ملف تأشيرة شنغن"),
    ("pdf_subtitle", "MG · Document audit report", "MG · تقرير مراجعة المستندات"),
    ("applicant_info", "Applicant information", "بيانات مقدم الطلب"),
    ("findings_count", "Findings: {count}", "عدد الملاحظات: {count}"),
    ("cover_audit", "Cover letter completeness", "اكتمال الخطاب التوضيحي"),
    ("employment_audit", "Employment documents", "مستندات العمل"),
    ("present", "Present", "موجود"),
    ("missing", "Missing or not confirmed", "غير موجود أو غير مؤكد"),
    ("extracted", "Extracted evidence", "البيانات المستخرجة"),
    ("business_match", "Business purpose matches the professional sector.", "غرض رحلة العمل متوافق مع القطاع المهني."),
    ("business_check", "Review the business purpose and supporting professional evidence.", "راجع غرض رحلة العمل والمستندات المهنية الداعمة."),
    ("tourism", "Destination assessment", "تقييم الوجهة"),
    ("tourism_known", "The destination is recognised by the city reference list.", "الوجهة مدرجة في قائمة المدن المرجعية."),
    ("tourism_check", "Confirm the destination and itinerary using the original bookings.", "تحقّق من الوجهة وخطة الرحلة بالرجوع إلى الحجوزات الأصلية."),
    ("history_description", "Past reviews grouped by client, with the latest result shown.", "المراجعات السابقة مجمّعة حسب العميل، مع عرض أحدث نتيجة."),
    ("history_empty", "You have not reviewed any files yet.", "لم تراجع أي ملفات بعد."),
    ("history_failed", "Unable to load review history. Please try again.", "تعذّر تحميل سجل المراجعات. يُرجى المحاولة مجدداً."),
    ("country", "Country", "الدولة"),
    ("agent", "Agent", "الموظف"),
    ("date", "Date (Cairo)", "التاريخ بتوقيت القاهرة"),
    ("latest_score", "Latest score (%)", "آخر درجة (%)"),
    ("edits_done", "Reviewed more than once", "تمت مراجعته أكثر من مرة"),
    ("yes", "Yes", "نعم"),
    ("no", "No", "لا"),
    ("search", "Search client, country or agent", "البحث باسم العميل أو الدولة أو الموظف"),
    ("page", "Page", "الصفحة"),
    ("log_scope", "Latest {count} reviews", "آخر {count} مراجعات"),
    ("export_csv", "Export displayed reviews", "تصدير المراجعات المعروضة"),
    ("admin_description", "Manage team access and review activity.", "إدارة صلاحيات الفريق ومتابعة نشاط المراجعات."),
    ("total_reviews", "Reviews", "المراجعات"),
    ("pending_count", "Pending approvals", "طلبات بانتظار الموافقة"),
    ("average_score", "Average file score", "متوسط درجة الملفات"),
    ("approval_queue", "Team access", "صلاحيات الفريق"),
    ("approve", "Approve", "موافقة"),
    ("revoke", "Revoke access", "سحب الصلاحية"),
    ("approved", "Approved", "معتمد"),
    ("pending", "Pending", "بانتظار الموافقة"),
    ("access_updated", "Access updated.", "تم تحديث الصلاحية."),
    ("access_update_failed", "Unable to update access. Please try again.", "تعذّر تحديث الصلاحية. يُرجى المحاولة مجدداً."),
    ("review_log", "Team review log", "سجل مراجعات الفريق"),
    ("log_failed", "The report is ready, but history could not be saved.", "التقرير جاهز، لكن تعذّر حفظه في السجل."),
    ("no_results", "No matching results.", "لا توجد نتائج مطابقة."),
    ("how_description", "One package, four review steps", "حزمة مستندات واحدة، وأربع خطوات للمراجعة"),
    ("how_read", "Read scanned and text documents together to extract structured evidence.", "قراءة المستندات المصورة والنصية معاً لاستخراج البيانات المنظمة."),
    ("how_rules", "Compare identity, dates, insurance, accommodation and employment details.", "مطابقة بيانات الهوية والتواريخ والتأمين والإقامة والعمل."),
    ("how_business", "For business trips, compare the professional sector with the stated trip purpose.", "في رحلات العمل، يُقارن القطاع المهني بالغرض المعلن من الرحلة."),
    ("how_score", "Apply the existing severity deductions and completeness bonuses, then prioritise corrections.", "تطبيق خصومات مستويات الأهمية ومكافآت اكتمال الملف، ثم ترتيب التعديلات."),
]
for item in _COPY:
    _add(*item)

_DOCUMENTS = {
    "passport": ("Passport", "جواز السفر"),
    "visa_form": ("Visa application form", "نموذج طلب التأشيرة"),
    "cover_letter": ("Cover letter", "الخطاب التوضيحي"),
    "hotel": ("Hotel bookings", "حجوزات الإقامة"),
    "flight": ("Flight reservations", "حجوزات الطيران"),
    "insurance": ("Travel insurance", "تأمين السفر"),
    "employment": ("Employment documents", "مستندات العمل"),
    "travel_plan": ("Travel plan", "خطة الرحلة"),
    "supporting": ("Supporting documents", "المستندات الداعمة"),
}
for key, pair in _DOCUMENTS.items():
    _add("doc_" + key, *pair)

_FIELDS = {
    "passport_number": ("Passport number", "رقم جواز السفر"),
    "applicant_name": ("Applicant name", "اسم مقدم الطلب"),
    "full_name": ("Full name", "الاسم الكامل"),
    "date_of_birth": ("Date of birth", "تاريخ الميلاد"),
    "passport_expiry": ("Passport expiry", "صلاحية جواز السفر"),
    "coverage_amount_eur": ("Medical coverage amount", "مبلغ التغطية الطبية"),
    "main_schengen_destination": ("Main destination", "الوجهة الرئيسية"),
    "leave_approval_confirmed": ("Leave approval", "الموافقة على الإجازة"),
    "employer_name in cover letter": ("Employer in cover letter", "ذكر جهة العمل في الخطاب"),
    "employer_name vs company_name": ("Employer and registered company", "جهة العمل والشركة المسجلة"),
    "travel_cities": ("Itinerary cities", "مدن الرحلة"),
    "departure_date vs check_in_date": ("Departure and first check-in", "المغادرة وأول تسجيل وصول"),
    "return_date vs check_out_date": ("Return and last check-out", "العودة وآخر تسجيل مغادرة"),
    "valid_from vs departure_date": ("Insurance start and departure", "بدء التأمين والمغادرة"),
    "valid_until vs return_date": ("Insurance end and return", "نهاية التأمين والعودة"),
    "intended_arrival vs departure_date": ("Visa entry and departure", "دخول منطقة شنغن والمغادرة"),
    "intended_departure vs return_date": ("Visa exit and return", "الخروج من منطقة شنغن والعودة"),
    "departure_date / return_date": ("Departure and return dates", "تاريخا المغادرة والعودة"),
    "approved_leave_start vs flight departure": ("Leave start and departure", "بدء الإجازة والمغادرة"),
    "approved_leave_end vs flight return": ("Leave end and return", "نهاية الإجازة والعودة"),
    "check_in_date": ("Check-in date", "تاريخ تسجيل الوصول"),
    "check_out_date": ("Check-out date", "تاريخ تسجيل المغادرة"),
    "departure_date": ("Departure date", "تاريخ المغادرة"),
    "return_date": ("Return date", "تاريخ العودة"),
    "valid_from": ("Insurance start", "بداية التأمين"),
    "valid_until": ("Insurance end", "نهاية التأمين"),
    "purpose_of_visit": ("Visit purpose", "غرض الزيارة"),
    "funding_source": ("Trip funding", "تمويل الرحلة"),
    "ties_to_home_country": ("Home-country ties", "الروابط ببلد الإقامة"),
    "attached_documents_listed": ("Supporting documents list", "قائمة المستندات المرفقة"),
    "employer_mentioned": ("Employer mentioned", "ذكر جهة العمل"),
    "job_title": ("Job title", "المسمى الوظيفي"),
    "employer_name": ("Employer", "جهة العمل"),
    "monthly_salary": ("Monthly salary", "الراتب الشهري"),
    "approved_leave_start": ("Approved leave start", "بداية الإجازة المعتمدة"),
    "approved_leave_end": ("Approved leave end", "نهاية الإجازة المعتمدة"),
    "field_of_work": ("Professional sector", "القطاع المهني"),
    "invitation_topic": ("Business invitation purpose", "غرض دعوة العمل"),
    "field_of_work vs invitation_topic": ("Sector and business purpose", "القطاع وغرض رحلة العمل"),
    "hotel": ("Accommodation evidence", "مستندات الإقامة"),
    "hotel_coverage_gap": ("Accommodation coverage gap", "فجوة في تغطية الإقامة"),
    "hotel_date_order": ("Accommodation date order", "ترتيب مواعيد الإقامة"),
}
for key, pair in _FIELDS.items():
    _add("field_" + key, *pair)


def t(key: str, lang: str | None = None, **values) -> str:
    if lang is None:
        import streamlit as st
        lang = st.session_state.get("lang", "en")
    return STRINGS[key]["ar" if lang == "ar" else "en"].format(**values)


def field_label(field: str, lang: str = "en") -> str:
    return t("field_" + field, lang) if "field_" + field in STRINGS else t("issue", lang)


def document_label(name: str, lang: str = "en") -> str:
    if lang == "en":
        return name
    import re
    translations = [
        ("Commercial Registry", "السجل التجاري"), ("Tax Card", "البطاقة الضريبية"),
        ("Invitation Letter", "خطاب الدعوة"), ("Visa Application Form", "نموذج طلب التأشيرة"),
        ("Travel Insurance (Insured Passport No.)", "تأمين السفر (رقم جواز المؤمن عليه)"),
        ("Travel Insurance", "تأمين السفر"), ("Hotel Reservation", "حجز الإقامة"),
        ("Flight Reservation", "حجز الطيران"), ("Employment Documents", "مستندات العمل"),
        ("Travel Itinerary", "خطة الرحلة"), ("Cover Letter", "الخطاب التوضيحي"),
        ("Passport", "جواز السفر"), ("Flight", "الطيران"), ("Hotel", "الإقامة"),
    ]
    for source, target in translations:
        name = name.replace(source, target)
    return name


# Stable IDs belong to rule constructors; English fixes retain their original precise evidence.
ISSUE_AR = {
    "validation.01": "تعذّر استخراج رقم الجواز. ارفع صورة واضحة تُظهر منطقة القراءة الآلية كاملة دون حجب.",
    "validation.02": "رقم الجواز في المستند لا يطابق الجواز المرفق. صحّح الرقم وتحقّق من استخدام الجواز الصحيح في جميع المستندات.",
    "validation.03": "الاسم في نموذج الطلب لا يطابق اسم صاحب الجواز. تحقّق من إرفاق الجواز الصحيح لهذا الطلب.",
    "validation.04": "اسم صاحب الحجز لا يطابق الاسم في الجواز بوضوح. عدّل الحجز ليطابق الاسم المطبوع في الجواز.",
    "validation.05": "تاريخ الميلاد في نموذج الطلب لا يطابق الجواز. صحّح النموذج وفق بيانات الجواز.",
    "validation.07": "تعذّر تحديد مبلغ التغطية الطبية. أرفق وثيقة تُظهر المبلغ باليورو بوضوح.",
    "validation.08": "التغطية الطبية أقل من الحد المطلوب البالغ 30,000 يورو. اطلب وثيقة تأمين بتغطية كافية.",
    "validation.09": "تعذّر تحديد الوجهة الرئيسية. أرفق خطة توضح عدد ليالي الإقامة في كل دولة.",
    "validation.10": "الوجهة المعلنة تختلف عن الدولة ذات أطول إقامة. راجع جهة تقديم الطلب وفق توزيع ليالي الرحلة.",
    "validation.11": "تعذّر قراءة تاريخ انتهاء الجواز. ارفع نسخة كاملة وواضحة من صفحة البيانات.",
    "validation.12": "انتهت صلاحية الجواز. جدّد الجواز قبل تقديم طلب التأشيرة.",
    "validation.13": "تنتهي صلاحية الجواز خلال ثلاثة أشهر من العودة. جدّد الجواز ليغطي المدة المطلوبة.",
    "validation.14": "لم يُرصد اعتماد صريح للإجازة. أرفق خطاب موافقة على الإجازة موقعاً من جهة العمل.",
    "validation.15": "تبدأ الإجازة المعتمدة بعد المغادرة. اطلب تعديل خطاب الإجازة ليغطي بداية الرحلة.",
    "validation.16": "تنتهي الإجازة المعتمدة قبل العودة. اطلب تمديدها لتغطي مدة الرحلة كاملة.",
    "validation.17": "لم تُذكر جهة العمل في الخطاب التوضيحي. أضف اسم جهة العمل وتأكيد الحالة الوظيفية.",
    "validation.18": "اسم جهة العمل لا يتوافق بوضوح مع الشركة في السجل التجاري. أرفق خطاباً يشرح العلاقة بين الجهتين.",
    "validation.19": "البيانات المطلوبة غير موجودة أو تعذّرت قراءتها. أرفق المستند كاملاً وبجودة واضحة.",
    "business.01": "تعذّر تحديد القطاع المهني من السجل التجاري أو البطاقة الضريبية. أرفق ترجمة واضحة تُظهر نشاط العمل.",
    "business.02": "تعذّر تحديد غرض رحلة العمل. أضف وصفاً صريحاً لموضوع الاجتماع أو المؤتمر في خطاب الدعوة.",
    "business.03": "غرض رحلة العمل لا يتوافق بوضوح مع القطاع المهني. أضف شرحاً للعلاقة المهنية في الخطاب التوضيحي.",
    "city.non_schengen": "تتضمن خطة الرحلة مدينة خارج منطقة شنغن. راجع متطلبات الدخول إليها وعدّل الوجهة أو نوع التأشيرة المناسب.",
    "city.unknown": "تعذّر التحقق من المدينة في القائمة المرجعية. أكّد وقوعها ضمن منطقة شنغن بالرجوع إلى المصدر الرسمي.",
    "date.departure_date vs check_in_date": "موعد الطيران يأتي بعد بداية حجز الإقامة. طابق موعد الوصول مع أول تسجيل وصول.",
    "date.return_date vs check_out_date": "رحلة العودة تسبق نهاية حجز الإقامة. صحّح موعد الطيران أو آخر تسجيل مغادرة.",
    "date.valid_from vs departure_date": "يبدأ التأمين بعد المغادرة. اطلب وثيقة سارية من تاريخ المغادرة.",
    "date.valid_until vs return_date": "ينتهي التأمين قبل العودة. مدّد الوثيقة حتى نهاية الرحلة.",
    "date.intended_arrival vs departure_date": "موعد الدخول في نموذج الطلب يختلف عن الطيران بأكثر من ثلاثة أيام. حدّث النموذج وفق المواعيد الفعلية.",
    "date.intended_departure vs return_date": "موعد الخروج في نموذج الطلب يختلف عن العودة بأكثر من ثلاثة أيام. حدّث النموذج وفق موعد العودة الفعلي.",
    "date.departure_date / return_date": "موعد المغادرة لا يسبق العودة. صحّح ترتيب تاريخي الرحلة.",
    "date.hotel_coverage_gap": "توجد ليالٍ غير مغطاة بحجوزات الإقامة. أرفق حجوزات متصلة تغطي كل ليلة من المغادرة حتى العودة.",
    "date.hotel_date_order": "تاريخ تسجيل الوصول لا يسبق المغادرة. صحّح مواعيد حجز الإقامة.",
}


def issue_translation(key: str, field: str) -> tuple[str, str]:
    return field_label(field, "ar"), ISSUE_AR.get(key, ISSUE_AR["validation.19"])


def issue_text(issue, lang: str):
    if lang == "ar":
        return issue.title_ar, issue.fix_ar
    return issue.title_en, issue.recommended_fix


def isolated_value(value, lang):
    """Keep dates, numbers, references and email addresses readable within Arabic labels."""
    return "\u2066"+str(value)+"\u2069" if lang=="ar" else str(value)
