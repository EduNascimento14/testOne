from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from audit_app.constants import CHECKLIST_BASE, CRITICIDADES, PRIORIDADES, STATUS_AUDITORIA, STATUS_CONFORMIDADE, STATUS_PAC, TIPOS_ACHADO
from audit_app.models import Achado, Auditoria, Diretiva, Requisito, RespostaChecklist, Site, Usuario
from audit_app.seed import ensure_auditoria_checklist, logical_requisito_codes, seed_base, validate_seed
from audit_app.services import achados_df, conformidade_percentual, criar_auditoria, export_checklist_excel, export_plano_acao_excel, export_relatorio_pdf, maturidade_media, pac_consolidado_df, pontuacao_por, respostas_df, salvar_respostas, salvar_upload_ehs, to_excel_bytes
from audit_app.ui import can_admin, can_edit, header, is_global_user, kpi_card, section, select_auditoria, visible_site_ids


def can_edit_audit(user, auditoria=None):
    if not can_edit(user):
        return False
    if is_global_user(user):
        return True
    return bool(user and user.perfil == "EHS_Local" and (auditoria is None or user.site_id == auditoria.site_auditado_id))


def page_dashboard_ehs(session, user):
    header("Indicadores EHS Directives", "Conformidade, maturidade e PAC de auditorias cruzadas.")
    site_ids = visible_site_ids(session, user)
    df = respostas_df(session, site_ids=site_ids)
    ach = achados_df(session, site_ids=site_ids)
    q = session.query(Auditoria)
    if not is_global_user(user):
        q = q.filter(Auditoria.site_auditado_id.in_(site_ids))
    metrics = [("Planejadas", q.filter_by(status="Planejada").count()), ("Em andamento", q.filter_by(status="Em andamento").count()), ("Concluídas", q.filter_by(status="Concluída").count()), ("Conformidade média", f"{conformidade_percentual(df)}%"), ("Maturidade média", maturidade_media(df)), ("PAC aberto", int(ach["status"].isin(["Aberto", "Em andamento", "Vencido"]).sum()) if not ach.empty else 0), ("PAC vencido", int(ach["vencido"].sum()) if not ach.empty else 0), ("NC críticas", int((ach["tipo_desvio"] == "Não conformidade crítica").sum()) if not ach.empty else 0)]
    cols = st.columns(4)
    for idx, (label, value) in enumerate(metrics):
        with cols[idx % 4]:
            kpi_card(label, value)
    if not df.empty:
        c1, c2 = st.columns(2)
        c1.plotly_chart(px.bar(pontuacao_por(df, "site"), x="site", y="conformidade", title="Conformidade por site", text_auto=True, range_y=[0, 100]), use_container_width=True)
        c2.plotly_chart(px.bar(pontuacao_por(df, "diretiva"), x="diretiva", y="conformidade", title="Conformidade por categoria", text_auto=True, range_y=[0, 100]), use_container_width=True)
    if not ach.empty:
        st.dataframe(ach, use_container_width=True, hide_index=True)


