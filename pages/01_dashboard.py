from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st
from utils.theme import apply_nr12_theme, page_header
from auth import require_login
from database import get_session, init_db
from models import ActionPlan, Audit, Document, Machine, Site
from utils.calculations import audit_schedule_df, dashboard_kpis, document_status, machines_df, update_machine_suggestion
from utils.validations import CRITICALITIES, MACHINE_STATUS, SCHEDULED_AUDIT_TYPES

st.set_page_config(page_title="Dashboard NR-12", page_icon="📊", layout="wide")
apply_nr12_theme()
init_db(); session = get_session(); user = require_login(session)
if not user: st.stop()

page_header("📊 Dashboard NR-12 Corporativo", "Sustentação da conformidade, prazos de verificação, desvios críticos e governança por site.")
for m in session.query(Machine).all():
    update_machine_suggestion(session, m, user.name)
session.commit()

sites = session.query(Site).order_by(Site.code).all()
allowed = sites if user.role == "Admin Corporativo" else [user.site]
with st.sidebar:
    site_codes = st.multiselect("Site", [s.code for s in allowed], default=[s.code for s in allowed])
    status_filter = st.multiselect("Status NR-12", MACHINE_STATUS)
    crit_filter = st.multiselect("Criticidade", CRITICALITIES)
    audit_type_filter = st.multiselect("Tipo de verificação", SCHEDULED_AUDIT_TYPES, default=SCHEDULED_AUDIT_TYPES)

q = session.query(Machine).join(Site).filter(Site.code.in_(site_codes))
if status_filter: q = q.filter(Machine.nr12_status.in_(status_filter))
if crit_filter: q = q.filter(Machine.criticality.in_(crit_filter))
filtered_ids = [m.id for m in q.all()]

k = dashboard_kpis(session)
cols = st.columns(6)
for col, label, key in zip(cols, ["Máquinas", "Conformes", "Com observação", "Pendentes", "Bloqueadas", "Em readequação"], ["total_machines", "conformes", "observacao", "pendentes", "bloqueadas", "em_readequacao"]):
    col.metric(label, k[key])
cols = st.columns(6)
for col, label, key in zip(cols, ["Auditorias vencidas", "Próximos 30 dias", "Ações abertas", "Ações vencidas", "Docs vencidos", "MOCs críticas"], ["auditorias_vencidas", "auditorias_30d", "acoes_abertas", "acoes_vencidas", "documentos_vencidos", "mudancas_criticas_sem_validacao"]):
    col.metric(label, k[key])

if k["bloqueadas"] or k["acoes_vencidas"] or k["mudancas_criticas_sem_validacao"]:
    st.error("Há máquinas bloqueadas, ações vencidas ou mudanças críticas sem validação que exigem priorização do Comitê Local NR-12.")
if k["auditorias_vencidas"]:
    st.warning("Existem verificações NR-12 vencidas. Consulte a aba Agenda de Próximas Verificações NR-12.")

mdf = machines_df(session)
if not mdf.empty:
    mdf = mdf[mdf["ID"].isin(filtered_ids)] if filtered_ids else mdf.iloc[0:0]

schedule = audit_schedule_df(session, filtered_ids) if filtered_ids else pd.DataFrame()
if not schedule.empty and audit_type_filter:
    schedule = schedule[schedule["Tipo"].isin(audit_type_filter)]

if not mdf.empty:
    c1, c2 = st.columns(2)
    c1.plotly_chart(px.histogram(mdf, x="Site", color="Status NR-12", barmode="group", title="Status NR-12 por site", text_auto=True), use_container_width=True)
    crit = mdf.groupby(["Criticidade", "Status NR-12"], as_index=False).size()
    c2.plotly_chart(px.bar(crit, x="Criticidade", y="size", color="Status NR-12", title="Status por criticidade", text_auto=True), use_container_width=True)

if not schedule.empty:
    c3, c4 = st.columns(2)
    c3.plotly_chart(px.histogram(schedule, x="Tipo", color="Status do prazo", barmode="group", title="Agenda por tipo de verificação", text_auto=True), use_container_width=True)
    due_by_site = schedule.groupby(["Site", "Status do prazo"], as_index=False).size()
    c4.plotly_chart(px.bar(due_by_site, x="Site", y="size", color="Status do prazo", title="Prazos por site", text_auto=True), use_container_width=True)
    st.subheader("Próximas verificações prioritárias")
    priority = {"Vencida": 0, "Próxima": 1, "Programada": 2}
    agenda = schedule.assign(_ordem=schedule["Status do prazo"].map(priority)).sort_values(["_ordem", "Próxima auditoria"]).drop(columns=["_ordem"]).head(15)
    st.dataframe(agenda, use_container_width=True, hide_index=True)

actions = session.query(ActionPlan).join(Machine).filter(ActionPlan.machine_id.in_(filtered_ids)).all() if filtered_ids else []
adf = pd.DataFrame([{"Status": a.status, "Classificação": a.classification, "Máquina": a.machine.machine_code, "Prazo": a.due_date, "Site": a.machine.site.code} for a in actions])
if not adf.empty:
    c5, c6 = st.columns(2)
    c5.plotly_chart(px.histogram(adf, x="Status", color="Classificação", title="Plano de ação por status e classificação", text_auto=True), use_container_width=True)
    overdue = adf[pd.to_datetime(adf["Prazo"]).dt.date < pd.Timestamp.today().date()] if "Prazo" in adf else pd.DataFrame()
    if not overdue.empty:
        c6.plotly_chart(px.histogram(overdue, x="Site", color="Classificação", title="Ações vencidas por site", text_auto=True), use_container_width=True)

audf = pd.DataFrame([{"Mês": a.audit_date.strftime("%Y-%m"), "Resultado": a.result, "Tipo": a.audit_type} for a in session.query(Audit).filter(Audit.machine_id.in_(filtered_ids)).all()]) if filtered_ids else pd.DataFrame()
if not audf.empty:
    st.plotly_chart(px.histogram(audf, x="Mês", color="Tipo", facet_row="Resultado", title="Histórico de verificações por mês, tipo e resultado"), use_container_width=True)

docs = session.query(Document).filter(Document.machine_id.in_(filtered_ids)).all() if filtered_ids else []
ddf = pd.DataFrame([{"Tipo": d.document_type, "Status": document_status(d.expiry_date, d.status)} for d in docs])
if not ddf.empty:
    doc_status = ddf.groupby(["Tipo", "Status"], as_index=False).size()
    st.plotly_chart(px.bar(doc_status, x="Tipo", y="size", color="Status", title="Prontidão documental por tipo", text_auto=True), use_container_width=True)

rank = mdf.assign(Peso=mdf["Criticidade"].map({"Alta": 3, "Média": 2, "Baixa": 1}).fillna(1)).sort_values(["Peso", "Status NR-12"], ascending=False).head(10) if not mdf.empty else pd.DataFrame()
st.subheader("Máquinas prioritárias")
st.dataframe(rank, use_container_width=True, hide_index=True)
session.close()
