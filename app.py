import streamlit as st

from audit_app.constants import APP_TITLE
from audit_app.database import get_session, init_db
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
from audit_app.ui import apply_theme, header, portal_card, sidebar_user


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


def abrir_nr12():
    try:
        st.switch_page("pages/01_dashboard.py")
    except Exception:
        st.session_state["mostrar_link_nr12"] = True
        st.rerun()


def page_portal(session, user):
    header("Plataforma EHS", "Escolha o módulo que deseja acessar.")
    col1, col2 = st.columns(2)
    with col1:
        portal_card(
            "Auditoria Cruzada EHS Directives",
            "Planejamento, execução de checklist, PAC, relatórios e base de requisitos EHS.",
        )
        if st.button("Acessar Auditoria Cruzada", type="primary", use_container_width=True):
            st.session_state["modulo_ativo"] = "auditoria_cruzada"
            st.session_state.pop("mostrar_link_nr12", None)
            st.rerun()
    with col2:
        portal_card(
            "Sustentação NR-12",
            "Inventário de máquinas, documentos, inspeções, auditorias, PAC, MOC e relatórios NR-12.",
        )
        if st.button("Acessar Sustentação NR-12", use_container_width=True):
            abrir_nr12()

    if st.session_state.get("mostrar_link_nr12"):
        st.info("Acesse o módulo de Sustentação NR-12 pelo link abaixo.")
        if hasattr(st, "page_link"):
            st.page_link("pages/01_dashboard.py", label="Abrir Sustentação NR-12")
        else:
            st.warning("Abra a página de Sustentação NR-12 pelo menu lateral do Streamlit.")


def sidebar_auditoria():
    st.sidebar.markdown("<div class='sidebar-section-title'>Portal</div>", unsafe_allow_html=True)
    if st.sidebar.button("Voltar ao portal", use_container_width=True):
        st.session_state["modulo_ativo"] = "portal"
        st.session_state.pop("mostrar_link_nr12", None)
        st.rerun()
    if st.sidebar.button("Ir para Sustentação NR-12", use_container_width=True):
        abrir_nr12()

    st.sidebar.markdown("<div class='sidebar-section-title'>Auditoria Cruzada</div>", unsafe_allow_html=True)
    return st.sidebar.radio("Navegação", list(AUDITORIA_NAV.keys()), label_visibility="collapsed")


def render_auditoria_cruzada(page, session, user):
    AUDITORIA_NAV[page](session, user)


def main():
    st.set_page_config(page_title=APP_TITLE, page_icon="EHS", layout="wide")
    apply_theme()
    try:
        init_db()
    except Exception:
        st.error("Não foi possível inicializar a plataforma EHS.")
        st.stop()

    with get_session() as session:
        user = sidebar_user(session)
        if not user:
            st.stop()

        st.sidebar.divider()
        if st.session_state.get("modulo_ativo") != "auditoria_cruzada":
            st.session_state["modulo_ativo"] = "portal"
            page_portal(session, user)
            return

        page = sidebar_auditoria()
        render_auditoria_cruzada(page, session, user)


if __name__ == "__main__":
    main()
