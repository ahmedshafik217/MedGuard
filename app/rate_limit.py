"""Login rate limiting, backed by the login_attempts sqlite table instead of
an in-memory counter or an external dependency (Flask-Limiter/Redis) --
consistent with the rest of the app's "few moving parts" approach, and it
means limits survive a server restart and work correctly even if the app is
ever run with multiple worker processes (an in-memory dict would not).

Two independent limits are checked, both counting only FAILED attempts
within a rolling time window (a correct login never itself causes a
lockout):

  1. Per identifier (a username, or a patient's public ID) -- stops
     someone from password-guessing a single account no matter how many
     different source IPs they spread the attempts across.
  2. Per source IP -- stops someone from spraying guesses across many
     different accounts/IDs from one machine (e.g. enumerating patient
     IDs via the QR magic link). This limit is deliberately looser than
     the per-identifier one, since a shared front-desk/kiosk IP will
     legitimately see many different patients logging in.

Caveat worth knowing before relying on this in production: IP-based
limiting only sees request.remote_addr, so if the app is ever put behind a
reverse proxy, that proxy's own IP must be excluded / X-Forwarded-For must
be trusted correctly (e.g. via werkzeug's ProxyFix) or every request will
appear to come from the same address, making the per-IP limit useless (the
per-identifier limit is unaffected either way).
"""
from datetime import datetime, timedelta, timezone

from flask import current_app

from app.db import get_db


def _now():
    return datetime.now(timezone.utc)


def _iso(dt):
    return dt.isoformat(timespec="seconds")


def record_attempt(scope, identifier, ip_address, success):
    """Log one login attempt. Call this after checking credentials, with
    success=True/False -- both outcomes are recorded (successes are kept
    for a possible future "recent logins" view, but never count toward a
    lockout)."""
    db = get_db()
    db.execute(
        "INSERT INTO login_attempts (scope, identifier, ip_address, success, attempted_at) VALUES (?, ?, ?, ?, ?)",
        (scope, identifier, ip_address or "unknown", int(bool(success)), _iso(_now())),
    )
    db.commit()
    # Opportunistic cleanup so this table never grows unbounded on a
    # long-running install -- cheap, index-backed delete of anything well
    # outside any window this module would ever check.
    cutoff = _iso(_now() - timedelta(days=1))
    db.execute("DELETE FROM login_attempts WHERE attempted_at < ?", (cutoff,))
    db.commit()


def _recent_failure_count(where_clause, params, window_minutes):
    db = get_db()
    cutoff = _iso(_now() - timedelta(minutes=window_minutes))
    row = db.execute(
        f"SELECT COUNT(*) AS c FROM login_attempts WHERE success = 0 AND attempted_at >= ? AND {where_clause}",
        (cutoff, *params),
    ).fetchone()
    return row["c"]


def check_registration_rate(ip_address):
    """Returns None if a new self-service patient registration from this IP
    may proceed, or an int number of minutes to report to the visitor if
    too many registrations have already come from this IP recently.

    Unlike check_lockout() above, this isn't about failed login guesses --
    a registration basically always "succeeds" (there's no password to get
    wrong), so counting only failures would never catch anything. Instead
    every registration attempt from an IP counts against this limit,
    success or not, which is what actually stops someone from scripting
    hundreds of throwaway patient records in a row. A shared front-desk/
    kiosk IP registering a handful of real patients in a row is expected
    and stays well under the default limit."""
    cfg = current_app.config
    window = cfg.get("REGISTRATION_WINDOW_MINUTES", 60)
    limit = cfg.get("REGISTRATION_IP_LIMIT", 8)

    db = get_db()
    cutoff = _iso(_now() - timedelta(minutes=window))
    row = db.execute(
        "SELECT COUNT(*) AS c FROM login_attempts "
        "WHERE scope = 'patient_register' AND ip_address = ? AND attempted_at >= ?",
        (ip_address or "unknown", cutoff),
    ).fetchone()
    if row["c"] >= limit:
        return window
    return None


def record_registration(ip_address):
    """Log one self-service patient registration for check_registration_rate()
    above. Reuses the same login_attempts table/cleanup as record_attempt()
    rather than a separate table -- it's the same shape of data (an IP, a
    timestamp, a scope to filter by) and keeps the rate-limiting logic in
    one place. 'success' is always recorded True here since there's no
    pass/fail outcome to a registration, only a count."""
    db = get_db()
    db.execute(
        "INSERT INTO login_attempts (scope, identifier, ip_address, success, attempted_at) VALUES (?, ?, ?, ?, ?)",
        ("patient_register", ip_address or "unknown", ip_address or "unknown", 1, _iso(_now())),
    )
    db.commit()


