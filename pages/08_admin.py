from __future__ import annotations

import streamlit as st
from auth import can_admin, hash_password, require_login
from database import get_session, init_db
from models import Site, User
from utils.validations import ROLES

st.set_page_config(page_title="Admin", page_icon="⚙️", layout="wide")
init_db(); session = get_session(); user = require_login(session)
if not user: st.stop()
st.title("⚙️ Administração")
if not can_admin(user):
    st.warning("Apenas Admin Corporativo pode cadastrar usuários e alterar bases administrativas."); st.stop()

sites = session.query(Site).order_by(Site.code).all()
tab1, tab2 = st.tabs(["Usuários", "Sites"])
with tab1:
    with st.form("new_user"):
        c1, c2, c3 = st.columns(3)
        name = c1.text_input("Nome")
        email = c2.text_input("E-mail")
        role = c3.selectbox("Perfil", ROLES)
        site = st.selectbox("Site do usuário", [None] + sites, format_func=lambda s: "Todos" if s is None else s.code)
        password = st.text_input("Senha inicial", type="password", value="nr12@123")
        active = st.checkbox("Ativo", value=True)
        if st.form_submit_button("Criar usuário"):
            session.add(User(name=name, email=email, role=role, site_id=site.id if site else None, password_hash=hash_password(password), active=active)); session.commit(); st.success("Usuário criado."); st.rerun()
    st.dataframe([{"ID": u.id, "Nome": u.name, "E-mail": u.email, "Perfil": u.role, "Site": u.site.code if u.site else "Todos", "Ativo": u.active} for u in session.query(User).all()], use_container_width=True, hide_index=True)
with tab2:
    st.dataframe([{"ID": s.id, "Código": s.code, "Nome": s.name, "Ativo": s.active} for s in sites], use_container_width=True, hide_index=True)
session.close()
