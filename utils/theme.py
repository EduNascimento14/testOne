from __future__ import annotations

import html
import streamlit as st


def apply_nr12_theme() -> None:
    st.markdown(
        """
        <style>
        :root {
            --brand-bg: #f6f8fb;
            --card-bg: #ffffff;
            --muted: #5f6b7a;
            --border: #e7ebf3;
            --title: #12263f;
            --accent: #1f4bb8;
            --sidebar-start: #ffcd61;
            --sidebar-end: #ffb91d;
        }
        .stApp {
            background: var(--brand-bg);
        }
        .block-container {
            padding-top: 1.4rem;
            padding-bottom: 2.2rem;
        }
        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, var(--sidebar-start) 0%, var(--sidebar-end) 100%) !important;
            border-right: 1px solid rgba(18, 38, 63, 0.12);
        }
        section[data-testid="stSidebar"] * {
            color: #1f1f1f !important;
        }
        section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
        section[data-testid="stSidebar"] label,
        section[data-testid="stSidebar"] span {
            font-weight: 500;
        }
        section[data-testid="stSidebar"] div[data-baseweb="select"] > div,
        section[data-testid="stSidebar"] div[role="radiogroup"],
        section[data-testid="stSidebar"] input {
            background: rgba(255, 255, 255, 0.42) !important;
            border-color: rgba(18, 38, 63, 0.20) !important;
            border-radius: 10px !important;
        }
        section[data-testid="stSidebar"] button {
            border-color: rgba(18, 38, 63, 0.22) !important;
            background: rgba(255, 255, 255, 0.58) !important;
            color: #1f1f1f !important;
        }
        .page-header {
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 1rem 1.2rem;
            margin-bottom: 1rem;
            box-shadow: 0 4px 16px rgba(18, 38, 63, 0.05);
        }
        .page-header h1 {
            margin: 0;
            font-size: 1.55rem;
            line-height: 1.25;
            color: var(--title);
        }
        .page-header p {
            margin: 0.35rem 0 0;
            color: var(--muted);
            font-size: 0.94rem;
        }
        .section-title {
            margin: 1.1rem 0 0.55rem;
            color: var(--title);
            font-size: 1.08rem;
            font-weight: 600;
        }
        div[data-testid="stMetric"] {
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 0.8rem 0.95rem;
            box-shadow: 0 2px 8px rgba(18, 38, 63, 0.04);
        }
        div[data-testid="stMetric"] label,
        div[data-testid="stMetric"] [data-testid="stMetricLabel"] {
            color: var(--muted) !important;
        }
        div[data-testid="stDataFrame"],
        div[data-testid="stExpander"],
        div[data-testid="stPlotlyChart"] {
            border-radius: 12px;
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 0.35rem;
        }
        .stTabs [data-baseweb="tab"] {
            background: rgba(255,255,255,0.72);
            border: 1px solid var(--border);
            border-radius: 999px;
            padding: 0.35rem 0.9rem;
        }
        .stTabs [aria-selected="true"] {
            background: #ffffff;
            color: var(--accent) !important;
            border-color: rgba(31, 75, 184, 0.22);
        }
        .stButton > button,
        .stDownloadButton > button,
        button[kind="primary"] {
            border-radius: 10px !important;
            border: 1px solid rgba(31, 75, 184, 0.24) !important;
            box-shadow: 0 2px 8px rgba(18, 38, 63, 0.04);
        }
        .status-ok {color:#065f46;font-weight:700}
        .status-warn {color:#92400e;font-weight:700}
        .status-bad {color:#7f1d1d;font-weight:700}
        .status-muted {color:#334155;font-weight:700}
        </style>
        """,
        unsafe_allow_html=True,
    )


def page_header(title: str, subtitle: str | None = None) -> None:
    subtitle_html = f"<p>{html.escape(subtitle)}</p>" if subtitle else ""
    st.markdown(
        f"<div class='page-header'><h1>{html.escape(title)}</h1>{subtitle_html}</div>",
        unsafe_allow_html=True,
    )


def section_title(title: str) -> None:
    st.markdown(f"<div class='section-title'>{html.escape(title)}</div>", unsafe_allow_html=True)
