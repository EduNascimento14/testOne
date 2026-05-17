from __future__ import annotations

import streamlit as st
from database import get_session, init_db
from auth import require_login

st.set_page_config(page_title="NR-12 Manager", page_icon="🛡️", layout="wide")

CUSTOM_CSS = """
<style>
.block-container {padding-top: 1.5rem;}
.nr12-card {border-radius: 14px; padding: 1rem; background: #f8fafc; border: 1px solid #e2e8f0;}
.status-ok {color:#15803d;font-weight:700}.status-warn {color:#ca8a04;font-weight:700}.status-bad {color:#b91c1c;font-weight:700}.status-muted {color:#64748b;font-weight:700}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
init_db()

session = get_session()
user = require_login(session)
if not user:
    st.stop()

st.title("🛡️ Sustentação da Conformidade NR-12")
st.markdown("Plataforma corporativa para inventário, documentação, auditorias, planos de ação e gestão de mudanças em máquinas e equipamentos.")

st.info("Use o menu lateral do Streamlit para navegar pelos módulos. O banco SQLite é criado automaticamente em `nr12_app.db` e pode ser substituído futuramente via `DATABASE_URL`.")

st.subheader("Perfis e visão de acesso")
st.write(
    "Admins corporativos acessam todos os sites; perfis site ficam restritos ao site cadastrado; visualizadores consultam dados sem edição."
)

st.subheader("Primeiros passos")
st.markdown(
    """
1. Acesse **Dashboard** para visão consolidada.
2. Cadastre ou importe máquinas em **Inventário**.
3. Vincule documentos legais/técnicos em **Documentos NR-12**.
4. Execute checklists em **Auditorias/Inspeções** e gere ações automaticamente.
5. Acompanhe tratativas em **Planos de Ação** e mudanças em **Gestão de Mudanças**.
"""
)
session.close()
