"""Data-access functions over the sqlite3 database (see app/db.py). Each
function returns plain dicts (or lists of dicts) rather than ORM objects --
Jinja templates can use dot-notation on dicts just fine, and it keeps every
query explicit and easy to audit for a patient-safety tool."""
import json
import secrets
import string
from datetime import date, datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from app.db import get_db


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _row_to_dict(row):
    return dict(row) if row is not None else None


def new_public_id():
    alphabet = string.ascii_uppercase + string.digits
    alphabet = "".join(c for c in alphabet if c not in "0O1IL")
    suffix = "".join(secrets.choice(alphabet) for _ in range(6))
    return f"ASH-{suffix}"


def age_years(date_of_birth_str):
    if not date_of_birth_str:
        return None
    dob = date.fromisoformat(date_of_birth_str)
    today = date.today()
    years = today.year - dob.year
    if (today.month, today.day) < (dob.month, dob.day):
        years -= 1
    return years


# ---------------------------------------------------------------- owners --

# 'owner' = full database access (the clinical pharmacist / hospital
# controller account). 'staff' = limited account: can look up any patient
# and view their record, and add antibiotic entries (the safety-check
# workflow), but cannot edit allergies/conditions/pregnancy status, reset
# passwords, manage the antibiotic reference database, view the audit log,
# create new patient records, or create other accounts.
OWNER_ROLES = ("owner", "staff")


def create_owner(username, password, role="owner"):
    if role not in OWNER_ROLES:
        role = "owner"
    db = get_db()
    db.execute(
        "INSERT INTO owner_users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
        (username, generate_password_hash(password), role, _now()),
    )
    db.commit()


def is_full_owner(owner):
    return bool(owner) and owner.get("role", "owner") == "owner"


def get_owner_by_username(username):
    db = get_db()
    return _row_to_dict(db.execute(
        "SELECT * FROM owner_users WHERE username = ?", (username,)
    ).fetchone())


def get_owner_by_id(owner_id):
    db = get_db()
    return _row_to_dict(db.execute(
        "SELECT * FROM owner_users WHERE id = ?", (owner_id,)
    ).fetchone())


def check_owner_password(owner, password):
    return bool(owner) and check_password_hash(owner["password_hash"], password)


def list_owners():
    db = get_db()
    return [dict(r) for r in db.execute("SELECT * FROM owner_users ORDER BY created_at").fetchall()]


# --------------------------------------------------------------- patients --

