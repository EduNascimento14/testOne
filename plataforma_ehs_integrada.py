import streamlit as st

from ehs_integrada.database import get_session, init_db
from ehs_integrada.models import Usuario
from ehs_integrada.pages_auditoria import (
    page_administracao,
    page_base_checklist_ehs,
    page_checklist_ehs,
    page_dashboard_auditoria,
    page_pac_auditoria,
    page_planejamento,
    page_relatorios_auditoria,
)
from ehs_integrada.pages_nr12 import (
    page_dashboard_nr12,
    page_documentos,
    page_inventario,
    page_moc_nr12,
    page_pac_nr12,
    page_relatorios_nr12,
    page_termo_nr12,
    page_verificacoes,
)
from ehs_integrada.seed import seed_base
from ehs_integrada.ui import apply_theme, close_card, header, module_card, sidebar_header


st.set_page_config(page_title="Plataforma EHS Integrada", layout="wide")


NR12_ROUTES = {
    "Dashboard NR-12": page_dashboard_nr12,
    "Inventário de Máquinas": page_inventario,
    "Documentos NR-12": page_documentos,
    "Checklists e Inspeções NR-12": page_verificacoes,
    "PAC NR-12": page_pac_nr12,
    "Gestão de Mudanças / MOC": page_moc_nr12,
    "Termo de Garantia do Site": page_termo_nr12,
    "Relatórios NR-12": page_relatorios_nr12,
}

EHS_ROUTES = {
    "Dashboard Auditoria Cruzada": page_dashboard_auditoria,
    "Planejamento de Auditorias": page_planejamento,
    "Execução do Checklist EHS Directives": page_checklist_ehs,
    "PAC Auditoria Cruzada": page_pac_auditoria,
    "Base do Checklist EHS": page_base_checklist_ehs,
    "Relatórios Auditoria Cruzada": page_relatorios_auditoria,
    "Administração": page_administracao,
}


def select_user(session):
    users = session.query(Usuario).filter_by(ativo=True).order_by(Usuario.nome).all()
    if not users:
        st.error("Não há usuários ativos cadastrados.")
        st.stop()
    current_id = st.session_state.get("ehs_integrada_user_id", users[0].id)
    selected = st.selectbox(
        "Usuário",
        users,
        index=[u.id for u in users].index(current_id) if current_id in [u.id for u in users] else 0,
        format_func=lambda u: f"{u.nome} · {u.perfil}" + (f" · {u.site.codigo}" if u.site else ""),
    )
    st.session_state["ehs_integrada_user_id"] = selected.id
    return selected


def page_home(session, user):
    header("Plataforma EHS Integrada", "Sustentação NR-12 e Auditorias Cruzadas de Diretrizes EHS.")
    c1, c2 = st.columns(2)
    with c1:
        module_card(
            "Sustentação NR-12",
            "Inventário de máquinas, documentos, inspeções, auditorias, PAC, MOC e termo anual de garantia da conformidade.",
        )
        if st.button("Acessar Sustentação NR-12", use_container_width=True):
            st.session_state["ehs_integrada_modulo"] = "nr12"
            st.session_state["ehs_integrada_pagina"] = "Dashboard NR-12"
            st.rerun()
        close_card()
    with c2:
        module_card(
            "Auditoria Cruzada EHS Directives",
            "Planejamento, execução de checklist, evidências, maturidade, PAC e relatórios das diretrizes EHS.",
        )
        if st.button("Acessar Auditoria Cruzada", use_container_width=True):
            st.session_state["ehs_integrada_modulo"] = "auditoria"
            st.session_state["ehs_integrada_pagina"] = "Dashboard Auditoria Cruzada"
            st.rerun()
        close_card()
    st.caption(f"Sessão: {user.nome} · {user.perfil}")


def sidebar_navigation(user, modulo):
    routes = NR12_ROUTES if modulo == "nr12" else EHS_ROUTES
    sidebar_header(user, "Sustentação NR-12" if modulo == "nr12" else "Auditoria Cruzada EHS Directives")
    if st.sidebar.button("Voltar à tela inicial", use_container_width=True):
        st.session_state["ehs_integrada_modulo"] = "home"
        st.session_state.pop("ehs_integrada_pagina", None)
        st.rerun()
    st.sidebar.markdown("---")
    page = st.sidebar.radio("Navegação", list(routes.keys()), key=f"nav_{modulo}", label_visibility="collapsed")
    st.session_state["ehs_integrada_pagina"] = page
    return page, routes[page]


def main():
    init_db()
    session = get_session()
    try:
        seed_base(session)
        modulo = st.session_state.get("ehs_integrada_modulo", "home")
        apply_theme(hide_sidebar=modulo in {"home", None})
        if modulo in {"home", None}:
            user = select_user(session)
            page_home(session, user)
            return

        user_id = st.session_state.get("ehs_integrada_user_id")
        user = session.get(Usuario, user_id) if user_id else None
        if user is None:
            st.session_state["ehs_integrada_modulo"] = "home"
            st.rerun()

        page, renderer = sidebar_navigation(user, modulo)
        renderer(session, user)
    finally:
        session.close()


if __name__ == "__main__":
    main()
