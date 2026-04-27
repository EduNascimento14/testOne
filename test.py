import io
import re
import html
import base64
import tempfile
from datetime import datetime, date, timedelta

import numpy as np
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    Image,
    KeepTogether,
)
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics


APP_TITLE = "Permit & License Intelligence Report"
DEFAULT_WARNING_DAYS = 90
DEFAULT_CRITICAL_DAYS = 30


st.set_page_config(
    page_title="Permit & License Report",
    page_icon="📄",
    layout="wide",
)


CUSTOM_CSS = """
<style>
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 1300px;
    }
    .hero {
        padding: 26px 30px;
        border-radius: 20px;
        background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 55%, #0369a1 100%);
        color: white;
        margin-bottom: 22px;
        box-shadow: 0 10px 28px rgba(15, 23, 42, 0.18);
    }
    .hero h1 {
        font-size: 34px;
        margin-bottom: 6px;
        font-weight: 750;
    }
    .hero p {
        margin: 0;
        opacity: 0.90;
        font-size: 15px;
    }
    .metric-card {
        padding: 18px 20px;
        border: 1px solid #e5e7eb;
        border-radius: 18px;
        background: white;
        box-shadow: 0 6px 18px rgba(15, 23, 42, 0.06);
        min-height: 114px;
    }
    .metric-label {
        color: #64748b;
        font-size: 13px;
        font-weight: 600;
        margin-bottom: 8px;
    }
    .metric-value {
        font-size: 32px;
        color: #0f172a;
        font-weight: 750;
        line-height: 1.05;
    }
    .metric-note {
        color: #64748b;
        font-size: 12px;
        margin-top: 6px;
    }
    .section-title {
        margin-top: 20px;
        margin-bottom: 8px;
        font-size: 22px;
        font-weight: 750;
        color: #0f172a;
    }
    div[data-testid="stDataFrame"] {
        border: 1px solid #e5e7eb;
        border-radius: 14px;
        overflow: hidden;
    }
</style>
"""


def normalize_column_name(value: str) -> str:
    value = str(value).strip().lower()
    value = value.replace("&", "and")
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return re.sub(r"_+", "_", value).strip("_")


def find_header_row(raw_df: pd.DataFrame) -> int:
    required_terms = ["permit", "expiration", "division"]
    best_row = 0
    best_score = -1

    for idx in range(min(20, len(raw_df))):
        row_values = [str(x).strip().lower() for x in raw_df.iloc[idx].tolist() if pd.notna(x)]
        joined = " | ".join(row_values)
        score = sum(term in joined for term in required_terms)
        score += sum("permit" in v for v in row_values)
        score += sum("expiration" in v or "expiry" in v or "validity" in v for v in row_values)

        if score > best_score:
            best_score = score
            best_row = idx

    return best_row


def load_excel(uploaded_file) -> pd.DataFrame:
    raw = pd.read_excel(uploaded_file, sheet_name=0, header=None, engine="openpyxl")
    header_row = find_header_row(raw)

    headers = raw.iloc[header_row].fillna("").astype(str).str.strip().tolist()
    df = raw.iloc[header_row + 1 :].copy()
    df.columns = headers
    df = df.dropna(how="all")
    df = df.loc[:, [str(c).strip() != "" and not str(c).startswith("Unnamed") for c in df.columns]]
    df.columns = [str(c).strip() for c in df.columns]

    empty_like = {"", "nan", "none", "null"}
    df = df.replace(r"^\s*$", np.nan, regex=True)
    for col in df.columns:
        if df[col].astype(str).str.lower().isin(empty_like).all():
            df = df.drop(columns=[col])

    return df


def get_first_existing_column(df: pd.DataFrame, possible_names: list[str]) -> str | None:
    normalized_map = {normalize_column_name(c): c for c in df.columns}
    for name in possible_names:
        normalized = normalize_column_name(name)
        if normalized in normalized_map:
            return normalized_map[normalized]
    return None