def page_planejamento(session, user):
    header("Planejar Auditoria Cruzada", "Cadastre auditorias e gere automaticamente o checklist EHS Directives.")
    site_ids = visible_site_ids(session, user)
    sites = session.query(Site).filter(Site.ativo.is_(True), Site.id.in_(site_ids)).order_by(Site.codigo).all()
    all_sites = session.query(Site).filter_by(ativo=True).order_by(Site.codigo).all()
    if not sites:
        st.error("Não há sites disponíveis para este perfil.")
        return
    c1, c2, c3 = st.columns(3)
    with c1: kpi_card("Sites disponíveis", len(sites))
    with c2: kpi_card("Itens do checklist", session.query(Requisito).filter_by(ativo=True).count())
    with c3: kpi_card("Categorias", len(CHECKLIST_BASE))
    with st.form("nova_auditoria"):
        a, b, c = st.columns(3)
        site_auditado = a.selectbox("Site auditado", sites, format_func=lambda s: s.codigo)
        ciclo = b.text_input("Ciclo", value=f"Ciclo {date.today().year}-1")
        data_planejada = c.date_input("Data planejada", value=date.today())
        with st.expander("Campos opcionais"):
            d, e, f = st.columns(3)
            site_lider = d.selectbox("Site auditor líder", all_sites, index=1 if len(all_sites) > 1 else 0, format_func=lambda s: s.codigo)
            site_apoio = e.selectbox("Site auditor apoio", [None] + all_sites, format_func=lambda s: "Sem apoio" if s is None else s.codigo)
            status = f.selectbox("Status", STATUS_AUDITORIA)
            auditor_lider = st.text_input("Auditor líder", value=user.nome if user else "")
            auditor_apoio = st.text_input("Auditor apoio")
            escopo = st.text_area("Escopo", value="Checklist corporativo de Auditoria Cruzada de EHS Directives.")
            observacoes = st.text_area("Observações")
        submitted = st.form_submit_button("Criar auditoria", type="primary", disabled=not can_edit_audit(user))
    if submitted:
        try:
            aud = criar_auditoria(session, nome=f"Auditoria Cruzada {site_auditado.codigo} - {ciclo}", ano=date.today().year, ciclo=ciclo, site_auditado_id=site_auditado.id, site_auditor_lider_id=site_lider.id, site_auditor_apoio_id=site_apoio.id if site_apoio else None, auditor_lider=auditor_lider, auditor_apoio=auditor_apoio, data_planejada=data_planejada, status=status, escopo=escopo, observacoes=observacoes)
            st.success(f"Auditoria #{aud.id} criada.")
        except ValueError as exc:
            st.error(str(exc))
    rows = [{"ID": a.id, "Nome": a.nome, "Site": a.site_auditado.codigo, "Ciclo": a.ciclo, "Data planejada": a.data_planejada, "Status": a.status} for a in session.query(Auditoria).order_by(Auditoria.id.desc()).all()]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def page_checklist(session, user):
    header("Executar Checklist EHS Directives", "Registre respostas, evidências e PAC por item.")
    auditoria = select_auditoria(session, user)
    if not auditoria:
        return
    ensure_auditoria_checklist(session, auditoria.id)
    editable = can_edit_audit(user, auditoria)
    df = respostas_df(session, auditoria.id)
    if df.empty:
        st.warning("Não há requisitos ativos para esta auditoria.")
        return
    c1, c2, c3 = st.columns(3)
    categoria = c1.selectbox("Categoria", ["Todas"] + sorted(df["diretiva"].dropna().unique().tolist()))
    status = c2.selectbox("Status", ["Todos"] + STATUS_CONFORMIDADE)
    criticidade = c3.selectbox("Criticidade", ["Todas"] + CRITICIDADES)
    filtered = df.copy()
    if categoria != "Todas": filtered = filtered[filtered["diretiva"] == categoria]
    if status != "Todos": filtered = filtered[filtered["status"] == status]
    if criticidade != "Todas": filtered = filtered[filtered["criticidade"] == criticidade]
    cols = ["id", "diretiva", "codigo_requisito", "criticidade", "pergunta", "aplicavel", "status", "nota_maturidade", "evidencia_verificada", "comentario_auditor", "necessita_acao"]
    edited = st.data_editor(filtered[cols], hide_index=True, use_container_width=True, disabled=["id", "diretiva", "codigo_requisito", "criticidade", "pergunta"] if editable else cols, column_config={"status": st.column_config.SelectboxColumn("Status", options=STATUS_CONFORMIDADE)}, key=f"editor_ehs_{auditoria.id}")
    if st.button("Salvar respostas", type="primary", disabled=not editable):
        salvar_respostas(session, edited, user.nome if user else None)
        st.success("Respostas salvas.")
    desvios = edited[(edited["status"].isin(["Não Conforme", "Parcialmente Conforme"])) | (edited["necessita_acao"] == True)]
    if not desvios.empty:
        section("PAC do checklist")
        rid = st.selectbox("Item", desvios["id"].tolist(), format_func=lambda i: f"Resposta #{i}")
        resp = session.get(RespostaChecklist, int(rid))
        with st.form("novo_pac_checklist"):
            tipo = st.selectbox("Tipo de achado", TIPOS_ACHADO)
            descricao = st.text_area("Descrição", value=resp.requisito.pergunta if resp else "")
            acao = st.text_area("Ação corretiva")
            a, b, c = st.columns(3)
            responsavel = a.text_input("Responsável")
            prazo = b.date_input("Prazo", value=date.today())
            prioridade = c.selectbox("Criticidade", PRIORIDADES)
            if st.form_submit_button("Criar PAC", disabled=not editable):
                session.add(Achado(auditoria_id=auditoria.id, requisito_id=resp.requisito_id, site_id=auditoria.site_auditado_id, tipo_achado=tipo, descricao=descricao, acao_corretiva=acao, responsavel=responsavel, prazo=prazo, prioridade=prioridade, status="Aberto"))
                st.success("PAC criado.")


