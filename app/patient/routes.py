from datetime import date

from flask import Response, current_app, flash, jsonify, redirect, render_template, request, url_for

from app import models
from app.ai_gemini import AIScanError, AIScanNotConfigured
from app.patient import bp
from app.pdf_export import generate_patient_history_pdf
from app.pdf_export_ar import WkhtmltopdfNotFound, generate_patient_history_pdf_arabic
from app.prescription_scan import build_scan_note, scan_prescription_image
from app.rate_limit import check_patient_ai_scan_rate, record_patient_ai_scan
from app.records import (
    add_allergy_from_form, add_antibiotic_from_form, add_condition_from_form, add_hospitalization_from_form,
    add_medication_from_form, attach_infection_origin,
)
from app.utils import current_patient, patient_required
from app.voice_resolve import resolve_antibiotic_from_audio


@bp.route("/")
@patient_required
def dashboard():
    patient = current_patient()
    patient["allergies"] = models.list_allergies(patient["id"])
    patient["conditions"] = models.list_conditions(patient["id"])
    patient["medications"] = models.list_medications(patient["id"])
    patient["hospitalizations"] = models.list_hospitalizations(patient["id"])
    patient["antibiotic_records"] = attach_infection_origin(
        models.list_antibiotic_records(patient["id"]), patient["hospitalizations"],
    )
    return render_template("patient/dashboard.html", patient=patient)


@bp.route("/qr")
@patient_required
def my_qr():
    patient = current_patient()
    return render_template(
        "qr_card.html",
        patient=patient,
        has_password=models.patient_has_password(patient),
        qr_url=url_for("auth.go_via_qr", public_id=patient["public_id"], _external=True),
        back_url=url_for("patient.dashboard"),
        back_label="back",
        created=False,
    )


@bp.route("/export-pdf")
@bp.route("/export-pdf/en")
@patient_required
def export_pdf():
    patient = current_patient()
    allergies = models.list_allergies(patient["id"])
    conditions = models.list_conditions(patient["id"])
    records = models.list_antibiotic_records(patient["id"])
    pdf_bytes = generate_patient_history_pdf(patient, allergies, conditions, records)
    models.log_action("patient", patient["public_id"], "export_pdf_en", target=patient["public_id"])
    filename = f"{patient['public_id']}-antibiotic-summary-en.pdf"
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@bp.route("/export-pdf/ar")
@patient_required
def export_pdf_ar():
    patient = current_patient()
    allergies = models.list_allergies(patient["id"])
    conditions = models.list_conditions(patient["id"])
    records = models.list_antibiotic_records(patient["id"])
    try:
        pdf_bytes = generate_patient_history_pdf_arabic(patient, allergies, conditions, records)
    except WkhtmltopdfNotFound as exc:
        return (str(exc), 500)
    models.log_action("patient", patient["public_id"], "export_pdf_ar", target=patient["public_id"])
    filename = f"{patient['public_id']}-antibiotic-summary-ar.pdf"
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@bp.route("/allergies/add", methods=["POST"])
@patient_required
def add_allergy():
    patient = current_patient()
    add_allergy_from_form(patient, request.form)
    models.log_action("patient", patient["public_id"], "add_allergy", target=patient["public_id"])
    return redirect(url_for("patient.dashboard"))


@bp.route("/conditions/add", methods=["POST"])
@patient_required
def add_condition():
    patient = current_patient()
    add_condition_from_form(patient, request.form)
    models.log_action("patient", patient["public_id"], "add_condition", target=patient["public_id"])
    return redirect(url_for("patient.dashboard"))


@bp.route("/medications/add", methods=["POST"])
@patient_required
def add_medication():
    patient = current_patient()
    add_medication_from_form(patient, request.form)
    models.log_action("patient", patient["public_id"], "add_medication", target=patient["public_id"])
    return redirect(url_for("patient.dashboard"))


@bp.route("/hospitalizations/add", methods=["POST"])
@patient_required
def add_hospitalization():
    patient = current_patient()
    add_hospitalization_from_form(patient, request.form, recorded_by="patient")
    models.log_action("patient", patient["public_id"], "add_hospitalization", target=patient["public_id"])
    return redirect(url_for("patient.dashboard"))


@bp.route("/pregnancy-status", methods=["POST"])
@patient_required
def update_pregnancy_status():
    patient = current_patient()
    dob_start_raw = request.form.get("pregnancy_start_date", "").strip()
    edd_raw = request.form.get("expected_delivery_date", "").strip()
    try:
        start_date = date.fromisoformat(dob_start_raw).isoformat() if dob_start_raw else None
    except ValueError:
        start_date = None
    try:
        due_date = date.fromisoformat(edd_raw).isoformat() if edd_raw else None
    except ValueError:
        due_date = None
    models.update_pregnancy_status(
        patient["id"], request.form.get("pregnancy_status", patient["pregnancy_status"]),
        pregnancy_start_date=start_date, expected_delivery_date=due_date,
    )
    models.log_action("patient", patient["public_id"], "update_pregnancy_status", target=patient["public_id"])
    return redirect(url_for("patient.dashboard"))


