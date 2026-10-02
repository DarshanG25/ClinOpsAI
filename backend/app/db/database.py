"""SQLAlchemy engine/session setup.

The project scaffold originally targeted MongoDB (see git history /
`docker-compose.yml`) but shipped no working connection code and no models.
Per the project brief, since the DB layer was incomplete we standardise on
SQLite via SQLAlchemy so the app is runnable with zero external services.
The engine URL is fully configurable through DATABASE_URL, so swapping to
Postgres/MySQL later only requires changing the connection string.
"""
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config.settings import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a DB session and closes it afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables. Safe to call repeatedly (no-op if they exist)."""
    from app.models import domain  # noqa: F401  (ensures models are registered)

    Base.metadata.create_all(bind=engine)
    transcript_columns = {
        column["name"] for column in inspect(engine).get_columns("transcripts")
    }
    if "diarization_status" not in transcript_columns:
        with engine.begin() as connection:
            connection.execute(text(
                "ALTER TABLE transcripts ADD COLUMN diarization_status VARCHAR DEFAULT 'not_run'"
            ))
