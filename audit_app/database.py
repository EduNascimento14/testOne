from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from audit_app.constants import DATABASE_URL, UPLOAD_DIR
from audit_app.models import Base
from audit_app.seed import seed_base

UPLOAD_DIR.mkdir(exist_ok=True)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


@contextmanager
def get_session():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db():
    Base.metadata.create_all(engine)
    with get_session() as session:
        seed_base(session)