def excel_serial_to_datetime(value):
    if pd.isna(value):
        return pd.NaT

    if isinstance(value, (datetime, date)):
        return pd.to_datetime(value, errors="coerce")

    value_str = str(value).strip()
    if value_str.lower() in {"not specified", "not_specified", "n/a", "na", "-", ""}:
        return pd.NaT

    if isinstance(value, (int, float, np.integer, np.floating)):
        if 1 <= float(value) <= 80000:
            return pd.to_datetime("1899-12-30") + pd.to_timedelta(float(value), unit="D")

    parsed = pd.to_datetime(value_str, errors="coerce", dayfirst=False)
    if pd.isna(parsed):
        parsed = pd.to_datetime(value_str, errors="coerce", dayfirst=True)

    return parsed


def clean_text(value):
    if pd.isna(value):
        return ""
    text = html.unescape(str(value))
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    if text.lower() in {"not specified", "nan", "none", "null"}:
        return ""
    return text


def prepare_data(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    columns = {
        "group": get_first_existing_column(df, ["Group"]),
        "division": get_first_existing_column(df, ["Division"]),
        "site": get_first_existing_column(df, ["Business Unit", "Site", "Unit", "Location"]),
        "media": get_first_existing_column(df, ["Media", "Category", "Area"]),
        "permit_id": get_first_existing_column(df, ["Permit ID", "ID"]),
        "permit_name": get_first_existing_column(df, ["Permit Name", "License Name", "Permit", "License"]),
        "description": get_first_existing_column(df, ["Description"]),
        "external_number": get_first_existing_column(df, ["External Permit Number", "External Number", "Number"]),
        "requirements": get_first_existing_column(df, ["# of Requirements", "Requirements"]),
        "issued": get_first_existing_column(df, ["Issued", "Issue Date", "Issued Date"]),
        "expiration": get_first_existing_column(df, ["Expiration Date", "Expiry Date", "Validity Date", "Expiration"]),
        "renewal_required": get_first_existing_column(df, ["Renewal Required By", "Renewal Required", "Renewal Due"]),
        "renewal_submitted": get_first_existing_column(df, ["Renewal Submitted Date", "Renewal Submitted"]),
        "open_tasks": get_first_existing_column(df, ["Open Calendar Tasks", "Open Tasks"]),
        "past_due_tasks": get_first_existing_column(df, ["Past Due Calendar Tasks", "Past Due Tasks"]),
        "upcoming_tasks": get_first_existing_column(df, ["Upcoming in next 30 days Calendar Tasks", "Upcoming Calendar Tasks"]),
        "closed_tasks": get_first_existing_column(df, ["Closed in the past 12 months Calendar Tasks", "Closed Tasks"]),
    }

    prepared = pd.DataFrame(index=df.index)

    for key in ["group", "division", "site", "media", "permit_name", "description", "external_number"]:
        col = columns.get(key)
        prepared[key] = df[col].map(clean_text) if col else ""

    for key in ["permit_id", "requirements", "open_tasks", "past_due_tasks", "upcoming_tasks", "closed_tasks"]:
        col = columns.get(key)
        prepared[key] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int) if col else 0

    for key in ["issued", "expiration", "renewal_required", "renewal_submitted"]:
        col = columns.get(key)
        prepared[key] = df[col].map(excel_serial_to_datetime) if col else pd.NaT

    prepared["site"] = prepared["site"].replace("", "Não informado")
    prepared["division"] = prepared["division"].replace("", "Não informado")
    prepared["media"] = prepared["media"].replace("", "Não informado")
    prepared["permit_name"] = prepared["permit_name"].replace("", "Sem nome informado")

    today = pd.Timestamp(date.today())
    prepared["days_to_expire"] = (prepared["expiration"] - today).dt.days
    prepared["days_to_renewal"] = (prepared["renewal_required"] - today).dt.days

    prepared["status"] = np.select(
        [
            prepared["expiration"].isna(),
            prepared["days_to_expire"] < 0,
            prepared["days_to_expire"] <= DEFAULT_CRITICAL_DAYS,
            prepared["days_to_expire"] <= DEFAULT_WARNING_DAYS,
        ],
        [
            "Sem data de vencimento",
            "Vencida",
            f"Vence em até {DEFAULT_CRITICAL_DAYS} dias",
            f"Vence em até {DEFAULT_WARNING_DAYS} dias",
        ],
        default="Regular",
    )

    prepared["renewal_status"] = np.select(
        [
            prepared["renewal_required"].isna(),
            prepared["days_to_renewal"] < 0,
            prepared["days_to_renewal"] <= DEFAULT_CRITICAL_DAYS,
        ],
        [
            "Sem prazo de renovação",
            "Renovação atrasada",
            f"Renovação em até {DEFAULT_CRITICAL_DAYS} dias",
        ],
        default="Regular",
    )

    prepared["risk_score"] = (
        (prepared["status"] == "Vencida").astype(int) * 5
        + (prepared["status"] == f"Vence em até {DEFAULT_CRITICAL_DAYS} dias").astype(int) * 4
        + (prepared["status"] == f"Vence em até {DEFAULT_WARNING_DAYS} dias").astype(int) * 2
        + (prepared["renewal_status"] == "Renovação atrasada").astype(int) * 3
        + (prepared["past_due_tasks"] > 0).astype(int) * 2
        + (prepared["open_tasks"] > 0).astype(int)
    )

    return prepared, columns


