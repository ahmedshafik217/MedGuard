from datetime import date

from flask import Response, flash, redirect, render_template, request, url_for

from app import models
from app.owner import bp
from app.pdf_export import generate_patient_history_pdf
from app.pdf_export_ar import WkhtmltopdfNotFound, generate_patient_history_pdf_arabic
from app.records import add_allergy_from_form, add_antibiotic_from_form, add_condition_from_form
from app.utils import current_actor_label, current_owner, current_owner_role, full_owner_required, owner_required


@bp.route("/")
@owner_required
def dashboard():
    is_full = models.is_full_owner(current_owner())
    q = request.args.get("q", "").strip()
    if is_full:
        patients = models.list_patients(search=q or None)
    else:
        # Staff can only pull up a specific patient by exact full name or
        # ID -- no default browsing of the whole patient list, and no
        # partial-substring search either. See models.find_patients_exact.
        patients = models.find_patients_exact(q) if q else []
    stats = flagged_records = recent_records = None
    if is_full:
        # The controller/clinical-pharmacist dashboard surfaces what needs
        # attention first (flagged safety alerts, recent activity) rather
        # than just being a plain relabel of the same patient list.
        stats = {
            "patient_count": models.count_patients(),
            "antibiotic_count": models.count_antibiotics(),
            "record_count": models.count_antibiotic_records(),
        }
        flagged_records = models.list_recent_flagged_records()
        recent_records = models.list_recent_antibiotic_records(limit=10)
    return render_template(
        "owner/dashboard.html",
        patients=patients, q=q, stats=stats,
        flagged_records=flagged_records, recent_records=recent_records,
    )


@bp.route("/patients/new", methods=["GET", "POST"])
@full_owner_required
def create_patient():
    """Owner/staff-side manual creation of a patient record -- for a patient
    being onboarded at the hospital/pharmacy desk rather than registering
    themselves. Ends on the QR/ID card screen so the owner can immediately
    hand the patient their code."""
    if request.method == "POST":
        gender = request.form.get("gender", "unspecified")
        full_name = request.form.get("full_name", "").strip() or None
        password = request.form.get("password", "").strip() or None
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

        if gender == "female":
            pregnancy_status = request.form.get("pregnancy_status", "unknown")
            models.update_pregnancy_status(patient["id"], pregnancy_status)

        models.log_action("owner", current_actor_label(), "create_patient_record", target=patient["public_id"])
        flash("Patient record created.", "success")
        return redirect(url_for("owner.patient_qr", public_id=patient["public_id"], created="1"))

    return render_template("owner/create_patient.html")


@bp.route("/patients/<public_id>/qr")
@owner_required
def patient_qr(public_id):
    patient = models.get_patient_by_public_id(public_id)
    if not patient:
        return ("Patient not found.", 404)
    return render_template(
        "qr_card.html",
        patient=patient,
        has_password=models.patient_has_password(patient),
        qr_url=url_for("auth.go_via_qr", public_id=patient["public_id"], _external=True),
        back_url=url_for("owner.patient_detail", public_id=patient["public_id"]),
        back_label="go_to_full_record",
        created=request.args.get("created") == "1",
    )


@bp.route("/patients/<public_id>")
@owner_required
def patient_detail(public_id):
    patient = models.get_patient_by_public_id(public_id)
    if not patient:
        return ("Patient not found.", 404)
    patient["allergies"] = models.list_allergies(patient["id"])
    patient["conditions"] = models.list_conditions(patient["id"])
    patient["antibiotic_records"] = models.list_antibiotic_records(patient["id"])
    models.log_action("owner", current_actor_label(), "view_patient", target=public_id)
    return render_template("owner/patient_detail.html", patient=patient)


