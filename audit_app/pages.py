from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from audit_app.constants import CHECKLIST_BASE, CRITICIDADES, PRIORIDADES, STATUS_AUDITORIA, STATUS_CONFORMIDADE, STATUS_PAC, TIPOS_ACHADO
from audit_app.models import Achado, Auditoria, Diretiva, Requisito, RespostaChecklist, Site, Usuario
from audit_app.seed import ensure_auditoria_checklist, logical_requisito_codes, seed_base, validate_seed
from audit_app.services import (
    achados_df,
    conformidade_percentual,
    criar_auditoria,
    export_checklist_excel,
    export_plano_acao_excel,
    export_relatorio_pdf,
    maturidade_media,
    pontuacao_por,
    respostas_df,
    salvar_respostas,
    salvar_upload_ehs,
)
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
    metrics = [
        ("Planejadas", q.filter_by(status="Planejada").count()),
        ("Em andamento", q.filter_by(status="Em andamento").count()),
        ("Concluídas", q.filter_by(status="Concluída").count()),
        ("Conformidade média", f"{conformidade_percentual(df)}%"),
        ("Maturidade média", maturidade_media(df)),
        ("PAC aberto", int(ach["status"].isin(["Aberto", "Em andamento", "Vencido"]).sum()) if not ach.empty else 0),
        ("PAC vencido", int(ach["vencido"].sum()) if not ach.empty else 0),
        ("NC críticas", int((ach["tipo_desvio"] == "Não conformidade crítica").sum()) if not ach.empty else 0),
    ]
    cols = st.columns(4)
    for idx, (label, value) in enumerate(metrics):
        with cols[idx % 4]:
            kpi_card(label, value)
    if df.empty:
        st.info("Ainda não há respostas de checklist para os filtros atuais.")
        return
    c1, c2 = st.columns(2)
    c1.plotly_chart(px.bar(pontuacao_por(df, "site"), x="site", y="conformidade", title="Conformidade por site", text_auto=True, range_y=[0, 100], color_discrete_sequence=["#1f4bb8"]), use_container_width=True)
    c2.plotly_chart(px.bar(pontuacao_por(df, "diretiva"), x="diretiva", y="conformidade", title="Conformidade por categoria", text_auto=True, range_y=[0, 100], color_discrete_sequence=["#12263f"]), use_container_width=True)
    if not ach.empty:
        st.plotly_chart(px.bar(ach.groupby(["site", "status"], as_index=False).size(), x="site", y="size", color="status", title="PAC por site e status"), use_container_width=True)


