from datetime import date, datetime, timedelta
from io import BytesIO
from pathlib import Path
from re import sub
from xml.sax.saxutils import escape

import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from audit_app.constants import DOCUMENTOS_ESSENCIAIS_NR12, STATUS_CONFORMIDADE, UPLOAD_DIR
from audit_app.models import Achado, Auditoria, ChecklistItemNR12, Diretiva, DocumentoNR12, EvidenciaArquivo, MaquinaNR12, MOCNR12, PACNR12, Requisito, RespostaChecklist, RespostaNR12, Site, TermoGarantiaNR12, VerificacaoNR12
from audit_app.seed import ensure_auditoria_checklist


def safe_filename(name):
    return sub(r"[^A-Za-z0-9._-]+", "_", Path(name).name).strip("._") or "arquivo"


def save_uploaded_file(uploaded_file, prefix):
    UPLOAD_DIR.mkdir(exist_ok=True)
    filename = safe_filename(uploaded_file.name)
    path = UPLOAD_DIR / f"{prefix}_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}_{filename}"
    path.write_bytes(uploaded_file.getbuffer())
    return filename, str(path)


def conformidade_percentual(df):
    if df.empty or "status" not in df:
        return 0.0
    valid = df[df["status"] != "Não Aplicável"]
    if valid.empty:
        return 0.0
    return round(float(valid["status"].map({"Conforme": 1, "Parcialmente Conforme": 0.5, "Não Conforme": 0}).fillna(0).mean() * 100), 1)


def maturidade_media(df):
    if df.empty or "nota_maturidade" not in df or "status" not in df:
        return 0.0
    valid = df[(df["status"] != "Não Aplicável") & (df["nota_maturidade"].notna())]
    return round(float(valid["nota_maturidade"].mean()), 2) if not valid.empty else 0.0


def respostas_df(session, auditoria_id=None, site_ids=None):
    q = session.query(RespostaChecklist, Auditoria, Requisito, Diretiva, Site).join(Auditoria).join(Requisito).join(Diretiva).join(Site, Auditoria.site_auditado_id == Site.id)
    if auditoria_id:
        q = q.filter(Auditoria.id == auditoria_id)
    if site_ids is not None:
        q = q.filter(Auditoria.site_auditado_id.in_(site_ids))
    rows = []
    for resp, aud, req, dir_, site in q.all():
        rows.append({"id": resp.id, "auditoria_id": aud.id, "auditoria": aud.nome, "site": site.codigo, "ciclo": aud.ciclo, "diretiva": dir_.titulo, "codigo_requisito": req.codigo_requisito, "pergunta": req.pergunta, "criticidade": req.criticidade, "aplicavel": resp.aplicavel, "status": resp.status_conformidade, "nota_maturidade": resp.nota_maturidade, "evidencia_verificada": resp.evidencia_verificada or "", "comentario_auditor": resp.comentario_auditor or "", "necessita_acao": resp.necessita_acao})
    return pd.DataFrame(rows)


def _pac_row(origem, site, maquina, auditoria, requisito, tipo, criticidade, descricao, responsavel, area, prazo, status):
    vencido = bool(prazo and prazo < date.today() and status not in ["Concluído", "Cancelado"])
    return {"origem": origem, "site": site, "maquina": maquina or "", "auditoria": auditoria or "", "requisito": requisito or "", "tipo_desvio": tipo or "", "criticidade": criticidade or "", "descricao": descricao or "", "responsavel": responsavel or "", "area_responsavel": area or "", "prazo": prazo, "status": "Vencido" if vencido else status, "vencido": vencido}


