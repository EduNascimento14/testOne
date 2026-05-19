from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from audit_app.constants import CHECKLIST_BASE, CRITICIDADES, PRIORIDADES, STATUS_ACHADO, STATUS_CONFORMIDADE, TIPOS_ACHADO
from audit_app.models import Achado, Auditoria, Diretiva, Requisito, RespostaChecklist, Site
from audit_app.seed import ensure_auditoria_checklist, logical_requisito_codes, seed_base, validate_seed
from audit_app.services import achados_df, conformidade_percentual, criar_auditoria, dashboard_kpis, export_checklist_excel, export_plano_acao_excel, export_relatorio_pdf, maturidade_media, pontuacao_por, respostas_df, salvar_respostas, salvar_upload
from audit_app.ui import header, kpi_card, section, select_auditoria


def can_admin(user):
    return bool(user and user.perfil == "Admin_LAG")


def can_edit_audit(user, auditoria=None):
    if not user or user.perfil == "Visualizador":
        return False
    if user.perfil in ["Admin_LAG", "Auditor"]:
        return True
    if user.perfil == "EHS_Local" and auditoria and user.site_id == auditoria.site_auditado_id:
        return True
    return user.perfil == "EHS_Local" and auditoria is None


def can_edit_action(user, achado=None):
    if not user or user.perfil == "Visualizador":
        return False
    if user.perfil in ["Admin_LAG", "Auditor", "EHS_Local"]:
        return True
    return bool(achado and user.perfil == "Responsavel_Acao" and achado.responsavel and achado.responsavel.lower() == user.nome.lower())


def page_dashboard(session):
    header("Dashboard EHS", "Visão consolidada de auditorias, conformidade, maturidade e PAC.")
    k = dashboard_kpis(session)
    cols = st.columns(8)
    metrics = [("Planejadas", k["planejadas"]), ("Em andamento", k["em_andamento"]), ("Concluídas", k["concluidas"]), ("Conformidade média", f"{k['conformidade_media']}%"), ("Maturidade média", k["maturidade_media"]), ("PAC aberto", k["achados_abertos"]), ("PAC vencido", k["achados_vencidos"]), ("NC críticas", k["nc_criticas_abertas"])]
    for col, (label, value) in zip(cols, metrics):
        with col:
            kpi_card(label, value)
    if k["achados_vencidos"] or k["nc_criticas_abertas"]:
        st.error("Há ações vencidas ou não conformidades críticas abertas que exigem priorização.")

    df = respostas_df(session)
    ach = achados_df(session)
    if df.empty:
        st.info("Crie uma auditoria para habilitar os gráficos.")
        return

    site_score = pontuacao_por(df, "site")
    cat_score = pontuacao_por(df, "diretiva")
    c1, c2 = st.columns(2)
    c1.plotly_chart(px.bar(site_score, x="site", y="conformidade", title="Conformidade por site", text_auto=True, range_y=[0, 100], color_discrete_sequence=["#1f4bb8"]), use_container_width=True)
    c2.plotly_chart(px.bar(site_score, x="site", y="maturidade", title="Maturidade por site", text_auto=True, range_y=[0, 5], color_discrete_sequence=["#ffb91d"]), use_container_width=True)
    c3, c4 = st.columns(2)
    c3.plotly_chart(px.bar(cat_score, x="diretiva", y="conformidade", title="Conformidade por categoria", text_auto=True, range_y=[0, 100], color_discrete_sequence=["#12263f"]), use_container_width=True)
    if not ach.empty:
        c4.plotly_chart(px.pie(ach, names="tipo_achado", title="Registros por tipo"), use_container_width=True)
        st.plotly_chart(px.bar(ach.groupby("status", as_index=False).size(), x="status", y="size", title="PAC por status", text_auto=True, color_discrete_sequence=["#1f4bb8"]), use_container_width=True)

    heat_rows = [{"site": site_, "diretiva": diretiva, "conformidade": conformidade_percentual(group)} for (site_, diretiva), group in df.groupby(["site", "diretiva"])]
    hdf = pd.DataFrame(heat_rows)
    if not hdf.empty:
        st.plotly_chart(px.imshow(hdf.pivot(index="site", columns="diretiva", values="conformidade"), title="Heatmap site x categoria", aspect="auto", color_continuous_scale="RdYlGn", zmin=0, zmax=100), use_container_width=True)

    section("Top 10 maiores gaps")
    gaps = df[df["status"].isin(["Não Conforme", "Parcialmente Conforme"])].head(10)
    st.dataframe(gaps[["site", "diretiva", "codigo_requisito", "criticidade", "status", "pergunta"]], use_container_width=True, hide_index=True)


