from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
import streamlit as st
from utils.theme import apply_nr12_theme, page_header
from auth import can_edit, require_login
from database import get_session, init_db
from models import ActionPlan, Audit, AuditItem, ChecklistTemplate, Machine
from utils.calculations import calculate_audit_result, update_machine_suggestion
from utils.validations import AUDIT_TYPES, ITEM_RESULTS, audit_periodicity_label

st.set_page_config(page_title="Auditorias", page_icon="✅", layout="wide")
apply_nr12_theme()
init_db(); session = get_session(); user = require_login(session)
if not user: st.stop()
page_header("✅ Auditorias e Inspeções de Sustentação NR-12", "Checklists enxutos por tipo de verificação, pontuação automática e geração de planos de ação.")

machines_query = session.query(Machine).order_by(Machine.machine_code)
if user.role != "Admin Corporativo":
    machines_query = machines_query.filter(Machine.site_id == user.site_id)
machine_options = [(m.id, m.machine_code, m.name, m.criticality) for m in machines_query.all()]
machine_labels = {machine_id: f"{code} - {name}" for machine_id, code, name, _ in machine_options}
machine_criticalities = {machine_id: criticality for machine_id, _, _, criticality in machine_options}
if not machine_options:
    st.warning("Cadastre uma máquina antes de registrar auditorias."); st.stop()

def save_upload(file, prefix):
    if not file: return None
    uploads_dir = Path("uploads")
    uploads_dir.mkdir(exist_ok=True)
    path = uploads_dir / f"{prefix}_{date.today().isoformat()}_{file.name}"
    path.write_bytes(file.getbuffer()); return str(path)

with st.form("audit_form"):
    c1, c2, c3 = st.columns(3)
    machine_id = c1.selectbox("Máquina", [machine_id for machine_id, _, _, _ in machine_options], format_func=lambda mid: machine_labels[mid])
    audit_type = c2.selectbox("Tipo de verificação", AUDIT_TYPES)
    audit_date = c3.date_input("Data", value=date.today())
    st.caption(f"Periodicidade recomendada para criticidade {machine_criticalities[machine_id]}: {audit_periodicity_label(machine_criticalities[machine_id], audit_type)}")
    auditor = st.text_input("Responsável", value=user.name)
    participants = st.text_input("Participantes")
    general_notes = st.text_area("Observações gerais")
    templates = session.query(ChecklistTemplate).filter_by(active=True, audit_type=audit_type).order_by(ChecklistTemplate.position).all()
    if not templates:
        templates = session.query(ChecklistTemplate).filter_by(active=True, audit_type="Auditoria EHS").order_by(ChecklistTemplate.position).all()
    st.markdown("### Checklist aplicável")
    item_payload = []
    for t in templates:
        st.markdown(f"**{t.position}. {t.question}** {'🚨 crítico' if t.is_critical else ''}")
        if t.evidence_expected:
            st.caption(f"Evidência esperada: {t.evidence_expected}")
        r1, r2, r3 = st.columns([1, 2, 1])
        result = r1.selectbox("Resultado", ITEM_RESULTS, key=f"res_{t.id}")
        comment = r2.text_input("Comentário / evidência", key=f"com_{t.id}")
        gen = r3.checkbox("Gera ação?", value=(result == "Não conforme"), key=f"act_{t.id}")
        item_payload.append({"question": t.question, "is_critical": t.is_critical, "result": result, "comment": comment, "generate_action": gen})
    evidence = st.file_uploader("Evidências anexas da verificação")
    submitted = st.form_submit_button("Salvar verificação", disabled=not can_edit(user))
if submitted:
    machine = session.get(Machine, machine_id)
    score, result, critical_nc = calculate_audit_result(item_payload)
    audit = Audit(machine_id=machine.id, site_id=machine.site_id, audit_type=audit_type, audit_date=audit_date, auditor=auditor, participants=participants, result=result, score=score, general_notes=general_notes, evidence_path=save_upload(evidence, "audit"))
    session.add(audit); session.flush()
    for item in item_payload:
        session.add(AuditItem(audit_id=audit.id, **item))
        if item["result"] == "Não conforme" and item["generate_action"]:
            session.add(ActionPlan(origin="Inspeção" if audit_type != "Auditoria EHS" else "Auditoria", machine_id=machine.id, audit_id=audit.id, deviation_description=item["question"] + (f" | {item['comment']}" if item.get("comment") else ""), classification="Crítico" if item["is_critical"] else "Maior", responsible=auditor, responsible_area="EHS" if audit_type == "Auditoria EHS" else "Manutenção", due_date=date.today()+timedelta(days=30), status="Aberta"))
    if audit_type == "Auditoria EHS":
        machine.last_audit_date = audit_date
    machine.next_audit_date = None
    machine.nr12_status = result
    update_machine_suggestion(session, machine, user.name); session.commit(); st.success(f"Verificação salva: {score}% - {result}. Ações geradas para itens não conformes marcados."); st.rerun()

st.subheader("Histórico de verificações")
audits = session.query(Audit).join(Machine).order_by(Audit.audit_date.desc()).all()
if user.role != "Admin Corporativo": audits = [a for a in audits if a.site_id == user.site_id]
st.dataframe([{"ID": a.id, "Site": a.site.code, "Máquina": a.machine.machine_code, "Tipo": a.audit_type, "Data": a.audit_date, "Responsável": a.auditor, "Resultado": a.result, "Pontuação": a.score, "Itens": len(a.items)} for a in audits], use_container_width=True, hide_index=True)
session.close()
