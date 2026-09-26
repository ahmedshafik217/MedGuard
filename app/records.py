"""Shared helpers for mutating a patient's record, used by both the patient
blueprint (patient editing their own record) and the owner blueprint (owner
editing any record on a patient's behalf). Keeping this in one place means
the safety-check logic is only ever called from one code path."""
from datetime import date

from flask import current_app, session

from app import models, notify
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


def add_medication_from_form(patient, form, source="manual", source_photo=None):
    name = form.get("medication_name", "").strip()
    reference = models.get_medication_reference_by_name(name) if name else None
    models.add_medication(
        patient_id=patient["id"],
        medication_name=name,
        medication_id=reference["id"] if reference else None,
        notes=form.get("notes", "").strip() or None,
        source=source,
        source_photo=source_photo,
    )


def add_medications_from_ai_scan(patient, scan_result, source_photo):
    """Turns app/medication_scan.py's scan_medication_image() output into
    saved patient_medications rows -- one add_medication_from_form() call
    per item, exactly like a hand-typed entry (so it gets the same
    medications_reference resolution). Items the AI flagged as actually
    being an ANTIBIOTIC are deliberately skipped here -- filing a real
    antibiotic away as a plain "other medication" would mean it never goes
    through the allergy/pregnancy/condition/recent-exposure safety check
    that only runs for antibiotic entries (see add_antibiotic_from_form
    below). Returns (added_names, skipped_antibiotic_names) so the caller
    can flash a clear message about each.
    """
    from app.medication_scan import build_medication_scan_note

    added_names = []
    skipped_antibiotic_names = []
    for item in scan_result.get("medications", []):
        display_name = (item.get("medication_name") or item.get("name_as_written") or "").strip()
        if not display_name:
            continue
        if item.get("is_likely_antibiotic"):
            skipped_antibiotic_names.append(display_name)
            continue
        form_data = {
            "medication_name": display_name,
            "notes": build_medication_scan_note(item),
        }
        add_medication_from_form(patient, form_data, source="photo_ai", source_photo=source_photo)
        added_names.append(display_name)
    return added_names, skipped_antibiotic_names


def add_hospitalization_from_form(patient, form, recorded_by="patient"):
    admission_raw = form.get("admission_date", "").strip()
    if admission_raw:
        try:
            admission_date = date.fromisoformat(admission_raw).isoformat()
        except ValueError:
            admission_date = date.today().isoformat()
    else:
        admission_date = date.today().isoformat()

    discharge_raw = form.get("discharge_date", "").strip()
    discharge_date = None
    if discharge_raw:
        try:
            discharge_date = date.fromisoformat(discharge_raw).isoformat()
        except ValueError:
            discharge_date = None
    if discharge_date and discharge_date < admission_date:
        # Not a valid stay (discharge before admission) -- drop the
        # discharge date rather than save something nonsensical; the stay
        # is then just shown as ongoing/open-ended.
        discharge_date = None

    models.add_hospitalization(
        patient_id=patient["id"],
        admission_date=admission_date,
        discharge_date=discharge_date,
        reason=form.get("reason", "").strip() or None,
        notes=form.get("notes", "").strip() or None,
        recorded_by=recorded_by,
    )


def classify_infection_origin(symptom_onset_date, hospitalizations):
    """Purely informational Hospital-Acquired (HAI) vs Community-Acquired
    (CAI) label for one antibiotic record -- never touches the safety-check
    engine or its alerts. Returns 'hospital_acquired', 'community_acquired',
    or None when there isn't enough information to say anything (no
    symptom-onset date recorded for this entry).

    Standard clinical rule (dates only -- no time of day is collected, so
    "48 hours" is treated as 2 full calendar days, and "48-72 hours after
    discharge" as 2-3 days after discharge):
      - Hospital-Acquired: onset is >=48h after admission AND still within
        that same hospital stay (before/at discharge, or the stay is still
        ongoing); OR onset falls 48-72h after discharge (a very recently
        discharged patient still counts as hospital-acquired).
      - Otherwise: Community-Acquired.
    """
    if not symptom_onset_date:
        return None
    try:
        onset = date.fromisoformat(symptom_onset_date)
    except ValueError:
        return None

    for stay in hospitalizations or []:
        admission_raw = stay.get("admission_date")
        if not admission_raw:
            continue
        try:
            admission = date.fromisoformat(admission_raw)
        except ValueError:
            continue

        discharge = None
        discharge_raw = stay.get("discharge_date")
        if discharge_raw:
            try:
                discharge = date.fromisoformat(discharge_raw)
            except ValueError:
                discharge = None

        if onset >= admission and (discharge is None or onset <= discharge):
            if (onset - admission).days >= 2:
                return "hospital_acquired"
        elif discharge is not None and onset > discharge:
            days_after_discharge = (onset - discharge).days
            if 2 <= days_after_discharge <= 3:
                return "hospital_acquired"

    return "community_acquired"


def attach_infection_origin(records, hospitalizations):
    """Mutates each antibiotic-record dict in place, adding an
    'infection_origin' key (see classify_infection_origin above) -- shared
    by the patient dashboard and the owner patient-detail page so both
    display the exact same label from the exact same rule."""
    for record in records:
        record["infection_origin"] = classify_infection_origin(
            record.get("symptom_onset_date"), hospitalizations,
        )
    return records


