from __future__ import annotations

from io import BytesIO

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy.orm import Session

from .calculations import achados_df, pontuacao_por, respostas_df, resumo_auditoria
from .models import Achado, Auditoria


def export_checklist_excel(session: Session, auditoria_id: int) -> bytes:
    df = respostas_df(session, auditoria_id)
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Checklist")
        pontuacao_por(df, "diretiva").to_excel(writer, index=False, sheet_name="Resumo GdT")
    return output.getvalue()


def export_plano_acao_excel(session: Session, auditoria_id: int | None = None) -> bytes:
    df = achados_df(session)
    if auditoria_id and not df.empty:
        df = df[df["auditoria_id"] == auditoria_id]
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Plano de Ação")
    return output.getvalue()


def export_relatorio_pdf(session: Session, auditoria_id: int) -> bytes:
    auditoria = session.get(Auditoria, auditoria_id)
    if not auditoria:
        raise ValueError("Auditoria não encontrada.")
    resumo = resumo_auditoria(session, auditoria_id)
    df = respostas_df(session, auditoria_id)
    por_gdt = pontuacao_por(df, "diretiva")
    achados = session.query(Achado).filter_by(auditoria_id=auditoria_id).all()
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, title=f"Relatório {auditoria.nome}")
    styles = getSampleStyleSheet()
    story = [Paragraph("Relatório de Auditoria Cruzada GdTs / EHS Directives", styles["Title"]), Spacer(1, 12)]
    site = auditoria.site_auditado.codigo if auditoria.site_auditado else "-"
    story.append(Paragraph(f"<b>Auditoria:</b> {auditoria.nome}<br/><b>Site auditado:</b> {site}<br/><b>Equipe:</b> {auditoria.auditor_lider} / {auditoria.auditor_apoio or '-'}<br/><b>Período:</b> {auditoria.data_inicio or '-'} a {auditoria.data_fim or '-'}<br/><b>Escopo:</b> {auditoria.escopo or '-'}", styles["BodyText"]))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"<b>Resumo executivo:</b> conformidade {resumo['conformidade']}%, maturidade {resumo['maturidade']} e classificação {resumo['classificacao']}.", styles["BodyText"]))
    story.append(Spacer(1, 12))
    data = [["GdT", "Conformidade %", "Maturidade"]] + por_gdt.fillna(0).values.tolist()[:30]
    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E79")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("GRID", (0, 0), (-1, -1), 0.25, colors.grey), ("FONTSIZE", (0, 0), (-1, -1), 8)]))
    story.extend([Paragraph("Resultado por GdT", styles["Heading2"]), table, Spacer(1, 12)])
    story.append(Paragraph("Principais achados e plano de ação", styles["Heading2"]))
    for ach in achados[:20]:
        story.append(Paragraph(f"<b>{ach.tipo_achado}</b> — {ach.descricao[:250]}<br/>Responsável: {ach.responsavel or '-'} | Prazo: {ach.prazo or '-'} | Status: {ach.status}", styles["BodyText"]))
        story.append(Spacer(1, 6))
    boas = [a for a in achados if a.tipo_achado == "Boa prática"]
    if boas:
        story.append(Paragraph("Boas práticas: " + "; ".join(a.descricao[:120] for a in boas), styles["BodyText"]))
    story.append(Spacer(1, 12))
    story.append(Paragraph("Conclusão: usar este relatório como base para reunião de fechamento, priorização de CAPAs e acompanhamento LAG/EHS Local.", styles["BodyText"]))
    doc.build(story)
    return buffer.getvalue()
