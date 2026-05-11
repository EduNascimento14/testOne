from __future__ import annotations

from datetime import date
import pandas as pd
import plotly.express as px
import streamlit as st
from ehs_audit.auth import can_edit_achado, can_edit_admin, can_edit_auditoria
from ehs_audit.calculations import achados_df, dashboard_kpis, pontuacao_por, respostas_df, resumo_auditoria
from ehs_audit.config import APP_ENV
from ehs_audit.constants import CRITICIDADES, PRIORIDADES, STATUS_ACHADO, STATUS_CONFORMIDADE, TIPOS_ACHADO
from ehs_audit.checklist_seed import ensure_seed_data, validate_checklist_seed
from ehs_audit.db import get_session, init_db
from ehs_audit.exporters import export_checklist_excel, export_plano_acao_excel, export_relatorio_pdf
from ehs_audit.models import Achado, Auditoria, Diretiva, Requisito, Site, Usuario
from ehs_audit.services import criar_auditoria, salvar_respostas, salvar_upload
from ehs_audit.ui import apply_theme, header, sidebar_user

st.set_page_config(page_title="Auditoria Cruzada EHS Directives", page_icon="🛡️", layout="wide")
apply_theme()
init_db()


def get_options(session, model, label_attr="codigo", active_only=True):
    q = session.query(model)
    if active_only and hasattr(model, "ativo"):
        q = q.filter_by(ativo=True)
    return q.order_by(getattr(model, label_attr)).all()


def page_dashboard(session):
    header("Dashboard EHS / GdTs", "Visão consolidada de auditorias cruzadas, maturidade, conformidade e CAPAs.")
    k = dashboard_kpis(session)
    cols = st.columns(8)
    metrics = [("Planejadas", k["planejadas"]), ("Em andamento", k["em_andamento"]), ("Concluídas", k["concluidas"]), ("Conformidade média", f"{k['conformidade_media']}%"), ("Maturidade média", k["maturidade_media"]), ("Achados abertos", k["achados_abertos"]), ("Achados vencidos", k["achados_vencidos"]), ("NC críticas", k["nc_criticas_abertas"])]
    for col, (label, value) in zip(cols, metrics):
        col.metric(label, value)
    if k["achados_vencidos"] or k["nc_criticas_abertas"]:
        st.error("Há ações vencidas ou não conformidades críticas abertas que exigem priorização.")
    df = respostas_df(session)
    ach = achados_df(session)
    if df.empty:
        st.info("Crie uma auditoria para habilitar os gráficos.")
        return
    c1, c2 = st.columns(2)
    site_score = pontuacao_por(df, "site")
    gdt_score = pontuacao_por(df, "diretiva")
    c1.plotly_chart(px.bar(site_score, x="site", y="conformidade", title="Conformidade por site", text_auto=True, range_y=[0, 100]), use_container_width=True)
    c2.plotly_chart(px.bar(site_score, x="site", y="maturidade", title="Maturidade por site", text_auto=True, range_y=[0, 5]), use_container_width=True)
    c3, c4 = st.columns(2)
    c3.plotly_chart(px.bar(gdt_score, x="diretiva", y="conformidade", title="Conformidade por GdT", text_auto=True, range_y=[0, 100]), use_container_width=True)
    if not ach.empty:
        c4.plotly_chart(px.pie(ach, names="tipo_achado", title="Achados por tipo"), use_container_width=True)
        st.plotly_chart(px.bar(ach.groupby("status", as_index=False).size(), x="status", y="size", title="Ações por status", text_auto=True), use_container_width=True)
    heat = gdt_score.copy()
    if not df.empty:
        heat_rows = []
        for (site, diretiva), group in df.groupby(["site", "diretiva"]):
            heat_rows.append({"site": site, "diretiva": diretiva, "conformidade": pontuacao_por(group, "diretiva")["conformidade"].iloc[0]})
        hdf = pd.DataFrame(heat_rows)
        if not hdf.empty:
            st.plotly_chart(px.imshow(hdf.pivot(index="site", columns="diretiva", values="conformidade"), title="Heatmap site x GdT", aspect="auto", color_continuous_scale="RdYlGn", zmin=0, zmax=100), use_container_width=True)
    gaps = df[df["status"].isin(["Não Conforme", "Parcialmente Conforme"])].head(10)
    st.subheader("Top 10 maiores gaps")
    st.dataframe(gaps[["site", "diretiva", "codigo_requisito", "criticidade", "status", "pergunta"]], use_container_width=True, hide_index=True)
    if "ciclo" in df:
        evo = pontuacao_por(df, "ciclo")
        st.plotly_chart(px.line(evo, x="ciclo", y="conformidade", markers=True, title="Evolução por ciclo"), use_container_width=True)


