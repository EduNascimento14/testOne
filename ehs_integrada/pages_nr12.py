from datetime import date
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from ehs_integrada.exports import export_machine_pdf, export_nr12_audits_excel, export_nr12_documents_excel, export_nr12_inventory_excel, export_nr12_moc_excel, export_nr12_pac_excel, export_termo_pdf
from ehs_integrada.models import NR12ChecklistItem, NR12Documento, NR12Maquina, NR12MOC, NR12PAC, NR12Resposta, NR12TermoGarantia, NR12Verificacao
from ehs_integrada.services import apply_nr12_respostas, create_nr12_verificacao, nr12_documentos_df, nr12_kpis, nr12_maquinas_df, nr12_mocs_df, nr12_pacs_df, nr12_schedule_df, nr12_verificacoes_df, save_uploaded_file, site_options, update_machine_status
from ehs_integrada.ui import alert_card, empty_state, header, kpi_card
from ehs_integrada.validations import CLASSIFICACOES, CRITICIDADES, DOCUMENTOS_NR12, STATUS_NR12, TIPOS_MUDANCA_CRITICA, TIPOS_VERIFICACAO_NR12, document_status


def _site_filter(session, user):
    sites = site_options(session, user)
    labels = ["Todos"] + [s.codigo for s in sites] if user.perfil == "Admin_LAG" else [s.codigo for s in sites]
    selected = st.selectbox("Site", labels)
    if selected == "Todos":
        return None
    return [next(s.id for s in sites if s.codigo == selected)]


def _machines(session, site_ids=None):
    q = session.query(NR12Maquina).order_by(NR12Maquina.codigo)
    if site_ids is not None:
        q = q.filter(NR12Maquina.site_id.in_(site_ids))
    return q.all()


def page_dashboard_nr12(session, user):
    header("Dashboard NR-12", "Visão executiva da sustentação da conformidade legal das máquinas já adequadas.")
    site_ids = _site_filter(session, user)
    k = nr12_kpis(session, site_ids)
    cols = st.columns(5)
    for col, label, value, help_text in [
        (cols[0], "Máquinas", k["total"], "Inventário ativo"),
        (cols[1], "% conformes", f"{k['conformes_pct']}%", "Status sustentado"),
        (cols[2], "Bloqueadas", k["bloqueadas"], "Desvio crítico"),
        (cols[3], "PACs vencidos", k["pacs_vencidos"], "Ações em atraso"),
        (cols[4], "MOCs críticas", k["mocs_sem_validacao"], "Sem validação"),
    ]:
        with col:
            kpi_card(label, value, help_text)
    if k["bloqueadas"] or k["pacs_vencidos"] or k["mocs_sem_validacao"]:
        alert_card("Prioridade de gestão", "Há bloqueios, ações vencidas ou mudanças críticas pendentes de validação.", "critical")
    machines = nr12_maquinas_df(session, site_ids)
    col1, col2 = st.columns(2)
    with col1:
        if not machines.empty:
            fig = px.histogram(machines, x="Status NR-12", color="Status NR-12", title="Status das máquinas")
            fig.update_layout(showlegend=False, margin=dict(l=10, r=10, t=45, b=10))
            st.plotly_chart(fig, use_container_width=True)
    with col2:
        schedule = nr12_schedule_df(session, site_ids)
        if not schedule.empty:
            fig = px.histogram(schedule, x="Status", color="Tipo", title="Agenda de verificações")
            fig.update_layout(margin=dict(l=10, r=10, t=45, b=10))
            st.plotly_chart(fig, use_container_width=True)
    st.subheader("Máquinas prioritárias")
    priority = machines[machines["Status NR-12"].isin(["Bloqueada por desvio crítico", "Pendente de ação não crítica"])] if not machines.empty else machines
    st.dataframe(priority, use_container_width=True, hide_index=True) if not priority.empty else empty_state("Nenhuma máquina prioritária para os filtros selecionados.")


