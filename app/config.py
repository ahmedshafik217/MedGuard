import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-key-change-me")

    DATABASE_PATH = os.environ.get(
        "DATABASE_PATH", str(BASE_DIR / "instance" / "alshefa.db")
    )

    # Session / cookie security. SESSION_COOKIE_SECURE must be "1" once the app
    # is served over HTTPS in production -- see .env.example.
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "0") == "1"

    # How many days count as "recent" antibiotic exposure for the safety engine.
    RECENT_EXPOSURE_DAYS = int(os.environ.get("RECENT_EXPOSURE_DAYS", "30"))

    # How many days a culture & sensitivity result stays "current" for the
    # safety engine's resistant-organism warning (see app/engine/
    # safety_check.py) -- susceptibility can genuinely change over time, so
    # an old culture shouldn't block a drug forever, only a reasonably
    # recent one.
    CULTURE_RESISTANCE_LOOKBACK_DAYS = int(os.environ.get("CULTURE_RESISTANCE_LOOKBACK_DAYS", "30"))

    # Login rate limiting (see app/rate_limit.py): after this many FAILED
    # attempts against the same username/patient ID, or this many failed
    # attempts from the same source IP (looser, since a hospital front
    # desk/kiosk may be shared by many legitimate patients), further
    # attempts are blocked until the window passes. Only failures count --
    # a correct login never contributes to a lockout.
    LOGIN_ATTEMPT_LIMIT = int(os.environ.get("LOGIN_ATTEMPT_LIMIT", "5"))
    LOGIN_ATTEMPT_WINDOW_MINUTES = int(os.environ.get("LOGIN_ATTEMPT_WINDOW_MINUTES", "15"))
    LOGIN_IP_ATTEMPT_LIMIT = int(os.environ.get("LOGIN_IP_ATTEMPT_LIMIT", "20"))

    # Self-service patient registration (see app/rate_limit.py's
    # check_registration_rate): after this many registrations from the
    # same source IP within the window, further registrations are blocked
    # until it passes -- stops the open registration form from being used
    # to flood the patient list with throwaway records. Looser than the
    # login limits since a real front-desk/kiosk IP may legitimately
    # register several new patients in a row.
    REGISTRATION_IP_LIMIT = int(os.environ.get("REGISTRATION_IP_LIMIT", "8"))
    REGISTRATION_WINDOW_MINUTES = int(os.environ.get("REGISTRATION_WINDOW_MINUTES", "60"))

    # First-run owner account (used only by seed.py).
    OWNER_USERNAME = os.environ.get("OWNER_USERNAME", "admin")
    OWNER_PASSWORD = os.environ.get("OWNER_PASSWORD", "change-this-password")

    LANGUAGES = ["en", "ar"]
    DEFAULT_LANGUAGE = "ar"

    # Prescription photo scan (see app/prescription_scan.py, README.md
    # section "Prescription photo scan"): reads a photo of a written
    # prescription with an AI vision model and pulls out just the
    # antibiotics. Feature is silently unavailable (clear error shown to
    # staff) until GEMINI_API_KEY is set -- nothing else in the app
    # depends on it.
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
    PRESCRIPTION_PHOTO_MAX_BYTES = int(os.environ.get("PRESCRIPTION_PHOTO_MAX_MB", "10")) * 1024 * 1024
    # A little headroom over the photo limit itself for multipart overhead.
    MAX_CONTENT_LENGTH = PRESCRIPTION_PHOTO_MAX_BYTES + 2 * 1024 * 1024

    # Outbound email (see app/mailer.py): a patient's one-time email
    # sign-in code, password-reset notices, a "new antibiotic added" copy,
    # and the full-owner "danger alert" notice all go out this way.
    # Silently unavailable (the email sign-in option just doesn't appear,
    # and the notification emails are simply skipped) until SMTP_USERNAME
    # and SMTP_PASSWORD are both set -- nothing else in the app depends on
    # it. Defaults target Gmail's own SMTP relay (587, STARTTLS): the
    # simplest setup is a Gmail account plus an "app password"
    # (https://myaccount.google.com/apppasswords) -- SMTP_USERNAME is the
    # full Gmail address, SMTP_PASSWORD is the 16-character app password
    # (NOT the normal Gmail login password). Any other SMTP-compatible
    # provider works the same way by overriding SMTP_HOST/SMTP_PORT too.
    SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
    SMTP_USERNAME = os.environ.get("SMTP_USERNAME")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
    SMTP_FROM_NAME = os.environ.get("SMTP_FROM_NAME", "AmanBio - Al Shefa")

    # Email sign-in code (see app/notify.py, app/models.py's
    # create_patient_login_code/verify_patient_login_code): how long a
    # requested code stays valid, and how many codes a given email/IP may
    # request in a window -- separate from LOGIN_ATTEMPT_LIMIT above (that
    # one is about WRONG-code guesses; this one is about how often a code
    # can be requested at all, so the sign-in form can't be used to spam
    # someone's inbox).
    EMAIL_CODE_TTL_MINUTES = int(os.environ.get("EMAIL_CODE_TTL_MINUTES", "10"))
    EMAIL_CODE_REQUEST_LIMIT = int(os.environ.get("EMAIL_CODE_REQUEST_LIMIT", "5"))
    EMAIL_CODE_REQUEST_WINDOW_MINUTES = int(os.environ.get("EMAIL_CODE_REQUEST_WINDOW_MINUTES", "15"))

    # Outbound SMS (see app/sms.py): a patient's one-time phone sign-in
    # code, plus SMS copies of the password-reset and new-antibiotic
    # notices (the "critical safety alert" notice still only goes to full
    # owners by email -- owner accounts don't have a phone number field).
    # Silently unavailable until all three TWILIO_* vars are set --
    # nothing else in the app depends on it. Currently configured for a
    # PLAIN Twilio phone number (no Saudi alphanumeric sender-ID
    # registration yet -- see app/sms.py's docstring for what that means
    # for cost and how to switch providers later once the hospital/
    # pharmacy's business registration (CR) is in hand).
    TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
    TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
    TWILIO_FROM_NUMBER = os.environ.get("TWILIO_FROM_NUMBER")

    SMS_CODE_TTL_MINUTES = int(os.environ.get("SMS_CODE_TTL_MINUTES", "10"))
    SMS_CODE_REQUEST_LIMIT = int(os.environ.get("SMS_CODE_REQUEST_LIMIT", "5"))
    SMS_CODE_REQUEST_WINDOW_MINUTES = int(os.environ.get("SMS_CODE_REQUEST_WINDOW_MINUTES", "15"))

    # AI help/support chat (see app/help_chat.py): the floating help icon
    # shown site-wide. Reuses GEMINI_API_KEY/GEMINI_MODEL above -- no new
    # setup needed. These two just cap how many chat messages one IP can
    # send in a window, since this endpoint (unlike the other Gemini
    # features) is reachable without signing in at all.
    HELP_CHAT_IP_LIMIT = int(os.environ.get("HELP_CHAT_IP_LIMIT", "20"))
    HELP_CHAT_WINDOW_MINUTES = int(os.environ.get("HELP_CHAT_WINDOW_MINUTES", "15"))

    # Patient self-service AI photo-scan / voice-resolve when adding their
    # own antibiotic (see app/patient/routes.py, app/rate_limit.py's
    # check_patient_ai_scan_rate) -- the owner/staff side of the same
    # features has no limit (see app/owner/routes.py) since staff are a
    # small, trusted population; patients are not, and each tap can
    # trigger a real Gemini API cost.
    PATIENT_AI_SCAN_LIMIT = int(os.environ.get("PATIENT_AI_SCAN_LIMIT", "10"))
    PATIENT_AI_SCAN_WINDOW_MINUTES = int(os.environ.get("PATIENT_AI_SCAN_WINDOW_MINUTES", "15"))
