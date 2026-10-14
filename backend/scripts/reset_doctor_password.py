import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import getpass

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.database import SessionLocal
from app.models.domain import User


def main():
    email = input("Doctor login email: ").strip().lower()
    password = getpass.getpass("Enter new password (hidden): ")
    confirm = getpass.getpass("Confirm new password: ")

    if len(password) < 12:
        print("Password must be at least 12 characters.")
        return

    if password != confirm:
        print("Passwords do not match.")
        return

    db: Session = SessionLocal()

    try:
        user = (
            db.query(User)
            .filter(User.email == email, User.role == "doctor")
            .first()
        )

        if user is None:
            print("No doctor account found with that email.")
            return

        user.password_hash = hash_password(password)
        db.commit()

        print("Doctor password reset successfully.")
        print("Your doctor account and clinical records were preserved.")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()