def page_inventario(session, user):
    header("Inventário de Máquinas", "Cadastro, consulta e exportação das máquinas dentro do escopo de sustentação NR-12.")
    site_ids = _site_filter(session, user)
    sites = site_options(session, user)
    machines = _machines(session, site_ids)
    selected = st.selectbox("Editar máquina existente", ["Nova máquina"] + [f"{m.codigo} · {m.nome}" for m in machines])
    machine = None if selected == "Nova máquina" else machines[[f"{m.codigo} · {m.nome}" for m in machines].index(selected)]
    with st.form("form_maquina"):
        c1, c2, c3 = st.columns(3)
        codigo = c1.text_input("Código da máquina", value=machine.codigo if machine else "")
        site_label = c2.selectbox("Site", [s.codigo for s in sites], index=[s.id for s in sites].index(machine.site_id) if machine and machine.site_id in [s.id for s in sites] else 0)
        area = c3.text_input("Área/setor", value=machine.area if machine else "")
        c1, c2, c3 = st.columns(3)
        linha = c1.text_input("Linha/processo", value=(machine.linha_processo or "") if machine else "")
        nome = c2.text_input("Nome da máquina", value=machine.nome if machine else "")
        fabricante = c3.text_input("Fabricante", value=(machine.fabricante or "") if machine else "")
        with st.expander("Dados técnicos e governança", expanded=False):
            c1, c2, c3 = st.columns(3)
            modelo = c1.text_input("Modelo", value=(machine.modelo or "") if machine else "")
            serie = c2.text_input("Número de série", value=(machine.numero_serie or "") if machine else "")
            ano = c3.number_input("Ano", 1900, 2100, value=(machine.ano or 2020) if machine else 2020)
            c1, c2, c3 = st.columns(3)
            tipo = c1.text_input("Tipo de equipamento", value=(machine.tipo_equipamento or "") if machine else "")
            responsavel = c2.text_input("Responsável da área", value=(machine.responsavel_area or "") if machine else "")
            criticidade = c3.selectbox("Criticidade", CRITICIDADES, index=CRITICIDADES.index(machine.criticidade) if machine and machine.criticidade in CRITICIDADES else 2)
            status = st.selectbox("Status NR-12", STATUS_NR12, index=STATUS_NR12.index(machine.status_nr12) if machine and machine.status_nr12 in STATUS_NR12 else 2)
            c1, c2, c3 = st.columns(3)
            ultima_adequacao = c1.date_input("Última adequação NR-12", value=(machine.ultima_adequacao or date.today()) if machine else date.today())
            ultima_auditoria = c2.date_input("Última auditoria", value=(machine.ultima_auditoria or date.today()) if machine else date.today())
            proxima_auditoria = c3.date_input("Próxima auditoria prevista", value=(machine.proxima_auditoria or date.today()) if machine else date.today())
            c1, c2, c3, c4, c5 = st.columns(5)
            laudo = c1.checkbox("Laudo NR-12", value=machine.possui_laudo if machine else False)
            art = c2.checkbox("ART", value=machine.possui_art if machine else False)
            risco = c3.checkbox("Apreciação de risco", value=machine.possui_apreciacao_risco if machine else False)
            manual = c4.checkbox("Manual atualizado", value=machine.possui_manual_atualizado if machine else False)
            treinamento = c5.checkbox("Treinamento", value=machine.possui_treinamento if machine else False)
            observacoes = st.text_area("Observações", value=(machine.observacoes or "") if machine else "")
        submitted = st.form_submit_button("Salvar máquina")
    if submitted:
        if not codigo or not nome or not area:
            st.warning("Informe código, nome e área da máquina.")
        else:
            site = next(s for s in sites if s.codigo == site_label)
            obj = machine or NR12Maquina(codigo=codigo, site_id=site.id, area=area, nome=nome)
            obj.codigo = codigo; obj.site_id = site.id; obj.area = area; obj.linha_processo = linha; obj.nome = nome
            obj.fabricante = fabricante; obj.modelo = modelo; obj.numero_serie = serie; obj.ano = int(ano); obj.tipo_equipamento = tipo
            obj.responsavel_area = responsavel; obj.criticidade = criticidade; obj.status_nr12 = status
            obj.ultima_adequacao = ultima_adequacao; obj.ultima_auditoria = ultima_auditoria; obj.proxima_auditoria = proxima_auditoria
            obj.possui_laudo = laudo; obj.possui_art = art; obj.possui_apreciacao_risco = risco; obj.possui_manual_atualizado = manual; obj.possui_treinamento = treinamento; obj.observacoes = observacoes
            session.add(obj); session.flush(); update_machine_status(session, obj); session.commit(); st.success("Máquina salva."); st.rerun()
    df = nr12_maquinas_df(session, site_ids)
    st.download_button("Exportar inventário Excel", export_nr12_inventory_excel(session, site_ids), "inventario_nr12.xlsx")
    st.dataframe(df, use_container_width=True, hide_index=True)