def page_planejamento(session, user):
    header("Planejar Auditoria Cruzada", "Cadastre auditorias e gere automaticamente o checklist EHS Directives.")
    site_ids = visible_site_ids(session, user)
    sites = session.query(Site).filter(Site.ativo.is_(True), Site.id.in_(site_ids)).order_by(Site.codigo).all()
    all_sites = session.query(Site).filter_by(ativo=True).order_by(Site.codigo).all()
    total_reqs = session.query(Requisito).filter_by(ativo=True).count()
    c1, c2, c3 = st.columns(3)
    with c1:
        kpi_card("Sites disponíveis", len(sites))
    with c2:
        kpi_card("Itens do checklist", total_reqs)
    with c3:
        kpi_card("Categorias", len(CHECKLIST_BASE))
    if not sites:
        st.error("Não há sites disponíveis para este perfil.")
        return
    with st.form("nova_auditoria"):
        c1, c2, c3 = st.columns(3)
        site_auditado = c1.selectbox("Site auditado", sites, format_func=lambda s: s.codigo)
        ciclo = c2.text_input("Ciclo", value=f"Ciclo {date.today().year}-1")
        data_planejada = c3.date_input("Data planejada", value=date.today())
        with st.expander("Campos opcionais"):
            c4, c5, c6 = st.columns(3)
            site_lider = c4.selectbox("Site auditor líder", all_sites, index=1 if len(all_sites) > 1 else 0, format_func=lambda s: s.codigo)
            site_apoio = c5.selectbox("Site auditor apoio", [None] + all_sites, format_func=lambda s: "Sem apoio" if s is None else s.codigo)
            status = c6.selectbox("Status", STATUS_AUDITORIA)
            auditor_lider = st.text_input("Auditor líder", value=user.nome if user else "")
            auditor_apoio = st.text_input("Auditor apoio")
            escopo = st.text_area("Escopo", value="Checklist corporativo de Auditoria Cruzada de EHS Directives.", height=70)
            observacoes = st.text_area("Observações", height=70)
        submitted = st.form_submit_button("Criar auditoria", type="primary", disabled=not can_edit_audit(user))
    if submitted:
        try:
            auditoria = criar_auditoria(
                session,
                nome=f"Auditoria Cruzada {site_auditado.codigo} - {ciclo}",
                ano=date.today().year,
                ciclo=ciclo,
                site_auditado_id=site_auditado.id,
                site_auditor_lider_id=site_lider.id,
                site_auditor_apoio_id=site_apoio.id if site_apoio else None,
                auditor_lider=auditor_lider,
                auditor_apoio=auditor_apoio,
                data_planejada=data_planejada,
                status=status,
                escopo=escopo,
                observacoes=observacoes,
            )
            st.success(f"Auditoria #{auditoria.id} criada com {total_reqs} itens.")
        except ValueError as exc:
            st.error(str(exc))
    section("Auditorias cadastradas")
    q = session.query(Auditoria).order_by(Auditoria.id.desc())
    if not is_global_user(user):
        q = q.filter(Auditoria.site_auditado_id.in_(site_ids))
    rows = [{"ID": a.id, "Nome": a.nome, "Site": a.site_auditado.codigo, "Ciclo": a.ciclo, "Data planejada": a.data_planejada, "Status": a.status} for a in q.all()]
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
    section("Filtros")
    c1, c2, c3 = st.columns(3)
    categoria = c1.selectbox("Categoria", ["Todas"] + sorted(df["diretiva"].dropna().unique().tolist()))
    status = c2.selectbox("Status", ["Todos"] + STATUS_CONFORMIDADE)
    criticidade = c3.selectbox("Criticidade", ["Todas"] + CRITICIDADES)
    filtered = df.copy()
    if categoria != "Todas":
        filtered = filtered[filtered["diretiva"] == categoria]
    if status != "Todos":
        filtered = filtered[filtered["status"] == status]
    if criticidade != "Todas":
        filtered = filtered[filtered["criticidade"] == criticidade]
    section("Checklist")
    display_cols = ["id", "diretiva", "codigo_requisito", "criticidade", "pergunta", "aplicavel", "status", "nota_maturidade", "evidencia_verificada", "comentario_auditor", "necessita_acao"]
    edited = st.data_editor(
        filtered[display_cols],
        hide_index=True,
        use_container_width=True,
        disabled=["id", "diretiva", "codigo_requisito", "criticidade", "pergunta"] if editable else display_cols,
        column_config={
            "status": st.column_config.SelectboxColumn("Status", options=STATUS_CONFORMIDADE),
            "nota_maturidade": st.column_config.NumberColumn("Maturidade", min_value=0, max_value=5, step=1),
            "necessita_acao": st.column_config.CheckboxColumn("Gerar PAC?"),
            "evidencia_verificada": st.column_config.TextColumn("Evidência"),
            "comentario_auditor": st.column_config.TextColumn("Observação"),
        },
        key=f"editor_ehs_{auditoria.id}",
    )
    if st.button("Salvar respostas", type="primary", disabled=not editable):
        salvar_respostas(session, edited, user.nome if user else None)
        st.success("Respostas salvas.")
    desvios = edited[(edited["status"].isin(["Não Conforme", "Parcialmente Conforme"])) | (edited["necessita_acao"] == True)]
    section("PAC do checklist")
    if desvios.empty:
        st.info("Nenhum item filtrado exige PAC.")
    else:
        c1, c2 = st.columns([1, 2])
        selected_id = c1.selectbox("Item", desvios["id"].tolist(), format_func=lambda rid: f"Resposta #{rid}")
        resp = session.get(RespostaChecklist, int(selected_id))
        with c2.form("novo_pac_checklist"):
            tipo = st.selectbox("Tipo de achado", TIPOS_ACHADO)
            descricao = st.text_area("Descrição", value=resp.requisito.pergunta if resp else "")
            evidencia = st.text_area("Evidência")
            acao = st.text_area("Ação corretiva")
            c3, c4, c5 = st.columns(3)
            responsavel = c3.text_input("Responsável")
            prazo = c4.date_input("Prazo", value=date.today())
            prioridade = c5.selectbox("Criticidade", PRIORIDADES)
            if st.form_submit_button("Criar PAC", disabled=not editable):
                session.add(Achado(auditoria_id=auditoria.id, requisito_id=resp.requisito_id, site_id=auditoria.site_auditado_id, tipo_achado=tipo, descricao=descricao, evidencia=evidencia, acao_corretiva=acao, responsavel=responsavel, prazo=prazo, prioridade=prioridade, status="Aberto"))
                st.success("PAC criado.")
    with st.expander("Anexar evidência"):
        reqs = session.query(Requisito).filter_by(ativo=True).order_by(Requisito.codigo_requisito).all()
        req_id = st.selectbox("Item", [r.id for r in reqs], format_func=lambda rid: next(r for r in reqs if r.id == rid).codigo_requisito)
        uploaded = st.file_uploader("Arquivo de evidência")
        if uploaded and st.button("Salvar evidência", disabled=not editable):
            salvar_upload_ehs(uploaded, auditoria.id, req_id, None, user.nome if user else None, session)
            st.success("Evidência salva.")


