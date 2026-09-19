"""Reads a photo of EITHER a written prescription OR a medication package
(box/bottle/blister strip label) -- typed or handwritten, brand-name or
generic, Arabic or English -- with a vision-capable AI model, and extracts
ONLY the antibiotic entries on it -- any other medication on the same
photo is deliberately left out.

A prescription and a medicine package look very different (a doctor's
written order vs. a manufactured product label with a barcode/batch
number), so the model is told about both and figures out which one it's
looking at. The practical difference: a package almost never shows a dose
schedule (how often, for how many days) the way a prescription does --
that's expected and fine, the extracted entry is just added with those
fields blank for a pharmacist to fill in by hand, exactly like a partly
unclear prescription photo already works today.

Important: this module only turns a photo into the SAME plain dict that
the manual "Add antibiotic" form already produces. Whatever it extracts
still goes through app/records.py's add_antibiotic_from_form(), which runs
the exact same allergy / condition / recent-exposure / drug-interaction /
culture-resistance safety checks used for a hand-typed entry (see
app/engine/safety_check.py). This module never bypasses that -- it only
fills in the form faster.

Calls the Anthropic API directly over HTTPS with the standard library
(urllib) rather than the anthropic SDK, to keep this dependency-light
app's only new requirement an API key -- see README.md section
"Prescription photo scan" for setup.
"""
import base64
import io
import json
import urllib.error
import urllib.request

from app.dose_format import DOSE_UNITS, DURATION_UNITS, FREQUENCIES

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
MAX_IMAGE_DIMENSION = 1600
REQUEST_TIMEOUT_SECONDS = 55
TOOL_NAME = "record_prescription_antibiotics"


class PrescriptionScanError(Exception):
    """Any failure reading or interpreting the prescription photo. Callers
    should catch this and show the plain-language message to staff rather
    than letting the request fail with a 500."""


class PrescriptionScanNotConfigured(PrescriptionScanError):
    """The feature is installed but ANTHROPIC_API_KEY isn't set yet."""


def _downscale_image(image_bytes):
    """Best-effort downscale/re-encode to keep the request small and cheap.
    If Pillow isn't installed or can't open this file, fall back to sending
    the original bytes unchanged rather than failing the whole scan over a
    resize step that's a nice-to-have, not a requirement."""
    try:
        from PIL import Image
    except ImportError:
        return image_bytes, "image/jpeg"

    try:
        img = Image.open(io.BytesIO(image_bytes))
        img = img.convert("RGB")
        img.thumbnail((MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION))
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=85)
        return out.getvalue(), "image/jpeg"
    except Exception:
        return image_bytes, "image/jpeg"


_TOOL_SCHEMA = {
    "name": TOOL_NAME,
    "description": (
        "Record every ANTIBIOTIC medication found on this photo -- which may be a written "
        "prescription OR a medication package (box/bottle/blister strip label). "
        "Leave every non-antibiotic medication out entirely -- never list one "
        "of those as an antibiotic."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "antibiotics": {
                "type": "array",
                "description": "One entry per distinct antibiotic found on the photo. Empty array if none.",
                "items": {
                    "type": "object",
                    "properties": {
                        "antibiotic_name": {
                            "type": "string",
                            "description": (
                                "The GENERIC name of the antibiotic (e.g. 'Amoxicillin', not the brand "
                                "name 'Amoxil'), resolved using the hospital reference list you were "
                                "given when the drug is on it. If it's a real antibiotic not on that "
                                "list, give your best-known generic name from general pharmacology "
                                "knowledge instead of skipping it. If handwriting is too unclear to be "
                                "sure, still give your best-guess generic name here and set confidence "
                                "to \"low\"."
                            ),
                        },
                        "name_as_written": {
                            "type": "string",
                            "description": "Exactly what is written for this drug -- on the prescription, or on the medication package -- (brand name, generic, or as best you can make out), before you resolved it.",
                        },
                        "dose_amount": {"type": "string", "description": "Numeral only, e.g. '500'. Empty string if not stated -- a medication package's per-tablet/per-mL strength (e.g. '500' from '500mg tablets') counts and should be filled in here, that IS on the package."},
                        "dose_unit": {"type": "string", "enum": DOSE_UNITS + ["other", ""]},
                        "dose_unit_other": {"type": "string", "description": "Only set if dose_unit is 'other'."},
                        "frequency": {"type": "string", "enum": FREQUENCIES + ["other", ""], "description": "How often to take it. This is almost NEVER printed on a medication package (only on a prescription) -- leave empty ('') rather than guess when scanning a package."},
                        "frequency_other": {"type": "string", "description": "Only set if frequency is 'other'."},
                        "duration_amount": {"type": "string", "description": "Numeral only, e.g. '7'. Empty string if not stated -- this is almost NEVER printed on a medication package, only on a prescription."},
                        "duration_unit": {"type": "string", "enum": DURATION_UNITS + ["other", ""]},
                        "duration_unit_other": {"type": "string", "description": "Only set if duration_unit is 'other'."},
                        "prescribed_by": {"type": "string", "description": "Prescribing doctor's name if legible on a PRESCRIPTION, else empty string. Never applicable to a medication package."},
                        "prescribed_date": {"type": "string", "description": "ISO date YYYY-MM-DD if a prescribing/issue date is visible on a PRESCRIPTION, else empty string. Never use a package's manufacture date, expiry date, or batch/lot number here -- those are not the same thing and must be left out (mention an expiry date in notes instead, if it seems clinically relevant)."},
                        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                        "notes": {"type": "string", "description": "Anything the reviewing pharmacist should double-check (illegible handwriting, ambiguous dose, a package's expiry date, etc). Empty string if nothing."},
                    },
                    "required": ["antibiotic_name", "name_as_written", "confidence"],
                },
            },
            "other_medications_ignored": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Names (as written) of any NON-antibiotic medications also on the photo, correctly left out of 'antibiotics'.",
            },
            "read_issues": {
                "type": "string",
                "description": "Empty string if the photo was clear. Otherwise a short plain-language note, e.g. 'Handwriting on the second line is hard to read' or 'Photo is blurry / partly cut off'.",
            },
        },
        "required": ["antibiotics", "other_medications_ignored", "read_issues"],
    },
}


