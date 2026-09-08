"""Session-based auth helpers, used instead of Flask-Login to avoid an
extra dependency. Flask's session cookie is itself signed with SECRET_KEY
(via itsdangerous, bundled with Flask), so this is a normal, safe approach
for a small app -- just without the extra abstraction layer.

Session shape after login: {"actor_type": "owner"|"patient", "actor_id": int}
"""
from functools import wraps

from flask import abort, g, session

from app import models


def _clear_session_keep_lang():
    """session.clear() but preserve the visitor's chosen UI language --
    otherwise every login silently reverts the page to the default
    language, which is confusing and has nothing to do with security."""
    lang = session.get("lang")
    session.clear()
    if lang:
        session["lang"] = lang


def login_owner(owner):
    _clear_session_keep_lang()
    session["actor_type"] = "owner"
    session["actor_id"] = owner["id"]
    session.permanent = True


def login_patient(patient):
    _clear_session_keep_lang()
    session["actor_type"] = "patient"
    session["actor_id"] = patient["id"]
    session.permanent = True


def logout():
    _clear_session_keep_lang()


def current_owner():
    if session.get("actor_type") != "owner":
        return None
    if "_owner" not in g:
        g._owner = models.get_owner_by_id(session["actor_id"])
    return g._owner


def current_patient():
    if session.get("actor_type") != "patient":
        return None
    if "_patient" not in g:
        g._patient = models.get_patient_by_id(session["actor_id"])
    return g._patient


def current_actor_label():
    owner = current_owner()
    if owner:
        return owner["username"]
    patient = current_patient()
    if patient:
        return patient["public_id"]
    return "anonymous"


def current_owner_role():
    """'owner' (clinical pharmacist / controller, full access), 'staff'
    (limited account), or None if there's no owner-side session at all."""
    owner = current_owner()
    return owner.get("role", "owner") if owner else None


def owner_required(view):
    """Any authenticated owner_users account -- either role. Use this for
    routes both the full owner/controller and limited staff should reach
    (dashboard, viewing a patient, adding an antibiotic, PDF export)."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_owner():
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def full_owner_required(view):
    """Only the full owner/controller role (not limited staff). Use this for
    anything that edits allergies/conditions/pregnancy status, resets a
    password, manages the antibiotic reference database, creates patient
    records, views the audit log, or creates other accounts."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not models.is_full_owner(current_owner()):
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def patient_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_patient():
            abort(403)
        return view(*args, **kwargs)
    return wrapped