def page_documentos(session, user):
    header("Documentos NR-12", "Controle documental por máquina, com vencimentos e documentos essenciais.")
    site_ids = _site_filter(session, user)
    machines = _machines(session, site_ids)
    if not machines:
        empty_state("Cadastre uma máquina para registrar documentos.")
        return
    machine = st.selectbox("Máquina", machines, format_func=lambda m: f"{m.codigo} · {m.nome}")
    with st.form("form_doc"):
        c1, c2 = st.columns(2)
        tipo = c1.selectbox("Tipo de documento", DOCUMENTOS_NR12)
        nome = c2.text_input("Nome do documento", value=f"{tipo} - {machine.codigo}")
        c1, c2, c3 = st.columns(3)
        emissao = c1.date_input("Emissão", value=date.today())
        validade = c2.date_input("Validade", value=date.today())
        responsavel = c3.text_input("Responsável")
        arquivo = st.file_uploader("Anexo")
        observacoes = st.text_area("Observações")
        submitted = st.form_submit_button("Salvar documento")
    if submitted:
        path = save_uploaded_file(arquivo, f"nr12_doc_{machine.codigo}") if arquivo else None
        session.add(NR12Documento(maquina_id=machine.id, tipo_documento=tipo, nome=nome, data_emissao=emissao, data_validade=validade, responsavel=responsavel, status=document_status(validade), caminho_arquivo=path, observacoes=observacoes))
        if tipo == "Laudo NR-12": machine.possui_laudo = True
        if tipo == "ART": machine.possui_art = True
        if tipo == "Apreciação de risco": machine.possui_apreciacao_risco = True
        update_machine_status(session, machine); session.commit(); st.success("Documento salvo."); st.rerun()
    df = nr12_documentos_df(session, site_ids)
    st.download_button("Exportar documentos Excel", export_nr12_documents_excel(session, site_ids), "documentos_nr12.xlsx")
    st.dataframe(df, use_container_width=True, hide_index=True)
    for doc in session.query(NR12Documento).filter_by(maquina_id=machine.id).all():
        if doc.caminho_arquivo and Path(doc.caminho_arquivo).exists():
            st.download_button(f"Baixar {doc.nome}", Path(doc.caminho_arquivo).read_bytes(), file_name=Path(doc.caminho_arquivo).name, key=f"doc_{doc.id}")
        elif doc.caminho_arquivo:
            st.caption(f"Arquivo indisponível fisicamente: {doc.nome}")