def _render_pac_grid(df):
    if df.empty:
        st.info("Nenhum PAC cadastrado para os filtros atuais.")
        return
    st.dataframe(df, use_container_width=True, hide_index=True)


def page_pac_auditoria(session, user):
    header("PAC de Auditoria Cruzada", "Plano de Ação Corretiva das auditorias EHS Directives.")
    _render_pac_grid(achados_df(session, site_ids=visible_site_ids(session, user)))


def page_pac_consolidado(session, user):
    header("Relatório de PAC", "Visão consolidada de PAC de Auditoria Cruzada e Sustentação NR-12.")
    df = pac_consolidado_df(session, visible_site_ids(session, user))
    _render_pac_grid(df)
    st.download_button("Exportar PAC consolidado Excel", to_excel_bytes({"PAC Consolidado": df}), "pac_consolidado.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def page_relatorios_auditoria(session, user):
    header("Relatórios de Auditoria Cruzada", "Exportações executivas da auditoria EHS Directives.")
    auditoria = select_auditoria(session, user)
    if not auditoria:
        return
    df = respostas_df(session, auditoria.id)
    c1, c2, c3 = st.columns(3)
    with c1: kpi_card("Conformidade", f"{conformidade_percentual(df)}%")
    with c2: kpi_card("Maturidade", maturidade_media(df))
    with c3: kpi_card("PAC", len(achados_df(session, auditoria.id)))
    st.download_button("Checklist de auditoria cruzada em Excel", export_checklist_excel(session, auditoria.id), file_name=f"checklist_auditoria_{auditoria.id}.xlsx")
    st.download_button("Relatório de auditoria cruzada em PDF", export_relatorio_pdf(session, auditoria.id), file_name=f"relatorio_auditoria_{auditoria.id}.pdf")
    st.download_button("PAC de auditoria cruzada em Excel", export_plano_acao_excel(session, auditoria.id), file_name=f"pac_auditoria_{auditoria.id}.xlsx")


def page_base_checklists(session, user):
    header("Bases e Checklists", "Itens incorporados de EHS Directives e Sustentação NR-12.")
    valid = validate_seed(session)
    c1, c2, c3 = st.columns(3)
    with c1: kpi_card("Categorias EHS", valid["categorias"])
    with c2: kpi_card("Itens EHS", valid["requisitos_ativos"])
    with c3: kpi_card("Itens NR-12", valid["itens_nr12"])
    if st.button("Sincronizar bases incorporadas", disabled=not can_admin(user)):
        seed_base(session)
        st.success("Bases sincronizadas.")
    reqs = session.query(Requisito).filter(Requisito.codigo_requisito.in_(logical_requisito_codes())).order_by(Requisito.codigo_requisito).all()
    st.dataframe(pd.DataFrame([{"Código": r.codigo_requisito, "Categoria": r.diretiva.titulo, "Pergunta": r.pergunta, "Criticidade": r.criticidade, "Ativo": r.ativo} for r in reqs]), use_container_width=True, hide_index=True)


def page_usuarios(session, user):
    header("Usuários", "Perfis e vínculo por site.")
    if not can_admin(user):
        st.warning("Acesso restrito ao perfil Admin_LAG.")
        return
    rows = [{"ID": u.id, "Nome": u.nome, "E-mail": u.email, "Perfil": u.perfil, "Site": u.site.codigo if u.site else "Corporativo", "Ativo": u.ativo} for u in session.query(Usuario).order_by(Usuario.nome)]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def page_sites(session, user):
    header("Sites", "Administração das unidades da plataforma.")
    if not can_admin(user):
        st.warning("Acesso restrito ao perfil Admin_LAG.")
        return
    rows = [{"ID": s.id, "Código": s.codigo, "Nome": s.nome, "Ativo": s.ativo} for s in session.query(Site).order_by(Site.codigo)]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
