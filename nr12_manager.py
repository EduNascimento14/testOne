from __future__ import annotations

import streamlit as st
from auth import require_login
from database import get_session, init_db
from utils.theme import apply_nr12_theme, page_header, section_title

st.set_page_config(page_title="NR-12 Manager", page_icon="🛡️", layout="wide")
apply_nr12_theme()
init_db()

session = get_session()
user = require_login(session)
if not user:
    st.stop()

page_header(
    "🛡️ Sustentação da Conformidade NR-12",
    "Gestão corporativa de máquinas, documentos, auditorias, planos de ação e mudanças com impacto em segurança.",
)

section_title("Visão de acesso")
st.write("Admins corporativos acessam todos os sites; perfis locais visualizam e atuam conforme o site vinculado ao usuário.")

section_title("Módulos principais")
st.markdown(
    """
- **Dashboard:** indicadores consolidados e alertas críticos.
- **Inventário:** cadastro, consulta, importação e exportação de máquinas.
- **Documentos NR-12:** controle documental legal e técnico por máquina.
- **Auditorias/Inspeções:** checklists de sustentação e geração de ações.
- **Planos de Ação:** acompanhamento de desvios, prazos e validações.
- **Gestão de Mudanças:** registro de intervenções com impacto em segurança.
- **Relatórios:** exportações gerenciais e relatório por máquina.
"""
)
session.close()