def format_date(value):
    if pd.isna(value):
        return "Não informado"
    return pd.to_datetime(value).strftime("%d/%m/%Y")


def pct(value, total):
    if total == 0:
        return "0%"
    return f"{value / total:.0%}"


def generate_chart_image(data: pd.Series, title: str, xlabel: str = "", ylabel: str = "Quantidade", kind: str = "bar") -> io.BytesIO:
    fig, ax = plt.subplots(figsize=(8.4, 3.6))

    data = data.dropna()
    if len(data) == 0:
        data = pd.Series({"Sem dados": 0})

    if kind == "barh":
        data.sort_values().plot(kind="barh", ax=ax)
    else:
        data.plot(kind="bar", ax=ax)

    ax.set_title(title, fontsize=12, fontweight="bold", pad=12)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", alpha=0.22)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    if kind != "barh":
        ax.tick_params(axis="x", rotation=35)
        for label in ax.get_xticklabels():
            label.set_horizontalalignment("right")

    plt.tight_layout()
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=170, bbox_inches="tight")
    plt.close(fig)
    buffer.seek(0)
    return buffer


def build_summary(prepared: pd.DataFrame) -> dict:
    total = len(prepared)
    expired = int((prepared["status"] == "Vencida").sum())
    critical = int((prepared["status"] == f"Vence em até {DEFAULT_CRITICAL_DAYS} dias").sum())
    warning = int((prepared["status"] == f"Vence em até {DEFAULT_WARNING_DAYS} dias").sum())
    no_expiration = int((prepared["status"] == "Sem data de vencimento").sum())
    renewal_overdue = int((prepared["renewal_status"] == "Renovação atrasada").sum())
    past_due_tasks = int(prepared["past_due_tasks"].sum())
    open_tasks = int(prepared["open_tasks"].sum())

    return {
        "total": total,
        "expired": expired,
        "critical": critical,
        "warning": warning,
        "no_expiration": no_expiration,
        "renewal_overdue": renewal_overdue,
        "past_due_tasks": past_due_tasks,
        "open_tasks": open_tasks,
        "sites": prepared["site"].nunique(),
        "divisions": prepared["division"].nunique(),
        "media": prepared["media"].nunique(),
    }


def table_data_from_df(df: pd.DataFrame, columns: list[str], max_rows: int = 25) -> list[list[str]]:
    data = [columns]
    if df.empty:
        return [columns, ["Sem registros"] + [""] * (len(columns) - 1)]

    for _, row in df.head(max_rows).iterrows():
        line = []
        for col in columns:
            value = row.get(col, "")
            if isinstance(value, (pd.Timestamp, datetime, date)):
                line.append(format_date(value))
            elif col in {"expiration", "renewal_required", "issued", "renewal_submitted"}:
                line.append(format_date(value))
            else:
                line.append(str(value))
        data.append(line)

    return data


