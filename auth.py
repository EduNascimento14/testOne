from __future__ import annotations

import hashlib
import hmac
import streamlit as st
from sqlalchemy.orm import Session
from models import User

ADMIN = "Admin Corporativo"
EDIT_ROLES = {ADMIN, "EHS Site", "Manutenção", "Produção / Operação"}


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    return hmac.compare_digest(hash_password(password), password_hash)


def authenticate(session: Session, name: str, password: str) -> User | None:
    user = session.query(User).filter(User.name.ilike(name.strip()), User.active.is_(True)).first()
    if user and verify_password(password, user.password_hash):
        return user
    return None


def can_access_site(user: User | None, site_id: int | None) -> bool:
    if not user:
        return False
    if user.role == ADMIN:
        return True
    return user.site_id == site_id


def can_edit(user: User | None) -> bool:
    return bool(user and user.role in EDIT_ROLES)


def can_admin(user: User | None) -> bool:
    return bool(user and user.role == ADMIN)


def require_login(session: Session) -> User | None:
    if "user_id" in st.session_state:
        user = session.get(User, st.session_state.user_id)
        if user and user.active:
            with st.sidebar:
                st.success(f"{user.name} · {user.role}")
                if st.button("Sair"):
                    st.session_state.pop("user_id", None)
                    st.rerun()
            return user
    st.title("🔐 NR-12 Manager")
    st.caption("Acesse com suas credenciais corporativas.")
    with st.form("login"):
        name = st.text_input("Usuário", value="Eduardo")
        password = st.text_input("Senha", type="password", value="admin123")
        submitted = st.form_submit_button("Entrar")
    if submitted:
        user = authenticate(session, name, password)
        if user:
            st.session_state.user_id = user.id
            st.rerun()
        st.error("Usuário ou senha inválidos.")
    return None


def visible_site_filter(user: User | None, query):
    if user and user.role != ADMIN and user.site_id:
        return query.filter_by(site_id=user.site_id)
    return query
