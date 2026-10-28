"""English and Modern Standard Arabic copy for the entire interface."""
from __future__ import annotations

STRINGS = {}


def _add(key, en, ar):
    STRINGS[key] = {"en": en, "ar": ar}

_add("reasoning_title","Motivation letter and travel plan reasoning","مراجعة منطق خطاب الدافع وخطة الرحلة")
_add("reasoning_scope","AI reasoning is advisory and does not change the factual score. Every finding needs source evidence.","مراجعة الذكاء الاصطناعي استرشادية ولا تغير درجة التحقق من الوقائع. يجب أن يستند كل تعليق إلى دليل من المستندات.")
_add("reasoning_prepare","Prepare narrative review","تجهيز مراجعة النصوص")
_add("reasoning_reading","Reading the supplied documents locally…","جارٍ قراءة المستندات محلياً…")
_add("reasoning_prepare_failed","The complete file could not be prepared safely. Check readability or reduce the document set; no partial file was sent.","تعذر تجهيز الملف كاملاً بأمان. تحقق من وضوح المستندات أو قلل عددها؛ لم يُرسل ملف جزئي.")
_add("reasoning_not_started","Prepare the review to include the letter, travel plan and other supplied documents.","جهّز المراجعة لتشمل الخطاب وخطة الرحلة وبقية المستندات المرفقة.")
_add("reasoning_prepare_again","Prepare the packet again to use the selected language.","أعد تجهيز الملف لاستخدام اللغة المحددة.")
_add("reasoning_run","Run / retry AI reasoning","تشغيل مراجعة الذكاء الاصطناعي أو إعادة المحاولة")
_add("reasoning_running","Reviewing document logic and checking proposed findings…","جارٍ مراجعة منطق المستندات والتحقق من التعليقات المقترحة…")
_add("reasoning_unavailable","The reviewer could not finish. Your documents remain in this session. Restore the model service, then run / retry the reasoning review.","تعذر إكمال المراجعة. تظل المستندات في هذه الجلسة. أعد تشغيل خدمة النموذج ثم حاول مجدداً.")
_add("reasoning_partial","Narrative review is incomplete. Inspect the limitations before relying on its findings.","مراجعة النصوص غير مكتملة. راجع القيود قبل الاعتماد على النتائج.")
_add("reasoning_no_findings","No source-grounded concerns were retained. This is not a guarantee that the application or itinerary is correct.","لم تُعتمد ملاحظات مستندة إلى أدلة. هذا لا يضمن صحة الطلب أو برنامج الرحلة.")
_add("reasoning_suggestion","Suggested edit / action","التعديل أو الإجراء المقترح")
_add("reasoning_limitations","Narrative review limitations","قيود مراجعة النصوص")
_add("reasoning_download","Download narrative review (JSON)","تنزيل مراجعة النصوص (JSON)")
_add("reasoning_kind_contradiction","Possible contradiction — review the quoted sources","تعارض محتمل — راجع المصادر المقتبسة")
_add("reasoning_kind_coherence","Logic / coherence suggestion","اقتراح لتحسين المنطق والترابط")
_add("reasoning_kind_clarity","Clarity suggestion","اقتراح لتحسين الوضوح")
_add("reasoning_kind_unsupported_claim","Supporting evidence needs verification","يحتاج الدليل المؤيد إلى التحقق")
_add("reasoning_kind_needs_verification","Needs manual verification","يحتاج إلى تحقق يدوي")


_add('local_values','Extracted document values','البيانات المقروءة من المستندات')
_add('local_values_hint','Readings marked for verification are provisional and cannot establish a confirmed mismatch.','القراءات التي تحتاج إلى التحقق مؤقتة ولا تثبت وجود اختلاف مؤكد.')
_add('local_field_read','Read from the document','مقروء من المستند')
_add('local_field_verify','Needs verification against the original','يحتاج إلى التحقق من الأصل')
_add('local_unsupported','This template needs manual verification.','يتطلب هذا القالب تحققاً يدوياً.')
_add('local_download','Download extracted values (JSON)','تنزيل البيانات المقروءة (JSON)')
_add('local_template_hint','Only supported local templates are read automatically. Unsupported layouts require manual verification.','تُقرأ القوالب المحلية المدعومة تلقائياً فقط. تحتاج التنسيقات غير المدعومة إلى تحقق يدوي.')
_add('trip_type','Trip category','فئة الرحلة')
_add('trip_tourism','Tourism','سياحة')
_add('trip_business','Business','أعمال')
_add('review_starting','Starting document review…','جارٍ بدء مراجعة المستندات…')
_add('corrections_title','Corrections needed ({count})','التعديلات المطلوبة ({count})')
_add('incorrect_value','Found in the document','القيمة الموجودة في المستند')
_add('correct_value','Expected value','القيمة المطلوبة')
_add('missing_value','Missing','غير موجود')
_add('passport_upload_missing','No passport was uploaded. Add the passport image or PDF in the Passport section, then run the review again.','لم يتم رفع جواز السفر. أضف صورة الجواز أو ملف PDF في خانة جواز السفر، ثم أعد تشغيل المراجعة.')
_add('reference_source','Reference','المصدر المرجعي')
_add('no_confirmed_mismatches','No confirmed errors in the completed checks.','لا توجد أخطاء مؤكدة في عمليات التحقق المكتملة.')
_add('verification_notice','Review incomplete: {count} checks need verification. They are not confirmed errors.','المراجعة غير مكتملة: تحتاج {count} من عمليات التحقق إلى مراجعة. هذه ليست أخطاء مؤكدة.')
_add('verification_details','Checks needing verification','عمليات التحقق التي تحتاج إلى مراجعة')
_add('origin_local_key_value','Local key/value comparison','مطابقة محلية للمفاتيح والقيم')
_add('origin_local_rule','Local validation rule','قاعدة تحقق محلية')
_add('origin_unknown','Review method was not recorded for this result. Rerun the review for a check receipt.','لم تُسجّل طريقة المراجعة لهذه النتيجة. أعد المراجعة للحصول على سجل التحقق.')
_add('narrative_advice','Cover letter and travel plan suggestions','مقترحات الخطاب التوضيحي وخطة الرحلة')
_add('how_checked','How this was checked','كيف تم التحقق')
_add('proof_hint','The receipt records local parsers, file hashes and compared keys and values.','يسجل السجل أدوات القراءة المحلية وبصمات الملفات والمفاتيح والقيم المقارنة.')
_add('download_receipt','Download check receipt (JSON)','تنزيل سجل التحقق (JSON)')
_add('download_corrections','Download corrections (PDF)','تنزيل التعديلات (PDF)')
_add('error_region_unavailable','The exact field could not be located for a screenshot.','تعذر تحديد موضع الحقل بدقة لعرض صورة منه.')
_add('gap_required_coverage','Accommodation needed for these dates','الإقامة المطلوبة لهذه الفترة')
_add('permissions_and_limits','Permissions and review limits','الصلاحيات وحدود المراجعات')
_add('review_limits_summary','Saved limits: {hour}/hour · {day}/24 hours','الحدود المحفوظة: {hour} في الساعة · {day} خلال 24 ساعة')
_add('admin_reviews_unlimited','Unlimited reviews for admins — no hourly or daily cap.','مراجعات غير محدودة للمسؤولين — بدون حد بالساعة أو باليوم.')
_add('restoring_session','Restoring your sign-in…','جارٍ استعادة تسجيل الدخول…')
_add('review_limits_hint','Both limits apply independently. Raising the hourly limit does not raise the 24-hour allowance. Usage falls as each review leaves its rolling time window.','يُطبق الحدّان بصورة مستقلة. رفع الحد في الساعة لا يرفع حد المراجعات خلال 24 ساعة. ينخفض الاستخدام تدريجياً بخروج كل مراجعة من فترتها الزمنية.')
_add('permissions_updated','Permissions and review limits saved.','تم حفظ الصلاحيات وحدود المراجعات.')
_add('review_attempts_hint','Failed or interrupted review attempts also count toward these limits.','تُحتسب محاولات المراجعة الفاشلة أو المتوقفة أيضاً ضمن هذه الحدود.')
_add('limit_hourly','Hourly review limit reached','تم بلوغ الحد في الساعة')
_add('limit_daily','24-hour review limit reached','تم بلوغ الحد خلال 24 ساعة')
_add('limit_both','Hourly and 24-hour review limits reached','تم بلوغ الحد في الساعة وخلال 24 ساعة')
_add('rate_limited_details','{period}. Used: {hour_used}/{hour_limit} in the last hour; {day_used}/{day_limit} in the last 24 hours. Next available after {retry_at} (Cairo), if limits and usage stay unchanged.','{period}. الاستخدام: {hour_used}/{hour_limit} في آخر ساعة؛ {day_used}/{day_limit} في آخر 24 ساعة. أقرب وقت متاح بعد {retry_at} بتوقيت القاهرة، إذا لم تتغير الحدود أو الاستخدام.')
_add('maintenance_hint','Pauses customer access and new reviews. Administrators can resume the website here.','يوقف وصول العملاء والمراجعات الجديدة. يمكن للمسؤول الرئيسي إعادة تشغيل الموقع من هنا.')