def _build_prompt(known_antibiotics):
    ref_lines = []
    for a in known_antibiotics:
        brands = f" (brand names: {a['brand_names']})" if a.get("brand_names") else ""
        ref_lines.append(f"- {a['generic_name']}{brands} [{a['drug_class']}]")
    ref_block = "\n".join(ref_lines) if ref_lines else "(reference list unavailable)"

    return (
        "You are reading a photo for a hospital antibiotic safety system. The photo is EITHER:\n"
        "  (a) a real patient PRESCRIPTION -- typed/printed OR handwritten, possibly listing several "
        "medications together, OR\n"
        "  (b) a MEDICATION PACKAGE -- a photo of the actual box, bottle, or blister strip of a "
        "medicine, showing its printed product label (brand/generic name, strength, barcode, batch "
        "number, manufacturer, etc.) rather than a doctor's written order.\n"
        "Figure out which one you're looking at from what's actually in the photo, and read it "
        "accordingly -- in Arabic or English either way.\n\n"
        "Your ONLY job: identify every ANTIBIOTIC on it and extract structured details for each "
        "using the record_prescription_antibiotics tool. Completely ignore and exclude every "
        "medication that is not an antibiotic (painkillers, antihistamines, vitamins, antacids, "
        "etc.) -- list their names in other_medications_ignored instead, never in antibiotics.\n\n"
        "A prescription or package often names a BRAND, not the generic drug. Resolve brand names to "
        "generic names using this hospital's own reference list where the drug appears on it:\n"
        f"{ref_block}\n\n"
        "If an antibiotic isn't on that list, still extract it using your own pharmacology "
        "knowledge -- don't skip a real antibiotic just because this hospital hasn't added it to "
        "their reference table yet.\n\n"
        "Important for a MEDICATION PACKAGE specifically: a box/bottle label normally shows the drug's "
        "name and per-unit strength (e.g. '500mg' -> dose_amount/dose_unit), but essentially NEVER shows "
        "how often or how many days to take it, and NEVER shows a prescribing doctor. Leave frequency, "
        "duration, prescribed_by and prescribed_date empty in that case rather than guessing -- do not "
        "confuse a printed expiry date, manufacture date, or batch/lot number with prescribed_date; they "
        "are not the same thing and must not be used there.\n\n"
        "Handwriting is often messy and package photos can be glare/angle-distorted. Do your best, and "
        "use the confidence/notes fields honestly rather than guessing silently. Always call the tool "
        "exactly once, even if you find zero antibiotics (return an empty antibiotics array in that "
        "case)."
    )


def scan_prescription_image(image_bytes, api_key, model, known_antibiotics):
    """Returns {"antibiotics": [...], "other_medications_ignored": [...], "read_issues": "..."}.
    Raises PrescriptionScanError (or the PrescriptionScanNotConfigured subclass) on any failure."""
    if not api_key:
        raise PrescriptionScanNotConfigured(
            "Prescription photo scanning isn't turned on for this site yet -- ANTHROPIC_API_KEY isn't set."
        )

    processed_bytes, media_type = _downscale_image(image_bytes)
    b64_image = base64.b64encode(processed_bytes).decode("ascii")

    payload = {
        "model": model,
        "max_tokens": 2048,
        "tools": [_TOOL_SCHEMA],
        "tool_choice": {"type": "tool", "name": TOOL_NAME},
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64_image}},
                    {"type": "text", "text": _build_prompt(known_antibiotics)},
                ],
            }
        ],
    }

    req = urllib.request.Request(
        ANTHROPIC_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = json.loads(e.read().decode("utf-8")).get("error", {}).get("message", "")
        except Exception:
            pass
        raise PrescriptionScanError(f"The AI service rejected the request ({e.code}). {detail}".strip())
    except urllib.error.URLError as e:
        raise PrescriptionScanError(f"Couldn't reach the AI service: {e.reason}")
    except TimeoutError:
        raise PrescriptionScanError("The AI service took too long to respond. Please try again.")
    except (ValueError, json.JSONDecodeError):
        raise PrescriptionScanError("The AI service sent back something unreadable. Please try again.")

    for block in body.get("content", []):
        if block.get("type") == "tool_use" and block.get("name") == TOOL_NAME:
            result = block.get("input") or {}
            result.setdefault("antibiotics", [])
            result.setdefault("other_medications_ignored", [])
            result.setdefault("read_issues", "")
            return result

    raise PrescriptionScanError("The AI service didn't return a readable result. Please try again.")
