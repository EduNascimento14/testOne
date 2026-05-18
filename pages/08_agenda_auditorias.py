from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st
from utils.theme import apply_nr12_theme, page_header
from auth import require_login
from database import get_session, init_db
from models import Machine, Site
from utils.calculations import audit_schedule_df
from utils.exports import dataframe_to_excel
from utils.validations import CRITICALITIES, SCHEDULED_AUDIT_TYPES

st.set_page_config(page_title="Agenda NR-12", page_icon="📅", layout="wide")
apply_nr12_theme()
init_db(); session = get_session(); user = require_login(session)
if not user: st.stop()
page_header("📅 Agenda de Próximas Verificações NR-12", "Calendário por criticidade para pré-uso, manutenção e auditoria EHS.")

sites = session.query(Site).order_by(Site.code).all()
allowed = sites if user.role == "Admin Corporativo" else [user.site]
with st.sidebar:
    site_codes = st.multiselect("Site", [s.code for s in allowed], default=[s.code for s in allowed])
    audit_types = st.multiselect("Tipo", SCHEDULED_AUDIT_TYPES, default=SCHEDULED_AUDIT_TYPES)
    criticalities = st.multiselect("Criticidade", CRITICALITIES)
    due_status = st.multiselect("Prazo", ["Vencida", "Próxima", "Programada"], default=["Vencida", "Próxima"])

machines = session.query(Machine).join(Site).filter(Site.code.in_(site_codes)).all() if site_codes else []
machine_ids = [m.id for m in machines]
df = audit_schedule_df(session, machine_ids)
if not df.empty:
    if audit_types:
        df = df[df["Tipo"].isin(audit_types)]
    if criticalities:
        df = df[df["Criticidade"].isin(criticalities)]
    if due_status:
        df = df[df["Status do prazo"].isin(due_status)]

if df.empty:
    st.info("Nenhuma verificação encontrada para os filtros selecionados.")
    session.close(); st.stop()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Vencidas", int((df["Status do prazo"] == "Vencida").sum()))
c2.metric("Próximos 30 dias", int((df["Status do prazo"] == "Próxima").sum()))
c3.metric("Programadas", int((df["Status do prazo"] == "Programada").sum()))
c4.metric("Máquinas no filtro", df["ID"].nunique())

priority = {"Vencida": 0, "Próxima": 1, "Programada": 2}
df = df.assign(_ordem=df["Status do prazo"].map(priority)).sort_values(["_ordem", "Próxima auditoria", "Criticidade", "Site"]).drop(columns=["_ordem"])

c5, c6 = st.columns(2)
c5.plotly_chart(px.histogram(df, x="Tipo", color="Status do prazo", barmode="group", title="Verificações por tipo e prazo", text_auto=True), use_container_width=True)
c6.plotly_chart(px.histogram(df, x="Site", color="Status do prazo", barmode="group", title="Carga por site", text_auto=True), use_container_width=True)

heat = df.groupby(["Site", "Tipo", "Status do prazo"], as_index=False).size()
st.plotly_chart(px.bar(heat, x="Site", y="size", color="Tipo", facet_col="Status do prazo", title="Distribuição da agenda por site, tipo e prazo", text_auto=True), use_container_width=True)

st.subheader("Lista priorizada")
st.dataframe(df, use_container_width=True, hide_index=True)
st.download_button("Exportar agenda Excel", dataframe_to_excel(df, "Agenda NR12"), "agenda_auditorias_nr12.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
session.close()
