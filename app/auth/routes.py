from datetime import date

from flask import flash, redirect, render_template, request, session, url_for

from app import models
from app.auth import bp
from app.rate_limit import check_lockout, record_attempt
from app.utils import current_actor_label, current_owner, current_patient, login_owner, login_patient, logout


def _client_ip():
    return request.remote_addr or "unknown"


def _too_many_attempts_message(wait_minutes):
    return _t(
        f"Too many login attempts. Please wait about {wait_minutes} minutes and try again.",
        f"عدد محاولات تسجيل الدخول كبير جدًا. يرجى الانتظار حوالي {wait_minutes} دقيقة والمحاولة مرة أخرى.",
    )


@bp.route("/")
def choose_login():
    return render_template("auth/choose_login.html")


@bp.route("/owner-login", methods=["GET", "POST"])
def owner_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        identifier = username.lower()
        ip_address = _client_ip()

        wait_minutes = check_lockout("owner", identifier, ip_address)
        if wait_minutes:
            models.log_action("owner", username or "(blank)", "login_rate_limited", details=f"ip={ip_address}")
            flash(_too_many_attempts_message(wait_minutes), "error")
            return render_template("auth/owner_login.html")

        owner = models.get_owner_by_username(username)
        success = bool(owner and models.check_owner_password(owner, password))
        record_attempt("owner", identifier, ip_address, success)
        if success:
            login_owner(owner)
            models.log_action("owner", owner["username"], "login", details="Owner logged in")
            return redirect(url_for("owner.dashboard"))
        flash(_t("Invalid username or password.", "اسم المستخدم أو كلمة المرور غير صحيحة."), "error")
    return render_template("auth/owner_login.html")


@bp.route("/patient-login", methods=["GET", "POST"])
def patient_login():
    if request.method == "POST":
        public_id = request.form.get("public_id", "").strip().upper()
        password = request.form.get("password", "")
        ip_address = _client_ip()

        wait_minutes = check_lockout("patient", public_id, ip_address)
        if wait_minutes:
            models.log_action("patient", public_id or "(blank)", "login_rate_limited",
                              target=public_id or None, details=f"ip={ip_address}")
            flash(_too_many_attempts_message(wait_minutes), "error")
            return render_template("auth/patient_login.html", prefill_id=public_id)

        patient = models.get_patient_by_public_id(public_id)
        if not patient:
            record_attempt("patient", public_id, ip_address, success=False)
            flash(_t("No record found with that ID.", "لا يوجد سجل بهذا الرقم."), "error")
        elif models.patient_has_password(patient) and not models.check_patient_password(patient, password):
            record_attempt("patient", public_id, ip_address, success=False)
            flash(_t("Incorrect password.", "كلمة المرور غير صحيحة."), "error")
        else:
            record_attempt("patient", public_id, ip_address, success=True)
            login_patient(patient)
            models.log_action("patient", patient["public_id"], "login", target=patient["public_id"])
            return redirect(url_for("patient.dashboard"))
    prefill_id = request.args.get("prefill", "").strip().upper()
    return render_template("auth/patient_login.html", prefill_id=prefill_id)


@bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    """Self-service password reset: no email/SMS involved (this deployment
    doesn't have an SMS provider hooked up) -- identity is instead checked
    against phone number + date of birth already on file, the same way a
    front-desk check would ask "what's your ID, phone, and birth date".
    A patient whose record has no phone number and/or no date of birth on
    file can't use this and needs an owner/staff-assisted reset instead
    (see owner.reset_patient_password)."""
    prefill_id = request.args.get("prefill", "").strip().upper()
    if request.method == "POST":
        public_id = request.form.get("public_id", "").strip().upper()
        phone_number = request.form.get("phone_number", "").strip()
        dob_raw = request.form.get("date_of_birth", "").strip()
        new_password = request.form.get("new_password", "").strip()
        ip_address = _client_ip()

        wait_minutes = check_lockout("patient_reset", public_id or "(blank)", ip_address)
        if wait_minutes:
            flash(_too_many_attempts_message(wait_minutes), "error")
            return render_template("auth/forgot_password.html", prefill_id=public_id)

        try:
            date_of_birth = date.fromisoformat(dob_raw).isoformat() if dob_raw else None
        except ValueError:
            date_of_birth = None

        if not new_password:
            flash(_t("Please enter a new password.", "يرجى إدخال كلمة مرور جديدة."), "error")
            return render_template("auth/forgot_password.html", prefill_id=public_id)

        patient = models.find_patient_for_reset(public_id, phone_number, date_of_birth)
        record_attempt("patient_reset", public_id or "(blank)", ip_address, success=bool(patient))
        if not patient:
            models.log_action("patient", public_id or "(blank)", "password_reset_failed", target=public_id or None)
            flash(
                _t(
                    "We couldn't verify those details. Check your patient ID, phone number and date of "
                    "birth, or ask hospital/pharmacy staff to reset your password for you.",
                    "تعذر التحقق من هذه البيانات. تأكد من رقم المريض ورقم الهاتف وتاريخ الميلاد، أو "
                    "اطلب من موظفي المستشفى/الصيدلية إعادة تعيين كلمة المرور لك.",
                ),
                "error",
            )
            return render_template("auth/forgot_password.html", prefill_id=public_id)

        models.set_patient_password(patient["id"], new_password)
        models.log_action("patient", patient["public_id"], "password_reset_self", target=patient["public_id"])
        flash(_t("Password updated — you can log in now.", "تم تحديث كلمة المرور — يمكنك تسجيل الدخول الآن."),
              "success")
        return redirect(url_for("auth.patient_login", prefill=patient["public_id"]))

    return render_template("auth/forgot_password.html", prefill_id=prefill_id)


