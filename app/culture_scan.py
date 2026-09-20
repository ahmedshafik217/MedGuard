"""Reads a photo of a microbiology CULTURE & SENSITIVITY (antibiogram) lab
report -- typed or handwritten, in Arabic or English either way -- and
extracts the specimen type, organism, and every antibiotic's
Sensitive/Intermediate/Resistant result from its susceptibility panel.

Important: this module only turns a photo into the SAME plain dict that
the manual "Add culture result" form already produces. Whatever it
extracts still goes through app/records.py's add_culture_from_ai_scan()
(which calls add_culture_from_form() -- the exact same function a
hand-typed culture result uses, via a small adapter so the AI's
already-parsed sensitivity list looks like the form's repeatable rows).
This module never bypasses that -- it only fills in the form faster.
Unlike prescription scanning, a wrong Sensitive/Resistant reading here is
more dangerous than a missing one, so the prompt below is deliberately
told to leave a row out entirely rather than guess at an unclear result.

The actual HTTP call to Gemini and its shared error handling live in
app/ai_gemini.py, alongside app/prescription_scan.py (prescription/
medication-package photos) and app/voice_resolve.py (spoken antibiotic
names) -- this file owns only the culture-report-specific prompt and
schema.
"""
import base64

from app.ai_gemini import AIScanNotConfigured, call_gemini, downscale_image, reference_list_block

# Must match the <select> options in the "Add culture" form (patient_detail.html)
# and the specimen_/sensitivity result translation keys exactly.
_SPECIMEN_TYPES = ["blood", "urine", "wound", "sputum", "csf", "stool", "other"]
_SENSITIVITY_RESULTS = ["sensitive", "intermediate", "resistant"]

_CULTURE_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "specimen_type": {
            "type": "string",
            "enum": _SPECIMEN_TYPES,
            "description": "The specimen type the report was taken from. Use 'other' if it's none of the listed ones.",
        },
        "specimen_type_other": {
            "type": "string",
            "description": "Only set (and only if specimen_type is 'other') to the specimen type as named on the report, e.g. 'Throat swab' or 'CVC tip'.",
        },
        "collection_date": {
            "type": "string",
            "description": (
                "ISO date YYYY-MM-DD the SPECIMEN was collected from the patient, if printed on the "
                "report. Empty string if not stated. Never use the report's print date, received date, "
                "or result/finalized date instead -- those are not the same thing and must be left out."
            ),
        },
        "organism": {
            "type": "string",
            "description": (
                "The organism identified (e.g. 'Escherichia coli', 'Staphylococcus aureus (MRSA)'), "
                "exactly as best you can read it. If the report states no growth / no organism "
                "isolated, write that (e.g. 'No growth') rather than leaving this blank."
            ),
        },
        "lab_name": {
            "type": "string",
            "description": "Name of the laboratory or hospital that issued the report, if printed. Empty string if not shown.",
        },
        "sensitivities": {
            "type": "array",
            "description": (
                "One entry per antibiotic on the report's susceptibility/antibiogram panel with a "
                "clearly readable S/I/R result. Leave out any row whose result you can't read "
                "confidently rather than guessing -- an omitted antibiotic is far safer than a wrong "
                "Sensitive/Resistant result. Empty array if there's no susceptibility panel at all "
                "(e.g. a 'no growth' report)."
            ),
            "items": {
                "type": "object",
                "properties": {
                    "antibiotic_name": {
                        "type": "string",
                        "description": "The GENERIC antibiotic name as tested, resolved to this hospital's reference list spelling where it appears there.",
                    },
                    "result": {
                        "type": "string",
                        "enum": _SENSITIVITY_RESULTS,
                        "description": "The S/I/R result for this antibiotic. Map common report abbreviations: S -> sensitive, I -> intermediate, R -> resistant.",
                    },
                },
                "required": ["antibiotic_name", "result"],
            },
        },
        "notes": {
            "type": "string",
            "description": "Anything the reviewing pharmacist should double-check (illegible organism name, an antibiotic result you weren't confident enough to include, etc). Empty string if nothing.",
        },
        "read_issues": {
            "type": "string",
            "description": "Empty string if the photo was clear. Otherwise a short plain-language note, e.g. 'Bottom of the antibiogram table is cut off' or 'Photo is blurry.'",
        },
    },
    "required": ["specimen_type", "organism", "sensitivities", "read_issues"],
}


def _build_culture_prompt(known_antibiotics):
    ref_block = reference_list_block(known_antibiotics)
    return (
        "You are reading a photo of a microbiology CULTURE & SENSITIVITY (antibiogram) lab report for "
        "a hospital antibiotic safety system -- typed or handwritten, in Arabic or English either way.\n\n"
        "Extract structured details from it using the schema you were given: the specimen type it was "
        "taken from, the date the specimen was COLLECTED (not printed/reported), the organism "
        "identified (or 'No growth' if that's what the report says), the lab name if shown, and every "
        "antibiotic on its susceptibility panel together with its Sensitive/Intermediate/Resistant "
        "result.\n\n"
        "Resolve each tested antibiotic's name to this hospital's own generic-name spelling using its "
        "reference list where it appears there:\n"
        f"{ref_block}\n\n"
        "If a tested antibiotic isn't on that list, still include it using your own pharmacology "
        "knowledge for the correct generic spelling rather than skipping it. But if any single row's "
        "S/I/R result is genuinely too unclear to read confidently, leave that one row out entirely "
        "(mention it in notes) rather than guessing -- an incorrect resistance result is far more "
        "dangerous here than a missing one.\n\n"
        "Handwriting and photocopied/faxed lab reports are often messy. Do your best, and use the "
        "notes/read_issues fields honestly rather than guessing silently."
    )


def scan_culture_image(image_bytes, api_key, model, known_antibiotics):
    """Returns {"specimen_type": str, "specimen_type_other": str,
    "collection_date": str, "organism": str, "lab_name": str,
    "sensitivities": [{"antibiotic_name": str, "result": str}, ...],
    "notes": str, "read_issues": str}.
    Raises an app.ai_gemini.AIScanError (or the AIScanNotConfigured
    subclass) on any failure. See app/records.py's add_culture_from_ai_scan
    for what happens to this dict next."""
    if not api_key:
        raise AIScanNotConfigured(
            "Culture report photo scanning isn't turned on for this site yet -- GEMINI_API_KEY isn't set."
        )

    processed_bytes, media_type = downscale_image(image_bytes)
    b64_image = base64.b64encode(processed_bytes).decode("ascii")

    result = call_gemini(
        b64_data=b64_image,
        media_type=media_type,
        prompt=_build_culture_prompt(known_antibiotics),
        response_schema=_CULTURE_RESPONSE_SCHEMA,
        api_key=api_key,
        model=model,
        not_readable_message="The AI service didn't return a readable result. Please try again.",
        declined_message_template="The AI service declined to read this photo ({reason}).",
    )
    result.setdefault("specimen_type", "other")
    result.setdefault("specimen_type_other", "")
    result.setdefault("collection_date", "")
    result.setdefault("organism", "")
    result.setdefault("lab_name", "")
    result.setdefault("sensitivities", [])
    result.setdefault("notes", "")
    result.setdefault("read_issues", "")
    return result
