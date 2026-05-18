from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, scoped_session, sessionmaker

BASE_DIR = Path(__file__).resolve().parent
DB_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'nr12_app.db'}")

connect_args = {"check_same_thread": False} if DB_URL.startswith("sqlite") else {}
engine = create_engine(DB_URL, echo=False, future=True, connect_args=connect_args)
SessionLocal = scoped_session(sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True))
Base = declarative_base()


def _quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _sqlite_default_sql(column) -> str:
    default = getattr(column.default, "arg", None) if column.default is not None else None
    if default is None or callable(default):
        return ""
    if isinstance(default, bool):
        return f" DEFAULT {1 if default else 0}"
    if isinstance(default, (int, float)):
        return f" DEFAULT {default}"
    if isinstance(default, str):
        return " DEFAULT '" + default.replace("'", "''") + "'"
    return ""


def _sync_sqlite_schema() -> None:
    """Add columns introduced after the first SQLite database was created."""
    if engine.dialect.name != "sqlite":
        return

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as connection:
        for table in Base.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue
            existing_columns = {col["name"] for col in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing_columns or column.primary_key:
                    continue
                column_type = column.type.compile(dialect=engine.dialect)
                statement = (
                    f"ALTER TABLE {_quote_identifier(table.name)} "
                    f"ADD COLUMN {_quote_identifier(column.name)} {column_type}"
                    f"{_sqlite_default_sql(column)}"
                )
                connection.execute(text(statement))


def init_db(seed: bool = True) -> None:
    """Create tables, update local SQLite schema and optionally load initial NR-12 data."""
    import models  # noqa: F401 - registers SQLAlchemy models

    Base.metadata.create_all(bind=engine)
    _sync_sqlite_schema()
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
