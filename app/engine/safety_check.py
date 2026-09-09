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
                      recent_exposure_days=30, recent_class_record=None):
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
