from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from sqlalchemy import text

from config import Config


db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()


def create_app(config_object=None):
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object(Config)

    if config_object:
        app.config.from_object(config_object)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    login_manager.login_view = "admin.login"
    login_manager.login_message = "Please log in to continue."
    login_manager.login_message_category = "error"

    from app.models import Admin

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(Admin, int(user_id))

    from app.routes.main import main_bp
    from app.routes.careers import careers_bp
    from app.routes.admin import admin_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(careers_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")

    app.instance_path = str(app.instance_path)
    import os
    os.makedirs(app.instance_path, exist_ok=True)

    with app.app_context():
        db.create_all()

    return app
