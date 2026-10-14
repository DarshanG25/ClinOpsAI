
import getpass
import sys
from pathlib import Path

# Allow imports when the script is run from the backend directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.exc import IntegrityError

from app.core.security import hash_password
from app.db.database import SessionLocal
from app.models.domain import Doctor, User


def main():
    name = input("Doctor display name: ").strip()
    email = input("Doctor login email: ").strip().lower()
    password = getpass.getpass("Set doctor password (hidden): ")
    confirm = getpass.getpass("Confirm password: ")

    if not name or not email:
        print("Name and email are required.")
        return

    if len(password) < 12:
        print("Use a password with at least 12 characters.")
        return

    if password != confirm:
        print("Passwords do not match.")
        return

    db = SessionLocal()

    try:
        if db.query(User).filter(User.email == email).first():
            print("That email already belongs to an account. No changes made.")
            return

        # Reuse an existing unlinked doctor, if one exists.
        doctor = (
            db.query(Doctor)
            .filter(~Doctor.id.in_(
                db.query(User.doctor_id).filter(User.doctor_id.isnot(None))
            ))
            .first()
        )

        # Otherwise create a new doctor record.
        if doctor is None:
            doctor = Doctor(
                name=name,
                specialization="General Medicine",
                registration_no="DEMO-REG-0001",
            )
            db.add(doctor)
            db.flush()

        user = User(
            name=name,
            email=email,
            password_hash=hash_password(password),
            role="doctor",
            doctor_id=doctor.id,
            is_active=True,
        )

        db.add(user)
        db.commit()

        print("Doctor account created and linked successfully.")
        print("Login email:", email)
        print("Doctor record linked:", bool(user.doctor_id))

    except IntegrityError:
        db.rollback()
        print("A conflicting account or link exists. No changes were committed.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()