@bp.route("/go/<public_id>")
def go_via_qr(public_id):
    """Magic-link target for a patient's QR code. If the patient has no
    password, this logs them straight in (their unguessable public_id is
    already their whole credential in that case, same as typing it into the
    login form). If they do have a password, this just pre-fills the ID on
    the login page so the password still has to be entered — scanning the
    code never bypasses a password that's set.

    Rate-limited the same as the patient login form (same 'patient' scope,
    same public-ID identifier) since a passwordless record's ID guess IS a
    login attempt here -- guessing right logs the patient straight in."""
    normalized_id = public_id.strip().upper()
    ip_address = _client_ip()

    wait_minutes = check_lockout("patient", normalized_id, ip_address)
    if wait_minutes:
        flash(_too_many_attempts_message(wait_minutes), "error")
        return redirect(url_for("auth.choose_login"))

    patient = models.get_patient_by_public_id(public_id)
    if not patient:
        record_attempt("patient", normalized_id, ip_address, success=False)
        flash(_t("This QR code doesn't match any patient record.", "رمز QR هذا لا يطابق أي سجل مريض."), "error")
        return redirect(url_for("auth.choose_login"))

    record_attempt("patient", normalized_id, ip_address, success=True)
    if models.patient_has_password(patient):
        return redirect(url_for("auth.patient_login", prefill=patient["public_id"]))

    login_patient(patient)
    models.log_action("patient", patient["public_id"], "login_via_qr", target=patient["public_id"])
    return redirect(url_for("patient.dashboard"))


@bp.route("/register-patient", methods=["GET", "POST"])
def register_patient():
    """Self-service creation of a brand-new patient record. In real use this
    would typically happen once, at a hospital/pharmacy desk, or by the
    patient themselves on their own phone."""
    if request.method == "POST":
        gender = request.form.get("gender", "unspecified")
        password = request.form.get("password", "").strip() or None
        full_name = request.form.get("full_name", "").strip() or None
        phone_number = request.form.get("phone_number", "").strip() or None
        dob_raw = request.form.get("date_of_birth", "").strip()

        date_of_birth = None
        if dob_raw:
            try:
                date_of_birth = date.fromisoformat(dob_raw).isoformat()
            except ValueError:
                date_of_birth = None

        patient = models.create_patient(
            gender=gender, full_name=full_name, date_of_birth=date_of_birth, password=password,
            phone_number=phone_number,
        )
        models.log_action("patient", patient["public_id"], "record_created", target=patient["public_id"])

        login_patient(patient)
        flash(
            _t(
                f"Your new patient ID is {patient['public_id']}. Write it down — you need it to log in again.",
                f"رقم المريض الجديد الخاص بك هو {patient['public_id']}. احتفظ به لتسجيل الدخول لاحقاً.",
            ),
            "success",
        )
        return redirect(url_for("patient.dashboard"))
    return render_template("auth/register_patient.html")


@bp.route("/logout", endpoint="logout")
def logout_route():
    owner = current_owner()
    patient = current_patient()
    if owner:
        models.log_action("owner", owner["username"], "logout")
    elif patient:
        models.log_action("patient", patient["public_id"], "logout", target=patient["public_id"])
    logout()
    return redirect(url_for("auth.choose_login"))


def _t(en, ar):
    """Tiny inline translation helper for flash messages (routes run before
    templates render, so we pick based on the session language here too)."""
    return ar if session.get("lang", "ar") == "ar" else en