def page_planejamento(session, user):
    header("Planejar auditoria", "Crie auditorias cruzadas e gere automaticamente o checklist completo de requisitos ativos.")
    sites = get_options(session, Site)
    requisitos_ativos = session.query(Requisito).filter_by(ativo=True).count()
    st.caption(f"Requisitos ativos disponíveis para checklist: {requisitos_ativos}")
    with st.form("nova_auditoria"):
        c1, c2, c3 = st.columns(3)
        ano = c1.number_input("Ano", min_value=2020, max_value=2100, value=date.today().year)
        ciclo = c2.text_input("Ciclo", value=f"Ciclo {date.today().year}-1")
        data_planejada = c3.date_input("Data planejada", value=date.today())
        c4, c5, c6 = st.columns(3)
        site_auditado = c4.selectbox("Site auditado", sites, format_func=lambda s: s.codigo)
        site_lider = c5.selectbox("Site auditor líder", sites, format_func=lambda s: s.codigo, index=1 if len(sites) > 1 else 0)
        site_apoio = c6.selectbox("Site auditor apoio", [None] + sites, format_func=lambda s: "-" if s is None else s.codigo)
        auditor_lider = st.text_input("Auditor líder", value=user.nome if user else "")
        auditor_apoio = st.text_input("Auditor apoio")
        escopo = st.text_area("Escopo", value="Checklist completo das GdTs / EHS Directives aplicáveis ao site auditado.")
        observacoes = st.text_area("Observações")
        submitted = st.form_submit_button("Criar auditoria e gerar checklist", disabled=(not can_edit_admin(user) and user and user.perfil not in ["Auditor", "EHS_Local"]))
    if submitted:
        try:
            nome = f"Auditoria Cruzada {site_auditado.codigo} — {ciclo}"
            aud = criar_auditoria(session, nome=nome, ano=int(ano), ciclo=ciclo, site_auditado_id=site_auditado.id, site_auditor_lider_id=site_lider.id, site_auditor_apoio_id=site_apoio.id if site_apoio else None, auditor_lider=auditor_lider, auditor_apoio=auditor_apoio, data_planejada=data_planejada, status="Planejada", escopo=escopo, observacoes=observacoes)
            st.success(f"Auditoria criada com checklist automático: {aud.nome}.")
        except Exception as exc:
            st.error(str(exc))
    st.subheader("Auditorias cadastradas")
    auds = session.query(Auditoria).order_by(Auditoria.data_planejada.desc()).all()
    rows = [{"id": a.id, "nome": a.nome, "ano": a.ano, "ciclo": a.ciclo, "site": a.site_auditado.codigo, "status": a.status, "data_planejada": a.data_planejada} for a in auds]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def page_checklist(session, user):
    header("Executar checklist", "Edite respostas em formato de planilha e salve no banco de dados.")
    auds = session.query(Auditoria).order_by(Auditoria.id.desc()).all()
    if not auds:
        st.info("Crie uma auditoria primeiro.")
        return
    auditoria = st.selectbox("Auditoria", auds, format_func=lambda a: f"#{a.id} — {a.nome} ({a.status})")
    editable = can_edit_auditoria(user, auditoria)
    df = respostas_df(session, auditoria.id)
    if df.empty:
        st.warning("Checklist vazio. Verifique se há requisitos ativos cadastrados na base.")
        return
    c1, c2, c3 = st.columns(3)
    gdt = c1.multiselect("Filtrar por GdT", sorted(df["diretiva"].unique()))
    status = c2.multiselect("Filtrar por status", STATUS_CONFORMIDADE)
    crit = c3.multiselect("Filtrar por criticidade", CRITICIDADES)
    fdf = df.copy()
    if gdt: fdf = fdf[fdf["diretiva"].isin(gdt)]
    if status: fdf = fdf[fdf["status"].isin(status)]
    if crit: fdf = fdf[fdf["criticidade"].isin(crit)]
    edit_cols = ["resposta_id", "diretiva", "codigo_requisito", "criticidade", "pergunta", "aplicavel", "status", "nota_maturidade", "evidencia_verificada", "comentario_auditor", "necessita_acao"]
    edited = st.data_editor(fdf[edit_cols], use_container_width=True, hide_index=True, disabled=["resposta_id", "diretiva", "codigo_requisito", "criticidade", "pergunta"] if editable else edit_cols, column_config={"status": st.column_config.SelectboxColumn(options=STATUS_CONFORMIDADE), "nota_maturidade": st.column_config.NumberColumn(min_value=0, max_value=5, step=1)}, num_rows="fixed")
    if st.button("Salvar respostas", disabled=not editable):
        n = salvar_respostas(session, edited, user.nome if user else None)
        st.success(f"{n} respostas salvas.")
        st.rerun()
    desvios = edited[(edited["status"].isin(["Não Conforme", "Parcialmente Conforme"])) | (edited["necessita_acao"] == True)]  # noqa: E712
    with st.expander(f"Sugestões para criação de achado/CAPA ({len(desvios)})"):
        if desvios.empty:
            st.caption("Nenhum desvio filtrado no momento.")
        else:
            escolha = st.selectbox("Requisito para abrir achado", desvios.to_dict("records"), format_func=lambda r: f"{r['codigo_requisito']} — {r['status']}")
            with st.form("novo_achado_checklist"):
                tipo = st.selectbox("Tipo de achado", TIPOS_ACHADO)
                desc = st.text_area("Descrição", value=f"Desvio identificado no requisito {escolha['codigo_requisito']}: {escolha['pergunta'][:180]}")
                evidencia = st.text_area("Evidência", value=escolha.get("evidencia_verificada", ""))
                responsavel = st.text_input("Responsável")
                prazo = st.date_input("Prazo", value=date.today())
                prioridade = st.selectbox("Prioridade", PRIORIDADES)
                if st.form_submit_button("Criar achado revisado", disabled=not editable):
                    req_id = int(df[df["resposta_id"] == escolha["resposta_id"]]["requisito_id"].iloc[0])
                    session.add(Achado(auditoria_id=auditoria.id, requisito_id=req_id, site_id=auditoria.site_auditado_id, tipo_achado=tipo, descricao=desc, evidencia=evidencia, responsavel=responsavel, prazo=prazo, prioridade=prioridade, status="Aberto", data_abertura=date.today()))
                    session.commit(); st.success("Achado criado.")
    with st.expander("Upload simples de evidência"):
        reqs = session.query(Requisito).join(Diretiva).order_by(Diretiva.codigo, Requisito.codigo_requisito).all()
        req = st.selectbox("Requisito", reqs, format_func=lambda r: f"{r.codigo_requisito} — {r.pergunta[:80]}")
        uploaded = st.file_uploader("Arquivo de evidência")
        if uploaded and st.button("Salvar evidência", disabled=not editable):
            salvar_upload(uploaded, auditoria.id, req.id, None, user.nome if user else None, session)
            st.success("Arquivo salvo em uploads/.")


