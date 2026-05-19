from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from audit_app.constants import CRITICIDADES, DOCUMENTOS_ESSENCIAIS_NR12, PRIORIDADES, STATUS_MAQUINA, STATUS_PAC, TIPOS_DOCUMENTO_NR12, TIPOS_EQUIPAMENTO, TIPOS_MOC_CRITICA, TIPOS_VERIFICACAO_NR12
from audit_app.models import DocumentoNR12, MaquinaNR12, MOCNR12, PACNR12, RespostaNR12, Site, TermoGarantiaNR12, VerificacaoNR12
from audit_app.services import dashboard_integrado_kpis, documentos_df, ensure_verificacao_itens, export_relatorio_maquina_pdf, export_termo_garantia_pdf, finalizar_verificacao_nr12, maquinas_df, pac_nr12_df, recalcular_status_maquina, save_uploaded_file, termo_resumo, to_excel_bytes
from audit_app.ui import alert_card, can_edit, header, kpi_card, section, visible_site_ids


def _sites_visiveis(session, user):
    return session.query(Site).filter(Site.ativo.is_(True), Site.id.in_(visible_site_ids(session, user))).order_by(Site.codigo).all()


def _maquinas_visiveis(session, user):
    return session.query(MaquinaNR12).filter(MaquinaNR12.site_id.in_(visible_site_ids(session, user))).order_by(MaquinaNR12.codigo).all()


def page_dashboard_integrado(session, user):
    header("Dashboard Integrado", "Visão executiva de Auditoria Cruzada EHS Directives e Sustentação NR-12.")
    k = dashboard_integrado_kpis(session, visible_site_ids(session, user))
    metrics = [("Auditorias planejadas", k["aud_planejadas"]), ("Auditorias em andamento", k["aud_andamento"]), ("Auditorias concluídas", k["aud_concluidas"]), ("Conformidade EHS", f"{k['conformidade_ehs']}%"), ("Maturidade EHS", k["maturidade_ehs"]), ("PACs abertos", k["pacs_abertos"]), ("PACs vencidos", k["pacs_vencidos"]), ("NC críticas abertas", k["nc_criticas"]), ("Máquinas NR-12", k["maquinas_total"]), ("Máquinas conformes", k["maquinas_conformes"]), ("Com observação", k["maquinas_observacao"]), ("Pendentes", k["maquinas_pendentes"]), ("Bloqueadas", k["maquinas_bloqueadas"]), ("Auditorias NR-12 vencidas", k["auditorias_nr12_vencidas"]), ("Documentos vencidos", k["documentos_vencidos"]), ("MOCs sem validação", k["mocs_pendentes"])]
    cols = st.columns(4)
    for idx, (label, value) in enumerate(metrics):
        with cols[idx % 4]:
            kpi_card(label, value)
    if k["maquinas_bloqueadas"] or k["pacs_vencidos"] or k["mocs_pendentes"]:
        alert_card("Há exposições críticas que exigem priorização: máquinas bloqueadas, PACs vencidos ou MOCs críticas sem validação.")


def page_alertas_criticos(session, user):
    header("Alertas Críticos", "Exposições que exigem contenção, validação ou priorização.")
    site_ids = visible_site_ids(session, user)
    mq = maquinas_df(session, site_ids)
    docs = documentos_df(session, site_ids)
    pac = pac_nr12_df(session, site_ids)
    if not mq.empty:
        st.dataframe(mq[mq["status_nr12"] == "Bloqueada por desvio crítico"], use_container_width=True, hide_index=True)
    if not pac.empty:
        st.dataframe(pac[(pac["vencido"] == True) | (pac["criticidade"].isin(["Crítico", "Crítica"]))], use_container_width=True, hide_index=True)
    if not docs.empty:
        st.dataframe(docs[(docs["tipo_documento"].isin(DOCUMENTOS_ESSENCIAIS_NR12)) & (docs["status"].isin(["Vencido", "Próximo do vencimento"]))], use_container_width=True, hide_index=True)


