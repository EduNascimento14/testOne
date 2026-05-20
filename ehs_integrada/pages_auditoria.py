from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from ehs_integrada.exports import export_ehs_audit_pdf, export_ehs_checklist_excel, export_ehs_pac_excel
from ehs_integrada.models import EHSAuditoria, EHSIndicadorDiretiva, EHSPAC, EHSRequisito, EHSResposta, Site, Usuario
from ehs_integrada.services import apply_ehs_respostas, create_ehs_auditoria, ehs_kpis, ehs_pacs_df, ehs_respostas_df, site_options
from ehs_integrada.ui import empty_state, header, kpi_card
from ehs_integrada.validations import PERFIS, STATUS_AUDITORIA, STATUS_CONFORMIDADE_EHS


def _site_filter(session, user):
    sites = site_options(session, user)
    labels = ["Todos"] + [s.codigo for s in sites] if user.perfil == "Admin_LAG" else [s.codigo for s in sites]
    selected = st.selectbox("Site", labels)
    if selected == "Todos":
        return None
    return [next(s.id for s in sites if s.codigo == selected)]


def page_dashboard_auditoria(session, user):
    header("Dashboard Auditoria Cruzada", "Resultado executivo das auditorias de EHS Directives e seus PACs.")
    site_ids = _site_filter(session, user)
    kpis = ehs_kpis(session, site_ids)
    cols = st.columns(5)
    with cols[0]: kpi_card("Planejadas", kpis["planejadas"])
    with cols[1]: kpi_card("Em andamento", kpis["andamento"])
    with cols[2]: kpi_card("Concluídas", kpis["concluidas"])
    with cols[3]: kpi_card("Conformidade", f"{kpis['conformidade']}%")
    with cols[4]: kpi_card("Maturidade", kpis["maturidade"])
    cols = st.columns(4)
    with cols[0]: kpi_card("PACs abertos", kpis["pacs_abertos"])
    with cols[1]: kpi_card("PACs vencidos", kpis["pacs_vencidos"])
    with cols[2]: kpi_card("NC críticas", kpis["criticas"])
    with cols[3]: kpi_card("Sites auditados", kpis["sites_auditados"])

    df = ehs_respostas_df(session, site_ids=site_ids)
    pacs = ehs_pacs_df(session, site_ids)
    col1, col2 = st.columns(2)
    with col1:
        if not df.empty:
            by_dir = df[df["Status"] != "Não Aplicável"].groupby("Diretiva")["Status"].apply(lambda s: round(s.map({"Conforme": 1, "Parcialmente Conforme": .5, "Não Conforme": 0}).fillna(0).mean() * 100, 1)).reset_index(name="Conformidade")
            fig = px.bar(by_dir, x="Conformidade", y="Diretiva", orientation="h", title="Resultado por diretiva")
            fig.update_layout(margin=dict(l=10, r=10, t=45, b=10))
            st.plotly_chart(fig, use_container_width=True)
    with col2:
        if not df.empty:
            fig = px.histogram(df, x="Status", color="Status", title="Distribuição dos itens")
            fig.update_layout(showlegend=False, margin=dict(l=10, r=10, t=45, b=10))
            st.plotly_chart(fig, use_container_width=True)

    st.subheader("Principais gaps")
    gaps = df[df["Status"].isin(["Não Conforme", "Parcialmente Conforme"])] if not df.empty else df
    if gaps.empty:
        empty_state("Nenhum gap registrado para os filtros selecionados.")
    else:
        st.dataframe(gaps[["Site", "Auditoria", "Diretiva", "Código", "Status", "Criticidade", "Comentário"]].head(15), use_container_width=True, hide_index=True)
    if not pacs.empty:
        st.subheader("PACs vencidos e críticos")
        st.dataframe(pacs[(pacs["Vencido"]) | (pacs["Criticidade"].isin(["Crítico", "Crítica", "Alta"]))].head(12), use_container_width=True, hide_index=True)


