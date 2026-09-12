"""Thin sqlite3 data layer. We use plain sqlite3 (Python standard library)
instead of an ORM: it keeps the app dependency-light (only Flask itself is
required), which matters both for easy setup and for auditability of a
patient-safety tool -- every query is visible, explicit SQL."""
import sqlite3
from pathlib import Path

from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS owner_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'owner',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS patients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT UNIQUE NOT NULL,
    password_hash TEXT,
    full_name TEXT,
    phone_number TEXT,
    gender TEXT NOT NULL DEFAULT 'unspecified',
    date_of_birth TEXT,
    pregnancy_status TEXT NOT NULL DEFAULT 'unknown',
    pregnancy_updated_at TEXT,
    pregnancy_start_date TEXT,
    expected_delivery_date TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS patient_allergies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    allergen TEXT NOT NULL,
    drug_class TEXT,
    reaction TEXT,
    severity TEXT NOT NULL DEFAULT 'unknown',
    recorded_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS patient_conditions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    condition_name TEXT NOT NULL,
    notes TEXT,
    recorded_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS patient_medications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    medication_name TEXT NOT NULL,
    notes TEXT,
    recorded_at TEXT NOT NULL
);

-- Reference table of known dangerous combinations between an antibiotic
-- (matched either by its exact generic name, or by its whole drug class --
-- either/both may be set) and some OTHER (non-antibiotic) medication the
-- patient may already be taking. Owner-managed from Owner Dashboard ->
-- Drug Interactions, same pattern as the antibiotics reference table.
CREATE TABLE IF NOT EXISTS drug_interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    antibiotic_name TEXT,
    antibiotic_class TEXT,
    interacting_drug TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'warning',
    category_label TEXT,
    mechanism TEXT,
    management TEXT,
    notes TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS antibiotics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    generic_name TEXT UNIQUE NOT NULL,
    brand_names TEXT,
    drug_class TEXT NOT NULL,
    pregnancy_contraindicated INTEGER NOT NULL DEFAULT 0,
    pregnancy_notes TEXT,
    contraindicated_conditions_json TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS antibiotic_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    antibiotic_id INTEGER REFERENCES antibiotics(id),
    custom_name TEXT,
    dose TEXT,
    duration TEXT,
    -- Structured dose/duration (added so a dose entered in Arabic still
    -- displays correctly on an English PDF and vice versa -- see
    -- app/dose_format.py. dose/duration above are kept only as a fallback
    -- for records created before this existed; new records go entirely
    -- through the columns below instead of free text.
    dose_amount TEXT,
    dose_unit TEXT,
    dose_unit_other TEXT,
    frequency TEXT,
    frequency_other TEXT,
    duration_amount TEXT,
    duration_unit TEXT,
    duration_unit_other TEXT,
    prescribed_by TEXT,
    prescribed_date TEXT NOT NULL,
    notes TEXT,
    alerts_json TEXT,
    added_by TEXT NOT NULL DEFAULT 'patient',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_type TEXT NOT NULL,
    actor_label TEXT NOT NULL,
    action TEXT NOT NULL,
    target_patient_public_id TEXT,
    details TEXT,
    timestamp TEXT NOT NULL
);

-- Backs login rate limiting (app/rate_limit.py): one row per login attempt
-- (owner-login form, patient-login form, or the QR magic link), so brute
-- force / credential-guessing can be detected and slowed down per-account
-- and per-source-IP. A brand new table needs no ALTER-based migration --
-- CREATE TABLE IF NOT EXISTS already handles an already-running install.
CREATE TABLE IF NOT EXISTS login_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scope TEXT NOT NULL,          -- 'owner' or 'patient'
    identifier TEXT NOT NULL,     -- username (lowercased) or patient public_id (uppercased)
    ip_address TEXT NOT NULL,
    success INTEGER NOT NULL DEFAULT 0,
    attempted_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_login_attempts_identifier
    ON login_attempts(scope, identifier, attempted_at);
CREATE INDEX IF NOT EXISTS idx_login_attempts_ip
    ON login_attempts(ip_address, attempted_at);
"""


def get_db():
    if "db" not in g:
        db_path = current_app.config["DATABASE_PATH"]
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        g.db = sqlite3.connect(db_path)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def _migrate(db):
    """Small, additive schema migrations for databases created before a
    column existed -- so an already-running install with real patient data
    doesn't need to be recreated when the app gains a new field. Each check
    is a no-op if the column is already present."""
    cols = {row["name"] for row in db.execute("PRAGMA table_info(owner_users)")}
    if "role" not in cols:
        # 'owner' = full access (the account(s) that existed before roles
        # existed keep full access, which is what they had before).
        db.execute("ALTER TABLE owner_users ADD COLUMN role TEXT NOT NULL DEFAULT 'owner'")
        db.commit()

    record_cols = {row["name"] for row in db.execute("PRAGMA table_info(antibiotic_records)")}
    new_record_cols = [
        "dose_amount", "dose_unit", "dose_unit_other",
        "frequency", "frequency_other",
        "duration_amount", "duration_unit", "duration_unit_other",
    ]
    for col in new_record_cols:
        if col not in record_cols:
            db.execute(f"ALTER TABLE antibiotic_records ADD COLUMN {col} TEXT")
    db.commit()

    patient_cols = {row["name"] for row in db.execute("PRAGMA table_info(patients)")}
    if "phone_number" not in patient_cols:
        # Added for self-service "forgot password" recovery (phone number +
        # date of birth check) -- optional so existing patient records
        # created before this feature keep working unchanged.
        db.execute("ALTER TABLE patients ADD COLUMN phone_number TEXT")
        db.commit()

    patient_cols = {row["name"] for row in db.execute("PRAGMA table_info(patients)")}
    for col in ("pregnancy_start_date", "expected_delivery_date"):
        if col not in patient_cols:
            db.execute(f"ALTER TABLE patients ADD COLUMN {col} TEXT")
    db.commit()


def init_db(app):
    with app.app_context():
        db = get_db()
        db.executescript(SCHEMA)
        db.commit()
        _migrate(db)
    app.teardown_appcontext(close_db)
