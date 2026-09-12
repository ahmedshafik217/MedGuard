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


def add_medication_from_form(patient, form):
    models.add_medication(
        patient_id=patient["id"],
        medication_name=form.get("medication_name", "").strip(),
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
    recent_class_record = None
    if antibiotic:
        cutoff = recent_cutoff_date(recent_days)
        recent_record = models.find_recent_record(patient["id"], antibiotic["id"], cutoff)
        if antibiotic.get("drug_class"):
            recent_class_record = models.find_recent_record_by_class(
                patient["id"], antibiotic["drug_class"], cutoff,
                exclude_antibiotic_id=antibiotic["id"],
            )

    allergies = models.list_allergies(patient["id"])
    conditions = models.list_conditions(patient["id"])
    medications = models.list_medications(patient["id"])
    interactions = models.list_interactions_for_antibiotic(antibiotic)
    alerts = check_antibiotic(patient, antibiotic, allergies, conditions,
                               recent_record=recent_record, recent_exposure_days=recent_days,
                               recent_class_record=recent_class_record,
                               medications=medications, interactions=interactions)

    record = models.add_antibiotic_record(
        patient_id=patient["id"],
        antibiotic_id=antibiotic["id"] if antibiotic else None,
        custom_name=None if antibiotic else name,
        # dose/duration free text kept for very old callers only; the
        # actual dose/duration entry now goes entirely through the
        # structured fields below (see app/dose_format.py).
        dose=None,
        duration=None,
        dose_amount=form.get("dose_amount", "").strip() or None,
        dose_unit=form.get("dose_unit", "").strip() or None,
        dose_unit_other=form.get("dose_unit_other", "").strip() or None,
        frequency=form.get("frequency", "").strip() or None,
        frequency_other=form.get("frequency_other", "").strip() or None,
        duration_amount=form.get("duration_amount", "").strip() or None,
        duration_unit=form.get("duration_unit", "").strip() or None,
        duration_unit_other=form.get("duration_unit_other", "").strip() or None,
        prescribed_by=form.get("prescribed_by", "").strip() or None,
        prescribed_date=prescribed_date,
        notes=form.get("notes", "").strip() or None,
        alerts=alerts,
        added_by=added_by,
    )
    return record, alerts