def page_planejamento(session, user):
    header("Planejar auditoria", "Crie a auditoria e gere automaticamente o checklist corporativo.")
    sites = session.query(Site).filter_by(ativo=True).order_by(Site.codigo).all()
    total_reqs = session.query(Requisito).filter_by(ativo=True).count()
    cinfo1, cinfo2, cinfo3 = st.columns(3)
    with cinfo1: kpi_card("Sites disponíveis", len(sites))
    with cinfo2: kpi_card("Itens do checklist", total_reqs)
    with cinfo3: kpi_card("Categorias", len(CHECKLIST_BASE))
    if not sites:
        st.error("Cadastre ao menos um site ativo antes de criar auditorias.")
        return

    section("Nova auditoria")
    with st.form("nova_auditoria"):
        c1, c2, c3 = st.columns([1, 1.2, 1])
        ano = c1.number_input("Ano", min_value=2020, max_value=2100, value=date.today().year)
        ciclo = c2.text_input("Ciclo", value=f"Ciclo {date.today().year}-1")
        data_planejada = c3.date_input("Data planejada", value=date.today())
        c4, c5, c6 = st.columns(3)
        site_auditado = c4.selectbox("Site auditado", sites, format_func=lambda s: s.codigo)
        site_lider = c5.selectbox("Site auditor líder", sites, index=1 if len(sites) > 1 else 0, format_func=lambda s: s.codigo)
        site_apoio = c6.selectbox("Site auditor apoio", [None] + sites, format_func=lambda s: "Sem apoio" if s is None else s.codigo)
        c7, c8 = st.columns(2)
        auditor_lider = c7.text_input("Auditor líder", value=user.nome if user else "")
        auditor_apoio = c8.text_input("Auditor apoio")
        escopo = st.text_area("Escopo", value="Checklist corporativo de Auditoria Cruzada de EHS Directives.", height=80)
        observacoes = st.text_area("Observações", height=80)
        submitted = st.form_submit_button("Criar auditoria", type="primary", disabled=not can_edit_audit(user))
    if submitted:
        try:
            auditoria = criar_auditoria(session, nome=f"Auditoria Cruzada {site_auditado.codigo} - {ciclo}", ano=int(ano), ciclo=ciclo, site_auditado_id=site_auditado.id, site_auditor_lider_id=site_lider.id, site_auditor_apoio_id=site_apoio.id if site_apoio else None, auditor_lider=auditor_lider, auditor_apoio=auditor_apoio, data_planejada=data_planejada, status="Planejada", escopo=escopo, observacoes=observacoes)
            st.success(f"Auditoria #{auditoria.id} criada com {total_reqs} itens de checklist.")
        except ValueError as exc:
            st.error(str(exc))

    section("Auditorias cadastradas")
    auds = session.query(Auditoria).order_by(Auditoria.id.desc()).all()
    aud_cols = ["ID", "Nome", "Site", "Ciclo", "Data planejada", "Status"]
    st.dataframe(pd.DataFrame([{"ID": a.id, "Nome": a.nome, "Site": a.site_auditado.codigo, "Ciclo": a.ciclo, "Data planejada": a.data_planejada, "Status": a.status} for a in auds], columns=aud_cols), use_container_width=True, hide_index=True)