_add('doc_bank_statement','Bank statement','كشف الحساب البنكي')
_add('doc_other','Other trip costs','مصروفات الرحلة الأخرى')
_add('bank_scope','Bank statements need a supported local template. Until configured, the final balance requires manual verification.','تحتاج كشوف الحساب إلى قالب قراءة محلي مدعوم. حتى إضافته، يتطلب الرصيد الأخير تحققاً يدوياً.')
_add('bank_budget','Bank balance and trip budget','الرصيد البنكي وميزانية الرحلة')
_add('balance_available','Final available balance','آخر رصيد متاح')
_add('balance_closing','Final closing balance','آخر رصيد ختامي')
_add('balance_eur','Indicative balance in EUR','الرصيد الاسترشادي باليورو')
_add('balance_unknown','Final balance (unverified type)','الرصيد الأخير (النوع غير مؤكد)')
_add('balance_unreadable','No final-page balance could be verified. Supply a clearer final page showing the balance and currency.','تعذر التحقق من رصيد الصفحة الأخيرة. أرفق صفحة أخيرة أوضح يظهر بها الرصيد والعملة.')
_add('statement_date','Statement date','تاريخ كشف الحساب')
_add('daily_allowance','Daily spending allowance (EUR)','ميزانية المصروف اليومي (يورو)')
_add('allowance_hint','Editable planning assumption per travel day for meals, local transport and activities. EUR 75 is an internal starting assumption, not a consular minimum. Hotel and flight totals are added separately.','افتراض تخطيطي قابل للتعديل لكل يوم للسفر يشمل الطعام والتنقلات والأنشطة. مبلغ 75 يورو نقطة بداية داخلية وليس حداً قنصلياً. تضاف إجماليات الفندق والطيران بصورة منفصلة.')
_add('budget_scope','Planning comparison only; no score deduction. Uses quoted unpaid trip totals plus the daily allowance. Missing prices remain unknown. Balances are assessed separately and are never added together.','مقارنة تخطيطية فقط دون خصم نقاط. تشمل إجماليات الرحلة غير المدفوعة الواردة بالمستندات وميزانية المصروف اليومي. تظل الأسعار الناقصة غير معروفة. يُقيّم كل رصيد منفرداً ولا تُجمع الأرصدة.')
_add('budget_total','Known remaining trip budget + daily allowance','ميزانية الرحلة المتبقية المعروفة مع المصروف اليومي')
_add('allowance_total','Daily allowance for {days} travel days: EUR {amount}.','مصروف يومي لعدد {days} أيام سفر: {amount} يورو.')
_add('paid_excluded','Explicitly paid; excluded from remaining costs','مدفوع صراحة؛ مستبعد من المصروفات المتبقية')
_add('budget_covers_budget','This balance covers the quoted remaining bookings and selected daily allowance. Confirm unpriced extras and actual access to these funds.','يغطي هذا الرصيد الحجوزات المتبقية المسعرة والمصروف اليومي المحدد. تأكد من الإضافات غير المسعرة وإمكانية التصرف الفعلية في الأموال.')
_add('budget_partial_budget','This balance covers the known subtotal, but the whole trip cannot be assessed until missing costs are supplied.','يغطي هذا الرصيد الإجمالي الجزئي المعروف، لكن لا يمكن تقييم الرحلة كاملة قبل استكمال المصروفات الناقصة.')
_add('budget_below_budget','This balance is below the known remaining trip budget. Confirm additional accessible funding or reduce costs.','هذا الرصيد أقل من ميزانية الرحلة المتبقية المعروفة. أكد وجود تمويل إضافي متاح أو خفّض المصروفات.')
_add('budget_ownership_unknown','The final page does not establish that these funds belong to or are accessible to the applicant. Confirm ownership before relying on this balance.','لا تثبت الصفحة الأخيرة ملكية الأموال لمقدم الطلب أو إتاحتها له. أكد الملكية قبل الاعتماد على هذا الرصيد.')
_add('budget_conversion_unknown','A current currency conversion is unavailable. No affordability conclusion can be drawn across different currencies.','لا يتوفر تحويل عملة حديث؛ لا يمكن استنتاج كفاية الرصيد عند اختلاف العملات.')
_add('budget_missing','Whole-trip assessment is incomplete; missing','تقييم الرحلة كاملة غير مكتمل؛ البيانات الناقصة')
_add('budget_missing_flight_price','Flight total','إجمالي الطيران')
_add('budget_missing_hotel_price','Hotel total(s)','إجماليات الفنادق')
_add('budget_missing_currency_conversion','Currency conversion','تحويل العملات')
_add('budget_missing_travel_dates','Travel dates','تواريخ الرحلة')
_add('budget_rate_date','Indicative exchange-rate date: {date}. Bank charges and future rate changes are excluded.','تاريخ سعر الصرف الاسترشادي: {date}. لا يشمل رسوم البنك أو تغيرات الأسعار المستقبلية.')
_add('booking_held','Booking is on hold','الحجز معلّق (قيد الانتظار)')
_add('booking_confirmed','Booking is confirmed','الحجز مؤكد')
_add('booking_cancelled','Booking is cancelled','الحجز ملغى')
_add('booking_unknown','Booking status needs confirmation','حالة الحجز تحتاج إلى تأكيد')
_add('category_order','Upload category order','ترتيب فئات المستندات')
_add('category_order_hint','Super admin only. Move categories, then save the shared order for the whole team. Existing uploads stay in their original categories.','للمشرف العام فقط. حرّك الفئات ثم احفظ الترتيب المشترك لكل الفريق. تظل الملفات المرفوعة مرتبطة بفئاتها الأصلية.')
_add('category_to_move','Category to move','الفئة المراد تحريكها')
_add('move_up','Move up','تحريك لأعلى')
_add('move_down','Move down','تحريك لأسفل')
_add('save_order','Save category order','حفظ ترتيب الفئات')
_add('order_saved','Category order saved for the team.','تم حفظ ترتيب الفئات للفريق.')
_add('upload_preview','Page {page} of {pages} · {size} KB','الصفحة {page} من {pages} · {size} كيلوبايت')
_add('preview_unavailable','Preview unavailable','المعاينة غير متاحة')