class _ScanFormAdapter:
    """Makes a plain dict (as produced by an AI photo-scan extraction, see
    app/prescription_scan.py) look enough like a Flask form (.get/.getlist)
    for add_culture_from_form below to run completely unchanged -- so a
    scanned culture report goes through the exact same
    date-parsing/defaulting logic as one a pharmacist typed in by hand, in
    the one place that logic lives. List-valued dict entries answer
    .getlist(); everything else answers .get()."""

    def __init__(self, data):
        self._data = data

    def get(self, key, default=""):
        value = self._data.get(key, default)
        return default if value is None else value

    def getlist(self, key):
        value = self._data.get(key)
        return value if isinstance(value, list) else []


def add_culture_from_ai_scan(patient, extracted, recorded_by="owner"):
    """Turns app/prescription_scan.py's scan_culture_image() output into the
    same plain dict shape the manual "Add culture" form produces, then
    calls add_culture_from_form() below completely unchanged -- see that
    function's own comments for the date-parsing/defaulting this reuses.
    extracted's "notes" and "read_issues" are combined into one notes
    string so a pharmacist reviewing history later can see exactly what
    the AI read, same as _prescription_scan_note() does for antibiotics."""
    notes_parts = [
        'Read from a culture report photo.',
    ]
    if extracted.get("notes"):
        notes_parts.append(extracted["notes"].strip())
    if extracted.get("read_issues"):
        notes_parts.append(extracted["read_issues"].strip())

    form_data = {
        "specimen_type": extracted.get("specimen_type", ""),
        "specimen_type_other": extracted.get("specimen_type_other", ""),
        "collection_date": extracted.get("collection_date", ""),
        "organism": extracted.get("organism", ""),
        "lab_name": extracted.get("lab_name", ""),
        "notes": " ".join(notes_parts),
        "sensitivity_antibiotic_name": [
            (s.get("antibiotic_name") or "").strip() for s in extracted.get("sensitivities", [])
        ],
        "sensitivity_result": [
            (s.get("result") or "").strip() for s in extracted.get("sensitivities", [])
        ],
    }
    return add_culture_from_form(patient, _ScanFormAdapter(form_data), recorded_by=recorded_by)


def add_culture_from_form(patient, form, recorded_by="owner"):
    specimen_type = form.get("specimen_type", "").strip() or "other"
    specimen_type_other = form.get("specimen_type_other", "").strip() or None

    collection_raw = form.get("collection_date", "").strip()
    if collection_raw:
        try:
            collection_date = date.fromisoformat(collection_raw).isoformat()
        except ValueError:
            collection_date = date.today().isoformat()
    else:
        collection_date = date.today().isoformat()

    # Repeatable antibiotic+result rows -- see the "Add another antibiotic"
    # button on the culture form -- arrive as two same-length parallel
    # lists (sensitivity_antibiotic_name[i] goes with sensitivity_result[i]).
    # A row left blank on either side is skipped rather than saved
    # half-filled (see models.add_culture).
    names = form.getlist("sensitivity_antibiotic_name")
    results = form.getlist("sensitivity_result")
    sensitivities = [
        {"antibiotic_name": n, "result": r}
        for n, r in zip(names, results)
    ]

    return models.add_culture(
        patient_id=patient["id"],
        specimen_type=specimen_type,
        specimen_type_other=specimen_type_other,
        collection_date=collection_date,
        organism=form.get("organism", "").strip(),
        sensitivities=sensitivities,
        lab_name=form.get("lab_name", "").strip() or None,
        notes=form.get("notes", "").strip() or None,
        recorded_by=recorded_by,
    )


def add_antibiotic_from_form(patient, form, added_by, source="manual", source_photo=None):
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

    # Optional -- when the patient's symptoms actually started, as opposed
    # to prescribed_date (when the antibiotic was started). Used only for
    # the informational Hospital-Acquired/Community-Acquired label (see
    # classify_infection_origin above); left blank if not entered or not
    # a valid date, never defaulted to today (unlike prescribed_date --
    # guessing an onset date would make the HAI/CAI label misleading).
    onset_raw = form.get("symptom_onset_date", "").strip()
    symptom_onset_date = None
    if onset_raw:
        try:
            symptom_onset_date = date.fromisoformat(onset_raw).isoformat()
        except ValueError:
            symptom_onset_date = None

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

    culture_days = current_app.config.get("CULTURE_RESISTANCE_LOOKBACK_DAYS", 30)
    resistant_culture = None
    if antibiotic or name:
        culture_cutoff = recent_cutoff_date(culture_days)
        resistant_culture = models.find_resistant_culture(patient["id"], antibiotic, name, culture_cutoff)

    allergies = models.list_allergies(patient["id"])
    conditions = models.list_conditions(patient["id"])
    medications = models.list_medications(patient["id"])
    interactions = models.list_interactions_for_antibiotic(antibiotic)
    alerts = check_antibiotic(patient, antibiotic, allergies, conditions,
                               recent_record=recent_record, recent_exposure_days=recent_days,
                               recent_class_record=recent_class_record,
                               medications=medications, interactions=interactions,
                               resistant_culture=resistant_culture, culture_resistance_days=culture_days)

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
        symptom_onset_date=symptom_onset_date,
        notes=form.get("notes", "").strip() or None,
        alerts=alerts,
        added_by=added_by,
        source=source,
        source_photo=source_photo,
    )

    # Best-effort notification emails -- never block or fail the add
    # itself (see app/notify.py's own docstring). Every "add antibiotic"
    # entry point (manual form, photo scan, patient self-entry, staff
    # entry) goes through this one function, so this one hook covers all
    # of them.
    lang = session.get("lang", "ar")
    notify.send_new_antibiotic_notice(patient, record, lang=lang)
    if any(a.get("level") == "danger" for a in alerts):
        notify.send_danger_alert_to_owners(models.list_full_owner_emails(), patient, record, alerts, lang=lang)

    return record, alerts