def add_page_number(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#64748B"))
    canvas.drawString(1.2 * cm, 0.75 * cm, f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    canvas.drawRightString(landscape(A4)[0] - 1.2 * cm, 0.75 * cm, f"Página {doc.page}")
    canvas.restoreState()


def build_pdf(prepared: pd.DataFrame, original_filename: str) -> bytes:
    summary = build_summary(prepared)
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=1.2 * cm,
        leftMargin=1.2 * cm,
        topMargin=1.1 * cm,
        bottomMargin=1.1 * cm,
    )

    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="CoverTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=25,
            leading=29,
            textColor=colors.HexColor("#0F172A"),
            alignment=TA_LEFT,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SectionTitle",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=18,
            textColor=colors.HexColor("#0F172A"),
            spaceBefore=12,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SmallText",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#334155"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="Note",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#475569"),
            backColor=colors.HexColor("#F8FAFC"),
            borderColor=colors.HexColor("#E2E8F0"),
            borderWidth=0.6,
            borderPadding=7,
            spaceAfter=8,
        )
    )

    elements = []

    title_table = Table(
        [
            [
                Paragraph("Relatório Executivo de Licenças e Permits", styles["CoverTitle"]),
                Paragraph(
                    f"<b>Arquivo base:</b> {clean_text(original_filename)}<br/>"
                    f"<b>Data de referência:</b> {date.today().strftime('%d/%m/%Y')}<br/>"
                    f"<b>Janela crítica:</b> {DEFAULT_CRITICAL_DAYS} dias<br/>"
                    f"<b>Janela de atenção:</b> {DEFAULT_WARNING_DAYS} dias",
                    styles["SmallText"],
                ),
            ]
        ],
        colWidths=[18.5 * cm, 8.0 * cm],
    )
    title_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EFF6FF")),
                ("BOX", (0, 0), (-1, -1), 0.7, colors.HexColor("#BFDBFE")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 14),
                ("RIGHTPADDING", (0, 0), (-1, -1), 14),
                ("TOPPADDING", (0, 0), (-1, -1), 13),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 13),
            ]
        )
    )
    elements.append(title_table)
    elements.append(Spacer(1, 0.28 * cm))

    metric_rows = [
        [
            ("Total de licenças", summary["total"], "Base consolidada"),
            ("Vencidas", summary["expired"], pct(summary["expired"], summary["total"])),
            (f"≤ {DEFAULT_CRITICAL_DAYS} dias", summary["critical"], pct(summary["critical"], summary["total"])),
            (f"≤ {DEFAULT_WARNING_DAYS} dias", summary["warning"], pct(summary["warning"], summary["total"])),
        ],
        [
            ("Sem vencimento", summary["no_expiration"], pct(summary["no_expiration"], summary["total"])),
            ("Renovações atrasadas", summary["renewal_overdue"], "Prazo de renovação vencido"),
            ("Tarefas vencidas", summary["past_due_tasks"], "Calendar tasks"),
            ("Tarefas abertas", summary["open_tasks"], "Calendar tasks"),
        ],
    ]

    metric_table_data = []
    for row in metric_rows:
        metric_table_data.append(
            [
                Paragraph(
                    f"<font color='#64748B' size='8'><b>{label}</b></font><br/>"
                    f"<font color='#0F172A' size='20'><b>{value}</b></font><br/>"
                    f"<font color='#64748B' size='7'>{note}</font>",
                    styles["SmallText"],
                )
                for label, value, note in row
            ]
        )

    metric_table = Table(metric_table_data, colWidths=[6.6 * cm] * 4, rowHeights=[2.0 * cm, 2.0 * cm])
    metric_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#E2E8F0")),
                ("INNERGRID", (0, 0), (-1, -1), 0.6, colors.HexColor("#E2E8F0")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    elements.append(metric_table)

    insights = []
    if summary["expired"] > 0:
        insights.append(f"Existem {summary['expired']} licença(s) vencida(s), exigindo plano de ação imediato.")
    if summary["critical"] > 0:
        insights.append(f"{summary['critical']} licença(s) vencem em até {DEFAULT_CRITICAL_DAYS} dias; recomenda-se priorizar responsáveis e evidências de renovação.")
    if summary["renewal_overdue"] > 0:
        insights.append(f"{summary['renewal_overdue']} licença(s) possuem prazo de renovação atrasado.")
    if summary["past_due_tasks"] > 0:
        insights.append(f"Foram identificadas {summary['past_due_tasks']} tarefa(s) de calendário vencida(s).")
    if summary["no_expiration"] > 0:
        insights.append(f"{summary['no_expiration']} registro(s) não possuem data de vencimento informada; recomenda-se revisar se a licença é permanente ou se a validade está ausente.")
    if not insights:
        insights.append("Não foram identificados vencimentos críticos na janela configurada.")

    elements.append(Paragraph("Principais insights executivos", styles["SectionTitle"]))
    elements.append(Paragraph("<br/>".join([f"• {x}" for x in insights]), styles["Note"]))

    chart_status = generate_chart_image(prepared["status"].value_counts(), "Distribuição por status")
    chart_site = generate_chart_image(prepared["site"].value_counts().head(10), "Top sites por quantidade de licenças")
    chart_media = generate_chart_image(prepared["media"].value_counts().head(10), "Licenças por categoria/media")

    chart_table = Table(
        [[Image(chart_status, width=8.7 * cm, height=3.7 * cm), Image(chart_site, width=8.7 * cm, height=3.7 * cm), Image(chart_media, width=8.7 * cm, height=3.7 * cm)]],
        colWidths=[8.9 * cm] * 3,
    )
    chart_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    elements.append(chart_table)

    elements.append(PageBreak())

    priority = prepared.sort_values(["risk_score", "days_to_expire"], ascending=[False, True]).copy()
    priority["Vencimento"] = priority["expiration"].map(format_date)
    priority["Renovação até"] = priority["renewal_required"].map(format_date)
    priority["Dias"] = priority["days_to_expire"].fillna("").astype(str).str.replace(".0", "", regex=False)

    priority_cols = ["site", "division", "media", "permit_name", "Vencimento", "Dias", "status", "renewal_status"]
    priority_labels = ["Site", "Divisão", "Categoria", "Licença", "Vencimento", "Dias", "Status", "Renovação"]
    priority_df = priority[priority_cols].rename(columns=dict(zip(priority_cols, priority_labels)))

    elements.append(Paragraph("Lista priorizada para ação", styles["SectionTitle"]))
    elements.append(
        Paragraph(
            "A tabela abaixo prioriza licenças vencidas, próximas do vencimento, com renovação atrasada ou tarefas pendentes. "
            "Use esta seção como base para acionar os responsáveis por site/divisão.",
            styles["SmallText"],
        )
    )
    elements.append(Spacer(1, 0.15 * cm))

    priority_data = table_data_from_df(priority_df, priority_labels, max_rows=30)
    priority_table = Table(priority_data, repeatRows=1, colWidths=[2.6 * cm, 3.1 * cm, 2.5 * cm, 6.5 * cm, 2.2 * cm, 1.2 * cm, 3.2 * cm, 3.4 * cm])
    priority_table.setStyle(get_pdf_table_style())
    elements.append(priority_table)

    elements.append(PageBreak())

    site_summary = (
        prepared.groupby("site")
        .agg(
            Total=("permit_name", "count"),
            Vencidas=("status", lambda x: int((x == "Vencida").sum())),
            Criticas=("status", lambda x: int((x == f"Vence em até {DEFAULT_CRITICAL_DAYS} dias").sum())),
            Atencao=("status", lambda x: int((x == f"Vence em até {DEFAULT_WARNING_DAYS} dias").sum())),
            SemVencimento=("status", lambda x: int((x == "Sem data de vencimento").sum())),
            TarefasVencidas=("past_due_tasks", "sum"),
        )
        .reset_index()
        .sort_values(["Vencidas", "Criticas", "Atencao", "Total"], ascending=[False, False, False, False])
    )
    site_summary = site_summary.rename(
        columns={
            "site": "Site",
            "Criticas": f"≤ {DEFAULT_CRITICAL_DAYS} dias",
            "Atencao": f"≤ {DEFAULT_WARNING_DAYS} dias",
            "SemVencimento": "Sem vencimento",
            "TarefasVencidas": "Tarefas vencidas",
        }
    )

    division_summary = (
        prepared.groupby("division")
        .agg(
            Total=("permit_name", "count"),
            Vencidas=("status", lambda x: int((x == "Vencida").sum())),
            Criticas=("status", lambda x: int((x == f"Vence em até {DEFAULT_CRITICAL_DAYS} dias").sum())),
            Atencao=("status", lambda x: int((x == f"Vence em até {DEFAULT_WARNING_DAYS} dias").sum())),
            TarefasVencidas=("past_due_tasks", "sum"),
        )
        .reset_index()
        .sort_values(["Vencidas", "Criticas", "Atencao", "Total"], ascending=[False, False, False, False])
    )
    division_summary = division_summary.rename(
        columns={
            "division": "Divisão",
            "Criticas": f"≤ {DEFAULT_CRITICAL_DAYS} dias",
            "Atencao": f"≤ {DEFAULT_WARNING_DAYS} dias",
            "TarefasVencidas": "Tarefas vencidas",
        }
    )

    elements.append(Paragraph("Indicadores por site", styles["SectionTitle"]))
    site_columns = list(site_summary.columns)
    site_data = table_data_from_df(site_summary, site_columns, max_rows=35)
    site_table = Table(site_data, repeatRows=1, colWidths=[6.0 * cm, 2.0 * cm, 2.0 * cm, 2.2 * cm, 2.2 * cm, 2.8 * cm, 2.8 * cm])
    site_table.setStyle(get_pdf_table_style())
    elements.append(site_table)

    elements.append(Spacer(1, 0.35 * cm))
    elements.append(Paragraph("Indicadores por divisão", styles["SectionTitle"]))
    division_columns = list(division_summary.columns)
    division_data = table_data_from_df(division_summary, division_columns, max_rows=25)
    division_table = Table(division_data, repeatRows=1, colWidths=[7.0 * cm, 2.0 * cm, 2.0 * cm, 2.2 * cm, 2.2 * cm, 2.8 * cm])
    division_table.setStyle(get_pdf_table_style())
    elements.append(division_table)

    elements.append(PageBreak())

    missing_exp = prepared[prepared["expiration"].isna()].copy()
    missing_exp["Vencimento"] = missing_exp["expiration"].map(format_date)
    missing_exp_df = missing_exp[["site", "division", "media", "permit_name", "external_number"]].rename(
        columns={
            "site": "Site",
            "division": "Divisão",
            "media": "Categoria",
            "permit_name": "Licença",
            "external_number": "Número externo",
        }
    )

    elements.append(Paragraph("Registros sem data de vencimento", styles["SectionTitle"]))
    elements.append(
        Paragraph(
            "Esta seção ajuda a diferenciar licenças realmente permanentes de registros com informação incompleta. "
            "Recomenda-se validar a regra de validade com o responsável legal/EHS do site.",
            styles["SmallText"],
        )
    )
    elements.append(Spacer(1, 0.15 * cm))
    missing_columns = list(missing_exp_df.columns)
    missing_data = table_data_from_df(missing_exp_df, missing_columns, max_rows=30)
    missing_table = Table(missing_data, repeatRows=1, colWidths=[4.5 * cm, 5.2 * cm, 3.2 * cm, 8.0 * cm, 4.0 * cm])
    missing_table.setStyle(get_pdf_table_style())
    elements.append(missing_table)

    elements.append(Spacer(1, 0.35 * cm))
    elements.append(Paragraph("Recomendação de uso", styles["SectionTitle"]))
    elements.append(
        Paragraph(
            "Envie este PDF aos responsáveis por site e divisão com foco nas licenças vencidas, próximas de vencimento, "
            "com renovação atrasada ou sem validade informada. Para governança, recomenda-se registrar responsável, evidência de renovação, "
            "prazo-alvo e status de cada ação em uma base controlada.",
            styles["Note"],
        )
    )

    doc.build(elements, onFirstPage=add_page_number, onLaterPages=add_page_number)
    buffer.seek(0)
    return buffer.read()


def get_pdf_table_style():
    return TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 8),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 1), (-1, -1), 7.3),
            ("TEXTCOLOR", (0, 1), (-1, -1), colors.HexColor("#1E293B")),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]
    )