def achados_df(session, auditoria_id=None, site_ids=None):
    q = session.query(Achado, Auditoria, Site, Requisito).join(Auditoria, Achado.auditoria_id == Auditoria.id).join(Site, Achado.site_id == Site.id).outerjoin(Requisito, Achado.requisito_id == Requisito.id)
    if auditoria_id:
        q = q.filter(Auditoria.id == auditoria_id)
    if site_ids is not None:
        q = q.filter(Achado.site_id.in_(site_ids))
    rows = []
    for ach, aud, site, req in q.all():
        row = _pac_row("Auditoria Cruzada", site.codigo, "", aud.nome, req.codigo_requisito if req else "", ach.tipo_achado, ach.prioridade, ach.descricao, ach.responsavel, ach.area_responsavel, ach.prazo, ach.status)
        row["id"] = ach.id
        rows.append(row)
    return pd.DataFrame(rows)


def pac_nr12_df(session, site_ids=None):
    q = session.query(PACNR12, Site, MaquinaNR12).join(Site, PACNR12.site_id == Site.id).outerjoin(MaquinaNR12, PACNR12.maquina_id == MaquinaNR12.id)
    if site_ids is not None:
        q = q.filter(PACNR12.site_id.in_(site_ids))
    rows = []
    for pac, site, maq in q.all():
        row = _pac_row("NR-12", site.codigo, maq.codigo if maq else "", f"Verificação #{pac.verificacao_id}" if pac.verificacao_id else "", pac.item_codigo, pac.tipo_desvio, pac.criticidade, pac.descricao, pac.responsavel, pac.area_responsavel, pac.prazo, pac.status)
        row["id"] = pac.id
        rows.append(row)
    return pd.DataFrame(rows)


def pac_consolidado_df(session, site_ids=None):
    frames = [achados_df(session, site_ids=site_ids), pac_nr12_df(session, site_ids=site_ids)]
    frames = [f for f in frames if not f.empty]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def pontuacao_por(df, coluna):
    if df.empty or coluna not in df:
        return pd.DataFrame(columns=[coluna, "conformidade", "maturidade"])
    return pd.DataFrame([{coluna: v, "conformidade": conformidade_percentual(g), "maturidade": maturidade_media(g)} for v, g in df.groupby(coluna)])


def criar_auditoria(session, **data):
    if data["site_auditado_id"] == data["site_auditor_lider_id"]:
        raise ValueError("O site auditado deve ser diferente do site auditor líder.")
    auditoria = Auditoria(**data)
    session.add(auditoria)
    session.flush()
    ensure_auditoria_checklist(session, auditoria.id)
    return auditoria


def salvar_respostas(session, edited_df, avaliado_por):
    for row in edited_df.to_dict("records"):
        resp = session.get(RespostaChecklist, int(row["id"]))
        if resp:
            resp.aplicavel = bool(row.get("aplicavel", True))
            status = row.get("status", "Conforme")
            resp.status_conformidade = "Não Aplicável" if not resp.aplicavel else (status if status in STATUS_CONFORMIDADE else "Conforme")
            nota = row.get("nota_maturidade")
            resp.nota_maturidade = None if pd.isna(nota) else max(0, min(5, int(nota)))
            resp.evidencia_verificada = row.get("evidencia_verificada", "")
            resp.comentario_auditor = row.get("comentario_auditor", "")
            resp.necessita_acao = bool(row.get("necessita_acao", False))
            resp.avaliado_por = avaliado_por
            resp.data_avaliacao = datetime.utcnow()


def salvar_upload_ehs(uploaded_file, auditoria_id, requisito_id, achado_id, enviado_por, session):
    filename, path = save_uploaded_file(uploaded_file, f"ehs_aud{auditoria_id}_req{requisito_id}")
    session.add(EvidenciaArquivo(auditoria_id=auditoria_id, requisito_id=requisito_id, achado_id=achado_id, nome_arquivo=filename, caminho_arquivo=path, tipo_arquivo=getattr(uploaded_file, "type", None), enviado_por=enviado_por))


def documento_status(doc):
    if not doc.data_validade:
        return "Sem validade"
    if doc.data_validade < date.today():
        return "Vencido"
    if doc.data_validade <= date.today() + timedelta(days=60):
        return "Próximo do vencimento"
    return "Válido"


