from __future__ import annotations

from datetime import date
import pandas as pd
import streamlit as st
from sqlalchemy.exc import IntegrityError
from utils.theme import apply_nr12_theme, page_header
from auth import can_edit, require_login
from database import get_session, init_db
from models import Machine, Site
from utils.calculations import machines_df, update_machine_suggestion
from utils.exports import export_inventory_excel
from utils.validations import CRITICALITIES, MACHINE_STATUS

st.set_page_config(page_title="Inventário", page_icon="🏭", layout="wide")
apply_nr12_theme()
init_db(); session = get_session(); user = require_login(session)
if not user: st.stop()
page_header("🏭 Inventário de Máquinas e Equipamentos", "Cadastro, consulta, importação e exportação do parque instalado.")

sites = session.query(Site).order_by(Site.code).all(); allowed = sites if user.role == "Admin Corporativo" else [user.site]
site_map = {s.code: s for s in allowed}

def machine_form(machine: Machine | None = None):
    with st.form("machine_form"):
        c1, c2, c3 = st.columns(3)
        code = c1.text_input("ID da máquina", value=getattr(machine, "machine_code", ""))
        site_code = c2.selectbox("Site", list(site_map), index=list(site_map).index(machine.site.code) if machine and machine.site.code in site_map else 0)
        area = c3.text_input("Área / setor", value=getattr(machine, "area", ""))
        c4, c5, c6 = st.columns(3)
        line = c4.text_input("Linha / processo", value=getattr(machine, "line_process", "") or "")
        name = c5.text_input("Nome da máquina", value=getattr(machine, "name", "") or "")
        manufacturer = c6.text_input("Fabricante", value=getattr(machine, "manufacturer", "") or "")
        c7, c8, c9 = st.columns(3)
        model = c7.text_input("Modelo", value=getattr(machine, "model", "") or "")
        serial = c8.text_input("Número de série", value=getattr(machine, "serial_number", "") or "")
        year = c9.number_input("Ano de fabricação", min_value=1900, max_value=2100, value=getattr(machine, "manufacturing_year", None) or 2020)
        c10, c11, c12 = st.columns(3)
        equip_type = c10.text_input("Tipo de equipamento", value=getattr(machine, "equipment_type", "") or "")
        owner = c11.text_input("Responsável da área", value=getattr(machine, "area_owner", "") or "")
        criticality = c12.selectbox("Criticidade", CRITICALITIES, index=CRITICALITIES.index(machine.criticality) if machine and machine.criticality in CRITICALITIES else 1)
        c13, c14, c15 = st.columns(3)
        status = c13.selectbox("Status NR-12", MACHINE_STATUS, index=MACHINE_STATUS.index(machine.nr12_status) if machine and machine.nr12_status in MACHINE_STATUS else 3)
        adequacy = c14.date_input("Data da última adequação", value=getattr(machine, "last_nr12_adequacy_date", None) or date.today())
        last_audit = c15.date_input("Data da última auditoria", value=getattr(machine, "last_audit_date", None) or date.today())
        next_audit = st.date_input("Próxima auditoria prevista", value=getattr(machine, "next_audit_date", None) or date.today())
        b1, b2, b3, b4, b5 = st.columns(5)
        has_report = b1.checkbox("Possui laudo NR-12?", value=getattr(machine, "has_nr12_report", False))
        has_art = b2.checkbox("Possui ART?", value=getattr(machine, "has_art", False))
        has_risk = b3.checkbox("Possui apreciação de risco?", value=getattr(machine, "has_risk_assessment", False))
        has_manual = b4.checkbox("Manual atualizado?", value=getattr(machine, "has_updated_manual", False))
        has_training = b5.checkbox("Treinamento registrado?", value=getattr(machine, "has_training", False))
        notes = st.text_area("Observações", value=getattr(machine, "notes", "") or "")
        submitted = st.form_submit_button("Salvar", disabled=not can_edit(user))
    if submitted:
        code = code.strip()
        area = area.strip()
        name = name.strip()
        line = line.strip()
        manufacturer = manufacturer.strip()
        model = model.strip()
        serial = serial.strip()
        equip_type = equip_type.strip()
        owner = owner.strip()
        notes = notes.strip()
        if not code or not area or not name:
            st.error("ID, área e nome da máquina são obrigatórios."); return
        existing = session.query(Machine).filter_by(machine_code=code).first()
        if existing and (machine is None or existing.id != machine.id):
            st.error(f"Já existe uma máquina cadastrada com o ID {code}. Selecione essa máquina para editar ou use outro ID."); return
        m = machine or Machine(machine_code=code, site_id=site_map[site_code].id, area=area, name=name)
        m.machine_code, m.site_id, m.area, m.line_process, m.name = code, site_map[site_code].id, area, line, name
        m.manufacturer, m.model, m.serial_number, m.manufacturing_year = manufacturer, model, serial, int(year)
        m.equipment_type, m.area_owner, m.criticality, m.nr12_status = equip_type, owner, criticality, status
        m.last_nr12_adequacy_date, m.last_audit_date, m.next_audit_date = adequacy, last_audit, next_audit
        m.has_nr12_report, m.has_art, m.has_risk_assessment, m.has_updated_manual, m.has_training = has_report, has_art, has_risk, has_manual, has_training
        m.notes = notes
        try:
            session.add(m)
            session.flush()
            update_machine_suggestion(session, m, user.name)
            session.commit()
        except IntegrityError:
            session.rollback()
            st.error("Não foi possível salvar: já existe um registro com esses dados ou algum campo obrigatório está inválido.")
            return
        st.success("Máquina salva."); st.rerun()