_add('review_incomplete', 'Review incomplete — score is provisional', 'المراجعة غير مكتملة — الدرجة مبدئية')
_add('review_limitation', 'Review limitation · no score deduction', 'قيد في المراجعة · دون خصم نقاط')
_add('review_limitations', 'Review limitations', 'قيود المراجعة')
_add('field_approved_leave_dates', 'Approved leave dates', 'تواريخ الإجازة المعتمدة')
_add('field_document_readability', 'Source page coverage', 'تغطية صفحات المصدر')
_add('field_destination_country', 'Application main destination', 'الوجهة الرئيسية في الطلب')
_add('field_cover_letter_completeness', 'Cover letter completeness', 'اكتمال الخطاب التوضيحي')
_add('write_flight_day_arrival','The final-destination flight arrives at {time}. Make the first day consistent with that arrival and airport transfer.','تصل رحلة الوجهة النهائية الساعة {time}. اجعل برنامج اليوم الأول متوافقاً مع الوصول والانتقال من المطار.')
_add('write_flight_day_arrival_fix','Arrival at {time}; allow time for airport formalities and transfer before hotel check-in and optional activities. Confirm the transfer duration.','الوصول الساعة {time}؛ اترك وقتاً لإجراءات المطار والانتقال قبل دخول الفندق والأنشطة الاختيارية، وتحقق من مدة الانتقال.')
_add('write_flight_day_departure','The return flight departs at {time}. Plan checkout and the airport journey around the airline’s confirmed check-in deadline.','تغادر رحلة العودة الساعة {time}. حدد مغادرة الفندق والانتقال للمطار وفق الموعد المؤكد لإغلاق تسجيل السفر لدى الشركة.')
_add('write_flight_day_departure_fix','Flight departure at {time}; work backwards from the verified check-in deadline to set hotel checkout and transfer. Remove sightseeing that would compromise that schedule.','إقلاع الرحلة الساعة {time}؛ حدد موعد مغادرة الفندق والانتقال اعتماداً على الموعد المتحقق لإغلاق التسجيل، واحذف أي جولة تعطل هذا الجدول.')
_add('write_purpose_grounded','I plan to visit {country} from {start} to {end} for [confirmed purpose]. Explain why the itinerary suits that purpose.','أخطط لزيارة {country} من {start} إلى {end} بغرض [الغرض المؤكد]. اشرح سبب ملاءمة البرنامج لهذا الغرض.')
_add('write_funding_placeholder','[Actual payer] will cover [confirmed expenses], supported by [supplied evidence]. State only the verified final balance and confirm access to those funds. Account access alone does not establish sponsorship.','سيتحمل [الممول الفعلي] [المصروفات المؤكدة] وفق [المستند المرفق]. اذكر الرصيد الأخير المتحقق فقط وأكد إمكانية التصرف في الأموال؛ تفويض استخدام الحساب وحده لا يثبت الكفالة المالية.')
_add('write_ties_placeholder','Describe [actual obligations after the trip], such as continuing studies or employment, with [supporting dates/documents]. Confirm the applicant’s real plans before stating an intention to return.','اشرح [الالتزامات الفعلية بعد الرحلة] مثل استمرار الدراسة أو العمل، مع [المواعيد والمستندات المؤيدة]. تأكد من خطة مقدم الطلب الحقيقية قبل صياغة نية العودة.')
_add('write_calendar_verify','Verify the official holiday calendar and venue availability for this day. Statements in the itinerary have not been independently confirmed.','تحقق من التقويم الرسمي للعطلات وتوافر الأماكن في هذا اليوم؛ لم يتم تأكيد ما تقوله الخطة عن العطلات والمواعيد من مصدر مستقل.')
_add('write_calendar_action','Confirm the official calendar, attraction opening hours and restaurant availability before finalizing this day.','أكد التقويم الرسمي ومواعيد فتح المعالم وتوافر المطاعم قبل اعتماد برنامج هذا اليوم.')
_add('write_student_ties','Explain the applicant’s continuing studies and actual obligations after the trip using the enrollment evidence and confirmed dates. Confirm any required university travel permission; do not request an employment HR letter for a student without separate employment.','وضح استمرار دراسة مقدم الطلب والتزاماته الفعلية بعد الرحلة وفق شهادة القيد والمواعيد المؤكدة، وتحقق من أي موافقة سفر جامعية مطلوبة. لا تطلب خطاب عمل لطالب دون وجود عمل مستقل.')


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
    ("password_mismatch", "Passwords must match.", "يجب أن تتطابق كلمتا المرور."),
    ("password_short", "Use at least 6 characters. No uppercase, digit or symbol rules. Supabase requires a minimum of 6.", "استخدم 6 أحرف على الأقل، دون اشتراط أحرف كبيرة أو أرقام أو رموز. يفرض Supabase حداً أدنى من 6 أحرف."),
    ("username", "Username", "اسم المستخدم"),
    ("username_hint", "3–32 letters, numbers, dots, hyphens or underscores; start with a letter or number. Usernames are case-insensitive.", "من 3 إلى 32 حرفاً لاتينياً أو رقماً، مع السماح بالنقطة والشرطة والشرطة السفلية. ابدأ بحرف أو رقم. لا يفرق الاسم بين الأحرف الكبيرة والصغيرة."),
    ("username_invalid", "Enter a valid username: 3–32 characters, starting with a letter or number.", "أدخل اسم مستخدم صحيحاً من 3 إلى 32 حرفاً يبدأ بحرف لاتيني أو رقم."),
    ("username_taken", "That username is already in use. Choose another.", "اسم المستخدم مستخدم بالفعل. اختر اسماً آخر."),
    ("agent_email", "Reviewer email", "بريد المراجع"),
    ("attempts", "Review attempts", "محاولات المراجعة"),
    ("attempts_hint", "Includes started, completed and failed analyses. Older attempts may have no client or score. A running attempt may have been interrupted.", "يشمل التحليلات التي بدأت أو اكتملت أو فشلت. قد لا تتضمن المحاولات القديمة اسم العميل أو الدرجة. قد تكون المحاولة قيد التنفيذ قد انقطعت."),
    ("running", "Running / interrupted", "قيد التنفيذ / ربما انقطعت"),
    ("completed", "Completed", "مكتملة"),
    ("failed", "Failed", "فشلت"),
    ("legacy", "Earlier attempt", "محاولة سابقة"),
    ("combined_hint", "Upload each document in its matching section. Use the separate National ID translation and Bank declaration sections; put all HR files under Employment documents. Cover letter and travel plan may share one file.", "ارفع كل مستند في الخانة المخصصة له. استخدم خانتي ترجمة بطاقة الرقم القومي والإقرار البنكي، وارفع جميع ملفات العمل والراتب والإجازة ضمن مستندات العمل. يمكن جمع الخطاب التوضيحي وخطة الرحلة في ملف واحد."),
    ("writing_title", "Suggested document edits", "التعديلات المقترحة للمستندات"),
    ("writing_note", "Writing advice does not change the score. Verify every quote and proposed fact against the originals before editing.", "لا تغير توصيات الصياغة الدرجة. تحقق من كل اقتباس ومعلومة مقترحة بالرجوع إلى الأصل قبل التعديل."),
    ("source", "Source", "المصدر"),
    ("original_text", "Original wording", "النص الأصلي"),
    ("replacement", "Suggested wording", "الصياغة المقترحة"),
    ("edit_add", "Add", "إضافة"),
    ("edit_remove", "Remove", "حذف"),
    ("edit_replace", "Replace", "استبدال"),
    ("edit_verify", "Verify", "تحقق"),
    ("writing_ok", "No specific wording changes identified in the supplied section.", "لم تُحدد تعديلات صياغة محددة في القسم المرفق."),
    ("write_purpose", "State the actual purpose, countries and travel dates. Replace vague wording with: 'I plan to visit [country] for [verified purpose] from [arrival] to [departure].'", "اذكر الغرض الفعلي والدول والمواعيد: «أخطط لزيارة [الدولة] لغرض [الغرض المؤكد] من [الوصول] إلى [المغادرة]»."),
    ("write_funding", "Explain who pays and cite the supplied funding evidence: '[verified payer] will cover [expenses], supported by [document].' Do not invent a sponsor or balance.", "حدد من يمول الرحلة مع الإشارة إلى الدليل المرفق: «يتحمل [الممول المؤكد] [النفقات] وفق [المستند]». لا تختلق ممولاً أو رصيداً."),
    ("write_ties", "Describe only real home-country obligations supported by documents, such as employment and approved leave. Ask the applicant for missing facts; do not invent assets or family ties.", "وضح الالتزامات الحقيقية المثبتة بالمستندات، مثل العمل والإجازة المعتمدة. اطلب المعلومات الناقصة من مقدم الطلب ولا تختلق ممتلكات أو روابط أسرية."),
    ("write_attachments", "Add a numbered attachments list naming only documents actually supplied, including bookings, insurance and relevant employment/funding evidence.", "أضف قائمة مرقمة بالمرفقات الفعلية فقط، بما فيها الحجوزات والتأمين وأدلة العمل والتمويل ذات الصلة."),
    ("write_itinerary", "Add a day-by-day itinerary: date, city, accommodation, planned activity and transport. Match every night to the supplied hotel bookings and arrival/return to flights; verify activities with the applicant.", "أضف خطة يومية تتضمن التاريخ والمدينة والإقامة والنشاط والتنقل. طابق كل ليلة مع حجوزات الإقامة والوصول والعودة مع الطيران، وتحقق من الأنشطة مع مقدم الطلب."),
    ("write_plan_dates", "Add the itinerary start/end and a row for every travel day. Match arrival, transfers and departure to the actual bookings; do not leave uncovered days.", "أضف بداية الرحلة ونهايتها وصفاً لكل يوم. طابق الوصول والتنقل والمغادرة مع الحجوزات الفعلية ولا تترك أياماً دون بيان."),
    ("write_plan_cities", "Name each city and its accommodation, in travel order. Add only confirmed transfers and proposed activities clearly marked as plans.", "اذكر كل مدينة ومكان الإقامة بترتيب السفر. أضف التنقلات المؤكدة فقط ووضح أن الأنشطة المقترحة مجرد خطط."),
    ("write_plan_activities", "Complete each daily row with its date, city and specific planned activities. Add the matching accommodation and realistic transport; confirm missing choices with the applicant rather than inventing them.", "استكمل كل يوم بالتاريخ والمدينة والأنشطة المحددة. أضف الإقامة المطابقة والتنقل الواقعي، وتحقق من الخيارات الناقصة مع مقدم الطلب بدلاً من اختلاقها."),
    ("write_template", "Unfinished template text remains. Replace this exact placeholder with verified information, or remove the unused template line after checking that the required information is already stated.", "لا يزال النص يحتوي على عبارة من القالب غير مكتملة. استبدل هذا الموضع بالبيانات المؤكدة، أو احذف سطر القالب غير المستخدم بعد التحقق من أن المعلومات المطلوبة مذكورة بالفعل."),
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
    ('review_description','Compare document fields and find corrections before submission. An optional narrative review checks the motivation letter and travel plan against the supplied file.','قارن بيانات المستندات وحدد التعديلات قبل التقديم. تراجع الخدمة الاختيارية منطق خطاب الدافع وخطة الرحلة بمقارنتهما مع الملف المرفق.'),
    ("client_name", "Client name", "اسم العميل"),
    ("client_placeholder", "Applicant's full name", "الاسم الكامل لمقدم الطلب"),
    ("client_required", "Enter a client name before running the review.", "أدخل اسم العميل قبل بدء المراجعة."),
    ("model", "Analysis model", "نموذج التحليل"),
    ("advanced", "Review settings", "إعدادات المراجعة"),
    ("upload_title", "Application documents", "مستندات الطلب"),
    ("upload_hint", "PDF, JPG, PNG or WebP · 20 MB per file · 75 MB per review · up to 30 files", "PDF أو JPG أو PNG أو WebP · 20 ميجابايت للملف · 75 ميجابايت للمراجعة · حتى 30 ملفاً"),
    ("files_added", "{count} files added", "تمت إضافة {count} ملفات"),
    ("choose_files", "Drop or choose files", "اسحب الملفات أو اخترها"),
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
    ("step_business", "Compare document values", "مطابقة قيم المستندات"),
    ("step_score", "Prepare corrections", "إعداد التعديلات"),
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
    ("agent", "Reviewer username", "اسم مستخدم المراجع"),
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
    ('how_read','Read supported document templates locally. Unsupported layouts and unclear fields need verification. Prepare the optional narrative review to assess the letter and travel plan.','تُقرأ قوالب المستندات المدعومة محلياً. تحتاج التنسيقات غير المدعومة والبيانات غير الواضحة إلى التحقق. جهّز المراجعة الاختيارية لتقييم الخطاب وخطة الرحلة.'),
    ("how_rules", "Compare identity, dates, insurance, accommodation and employment details.", "مطابقة بيانات الهوية والتواريخ والتأمين والإقامة والعمل."),
    ("how_business", "For business trips, compare the professional sector with the stated trip purpose.", "في رحلات العمل، يُقارن القطاع المهني بالغرض المعلن من الرحلة."),
    ("how_score", "Apply the existing severity deductions and completeness bonuses, then prioritise corrections.", "تطبيق خصومات مستويات الأهمية ومكافآت اكتمال الملف، ثم ترتيب التعديلات."),
]
for item in _COPY:
    _add(*item)

