
"""SQLAlchemy engine/session setup.

The project uses SQLite by default and supports configurable database URLs.
Existing database records are preserved during schema migrations.
"""

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config.settings import settings


# Configure the database connection.
connect_args = (
    {"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {}
)

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()


def get_db():
    """Yield a database session and close it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create missing tables and safely migrate existing columns."""
    # Import models so SQLAlchemy registers all tables.
    from app.models import domain  # noqa: F401

    # Create tables that do not already exist.
    # This does not delete existing tables or their records.
    Base.metadata.create_all(bind=engine)

    # Add account-to-record linking columns to existing users tables.
    table_names = set(inspect(engine).get_table_names())

    if "users" in table_names:
        user_columns = {
            column["name"]
            for column in inspect(engine).get_columns("users")
        }

        with engine.begin() as connection:
            if "doctor_id" not in user_columns:
                connection.execute(
                    text(
                        "ALTER TABLE users "
                        "ADD COLUMN doctor_id VARCHAR "
                        "REFERENCES doctors(id)"
                    )
                )

            if "patient_id" not in user_columns:
                connection.execute(
                    text(
                        "ALTER TABLE users "
                        "ADD COLUMN patient_id VARCHAR "
                        "REFERENCES patients(id)"
                    )
                )

            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS "
                    "uq_users_doctor_id ON users(doctor_id)"
                )
            )
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS "
                    "uq_users_patient_id ON users(patient_id)"
                )
            )

    # Preserve the existing transcript migration.
    table_names = set(inspect(engine).get_table_names())

    if "transcripts" in table_names:
        transcript_columns = {
            column["name"]
            for column in inspect(engine).get_columns("transcripts")
        }

        if "diarization_status" not in transcript_columns:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "ALTER TABLE transcripts "
                        "ADD COLUMN diarization_status "
                        "VARCHAR DEFAULT 'not_run'"
                    )
                )