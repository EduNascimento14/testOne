from __future__ import annotations

import streamlit as st
from sqlalchemy.orm import Session

from .models import Usuario


def apply_theme() -> None:
    st.markdown("""
    <style>
    .stApp {background:#f6f8fb;} .block-container{padding-top:1.5rem;}
    div[data-testid="stMetric"]{background:white;border:1px solid #e5e7eb;border-radius:12px;padding:14px;box-shadow:0 2px 8px rgba(0,0,0,.04)}
    .ehs-header{background:white;border-left:6px solid #1f4e79;border-radius:12px;padding:1rem;margin-bottom:1rem;box-shadow:0 2px 8px rgba(0,0,0,.04)}
    .muted{color:#64748b}.danger{color:#b91c1c;font-weight:700}.warn{color:#b45309;font-weight:700}
    </style>
    """, unsafe_allow_html=True)


def header(title: str, subtitle: str = "") -> None:
    st.markdown(f"<div class='ehs-header'><h2>{title}</h2><div class='muted'>{subtitle}</div></div>", unsafe_allow_html=True)


def sidebar_user(session: Session) -> Usuario | None:
    users = session.query(Usuario).filter_by(ativo=True).order_by(Usuario.nome).all()
    if not users:
        st.sidebar.warning("Nenhum usuário cadastrado.")
        return None
    selected = st.sidebar.selectbox("Usuário MVP", users, format_func=lambda u: f"{u.nome} — {u.perfil}")
    return selected
