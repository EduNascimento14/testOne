import streamlit as st


def apply_theme(hide_sidebar=False):
    sidebar_css = """
    section[data-testid="stSidebar"] {display:none;}
    div[data-testid="collapsedControl"] {display:none;}
    """ if hide_sidebar else """
    section[data-testid="stSidebar"] > div {
        background: linear-gradient(180deg, #f7c948 0%, #d99a00 52%, #7a5600 100%);
        color: #1f2937;
    }
    section[data-testid="stSidebar"] * { color: #1f2937; }
    """
    st.markdown(
        f"""
        <style>
        .stApp {{ background: #f6f8fb; color: #172033; }}
        .block-container {{ padding-top: 1.5rem; padding-bottom: 2.5rem; max-width: 1380px; }}
        {sidebar_css}
        h1, h2, h3 {{ color: #162033; letter-spacing: 0; }}
        .ehs-header, .ehs-card, .ehs-kpi, .ehs-alert {{
            background: #ffffff;
            border: 1px solid #e3e8f2;
            border-radius: 8px;
            box-shadow: 0 8px 24px rgba(22, 32, 51, 0.06);
        }}
        .ehs-header {{ padding: 22px 24px; margin-bottom: 18px; }}
        .ehs-header h1 {{ font-size: 1.75rem; margin: 0 0 6px 0; }}
        .ehs-header p {{ margin: 0; color: #5d6b82; font-size: .98rem; }}
        .ehs-card {{ padding: 22px; min-height: 190px; margin-bottom: 14px; }}
        .ehs-card h3 {{ margin-top: 0; font-size: 1.15rem; }}
        .ehs-card p {{ color: #59687e; line-height: 1.45; }}
        .ehs-kpi {{ padding: 16px 18px; min-height: 112px; }}
        .ehs-kpi .label {{ color: #64748b; font-size: .82rem; font-weight: 700; text-transform: uppercase; }}
        .ehs-kpi .value {{ color: #111827; font-size: 1.8rem; font-weight: 800; margin-top: 8px; }}
        .ehs-kpi .help {{ color: #7c8798; font-size: .8rem; margin-top: 2px; }}
        .ehs-alert {{ padding: 14px 16px; border-left: 5px solid #d99a00; margin: 8px 0; }}
        .ehs-alert.critical {{ border-left-color: #b42318; }}
        .ehs-alert.ok {{ border-left-color: #16803c; }}
        div.stButton > button, div.stDownloadButton > button {{
            border-radius: 999px;
            border: 1px solid #d8a214;
            background: #f3b51b;
            color: #1e293b;
            font-weight: 700;
        }}
        div.stButton > button:hover, div.stDownloadButton > button:hover {{
            border-color: #b58000;
            background: #ffd45a;
            color: #111827;
        }}
        [data-testid="stMetric"] {{
            background: #ffffff;
            border: 1px solid #e3e8f2;
            border-radius: 8px;
            padding: 14px;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def header(title, subtitle=""):
    st.markdown(f"<div class='ehs-header'><h1>{title}</h1><p>{subtitle}</p></div>", unsafe_allow_html=True)


def module_card(title, description):
    st.markdown(f"<div class='ehs-card'><h3>{title}</h3><p>{description}</p>", unsafe_allow_html=True)


def close_card():
    st.markdown("</div>", unsafe_allow_html=True)


def kpi_card(label, value, help_text=""):
    st.markdown(
        f"<div class='ehs-kpi'><div class='label'>{label}</div><div class='value'>{value}</div><div class='help'>{help_text}</div></div>",
        unsafe_allow_html=True,
    )


def alert_card(title, text, level="warning"):
    cls = "critical" if level == "critical" else "ok" if level == "ok" else ""
    st.markdown(f"<div class='ehs-alert {cls}'><strong>{title}</strong><br>{text}</div>", unsafe_allow_html=True)


def empty_state(text):
    st.info(text)


def sidebar_header(user, modulo):
    st.sidebar.title("Plataforma EHS Integrada")
    st.sidebar.caption(modulo)
    st.sidebar.markdown("---")
    st.sidebar.markdown(f"**{user.nome}**")
    st.sidebar.caption(user.perfil if not user.site else f"{user.perfil} · {user.site.codigo}")
    st.sidebar.markdown("---")
