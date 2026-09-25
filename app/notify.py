"""Builds and sends every notification email AND SMS this app sends, in one
place (mirrors app/auth/routes.py's own small `_t()` bilingual-flash-message
pattern, just for emails/texts instead of flashes). Every function here is
best-effort and NEVER raises or blocks its caller -- see app/mailer.py's and
app/sms.py's own docstrings. A call site fires one of these and moves on; it
never branches on whether the email or text actually went out.

Only patient-facing notices go out by SMS (login code, password-reset
notice, new-antibiotic notice) -- owner/staff accounts don't have a phone
number field in this app, so send_owner_password_reset_notice and
send_danger_alert_to_owners below stay email-only. A patient without a
phone on file (any patient registered before phone became mandatory) just
doesn't get the SMS copy -- send_sms() itself is a no-op for a missing
number, same as send_email() is for a missing address."""
from app.mailer import send_email
from app.sms import send_sms


def _t(en, ar, lang):
    return ar if lang == "ar" else en


def send_patient_login_code(patient, code, lang="ar"):
    """The one-time sign-in code for app/auth/routes.py's
    patient_login_email flow (see app/models.py's create_patient_login_code
    for how the code itself is generated/stored)."""
    subject = _t("Your AmanBio sign-in code", "رمز الدخول الخاص بك - أمان بايو", lang)
    body = _t(
        f"Your one-time sign-in code is: {code}\n\n"
        f"It's valid for a few minutes and can only be used once. If you didn't request this, "
        f"you can safely ignore this email -- your account is still safe (nobody can sign in "
        f"without this code).",
        f"رمز الدخول الخاص بك هو: {code}\n\n"
        f"هذا الرمز صالح لبضع دقائق ويمكن استخدامه مرة واحدة فقط. إذا لم تطلب هذا الرمز، يمكنك "
        f"تجاهل هذه الرسالة بأمان -- حسابك ما زال آمناً (لا يمكن لأحد الدخول بدون هذا الرمز).",
        lang,
    )
    return send_email(patient.get("email"), subject, body)


def send_patient_login_code_sms(patient, code, lang="ar"):
    """The SMS equivalent of send_patient_login_code() above, for
    app/auth/routes.py's patient_login_phone flow -- a separate function
    (rather than folding this into the email one) because a sign-in code
    always goes to exactly the ONE channel the patient chose to sign in
    with, never both at once, unlike the plain notices below which go to
    every channel the patient has on file."""
    body = _t(
        f"AmanBio sign-in code: {code}. Valid a few minutes, use once. "
        f"Didn't request this? Your account is still safe -- ignore this text.",
        f"رمز الدخول في أمان بايو: {code}. صالح لبضع دقائق ويُستخدم مرة واحدة. "
        f"لم تطلب هذا الرمز؟ حسابك ما زال آمناً -- تجاهل هذه الرسالة.",
        lang,
    )
    return send_sms(patient.get("phone_number"), body)


def send_patient_password_reset_notice(patient, lang="ar"):
    """Sent after a patient's password is reset or removed, whether they
    did it themselves (auth.forgot_password) or hospital/pharmacy staff did
    it for them (owner.reset_patient_password) -- a plain security notice,
    not a code: if the patient didn't do this themselves, seeing it happen
    is the useful signal, not something to click or act on. Goes out on
    EVERY channel the patient has on file (email AND SMS), unlike a
    sign-in code which only ever goes to the one channel just used."""
    subject = _t("Your AmanBio password was changed", "تم تغيير كلمة مرور حسابك - أمان بايو", lang)
    body = _t(
        f"This is a notice that the password for your patient record ({patient.get('public_id', '')}) "
        f"was just changed. If this was you (or hospital/pharmacy staff helping you), no action is "
        f"needed. If you don't recognize this, please contact the hospital right away.",
        f"هذا إشعار بأن كلمة مرور سجلك ({patient.get('public_id', '')}) قد تم تغييرها للتو. إذا كنت "
        f"أنت من قام بذلك (أو أحد موظفي المستشفى/الصيدلية بمساعدتك)، فلا حاجة لأي إجراء. إذا لم "
        f"تتعرف على هذا التغيير، يرجى التواصل مع المستشفى فوراً.",
        lang,
    )
    sms_body = _t(
        f"AmanBio: the password for your patient record ({patient.get('public_id', '')}) was just changed. "
        f"Not you? Contact the hospital right away.",
        f"أمان بايو: تم تغيير كلمة مرور سجلك ({patient.get('public_id', '')}) للتو. لم يكن أنت؟ تواصل مع "
        f"المستشفى فوراً.",
        lang,
    )
    email_ok = send_email(patient.get("email"), subject, body)
    sms_ok = send_sms(patient.get("phone_number"), sms_body)
    return email_ok or sms_ok


