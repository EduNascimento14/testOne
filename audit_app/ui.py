from xml.sax.saxutils import escape

import streamlit as st

from audit_app.models import Auditoria, Site, Usuario


def apply_theme():
    st.markdown(
        """
        <style>
        :root {--brand-bg:#f6f8fb;--card-bg:#fff;--muted:#5f6b7a;--border:#e7ebf3;--title:#12263f;--accent:#1f4bb8;--gold-1:#ffcf66;--gold-2:#f2ab17;--danger:#b42318;--ok:#137333;}
        .stApp {background:var(--brand-bg);}
        .block-container {padding-top:1.2rem;padding-bottom:2.2rem;}
        section[data-testid="stSidebar"] {background:linear-gradient(180deg,var(--gold-1) 0%,var(--gold-2) 100%) !important;border-right:1px solid rgba(18,38,63,.12);}
        section[data-testid="stSidebar"] * {color:#1f1f1f !important;}
        .page-header {background:var(--card-bg);border:1px solid var(--border);border-radius:12px;padding:1rem 1.2rem;margin-bottom:1rem;box-shadow:0 4px 16px rgba(18,38,63,.05);}
        .page-header h1 {margin:0;font-size:1.55rem;color:var(--title);letter-spacing:0;}
        .page-header p {margin:.35rem 0 0;color:var(--muted);font-size:.94rem;}
        .portal-card {background:var(--card-bg);border:1px solid var(--border);border-radius:12px;padding:1.15rem 1.2rem;margin:.2rem 0 .75rem;min-height:150px;box-shadow:0 4px 16px rgba(18,38,63,.05);}
        .portal-card h2 {margin:0 0 .55rem;color:var(--title);font-size:1.2rem;letter-spacing:0;}
        .portal-card p {margin:0;color:var(--muted);font-size:.94rem;line-height:1.45;}
        .portal-user-card {background:var(--card-bg);border:1px solid var(--border);border-radius:12px;padding:.9rem 1rem;margin:0 0 1rem;box-shadow:0 4px 16px rgba(18,38,63,.04);max-width:420px;}
        .sidebar-profile {background:rgba(255,255,255,.38);border:1px solid rgba(18,38,63,.14);border-radius:10px;padding:.7rem .75rem;margin:.65rem 0 .9rem;}
        .sidebar-profile strong {display:block;color:#1f1f1f;font-size:.94rem;}
        .sidebar-profile span {display:block;color:#3d3d3d;font-size:.76rem;margin-top:.1rem;}
        .sidebar-section-title {font-size:.76rem;text-transform:uppercase;font-weight:800;letter-spacing:.04em;margin:.85rem 0 .35rem;color:#3d2b00;}
        div[data-testid="stForm"], div[data-testid="stExpander"] {background:var(--card-bg);border:1px solid var(--border);border-radius:10px;padding:.85rem 1rem;box-shadow:0 2px 8px rgba(18,38,63,.04);}
        .section-title {margin:1.1rem 0 .55rem;color:var(--title);font-size:1.08rem;font-weight:700;}
        .kpi-card {border:1px solid var(--border);background:var(--card-bg);border-radius:10px;padding:.9rem 1rem;box-shadow:0 2px 8px rgba(18,38,63,.04);min-height:88px;}
        .kpi-label {color:var(--muted);font-size:.78rem;margin-bottom:.15rem;}
        .kpi-value {color:var(--title);font-size:1.25rem;font-weight:800;}
        .alert-card {border-left:5px solid var(--danger);background:#fff;border-radius:10px;padding:.8rem 1rem;border-top:1px solid var(--border);border-right:1px solid var(--border);border-bottom:1px solid var(--border);}
        .stButton button, .stDownloadButton button {border-radius:10px !important;border:1px solid #d9e0ec !important;font-weight:700 !important;}
        .stButton button[kind="primary"] {background:var(--accent) !important;color:white !important;}
        div[data-testid="stDataFrame"], div[data-testid="stDataEditor"] {border-radius:10px;overflow:hidden;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def header(title, subtitle=""):
    st.markdown(
        f"<div class='page-header'><h1>{escape(str(title))}</h1><p>{escape(str(subtitle))}</p></div>",
        unsafe_allow_html=True,
    )


def portal_card(title, description):
    st.markdown(
        f"<div class='portal-card'><h2>{escape(str(title))}</h2><p>{escape(str(description))}</p></div>",
        unsafe_allow_html=True,
    )


def section(title):
    st.markdown(f"<div class='section-title'>{escape(str(title))}</div>", unsafe_allow_html=True)


def kpi_card(label, value):
    st.markdown(
        f"<div class='kpi-card'><div class='kpi-label'>{escape(str(label))}</div><div class='kpi-value'>{escape(str(value))}</div></div>",
        unsafe_allow_html=True,
    )


def alert_card(text):
    st.markdown(f"<div class='alert-card'>{escape(str(text))}</div>", unsafe_allow_html=True)


def is_global_user(user):
    return bool(user and user.perfil in ["Admin_LAG", "Auditor"])


def can_admin(user):
    return bool(user and user.perfil == "Admin_LAG")


def can_edit(user):
    return bool(user and user.perfil not in ["Visualizador"])


def visible_site_ids(session, user):
    if is_global_user(user) or not user:
        return [s.id for s in session.query(Site).filter_by(ativo=True).all()]
    return [user.site_id] if user.site_id else []


def site_filter_query(query, model_site_id_col, session, user):
    ids = visible_site_ids(session, user)
    return query.filter(model_site_id_col.in_(ids)) if ids else query.filter(False)


def sidebar_user(session):
    st.sidebar.markdown("### Plataforma EHS")
    st.sidebar.caption("Auditorias Cruzadas e Sustentação NR-12")
    usuarios = session.query(Usuario).filter_by(ativo=True).order_by(Usuario.nome).all()
    if not usuarios:
        st.sidebar.warning("Nenhum usuário ativo.")
        return None
    labels = {u.id: f"{u.nome} · {u.perfil}" for u in usuarios}
    selected_id = st.sidebar.selectbox("Usuário", list(labels), format_func=lambda user_id: labels[user_id])
    user = session.get(Usuario, selected_id)
    site = user.site.codigo if user and user.site else "Corporativo"
    st.sidebar.markdown(
        f"<div class='sidebar-profile'><strong>{escape(user.nome)}</strong><span>{escape(user.perfil)} · {escape(site)}</span></div>",
        unsafe_allow_html=True,
    )
    return user


def select_auditoria(session, user=None, label="Auditoria"):
    q = session.query(Auditoria).order_by(Auditoria.ano.desc(), Auditoria.id.desc())
    if user and not is_global_user(user):
        q = q.filter(Auditoria.site_auditado_id == user.site_id)
    auditorias = q.all()
    if not auditorias:
        st.info("Crie uma auditoria para utilizar esta tela.")
        return None
    labels = {a.id: f"#{a.id} · {a.nome} · {a.status}" for a in auditorias}
    selected_id = st.selectbox(label, list(labels), format_func=lambda audit_id: labels[audit_id])
    return session.get(Auditoria, selected_id)
