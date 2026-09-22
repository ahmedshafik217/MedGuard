"""Best-effort outbound email via plain SMTP (Python's own smtplib) -- no
third-party email-service SDK, consistent with how this app already talks
to Gemini directly over HTTPS with urllib (see app/ai_gemini.py's own
docstring for the same "keep dependencies light" reasoning).

Reads SMTP_HOST / SMTP_PORT / SMTP_USERNAME / SMTP_PASSWORD from config
(see app/config.py for defaults and the Gmail-app-password setup this is
built around). Every call site MUST treat a failed or unconfigured send as
a silent no-op -- email here is always a notification layered on top of an
action that has already succeeded (a password was already reset, a record
was already added), never a precondition for it. That mirrors how
app/models.py's log_action() treats a failed audit-log write: patient-
safety features keep working even if this side-channel has a problem.
"""
import smtplib
import ssl
from email.message import EmailMessage

from flask import current_app


def email_configured():
    """True once both SMTP_USERNAME and SMTP_PASSWORD are set. Callers use
    this to decide whether to even show the "sign in with email" option, or
    attempt to send a notification at all -- so an unconfigured site simply
    behaves as if this feature doesn't exist, rather than showing a broken
    option or silently failing every time."""
    cfg = current_app.config
    return bool(cfg.get("SMTP_USERNAME") and cfg.get("SMTP_PASSWORD"))


def send_email(to_address, subject, body_text):
    """Fire-and-forget plain-text email. Returns True/False for the
    caller's own logging if it wants it, but NEVER raises -- any problem
    (bad credentials, no network, an invalid address) is swallowed here."""
    if not to_address or not email_configured():
        return False
    cfg = current_app.config
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = f"{cfg.get('SMTP_FROM_NAME', 'AmanBio')} <{cfg['SMTP_USERNAME']}>"
        msg["To"] = to_address
        msg.set_content(body_text)

        context = ssl.create_default_context()
        with smtplib.SMTP(cfg.get("SMTP_HOST", "smtp.gmail.com"), int(cfg.get("SMTP_PORT", 587)),
                           timeout=15) as server:
            server.starttls(context=context)
            server.login(cfg["SMTP_USERNAME"], cfg["SMTP_PASSWORD"])
            server.send_message(msg)
        return True
    except Exception:
        return False
