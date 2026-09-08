"""Minimal hand-rolled i18n: a flat dict of key -> {en, ar}. Deliberately
simple (no Flask-Babel/.po files) since the app only needs two languages.
Add new keys here as templates need them; t() falls back to the key itself
(and prints a note) if a translation is missing, so typos are visible
immediately instead of silently showing blank text."""

STRINGS = {
    "site_name": {"en": "Al Shefa Specialized Hospital", "ar": "مستشفى الشفاء التخصصي"},
    "app_tagline": {"en": "Patient Antibiotic Safety Record", "ar": "سجل سلامة المضادات الحيوية للمريض"},
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
}


def t(key, lang="ar"):
    entry = STRINGS.get(key)
    if not entry:
        return f"[[{key}]]"
    return entry.get(lang, entry.get("en", key))
