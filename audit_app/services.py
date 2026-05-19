from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from audit_app.constants import ACHADOS_COLUMNS, APP_TITLE, RESPOSTAS_COLUMNS, UPLOAD_DIR
from audit_app.models import Achado, Auditoria, Diretiva, EvidenciaArquivo, Requisito, RespostaChecklist, Site
from audit_app.seed import ensure_auditoria_checklist


def conformidade_percentual(df):
    if df.empty or "status" not in df:
        return 0.0
    valid = df[df["status"] != "Não Aplicável"]
    if valid.empty:
        return 0.0
    pontos = valid["status"].map({"Conforme": 1, "Parcialmente Conforme": 0.5, "Não Conforme": 0, "Não Aplicável": None}).fillna(0)
    return round(float(pontos.mean() * 100), 1)


def maturidade_media(df):
    if df.empty or "nota_maturidade" not in df or "status" not in df:
        return 0.0
    valid = df[(df["status"] != "Não Aplicável") & (df["nota_maturidade"].notna())]
    return round(float(valid["nota_maturidade"].mean()), 2) if not valid.empty else 0.0


def classificar_resultado(conformidade, nc_critica_aberta=False):
    if conformidade >= 90 and not nc_critica_aberta:
        return "Referência / Maduro"
    if conformidade >= 75:
        return "Conforme com oportunidades de melhoria"
    if conformidade >= 50:
        return "Parcialmente conforme / requer plano robusto"
    return "Não conforme / requer intervenção"


def respostas_df(session, auditoria_id=None):
    q = session.query(RespostaChecklist, Auditoria, Requisito, Diretiva, Site).join(Auditoria, RespostaChecklist.auditoria_id == Auditoria.id).join(Requisito, RespostaChecklist.requisito_id == Requisito.id).join(Diretiva, Requisito.diretiva_id == Diretiva.id).join(Site, Auditoria.site_auditado_id == Site.id)
    if auditoria_id:
        q = q.filter(Auditoria.id == auditoria_id)
    rows = []
    for resp, aud, req, dir_, site in q.all():
        rows.append({"id": resp.id, "auditoria_id": aud.id, "auditoria": aud.nome, "site": site.codigo, "ciclo": aud.ciclo, "diretiva": dir_.titulo, "codigo_requisito": req.codigo_requisito, "pergunta": req.pergunta, "criticidade": req.criticidade, "aplicavel": resp.aplicavel, "status": resp.status_conformidade, "nota_maturidade": resp.nota_maturidade, "evidencia_verificada": resp.evidencia_verificada or "", "comentario_auditor": resp.comentario_auditor or "", "necessita_acao": resp.necessita_acao})
    return pd.DataFrame(rows, columns=RESPOSTAS_COLUMNS)


def achados_df(session, auditoria_id=None):
    q = session.query(Achado, Auditoria, Site, Requisito).join(Auditoria, Achado.auditoria_id == Auditoria.id).join(Site, Achado.site_id == Site.id).outerjoin(Requisito, Achado.requisito_id == Requisito.id)
    if auditoria_id:
        q = q.filter(Auditoria.id == auditoria_id)
    rows = []
    today = date.today()
    for ach, aud, site, req in q.all():
        vencido = bool(ach.prazo and ach.prazo < today and ach.status not in ["Concluído", "Cancelado"])
        rows.append({"id": ach.id, "auditoria": aud.nome, "site": site.codigo, "requisito": req.codigo_requisito if req else "-", "tipo_achado": ach.tipo_achado, "descricao": ach.descricao, "responsavel": ach.responsavel or "", "prazo": ach.prazo, "status": "Vencido" if vencido else ach.status, "prioridade": ach.prioridade, "vencido": vencido})
    return pd.DataFrame(rows, columns=ACHADOS_COLUMNS)


def pontuacao_por(df, coluna):
    if df.empty or coluna not in df:
        return pd.DataFrame(columns=[coluna, "conformidade", "maturidade"])
    rows = [{coluna: valor, "conformidade": conformidade_percentual(grupo), "maturidade": maturidade_media(grupo)} for valor, grupo in df.groupby(coluna)]
    return pd.DataFrame(rows, columns=[coluna, "conformidade", "maturidade"])


