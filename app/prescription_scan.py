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

Calls Google's Gemini API directly over HTTPS with the standard library
(urllib) rather than a Google SDK, to keep this dependency-light app's
only new requirement an API key -- see README.md section "Prescription
photo scan" for setup. Uses Gemini's "controlled generation" feature
(responseSchema + responseMimeType: application/json) to force a reply
that matches our schema exactly, the same role Anthropic's forced
tool-use served before this module switched providers.
"""
import base64
import io
import json
import urllib.error
import urllib.parse
import urllib.request

from app.dose_format import DOSE_UNITS, DURATION_UNITS, FREQUENCIES

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
MAX_IMAGE_DIMENSION = 1600
REQUEST_TIMEOUT_SECONDS = 55


class PrescriptionScanError(Exception):
    """Any failure reading or interpreting the prescription photo. Callers
    should catch this and show the plain-language message to staff rather
    than letting the request fail with a 500."""


class PrescriptionScanNotConfigured(PrescriptionScanError):
    """The feature is installed but GEMINI_API_KEY isn't set yet."""


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


# Gemini's "responseSchema" is a restricted subset of OpenAPI's schema
# format -- notably no "additionalProperties", but otherwise close enough
# to the tool schema this module used under Anthropic that the shape below
# is almost a direct port of it.
_ANTIBIOTIC_ITEM_SCHEMA = {
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
        "dose_unit": {"type": "string", "enum": DOSE_UNITS + ["other"], "description": "Omit this field entirely (do not include the key) if no dose unit is stated."},
        "dose_unit_other": {"type": "string", "description": "Only set if dose_unit is 'other'."},
        "frequency": {"type": "string", "enum": FREQUENCIES + ["other"], "description": "How often to take it. This is almost NEVER printed on a medication package (only on a prescription) -- omit this field entirely (do not include the key) rather than guess when scanning a package or when not stated."},
        "frequency_other": {"type": "string", "description": "Only set if frequency is 'other'."},
        "duration_amount": {"type": "string", "description": "Numeral only, e.g. '7'. Empty string if not stated -- this is almost NEVER printed on a medication package, only on a prescription."},
        "duration_unit": {"type": "string", "enum": DURATION_UNITS + ["other"], "description": "Omit this field entirely (do not include the key) if no duration unit is stated."},
        "duration_unit_other": {"type": "string", "description": "Only set if duration_unit is 'other'."},
        "prescribed_by": {"type": "string", "description": "Prescribing doctor's name if legible on a PRESCRIPTION, else empty string. Never applicable to a medication package."},
        "prescribed_date": {"type": "string", "description": "ISO date YYYY-MM-DD if a prescribing/issue date is visible on a PRESCRIPTION, else empty string. Never use a package's manufacture date, expiry date, or batch/lot number here -- those are not the same thing and must be left out (mention an expiry date in notes instead, if it seems clinically relevant)."},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "notes": {"type": "string", "description": "Anything the reviewing pharmacist should double-check (illegible handwriting, ambiguous dose, a package's expiry date, etc). Empty string if nothing."},
    },
    "required": ["antibiotic_name", "name_as_written", "confidence"],
}

_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "antibiotics": {
            "type": "array",
            "description": "One entry per distinct antibiotic found on the photo. Empty array if none.",
            "items": _ANTIBIOTIC_ITEM_SCHEMA,
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
}


def _reference_list_block(known_antibiotics):
    """Formats this hospital's antibiotics table into the plain-text block
    both the photo-scan and voice-resolve prompts hand the model, so brand
    names can be resolved to this hospital's own generic-name spelling."""
    ref_lines = []
    for a in known_antibiotics:
        brands = f" (brand names: {a['brand_names']})" if a.get("brand_names") else ""
        ref_lines.append(f"- {a['generic_name']}{brands} [{a['drug_class']}]")
    return "\n".join(ref_lines) if ref_lines else "(reference list unavailable)"


def _build_prompt(known_antibiotics):
    ref_block = _reference_list_block(known_antibiotics)

    return (
        "You are reading a photo for a hospital antibiotic safety system. The photo is EITHER:\n"
        "  (a) a real patient PRESCRIPTION -- typed/printed OR handwritten, possibly listing several "
        "medications together, OR\n"
        "  (b) a MEDICATION PACKAGE -- a photo of the actual box, bottle, or blister strip of a "
        "medicine, showing its printed product label (brand/generic name, strength, barcode, batch "
        "number, manufacturer, etc.) rather than a doctor's written order.\n"
        "Figure out which one you're looking at from what's actually in the photo, and read it "
        "accordingly -- in Arabic or English either way.\n\n"
        "Your ONLY job: identify every ANTIBIOTIC on it and extract structured details for each one, "
        "returned as JSON matching the schema you were given. Completely ignore and exclude every "
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
        "use the confidence/notes fields honestly rather than guessing silently. Return an empty "
        "antibiotics array if you find zero antibiotics -- never omit the field."
    )


def scan_prescription_image(image_bytes, api_key, model, known_antibiotics):
    """Returns {"antibiotics": [...], "other_medications_ignored": [...], "read_issues": "..."}.
    Raises PrescriptionScanError (or the PrescriptionScanNotConfigured subclass) on any failure."""
    if not api_key:
        raise PrescriptionScanNotConfigured(
            "Prescription photo scanning isn't turned on for this site yet -- GEMINI_API_KEY isn't set."
        )

    processed_bytes, media_type = _downscale_image(image_bytes)
    b64_image = base64.b64encode(processed_bytes).decode("ascii")

    result = _call_gemini(
        b64_data=b64_image,
        media_type=media_type,
        prompt=_build_prompt(known_antibiotics),
        response_schema=_RESPONSE_SCHEMA,
        api_key=api_key,
        model=model,
        not_readable_message="The AI service didn't return a readable result. Please try again.",
        declined_message_template="The AI service declined to read this photo ({reason}).",
    )
    result.setdefault("antibiotics", [])
    result.setdefault("other_medications_ignored", [])
    result.setdefault("read_issues", "")
    return result


