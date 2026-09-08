from flask import Flask, redirect, request, session, url_for

from app.config import Config
from app.csrf import init_csrf
from app.db import init_db
from app.translations import t as translate


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    init_db(app)
    init_csrf(app)

    from app.auth import bp as auth_bp
    from app.owner import bp as owner_bp
    from app.patient import bp as patient_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(owner_bp)
    app.register_blueprint(patient_bp)

    @app.route("/")
    def index():
        return redirect(url_for("auth.choose_login"))

    @app.route("/set-language/<lang>")
    def set_language(lang):
        if lang in app.config["LANGUAGES"]:
            session["lang"] = lang
        return redirect(request.referrer or url_for("auth.choose_login"))

    @app.context_processor
    def inject_i18n():
        lang = session.get("lang", app.config["DEFAULT_LANGUAGE"])
        return {
            "t": lambda key: translate(key, lang),
            "lang": lang,
            "dir": "rtl" if lang == "ar" else "ltr",
        }

    @app.context_processor
    def inject_auth_state():
        from app.utils import current_owner, current_patient
        owner = current_owner()
        patient = current_patient()
        return {
            "is_authenticated": bool(owner or patient),
            "is_owner_session": bool(owner),
            "is_patient_session": bool(patient),
            "owner_role": (owner.get("role", "owner") if owner else None),
        }

    @app.errorhandler(403)
    def forbidden(e):
        return ("Access denied for your account type.", 403)

    return app