def page_checklist(session, user):
    header("Executar checklist", "Responda os itens, registre evidências e indique necessidade de PAC.")
    auditoria = select_auditoria(session)
    if not auditoria:
        return
    ensure_auditoria_checklist(session, auditoria.id)
    editable = can_edit_audit(user, auditoria)
    df = respostas_df(session, auditoria.id)
    if df.empty:
        st.warning("Não há requisitos ativos para esta auditoria. Reexecute o seed da base ou revise a Base do Checklist.")
        return

    c1, c2, c3 = st.columns(3)
    categoria = c1.selectbox("Categoria", ["Todas"] + sorted(df["diretiva"].unique().tolist()))
    status = c2.selectbox("Status", ["Todos"] + STATUS_CONFORMIDADE)
    criticidade = c3.selectbox("Criticidade", ["Todas"] + CRITICIDADES)
    filtered = df.copy()
    if categoria != "Todas": filtered = filtered[filtered["diretiva"] == categoria]
    if status != "Todos": filtered = filtered[filtered["status"] == status]
    if criticidade != "Todas": filtered = filtered[filtered["criticidade"] == criticidade]

    display_cols = ["id", "diretiva", "codigo_requisito", "criticidade", "pergunta", "aplicavel", "status", "nota_maturidade", "evidencia_verificada", "comentario_auditor", "necessita_acao"]
    edited = st.data_editor(filtered[display_cols], hide_index=True, use_container_width=True, disabled=["id", "diretiva", "codigo_requisito", "criticidade", "pergunta"] if editable else display_cols, column_config={"status": st.column_config.SelectboxColumn("Status", options=STATUS_CONFORMIDADE), "nota_maturidade": st.column_config.NumberColumn("Maturidade", min_value=0, max_value=5, step=1), "necessita_acao": st.column_config.CheckboxColumn("Gerar PAC?"), "evidencia_verificada": st.column_config.TextColumn("Evidência"), "comentario_auditor": st.column_config.TextColumn("Observação")}, key=f"editor_{auditoria.id}")
    if st.button("Salvar respostas", type="primary", disabled=not editable):
        salvar_respostas(session, edited, user.nome if user else None)
        st.success("Respostas salvas.")

    desvios = edited[(edited["status"].isin(["Não Conforme", "Parcialmente Conforme"])) | (edited["necessita_acao"] == True)]
    with st.expander(f"Itens com indicação de PAC ({len(desvios)})"):
        st.dataframe(desvios[["codigo_requisito", "criticidade", "status", "pergunta"]], use_container_width=True, hide_index=True)
        if not desvios.empty:
            selected_id = st.selectbox("Item para registrar PAC", desvios["id"].tolist(), format_func=lambda rid: f"Resposta #{rid}")
            resp = session.get(RespostaChecklist, int(selected_id))
            if resp:
                with st.form("novo_pac_checklist"):
                    tipo = st.selectbox("Tipo", TIPOS_ACHADO)
                    descricao = st.text_area("Descrição", value=resp.requisito.pergunta)
                    evidencia = st.text_area("Evidência")
                    acao = st.text_area("Ação corretiva")
                    c1, c2, c3 = st.columns(3)
                    responsavel = c1.text_input("Responsável")
                    prazo = c2.date_input("Prazo", value=date.today())
                    prioridade = c3.selectbox("Prioridade", PRIORIDADES)
                    if st.form_submit_button("Criar PAC", disabled=not editable):
                        session.add(Achado(auditoria_id=auditoria.id, requisito_id=resp.requisito_id, site_id=auditoria.site_auditado_id, tipo_achado=tipo, descricao=descricao, evidencia=evidencia, acao_corretiva=acao, responsavel=responsavel, prazo=prazo, prioridade=prioridade, status="Aberto"))
                        st.success("PAC criado.")

    with st.expander("Anexar evidência ao item"):
        reqs = session.query(Requisito).filter_by(ativo=True).order_by(Requisito.codigo_requisito).all()
        if not reqs:
            st.info("Não há requisitos ativos para anexar evidências.")
        else:
            req_labels = {r.id: f"{r.codigo_requisito} · {r.pergunta[:80]}" for r in reqs}
            req_id = st.selectbox("Item", list(req_labels), format_func=lambda item_id: req_labels[item_id])
            uploaded = st.file_uploader("Arquivo de evidência")
            if uploaded and st.button("Salvar evidência", disabled=not editable):
                salvar_upload(uploaded, auditoria.id, req_id, None, user.nome if user else None, session)
                st.success("Evidência salva.")