def page_planejamento(session, user):
    header("Planejamento de Auditorias", "Cadastro e acompanhamento dos ciclos de auditoria cruzada EHS Directives.")
    sites = site_options(session, user)
    with st.form("planejamento_ehs"):
        c1, c2, c3 = st.columns(3)
        ano = c1.number_input("Ano", min_value=2020, max_value=2100, value=date.today().year)
        ciclo = c2.text_input("Ciclo", value="Ciclo 1")
        data_planejada = c3.date_input("Data planejada", value=date.today())
        c1, c2, c3 = st.columns(3)
        site_auditado = c1.selectbox("Site auditado", sites, format_func=lambda s: s.codigo)
        site_lider = c2.selectbox("Site auditor líder", sites, format_func=lambda s: s.codigo)
        site_apoio = c3.selectbox("Site auditor apoio", [None] + sites, format_func=lambda s: "-" if s is None else s.codigo)
        with st.expander("Campos opcionais", expanded=False):
            auditor_lider = st.text_input("Auditor líder", value=user.nome)
            auditor_apoio = st.text_input("Auditor apoio")
            escopo = st.text_area("Escopo", value="Diretrizes EHS corporativas")
            status = st.selectbox("Status", STATUS_AUDITORIA)
            observacoes = st.text_area("Observações")
        salvar = st.form_submit_button("Planejar auditoria")
    if salvar:
        if site_auditado.id == site_lider.id:
            st.warning("O site auditado deve ser diferente do site auditor líder.")
        else:
            aud = create_ehs_auditoria(session, {
                "nome": f"Auditoria Cruzada {site_auditado.codigo} {ano} {ciclo}",
                "ano": int(ano),
                "ciclo": ciclo,
                "site_auditado_id": site_auditado.id,
                "site_auditor_lider_id": site_lider.id,
                "site_auditor_apoio_id": site_apoio.id if site_apoio else None,
                "auditor_lider": auditor_lider,
                "auditor_apoio": auditor_apoio,
                "data_planejada": data_planejada,
                "status": status,
                "escopo": escopo,
                "observacoes": observacoes,
            })
            session.commit()
            st.session_state["ehs_auditoria_id"] = aud.id
            st.success("Auditoria planejada.")
            st.rerun()
    q = session.query(EHSAuditoria, Site).select_from(EHSAuditoria).join(Site, EHSAuditoria.site_auditado_id == Site.id)
    site_ids = None if user.perfil == "Admin_LAG" or user.site_id is None else [user.site_id]
    if site_ids is not None:
        q = q.filter(EHSAuditoria.site_auditado_id.in_(site_ids))
    rows = [{"ID": a.id, "Nome": a.nome, "Ano": a.ano, "Ciclo": a.ciclo, "Site": s.codigo, "Data planejada": a.data_planejada, "Status": a.status, "Auditor líder": a.auditor_lider} for a, s in q.order_by(EHSAuditoria.data_planejada.desc()).all()]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def page_checklist_ehs(session, user):
    header("Execução do Checklist EHS Directives", "Avaliação por requisito, evidências, maturidade e geração de PAC.")
    auditorias = session.query(EHSAuditoria).order_by(EHSAuditoria.data_planejada.desc(), EHSAuditoria.id.desc()).all()
    if not auditorias:
        empty_state("Planeje uma auditoria para executar o checklist.")
        return
    ids = [a.id for a in auditorias]
    current = st.selectbox("Auditoria", ids, index=ids.index(st.session_state.get("ehs_auditoria_id", ids[0])) if st.session_state.get("ehs_auditoria_id") in ids else 0, format_func=lambda aid: f"#{aid} · {session.get(EHSAuditoria, aid).nome}")
    df = ehs_respostas_df(session, auditoria_id=current)
    edited = st.data_editor(
        df[["ID", "Diretiva", "Código", "Pergunta", "Criticidade", "Aplicável", "Status", "Maturidade", "Evidência", "Comentário", "Necessita PAC"]],
        use_container_width=True,
        hide_index=True,
        disabled=["ID", "Diretiva", "Código", "Pergunta", "Criticidade"],
        column_config={
            "Status": st.column_config.SelectboxColumn(options=STATUS_CONFORMIDADE_EHS),
            "Maturidade": st.column_config.NumberColumn(min_value=0, max_value=5, step=1),
        },
    )
    c1, c2, c3 = st.columns(3)
    if c1.button("Salvar checklist"):
        apply_ehs_respostas(session, edited.to_dict("records"))
        session.commit()
        st.success("Checklist salvo.")
        st.rerun()
    if c2.button("Gerar PAC para desvios"):
        auditoria = session.get(EHSAuditoria, current)
        for row in edited.to_dict("records"):
            if row["Status"] in {"Não Conforme", "Parcialmente Conforme"} or row["Necessita PAC"]:
                resp = session.get(EHSResposta, int(row["ID"]))
                exists = session.query(EHSPAC).filter_by(auditoria_id=current, requisito_id=resp.requisito_id).first()
                if not exists:
                    session.add(EHSPAC(auditoria_id=current, site_id=auditoria.site_auditado_id, requisito_id=resp.requisito_id, tipo_achado="Não conformidade" if row["Status"] == "Não Conforme" else "Observação", descricao=row["Pergunta"], evidencia=row["Evidência"], criticidade="Crítica" if row["Criticidade"] == "Crítico" else "Média", responsavel=auditoria.auditor_lider, area_responsavel="EHS", prazo=date.today()))
        session.commit()
        st.success("PACs gerados.")
        st.rerun()
    c3.download_button("Exportar checklist Excel", export_ehs_checklist_excel(session, current), "checklist_ehs.xlsx")