def status_order(df: pd.DataFrame) -> pd.DataFrame:
    order = {
        "Vencida": 0,
        f"Vence em até {DEFAULT_CRITICAL_DAYS} dias": 1,
        f"Vence em até {DEFAULT_WARNING_DAYS} dias": 2,
        "Sem data de vencimento": 3,
        "Regular": 4,
    }
    return df.assign(_ord=df["status"].map(order).fillna(9)).sort_values(["_ord", "days_to_expire"]).drop(columns=["_ord"])


def make_download_link(pdf_bytes: bytes, file_name: str) -> str:
    b64 = base64.b64encode(pdf_bytes).decode()
    return f'<a href="data:application/pdf;base64,{b64}" download="{file_name}">Baixar PDF</a>'


st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

st.markdown(
    """
    <div class="hero">
        <h1>Permit & License Intelligence Report</h1>
        <p>Faça upload do relatório de licenças/permits em Excel e gere um PDF executivo com vencimentos, riscos, indicadores por site, divisão e categoria.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Configuração")
    uploaded_file = st.file_uploader("Upload do arquivo Excel", type=["xlsx", "xls"])
    st.caption("O app identifica automaticamente a linha de cabeçalho e trabalha com colunas como Business Unit, Division, Media, Permit Name, Expiration Date e Renewal Required By.")
    st.divider()
    st.info(
        "Critérios padrão: vencida, vencimento em até 30 dias, vencimento em até 90 dias, renovação atrasada e tarefas de calendário vencidas."
    )

if uploaded_file is None:
    st.warning("Faça upload do arquivo base para visualizar os indicadores e gerar o PDF.")
    st.stop()

try:
    raw_df = load_excel(uploaded_file)
    prepared, detected_columns = prepare_data(raw_df)
except Exception as exc:
    st.error("Não foi possível processar o arquivo. Verifique se o Excel possui uma aba com a base de licenças e cabeçalhos.")
    st.exception(exc)
    st.stop()

summary = build_summary(prepared)

st.subheader("Indicadores principais")
cols = st.columns(4)
metric_cards = [
    ("Total de licenças", summary["total"], "Registros processados"),
    ("Vencidas", summary["expired"], pct(summary["expired"], summary["total"])),
    (f"Vencem em até {DEFAULT_CRITICAL_DAYS} dias", summary["critical"], pct(summary["critical"], summary["total"])),
    (f"Vencem em até {DEFAULT_WARNING_DAYS} dias", summary["warning"], pct(summary["warning"], summary["total"])),
]

for col, (label, value, note) in zip(cols, metric_cards):
    with col:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">{label}</div>
                <div class="metric-value">{value}</div>
                <div class="metric-note">{note}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

cols = st.columns(4)
metric_cards_2 = [
    ("Sem vencimento", summary["no_expiration"], pct(summary["no_expiration"], summary["total"])),
    ("Renovações atrasadas", summary["renewal_overdue"], "Prazo de renovação vencido"),
    ("Tarefas vencidas", summary["past_due_tasks"], "Calendar tasks"),
    ("Tarefas abertas", summary["open_tasks"], "Calendar tasks"),
]
for col, (label, value, note) in zip(cols, metric_cards_2):
    with col:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">{label}</div>
                <div class="metric-value">{value}</div>
                <div class="metric-note">{note}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.markdown('<div class="section-title">Distribuições</div>', unsafe_allow_html=True)
chart_col1, chart_col2, chart_col3 = st.columns(3)

with chart_col1:
    st.bar_chart(prepared["status"].value_counts())
with chart_col2:
    st.bar_chart(prepared["site"].value_counts().head(12))
with chart_col3:
    st.bar_chart(prepared["media"].value_counts().head(12))

st.markdown('<div class="section-title">Base priorizada para ação</div>', unsafe_allow_html=True)
display_df = status_order(prepared).copy()
display_df["issued"] = display_df["issued"].map(format_date)
display_df["expiration"] = display_df["expiration"].map(format_date)
display_df["renewal_required"] = display_df["renewal_required"].map(format_date)
display_df["renewal_submitted"] = display_df["renewal_submitted"].map(format_date)

visible_columns = [
    "site",
    "division",
    "media",
    "permit_id",
    "permit_name",
    "external_number",
    "issued",
    "expiration",
    "days_to_expire",
    "renewal_required",
    "status",
    "renewal_status",
    "open_tasks",
    "past_due_tasks",
]
st.dataframe(
    display_df[visible_columns],
    use_container_width=True,
    hide_index=True,
    column_config={
        "site": "Site",
        "division": "Divisão",
        "media": "Categoria",
        "permit_id": "Permit ID",
        "permit_name": "Licença",
        "external_number": "Número externo",
        "issued": "Emissão",
        "expiration": "Vencimento",
        "days_to_expire": "Dias até vencer",
        "renewal_required": "Renovar até",
        "status": "Status",
        "renewal_status": "Status renovação",
        "open_tasks": "Tarefas abertas",
        "past_due_tasks": "Tarefas vencidas",
    },
)

st.markdown('<div class="section-title">Indicadores por site e divisão</div>', unsafe_allow_html=True)
tab1, tab2, tab3 = st.tabs(["Por site", "Por divisão", "Por categoria/media"])

with tab1:
    site_summary = (
        prepared.groupby("site")
        .agg(
            Total=("permit_name", "count"),
            Vencidas=("status", lambda x: int((x == "Vencida").sum())),
            Criticas=("status", lambda x: int((x == f"Vence em até {DEFAULT_CRITICAL_DAYS} dias").sum())),
            Atencao=("status", lambda x: int((x == f"Vence em até {DEFAULT_WARNING_DAYS} dias").sum())),
            SemVencimento=("status", lambda x: int((x == "Sem data de vencimento").sum())),
            TarefasVencidas=("past_due_tasks", "sum"),
        )
        .reset_index()
        .sort_values(["Vencidas", "Criticas", "Atencao", "Total"], ascending=[False, False, False, False])
    )
    st.dataframe(site_summary, use_container_width=True, hide_index=True)

with tab2:
    division_summary = (
        prepared.groupby("division")
        .agg(
            Total=("permit_name", "count"),
            Vencidas=("status", lambda x: int((x == "Vencida").sum())),
            Criticas=("status", lambda x: int((x == f"Vence em até {DEFAULT_CRITICAL_DAYS} dias").sum())),
            Atencao=("status", lambda x: int((x == f"Vence em até {DEFAULT_WARNING_DAYS} dias").sum())),
            TarefasVencidas=("past_due_tasks", "sum"),
        )
        .reset_index()
        .sort_values(["Vencidas", "Criticas", "Atencao", "Total"], ascending=[False, False, False, False])
    )
    st.dataframe(division_summary, use_container_width=True, hide_index=True)

with tab3:
    media_summary = (
        prepared.groupby("media")
        .agg(
            Total=("permit_name", "count"),
            Vencidas=("status", lambda x: int((x == "Vencida").sum())),
            Criticas=("status", lambda x: int((x == f"Vence em até {DEFAULT_CRITICAL_DAYS} dias").sum())),
            Atencao=("status", lambda x: int((x == f"Vence em até {DEFAULT_WARNING_DAYS} dias").sum())),
            TarefasVencidas=("past_due_tasks", "sum"),
        )
        .reset_index()
        .sort_values(["Vencidas", "Criticas", "Atencao", "Total"], ascending=[False, False, False, False])
    )
    st.dataframe(media_summary, use_container_width=True, hide_index=True)

st.markdown('<div class="section-title">Geração do PDF</div>', unsafe_allow_html=True)

if st.button("Gerar PDF executivo", type="primary"):
    with st.spinner("Gerando PDF..."):
        pdf_bytes = build_pdf(prepared, uploaded_file.name)
        file_name = f"permit_license_report_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"

    st.success("PDF gerado com sucesso.")
    st.download_button(
        label="Baixar PDF executivo",
        data=pdf_bytes,
        file_name=file_name,
        mime="application/pdf",
    )

    st.caption("Sugestão: envie o PDF aos responsáveis por site/divisão com foco nas ações priorizadas.")


with st.expander("Colunas detectadas no arquivo"):
    detected_df = pd.DataFrame(
        [{"Campo esperado": key, "Coluna encontrada": value or "Não encontrada"} for key, value in detected_columns.items()]
    )
    st.dataframe(detected_df, use_container_width=True, hide_index=True)


with st.expander("Como executar localmente"):
    st.code(
        """
pip install streamlit pandas openpyxl reportlab matplotlib numpy
streamlit run app_licencas.py
        """.strip(),
        language="bash",
    )