def documentos_df(session, site_ids=None):
    q = session.query(DocumentoNR12, MaquinaNR12, Site).join(MaquinaNR12).join(Site)
    if site_ids is not None:
        q = q.filter(MaquinaNR12.site_id.in_(site_ids))
    return pd.DataFrame([{"id": d.id, "site": s.codigo, "maquina": m.codigo, "tipo_documento": d.tipo_documento, "titulo": d.titulo, "emissao": d.data_emissao, "validade": d.data_validade, "status": documento_status(d), "responsavel": d.responsavel or "", "arquivo": d.nome_arquivo or ""} for d, m, s in q.all()])


def maquinas_df(session, site_ids=None):
    q = session.query(MaquinaNR12, Site).join(Site)
    if site_ids is not None:
        q = q.filter(MaquinaNR12.site_id.in_(site_ids))
    return pd.DataFrame([{"id": m.id, "site": s.codigo, "codigo": m.codigo, "nome": m.nome, "area_setor": m.area_setor, "linha_processo": m.linha_processo, "tipo_equipamento": m.tipo_equipamento, "criticidade": m.criticidade, "status_nr12": m.status_nr12, "responsavel_area": m.responsavel_area, "ultima_auditoria": m.ultima_auditoria, "proxima_auditoria_prevista": m.proxima_auditoria_prevista} for m, s in q.order_by(Site.codigo, MaquinaNR12.codigo).all()])


def calcular_status_maquina(session, maquina):
    if maquina.status_nr12 in ["Fora de uso", "Não aplicável"]:
        return maquina.status_nr12
    pac_critico = session.query(PACNR12).filter(PACNR12.maquina_id == maquina.id, PACNR12.criticidade.in_(["Crítico", "Crítica"]), PACNR12.status.notin_(["Concluído", "Cancelado"])).count()
    moc_pendente = session.query(MOCNR12).filter(MOCNR12.maquina_id == maquina.id, MOCNR12.impacta_seguranca.is_(True), MOCNR12.validacao_final != "Aprovada", MOCNR12.status.notin_(["Cancelada", "Concluída sem impacto"])).count()
    if pac_critico or moc_pendente:
        return "Bloqueada por desvio crítico"
    docs = session.query(DocumentoNR12).filter(DocumentoNR12.maquina_id == maquina.id, DocumentoNR12.tipo_documento.in_(DOCUMENTOS_ESSENCIAIS_NR12), DocumentoNR12.ativo.is_(True)).all()
    validos = {d.tipo_documento for d in docs if documento_status(d) in ["Válido", "Sem validade"]}
    flags = {"Apreciação de risco": maquina.possui_apreciacao_risco, "Laudo NR-12": maquina.possui_laudo_nr12, "ART": maquina.possui_art}
    if not all(tipo in validos or flags.get(tipo) for tipo in DOCUMENTOS_ESSENCIAIS_NR12):
        return "Pendente de ação não crítica"
    if maquina.proxima_auditoria_prevista and maquina.proxima_auditoria_prevista < date.today():
        return "Conforme com observação"
    return "Conforme"


def recalcular_status_maquina(session, maquina):
    maquina.status_nr12 = calcular_status_maquina(session, maquina)
    return maquina.status_nr12


def ensure_verificacao_itens(session, verificacao):
    existentes = {r.item_id for r in session.query(RespostaNR12).filter_by(verificacao_id=verificacao.id)}
    for item in session.query(ChecklistItemNR12).filter_by(tipo_verificacao=verificacao.tipo_verificacao, ativo=True).order_by(ChecklistItemNR12.codigo):
        if item.id not in existentes:
            session.add(RespostaNR12(verificacao_id=verificacao.id, item_id=item.id, aplicavel=True, status="Conforme"))
    session.flush()


