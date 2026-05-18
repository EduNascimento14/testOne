from __future__ import annotations

import streamlit as st
from utils.theme import apply_nr12_theme, page_header
from auth import require_login
from database import get_session, init_db
from models import Machine
from utils.exports import export_actions_excel, export_audits_excel, export_documents_excel, export_inventory_excel, export_machine_pdf

st.set_page_config(page_title="Relatórios", page_icon="📦", layout="wide")
apply_nr12_theme()
init_db(); session = get_session(); user = require_login(session)
if not user: st.stop()
page_header("📦 Relatórios e Exportações", "Exportações executivas, operacionais e relatório detalhado por máquina.")

c1, c2 = st.columns(2)
c1.download_button("Inventário de máquinas Excel", export_inventory_excel(session), "inventario_nr12.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
c2.download_button("Plano de ação Excel", export_actions_excel(session), "plano_acao_nr12.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
c3, c4 = st.columns(2)
c3.download_button("Documentos NR-12 Excel", export_documents_excel(session), "documentos_nr12.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
c4.download_button("Auditorias Excel", export_audits_excel(session), "auditorias_nr12.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

machines = session.query(Machine).order_by(Machine.machine_code).all()
if user.role != "Admin Corporativo": machines = [m for m in machines if m.site_id == user.site_id]
st.subheader("Relatório por máquina")
if machines:
    machine = st.selectbox("Máquina", machines, format_func=lambda m: f"{m.machine_code} - {m.name}")
    st.download_button("Baixar PDF da máquina", export_machine_pdf(session, machine.id), f"relatorio_{machine.machine_code}.pdf", "application/pdf")
    st.markdown("### Resumo")
    st.write({"Status NR-12": machine.nr12_status, "Status sugerido": machine.suggested_status, "Documentos": len(machine.documents), "Auditorias": len(machine.audits), "Ações": len(machine.actions), "Mudanças": len(machine.changes)})
session.close()