def page_dashboard_nr12(session, user):
    header("Dashboard NR-12", "Sustentação da conformidade legal em máquinas já adequadas.")
    site_ids = visible_site_ids(session, user)
    mq = maquinas_df(session, site_ids)
    docs = documentos_df(session, site_ids)
    pac = pac_nr12_df(session, site_ids)
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: kpi_card("Máquinas", len(mq))
    with c2: kpi_card("Conformes", int((mq["status_nr12"] == "Conforme").sum()) if not mq.empty else 0)
    with c3: kpi_card("Bloqueadas", int((mq["status_nr12"] == "Bloqueada por desvio crítico").sum()) if not mq.empty else 0)
    with c4: kpi_card("Docs vencidos", int((docs["status"] == "Vencido").sum()) if not docs.empty else 0)
    with c5: kpi_card("PAC vencido", int(pac["vencido"].sum()) if not pac.empty else 0)
    if not mq.empty:
        st.plotly_chart(px.pie(mq, names="status_nr12", title="Distribuição de status"), use_container_width=True)
        st.dataframe(mq, use_container_width=True, hide_index=True)


def page_inventario(session, user):
    header("Inventário de Máquinas", "Cadastro e controle das máquinas sob sustentação NR-12.")
    sites = _sites_visiveis(session, user)
    with st.form("maquina_form"):
        c1, c2, c3, c4 = st.columns(4)
        codigo = c1.text_input("Código da máquina")
        site = c2.selectbox("Site", sites, format_func=lambda s: s.codigo) if sites else None
        nome = c3.text_input("Nome da máquina")
        criticidade = c4.selectbox("Criticidade", CRITICIDADES)
        a, b, c, d = st.columns(4)
        area = a.text_input("Área/setor")
        linha = b.text_input("Linha/processo")
        tipo = c.selectbox("Tipo de equipamento", TIPOS_EQUIPAMENTO)
        responsavel = d.text_input("Responsável da área")
        laudo, art, apreciacao, manual, treinamento = st.columns(5)
        fl_laudo = laudo.checkbox("Laudo NR-12")
        fl_art = art.checkbox("ART")
        fl_ap = apreciacao.checkbox("Apreciação de risco")
        fl_manual = manual.checkbox("Manual atualizado")
        fl_treinamento = treinamento.checkbox("Treinamento")
        if st.form_submit_button("Salvar máquina", type="primary", disabled=not can_edit(user) or site is None):
            maq = session.query(MaquinaNR12).filter_by(codigo=codigo).one_or_none() or MaquinaNR12(codigo=codigo)
            session.add(maq)
            maq.site_id = site.id; maq.nome = nome; maq.area_setor = area; maq.linha_processo = linha; maq.tipo_equipamento = tipo; maq.responsavel_area = responsavel; maq.criticidade = criticidade; maq.possui_laudo_nr12 = fl_laudo; maq.possui_art = fl_art; maq.possui_apreciacao_risco = fl_ap; maq.possui_manual_atualizado = fl_manual; maq.possui_treinamento = fl_treinamento; maq.proxima_auditoria_prevista = date.today() + timedelta(days=180)
            session.flush(); recalcular_status_maquina(session, maq); st.success("Máquina salva.")
    df = maquinas_df(session, visible_site_ids(session, user))
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.download_button("Exportar inventário NR-12 em Excel", to_excel_bytes({"Inventário NR-12": df}), "inventario_nr12.xlsx")


def page_documentos(session, user):
    header("Documentos NR-12", "Controle documental com vencimento, anexos e documentos essenciais.")
    maquinas = _maquinas_visiveis(session, user)
    if not maquinas:
        st.info("Cadastre uma máquina antes de registrar documentos.")
        return
    with st.form("documento_nr12"):
        c1, c2, c3 = st.columns(3)
        maquina = c1.selectbox("Máquina", maquinas, format_func=lambda m: f"{m.codigo} · {m.nome}")
        tipo = c2.selectbox("Tipo de documento", TIPOS_DOCUMENTO_NR12)
        titulo = c3.text_input("Título")
        emissao = st.date_input("Data de emissão", value=date.today())
        validade = st.date_input("Data de validade", value=date.today() + timedelta(days=365))
        uploaded = st.file_uploader("Anexo")
        if st.form_submit_button("Salvar documento", type="primary", disabled=not can_edit(user)):
            filename = path = None
            if uploaded:
                filename, path = save_uploaded_file(uploaded, f"nr12_doc_maq{maquina.id}")
            session.add(DocumentoNR12(maquina_id=maquina.id, tipo_documento=tipo, titulo=titulo or tipo, data_emissao=emissao, data_validade=validade, nome_arquivo=filename, caminho_arquivo=path))
            recalcular_status_maquina(session, maquina); st.success("Documento salvo.")
    df = documentos_df(session, visible_site_ids(session, user))
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.download_button("Exportar documentos NR-12 em Excel", to_excel_bytes({"Documentos NR-12": df}), "documentos_nr12.xlsx")