def page_pac(session, user):
    header("Achados / PAC", "Plano de Ação Corretiva para desvios, observações e oportunidades de melhoria.")
    ach = achados_df(session)
    if ach.empty:
        st.info("Nenhum registro de PAC cadastrado.")
    else:
        c1, c2, c3, c4 = st.columns(4)
        sites = ["Todos"] + sorted(ach["site"].unique().tolist())
        tipos = ["Todos"] + TIPOS_ACHADO
        status_opts = ["Todos"] + list(dict.fromkeys(STATUS_ACHADO + ["Vencido"]))
        site_filter = c1.selectbox("Site", sites)
        tipo_filter = c2.selectbox("Tipo", tipos)
        status_filter = c3.selectbox("Status", status_opts)
        vencidos = c4.checkbox("Somente vencidos")
        filtered = ach.copy()
        if site_filter != "Todos": filtered = filtered[filtered["site"] == site_filter]
        if tipo_filter != "Todos": filtered = filtered[filtered["tipo_achado"] == tipo_filter]
        if status_filter != "Todos": filtered = filtered[filtered["status"] == status_filter]
        if vencidos: filtered = filtered[filtered["vencido"] == True]
        st.dataframe(filtered, use_container_width=True, hide_index=True)

    registros = session.query(Achado).order_by(Achado.id.desc()).all()
    if registros:
        section("Editar PAC")
        labels = {a.id: f"#{a.id} · {a.tipo_achado} · {a.status}" for a in registros}
        achado_id = st.selectbox("Registro", list(labels), format_func=lambda item_id: labels[item_id])
        achado = session.get(Achado, achado_id)
        if not achado:
            st.warning("Registro de PAC não encontrado.")
            return
        with st.form("editar_pac"):
            tipo = st.selectbox("Tipo", TIPOS_ACHADO, index=TIPOS_ACHADO.index(achado.tipo_achado) if achado.tipo_achado in TIPOS_ACHADO else 0)
            descricao = st.text_area("Descrição", value=achado.descricao)
            evidencia = st.text_area("Evidência", value=achado.evidencia or "")
            risco = st.text_area("Risco", value=achado.risco or "")
            causa = st.text_area("Causa raiz", value=achado.causa_raiz or "")
            acao_imediata = st.text_area("Ação imediata", value=achado.acao_imediata or "")
            acao_corretiva = st.text_area("Ação corretiva", value=achado.acao_corretiva or "")
            c1, c2, c3 = st.columns(3)
            responsavel = c1.text_input("Responsável", value=achado.responsavel or "")
            prazo = c2.date_input("Prazo", value=achado.prazo or date.today())
            prioridade = c3.selectbox("Prioridade", PRIORIDADES, index=PRIORIDADES.index(achado.prioridade) if achado.prioridade in PRIORIDADES else 1)
            c4, c5 = st.columns(2)
            status = c4.selectbox("Status", STATUS_ACHADO, index=STATUS_ACHADO.index(achado.status) if achado.status in STATUS_ACHADO else 0)
            data_conclusao = c5.date_input("Data de conclusão", value=achado.data_conclusao or date.today())
            eficacia = st.text_area("Verificação de eficácia", value=achado.verificacao_eficacia or "")
            status_eficacia = st.text_input("Status da eficácia", value=achado.status_eficacia or "")
            if st.form_submit_button("Salvar PAC", type="primary", disabled=not can_edit_action(user, achado)):
                achado.tipo_achado = tipo
                achado.descricao = descricao
                achado.evidencia = evidencia
                achado.risco = risco
                achado.causa_raiz = causa
                achado.acao_imediata = acao_imediata
                achado.acao_corretiva = acao_corretiva
                achado.responsavel = responsavel
                achado.prazo = prazo
                achado.prioridade = prioridade
                achado.status = status
                achado.data_conclusao = data_conclusao if status == "Concluído" else None
                achado.verificacao_eficacia = eficacia
                achado.status_eficacia = status_eficacia
                st.success("PAC atualizado.")


