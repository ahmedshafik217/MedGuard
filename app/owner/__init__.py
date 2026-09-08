from flask import Blueprint

bp = Blueprint("owner", __name__, url_prefix="/owner")

from app.owner import routes  # noqa: E402,F401