def create_patient(gender="unspecified", full_name=None, date_of_birth=None, password=None):
    db = get_db()
    public_id = new_public_id()
    while get_patient_by_public_id(public_id):  # astronomically unlikely, but be safe
        public_id = new_public_id()

    pregnancy_status = "not_applicable" if gender == "male" else "unknown"
    now = _now()
    password_hash = generate_password_hash(password) if password else None

    cur = db.execute(
        """INSERT INTO patients
           (public_id, password_hash, full_name, gender, date_of_birth,
            pregnancy_status, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (public_id, password_hash, full_name, gender, date_of_birth,
         pregnancy_status, now, now),
    )
    db.commit()
    return get_patient_by_id(cur.lastrowid)


def get_patient_by_id(patient_id):
    db = get_db()
    row = _row_to_dict(db.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone())
    if row:
        row["age_years"] = age_years(row["date_of_birth"])
    return row


def get_patient_by_public_id(public_id):
    db = get_db()
    row = _row_to_dict(db.execute(
        "SELECT * FROM patients WHERE public_id = ?", (public_id.strip().upper(),)
    ).fetchone())
    if row:
        row["age_years"] = age_years(row["date_of_birth"])
    return row


def check_patient_password(patient, password):
    if not patient or not patient.get("password_hash"):
        return False
    return check_password_hash(patient["password_hash"], password)


def patient_has_password(patient):
    return bool(patient and patient.get("password_hash"))


def set_patient_password(patient_id, password):
    db = get_db()
    password_hash = generate_password_hash(password) if password else None
    db.execute(
        "UPDATE patients SET password_hash = ?, updated_at = ? WHERE id = ?",
        (password_hash, _now(), patient_id),
    )
    db.commit()


def update_pregnancy_status(patient_id, status):
    db = get_db()
    db.execute(
        "UPDATE patients SET pregnancy_status = ?, pregnancy_updated_at = ?, updated_at = ? WHERE id = ?",
        (status, _now(), _now(), patient_id),
    )
    db.commit()


def list_patients(search=None, limit=200):
    db = get_db()
    if search:
        like = f"%{search}%"
        rows = db.execute(
            """SELECT * FROM patients WHERE public_id LIKE ? OR full_name LIKE ?
               ORDER BY created_at DESC LIMIT ?""",
            (like, like, limit),
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM patients ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def count_patients():
    db = get_db()
    return db.execute("SELECT COUNT(*) AS c FROM patients").fetchone()["c"]


def find_patients_exact(query):
    """Exact match (case-insensitive, trimmed) on public_id OR full_name --
    NOT a partial/substring search like list_patients() above. This backs
    the staff-role patient lookup: staff should only be able to pull up a
    specific patient they already know the full name or ID of, not browse
    or fish through the whole patient list by typing a couple of letters
    (that's the controller/owner's privilege, via list_patients()). Empty
    query returns no results rather than everyone, deliberately -- staff
    landing on the dashboard with no search typed should see nobody's data
    by default. May return more than one row if two patients happen to
    share the exact same full name."""
    q = (query or "").strip()
    if not q:
        return []
    db = get_db()
    rows = db.execute(
        """SELECT * FROM patients
           WHERE lower(public_id) = lower(?) OR lower(trim(full_name)) = lower(?)
           ORDER BY created_at DESC""",
        (q, q),
    ).fetchall()
    return [dict(r) for r in rows]


# --------------------------------------------------------------- allergies --

def add_allergy(patient_id, allergen, drug_class=None, reaction=None, severity="unknown"):
    db = get_db()
    db.execute(
        """INSERT INTO patient_allergies (patient_id, allergen, drug_class, reaction, severity, recorded_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (patient_id, allergen, drug_class, reaction, severity, _now()),
    )
    db.commit()


def list_allergies(patient_id):
    db = get_db()
    rows = db.execute(
        "SELECT * FROM patient_allergies WHERE patient_id = ? ORDER BY recorded_at DESC", (patient_id,)
    ).fetchall()
    return [dict(r) for r in rows]


# -------------------------------------------------------------- conditions --

def add_condition(patient_id, condition_name, notes=None):
    db = get_db()
    db.execute(
        """INSERT INTO patient_conditions (patient_id, condition_name, notes, recorded_at)
           VALUES (?, ?, ?, ?)""",
        (patient_id, condition_name, notes, _now()),
    )
    db.commit()


def list_conditions(patient_id):
    db = get_db()
    rows = db.execute(
        "SELECT * FROM patient_conditions WHERE patient_id = ? ORDER BY recorded_at DESC", (patient_id,)
    ).fetchall()
    return [dict(r) for r in rows]


# ------------------------------------------------------- antibiotic reference --

def _antibiotic_row_to_dict(row):
    d = _row_to_dict(row)
    if d is not None:
        d["contraindicated_conditions"] = json.loads(d["contraindicated_conditions_json"] or "[]")
    return d


def add_antibiotic(generic_name, drug_class, brand_names=None, pregnancy_contraindicated=False,
                    pregnancy_notes=None, contraindicated_conditions=None, notes=None):
    db = get_db()
    db.execute(
        """INSERT INTO antibiotics
           (generic_name, brand_names, drug_class, pregnancy_contraindicated,
            pregnancy_notes, contraindicated_conditions_json, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (generic_name, brand_names, drug_class, int(bool(pregnancy_contraindicated)),
         pregnancy_notes, json.dumps(contraindicated_conditions or []), notes),
    )
    db.commit()


def update_antibiotic(item_id, generic_name, drug_class, brand_names=None,
                       pregnancy_contraindicated=False, pregnancy_notes=None,
                       contraindicated_conditions=None, notes=None):
    db = get_db()
    db.execute(
        """UPDATE antibiotics SET generic_name=?, brand_names=?, drug_class=?,
           pregnancy_contraindicated=?, pregnancy_notes=?, contraindicated_conditions_json=?, notes=?
           WHERE id=?""",
        (generic_name, brand_names, drug_class, int(bool(pregnancy_contraindicated)),
         pregnancy_notes, json.dumps(contraindicated_conditions or []), notes, item_id),
    )
    db.commit()


def delete_antibiotic(item_id):
    db = get_db()
    db.execute("DELETE FROM antibiotics WHERE id = ?", (item_id,))
    db.commit()


def get_antibiotic_by_id(item_id):
    db = get_db()
    return _antibiotic_row_to_dict(db.execute("SELECT * FROM antibiotics WHERE id = ?", (item_id,)).fetchone())


def get_antibiotic_by_name(name):
    db = get_db()
    return _antibiotic_row_to_dict(db.execute(
        "SELECT * FROM antibiotics WHERE lower(generic_name) = lower(?)", (name.strip(),)
    ).fetchone())


def list_antibiotics():
    db = get_db()
    rows = db.execute("SELECT * FROM antibiotics ORDER BY generic_name").fetchall()
    return [_antibiotic_row_to_dict(r) for r in rows]


def count_antibiotics():
    db = get_db()
    return db.execute("SELECT COUNT(*) AS c FROM antibiotics").fetchone()["c"]


# ------------------------------------------------------------- antibiotic records --

def _record_row_to_dict(row):
    d = _row_to_dict(row)
    if d is None:
        return None
    d["alerts"] = json.loads(d["alerts_json"] or "[]")
    if d.get("antibiotic_id"):
        antibiotic = get_antibiotic_by_id(d["antibiotic_id"])
        d["display_name"] = antibiotic["generic_name"] if antibiotic else (d["custom_name"] or "Unknown")
    else:
        d["display_name"] = d["custom_name"] or "Unknown"
    return d


def add_antibiotic_record(patient_id, antibiotic_id, custom_name, dose, duration,
                           prescribed_by, prescribed_date, notes, alerts, added_by):
    db = get_db()
    cur = db.execute(
        """INSERT INTO antibiotic_records
           (patient_id, antibiotic_id, custom_name, dose, duration, prescribed_by,
            prescribed_date, notes, alerts_json, added_by, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (patient_id, antibiotic_id, custom_name, dose, duration, prescribed_by,
         prescribed_date, notes, json.dumps(alerts or []), added_by, _now()),
    )
    db.commit()
    return get_antibiotic_record_by_id(cur.lastrowid)


def get_antibiotic_record_by_id(record_id):
    db = get_db()
    return _record_row_to_dict(db.execute(
        "SELECT * FROM antibiotic_records WHERE id = ?", (record_id,)
    ).fetchone())


def list_antibiotic_records(patient_id):
    db = get_db()
    rows = db.execute(
        "SELECT * FROM antibiotic_records WHERE patient_id = ? ORDER BY prescribed_date DESC, id DESC",
        (patient_id,),
    ).fetchall()
    return [_record_row_to_dict(r) for r in rows]


def find_recent_record(patient_id, antibiotic_id, cutoff_date_str, exclude_record_id=None):
    """Most recent prior record of this exact antibiotic on/after cutoff_date_str."""
    db = get_db()
    query = """SELECT * FROM antibiotic_records
               WHERE patient_id = ? AND antibiotic_id = ? AND prescribed_date >= ?"""
    params = [patient_id, antibiotic_id, cutoff_date_str]
    if exclude_record_id:
        query += " AND id != ?"
        params.append(exclude_record_id)
    query += " ORDER BY prescribed_date DESC LIMIT 1"
    return _record_row_to_dict(db.execute(query, params).fetchone())


def find_recent_record_by_class(patient_id, drug_class, cutoff_date_str, exclude_antibiotic_id=None):
    """Most recent prior record of a DIFFERENT antibiotic in the same drug
    class (e.g. two different penicillins, or a cephalosporin after a
    penicillin) on/after cutoff_date_str. This is what catches "same
    antibiotic GROUP within a month" -- find_recent_record() above only
    catches the exact same drug, so a patient given Amoxicillin then, three
    weeks later, Augmentin (both Penicillins) was previously not flagged at
    all since they're different antibiotic rows. Requires a JOIN against
    antibiotics since drug_class lives there, not on antibiotic_records."""
    db = get_db()
    query = """SELECT ar.* FROM antibiotic_records ar
               JOIN antibiotics a ON a.id = ar.antibiotic_id
               WHERE ar.patient_id = ? AND lower(a.drug_class) = lower(?)
                 AND ar.prescribed_date >= ?"""
    params = [patient_id, drug_class, cutoff_date_str]
    if exclude_antibiotic_id:
        query += " AND ar.antibiotic_id != ?"
        params.append(exclude_antibiotic_id)
    query += " ORDER BY ar.prescribed_date DESC LIMIT 1"
    return _record_row_to_dict(db.execute(query, params).fetchone())


def count_antibiotic_records():
    db = get_db()
    return db.execute("SELECT COUNT(*) AS c FROM antibiotic_records").fetchone()["c"]


def list_recent_antibiotic_records(limit=20):
    """Most recent antibiotic entries across ALL patients, newest first --
    backs the clinical-pharmacist/controller dashboard's activity feed so
    the owner can see what's being added hospital-wide without opening
    each patient's record individually."""
    db = get_db()
    rows = db.execute(
        """SELECT ar.*, p.public_id AS patient_public_id, p.full_name AS patient_full_name
           FROM antibiotic_records ar
           JOIN patients p ON p.id = ar.patient_id
           ORDER BY ar.created_at DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    return [_record_row_to_dict(r) for r in rows]


def list_recent_flagged_records(scan_limit=300, max_results=15):
    """Recent antibiotic entries whose safety check produced a danger or
    warning alert, newest first -- the 'what needs my attention' feed on
    the controller dashboard. Scans the most recent `scan_limit` entries
    hospital-wide (cheap at this scale, no extra table/index needed) and
    returns up to `max_results` flagged ones."""
    recent = list_recent_antibiotic_records(limit=scan_limit)
    flagged = [
        r for r in recent
        if any(a.get("level") in ("danger", "warning") for a in r.get("alerts", []))
    ]
    return flagged[:max_results]


# -------------------------------------------------------------------- audit --

def log_action(actor_type, actor_label, action, target=None, details=None):
    """Best-effort audit trail write. Never raise -- patient-safety features
    must keep working even if the audit log has a problem."""
    try:
        db = get_db()
        db.execute(
            """INSERT INTO audit_logs (actor_type, actor_label, action, target_patient_public_id, details, timestamp)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (actor_type, actor_label, action, target, details, _now()),
        )
        db.commit()
    except Exception:
        pass


def list_audit_logs(limit=500):
    db = get_db()
    rows = db.execute("SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]
