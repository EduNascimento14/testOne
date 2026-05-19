from xml.sax.saxutils import escape

import streamlit as st

from audit_app.models import Auditoria, Usuario


def apply_theme():
    st.markdown(
        """
        <style>
        :root {--brand-bg:#f6f8fb;--card-bg:#ffffff;--muted:#5f6b7a;--border:#e7ebf3;--title:#12263f;--accent:#1f4bb8;--gold-1:#ffcd61;--gold-2:#ffb91d;}
        .stApp {background:var(--brand-bg);} .block-container {padding-top:1.4rem;padding-bottom:2.2rem;}
        section[data-testid="stSidebar"] {background:linear-gradient(180deg,var(--gold-1) 0%,var(--gold-2) 100%) !important;border-right:1px solid rgba(18,38,63,.12);}
        section[data-testid="stSidebar"] * {color:#1f1f1f !important;} section[data-testid="stSidebar"] [data-testid="stRadio"] label {font-weight:700;}
        .page-header {background:var(--card-bg);border:1px solid var(--border);border-radius:14px;padding:1rem 1.2rem;margin-bottom:1rem;box-shadow:0 4px 16px rgba(18,38,63,.05);} .page-header h1 {margin:0;font-size:1.55rem;color:var(--title);} .page-header p {margin:.35rem 0 0;color:var(--muted);font-size:.94rem;}
        div[data-testid="stForm"], div[data-testid="stExpander"] {background:var(--card-bg);border:1px solid var(--border);border-radius:12px;padding:.85rem 1rem;box-shadow:0 2px 8px rgba(18,38,63,.04);} .section-title {margin:1.1rem 0 .55rem;color:var(--title);font-size:1.08rem;font-weight:700;}
        .kpi-card {border:1px solid var(--border);background:var(--card-bg);border-radius:12px;padding:.9rem 1rem;box-shadow:0 2px 8px rgba(18,38,63,.04);min-height:88px;} .kpi-label {color:var(--muted);font-size:.78rem;margin-bottom:.15rem;} .kpi-value {color:var(--title);font-size:1.25rem;font-weight:800;}
        .stButton button, .stDownloadButton button {border-radius:10px !important;border:1px solid #d9e0ec !important;font-weight:700 !important;} .stButton button[kind="primary"] {background:var(--accent) !important;color:white !important;} div[data-testid="stDataFrame"], div[data-testid="stDataEditor"] {border-radius:12px;overflow:hidden;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def header(title, subtitle=""):
    st.markdown(f"<div class='page-header'><h1>{escape(str(title))}</h1><p>{escape(str(subtitle))}</p></div>", unsafe_allow_html=True)


def section(title):
    st.markdown(f"<div class='section-title'>{escape(str(title))}</div>", unsafe_allow_html=True)


def kpi_card(label, value):
    st.markdown(f"<div class='kpi-card'><div class='kpi-label'>{escape(str(label))}</div><div class='kpi-value'>{escape(str(value))}</div></div>", unsafe_allow_html=True)


def sidebar_user(session):
    st.sidebar.markdown("### Auditoria EHS")
    st.sidebar.caption("Gestão corporativa de auditorias cruzadas")
    usuarios = session.query(Usuario).filter_by(ativo=True).order_by(Usuario.nome).all()
    if not usuarios:
        st.sidebar.warning("Nenhum usuário ativo.")
        return None
    labels = {u.id: f"{u.nome} · {u.perfil}" for u in usuarios}
    selected_id = st.sidebar.selectbox("Usuário", list(labels), format_func=lambda user_id: labels[user_id])
    return session.get(Usuario, selected_id)


def select_auditoria(session, label="Auditoria"):
    auditorias = session.query(Auditoria).order_by(Auditoria.ano.desc(), Auditoria.id.desc()).all()
    if not auditorias:
        st.info("Crie uma auditoria para utilizar esta tela.")
        return None
    labels = {a.id: f"#{a.id} · {a.nome} · {a.status}" for a in auditorias}
    selected_id = st.selectbox(label, list(labels), format_func=lambda audit_id: labels[audit_id])
    return session.get(Auditoria, selected_id)
