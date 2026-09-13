"""Central definition of every owner-side account role: which role keys
exist, what each is labeled as (Owner Dashboard -> Site Settings' dropdown
and account badges), and what each one is allowed to do.

Why this file exists: with 11 different job titles now able to log into
the owner/staff side of the app, scattering `if role == "..."` checks
across routes and templates would make it very easy for one of them to
drift out of sync (e.g. a new route that forgets to block "Nurse"). Every
permission check in this app instead reads from TIER_PERMISSIONS below, so
a role's abilities are defined in exactly ONE place.

'owner' (the clinical pharmacist / hospital controller / admin account) is
intentionally NOT in ROLE_TIER below -- it always has full access to
everything, checked separately via models.is_full_owner() /
app.utils.full_owner_required, and permissions_for(is_owner=True) always
returns every permission True regardless of tier.

'staff' is the ORIGINAL limited role that existed before this file did.
It is kept mapped to a tier (so any account created before this change
keeps working exactly as it did) but is deliberately left out of
CREATABLE_ROLES -- new accounts pick one of the specific job titles below
instead of the old generic "staff" label.
"""

# A tier is a bundle of yes/no permissions shared by one or more role
# keys. Putting permissions on the TIER (not duplicated per role) is what
# makes "Residents, Specialists and Pharmacists all behave the same"
# actually guaranteed, rather than something that has to be remembered.
TIER_PERMISSIONS = {
    # Residents / Specialists / Pharmacists: must look a patient up by
    # their exact name or ID (no browsing the whole hospital list), can
    # view that patient's record, and can add antibiotic entries -- but
    # NOT ones flagged "Restricted" in the Antibiotic Reference database.
    "prescriber_basic": {
        "browse_all_patients": False,
        "view_patient": True,
        "add_antibiotic": True,
        "add_restricted_antibiotic": False,
        "quality_report": False,
        "pharmacy_report": False,
    },
    # Senior Specialists / Consultants: same lookup style as above, but
    # may add ANY antibiotic, including ones marked Restricted.
    "prescriber_full": {
        "browse_all_patients": False,
        "view_patient": True,
        "add_antibiotic": True,
        "add_restricted_antibiotic": True,
        "quality_report": False,
        "pharmacy_report": False,
    },
    # Nurse: same exact-name/ID lookup, but view-only -- cannot add or
    # remove anything at all.
    "read_only_search": {
        "browse_all_patients": False,
        "view_patient": True,
        "add_antibiotic": False,
        "add_restricted_antibiotic": False,
        "quality_report": False,
        "pharmacy_report": False,
    },
    # Infection Control Specialist / Head Nurse: can browse the FULL
    # hospital-wide patient list (no need to already know a name/ID), but
    # view-only -- cannot add or remove anything.
    "hospital_view_all": {
        "browse_all_patients": True,
        "view_patient": True,
        "add_antibiotic": False,
        "add_restricted_antibiotic": False,
        "quality_report": False,
        "pharmacy_report": False,
    },
    # Quality Control Manager: same hospital-wide browse/view access as
    # above, PLUS the analysis PDF report (repeated antibiotics,
    # allergies, contraindications, interactions, etc. across all
    # patients).
    "quality_reports": {
        "browse_all_patients": True,
        "view_patient": True,
        "add_antibiotic": False,
        "add_restricted_antibiotic": False,
        "quality_report": True,
        "pharmacy_report": False,
    },
    # Pharmacy Manager: same hospital-wide browse/view access, PLUS the
    # monthly antibiotic-usage-count PDF report.
    "pharmacy_reports": {
        "browse_all_patients": True,
        "view_patient": True,
        "add_antibiotic": False,
        "add_restricted_antibiotic": False,
        "quality_report": False,
        "pharmacy_report": True,
    },
}

# role key -> which tier it uses. 'owner' is deliberately absent -- it's
# handled as its own always-full-access case (see module docstring).
ROLE_TIER = {
    "staff": "prescriber_full",  # legacy role, kept working exactly as before
    "resident": "prescriber_basic",
    "specialist": "prescriber_basic",
    "pharmacist": "prescriber_basic",
    "senior_specialist": "prescriber_full",
    "consultant": "prescriber_full",
    "nurse": "read_only_search",
    "infection_control": "hospital_view_all",
    "head_nurse": "hospital_view_all",
    "quality_control_manager": "quality_reports",
    "pharmacy_manager": "pharmacy_reports",
}

# Role keys offered when CREATING a new account from Owner Dashboard ->
# Site Settings, in the order they should appear in the dropdown. 'staff'
# is excluded on purpose (see module docstring) -- old accounts with that
# role keep working, it's just not offered for new ones any more.
CREATABLE_ROLES = [
    "owner",
    "resident",
    "specialist",
    "senior_specialist",
    "consultant",
    "pharmacist",
    "nurse",
    "head_nurse",
    "infection_control",
    "quality_control_manager",
    "pharmacy_manager",
]

# Every role key the owner_users.role column may legally hold: the
# creatable ones, plus 'staff' for backward compatibility with accounts
# created before this file existed.
ALL_ROLES = CREATABLE_ROLES + ["staff"]

# The safest possible fallback for a role value this module doesn't
# recognize (a blank/corrupted column, a hand-edited form post, ...): the
# most restrictive tier that still lets someone log in and look something
# up, so a typo can never accidentally grant MORE access than intended.
DEFAULT_SAFE_ROLE = "nurse"


def role_tier(role):
    """Tier name for a non-owner role key. Callers should check
    models.is_full_owner() FIRST and only consult this for the non-owner
    case -- 'owner' has no tier entry here at all, by design (see module
    docstring). An unrecognized role value safely falls back to the most
    restrictive tier rather than raising or granting broad access."""
    return ROLE_TIER.get(role, ROLE_TIER[DEFAULT_SAFE_ROLE])


def permissions_for(role, is_owner=False):
    """Full permission dict for one owner_users account.

    is_owner=True (i.e. role == 'owner') always returns every permission
    True, regardless of ROLE_TIER -- the full owner/controller can do
    everything the narrower roles can, plus the owner-only actions (audit
    log, managing reference data, creating accounts/patients, editing
    allergies/conditions/pregnancy/phone) that are checked separately via
    app.utils.full_owner_required and never live in this dict."""
    if is_owner:
        return {
            "browse_all_patients": True,
            "view_patient": True,
            "add_antibiotic": True,
            "add_restricted_antibiotic": True,
            "quality_report": True,
            "pharmacy_report": True,
        }
    return dict(TIER_PERMISSIONS[role_tier(role)])