def page_pac_auditoria(session, user):
    header("PAC Auditoria Cruzada", "Plano de Ação Corretiva para achados das auditorias cruzadas.")
    site_ids = _site_filter(session, user)
    auditorias = session.query(EHSAuditoria).all()
    requisitos = session.query(EHSRequisito).all()
    with st.form("novo_pac_ehs"):
        c1, c2, c3 = st.columns(3)
        auditoria = c1.selectbox("Auditoria", auditorias, format_func=lambda a: a.nome) if auditorias else None
        requisito = c2.selectbox("Requisito", [None] + requisitos, format_func=lambda r: "-" if r is None else r.codigo)
        criticidade = c3.selectbox("Criticidade", ["Crítica", "Alta", "Média", "Baixa"])
        tipo = st.text_input("Tipo de achado", value="Não conformidade")
        descricao = st.text_area("Descrição")
        c1, c2, c3 = st.columns(3)
        responsavel = c1.text_input("Responsável")
        area = c2.text_input("Área responsável")
        prazo = c3.date_input("Prazo", value=date.today())
        c1, c2 = st.columns(2)
        risco = c1.text_area("Risco")
        acao = c2.text_area("Ação corretiva")
        criar = st.form_submit_button("Criar PAC")
    if criar and auditoria and descricao:
        session.add(EHSPAC(auditoria_id=auditoria.id, site_id=auditoria.site_auditado_id, requisito_id=requisito.id if requisito else None, tipo_achado=tipo, descricao=descricao, risco=risco, acao_corretiva=acao, responsavel=responsavel, area_responsavel=area, prazo=prazo, criticidade=criticidade, status="Aberto"))
        session.commit()
        st.success("PAC criado.")
        st.rerun()
    df = ehs_pacs_df(session, site_ids)
    with st.expander("Filtros", expanded=False):
        status = st.multiselect("Status", sorted(df["Status"].dropna().unique()) if not df.empty else [])
        somente_vencidos = st.checkbox("Somente vencidos")
    if status and not df.empty:
        df = df[df["Status"].isin(status)]
    if somente_vencidos and not df.empty:
        df = df[df["Vencido"]]
    st.download_button("Exportar PAC Excel", export_ehs_pac_excel(session, site_ids), "pac_auditoria_cruzada.xlsx")
    st.dataframe(df, use_container_width=True, hide_index=True)