def page_auditorias_nr12(session, user):
    header("Auditorias e Inspeções NR-12", "Checklists operacionais, manutenção, EHS, corporativos e pós-MOC.")
    maquinas = _maquinas_visiveis(session, user)
    if not maquinas:
        return
    with st.form("nova_verificacao"):
        maq = st.selectbox("Máquina", maquinas, format_func=lambda m: f"{m.codigo} · {m.nome}")
        tipo = st.selectbox("Tipo de verificação", TIPOS_VERIFICACAO_NR12)
        prox = st.date_input("Próxima verificação", value=date.today() + timedelta(days=180))
        if st.form_submit_button("Criar verificação", type="primary", disabled=not can_edit(user)):
            v = VerificacaoNR12(maquina_id=maq.id, site_id=maq.site_id, tipo_verificacao=tipo, data_verificacao=date.today(), proxima_verificacao=prox, responsavel=user.nome if user else "")
            session.add(v); session.flush(); ensure_verificacao_itens(session, v); st.success(f"Verificação #{v.id} criada.")
    verificacoes = session.query(VerificacaoNR12).filter(VerificacaoNR12.site_id.in_(visible_site_ids(session, user))).order_by(VerificacaoNR12.id.desc()).all()
    if verificacoes:
        v = st.selectbox("Verificação", verificacoes, format_func=lambda x: f"#{x.id} · {x.maquina.codigo} · {x.tipo_verificacao}")
        ensure_verificacao_itens(session, v)
        respostas = session.query(RespostaNR12).filter_by(verificacao_id=v.id).join(RespostaNR12.item).all()
        df = pd.DataFrame([{"id": r.id, "Código": r.item.codigo, "Criticidade": r.item.criticidade, "Pergunta": r.item.pergunta, "Aplicável": r.aplicavel, "Status": r.status, "Comentário": r.comentario or "", "Evidência": r.evidencia or ""} for r in respostas])
        edited = st.data_editor(df, hide_index=True, use_container_width=True, disabled=["id", "Código", "Criticidade", "Pergunta"], column_config={"Status": st.column_config.SelectboxColumn("Status", options=["Conforme", "Conforme com observação", "Não Conforme"])})
        if st.button("Salvar e calcular resultado", type="primary", disabled=not can_edit(user)):
            for row in edited.to_dict("records"):
                r = session.get(RespostaNR12, int(row["id"])); r.aplicavel = bool(row["Aplicável"]); r.status = row["Status"]; r.comentario = row["Comentário"]; r.evidencia = row["Evidência"]
            finalizar_verificacao_nr12(session, v); st.success(f"Resultado: {v.resultado} · {v.pontuacao}%")


def page_pac_nr12(session, user):
    header("PAC NR-12", "Plano de Ação Corretiva da sustentação NR-12.")
    df = pac_nr12_df(session, visible_site_ids(session, user))
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.download_button("Exportar PAC NR-12 em Excel", to_excel_bytes({"PAC NR-12": df}), "pac_nr12.xlsx")


