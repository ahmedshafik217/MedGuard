from flask import Blueprint

bp = Blueprint("patient", __name__, url_prefix="/patient")

from app.patient import routes  # noqa: E402,F401