@bp.route("/phone-number", methods=["POST"])
@patient_required
def update_phone():
    patient = current_patient()
    models.update_phone_number(patient["id"], request.form.get("phone_number", "").strip() or None)
    models.log_action("patient", patient["public_id"], "update_phone_number", target=patient["public_id"])
    return redirect(url_for("patient.dashboard"))


@bp.route("/email", methods=["POST"])
@patient_required
def update_email():
    """Optional, self-service -- adding an email here is what makes the
    email+one-time-code sign-in option (auth.patient_login_email) and the
    email notifications (new antibiotic added, password changed) available
    for this patient; leaving it blank keeps everything working exactly as
    before on the ASH-XXXXXX ID alone (see app/models.py's update_email)."""
    patient = current_patient()
    email = request.form.get("email", "").strip()
    try:
        models.update_email(patient["id"], email)
    except models.EmailAlreadyUsed:
        flash("That email is already in use on another record.", "error")
        return redirect(url_for("patient.dashboard"))
    models.log_action("patient", patient["public_id"], "update_email", target=patient["public_id"])
    flash("Email updated.", "success")
    return redirect(url_for("patient.dashboard"))


@bp.route("/antibiotics/add", methods=["GET", "POST"])
@patient_required
def add_antibiotic():
    patient = current_patient()
    if request.method == "POST":
        record, alerts = add_antibiotic_from_form(patient, request.form, added_by="patient")
        models.log_action("patient", patient["public_id"], "add_antibiotic_record",
                          target=patient["public_id"], details=record["display_name"])
        # Redirect (rather than rendering the result directly) so the
        # browser's Back button doesn't try to resubmit this POST.
        return redirect(url_for("patient.antibiotic_result", record_id=record["id"]))
    reference_names = [a["generic_name"] for a in models.list_antibiotics()]
    return render_template("patient/add_antibiotic.html", reference_names=reference_names)


@bp.route("/antibiotics/scan-photo", methods=["POST"])
@patient_required
def scan_antibiotic_photo():
    """Patient-facing self-service version of app/owner/routes.py's
    scan_patient_antibiotic_photo -- same underlying AI photo scan (see
    app/prescription_scan.py), same safety checks on save (still goes
    through add_antibiotic_from_form(), never bypassed), but for the
    patient's OWN record only, reached from their own "Add antibiotic"
    page (see patient/add_antibiotic.html) rather than a staff dashboard.
    No restricted-antibiotic gate here -- that concept only applies to
    staff roles (app/roles.py); a patient documenting their own
    prescription has no such restriction, same as the manual add_antibiotic
    route above already has none."""
    patient = current_patient()
    ip_address = request.remote_addr or "unknown"

    wait_minutes = check_patient_ai_scan_rate(patient["public_id"], ip_address)
    if wait_minutes is not None:
        flash(
            f"You've used the AI photo scan a lot in a short time -- please wait about {wait_minutes} "
            "minutes, or add this one manually below.",
            "error",
        )
        return redirect(url_for("patient.add_antibiotic"))

    photo = request.files.get("prescription_photo")
    if not photo or not photo.filename:
        flash("Choose or take a photo of the prescription or medication package first.", "error")
        return redirect(url_for("patient.add_antibiotic"))

    image_bytes = photo.read()
    if not image_bytes:
        flash("That photo looks empty — please try again.", "error")
        return redirect(url_for("patient.add_antibiotic"))
    if len(image_bytes) > current_app.config["PRESCRIPTION_PHOTO_MAX_BYTES"]:
        max_mb = current_app.config["PRESCRIPTION_PHOTO_MAX_BYTES"] // (1024 * 1024)
        flash(f"That photo is too large (max {max_mb} MB). Please retake it or choose a smaller file.", "error")
        return redirect(url_for("patient.add_antibiotic"))

    record_patient_ai_scan(patient["public_id"], ip_address)
    known_antibiotics = models.list_antibiotics()
    try:
        result = scan_prescription_image(
            image_bytes,
            api_key=current_app.config["GEMINI_API_KEY"],
            model=current_app.config["GEMINI_MODEL"],
            known_antibiotics=known_antibiotics,
        )
    except AIScanNotConfigured as e:
        flash(str(e), "error")
        return redirect(url_for("patient.add_antibiotic"))
    except AIScanError as e:
        models.log_action("patient", patient["public_id"], "prescription_scan_failed",
                          target=patient["public_id"], details=str(e))
        flash(f"Couldn't read that photo: {e}", "error")
        return redirect(url_for("patient.add_antibiotic"))

    added_names = []
    for item in result.get("antibiotics", []):
        name = (item.get("antibiotic_name") or "").strip()
        if not name:
            continue
        form_data = {
            "antibiotic_name": name,
            "prescribed_date": (item.get("prescribed_date") or "").strip(),
            "prescribed_by": (item.get("prescribed_by") or "").strip(),
            "dose_amount": (item.get("dose_amount") or "").strip(),
            "dose_unit": (item.get("dose_unit") or "").strip(),
            "dose_unit_other": (item.get("dose_unit_other") or "").strip(),
            "frequency": (item.get("frequency") or "").strip(),
            "frequency_other": (item.get("frequency_other") or "").strip(),
            "duration_amount": (item.get("duration_amount") or "").strip(),
            "duration_unit": (item.get("duration_unit") or "").strip(),
            "duration_unit_other": (item.get("duration_unit_other") or "").strip(),
            "notes": build_scan_note(item),
        }
        record, _alerts = add_antibiotic_from_form(
            patient, form_data,
            added_by="patient (📷 AI prescription scan)",
            source="photo_ai",
            source_photo=image_bytes,
        )
        added_names.append(record["display_name"])
        models.log_action("patient", patient["public_id"], "add_antibiotic_record_from_photo",
                          target=patient["public_id"], details=record["display_name"])

    ignored = [n for n in (result.get("other_medications_ignored") or []) if n and n.strip()]

    if added_names:
        msg = f"Added from the photo: {', '.join(added_names)}."
        if ignored:
            msg += f" Ignored (not antibiotics): {', '.join(ignored)}."
        if result.get("read_issues"):
            msg += f" Note: {result['read_issues']}"
        flash(msg, "success")
    else:
        msg = "No antibiotics could be identified in that photo."
        if ignored:
            msg += f" Found other medication(s) ({', '.join(ignored)}) but no antibiotics."
        if result.get("read_issues"):
            msg += f" {result['read_issues']}"
        msg += " Please add it manually below, or retake a clearer photo."
        flash(msg, "error")

    # A photo can add more than one antibiotic at once, so (like the owner
    # side) this redirects to the record list rather than a single
    # antibiotic's result page.
    return redirect(url_for("patient.dashboard"))


