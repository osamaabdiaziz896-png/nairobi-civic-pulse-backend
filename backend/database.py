"""
database.py
Handles the PostgreSQL connection and session management for Nairobi Civic Pulse.

Set DATABASE_URL as an environment variable, e.g.:
    postgresql+psycopg2://civic_user:civic_pass@localhost:5432/nairobi_civic_pulse

If DATABASE_URL is not set, falls back to a local SQLite file (db.sqlite3) so the
project can be demoed instantly without installing/configuring PostgreSQL.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./db.sqlite3",  # zero-config fallback for local demos
)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a DB session and closes it afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables. Safe to call repeatedly (no-op if tables exist)."""
    import backend.models  # noqa: F401  (ensure models are registered on Base)
    Base.metadata.create_all(bind=engine)