def send_owner_password_reset_notice(owner, lang="ar"):
    """Same idea as send_patient_password_reset_notice above, for a
    staff/owner-side account -- sent whether they changed their own
    password (owner.change_password) or the full owner/controller reset it
    for them (owner.reset_owner_password). Email-only: owner_users has no
    phone number field in this app (only patients do)."""
    subject = _t("Your AmanBio account password was changed", "تم تغيير كلمة مرور حسابك - أمان بايو", lang)
    body = _t(
        f"This is a notice that the password for your staff account ({owner.get('username', '')}) "
        f"was just changed. If this was you, no action is needed. If you don't recognize this, "
        f"please contact the hospital's site administrator right away.",
        f"هذا إشعار بأن كلمة مرور حساب الموظف الخاص بك ({owner.get('username', '')}) قد تم تغييرها "
        f"للتو. إذا كنت أنت من قام بذلك، فلا حاجة لأي إجراء. إذا لم تتعرف على هذا التغيير، يرجى "
        f"التواصل مع مسؤول الموقع في المستشفى فوراً.",
        lang,
    )
    return send_email(owner.get("email"), subject, body)


def send_new_antibiotic_notice(patient, record, lang="ar"):
    """Sent to the patient (on every channel they have on file -- email
    and/or SMS) whenever a new antibiotic entry is added to their record --
    by themselves, or by hospital/pharmacy staff -- so they have a copy
    even without opening the app. Fires from app/records.py's
    add_antibiotic_from_form(), which every "add antibiotic" entry point
    (manual form, photo scan, patient self-entry, staff entry) already
    goes through, so this one hook covers all of them."""
    name = record.get("display_name") or "an antibiotic"
    date_str = record.get("prescribed_date") or ""
    subject = _t(f"New antibiotic added to your record: {name}",
                 f"تمت إضافة مضاد حيوي جديد لسجلك: {name}", lang)
    body = _t(
        f"A new antibiotic entry was added to your AmanBio patient record ({patient.get('public_id', '')}):\n\n"
        f"  Antibiotic: {name}\n"
        f"  Date: {date_str}\n\n"
        f"You can see the full details, including any safety notes, by signing in to your record.",
        f"تمت إضافة مضاد حيوي جديد إلى سجلك في أمان بايو ({patient.get('public_id', '')}):\n\n"
        f"  المضاد الحيوي: {name}\n"
        f"  التاريخ: {date_str}\n\n"
        f"يمكنك الاطلاع على كافة التفاصيل، بما في ذلك أي ملاحظات تتعلق بالسلامة، من خلال تسجيل "
        f"الدخول إلى سجلك.",
        lang,
    )
    sms_body = _t(
        f"AmanBio: a new antibiotic ({name}) was added to your record ({patient.get('public_id', '')}) "
        f"on {date_str}. Sign in for full details.",
        f"أمان بايو: تمت إضافة مضاد حيوي جديد ({name}) لسجلك ({patient.get('public_id', '')}) بتاريخ "
        f"{date_str}. سجّل الدخول لمزيد من التفاصيل.",
        lang,
    )
    sms_ok = send_sms(patient.get("phone_number"), sms_body)
    email_ok = send_email(patient.get("email"), subject, body)
    return email_ok or sms_ok


def send_danger_alert_to_owners(owner_emails, patient, record, alerts, lang="ar"):
    """Sent to every full owner/controller account that has an email on
    file, whenever a newly added antibiotic record triggers at least one
    'danger'-level safety alert (see app/engine/safety_check.py) --
    regardless of who added the record or whether they were the one who
    saw the on-screen warning. owner_emails: list of addresses (see
    models.list_full_owner_emails()) -- sent as one message per recipient
    rather than one message with everyone in To/Cc, so staff addresses
    aren't exposed to each other. Email-only: owner_users has no phone
    number field in this app (only patients do)."""
    if not owner_emails:
        return False
    name = record.get("display_name") or "an antibiotic"
    danger_titles = [a.get("title", "") for a in alerts if a.get("level") == "danger"]
    titles_str = "; ".join(t for t in danger_titles if t) or _t("(see the record for details)",
                                                                   "(راجع السجل للتفاصيل)", lang)
    subject = _t(f"Safety alert: {patient.get('public_id', '')} - {name}",
                 f"تنبيه سلامة: {patient.get('public_id', '')} - {name}", lang)
    body = _t(
        f"A newly added antibiotic record triggered a DANGER-level safety alert:\n\n"
        f"  Patient: {patient.get('public_id', '')}"
        f"{' (' + patient['full_name'] + ')' if patient.get('full_name') else ''}\n"
        f"  Antibiotic: {name}\n"
        f"  Alert(s): {titles_str}\n\n"
        f"Please review this patient's record as soon as convenient.",
        f"سجل مضاد حيوي تمت إضافته حديثاً أدى إلى تنبيه سلامة بمستوى خطر:\n\n"
        f"  المريض: {patient.get('public_id', '')}"
        f"{' (' + patient['full_name'] + ')' if patient.get('full_name') else ''}\n"
        f"  المضاد الحيوي: {name}\n"
        f"  التنبيه(ات): {titles_str}\n\n"
        f"يرجى مراجعة سجل هذا المريض في أقرب وقت ممكن.",
        lang,
    )
    sent_any = False
    for address in owner_emails:
        if send_email(address, subject, body):
            sent_any = True
    return sent_any
