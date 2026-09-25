"""Best-effort outbound SMS via Twilio's REST API, called directly with the
standard library's urllib (no twilio SDK dependency) -- same "keep
dependencies light" approach as app/mailer.py (SMTP) and app/ai_gemini.py
(Gemini over HTTPS).

Reads TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / TWILIO_FROM_NUMBER from
config. Every call site MUST treat a failed or unconfigured send as a
silent no-op -- exactly like app/mailer.py's send_email(): an SMS here is
always a notification layered on top of an action that has already
succeeded, never a precondition for it.

NOTE on cost/provider (as of the account set up 2026-09): this deployment
sends from a PLAIN Twilio phone number, not a registered Saudi
alphanumeric sender name ("AlShefa") -- registering a custom sender name
requires the hospital/pharmacy's business registration number (CR) plus an
authorization letter, which wasn't available yet. Texts arrive from an
ordinary international number, and Twilio's per-message cost to Saudi
numbers (~$0.19) is meaningfully higher than a local provider (~0.06-0.10
SAR with Taqnyat/Unifonic/STC at volume). This was a deliberate "get it
working now, switch later" choice. When the CR is available, switching
providers only means rewriting the two functions below (and the TWILIO_*
env vars) -- nothing else in the app talks to Twilio directly.
"""
import base64
import urllib.error
import urllib.parse
import urllib.request

from flask import current_app


def sms_configured():
    """True once TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN and
    TWILIO_FROM_NUMBER are all set. Callers use this to decide whether to
    show the "sign in with phone" option at all, or attempt to send a
    notification -- so an unconfigured site simply behaves as if this
    feature doesn't exist."""
    cfg = current_app.config
    return bool(cfg.get("TWILIO_ACCOUNT_SID") and cfg.get("TWILIO_AUTH_TOKEN") and cfg.get("TWILIO_FROM_NUMBER"))


def _to_e164_sa(raw):
    """Best-effort conversion of a Saudi mobile number in any common local
    format ('0512345678', '512345678', '+966512345678', with spaces/
    dashes) to E.164 ('+966512345678') for actually placing an SMS --
    separate from app/models.py's _normalize_phone, which is only for
    comparing two typed numbers for equality and deliberately throws away
    the country code. Returns None for anything that doesn't look like a
    valid Saudi mobile number (9 digits after the country code, starting
    with 5) rather than guessing and sending to the wrong place."""
    digits = "".join(ch for ch in (raw or "") if ch.isdigit())
    if digits.startswith("00966"):
        digits = digits[2:]
    if digits.startswith("966"):
        subscriber = digits[3:]
    elif digits.startswith("0"):
        subscriber = digits[1:]
    else:
        subscriber = digits
    if len(subscriber) != 9 or not subscriber.startswith("5"):
        return None
    return f"+966{subscriber}"


def send_sms(to_number, body_text):
    """Fire-and-forget SMS via Twilio's REST API. Returns True/False for
    the caller's own logging if it wants it, but NEVER raises -- any
    problem (bad credentials, no network, an unparseable number, Twilio
    account balance exhausted) is swallowed here, exactly like
    app/mailer.py's send_email()."""
    if not to_number or not sms_configured():
        return False
    e164 = _to_e164_sa(to_number)
    if not e164:
        return False
    cfg = current_app.config
    account_sid = cfg["TWILIO_ACCOUNT_SID"]
    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
    payload = urllib.parse.urlencode({
        "To": e164,
        "From": cfg["TWILIO_FROM_NUMBER"],
        "Body": body_text,
    }).encode("utf-8")
    credentials = base64.b64encode(f"{account_sid}:{cfg['TWILIO_AUTH_TOKEN']}".encode("utf-8")).decode("ascii")

    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Authorization", f"Basic {credentials}")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return 200 <= resp.status < 300
    except Exception:
        return False