_DOCUMENTS = {
    "ds160": ("DS-160", "نموذج DS-160"),
    "client_form": ("Client form", "استمارة العميل"),
    "passport": ("Passport", "جواز السفر"),
    "visa_form": ("Visa application form", "نموذج طلب التأشيرة"),
    "cover_letter": ("Cover letter", "الخطاب التوضيحي"),
    "hotel": ("Hotel bookings", "حجوزات الإقامة"),
    "flight": ("Flight reservations", "حجوزات الطيران"),
    "insurance": ("Travel insurance", "تأمين السفر"),
    "employment": ("Employment documents", "مستندات العمل"),
    "travel_plan": ("Travel plan", "خطة الرحلة"),
    "supporting": ("Supporting documents", "المستندات الداعمة"),
    "appointment": ("Embassy appointment", "موعد السفارة"),
    "national_id_translation": ("National ID translation", "ترجمة بطاقة الرقم القومي"),
    "bank_declaration": ("Bank declaration", "الإقرار البنكي"),
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
    "given_names": ("Given names", "الأسماء الأولى"),
    "surname": ("Surname", "اسم العائلة"),
    "passport_issue": ("Passport issue date", "تاريخ إصدار الجواز"),
    "national_id_number": ("National ID number", "رقم بطاقة الهوية"),
    "national_id_issue": ("National ID issue date", "تاريخ إصدار بطاقة الهوية"),
    "national_id_expiry": ("National ID expiry date", "تاريخ انتهاء بطاقة الهوية"),
    "identity_date_order": ("Identity issue / expiry dates", "ترتيب تاريخي إصدار الهوية وانتهائها"),
    "appointment_date": ("Embassy appointment date", "تاريخ موعد السفارة"),
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
        ("DS-160", "نموذج DS-160"), ("Client Form", "استمارة العميل"),
        ("Commercial Registry", "السجل التجاري"), ("Tax Card", "البطاقة الضريبية"),
        ("Invitation Letter", "خطاب الدعوة"), ("Visa Application Form", "نموذج طلب التأشيرة"),
        ("Travel Insurance (Insured Passport No.)", "تأمين السفر (رقم جواز المؤمن عليه)"),
        ("Travel Insurance", "تأمين السفر"), ("Hotel Reservation", "حجز الإقامة"),
        ("Flight Reservation", "حجز الطيران"), ("Employment Documents", "مستندات العمل"),
        ("Travel Itinerary", "خطة الرحلة"), ("Cover Letter", "الخطاب التوضيحي"),
        ("National ID", "بطاقة الهوية"), ("Supporting Documents", "المستندات الداعمة"),
        ("Embassy Appointment", "موعد السفارة"),
        ("Passport", "جواز السفر"), ("Flight", "الطيران"), ("Hotel", "الإقامة"),
    ]
    for source, target in translations:
        name = name.replace(source, target)
    return name


