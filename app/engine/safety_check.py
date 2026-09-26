"""The core patient-safety logic: given a patient's recorded allergies,
conditions and history, and a candidate antibiotic entry, return a list of
alerts. This is a clinical-decision-SUPPORT tool -- every alert should be
read and verified by a licensed physician or pharmacist, never treated as a
final answer on its own.

Each alert is a plain dict so it can be JSON-serialized and stored on the
antibiotic record for the historical audit trail:
    {"level": "danger" | "warning" | "info",
     "code": short machine-readable reason,
     "title": short heading,
     "message": human-readable explanation}
"""
from datetime import date, timedelta

# Known partial cross-reactivity between antibiotic classes. This is a
# starting reference only (e.g. penicillin/cephalosporin cross-reactivity is
# real but low, historically over-quoted) -- the owner should review and
# adjust this table from clinical guidance before relying on it.
CROSS_REACTIVE_CLASSES = {
    "Penicillin": ["Cephalosporin", "Carbapenem"],
    "Cephalosporin": ["Penicillin"],
}


def _class_matches(a, b):
    if not a or not b:
        return False
    return a.strip().lower() == b.strip().lower()


def check_antibiotic(patient, antibiotic, allergies, conditions, recent_record=None,
                      recent_exposure_days=30, recent_class_record=None,
                      medications=None, interactions=None,
                      resistant_culture=None, culture_resistance_days=30):
    """
    patient: dict (Patient row) -- needs 'pregnancy_status'
    antibiotic: dict (Antibiotic row) or None if a free-text/custom name was
                entered that isn't in the reference database
    allergies: list[dict] -- this patient's PatientAllergy rows
    conditions: list[dict] -- this patient's PatientCondition rows
    recent_record: dict or None -- most recent prior AntibioticRecord of the
                    SAME antibiotic within the lookback window, if any
    recent_class_record: dict or None -- most recent prior AntibioticRecord
                    of a DIFFERENT antibiotic in the SAME drug class within
                    the lookback window, if any (e.g. Augmentin after a
                    recent Amoxicillin course -- both Penicillins)
    medications: list[dict] or None -- this patient's PatientMedication rows
                    (other, non-antibiotic drugs they're currently taking)
    interactions: list[dict] or None -- DrugInteraction reference rows
                    already narrowed down (by app.models.list_interactions_
                    for_antibiotic) to ones relevant to THIS antibiotic
    resistant_culture: dict or None -- this patient's own most recent
                    culture & sensitivity result (app.models.
                    find_resistant_culture), already narrowed down by the
                    caller to one within culture_resistance_days that shows
                    THIS antibiotic as resistant, if any
    culture_resistance_days: int -- the lookback window used above, only
                    used here for the alert's own message text
    Returns: list[dict] alerts (empty means the caller should show "no issues").
    """
    alerts = []

    # 1. Allergy check (direct match + known cross-reactive classes)
    for allergy in allergies:
        allergen = (allergy.get("allergen") or "").strip().lower()
        allergy_class = (allergy.get("drug_class") or "").strip()

        direct_hit = antibiotic and allergen and (
            allergen == antibiotic["generic_name"].strip().lower()
            or (antibiotic.get("drug_class") and allergen == antibiotic["drug_class"].strip().lower())
        )
        class_hit = antibiotic and allergy_class and _class_matches(allergy_class, antibiotic.get("drug_class"))

        if direct_hit or class_hit:
            alerts.append({
                "level": "danger",
                "code": "allergy_direct",
                "title": "Recorded allergy match",
                "message": (
                    f"Patient has a recorded {allergy.get('severity', 'unknown')} allergy to "
                    f"'{allergy.get('allergen')}'"
                    + (f" (reaction: {allergy['reaction']})" if allergy.get("reaction") else "")
                    + ". Do not proceed without physician/pharmacist review."
                ),
            })
            continue

        if antibiotic:
            for cross_class in CROSS_REACTIVE_CLASSES.get(allergy_class, []):
                if _class_matches(cross_class, antibiotic.get("drug_class")):
                    alerts.append({
                        "level": "warning",
                        "code": "allergy_cross_reactivity",
                        "title": "Possible cross-reactivity",
                        "message": (
                            f"Patient is allergic to '{allergy.get('allergen')}' ({allergy_class}). "
                            f"{antibiotic['generic_name']} ({antibiotic.get('drug_class')}) has known "
                            "partial cross-reactivity risk. Clinical judgment required."
                        ),
                    })

    # 2. Pregnancy contraindication
    if patient.get("pregnancy_status") == "pregnant" and antibiotic and antibiotic.get("pregnancy_contraindicated"):
        alerts.append({
            "level": "danger",
            "code": "pregnancy_contraindicated",
            "title": "Contraindicated in pregnancy",
            "message": (
                f"{antibiotic['generic_name']} is recorded as contraindicated (or to be avoided) "
                f"during pregnancy. {antibiotic.get('pregnancy_notes') or ''}".strip()
            ),
        })

    # 2b. Culture & sensitivity: this patient's OWN organism tested
    # RESISTANT to this exact antibiotic, on a culture collected recently
    # enough to still be trusted (culture_resistance_days -- susceptibility
    # can change over time, so an old result doesn't block a drug forever).
    # Danger level: prescribing a drug an organism is already known
    # resistant to is a real clinical error, not just a caution. Checked
    # even when `antibiotic` is None (a custom/free-text name not on the
    # reference list) -- a resistant match can still be found by name (see
    # app.models.find_resistant_culture), and staying silent just because
    # the drug isn't in the reference table would defeat the whole point.
    if resistant_culture:
        organism = resistant_culture.get("organism") or "the organism"
        drug_label = antibiotic["generic_name"] if antibiotic else resistant_culture.get("cs_antibiotic_name")
        alerts.append({
            "level": "danger",
            "code": "culture_resistant",
            "title": "Resistant on recent culture",
            "message": (
                f"A culture collected {resistant_culture['collection_date']} shows {organism} is "
                f"RESISTANT to {drug_label} in this patient, within the last "
                f"{culture_resistance_days} days. Do not proceed without physician/pharmacist review."
            ),
        })

    # 3. Recent exposure to the same antibiotic
    if antibiotic and recent_record:
        alerts.append({
            "level": "warning",
            "code": "recent_exposure",
            "title": "Recent exposure to the same antibiotic",
            "message": (
                f"Patient already received {antibiotic['generic_name']} on "
                f"{recent_record['prescribed_date']}, within the last "
                f"{recent_exposure_days} days. Review necessity/resistance risk."
            ),
        })

    # 3b. Recent exposure to a DIFFERENT antibiotic in the SAME class (e.g.
    # two different penicillins within the lookback window). Kept as a
    # separate alert from #3 above so the message correctly says which drug
    # was actually given before, rather than implying it was the same one.
    if antibiotic and recent_class_record:
        alerts.append({
            "level": "warning",
            "code": "recent_exposure_class",
            "title": "Recent exposure to the same antibiotic group",
            "message": (
                f"Patient already received {recent_class_record['display_name']} "
                f"(also {antibiotic.get('drug_class')}) on "
                f"{recent_class_record['prescribed_date']}, within the last "
                f"{recent_exposure_days} days. Same-class repeat exposure -- "
                "review necessity/resistance risk."
            ),
        })

    # 4. Medical condition contraindications
    if antibiotic:
        contraindicated = [c.strip().lower() for c in antibiotic.get("contraindicated_conditions", [])]
        for condition in conditions:
            name = (condition.get("condition_name") or "").strip().lower()
            if name and name in contraindicated:
                alerts.append({
                    "level": "danger",
                    "code": "condition_contraindicated",
                    "title": "Contraindicated medical condition",
                    "message": (
                        f"Patient has a recorded condition '{condition.get('condition_name')}' which is "
                        f"listed as a contraindication for {antibiotic['generic_name']}."
                    ),
                })

    # 5. Drug-drug interactions with another medication the patient is
    # currently recorded as taking (not itself an antibiotic -- e.g.
    # tizanidine, warfarin). Reference rows are pre-narrowed by the caller
    # to ones that apply to THIS antibiotic (by exact name or whole class);
    # here we just match those against what's on the patient's medication
    # list. Severity/level comes from the reference entry itself (sensible
    # to store danger for a hard contraindication, warning for "monitor
    # closely", etc.) rather than being hardcoded, since real interaction
    # severity varies entry to entry.
    if antibiotic and medications and interactions:
        for medication in medications:
            # Match by every name this medication is known under: what the
            # patient actually typed/scanned, PLUS -- when it resolved to a
            # medications_reference row (see app.models.get_medication_
            # reference_by_name) -- that row's generic name and every one
            # of its brand names. This is what lets a patient-recorded
            # brand name (e.g. "Coumadin") still match a reference
            # interaction row written against the generic name
            # ("Warfarin"), and vice versa, instead of silently missing the
            # interaction just because the two sides used different names
            # for the same drug.
            candidates = {(medication.get("medication_name") or "").strip().lower()}
            if medication.get("resolved_generic_name"):
                candidates.add(medication["resolved_generic_name"].strip().lower())
            for brand in medication.get("resolved_brand_names") or []:
                candidates.add(brand.strip().lower())
            candidates.discard("")
            if not candidates:
                continue
            for interaction in interactions:
                ref_drug = (interaction.get("interacting_drug") or "").strip().lower()
                if not ref_drug or ref_drug not in candidates:
                    continue
                message_parts = []
                if interaction.get("category_label"):
                    message_parts.append(f"[{interaction['category_label']}]")
                if interaction.get("mechanism"):
                    message_parts.append(interaction["mechanism"])
                if interaction.get("management"):
                    message_parts.append(f"Management: {interaction['management']}")
                if interaction.get("notes"):
                    message_parts.append(interaction["notes"])
                message = " ".join(message_parts).strip() or (
                    f"{antibiotic['generic_name']} has a recorded interaction with "
                    f"{medication.get('medication_name')}."
                )
                alerts.append({
                    "level": interaction.get("severity") or "warning",
                    "code": "drug_drug_interaction",
                    "title": f"Interaction: {antibiotic['generic_name']} + {medication.get('medication_name')}",
                    "message": message,
                })

    if not antibiotic:
        alerts.append({
            "level": "info",
            "code": "not_in_reference",
            "title": "Antibiotic not in reference database",
            "message": (
                "This antibiotic name was not found in the hospital's reference list, so "
                "automatic allergy/pregnancy/condition checks could not run for it. "
                "Please verify manually and ask the owner/admin to add it to the reference list."
            ),
        })

    if not alerts:
        alerts.append({
            "level": "info",
            "code": "no_issues_found",
            "title": "No known issues found",
            "message": (
                "Based on the information currently recorded for this patient, no allergy, "
                "pregnancy, recent-exposure, or condition-based issues were found. This does "
                "not replace a physician or pharmacist's own judgment."
            ),
        })

    return alerts


def recent_cutoff_date(days):
    return (date.today() - timedelta(days=days)).isoformat()
