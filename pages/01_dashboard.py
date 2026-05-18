from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st
from utils.theme import apply_nr12_theme, page_header
from auth import require_login
from database import get_session, init_db
from models import ActionPlan, Audit, Document, Machine, Site
from utils.calculations import dashboard_kpis, document_status, machines_df, update_machine_suggestion
from utils.validations import CRITICALITIES, MACHINE_STATUS

st.set_page_config(page_title="Dashboard NR-12", page_icon="📊", layout="wide")
apply_nr12_theme()
init_db(); session = get_session(); user = require_login(session)
if not user: st.stop()

page_header("📊 Dashboard NR-12 Corporativo", "Indicadores consolidados, alertas críticos e visão por site.")
for m in session.query(Machine).all():
    update_machine_suggestion(session, m, user.name)
session.commit()

sites = session.query(Site).order_by(Site.code).all()
allowed = sites if user.role == "Admin Corporativo" else [user.site]
with st.sidebar:
    site_codes = st.multiselect("Site", [s.code for s in allowed], default=[s.code for s in allowed])
    status_filter = st.multiselect("Status", MACHINE_STATUS)
    crit_filter = st.multiselect("Criticidade", CRITICALITIES)

q = session.query(Machine).join(Site).filter(Site.code.in_(site_codes))
if status_filter: q = q.filter(Machine.nr12_status.in_(status_filter))
if crit_filter: q = q.filter(Machine.criticality.in_(crit_filter))
filtered_ids = [m.id for m in q.all()]

k = dashboard_kpis(session)
cols = st.columns(5)
for col, label, key in zip(cols, ["Máquinas", "Conformes", "Com ressalvas", "Não conformes", "Em adequação"], ["total_machines", "conformes", "ressalvas", "nao_conformes", "em_adequacao"]):
    col.metric(label, k[key])
cols = st.columns(5)
for col, label, key in zip(cols, ["Ações abertas", "Ações vencidas", "Ações críticas", "Auditorias vencidas", "Docs vencidos"], ["acoes_abertas", "acoes_vencidas", "acoes_criticas", "auditorias_vencidas", "documentos_vencidos"]):
    col.metric(label, k[key])
cols = st.columns(5)
for col, label, key in zip(cols, ["Sem laudo", "Sem ART", "Sem apreciação", "Mudanças abertas", "Mudanças críticas"], ["sem_laudo", "sem_art", "sem_apreciacao", "mudancas_abertas", "mudancas_criticas_sem_validacao"]):
    col.metric(label, k[key])

if k["acoes_vencidas"] or k["mudancas_criticas_sem_validacao"]:
    st.error("Existem ações vencidas ou mudanças críticas sem validação que podem comprometer a sustentação NR-12.")

mdf = machines_df(session)
if not mdf.empty:
    mdf = mdf[mdf["ID"].isin(filtered_ids)] if filtered_ids else mdf.iloc[0:0]
    c1, c2 = st.columns(2)
    if not mdf.empty:
        c1.plotly_chart(px.histogram(mdf, x="Site", color="Status NR-12", barmode="group", title="Status NR-12 por site"), use_container_width=True)
        area = mdf.groupby(["Área", "Status NR-12"], as_index=False).size()
        c2.plotly_chart(px.bar(area, x="Área", y="size", color="Status NR-12", title="Conformidade por área"), use_container_width=True)

actions = session.query(ActionPlan).join(Machine).filter(ActionPlan.machine_id.in_(filtered_ids)).all() if filtered_ids else []
adf = pd.DataFrame([{"Status": a.status, "Classificação": a.classification, "Máquina": a.machine.machine_code, "Prazo": a.due_date} for a in actions])
if not adf.empty:
    c3, c4 = st.columns(2)
    c3.plotly_chart(px.pie(adf, names="Status", title="Ações por status"), use_container_width=True)
    c4.plotly_chart(px.bar(adf.groupby("Classificação", as_index=False).size(), x="Classificação", y="size", title="Ações por criticidade", text_auto=True), use_container_width=True)

audf = pd.DataFrame([{"Mês": a.audit_date.strftime("%Y-%m"), "Resultado": a.result} for a in session.query(Audit).filter(Audit.machine_id.in_(filtered_ids)).all()]) if filtered_ids else pd.DataFrame()
if not audf.empty:
    st.plotly_chart(px.histogram(audf, x="Mês", color="Resultado", title="Auditorias por mês"), use_container_width=True)

docs = session.query(Document).filter(Document.machine_id.in_(filtered_ids)).all() if filtered_ids else []
ddf = pd.DataFrame([{"Tipo": d.document_type, "Status": document_status(d.expiry_date, d.status)} for d in docs])
if not ddf.empty:
    overdue = ddf[ddf["Status"] == "Vencido"].groupby("Tipo", as_index=False).size()
    if not overdue.empty:
        st.plotly_chart(px.bar(overdue, x="Tipo", y="size", title="Documentos vencidos por tipo", text_auto=True), use_container_width=True)

rank = mdf.assign(Peso=mdf["Criticidade"].map({"Alta": 3, "Média": 2, "Baixa": 1}).fillna(1)).sort_values(["Peso", "Status NR-12"], ascending=False).head(10) if not mdf.empty else pd.DataFrame()
st.subheader("Ranking de máquinas críticas")
st.dataframe(rank, use_container_width=True, hide_index=True)
session.close()