def page_pac_auditoria(session, user):
    header("PAC de Auditoria Cruzada", "Plano de Ação Corretiva das auditorias EHS Directives.")
    site_ids = visible_site_ids(session, user)
    df = achados_df(session, site_ids=site_ids)
    _render_pac_grid(df)
    registros = session.query(Achado).order_by(Achado.id.desc())
    if not is_global_user(user):
        registros = registros.filter(Achado.site_id.in_(site_ids))
    registros = registros.all()
    if not registros:
        return
    section("Editar PAC")
    labels = {a.id: f"#{a.id} · {a.tipo_achado} · {a.status}" for a in registros}
    achado = session.get(Achado, st.selectbox("Registro", list(labels), format_func=lambda item_id: labels[item_id]))
    with st.form("editar_pac_auditoria"):
        c1, c2, c3 = st.columns(3)
        status = c1.selectbox("Status", STATUS_PAC, index=STATUS_PAC.index(achado.status) if achado.status in STATUS_PAC else 0)
        prazo = c2.date_input("Prazo", value=achado.prazo or date.today())
        prioridade = c3.selectbox("Criticidade", PRIORIDADES, index=PRIORIDADES.index(achado.prioridade) if achado.prioridade in PRIORIDADES else 2)
        responsavel = st.text_input("Responsável", value=achado.responsavel or "")
        acao_corretiva = st.text_area("Ação corretiva", value=achado.acao_corretiva or "")
        evidencia_conclusao = st.text_area("Evidência de conclusão", value=achado.evidencia_conclusao or "")
        validacao_ehs = st.selectbox("Validação EHS", ["Pendente", "Aprovada", "Reprovada", "Não aplicável"], index=0)
        eficacia = st.text_area("Verificação de eficácia", value=achado.verificacao_eficacia or "")
        if st.form_submit_button("Salvar PAC", type="primary", disabled=not can_edit(user)):
            achado.status = status
            achado.prazo = prazo
            achado.prioridade = prioridade
            achado.responsavel = responsavel
            achado.acao_corretiva = acao_corretiva
            achado.evidencia_conclusao = evidencia_conclusao
            achado.validacao_ehs = validacao_ehs
            achado.verificacao_eficacia = eficacia
            achado.data_conclusao = date.today() if status == "Concluído" else None
            st.success("PAC atualizado.")


def _render_pac_grid(df):
    if df.empty:
        st.info("Nenhum PAC cadastrado para os filtros atuais.")
        return
    c1, c2, c3, c4, c5 = st.columns(5)
    site = c1.selectbox("Site", ["Todos"] + sorted(df["site"].dropna().unique().tolist()))
    origem = c2.selectbox("Origem", ["Todos"] + sorted(df["origem"].dropna().unique().tolist()))
    status = c3.selectbox("Status", ["Todos"] + sorted(df["status"].dropna().unique().tolist()))
    criticidade = c4.selectbox("Criticidade", ["Todos"] + sorted(df["criticidade"].dropna().unique().tolist()))
    vencidos = c5.checkbox("Vencidos")
    filtered = df.copy()
    if site != "Todos":
        filtered = filtered[filtered["site"] == site]
    if origem != "Todos":
        filtered = filtered[filtered["origem"] == origem]
    if status != "Todos":
        filtered = filtered[filtered["status"] == status]
    if criticidade != "Todos":
        filtered = filtered[filtered["criticidade"] == criticidade]
    if vencidos:
        filtered = filtered[filtered["vencido"] == True]
    c1, c2, c3 = st.columns(3)
    with c1:
        kpi_card("PAC aberto", int(filtered["status"].isin(["Aberto", "Em andamento", "Vencido"]).sum()))
    with c2:
        kpi_card("PAC vencido", int(filtered["vencido"].sum()))
    with c3:
        kpi_card("Críticos", int(filtered["criticidade"].isin(["Crítico", "Crítica"]).sum()))
    st.dataframe(filtered, use_container_width=True, hide_index=True)