def dashboard_kpis(session):
    df = respostas_df(session)
    ach = achados_df(session)
    return {
        "planejadas": session.query(Auditoria).filter_by(status="Planejada").count(),
        "em_andamento": session.query(Auditoria).filter_by(status="Em andamento").count(),
        "concluidas": session.query(Auditoria).filter_by(status="Concluída").count(),
        "conformidade_media": conformidade_percentual(df),
        "maturidade_media": maturidade_media(df),
        "achados_abertos": int(ach["status"].isin(["Aberto", "Em andamento", "Vencido"]).sum()) if not ach.empty else 0,
        "achados_vencidos": int(ach["vencido"].sum()) if not ach.empty else 0,
        "nc_criticas_abertas": session.query(Achado).filter(Achado.tipo_achado == "Não conformidade crítica", Achado.status.in_(["Aberto", "Em andamento", "Vencido"])).count(),
    }


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
        if not resp:
            continue
        nota = row.get("nota_maturidade")
        resp.aplicavel = bool(row.get("aplicavel", True))
        resp.status_conformidade = "Não Aplicável" if not resp.aplicavel else row.get("status", "Conforme")
        resp.nota_maturidade = None if pd.isna(nota) else max(0, min(5, int(nota)))
        resp.evidencia_verificada = row.get("evidencia_verificada", "")
        resp.comentario_auditor = row.get("comentario_auditor", "")
        resp.necessita_acao = bool(row.get("necessita_acao", False))
        resp.avaliado_por = avaliado_por
        resp.data_avaliacao = datetime.utcnow()


def salvar_upload(uploaded_file, auditoria_id, requisito_id, achado_id, enviado_por, session):
    UPLOAD_DIR.mkdir(exist_ok=True)
    safe_name = Path(uploaded_file.name).name
    path = UPLOAD_DIR / f"aud{auditoria_id}_req{requisito_id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}_{safe_name}"
    path.write_bytes(uploaded_file.getbuffer())
    session.add(EvidenciaArquivo(auditoria_id=auditoria_id, requisito_id=requisito_id, achado_id=achado_id, nome_arquivo=safe_name, caminho_arquivo=str(path), tipo_arquivo=getattr(uploaded_file, "type", None), enviado_por=enviado_por))


def export_checklist_excel(session, auditoria_id):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        respostas_df(session, auditoria_id).to_excel(writer, index=False, sheet_name="Checklist")
    output.seek(0)
    return output.read()


def export_plano_acao_excel(session, auditoria_id):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        achados_df(session, auditoria_id).to_excel(writer, index=False, sheet_name="PAC")
    output.seek(0)
    return output.read()


def pdf_text(value):
    return escape("" if value is None else str(value))


def export_relatorio_pdf(session, auditoria_id):
    auditoria = session.get(Auditoria, auditoria_id)
    df = respostas_df(session, auditoria_id)
    ach = achados_df(session, auditoria_id)
    conformidade = conformidade_percentual(df)
    maturidade = maturidade_media(df)
    nc_critica = bool(not ach.empty and ((ach["tipo_achado"] == "Não conformidade crítica") & (ach["status"].isin(["Aberto", "Em andamento", "Vencido"]))).any())
    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4)
    styles = getSampleStyleSheet()
    story = [Paragraph(APP_TITLE, styles["Title"]), Spacer(1, 10)]
    story.append(Paragraph(f"Auditoria: {pdf_text(auditoria.nome if auditoria else auditoria_id)}", styles["Heading2"]))
    story.append(Paragraph(f"Conformidade: {conformidade}% | Maturidade: {maturidade} | Resultado: {pdf_text(classificar_resultado(conformidade, nc_critica))}", styles["BodyText"]))
    story.append(Spacer(1, 12))
    resultado = pontuacao_por(df, "diretiva")
    table_data = [["Categoria", "Conformidade", "Maturidade"]] + resultado.round(2).astype(str).values.tolist() if not resultado.empty else [["Categoria", "Conformidade", "Maturidade"]]
    table = Table(table_data, repeatRows=1)
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#12263f")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("GRID", (0, 0), (-1, -1), 0.25, colors.grey), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold")]))
    story.append(table)
    story.append(Spacer(1, 12))
    story.append(Paragraph("Principais registros do PAC", styles["Heading2"]))
    if ach.empty:
        story.append(Paragraph("Não há registros de PAC para esta auditoria.", styles["BodyText"]))
    else:
        for item in ach.head(10).to_dict("records"):
            story.append(Paragraph(f"{pdf_text(item['tipo_achado'])} - {pdf_text(item['descricao'])} - {pdf_text(item['status'])}", styles["BodyText"]))
    story.append(Spacer(1, 12))
    story.append(Paragraph("Conclusão: utilizar este relatório como base para reunião de fechamento, priorização do PAC e acompanhamento de EHS.", styles["BodyText"]))
    doc.build(story)
    output.seek(0)
    return output.read()
