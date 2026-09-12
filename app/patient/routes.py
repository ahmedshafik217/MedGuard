from datetime import date

from flask import Response, redirect, render_template, request, url_for

from app import models
from app.patient import bp
from app.pdf_export import generate_patient_history_pdf
from app.pdf_export_ar import WkhtmltopdfNotFound, generate_patient_history_pdf_arabic
from app.records import add_allergy_from_form, add_antibiotic_from_form, add_condition_from_form
from app.utils import current_patient, patient_required


@bp.route("/")
@patient_required
def dashboard():
    patient = current_patient()
    patient["allergies"] = models.list_allergies(patient["id"])
    patient["conditions"] = models.list_conditions(patient["id"])
    patient["antibiotic_records"] = models.list_antibiotic_records(patient["id"])
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


@bp.route("/antibiotics/<int:record_id>/result")
@patient_required
def antibiotic_result(record_id):
    patient = current_patient()
    record = models.get_antibiotic_record_by_id(record_id)
    if not record or record["patient_id"] != patient["id"]:
        return ("Record not found.", 404)
    return render_template("patient/antibiotic_result.html", patient=patient,
                           record=record, alerts=record["alerts"])