def finalizar_verificacao_nr12(session, verificacao):
    respostas = session.query(RespostaNR12).filter_by(verificacao_id=verificacao.id).all()
    aplicaveis = [r for r in respostas if r.aplicavel]
    score = round(sum({"Conforme": 1, "Conforme com observação": 0.7, "Não Conforme": 0}.get(r.status, 0) for r in aplicaveis) / len(aplicaveis) * 100, 1) if aplicaveis else 0
    critico_nc = any(r.status == "Não Conforme" and r.item.criticidade == "Crítico" for r in aplicaveis)
    verificacao.pontuacao = score
    verificacao.resultado = "Bloqueada por desvio crítico" if critico_nc else ("Pendente de ação não crítica" if score < 70 else ("Conforme com observação" if score < 90 else "Conforme"))
    verificacao.maquina.ultima_auditoria = verificacao.data_verificacao
    verificacao.maquina.proxima_auditoria_prevista = verificacao.proxima_verificacao or (verificacao.data_verificacao + timedelta(days=180))
    for r in respostas:
        if r.aplicavel and r.status == "Não Conforme" and not session.query(PACNR12).filter_by(verificacao_id=verificacao.id, item_codigo=r.item.codigo, maquina_id=verificacao.maquina_id).one_or_none():
            session.add(PACNR12(site_id=verificacao.site_id, maquina_id=verificacao.maquina_id, verificacao_id=verificacao.id, item_codigo=r.item.codigo, tipo_desvio="Item não conforme", criticidade="Crítico" if r.item.criticidade == "Crítico" else "Alta", descricao=r.item.pergunta, evidencia=r.evidencia, risco="Perda de condição segura NR-12", prazo=date.today() + timedelta(days=15 if r.item.criticidade == "Crítico" else 30), status="Aberto"))
    recalcular_status_maquina(session, verificacao.maquina)


def dashboard_integrado_kpis(session, site_ids=None):
    df_ehs = respostas_df(session, site_ids=site_ids)
    pac = pac_consolidado_df(session, site_ids=site_ids)
    mq = maquinas_df(session, site_ids=site_ids)
    docs = documentos_df(session, site_ids=site_ids)
    q_aud = session.query(Auditoria)
    q_moc = session.query(MOCNR12)
    if site_ids is not None:
        q_aud = q_aud.filter(Auditoria.site_auditado_id.in_(site_ids))
        q_moc = q_moc.filter(MOCNR12.site_id.in_(site_ids))
    datas = pd.to_datetime(mq["proxima_auditoria_prevista"], errors="coerce") if not mq.empty else pd.Series(dtype="datetime64[ns]")
    return {"aud_planejadas": q_aud.filter_by(status="Planejada").count(), "aud_andamento": q_aud.filter_by(status="Em andamento").count(), "aud_concluidas": q_aud.filter_by(status="Concluída").count(), "conformidade_ehs": conformidade_percentual(df_ehs), "maturidade_ehs": maturidade_media(df_ehs), "pacs_abertos": int(pac["status"].isin(["Aberto", "Em andamento", "Vencido"]).sum()) if not pac.empty else 0, "pacs_vencidos": int(pac["vencido"].sum()) if not pac.empty else 0, "nc_criticas": int(pac["criticidade"].isin(["Crítico", "Crítica"]).sum()) if not pac.empty else 0, "maquinas_total": len(mq), "maquinas_conformes": int((mq["status_nr12"] == "Conforme").sum()) if not mq.empty else 0, "maquinas_observacao": int((mq["status_nr12"] == "Conforme com observação").sum()) if not mq.empty else 0, "maquinas_pendentes": int((mq["status_nr12"] == "Pendente de ação não crítica").sum()) if not mq.empty else 0, "maquinas_bloqueadas": int((mq["status_nr12"] == "Bloqueada por desvio crítico").sum()) if not mq.empty else 0, "auditorias_nr12_vencidas": int((datas.notna() & (datas.dt.date < date.today())).sum()) if not datas.empty else 0, "documentos_vencidos": int((docs["status"] == "Vencido").sum()) if not docs.empty else 0, "mocs_pendentes": q_moc.filter(MOCNR12.impacta_seguranca.is_(True), MOCNR12.validacao_final != "Aprovada").count()}


