"""Minimal CSRF protection, in place of Flask-WTF's CSRFProtect (kept out to
avoid an extra dependency). One random token per browser session, checked on
every state-changing (POST) request; templates render it via csrf_token()."""
import secrets

from flask import abort, request, session


def get_csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(32)
    return session["csrf_token"]


def validate_csrf_or_abort():
    if request.method != "POST":
        return
    sent = request.form.get("csrf_token", "")
    expected = session.get("csrf_token", "")
    if not expected or not secrets.compare_digest(sent, expected):
        abort(400, description="Invalid or missing CSRF token. Please reload the page and try again.")


def init_csrf(app):
    app.before_request(validate_csrf_or_abort)
    app.jinja_env.globals["csrf_token"] = get_csrf_token