def page_verificacoes(session, user):
    header("Checklists e Inspeções NR-12", "Execução de checklists operacionais, inspeções de manutenção e auditorias EHS.")
    site_ids = _site_filter(session, user)
    machines = _machines(session, site_ids)
    if not machines:
        empty_state("Cadastre uma máquina para executar verificações.")
        return
    with st.form("nova_verificacao"):
        c1, c2, c3 = st.columns(3)
        machine = c1.selectbox("Máquina", machines, format_func=lambda m: f"{m.codigo} · {m.nome}")
        tipo = c2.selectbox("Tipo de verificação", TIPOS_VERIFICACAO_NR12)
        data_verificacao = c3.date_input("Data", value=date.today())
        auditor = st.text_input("Responsável pela verificação", value=user.nome)
        participantes = st.text_area("Participantes")
        criar = st.form_submit_button("Criar verificação")
    if criar:
        verificacao = create_nr12_verificacao(session, machine, tipo, auditor, data_verificacao, participantes)
        session.commit(); st.session_state["nr12_verificacao_id"] = verificacao.id; st.rerun()
    verificacoes = session.query(NR12Verificacao).order_by(NR12Verificacao.data_verificacao.desc(), NR12Verificacao.id.desc()).all()
    if verificacoes:
        ids = [v.id for v in verificacoes]
        current_id = st.selectbox("Verificação em edição", ids, index=ids.index(st.session_state.get("nr12_verificacao_id", ids[0])) if st.session_state.get("nr12_verificacao_id") in ids else 0, format_func=lambda vid: f"#{vid} · {session.get(NR12Verificacao, vid).tipo_verificacao}")
        verificacao = session.get(NR12Verificacao, current_id)
        rows = []
        query = session.query(NR12Resposta).filter_by(verificacao_id=current_id).join(NR12ChecklistItem, NR12Resposta.item_id == NR12ChecklistItem.id).order_by(NR12ChecklistItem.posicao)
        for resp in query:
            rows.append({"ID": resp.id, "Código": resp.item.codigo, "Pergunta": resp.item.pergunta, "Crítico": resp.item.critico, "Aplicável": resp.aplicavel, "Resultado": resp.resultado, "Comentário": resp.comentario or "", "Evidência": resp.evidencia or "", "Gerar PAC": resp.gerar_pac})
        edited = st.data_editor(pd.DataFrame(rows), use_container_width=True, hide_index=True, disabled=["ID", "Código", "Pergunta", "Crítico"], column_config={"Resultado": st.column_config.SelectboxColumn(options=["Conforme", "Não conforme", "Não aplicável"])})
        c1, c2 = st.columns(2)
        if c1.button("Salvar respostas"):
            apply_nr12_respostas(session, current_id, edited.to_dict("records")); session.commit(); st.success("Verificação salva."); st.rerun()
        if c2.button("Gerar PAC para desvios"):
            for row in edited.to_dict("records"):
                if row.get("Gerar PAC") or row.get("Resultado") == "Não conforme":
                    resp = session.get(NR12Resposta, int(row["ID"]))
                    exists = session.query(NR12PAC).filter_by(verificacao_id=current_id, item_id=resp.item_id).first()
                    if not exists:
                        session.add(NR12PAC(origem=verificacao.tipo_verificacao, site_id=verificacao.site_id, maquina_id=verificacao.maquina_id, verificacao_id=current_id, item_id=resp.item_id, descricao_desvio=row["Pergunta"], classificacao="Crítico" if row["Crítico"] else "Maior", responsavel=verificacao.maquina.responsavel_area, area_responsavel="Operação/Manutenção", prazo=date.today()))
            update_machine_status(session, verificacao.maquina); session.commit(); st.success("PACs gerados."); st.rerun()
    st.download_button("Exportar verificações Excel", export_nr12_audits_excel(session, site_ids), "verificacoes_nr12.xlsx")
    st.dataframe(nr12_verificacoes_df(session, site_ids), use_container_width=True, hide_index=True)