def _call_gemini(b64_data, media_type, prompt, response_schema, api_key, model,
                  not_readable_message, declined_message_template):
    """Shared HTTP/parsing plumbing for both the photo-scan and voice-resolve
    calls below: send one inline media part (image or audio) plus a text
    prompt to Gemini's generateContent endpoint, using "controlled
    generation" (responseSchema + responseMimeType: application/json) to
    force a reply matching the given schema, and return the parsed JSON
    dict. Raises PrescriptionScanError on any failure."""
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"inline_data": {"mime_type": media_type, "data": b64_data}},
                    {"text": prompt},
                ],
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": response_schema,
        },
    }

    url = f"{GEMINI_API_BASE}/{urllib.parse.quote(model)}:generateContent?key={urllib.parse.quote(api_key)}"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"content-type": "application/json"},
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

    try:
        candidates = body.get("candidates") or []
        if not candidates:
            block_reason = (body.get("promptFeedback") or {}).get("blockReason")
            if block_reason:
                raise PrescriptionScanError(declined_message_template.format(reason=block_reason))
            raise PrescriptionScanError(not_readable_message)

        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts)
        return json.loads(text)
    except PrescriptionScanError:
        raise
    except Exception:
        raise PrescriptionScanError("The AI service sent back something unreadable. Please try again.")


_VOICE_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "heard": {
            "type": "string",
            "description": "Your best-effort plain transcription of what was said, even if it doesn't form a real word -- this is shown to the pharmacist so they can see what the system picked up.",
        },
        "resolved_name": {
            "type": "string",
            "description": (
                "The correctly-spelled GENERIC antibiotic name you believe was spoken, resolved to "
                "this hospital's own spelling using the reference list when it's a brand name or an "
                "alternate spelling. If you cannot confidently identify a real antibiotic drug name "
                "from the audio, put your best-effort transcription here instead (same as 'heard') "
                "rather than inventing one."
            ),
        },
        "matched": {
            "type": "boolean",
            "description": "true only if you are reasonably confident a specific real antibiotic drug name was said -- false for silence, noise, an unrelated word, or genuine uncertainty.",
        },
    },
    "required": ["heard", "resolved_name", "matched"],
}


def _build_voice_prompt(known_antibiotics):
    ref_block = _reference_list_block(known_antibiotics)
    return (
        "You are listening to a short audio clip of a hospital pharmacist speaking the name of ONE "
        "antibiotic drug out loud, so it can be typed into a patient's record -- often with a short "
        "filler phrase attached ('give me...', 'add...', 'it's...'), sometimes in a non-native English "
        "accent, and sometimes a brand name rather than the generic drug name.\n\n"
        "Your job: figure out which real antibiotic drug they most likely meant, using both what you "
        "hear AND your own pharmacology knowledge of how antibiotic names actually sound -- a generic "
        "browser speech-to-text engine often mishears drug names as unrelated ordinary English words "
        "(e.g. 'Cefuroxime' misheard as 'Seafood', 'Ceftriaxone' as 'Safe try zone'); you should do "
        "meaningfully better than that by reasoning about which real drug name the sounds actually "
        "match, not just transcribing literally.\n\n"
        "Resolve brand names to this hospital's own generic-name spelling using its reference list "
        "where the drug appears on it:\n"
        f"{ref_block}\n\n"
        "If the drug isn't on that list, still identify it using your own general pharmacology "
        "knowledge rather than giving up. Only set matched to false if you genuinely cannot identify "
        "any specific real antibiotic from the audio (silence, unrelated speech, background noise, "
        "or a word that doesn't correspond to any real drug name) -- in that case put your best plain "
        "transcription in both 'heard' and 'resolved_name' rather than guessing a random drug."
    )


def resolve_antibiotic_from_audio(audio_bytes, media_type, api_key, model, known_antibiotics):
    """AI-powered replacement for app/voice_match.py's plain fuzzy-text
    matching: takes the actual recorded audio clip from the microphone
    button (rather than trusting the browser's own free, generic speech
    recognizer to have transcribed it correctly first) and asks Gemini to
    identify which antibiotic was said directly from the sound, with this
    hospital's antibiotic list as context. Returns
    {"heard": str, "resolved_name": str, "matched": bool}. Raises
    PrescriptionScanError (or the PrescriptionScanNotConfigured subclass)
    on any failure -- callers should treat that the same as "didn't match"
    and let the pharmacist type the name instead."""
    if not api_key:
        raise PrescriptionScanNotConfigured(
            "Voice-powered antibiotic name matching isn't turned on for this site yet -- GEMINI_API_KEY isn't set."
        )

    b64_audio = base64.b64encode(audio_bytes).decode("ascii")

    result = _call_gemini(
        b64_data=b64_audio,
        media_type=media_type or "audio/webm",
        prompt=_build_voice_prompt(known_antibiotics),
        response_schema=_VOICE_RESPONSE_SCHEMA,
        api_key=api_key,
        model=model,
        not_readable_message="The AI service didn't return a readable result. Please try again.",
        declined_message_template="The AI service declined to process this recording ({reason}).",
    )
    result.setdefault("heard", "")
    result.setdefault("resolved_name", result.get("heard", ""))
    result.setdefault("matched", False)
    return result
