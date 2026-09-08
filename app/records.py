"""Shared helpers for mutating a patient's record, used by both the patient
blueprint (patient editing their own record) and the owner blueprint (owner
editing any record on a patient's behalf). Keeping this in one place means
the safety-check logic is only ever called from one code path."""
from datetime import date

from flask import current_app

from app import models
from app.engine.safety_check import check_antibiotic, recent_cutoff_date


def add_allergy_from_form(patient, form):
    models.add_allergy(
        patient_id=patient["id"],
        allergen=form.get("allergen", "").strip(),
        drug_class=form.get("drug_class", "").strip() or None,
        reaction=form.get("reaction", "").strip() or None,
        severity=form.get("severity", "unknown"),
    )


def add_condition_from_form(patient, form):
    models.add_condition(
        patient_id=patient["id"],
        condition_name=form.get("condition_name", "").strip(),
        notes=form.get("notes", "").strip() or None,
    )


def add_antibiotic_from_form(patient, form, added_by):
    name = form.get("antibiotic_name", "").strip()
    antibiotic = models.get_antibiotic_by_name(name) if name else None

    date_raw = form.get("prescribed_date", "").strip()
    if date_raw:
        try:
            prescribed_date = date.fromisoformat(date_raw).isoformat()
        except ValueError:
            prescribed_date = date.today().isoformat()
    else:
        prescribed_date = date.today().isoformat()

    recent_days = current_app.config.get("RECENT_EXPOSURE_DAYS", 30)
    recent_record = None
    if antibiotic:
        cutoff = recent_cutoff_date(recent_days)
        recent_record = models.find_recent_record(patient["id"], antibiotic["id"], cutoff)

    allergies = models.list_allergies(patient["id"])
    conditions = models.list_conditions(patient["id"])
    alerts = check_antibiotic(patient, antibiotic, allergies, conditions,
                               recent_record=recent_record, recent_exposure_days=recent_days)

    record = models.add_antibiotic_record(
        patient_id=patient["id"],
        antibiotic_id=antibiotic["id"] if antibiotic else None,
        custom_name=None if antibiotic else name,
        dose=form.get("dose", "").strip() or None,
        duration=form.get("duration", "").strip() or None,
        prescribed_by=form.get("prescribed_by", "").strip() or None,
        prescribed_date=prescribed_date,
        notes=form.get("notes", "").strip() or None,
        alerts=alerts,
        added_by=added_by,
    )
    return record, alerts
