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
    email TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS patients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT UNIQUE NOT NULL,
    password_hash TEXT,
    full_name TEXT,
    phone_number TEXT,
    email TEXT,
    gender TEXT NOT NULL DEFAULT 'unspecified',
    date_of_birth TEXT,
    pregnancy_status TEXT NOT NULL DEFAULT 'unknown',
    pregnancy_updated_at TEXT,
    pregnancy_start_date TEXT,
    expected_delivery_date TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- NOTE: no "CREATE ... INDEX ON patients(email)" here even though the
-- column is declared above -- on an already-running install (most real
-- deployments), this script runs against a patients table that predates
-- the email column, and creating an index on a column that doesn't exist
-- yet would fail this whole executescript() before _migrate() below ever
-- gets a chance to ADD COLUMN it in. The unique index is created in
-- _migrate() instead, strictly after the column is guaranteed to exist.

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
    notes TEXT,
    -- 1 = only a Senior Specialist/Consultant (or the Admin/Controller)
    -- may add this antibiotic to a patient's record; Residents/
    -- Specialists/Pharmacists are blocked from it (see app/roles.py).
    restricted INTEGER NOT NULL DEFAULT 0
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
    -- Optional: when the patient's symptoms actually started (as opposed to
    -- prescribed_date, when the antibiotic was started) -- compared against
    -- patient_hospitalizations above to label this entry as likely
    -- Hospital-Acquired vs Community-Acquired. Purely informational (see
    -- app/records.py's classify_infection_origin()); never affects the
    -- safety-check engine.
    symptom_onset_date TEXT,
    notes TEXT,
    alerts_json TEXT,
    added_by TEXT NOT NULL DEFAULT 'patient',
    -- 'manual' (typed into the form, the default) or 'photo_ai' (extracted
    -- from a prescription photo -- see app/prescription_scan.py). The
    -- source photo itself is kept in source_photo for traceability (a
    -- pharmacist can always go back and check what the AI actually read).
    source TEXT NOT NULL DEFAULT 'manual',
    source_photo BLOB,
    created_at TEXT NOT NULL
);

-- Culture & sensitivity lab results: what organism was found in a patient
-- specimen, and which antibiotics it tested Sensitive/Intermediate/
-- Resistant to. Brand new tables -- no ALTER-based migration needed (see
-- the login_attempts comment above for why).
CREATE TABLE IF NOT EXISTS patient_cultures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    specimen_type TEXT NOT NULL,
    specimen_type_other TEXT,
    collection_date TEXT NOT NULL,
    organism TEXT NOT NULL,
    lab_name TEXT,
    notes TEXT,
    recorded_by TEXT NOT NULL DEFAULT 'owner',
    created_at TEXT NOT NULL
);

-- One row per antibiotic actually tested against a given culture.
-- antibiotic_id is filled in when the typed name matches this hospital's
-- reference list (kept NULL otherwise, same fallback as antibiotic_records.
-- custom_name) -- antibiotic_name is always kept either way so the result
-- always displays correctly even for a drug not on the reference list.
CREATE TABLE IF NOT EXISTS culture_sensitivities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    culture_id INTEGER NOT NULL REFERENCES patient_cultures(id) ON DELETE CASCADE,
    antibiotic_id INTEGER REFERENCES antibiotics(id),
    antibiotic_name TEXT NOT NULL,
    result TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_patient_cultures_patient
    ON patient_cultures(patient_id, collection_date);
CREATE INDEX IF NOT EXISTS idx_culture_sensitivities_culture
    ON culture_sensitivities(culture_id);
CREATE INDEX IF NOT EXISTS idx_culture_sensitivities_antibiotic
    ON culture_sensitivities(antibiotic_id);

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

-- One-time sign-in codes emailed to a patient (see app/mailer.py,
-- app/notify.py, and auth.patient_login_email / auth.patient_login_email_verify
-- below) -- an easier alternative to remembering an ASH-XXXXXX patient ID,
-- for a patient who'd rather sign in with their email. code_hash (never the
-- plain code) is checked the same way a password is (werkzeug's
-- generate_password_hash/check_password_hash). Only the newest, unconsumed,
-- unexpired row for a given patient is ever valid (see
-- models.verify_patient_login_code) -- requesting a fresh code makes any
-- earlier one moot without needing to explicitly invalidate it.
CREATE TABLE IF NOT EXISTS patient_login_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    code_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    consumed INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_patient_login_codes_patient
    ON patient_login_codes(patient_id, created_at);

