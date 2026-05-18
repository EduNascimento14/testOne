from __future__ import annotations

from datetime import date
from pathlib import Path
import streamlit as st
from utils.theme import apply_nr12_theme, page_header
from auth import can_edit, require_login
from database import get_session, init_db
from models import ActionPlan, Machine
from utils.calculations import actions_df, update_machine_suggestion
from utils.exports import export_actions_excel
from utils.validations import ACTION_CLASSES, ACTION_ORIGINS, ACTION_STATUS, RESPONSIBLE_AREAS

st.set_page_config(page_title="Planos de Ação", page_icon="🧰", layout="wide")
apply_nr12_theme()
init_db(); session = get_session(); user = require_login(session)
if not user: st.stop()
page_header("🧰 Planos de Ação e Tratativa de Desvios", "Acompanhamento de responsabilidades, prazos, evidências e validação EHS.")

machines = session.query(Machine).order_by(Machine.machine_code).all()
if user.role != "Admin Corporativo": machines = [m for m in machines if m.site_id == user.site_id]

def save_upload(file):
    if not file: return None
    path = Path("uploads") / f"action_{date.today().isoformat()}_{file.name}"
    path.write_bytes(file.getbuffer()); return str(path)

with st.expander("Criar ação manual", expanded=True):
    with st.form("action_new"):
        machine = st.selectbox("Máquina vinculada", machines, format_func=lambda m: f"{m.machine_code} - {m.name}")
        origin = st.selectbox("Origem", ACTION_ORIGINS)
        desc = st.text_area("Descrição do desvio")
        c1, c2, c3, c4 = st.columns(4)
        classification = c1.selectbox("Classificação", ACTION_CLASSES)
        responsible = c2.text_input("Responsável")
        area = c3.selectbox("Área responsável", RESPONSIBLE_AREAS)
        due = c4.date_input("Prazo", value=date.today())
        comments = st.text_area("Comentários")
        if st.form_submit_button("Criar ação", disabled=not can_edit(user)):
            session.add(ActionPlan(origin=origin, machine_id=machine.id, deviation_description=desc, classification=classification, responsible=responsible, responsible_area=area, due_date=due, status="Aberta", comments=comments))
            session.flush(); update_machine_suggestion(session, machine, user.name); session.commit(); st.success("Ação criada."); st.rerun()

df = actions_df(session)
if not df.empty and user.role != "Admin Corporativo": df = df[df["Site"] == user.site.code]
st.dataframe(df, use_container_width=True, hide_index=True)
st.download_button("Exportar plano de ação Excel", export_actions_excel(session), "plano_acao_nr12.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

actions = session.query(ActionPlan).join(Machine).order_by(ActionPlan.id.desc()).all()
if user.role != "Admin Corporativo": actions = [a for a in actions if a.machine.site_id == user.site_id]
if actions:
    st.subheader("Atualizar ação")
    action = st.selectbox("Ação", actions, format_func=lambda a: f"#{a.id} {a.machine.machine_code} - {a.classification} - {a.status}")
    with st.form("action_edit"):
        status = st.selectbox("Status", ACTION_STATUS, index=ACTION_STATUS.index(action.status) if action.status in ACTION_STATUS else 0)
        responsible = st.text_input("Responsável", value=action.responsible or "")
        due = st.date_input("Prazo", value=action.due_date or date.today())
        evidence = st.file_uploader("Evidência de conclusão")
        ehs_validation = st.checkbox("Validação EHS", value=action.ehs_validation)
        comments = st.text_area("Comentários", value=action.comments or "")
        if st.form_submit_button("Salvar atualização", disabled=not can_edit(user)):
            if status == "Concluída" and not (evidence or action.completion_evidence) or (status == "Concluída" and not ehs_validation):
                st.error("Ação concluída precisa de evidência e validação EHS.")
            else:
                action.status, action.responsible, action.due_date, action.ehs_validation, action.comments = status, responsible, due, ehs_validation, comments
                if evidence: action.completion_evidence = save_upload(evidence)
                if status == "Concluída": action.completion_date = date.today()
                update_machine_suggestion(session, action.machine, user.name); session.commit(); st.success("Ação atualizada."); st.rerun()
session.close()