def page_pac_nr12(session, user):
    header("PAC NR-12", "Plano de Ação Corretiva para desvios de sustentação NR-12.")
    site_ids = _site_filter(session, user)
    machines = _machines(session, site_ids)
    with st.form("novo_pac_nr12"):
        machine = st.selectbox("Máquina", machines, format_func=lambda m: f"{m.codigo} · {m.nome}") if machines else None
        c1, c2, c3 = st.columns(3)
        origem = c1.text_input("Origem", value="Auditoria EHS")
        classificacao = c2.selectbox("Classificação", CLASSIFICACOES)
        prazo = c3.date_input("Prazo", value=date.today())
        descricao = st.text_area("Descrição do desvio")
        c1, c2 = st.columns(2)
        responsavel = c1.text_input("Responsável")
        area = c2.text_input("Área responsável")
        criar = st.form_submit_button("Criar PAC")
    if criar and machine and descricao:
        session.add(NR12PAC(origem=origem, site_id=machine.site_id, maquina_id=machine.id, descricao_desvio=descricao, classificacao=classificacao, responsavel=responsavel, area_responsavel=area, prazo=prazo, status="Aberto"))
        update_machine_status(session, machine); session.commit(); st.success("PAC criado."); st.rerun()
    df = nr12_pacs_df(session, site_ids)
    st.download_button("Exportar PAC Excel", export_nr12_pac_excel(session, site_ids), "pac_nr12.xlsx")
    st.dataframe(df, use_container_width=True, hide_index=True)


def page_moc_nr12(session, user):
    header("Gestão de Mudanças / MOC NR-12", "Controle de intervenções e mudanças com impacto em segurança de máquinas.")
    site_ids = _site_filter(session, user)
    machines = _machines(session, site_ids)
    if not machines:
        empty_state("Cadastre uma máquina para registrar MOC.")
        return
    with st.form("novo_moc"):
        machine = st.selectbox("Máquina", machines, format_func=lambda m: f"{m.codigo} · {m.nome}")
        c1, c2 = st.columns(2)
        tipo = c1.selectbox("Tipo de mudança", TIPOS_MUDANCA_CRITICA)
        data_mudanca = c2.date_input("Data", value=date.today())
        descricao = st.text_area("Descrição")
        c1, c2 = st.columns(2)
        solicitante = c1.text_input("Solicitante", value=user.nome)
        area = c2.text_input("Área solicitante")
        c1, c2, c3 = st.columns(3)
        impacta = c1.checkbox("Impacta segurança", value=True)
        exige_moc = c2.checkbox("Exige MOC", value=True)
        status = c3.selectbox("Status", ["Solicitada", "Em análise", "Implementada", "Encerrada", "Reprovada"])
        c1, c2, c3, c4 = st.columns(4)
        ehs = c1.checkbox("Aprovação EHS")
        manut = c2.checkbox("Aprovação Manutenção")
        eng = c3.checkbox("Aprovação Engenharia")
        prod = c4.checkbox("Aprovação Produção")
        c1, c2 = st.columns(2)
        pos = c1.checkbox("Exige auditoria pós-mudança")
        trein = c2.checkbox("Exige treinamento")
        anexo = st.file_uploader("Anexo MOC")
        criar = st.form_submit_button("Salvar MOC")
    if criar:
        path = save_uploaded_file(anexo, f"nr12_moc_{machine.codigo}") if anexo else None
        session.add(NR12MOC(maquina_id=machine.id, site_id=machine.site_id, tipo_mudanca=tipo, descricao=descricao, solicitante=solicitante, area_solicitante=area, data_mudanca=data_mudanca, impacta_seguranca=impacta, exige_moc=exige_moc, status=status, aprovacao_ehs=ehs, aprovacao_manutencao=manut, aprovacao_engenharia=eng, aprovacao_producao=prod, exige_auditoria_pos_mudanca=pos, exige_treinamento=trein, caminho_anexo=path))
        update_machine_status(session, machine); session.commit(); st.success("MOC salva."); st.rerun()
    df = nr12_mocs_df(session, site_ids)
    st.download_button("Exportar MOC Excel", export_nr12_moc_excel(session, site_ids), "moc_nr12.xlsx")
    st.dataframe(df, use_container_width=True, hide_index=True)