def page_base_checklist_ehs(session, user):
    header("Base do Checklist EHS", "Visualização e administração dos requisitos incorporados de EHS Directives.")
    rows = []
    for req, diretiva in (
        session.query(EHSRequisito, EHSIndicadorDiretiva)
        .select_from(EHSRequisito)
        .join(EHSIndicadorDiretiva, EHSRequisito.diretiva_id == EHSIndicadorDiretiva.id)
        .order_by(EHSIndicadorDiretiva.codigo, EHSRequisito.codigo)
    ):
        rows.append({"ID": req.id, "Diretiva": diretiva.titulo, "Código": req.codigo, "Pergunta": req.pergunta, "Criticidade": req.criticidade, "Evidência esperada": req.evidencia_esperada, "Ativo": req.ativo})
    edited = st.data_editor(pd.DataFrame(rows), use_container_width=True, hide_index=True, disabled=["ID", "Diretiva", "Código", "Pergunta"])
    if st.button("Salvar ajustes da base"):
        for row in edited.to_dict("records"):
            req = session.get(EHSRequisito, int(row["ID"]))
            if req:
                req.criticidade = row["Criticidade"]
                req.evidencia_esperada = row["Evidência esperada"]
                req.ativo = bool(row["Ativo"])
        session.commit()
        st.success("Base atualizada.")


def page_relatorios_auditoria(session, user):
    header("Relatórios Auditoria Cruzada", "Exportações de checklist, PAC e relatório executivo em PDF.")
    site_ids = _site_filter(session, user)
    auditorias = session.query(EHSAuditoria).order_by(EHSAuditoria.data_planejada.desc()).all()
    if auditorias:
        auditoria = st.selectbox("Auditoria", auditorias, format_func=lambda a: a.nome)
        c1, c2, c3 = st.columns(3)
        c1.download_button("Checklist Excel", export_ehs_checklist_excel(session, auditoria.id), "checklist_auditoria.xlsx")
        c2.download_button("PAC Excel", export_ehs_pac_excel(session, site_ids), "pac_auditoria.xlsx")
        c3.download_button("Relatório PDF", export_ehs_audit_pdf(session, auditoria.id, site_ids), f"relatorio_auditoria_{auditoria.id}.pdf", mime="application/pdf")
    df = ehs_respostas_df(session, site_ids=site_ids)
    if not df.empty:
        st.subheader("Resultado por site")
        site_result = df[df["Status"] != "Não Aplicável"].groupby("Site")["Status"].apply(lambda s: round(s.map({"Conforme": 1, "Parcialmente Conforme": .5, "Não Conforme": 0}).fillna(0).mean() * 100, 1)).reset_index(name="Conformidade")
        st.dataframe(site_result, use_container_width=True, hide_index=True)


def page_administracao(session, user):
    header("Administração", "Usuários, sites e parâmetros básicos da plataforma integrada.")
    tab_users, tab_sites = st.tabs(["Usuários", "Sites"])
    with tab_users:
        with st.form("novo_usuario"):
            c1, c2, c3 = st.columns(3)
            nome = c1.text_input("Nome")
            email = c2.text_input("Email")
            perfil = c3.selectbox("Perfil", PERFIS)
            sites = session.query(Site).filter_by(ativo=True).order_by(Site.codigo).all()
            site = st.selectbox("Site vinculado", [None] + sites, format_func=lambda s: "-" if s is None else s.codigo)
            if st.form_submit_button("Criar usuário") and nome and email:
                session.add(Usuario(nome=nome, email=email, perfil=perfil, site_id=site.id if site else None, ativo=True))
                session.commit()
                st.success("Usuário criado.")
                st.rerun()
        users = session.query(Usuario).order_by(Usuario.nome).all()
        st.dataframe(pd.DataFrame([{"Nome": u.nome, "Email": u.email, "Perfil": u.perfil, "Site": u.site.codigo if u.site else "Todos", "Ativo": u.ativo} for u in users]), use_container_width=True, hide_index=True)
    with tab_sites:
        with st.form("novo_site"):
            c1, c2 = st.columns(2)
            codigo = c1.text_input("Código")
            nome = c2.text_input("Nome")
            if st.form_submit_button("Criar site") and codigo and nome:
                session.add(Site(codigo=codigo.upper(), nome=nome, ativo=True))
                session.commit()
                st.success("Site criado.")
                st.rerun()
        sites = session.query(Site).order_by(Site.codigo).all()
        st.dataframe(pd.DataFrame([{"Código": s.codigo, "Nome": s.nome, "Ativo": s.ativo} for s in sites]), use_container_width=True, hide_index=True)
