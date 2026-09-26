"""Reads a photo of a medication package (box/bottle/blister strip label) --
brand-name or generic, Arabic or English -- and extracts the OTHER
(non-antibiotic) medications on it, for the patient's "My Other
Medications" list (see app/records.py's add_medication_from_form and
app/engine/safety_check.py's drug-drug interaction check).

This is the mirror image of app/prescription_scan.py, which does the same
kind of photo reading but keeps ONLY antibiotics and discards everything
else. Here it's the other way around: a patient scanning, say, their blood
thinner or antihistamine box doesn't know (and shouldn't need to know) its
scientific/generic name -- this reads whatever brand name is printed and
resolves it against this hospital's medications reference list (see
app/db.py's medications_reference table) the same way a prescription photo
resolves an antibiotic brand name.

If the photo actually shows an ANTIBIOTIC instead (people don't always sort
their own medications into "antibiotic" vs "other" before taking a photo),
this flags that per item (is_likely_antibiotic) rather than silently filing
a real antibiotic away as a plain "other medication" -- the caller skips
those and tells the patient to use the antibiotic scanner instead, so it
still gets the full allergy/pregnancy/condition/recent-exposure safety
check that only runs for antibiotic entries.

The actual HTTP call to Gemini and its shared error handling live in
app/ai_gemini.py, alongside app/prescription_scan.py, app/culture_scan.py
and app/voice_resolve.py -- this file owns only the medication-specific
prompt and schema."""
import base64

from app.ai_gemini import AIScanNotConfigured, call_gemini, downscale_image

_MEDICATION_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "medication_name": {
            "type": "string",
            "description": (
                "The GENERIC name of the medication (e.g. 'Warfarin', not the brand name "
                "'Coumadin'), resolved using the hospital's medications reference list you were "
                "given when the drug is on it. If it's a real medication not on that list, give "
                "your best-known generic name from general pharmacology knowledge instead of "
                "skipping it. If the label is too unclear to be sure, still give your best-guess "
                "generic name here and set confidence to \"low\"."
            ),
        },
        "name_as_written": {
            "type": "string",
            "description": "Exactly what is written on the package for this drug (brand name, generic, or as best you can make out), before you resolved it.",
        },
        "is_likely_antibiotic": {
            "type": "boolean",
            "description": (
                "True if this medication is actually an ANTIBIOTIC (e.g. Amoxicillin, "
                "Azithromycin, any -cillin/-mycin/-floxacin type drug) rather than another kind "
                "of medication. Antibiotics should still be reported here (never silently "
                "dropped) so the app can tell the patient to add it through the antibiotic "
                "scanner instead, where it gets proper safety checks."
            ),
        },
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "notes": {"type": "string", "description": "Anything the reviewing pharmacist should double-check (glare, unclear label, expiry date, etc). Empty string if nothing."},
    },
    "required": ["medication_name", "name_as_written", "is_likely_antibiotic", "confidence"],
}

_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "medications": {
            "type": "array",
            "description": "One entry per distinct medication found on the photo. Empty array if none.",
            "items": _MEDICATION_ITEM_SCHEMA,
        },
        "read_issues": {
            "type": "string",
            "description": "Empty string if the photo was clear. Otherwise a short plain-language note, e.g. 'Label is blurry / partly cut off'.",
        },
    },
    "required": ["medications", "read_issues"],
}


def _medication_reference_block(known_medications):
    """Same idea as app.ai_gemini.reference_list_block, but for the
    medications_reference table's shape (generic_name/brand_names only --
    no drug_class, unlike the antibiotics table)."""
    lines = []
    for m in known_medications:
        brands = f" (brand names: {m['brand_names']})" if m.get("brand_names") else ""
        lines.append(f"- {m['generic_name']}{brands}")
    return "\n".join(lines) if lines else "(reference list unavailable)"


def _build_prompt(known_medications):
    ref_block = _medication_reference_block(known_medications)
    return (
        "You are reading a photo of a medication package (box, bottle, or blister strip) for a "
        "hospital patient-safety system. The photo shows the printed product label -- brand or "
        "generic name, strength, barcode, batch number, manufacturer, etc. -- in Arabic or "
        "English either way.\n\n"
        "Your job: identify every medication on it and extract structured details for each one, "
        "returned as JSON matching the schema you were given.\n\n"
        "A package often names a BRAND, not the generic drug. Resolve brand names to generic "
        "names using this hospital's own reference list where the drug appears on it:\n"
        f"{ref_block}\n\n"
        "If a medication isn't on that list, still extract it using your own pharmacology "
        "knowledge -- don't skip a real medication just because this hospital hasn't added it to "
        "their reference table yet.\n\n"
        "If any medication on the photo is actually an ANTIBIOTIC, still include it in the "
        "'medications' array (never drop it), but set is_likely_antibiotic to true for it -- the "
        "app handles those separately.\n\n"
        "Labels can be glare/angle-distorted or partly obscured. Do your best, and use the "
        "confidence/notes fields honestly rather than guessing silently. Return an empty "
        "medications array if you find zero medications -- never omit the field."
    )


def build_medication_scan_note(item):
    """Builds the patient_medications.notes text for a photo-extracted
    entry, so a pharmacist (or the patient themselves) reviewing the list
    later can see exactly what the AI read -- same idea as
    app.prescription_scan.build_scan_note."""
    as_written = (item.get("name_as_written") or "").strip()
    confidence = item.get("confidence") or "unknown"
    parts = [f'Read from a medication package photo (as written: "{as_written}"; confidence: {confidence}).']
    if item.get("notes"):
        parts.append(item["notes"].strip())
    return " ".join(p for p in parts if p)


def scan_medication_image(image_bytes, api_key, model, known_medications):
    """Returns {"medications": [...], "read_issues": "..."}. Raises an
    app.ai_gemini.AIScanError (or the AIScanNotConfigured subclass) on any
    failure."""
    if not api_key:
        raise AIScanNotConfigured(
            "Medication photo scanning isn't turned on for this site yet -- GEMINI_API_KEY isn't set."
        )

    processed_bytes, media_type = downscale_image(image_bytes)
    b64_image = base64.b64encode(processed_bytes).decode("ascii")

    result = call_gemini(
        b64_data=b64_image,
        media_type=media_type,
        prompt=_build_prompt(known_medications),
        response_schema=_RESPONSE_SCHEMA,
        api_key=api_key,
        model=model,
        not_readable_message="The AI service didn't return a readable result. Please try again.",
        declined_message_template="The AI service declined to read this photo ({reason}).",
    )
    result.setdefault("medications", [])
    result.setdefault("read_issues", "")
    return result
