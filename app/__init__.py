
import os

from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect

from config import Config


db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()


def create_app(config_object=None):
    """Create and configure the Flask application."""
    app = Flask(__name__, instance_relative_config=True)

    # Load application configuration.
    app.config.from_object(Config)

    if config_object:
        app.config.from_object(config_object)

    # Validate essential configuration.
    if not app.config.get("SECRET_KEY"):
        raise RuntimeError(
            "SECRET_KEY is missing. Configure it in your environment."
        )

    if not app.config.get("SQLALCHEMY_DATABASE_URI"):
        raise RuntimeError(
            "SQLALCHEMY_DATABASE_URI is missing. Check config.py and .env."
        )

    app.config.setdefault("SQLALCHEMY_TRACK_MODIFICATIONS", False)

    os.makedirs(app.instance_path, exist_ok=True)

    # Initialize extensions.
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    login_manager.login_view = "admin.login"
    login_manager.login_message = "Please log in to continue."
    login_manager.login_message_category = "error"

    # Import models and configure user loading.
    from app.models import Admin

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return db.session.get(Admin, int(user_id))
        except (TypeError, ValueError):
            return None

    # Register blueprints.
    from app.routes.main import main_bp
    from app.routes.careers import careers_bp
    from app.routes.admin import admin_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(careers_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")

    # Do not connect to the database or create tables automatically here.
    return app