tab1, tab2, tab3 = st.tabs(["Consultar", "Cadastrar/Editar", "Importar Excel"])
with tab1:
    df = machines_df(session)
    if not df.empty:
        if user.role != "Admin Corporativo": df = df[df["Site"] == user.site.code]
        c1, c2, c3, c4 = st.columns(4)
        sf = c1.multiselect("Site", sorted(df["Site"].unique()))
        af = c2.multiselect("Área", sorted(df["Área"].dropna().unique()))
        stf = c3.multiselect("Status", MACHINE_STATUS)
        cf = c4.multiselect("Criticidade", CRITICALITIES)
        due = st.checkbox("Somente auditoria vencida")
        f = df.copy()
        if sf: f = f[f["Site"].isin(sf)]
        if af: f = f[f["Área"].isin(af)]
        if stf: f = f[f["Status NR-12"].isin(stf)]
        if cf: f = f[f["Criticidade"].isin(cf)]
        if due: f = f[pd.to_datetime(f["Próxima auditoria"]).dt.date < date.today()]
        st.dataframe(f, use_container_width=True, hide_index=True)
        st.download_button("Exportar inventário Excel", export_inventory_excel(session), "inventario_nr12.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
with tab2:
    machines = session.query(Machine).order_by(Machine.machine_code).all()
    if user.role != "Admin Corporativo": machines = [m for m in machines if m.site_id == user.site_id]
    choice = st.selectbox("Editar máquina existente (opcional)", [None] + machines, format_func=lambda m: "Nova máquina" if m is None else f"{m.machine_code} - {m.name}")
    machine_form(choice)
    if choice and st.button("Excluir máquina", disabled=not can_edit(user)):
        session.delete(choice); session.commit(); st.success("Máquina excluída."); st.rerun()
with tab3:
    up = st.file_uploader("Planilha com colunas Código, Site, Área, Máquina, Criticidade, Status NR-12", type=["xlsx"])
    if up and st.button("Importar", disabled=not can_edit(user)):
        imp = pd.read_excel(up); count = 0
        for _, r in imp.iterrows():
            site = session.query(Site).filter_by(code=str(r.get("Site")).strip()).first()
            if not site or (user.role != "Admin Corporativo" and site.id != user.site_id): continue
            m = session.query(Machine).filter_by(machine_code=str(r.get("Código")).strip()).first() or Machine(machine_code=str(r.get("Código")).strip(), site_id=site.id, area="", name="")
            m.site_id=site.id; m.area=str(r.get("Área", "")); m.name=str(r.get("Máquina", "")); m.criticality=str(r.get("Criticidade", "Média")); m.nr12_status=str(r.get("Status NR-12", "Em adequação"));
            session.add(m); count += 1
        session.commit(); st.success(f"{count} máquinas importadas/atualizadas.")
session.close()
