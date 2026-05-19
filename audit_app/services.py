from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from re import sub
from xml.sax.saxutils import escape

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from audit_app.constants import STATUS_CONFORMIDADE, UPLOAD_DIR
from audit_app.models import Achado, Auditoria, Diretiva, EvidenciaArquivo, Requisito, RespostaChecklist, Site
from audit_app.seed import ensure_auditoria_checklist


def safe_filename(name):
    stem = Path(name).name
    stem = sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._")
    return stem or "arquivo"


def save_uploaded_file(uploaded_file, prefix):
    UPLOAD_DIR.mkdir(exist_ok=True)
    filename = safe_filename(uploaded_file.name)
    path = UPLOAD_DIR / f"{prefix}_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}_{filename}"
    path.write_bytes(uploaded_file.getbuffer())
    return filename, str(path)


def normalizar_nota_maturidade(value):
    if value is None or pd.isna(value):
        return None
    try:
        return max(0, min(5, int(value)))
    except (TypeError, ValueError):
        return None


def conformidade_percentual(df):
    if df.empty or "status" not in df:
        return 0.0
    valid = df[df["status"] != "Não Aplicável"]
    if valid.empty:
        return 0.0
    pontos = valid["status"].map({"Conforme": 1, "Parcialmente Conforme": 0.5, "Não Conforme": 0}).fillna(0)
    return round(float(pontos.mean() * 100), 1)


def maturidade_media(df):
    if df.empty or "nota_maturidade" not in df or "status" not in df:
        return 0.0
    valid = df[(df["status"] != "Não Aplicável") & (df["nota_maturidade"].notna())]
    return round(float(valid["nota_maturidade"].mean()), 2) if not valid.empty else 0.0


def respostas_df(session, auditoria_id=None, site_ids=None):
    q = (
        session.query(RespostaChecklist, Auditoria, Requisito, Diretiva, Site)
        .select_from(RespostaChecklist)
        .join(Auditoria, RespostaChecklist.auditoria_id == Auditoria.id)
        .join(Requisito, RespostaChecklist.requisito_id == Requisito.id)
        .join(Diretiva, Requisito.diretiva_id == Diretiva.id)
        .join(Site, Auditoria.site_auditado_id == Site.id)
    )
    if auditoria_id:
        q = q.filter(Auditoria.id == auditoria_id)
    if site_ids is not None:
        q = q.filter(Auditoria.site_auditado_id.in_(site_ids))
    rows = []
    for resp, aud, req, dir_, site in q.all():
        rows.append(
            {
                "id": resp.id,
                "auditoria_id": aud.id,
                "auditoria": aud.nome,
                "site": site.codigo,
                "ciclo": aud.ciclo,
                "diretiva": dir_.titulo,
                "codigo_requisito": req.codigo_requisito,
                "pergunta": req.pergunta,
                "criticidade": req.criticidade,
                "aplicavel": resp.aplicavel,
                "status": resp.status_conformidade,
                "nota_maturidade": resp.nota_maturidade,
                "evidencia_verificada": resp.evidencia_verificada or "",
                "comentario_auditor": resp.comentario_auditor or "",
                "necessita_acao": resp.necessita_acao,
            }
        )
    return pd.DataFrame(rows)


def achados_df(session, auditoria_id=None, site_ids=None):
    q = (
        session.query(Achado, Auditoria, Site, Requisito)
        .select_from(Achado)
        .join(Auditoria, Achado.auditoria_id == Auditoria.id)
        .join(Site, Achado.site_id == Site.id)
        .outerjoin(Requisito, Achado.requisito_id == Requisito.id)
    )
    if auditoria_id:
        q = q.filter(Auditoria.id == auditoria_id)
    if site_ids is not None:
        q = q.filter(Achado.site_id.in_(site_ids))
    rows = []
    today = date.today()
    for ach, aud, site, req in q.all():
        vencido = bool(ach.prazo and ach.prazo < today and ach.status not in ["Concluído", "Cancelado"])
        rows.append(
            {
                "id": ach.id,
                "origem": "Auditoria Cruzada",
                "auditoria": aud.nome,
                "site": site.codigo,
                "maquina": "",
                "requisito": req.codigo_requisito if req else "-",
                "tipo_desvio": ach.tipo_achado,
                "criticidade": ach.prioridade,
                "descricao": ach.descricao,
                "responsavel": ach.responsavel or "",
                "area_responsavel": ach.area_responsavel or "",
                "prazo": ach.prazo,
                "status": "Vencido" if vencido else ach.status,
                "vencido": vencido,
            }
        )
    return pd.DataFrame(rows)


