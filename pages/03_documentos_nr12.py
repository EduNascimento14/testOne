from __future__ import annotations

from datetime import date
from pathlib import Path
import streamlit as st
from auth import can_edit, require_login
from database import get_session, init_db
from models import Document, Machine
from utils.calculations import document_status, update_machine_suggestion
from utils.exports import export_documents_excel
from utils.validations import DOCUMENT_STATUS, DOCUMENT_TYPES

st.set_page_config(page_title="Documentos NR-12", page_icon="📄", layout="wide")
init_db(); session = get_session(); user = require_login(session)
if not user: st.stop()
st.title("📄 Documentação Legal e Técnica NR-12")

machines = session.query(Machine).order_by(Machine.machine_code).all()
if user.role != "Admin Corporativo": machines = [m for m in machines if m.site_id == user.site_id]
if not machines:
    st.warning("Cadastre uma máquina antes de inserir documentos."); st.stop()

def save_upload(file):
    if not file: return None
    path = Path("uploads") / f"doc_{date.today().isoformat()}_{file.name}"
    path.write_bytes(file.getbuffer())
    return str(path)

with st.expander("Cadastrar documento", expanded=True):
    with st.form("doc_form"):
        machine = st.selectbox("Máquina vinculada", machines, format_func=lambda m: f"{m.machine_code} - {m.name}")
        c1, c2 = st.columns(2)
        dtype = c1.selectbox("Tipo de documento", DOCUMENT_TYPES)
        name = c2.text_input("Nome do documento")
        c3, c4, c5 = st.columns(3)
        issue = c3.date_input("Data de emissão", value=date.today())
        has_expiry = c4.checkbox("Possui validade?", value=False)
        expiry = c5.date_input("Data de validade", value=date.today()) if has_expiry else None
        responsible = st.text_input("Responsável")
        status = st.selectbox("Status informado", DOCUMENT_STATUS)
        uploaded = st.file_uploader("Upload do arquivo")
        notes = st.text_area("Observações")
        if st.form_submit_button("Salvar documento", disabled=not can_edit(user)):
            file_path = save_upload(uploaded)
            calc = document_status(expiry, status)
            doc = Document(machine_id=machine.id, document_type=dtype, name=name or dtype, issue_date=issue, expiry_date=expiry, responsible=responsible, status=calc, file_path=file_path, notes=notes)
            if dtype == "Laudo NR-12": machine.has_nr12_report = calc != "Ausente"
            if dtype == "ART": machine.has_art = calc != "Ausente"
            if dtype == "Apreciação de risco": machine.has_risk_assessment = calc != "Ausente"
            session.add(doc); session.flush(); update_machine_suggestion(session, machine, user.name); session.commit(); st.success("Documento salvo."); st.rerun()

docs = session.query(Document).join(Machine).all()
if user.role != "Admin Corporativo": docs = [d for d in docs if d.machine.site_id == user.site_id]
rows = []
for d in docs:
    d.status = document_status(d.expiry_date, d.status)
    rows.append({"ID": d.id, "Site": d.machine.site.code, "Máquina": d.machine.machine_code, "Tipo": d.document_type, "Nome": d.name, "Emissão": d.issue_date, "Validade": d.expiry_date, "Responsável": d.responsible, "Status": d.status, "Arquivo": d.file_path})
session.commit()
st.dataframe(rows, use_container_width=True, hide_index=True)
st.download_button("Exportar documentos Excel", export_documents_excel(session), "documentos_nr12.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

if docs:
    st.subheader("Excluir documento")
    doc = st.selectbox("Documento", docs, format_func=lambda d: f"#{d.id} {d.machine.machine_code} - {d.document_type}")
    if st.button("Excluir", disabled=not can_edit(user)):
        machine = doc.machine; session.delete(doc); session.flush(); update_machine_suggestion(session, machine, user.name); session.commit(); st.success("Documento excluído."); st.rerun()
session.close()