def page_achados(session, user):
    header("Achados / CAPA", "Gestão objetiva de não conformidades, observações, boas práticas e plano de ação.")
    df = achados_df(session)
    if df.empty:
        st.info("Nenhum achado registrado.")
    else:
        c1, c2, c3, c4 = st.columns(4)
        site = c1.multiselect("Site", sorted(df["site"].unique()))
        tipo = c2.multiselect("Tipo", TIPOS_ACHADO)
        status = c3.multiselect("Status", STATUS_ACHADO)
        vencidos = c4.checkbox("Somente vencidos")
        f = df.copy()
        if site: f = f[f["site"].isin(site)]
        if tipo: f = f[f["tipo_achado"].isin(tipo)]
        if status: f = f[f["status"].isin(status)]
        if vencidos: f = f[f["vencido"]]
        st.dataframe(f, use_container_width=True, hide_index=True)
    achados = session.query(Achado).order_by(Achado.id.desc()).all()
    if achados:
        st.subheader("Editar plano de ação")
        ach = st.selectbox("Achado", achados, format_func=lambda a: f"#{a.id} — {a.tipo_achado} — {a.status}")
        with st.form("editar_achado"):
            status = st.selectbox("Status", STATUS_ACHADO, index=STATUS_ACHADO.index(ach.status) if ach.status in STATUS_ACHADO else 0)
            acao_imediata = st.text_area("Ação imediata", value=ach.acao_imediata or "")
            acao_corretiva = st.text_area("Ação corretiva", value=ach.acao_corretiva or "")
            causa_raiz = st.text_area("Causa raiz", value=ach.causa_raiz or "")
            responsavel = st.text_input("Responsável", value=ach.responsavel or "")
            prazo = st.date_input("Prazo", value=ach.prazo or date.today())
            verificacao = st.text_area("Verificação de eficácia", value=ach.verificacao_eficacia or "")
            status_eficacia = st.text_input("Status da eficácia", value=ach.status_eficacia or "")
            if st.form_submit_button("Salvar CAPA", disabled=not can_edit_achado(user, ach)):
                ach.status, ach.acao_imediata, ach.acao_corretiva, ach.causa_raiz = status, acao_imediata, acao_corretiva, causa_raiz
                ach.responsavel, ach.prazo, ach.verificacao_eficacia, ach.status_eficacia = responsavel, prazo, verificacao, status_eficacia
                ach.data_conclusao = date.today() if status == "Concluído" and not ach.data_conclusao else ach.data_conclusao
                session.commit(); st.success("Achado atualizado.")


