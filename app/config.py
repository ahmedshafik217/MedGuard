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

    # Login rate limiting (see app/rate_limit.py): after this many FAILED
    # attempts against the same username/patient ID, or this many failed
    # attempts from the same source IP (looser, since a hospital front
    # desk/kiosk may be shared by many legitimate patients), further
    # attempts are blocked until the window passes. Only failures count --
    # a correct login never contributes to a lockout.
    LOGIN_ATTEMPT_LIMIT = int(os.environ.get("LOGIN_ATTEMPT_LIMIT", "5"))
    LOGIN_ATTEMPT_WINDOW_MINUTES = int(os.environ.get("LOGIN_ATTEMPT_WINDOW_MINUTES", "15"))
    LOGIN_IP_ATTEMPT_LIMIT = int(os.environ.get("LOGIN_IP_ATTEMPT_LIMIT", "20"))

    # First-run owner account (used only by seed.py).
    OWNER_USERNAME = os.environ.get("OWNER_USERNAME", "admin")
    OWNER_PASSWORD = os.environ.get("OWNER_PASSWORD", "change-this-password")

    LANGUAGES = ["en", "ar"]
    DEFAULT_LANGUAGE = "ar"