@bp.route("/patients/<public_id>/export-pdf")
@bp.route("/patients/<public_id>/export-pdf/en")
@owner_required
def export_patient_pdf(public_id):
    patient = models.get_patient_by_public_id(public_id)
    if not patient:
        return ("Patient not found.", 404)
    allergies = models.list_allergies(patient["id"])
    conditions = models.list_conditions(patient["id"])
    records = models.list_antibiotic_records(patient["id"])
    pdf_bytes = generate_patient_history_pdf(patient, allergies, conditions, records)
    models.log_action("owner", current_actor_label(), "export_pdf_en", target=public_id)
    filename = f"{patient['public_id']}-antibiotic-summary-en.pdf"
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@bp.route("/patients/<public_id>/export-pdf/ar")
@owner_required
def export_patient_pdf_ar(public_id):
    patient = models.get_patient_by_public_id(public_id)
    if not patient:
        return ("Patient not found.", 404)
    allergies = models.list_allergies(patient["id"])
    conditions = models.list_conditions(patient["id"])
    records = models.list_antibiotic_records(patient["id"])
    try:
        pdf_bytes = generate_patient_history_pdf_arabic(patient, allergies, conditions, records)
    except WkhtmltopdfNotFound as exc:
        return (str(exc), 500)
    models.log_action("owner", current_actor_label(), "export_pdf_ar", target=public_id)
    filename = f"{patient['public_id']}-antibiotic-summary-ar.pdf"
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@bp.route("/patients/<public_id>/reset-password", methods=["POST"])
@full_owner_required
def reset_patient_password(public_id):
    patient = models.get_patient_by_public_id(public_id)
    if not patient:
        return ("Patient not found.", 404)
    new_password = request.form.get("new_password", "").strip()
    models.set_patient_password(patient["id"], new_password or None)
    models.log_action("owner", current_actor_label(), "reset_patient_password", target=public_id)
    flash("Password updated." if new_password else "Password removed — patient can log in with ID only.", "success")
    return redirect(url_for("owner.patient_detail", public_id=public_id))


@bp.route("/patients/<public_id>/allergies/add", methods=["POST"])
@full_owner_required
def add_patient_allergy(public_id):
    patient = models.get_patient_by_public_id(public_id)
    if not patient:
        return ("Patient not found.", 404)
    add_allergy_from_form(patient, request.form)
    models.log_action("owner", current_actor_label(), "add_allergy", target=public_id)
    return redirect(url_for("owner.patient_detail", public_id=public_id))


@bp.route("/patients/<public_id>/conditions/add", methods=["POST"])
@full_owner_required
def add_patient_condition(public_id):
    patient = models.get_patient_by_public_id(public_id)
    if not patient:
        return ("Patient not found.", 404)
    add_condition_from_form(patient, request.form)
    models.log_action("owner", current_actor_label(), "add_condition", target=public_id)
    return redirect(url_for("owner.patient_detail", public_id=public_id))


@bp.route("/patients/<public_id>/pregnancy-status", methods=["POST"])
@full_owner_required
def update_patient_pregnancy_status(public_id):
    patient = models.get_patient_by_public_id(public_id)
    if not patient:
        return ("Patient not found.", 404)
    models.update_pregnancy_status(patient["id"], request.form.get("pregnancy_status", patient["pregnancy_status"]))
    models.log_action("owner", current_actor_label(), "update_pregnancy_status", target=public_id)
    return redirect(url_for("owner.patient_detail", public_id=public_id))


@bp.route("/patients/<public_id>/phone-number", methods=["POST"])
@full_owner_required
def update_patient_phone(public_id):
    patient = models.get_patient_by_public_id(public_id)
    if not patient:
        return ("Patient not found.", 404)
    models.update_phone_number(patient["id"], request.form.get("phone_number", "").strip() or None)
    models.log_action("owner", current_actor_label(), "update_phone_number", target=public_id)
    flash("Phone number updated.", "success")
    return redirect(url_for("owner.patient_detail", public_id=public_id))


@bp.route("/patients/<public_id>/antibiotics/add", methods=["POST"])
@owner_required
def add_patient_antibiotic(public_id):
    patient = models.get_patient_by_public_id(public_id)
    if not patient:
        return ("Patient not found.", 404)
    record, alerts = add_antibiotic_from_form(patient, request.form, added_by=current_owner_role() or "owner")
    models.log_action("owner", current_actor_label(), "add_antibiotic_record", target=public_id,
                      details=record["display_name"])
    # Redirect (rather than rendering the result directly) so the browser's
    # Back button doesn't try to resubmit this POST -- see antibiotic_result().
    return redirect(url_for("owner.antibiotic_result", public_id=public_id, record_id=record["id"]))