@bp.route("/antibiotics/resolve-voice-audio", methods=["POST"])
@patient_required
def resolve_antibiotic_voice_audio():
    """Patient-facing self-service version of app/owner/routes.py's
    resolve_antibiotic_voice_audio -- records the actual audio clip from
    the microphone button on the "Add antibiotic" form and sends it to
    Gemini (see app/voice_resolve.py) to resolve the spoken drug name,
    rather than trusting the browser's own free, generic speech-to-text.
    Called by plain fetch(), never touches a patient record itself -- the
    actual save still goes through the normal add_antibiotic form submit."""
    patient = current_patient()
    ip_address = request.remote_addr or "unknown"

    wait_minutes = check_patient_ai_scan_rate(patient["public_id"], ip_address)
    if wait_minutes is not None:
        return jsonify({
            "heard": "", "resolved_name": "", "matched": False,
            "error": "Too many AI requests recently -- please wait a few minutes, or type the name in by hand.",
        })

    audio = request.files.get("audio")
    if not audio or not audio.filename:
        return jsonify({"heard": "", "resolved_name": "", "matched": False, "error": "No recording received."})

    audio_bytes = audio.read()
    if not audio_bytes:
        return jsonify({"heard": "", "resolved_name": "", "matched": False, "error": "That recording came out empty."})

    record_patient_ai_scan(patient["public_id"], ip_address)
    try:
        result = resolve_antibiotic_from_audio(
            audio_bytes,
            media_type=audio.mimetype,
            api_key=current_app.config["GEMINI_API_KEY"],
            model=current_app.config["GEMINI_MODEL"],
            known_antibiotics=models.list_antibiotics(),
        )
    except AIScanNotConfigured as e:
        return jsonify({"heard": "", "resolved_name": "", "matched": False, "error": str(e)})
    except AIScanError as e:
        models.log_action("patient", patient["public_id"], "voice_resolve_failed",
                          target=patient["public_id"], details=str(e))
        return jsonify({"heard": "", "resolved_name": "", "matched": False, "error": str(e)})

    return jsonify(result)


@bp.route("/antibiotics/<int:record_id>/result")
@patient_required
def antibiotic_result(record_id):
    patient = current_patient()
    record = models.get_antibiotic_record_by_id(record_id)
    if not record or record["patient_id"] != patient["id"]:
        return ("Record not found.", 404)
    return render_template("patient/antibiotic_result.html", patient=patient,
                           record=record, alerts=record["alerts"])
