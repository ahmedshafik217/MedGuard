"""Shared plumbing behind every Gemini-powered feature in this app --
prescription-photo scanning (app/prescription_scan.py), culture-report
photo scanning (app/culture_scan.py), and AI-powered voice antibiotic-name
resolution (app/voice_resolve.py). Each of those files owns its own prompt
and schema; this file only owns the one thing they all need identically:
sending an image or audio clip plus a text prompt to Gemini's
generateContent endpoint and getting back JSON that matches a given
schema.

Calls Google's Gemini API directly over HTTPS with the standard library
(urllib) rather than a Google SDK, to keep this dependency-light app's
only new requirement an API key -- see README.md section "Prescription
photo scan" for setup. Uses Gemini's "controlled generation" feature
(responseSchema + responseMimeType: application/json) to force a reply
that matches the caller's schema exactly, the same role Anthropic's forced
tool-use served before this app switched providers.
"""
import io
import json
import urllib.error
import urllib.parse
import urllib.request

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
MAX_IMAGE_DIMENSION = 1600
REQUEST_TIMEOUT_SECONDS = 55


class AIScanError(Exception):
    """Any failure reading or interpreting a photo/audio clip with Gemini.
    Callers should catch this and show the plain-language message to staff
    rather than letting the request fail with a 500."""


class AIScanNotConfigured(AIScanError):
    """The feature is installed but GEMINI_API_KEY isn't set yet."""


def downscale_image(image_bytes):
    """Best-effort downscale/re-encode to keep the request small and cheap.
    If Pillow isn't installed or can't open this file, fall back to sending
    the original bytes unchanged rather than failing the whole scan over a
    resize step that's a nice-to-have, not a requirement. Shared by both
    photo-based features (prescription and culture-report scanning) --
    voice resolution has no image to downscale."""
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


def reference_list_block(known_antibiotics):
    """Formats this hospital's antibiotics table into the plain-text block
    every feature's prompt hands the model, so brand names can be resolved
    to this hospital's own generic-name spelling. Shared by all three
    features -- prescription scanning, culture scanning, and voice
    resolution all need to resolve a name against the same reference
    list."""
    ref_lines = []
    for a in known_antibiotics:
        brands = f" (brand names: {a['brand_names']})" if a.get("brand_names") else ""
        ref_lines.append(f"- {a['generic_name']}{brands} [{a['drug_class']}]")
    return "\n".join(ref_lines) if ref_lines else "(reference list unavailable)"


def call_gemini(b64_data, media_type, prompt, response_schema, api_key, model,
                 not_readable_message, declined_message_template):
    """Send one inline media part (image or audio) plus a text prompt to
    Gemini's generateContent endpoint, using "controlled generation"
    (responseSchema + responseMimeType: application/json) to force a reply
    matching the given schema, and return the parsed JSON dict. Raises
    AIScanError on any failure -- HTTP-level, or Gemini declining/failing
    to produce a readable result."""
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
        raise AIScanError(f"The AI service rejected the request ({e.code}). {detail}".strip())
    except urllib.error.URLError as e:
        raise AIScanError(f"Couldn't reach the AI service: {e.reason}")
    except TimeoutError:
        raise AIScanError("The AI service took too long to respond. Please try again.")
    except (ValueError, json.JSONDecodeError):
        raise AIScanError("The AI service sent back something unreadable. Please try again.")

    try:
        candidates = body.get("candidates") or []
        if not candidates:
            block_reason = (body.get("promptFeedback") or {}).get("blockReason")
            if block_reason:
                raise AIScanError(declined_message_template.format(reason=block_reason))
            raise AIScanError(not_readable_message)

        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts)
        return json.loads(text)
    except AIScanError:
        raise
    except Exception:
        raise AIScanError("The AI service sent back something unreadable. Please try again.")
