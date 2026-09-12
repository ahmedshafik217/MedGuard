"""Minimal hand-rolled i18n: a flat dict of key -> {en, ar}. Deliberately
simple (no Flask-Babel/.po files) since the app only needs two languages.
Add new keys here as templates need them; t() falls back to the key itself
(and prints a note) if a translation is missing, so typos are visible
immediately instead of silently showing blank text."""

STRINGS = {
    "site_name": {"en": "Al Shefa Specialized Hospital", "ar": "مستشفى الشفاء التخصصي"},
    "app_tagline": {"en": "Patient Antibiotic Safety Record", "ar": "سجل سلامة المضادات الحيوية للمريض"},
    # The app's own product identity, shown big on the welcome/login page
    # hero -- distinct from "site_name" above, which is the hospital
    # institution's name (still used in the navbar/footer/PDF exports).
    "app_display_name": {"en": "AmanBio", "ar": "أمان بايو"},
    "app_identity_tagline": {
        "en": "Your antibiotic safety identity (AI supported)",
        "ar": "هويتك للاستخدام الآمن للمضاد الحيوي (مدعوم بالذكاء الاصطناعي)",
    },
    "footer_credit": {
        "en": "Built for Al Shefa Specialized Hospital",
        "ar": "صُمم لمستشفى الشفاء التخصصي",
    },
    # --- New hospital-provided branded design (welcome page + sitewide
    # header/footer), added for the AmanBio visual redesign. The hospital
    # motto ("hospital_motto") is a brand slogan, not a normal UI string --
    # per the reference design it's always shown in Arabic script even on
    # the English site, with "hospital_motto_gloss" as a small English
    # translation underneath (only shown in English mode).
    "hospital_motto": {"en": "الشفاء غاية ورعاية وأمان", "ar": "الشفاء غاية ورعاية وأمان"},
    "hospital_motto_gloss": {"en": "Together for a Safer Care", "ar": ""},
    "hero_word_remember": {"en": "Remember", "ar": "تذكر"},
    "hero_word_check": {"en": "Check", "ar": "تحقق"},
    "hero_word_protect": {"en": "Protect", "ar": "احم نفسك"},
    "hero_cursive_line1": {"en": "Better Care", "ar": "رعاية أفضل"},
    "hero_cursive_line2": {"en": "Safer Tomorrow", "ar": "لمستقبل أكثر صحة"},
    "feature_history_title": {"en": "Antibiotic History", "ar": "سجل المضادات الحيوية"},
    "feature_history_desc": {"en": "Keep track of past antibiotics", "ar": "تابع استخدام المضادات الحيوية السابقة"},
    "feature_allergy_title": {"en": "Allergy Check", "ar": "التحقق من الحساسية"},
    "feature_allergy_desc": {"en": "Avoid allergic reactions", "ar": "تجنب ردود الفعل التحسسية"},
    "feature_pregnancy_title": {"en": "Pregnancy Safety", "ar": "سلامة الحمل"},
    "feature_pregnancy_desc": {"en": "Prevent contraindicated use", "ar": "منع الاستخدام غير المناسب"},
    "feature_risk_title": {"en": "Risk Alerts", "ar": "تنبيهات المخاطر"},
    "feature_risk_desc": {"en": "Identify important precautions", "ar": "التعرف على الاحتياطات المهمة"},
    "najran_label": {"en": "Najran", "ar": "نجران"},
    "najran_tagline": {"en": "For a Healthier Community", "ar": "من أجل مجتمع أكثر صحة"},
    "staff_card_desc": {
        "en": "For Doctors, Pharmacists and Authorized Staff",
        "ar": "للأطباء والصيادلة والكوادر المصرح لهم",
    },
    "patient_card_title": {"en": "Patient Login", "ar": "دخول المريض"},
    "patient_card_desc": {
        "en": "Access your Antibiotic Safety ID",
        "ar": "الوصول إلى هويتك لسلامة المضادات الحيوية",
    },
    "new_patient_card_title": {"en": "New Patient", "ar": "مريض جديد"},
    "new_patient_card_desc": {
        "en": "Create a new patient record and get your Antibiotic ID",
        "ar": "إنشاء سجل مريض جديد والحصول على هويتك للمضادات الحيوية",
    },
    "login_button": {"en": "Login", "ar": "تسجيل الدخول"},
    "create_record_button": {"en": "Create Record", "ar": "إنشاء سجل جديد"},
    "strip_safe_title": {"en": "Safe Antibiotic Use", "ar": "الاستخدام الآمن للمضادات الحيوية"},
    "strip_safe_desc": {"en": "For you. For your community.", "ar": "من أجلك. من أجل مجتمعك."},
    "strip_support_title": {"en": "Support Clinical Decisions", "ar": "دعم القرارات السريرية"},
    "strip_support_desc": {"en": "Evidence-based alerts", "ar": "تنبيهات مبنية على الأدلة"},
    "strip_reduce_title": {"en": "Reduce Antibiotic Misuse", "ar": "الحد من إساءة استخدام المضادات الحيوية"},
    "strip_reduce_desc": {"en": "A healthier tomorrow", "ar": "لمستقبل أكثر صحة"},
    "strip_community_title": {"en": "Community Health", "ar": "صحة المجتمع"},
    "strip_community_desc": {"en": "Our commitment to Najran", "ar": "ملتزمون من أجل نجران"},
    "footer_region": {"en": "Najran, KSA", "ar": "نجران، المملكة العربية السعودية"},
    "disclaimer": {
        "en": "This tool supports clinical decisions. It does not replace the judgment of a "
              "licensed physician or pharmacist. Always verify alerts independently.",
        "ar": "هذه الأداة تساعد في اتخاذ القرار السريري ولا تغني عن تقييم الطبيب أو الصيدلي "
              "المختص. يجب دائماً التحقق من التنبيهات بشكل مستقل.",
    },
    "choose_login_title": {"en": "Who is logging in?", "ar": "من يقوم بتسجيل الدخول؟"},
    "owner_login_btn": {"en": "Hospital Staff Login", "ar": "دخول موظفي المستشفى"},
    "patient_login_btn": {"en": "Patient", "ar": "مريض"},
    "new_patient_btn": {"en": "New patient — create a record", "ar": "مريض جديد — إنشاء سجل"},
    "username": {"en": "Username", "ar": "اسم المستخدم"},
    "password": {"en": "Password", "ar": "كلمة المرور"},
    "password_optional": {"en": "Password (optional)", "ar": "كلمة المرور (اختياري)"},
    "patient_id": {"en": "Patient ID", "ar": "رقم المريض"},
    "login": {"en": "Log in", "ar": "تسجيل الدخول"},
    "logout": {"en": "Log out", "ar": "تسجيل الخروج"},
    "back": {"en": "Back", "ar": "رجوع"},
    "full_name_optional": {"en": "Full name (optional)", "ar": "الاسم الكامل (اختياري)"},
    "date_of_birth": {"en": "Date of birth", "ar": "تاريخ الميلاد"},
    "gender": {"en": "Gender", "ar": "الجنس"},
    "male": {"en": "Male", "ar": "ذكر"},
    "female": {"en": "Female", "ar": "أنثى"},
    "create_record": {"en": "Create my record", "ar": "إنشاء سجلي"},
    "owner_dashboard": {"en": "Owner Dashboard", "ar": "لوحة تحكم المالك"},
    "all_patients": {"en": "All Patients", "ar": "جميع المرضى"},
    "antibiotic_reference": {"en": "Antibiotic Reference Database", "ar": "قاعدة بيانات المضادات الحيوية"},
    "audit_log": {"en": "Audit Log", "ar": "سجل النشاط"},
    "search_patients": {"en": "Search by patient ID or name...", "ar": "ابحث برقم المريض أو الاسم..."},
    "staff_search_placeholder": {
        "en": "Enter the patient's full name or ID exactly...",
        "ar": "اكتب اسم المريض بالكامل أو رقم المريض بالضبط...",
    },
    "staff_search_hint": {
        "en": "Type a patient's full name or ID above to open their record. "
              "For patient privacy, staff accounts can't browse the full patient list.",
        "ar": "اكتب اسم المريض بالكامل أو رقم المريض في الأعلى لعرض سجله. "
              "حفاظاً على خصوصية المرضى، لا يمكن لحسابات الموظفين تصفح كل قائمة المرضى.",
    },
    "no_patient_found": {
        "en": "No patient found with that exact name or ID. Double-check the spelling with the patient.",
        "ar": "لا يوجد مريض بهذا الاسم أو الرقم بالضبط. تأكد من التهجئة مع المريض.",
    },
    "view": {"en": "View", "ar": "عرض"},
    "patient_dashboard": {"en": "My Health Record", "ar": "سجلي الصحي"},
    "my_profile": {"en": "My Profile", "ar": "بياناتي"},
    "my_allergies": {"en": "My Allergies", "ar": "الحساسية"},
    "my_conditions": {"en": "My Medical Conditions", "ar": "الحالات المرضية"},
    "antibiotic_history": {"en": "Antibiotic History", "ar": "سجل المضادات الحيوية"},
    "add_antibiotic": {"en": "Add a new antibiotic", "ar": "إضافة مضاد حيوي جديد"},
    "add_allergy": {"en": "Add allergy", "ar": "إضافة حساسية"},
    "add_condition": {"en": "Add condition", "ar": "إضافة حالة مرضية"},
    "antibiotic_name": {"en": "Antibiotic name", "ar": "اسم المضاد الحيوي"},
    "dose": {"en": "Dose", "ar": "الجرعة"},
    "duration": {"en": "Duration", "ar": "المدة"},
    "prescribed_by_optional": {"en": "Prescribed by (optional)", "ar": "وصفه (اختياري)"},
    "prescribed_date": {"en": "Date prescribed", "ar": "تاريخ الوصف"},
    "submit_check": {"en": "Add & check for safety alerts", "ar": "إضافة والتحقق من التنبيهات"},
    "pregnancy_status": {"en": "Pregnancy status", "ar": "حالة الحمل"},
    "pregnant": {"en": "Currently pregnant", "ar": "حامل حالياً"},
    "not_pregnant": {"en": "Not pregnant", "ar": "غير حامل"},
    "not_applicable": {"en": "Not applicable", "ar": "لا ينطبق"},
    "unknown": {"en": "Unknown / not recorded", "ar": "غير معروف / غير مسجل"},
    "save": {"en": "Save", "ar": "حفظ"},
    "cancel": {"en": "Cancel", "ar": "إلغاء"},
    "no_records_yet": {"en": "No records yet.", "ar": "لا توجد سجلات بعد."},
    "severity": {"en": "Severity", "ar": "الشدة"},
    "reaction_optional": {"en": "Reaction (optional)", "ar": "رد الفعل (اختياري)"},
    "allergen": {"en": "Allergen / drug", "ar": "المادة المسببة للحساسية / الدواء"},
    "condition_name": {"en": "Condition name", "ar": "اسم الحالة"},
    "your_patient_id_is": {"en": "Your patient ID", "ar": "رقم المريض الخاص بك"},
    "keep_id_safe": {
        "en": "Keep this ID safe — you'll need it to log back in.",
        "ar": "احتفظ بهذا الرقم في مكان آمن — ستحتاجه لتسجيل الدخول مرة أخرى.",
    },
    "danger": {"en": "Danger", "ar": "خطر"},
    "warning": {"en": "Warning", "ar": "تنبيه"},
    "info": {"en": "Info", "ar": "معلومة"},
    "manage_reference": {"en": "Manage reference antibiotics", "ar": "إدارة قاعدة المضادات الحيوية"},
    "add_antibiotic_reference": {"en": "Add antibiotic to reference database", "ar": "إضافة مضاد حيوي إلى القاعدة"},
    "drug_class": {"en": "Drug class", "ar": "فئة الدواء"},
    "brand_names_optional": {"en": "Brand names (optional)", "ar": "الأسماء التجارية (اختياري)"},
    "contraindicated_in_pregnancy": {"en": "Contraindicated in pregnancy", "ar": "ممنوع في الحمل"},
    "pregnancy_notes_optional": {"en": "Pregnancy notes (optional)", "ar": "ملاحظات الحمل (اختياري)"},
    "contraindicated_conditions_optional": {
        "en": "Contraindicated conditions, comma-separated (optional)",
        "ar": "الحالات الممنوعة، مفصولة بفواصل (اختياري)",
    },
    "notes_optional": {"en": "Notes (optional)", "ar": "ملاحظات (اختياري)"},
    "generic_name": {"en": "Generic name", "ar": "الاسم العلمي"},
    "actor": {"en": "Actor", "ar": "الجهة"},
    "action": {"en": "Action", "ar": "الإجراء"},
    "target": {"en": "Target patient", "ar": "المريض المستهدف"},
    "timestamp": {"en": "Time", "ar": "الوقت"},
    "no_alerts": {"en": "No known issues found", "ar": "لم يتم العثور على مشاكل معروفة"},
    "years_old": {"en": "years old", "ar": "سنة"},
    "reset_password": {"en": "Reset password", "ar": "إعادة تعيين كلمة المرور"},
    "new_password_optional": {"en": "New password (leave blank to remove password)", "ar": "كلمة مرور جديدة (اتركها فارغة لإزالة كلمة المرور)"},
    "site_settings": {"en": "Site settings", "ar": "إعدادات الموقع"},
    "add_owner_account": {"en": "Add another owner/admin account", "ar": "إضافة حساب مسؤول آخر"},
    "delete": {"en": "Delete", "ar": "حذف"},
    "confirm_delete": {"en": "Are you sure?", "ar": "هل أنت متأكد؟"},
    "add_new_patient": {"en": "+ New patient", "ar": "+ مريض جديد"},
    "create_patient_title": {"en": "Create a new patient record", "ar": "إنشاء سجل مريض جديد"},
    "create_and_continue": {"en": "Create record", "ar": "إنشاء السجل"},
    "patient_created_title": {"en": "Patient record created", "ar": "تم إنشاء سجل المريض"},
    "your_patient_qr": {"en": "Patient QR Code", "ar": "رمز QR الخاص بالمريض"},
    "view_qr": {"en": "View / print QR code & ID", "ar": "عرض / طباعة رمز QR والبطاقة"},
    "scan_to_open_record": {
        "en": "Scanning this code on the patient's phone opens their record directly.",
        "ar": "مسح هذا الرمز على هاتف المريض يفتح سجله مباشرة.",
    },
    "print_id_card": {"en": "Print ID card", "ar": "طباعة بطاقة الهوية"},
    "go_to_full_record": {"en": "Go to full record", "ar": "الذهاب إلى السجل الكامل"},
    "password_protected_note": {
        "en": "This record is password-protected — scanning the code still asks for the password.",
        "ar": "هذا السجل محمي بكلمة مرور — سيُطلب إدخالها حتى بعد مسح الرمز.",
    },
    "no_password_note": {
        "en": "No password is set — anyone who scans this code or learns the ID can open this record. "
              "Set a password from here if that's a concern.",
        "ar": "لا توجد كلمة مرور مضبوطة — أي شخص يمسح هذا الرمز أو يعرف الرقم يمكنه فتح هذا السجل. "
              "يمكنك تعيين كلمة مرور إذا كان ذلك مهماً.",
    },
    "set_password_now": {"en": "Set a password now", "ar": "تعيين كلمة مرور الآن"},
    "optional_initial_password": {"en": "Set a password now (optional)", "ar": "تعيين كلمة مرور الآن (اختياري)"},
    "export_pdf": {"en": "Export PDF for doctor visit", "ar": "تصدير PDF لزيارة الطبيب"},
    "export_pdf_en": {"en": "Export PDF (English)", "ar": "تصدير PDF (إنجليزي)"},
    "export_pdf_ar": {"en": "Export PDF (Arabic)", "ar": "تصدير PDF (عربي)"},

    # -- Roles: full owner/controller (clinical pharmacist) vs limited staff --
    "controller_dashboard_title": {
        "en": "Clinical Pharmacist — Controller Dashboard",
        "ar": "لوحة تحكم الصيدلي الإكلينيكي — المتحكم",
    },
    "staff_dashboard_title": {"en": "Staff Dashboard", "ar": "لوحة تحكم الموظف"},
    "flagged_alerts_title": {"en": "Recent Safety Alerts", "ar": "التنبيهات الأخيرة"},
    "no_flagged_alerts": {
        "en": "No danger or warning alerts in recent activity.",
        "ar": "لا توجد تنبيهات خطر أو تحذير في النشاط الأخير.",
    },
    "recent_activity_title": {
        "en": "Recent Antibiotic Entries (All Patients)",
        "ar": "آخر إدخالات المضادات الحيوية (جميع المرضى)",
    },
    "role": {"en": "Role", "ar": "الصلاحية"},
    "role_owner": {
        "en": "Clinical Pharmacist / Controller (full access)",
        "ar": "صيدلي إكلينيكي / متحكم (وصول كامل)",
    },
    "role_staff": {
        "en": "Staff (view patients & add antibiotics only)",
        "ar": "موظف (عرض المرضى وإضافة المضادات فقط)",
    },
    "accounts_list_title": {"en": "Controller & Staff Accounts", "ar": "حسابات المتحكم والموظفين"},
    "staff_view_only_note": {
        "en": "Only the clinical pharmacist / controller can add or change this.",
        "ar": "فقط الصيدلي الإكلينيكي / المتحكم يمكنه إضافة أو تعديل هذا.",
    },

    # Structured dose/duration (app/dose_format.py). Fixed-vocabulary dropdown
    # options instead of free text, so a dose entered while the UI is in
    # Arabic still renders correctly on an English PDF and vice versa --
    # translating a small closed set of unit/frequency codes via this same
    # dictionary is safe, unlike running patient-entered free text through a
    # machine translator (which risks silently mistranslating a number or
    # unit on a patient-safety record).
    "dose_amount": {"en": "Amount", "ar": "الكمية"},
    "dose_unit": {"en": "Unit", "ar": "الوحدة"},
    "frequency": {"en": "Frequency", "ar": "عدد مرات الجرعة"},
    "duration_amount": {"en": "Duration", "ar": "المدة"},
    "duration_unit": {"en": "Duration unit", "ar": "وحدة المدة"},
    "choose_option": {"en": "-- choose --", "ar": "-- اختر --"},
    "other_specify": {"en": "Other (type below)", "ar": "غير ذلك (اكتب في الأسفل)"},
    "other_free_text_optional": {
        "en": "If \"Other\" selected above, type it here (optional)",
        "ar": "لو اخترت \"غير ذلك\" فوق، اكتبها هنا (اختياري)",
    },

    "dose_unit_mg": {"en": "mg", "ar": "مجم"},
    "dose_unit_g": {"en": "g", "ar": "جم"},
    "dose_unit_ml": {"en": "mL", "ar": "مل"},
    "dose_unit_iu": {"en": "IU", "ar": "وحدة دولية"},
    "dose_unit_tablet": {"en": "tablet(s)", "ar": "قرص/أقراص"},
    "dose_unit_capsule": {"en": "capsule(s)", "ar": "كبسولة/كبسولات"},

    "freq_once_daily": {"en": "once daily", "ar": "مرة واحدة يومياً"},
    "freq_twice_daily": {"en": "twice daily", "ar": "مرتين يومياً"},
    "freq_three_times_daily": {"en": "three times daily", "ar": "3 مرات يومياً"},
    "freq_four_times_daily": {"en": "four times daily", "ar": "4 مرات يومياً"},
    "freq_every_6h": {"en": "every 6 hours", "ar": "كل 6 ساعات"},
    "freq_every_8h": {"en": "every 8 hours", "ar": "كل 8 ساعات"},
    "freq_every_12h": {"en": "every 12 hours", "ar": "كل 12 ساعة"},
    "freq_every_24h": {"en": "every 24 hours", "ar": "كل 24 ساعة"},
    "freq_as_needed": {"en": "as needed (PRN)", "ar": "عند الحاجة"},
    "freq_single_dose": {"en": "single dose", "ar": "جرعة واحدة فقط"},

    # NOTE: deliberately "يوم"/"أسبوع" (singular), not the slash-joined
    # day/days dual form ("يوم/أيام") the UI copy would normally use --
    # confirmed via isolated wkhtmltopdf renders that a "word/word" slash
    # pattern right next to a <bdi>-wrapped digit corrupts in the Arabic PDF
    # (see app/bidi_fix.py). The number already in front of it makes the
    # plural form obvious ("7 يوم" reads fine), so nothing is lost.
    "duration_unit_day": {"en": "day(s)", "ar": "يوم"},
    "duration_unit_week": {"en": "week(s)", "ar": "أسبوع"},
    "duration_unit_dose": {"en": "single dose (one-time)", "ar": "جرعة واحدة (مرة واحدة فقط)"},
}


def t(key, lang="ar"):
    entry = STRINGS.get(key)
    if not entry:
        return f"[[{key}]]"
    return entry.get(lang, entry.get("en", key))
