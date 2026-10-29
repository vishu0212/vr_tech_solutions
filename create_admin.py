
import getpass
from pathlib import Path

from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

load_dotenv(Path(__file__).resolve().parent / ".env")

from app import create_app, db
from app.models import Admin


def create_admin():
    app = create_app()

    with app.app_context():
        print("\n=== VR Tech Solutions | Create Admin ===\n")

        username = input("Enter admin username: ").strip()
        email = input("Enter admin email: ").strip().lower()

        if not username:
            print("Error: Username cannot be empty.")
            return

        if not email or "@" not in email:
            print("Error: Enter a valid email address.")
            return

        # Check for an existing username
        if Admin.query.filter_by(username=username).first():
            print("Error: This username already exists.")
            return

        # Check for an existing email
        if Admin.query.filter_by(email=email).first():
            print("Error: This email already exists.")
            return

        # Password input
        password = getpass.getpass(
            "Create password (minimum 6 characters): "
        )
        confirm_password = getpass.getpass(
            "Confirm password: "
        )

        if len(password) < 6:
            print("Error: Password must contain at least 6 characters.")
            return

        if password != confirm_password:
            print("Error: Passwords do not match.")
            return

        # Create admin account
        admin = Admin(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            is_active=True
        )

        try:
            db.session.add(admin)
            db.session.commit()

            print("\nAdmin account created successfully!")
            print("Username:", username)
            print("Email:", email)
            print("Open your admin login page to sign in.")

        except Exception as error:
            db.session.rollback()
            print("\nFailed to create the admin account.")
            print("Error:", error)


if __name__ == "__main__":
    create_admin()
