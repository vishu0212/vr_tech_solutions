
import os

from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect

from config import Config


# =========================================================
# INITIALIZE FLASK EXTENSIONS
# =========================================================

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()


# =========================================================
# APPLICATION FACTORY
# =========================================================

def create_app(config_object=None):

    # Use a writable temporary instance directory on Vercel.
    # Use Flask's normal instance directory locally.
    if os.environ.get("VERCEL"):
        app = Flask(
            __name__,
            instance_path="/tmp/vr_tech_solutions_instance",
            instance_relative_config=True
        )
    else:
        app = Flask(
            __name__,
            instance_relative_config=True
        )

    # -----------------------------------------------------
    # LOAD CONFIGURATION
    # -----------------------------------------------------

    app.config.from_object(Config)

    if config_object is not None:
        app.config.from_object(config_object)

    # -----------------------------------------------------
    # VALIDATE REQUIRED CONFIGURATION
    # -----------------------------------------------------

    if not app.config.get("SECRET_KEY"):
        raise RuntimeError(
            "SECRET_KEY is missing. Configure it in your environment."
        )

    if not app.config.get("SQLALCHEMY_DATABASE_URI"):
        raise RuntimeError(
            "SQLALCHEMY_DATABASE_URI is missing. "
            "Configure your database settings."
        )

    app.config.setdefault(
        "SQLALCHEMY_TRACK_MODIFICATIONS",
        False
    )

    # -----------------------------------------------------
    # CREATE INSTANCE DIRECTORY
    # -----------------------------------------------------

    # Local development: normal Flask instance directory.
    # Vercel: writable temporary directory under /tmp.
    os.makedirs(app.instance_path, exist_ok=True)

    # -----------------------------------------------------
    # INITIALIZE EXTENSIONS
    # -----------------------------------------------------

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    # -----------------------------------------------------
    # LOGIN CONFIGURATION
    # -----------------------------------------------------

    login_manager.login_view = "admin.login"

    login_manager.login_message = "Please log in to continue."

    login_manager.login_message_category = "error"

    # -----------------------------------------------------
    # USER LOADER
    # -----------------------------------------------------

    from app.models import Admin

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return db.session.get(Admin, int(user_id))
        except (TypeError, ValueError):
            return None

    # -----------------------------------------------------
    # REGISTER BLUEPRINTS
    # -----------------------------------------------------

    from app.routes.main import main_bp
    from app.routes.careers import careers_bp
    from app.routes.admin import admin_bp

    app.register_blueprint(main_bp)

    app.register_blueprint(careers_bp)

    app.register_blueprint(
        admin_bp,
        url_prefix="/admin"
    )

    # -----------------------------------------------------
    # RETURN APPLICATION
    # -----------------------------------------------------

    return app