# Stable IDs belong to rule constructors; English fixes retain their original precise evidence.
ISSUE_AR = {
    'document.not_uploaded':'لم يتم رفع المستند. أضف جواز السفر في الخانة المخصصة له، ثم أعد تشغيل المراجعة.',
    "identity.id_reference_note": "تمت قراءة الرقم القومي، لكن لا يتوفر مرجع مستقل مقروء للتحقق منه. راجعه مع أصل البطاقة عند توفره. هذه ليست مخالفة مؤكدة ولا تُخصم بسببها نقاط.",
    "identity.mismatch": "بيان الهوية لا يطابق المستند المرجعي. تحقق من الأصل وصحح النموذج أو أعد إصدار الحجز ليطابق البيانات حرفياً. لا تخمن الحروف ولا تعدّل وثيقة هوية رسمية.",
    "identity.unreadable": "البيان غير مقروء أو ملتبس ويستلزم تحققاً يدوياً. أرفق أصلاً واضحاً أو نقلاً رسمياً قبل التقديم؛ لم يُحسم هذا البيان.",
    "identity.reference": "لا يوجد بيان مرجعي مقروء للتحقق من هذه القيمة. أرفق صفحة الهوية الأصلية بوضوح قبل التقديم؛ لم يُحسم هذا البيان.",
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
    "date.intended_arrival vs departure_date": "موعد الطيران يختلف عن تاريخ الوصول في نموذج الطلب. طابق التاريخين بدقة.",
    "date.intended_departure vs return_date": "موعد العودة يختلف عن تاريخ المغادرة في نموذج الطلب. طابق التاريخين بدقة.",
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


for item in [
    ("not_ready","Not ready — critical corrections required","غير جاهز — توجد تعديلات حرجة"),
    ("needs_attention","Needs attention — review the findings","يحتاج مراجعة — راجع الملاحظات"),
    ("checks_passed","File checks passed","اجتاز فحوصات الملف"),
    ("quality_title","Extraction and source coverage","استخراج البيانات وتغطية المصادر"),
    ('quality_note','Completeness measures populated fields, not accuracy. Check the originals for uncertain or conflicting fields.','الاكتمال يقيس الحقول المستخرجة وليس دقتها. راجع الأصول للحقول المتعارضة أو غير الواضحة.'),
    ("completeness","Field completeness","اكتمال الحقول"),
    ("pages_read","Pages reported read","الصفحات المُبلّغ عن قراءتها"),
    ("supporting_title","Supporting evidence assessment","تقييم المستندات الداعمة"),
    ("supporting_note","Checks compare the supplied documents. Consistent information does not establish authenticity or confirm facts with an issuer.","تقارن الفحوص المستندات المرفقة. توافق البيانات لا يثبت أصالة المستند ولا يؤكد الحقائق لدى جهة الإصدار."),
    ("consistent","Consistent with supplied evidence","متوافق مع المستندات المرفقة"),
    ("conflicts","Conflicts with supplied evidence","يتعارض مع المستندات المرفقة"),
    ("unverified","Unverified — needs corroboration","غير مؤكد — يحتاج دليلاً داعماً"),
    ("source_left","Original document","المستند الأصلي"),
    ("correction_right","Expected value / reference","القيمة المطلوبة / المرجع"),
    ("page_preview","Original page preview; error location is not confirmed","معاينة الصفحة الأصلية؛ لم يتم تأكيد موضع الخطأ"),
    ("matched_region","Region matched to original PDF text","موضع مطابق لنص ملف PDF الأصلي"),
    ("evidence_unavailable","A reliable source image could not be located. Verify this field in the original document.","تعذّر تحديد صورة مصدر موثوقة. راجع هذا البيان في المستند الأصلي."),
    ("evidence_note","Left: the actual source. Right: the expected value and available reference. The reference is not an edited or reissued document.","يساراً: المصدر الفعلي. يميناً: القيمة المطلوبة والمرجع المتاح. المرجع ليس وثيقة معدلة أو مُعاد إصدارها."),
    ("day","Day","اليوم"),
    ("write_specific_day","Add or complete the plan for {day}: city, realistic activities and accommodation.","أضف أو أكمل خطة يوم {day}: المدينة والأنشطة الواقعية والإقامة."),
    ("write_day_structure","{day} — Accommodation evidence: {stay}. Add [confirmed activities], [travel time] and [transport if needed]. Check opening hours and booking details; keep arrival/departure days practical.","{day} — مستند الإقامة: {stay}. أضف [الأنشطة المؤكدة] و[وقت التنقل] و[المواصلات عند الحاجة]. تحقق من ساعات العمل والحجوزات واجعل يومي الوصول والمغادرة واقعيين."),
    ("write_transfer","For {day}, explain the transfer from {origin} to {destination}, including realistic transport and duration.","ليوم {day}، وضّح الانتقال من {origin} إلى {destination} بوسيلة نقل ومدة واقعيّتين."),
    ("super_admin","Super administrator","المشرف العام"),
    ("user","Reviewer","مراجع"),
    ("role","Role","الصلاحية"),
    ("hourly_limit","Reviews per hour","المراجعات في الساعة"),
    ("daily_limit","Reviews per 24 hours","المراجعات خلال 24 ساعة"),
    ("save_changes","Save changes","حفظ التغييرات"),
    ("reviews_enabled","Allow new reviews","السماح بمراجعات جديدة"),
    ("admin_audit","Administration activity","سجل إدارة التطبيق"),
]:
    _add(*item)

ISSUE_AR.update({
    'context.application_completeness':'أكمل بيانات الاتصال والهوية المطلوبة والفارغة في نموذج الطلب وفق التفاصيل المتحققة لمقدم الطلب.',
    'context.translation_dob':'راجع تاريخ الميلاد المكتوب بالأرقام والشهر المكتوب بالحروف مع الأصل، واطلب تصحيح الترجمة مع الحفاظ على صاحب البيان الصحيح.',
    'context.reservation_validity':'انتهت نافذة السداد المطبوعة في هذه النسخة. اطلب تأكيداً حديثاً من الشركة أو حجزاً صالحاً؛ لا تثبت هذه النسخة وحدها أن الحجز ألغي ولا تعني وجوب شراء تذكرة.',
    'context.translation_honorific':'اطلب تصحيح لقب مقدم الطلب في الترجمة وفق الجواز. هذا خطأ في الصياغة وليس دليلاً على اختلاف هوية مقدم الطلب.',
    'context.cover_letter_completeness':'أضف أو أكمل الخطاب التوضيحي ليشرح الغرض من الزيارة والتمويل والارتباط ببلد الإقامة، بوقائع تدعمها المستندات وقائمة بالمرفقات. خطة الأنشطة وحدها ليست خطاباً توضيحياً.',
    'context.destination_country':'صحح خانة الوجهة الرئيسية في نموذج الطلب لتوافق الدولة ذات الإقامة الرئيسية الفعلية. خانة أول دخول منفصلة عنها.',
    "identity.name_format":"استخدم الاسم الكامل في جواز السفر أو الاسم الأول واسم العائلة الكامل فقط، وبنفس التهجئة. لا تقبل الأسماء الفارغة.",
    "dates.exact":"يجب أن تتطابق مواعيد الرحلة مع التواريخ في نموذج طلب التأشيرة دون هامش زمني. صحح المستند المختلف وفق المواعيد المؤكدة.",
    "dates.boundary":"موعد المستند خارج فترة السفر في نموذج الطلب. اجعل الحجوزات والخطة تغطي الفترة الصحيحة كاملة.",
    "hr.window":"تبدأ الرحلة في أول يوم للإجازة المعتمدة أو اليوم التالي، وتنتهي في آخر يوم أو اليوم السابق. لا يجوز السفر قبل بداية الإجازة أو بعد نهايتها.",
    "support.conflict":"توجد بيانات متعارضة بين المستند الداعم والمستندات المرجعية. قارن القيم المعروضة مع الأصول وصحح التعارض قبل التقديم.",
    "support.unverified":"تعذّر تأكيد هذه المعلومة من المستندات المرفقة. اطلب دليلاً واضحاً أو تحقق من جهة الإصدار؛ توافق النصوص لا يثبت الأصالة.",
    "evidence.incomplete":"لم تُقرأ بعض الصفحات أو لم يمكن تتبع البيانات إلى مصدر واضح. راجع الأصول وأرفق نسخة أوضح أو تحقق يدوياً قبل الاعتماد على النتيجة.",
})


# Administration workspace and appointment planning.
for item in [
    ('admin_section','Dashboard section','قسم لوحة الإدارة'),
    ('admin_reviews','Reviews','المراجعات'),
    ('admin_access','Access approval and revoke','الموافقة على الوصول وإلغاؤه'),
    ('admin_uploads','Upload categories','فئات رفع المستندات'),
    ('admin_team_log','Team review log','سجل مراجعات الفريق'),
    ('admin_maintenance','Website maintenance','صيانة الموقع'),
    ('super_admin_section','Only the super administrator can manage this section.','إدارة هذا القسم متاحة للمسؤول الرئيسي فقط.'),
    ('reviews_open','New reviews are enabled.','المراجعات الجديدة متاحة.'),
    ('reviews_closed','New reviews are paused.','المراجعات الجديدة متوقفة مؤقتاً.'),
    ('maintenance_title','Service under maintenance','الخدمة قيد الصيانة'),
    ('maintenance_message','The service is currently under maintenance. Please try again later.','الخدمة قيد الصيانة حالياً. يرجى المحاولة لاحقاً.'),
    ('website_live','The website is live.','الموقع متاح.'),
    ('pause_website','Pause website for maintenance','إيقاف الموقع للصيانة'),
    ('resume_website','Resume website','إعادة تشغيل الموقع'),
    ('management_sign_in','Administrator sign-in','تسجيل دخول الإدارة'),
    ('check_service','Check service status','التحقق من حالة الخدمة'),
    ('service_unavailable','Service status is unavailable. Please try again shortly.','تعذر التحقق من حالة الخدمة. يرجى المحاولة بعد قليل.'),
    ('appointment_hint','Upload the actual embassy/visa-centre appointment letter. Our planning rule requires travel to start at least 60 calendar days after the appointment; this is not an embassy processing guarantee.','ارفع خطاب موعد السفارة أو مركز التأشيرات. تشترط قاعدة التخطيط لخدمتنا بدء السفر بعد الموعد بـ60 يوماً تقويمياً على الأقل؛ وليست ضماناً لمدة معالجة السفارة.'),

]:
    _add(*item)

for item in [
    ('visa_program', 'Application category', 'فئة طلب التأشيرة'),
    ('program_schengen', 'Schengen', 'شنغن'),
    ('program_canada', 'Canada', 'كندا'),
    ('program_usa', 'USA', 'الولايات المتحدة'),
    ('program_uk', 'UK', 'المملكة المتحدة'),
    ('schengen_country', 'Schengen country', 'دولة شنغن'),
    ('country_spain', 'Spain', 'إسبانيا'),
    ('country_france', 'France', 'فرنسا'),
    ('country_germany', 'Germany', 'ألمانيا'),
    ('country_italy', 'Italy', 'إيطاليا'),
    ('country_netherlands', 'Netherlands', 'هولندا'),
    ('country_sweden', 'Sweden', 'السويد'),
    ('country_belgium', 'Belgium', 'بلجيكا'),
    ('country_greece', 'Greece', 'اليونان'),
    ('under_processing', 'Under processing', 'قيد التجهيز'),
    ('destination_processing', '{destination} is under processing. Document uploads and reviews are not available yet.', 'خدمة {destination} قيد التجهيز. رفع المستندات ومراجعتها غير متاحين حالياً.'),
    ('spain_workspace', 'Schengen · Spain document review', 'شنغن · مراجعة مستندات إسبانيا'),
    ('schengen_workspace', 'Schengen · {destination} document review', 'شنغن · مراجعة مستندات {destination}'),
    ('combined_hint_schengen', 'Upload each document in its matching section; put all HR files under Employment documents. Cover letter and travel plan may share one file.', 'ارفع كل مستند في الخانة المخصصة له، وارفع جميع ملفات العمل والراتب والإجازة ضمن مستندات العمل. يمكن جمع الخطاب التوضيحي وخطة الرحلة في ملف واحد.'),
    ('review_scope_unavailable', 'This application category is under processing. Choose Schengen and Tourism to continue.', 'فئة الطلب هذه قيد التجهيز. اختر شنغن والسياحة للمتابعة.'),
]:
    _add(*item)

# Gemini narrative review and token cost accounting.
for item in [
 ('reasoning_scope','Gemini reviews letter/plan text against locally extracted reference facts. Advisory findings do not change the factual score.','يراجع Gemini نص الخطاب والخطة مقارنة بالبيانات المستخرجة محلياً. الملاحظات استرشادية ولا تغيّر درجة التحقق.'),
 ('reasoning_unavailable','Gemini could not finish this review. Your local results remain available.','تعذر إكمال مراجعة Gemini. تظل نتائج المراجعة المحلية متاحة.'),
 ('gemini_config_missing','Gemini is not configured. The administrator must add GEMINI_API_KEY to server secrets.','لم يتم إعداد Gemini. يجب على المسؤول إضافة GEMINI_API_KEY إلى أسرار الخادم.'),
 ('reasoning_extracted','Extracted reference field; verify against the original document.','بيان مرجعي مستخرج؛ راجعه في المستند الأصلي.'),
 ('reasoning_retry_quota','A new AI review or retry uses one of your five daily reviews. The initial AI review is included in the submitted review.','تستهلك المراجعة الجديدة أو إعادة المحاولة واحدة من خمس مراجعات يومية. المراجعة الأولى بالذكاء الاصطناعي مشمولة في المراجعة المرسلة.'),
 ('daily_limit','Reviews per Cairo day (maximum 5)','المراجعات يومياً بتوقيت القاهرة (بحد أقصى 5)'),
 ('review_limits_hint','Maximum five reviews per user per Cairo calendar day. Resets at midnight. An hourly limit may be lower.','خمس مراجعات كحد أقصى لكل مستخدم في اليوم بتوقيت القاهرة. يتجدد الحد عند منتصف الليل. قد يكون الحد بالساعة أقل.'),
 ('admin_costs','Gemini usage and cost','استخدام Gemini والتكلفة'),
 ('cost_period','Period (Cairo time)','الفترة (بتوقيت القاهرة)'),
 ('cost_today','Today','اليوم'),('cost_month','This month','هذا الشهر'),('cost_30_days','Last 30 days','آخر 30 يوماً'),
 ('cost_users','Filter by user','تصفية حسب المستخدم'),
 ('cost_requests','AI requests','طلبات الذكاء الاصطناعي'),
 ('cost_input','Input tokens','رموز الإدخال'),('cost_output','Output + thinking tokens','رموز الإخراج والتفكير'),
 ('cost_total_egp','Recorded cost (EGP)','التكلفة المسجلة (جنيه مصري)'),
 ('cost_unavailable','Cost records are unavailable. Check the Gemini database migration and connection.','سجلات التكلفة غير متاحة. تحقق من تحديث قاعدة البيانات والاتصال.'),
 ('cost_empty','No Gemini requests in this period. Local-only reviews have no Gemini cost.','لا توجد طلبات Gemini في هذه الفترة. المراجعات المحلية لا تستهلك Gemini.'),
 ('cost_unknown','Usage is unknown for {usage} requests; EGP conversion is missing for {fx}. Totals exclude unknown amounts.','استخدام غير معروف لـ{usage} طلبات؛ وتحويل الجنيه غير متاح لـ{fx}. الإجماليات لا تشمل القيم المجهولة.'),
 ('cost_rates_note','Costs are estimates from actual provider token totals, including thinking and cached-input pricing. Each request keeps its price and USD/EGP rate snapshot. Taxes and bank charges are excluded.','التكلفة تقديرية وفق الرموز الفعلية للمزود، بما فيها التفكير وتسعير الإدخال المخزن. يحتفظ كل طلب بأسعاره وسعر صرف الدولار. لا تشمل الضرائب ورسوم البنك.'),
 ('cost_by_user','Usage by user','الاستخدام حسب المستخدم'),
 ('cost_actual','Actual usage per review request','الاستخدام الفعلي لكل طلب مراجعة'),
 ('cost_files','Estimated allocation per file','التوزيع التقديري لكل ملف'),
 ('cost_allocation_note','Gemini bills the combined request. Per-file input, output and cost shares are estimates allocated by each file’s share of the sent context bytes, including shared prompt/output overhead. They sum to the request totals; they are not separately metered by Google.','يحاسب Gemini على الطلب المجمع. أنصبة الرموز والتكلفة لكل ملف تقديرية حسب حجم سياقه المرسل، مع توزيع التعليمات والإخراج المشترك. مجموعها يساوي إجمالي الطلب ولا يقيسها Google منفصلة.'),
 ('reserved','Pending / usage unknown','قيد التنفيذ / الاستخدام غير معروف'),
 ('cost_col_user','User','المستخدم'),('cost_col_date','Cairo time','توقيت القاهرة'),
 ('cost_col_review_id','Review ID','معرف المراجعة'),('cost_col_status','Status','الحالة'),
 ('cost_col_model','Model','النموذج'),('cost_col_requests','Requests','الطلبات'),
 ('cost_col_input_tokens','Input tokens','رموز الإدخال'),('cost_col_output_tokens','Output tokens','رموز الإخراج'),
 ('cost_col_thinking_tokens','Thinking tokens','رموز التفكير'),('cost_col_billable_output_tokens','Output + thinking','الإخراج والتفكير'),
 ('cost_col_cached_input_tokens','Cached input tokens','رموز الإدخال المخزن'),
 ('cost_col_cost_usd','Cost USD','التكلفة بالدولار'),('cost_col_cost_egp','Cost EGP','التكلفة بالجنيه'),
 ('cost_col_usd_egp','USD/EGP rate','سعر الدولار بالجنيه'),('cost_col_fx_date','Rate date','تاريخ الصرف'),
 ('cost_col_filename','File','الملف'),('cost_col_context_mode','Context sent','السياق المرسل'),
 ('cost_col_unknown','Unknown amounts','قيم غير معروفة'),
]:
    _add(*item)
_add('privacy','Files are processed in server memory. When you submit a letter or travel plan, its text and relevant supporting context are sent to Google Gemini using the paid API. Passports, applications, hotels and flights use locally extracted facts, without sending their PDFs. The app stores usage, filenames and costs, not document contents or AI responses.','تُعالج الملفات في ذاكرة الخادم. عند إرسال خطاب أو خطة رحلة يُرسل نصها والسياق الداعم إلى Google Gemini عبر الواجهة المدفوعة. تُرسل بيانات الجواز والطلب والفندق والطيران المستخرجة محلياً دون ملفاتها الأصلية. يحفظ التطبيق الاستخدام وأسماء الملفات والتكلفة، ولا يحفظ محتوى المستندات أو ردود الذكاء الاصطناعي.')

_add('cost_context_extracted_fields','Extracted fields','البيانات المستخرجة')
_add('cost_context_full_text','Document text','نص المستند')
for _cost_item in (
 ('cost_calculator','Estimate the cost of one file','تقدير تكلفة ملف واحد'),
 ('cost_calculator_note','Planning calculator, not recorded usage. Enter input tokens and total output including thinking. No Gemini request is sent.','حاسبة تقديرية وليست استخداماً مسجلاً. أدخل رموز الإدخال والإخراج شاملاً التفكير. لا يُرسل أي طلب إلى Gemini.'),
 ('cost_estimated_usd','Estimated cost (USD)','التكلفة التقديرية بالدولار'),
 ('cost_estimated_egp','Estimated cost (EGP)','التكلفة التقديرية بالجنيه'),
 ('cost_formula','USD = (input tokens × {input} + output/thinking tokens × {output}) ÷ 1,000,000. Standard uncached rates.','الدولار = (رموز الإدخال × {input} + رموز الإخراج والتفكير × {output}) ÷ 1,000,000. أسعار عادية بدون تخزين مؤقت.'),
 ('cost_fx_snapshot','USD/EGP: {rate} · Rate date: {date}','الدولار بالجنيه: {rate} · تاريخ السعر: {date}'),
 ('cost_fx_unavailable','USD/EGP conversion is unavailable. USD estimates remain available; no EGP amount was invented.','تحويل الدولار إلى الجنيه غير متاح. يظل التقدير بالدولار متاحاً دون افتراض سعر صرف.'),
 ('cost_avg_review','Average per AI review','المتوسط لكل مراجعة ذكاء اصطناعي'),
 ('cost_avg_file','Estimated average per document','المتوسط التقديري لكل مستند'),
 ('cost_avg_input','Average input tokens','متوسط رموز الإدخال'),
 ('cost_avg_output','Average output + thinking tokens','متوسط رموز الإخراج والتفكير'),
 ('cost_avg_egp','Average cost (EGP)','متوسط التكلفة بالجنيه'),
 ('cost_averages_note','Averages include recorded values only. Unknown usage/cost stays unknown. Per-document figures are allocated estimates, not independent provider measurements.','تشمل المتوسطات القيم المسجلة فقط. تظل الرموز والتكاليف المجهولة غير معروفة. أرقام المستندات أنصبة تقديرية وليست قياسات مستقلة من المزود.'),
 ('cost_by_category','Estimated averages by document type','المتوسطات التقديرية حسب نوع المستند'),
 ('cost_other','Unspecified type','نوع غير محدد'),
 ('cost_col_category','Document type','نوع المستند'),('cost_col_files','Files','الملفات'),
 ('cost_col_avg_input_tokens','Average input tokens','متوسط رموز الإدخال'),
 ('cost_col_avg_output_tokens','Average output + thinking tokens','متوسط رموز الإخراج والتفكير'),
 ('cost_col_avg_cost_egp','Average EGP cost','متوسط التكلفة بالجنيه'),
 ('cost_col_fallback_from','Quota fallback from','النموذج الذي بلغ حد الاستخدام'),
 ('reasoning_fallback_used','Gemini 3.8 reached its quota. This review used Gemini 3.6 Flash.','بلغ Gemini 3.8 حد الاستخدام. استُخدم Gemini 3.6 Flash لهذه المراجعة.'),
):_add(*_cost_item)
_add('cost_requests','AI reviews','مراجعات الذكاء الاصطناعي')

# Multi-format, financial and bilingual evidence review.
for item in [
 ('reasoning_title','Letter, itinerary, bank and translation review','مراجعة الخطاب والخطة وكشف الحساب والترجمة'),
 ('reasoning_scope','Reference documents use local JSON/text. Only bank/supporting files can use PDF input when visual reading is needed. Findings are advisory; the factual score is separate.','تستخدم المستندات المرجعية بيانات ونصوصاً مستخرجة محلياً. يمكن قراءة كشف الحساب والمستندات الداعمة بصيغة PDF عند الحاجة البصرية. الملاحظات استرشادية ودرجة الوقائع منفصلة.'),
 ('bank_scope','Upload the complete statement covering the latest six months, including transactions, opening/closing dates and the latest balance.','ارفع كشف الحساب كاملاً لآخر ستة أشهر، شاملاً الحركات وفترة الكشف وآخر رصيد.'),
 ('word_conversion_failed','This Word file could not be read completely. Save a readable DOCX or PDF copy and upload it again.','تعذرت قراءة ملف Word بالكامل. احفظ نسخة DOCX أو PDF واضحة وارفعها مجدداً.'),
 ('upload_formats','PDF, Word (.doc/.docx), HTML, text and images are accepted. Word/HTML are converted locally; scripts and macros are never run.','تُقبل ملفات PDF وWord وHTML والنصوص والصور. يُحوّل Word وHTML محلياً دون تشغيل النصوص البرمجية أو وحدات الماكرو.'),
 ('converted_copy_note','Word/HTML documents have reflowed evidence copies; cited page numbers refer to those converted copies.','لمستندات Word وHTML نسخ محوّلة معاد تنسيقها؛ تشير أرقام الصفحات إلى النسخ المحوّلة.'),
 ('review_bank_problems','Bank statement points requiring explanation','ملاحظات كشف الحساب التي تحتاج توضيحاً'),
 ('review_trip_budget','Estimated tourism trip cost','التكلفة التقديرية للرحلة السياحية'),
 ('review_sources','Source evidence','الأدلة من المستندات'),
 ('review_visual_quote','Read visually from the PDF; verify this quotation and value in the original.','قُرئ من صورة PDF؛ راجع الاقتباس والقيمة في المستند الأصلي.'),
 ('review_action_remove','Remove','احذف'),('review_action_correct','Correct','صحّح'),('review_action_verify','Verify','تحقّق'),
 ('reasoning_kind_translation_error','English translation differs from the Arabic original','الترجمة الإنجليزية تختلف عن الأصل العربي'),
 ('bank_salary_missing','The HR states a monthly {basis} salary of {amount} {currency}, but no exact matching credit was found in the completely read months: {months}. Confirm payroll dates, deductions and split payments.','يذكر خطاب العمل راتباً شهرياً {basis} بقيمة {amount} {currency}، ولم تظهر إضافة مطابقة تماماً في الأشهر المقروءة بالكامل: {months}. تحقق من مواعيد الصرف والاستقطاعات والدفعات المجزأة.'),
 ('bank_salary_currency','The HR salary is {amount} {salary_currency}, while this account is in {currency}. A direct salary match cannot be established.','الراتب في خطاب العمل {amount} {salary_currency}، بينما الحساب بعملة {currency}. لا يمكن تأكيد التطابق المباشر.'),
 ('bank_large_credit','On {date}, credits of {amount} {currency} were identified. Their share of the comparable total incoming funds is {share}%. This meets the configured large-credit rule; explain and document the source.','ظهرت في {date} إضافات بقيمة {amount} {currency}. حصتها من إجمالي الإيداعات القابلة للمقارنة {share}٪. تحقق شرط الإيداع الكبير؛ وضّح مصدره وأرفق ما يؤيده.'),
 ('bank_short_window','The supplied statement covers {start} to {end}; it does not establish the full six-month review window.','يغطي الكشف المرفق الفترة من {start} إلى {end} ولا يثبت تغطية نافذة المراجعة الكاملة لستة أشهر.'),
 ('bank_flag_explanation','This is a request for explanation, not an authenticity finding or evidence of illegal funds. Totals and absences depend on readable, complete transaction coverage.','هذه ملاحظة لطلب توضيح، وليست حكماً على الأصالة أو دليلاً على أموال غير مشروعة. تعتمد الإجماليات وعدم العثور على حركة على اكتمال الحركات ووضوحها.'),
 ('salary_net','net','صافياً'),('salary_gross','gross','إجمالياً'),('salary_unknown','stated','مذكوراً'),('salary_unspecified','stated','مذكوراً'),
 ('budget_estimate_note','Planning estimates include food, local transport and tourism activities, plus intercity transport and quoted hotel/flight totals. They are not live prices or consular minimums. Unknown prices remain missing.','تشمل التقديرات الطعام والتنقل المحلي والأنشطة السياحية والتنقل بين المدن وأسعار الفندق والطيران الواردة بالمستندات. ليست أسعاراً مباشرة أو حداً قنصلياً. تبقى الأسعار غير المتاحة بيانات ناقصة.'),
 ('budget_total_trip','Estimated total trip cost','إجمالي تكلفة الرحلة التقديرية'),
 ('budget_remaining_trip','Estimated amount still needed','المبلغ التقديري المتبقي'),
 ('budget_egp_estimate','Approximately EGP {low}–{high}; exchange-rate date: {date}.','نحو {low}–{high} جنيه مصري؛ تاريخ سعر الصرف: {date}.'),
 ('budget_city_estimate','{city}: {days} days × EUR {low}–{high} per day, excluding hotel and flights.','{city}: {days} أيام × {low}–{high} يورو يومياً، دون الفندق والطيران.'),
 ('budget_latest_balance','Latest verified applicant balance: {amount} {currency}, statement ending {date}.','آخر رصيد متحقق لمقدم الطلب: {amount} {currency}، وينتهي الكشف في {date}.'),
 ('budget_result_below_estimate','The balance is below the lower estimated remaining trip cost.','الرصيد أقل من الحد الأدنى للتكلفة المتبقية التقديرية.'),
 ('budget_result_within_range','The balance falls inside the estimated remaining-cost range; allow for uncertainty.','يقع الرصيد داخل نطاق التكلفة المتبقية التقديرية؛ ضع هامشاً لعدم اليقين.'),
 ('budget_result_covers_estimated_range','The balance covers this estimated remaining-cost range, subject to access to the funds and unpriced extras.','يغطي الرصيد نطاق التكلفة المتبقية التقديري، بشرط إتاحة الأموال واحتساب المصروفات غير المسعرة.'),
 ('budget_result_partial_estimate','Some costs are unknown, so affordability is not established.','بعض التكاليف غير معروفة، فلا يمكن تأكيد كفاية الرصيد.'),
 ('budget_result_unknown','The currency conversion or available balance is unknown.','تحويل العملة أو الرصيد المتاح غير معروف.'),
 ('budget_missing_data','Estimate is incomplete. Missing or unverified: {items}.','التقدير غير مكتمل. بيانات ناقصة أو غير متحققة: {items}.'),
 ('budget_missing_city_evidence','city evidence','دليل المدينة'),('budget_missing_trip_day_coverage','trip dates/day coverage','تواريخ الرحلة وتغطية الأيام'),
 ('budget_missing_transport_range','transport estimate','تقدير التنقل'),('budget_missing_reservation_evidence','booking price evidence','دليل سعر الحجز'),
 ('budget_missing_currency_conversion','exchange rate','سعر الصرف'),('budget_missing_flight_price','flight price','سعر الطيران'),
 ('budget_missing_hotel_price','hotel prices','أسعار الفنادق'),('budget_missing_verified_latest_applicant_balance','verified latest applicant balance','آخر رصيد متحقق لمقدم الطلب'),
 ('budget_missing_city_cost_estimates','city cost estimates','تقديرات تكلفة المدن'),
 ('cost_context_extracted_text','Locally extracted text','نص مستخرج محلياً'),('cost_context_pdf_visual','PDF and available local text','PDF والنص المحلي المتاح'),
 ('privacy','Documents are processed in server memory. Gemini receives JSON/text for passports, visa forms, hotels, flights, HR and insurance. Bank/supporting files may use PDF input for visual reading. Usage, filenames and estimated costs are stored, not document text or AI answers.','تُعالج المستندات في ذاكرة الخادم. يتلقى Gemini بيانات ونصوص الجواز والطلب والفندق والطيران والعمل والتأمين. قد يُستخدم PDF لكشف الحساب والمستندات الداعمة للقراءة البصرية. يُحفظ الاستخدام وأسماء الملفات والتكلفة التقديرية، دون نصوص المستندات أو إجابات الذكاء الاصطناعي.'),
]:
    _add(*item)

_add('text_section','Text section','قسم النص')
_add('usa_workspace','USA · Local DS-160 consistency review','الولايات المتحدة · مراجعة محلية لتطابق بيانات DS-160')
_add('usa_review_description','Compare DS-160 answers with the passport and client form. Check the hotel name and check-in/check-out dates.','قارن إجابات DS-160 بجواز السفر واستمارة العميل، وتحقق من اسم الفندق وتاريخي الوصول والمغادرة في الحجز.')
_add('usa_upload_hint','Upload the full DS-160 application/review printout, hotel booking, passport and client form. A confirmation page alone does not contain all the answers needed for comparison.','ارفع نسخة الطلب الكامل أو مراجعة بيانات DS-160، وحجز الفندق، وجواز السفر، واستمارة العميل. صفحة التأكيد وحدها لا تحتوي على جميع الإجابات اللازمة للمقارنة.')
_add('usa_privacy','USA documents are read locally into structured fields and text. No Gemini or other external AI requests are made.','تُقرأ مستندات الولايات المتحدة محلياً إلى حقول ونصوص منظمة. لا تُرسل أي طلبات إلى Gemini أو أي ذكاء اصطناعي خارجي.')
_add('usa_results','USA document consistency review','مراجعة تطابق مستندات الولايات المتحدة')
_add('usa_wrong_passport_verified','The uploaded passport belongs to a different applicant. Upload the passport matching the DS-160 and client form; do not replace their identity details with this passport.','جواز السفر المرفوع يخص شخصاً آخر. ارفع جواز السفر المطابق لنموذج DS-160 واستمارة العميل، ولا تستبدل بياناتهما ببيانات هذا الجواز.')
_add('usa_wrong_passport_provisional','Possible wrong passport: the name and number read from this image differ from the DS-160 and client form. Verify the original passport; the image reading is provisional.','قد يكون جواز السفر المرفوع خاطئاً: الاسم والرقم المقروءان من الصورة يختلفان عن DS-160 واستمارة العميل. تحقق من أصل الجواز؛ قراءة الصورة لم تُؤكد بعد.')
_add('usa_wrong_passport_title','Wrong passport uploaded','تم رفع جواز سفر لشخص آخر')
_add('usa_wrong_passport_possible','Possible wrong passport uploaded','قد يكون جواز السفر المرفوع لشخص آخر')
_add('usa_problem_title','Problems to correct','مشكلات تحتاج إلى تصحيح')
_add('usa_wrong_value','Wrong / uploaded value','القيمة الخاطئة أو المرفوعة')
_add('usa_right_value','Correct / expected value','القيمة الصحيحة أو المطلوبة')
_add('usa_source_details','Show source evidence','عرض أدلة المستندات')
_add('usa_evidence_title','Source evidence','أدلة المستندات')
_add('usa_converted_text_evidence','Converted text evidence · original text section','دليل نصي محوّل · قسم من النص الأصلي')
_add('usa_check_unavailable','The comparison could not be completed from the supplied fields.','تعذر إكمال المقارنة بالحقول المقدمة.')
_add('usa_ocr_note','The image reading needs verification against the original.','تحتاج قراءة الصورة إلى التحقق من الأصل.')
_add('field_passport_identity','Passport holder','صاحب جواز السفر')
_add('field_hotel_name','Hotel name','اسم الفندق')
_add('field_us_contact_hotel','DS-160 U.S. contact — hotel workflow','جهة الاتصال الأمريكية في DS-160 — مسار الفندق')
_add('usa_contact_hotel_workflow','This review workflow expects hotel contact information when a hotel booking is supplied. Compare the DS-160 contact section with the hotel details printed on the booking.','يتطلب مسار المراجعة هذا بيانات اتصال الفندق عند تقديم حجز فندقي. قارن قسم جهة الاتصال في DS-160 ببيانات الفندق المطبوعة على الحجز.')
_add('usa_checked_document','Document being checked','المستند الجاري فحصه')
_add('usa_comparison_document','Comparison document','المستند المستخدم للمقارنة')
_add('usa_checked_value','Value in the checked document','القيمة في المستند الجاري فحصه')
_add('usa_comparison_value','Value in the comparison document','القيمة في مستند المقارنة')
_add('usa_no_comparison_value','No readable comparison value','لا تتوفر قيمة مقروءة للمقارنة')
_add('usa_value_not_extracted','Value not extracted','لم تُستخرج القيمة')
_add('usa_document_not_supplied','Not supplied','لم يُرفق')
_add('usa_source_explainer','Values and evidence come from your uploaded documents. Each comparison names its file and page or text section. A blank value means the reader could not extract it; it is not proof of an error.','تأتي القيم والأدلة من مستنداتك المرفوعة. تُذكر أسماء الملفات وأرقام الصفحات أو أقسام النص لكل مقارنة. تعني القيمة الفارغة أن القارئ تعذر عليه استخراجها، ولا تثبت وجود خطأ.')
_add('usa_missing_hotel_contacts','Not available on the booking: {fields}. These details need verification; no replacement value was guessed.','غير متوفر في الحجز: {fields}. تحتاج هذه البيانات إلى تحقق؛ ولم تُخمن قيم بديلة.')
_add('field_hotel_phone','Hotel phone','هاتف الفندق')
_add('field_hotel_email','Hotel email','البريد الإلكتروني للفندق')
_add('usa_verification','Needs verification','يحتاج إلى تحقق')
_add('usa_coverage','Checks matched','فحوص متطابقة')
_add('usa_incomplete','Some comparisons could not be completed. Read the verification notes before using these results.','تعذر إكمال بعض المقارنات. اقرأ ملاحظات التحقق قبل الاعتماد على النتائج.')
_add('usa_fields','Extracted fields and comparison details','الحقول المستخرجة وتفاصيل المقارنة')
_add('usa_download_json','Download structured review (JSON)','تنزيل المراجعة المنظمة (JSON)')
_add('usa_reference_conflict','References disagree; verify the original documents before changing DS-160.','تختلف المستندات المرجعية؛ تحقق من الأصول قبل تعديل DS-160.')
_add('usa_field_unavailable','Missing, ambiguous or OCR-only values cannot establish a confirmed mismatch.','القيم المفقودة أو الملتبسة أو المقروءة فقط بالتعرف الضوئي لا تثبت وجود اختلاف مؤكد.')
_add('usa_hotel_contact_name','DS-160 provides a U.S. contact organization. Verify whether this is the hotel and whether its name is abbreviated.','يتضمن DS-160 اسم جهة اتصال في الولايات المتحدة. تحقق مما إذا كانت هذه الجهة هي الفندق وما إذا كان الاسم مختصراً.')
_add('usa_salary_basis','Monthly salary and average monthly income can have different bases. Verify the amounts and their meaning before correcting them.','قد يختلف أساس الراتب الشهري عن متوسط الدخل الشهري. تحقق من القيم ومعناها قبل تعديلها.')
_add('usa_duration_basis','When DS-160 states days without a departure date, arrival and departure may both count as travel days. The comparison allows either day-count convention.','عندما يذكر DS-160 عدد الأيام دون تاريخ المغادرة، قد يُحسب يوما الوصول والمغادرة ضمن مدة الرحلة. تراعي المقارنة طريقتي حساب الأيام.')
_add('usa_not_eligibility','These checks compare supplied information; they do not assess visa eligibility or document authenticity.','تقارن هذه الفحوص البيانات المقدمة؛ ولا تحدد أهلية التأشيرة أو صحة المستندات.')
for _field,_en,_ar in (
    ('surname','Surname','اسم العائلة'),('given_names','Given names','الأسماء الأولى'),
    ('nationality','Nationality','الجنسية'),('gender','Sex','الجنس'),
    ('arrival_date','Arrival date','تاريخ الوصول'),('departure_date','Departure date','تاريخ المغادرة'),
    ('length_of_stay','Length of stay','مدة الإقامة'),('hotel_address','Hotel/stay address','عنوان الفندق أو الإقامة'),
    ('stay_city','City of stay','مدينة الإقامة'),('stay_state','State of stay','ولاية الإقامة'),
    ('stay_zip','ZIP/postal code','الرمز البريدي'),('email','Email','البريد الإلكتروني'),
    ('phone','Phone','الهاتف'),('marital_status','Marital status','الحالة الاجتماعية'),
    ('employer_name','Employer name','اسم جهة العمل'),('occupation','Occupation','المهنة'),
    ('document_coverage','Document coverage','تغطية المستند'),
    ('national_id_number','National ID number','الرقم القومي'),('birth_city','City of birth','مدينة الميلاد'),
    ('birth_country','Country of birth','دولة الميلاد'),('employment_start_date','Employment start date','تاريخ بدء العمل'),
    ('monthly_salary','Monthly salary','الراتب الشهري'),('monthly_income','Average monthly income','متوسط الدخل الشهري'),
    ('employer_address','Employer address','عنوان جهة العمل'),('employer_phone','Employer phone','هاتف جهة العمل'),
    ('education_name','Educational institution','المؤسسة التعليمية'),('education_course','Course of study','التخصص الدراسي'),
    ('education_period','Education period','فترة الدراسة'),('father_full_name',"Father's full name",'اسم الأب بالكامل'),
    ('father_date_of_birth',"Father's date of birth",'تاريخ ميلاد الأب'),('mother_full_name',"Mother's full name",'اسم الأم بالكامل'),
    ('mother_date_of_birth',"Mother's date of birth",'تاريخ ميلاد الأم'),('spouse_full_name',"Spouse's full name",'اسم الزوج أو الزوجة'),
    ('spouse_date_of_birth',"Spouse's date of birth",'تاريخ ميلاد الزوج أو الزوجة'),('spouse_nationality',"Spouse's nationality",'جنسية الزوج أو الزوجة'),
    ('languages','Languages','اللغات'),('trip_sponsor','Trip sponsor','المتكفل بمصاريف الرحلة'),
    ('social_facebook','Facebook account','حساب فيسبوك'),('social_instagram','Instagram account','حساب إنستجرام'),
    ('social_linkedin','LinkedIn account','حساب لينكدإن'),('social_twitter','Twitter / X account','حساب تويتر أو إكس'),
    ('prior_refusal','Previous U.S. visa refusal','رفض تأشيرة أمريكية سابق'),('prior_us_visit','Previous U.S. visit','زيارة سابقة للولايات المتحدة'),
    ('military_service','Military service','الخدمة العسكرية'),('relatives_us','Relatives in the U.S.','الأقارب في الولايات المتحدة'),
):
    _add('field_'+_field,_en,_ar)

_add('bank_salary_uncertain','The HR states {amount} {currency}, but salary credits could not be verified for: {months}. Check the account, readable transaction rows and payroll details.','يذكر خطاب العمل {amount} {currency}، وتعذر التحقق من إضافات الراتب للأشهر: {months}. راجع الحساب وصفوف الحركات المقروءة وتفاصيل صرف الراتب.')
_add('converted_copy_note','Word/HTML evidence is converted locally. Native-text citations use text sections; PDF citations refer to the reflowed evidence copy.','تُحوّل أدلة Word وHTML محلياً. تشير إحالات النص الأصلي إلى أقسام النص، وإحالات PDF إلى نسخة الأدلة المعاد تنسيقها.')
_add('budget_payment_assumption','Bookings without explicit payment confirmation are included in the estimated amount still needed.','تُحتسب الحجوزات التي لا يوجد تأكيد صريح لسدادها ضمن المبلغ التقديري المتبقي.')

_add('supporting_translation_hint','Upload the Arabic original and matching English translation together or as separate files. Arabic anchors the translation comparison.','ارفع الأصل العربي وترجمته الإنجليزية المطابقة معاً أو في ملفات منفصلة. يُعتمد الأصل العربي مرجعاً لمقارنة الترجمة.')
_add('bank_large_credit_absolute','On {date}, credits of {amount} {currency} meet the EGP 500,000 rule. Their share of total incoming funds could not be verified; explain and document the source.','ظهرت في {date} إضافات بقيمة {amount} {currency} تستوفي حد 500,000 جنيه. تعذّر التحقق من حصتها من إجمالي الإيداعات؛ وضّح مصدرها وأرفق ما يؤيده.')
