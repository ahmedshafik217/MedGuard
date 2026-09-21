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
