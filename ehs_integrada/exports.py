from io import BytesIO
from xml.sax.saxutils import escape

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ehs_integrada.models import NR12Maquina, Site
from ehs_integrada.services import ehs_pacs_df, ehs_respostas_df, nr12_documentos_df, nr12_maquinas_df, nr12_mocs_df, nr12_pacs_df, nr12_verificacoes_df


def dataframe_to_excel(df, sheet_name="Dados"):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        data = df if not df.empty else pd.DataFrame()
        data.to_excel(writer, index=False, sheet_name=sheet_name[:31])
        worksheet = writer.sheets[sheet_name[:31]]
        for column_cells in worksheet.columns:
            length = max(len(str(cell.value or "")) for cell in column_cells)
            worksheet.column_dimensions[column_cells[0].column_letter].width = min(max(length + 2, 12), 60)
    return output.getvalue()


def sheets_to_excel(sheets):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for name, df in sheets.items():
            (df if not df.empty else pd.DataFrame()).to_excel(writer, index=False, sheet_name=name[:31])
    return output.getvalue()


def _pdf_text(value):
    return escape("" if value is None else str(value))


def build_pdf(title, blocks, tables=None):
    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4, rightMargin=34, leftMargin=34, topMargin=34, bottomMargin=34)
    styles = getSampleStyleSheet()
    story = [Paragraph(_pdf_text(title), styles["Title"]), Spacer(1, 12)]
    for heading, text in blocks:
        story.append(Paragraph(_pdf_text(heading), styles["Heading2"]))
        story.append(Paragraph(_pdf_text(text), styles["BodyText"]))
        story.append(Spacer(1, 8))
    for table_title, df in tables or []:
        story.append(Paragraph(_pdf_text(table_title), styles["Heading2"]))
        data = [list(df.columns)] + df.fillna("").astype(str).head(35).values.tolist() if not df.empty else [["Sem registros"]]
        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4b3500")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d8dde8")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
        ]))
        story.append(table)
        story.append(Spacer(1, 10))
    doc.build(story)
    return output.getvalue()


def export_nr12_inventory_excel(session, site_ids=None):
    return dataframe_to_excel(nr12_maquinas_df(session, site_ids), "Inventario NR12")


def export_nr12_documents_excel(session, site_ids=None):
    return dataframe_to_excel(nr12_documentos_df(session, site_ids), "Documentos NR12")


def export_nr12_audits_excel(session, site_ids=None):
    return dataframe_to_excel(nr12_verificacoes_df(session, site_ids), "Auditorias NR12")


def export_nr12_pac_excel(session, site_ids=None):
    return dataframe_to_excel(nr12_pacs_df(session, site_ids), "PAC NR12")


def export_nr12_moc_excel(session, site_ids=None):
    return dataframe_to_excel(nr12_mocs_df(session, site_ids), "MOC NR12")


def export_ehs_checklist_excel(session, auditoria_id=None, site_ids=None):
    return dataframe_to_excel(ehs_respostas_df(session, auditoria_id, site_ids), "Checklist EHS")


def export_ehs_pac_excel(session, site_ids=None):
    return dataframe_to_excel(ehs_pacs_df(session, site_ids), "PAC Auditoria")


def export_machine_pdf(session, machine_id):
    machine = session.get(NR12Maquina, machine_id)
    site = session.get(Site, machine.site_id) if machine else None
    pacs = nr12_pacs_df(session, [machine.site_id]) if machine else pd.DataFrame()
    pacs = pacs[pacs["Máquina"] == machine.codigo] if not pacs.empty and machine else pacs
    docs = nr12_documentos_df(session, [machine.site_id]) if machine else pd.DataFrame()
    docs = docs[docs["Máquina"] == machine.codigo] if not docs.empty and machine else docs
    return build_pdf(
        f"Relatório NR-12 da Máquina {machine.codigo if machine else ''}",
        [
            ("Identificação", f"Site: {site.codigo if site else '-'} | Área: {machine.area if machine else '-'} | Máquina: {machine.nome if machine else '-'}"),
            ("Status", f"Criticidade: {machine.criticidade if machine else '-'} | Status NR-12: {machine.status_nr12 if machine else '-'}"),
        ],
        [("Documentos", docs[["Tipo", "Nome", "Validade", "Status"]] if not docs.empty else docs), ("PAC", pacs[["Descrição", "Classificação", "Prazo", "Status"]] if not pacs.empty else pacs)],
    )


def export_ehs_audit_pdf(session, auditoria_id, site_ids=None):
    checklist = ehs_respostas_df(session, auditoria_id, site_ids)
    pacs = ehs_pacs_df(session, site_ids)
    if not pacs.empty:
        pacs = pacs[pacs["Auditoria"].isin(checklist["Auditoria"].unique())]
    return build_pdf(
        f"Relatório de Auditoria Cruzada #{auditoria_id}",
        [
            ("Resultado", "Relatório executivo da auditoria com resultado por diretiva e PAC associado."),
        ],
        [
            ("Checklist", checklist[["Site", "Diretiva", "Código", "Status", "Maturidade"]] if not checklist.empty else checklist),
            ("PAC", pacs[["Site", "Requisito", "Criticidade", "Prazo", "Status"]] if not pacs.empty else pacs),
        ],
    )


def export_termo_pdf(site, ciclo, indicadores, responsaveis, declaracao, ressalvas, plano):
    blocks = [
        ("Site e ciclo", f"Site: {site.codigo} - {site.nome} | Ciclo: {ciclo}"),
        ("Síntese", " | ".join(f"{k}: {v}" for k, v in indicadores.items())),
        ("Responsáveis", " | ".join(f"{k}: {v or '-'}" for k, v in responsaveis.items())),
        ("Declaração", declaracao),
        ("Ressalvas e pendências", ressalvas or "Sem ressalvas registradas."),
        ("Plano de ação associado", plano or "Acompanhamento conforme PAC do sistema."),
    ]
    return build_pdf("Termo de Garantia de Sustentação NR-12 do Site", blocks)
