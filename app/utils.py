"""Session-based auth helpers, used instead of Flask-Login to avoid an
extra dependency. Flask's session cookie is itself signed with SECRET_KEY
(via itsdangerous, bundled with Flask), so this is a normal, safe approach
for a small app -- just without the extra abstraction layer.

Session shape after login: {"actor_type": "owner"|"patient", "actor_id": int}
"""
from functools import wraps

from flask import abort, g, session

from app import models
from app.roles import permissions_for


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
    """The current owner-side account's role key -- 'owner' (clinical
    pharmacist / controller, full access), one of the specific job-title
    roles defined in app/roles.py (resident, nurse, pharmacy_manager, ...),
    the legacy 'staff', or None if there's no owner-side session at all."""
    owner = current_owner()
    return owner.get("role", "owner") if owner else None


def current_owner_permissions():
    """Permission dict for the CURRENTLY LOGGED IN owner-side account (see
    app/roles.py for what each key means). Returns the most restrictive
    (view-nothing) permissions if there's no owner-side session at all, so
    a template or check can call this safely even when nobody is logged
    in."""
    owner = current_owner()
    if not owner:
        return {
            "browse_all_patients": False, "view_patient": False, "add_antibiotic": False,
            "add_restricted_antibiotic": False, "quality_report": False, "pharmacy_report": False,
            "culture_analysis": False,
        }
    return permissions_for(owner.get("role", "owner"), is_owner=models.is_full_owner(owner))


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


def culture_analysis_required(view):
    """Only the full owner/controller, Infection Control, and Consultant
    roles can reach the hospital-wide culture analysis page (see
    app/roles.py's culture_analysis permission) -- deliberately narrower
    than browse_all_patients: Head Nurse, Quality Control Manager and
    Pharmacy Manager can browse the patient list but not this page."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_owner() or not current_owner_permissions()["culture_analysis"]:
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def antibiotic_add_required(view):
    """Any owner-side account whose role is allowed to add an antibiotic
    entry AT ALL (Resident/Specialist/Pharmacist/Senior Specialist/
    Consultant/legacy staff/full owner). Whether this specific antibiotic
    is one they're allowed to add (i.e. it isn't marked Restricted, for the
    roles that can't touch restricted drugs) is a separate check made
    inside the route itself, since that depends on which antibiotic was
    actually requested. Nurse, Infection Control, Head Nurse, Quality
    Control Manager and Pharmacy Manager are all blocked here."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_owner() or not current_owner_permissions()["add_antibiotic"]:
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def hospital_browse_required(view):
    """Any owner-side account whose role can browse the FULL hospital-wide
    patient list (Infection Control, Head Nurse, Quality Control Manager,
    Pharmacy Manager, or the full owner/controller). The search-only roles
    (Resident, Specialist, Pharmacist, Senior Specialist, Consultant,
    Nurse, legacy staff) are blocked here -- they can still view an
    individual patient once they've found one via exact-match search,
    that's checked separately."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_owner() or not current_owner_permissions()["browse_all_patients"]:
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def quality_report_required(view):
    """Only the Quality Control Manager (or the full owner/controller) can
    reach the quality/safety analysis PDF report screen."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_owner() or not current_owner_permissions()["quality_report"]:
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def pharmacy_report_required(view):
    """Only the Pharmacy Manager (or the full owner/controller) can reach
    the monthly antibiotic-usage PDF report screen."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_owner() or not current_owner_permissions()["pharmacy_report"]:
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
