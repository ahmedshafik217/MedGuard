"""AI-powered help & support chat -- a small floating widget (see the
"help-chat-*" block in app/templates/base.html) that lets anyone using the
site -- a patient, a hospital/pharmacy staff member, or a visitor still on
the welcome/login page -- ask in plain language "how do I add an
antibiotic?" or "what does this app actually do for me?" and get an
immediate, plain-language answer, instead of hunting through menus or
calling the hospital.

Built on the same Gemini integration already used for prescription/culture
photo scanning and voice antibiotic-name resolution (see
app/ai_gemini.py) -- GEMINI_API_KEY / GEMINI_MODEL are already configured
for those features, so this one needs no new setup on top of what's
already on Render. Silently unavailable (the help icon simply doesn't
render -- see help_chat_configured() below, injected into every template
in app/__init__.py's inject_i18n() the same way email_configured() and
sms_configured() already are) until GEMINI_API_KEY is set.

IMPORTANT SAFETY BOUNDARY: this assistant answers ONLY questions about the
app itself -- what it does, how to use a feature, what benefit it gives
the patient. The system prompt below explicitly forbids it from ever
giving clinical/medical advice (a dosing question, "is this drug safe for
me", interpreting a lab/culture result, what to do about a symptom, etc.)
-- any such question must be redirected to a licensed pharmacist/doctor,
or to the app's own tested safety-check engine (see app/engine/
safety_check.py) rather than the assistant's own judgment. That is a
product/safety boundary, not a style preference: the whole point of this
app is to route drug-safety decisions through a licensed professional and
its own reviewed logic, never through a general-purpose AI's opinion."""
from flask import current_app

from app.ai_gemini import AIScanError, AIScanNotConfigured, call_gemini_chat

# A generous but firm cap -- keeps one request cheap and keeps a visitor
# from pasting in an essay. The widget's own textarea enforces this too,
# this is the server-side backstop.
MAX_MESSAGE_LENGTH = 500

# How many of the most recent user/assistant turns are replayed as context
# on each new message -- enough for a short back-and-forth to make sense,
# small enough that a long chat never balloons a single request's cost.
MAX_HISTORY_TURNS = 6