def page_relatorios(session):
    header("Relatórios e exportações", "Gere relatório PDF, checklist completo e plano de ação em Excel por auditoria.")
    auds = session.query(Auditoria).order_by(Auditoria.id.desc()).all()
    if not auds:
        st.info("Nenhuma auditoria disponível.")
        return
    auditoria = st.selectbox("Auditoria", auds, format_func=lambda a: f"#{a.id} — {a.nome}")
    resumo = resumo_auditoria(session, auditoria.id)
    c1, c2, c3 = st.columns(3)
    c1.metric("Conformidade", f"{resumo['conformidade']}%")
    c2.metric("Maturidade", resumo["maturidade"])
    c3.metric("Classificação", resumo["classificacao"])
    st.download_button("Exportar relatório PDF", export_relatorio_pdf(session, auditoria.id), file_name=f"relatorio_auditoria_{auditoria.id}.pdf", mime="application/pdf")
    st.download_button("Exportar checklist Excel", export_checklist_excel(session, auditoria.id), file_name=f"checklist_auditoria_{auditoria.id}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    st.download_button("Exportar plano de ação Excel", export_plano_acao_excel(session, auditoria.id), file_name=f"plano_acao_auditoria_{auditoria.id}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def page_admin(session, user):
    header("Base do Checklist", "Consulte as GdTs e requisitos incorporados ao sistema.")
    if not can_edit_admin(user):
        st.warning("Apenas Admin_LAG pode alterar dados administrativos neste MVP.")

    validacao = validate_checklist_seed(session)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("GdTs cadastradas", validacao["diretivas"])
    c2.metric("Requisitos cadastrados", validacao["requisitos"])
    c3.metric("Requisitos ativos", session.query(Requisito).filter_by(ativo=True).count())
    c4.metric("Base validada", "Sim" if validacao["valido"] else "Não")
    if not validacao["valido"]:
        st.error("A base do checklist está inconsistente. Reexecute o seed da base.")

    tab1, tab2, tab3 = st.tabs(["GdTs e requisitos", "Usuários", "Sites"])
    with tab1:
        if st.button("Reexecutar seed da base", disabled=not can_edit_admin(user)):
            result = ensure_seed_data(session)
            st.success(f"Seed reexecutado. GdTs: {result['diretivas']} | Requisitos: {result['requisitos']} | Base validada: {'Sim' if result['valido'] else 'Não'}")
            st.rerun()
        dirs = session.query(Diretiva).order_by(Diretiva.codigo).all()
        st.subheader("GdTs cadastradas")
        st.dataframe(pd.DataFrame([{"id": d.id, "codigo": d.codigo, "titulo": d.titulo, "ativa": d.ativa, "observacao": d.observacao or ""} for d in dirs]), use_container_width=True, hide_index=True)
        reqs = session.query(Requisito).join(Diretiva).order_by(Diretiva.codigo, Requisito.codigo_requisito).all()
        st.subheader("Requisitos cadastrados")
        if reqs:
            rdf = pd.DataFrame([{"id": r.id, "diretiva": r.diretiva.codigo, "codigo_requisito": r.codigo_requisito, "pergunta": r.pergunta, "criticidade": r.criticidade, "ativo": r.ativo} for r in reqs])
            edited = st.data_editor(rdf, use_container_width=True, hide_index=True, disabled=["id", "diretiva", "codigo_requisito", "pergunta"], column_config={"criticidade": st.column_config.SelectboxColumn(options=CRITICIDADES)})
            if st.button("Salvar criticidade/ativo", disabled=not can_edit_admin(user)):
                for row in edited.to_dict("records"):
                    req = session.get(Requisito, int(row["id"]))
                    req.criticidade = row["criticidade"]
                    req.ativo = bool(row["ativo"])
                session.commit()
                st.success("Requisitos atualizados.")
        else:
            st.info("Nenhum requisito cadastrado.")
    with tab2:
        sites = get_options(session, Site, active_only=False)
        with st.form("novo_usuario"):
            nome = st.text_input("Nome")
            email = st.text_input("E-mail")
            perfil = st.selectbox("Perfil", ["Admin_LAG", "EHS_Local", "Auditor", "Visualizador", "Responsavel_Acao"])
            site = st.selectbox("Site", [None] + sites, format_func=lambda s: "-" if s is None else s.codigo)
            if st.form_submit_button("Cadastrar usuário", disabled=not can_edit_admin(user)) and nome and email:
                session.add(Usuario(nome=nome, email=email, perfil=perfil, site_id=site.id if site else None, ativo=True))
                session.commit()
                st.success("Usuário cadastrado.")
        st.dataframe(pd.DataFrame([{"id": u.id, "nome": u.nome, "email": u.email, "perfil": u.perfil, "site": u.site.codigo if u.site else "-", "ativo": u.ativo} for u in session.query(Usuario).all()]), use_container_width=True, hide_index=True)
    with tab3:
        with st.form("novo_site"):
            codigo = st.text_input("Código")
            nome = st.text_input("Nome")
            if st.form_submit_button("Cadastrar site", disabled=not can_edit_admin(user)) and codigo and nome:
                session.add(Site(codigo=codigo.upper(), nome=nome, ativo=True))
                session.commit()
                st.success("Site cadastrado.")
        st.dataframe(pd.DataFrame([{"id": s.id, "codigo": s.codigo, "nome": s.nome, "ativo": s.ativo} for s in session.query(Site).order_by(Site.codigo)]), use_container_width=True, hide_index=True)
    if APP_ENV == "development":
        with st.expander("Zona de desenvolvimento"):
            st.warning("Reinicialização destrutiva disponível apenas em APP_ENV=development.")
            if st.button("Recriar banco vazio", disabled=not can_edit_admin(user)):
                from ehs_audit.db import engine
                from ehs_audit.models import Base
                Base.metadata.drop_all(engine)
                init_db()
                st.success("Banco reinicializado.")
                st.rerun()

def main():
    with get_session() as session:
        st.sidebar.title("🛡️ EHS Directives")
        user = sidebar_user(session)
        page = st.sidebar.radio("Navegação", ["Dashboard", "Planejamento", "Checklist", "Achados / CAPA", "Relatórios", "Administração"])
        if user:
            st.sidebar.info(f"Perfil: {user.perfil}")
        if page == "Dashboard": page_dashboard(session)
        elif page == "Planejamento": page_planejamento(session, user)
        elif page == "Checklist": page_checklist(session, user)
        elif page == "Achados / CAPA": page_achados(session, user)
        elif page == "Relatórios": page_relatorios(session)
        elif page == "Administração": page_admin(session, user)
        st.sidebar.markdown("---")


if __name__ == "__main__":
    main()
