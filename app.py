import streamlit as st

from audit_app.constants import APP_TITLE
from audit_app.database import get_session, init_db
from audit_app.nr12_pages import (
    page_alertas_criticos,
    page_auditorias_nr12,
    page_dashboard_integrado,
    page_dashboard_nr12,
    page_documentos,
    page_exportacoes_gerais,
    page_inventario,
    page_moc,
    page_pac_nr12,
    page_relatorio_maquina,
    page_termo_garantia,
)
from audit_app.pages import (
    page_base_checklists,
    page_checklist,
    page_dashboard_ehs,
    page_pac_auditoria,
    page_pac_consolidado,
    page_planejamento,
    page_relatorios_auditoria,
    page_sites,
    page_usuarios,
)
from audit_app.ui import apply_theme, sidebar_user


NAV = {
    "Visão Geral": ["Dashboard Integrado", "Alertas Críticos", "Indicadores"],
    "Auditoria Cruzada EHS Directives": [
        "Planejar Auditoria Cruzada",
        "Executar Checklist EHS Directives",
        "PAC de Auditoria Cruzada",
        "Base do Checklist EHS",
        "Relatórios de Auditoria Cruzada",
    ],
    "Sustentação NR-12": [
        "Dashboard NR-12",
        "Inventário de Máquinas",
        "Documentos NR-12",
        "Auditorias e Inspeções NR-12",
        "PAC NR-12",
        "Gestão de Mudanças / MOC",
        "Termo de Garantia do Site",
    ],
    "Relatórios": ["Exportações Gerais", "Relatório por Site", "Relatório por Máquina", "Relatório de PAC"],
    "Administração": ["Usuários", "Sites", "Bases e Checklists"],
}


def render_page(page, session, user):
    routes = {
        "Dashboard Integrado": page_dashboard_integrado,
        "Alertas Críticos": page_alertas_criticos,
        "Indicadores": page_dashboard_ehs,
        "Planejar Auditoria Cruzada": page_planejamento,
        "Executar Checklist EHS Directives": page_checklist,
        "PAC de Auditoria Cruzada": page_pac_auditoria,
        "Base do Checklist EHS": page_base_checklists,
        "Relatórios de Auditoria Cruzada": page_relatorios_auditoria,
        "Dashboard NR-12": page_dashboard_nr12,
        "Inventário de Máquinas": page_inventario,
        "Documentos NR-12": page_documentos,
        "Auditorias e Inspeções NR-12": page_auditorias_nr12,
        "PAC NR-12": page_pac_nr12,
        "Gestão de Mudanças / MOC": page_moc,
        "Termo de Garantia do Site": page_termo_garantia,
        "Exportações Gerais": page_exportacoes_gerais,
        "Relatório por Site": page_dashboard_integrado,
        "Relatório por Máquina": page_relatorio_maquina,
        "Relatório de PAC": page_pac_consolidado,
        "Usuários": page_usuarios,
        "Sites": page_sites,
        "Bases e Checklists": page_base_checklists,
    }
    routes[page](session, user)


def main():
    st.set_page_config(page_title=APP_TITLE, page_icon="🛡️", layout="wide")
    apply_theme()
    try:
        init_db()
    except Exception as exc:
        st.error("Não foi possível inicializar a plataforma EHS.")
        st.exception(exc)
        st.stop()
    with get_session() as session:
        user = sidebar_user(session)
        st.sidebar.divider()
        grupo = st.sidebar.radio("Módulo", list(NAV.keys()))
        page = st.sidebar.radio("Navegação", NAV[grupo])
        render_page(page, session, user)


if __name__ == "__main__":
    main()