@bp.route("/patients/<public_id>/antibiotics/<int:record_id>/result")
@owner_required
def antibiotic_result(public_id, record_id):
    patient = models.get_patient_by_public_id(public_id)
    if not patient:
        return ("Patient not found.", 404)
    record = models.get_antibiotic_record_by_id(record_id)
    if not record or record["patient_id"] != patient["id"]:
        return ("Record not found.", 404)
    return render_template("owner/antibiotic_result.html", patient=patient, record=record, alerts=record["alerts"])


@bp.route("/antibiotics")
@full_owner_required
def antibiotics():
    items = models.list_antibiotics()
    return render_template("owner/antibiotics.html", items=items)


@bp.route("/antibiotics/add", methods=["GET", "POST"])
@full_owner_required
def add_antibiotic():
    if request.method == "POST":
        name = request.form.get("generic_name", "").strip()
        if not name:
            flash("Generic name is required.", "error")
        elif models.get_antibiotic_by_name(name):
            flash("An antibiotic with that generic name already exists.", "error")
        else:
            conditions_raw = request.form.get("contraindicated_conditions", "").strip()
            models.add_antibiotic(
                generic_name=name,
                brand_names=request.form.get("brand_names", "").strip() or None,
                drug_class=request.form.get("drug_class", "").strip(),
                pregnancy_contraindicated=bool(request.form.get("pregnancy_contraindicated")),
                pregnancy_notes=request.form.get("pregnancy_notes", "").strip() or None,
                contraindicated_conditions=[c.strip() for c in conditions_raw.split(",") if c.strip()],
                notes=request.form.get("notes", "").strip() or None,
            )
            models.log_action("owner", current_actor_label(), "add_antibiotic_reference", details=name)
            flash("Antibiotic added to reference database.", "success")
            return redirect(url_for("owner.antibiotics"))
    return render_template("owner/antibiotic_form.html", item=None)


@bp.route("/antibiotics/<int:item_id>/edit", methods=["GET", "POST"])
@full_owner_required
def edit_antibiotic(item_id):
    item = models.get_antibiotic_by_id(item_id)
    if not item:
        return ("Not found.", 404)
    if request.method == "POST":
        conditions_raw = request.form.get("contraindicated_conditions", "").strip()
        models.update_antibiotic(
            item_id,
            generic_name=request.form.get("generic_name", "").strip(),
            drug_class=request.form.get("drug_class", "").strip(),
            brand_names=request.form.get("brand_names", "").strip() or None,
            pregnancy_contraindicated=bool(request.form.get("pregnancy_contraindicated")),
            pregnancy_notes=request.form.get("pregnancy_notes", "").strip() or None,
            contraindicated_conditions=[c.strip() for c in conditions_raw.split(",") if c.strip()],
            notes=request.form.get("notes", "").strip() or None,
        )
        models.log_action("owner", current_actor_label(), "edit_antibiotic_reference",
                          details=request.form.get("generic_name", "").strip())
        flash("Antibiotic updated.", "success")
        return redirect(url_for("owner.antibiotics"))
    return render_template("owner/antibiotic_form.html", item=item)


@bp.route("/antibiotics/<int:item_id>/delete", methods=["POST"])
@full_owner_required
def delete_antibiotic(item_id):
    item = models.get_antibiotic_by_id(item_id)
    if not item:
        return ("Not found.", 404)
    models.delete_antibiotic(item_id)
    models.log_action("owner", current_actor_label(), "delete_antibiotic_reference", details=item["generic_name"])
    flash("Antibiotic removed from reference database.", "success")
    return redirect(url_for("owner.antibiotics"))


@bp.route("/audit-log")
@full_owner_required
def audit_log():
    entries = models.list_audit_logs()
    return render_template("owner/audit_log.html", entries=entries)


@bp.route("/settings", methods=["GET", "POST"])
@full_owner_required
def settings():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        role = request.form.get("role", "staff").strip()
        if role not in models.OWNER_ROLES:
            role = "staff"
        if not username or not password:
            flash("Username and password are required.", "error")
        elif models.get_owner_by_username(username):
            flash("That username already exists.", "error")
        else:
            models.create_owner(username, password, role=role)
            models.log_action("owner", current_actor_label(), "add_owner_account", details=f"{username} ({role})")
            flash("New account created.", "success")
    owners = models.list_owners()
    return render_template("owner/settings.html", owners=owners)