def pontuacao_por(df, coluna):
    if df.empty or coluna not in df:
        return pd.DataFrame(columns=[coluna, "conformidade", "maturidade"])
    rows = [
        {coluna: valor, "conformidade": conformidade_percentual(grupo), "maturidade": maturidade_media(grupo)}
        for valor, grupo in df.groupby(coluna)
    ]
    return pd.DataFrame(rows)


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
        resp.aplicavel = bool(row.get("aplicavel", True))
        status = row.get("status", "Conforme")
        resp.status_conformidade = "Não Aplicável" if not resp.aplicavel else (status if status in STATUS_CONFORMIDADE else "Conforme")
        resp.nota_maturidade = normalizar_nota_maturidade(row.get("nota_maturidade"))
        resp.evidencia_verificada = row.get("evidencia_verificada", "")
        resp.comentario_auditor = row.get("comentario_auditor", "")
        resp.necessita_acao = bool(row.get("necessita_acao", False))
        resp.avaliado_por = avaliado_por
        resp.data_avaliacao = datetime.utcnow()


def salvar_upload_ehs(uploaded_file, auditoria_id, requisito_id, achado_id, enviado_por, session):
    filename, path = save_uploaded_file(uploaded_file, f"ehs_aud{auditoria_id}_req{requisito_id}")
    session.add(
        EvidenciaArquivo(
            auditoria_id=auditoria_id,
            requisito_id=requisito_id,
            achado_id=achado_id,
            nome_arquivo=filename,
            caminho_arquivo=path,
            tipo_arquivo=getattr(uploaded_file, "type", None),
            enviado_por=enviado_por,
        )
    )


def to_excel_bytes(sheets):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for name, df in sheets.items():
            (df if not df.empty else pd.DataFrame()).to_excel(writer, index=False, sheet_name=name[:31])
    output.seek(0)
    return output.read()


def export_checklist_excel(session, auditoria_id):
    return to_excel_bytes({"Checklist": respostas_df(session, auditoria_id)})


def export_plano_acao_excel(session, auditoria_id):
    return to_excel_bytes({"PAC Auditoria": achados_df(session, auditoria_id)})


def pdf_text(value):
    return escape("" if value is None else str(value))


def build_pdf(title, blocks, tables=None):
    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4, rightMargin=32, leftMargin=32, topMargin=32, bottomMargin=32)
    styles = getSampleStyleSheet()
    story = [Paragraph(pdf_text(title), styles["Title"]), Spacer(1, 10)]
    for heading, text in blocks:
        story.append(Paragraph(pdf_text(heading), styles["Heading2"]))
        story.append(Paragraph(pdf_text(text), styles["BodyText"]))
        story.append(Spacer(1, 8))
    for table_title, df in (tables or []):
        story.append(Paragraph(pdf_text(table_title), styles["Heading2"]))
        data = [list(df.columns)] + df.fillna("").astype(str).head(30).values.tolist() if not df.empty else [["Sem registros"]]
        table = Table(data, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#12263f")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 7),
                ]
            )
        )
        story.append(table)
        story.append(Spacer(1, 10))
    doc.build(story)
    output.seek(0)
    return output.read()


def export_relatorio_pdf(session, auditoria_id):
    auditoria = session.get(Auditoria, auditoria_id)
    df = respostas_df(session, auditoria_id)
    ach = achados_df(session, auditoria_id)
    return build_pdf(
        f"Relatório de Auditoria Cruzada #{auditoria_id}",
        [
            ("Auditoria", auditoria.nome if auditoria else ""),
            ("Resultado", f"Conformidade: {conformidade_percentual(df)}% | Maturidade: {maturidade_media(df)}"),
        ],
        [
            ("Resultado por categoria", pontuacao_por(df, "diretiva")),
            ("PAC", ach[["site", "tipo_desvio", "criticidade", "status", "prazo"]] if not ach.empty else ach),
        ],
    )