def check_email_code_request_rate(email, ip_address):
    """Returns None if requesting a new email sign-in code (see
    app/notify.py's send_patient_login_code) may proceed, or an int number
    of minutes to wait if too many codes have already been requested
    recently.

    Same "count every attempt, not just failures" reasoning as
    check_registration_rate() above -- requesting a code basically always
    "succeeds" (an email either exists or it doesn't; either way a request
    was made), so this has to cap the RATE of requests, not a failure
    count, or someone could otherwise flood a patient's inbox with codes,
    or hammer the SMTP account's own sending limits. Checked both per-email
    (stops one inbox being spammed) and per-IP (looser, stops one machine
    spamming many different emails) -- same two-limit shape as
    check_lockout(), just against a request count instead of failures."""
    cfg = current_app.config
    window = cfg.get("EMAIL_CODE_REQUEST_WINDOW_MINUTES", 15)
    limit = cfg.get("EMAIL_CODE_REQUEST_LIMIT", 5)
    db = get_db()
    cutoff = _iso(_now() - timedelta(minutes=window))

    email_count = db.execute(
        "SELECT COUNT(*) AS c FROM login_attempts "
        "WHERE scope = 'patient_email_code_request' AND identifier = ? AND attempted_at >= ?",
        ((email or "").strip().lower(), cutoff),
    ).fetchone()["c"]
    if email_count >= limit:
        return window

    ip_count = db.execute(
        "SELECT COUNT(*) AS c FROM login_attempts "
        "WHERE scope = 'patient_email_code_request' AND ip_address = ? AND attempted_at >= ?",
        (ip_address or "unknown", cutoff),
    ).fetchone()["c"]
    if ip_count >= limit * 4:  # looser than the per-email limit, same ratio idea as check_lockout
        return window

    return None


def record_email_code_request(email, ip_address):
    """Log one email-sign-in-code request for check_email_code_request_rate()
    above. Reuses login_attempts the same way record_registration() does --
    'success' is always True here, this table row only exists to be
    counted, not to record a pass/fail outcome."""
    db = get_db()
    db.execute(
        "INSERT INTO login_attempts (scope, identifier, ip_address, success, attempted_at) VALUES (?, ?, ?, ?, ?)",
        ("patient_email_code_request", (email or "").strip().lower(), ip_address or "unknown", 1, _iso(_now())),
    )
    db.commit()


def _normalize_phone_for_rate_limit(raw):
    """Digits only, last 9 -- a local duplicate of app/models.py's own
    _normalize_phone rather than importing it, same as this module already
    keeps its own private _now()/_iso() instead of importing app/models.py's.
    Only needs to be consistent with itself (same input -> same identifier
    every time), not cryptographically exact."""
    digits = "".join(ch for ch in (raw or "") if ch.isdigit())
    return digits[-9:] if len(digits) >= 9 else digits


def check_sms_code_request_rate(phone_number, ip_address):
    """Phone equivalent of check_email_code_request_rate() above -- same
    reasoning (requesting a code basically always "succeeds", so this caps
    the RATE of requests, not a failure count) and same two-limit shape
    (per-phone, looser per-IP)."""
    cfg = current_app.config
    window = cfg.get("SMS_CODE_REQUEST_WINDOW_MINUTES", 15)
    limit = cfg.get("SMS_CODE_REQUEST_LIMIT", 5)
    db = get_db()
    cutoff = _iso(_now() - timedelta(minutes=window))
    identifier = _normalize_phone_for_rate_limit(phone_number)

    phone_count = db.execute(
        "SELECT COUNT(*) AS c FROM login_attempts "
        "WHERE scope = 'patient_sms_code_request' AND identifier = ? AND attempted_at >= ?",
        (identifier, cutoff),
    ).fetchone()["c"]
    if phone_count >= limit:
        return window

    ip_count = db.execute(
        "SELECT COUNT(*) AS c FROM login_attempts "
        "WHERE scope = 'patient_sms_code_request' AND ip_address = ? AND attempted_at >= ?",
        (ip_address or "unknown", cutoff),
    ).fetchone()["c"]
    if ip_count >= limit * 4:
        return window

    return None


def record_sms_code_request(phone_number, ip_address):
    """Log one SMS-sign-in-code request for check_sms_code_request_rate()
    above -- same pattern as record_email_code_request()."""
    db = get_db()
    db.execute(
        "INSERT INTO login_attempts (scope, identifier, ip_address, success, attempted_at) VALUES (?, ?, ?, ?, ?)",
        ("patient_sms_code_request", _normalize_phone_for_rate_limit(phone_number), ip_address or "unknown", 1,
         _iso(_now())),
    )
    db.commit()


def check_lockout(scope, identifier, ip_address):
    """Returns None if this login attempt may proceed, or an int number of
    minutes to report to the user if either limit is currently exceeded
    (a fixed "wait about this long" figure -- the configured window --
    rather than an exact countdown to the oldest attempt aging out, which
    keeps this simple and is close enough for a lockout message)."""
    cfg = current_app.config
    window = cfg.get("LOGIN_ATTEMPT_WINDOW_MINUTES", 15)
    identifier_limit = cfg.get("LOGIN_ATTEMPT_LIMIT", 5)
    ip_limit = cfg.get("LOGIN_IP_ATTEMPT_LIMIT", 20)

    identifier_failures = _recent_failure_count(
        "scope = ? AND identifier = ?", (scope, identifier), window
    )
    if identifier_failures >= identifier_limit:
        return window

    ip_failures = _recent_failure_count(
        "ip_address = ?", (ip_address or "unknown",), window
    )
    if ip_failures >= ip_limit:
        return window

    return None
