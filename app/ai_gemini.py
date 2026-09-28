"""Shared plumbing behind every AI-powered feature in this app --
prescription-photo scanning (app/prescription_scan.py), culture-report
photo scanning (app/culture_scan.py), other-medication photo scanning
(app/medication_scan.py), AI-powered voice antibiotic-name resolution
(app/voice_resolve.py), and the AI help/support chat (app/help_chat.py).
Each of those files owns its own prompt (and, for the first four, a
forced-JSON schema); this file owns the two things they need against the
AI provider's API: call_gemini() below for a single image/audio part + a
schema-forced JSON reply, and call_gemini_chat() for a free-text,
multi-turn conversation with no image and no forced schema.

NOTE ON THE FILE/FUNCTION NAMES: this app switched its AI provider from
Google's Gemini to OpenAI (see the "why" below) -- everything in this file
now talks to OpenAI's API, not Gemini's. The filename and the function
names call_gemini()/call_gemini_chat() were deliberately left exactly as
they were rather than renamed, purely so the five call sites elsewhere in
the app (prescription_scan.py, culture_scan.py, medication_scan.py,
voice_resolve.py, help_chat.py) didn't all need to change their imports
too -- this file's CONTENTS are the only thing that changed. If you're
reading this fresh: think of "gemini" here as this app's historical name
for "the AI provider module", not a claim about which provider it calls.

Why the switch: Google Cloud billing for a Saudi Arabia-billing-address
account is mandatorily routed through a local reseller (CNTXT) on a slow
monthly invoice cycle rather than instant prepay, which didn't fit this
app's competition deadline. OpenAI's API is directly usable from Saudi
Arabia with ordinary instant card prepay (as little as $5), no reseller
detour -- see README.md for setup.

Calls OpenAI's API directly over HTTPS with the standard library (urllib)
rather than the official Python SDK, to keep this dependency-light app's
only new requirement an API key -- same approach this file always used.
Uses OpenAI's Chat Completions endpoint with "Structured Outputs"
(response_format: json_schema) to steer a reply to match the caller's
schema, the same role Gemini's "controlled generation" (responseSchema)
served before this switch, and Anthropic's forced tool-use before that.

One real capability gap versus Gemini: no current OpenAI chat model
accepts an audio clip AND produces a forced-JSON-schema reply in the same
call the way Gemini could. So a caller that hands call_gemini() an
audio/* media_type (only app/voice_resolve.py does this) gets a two-step
flow instead of one: the audio is transcribed to plain text first (via
OpenAI's separate speech-to-text endpoint, which -- unlike the chat
endpoint's audio input -- tolerates the wide range of formats a phone's
browser actually records in), then that transcript is reasoned about by
the same JSON-schema-forced text call the image-based features use. This
loses a little of the direct acoustic reasoning Gemini could do, but
keeps working: if it ever mis-transcribes badly, that just means a worse
guess or no match, exactly like today's fallback -- the pharmacist can
always type the name by hand, nothing about that failure mode changed.
"""
import base64
import io
import json
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

OPENAI_API_BASE = "https://api.openai.com/v1"
CHAT_COMPLETIONS_URL = f"{OPENAI_API_BASE}/chat/completions"
TRANSCRIPTIONS_URL = f"{OPENAI_API_BASE}/audio/transcriptions"

# The model used only for the audio -> text transcription half of the
# voice-resolution two-step flow described above -- never configurable via
# GEMINI_MODEL/OPENAI_MODEL, since it needs to be a transcription model
# specifically, not whatever general chat/vision model the hospital has
# configured for everything else.
AUDIO_TRANSCRIBE_MODEL = "gpt-4o-transcribe"

# Common browser MediaRecorder / mobile-recording formats mapped to a file
# extension for the transcription upload below -- the transcription
# endpoint infers the audio format from the filename extension plus the
# actual bytes, so this only needs to be a reasonable guess, not exact.
_AUDIO_EXTENSIONS = {
    "audio/webm": "webm",
    "audio/ogg": "ogg",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/wave": "wav",
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/mp4": "mp4",
    "audio/x-m4a": "m4a",
    "audio/m4a": "m4a",
    "audio/aac": "aac",
    "audio/flac": "flac",
}

MAX_IMAGE_DIMENSION = 1600
REQUEST_TIMEOUT_SECONDS = 55

# OpenAI returns HTTP 503 during brief, model-wide traffic spikes -- the
# same kind of transient, Google-side-equivalent capacity issue Gemini's
# 503 meant, not a problem with this app's API key or billing. Retried a
# couple of times with backoff before giving up, same as before.
# Deliberately NOT applied to 429 (a quota/rate-limit issue retrying
# immediately won't fix) or any other error (a real, non-transient
# failure). Unlike the Gemini version of this file, there's no second
# cross-model fallback chain here -- OpenAI's uptime for a paid key is
# high enough for this app's low demo volume that retry-with-backoff alone
# should be enough; a fallback model can be added later if that turns out
# to be wrong.
MAX_503_RETRIES = 2
RETRY_BACKOFF_SECONDS = (1.5, 3.5)