-- Recent inpatient hospital stays -- lets the app work out whether an
-- infection is likely Hospital-Acquired (HAI) vs Community-Acquired (CAI)
-- by comparing a "symptom onset date" (see antibiotic_records.symptom_onset_date
-- below) against these admission/discharge dates -- see
-- app/records.py's classify_infection_origin(). discharge_date is nullable:
-- a still-ongoing admission has no discharge date yet. Brand new table --
-- no ALTER-based migration needed (see the login_attempts comment above
-- for why).
CREATE TABLE IF NOT EXISTS patient_hospitalizations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    admission_date TEXT NOT NULL,
    discharge_date TEXT,
    reason TEXT,
    notes TEXT,
    recorded_by TEXT NOT NULL DEFAULT 'patient',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_patient_hospitalizations_patient
    ON patient_hospitalizations(patient_id, admission_date);
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

    record_cols = {row["name"] for row in db.execute("PRAGMA table_info(antibiotic_records)")}
    if "source" not in record_cols:
        # Existing records were all entered by hand -- 'manual' is the
        # correct history for every row that predates this feature.
        db.execute("ALTER TABLE antibiotic_records ADD COLUMN source TEXT NOT NULL DEFAULT 'manual'")
    if "source_photo" not in record_cols:
        db.execute("ALTER TABLE antibiotic_records ADD COLUMN source_photo BLOB")
    db.commit()

    record_cols = {row["name"] for row in db.execute("PRAGMA table_info(antibiotic_records)")}
    if "symptom_onset_date" not in record_cols:
        # NULL for every record that predates this feature -- the HAI/CAI
        # label simply doesn't show for those (see
        # app/records.py's classify_infection_origin(), which treats a
        # missing onset date as "not enough information" rather than
        # guessing).
        db.execute("ALTER TABLE antibiotic_records ADD COLUMN symptom_onset_date TEXT")
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

    antibiotic_cols = {row["name"] for row in db.execute("PRAGMA table_info(antibiotics)")}
    if "restricted" not in antibiotic_cols:
        # Existing antibiotics default to NOT restricted (0) -- nobody's
        # prescribing ability silently narrows the moment this update
        # ships; the owner/controller has to deliberately tick "Restricted"
        # on the drugs that need it.
        db.execute("ALTER TABLE antibiotics ADD COLUMN restricted INTEGER NOT NULL DEFAULT 0")
        db.commit()

    # Optional email address -- lets a patient sign in with a one-time
    # emailed code instead of remembering their ASH-XXXXXX ID (see
    # app/mailer.py, app/notify.py), and backs the "new antibiotic added"
    # notification email. The ADD COLUMN has to happen before the unique
    # index below can be created on an already-running install.
    patient_cols = {row["name"] for row in db.execute("PRAGMA table_info(patients)")}
    if "email" not in patient_cols:
        db.execute("ALTER TABLE patients ADD COLUMN email TEXT")
        db.commit()
    # One email can only ever resolve to one patient -- see the comment in
    # SCHEMA above for why this is safe to add even with existing NULLs.
    db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_patients_email ON patients(email)")
    db.commit()

    # Optional email for an owner-side account -- currently only used to
    # send the "danger"-level safety-alert notification (see
    # app/records.py) to the full owner/controller. Not unique: nothing
    # looks an owner account up BY email the way patient sign-in does.
    owner_cols = {row["name"] for row in db.execute("PRAGMA table_info(owner_users)")}
    if "email" not in owner_cols:
        db.execute("ALTER TABLE owner_users ADD COLUMN email TEXT")
        db.commit()


def init_db(app):
    with app.app_context():
        db = get_db()
        db.executescript(SCHEMA)
        db.commit()
        _migrate(db)
    app.teardown_appcontext(close_db)
