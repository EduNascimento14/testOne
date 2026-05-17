from __future__ import annotations

from io import BytesIO
import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from sqlalchemy.orm import Session
from models import ActionPlan, Audit, ChangeManagement, Document, Machine, Site
from utils.calculations import actions_df, machines_df


def dataframe_to_excel(df: pd.DataFrame, sheet_name: str = "Dados") -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name[:31])
        ws = writer.sheets[sheet_name[:31]]
        for column_cells in ws.columns:
            length = max(len(str(cell.value or "")) for cell in column_cells)
            ws.column_dimensions[column_cells[0].column_letter].width = min(max(length + 2, 12), 60)
    return buffer.getvalue()


def export_inventory_excel(session: Session) -> bytes:
    return dataframe_to_excel(machines_df(session), "Inventario")


def export_actions_excel(session: Session) -> bytes:
    return dataframe_to_excel(actions_df(session), "Plano de Acao")


def export_documents_excel(session: Session) -> bytes:
    rows = []
    for d in session.query(Document).join(Machine).join(Site).all():
        rows.append({"Site": d.machine.site.code, "Máquina": d.machine.machine_code, "Tipo": d.document_type, "Nome": d.name, "Emissão": d.issue_date, "Validade": d.expiry_date, "Responsável": d.responsible, "Status": d.status, "Arquivo": d.file_path})
    return dataframe_to_excel(pd.DataFrame(rows), "Documentos")


def export_audits_excel(session: Session) -> bytes:
    rows = []
    for a in session.query(Audit).join(Machine).join(Site).all():
        rows.append({"ID": a.id, "Site": a.site.code, "Máquina": a.machine.machine_code, "Tipo": a.audit_type, "Data": a.audit_date, "Auditor": a.auditor, "Resultado": a.result, "Pontuação": a.score, "Observações": a.general_notes})
    return dataframe_to_excel(pd.DataFrame(rows), "Auditorias")


def export_machine_pdf(session: Session, machine_id: int) -> bytes:
    m = session.get(Machine, machine_id)
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    y = 800
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, y, f"Relatório NR-12 da Máquina {m.machine_code}")
    y -= 30
    c.setFont("Helvetica", 10)
    lines = [
        f"Site: {m.site.code} | Área: {m.area} | Linha: {m.line_process or '-'}",
        f"Nome: {m.name} | Fabricante: {m.manufacturer or '-'} | Modelo: {m.model or '-'}",
        f"Criticidade: {m.criticality} | Status NR-12: {m.nr12_status} | Status sugerido: {m.suggested_status or '-'}",
        f"Última auditoria: {m.last_audit_date or '-'} | Próxima auditoria: {m.next_audit_date or '-'}",
        f"Documentos: {len(m.documents)} | Auditorias: {len(m.audits)} | Ações: {len(m.actions)} | Mudanças: {len(m.changes)}",
    ]
    for line in lines:
        c.drawString(40, y, line[:120]); y -= 18
    y -= 10; c.setFont("Helvetica-Bold", 11); c.drawString(40, y, "Ações abertas"); y -= 18; c.setFont("Helvetica", 9)
    for a in [x for x in m.actions if x.status not in {"Concluída", "Cancelada"}][:12]:
        c.drawString(40, y, f"#{a.id} {a.classification} - {a.deviation_description[:85]} - Prazo: {a.due_date or '-'}")
        y -= 14
        if y < 80:
            c.showPage(); y = 800
    c.save()
    return buffer.getvalue()
