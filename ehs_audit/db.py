from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .config import DATABASE_URL
from .constants import SITES_PADRAO
from .models import Base, Site, Usuario

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, echo=False, future=True, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_db() -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        seed_defaults(session)


@contextmanager
def get_session() -> Session:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def seed_defaults(session: Session) -> None:
    sites = {}
    for codigo in SITES_PADRAO:
        site = session.query(Site).filter_by(codigo=codigo).one_or_none()
        if not site:
            site = Site(codigo=codigo, nome=f"Unidade {codigo}", ativo=True)
            session.add(site)
            session.flush()
        sites[codigo] = site
    if not session.query(Usuario).filter_by(email="admin.lag@empresa.local").one_or_none():
        session.add(Usuario(nome="Admin LAG", email="admin.lag@empresa.local", perfil="Admin_LAG", ativo=True))
    for codigo, site in sites.items():
        email = f"ehs.{codigo.lower()}@empresa.local"
        if not session.query(Usuario).filter_by(email=email).one_or_none():
            session.add(Usuario(nome=f"EHS Local {codigo}", email=email, site_id=site.id, perfil="EHS_Local", ativo=True))
    session.commit()
