import streamlit as st

from audit_app.constants import APP_TITLE
from audit_app.database import get_session, init_db
from audit_app.pages import page_base, page_checklist, page_dashboard, page_pac, page_planejamento, page_relatorios
from audit_app.ui import apply_theme, sidebar_user


def main():
    st.set_page_config(page_title=APP_TITLE, page_icon="🛡️", layout="wide")
    apply_theme()
    try:
        init_db()
    except Exception as exc:
        st.error("Erro ao inicializar o banco de dados da auditoria cruzada.")
        st.exception(exc)
        st.stop()

    with get_session() as session:
        user = sidebar_user(session)
        page = st.sidebar.radio("Navegação", ["Dashboard", "Planejar auditoria", "Executar checklist", "Achados / PAC", "Relatórios", "Base do Checklist"])
        if page == "Dashboard":
            page_dashboard(session)
        elif page == "Planejar auditoria":
            page_planejamento(session, user)
        elif page == "Executar checklist":
            page_checklist(session, user)
        elif page == "Achados / PAC":
            page_pac(session, user)
        elif page == "Relatórios":
            page_relatorios(session)
        elif page == "Base do Checklist":
            page_base(session, user)


if __name__ == "__main__":
    main()