SYSTEM_PROMPT = """You are "Aman" (أمان), the friendly in-app help assistant for AmanBio -- \
a bilingual (Arabic/English) web app built for Al Shefa Specialized Hospital that lets a \
patient keep their own antibiotic-safety record on their phone.

WHAT THE APP ACTUALLY DOES (this is your only knowledge domain -- explain and recommend \
only what is true here, don't invent features):
- Every patient has a private record of: allergies, pregnancy status (if applicable), \
recorded medical conditions, and their full antibiotic history.
- Each time a physician or pharmacist prescribes an antibiotic, the patient (or hospital \
staff) adds it to the record, and the app AUTOMATICALLY runs a safety check against: \
recorded allergies (including known cross-reactive drug classes), pregnancy \
contraindications, recent exposure to the same antibiotic, recorded medical-condition \
contraindications, and (when a recent culture/sensitivity result is on file) resistant-\
organism warnings. This is the app's core benefit: it catches a dangerous repeat \
prescription or interaction before it happens.
- Every patient gets a private Patient ID (like ASH-7K3F9Q) and a QR code / printable ID \
card. Scanning the QR code (or handing over the ID) at a hospital/pharmacy desk pulls up \
the record instantly -- much faster and safer than the patient trying to recall their own \
antibiotic history from memory.
- A patient (or staff, for any patient) can export a one-page PDF summary -- in either \
English or Arabic -- of the full record and history, to bring to a doctor's visit.
- Sign-in options depend on what the hospital has configured: always by Patient ID (with \
an optional password), and sometimes also by email one-time code. If a patient forgets \
their password (or even their Patient ID), the "Forgot password?" link lets them recover \
access using their phone number and date of birth, which are on file even when phone-\
based messaging isn't turned on.
- The whole site works in Arabic or English -- there is a language toggle at the very top \
of every page, and switching does not lose any entered data.
- Hospital/pharmacy staff have their own dashboard to look up any patient, add antibiotics, \
run photo-based prescription scanning (an AI reads a photo of a written prescription), and \
(for a full Clinical Pharmacist/Controller account) manage the antibiotic reference \
database and staff accounts.

WHAT YOU MUST NEVER DO:
- Never give clinical or medical advice of any kind: no dosing guidance, no opinion on \
whether a specific drug is safe for a specific person, no interpreting a lab/culture \
result, no reacting to a described symptom, no suggesting a diagnosis or treatment. If \
asked anything like this, say plainly that you can only help with using the app, and that \
this kind of question needs a licensed pharmacist or physician -- or, if it's about \
whether a specific antibiotic is safe to take, point them to the app's own "Add \
Antibiotic" feature, which runs the real safety check against their actual record.
- Never claim to be a doctor, pharmacist, or any kind of medical professional.
- Never ask the visitor to tell you their allergies, medications, conditions, or any other \
health information in this chat -- that information belongs in the app's own record forms, \
not in a chat log. If they start describing personal health details, gently redirect them \
to the relevant page in the app instead of continuing to discuss the details themselves.
- Never invent a feature, button, or page that isn't described above. If you're not sure \
the app has something, say you're not sure rather than guessing.
- Never discuss anything unrelated to this app (general knowledge, other topics, writing \
code, etc.) -- politely steer back to how you can help with the app.

STYLE:
- Keep answers short: 2-4 sentences for a simple question, a short list only if genuinely \
helpful for step-by-step instructions.
- Warm, plain, non-technical language -- you're talking to a patient, not a clinician.
- Always reply in the SAME language the visitor's site is currently set to (you will be \
told which one), regardless of what language they type in.
- This is a prototype built for a competition, not yet a legally registered commercial \
product -- if asked directly about legal/business status, say so honestly rather than \
making claims about the hospital's official adoption of it."""


def help_chat_configured():
    """True once GEMINI_API_KEY is set -- same "configured" gating pattern
    as app/mailer.py's email_configured() and app/sms.py's sms_configured().
    Callers (the context processor in app/__init__.py) use this to decide
    whether the floating help icon even renders."""
    return bool(current_app.config.get("GEMINI_API_KEY"))


def ask_help_assistant(message, history, lang):
    """Send one visitor message (plus recent conversation history) to the
    help assistant and return its plain-text reply. Raises AIScanNotConfigured
    if GEMINI_API_KEY isn't set, or AIScanError for any other failure --
    callers should catch both the same way the Gemini-powered owner routes
    already do (see app/owner/routes.py's resolve_antibiotic_voice_audio).

    history is a list of (role, text) tuples already in chronological order,
    where role is "user" or "assistant" -- exactly what the widget's own
    fetch() call sends back on each turn (see base.html), never persisted
    server-side. lang is "ar" or "en", the visitor's current site language."""
    if not help_chat_configured():
        raise AIScanNotConfigured("The help assistant isn't set up on this site yet.")

    message = (message or "").strip()
    if not message:
        raise AIScanError("Please type a question first.")
    message = message[:MAX_MESSAGE_LENGTH]

    language_name = "Arabic" if lang == "ar" else "English"
    system_instruction = f"{SYSTEM_PROMPT}\n\nThe visitor's site is currently set to {language_name}. Reply in {language_name}."

    turns = []
    for role, text in (history or [])[-(MAX_HISTORY_TURNS * 2):]:
        gemini_role = "model" if role == "assistant" else "user"
        clean_text = (text or "").strip()[:MAX_MESSAGE_LENGTH]
        if clean_text:
            turns.append((gemini_role, clean_text))
    turns.append(("user", message))

    cfg = current_app.config
    return call_gemini_chat(
        messages=turns,
        system_instruction=system_instruction,
        api_key=cfg["GEMINI_API_KEY"],
        model=cfg["GEMINI_MODEL"],
    )
