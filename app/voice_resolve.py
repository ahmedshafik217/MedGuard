"""AI-powered replacement for app/voice_match.py's plain fuzzy-text
matching: takes the actual recorded audio clip from the microphone button
on the "Add antibiotic" form (rather than trusting the browser's own free,
generic speech recognizer to have transcribed it correctly first) and asks
Gemini to identify which antibiotic was said directly from the sound, with
this hospital's antibiotic list as context.

A generic browser speech-to-text engine frequently mishears drug names as
unrelated ordinary English words -- "Cefuroxime" as "Seafood",
"Ceftriaxone" as "Safe try zone" -- because it transcribes blindly with no
medical vocabulary. This module instead has Gemini reason directly from
the audio about which real antibiotic name the sounds actually match,
using both what it hears and its own pharmacology knowledge, which does
meaningfully better than blind transcription.

This never touches a patient record itself -- it only fills in the "Add
antibiotic" form's name field faster, the same safety checks in
app/records.py still run when that form is actually submitted.

The actual HTTP call to Gemini and its shared error handling live in
app/ai_gemini.py, alongside app/prescription_scan.py and
app/culture_scan.py (photo-based features) -- this file owns only the
voice-specific prompt and schema.
"""
import base64

from app.ai_gemini import AIScanNotConfigured, call_gemini, reference_list_block

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
    ref_block = reference_list_block(known_antibiotics)
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
    """Returns {"heard": str, "resolved_name": str, "matched": bool}.
    Raises an app.ai_gemini.AIScanError (or the AIScanNotConfigured
    subclass) on any failure -- callers should treat that the same as
    "didn't match" and let the pharmacist type the name instead."""
    if not api_key:
        raise AIScanNotConfigured(
            "Voice-powered antibiotic name matching isn't turned on for this site yet -- GEMINI_API_KEY isn't set."
        )

    b64_audio = base64.b64encode(audio_bytes).decode("ascii")

    result = call_gemini(
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