class AIScanError(Exception):
    """Any failure reading or interpreting a photo/audio clip with the AI
    provider. Callers should catch this and show the plain-language
    message to staff rather than letting the request fail with a 500."""


class AIScanNotConfigured(AIScanError):
    """The feature is installed but the API key isn't set yet."""


class AIScanRateLimited(AIScanError):
    """The provider returned HTTP 429 -- the API key's quota (its
    per-minute or per-day request/token allowance, or a billing limit) is
    used up for right now. This is never a problem with the specific
    photo/recording, so callers can show a calmer, more specific message
    than the generic AIScanError catch-all and suggest trying again
    shortly or entering it by hand meanwhile."""


def downscale_image(image_bytes):
    """Best-effort downscale/re-encode to keep the request small and cheap.
    If Pillow isn't installed or can't open this file, fall back to sending
    the original bytes unchanged rather than failing the whole scan over a
    resize step that's a nice-to-have, not a requirement. Shared by every
    photo-based feature -- voice resolution has no image to downscale."""
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
    to this hospital's own generic-name spelling. Shared by all the
    antibiotic-facing features -- prescription scanning, culture scanning,
    and voice resolution all need to resolve a name against the same
    reference list."""
    ref_lines = []
    for a in known_antibiotics:
        brands = f" (brand names: {a['brand_names']})" if a.get("brand_names") else ""
        ref_lines.append(f"- {a['generic_name']}{brands} [{a['drug_class']}]")
    return "\n".join(ref_lines) if ref_lines else "(reference list unavailable)"


def _request_openai(url, payload, api_key, timeout, rate_limited_message, headers=None, raw_body=None):
    """POST either a JSON payload or a pre-built raw_body (for the one
    multipart/form-data caller, the transcription endpoint below) to
    OpenAI, retrying a transient 503 with backoff, and return the parsed
    JSON response body on success. A 429 always raises AIScanRateLimited
    immediately (another attempt against an exhausted quota only wastes
    more of it); any other HTTP error, or a 503 on the last retry, raises
    AIScanError."""
    base_headers = {"authorization": f"Bearer {api_key}"}
    if raw_body is None:
        base_headers["content-type"] = "application/json"
        body_bytes = json.dumps(payload).encode("utf-8")
    else:
        body_bytes = raw_body
    if headers:
        base_headers.update(headers)

    for attempt in range(MAX_503_RETRIES + 1):
        req = urllib.request.Request(url, data=body_bytes, headers=base_headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = json.loads(e.read().decode("utf-8")).get("error", {}).get("message", "")
            except Exception:
                pass
            if e.code == 429:
                raise AIScanRateLimited(rate_limited_message)
            if e.code == 503 and attempt < MAX_503_RETRIES:
                time.sleep(RETRY_BACKOFF_SECONDS[attempt])
                continue
            raise AIScanError(f"The AI service rejected the request ({e.code}). {detail}".strip())
        except urllib.error.URLError as e:
            raise AIScanError(f"Couldn't reach the AI service: {e.reason}")
        except TimeoutError:
            raise AIScanError("The AI service took too long to respond. Please try again.")
        except (ValueError, json.JSONDecodeError):
            raise AIScanError("The AI service sent back something unreadable. Please try again.")


def _transcribe_audio(b64_data, media_type, api_key):
    """First half of the audio two-step described in this file's module
    docstring: turns a short recorded audio clip into a plain-text
    best-effort transcription via OpenAI's speech-to-text endpoint (a
    multipart/form-data file upload, not a JSON body -- a different shape
    from every other call in this file). Raises AIScanError/AIScanRateLimited
    on failure, same as everything else here."""
    try:
        raw_bytes = base64.b64decode(b64_data)
    except Exception:
        raise AIScanError("The recording could not be read. Please try again.")

    ext = _AUDIO_EXTENSIONS.get((media_type or "").lower(), "webm")
    boundary = uuid.uuid4().hex
    parts = [
        f'--{boundary}\r\nContent-Disposition: form-data; name="model"\r\n\r\n{AUDIO_TRANSCRIBE_MODEL}\r\n'.encode("utf-8"),
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="clip.{ext}"\r\n'
            f'Content-Type: {media_type or "application/octet-stream"}\r\n\r\n'
        ).encode("utf-8")
        + raw_bytes
        + b"\r\n",
        f"--{boundary}--\r\n".encode("utf-8"),
    ]
    body = b"".join(parts)

    result = _request_openai(
        TRANSCRIPTIONS_URL,
        payload=None,
        api_key=api_key,
        timeout=REQUEST_TIMEOUT_SECONDS,
        rate_limited_message=(
            "The AI scanning service has reached its usage limit for right now (this is a shared "
            "daily/per-minute allowance for the whole app, not an issue with this specific recording). "
            "Please wait a few minutes and try again, or enter this one by hand for now."
        ),
        headers={"content-type": f"multipart/form-data; boundary={boundary}"},
        raw_body=body,
    )
    return (result.get("text") or "").strip()


def call_gemini(b64_data, media_type, prompt, response_schema, api_key, model,
                 not_readable_message, declined_message_template):
    """Send one inline media part (image or audio) plus a text prompt to
    OpenAI, using "Structured Outputs" (response_format: json_schema) to
    steer a reply matching the given schema, and return the parsed JSON
    dict. Raises AIScanError on any failure -- HTTP-level, or the model
    declining/failing to produce a readable result.

    For an image, this is a single call. For audio (see this file's module
    docstring), it's transcribe-then-reason: the clip is turned into text
    first, then that text is reasoned about by the same schema-forced call
    an image would get, with the original prompt asking for that same
    reasoning either way."""
    if (media_type or "").startswith("audio/"):
        transcript = _transcribe_audio(b64_data, media_type, api_key)
        content = (
            f"{prompt}\n\n"
            f"You do not have the original audio -- only this automatic speech-to-text transcription of "
            f'it, which may well have misheard the drug name: "{transcript}"\n\n'
            "Reason about which real antibiotic drug name was most likely actually said, the same way "
            "you would reason about a garbled word over a bad phone line -- using both this transcription "
            "and your own pharmacology knowledge of how antibiotic names sound, not just the transcription "
            "literally. Put your best-effort read of what was transcribed in 'heard' as usual."
        )
        message_content = [{"type": "text", "text": content}]
    else:
        message_content = [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{b64_data}", "detail": "auto"}},
        ]

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": message_content}],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "extraction_result", "strict": False, "schema": response_schema},
        },
    }

    body = _request_openai(
        CHAT_COMPLETIONS_URL, payload, api_key, REQUEST_TIMEOUT_SECONDS,
        rate_limited_message=(
            "The AI scanning service has reached its usage limit for right now (this is a shared "
            "daily/per-minute allowance for the whole app, not an issue with this specific photo or "
            "recording). Please wait a few minutes and try again, or enter this one by hand for now."
        ),
    )

    try:
        choices = body.get("choices") or []
        if not choices:
            raise AIScanError(not_readable_message)
        choice = choices[0]
        if choice.get("finish_reason") == "content_filter":
            raise AIScanError(declined_message_template.format(reason="content_filter"))
        text = (choice.get("message", {}).get("content") or "").strip()
        if not text:
            raise AIScanError(not_readable_message)
        return json.loads(text)
    except AIScanError:
        raise
    except Exception:
        raise AIScanError("The AI service sent back something unreadable. Please try again.")


def call_gemini_chat(messages, system_instruction, api_key, model):
    """Send a short multi-turn text conversation to OpenAI's Chat
    Completions endpoint -- no image/audio part, no forced JSON schema,
    just plain conversational text in and out -- and return the
    assistant's reply as a plain string. Used only by the AI help/support
    chat (app/help_chat.py).

    messages is a list of (role, text) tuples in order, where role is
    "user" or "model" (this app's historical Gemini-era naming for
    "assistant", kept as-is so app/help_chat.py -- which already speaks in
    those terms -- didn't need to change) -- the last entry should be the
    visitor's newest message. system_instruction is a plain-text block of
    standing instructions (who the assistant is, what it may/may not do).

    Raises AIScanError on any failure, reusing the same exception
    hierarchy as call_gemini() above so callers can handle both the same
    way."""
    chat_messages = [{"role": "system", "content": system_instruction}]
    for role, text in messages:
        chat_messages.append({"role": "assistant" if role == "model" else "user", "content": text})

    payload = {
        "model": model,
        "messages": chat_messages,
        # Short, focused answers -- this is a help widget, not a
        # long-form writing assistant, and a hard cap keeps a single
        # reply cheap regardless of what's asked. (No temperature override
        # here -- some current models reject a custom temperature outright,
        # and the system prompt's own "keep answers short" instruction plus
        # this cap already do the real work.)
        "max_completion_tokens": 400,
    }

    body = _request_openai(
        CHAT_COMPLETIONS_URL, payload, api_key, REQUEST_TIMEOUT_SECONDS,
        rate_limited_message=(
            "The help assistant has reached its usage limit for right now (a shared allowance for "
            "the whole app). Please try again in a few minutes."
        ),
    )

    try:
        choices = body.get("choices") or []
        if not choices:
            raise AIScanError("The assistant didn't return a reply. Please try again.")
        choice = choices[0]
        if choice.get("finish_reason") == "content_filter":
            raise AIScanError("The assistant couldn't answer that (content_filter). Please rephrase.")
        text = (choice.get("message", {}).get("content") or "").strip()
        if not text:
            raise AIScanError("The assistant didn't return a reply. Please try again.")
        return text
    except AIScanError:
        raise
    except Exception:
        raise AIScanError("The AI service sent back something unreadable. Please try again.")
