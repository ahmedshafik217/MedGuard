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
