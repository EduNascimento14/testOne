from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
import streamlit as st
from auth import can_edit, require_login
from database import get_session, init_db
from models import ActionPlan, Audit, AuditItem, ChecklistTemplate, Machine
from utils.calculations import calculate_audit_result, update_machine_suggestion
from utils.validations import ACTION_CLASSES, AUDIT_TYPES, ITEM_RESULTS, RESPONSIBLE_AREAS

st.set_page_config(page_title="Auditorias", page_icon="✅", layout="wide")
init_db(); session = get_session(); user = require_login(session)
if not user: st.stop()
st.title("✅ Auditorias e Inspeções de Sustentação NR-12")

machines = session.query(Machine).order_by(Machine.machine_code).all()
if user.role != "Admin Corporativo": machines = [m for m in machines if m.site_id == user.site_id]
templates = session.query(ChecklistTemplate).filter_by(active=True).order_by(ChecklistTemplate.position).all()

def save_upload(file, prefix):
    if not file: return None
    path = Path("uploads") / f"{prefix}_{date.today().isoformat()}_{file.name}"
    path.write_bytes(file.getbuffer()); return str(path)

with st.form("audit_form"):
    c1, c2, c3 = st.columns(3)
    machine = c1.selectbox("Máquina", machines, format_func=lambda m: f"{m.machine_code} - {m.name}")
    audit_type = c2.selectbox("Tipo de auditoria", AUDIT_TYPES)
    audit_date = c3.date_input("Data", value=date.today())
    auditor = st.text_input("Auditor responsável", value=user.name)
    participants = st.text_input("Participantes")
    general_notes = st.text_area("Observações gerais")
    st.markdown("### Checklist padrão NR-12")
    item_payload = []
    for t in templates:
        st.markdown(f"**{t.position}. {t.question}** {'🚨 crítico' if t.is_critical else ''}")
        r1, r2, r3 = st.columns([1, 2, 1])
        result = r1.selectbox("Resultado", ITEM_RESULTS, key=f"res_{t.id}")
        comment = r2.text_input("Comentário", key=f"com_{t.id}")
        gen = r3.checkbox("Gera plano de ação?", value=(result == "Não conforme"), key=f"act_{t.id}")
        item_payload.append({"question": t.question, "is_critical": t.is_critical, "result": result, "comment": comment, "generate_action": gen})
    evidence = st.file_uploader("Evidências anexas da auditoria")
    submitted = st.form_submit_button("Salvar auditoria/checklist", disabled=not can_edit(user))
if submitted:
    score, result, critical_nc = calculate_audit_result(item_payload)
    audit = Audit(machine_id=machine.id, site_id=machine.site_id, audit_type=audit_type, audit_date=audit_date, auditor=auditor, participants=participants, result=result, score=score, general_notes=general_notes, evidence_path=save_upload(evidence, "audit"))
    session.add(audit); session.flush()
    for item in item_payload:
        session.add(AuditItem(audit_id=audit.id, **item))
        if item["result"] == "Não conforme" and item["generate_action"]:
            session.add(ActionPlan(origin="Auditoria", machine_id=machine.id, audit_id=audit.id, deviation_description=item["question"] + (f" | {item['comment']}" if item.get("comment") else ""), classification="Crítico" if item["is_critical"] else "Médio", responsible=auditor, responsible_area="EHS", due_date=date.today()+timedelta(days=30), status="Aberta"))
    machine.last_audit_date = audit_date; machine.next_audit_date = audit_date + timedelta(days=180); machine.nr12_status = result
    update_machine_suggestion(session, machine, user.name); session.commit(); st.success(f"Auditoria salva: {score}% - {result}. Ações geradas para itens não conformes marcados."); st.rerun()

st.subheader("Histórico de auditorias")
audits = session.query(Audit).join(Machine).order_by(Audit.audit_date.desc()).all()
if user.role != "Admin Corporativo": audits = [a for a in audits if a.site_id == user.site_id]
st.dataframe([{"ID": a.id, "Site": a.site.code, "Máquina": a.machine.machine_code, "Tipo": a.audit_type, "Data": a.audit_date, "Auditor": a.auditor, "Resultado": a.result, "Pontuação": a.score, "Itens": len(a.items)} for a in audits], use_container_width=True, hide_index=True)
session.close()