def to_excel_bytes(sheets):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for name, df in sheets.items():
            (df if not df.empty else pd.DataFrame()).to_excel(writer, index=False, sheet_name=name[:31])
    output.seek(0)
    return output.read()


def build_pdf(title, blocks):
    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4)
    styles = getSampleStyleSheet()
    story = [Paragraph(escape(title), styles["Title"]), Spacer(1, 10)]
    for h, t in blocks:
        story += [Paragraph(escape(str(h)), styles["Heading2"]), Paragraph(escape(str(t)), styles["BodyText"]), Spacer(1, 8)]
    doc.build(story)
    output.seek(0)
    return output.read()


def export_checklist_excel(session, auditoria_id):
    return to_excel_bytes({"Checklist": respostas_df(session, auditoria_id)})


def export_plano_acao_excel(session, auditoria_id):
    return to_excel_bytes({"PAC Auditoria": achados_df(session, auditoria_id)})


def export_relatorio_pdf(session, auditoria_id):
    auditoria = session.get(Auditoria, auditoria_id)
    df = respostas_df(session, auditoria_id)
    return build_pdf(f"Relatório de Auditoria Cruzada #{auditoria_id}", [("Auditoria", auditoria.nome if auditoria else ""), ("Resultado", f"Conformidade: {conformidade_percentual(df)}% | Maturidade: {maturidade_media(df)}")])


def export_relatorio_maquina_pdf(session, maquina_id):
    maquina = session.get(MaquinaNR12, maquina_id)
    return build_pdf("Relatório por Máquina", [("Máquina", f"{maquina.codigo} - {maquina.nome}" if maquina else "Máquina não encontrada"), ("Status", maquina.status_nr12 if maquina else "")])


def termo_resumo(session, site_id):
    mq = maquinas_df(session, [site_id])
    docs = documentos_df(session, [site_id])
    pac = pac_nr12_df(session, [site_id])
    datas = pd.to_datetime(mq["proxima_auditoria_prevista"], errors="coerce") if not mq.empty else pd.Series(dtype="datetime64[ns]")
    return {"maquinas": len(mq), "conformes": int((mq["status_nr12"] == "Conforme").sum()) if not mq.empty else 0, "observacao": int((mq["status_nr12"] == "Conforme com observação").sum()) if not mq.empty else 0, "pendentes": int((mq["status_nr12"] == "Pendente de ação não crítica").sum()) if not mq.empty else 0, "bloqueadas": int((mq["status_nr12"] == "Bloqueada por desvio crítico").sum()) if not mq.empty else 0, "documentos_pendentes": int(docs["status"].isin(["Vencido", "Próximo do vencimento"]).sum()) if not docs.empty else 0, "auditorias_vencidas": int((datas.notna() & (datas.dt.date < date.today())).sum()) if not datas.empty else 0, "pac_criticos": int(pac["criticidade"].isin(["Crítico", "Crítica"]).sum()) if not pac.empty else 0, "pac_vencidos": int(pac["vencido"].sum()) if not pac.empty else 0, "mocs_pendentes": session.query(MOCNR12).filter(MOCNR12.site_id == site_id, MOCNR12.impacta_seguranca.is_(True), MOCNR12.validacao_final != "Aprovada").count()}


def export_termo_garantia_pdf(session, termo_id):
    termo = session.get(TermoGarantiaNR12, termo_id)
    if not termo:
        return build_pdf("Termo de Garantia NR-12", [("Registro", "Termo não encontrado")])
    r = termo_resumo(session, termo.site_id)
    return build_pdf("Termo de Garantia de Sustentação da Conformidade NR-12 do Site", [("Resumo", f"Site {termo.site.codigo} | Máquinas {r['maquinas']} | Conformes {r['conformes']} | Bloqueadas {r['bloqueadas']}"), ("Declaração", termo.declaracao or "O site possui rotina ativa de sustentação NR-12."), ("Ressalvas", termo.ressalvas or "Sem ressalvas registradas.")])
