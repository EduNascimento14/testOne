from __future__ import annotations

from datetime import date
from pathlib import Path
import streamlit as st
from utils.theme import apply_nr12_theme, page_header
from auth import can_edit, require_login
from database import get_session, init_db
from models import ChangeManagement, Machine
from utils.calculations import update_machine_suggestion
from utils.validations import CHANGE_STATUS, CHANGE_TYPES, RESPONSIBLE_AREAS, SAFETY_CHANGE_TYPES

st.set_page_config(page_title="Gestão de Mudanças", page_icon="🔁", layout="wide")
apply_nr12_theme()
init_db(); session = get_session(); user = require_login(session)
if not user: st.stop()
page_header("🔁 Gestão de Mudanças / Intervenções NR-12", "Registro e validação de alterações com potencial impacto em segurança.")

machines = session.query(Machine).order_by(Machine.machine_code).all()
if user.role != "Admin Corporativo": machines = [m for m in machines if m.site_id == user.site_id]

def save_upload(file):
    if not file: return None
    path = Path("uploads") / f"moc_{date.today().isoformat()}_{file.name}"
    path.write_bytes(file.getbuffer()); return str(path)

with st.form("moc_form"):
    c1, c2, c3 = st.columns(3)
    machine = c1.selectbox("Máquina", machines, format_func=lambda m: f"{m.machine_code} - {m.name}")
    change_type = c2.selectbox("Tipo de mudança", CHANGE_TYPES)
    change_date = c3.date_input("Data", value=date.today())
    desc = st.text_area("Descrição da mudança")
    c4, c5 = st.columns(2)
    requester = c4.text_input("Solicitante", value=user.name)
    requester_area = c5.selectbox("Área solicitante", RESPONSIBLE_AREAS)
    impacts_safety = st.checkbox("Impacta segurança?", value=change_type in SAFETY_CHANGE_TYPES)
    requires_moc = st.checkbox("Exige MOC?", value=impacts_safety or change_type in SAFETY_CHANGE_TYPES)
    status = st.selectbox("Status", CHANGE_STATUS)
    a1, a2, a3, a4 = st.columns(4)
    ehs = a1.checkbox("Aprovação EHS")
    maint = a2.checkbox("Aprovação manutenção")
    eng = a3.checkbox("Aprovação engenharia")
    prod = a4.checkbox("Aprovação produção")
    needs_audit = st.checkbox("Necessita nova auditoria pós-mudança?", value=impacts_safety)
    needs_training = st.checkbox("Necessita treinamento?", value=impacts_safety)
    docs = st.file_uploader("Documentos anexos")
    obs = st.text_area("Observações")
    if st.form_submit_button("Registrar mudança", disabled=not can_edit(user)):
        if change_type in SAFETY_CHANGE_TYPES:
            impacts_safety = True; requires_moc = True
        cm = ChangeManagement(machine_id=machine.id, site_id=machine.site_id, change_type=change_type, description=desc, requester=requester, requester_area=requester_area, change_date=change_date, impacts_safety=impacts_safety, requires_moc=requires_moc, status=status, ehs_approval=ehs, maintenance_approval=maint, engineering_approval=eng, production_approval=prod, attached_documents=save_upload(docs), needs_post_change_audit=needs_audit, needs_training=needs_training, observations=obs)
        session.add(cm); session.flush(); update_machine_suggestion(session, machine, user.name); session.commit(); st.success("Mudança registrada."); st.rerun()

changes = session.query(ChangeManagement).join(Machine).order_by(ChangeManagement.id.desc()).all()
if user.role != "Admin Corporativo": changes = [c for c in changes if c.site_id == user.site_id]
rows = []
for c in changes:
    critical_pending = c.impacts_safety and c.status not in {"Encerrada", "Reprovada"} and not (c.ehs_approval and (c.maintenance_approval or c.engineering_approval))
    rows.append({"ID": c.id, "Site": c.site.code, "Máquina": c.machine.machine_code, "Tipo": c.change_type, "Data": c.change_date, "Impacta segurança": c.impacts_safety, "Exige MOC": c.requires_moc, "Status": c.status, "Aprovação EHS": c.ehs_approval, "Aprovação Manut/Eng": c.maintenance_approval or c.engineering_approval, "Alerta crítico": critical_pending})
st.dataframe(rows, use_container_width=True, hide_index=True)
session.close()