def page_relatorios(session):
    header("Relatórios e exportações", "Gere relatório PDF, checklist e plano de ação por auditoria.")
    auditoria = select_auditoria(session)
    if not auditoria:
        return
    df = respostas_df(session, auditoria.id)
    ach = achados_df(session, auditoria.id)
    c1, c2, c3 = st.columns(3)
    with c1: kpi_card("Conformidade", f"{conformidade_percentual(df)}%")
    with c2: kpi_card("Maturidade", maturidade_media(df))
    with c3: kpi_card("Registros PAC", len(ach))
    st.download_button("Exportar relatório PDF", export_relatorio_pdf(session, auditoria.id), file_name=f"relatorio_auditoria_{auditoria.id}.pdf", mime="application/pdf")
    st.download_button("Exportar checklist Excel", export_checklist_excel(session, auditoria.id), file_name=f"checklist_auditoria_{auditoria.id}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    st.download_button("Exportar plano de ação Excel", export_plano_acao_excel(session, auditoria.id), file_name=f"plano_acao_auditoria_{auditoria.id}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    section("Resultado por categoria")
    st.dataframe(pontuacao_por(df, "diretiva"), use_container_width=True, hide_index=True)


def page_base(session, user):
    header("Base do Checklist", "Categorias e perguntas incorporadas ao sistema.")
    valid = validate_seed(session)
    c1, c2, c3 = st.columns(3)
    with c1: kpi_card("Categorias", valid["categorias"])
    with c2: kpi_card("Requisitos ativos", valid["requisitos_ativos"])
    with c3: kpi_card("Base", "OK" if valid["base_ok"] else "Revisar")
    if st.button("Reexecutar seed da base", disabled=not can_admin(user)):
        seed_base(session)
        st.success("Base sincronizada.")
    section("Categorias")
    dirs = session.query(Diretiva).filter(Diretiva.codigo.in_([c["codigo"] for c in CHECKLIST_BASE])).order_by(Diretiva.codigo).all()
    st.dataframe(pd.DataFrame([{"Código": d.codigo, "Título": d.titulo, "Descrição": d.descricao, "Ativa": d.ativa} for d in dirs], columns=["Código", "Título", "Descrição", "Ativa"]), use_container_width=True, hide_index=True)
    section("Requisitos")
    reqs = session.query(Requisito).filter(Requisito.codigo_requisito.in_(logical_requisito_codes())).order_by(Requisito.codigo_requisito).all()
    req_df = pd.DataFrame([{"id": r.id, "Código": r.codigo_requisito, "Categoria": r.diretiva.titulo, "Pergunta": r.pergunta, "Criticidade": r.criticidade, "Ativo": r.ativo} for r in reqs], columns=["id", "Código", "Categoria", "Pergunta", "Criticidade", "Ativo"])
    edited = st.data_editor(req_df, hide_index=True, use_container_width=True, disabled=["id", "Código", "Categoria", "Pergunta"], column_config={"Criticidade": st.column_config.SelectboxColumn("Criticidade", options=CRITICIDADES), "Ativo": st.column_config.CheckboxColumn("Ativo")})
    if st.button("Salvar ajustes", type="primary", disabled=not can_admin(user)):
        for row in edited.to_dict("records"):
            req = session.get(Requisito, int(row["id"]))
            if req:
                req.criticidade = row["Criticidade"]
                req.ativo = bool(row["Ativo"])
        st.success("Ajustes salvos.")