def page_relatorios_auditoria(session, user):
    header("Relatórios de Auditoria Cruzada", "Exportações executivas da auditoria EHS Directives.")
    auditoria = select_auditoria(session, user)
    if not auditoria:
        return
    df = respostas_df(session, auditoria.id)
    ach = achados_df(session, auditoria.id)
    c1, c2, c3 = st.columns(3)
    with c1:
        kpi_card("Conformidade", f"{conformidade_percentual(df)}%")
    with c2:
        kpi_card("Maturidade", maturidade_media(df))
    with c3:
        kpi_card("PAC", len(ach))
    st.download_button("Checklist de auditoria cruzada em Excel", export_checklist_excel(session, auditoria.id), file_name=f"checklist_auditoria_{auditoria.id}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    st.download_button("Relatório de auditoria cruzada em PDF", export_relatorio_pdf(session, auditoria.id), file_name=f"relatorio_auditoria_{auditoria.id}.pdf", mime="application/pdf")
    st.download_button("PAC de auditoria cruzada em Excel", export_plano_acao_excel(session, auditoria.id), file_name=f"pac_auditoria_{auditoria.id}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def page_base_checklists(session, user):
    header("Base do Checklist EHS", "Itens incorporados de EHS Directives para auditorias cruzadas.")
    valid = validate_seed(session)
    c1, c2 = st.columns(2)
    with c1:
        kpi_card("Categorias EHS", valid["categorias"])
    with c2:
        kpi_card("Itens EHS", valid["requisitos_ativos"])
    if st.button("Sincronizar base incorporada", disabled=not can_admin(user)):
        seed_base(session)
        st.success("Base sincronizada.")
    dirs = session.query(Diretiva).order_by(Diretiva.codigo).all()
    st.dataframe(pd.DataFrame([{"Código": d.codigo, "Título": d.titulo, "Ativa": d.ativa} for d in dirs]), use_container_width=True, hide_index=True)
    reqs = session.query(Requisito).filter(Requisito.codigo_requisito.in_(logical_requisito_codes())).order_by(Requisito.codigo_requisito).all()
    req_df = pd.DataFrame([{"id": r.id, "Código": r.codigo_requisito, "Categoria": r.diretiva.titulo, "Pergunta": r.pergunta, "Criticidade": r.criticidade, "Evidência esperada": r.tipo_evidencia_esperada, "Ativo": r.ativo} for r in reqs])
    edited = st.data_editor(req_df, hide_index=True, use_container_width=True, disabled=["id", "Código", "Categoria", "Pergunta"], column_config={"Criticidade": st.column_config.SelectboxColumn("Criticidade", options=CRITICIDADES)})
    if st.button("Salvar base EHS", type="primary", disabled=not can_admin(user)):
        for row in edited.to_dict("records"):
            req = session.get(Requisito, int(row["id"]))
            if req:
                req.criticidade = row["Criticidade"]
                req.tipo_evidencia_esperada = row["Evidência esperada"]
                req.ativo = bool(row["Ativo"])
        st.success("Base EHS atualizada.")


def page_usuarios(session, user):
    header("Usuários", "Perfis e vínculo por site.")
    if not can_admin(user):
        st.warning("Acesso restrito ao perfil Admin_LAG.")
        return
    sites = session.query(Site).filter_by(ativo=True).order_by(Site.codigo).all()
    with st.form("novo_usuario"):
        c1, c2, c3, c4 = st.columns(4)
        nome = c1.text_input("Nome")
        email = c2.text_input("E-mail")
        from audit_app.constants import PERFIS

        perfil = c3.selectbox("Perfil", PERFIS)
        site = c4.selectbox("Site", [None] + sites, format_func=lambda s: "Corporativo" if s is None else s.codigo)
        if st.form_submit_button("Criar usuário", type="primary"):
            if nome and email:
                session.add(Usuario(nome=nome, email=email, perfil=perfil, site_id=site.id if site else None, ativo=True))
                st.success("Usuário criado.")
    rows = [{"ID": u.id, "Nome": u.nome, "E-mail": u.email, "Perfil": u.perfil, "Site": u.site.codigo if u.site else "Corporativo", "Ativo": u.ativo} for u in session.query(Usuario).order_by(Usuario.nome)]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def page_sites(session, user):
    header("Sites", "Administração das unidades da plataforma.")
    if not can_admin(user):
        st.warning("Acesso restrito ao perfil Admin_LAG.")
        return
    with st.form("novo_site"):
        c1, c2 = st.columns(2)
        codigo = c1.text_input("Código")
        nome = c2.text_input("Nome")
        if st.form_submit_button("Criar site", type="primary") and codigo and nome:
            session.add(Site(codigo=codigo.upper(), nome=nome, ativo=True))
            st.success("Site criado.")
    rows = [{"ID": s.id, "Código": s.codigo, "Nome": s.nome, "Ativo": s.ativo} for s in session.query(Site).order_by(Site.codigo)]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
