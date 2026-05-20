from pathlib import Path
from xml.sax.saxutils import escape

import streamlit as st

from audit_app.constants import APP_TITLE
from audit_app.database import get_session, init_db
from audit_app.models import Usuario
from audit_app.pages import (
    page_base_checklists,
    page_checklist,
    page_dashboard_ehs,
    page_pac_auditoria,
    page_planejamento,
    page_relatorios_auditoria,
    page_sites,
    page_usuarios,
)
from audit_app.ui import apply_theme, header


NR12_DASHBOARD = "pages/01_dashboard.py"

AUDITORIA_NAV = {
    "Dashboard Auditoria Cruzada": page_dashboard_ehs,
    "Planejar Auditoria Cruzada": page_planejamento,
    "Executar Checklist EHS Directives": page_checklist,
    "PAC de Auditoria Cruzada": page_pac_auditoria,
    "Relatórios de Auditoria Cruzada": page_relatorios_auditoria,
    "Base do Checklist EHS": page_base_checklists,
    "Usuários": page_usuarios,
    "Sites": page_sites,
}


def hide_sidebar():
    st.markdown(
        """
        <style>
        section[data-testid="stSidebar"], div[data-testid="collapsedControl"] {display:none !important;}
        .block-container {max-width:1180px;padding-left:2rem;padding-right:2rem;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def portal_card(title, description):
    st.markdown(
        f"<div class='portal-card'><h2>{escape(str(title))}</h2><p>{escape(str(description))}</p></div>",
        unsafe_allow_html=True,
    )


def usuarios_ativos(session):
    return session.query(Usuario).filter_by(ativo=True).order_by(Usuario.nome).all()


def usuario_atual(session):
    usuarios = usuarios_ativos(session)
    if not usuarios:
        return None
    selected_id = st.session_state.get("usuario_id")
    if selected_id not in {u.id for u in usuarios}:
        selected_id = usuarios[0].id
        st.session_state["usuario_id"] = selected_id
    return session.get(Usuario, selected_id)


def seletor_usuario_portal(session):
    usuarios = usuarios_ativos(session)
    if not usuarios:
        st.warning("Nenhum usuário ativo cadastrado.")
        return None
    selected_id = st.session_state.get("usuario_id", usuarios[0].id)
    ids = [u.id for u in usuarios]
    index = ids.index(selected_id) if selected_id in ids else 0
    labels = {u.id: f"{u.nome} · {u.perfil}" for u in usuarios}
    st.markdown("<div class='portal-user-card'>", unsafe_allow_html=True)
    novo_id = st.selectbox("Usuário", ids, index=index, format_func=lambda user_id: labels[user_id])
    st.markdown("</div>", unsafe_allow_html=True)
    st.session_state["usuario_id"] = novo_id
    return session.get(Usuario, novo_id)


def sidebar_usuario(session):
    user = usuario_atual(session)
    if not user:
        st.sidebar.warning("Nenhum usuário ativo.")
        return None
    site = user.site.codigo if user.site else "Corporativo"
    st.sidebar.markdown("### Plataforma EHS")
    st.sidebar.caption("Auditoria Cruzada EHS Directives")
    st.sidebar.markdown(
        f"<div class='sidebar-profile'><strong>{escape(user.nome)}</strong><span>{escape(user.perfil)} · {escape(site)}</span></div>",
        unsafe_allow_html=True,
    )
    return user


def nr12_page_disponivel():
    return Path(NR12_DASHBOARD).exists()


def abrir_nr12():
    if nr12_page_disponivel() and hasattr(st, "switch_page"):
        try:
            st.switch_page(NR12_DASHBOARD)
        except Exception:
            pass
    st.session_state["mostrar_link_nr12"] = True
    st.rerun()


def render_link_nr12():
    if not st.session_state.get("mostrar_link_nr12"):
        return
    if nr12_page_disponivel() and hasattr(st, "page_link"):
        st.info("Acesse o módulo de Sustentação NR-12 pelo link abaixo.")
        st.page_link(NR12_DASHBOARD, label="Abrir Sustentação NR-12")
    else:
        st.warning("O módulo de Sustentação NR-12 não está disponível neste deploy. Verifique se as páginas NR-12 foram publicadas no repositório.")


def page_portal(session):
    hide_sidebar()
    header("Plataforma EHS", "Escolha o módulo que deseja acessar.")
    user = seletor_usuario_portal(session)
    if not user:
        return

    col1, col2 = st.columns(2)
    with col1:
        portal_card(
            "Auditoria Cruzada EHS Directives",
            "Planejamento, execução de checklist, PAC, relatórios e base de requisitos EHS.",
        )
        if st.button("Acessar Auditoria Cruzada", type="primary", use_container_width=True):
            st.session_state["modulo_ativo"] = "auditoria_cruzada"
            st.session_state["auditoria_page"] = "Dashboard Auditoria Cruzada"
            st.session_state.pop("mostrar_link_nr12", None)
            st.rerun()
    with col2:
        portal_card(
            "Sustentação NR-12",
            "Inventário de máquinas, documentos, inspeções, auditorias, PAC, MOC e relatórios NR-12.",
        )
        if st.button("Acessar Sustentação NR-12", use_container_width=True):
            abrir_nr12()

    render_link_nr12()


def sidebar_auditoria(session):
    user = sidebar_usuario(session)
    if not user:
        st.stop()

    st.sidebar.markdown("<div class='sidebar-section-title'>Portal</div>", unsafe_allow_html=True)
    if st.sidebar.button("Voltar ao portal", use_container_width=True):
        st.session_state["modulo_ativo"] = "portal"
        st.session_state.pop("mostrar_link_nr12", None)
        st.rerun()
    if st.sidebar.button("Ir para Sustentação NR-12", use_container_width=True):
        abrir_nr12()

    st.sidebar.divider()
    st.sidebar.markdown("<div class='sidebar-section-title'>Auditoria Cruzada</div>", unsafe_allow_html=True)
    pagina_atual = st.session_state.get("auditoria_page", "Dashboard Auditoria Cruzada")
    paginas = list(AUDITORIA_NAV.keys())
    index = paginas.index(pagina_atual) if pagina_atual in paginas else 0
    page = st.sidebar.radio("Navegação", paginas, index=index, label_visibility="collapsed")
    st.session_state["auditoria_page"] = page
    return page, user


def render_auditoria_cruzada(page, session, user):
    AUDITORIA_NAV[page](session, user)


def main():
    st.set_page_config(page_title=APP_TITLE, page_icon="🛡️", layout="wide")
    apply_theme()
    try:
        init_db()
    except Exception:
        st.error("Não foi possível inicializar a plataforma EHS.")
        st.stop()

    with get_session() as session:
        if st.session_state.get("modulo_ativo") != "auditoria_cruzada":
            st.session_state["modulo_ativo"] = "portal"
            page_portal(session)
            return

        page, user = sidebar_auditoria(session)
        render_auditoria_cruzada(page, session, user)


if __name__ == "__main__":
    main()