def page_termo_nr12(session, user):
    header("Termo de Garantia de Sustentação NR-12 do Site", "Consolidação anual para assinatura e validação da governança local.")
    sites = site_options(session, user)
    site = st.selectbox("Site", sites, format_func=lambda s: f"{s.codigo} · {s.nome}")
    ciclo = st.text_input("Ano/ciclo", value=str(date.today().year))
    k = nr12_kpis(session, [site.id])
    indicadores = {"Máquinas": k["total"], "Conformes": f"{k['conformes_pct']}%", "Observação": k["observacao"], "Pendentes": k["pendentes"], "Bloqueadas": k["bloqueadas"], "Docs vencidos": k["docs_vencidos"], "Auditorias vencidas": k["auditorias_vencidas"], "PACs críticos": k["pacs_criticos"], "MOCs sem validação": k["mocs_sem_validacao"]}
    cols = st.columns(5)
    for idx, (label, value) in enumerate(indicadores.items()):
        with cols[idx % 5]: kpi_card(label, value)
    with st.form("termo_nr12"):
        c1, c2 = st.columns(2)
        ehs = c1.text_input("Responsável EHS")
        manut = c2.text_input("Responsável Manutenção")
        c1, c2, c3 = st.columns(3)
        oper = c1.text_input("Responsável Produção/Operação")
        eng = c2.text_input("Responsável Engenharia")
        lider = c3.text_input("Liderança do site")
        declaracao = st.text_area("Declaração formal", value="O site declara possuir rotina ativa de sustentação da conformidade NR-12 para máquinas já adequadas, com governança local, controle documental, inspeções, PAC e gestão de mudanças.")
        ressalvas = st.text_area("Ressalvas e pendências")
        plano = st.text_area("Plano de ação associado")
        salvar = st.form_submit_button("Registrar termo")
    responsaveis = {"EHS": ehs, "Manutenção": manut, "Produção/Operação": oper, "Engenharia": eng, "Liderança": lider}
    st.download_button("Exportar Termo NR-12 em PDF", export_termo_pdf(site, ciclo, indicadores, responsaveis, declaracao, ressalvas, plano), f"termo_nr12_{site.codigo}_{ciclo}.pdf", mime="application/pdf")
    if salvar:
        session.add(NR12TermoGarantia(site_id=site.id, ciclo=ciclo, responsavel_ehs=ehs, responsavel_manutencao=manut, responsavel_operacao=oper, responsavel_engenharia=eng, lideranca_site=lider, declaracao=declaracao, ressalvas=ressalvas, plano_acao=plano))
        session.commit(); st.success("Termo registrado.")


def page_relatorios_nr12(session, user):
    header("Relatórios NR-12", "Exportações executivas de inventário, documentos, verificações, PAC, MOC e relatório por máquina.")
    site_ids = _site_filter(session, user)
    c1, c2, c3 = st.columns(3)
    c1.download_button("Inventário Excel", export_nr12_inventory_excel(session, site_ids), "inventario_nr12.xlsx")
    c2.download_button("Documentos Excel", export_nr12_documents_excel(session, site_ids), "documentos_nr12.xlsx")
    c3.download_button("Auditorias Excel", export_nr12_audits_excel(session, site_ids), "auditorias_nr12.xlsx")
    c1, c2 = st.columns(2)
    c1.download_button("PAC Excel", export_nr12_pac_excel(session, site_ids), "pac_nr12.xlsx")
    c2.download_button("MOC Excel", export_nr12_moc_excel(session, site_ids), "moc_nr12.xlsx")
    machines = _machines(session, site_ids)
    if machines:
        machine = st.selectbox("Relatório por máquina", machines, format_func=lambda m: f"{m.codigo} · {m.nome}")
        st.download_button("Exportar relatório por máquina em PDF", export_machine_pdf(session, machine.id), f"relatorio_{machine.codigo}.pdf", mime="application/pdf")
