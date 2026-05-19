from __future__ import annotations

from datetime import date
from pathlib import Path
import mimetypes
import streamlit as st
from utils.theme import apply_nr12_theme, page_header
from auth import can_edit, require_login
from database import get_session, init_db
from models import Document, Machine
from utils.calculations import document_status, update_machine_suggestion
from utils.exports import export_documents_excel
from utils.validations import DOCUMENT_STATUS, DOCUMENT_TYPES

st.set_page_config(page_title="Documentos NR-12", page_icon="📄", layout="wide")
apply_nr12_theme()
init_db(); session = get_session(); user = require_login(session)
if not user: st.stop()
page_header("📄 Documentação Legal e Técnica NR-12", "Controle de documentos obrigatórios, validade e evidências por máquina.")

machines_query = session.query(Machine).order_by(Machine.machine_code)
if user.role != "Admin Corporativo":
    machines_query = machines_query.filter(Machine.site_id == user.site_id)
machine_options = [(m.id, m.machine_code, m.name) for m in machines_query.all()]
machine_labels = {machine_id: f"{code} - {name}" for machine_id, code, name in machine_options}
if not machine_options:
    st.warning("Cadastre uma máquina antes de inserir documentos."); st.stop()

def save_upload(file):
    if not file: return None
    uploads_dir = Path("uploads")
    uploads_dir.mkdir(exist_ok=True)
    path = uploads_dir / f"doc_{date.today().isoformat()}_{file.name}"
    path.write_bytes(file.getbuffer())
    return str(path)

def attachment_path(doc: Document) -> Path | None:
    return Path(doc.file_path) if doc.file_path else None

def attachment_label(doc: Document) -> str:
    path = attachment_path(doc)
    file_name = path.name if path else "sem arquivo"
    return f"#{doc.id} {doc.machine.machine_code} - {doc.document_type} - {file_name}"

with st.expander("Cadastrar documento", expanded=True):
    with st.form("doc_form"):
        machine_id = st.selectbox("Máquina vinculada", [machine_id for machine_id, _, _ in machine_options], format_func=lambda mid: machine_labels[mid])
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
            machine = session.get(Machine, machine_id)
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
    rows.append({"ID": d.id, "Site": d.machine.site.code, "Máquina": d.machine.machine_code, "Tipo": d.document_type, "Nome": d.name, "Emissão": d.issue_date, "Validade": d.expiry_date, "Responsável": d.responsible, "Status": d.status, "Anexo": Path(d.file_path).name if d.file_path else "Sem anexo"})
session.commit()
st.dataframe(rows, use_container_width=True, hide_index=True)
st.download_button("Exportar documentos Excel", export_documents_excel(session), "documentos_nr12.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

attached_docs = [d for d in docs if d.file_path]
if attached_docs:
    st.subheader("Baixar documento anexado")
    download_doc_id = st.selectbox("Arquivo", [d.id for d in attached_docs], format_func=lambda did: attachment_label(next(d for d in attached_docs if d.id == did)))
    download_doc = session.get(Document, download_doc_id)
    path = attachment_path(download_doc)
    if path and path.exists():
        mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        st.download_button(
            "Baixar anexo selecionado",
            data=path.read_bytes(),
            file_name=path.name,
            mime=mime_type,
            use_container_width=True,
        )
    else:
        st.error("O registro existe, mas o arquivo anexado não foi encontrado no armazenamento atual do app.")

if docs:
    st.subheader("Excluir documento")
    doc_options = [(d.id, d.machine.machine_code, d.document_type) for d in docs]
    doc_labels = {doc_id: f"#{doc_id} {machine_code} - {document_type}" for doc_id, machine_code, document_type in doc_options}
    doc_id = st.selectbox("Documento", [doc_id for doc_id, _, _ in doc_options], format_func=lambda did: doc_labels[did])
    if st.button("Excluir", disabled=not can_edit(user)):
        doc = session.get(Document, doc_id)
        machine = session.get(Machine, doc.machine_id)
        session.delete(doc); session.flush(); update_machine_suggestion(session, machine, user.name); session.commit(); st.success("Documento excluído."); st.rerun()
session.close()