def page_moc(session, user):
    header("Gestão de Mudanças / MOC", "Controle formal de alterações com impacto em dispositivos e controles críticos de segurança.")
    maquinas = _maquinas_visiveis(session, user)
    if not maquinas:
        return
    with st.form("nova_moc"):
        maquina = st.selectbox("Máquina", maquinas, format_func=lambda m: f"{m.codigo} · {m.nome}")
        tipo = st.selectbox("Tipo de mudança", TIPOS_MOC_CRITICA + ["Outra"])
        titulo = st.text_input("Título")
        impacta = st.checkbox("Impacta segurança?", value=True)
        if st.form_submit_button("Registrar MOC", type="primary", disabled=not can_edit(user)):
            moc = MOCNR12(site_id=maquina.site_id, maquina_id=maquina.id, titulo=titulo or tipo, tipo_mudanca=tipo, impacta_seguranca=impacta, exige_moc=impacta, responsavel=user.nome if user else "")
            session.add(moc); session.flush(); recalcular_status_maquina(session, maquina); st.success("MOC registrada.")
    rows = [{"ID": m.id, "Site": m.site.codigo, "Máquina": m.maquina.codigo, "Tipo": m.tipo_mudanca, "EHS": m.aprovacao_ehs, "Validação": m.validacao_final, "Status": m.status} for m in session.query(MOCNR12).filter(MOCNR12.site_id.in_(visible_site_ids(session, user))).order_by(MOCNR12.id.desc())]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def page_termo_garantia(session, user):
    header("Termo de Garantia do Site", "Termo anual de sustentação da conformidade legal NR-12.")
    sites = _sites_visiveis(session, user)
    if not sites:
        return
    site = st.selectbox("Site", sites, format_func=lambda s: s.codigo)
    resumo = termo_resumo(session, site.id)
    cols = st.columns(5)
    for idx, (label, key) in enumerate([("Máquinas", "maquinas"), ("Conformes", "conformes"), ("Pendentes", "pendentes"), ("Bloqueadas", "bloqueadas"), ("MOCs pendentes", "mocs_pendentes")]):
        with cols[idx]: kpi_card(label, resumo[key])
    with st.form("termo_garantia"):
        ano = st.number_input("Ano/ciclo", min_value=2020, max_value=2100, value=date.today().year)
        declaracao = st.text_area("Declaração formal", value="O site possui rotina ativa de sustentação da conformidade NR-12 para máquinas já adequadas.")
        ressalvas = st.text_area("Ressalvas, pendências e plano de ação")
        if st.form_submit_button("Registrar termo", type="primary", disabled=not can_edit(user)):
            termo = TermoGarantiaNR12(site_id=site.id, ano=int(ano), ciclo=f"Anual {ano}", declaracao=declaracao, ressalvas=ressalvas)
            session.add(termo); session.flush(); st.success(f"Termo #{termo.id} registrado.")
    termos = session.query(TermoGarantiaNR12).filter_by(site_id=site.id).order_by(TermoGarantiaNR12.id.desc()).all()
    if termos:
        termo = st.selectbox("Termo para exportação", termos, format_func=lambda t: f"#{t.id} · {t.ciclo}")
        st.download_button("Exportar Termo de Garantia NR-12 em PDF", export_termo_garantia_pdf(session, termo.id), f"termo_garantia_nr12_{site.codigo}_{termo.ano}.pdf")


def page_relatorio_maquina(session, user):
    header("Relatório por Máquina", "Resumo documental, auditorias e PAC por equipamento.")
    maquinas = _maquinas_visiveis(session, user)
    if maquinas:
        maquina = st.selectbox("Máquina", maquinas, format_func=lambda m: f"{m.codigo} · {m.nome}")
        st.download_button("Exportar relatório por máquina em PDF", export_relatorio_maquina_pdf(session, maquina.id), f"relatorio_maquina_{maquina.codigo}.pdf")


def page_exportacoes_gerais(session, user):
    header("Exportações Gerais", "Bases executivas da plataforma integrada.")
    site_ids = visible_site_ids(session, user)
    st.download_button("Inventário NR-12 em Excel", to_excel_bytes({"Inventário": maquinas_df(session, site_ids)}), "inventario_nr12.xlsx")
    st.download_button("Documentos NR-12 em Excel", to_excel_bytes({"Documentos": documentos_df(session, site_ids)}), "documentos_nr12.xlsx")
    st.download_button("PAC NR-12 em Excel", to_excel_bytes({"PAC NR-12": pac_nr12_df(session, site_ids)}), "pac_nr12.xlsx")
