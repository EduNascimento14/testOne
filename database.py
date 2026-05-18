from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, scoped_session, sessionmaker

BASE_DIR = Path(__file__).resolve().parent
DB_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'nr12_app.db'}")

connect_args = {"check_same_thread": False} if DB_URL.startswith("sqlite") else {}
engine = create_engine(DB_URL, echo=False, future=True, connect_args=connect_args)
SessionLocal = scoped_session(sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True))
Base = declarative_base()


def init_db(seed: bool = True) -> None:
    """Create tables and optionally load initial NR-12 reference data."""
    import models  # noqa: F401 - registers SQLAlchemy models

    Base.metadata.create_all(bind=engine)
    if seed:
        from utils.seed_data import seed_initial_data

        db = SessionLocal()
        try:
            seed_initial_data(db)
        finally:
            db.close()


@contextmanager
def session_scope():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_session():
    return SessionLocal()
