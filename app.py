
# -*- coding: utf-8 -*-
"""
Plataforma Integrada EHS — NR-12 e Auditorias Cruzadas
Arquivo monolítico Streamlit. Renomeie para plataforma_ehs_integrada.py e rode:
streamlit run plataforma_ehs_integrada.py
"""

# ============================================================
# 1. Imports
# ============================================================
import os, io, logging, re, calendar
from datetime import date, datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import create_engine, Column, Integer, String, Text, Date, DateTime, Boolean, Float, ForeignKey, UniqueConstraint, LargeBinary, inspect
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

# ============================================================
# 2. Configurações
# ============================================================
st.set_page_config(page_title="Plataforma Integrada EHS", page_icon="🛡️", layout="wide")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///plataforma_ehs_integrada.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("plataforma_ehs")

# ============================================================
# 3. Constantes
# ============================================================
SITES_PADRAO = ["SJC", "DIA", "CAC", "JAC", "JUN", "PER"]


# Nomenclatura visual padronizada do módulo de máquinas.
NOME_MODULO_MAQUINAS = "Sustentação de Proteções de Máquinas"
NOME_DASH_MAQUINAS = "Dashboard de Proteções de Máquinas"
NOME_DOCS_MAQUINAS = "Documentos de Proteções de Máquinas"
NOME_CHECKLISTS_MAQUINAS = "Checklists e Inspeções de Proteções de Máquinas"
NOME_BASE_CHECKLISTS_MAQUINAS = "Base de Checklists de Proteções"
NOME_PAC_MAQUINAS = "PAC de Proteções de Máquinas"
NOME_MOC_MAQUINAS = "MOC de Proteções de Máquinas"
NOME_RELATORIOS_MAQUINAS = "Relatórios de Proteções de Máquinas"
NOME_STATUS_PROTECAO = "Status de Proteção"
NOME_TERMO_MAQUINAS = "Termo de Garantia de Proteções de Máquinas"

# Site master: fonte única para nomes, grupos e divisões produtivas.
SITES_INFO = {
    "CAC": {"nome_curto": "Cachoeirinha", "nome_padrao": "MSG Br CAC - Cachoeirinha", "grupo": "MSG", "divisao": "MSG Br"},
    "JAC": {"nome_curto": "Jacareí", "nome_padrao": "MSG Br JAC - Jacareí", "grupo": "MSG", "divisao": "MSG Br"},
    "JUN": {"nome_curto": "Jundiaí", "nome_padrao": "EMG Br JU - Jundiaí", "grupo": "EMG", "divisao": "EMG Br"},
    "PER": {"nome_curto": "Perus", "nome_padrao": "EMG Br SP - Perus", "grupo": "EMG", "divisao": "EMG Br"},
    "SJC": {"nome_curto": "São José dos Campos", "nome_padrao": "Filtration Br - São José dos Campos", "grupo": "Filtration", "divisao": "Filtration Br"},
    "DIA": {"nome_curto": "Diadema", "nome_padrao": "FCG Br - Diadema", "grupo": "FCG", "divisao": "FCG Br"},
    "Corporativo": {"nome_curto": "Corporativo", "nome_padrao": "Corporativo", "grupo": "Corporativo", "divisao": "Corporativo"},
}
SITE_ALIASES = {
    "CACHOEIRINHA": "CAC", "MSG CAC": "CAC", "MSG BR CAC": "CAC", "CAC": "CAC",
    "JACAREI": "JAC", "JACAREÍ": "JAC", "MSG JAC": "JAC", "MSG BR JAC": "JAC", "JAC": "JAC",
    "JUNDIAI": "JUN", "JUNDIAÍ": "JUN", "EMG JU": "JUN", "EMG BR JU": "JUN", "JUN": "JUN",
    "PERUS": "PER", "SAO PAULO": "PER", "SÃO PAULO": "PER", "EMG SP": "PER", "EMG BR SP": "PER", "PER": "PER",
    "SAO JOSE DOS CAMPOS": "SJC", "SÃO JOSÉ DOS CAMPOS": "SJC", "SJC": "SJC", "PFG": "SJC", "FILTRATION": "SJC",
    "DIADEMA": "DIA", "DIA": "DIA", "FCG": "DIA", "FCG BR": "DIA",
    "CORPORATIVO": "Corporativo", "CORPORATE": "Corporativo",
}

PERMISSION_MATRIX = {
    "Admin_LAG": {"*": {"visualizar", "criar", "editar", "excluir", "aprovar", "exportar", "administrar"}},
    "EHS_Local": {
        "home": {"visualizar"}, "maquinas": {"visualizar", "criar", "editar", "exportar"},
        "documentos_maquinas": {"visualizar", "criar", "editar", "exportar"},
        "checklists_maquinas": {"visualizar", "criar", "editar", "exportar"},
        "pac_maquinas": {"visualizar", "criar", "editar", "aprovar", "exportar"},
        "moc_maquinas": {"visualizar", "criar", "editar", "aprovar", "exportar"},
        "auditoria_ehs": {"visualizar", "criar", "editar", "aprovar", "exportar"},
        "pac_ehs": {"visualizar", "criar", "editar", "aprovar", "exportar"},
        "relatorios": {"visualizar", "exportar"}, "admin": {"visualizar"}
    },
    "Auditor": {"auditoria_ehs": {"visualizar", "criar", "editar", "exportar"}, "pac_ehs": {"visualizar", "criar", "editar", "exportar"}, "relatorios": {"visualizar", "exportar"}, "home": {"visualizar"}, "maquinas": {"visualizar"}},
    "Manutencao": {"home": {"visualizar"}, "maquinas": {"visualizar", "criar", "editar", "exportar"}, "documentos_maquinas": {"visualizar", "criar", "editar", "exportar"}, "checklists_maquinas": {"visualizar", "criar", "editar"}, "pac_maquinas": {"visualizar", "criar", "editar"}, "moc_maquinas": {"visualizar", "criar", "editar"}},
    "Producao_Operacao": {"home": {"visualizar"}, "maquinas": {"visualizar"}, "checklists_maquinas": {"visualizar", "criar"}, "pac_maquinas": {"visualizar", "editar"}, "moc_maquinas": {"visualizar", "criar"}},
    "Engenharia": {"home": {"visualizar"}, "maquinas": {"visualizar", "criar", "editar", "exportar"}, "documentos_maquinas": {"visualizar", "criar", "editar"}, "checklists_maquinas": {"visualizar", "criar", "editar"}, "pac_maquinas": {"visualizar", "criar", "editar"}, "moc_maquinas": {"visualizar", "criar", "editar", "aprovar"}},
    "Responsavel_Acao": {"home": {"visualizar"}, "pac_maquinas": {"visualizar", "editar"}, "pac_ehs": {"visualizar", "editar"}, "relatorios": {"visualizar"}},
    "Visualizador": {"home": {"visualizar"}, "maquinas": {"visualizar"}, "documentos_maquinas": {"visualizar"}, "checklists_maquinas": {"visualizar"}, "pac_maquinas": {"visualizar"}, "moc_maquinas": {"visualizar"}, "auditoria_ehs": {"visualizar"}, "pac_ehs": {"visualizar"}, "relatorios": {"visualizar"}},
}

PESOS_PRIORIDADE_MAQUINAS = {
    "risco": {"Apreciação de risco não realizada": 60, "Extremo": 55, "Alto": 45, "Significativo": 30, "Atenção": 15, "Desprezível": 5},
    "status_nao_conforme": 35,
    "auditoria_vencida": 55,
    "auditoria_30d": 35,
    "auditoria_60d": 20,
    "pac_critico": 45,
    "doc_ausente": 30,
    "doc_vencido": 35,
    "sem_data_adequacao": 25,
    "moc_sem_validacao": 40,
    "reincidencia_pac": 8,
}
PERFIS = ["Admin_LAG","EHS_Local","Auditor","Manutencao","Producao_Operacao","Engenharia","Responsavel_Acao","Visualizador"]
USUARIOS_PADRAO = [
    ("Eduardo","Admin_LAG","Corporativo"), ("Capitu","Admin_LAG","Corporativo"),
    ("EHS SJC","EHS_Local","SJC"), ("Manutenção SJC","Manutencao","SJC"),
    ("Produção SJC","Producao_Operacao","SJC"), ("Auditor EHS","Auditor","Corporativo")
]
STATUS_MAQUINA = ["Conforme","Não conforme"]
CRITICIDADES = ["Alta","Média","Baixa"]
RISCOS_MAQUINA = ["Apreciação de risco não realizada", "Desprezível", "Atenção", "Significativo", "Alto", "Extremo"]
STATUS_COLOR_MAP = {
    "Conforme": "#16a34a",
    "Não conforme": "#dc2626",
}
# Paleta única para todos os indicadores e gráficos de Risco da Máquina.
# Escala visual: verde = melhor risco; vermelho escuro = pior risco.
RISCO_COLOR_MAP = {
    "Desprezível": "#16a34a",
    "Atenção": "#facc15",
    "Significativo": "#fb923c",
    "Alto": "#ef4444",
    "Extremo": "#b91c1c",
    "Apreciação de risco não realizada": "#475569",
}
RISCO_CARD_STYLE_MAP = {
    "Desprezível": {"bg": RISCO_COLOR_MAP["Desprezível"], "fg": "#ffffff", "border": "#15803d"},
    "Atenção": {"bg": RISCO_COLOR_MAP["Atenção"], "fg": "#422006", "border": "#ca8a04"},
    "Significativo": {"bg": RISCO_COLOR_MAP["Significativo"], "fg": "#ffffff", "border": "#ea580c"},
    "Alto": {"bg": RISCO_COLOR_MAP["Alto"], "fg": "#ffffff", "border": "#dc2626"},
    "Extremo": {"bg": RISCO_COLOR_MAP["Extremo"], "fg": "#ffffff", "border": "#7f1d1d"},
    "Apreciação de risco não realizada": {"bg": RISCO_COLOR_MAP["Apreciação de risco não realizada"], "fg": "#ffffff", "border": "#334155"},
}
PAC_COLOR_MAP = {"Crítico": "#dc2626", "Maior": "#f97316", "Menor": "#eab308"}
STATUS_PAC_COLOR_MAP = {"Aberta":"#f97316", "Em andamento":"#3b82f6", "Aguardando validação":"#8b5cf6", "Concluída":"#16a34a", "Vencida":"#dc2626", "Cancelada":"#64748b"}
DOCUMENTOS_ESSENCIAIS = ["Laudo NR-12","ART","Apreciação de risco"]
TIPOS_DOC_NR12 = ["Inventário NR-12","Apreciação de risco","Laudo NR-12","ART","Projeto mecânico","Projeto elétrico","Diagrama de segurança","Manual de operação","Manual de manutenção","Registro de treinamento","Evidência fotográfica","Checklist de validação","Termo de liberação para uso","Registro de intervenção","Registro de bloqueio/liberação","Outros"]
TIPOS_VERIFICACAO_NR12 = ["Inspeção de manutenção","Auditoria EHS","Auditoria corporativa","Auditoria extraordinária após incidente/quase-acidente"]
RESULTADOS_NR12 = ["Conforme","Não conforme"]
STATUS_PAC = ["Aberta","Em andamento","Aguardando validação","Concluída","Vencida","Cancelada"]
CLASSIFICACAO_PAC = ["Crítico","Maior","Menor"]
TIPOS_MUDANCA_CRITICA = ["Alteração de software/PLC","Alteração de relé/controlador de segurança","Substituição de componente de segurança","Remoção temporária de proteção","Alteração de proteção fixa/móvel","Alteração de sensores, cortinas, scanners ou intertravamentos","Mudança de layout com impacto em segurança","Retrofit","Manutenção corretiva crítica","Alteração mecânica, elétrica, pneumática ou hidráulica com impacto na condição segura"]
TIPOS_MUDANCA = TIPOS_MUDANCA_CRITICA + ["Ajuste operacional sem impacto em segurança","Atualização documental","Manutenção preventiva","Melhoria ergonômica sem impacto em segurança","Outro"]
STATUS_MOC = ["Aberta","Em análise","Aprovada","Implementada","Validada","Reprovada","Cancelada"]
STATUS_AUDITORIA = ["Planejada","Em andamento","Concluída","Cancelada"]
STATUS_RESPOSTA_EHS = ["Conforme","Parcialmente Conforme","Não Conforme"]
TIPOS_ACHADO_EHS = ["Não conformidade crítica","Não conformidade maior","Não conformidade menor","Observação","Oportunidade de melhoria","Boa prática"]

CHECKLIST_NR12 = {
"Checklist operacional":[
("Proteções fixas e móveis estão instaladas, íntegras e sem remoção indevida?",True),
("Botões de emergência estão acessíveis, identificados e sem obstrução?",True),
("Não há bypass visível, jumper, calço, fita, amarração ou improviso em dispositivos de segurança?",True),
("Sinalizações de segurança e identificação da máquina estão legíveis e preservadas?",False),
("Painéis, cabos, conexões e mangueiras não apresentam condição anormal aparente?",False),
("A máquina está sem ruído, vibração, vazamento ou condição insegura aparente?",False),
("Operador está treinado/autorizado e conhece a comunicação de desvios?",False),
("Desvios identificados foram comunicados imediatamente à liderança, Manutenção ou EHS?",False)],
"Inspeção de manutenção":[
("Proteções fixas e móveis estão presentes, íntegras, fixadas e alinhadas conforme projeto/laudo?",True),
("Intertravamentos, sensores, chaves, cortinas ou scanners funcionam conforme teste previsto?",True),
("Botões de emergência geram parada segura e não provocam partida inesperada no desacionamento?",True),
("Relé/controlador/PLC de segurança não apresenta falha, alarme ou alteração sem aprovação formal?",True),
("Não há bypass, atuador avulso, jumper, imã externo, fita, calço ou anulação de dispositivo?",True),
("Partida, rearme, modos de operação e parada segura permanecem conforme condição validada?",True),
("Painéis elétricos estão fechados, identificados, sem dano e com documentação rastreável?",False),
("Fontes de energia, pontos de bloqueio e procedimento LOTO estão disponíveis e funcionais?",False),
("Intervenções em proteção/dispositivo de segurança possuem ordem, registro e teste funcional pós-intervenção?",False),
("Componentes substituídos são equivalentes ou tiveram avaliação formal quando diferentes?",True),
("Proteções removidas para manutenção foram reinstaladas antes do retorno à operação?",True),
("Pendências, desvios e necessidade de bloqueio foram registrados e encaminhados?",False)],
"Auditoria EHS":[
("Inventário NR-12 está atualizado com status, criticidade, periodicidade, responsável e próximas inspeções?",False),
("Periodicidades de pré-uso, manutenção e auditoria EHS estão planejadas conforme criticidade?",False),
("Laudo NR-12, ART e apreciação de risco estão disponíveis e compatíveis com a condição atual?",True),
("Treinamentos de operadores e manutenção estão disponíveis para máquinas aplicáveis?",False),
("Checklists operacionais e inspeções de manutenção estão sendo executados no prazo?",False),
("Proteções, intertravamentos, sensores/cortinas e emergências permanecem funcionais em campo?",True),
("Não há evidência de bypass, descaracterização de segurança ou alteração sem aprovação?",True),
("Alterações que possam afetar a condição segura da máquina foram avaliadas, aprovadas, testadas e documentadas antes da liberação?",True),
("Desvios críticos geraram bloqueio imediato e liberação formal após correção/teste funcional?",True),
("Planos de ação possuem responsável, prazo, classificação e acompanhamento de vencidos/reincidentes?",False),
("Comitê Local NR-12 acompanha indicadores, desvios, bloqueios e pendências?",False),
("A liderança do site revisa periodicamente a consolidação de pendências, bloqueios, auditorias vencidas e PACs críticos?",False)]}
CHECKLIST_NR12["Auditoria corporativa"] = CHECKLIST_NR12["Auditoria EHS"]
CHECKLIST_NR12["Auditoria extraordinária após incidente/quase-acidente"] = CHECKLIST_NR12["Auditoria EHS"]

CHECKLIST_EHS = {
"Categoria 1 — Liderança e Gestão EHS":["Existe política de EHS formalizada e comunicada?","A liderança participa ativamente das ações de EHS?","Existem metas e indicadores de EHS definidos?","Os indicadores são monitorados periodicamente?","Existem reuniões periódicas de EHS?","Existe definição clara de responsabilidades EHS?","A organização promove cultura de reporte sem culpa?","Existem mecanismos formais de melhoria contínua?","Os riscos críticos são acompanhados pela liderança?","Existe integração entre EHS e operação?"],
"Categoria 2 — Conformidade Legal":["Existe levantamento atualizado de requisitos legais?","As licenças ambientais estão válidas?","Existem controles para condicionantes legais?","Os requisitos legais possuem evidências documentadas?","Existe monitoramento periódico de atendimento legal?","Há gestão de prazos legais?","Existe plano para adequação de não conformidades legais?","Existem auditorias legais periódicas?","Há rastreabilidade documental?","Os responsáveis legais estão definidos?"],
"Categoria 3 — Gestão de Riscos":["Existe processo formal de identificação de perigos?","Os riscos ocupacionais estão avaliados?","Existem controles implementados para riscos críticos?","Há hierarquia de controles aplicada?","Existe revisão periódica das análises de risco?","Mudanças operacionais passam por avaliação de risco?","Existe gestão de mudanças formal?","Há participação dos trabalhadores nas análises?","Os riscos ambientais estão avaliados?","Existe monitoramento de eficácia dos controles?"],
"Categoria 4 — Investigação de Incidentes":["Existe processo formal de investigação?","Os incidentes são reportados adequadamente?","As causas sistêmicas são avaliadas?","Há definição de ações corretivas?","Existe acompanhamento das ações?","Os aprendizados são compartilhados?","Há foco em melhoria do sistema e não culpabilização?","Near misses são investigados?","Existe rastreabilidade das investigações?","Indicadores de incidentes são monitorados?"],
"Categoria 5 — Treinamentos e Competências":["Existe matriz de treinamento atualizada?","Os treinamentos obrigatórios estão válidos?","Há avaliação de eficácia dos treinamentos?","Os terceiros recebem treinamentos adequados?","Existe controle de vencimentos?","As competências críticas estão mapeadas?","Há registros formais dos treinamentos?","Existe integração EHS para novos colaboradores?","Os líderes recebem treinamento em EHS?","Existe reciclagem periódica?"],
"Categoria 6 — Gestão Ambiental":["Existe segregação adequada de resíduos?","Os resíduos possuem identificação?","Existe controle de MTR?","Os CDFs são controlados?","Há controle de empresas destinadoras?","Existem inspeções ambientais periódicas?","Há controle de emissões atmosféricas?","Existe controle de efluentes?","Existe plano de resposta ambiental?","Há monitoramento de indicadores ambientais?"],
"Categoria 7 — Segurança Operacional":["Máquinas possuem proteções adequadas?","Existe atendimento à NR-12?","Há bloqueio e etiquetagem implementados?","Os EPIs estão adequados?","Existe inspeção periódica de segurança?","Há controle de permissões de trabalho?","Existe controle de trabalho em altura?","Espaços confinados possuem gestão adequada?","Existe controle de energia perigosa?","Há inspeções comportamentais estruturadas?"],
"Categoria 8 — Preparação e Resposta a Emergências":["Existe plano de emergência atualizado?","Há brigada treinada?","Existem simulados periódicos?","Os equipamentos de emergência estão inspecionados?","Existe controle de produtos perigosos?","Há rotas de fuga sinalizadas?","Existe comunicação de emergência definida?","Os cenários críticos foram avaliados?","Existe integração com serviços externos?","Há registros dos simulados?"]}

# ============================================================
# 4. Tema CSS
# ============================================================
def apply_theme():
    st.markdown("""
    <style>
    :root{
        --bg:#f6f8fb; --card:#ffffff; --ink:#111827; --muted:#64748b;
        --line:#e5e7eb; --gold:#d9a514; --gold2:#f5c542; --navy:#0f172a;
    }
    .stApp{background:var(--bg); font-family:"Inter","Segoe UI",Arial,sans-serif; color:var(--ink);}
    .block-container{padding-top:1.4rem; padding-bottom:2rem;}
    [data-testid="stSidebarNav"]{display:none!important;visibility:hidden!important;height:0!important;}
    section[data-testid="stSidebar"]{
        background:
          radial-gradient(circle at 20% 8%, rgba(96,165,250,.22), transparent 28%),
          radial-gradient(circle at 92% 35%, rgba(34,197,94,.10), transparent 24%),
          linear-gradient(160deg,#0b1220 0%,#111827 48%,#182235 100%)!important;
        border-right:1px solid rgba(255,255,255,.08);
        box-shadow:14px 0 35px rgba(15,23,42,.14);
    }
    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3,
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] span,
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] div[data-testid="stMarkdownContainer"]{color:#f8fafc!important;}
    section[data-testid="stSidebar"] .stCaptionContainer,
    section[data-testid="stSidebar"] small{color:#cbd5e1!important;}
    section[data-testid="stSidebar"] [data-baseweb="select"] *{color:#111827!important;}
    section[data-testid="stSidebar"] div[role="radiogroup"] label{
        background:rgba(255,255,255,.08); border:1px solid rgba(255,255,255,.10);
        border-radius:14px; padding:.55rem .7rem; margin:.18rem 0;
        transition:all .18s ease; box-shadow:0 8px 20px rgba(0,0,0,.08);
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] label:hover{
        background:rgba(245,197,66,.18); border-color:rgba(245,197,66,.45); transform:translateX(2px);
    }
    section[data-testid="stSidebar"] div.stButton>button{
        background:linear-gradient(135deg,#f8fafc,#ffffff)!important; color:#0f172a!important;
        border:1px solid rgba(148,163,184,.45)!important; box-shadow:0 10px 24px rgba(0,0,0,.18)!important;
    }
    section[data-testid="stSidebar"] div.stButton>button *,
    section[data-testid="stSidebar"] div.stButton>button p,
    section[data-testid="stSidebar"] div.stButton>button span{color:#0f172a!important;}
    div.stButton>button,div.stDownloadButton>button{
        border-radius:14px;border:1px solid #d7dde8;background:#fff;font-weight:750;
        box-shadow:0 6px 18px rgba(31,41,55,.07); transition:all .15s ease;
    }
    div.stButton>button:hover,div.stDownloadButton>button:hover{border-color:var(--gold); transform:translateY(-1px); box-shadow:0 10px 24px rgba(31,41,55,.12);}
    .ehs-header,.card,.kpi{background:var(--card);border:1px solid var(--line);border-radius:22px;box-shadow:0 10px 25px rgba(31,41,55,.07);padding:1rem;margin-bottom:.8rem}
    .ehs-header{background:linear-gradient(135deg,#fff,#fff8e3)} .ehs-header h1{margin:0;color:var(--ink);letter-spacing:-.03em}.ehs-header p{margin:.2rem 0;color:#5b6575}
    .kpi-label{color:#697386;font-size:.78rem;font-weight:850;text-transform:uppercase;letter-spacing:.02em}.kpi-value{font-size:1.8rem;font-weight:900;color:var(--ink)}.muted{color:#697386;font-size:.85rem}
    .section-title{font-size:1.2rem;font-weight:900;color:#1f2937;margin:1rem 0 .5rem;letter-spacing:-.01em}
    .empty{border:1px dashed #c9d1df;border-radius:18px;background:#fff;padding:1rem;text-align:center;color:#697386}
    .alert{background:#fff7df;border-left:6px solid var(--gold);border-radius:16px;padding:.8rem;margin:.5rem 0}
    .check-item{border:1px solid #e5e7eb;border-radius:18px;background:#fff;padding:1rem;margin:.7rem 0;box-shadow:0 8px 22px rgba(15,23,42,.05)}
    .check-q{font-weight:850;color:#111827;font-size:1rem;margin-bottom:.4rem}
    .check-meta{display:inline-block;border-radius:999px;padding:.12rem .5rem;font-size:.72rem;font-weight:800;background:#fff7df;color:#7a5400;border:1px solid #f3d27a;margin-left:.4rem}
    .check-category{margin:1rem 0 .35rem;padding:.55rem .8rem;border-radius:14px;background:#eef2ff;color:#1e293b;font-weight:900;border:1px solid #dbe3ff}
    </style>""", unsafe_allow_html=True)
def hide_sidebar_on_home():
    """Na tela inicial, a plataforma se comporta como landing page, sem menu lateral."""
    if st.session_state.get("modulo", "home") == "home":
        st.markdown("""
        <style>
        section[data-testid="stSidebar"]{display:none!important;}
        [data-testid="collapsedControl"]{display:none!important;}
        .block-container{padding-left:3rem!important;padding-right:3rem!important;}
        </style>
        """, unsafe_allow_html=True)

# ============================================================
# 5. Banco e modelos SQLAlchemy
# ============================================================
class Site(Base):
    __tablename__="sites"; id=Column(Integer,primary_key=True); codigo=Column(String(30),unique=True,nullable=False); nome=Column(String(120)); ativo=Column(Boolean,default=True)
class Usuario(Base):
    __tablename__="usuarios"; id=Column(Integer,primary_key=True); nome=Column(String(120),unique=True,nullable=False); perfil=Column(String(60)); site_id=Column(Integer,ForeignKey("sites.id")); ativo=Column(Boolean,default=True); site=relationship("Site")
class MaquinaNR12(Base):
    __tablename__="maquinas_nr12"
    id=Column(Integer,primary_key=True); codigo=Column(String(80),unique=True,nullable=False); site_id=Column(Integer,ForeignKey("sites.id"),nullable=False)
    area_setor=Column(String(120)); linha_processo=Column(String(120)); nome=Column(String(160),nullable=False); fabricante=Column(String(120)); modelo=Column(String(120)); numero_serie=Column(String(120)); ano=Column(String(20)); tipo_equipamento=Column(String(120)); responsavel_area=Column(String(120))
    criticidade=Column(String(20),default="Média"); risco_maquina=Column(String(80),default="Apreciação de risco não realizada"); status_nr12=Column(String(80),default="Conforme"); ultima_adequacao=Column(Date); ultima_auditoria=Column(Date); proxima_auditoria=Column(Date); data_prevista_adequacao=Column(Date)
    possui_laudo=Column(Boolean,default=False); possui_art=Column(Boolean,default=False); possui_apreciacao_risco=Column(Boolean,default=False); possui_manual_atualizado=Column(Boolean,default=False); possui_treinamento=Column(Boolean,default=False)
    observacoes=Column(Text); criado_em=Column(DateTime,default=datetime.utcnow); site=relationship("Site")
class DocumentoNR12(Base):
    __tablename__="documentos_nr12"; id=Column(Integer,primary_key=True); maquina_id=Column(Integer,ForeignKey("maquinas_nr12.id")); site_id=Column(Integer,ForeignKey("sites.id")); tipo=Column(String(120)); descricao=Column(Text); data_emissao=Column(Date); data_validade=Column(Date); arquivo_nome=Column(String(260)); arquivo_caminho=Column(String(500)); arquivo_bytes=Column(LargeBinary); responsavel=Column(String(120)); observacoes=Column(Text); criado_em=Column(DateTime,default=datetime.utcnow); maquina=relationship("MaquinaNR12"); site=relationship("Site")
class VerificacaoNR12(Base):
    __tablename__="verificacoes_nr12"; id=Column(Integer,primary_key=True); maquina_id=Column(Integer,ForeignKey("maquinas_nr12.id")); site_id=Column(Integer,ForeignKey("sites.id")); tipo=Column(String(120)); checklist_versao_id=Column(Integer,ForeignKey("checklist_versoes_maquinas.id")); data_verificacao=Column(Date); responsavel=Column(String(120)); resultado=Column(String(80)); pontuacao=Column(Float,default=0); possui_nc_critica=Column(Boolean,default=False); observacoes=Column(Text); proxima_verificacao=Column(Date); criado_em=Column(DateTime,default=datetime.utcnow); maquina=relationship("MaquinaNR12"); checklist_versao=relationship("ChecklistVersaoMaquinas")
class ChecklistItemNR12(Base):
    __tablename__="checklist_itens_nr12"; id=Column(Integer,primary_key=True); tipo_checklist=Column(String(120)); ordem=Column(Integer); pergunta=Column(Text); item_critico=Column(Boolean,default=False); ativo=Column(Boolean,default=True); __table_args__=(UniqueConstraint("tipo_checklist","ordem",name="uq_nr12_tipo_ordem"),)
class RespostaNR12(Base):
    __tablename__="respostas_nr12"; id=Column(Integer,primary_key=True); verificacao_id=Column(Integer,ForeignKey("verificacoes_nr12.id")); item_id=Column(Integer,ForeignKey("checklist_itens_nr12.id")); aplicavel=Column(Boolean,default=True); resultado=Column(String(60)); comentario_evidencia=Column(Text); gerar_pac=Column(Boolean,default=False); pergunta_snapshot=Column(Text); item_critico_snapshot=Column(Boolean,default=False); item=relationship("ChecklistItemNR12")
class PACNR12(Base):
    __tablename__="pac_nr12"; id=Column(Integer,primary_key=True); origem=Column(String(120)); site_id=Column(Integer,ForeignKey("sites.id")); maquina_id=Column(Integer,ForeignKey("maquinas_nr12.id")); verificacao_id=Column(Integer,ForeignKey("verificacoes_nr12.id")); item_checklist=Column(Text); descricao_desvio=Column(Text); classificacao=Column(String(40)); responsavel=Column(String(120)); area_responsavel=Column(String(120)); prazo=Column(Date); status=Column(String(60)); evidencia_conclusao=Column(Text); validacao_ehs=Column(Boolean,default=False); data_conclusao=Column(Date); comentarios=Column(Text); verificacao_eficacia=Column(Text); criado_em=Column(DateTime,default=datetime.utcnow); maquina=relationship("MaquinaNR12")
class MOCNR12(Base):
    __tablename__="moc_nr12"; id=Column(Integer,primary_key=True); maquina_id=Column(Integer,ForeignKey("maquinas_nr12.id")); site_id=Column(Integer,ForeignKey("sites.id")); tipo_mudanca=Column(String(180)); descricao=Column(Text); solicitante=Column(String(120)); area_solicitante=Column(String(120)); data=Column(Date); impacta_seguranca=Column(Boolean,default=False); exige_moc=Column(Boolean,default=False); status=Column(String(60)); aprovacao_ehs=Column(Boolean,default=False); aprovacao_manutencao=Column(Boolean,default=False); aprovacao_engenharia=Column(Boolean,default=False); aprovacao_producao=Column(Boolean,default=False); necessita_auditoria_pos_mudanca=Column(Boolean,default=False); necessita_treinamento=Column(Boolean,default=False); anexos=Column(Text); observacoes=Column(Text); validacao_final=Column(Boolean,default=False); criado_em=Column(DateTime,default=datetime.utcnow); maquina=relationship("MaquinaNR12")
class TermoGarantiaNR12(Base):
    __tablename__="termos_garantia_nr12"; id=Column(Integer,primary_key=True); site_id=Column(Integer,ForeignKey("sites.id")); ano_ciclo=Column(Integer); responsavel_ehs=Column(String(120)); responsavel_manutencao=Column(String(120)); responsavel_producao=Column(String(120)); responsavel_engenharia=Column(String(120)); lideranca_site=Column(String(120)); ressalvas=Column(Text); pendencias=Column(Text); declaracao_formal=Column(Text); data_emissao=Column(Date,default=date.today)
class AnexoArquivo(Base):
    __tablename__="anexos_arquivos"; id=Column(Integer,primary_key=True); modulo=Column(String(80)); entidade=Column(String(80)); entidade_id=Column(Integer); nome_arquivo=Column(String(260)); caminho=Column(String(500)); criado_em=Column(DateTime,default=datetime.utcnow)
class DiretivaEHS(Base):
    __tablename__="diretivas_ehs"; id=Column(Integer,primary_key=True); categoria=Column(String(180),unique=True); descricao=Column(Text); ativo=Column(Boolean,default=True)
class RequisitoEHS(Base):
    __tablename__="requisitos_ehs"; id=Column(Integer,primary_key=True); diretiva_id=Column(Integer,ForeignKey("diretivas_ehs.id")); ordem=Column(Integer); pergunta=Column(Text); criticidade=Column(String(40),default="Média"); evidencia_esperada=Column(Text); ativo=Column(Boolean,default=True); diretiva=relationship("DiretivaEHS"); __table_args__=(UniqueConstraint("diretiva_id","ordem",name="uq_ehs_diretiva_ordem"),)
class AuditoriaCruzada(Base):
    __tablename__="auditorias_cruzadas"; id=Column(Integer,primary_key=True); ano=Column(Integer); ciclo=Column(String(80)); site_auditado_id=Column(Integer,ForeignKey("sites.id")); site_auditor_lider_id=Column(Integer,ForeignKey("sites.id")); site_auditor_apoio_id=Column(Integer,ForeignKey("sites.id")); auditor_lider=Column(String(120)); auditor_apoio=Column(String(120)); data_planejada=Column(Date); data_inicio=Column(Date); data_fim=Column(Date); status=Column(String(60)); escopo=Column(Text); observacoes=Column(Text); conformidade_percentual=Column(Float,default=0); maturidade_media=Column(Float,default=0); criado_em=Column(DateTime,default=datetime.utcnow)
class RespostaAuditoriaEHS(Base):
    __tablename__="respostas_auditoria_ehs"; id=Column(Integer,primary_key=True); auditoria_id=Column(Integer,ForeignKey("auditorias_cruzadas.id")); requisito_id=Column(Integer,ForeignKey("requisitos_ehs.id")); aplicavel=Column(Boolean,default=True); status=Column(String(60)); nota_maturidade=Column(Float,default=3); evidencia_verificada=Column(Text); comentario_auditor=Column(Text); necessita_pac=Column(Boolean,default=False); requisito=relationship("RequisitoEHS"); __table_args__=(UniqueConstraint("auditoria_id","requisito_id",name="uq_resp_auditoria_requisito"),)
class PACEHS(Base):
    __tablename__="pac_ehs"; id=Column(Integer,primary_key=True); auditoria_id=Column(Integer,ForeignKey("auditorias_cruzadas.id")); site_id=Column(Integer,ForeignKey("sites.id")); requisito_id=Column(Integer,ForeignKey("requisitos_ehs.id")); tipo_achado=Column(String(80)); descricao=Column(Text); evidencia=Column(Text); risco=Column(Text); causa_raiz=Column(Text); acao_imediata=Column(Text); acao_corretiva=Column(Text); responsavel=Column(String(120)); area_responsavel=Column(String(120)); prazo=Column(Date); status=Column(String(60)); prioridade_criticidade=Column(String(40)); evidencia_conclusao=Column(Text); validacao_ehs=Column(Boolean,default=False); data_conclusao=Column(Date); verificacao_eficacia=Column(Text); status_eficacia=Column(String(80)); criado_em=Column(DateTime,default=datetime.utcnow); requisito=relationship("RequisitoEHS")
class EvidenciaEHS(Base):
    __tablename__="evidencias_ehs"; id=Column(Integer,primary_key=True); auditoria_id=Column(Integer); requisito_id=Column(Integer); pac_id=Column(Integer); descricao=Column(Text); arquivo_nome=Column(String(260)); arquivo_caminho=Column(String(500)); criado_em=Column(DateTime,default=datetime.utcnow)


class ChecklistVersaoMaquinas(Base):
    __tablename__ = "checklist_versoes_maquinas"
    id = Column(Integer, primary_key=True)
    tipo_checklist = Column(String(120), nullable=False)
    versao = Column(Integer, default=1)
    descricao = Column(Text)
    ativo = Column(Boolean, default=True)
    criado_em = Column(DateTime, default=datetime.utcnow)
    criado_por = Column(String(120))
    perguntas = relationship("ChecklistPerguntaVersaoMaquinas", cascade="all, delete-orphan")
    __table_args__ = (UniqueConstraint("tipo_checklist", "versao", name="uq_checklist_maquinas_tipo_versao"),)

class ChecklistPerguntaVersaoMaquinas(Base):
    __tablename__ = "checklist_perguntas_versao_maquinas"
    id = Column(Integer, primary_key=True)
    checklist_versao_id = Column(Integer, ForeignKey("checklist_versoes_maquinas.id"))
    ordem = Column(Integer)
    pergunta = Column(Text)
    item_critico = Column(Boolean, default=False)
    ativo = Column(Boolean, default=True)
    versao = relationship("ChecklistVersaoMaquinas")
    __table_args__ = (UniqueConstraint("checklist_versao_id", "ordem", name="uq_checklist_versao_ordem"),)

class LogSistema(Base):
    __tablename__ = "logs_sistema"
    id = Column(Integer, primary_key=True)
    usuario = Column(String(120))
    perfil = Column(String(80))
    modulo = Column(String(120))
    entidade = Column(String(120))
    entidade_id = Column(Integer)
    acao = Column(String(120))
    campo = Column(String(120))
    valor_anterior = Column(Text)
    valor_novo = Column(Text)
    data_hora = Column(DateTime, default=datetime.utcnow)
    observacao = Column(Text)

# ============================================================
# 6. Seed inicial
# ============================================================
def ensure_schema_updates():
    try:
        insp = inspect(engine)
        if "maquinas_nr12" in insp.get_table_names():
            cols = {c["name"] for c in insp.get_columns("maquinas_nr12")}
            with engine.begin() as conn:
                if "risco_maquina" not in cols:
                    conn.exec_driver_sql("ALTER TABLE maquinas_nr12 ADD COLUMN risco_maquina VARCHAR(80) DEFAULT 'Apreciação de risco não realizada'")
                if "data_prevista_adequacao" not in cols:
                    conn.exec_driver_sql("ALTER TABLE maquinas_nr12 ADD COLUMN data_prevista_adequacao DATE")
        insp = inspect(engine)
        if "documentos_nr12" in insp.get_table_names():
            cols = {c["name"] for c in insp.get_columns("documentos_nr12")}
            with engine.begin() as conn:
                if "arquivo_bytes" not in cols:
                    conn.exec_driver_sql("ALTER TABLE documentos_nr12 ADD COLUMN arquivo_bytes BLOB")
    except Exception:
        pass

def sync_checklists_base(db):
    for tipo, itens in CHECKLIST_NR12.items():
        for i, (pergunta, critico) in enumerate(itens, 1):
            item = db.query(ChecklistItemNR12).filter_by(tipo_checklist=tipo, ordem=i).first()
            if item:
                item.pergunta = pergunta
                item.item_critico = critico
                item.ativo = True
            else:
                db.add(ChecklistItemNR12(tipo_checklist=tipo, ordem=i, pergunta=pergunta, item_critico=critico, ativo=True))
    for cat, pergs in CHECKLIST_EHS.items():
        d = db.query(DiretivaEHS).filter_by(categoria=cat).first()
        if not d:
            d = DiretivaEHS(categoria=cat, descricao=cat, ativo=True)
            db.add(d)
            db.flush()
        for i, p in enumerate(pergs, 1):
            req = db.query(RequisitoEHS).filter_by(diretiva_id=d.id, ordem=i).first()
            if req:
                req.pergunta = p
            else:
                db.add(RequisitoEHS(diretiva_id=d.id, ordem=i, pergunta=p, criticidade="Alta" if i in [1,3,7] else "Média", evidencia_esperada="Evidência documental, registros, entrevistas e/ou verificação em campo.", ativo=True))

def init_db():
    Base.metadata.create_all(engine); ensure_schema_updates(); db=SessionLocal()
    try:
        if not db.query(Site).filter_by(codigo="Corporativo").first(): db.add(Site(codigo="Corporativo",nome="Corporativo"))
        for s in SITES_PADRAO:
            if not db.query(Site).filter_by(codigo=s).first(): db.add(Site(codigo=s,nome=s))
        db.flush()
        for nome,perfil,sitecod in USUARIOS_PADRAO:
            if not db.query(Usuario).filter_by(nome=nome).first():
                stt=db.query(Site).filter_by(codigo=sitecod).first(); db.add(Usuario(nome=nome,perfil=perfil,site_id=stt.id if stt else None))
        sync_checklists_base(db)
        for maq in db.query(MaquinaNR12).all():
            maq.status_nr12 = normalizar_status_nr12(maq.status_nr12)
        db.commit()
        if db.query(MaquinaNR12).count()==0:
            sjc=db.query(Site).filter_by(codigo="SJC").first()
            m=MaquinaNR12(codigo="SJC-PRENSA-001",site_id=sjc.id,area_setor="Produção",linha_processo="Linha 1",nome="Prensa hidráulica 001",fabricante="Fabricante A",modelo="PH-100",numero_serie="PH100",ano="2020",tipo_equipamento="Prensa",responsavel_area="Produção",criticidade="Alta",risco_maquina="Significativo",status_nr12="Não conforme",ultima_adequacao=date.today()-timedelta(days=180),ultima_auditoria=date.today()-timedelta(days=90),proxima_auditoria=date.today()+timedelta(days=40),data_prevista_adequacao=date.today()+timedelta(days=120),possui_laudo=True,possui_art=True,possui_apreciacao_risco=True,possui_manual_atualizado=True,possui_treinamento=True)
            db.add(m); db.flush()
            for t in DOCUMENTOS_ESSENCIAIS: db.add(DocumentoNR12(maquina_id=m.id,site_id=sjc.id,tipo=t,descricao=t,data_emissao=date.today()-timedelta(days=200),data_validade=date.today()+timedelta(days=365),arquivo_nome=t+".pdf",responsavel="EHS"))
            db.add(PACNR12(origem="Seed",site_id=sjc.id,maquina_id=m.id,descricao_desvio="Pendência menor em sinalização.",classificacao="Menor",responsavel="Manutenção SJC",area_responsavel="Manutenção",prazo=date.today()+timedelta(days=20),status="Em andamento"))
            db.commit()
        if db.query(AuditoriaCruzada).count()==0:
            sjc=db.query(Site).filter_by(codigo="SJC").first(); dia=db.query(Site).filter_by(codigo="DIA").first()
            a=AuditoriaCruzada(ano=date.today().year,ciclo="Ciclo 1",site_auditado_id=sjc.id,site_auditor_lider_id=dia.id,auditor_lider="Auditor EHS",data_planejada=date.today()+timedelta(days=30),status="Planejada",escopo="Auditoria cruzada seed")
            db.add(a); db.flush(); gerar_checklist_automatico_ehs(db,a.id,False); db.commit()
    finally: db.close()

# ============================================================
# 7. Permissão
# ============================================================
def can_admin(u): return bool(u and u.perfil=="Admin_LAG")
def can_edit(u,ctx="geral"):
    if not u or u.perfil=="Visualizador": return False
    if u.perfil=="Admin_LAG": return True
    return {
        "auditoria":["EHS_Local","Auditor"], "pac_ehs":["EHS_Local","Auditor","Responsavel_Acao"],
        "nr12_operacao":["EHS_Local","Producao_Operacao","Manutencao","Engenharia"],
        "nr12_manutencao":["EHS_Local","Manutencao","Engenharia"], "moc":["EHS_Local","Manutencao","Engenharia","Producao_Operacao"]
    }.get(ctx,["EHS_Local","Auditor","Manutencao","Engenharia","Responsavel_Acao"]).__contains__(u.perfil)
def visible_site_ids(u,db):
    if not u: return []
    if u.perfil=="Admin_LAG" or (u.site and u.site.codigo=="Corporativo"):
        return [s.id for s in db.query(Site).filter(Site.codigo!="Corporativo",Site.ativo==True).all()]
    return [u.site_id] if u.site_id else []

# ============================================================
# 8. Utilitários, 9. Cálculos, 10. Exportação
# ============================================================
def as_date(v):
    if v in (None,""): return None
    if isinstance(v,datetime): return v.date()
    if isinstance(v,date): return v
    try: return pd.to_datetime(v).date()
    except Exception: return None
def fmt_date(v): v=as_date(v); return v.strftime("%d/%m/%Y") if v else "—"
def site_code(db,id): s=db.get(Site,id) if id else None; return s.codigo if s else "—"
def machine_options(db,ids): return {f"{m.codigo} — {m.nome}":m.id for m in db.query(MaquinaNR12).filter(MaquinaNR12.site_id.in_(ids)).order_by(MaquinaNR12.codigo)}
def identificar_pac_vencido(prazo,status): return bool(as_date(prazo) and as_date(prazo)<date.today() and status not in ["Concluída","Cancelada"])
def calcular_status_documento(doc):
    if not doc: return "Ausente"
    if not doc.data_validade: return "Sem vencimento"
    if doc.data_validade<date.today(): return "Vencido"
    if doc.data_validade<=date.today()+timedelta(days=60): return "Próximo do vencimento"
    return "Válido"
def normalizar_status_nr12(status):
    return "Conforme" if status == "Conforme" else "Não conforme"

def calcular_status_maquina_nr12(db,m):
    if not m:
        return "Não conforme"
    docs={d.tipo:d for d in db.query(DocumentoNR12).filter_by(maquina_id=m.id)}
    if any((t not in docs) or calcular_status_documento(docs[t])=="Vencido" for t in DOCUMENTOS_ESSENCIAIS):
        return "Não conforme"
    if db.query(PACNR12).filter(PACNR12.maquina_id==m.id,PACNR12.classificacao=="Crítico",PACNR12.status.in_(["Aberta","Em andamento","Aguardando validação","Vencida"])).first():
        return "Não conforme"
    return normalizar_status_nr12(m.status_nr12)
def calcular_meta_adequacao_nr12(db, maquinas):
    total = len(maquinas)
    if total == 0:
        return {"total":0,"adequadas":0,"percentual_atual":0,"previstas_ate_hoje":0,"percentual_previsto":0,"dentro_plano":True,"vencidas":0,"sem_data":0}
    status_por_id = {m.id: calcular_status_maquina_nr12(db, m) for m in maquinas}
    adequadas = sum(1 for m in maquinas if status_por_id[m.id] == "Conforme")
    previstas_ate_hoje = sum(
        1 for m in maquinas
        if status_por_id[m.id] == "Conforme"
        or (as_date(getattr(m, "data_prevista_adequacao", None)) and as_date(getattr(m, "data_prevista_adequacao", None)) <= date.today())
    )
    vencidas = sum(
        1 for m in maquinas
        if status_por_id[m.id] != "Conforme"
        and as_date(getattr(m, "data_prevista_adequacao", None))
        and as_date(getattr(m, "data_prevista_adequacao", None)) < date.today()
    )
    sem_data = sum(
        1 for m in maquinas
        if status_por_id[m.id] != "Conforme"
        and not as_date(getattr(m, "data_prevista_adequacao", None))
    )
    return {
        "total": total,
        "adequadas": adequadas,
        "percentual_atual": round(adequadas / total * 100, 1),
        "previstas_ate_hoje": previstas_ate_hoje,
        "percentual_previsto": round(previstas_ate_hoje / total * 100, 1),
        "dentro_plano": adequadas >= previstas_ate_hoje,
        "vencidas": vencidas,
        "sem_data": sem_data,
    }

def montar_evolucao_adequacao_nr12(db, maquinas):
    total = len(maquinas)
    if total == 0:
        return pd.DataFrame()
    status_por_id = {m.id: calcular_status_maquina_nr12(db, m) for m in maquinas}
    datas_previstas = sorted({as_date(getattr(m, "data_prevista_adequacao", None)) for m in maquinas if as_date(getattr(m, "data_prevista_adequacao", None))})
    if not datas_previstas:
        return pd.DataFrame()
    pontos = sorted(set([date.today()] + datas_previstas))
    adequadas_atuais = sum(1 for m in maquinas if status_por_id[m.id] == "Conforme")
    rows = []
    for d in pontos:
        previstas = sum(
            1 for m in maquinas
            if status_por_id[m.id] == "Conforme"
            or (as_date(getattr(m, "data_prevista_adequacao", None)) and as_date(getattr(m, "data_prevista_adequacao", None)) <= d)
        )
        rows.append({"Data": d, "Série": "Evolução esperada", "% Adequação": round(previstas / total * 100, 1), "Quantidade": previstas})
        rows.append({"Data": d, "Série": "Conformidade atual", "% Adequação": round(adequadas_atuais / total * 100, 1), "Quantidade": adequadas_atuais})
    return pd.DataFrame(rows)
def calcular_resultado_verificacao_nr12(resps):
    ap=[r for r in resps if r.aplicavel and r.resultado!="Não aplicável"]
    if not ap:
        return "Não conforme",0,False
    pct=round(sum(1 for r in ap if r.resultado=="Conforme")/len(ap)*100,1)
    crit=any(r.resultado=="Não conforme" and r.item and r.item.item_critico for r in ap)
    if crit or pct < 90:
        return "Não conforme",pct,crit
    return "Conforme",pct,False
def calcular_conformidade_ehs(resps):
    ap=[r for r in resps if r.aplicavel and r.status!="Não Aplicável"]
    if not ap: return 0
    pts=sum(1 if r.status=="Conforme" else .5 if r.status=="Parcialmente Conforme" else 0 for r in ap)
    return round(pts/len(ap)*100,1)
def calcular_maturidade_ehs(resps):
    ap=[r for r in resps if r.aplicavel and r.status!="Não Aplicável"]; return round(sum(float(r.nota_maturidade or 0) for r in ap)/len(ap),2) if ap else 0
def gerar_pac_automatico_nr12(db,ver,r,resp=""):
    if db.query(PACNR12).filter_by(verificacao_id=ver.id,item_checklist=r.item.pergunta).first(): return
    clas="Crítico" if r.item and r.item.item_critico else "Maior"
    db.add(PACNR12(origem=ver.tipo,site_id=ver.site_id,maquina_id=ver.maquina_id,verificacao_id=ver.id,item_checklist=r.item.pergunta,descricao_desvio=r.comentario_evidencia or r.item.pergunta,classificacao=clas,responsavel=resp,area_responsavel="A definir",prazo=date.today()+timedelta(days=15 if clas=="Crítico" else 30),status="Aberta"))
def gerar_pac_automatico_ehs(db,a,r,resp=""):
    if db.query(PACEHS).filter_by(auditoria_id=a.id,requisito_id=r.requisito_id).first(): return
    tipo="Não conformidade crítica" if r.status=="Não Conforme" and r.requisito and r.requisito.criticidade=="Alta" else "Não conformidade maior" if r.status=="Não Conforme" else "Observação"
    db.add(PACEHS(auditoria_id=a.id,site_id=a.site_auditado_id,requisito_id=r.requisito_id,tipo_achado=tipo,descricao=r.comentario_auditor or r.requisito.pergunta,evidencia=r.evidencia_verificada,risco="A avaliar",causa_raiz="A definir",acao_imediata="A definir",acao_corretiva="A definir",responsavel=resp,area_responsavel="A definir",prazo=date.today()+timedelta(days=15 if tipo=="Não conformidade crítica" else 30),status="Aberta",prioridade_criticidade="Alta" if tipo=="Não conformidade crítica" else "Média"))
def gerar_excel(sheets):
    out=io.BytesIO()
    with pd.ExcelWriter(out,engine="openpyxl") as w:
        for name,df in sheets.items():
            if df is None or df.empty: df=pd.DataFrame({"Mensagem":["Sem dados"]})
            df.to_excel(w,index=False,sheet_name=name[:31])
    return out.getvalue()
def gerar_pdf(titulo,subtitulo,secoes):
    buf=io.BytesIO(); doc=SimpleDocTemplate(buf,pagesize=A4,rightMargin=1.5*cm,leftMargin=1.5*cm,topMargin=1.5*cm,bottomMargin=1.5*cm)
    styles=getSampleStyleSheet(); title=ParagraphStyle("T",parent=styles["Title"],fontSize=17,textColor=colors.HexColor("#111827")); h=ParagraphStyle("H",parent=styles["Heading2"],fontSize=12); b=ParagraphStyle("B",parent=styles["BodyText"],fontSize=8,leading=11)
    story=[Paragraph(titulo,title),Paragraph(subtitulo,b),Spacer(1,.3*cm)]
    for t,c in secoes:
        story.append(Paragraph(t,h))
        if isinstance(c,pd.DataFrame):
            if c.empty: story.append(Paragraph("Sem dados.",b))
            else:
                df=c.fillna("—").astype(str).iloc[:25,:6]
                tbl=Table([list(df.columns)]+df.values.tolist(),repeatRows=1)
                tbl.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#f5c542")),("GRID",(0,0),(-1,-1),.25,colors.lightgrey),("FONTSIZE",(0,0),(-1,-1),7),("VALIGN",(0,0),(-1,-1),"TOP")]))
                story.append(tbl)
        else: story.append(Paragraph(str(c).replace("\n","<br/>"),b))
        story.append(Spacer(1,.25*cm))
    doc.build(story); return buf.getvalue()
def update_vencidos(db):
    for model in [PACNR12,PACEHS]:
        for p in db.query(model).filter(model.status.notin_(["Concluída","Cancelada"])):
            if identificar_pac_vencido(p.prazo,p.status): p.status="Vencida"
    db.commit()

# ============================================================
# 11. Componentes de UI
# ============================================================
def header(t,s=""): st.markdown(f"<div class='ehs-header'><h1>{t}</h1><p>{s}</p></div>",unsafe_allow_html=True)
def section(t): st.markdown(f"<div class='section-title'>{t}</div>",unsafe_allow_html=True)
def kpi_card(l,v,h=""): st.markdown(f"<div class='kpi'><div class='kpi-label'>{l}</div><div class='kpi-value'>{v}</div><div class='muted'>{h}</div></div>",unsafe_allow_html=True)
def html_escape(v):
    return str(v).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
def kpi_card_colorido(l,v,h="",bg="#ffffff",fg="#111827",border="#e5e7eb"):
    st.markdown(
        f"""
        <div class='kpi' style='background:{bg};border-color:{border};box-shadow:0 10px 25px rgba(15,23,42,.13);'>
            <div class='kpi-label' style='color:{fg};opacity:.92;'>{html_escape(l)}</div>
            <div class='kpi-value' style='color:{fg};'>{html_escape(v)}</div>
            <div class='muted' style='color:{fg};opacity:.88;'>{html_escape(h)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
def module_card(t,d,i): st.markdown(f"<div class='card'><h3>{i} {t}</h3><p class='muted'>{d}</p></div>",unsafe_allow_html=True)
def empty_state(t): st.markdown(f"<div class='empty'>{t}</div>",unsafe_allow_html=True)
def alert_card(t): st.markdown(f"<div class='alert'>{t}</div>",unsafe_allow_html=True)
def user_selector(db, location="sidebar"):
    us=db.query(Usuario).filter_by(ativo=True).order_by(Usuario.nome).all(); nomes=[u.nome for u in us]
    if not nomes:
        return None
    if "usuario_nome" not in st.session_state:
        st.session_state.usuario_nome="Eduardo" if "Eduardo" in nomes else nomes[0]
    idx=nomes.index(st.session_state.usuario_nome) if st.session_state.usuario_nome in nomes else 0
    if location=="main":
        c1,c2=st.columns([3,1])
        with c2:
            sel=st.selectbox("Usuário",nomes,index=idx,key="usuario_home_select")
            u=db.query(Usuario).filter_by(nome=sel).first()
            st.caption(f"Perfil: {u.perfil} | Site: {u.site.codigo if u and u.site else '—'}")
    else:
        sel=st.sidebar.selectbox("Usuário",nomes,index=idx,key="usuario_sidebar_select")
        u=db.query(Usuario).filter_by(nome=sel).first()
        st.sidebar.caption(f"Perfil: {u.perfil} | Site: {u.site.codigo if u and u.site else '—'}")
    st.session_state.usuario_nome=sel
    return u
def download_excel_button(label,file,sheets): st.download_button(label,gerar_excel(sheets),file,mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True)
def download_pdf_button(label,file,pdf): st.download_button(label,pdf,file,mime="application/pdf",use_container_width=True)

# DataFrames
def df_maquinas(db,ids):
    rows = []
    for m in db.query(MaquinaNR12).filter(MaquinaNR12.site_id.in_(ids)).order_by(MaquinaNR12.codigo):
        risco = m.risco_maquina or ("Desprezível" if m.possui_apreciacao_risco else "Apreciação de risco não realizada")
        rows.append({"ID":m.id,"Código":m.codigo,"Site":site_code(db,m.site_id),"Área":m.area_setor,"Linha":m.linha_processo,"Máquina":m.nome,"Fabricante":m.fabricante,"Modelo":m.modelo,"Série":m.numero_serie,"Ano":m.ano,"Tipo":m.tipo_equipamento,"Responsável":m.responsavel_area,"Criticidade":m.criticidade,"Risco":risco,"Status NR-12":calcular_status_maquina_nr12(db,m),"Data prevista adequação":fmt_date(getattr(m,"data_prevista_adequacao",None)),"Próxima auditoria":fmt_date(m.proxima_auditoria),"Laudo":"Sim" if m.possui_laudo else "Não","ART":"Sim" if m.possui_art else "Não","Apreciação":"Sim" if m.possui_apreciacao_risco else "Não","Manual":"Sim" if m.possui_manual_atualizado else "Não","Treinamento":"Sim" if m.possui_treinamento else "Não","Observações":m.observacoes})
    return pd.DataFrame(rows)
def df_docs(db,ids):
    return pd.DataFrame([{"ID":d.id,"Site":site_code(db,d.site_id),"Máquina":d.maquina.codigo if d.maquina else "—","Tipo":d.tipo,"Status":calcular_status_documento(d),"Emissão":fmt_date(d.data_emissao),"Validade":fmt_date(d.data_validade),"Arquivo":d.arquivo_nome,"Responsável":d.responsavel,"Descrição":d.descricao,"Observações":d.observacoes} for d in db.query(DocumentoNR12).filter(DocumentoNR12.site_id.in_(ids)).order_by(DocumentoNR12.id.desc())])
def df_ver(db,ids):
    return pd.DataFrame([{"ID":v.id,"Site":site_code(db,v.site_id),"Máquina":v.maquina.codigo if v.maquina else "—","Tipo":v.tipo,"Data":fmt_date(v.data_verificacao),"Responsável":v.responsavel,"Resultado":v.resultado,"Pontuação %":v.pontuacao,"NC crítica":"Sim" if v.possui_nc_critica else "Não","Próxima":fmt_date(v.proxima_verificacao),"Observações":v.observacoes} for v in db.query(VerificacaoNR12).filter(VerificacaoNR12.site_id.in_(ids)).order_by(VerificacaoNR12.id.desc())])
def df_pac_nr12(db,ids):
    return pd.DataFrame([{"ID":p.id,"Site":site_code(db,p.site_id),"Máquina":p.maquina.codigo if p.maquina else "—","Origem":p.origem,"Classificação":p.classificacao,"Status":"Vencida" if identificar_pac_vencido(p.prazo,p.status) else p.status,"Responsável":p.responsavel,"Área":p.area_responsavel,"Prazo":fmt_date(p.prazo),"Desvio":p.descricao_desvio,"Evidência":p.evidencia_conclusao,"Validação EHS":"Sim" if p.validacao_ehs else "Não","Eficácia":p.verificacao_eficacia} for p in db.query(PACNR12).filter(PACNR12.site_id.in_(ids)).order_by(PACNR12.id.desc())])
def df_moc(db,ids):
    return pd.DataFrame([{"ID":m.id,"Site":site_code(db,m.site_id),"Máquina":m.maquina.codigo if m.maquina else "—","Tipo":m.tipo_mudanca,"Descrição":m.descricao,"Solicitante":m.solicitante,"Área":m.area_solicitante,"Data":fmt_date(m.data),"Impacta segurança":"Sim" if m.impacta_seguranca else "Não","Exige MOC":"Sim" if m.exige_moc else "Não","Status":m.status,"EHS":"Sim" if m.aprovacao_ehs else "Não","Manutenção":"Sim" if m.aprovacao_manutencao else "Não","Engenharia":"Sim" if m.aprovacao_engenharia else "Não","Produção":"Sim" if m.aprovacao_producao else "Não","Auditoria pós":"Sim" if m.necessita_auditoria_pos_mudanca else "Não","Treinamento":"Sim" if m.necessita_treinamento else "Não","Validação final":"Sim" if m.validacao_final else "Não"} for m in db.query(MOCNR12).filter(MOCNR12.site_id.in_(ids)).order_by(MOCNR12.id.desc())])
def df_aud(db,ids):
    rows=[]
    for a in db.query(AuditoriaCruzada).filter(AuditoriaCruzada.site_auditado_id.in_(ids)).order_by(AuditoriaCruzada.id.desc()):
        res=db.query(RespostaAuditoriaEHS).filter_by(auditoria_id=a.id).all(); a.conformidade_percentual=calcular_conformidade_ehs(res); a.maturidade_media=calcular_maturidade_ehs(res)
        rows.append({"ID":a.id,"Ano":a.ano,"Ciclo":a.ciclo,"Site auditado":site_code(db,a.site_auditado_id),"Site auditor líder":site_code(db,a.site_auditor_lider_id),"Site auditor apoio":site_code(db,a.site_auditor_apoio_id),"Auditor líder":a.auditor_lider,"Auditor apoio":a.auditor_apoio,"Data planejada":fmt_date(a.data_planejada),"Início":fmt_date(a.data_inicio),"Fim":fmt_date(a.data_fim),"Status":a.status,"Conformidade %":a.conformidade_percentual,"Maturidade":a.maturidade_media,"Escopo":a.escopo})
    db.commit(); return pd.DataFrame(rows)
def df_pac_ehs(db,ids):
    return pd.DataFrame([{"ID":p.id,"Site":site_code(db,p.site_id),"Auditoria":p.auditoria_id,"Requisito":p.requisito.pergunta if p.requisito else "—","Tipo de achado":p.tipo_achado,"Descrição":p.descricao,"Evidência":p.evidencia,"Risco":p.risco,"Causa raiz":p.causa_raiz,"Ação imediata":p.acao_imediata,"Ação corretiva":p.acao_corretiva,"Responsável":p.responsavel,"Área":p.area_responsavel,"Prazo":fmt_date(p.prazo),"Status":"Vencida" if identificar_pac_vencido(p.prazo,p.status) else p.status,"Prioridade":p.prioridade_criticidade,"Validação EHS":"Sim" if p.validacao_ehs else "Não","Eficácia":p.verificacao_eficacia} for p in db.query(PACEHS).filter(PACEHS.site_id.in_(ids)).order_by(PACEHS.id.desc())])

# ============================================================
# 12. Páginas comuns
# ============================================================
def dashboard_integrado(db,u):
    ids=visible_site_ids(u,db); update_vencidos(db)
    ms=db.query(MaquinaNR12).filter(MaquinaNR12.site_id.in_(ids)).all()
    auds=db.query(AuditoriaCruzada).filter(AuditoriaCruzada.site_auditado_id.in_(ids)).all()
    conf=[calcular_conformidade_ehs(db.query(RespostaAuditoriaEHS).filter_by(auditoria_id=a.id).all()) for a in auds]
    vals=[len(ms),sum(1 for m in ms if calcular_status_maquina_nr12(db,m)=="Não conforme"),db.query(PACNR12).filter(PACNR12.site_id.in_(ids),PACNR12.status=="Vencida").count(),db.query(PACNR12).filter(PACNR12.site_id.in_(ids),PACNR12.status.in_(["Aberta","Em andamento","Aguardando validação"])).count(),db.query(AuditoriaCruzada).filter(AuditoriaCruzada.site_auditado_id.in_(ids),AuditoriaCruzada.status=="Em andamento").count(),f"{round(sum(conf)/len(conf),1) if conf else 0}%",db.query(PACEHS).filter(PACEHS.site_id.in_(ids),PACEHS.status=="Vencida").count(),db.query(PACEHS).filter(PACEHS.site_id.in_(ids),PACEHS.tipo_achado=="Não conformidade crítica",PACEHS.status.in_(["Aberta","Em andamento","Vencida"])).count()]
    labs=["Total de máquinas NR-12","Máquinas não conformes","PACs NR-12 vencidos","PACs NR-12 abertos","Auditorias em andamento","Conformidade média EHS","PACs EHS vencidos","NC críticas EHS"]
    section("Visão geral integrada")
    for chunk in [range(4),range(4,8)]:
        cols=st.columns(4)
        for c,i in zip(cols,chunk):
            with c: kpi_card(labs[i],vals[i])
    alerts=[]
    for p in db.query(PACNR12).filter(PACNR12.site_id.in_(ids),PACNR12.status.in_(["Vencida","Aberta","Em andamento"])).limit(5): 
        if p.status=="Vencida" or p.classificacao=="Crítico": alerts.append({"Módulo":"NR-12","Tipo":p.classificacao,"Site":site_code(db,p.site_id),"Descrição":(p.descricao_desvio or "")[:120],"Prazo":fmt_date(p.prazo),"Status":p.status})
    for p in db.query(PACEHS).filter(PACEHS.site_id.in_(ids),PACEHS.status.in_(["Vencida","Aberta","Em andamento"])).limit(5):
        if p.status=="Vencida" or p.tipo_achado=="Não conformidade crítica": alerts.append({"Módulo":"Auditoria EHS","Tipo":p.tipo_achado,"Site":site_code(db,p.site_id),"Descrição":(p.descricao or "")[:120],"Prazo":fmt_date(p.prazo),"Status":p.status})
    section("Alertas principais")
    if alerts:
        st.dataframe(pd.DataFrame(alerts), use_container_width=True, hide_index=True)
    else:
        empty_state("Nenhum alerta crítico ou vencido identificado.")

def home_page(db,u):
    header("Plataforma Integrada EHS","NR-12 e Auditorias Cruzadas de Diretrizes de EHS em uma única aplicação")
    dashboard_integrado(db,u); section("Módulos")
    c1,c2=st.columns(2)
    with c1:
        module_card("Sustentação NR-12","Inventário, documentos, checklists, PAC, pendências e relatórios.","⚙️")
        if st.button("Acessar Sustentação NR-12",use_container_width=True):
            st.session_state.modulo="nr12"
            st.session_state.page_nr12="Dashboard NR-12"
            st.session_state.nav_nr12="Dashboard NR-12"
            st.rerun()
    with c2:
        module_card("Auditoria Cruzada de Diretrizes de EHS","Planejamento, checklist incorporado, evidências, maturidade, PAC e relatórios.","🧭")
        if st.button("Acessar Auditoria Cruzada",use_container_width=True):
            st.session_state.modulo="ehs"
            st.session_state.page_ehs="Dashboard Auditoria Cruzada"
            st.session_state.nav_ehs="Dashboard Auditoria Cruzada"
            st.rerun()
def nr12_dashboard(db,u):
    header("Sustentação da Conformidade NR-12","Dashboard para máquinas submetidas à NR-12")
    ids=visible_site_ids(u,db)
    dfm_full=df_maquinas(db,ids)
    if dfm_full.empty:
        empty_state("Nenhuma máquina cadastrada para os filtros de acesso do usuário.")
        return
    section("Filtros")
    f1,f2,f3,f4=st.columns(4)
    unidades=f1.multiselect("Unidade", sorted(dfm_full["Site"].dropna().unique()))
    riscos=f2.multiselect("Risco da máquina", [r for r in RISCOS_MAQUINA if r in set(dfm_full["Risco"].dropna())])
    crits=f3.multiselect("Criticidade", sorted(dfm_full["Criticidade"].dropna().unique()))
    status_f=f4.multiselect("Status NR-12", [s for s in STATUS_MAQUINA if s in set(dfm_full["Status NR-12"].dropna())])
    dfm=dfm_full.copy()
    if unidades: dfm=dfm[dfm["Site"].isin(unidades)]
    if riscos: dfm=dfm[dfm["Risco"].isin(riscos)]
    if crits: dfm=dfm[dfm["Criticidade"].isin(crits)]
    if status_f: dfm=dfm[dfm["Status NR-12"].isin(status_f)]
    m_ids=dfm["ID"].astype(int).tolist() if not dfm.empty else []
    ms=db.query(MaquinaNR12).filter(MaquinaNR12.id.in_(m_ids)).all() if m_ids else []
    sts=[calcular_status_maquina_nr12(db,m) for m in ms]
    total=len(ms)
    docs=db.query(DocumentoNR12).filter(DocumentoNR12.maquina_id.in_(m_ids)).all() if m_ids else []
    dfp=df_pac_nr12(db,ids)
    if not dfp.empty and not dfm.empty:
        codigos=set(dfm["Código"].astype(str))
        dfp=dfp[dfp["Máquina"].isin(codigos)]
    meta=calcular_meta_adequacao_nr12(db,ms)
    cards=[
        ("Total de máquinas",total),
        ("% máquinas conformes",f"{round(sts.count('Conforme')/total*100,1) if total else 0}%"),
        ("Meta de adequação",f"{meta['percentual_atual']}%",f"{meta['adequadas']}/{meta['total']} máquinas adequadas"),
        ("Status do plano","Dentro do plano" if meta["dentro_plano"] else "Fora do plano",f"Adequadas: {meta['adequadas']} | Previstas até hoje: {meta['previstas_ate_hoje']}"),
        ("Máquinas não conformes",sts.count("Não conforme")),
        ("Adequações vencidas",meta["vencidas"],"Máquinas não conformes com data prevista ultrapassada"),
        ("Sem data de adequação",meta["sem_data"],"Máquinas não conformes sem data prevista"),
        ("Docs essenciais vencidos",sum(1 for d in docs if d.tipo in DOCUMENTOS_ESSENCIAIS and calcular_status_documento(d)=="Vencido")),
        ("Docs essenciais ausentes",sum(sum(1 for t in DOCUMENTOS_ESSENCIAIS if t not in {d.tipo for d in db.query(DocumentoNR12).filter_by(maquina_id=m.id)}) for m in ms)),
        ("Verificações vencidas",sum(1 for m in ms if m.proxima_auditoria and m.proxima_auditoria<date.today())),
        ("Verificações próximas",sum(1 for m in ms if m.proxima_auditoria and date.today()<=m.proxima_auditoria<=date.today()+timedelta(days=60))),
        ("PACs abertos",0 if dfp.empty else int(dfp["Status"].isin(["Aberta","Em andamento","Aguardando validação"]).sum())),
        ("PACs vencidos",0 if dfp.empty else int((dfp["Status"]=="Vencida").sum())),
        ("Risco alto/extremo",0 if dfm.empty else int(dfm["Risco"].isin(["Alto","Extremo","Apreciação de risco não realizada"]).sum()))
    ]
    for base in range(0,len(cards),4):
        cols=st.columns(4)
        for c,card in zip(cols,cards[base:base+4]):
            with c:
                if len(card)==3:
                    kpi_card(card[0],card[1],card[2])
                else:
                    kpi_card(card[0],card[1])
    if meta["dentro_plano"]:
        st.success(f"Meta de adequação dentro do plano: {meta['adequadas']} máquinas conformes para {meta['previstas_ate_hoje']} previstas até hoje.")
    else:
        st.warning(f"Meta de adequação fora do plano: {meta['adequadas']} máquinas conformes para {meta['previstas_ate_hoje']} previstas até hoje.")

    section("Indicador por tipo de risco da máquina")
    risco_counts=dfm.groupby("Risco",as_index=False).size().rename(columns={"size":"Quantidade"}) if not dfm.empty else pd.DataFrame(columns=["Risco","Quantidade"])
    risco_dict={r:0 for r in RISCOS_MAQUINA}
    if not risco_counts.empty:
        risco_dict.update(dict(zip(risco_counts["Risco"],risco_counts["Quantidade"])))
    for base in range(0,len(RISCOS_MAQUINA),3):
        cols=st.columns(3)
        for c,risco_nome in zip(cols,RISCOS_MAQUINA[base:base+3]):
            with c:
                estilo=RISCO_CARD_STYLE_MAP.get(risco_nome,{"bg":"#ffffff","fg":"#111827","border":"#e5e7eb"})
                kpi_card_colorido(risco_nome,risco_dict.get(risco_nome,0),"Máquinas nesse nível de risco",estilo["bg"],estilo["fg"],estilo["border"])

    section("Gráficos")
    c1,c2=st.columns(2)
    with c1:
        st.plotly_chart(px.histogram(dfm, x="Site", color="Status NR-12", barmode="group", title="Status NR-12 por site", color_discrete_map=STATUS_COLOR_MAP).update_layout(template="plotly_white"), use_container_width=True)
    with c2:
        fig_risco = px.bar(
            risco_counts,
            x="Risco",
            y="Quantidade",
            color="Risco",
            text="Quantidade",
            title="Quantidade de máquinas por risco",
            color_discrete_map=RISCO_COLOR_MAP,
            category_orders={"Risco": RISCOS_MAQUINA},
        )
        fig_risco.update_traces(textposition="outside", marker_line_color="#ffffff", marker_line_width=1.2)
        fig_risco.update_layout(
            template="plotly_white",
            xaxis_title="Risco",
            yaxis_title="Máquinas",
            showlegend=False,
        )
        st.plotly_chart(fig_risco, use_container_width=True)
    c3,c4=st.columns(2)
    with c3:
        if not dfp.empty:
            st.plotly_chart(px.histogram(dfp, x="Status", color="Classificação", barmode="group", title="PAC por status/classificação", color_discrete_map=PAC_COLOR_MAP).update_layout(template="plotly_white"), use_container_width=True)
        else:
            empty_state("Sem PACs para os filtros selecionados.")
    with c4:
        verificacoes_vencidas=sum(1 for m in ms if m.proxima_auditoria and m.proxima_auditoria<date.today())
        verificacoes_proximas=sum(1 for m in ms if m.proxima_auditoria and date.today()<=m.proxima_auditoria<=date.today()+timedelta(days=60))
        dv=pd.DataFrame([{"Tipo":"Vencidas","Qtd":verificacoes_vencidas},{"Tipo":"Próximas","Qtd":verificacoes_proximas}])
        st.plotly_chart(px.bar(dv,x="Tipo",y="Qtd",color="Tipo",title="Verificações vencidas/próximas", color_discrete_map={"Vencidas":"#dc2626","Próximas":"#f59e0b"}).update_layout(template="plotly_white", showlegend=False),use_container_width=True)

    section("Evolução esperada da adequação NR-12")
    evolucao=montar_evolucao_adequacao_nr12(db,ms)
    if not evolucao.empty:
        st.plotly_chart(
            px.line(evolucao, x="Data", y="% Adequação", color="Série", markers=True,
                    hover_data=["Quantidade"], title="Evolução esperada da adequação com base na Data Prevista para Adequação")
              .update_layout(template="plotly_white", yaxis_range=[0,100], xaxis_title="Data", yaxis_title="% de máquinas adequadas"),
            use_container_width=True
        )
    else:
        empty_state("Sem datas previstas de adequação cadastradas para gerar a evolução esperada.")

    section("Máquinas prioritárias")
    pr=dfm[dfm["Status NR-12"]=="Não conforme"] if not dfm.empty else pd.DataFrame()
    if not pr.empty:
        st.dataframe(pr, use_container_width=True, hide_index=True)
    else:
        empty_state("Nenhuma máquina prioritária nos filtros selecionados.")

def nr12_inventario(db,u):
    header("Inventário de Máquinas","Cadastro, edição, consulta e exportação")
    ids=visible_site_ids(u,db)
    sites={s.codigo:s.id for s in db.query(Site).filter(Site.id.in_(ids)).order_by(Site.codigo)}

    # 1) Consulta
    section("Consulta")
    df=df_maquinas(db,ids)
    if df.empty:
        empty_state("Nenhuma máquina cadastrada.")
    else:
        f1,f2,f3,f4=st.columns(4)
        fs=f1.multiselect("Filtrar status",sorted(df["Status NR-12"].dropna().unique()))
        fr=f2.multiselect("Filtrar risco",[r for r in RISCOS_MAQUINA if r in set(df["Risco"].dropna())])
        fc=f3.multiselect("Filtrar criticidade",sorted(df["Criticidade"].dropna().unique()))
        fu=f4.multiselect("Filtrar unidade",sorted(df["Site"].dropna().unique()))
        f=df.copy()
        if fs: f=f[f["Status NR-12"].isin(fs)]
        if fr: f=f[f["Risco"].isin(fr)]
        if fc: f=f[f["Criticidade"].isin(fc)]
        if fu: f=f[f["Site"].isin(fu)]
        st.dataframe(f,use_container_width=True,hide_index=True)
        download_excel_button("Exportar Excel","inventario_maquinas_nr12.xlsx",{"Inventário":f})

    # 2) Cadastrar máquina
    if can_edit(u,"nr12_manutencao"):
        if not sites:
            alert_card("Nenhum site disponível para cadastro conforme o perfil do usuário.")
        else:
            with st.expander("Cadastrar máquina"):
                with st.form("maq"):
                    a,b,c=st.columns(3)
                    with a:
                        cod=st.text_input("Código*")
                        site=st.selectbox("Site*",list(sites))
                        area=st.text_input("Área/setor")
                        linha=st.text_input("Linha/processo")
                        nome=st.text_input("Nome*")
                        fab=st.text_input("Fabricante")
                    with b:
                        mod=st.text_input("Modelo")
                        serie=st.text_input("Número de série")
                        ano=st.text_input("Ano")
                        tipo=st.text_input("Tipo de equipamento")
                        resp=st.text_input("Responsável da área")
                        crit=st.selectbox("Criticidade",CRITICIDADES)
                    with c:
                        risco=st.selectbox("Risco da máquina",RISCOS_MAQUINA)
                        status=st.selectbox("Status NR-12",STATUS_MAQUINA)
                        prox=st.date_input("Próxima auditoria prevista",value=date.today()+timedelta(days=180))
                        data_prevista_adequacao=None
                        if status!="Conforme":
                            data_prevista_adequacao=st.date_input("Data prevista para adequação",value=date.today()+timedelta(days=90),help="Obrigatória para máquinas com Status NR-12 diferente de Conforme.")
                        else:
                            st.caption("Máquina conforme: data prevista para adequação não aplicável.")
                    ck=st.columns(5)
                    laudo=ck[0].checkbox("Laudo")
                    art=ck[1].checkbox("ART")
                    apr=ck[2].checkbox("Apreciação")
                    man=ck[3].checkbox("Manual")
                    tre=ck[4].checkbox("Treinamento")
                    obs=st.text_area("Observações")
                    if st.form_submit_button("Salvar",use_container_width=True):
                        if cod and nome and not db.query(MaquinaNR12).filter_by(codigo=cod).first():
                            db.add(MaquinaNR12(codigo=cod,site_id=sites[site],area_setor=area,linha_processo=linha,nome=nome,fabricante=fab,modelo=mod,numero_serie=serie,ano=ano,tipo_equipamento=tipo,responsavel_area=resp,criticidade=crit,risco_maquina=risco,status_nr12=status,proxima_auditoria=prox,data_prevista_adequacao=data_prevista_adequacao,possui_laudo=laudo,possui_art=art,possui_apreciacao_risco=apr,possui_manual_atualizado=man,possui_treinamento=tre,observacoes=obs))
                            db.commit()
                            st.success("Máquina cadastrada.")
                            st.rerun()
                        else:
                            st.error("Preencha código/nome e evite código duplicado.")

    # 3) Editar máquina
    if can_edit(u,"nr12_manutencao"):
        opts=machine_options(db,ids)
        if opts:
            with st.expander("Editar máquina"):
                lab=st.selectbox("Máquina",list(opts),key="nr12_editar_maquina_select")
                m=db.get(MaquinaNR12,opts[lab])
                with st.form("editmaq"):
                    status_atual=normalizar_status_nr12(m.status_nr12)
                    novo_status=st.selectbox("Status",STATUS_MAQUINA,index=STATUS_MAQUINA.index(status_atual))
                    nova_criticidade=st.selectbox("Criticidade",CRITICIDADES,index=CRITICIDADES.index(m.criticidade) if m.criticidade in CRITICIDADES else 1)
                    risco_atual=m.risco_maquina or "Apreciação de risco não realizada"
                    novo_risco=st.selectbox("Risco da máquina",RISCOS_MAQUINA,index=RISCOS_MAQUINA.index(risco_atual) if risco_atual in RISCOS_MAQUINA else 0)
                    nova_proxima_auditoria=st.date_input("Próxima auditoria prevista",value=m.proxima_auditoria or date.today()+timedelta(days=180))
                    nova_data_prevista=None
                    if novo_status!="Conforme":
                        nova_data_prevista=st.date_input("Data prevista para adequação",value=m.data_prevista_adequacao or date.today()+timedelta(days=90),help="Use esta data para compor a meta e a evolução esperada de adequação.")
                    else:
                        st.caption("Máquina conforme: data prevista para adequação será limpa ao salvar.")
                    novas_observacoes=st.text_area("Observações",m.observacoes or "")
                    if st.form_submit_button("Atualizar",use_container_width=True):
                        m.status_nr12=novo_status
                        m.criticidade=nova_criticidade
                        m.risco_maquina=novo_risco
                        m.proxima_auditoria=nova_proxima_auditoria
                        m.data_prevista_adequacao=None if novo_status=="Conforme" else nova_data_prevista
                        m.observacoes=novas_observacoes
                        db.commit()
                        st.success("Atualizado.")
                        st.rerun()

def nr12_documentos(db,u):
    header("Documentos NR-12","Controle de documentos essenciais, validade, evidências e anexos")
    ids=visible_site_ids(u,db)
    opts=machine_options(db,ids)

    # 1) Consulta
    section("Consulta")
    df=df_docs(db,ids)
    if not df.empty:
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        empty_state("Nenhum documento.")
    download_excel_button("Exportar documentos Excel","documentos_nr12.xlsx",{"Documentos":df})

    # 2) Arquivos anexados por máquina
    section("Arquivos anexados")
    if not opts:
        empty_state("Cadastre uma máquina antes de consultar arquivos anexados.")
    else:
        lab_arq=st.selectbox("Selecionar máquina",list(opts),key="docs_nr12_maquina_arquivos")
        maquina_id=opts[lab_arq]
        docs=db.query(DocumentoNR12).filter(DocumentoNR12.maquina_id==maquina_id,DocumentoNR12.site_id.in_(ids)).order_by(DocumentoNR12.id.desc()).all()
        docs_com_arquivo=[d for d in docs if d.arquivo_nome]
        if not docs_com_arquivo:
            empty_state("Nenhum arquivo anexado para a máquina selecionada.")
        else:
            for d in docs_com_arquivo:
                c1,c2,c3,c4=st.columns([1.4,1.4,2.2,1])
                c1.markdown(f"**{d.tipo}**")
                c2.write(calcular_status_documento(d))
                c3.write(d.arquivo_nome)
                arquivo_data=d.arquivo_bytes
                if not arquivo_data and d.arquivo_caminho and os.path.exists(d.arquivo_caminho):
                    try:
                        with open(d.arquivo_caminho,"rb") as f:
                            arquivo_data=f.read()
                    except Exception:
                        arquivo_data=None
                if arquivo_data:
                    c4.download_button("Baixar",data=arquivo_data,file_name=d.arquivo_nome,mime="application/octet-stream",key=f"doc_download_{d.id}",use_container_width=True)
                else:
                    c4.caption("Arquivo registrado sem conteúdo salvo para download.")

    # 3) Cadastrar documento
    if can_edit(u,"nr12_manutencao") and opts:
        with st.expander("Cadastrar documento"):
            with st.form("doc"):
                lab=st.selectbox("Máquina",list(opts),key="docs_nr12_maquina_cadastro")
                tipo=st.selectbox("Tipo",TIPOS_DOC_NR12)
                emiss=st.date_input("Emissão",date.today())
                valid=st.date_input("Validade",date.today()+timedelta(days=365))
                resp=st.text_input("Responsável")
                up=st.file_uploader("Arquivo")
                desc=st.text_area("Descrição")
                if st.form_submit_button("Salvar",use_container_width=True):
                    m=db.get(MaquinaNR12,opts[lab])
                    fname=up.name if up else ""
                    fbytes=up.getvalue() if up else None
                    db.add(DocumentoNR12(maquina_id=m.id,site_id=m.site_id,tipo=tipo,descricao=desc,data_emissao=emiss,data_validade=valid,arquivo_nome=fname,arquivo_caminho=fname,arquivo_bytes=fbytes,responsavel=resp))
                    if tipo=="Laudo NR-12": m.possui_laudo=True
                    if tipo=="ART": m.possui_art=True
                    if tipo=="Apreciação de risco": m.possui_apreciacao_risco=True
                    db.commit()
                    st.success("Documento salvo.")
                    st.rerun()

def nr12_checklists(db,u):
    header("Checklists e Inspeções NR-12", "Registro por máquina, pontuação e geração automática de PAC")
    ids = visible_site_ids(u, db)
    opts = machine_options(db, ids)

    # 1) Verificações registradas
    df = df_ver(db, ids)
    section("Verificações registradas")
    if not df.empty:
        st.dataframe(df, use_container_width=True, hide_index=True)
        ids_disponiveis=df["ID"].astype(int).tolist()
        labels={int(row["ID"]): f'{int(row["ID"])} — {row["Máquina"]} — {row["Tipo"]} — {row["Data"]} — {row["Resultado"]}' for _, row in df.iterrows()}
        selecionadas=st.multiselect(
            "Selecionar checklists/verificações para baixar o resultado detalhado",
            ids_disponiveis,
            format_func=lambda x: labels.get(int(x), str(x)),
            key="nr12_verificacoes_download_select",
        )
        if selecionadas:
            resumo=df[df["ID"].astype(int).isin([int(x) for x in selecionadas])].copy()
            respostas=[]
            verificacoes=db.query(VerificacaoNR12).filter(VerificacaoNR12.id.in_([int(x) for x in selecionadas])).order_by(VerificacaoNR12.id.desc()).all()
            for v in verificacoes:
                for r in db.query(RespostaNR12).filter_by(verificacao_id=v.id).all():
                    respostas.append({
                        "Verificação ID":v.id,
                        "Site":site_code(db,v.site_id),
                        "Máquina":v.maquina.codigo if v.maquina else "—",
                        "Tipo de checklist":v.tipo,
                        "Data":fmt_date(v.data_verificacao),
                        "Responsável":v.responsavel,
                        "Ordem":r.item.ordem if r.item else "—",
                        "Pergunta":r.item.pergunta if r.item else "—",
                        "Item crítico":"Sim" if r.item and r.item.item_critico else "Não",
                        "Aplicável":"Sim" if r.aplicavel else "Não",
                        "Resultado":"Não aplicável" if not r.aplicavel else r.resultado,
                        "Comentário/evidência":r.comentario_evidencia,
                        "Gerou PAC":"Sim" if r.gerar_pac else "Não",
                    })
            download_excel_button(
                "Baixar resultado detalhado dos checklists selecionados",
                "resultado_checklists_nr12.xlsx",
                {"Resumo":resumo,"Respostas":pd.DataFrame(respostas)}
            )
    else:
        empty_state("Nenhuma verificação.")
    download_excel_button("Exportar verificações Excel", "verificacoes_nr12.xlsx", {"Verificações": df})

    # 2) Tipo de checklist e checklist
    section("Tipo de checklist")
    if not opts:
        empty_state("Cadastre uma máquina antes.")
        return
    if not can_edit(u, "nr12_operacao"):
        alert_card("Seu perfil permite consulta, mas não registro.")
        return

    tipo = st.selectbox("Tipo de checklist", TIPOS_VERIFICACAO_NR12, key="nr12_tipo_checklist_selector")
    itens = db.query(ChecklistItemNR12).filter_by(tipo_checklist=tipo, ativo=True).order_by(ChecklistItemNR12.ordem).all()
    section("Checklist")
    with st.form(f"ver_{tipo}"):
        lab = st.selectbox("Máquina", list(opts), key=f"maq_{tipo}")
        resp = st.text_input("Responsável", u.nome, key=f"resp_{tipo}")
        obs = st.text_area("Observações", key=f"obs_{tipo}")
        temp = []
        for it in itens:
            st.markdown(
                f"<div class='check-item'><div class='check-q'>{it.ordem}. {it.pergunta}"
                f"{'<span class=\"check-meta\">Crítico</span>' if it.item_critico else ''}</div></div>",
                unsafe_allow_html=True,
            )
            c1, c2, c3, c4 = st.columns([1, 1.3, 2.6, 1])
            apl = c1.checkbox("Aplicável", True, key=f"nr12_ap_{tipo}_{it.id}")
            res = c2.selectbox("Resultado", RESULTADOS_NR12, key=f"nr12_rr_{tipo}_{it.id}")
            com = c3.text_input("Comentário/evidência", key=f"nr12_co_{tipo}_{it.id}")
            gp = c4.checkbox("Gerar PAC", False, key=f"nr12_gp_{tipo}_{it.id}")
            temp.append((it, apl, res, com, gp))
        if st.form_submit_button("Salvar verificação", use_container_width=True):
            m = db.get(MaquinaNR12, opts[lab])
            v = VerificacaoNR12(
                maquina_id=m.id,
                site_id=m.site_id,
                tipo=tipo,
                data_verificacao=date.today(),
                responsavel=resp,
                observacoes=obs,
                proxima_verificacao=date.today() + timedelta(days=180),
            )
            db.add(v)
            db.flush()
            rs = []
            for it, apl, res, com, gp in temp:
                r = RespostaNR12(
                    verificacao_id=v.id,
                    item_id=it.id,
                    aplicavel=apl,
                    resultado="Não aplicável" if not apl else res,
                    comentario_evidencia=com,
                    gerar_pac=gp,
                )
                db.add(r)
                rs.append(r)
            db.flush()
            v.resultado, v.pontuacao, v.possui_nc_critica = calcular_resultado_verificacao_nr12(rs)
            m.ultima_auditoria = date.today()
            m.proxima_auditoria = v.proxima_verificacao
            m.status_nr12 = v.resultado if v.resultado in STATUS_MAQUINA else normalizar_status_nr12(m.status_nr12)
            for r in rs:
                if r.resultado == "Não conforme" or r.gerar_pac:
                    gerar_pac_automatico_nr12(db, v, r, resp)
            db.commit()
            st.success(f"Verificação salva: {v.resultado} | {v.pontuacao}%")
            st.rerun()

def nr12_pac(db,u):
    header("PAC NR-12","Planos de ação corretiva")
    ids=visible_site_ids(u,db)
    sites={s.codigo:s.id for s in db.query(Site).filter(Site.id.in_(ids))}
    opts=machine_options(db,ids)

    # 1) Consulta
    df=df_pac_nr12(db,ids)
    section("Consulta")
    if not df.empty:
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        empty_state("Nenhum PAC.")
    download_excel_button("Exportar PAC NR-12 Excel","pac_nr12.xlsx",{"PAC":df})

    # 2) Cadastrar PAC manual
    if can_edit(u,"nr12_manutencao") and sites:
        with st.expander("Cadastrar PAC manual"):
            with st.form("pacn"):
                site=st.selectbox("Site",list(sites))
                maq=st.selectbox("Máquina",["—"]+list(opts))
                clas=st.selectbox("Classificação",CLASSIFICACAO_PAC)
                stat=st.selectbox("Status",STATUS_PAC)
                prazo=st.date_input("Prazo",date.today()+timedelta(days=30))
                resp=st.text_input("Responsável")
                area=st.text_input("Área")
                desc=st.text_area("Descrição do desvio")
                if st.form_submit_button("Salvar",use_container_width=True):
                    db.add(PACNR12(origem="Manual",site_id=sites[site],maquina_id=None if maq=="—" else opts[maq],classificacao=clas,status=stat,prazo=prazo,responsavel=resp,area_responsavel=area,descricao_desvio=desc))
                    db.commit()
                    st.success("PAC salvo.")
                    st.rerun()

    # 3) Atualizar PAC
    if can_edit(u,"nr12_manutencao") and not df.empty:
        with st.expander("Atualizar PAC"):
            pac_id=int(st.selectbox("Selecionar PAC",df["ID"].astype(int).tolist(),key="nr12_pac_update_select"))
            p=db.get(PACNR12,pac_id)
            with st.form("editpacn"):
                p.status=st.selectbox("Status",STATUS_PAC,index=STATUS_PAC.index(p.status) if p.status in STATUS_PAC else 0)
                p.evidencia_conclusao=st.text_area("Evidência de conclusão",p.evidencia_conclusao or "")
                p.validacao_ehs=st.checkbox("Validação EHS",p.validacao_ehs)
                p.verificacao_eficacia=st.text_area("Verificação de eficácia",p.verificacao_eficacia or "")
                if st.form_submit_button("Atualizar",use_container_width=True):
                    if p.status=="Concluída" and not p.evidencia_conclusao:
                        st.error("PAC concluído exige evidência.")
                    elif p.status=="Concluída" and p.classificacao=="Crítico" and not p.validacao_ehs:
                        st.error("PAC crítico concluído exige validação EHS.")
                    else:
                        if p.status=="Concluída" and not p.data_conclusao:
                            p.data_conclusao=date.today()
                        db.commit()
                        st.success("Atualizado.")
                        st.rerun()
def prioridade_auditoria_nr12(db,m):
    risco = m.risco_maquina or ("Desprezível" if m.possui_apreciacao_risco else "Apreciação de risco não realizada")
    risco_peso={"Apreciação de risco não realizada":6,"Extremo":5,"Alto":4,"Significativo":3,"Atenção":2,"Desprezível":1}.get(risco,1)
    status=calcular_status_maquina_nr12(db,m)
    status_peso={"Não conforme":5,"Conforme":0}.get(status,0)
    if not m.proxima_auditoria:
        prazo_peso=80; dias=None; prazo_txt="Sem data"
    else:
        dias=(m.proxima_auditoria-date.today()).days
        if dias < 0: prazo_peso=100; prazo_txt="Vencida"
        elif dias <= 30: prazo_peso=70; prazo_txt="Até 30 dias"
        elif dias <= 60: prazo_peso=45; prazo_txt="Até 60 dias"
        elif dias <= 90: prazo_peso=20; prazo_txt="Até 90 dias"
        else: prazo_peso=0; prazo_txt="Planejada"
    score=prazo_peso + risco_peso*10 + status_peso*8
    if score >= 130: prioridade="Crítica"
    elif score >= 95: prioridade="Alta"
    elif score >= 60: prioridade="Média"
    else: prioridade="Baixa"
    return score, prioridade, prazo_txt, dias, risco

def nr12_central_pendencias(db,u):
    header("Central de Pendências NR-12","Próximas auditorias ordenadas por prioridade")
    ids=visible_site_ids(u,db)
    ms=db.query(MaquinaNR12).filter(MaquinaNR12.site_id.in_(ids)).all()
    rows=[]
    for m in ms:
        score, prioridade, prazo_txt, dias, risco = prioridade_auditoria_nr12(db,m)
        rows.append({
            "Prioridade":prioridade,
            "Score":score,
            "Site":site_code(db,m.site_id),
            "Código":m.codigo,
            "Máquina":m.nome,
            "Área":m.area_setor,
            "Risco":risco,
            "Criticidade":m.criticidade,
            "Status NR-12":calcular_status_maquina_nr12(db,m),
            "Próxima auditoria":fmt_date(m.proxima_auditoria),
            "Dias para vencer":dias if dias is not None else "—",
            "Situação do prazo":prazo_txt,
        })
    df=pd.DataFrame(rows).sort_values(["Score","Risco"],ascending=[False,True]) if rows else pd.DataFrame()
    if df.empty:
        empty_state("Nenhuma máquina cadastrada.")
        return
    f1,f2,f3=st.columns(3)
    unidade=f1.multiselect("Filtrar unidade",sorted(df["Site"].unique()))
    risco=f2.multiselect("Filtrar risco",[r for r in RISCOS_MAQUINA if r in set(df["Risco"].dropna())])
    prioridade=f3.multiselect("Filtrar prioridade",[p for p in ["Crítica","Alta","Média","Baixa"] if p in set(df["Prioridade"].dropna())])
    if unidade: df=df[df["Site"].isin(unidade)]
    if risco: df=df[df["Risco"].isin(risco)]
    if prioridade: df=df[df["Prioridade"].isin(prioridade)]
    st.dataframe(df.drop(columns=["Score"]),use_container_width=True,hide_index=True)
    download_excel_button("Exportar central de pendências", "central_pendencias_nr12.xlsx", {"Pendências": df.drop(columns=["Score"])})

def nr12_moc(db,u):
    header("Gestão de Mudanças / MOC NR-12","Mudanças críticas, aprovações e validação")
    ids=visible_site_ids(u,db); sites={s.codigo:s.id for s in db.query(Site).filter(Site.id.in_(ids))}; opts=machine_options(db,ids)
    if can_edit(u,"moc"):
        with st.form("moc"):
            c1,c2,c3=st.columns(3)
            site=c1.selectbox("Site",list(sites)); maq=c1.selectbox("Máquina",["—"]+list(opts)); tipo=c1.selectbox("Tipo de mudança",TIPOS_MUDANCA)
            solic=c2.text_input("Solicitante",u.nome); area=c2.text_input("Área solicitante"); status=c2.selectbox("Status",STATUS_MOC)
            imp=c3.checkbox("Impacta segurança?",tipo in TIPOS_MUDANCA_CRITICA); exige=c3.checkbox("Exige MOC?",tipo in TIPOS_MUDANCA_CRITICA or imp); val=c3.checkbox("Validação final")
            ehs=st.checkbox("Aprovação EHS"); man=st.checkbox("Aprovação Manutenção"); eng=st.checkbox("Aprovação Engenharia"); prod=st.checkbox("Aprovação Produção"); aud=st.checkbox("Necessita auditoria pós-mudança?"); tre=st.checkbox("Necessita treinamento?")
            desc=st.text_area("Descrição"); obs=st.text_area("Observações")
            if st.form_submit_button("Salvar MOC",use_container_width=True):
                crit=tipo in TIPOS_MUDANCA_CRITICA or imp
                if crit and (not exige or (status in ["Aprovada","Implementada","Validada"] and (not ehs or not (man or eng)))): st.error("Mudança crítica exige MOC, aprovação EHS e aprovação de Manutenção ou Engenharia.")
                else:
                    mid=None if maq=="—" else opts[maq]; db.add(MOCNR12(site_id=sites[site],maquina_id=mid,tipo_mudanca=tipo,descricao=desc,solicitante=solic,area_solicitante=area,data=date.today(),impacta_seguranca=imp,exige_moc=exige,status=status,aprovacao_ehs=ehs,aprovacao_manutencao=man,aprovacao_engenharia=eng,aprovacao_producao=prod,necessita_auditoria_pos_mudanca=aud,necessita_treinamento=tre,observacoes=obs,validacao_final=val))
                    if mid and crit and status=="Implementada" and not val: db.get(MaquinaNR12,mid).status_nr12="Não conforme"
                    db.commit(); st.success("MOC salva."); st.rerun()
    df = df_moc(db, ids)
    section("MOCs registradas")
    if not df.empty:
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        empty_state("Nenhuma MOC.")
    download_excel_button("Exportar MOC Excel", "moc_nr12.xlsx", {"MOC": df})
def nr12_termo(db,u):
    header("Termo de Garantia NR-12","Emissão anual por site")
    ids=visible_site_ids(u,db); sites={s.codigo:s.id for s in db.query(Site).filter(Site.id.in_(ids))}
    with st.form("termo"):
        site=st.selectbox("Site",list(sites)); ano=st.number_input("Ano/ciclo",2020,2100,date.today().year); ehs=st.text_input("Responsável EHS"); man=st.text_input("Responsável Manutenção"); prod=st.text_input("Responsável Produção/Operação"); eng=st.text_input("Responsável Engenharia"); lid=st.text_input("Liderança do site"); res=st.text_area("Ressalvas"); pend=st.text_area("Pendências"); dec=st.text_area("Declaração formal","Declaramos que o site acompanha a sustentação da conformidade NR-12 das máquinas já adequadas, mantendo inventário, controles documentais, inspeções, PAC e MOC.")
        if st.form_submit_button("Gerar termo",use_container_width=True):
            sid=sites[site]; ms=db.query(MaquinaNR12).filter_by(site_id=sid).all(); sts=[calcular_status_maquina_nr12(db,m) for m in ms]
            resumo=pd.DataFrame([{"Indicador":"Total de máquinas","Valor":len(ms)},{"Indicador":"Conformes","Valor":sts.count("Conforme")},{"Indicador":"Não conformes","Valor":sts.count("Não conforme")},{"Indicador":"PACs críticos abertos/vencidos","Valor":db.query(PACNR12).filter(PACNR12.site_id==sid,PACNR12.classificacao=="Crítico",PACNR12.status.in_(["Aberta","Em andamento","Vencida"])).count()},{"Indicador":"MOCs críticas sem validação","Valor":db.query(MOCNR12).filter(MOCNR12.site_id==sid,MOCNR12.exige_moc==True,MOCNR12.validacao_final==False).count()}])
            if can_edit(u,"nr12_manutencao"): db.add(TermoGarantiaNR12(site_id=sid,ano_ciclo=ano,responsavel_ehs=ehs,responsavel_manutencao=man,responsavel_producao=prod,responsavel_engenharia=eng,lideranca_site=lid,ressalvas=res,pendencias=pend,declaracao_formal=dec)); db.commit()
            pdf=gerar_pdf(f"Termo de Garantia de Sustentação NR-12 — {site}",f"Ano/ciclo: {ano} | Emissão: {fmt_date(date.today())}",[("Declaração",dec),("Responsáveis",pd.DataFrame([{"Função":"EHS","Responsável":ehs},{"Função":"Manutenção","Responsável":man},{"Função":"Produção/Operação","Responsável":prod},{"Função":"Engenharia","Responsável":eng},{"Função":"Liderança","Responsável":lid}])),("Consolidação",resumo),("Ressalvas",res or "Sem ressalvas."),("Pendências",pend or "Sem pendências.")])
            download_pdf_button("Baixar termo NR-12 PDF",f"termo_nr12_{site}_{ano}.pdf",pdf)
def nr12_relatorios(db,u):
    header("Relatórios NR-12","Exportações em Excel e PDFs")
    ids=visible_site_ids(u,db)
    d={"Inventário":df_maquinas(db,ids),"Documentos":df_docs(db,ids),"Verificações":df_ver(db,ids),"PAC":df_pac_nr12(db,ids)}
    cols=st.columns(4)
    for (name,df),c in zip(d.items(),cols):
        with c: download_excel_button(f"{name} Excel",f"{name.lower()}_nr12.xlsx",{name:df})
    download_excel_button("Pacote NR-12 Excel","pacote_nr12.xlsx",d)
    opts=machine_options(db,ids)
    if opts:
        lab=st.selectbox("Relatório PDF por máquina",list(opts)); m=db.get(MaquinaNR12,opts[lab])
        dados=df_maquinas(db,[m.site_id]); dados=dados[dados["ID"]==m.id]
        docs=df_docs(db,[m.site_id]); docs=docs[docs["ID"].isin([d.id for d in db.query(DocumentoNR12).filter_by(maquina_id=m.id).all()])] if not docs.empty else docs
        pacs=df_pac_nr12(db,[m.site_id]); pacs=pacs[pacs["Máquina"]==m.codigo] if not pacs.empty else pacs
        vers=pd.DataFrame([{"ID":v.id,"Tipo":v.tipo,"Data":fmt_date(v.data_verificacao),"Responsável":v.responsavel,"Resultado":v.resultado,"Pontuação %":v.pontuacao,"NC crítica":"Sim" if v.possui_nc_critica else "Não","Próxima":fmt_date(v.proxima_verificacao),"Observações":v.observacoes} for v in db.query(VerificacaoNR12).filter_by(maquina_id=m.id).order_by(VerificacaoNR12.data_verificacao.desc())])
        pdf=gerar_pdf(f"Relatório por Máquina — {m.codigo}",f"{m.nome} | Site {site_code(db,m.site_id)}",[("Dados",dados),("Auditorias e verificações realizadas",vers),("Documentos",docs),("PACs",pacs)])
        download_pdf_button("Baixar relatório por máquina PDF",f"relatorio_maquina_{m.codigo}.pdf",pdf)

# ============================================================
# 14. Páginas Auditoria Cruzada
# ============================================================
def gerar_checklist_automatico_ehs(db,auditoria_id,commit=True):
    for r in db.query(RequisitoEHS).join(DiretivaEHS).filter(RequisitoEHS.ativo==True,DiretivaEHS.ativo==True):
        if not db.query(RespostaAuditoriaEHS).filter_by(auditoria_id=auditoria_id,requisito_id=r.id).first():
            db.add(RespostaAuditoriaEHS(auditoria_id=auditoria_id,requisito_id=r.id,aplicavel=True,status="Conforme",nota_maturidade=3))
    if commit: db.commit()

def ehs_dashboard(db,u):
    header("Auditoria Cruzada de Diretrizes de EHS","Dashboard de planejamento, conformidade, maturidade e PAC")
    ids=visible_site_ids(u,db)
    da=df_aud(db,ids)
    dp=df_pac_ehs(db,ids)
    vals=[
        (da["Status"]=="Planejada").sum() if not da.empty else 0,
        (da["Status"]=="Em andamento").sum() if not da.empty else 0,
        (da["Status"]=="Concluída").sum() if not da.empty else 0,
        round(da["Conformidade %"].mean(),1) if not da.empty else 0,
        round(da["Maturidade"].mean(),2) if not da.empty else 0,
        (dp["Status"].isin(["Aberta","Em andamento","Aguardando validação"])).sum() if not dp.empty else 0,
        (dp["Status"]=="Vencida").sum() if not dp.empty else 0,
        (dp["Tipo de achado"]=="Não conformidade crítica").sum() if not dp.empty else 0
    ]
    labs=["Auditorias planejadas","Em andamento","Concluídas","Conformidade média","Maturidade média","PACs abertos","PACs vencidos","NC críticas"]
    for chunk in [range(4),range(4,8)]:
        cols=st.columns(4)
        for c,i in zip(cols,chunk):
            with c:
                kpi_card(labs[i],f"{vals[i]}%" if i==3 else vals[i])

    section("Principais gaps")
    if not dp.empty:
        gaps=dp.copy()
        ordem_status={"Vencida":0,"Aberta":1,"Em andamento":2,"Aguardando validação":3,"Concluída":4,"Cancelada":5}
        ordem_tipo={"Não conformidade crítica":0,"Não conformidade maior":1,"Não conformidade menor":2,"Observação":3,"Oportunidade de melhoria":4,"Boa prática":5}
        gaps["_ordem_status"]=gaps["Status"].map(ordem_status).fillna(9)
        gaps["_ordem_tipo"]=gaps["Tipo de achado"].map(ordem_tipo).fillna(9)
        gaps=gaps.sort_values(["_ordem_status","_ordem_tipo","Site"]).drop(columns=["_ordem_status","_ordem_tipo"])
        st.dataframe(gaps.head(20), use_container_width=True, hide_index=True)
    else:
        empty_state("Nenhum gap registrado.")

    section("Gráficos")
    c1,c2=st.columns(2)
    with c1:
        auditorias=db.query(AuditoriaCruzada).filter(AuditoriaCruzada.site_auditado_id.in_(ids)).all()
        ultimas_por_site={}
        def chave_auditoria(a):
            return (a.data_fim or a.data_inicio or a.data_planejada or date.min, a.id or 0)
        for a in auditorias:
            atual=ultimas_por_site.get(a.site_auditado_id)
            if atual is None or chave_auditoria(a)>chave_auditoria(atual):
                ultimas_por_site[a.site_auditado_id]=a
        rows=[]
        for a in ultimas_por_site.values():
            res=db.query(RespostaAuditoriaEHS).filter_by(auditoria_id=a.id).all()
            rows.append({
                "Auditoria":a.id,
                "Site auditado":site_code(db,a.site_auditado_id),
                "Data de referência":fmt_date(a.data_fim or a.data_inicio or a.data_planejada),
                "Status":a.status,
                "Conformidade %":calcular_conformidade_ehs(res),
                "Maturidade":calcular_maturidade_ehs(res),
            })
        latest_df=pd.DataFrame(rows)
        if not latest_df.empty:
            st.plotly_chart(
                px.bar(latest_df, x="Site auditado", y="Conformidade %", color="Conformidade %",
                       hover_data=["Auditoria","Data de referência","Status","Maturidade"],
                       title="Conformidade por site — última auditoria registrada").update_layout(template="plotly_white", yaxis_range=[0,100]),
                use_container_width=True
            )
        else:
            empty_state("Sem auditorias.")
    with c2:
        if not dp.empty:
            st.plotly_chart(px.histogram(dp, x="Status", color="Prioridade", barmode="group", title="PAC por status").update_layout(template="plotly_white"), use_container_width=True)
        else:
            empty_state("Sem PACs.")

def ehs_planejamento(db,u):
    header("Planejamento de Auditorias","Cadastro de ciclos e geração automática do checklist")
    ids=visible_site_ids(u,db)
    sv={s.codigo:s.id for s in db.query(Site).filter(Site.id.in_(ids))}
    sall={s.codigo:s.id for s in db.query(Site).filter(Site.codigo!="Corporativo")}

    section("Auditorias cadastradas")
    da = df_aud(db, ids)
    if not da.empty:
        st.dataframe(da, use_container_width=True, hide_index=True)
    else:
        empty_state("Nenhuma auditoria.")
    download_excel_button("Exportar auditorias Excel", "auditorias_cruzadas.xlsx", {"Auditorias": da})

    if can_edit(u,"auditoria") and sv:
        with st.expander("Cadastrar próxima auditoria"):
            with st.form("aud"):
                ano=st.number_input("Ano",2020,2100,date.today().year)
                ciclo=st.text_input("Ciclo","Ciclo 1")
                site=st.selectbox("Site auditado",list(sv))
                lider=st.selectbox("Site auditor líder",["—"]+list(sall))
                apoio=st.selectbox("Site auditor apoio",["—"]+list(sall))
                aud_l=st.text_input("Auditor líder",u.nome)
                aud_a=st.text_input("Auditor apoio")
                data=st.date_input("Data planejada",date.today()+timedelta(days=30))
                status=st.selectbox("Status",STATUS_AUDITORIA)
                esc=st.text_area("Escopo")
                obs=st.text_area("Observações")
                if st.form_submit_button("Criar auditoria e checklist",use_container_width=True):
                    a=AuditoriaCruzada(ano=ano,ciclo=ciclo,site_auditado_id=sv[site],site_auditor_lider_id=None if lider=="—" else sall[lider],site_auditor_apoio_id=None if apoio=="—" else sall[apoio],auditor_lider=aud_l,auditor_apoio=aud_a,data_planejada=data,status=status,escopo=esc,observacoes=obs)
                    db.add(a)
                    db.flush()
                    gerar_checklist_automatico_ehs(db,a.id,False)
                    db.commit()
                    st.success("Auditoria criada.")
                    st.rerun()

def ehs_checklist(db,u):
    header("Checklist Diretrizes de EHS", "Checklist incorporado, pontuação, maturidade e geração de PAC")
    msg=st.session_state.pop("ehs_checklist_saved_msg", None)
    if msg:
        st.success(msg)
    ids = visible_site_ids(u, db)
    auds = db.query(AuditoriaCruzada).filter(AuditoriaCruzada.site_auditado_id.in_(ids)).order_by(AuditoriaCruzada.id.desc()).all()
    if not auds:
        empty_state("Crie uma auditoria no planejamento.")
        return
    amap = {f"{a.id} — {site_code(db,a.site_auditado_id)} — {a.ciclo} — {a.status}": a.id for a in auds}
    a = db.get(AuditoriaCruzada, amap[st.selectbox("Auditoria", list(amap), key="auditoria_ehs_selector")])
    gerar_checklist_automatico_ehs(db, a.id)
    res = db.query(RespostaAuditoriaEHS).join(RequisitoEHS).join(DiretivaEHS).filter(
        RespostaAuditoriaEHS.auditoria_id == a.id
    ).order_by(DiretivaEHS.categoria, RequisitoEHS.ordem).all()
    c1, c2, c3 = st.columns(3)
    with c1:
        kpi_card("Conformidade", f"{calcular_conformidade_ehs(res)}%")
    with c2:
        kpi_card("Maturidade média", calcular_maturidade_ehs(res))
    with c3:
        kpi_card("Itens", len(res))
    pode_editar = can_edit(u, "auditoria")
    respostas_para_salvar = []
    if pode_editar:
        with st.form(f"form_checklist_ehs_{a.id}"):
            categoria_atual = None
            for r in res:
                categoria = r.requisito.diretiva.categoria
                if categoria != categoria_atual:
                    st.markdown(f"<div class='check-category'>{categoria}</div>", unsafe_allow_html=True)
                    categoria_atual = categoria
                st.markdown(
                    f"<div class='check-item'><div class='check-q'>{r.requisito.ordem}. {r.requisito.pergunta}"
                    f"<span class='check-meta'>{r.requisito.criticidade}</span></div>"
                    f"<div class='muted'>Evidência esperada: {r.requisito.evidencia_esperada or 'Verificar evidência aplicável.'}</div></div>",
                    unsafe_allow_html=True,
                )
                col1, col2, col3, col4, col5, col6 = st.columns([.85, 1.45, 1, 2.2, 2.2, .9])
                apl = col1.checkbox("Aplicável", value=bool(r.aplicavel), key=f"ehs_ap_{a.id}_{r.id}")
                status_atual = r.status if r.status in STATUS_RESPOSTA_EHS else "Conforme"
                status = col2.selectbox("Status", STATUS_RESPOSTA_EHS, index=STATUS_RESPOSTA_EHS.index(status_atual), key=f"ehs_status_{a.id}_{r.id}")
                maturidade = col3.number_input("Maturidade", min_value=0.0, max_value=5.0, value=float(r.nota_maturidade or 0), step=.5, key=f"ehs_mat_{a.id}_{r.id}")
                evidencia = col4.text_input("Evidência verificada", value=r.evidencia_verificada or "", key=f"ehs_evid_{a.id}_{r.id}")
                comentario = col5.text_input("Comentário do auditor", value=r.comentario_auditor or "", key=f"ehs_com_{a.id}_{r.id}")
                pac = col6.checkbox("PAC", value=bool(r.necessita_pac), key=f"ehs_pac_{a.id}_{r.id}")
                respostas_para_salvar.append((r.id, apl, status, maturidade, evidencia, comentario, pac))
            if st.form_submit_button("Salvar checklist e gerar PACs necessários", use_container_width=True):
                for rid, apl, status, maturidade, evidencia, comentario, pac in respostas_para_salvar:
                    r = db.get(RespostaAuditoriaEHS, int(rid))
                    r.aplicavel = bool(apl)
                    r.status = "Não Aplicável" if not apl else status
                    r.nota_maturidade = float(maturidade)
                    r.evidencia_verificada = evidencia
                    r.comentario_auditor = comentario
                    r.necessita_pac = bool(pac)
                db.flush()
                res_atual = db.query(RespostaAuditoriaEHS).filter_by(auditoria_id=a.id).all()
                a.conformidade_percentual = calcular_conformidade_ehs(res_atual)
                a.maturidade_media = calcular_maturidade_ehs(res_atual)
                for r in res_atual:
                    if r.necessita_pac or r.status in ["Não Conforme", "Parcialmente Conforme"]:
                        gerar_pac_automatico_ehs(db, a, r, a.auditor_lider)
                db.commit()
                st.session_state["ehs_checklist_saved_msg"]="Checklist salvo com sucesso. Os PACs necessários foram gerados ou atualizados."
                st.rerun()
    else:
        categoria_atual = None
        for r in res:
            categoria = r.requisito.diretiva.categoria
            if categoria != categoria_atual:
                st.markdown(f"<div class='check-category'>{categoria}</div>", unsafe_allow_html=True)
                categoria_atual = categoria
            status_txt = "Não Aplicável" if not r.aplicavel else r.status
            st.markdown(
                f"<div class='check-item'><div class='check-q'>{r.requisito.ordem}. {r.requisito.pergunta}"
                f"<span class='check-meta'>{r.requisito.criticidade}</span></div>"
                f"<div class='muted'>Status: <b>{status_txt}</b> | Maturidade: <b>{r.nota_maturidade}</b></div>"
                f"<div class='muted'>Evidência: {r.evidencia_verificada or '—'}</div>"
                f"<div class='muted'>Comentário: {r.comentario_auditor or '—'}</div></div>",
                unsafe_allow_html=True,
            )

def ehs_pac(db,u):
    header("PAC Auditoria Cruzada","Tratamento de achados e verificação de eficácia")
    ids=visible_site_ids(u,db)
    sites={s.codigo:s.id for s in db.query(Site).filter(Site.id.in_(ids))}

    if can_edit(u,"pac_ehs") and sites:
        with st.expander("Cadastrar PAC EHS manual"):
            with st.form("pace"):
                site=st.selectbox("Site",list(sites))
                tipo=st.selectbox("Tipo de achado",TIPOS_ACHADO_EHS)
                pr=st.selectbox("Prioridade/criticidade",["Alta","Média","Baixa"])
                stat=st.selectbox("Status",STATUS_PAC)
                prazo=st.date_input("Prazo",date.today()+timedelta(days=30))
                resp=st.text_input("Responsável")
                area=st.text_input("Área responsável")
                desc=st.text_area("Descrição")
                evid=st.text_area("Evidência")
                risco=st.text_area("Risco")
                causa=st.text_area("Causa raiz")
                aci=st.text_area("Ação imediata")
                acc=st.text_area("Ação corretiva")
                if st.form_submit_button("Salvar PAC EHS",use_container_width=True):
                    db.add(PACEHS(site_id=sites[site],tipo_achado=tipo,prioridade_criticidade=pr,status=stat,prazo=prazo,responsavel=resp,area_responsavel=area,descricao=desc,evidencia=evid,risco=risco,causa_raiz=causa,acao_imediata=aci,acao_corretiva=acc))
                    db.commit()
                    st.success("PAC salvo.")
                    st.rerun()

    df = df_pac_ehs(db, ids)
    if not df.empty:
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        empty_state("Nenhum PAC EHS.")
    download_excel_button("Exportar PAC EHS Excel", "pac_ehs.xlsx", {"PAC EHS": df})

    if can_edit(u,"pac_ehs") and not df.empty:
        with st.expander("Atualizar status das ações levantadas"):
            pac_id=int(st.selectbox("Selecionar ação/PAC",df["ID"].astype(int).tolist(),key="ehs_pac_update_select"))
            p=db.get(PACEHS,pac_id)
            with st.form("edit_pac_ehs_status"):
                novo_status=st.selectbox("Status",STATUS_PAC,index=STATUS_PAC.index(p.status) if p.status in STATUS_PAC else 0)
                evidencia=st.text_area("Evidência de conclusão",p.evidencia_conclusao or "")
                validacao=st.checkbox("Validação EHS",p.validacao_ehs)
                eficacia=st.text_area("Verificação de eficácia",p.verificacao_eficacia or "")
                status_eficacia=st.selectbox("Status da eficácia",["Não avaliada","Eficaz","Parcialmente eficaz","Ineficaz"],index=["Não avaliada","Eficaz","Parcialmente eficaz","Ineficaz"].index(p.status_eficacia) if p.status_eficacia in ["Não avaliada","Eficaz","Parcialmente eficaz","Ineficaz"] else 0)
                if st.form_submit_button("Atualizar status",use_container_width=True):
                    if novo_status=="Concluída" and not evidencia:
                        st.error("PAC concluído exige evidência de conclusão.")
                    else:
                        p.status=novo_status
                        p.evidencia_conclusao=evidencia
                        p.validacao_ehs=validacao
                        p.verificacao_eficacia=eficacia
                        p.status_eficacia=status_eficacia
                        if novo_status=="Concluída" and not p.data_conclusao:
                            p.data_conclusao=date.today()
                        db.commit()
                        st.success("Status atualizado.")
                        st.rerun()
def ehs_base_checklist(db,u):
    header("Base do Checklist EHS","Visualizar categorias, requisitos, criticidade e evidência esperada")
    reqs=db.query(RequisitoEHS).join(DiretivaEHS).order_by(DiretivaEHS.categoria,RequisitoEHS.ordem).all()
    df=pd.DataFrame([{"ID":r.id,"Categoria":r.diretiva.categoria,"Ordem":r.ordem,"Requisito":r.pergunta,"Ativo":r.ativo,"Criticidade":r.criticidade,"Evidência esperada":r.evidencia_esperada} for r in reqs])
    if can_edit(u,"auditoria"):
        ed=st.data_editor(df,use_container_width=True,hide_index=True,disabled=["ID","Categoria","Ordem","Requisito"],column_config={"Criticidade":st.column_config.SelectboxColumn("Criticidade",options=CRITICIDADES)})
        if st.button("Salvar ajustes",use_container_width=True):
            for _,row in ed.iterrows():
                r=db.get(RequisitoEHS,int(row["ID"])); r.ativo=bool(row["Ativo"]); r.criticidade=row["Criticidade"]; r.evidencia_esperada=row["Evidência esperada"]
            db.commit(); st.success("Base atualizada."); st.rerun()
    else: st.dataframe(df,use_container_width=True,hide_index=True)
def ehs_relatorios(db,u):
    header("Relatórios Auditoria Cruzada","Exportações em Excel e PDF")
    ids=visible_site_ids(u,db); da=df_aud(db,ids); dp=df_pac_ehs(db,ids)
    base=pd.DataFrame([{"Categoria":r.diretiva.categoria,"Ordem":r.ordem,"Requisito":r.pergunta,"Ativo":"Sim" if r.ativo else "Não","Criticidade":r.criticidade,"Evidência esperada":r.evidencia_esperada} for r in db.query(RequisitoEHS).join(DiretivaEHS).order_by(DiretivaEHS.categoria,RequisitoEHS.ordem)])
    download_excel_button("Checklist Excel","checklist_ehs.xlsx",{"Checklist":base}); download_excel_button("PAC EHS Excel","pac_ehs.xlsx",{"PAC":dp}); download_excel_button("Pacote Auditoria Excel","auditoria_cruzada_ehs.xlsx",{"Auditorias":da,"Checklist":base,"PAC":dp})
    auds=db.query(AuditoriaCruzada).filter(AuditoriaCruzada.site_auditado_id.in_(ids)).order_by(AuditoriaCruzada.id.desc()).all()
    if auds:
        amap={f"{a.id} — {site_code(db,a.site_auditado_id)} — {a.ciclo}":a.id for a in auds}; a=db.get(AuditoriaCruzada,amap[st.selectbox("Relatório PDF",list(amap))]); res=db.query(RespostaAuditoriaEHS).filter_by(auditoria_id=a.id).all()
        dfr=pd.DataFrame([{"Categoria":r.requisito.diretiva.categoria,"Requisito":r.requisito.pergunta,"Status":r.status,"Maturidade":r.nota_maturidade,"Evidência":r.evidencia_verificada,"Comentário":r.comentario_auditor} for r in res])
        pdf=gerar_pdf(f"Relatório de Auditoria Cruzada de Diretrizes de EHS — {site_code(db,a.site_auditado_id)}",f"Auditoria {a.id} | {a.ciclo} | Conformidade {calcular_conformidade_ehs(res)}% | Maturidade {calcular_maturidade_ehs(res)}",[("Dados",pd.DataFrame([{"Ano":a.ano,"Ciclo":a.ciclo,"Site":site_code(db,a.site_auditado_id),"Status":a.status,"Auditor líder":a.auditor_lider}])),("Resultado por item",dfr),("PACs vinculados",dp[dp["Auditoria"]==a.id] if not dp.empty else dp)])
        download_pdf_button("Baixar relatório de auditoria PDF",f"relatorio_auditoria_ehs_{a.id}.pdf",pdf)

# ============================================================
# 15. Roteamento principal
# ============================================================

def render_sidebar(db,u):
    mod=st.session_state.get("modulo","home")
    if mod=="home":
        return
    st.sidebar.markdown("### Navegação")
    if st.sidebar.button("🏠 Voltar para a tela inicial",use_container_width=True):
        st.session_state.modulo="home"
        st.rerun()
    st.sidebar.divider()
    if mod=="nr12":
        pages=["Dashboard NR-12","Central de Pendências","Inventário de Máquinas","Documentos NR-12","Checklists e Inspeções","PAC NR-12","Relatórios NR-12"]
        current=st.session_state.get("page_nr12",pages[0])
        if current not in pages:
            current=pages[0]
            st.session_state.page_nr12=current
        if st.session_state.get("nav_nr12") not in pages:
            st.session_state.nav_nr12=current
        selected=st.sidebar.radio("Sustentação NR-12",pages,key="nav_nr12")
        st.session_state.page_nr12=selected
    elif mod=="ehs":
        pages=["Dashboard Auditoria Cruzada","Planejamento de Auditorias","Checklist Diretrizes de EHS","PAC Auditoria Cruzada","Base do Checklist EHS","Relatórios Auditoria Cruzada"]
        current=st.session_state.get("page_ehs",pages[0])
        if current not in pages:
            current=pages[0]
            st.session_state.page_ehs=current
        if st.session_state.get("nav_ehs") not in pages:
            st.session_state.nav_ehs=current
        selected=st.sidebar.radio("Auditoria Cruzada de Diretrizes de EHS",pages,key="nav_ehs")
        st.session_state.page_ehs=selected
def route(db,u):
    mod=st.session_state.get("modulo","home")
    if mod=="home": home_page(db,u)
    elif mod=="nr12":
        {"Dashboard NR-12":nr12_dashboard,"Central de Pendências":nr12_central_pendencias,"Inventário de Máquinas":nr12_inventario,"Documentos NR-12":nr12_documentos,"Checklists e Inspeções":nr12_checklists,"PAC NR-12":nr12_pac,"Relatórios NR-12":nr12_relatorios}[st.session_state.get("page_nr12","Dashboard NR-12")](db,u)
    elif mod=="ehs":
        {"Dashboard Auditoria Cruzada":ehs_dashboard,"Planejamento de Auditorias":ehs_planejamento,"Checklist Diretrizes de EHS":ehs_checklist,"PAC Auditoria Cruzada":ehs_pac,"Base do Checklist EHS":ehs_base_checklist,"Relatórios Auditoria Cruzada":ehs_relatorios}[st.session_state.get("page_ehs","Dashboard Auditoria Cruzada")](db,u)


# ============================================================
# 15B. Melhorias corporativas — nomenclatura, governança, dashboards e dados
# ============================================================
def normalize_text_key(valor):
    if valor is None:
        return ""
    txt = str(valor).strip().upper()
    txt = re.sub(r"[,;._/\\-]+", " ", txt)
    txt = re.sub(r"\s+", " ", txt)
    return txt

def normalize_site_code(valor):
    if valor is None:
        return "—"
    raw = str(valor).strip()
    if raw in SITES_INFO:
        return raw
    key = normalize_text_key(raw)
    for alias, codigo in SITE_ALIASES.items():
        if alias in key:
            return codigo
    return raw

def site_nome_padrao(codigo):
    codigo = normalize_site_code(codigo)
    return SITES_INFO.get(codigo, {}).get("nome_padrao", codigo or "—")

def site_nome_curto(codigo):
    codigo = normalize_site_code(codigo)
    return SITES_INFO.get(codigo, {}).get("nome_curto", codigo or "—")

def site_grupo(codigo):
    codigo = normalize_site_code(codigo)
    return SITES_INFO.get(codigo, {}).get("grupo", "—")

def site_divisao(codigo):
    codigo = normalize_site_code(codigo)
    return SITES_INFO.get(codigo, {}).get("divisao", "—")

def site_label(codigo, formato="padrao"):
    codigo = normalize_site_code(codigo)
    if formato == "curto":
        return site_nome_curto(codigo)
    if formato == "codigo":
        return codigo
    if formato == "grupo":
        return f"{site_grupo(codigo)} | {site_nome_curto(codigo)}"
    return site_nome_padrao(codigo)

# Redefinição visual: todas as tabelas continuam usando código interno para permissão,
# mas a interface passa a exibir nomes padronizados.
def site_code(db, id):
    s = db.get(Site, id) if id else None
    return site_label(s.codigo) if s else "—"

def site_code_raw(db, id):
    s = db.get(Site, id) if id else None
    return s.codigo if s else "—"

def has_permission(usuario, modulo, acao):
    if not usuario:
        return False
    if usuario.perfil == "Admin_LAG":
        return True
    matriz = PERMISSION_MATRIX.get(usuario.perfil, {})
    if acao in matriz.get("*", set()):
        return True
    return acao in matriz.get(modulo, set())

def permission_guard(usuario, modulo, acao="visualizar"):
    if has_permission(usuario, modulo, acao):
        return True
    alert_card(f"Seu perfil não possui permissão para {acao} neste módulo.")
    return False

def can_edit(u, ctx="geral"):
    if not u or u.perfil == "Visualizador":
        return False
    if u.perfil == "Admin_LAG":
        return True
    contexto_modulo = {
        "auditoria": "auditoria_ehs",
        "pac_ehs": "pac_ehs",
        "nr12_operacao": "checklists_maquinas",
        "nr12_manutencao": "maquinas",
        "moc": "moc_maquinas",
        "geral": "maquinas",
    }.get(ctx, "maquinas")
    return has_permission(u, contexto_modulo, "editar") or has_permission(u, contexto_modulo, "criar")

def registrar_log(db, usuario, modulo, entidade, entidade_id, acao, campo=None, valor_anterior=None, valor_novo=None, observacao=None):
    try:
        db.add(LogSistema(
            usuario=getattr(usuario, "nome", None), perfil=getattr(usuario, "perfil", None),
            modulo=modulo, entidade=entidade, entidade_id=int(entidade_id) if entidade_id else None,
            acao=acao, campo=campo,
            valor_anterior=None if valor_anterior is None else str(valor_anterior),
            valor_novo=None if valor_novo is None else str(valor_novo),
            observacao=observacao,
        ))
    except Exception as e:
        logger.exception("Falha ao registrar log: %s", e)

def table_exists(table_name):
    try:
        return table_name in inspect(engine).get_table_names()
    except Exception as e:
        logger.exception("Erro ao inspecionar tabela %s", table_name)
        return False

def column_exists(table_name, column_name):
    try:
        if not table_exists(table_name):
            return False
        return column_name in {c["name"] for c in inspect(engine).get_columns(table_name)}
    except Exception as e:
        logger.exception("Erro ao inspecionar coluna %s.%s", table_name, column_name)
        return False

def safe_add_column(table_name, column_name, sql_definition):
    if not table_exists(table_name) or column_exists(table_name, column_name):
        return
    try:
        with engine.begin() as conn:
            conn.exec_driver_sql(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {sql_definition}")
        logger.info("Coluna adicionada: %s.%s", table_name, column_name)
    except Exception as e:
        logger.exception("Erro ao adicionar coluna %s.%s: %s", table_name, column_name, e)

def ensure_schema_updates():
    try:
        safe_add_column("maquinas_nr12", "risco_maquina", "VARCHAR(80) DEFAULT 'Apreciação de risco não realizada'")
        safe_add_column("maquinas_nr12", "data_prevista_adequacao", "DATE")
        safe_add_column("documentos_nr12", "arquivo_bytes", "BLOB")
        safe_add_column("verificacoes_nr12", "checklist_versao_id", "INTEGER")
        safe_add_column("respostas_nr12", "pergunta_snapshot", "TEXT")
        safe_add_column("respostas_nr12", "item_critico_snapshot", "BOOLEAN DEFAULT 0")
    except Exception as e:
        logger.exception("Falha geral na atualização de schema: %s", e)

def sync_checklist_versions(db):
    """Seed versionado dos checklists de máquinas, sem apagar histórico."""
    for tipo, itens in CHECKLIST_NR12.items():
        versao = db.query(ChecklistVersaoMaquinas).filter_by(tipo_checklist=tipo, versao=1).first()
        if not versao:
            versao = ChecklistVersaoMaquinas(tipo_checklist=tipo, versao=1, descricao="Versão inicial migrada do checklist padrão.", ativo=True, criado_por="Sistema")
            db.add(versao)
            db.flush()
        for i, (pergunta, critico) in enumerate(itens, 1):
            p = db.query(ChecklistPerguntaVersaoMaquinas).filter_by(checklist_versao_id=versao.id, ordem=i).first()
            if not p:
                db.add(ChecklistPerguntaVersaoMaquinas(checklist_versao_id=versao.id, ordem=i, pergunta=pergunta, item_critico=critico, ativo=True))

def sync_checklists_base(db):
    # Seed legado, preservado por compatibilidade com respostas históricas.
    for tipo, itens in CHECKLIST_NR12.items():
        for i, (pergunta, critico) in enumerate(itens, 1):
            item = db.query(ChecklistItemNR12).filter_by(tipo_checklist=tipo, ordem=i).first()
            if item:
                if not item.pergunta:
                    item.pergunta = pergunta
                item.item_critico = bool(item.item_critico or critico)
                item.ativo = True
            else:
                db.add(ChecklistItemNR12(tipo_checklist=tipo, ordem=i, pergunta=pergunta, item_critico=critico, ativo=True))
    sync_checklist_versions(db)
    for cat, pergs in CHECKLIST_EHS.items():
        d = db.query(DiretivaEHS).filter_by(categoria=cat).first()
        if not d:
            d = DiretivaEHS(categoria=cat, descricao=cat, ativo=True)
            db.add(d); db.flush()
        for i, p in enumerate(pergs, 1):
            req = db.query(RequisitoEHS).filter_by(diretiva_id=d.id, ordem=i).first()
            if req:
                req.pergunta = p
            else:
                db.add(RequisitoEHS(diretiva_id=d.id, ordem=i, pergunta=p, criticidade="Alta" if i in [1,3,7] else "Média", evidencia_esperada="Evidência documental, registros, entrevistas e/ou verificação em campo.", ativo=True))

def init_db():
    Base.metadata.create_all(engine)
    ensure_schema_updates()
    db = SessionLocal()
    try:
        corp = db.query(Site).filter_by(codigo="Corporativo").first()
        if not corp:
            db.add(Site(codigo="Corporativo", nome="Corporativo"))
        for s in SITES_PADRAO:
            site = db.query(Site).filter_by(codigo=s).first()
            if not site:
                db.add(Site(codigo=s, nome=site_nome_padrao(s)))
            else:
                site.nome = site_nome_padrao(s)
        db.flush()
        for nome, perfil, sitecod in USUARIOS_PADRAO:
            if not db.query(Usuario).filter_by(nome=nome).first():
                stt = db.query(Site).filter_by(codigo=sitecod).first()
                db.add(Usuario(nome=nome, perfil=perfil, site_id=stt.id if stt else None))
        sync_checklists_base(db)
        for maq in db.query(MaquinaNR12).all():
            maq.status_nr12 = normalizar_status_nr12(maq.status_nr12)
        db.commit()
        if db.query(MaquinaNR12).count() == 0:
            sjc = db.query(Site).filter_by(codigo="SJC").first()
            m = MaquinaNR12(codigo="SJC-PRENSA-001", site_id=sjc.id, area_setor="Produção", linha_processo="Linha 1", nome="Prensa hidráulica 001", fabricante="Fabricante A", modelo="PH-100", numero_serie="PH100", ano="2020", tipo_equipamento="Prensa", responsavel_area="Produção", criticidade="Alta", risco_maquina="Significativo", status_nr12="Não conforme", ultima_adequacao=date.today()-timedelta(days=180), ultima_auditoria=date.today()-timedelta(days=90), proxima_auditoria=date.today()+timedelta(days=40), data_prevista_adequacao=date.today()+timedelta(days=120), possui_laudo=True, possui_art=True, possui_apreciacao_risco=True, possui_manual_atualizado=True, possui_treinamento=True)
            db.add(m); db.flush()
            for t in DOCUMENTOS_ESSENCIAIS:
                db.add(DocumentoNR12(maquina_id=m.id, site_id=sjc.id, tipo=t, descricao=t, data_emissao=date.today()-timedelta(days=200), data_validade=date.today()+timedelta(days=365), arquivo_nome=t+".pdf", responsavel="EHS"))
            db.add(PACNR12(origem="Seed", site_id=sjc.id, maquina_id=m.id, descricao_desvio="Pendência menor em sinalização.", classificacao="Menor", responsavel="Manutenção SJC", area_responsavel="Manutenção", prazo=date.today()+timedelta(days=20), status="Em andamento"))
            db.commit()
        if db.query(AuditoriaCruzada).count() == 0:
            sjc = db.query(Site).filter_by(codigo="SJC").first(); dia = db.query(Site).filter_by(codigo="DIA").first()
            a = AuditoriaCruzada(ano=date.today().year, ciclo="Ciclo 1", site_auditado_id=sjc.id, site_auditor_lider_id=dia.id, auditor_lider="Auditor EHS", data_planejada=date.today()+timedelta(days=30), status="Planejada", escopo="Auditoria cruzada seed")
            db.add(a); db.flush(); gerar_checklist_automatico_ehs(db, a.id, False); db.commit()
    finally:
        db.close()

def pergunta_resposta_nr12(r):
    if getattr(r, "pergunta_snapshot", None):
        return r.pergunta_snapshot
    return r.item.pergunta if getattr(r, "item", None) else "—"

def item_critico_resposta_nr12(r):
    if getattr(r, "pergunta_snapshot", None) is not None:
        return bool(getattr(r, "item_critico_snapshot", False))
    return bool(r.item and r.item.item_critico)

def calcular_resultado_verificacao_nr12(resps):
    ap = [r for r in resps if r.aplicavel and r.resultado != "Não aplicável"]
    if not ap:
        return "Não conforme", 0, False
    pct = round(sum(1 for r in ap if r.resultado == "Conforme") / len(ap) * 100, 1)
    crit = any(r.resultado == "Não conforme" and item_critico_resposta_nr12(r) for r in ap)
    if crit or pct < 90:
        return "Não conforme", pct, crit
    return "Conforme", pct, False

def gerar_pac_automatico_nr12(db, ver, r, resp=""):
    pergunta = pergunta_resposta_nr12(r)
    if db.query(PACNR12).filter_by(verificacao_id=ver.id, item_checklist=pergunta).first():
        return
    clas = "Crítico" if item_critico_resposta_nr12(r) else "Maior"
    db.add(PACNR12(origem=ver.tipo, site_id=ver.site_id, maquina_id=ver.maquina_id, verificacao_id=ver.id, item_checklist=pergunta, descricao_desvio=r.comentario_evidencia or pergunta, classificacao=clas, responsavel=resp, area_responsavel="A definir", prazo=date.today()+timedelta(days=15 if clas=="Crítico" else 30), status="Aberta"))

def explicar_status_maquina(db, maquina):
    motivos, bloqueios, docs_pendentes, pacs_criticos = [], [], [], []
    if not maquina:
        return {"status_calculado":"Não conforme", "motivos":["Máquina não encontrada"], "bloqueios_criticos":[], "documentos_pendentes":[], "pacs_criticos_abertos":[], "recomendacao":"Verificar cadastro."}
    docs = {d.tipo: d for d in db.query(DocumentoNR12).filter_by(maquina_id=maquina.id).all()}
    for t in DOCUMENTOS_ESSENCIAIS:
        d = docs.get(t)
        st_doc = calcular_status_documento(d) if d else "Ausente"
        if st_doc in ["Ausente", "Vencido"]:
            texto = f"{t} {'ausente' if st_doc == 'Ausente' else 'vencido'}"
            motivos.append(texto); docs_pendentes.append(texto)
            if t in ["Laudo NR-12", "ART", "Apreciação de risco"]:
                bloqueios.append(texto)
    pacs = db.query(PACNR12).filter(PACNR12.maquina_id==maquina.id, PACNR12.classificacao=="Crítico", PACNR12.status.in_(["Aberta","Em andamento","Aguardando validação","Vencida"])).all()
    for p in pacs:
        txt = f"PAC crítico aberto/vencido #{p.id}: {(p.descricao_desvio or '')[:80]}"
        motivos.append(txt); bloqueios.append(txt); pacs_criticos.append(txt)
    if normalizar_status_nr12(maquina.status_nr12) == "Não conforme":
        motivos.append("Máquina não conforme declarada no inventário")
    if maquina.proxima_auditoria and maquina.proxima_auditoria < date.today():
        motivos.append("Próxima auditoria/verificação vencida")
    if normalizar_status_nr12(maquina.status_nr12) != "Conforme" and not as_date(getattr(maquina, "data_prevista_adequacao", None)):
        motivos.append("Máquina não conforme sem data prevista de adequação")
    moc_aberta = db.query(MOCNR12).filter(MOCNR12.maquina_id==maquina.id, MOCNR12.exige_moc==True, MOCNR12.status.in_(["Implementada","Aprovada"]), MOCNR12.validacao_final==False).first()
    if moc_aberta:
        motivos.append("MOC crítica implementada/aprovada sem validação final"); bloqueios.append("MOC crítica sem validação final")
    status = "Não conforme" if motivos else "Conforme"
    recomendacao = "Tratar pendências críticas, atualizar documentos e validar proteções antes da liberação." if status == "Não conforme" else "Manter rotina de inspeções, documentos e MOC."
    return {"status_calculado": status, "motivos": motivos or ["Sem pendências críticas identificadas"], "bloqueios_criticos": bloqueios, "documentos_pendentes": docs_pendentes, "pacs_criticos_abertos": pacs_criticos, "recomendacao": recomendacao}

def calcular_status_maquina_nr12(db, m):
    return explicar_status_maquina(db, m)["status_calculado"] if m else "Não conforme"

def df_maquinas(db, ids):
    rows = []
    for m in db.query(MaquinaNR12).filter(MaquinaNR12.site_id.in_(ids)).order_by(MaquinaNR12.codigo):
        exp = explicar_status_maquina(db, m)
        risco = m.risco_maquina or ("Desprezível" if m.possui_apreciacao_risco else "Apreciação de risco não realizada")
        codigo = site_code_raw(db, m.site_id)
        rows.append({"ID":m.id,"Código":m.codigo,"Site":site_label(codigo),"Código site":codigo,"Grupo":site_grupo(codigo),"Divisão":site_divisao(codigo),"Área":m.area_setor,"Linha":m.linha_processo,"Máquina":m.nome,"Fabricante":m.fabricante,"Modelo":m.modelo,"Série":m.numero_serie,"Ano":m.ano,"Tipo":m.tipo_equipamento,"Responsável":m.responsavel_area,"Criticidade":m.criticidade,"Risco":risco,NOME_STATUS_PROTECAO:exp["status_calculado"],"Motivo da não conformidade":"; ".join(exp["motivos"]) if exp["status_calculado"] != "Conforme" else "—","Data prevista adequação":fmt_date(getattr(m,"data_prevista_adequacao",None)),"Próxima auditoria":fmt_date(m.proxima_auditoria),"Laudo":"Sim" if m.possui_laudo else "Não","ART":"Sim" if m.possui_art else "Não","Apreciação":"Sim" if m.possui_apreciacao_risco else "Não","Manual":"Sim" if m.possui_manual_atualizado else "Não","Treinamento":"Sim" if m.possui_treinamento else "Não","Observações":m.observacoes})
    return pd.DataFrame(rows)

def df_docs(db, ids):
    rows=[]
    for d in db.query(DocumentoNR12).filter(DocumentoNR12.site_id.in_(ids)).order_by(DocumentoNR12.id.desc()):
        cod=site_code_raw(db,d.site_id)
        rows.append({"ID":d.id,"Site":site_label(cod),"Código site":cod,"Grupo":site_grupo(cod),"Máquina":d.maquina.codigo if d.maquina else "—","Tipo":d.tipo,"Status":calcular_status_documento(d),"Emissão":fmt_date(d.data_emissao),"Validade":fmt_date(d.data_validade),"Arquivo":d.arquivo_nome,"Responsável":d.responsavel,"Descrição":d.descricao,"Observações":d.observacoes})
    return pd.DataFrame(rows)

def df_ver(db, ids):
    rows=[]
    for v in db.query(VerificacaoNR12).filter(VerificacaoNR12.site_id.in_(ids)).order_by(VerificacaoNR12.id.desc()):
        cod=site_code_raw(db,v.site_id)
        rows.append({"ID":v.id,"Site":site_label(cod),"Código site":cod,"Grupo":site_grupo(cod),"Máquina":v.maquina.codigo if v.maquina else "—","Tipo":v.tipo,"Versão checklist":v.checklist_versao.versao if getattr(v,"checklist_versao",None) else "Histórico","Data":fmt_date(v.data_verificacao),"Responsável":v.responsavel,"Resultado":v.resultado,"Pontuação %":v.pontuacao,"NC crítica":"Sim" if v.possui_nc_critica else "Não","Próxima":fmt_date(v.proxima_verificacao),"Observações":v.observacoes})
    return pd.DataFrame(rows)

def df_pac_nr12(db, ids):
    rows=[]
    for p in db.query(PACNR12).filter(PACNR12.site_id.in_(ids)).order_by(PACNR12.id.desc()):
        cod=site_code_raw(db,p.site_id)
        rows.append({"ID":p.id,"Site":site_label(cod),"Código site":cod,"Grupo":site_grupo(cod),"Máquina":p.maquina.codigo if p.maquina else "—","Origem":p.origem,"Classificação":p.classificacao,"Status":"Vencida" if identificar_pac_vencido(p.prazo,p.status) else p.status,"Responsável":p.responsavel,"Área":p.area_responsavel,"Prazo":fmt_date(p.prazo),"Desvio":p.descricao_desvio,"Evidência":p.evidencia_conclusao,"Validação EHS":"Sim" if p.validacao_ehs else "Não","Eficácia":p.verificacao_eficacia})
    return pd.DataFrame(rows)

def df_moc(db, ids):
    rows=[]
    for m in db.query(MOCNR12).filter(MOCNR12.site_id.in_(ids)).order_by(MOCNR12.id.desc()):
        cod=site_code_raw(db,m.site_id)
        rows.append({"ID":m.id,"Site":site_label(cod),"Código site":cod,"Grupo":site_grupo(cod),"Máquina":m.maquina.codigo if m.maquina else "—","Tipo":m.tipo_mudanca,"Descrição":m.descricao,"Solicitante":m.solicitante,"Área":m.area_solicitante,"Data":fmt_date(m.data),"Impacta segurança":"Sim" if m.impacta_seguranca else "Não","Exige MOC":"Sim" if m.exige_moc else "Não","Status":m.status,"EHS":"Sim" if m.aprovacao_ehs else "Não","Manutenção":"Sim" if m.aprovacao_manutencao else "Não","Engenharia":"Sim" if m.aprovacao_engenharia else "Não","Produção":"Sim" if m.aprovacao_producao else "Não","Auditoria pós":"Sim" if m.necessita_auditoria_pos_mudanca else "Não","Treinamento":"Sim" if m.necessita_treinamento else "Não","Validação final":"Sim" if m.validacao_final else "Não"})
    return pd.DataFrame(rows)

def df_aud(db, ids):
    rows=[]
    for a in db.query(AuditoriaCruzada).filter(AuditoriaCruzada.site_auditado_id.in_(ids)).order_by(AuditoriaCruzada.id.desc()):
        res=db.query(RespostaAuditoriaEHS).filter_by(auditoria_id=a.id).all(); a.conformidade_percentual=calcular_conformidade_ehs(res); a.maturidade_media=calcular_maturidade_ehs(res)
        cod=site_code_raw(db,a.site_auditado_id)
        rows.append({"ID":a.id,"Ano":a.ano,"Ciclo":a.ciclo,"Site auditado":site_label(cod),"Código site":cod,"Grupo":site_grupo(cod),"Site auditor líder":site_code(db,a.site_auditor_lider_id),"Site auditor apoio":site_code(db,a.site_auditor_apoio_id),"Auditor líder":a.auditor_lider,"Auditor apoio":a.auditor_apoio,"Data planejada":fmt_date(a.data_planejada),"Início":fmt_date(a.data_inicio),"Fim":fmt_date(a.data_fim),"Status":a.status,"Conformidade %":a.conformidade_percentual,"Maturidade":a.maturidade_media,"Escopo":a.escopo})
    db.commit(); return pd.DataFrame(rows)

def df_pac_ehs(db, ids):
    rows=[]
    for p in db.query(PACEHS).filter(PACEHS.site_id.in_(ids)).order_by(PACEHS.id.desc()):
        cod=site_code_raw(db,p.site_id)
        rows.append({"ID":p.id,"Site":site_label(cod),"Código site":cod,"Grupo":site_grupo(cod),"Auditoria":p.auditoria_id,"Categoria":p.requisito.diretiva.categoria if p.requisito and p.requisito.diretiva else "—","Requisito":p.requisito.pergunta if p.requisito else "—","Tipo de achado":p.tipo_achado,"Descrição":p.descricao,"Evidência":p.evidencia,"Risco":p.risco,"Causa raiz":p.causa_raiz,"Ação imediata":p.acao_imediata,"Ação corretiva":p.acao_corretiva,"Responsável":p.responsavel,"Área":p.area_responsavel,"Prazo":fmt_date(p.prazo),"Status":"Vencida" if identificar_pac_vencido(p.prazo,p.status) else p.status,"Prioridade":p.prioridade_criticidade,"Validação EHS":"Sim" if p.validacao_ehs else "Não","Eficácia":p.verificacao_eficacia})
    return pd.DataFrame(rows)

def df_logs(db):
    return pd.DataFrame([{"ID":l.id,"Data/hora":l.data_hora,"Usuário":l.usuario,"Perfil":l.perfil,"Módulo":l.modulo,"Entidade":l.entidade,"Entidade ID":l.entidade_id,"Ação":l.acao,"Campo":l.campo,"Valor anterior":l.valor_anterior,"Valor novo":l.valor_novo,"Observação":l.observacao} for l in db.query(LogSistema).order_by(LogSistema.id.desc()).limit(5000)])

def calcular_qualidade_dados(db, ids):
    rows=[]
    def add(modulo, site_id, tipo, prioridade, entidade, entidade_id, descricao, recomendacao):
        cod=site_code_raw(db,site_id) if site_id else "Corporativo"
        rows.append({"Módulo":modulo,"Site":site_label(cod),"Código site":cod,"Grupo":site_grupo(cod),"Tipo":tipo,"Prioridade":prioridade,"Entidade":entidade,"ID":entidade_id,"Descrição":descricao,"Recomendação":recomendacao})
    for m in db.query(MaquinaNR12).filter(MaquinaNR12.site_id.in_(ids)).all():
        exp=explicar_status_maquina(db,m)
        if not m.responsavel_area: add("Máquinas",m.site_id,"Máquina sem responsável","Média","Máquina",m.id,f"{m.codigo} sem responsável de área.","Definir responsável no inventário.")
        if not m.proxima_auditoria: add("Máquinas",m.site_id,"Máquina sem próxima auditoria","Alta","Máquina",m.id,f"{m.codigo} sem próxima auditoria.","Cadastrar periodicidade e próxima verificação.")
        if exp["status_calculado"]!="Conforme" and not as_date(m.data_prevista_adequacao): add("Máquinas",m.site_id,"Não conforme sem data de adequação","Alta","Máquina",m.id,f"{m.codigo} não conforme sem data prevista.","Definir data prevista de adequação.")
        if (m.risco_maquina or "") == "Apreciação de risco não realizada": add("Máquinas",m.site_id,"Risco não avaliado","Alta","Máquina",m.id,f"{m.codigo} sem apreciação de risco realizada.","Realizar/registrar apreciação de risco.")
        docs={d.tipo:d for d in db.query(DocumentoNR12).filter_by(maquina_id=m.id).all()}
        for t in DOCUMENTOS_ESSENCIAIS:
            if t not in docs: add("Documentos",m.site_id,"Documento essencial ausente","Alta","Máquina",m.id,f"{t} ausente para {m.codigo}.","Anexar documento essencial.")
            elif calcular_status_documento(docs[t])=="Vencido": add("Documentos",m.site_id,"Documento essencial vencido","Alta","Documento",docs[t].id,f"{t} vencido para {m.codigo}.","Renovar/anexar versão válida.")
    for p in db.query(PACNR12).filter(PACNR12.site_id.in_(ids)).all():
        stp="Vencida" if identificar_pac_vencido(p.prazo,p.status) else p.status
        if not p.responsavel: add("PAC Máquinas",p.site_id,"PAC sem responsável","Média","PAC",p.id,"PAC sem responsável definido.","Atribuir responsável.")
        if stp=="Vencida": add("PAC Máquinas",p.site_id,"PAC vencido","Alta","PAC",p.id,"PAC vencido.","Replanejar e concluir ação.")
        if p.status=="Concluída" and not p.evidencia_conclusao: add("PAC Máquinas",p.site_id,"PAC concluído sem evidência","Alta","PAC",p.id,"PAC concluído sem evidência.","Anexar evidência de conclusão.")
        if p.status=="Concluída" and p.classificacao=="Crítico" and not p.validacao_ehs: add("PAC Máquinas",p.site_id,"PAC crítico sem validação EHS","Alta","PAC",p.id,"PAC crítico concluído sem validação EHS.","Realizar validação EHS.")
    for m in db.query(MOCNR12).filter(MOCNR12.site_id.in_(ids), MOCNR12.exige_moc==True, MOCNR12.validacao_final==False).all():
        add("MOC",m.site_id,"MOC crítica sem validação final","Alta","MOC",m.id,"MOC crítica sem validação final.","Concluir validação final antes de liberar condição.")
    for a in db.query(AuditoriaCruzada).filter(AuditoriaCruzada.site_auditado_id.in_(ids)).all():
        total_req=db.query(RequisitoEHS).filter_by(ativo=True).count(); total_resp=db.query(RespostaAuditoriaEHS).filter_by(auditoria_id=a.id).count()
        if total_resp < total_req: add("Auditoria EHS",a.site_auditado_id,"Auditoria sem checklist completo","Média","Auditoria",a.id,"Auditoria com checklist incompleto.","Gerar ou revisar checklist automático.")
        if a.status=="Planejada" and a.data_planejada and a.data_planejada < date.today(): add("Auditoria EHS",a.site_auditado_id,"Auditoria planejada vencida","Média","Auditoria",a.id,"Auditoria planejada com data vencida.","Atualizar planejamento ou iniciar auditoria.")
        for r in db.query(RespostaAuditoriaEHS).filter_by(auditoria_id=a.id).all():
            if r.status in ["Não Conforme","Parcialmente Conforme"] and not r.evidencia_verificada:
                add("Auditoria EHS",a.site_auditado_id,"Resposta não conforme sem evidência","Média","Resposta",r.id,"Resposta de auditoria sem evidência.","Adicionar evidência verificada.")
    df=pd.DataFrame(rows)
    penalidade={"Alta":5,"Média":3,"Baixa":1}
    score=max(0,min(100,100-sum(penalidade.get(x,2) for x in df["Prioridade"]))) if not df.empty else 100
    return score, df

def kpi_card_modulo(modulo, metrica, valor, descricao="", cor="#0f172a"):
    st.markdown(f"""
    <div class='kpi' style='border-top:4px solid {cor};'>
      <div class='kpi-label'>[{html_escape(modulo)}]</div>
      <div style='font-weight:850;color:#111827;margin-top:.1rem'>{html_escape(metrica)}</div>
      <div class='kpi-value'>{html_escape(valor)}</div>
      <div class='muted'>{html_escape(descricao)}</div>
    </div>
    """, unsafe_allow_html=True)

def dashboard_integrado(db,u):
    ids=visible_site_ids(u,db); update_vencidos(db)
    ms=db.query(MaquinaNR12).filter(MaquinaNR12.site_id.in_(ids)).all()
    total=len(ms); conformes=sum(1 for m in ms if calcular_status_maquina_nr12(db,m)=="Conforme")
    risco_alto=sum(1 for m in ms if (m.risco_maquina or "Apreciação de risco não realizada") in ["Alto","Extremo","Apreciação de risco não realizada"])
    da=df_aud(db,ids); dp=df_pac_ehs(db,ids); score_q, dfq=calcular_qualidade_dados(db,ids)
    conf_media=round(da["Conformidade %"].mean(),1) if not da.empty else 0
    mat_media=round(da["Maturidade"].mean(),2) if not da.empty else 0
    section("Visão geral integrada")
    cols=st.columns(3)
    with cols[0]: kpi_card_modulo("Máquinas", "Total de máquinas", total, "Inventário dentro do escopo de acesso", "#2563eb")
    with cols[1]: kpi_card_modulo("Máquinas", "% máquinas conformes", f"{round(conformes/total*100,1) if total else 0}%", f"{conformes}/{total} conformes", "#16a34a")
    with cols[2]: kpi_card_modulo("Máquinas", "PACs vencidos", db.query(PACNR12).filter(PACNR12.site_id.in_(ids),PACNR12.status=="Vencida").count(), "Ações de proteções de máquinas", "#dc2626")
    cols=st.columns(3)
    with cols[0]: kpi_card_modulo("Máquinas", "Risco alto/extremo", risco_alto, "Inclui risco não avaliado", "#f97316")
    with cols[1]: kpi_card_modulo("Auditoria EHS", "Conformidade média", f"{conf_media}%", "Média das auditorias acessíveis", "#7c3aed")
    with cols[2]: kpi_card_modulo("Auditoria EHS", "Maturidade média", mat_media, "Escala 0 a 5", "#0891b2")
    cols=st.columns(3)
    with cols[0]: kpi_card_modulo("Auditoria EHS", "Auditorias em andamento", int((da["Status"]=="Em andamento").sum()) if not da.empty else 0, "Ciclos ativos", "#2563eb")
    with cols[1]: kpi_card_modulo("Auditoria EHS", "NCs críticas", int((dp["Tipo de achado"]=="Não conformidade crítica").sum()) if not dp.empty else 0, "Achados críticos", "#dc2626")
    with cols[2]: kpi_card_modulo("Qualidade dos Dados", "Score da base", f"{score_q}%", f"{len(dfq)} inconsistências mapeadas", "#d9a514")
    section("Alertas executivos")
    alerts=[]
    for _,r in (dfq.head(10).iterrows() if not dfq.empty else []):
        if r["Prioridade"]=="Alta": alerts.append({"Módulo":r["Módulo"],"Tipo":r["Tipo"],"Site":r["Site"],"Descrição":r["Descrição"],"Recomendação":r["Recomendação"]})
    if alerts: st.dataframe(pd.DataFrame(alerts),use_container_width=True,hide_index=True)
    else: empty_state("Nenhum alerta executivo crítico identificado.")

def home_page(db,u):
    header("Plataforma Integrada EHS", f"{NOME_MODULO_MAQUINAS} e Auditorias Cruzadas de Diretrizes de EHS")
    dashboard_integrado(db,u); section("Módulos")
    c1,c2=st.columns(2)
    with c1:
        module_card(NOME_MODULO_MAQUINAS,"Inventário, documentos, checklists, MOC, PAC, pendências, qualidade dos dados e relatórios.","⚙️")
        if st.button(f"Acessar {NOME_MODULO_MAQUINAS}",use_container_width=True):
            st.session_state.modulo="nr12"; st.session_state.page_nr12=NOME_DASH_MAQUINAS; st.session_state.nav_nr12=NOME_DASH_MAQUINAS; st.rerun()
    with c2:
        module_card("Auditoria Cruzada de Diretrizes de EHS","Planejamento, checklist incorporado, evidências, maturidade, PAC, análises regionais e relatórios.","🧭")
        if st.button("Acessar Auditoria Cruzada",use_container_width=True):
            st.session_state.modulo="ehs"; st.session_state.page_ehs="Dashboard Auditoria Cruzada"; st.session_state.nav_ehs="Dashboard Auditoria Cruzada"; st.rerun()

def montar_tendencias_maquinas(db, ids):
    vers=df_ver(db,ids)
    pac=df_pac_nr12(db,ids)
    docs=df_docs(db,ids)
    return vers,pac,docs

def nr12_dashboard(db,u):
    header(NOME_DASH_MAQUINAS,"Indicadores executivos, tendências, pendências e detalhamento das proteções de máquinas")
    ids=visible_site_ids(u,db); dfm_full=df_maquinas(db,ids)
    if dfm_full.empty: empty_state("Nenhuma máquina cadastrada para os filtros de acesso do usuário."); return
    with st.expander("Filtros", expanded=True):
        c1,c2,c3,c4=st.columns(4)
        unidades=c1.multiselect("Unidade", sorted(dfm_full["Site"].dropna().unique()))
        grupos=c2.multiselect("Grupo", sorted(dfm_full["Grupo"].dropna().unique()))
        riscos=c3.multiselect("Risco da máquina", [r for r in RISCOS_MAQUINA if r in set(dfm_full["Risco"].dropna())])
        status_f=c4.multiselect(NOME_STATUS_PROTECAO, [s for s in STATUS_MAQUINA if s in set(dfm_full[NOME_STATUS_PROTECAO].dropna())])
    dfm=dfm_full.copy()
    if unidades: dfm=dfm[dfm["Site"].isin(unidades)]
    if grupos: dfm=dfm[dfm["Grupo"].isin(grupos)]
    if riscos: dfm=dfm[dfm["Risco"].isin(riscos)]
    if status_f: dfm=dfm[dfm[NOME_STATUS_PROTECAO].isin(status_f)]
    m_ids=dfm["ID"].astype(int).tolist() if not dfm.empty else []
    ms=db.query(MaquinaNR12).filter(MaquinaNR12.id.in_(m_ids)).all() if m_ids else []
    dfp=df_pac_nr12(db,ids); dfp=dfp[dfp["Máquina"].isin(set(dfm["Código"].astype(str)))] if not dfp.empty and not dfm.empty else dfp
    meta=calcular_meta_adequacao_nr12(db,ms); total=len(ms); sts=[calcular_status_maquina_nr12(db,m) for m in ms]
    tab1,tab2,tab3,tab4=st.tabs(["Resumo","Tendências","Pendências","Detalhamento"])
    with tab1:
        cards=[("Total de máquinas",total),("% máquinas conformes",f"{round(sts.count('Conforme')/total*100,1) if total else 0}%"),("Fora do plano" if not meta["dentro_plano"] else "Dentro do plano",f"{meta['adequadas']}/{meta['previstas_ate_hoje']}","Adequadas x previstas até hoje"),("Máquinas não conformes",sts.count("Não conforme")),("Sem data de adequação",meta["sem_data"]),("PACs vencidos",0 if dfp.empty else int((dfp["Status"]=="Vencida").sum())),("Risco alto/extremo",0 if dfm.empty else int(dfm["Risco"].isin(["Alto","Extremo","Apreciação de risco não realizada"]).sum()))]
        for base in range(0,len(cards),4):
            cols=st.columns(min(4,len(cards)-base))
            for c,card in zip(cols,cards[base:base+4]):
                with c: kpi_card(card[0],card[1],card[2] if len(card)>2 else "")
        section("Máquinas por risco")
        risco_counts=dfm.groupby("Risco",as_index=False).size().rename(columns={"size":"Quantidade"}) if not dfm.empty else pd.DataFrame(columns=["Risco","Quantidade"])
        if not risco_counts.empty:
            fig=px.bar(risco_counts,x="Risco",y="Quantidade",color="Risco",text="Quantidade",title="Quantidade de máquinas por risco",color_discrete_map=RISCO_COLOR_MAP,category_orders={"Risco":RISCOS_MAQUINA})
            fig.update_traces(textposition="outside"); fig.update_layout(template="plotly_white",showlegend=False)
            st.plotly_chart(fig,use_container_width=True)
        else: empty_state("Sem dados de risco.")
    with tab2:
        vers,pac,docs=montar_tendencias_maquinas(db,ids)
        c1,c2=st.columns(2)
        with c1:
            if not vers.empty:
                vv=vers.copy(); vv["Mês"]=pd.to_datetime(vv["Data"],format="%d/%m/%Y",errors="coerce").dt.to_period("M").astype(str)
                real=vv.groupby("Mês",as_index=False).size().rename(columns={"size":"Verificações"})
                st.plotly_chart(px.line(real,x="Mês",y="Verificações",markers=True,title="Evolução de auditorias/verificações realizadas").update_layout(template="plotly_white"),use_container_width=True)
            else: empty_state("Sem verificações para tendência.")
        with c2:
            if not pac.empty:
                pp=pac.copy(); pp["Mês prazo"]=pd.to_datetime(pp["Prazo"],format="%d/%m/%Y",errors="coerce").dt.to_period("M").astype(str)
                gp=pp.groupby(["Mês prazo","Status"],as_index=False).size().rename(columns={"size":"Quantidade"})
                st.plotly_chart(px.bar(gp,x="Mês prazo",y="Quantidade",color="Status",barmode="group",title="Evolução de PACs por status",color_discrete_map=STATUS_PAC_COLOR_MAP).update_layout(template="plotly_white"),use_container_width=True)
            else: empty_state("Sem PACs para tendência.")
        c3,c4=st.columns(2)
        with c3:
            if not pac.empty:
                gp=pac.groupby("Classificação",as_index=False).size().rename(columns={"size":"Quantidade"})
                st.plotly_chart(px.bar(gp,x="Classificação",y="Quantidade",color="Classificação",text="Quantidade",title="Desvios/PACs por classificação",color_discrete_map=PAC_COLOR_MAP).update_layout(template="plotly_white",showlegend=False),use_container_width=True)
            else: empty_state("Sem desvios classificados.")
        with c4:
            if not docs.empty:
                gd=docs.groupby("Status",as_index=False).size().rename(columns={"size":"Quantidade"})
                st.plotly_chart(px.bar(gd,x="Status",y="Quantidade",color="Status",text="Quantidade",title="Documentos por status").update_layout(template="plotly_white",showlegend=False),use_container_width=True)
            else: empty_state("Sem documentos.")
    with tab3:
        pr=dfm[dfm[NOME_STATUS_PROTECAO]=="Não conforme"] if not dfm.empty else pd.DataFrame()
        if not pr.empty: st.dataframe(pr[["Site","Grupo","Código","Máquina","Risco",NOME_STATUS_PROTECAO,"Motivo da não conformidade","Responsável","Data prevista adequação"]],use_container_width=True,hide_index=True)
        else: empty_state("Nenhuma máquina prioritária nos filtros selecionados.")
    with tab4:
        st.dataframe(dfm,use_container_width=True,hide_index=True)
        download_excel_button("Exportar dashboard de máquinas", "dashboard_protecoes_maquinas.xlsx", {"Máquinas":dfm,"PAC":dfp})

def nr12_inventario(db,u):
    header("Inventário de Máquinas","Cadastro, edição, consulta e exportação")
    ids=visible_site_ids(u,db); sites={site_label(s.codigo):s.id for s in db.query(Site).filter(Site.id.in_(ids)).order_by(Site.codigo)}
    section("Consulta")
    df=df_maquinas(db,ids)
    if df.empty: empty_state("Nenhuma máquina cadastrada.")
    else:
        with st.expander("Filtros", expanded=True):
            c1,c2,c3,c4=st.columns(4)
            fs=c1.multiselect("Filtrar status",sorted(df[NOME_STATUS_PROTECAO].dropna().unique()))
            fr=c2.multiselect("Filtrar risco",[r for r in RISCOS_MAQUINA if r in set(df["Risco"].dropna())])
            fc=c3.multiselect("Filtrar criticidade",sorted(df["Criticidade"].dropna().unique()))
            fu=c4.multiselect("Filtrar unidade",sorted(df["Site"].dropna().unique()))
        f=df.copy()
        if fs: f=f[f[NOME_STATUS_PROTECAO].isin(fs)]
        if fr: f=f[f["Risco"].isin(fr)]
        if fc: f=f[f["Criticidade"].isin(fc)]
        if fu: f=f[f["Site"].isin(fu)]
        st.dataframe(f,use_container_width=True,hide_index=True)
        download_excel_button("Exportar Excel","inventario_maquinas.xlsx",{"Inventário":f})
    if has_permission(u,"maquinas","criar") and sites:
        with st.expander("Cadastrar máquina"):
            with st.form("maq_enh"):
                t1,t2,t3=st.tabs(["Dados básicos","Responsáveis e risco","Documentos e observações"])
                with t1:
                    a,b=st.columns(2); cod=a.text_input("Código*"); site=a.selectbox("Site*",list(sites)); nome=b.text_input("Nome*"); tipo=b.text_input("Tipo de equipamento"); area=a.text_input("Área/setor"); linha=b.text_input("Linha/processo")
                with t2:
                    a,b,c=st.columns(3); resp=a.text_input("Responsável da área"); crit=b.selectbox("Criticidade",CRITICIDADES); risco=c.selectbox("Risco da máquina",RISCOS_MAQUINA); status=a.selectbox(NOME_STATUS_PROTECAO,STATUS_MAQUINA); prox=b.date_input("Próxima auditoria prevista",value=date.today()+timedelta(days=180)); data_prevista_adequacao=None
                    if status!="Conforme": data_prevista_adequacao=c.date_input("Data prevista para adequação",value=date.today()+timedelta(days=90))
                with t3:
                    a,b,c=st.columns(3); fab=a.text_input("Fabricante"); mod=b.text_input("Modelo"); serie=c.text_input("Número de série"); ano=a.text_input("Ano"); ck=st.columns(5); laudo=ck[0].checkbox("Laudo"); art=ck[1].checkbox("ART"); apr=ck[2].checkbox("Apreciação"); man=ck[3].checkbox("Manual"); tre=ck[4].checkbox("Treinamento"); obs=st.text_area("Observações")
                if st.form_submit_button("Salvar",use_container_width=True):
                    if cod and nome and not db.query(MaquinaNR12).filter_by(codigo=cod).first():
                        m=MaquinaNR12(codigo=cod,site_id=sites[site],area_setor=area,linha_processo=linha,nome=nome,fabricante=fab,modelo=mod,numero_serie=serie,ano=ano,tipo_equipamento=tipo,responsavel_area=resp,criticidade=crit,risco_maquina=risco,status_nr12=status,proxima_auditoria=prox,data_prevista_adequacao=data_prevista_adequacao,possui_laudo=laudo,possui_art=art,possui_apreciacao_risco=apr,possui_manual_atualizado=man,possui_treinamento=tre,observacoes=obs)
                        db.add(m); db.flush(); registrar_log(db,u,"Máquinas","MaquinaNR12",m.id,"criar",observacao=f"Máquina {cod} cadastrada"); db.commit(); st.success("Máquina cadastrada."); st.rerun()
                    else: st.error("Preencha código/nome e evite código duplicado.")
    if has_permission(u,"maquinas","editar"):
        opts=machine_options(db,ids)
        if opts:
            with st.expander("Editar máquina"):
                lab=st.selectbox("Máquina",list(opts),key="editar_maquina_enh"); m=db.get(MaquinaNR12,opts[lab])
                with st.form("editmaq_enh"):
                    status_ant=m.status_nr12; status_atual=normalizar_status_nr12(m.status_nr12); novo_status=st.selectbox(NOME_STATUS_PROTECAO,STATUS_MAQUINA,index=STATUS_MAQUINA.index(status_atual)); nova_criticidade=st.selectbox("Criticidade",CRITICIDADES,index=CRITICIDADES.index(m.criticidade) if m.criticidade in CRITICIDADES else 1); risco_atual=m.risco_maquina or "Apreciação de risco não realizada"; novo_risco=st.selectbox("Risco da máquina",RISCOS_MAQUINA,index=RISCOS_MAQUINA.index(risco_atual) if risco_atual in RISCOS_MAQUINA else 0); nova_proxima_auditoria=st.date_input("Próxima auditoria prevista",value=m.proxima_auditoria or date.today()+timedelta(days=180)); nova_data_prevista=None
                    if novo_status!="Conforme": nova_data_prevista=st.date_input("Data prevista para adequação",value=m.data_prevista_adequacao or date.today()+timedelta(days=90))
                    novas_observacoes=st.text_area("Observações",m.observacoes or "")
                    if st.form_submit_button("Atualizar",use_container_width=True):
                        m.status_nr12=novo_status; m.criticidade=nova_criticidade; m.risco_maquina=novo_risco; m.proxima_auditoria=nova_proxima_auditoria; m.data_prevista_adequacao=None if novo_status=="Conforme" else nova_data_prevista; m.observacoes=novas_observacoes
                        registrar_log(db,u,"Máquinas","MaquinaNR12",m.id,"editar","status",status_ant,novo_status); db.commit(); st.success("Atualizado."); st.rerun()

def nr12_documentos(db,u):
    header(NOME_DOCS_MAQUINAS,"Controle de documentos essenciais, validade, evidências e anexos")
    ids=visible_site_ids(u,db); opts=machine_options(db,ids); df=df_docs(db,ids)
    section("Consulta")
    st.dataframe(df,use_container_width=True,hide_index=True) if not df.empty else empty_state("Nenhum documento.")
    download_excel_button("Exportar documentos Excel","documentos_protecoes_maquinas.xlsx",{"Documentos":df})
    section("Arquivos anexados")
    if not opts: empty_state("Cadastre uma máquina antes de consultar arquivos anexados.")
    else:
        lab_arq=st.selectbox("Selecionar máquina",list(opts),key="docs_maquina_arquivos_enh"); maquina_id=opts[lab_arq]
        for d in db.query(DocumentoNR12).filter(DocumentoNR12.maquina_id==maquina_id,DocumentoNR12.site_id.in_(ids)).order_by(DocumentoNR12.id.desc()).all():
            if d.arquivo_nome:
                c1,c2,c3,c4=st.columns([1.4,1.4,2.2,1]); c1.markdown(f"**{d.tipo}**"); c2.write(calcular_status_documento(d)); c3.write(d.arquivo_nome); arquivo_data=d.arquivo_bytes
                if arquivo_data: c4.download_button("Baixar",data=arquivo_data,file_name=d.arquivo_nome,mime="application/octet-stream",key=f"doc_download_enh_{d.id}",use_container_width=True)
    if has_permission(u,"documentos_maquinas","criar") and opts:
        with st.expander("Cadastrar documento"):
            with st.form("doc_enh"):
                lab=st.selectbox("Máquina",list(opts),key="docs_maquina_cadastro_enh"); tipo=st.selectbox("Tipo",TIPOS_DOC_NR12); emiss=st.date_input("Emissão",date.today()); valid=st.date_input("Validade",date.today()+timedelta(days=365)); resp=st.text_input("Responsável"); up=st.file_uploader("Arquivo"); desc=st.text_area("Descrição")
                if st.form_submit_button("Salvar",use_container_width=True):
                    m=db.get(MaquinaNR12,opts[lab]); fname=up.name if up else ""; fbytes=up.getvalue() if up else None; d=DocumentoNR12(maquina_id=m.id,site_id=m.site_id,tipo=tipo,descricao=desc,data_emissao=emiss,data_validade=valid,arquivo_nome=fname,arquivo_caminho=fname,arquivo_bytes=fbytes,responsavel=resp); db.add(d)
                    if tipo=="Laudo NR-12": m.possui_laudo=True
                    if tipo=="ART": m.possui_art=True
                    if tipo=="Apreciação de risco": m.possui_apreciacao_risco=True
                    db.flush(); registrar_log(db,u,"Documentos Máquinas","DocumentoNR12",d.id,"criar",observacao=tipo); db.commit(); st.success("Documento salvo."); st.rerun()

def get_active_checklist_versions(db):
    vers=db.query(ChecklistVersaoMaquinas).filter_by(ativo=True).order_by(ChecklistVersaoMaquinas.tipo_checklist,ChecklistVersaoMaquinas.versao.desc()).all()
    latest={}
    for v in vers:
        latest.setdefault(v.tipo_checklist,v)
    return latest

def nr12_checklists(db,u):
    header(NOME_CHECKLISTS_MAQUINAS,"Registro por máquina, versão de checklist, pontuação e geração automática de PAC")
    ids=visible_site_ids(u,db); opts=machine_options(db,ids); df=df_ver(db,ids)
    section("Verificações registradas")
    if not df.empty:
        st.dataframe(df,use_container_width=True,hide_index=True)
        download_excel_button("Exportar verificações Excel","verificacoes_protecoes_maquinas.xlsx",{"Verificações":df})
    else: empty_state("Nenhuma verificação.")
    section("Novo checklist")
    if not opts: empty_state("Cadastre uma máquina antes."); return
    if not has_permission(u,"checklists_maquinas","criar"): alert_card("Seu perfil permite consulta, mas não registro."); return
    latest=get_active_checklist_versions(db)
    if not latest: empty_state("Nenhuma versão ativa de checklist encontrada. Acesse a Base de Checklists de Proteções."); return
    tipo=st.selectbox("Tipo de checklist",list(latest.keys()),key="tipo_checklist_versionado")
    versoes=db.query(ChecklistVersaoMaquinas).filter_by(tipo_checklist=tipo,ativo=True).order_by(ChecklistVersaoMaquinas.versao.desc()).all()
    vsel=st.selectbox("Versão",versoes,format_func=lambda v:f"v{v.versao} — {v.descricao or 'sem descrição'}",key="versao_checklist_selector")
    itens=db.query(ChecklistPerguntaVersaoMaquinas).filter_by(checklist_versao_id=vsel.id,ativo=True).order_by(ChecklistPerguntaVersaoMaquinas.ordem).all()
    with st.form(f"ver_versionada_{vsel.id}"):
        lab=st.selectbox("Máquina",list(opts),key=f"maq_versionada_{vsel.id}"); resp=st.text_input("Responsável",u.nome,key=f"resp_versionada_{vsel.id}"); obs=st.text_area("Observações",key=f"obs_versionada_{vsel.id}"); temp=[]
        for it in itens:
            st.markdown(f"<div class='check-item'><div class='check-q'>{it.ordem}. {html_escape(it.pergunta)}{'<span class=\"check-meta\">Crítico</span>' if it.item_critico else ''}</div></div>",unsafe_allow_html=True)
            c1,c2,c3,c4=st.columns([1,1.3,2.6,1]); apl=c1.checkbox("Aplicável",True,key=f"ap_v{vsel.id}_{it.id}"); res=c2.selectbox("Resultado",RESULTADOS_NR12,key=f"res_v{vsel.id}_{it.id}"); com=c3.text_input("Comentário/evidência",key=f"com_v{vsel.id}_{it.id}"); gp=c4.checkbox("Gerar PAC",False,key=f"gp_v{vsel.id}_{it.id}"); temp.append((it,apl,res,com,gp))
        if st.form_submit_button("Salvar verificação",use_container_width=True):
            m=db.get(MaquinaNR12,opts[lab]); v=VerificacaoNR12(maquina_id=m.id,site_id=m.site_id,tipo=tipo,checklist_versao_id=vsel.id,data_verificacao=date.today(),responsavel=resp,observacoes=obs,proxima_verificacao=date.today()+timedelta(days=180)); db.add(v); db.flush(); rs=[]
            for it,apl,res,com,gp in temp:
                r=RespostaNR12(verificacao_id=v.id,item_id=None,aplicavel=apl,resultado="Não aplicável" if not apl else res,comentario_evidencia=com,gerar_pac=gp,pergunta_snapshot=it.pergunta,item_critico_snapshot=it.item_critico); db.add(r); rs.append(r)
            db.flush(); v.resultado,v.pontuacao,v.possui_nc_critica=calcular_resultado_verificacao_nr12(rs); m.ultima_auditoria=date.today(); m.proxima_auditoria=v.proxima_verificacao; m.status_nr12=v.resultado if v.resultado in STATUS_MAQUINA else normalizar_status_nr12(m.status_nr12)
            for r in rs:
                if r.resultado=="Não conforme" or r.gerar_pac: gerar_pac_automatico_nr12(db,v,r,resp)
            registrar_log(db,u,"Checklists Máquinas","VerificacaoNR12",v.id,"criar",observacao=f"{tipo} v{vsel.versao}"); db.commit(); st.success(f"Verificação salva: {v.resultado} | {v.pontuacao}%"); st.rerun()

def nr12_base_checklists(db,u):
    header(NOME_BASE_CHECKLISTS_MAQUINAS,"Gestão editável e versionada dos checklists de proteções de máquinas")
    if not has_permission(u,"checklists_maquinas","editar") and not can_admin(u):
        alert_card("Apenas perfis com permissão de edição podem administrar a base de checklists.")
    vers=db.query(ChecklistVersaoMaquinas).order_by(ChecklistVersaoMaquinas.tipo_checklist,ChecklistVersaoMaquinas.versao.desc()).all()
    dfv=pd.DataFrame([{"ID":v.id,"Tipo":v.tipo_checklist,"Versão":v.versao,"Descrição":v.descricao,"Ativo":v.ativo,"Criado em":v.criado_em,"Criado por":v.criado_por} for v in vers])
    st.dataframe(dfv,use_container_width=True,hide_index=True)
    download_excel_button("Exportar base de checklists","base_checklists_protecoes.xlsx",{"Versões":dfv,"Perguntas":pd.DataFrame([{"Versão ID":p.checklist_versao_id,"Tipo":p.versao.tipo_checklist if p.versao else "—","Versão":p.versao.versao if p.versao else "—","Ordem":p.ordem,"Pergunta":p.pergunta,"Crítico":p.item_critico,"Ativo":p.ativo} for p in db.query(ChecklistPerguntaVersaoMaquinas).all()])})
    if has_permission(u,"checklists_maquinas","editar") or can_admin(u):
        with st.expander("Editar perguntas da versão"):
            if vers:
                v=st.selectbox("Versão",vers,format_func=lambda x:f"{x.tipo_checklist} v{x.versao} {'(ativa)' if x.ativo else '(inativa)'}",key="editar_versao_checklist")
                perguntas=db.query(ChecklistPerguntaVersaoMaquinas).filter_by(checklist_versao_id=v.id).order_by(ChecklistPerguntaVersaoMaquinas.ordem).all()
                dfp=pd.DataFrame([{"ID":p.id,"Ordem":p.ordem,"Pergunta":p.pergunta,"Crítico":p.item_critico,"Ativo":p.ativo} for p in perguntas])
                ed=st.data_editor(dfp,use_container_width=True,hide_index=True,disabled=["ID"],num_rows="dynamic",key=f"editor_perguntas_{v.id}")
                c1,c2=st.columns(2)
                if c1.button("Salvar alterações",use_container_width=True,key=f"salvar_perguntas_{v.id}"):
                    existentes={p.id:p for p in perguntas}
                    for _,row in ed.iterrows():
                        rid=row.get("ID")
                        if pd.notna(rid) and int(rid) in existentes:
                            p=existentes[int(rid)]; p.ordem=int(row["Ordem"]); p.pergunta=str(row["Pergunta"]); p.item_critico=bool(row["Crítico"]); p.ativo=bool(row["Ativo"])
                        elif str(row.get("Pergunta","")).strip():
                            db.add(ChecklistPerguntaVersaoMaquinas(checklist_versao_id=v.id,ordem=int(row["Ordem"]),pergunta=str(row["Pergunta"]),item_critico=bool(row["Crítico"]),ativo=bool(row["Ativo"])))
                    registrar_log(db,u,"Checklists Máquinas","ChecklistVersaoMaquinas",v.id,"editar",observacao="Perguntas atualizadas"); db.commit(); st.success("Base atualizada."); st.rerun()
                if c2.button("Criar nova versão a partir desta",use_container_width=True,key=f"nova_versao_{v.id}"):
                    nv=(db.query(ChecklistVersaoMaquinas).filter_by(tipo_checklist=v.tipo_checklist).order_by(ChecklistVersaoMaquinas.versao.desc()).first().versao or 1)+1
                    nova=ChecklistVersaoMaquinas(tipo_checklist=v.tipo_checklist,versao=nv,descricao=f"Cópia da versão {v.versao}",ativo=True,criado_por=u.nome); db.add(nova); db.flush()
                    for p in perguntas: db.add(ChecklistPerguntaVersaoMaquinas(checklist_versao_id=nova.id,ordem=p.ordem,pergunta=p.pergunta,item_critico=p.item_critico,ativo=p.ativo))
                    registrar_log(db,u,"Checklists Máquinas","ChecklistVersaoMaquinas",nova.id,"criar",observacao=f"Nova versão {nv}"); db.commit(); st.success("Nova versão criada."); st.rerun()
        with st.expander("Criar novo tipo de checklist"):
            with st.form("novo_tipo_checklist"):
                tipo=st.text_input("Nome do tipo"); desc=st.text_area("Descrição"); pergunta=st.text_area("Primeira pergunta"); crit=st.checkbox("Item crítico")
                if st.form_submit_button("Criar tipo",use_container_width=True):
                    if tipo and pergunta:
                        v=ChecklistVersaoMaquinas(tipo_checklist=tipo,versao=1,descricao=desc,ativo=True,criado_por=u.nome); db.add(v); db.flush(); db.add(ChecklistPerguntaVersaoMaquinas(checklist_versao_id=v.id,ordem=1,pergunta=pergunta,item_critico=crit,ativo=True)); registrar_log(db,u,"Checklists Máquinas","ChecklistVersaoMaquinas",v.id,"criar",observacao=tipo); db.commit(); st.success("Tipo criado."); st.rerun()
                    else: st.error("Informe tipo e primeira pergunta.")

def nr12_pac(db,u):
    header(NOME_PAC_MAQUINAS,"Planos de ação corretiva das proteções de máquinas")
    ids=visible_site_ids(u,db); sites={site_label(s.codigo):s.id for s in db.query(Site).filter(Site.id.in_(ids))}; opts=machine_options(db,ids); df=df_pac_nr12(db,ids)
    section("Consulta"); st.dataframe(df,use_container_width=True,hide_index=True) if not df.empty else empty_state("Nenhum PAC."); download_excel_button("Exportar PAC Excel","pac_protecoes_maquinas.xlsx",{"PAC":df})
    if has_permission(u,"pac_maquinas","criar") and sites:
        with st.expander("Cadastrar PAC manual"):
            with st.form("pacn_enh"):
                site=st.selectbox("Site",list(sites)); maq=st.selectbox("Máquina",["—"]+list(opts)); clas=st.selectbox("Classificação",CLASSIFICACAO_PAC); stat=st.selectbox("Status",STATUS_PAC); prazo=st.date_input("Prazo",date.today()+timedelta(days=30)); resp=st.text_input("Responsável"); area=st.text_input("Área"); desc=st.text_area("Descrição do desvio")
                if st.form_submit_button("Salvar",use_container_width=True):
                    p=PACNR12(origem="Manual",site_id=sites[site],maquina_id=None if maq=="—" else opts[maq],classificacao=clas,status=stat,prazo=prazo,responsavel=resp,area_responsavel=area,descricao_desvio=desc); db.add(p); db.flush(); registrar_log(db,u,"PAC Máquinas","PACNR12",p.id,"criar",observacao=clas); db.commit(); st.success("PAC salvo."); st.rerun()
    if has_permission(u,"pac_maquinas","editar") and not df.empty:
        with st.expander("Atualizar PAC"):
            pac_id=int(st.selectbox("Selecionar PAC",df["ID"].astype(int).tolist(),key="pac_update_enh")); p=db.get(PACNR12,pac_id)
            with st.form("editpacn_enh"):
                status_ant=p.status; novo_status=st.selectbox("Status",STATUS_PAC,index=STATUS_PAC.index(p.status) if p.status in STATUS_PAC else 0); evidencia=st.text_area("Evidência de conclusão",p.evidencia_conclusao or ""); valid=st.checkbox("Validação EHS",p.validacao_ehs); eficacia=st.text_area("Verificação de eficácia",p.verificacao_eficacia or "")
                if st.form_submit_button("Atualizar",use_container_width=True):
                    if novo_status=="Concluída" and not evidencia: st.error("PAC concluído exige evidência.")
                    elif novo_status=="Concluída" and p.classificacao=="Crítico" and not valid: st.error("PAC crítico concluído exige validação EHS.")
                    else:
                        p.status=novo_status; p.evidencia_conclusao=evidencia; p.validacao_ehs=valid; p.verificacao_eficacia=eficacia
                        if novo_status=="Concluída" and not p.data_conclusao: p.data_conclusao=date.today()
                        registrar_log(db,u,"PAC Máquinas","PACNR12",p.id,"editar","status",status_ant,novo_status); db.commit(); st.success("Atualizado."); st.rerun()

def prioridade_auditoria_nr12(db,m):
    exp=explicar_status_maquina(db,m); motivos=[]; score=0; risco=m.risco_maquina or "Apreciação de risco não realizada"; score+=PESOS_PRIORIDADE_MAQUINAS["risco"].get(risco,5); motivos.append(f"Risco: {risco}")
    if exp["status_calculado"]=="Não conforme": score+=PESOS_PRIORIDADE_MAQUINAS["status_nao_conforme"]; motivos.append("Status não conforme")
    dias=None; prazo_txt="Sem data"; prazo=m.proxima_auditoria
    if not prazo: score+=PESOS_PRIORIDADE_MAQUINAS["auditoria_vencida"]; motivos.append("Sem próxima auditoria")
    else:
        dias=(prazo-date.today()).days
        if dias<0: score+=PESOS_PRIORIDADE_MAQUINAS["auditoria_vencida"]; prazo_txt="Vencida"; motivos.append("Auditoria vencida")
        elif dias<=30: score+=PESOS_PRIORIDADE_MAQUINAS["auditoria_30d"]; prazo_txt="Até 30 dias"; motivos.append("Auditoria até 30 dias")
        elif dias<=60: score+=PESOS_PRIORIDADE_MAQUINAS["auditoria_60d"]; prazo_txt="Até 60 dias"; motivos.append("Auditoria até 60 dias")
        else: prazo_txt="Planejada"
    pac_crit=db.query(PACNR12).filter(PACNR12.maquina_id==m.id,PACNR12.classificacao=="Crítico",PACNR12.status.in_(["Aberta","Em andamento","Aguardando validação","Vencida"])).count()
    if pac_crit: score+=PESOS_PRIORIDADE_MAQUINAS["pac_critico"]; motivos.append("PAC crítico aberto")
    docs={d.tipo:d for d in db.query(DocumentoNR12).filter_by(maquina_id=m.id).all()}
    for t in DOCUMENTOS_ESSENCIAIS:
        if t not in docs: score+=PESOS_PRIORIDADE_MAQUINAS["doc_ausente"]; motivos.append(f"{t} ausente")
        elif calcular_status_documento(docs[t])=="Vencido": score+=PESOS_PRIORIDADE_MAQUINAS["doc_vencido"]; motivos.append(f"{t} vencido")
    if exp["status_calculado"]!="Conforme" and not as_date(m.data_prevista_adequacao): score+=PESOS_PRIORIDADE_MAQUINAS["sem_data_adequacao"]; motivos.append("Sem data prevista de adequação")
    moc=db.query(MOCNR12).filter(MOCNR12.maquina_id==m.id,MOCNR12.exige_moc==True,MOCNR12.validacao_final==False).count()
    if moc: score+=PESOS_PRIORIDADE_MAQUINAS["moc_sem_validacao"]; motivos.append("MOC crítica sem validação")
    reinc=db.query(PACNR12).filter(PACNR12.maquina_id==m.id).count()
    if reinc>2: score+=min(30,reinc*PESOS_PRIORIDADE_MAQUINAS["reincidencia_pac"]); motivos.append(f"Reincidência de PAC: {reinc}")
    prioridade="Crítica" if score>=150 else "Alta" if score>=100 else "Média" if score>=55 else "Baixa"
    return score,prioridade,prazo_txt,dias,risco,"; ".join(motivos),exp["recomendacao"]

def nr12_central_pendencias(db,u):
    header("Central de Pendências","Priorização explicável por risco, documentos, PAC, MOC e prazos")
    ids=visible_site_ids(u,db); rows=[]
    for m in db.query(MaquinaNR12).filter(MaquinaNR12.site_id.in_(ids)).all():
        score,prioridade,prazo_txt,dias,risco,motivo,rec=prioridade_auditoria_nr12(db,m); cod=site_code_raw(db,m.site_id)
        rows.append({"Prioridade":prioridade,"Score":score,"Site":site_label(cod),"Código site":cod,"Grupo":site_grupo(cod),"Código":m.codigo,"Máquina":m.nome,"Responsável":m.responsavel_area,"Risco":risco,NOME_STATUS_PROTECAO:calcular_status_maquina_nr12(db,m),"Próxima auditoria":fmt_date(m.proxima_auditoria),"Dias para vencer":dias if dias is not None else "—","Situação do prazo":prazo_txt,"Motivo do score":motivo,"Ação recomendada":rec})
    df=pd.DataFrame(rows).sort_values("Score",ascending=False) if rows else pd.DataFrame()
    if df.empty: empty_state("Nenhuma máquina cadastrada."); return
    with st.expander("Filtros",expanded=True):
        c1,c2,c3,c4=st.columns(4); unidade=c1.multiselect("Unidade",sorted(df["Site"].unique())); grupo=c2.multiselect("Grupo",sorted(df["Grupo"].unique())); risco=c3.multiselect("Risco",[r for r in RISCOS_MAQUINA if r in set(df["Risco"].dropna())]); prioridade=c4.multiselect("Prioridade",[p for p in ["Crítica","Alta","Média","Baixa"] if p in set(df["Prioridade"].dropna())])
    if unidade: df=df[df["Site"].isin(unidade)]
    if grupo: df=df[df["Grupo"].isin(grupo)]
    if risco: df=df[df["Risco"].isin(risco)]
    if prioridade: df=df[df["Prioridade"].isin(prioridade)]
    st.dataframe(df,use_container_width=True,hide_index=True)
    download_excel_button("Exportar central de pendências","central_pendencias_protecoes_maquinas.xlsx",{"Pendências":df})

def nr12_moc(db,u):
    header(NOME_MOC_MAQUINAS,"Mudanças críticas, aprovações e validação final")
    ids=visible_site_ids(u,db); sites={site_label(s.codigo):s.id for s in db.query(Site).filter(Site.id.in_(ids))}; opts=machine_options(db,ids)
    if has_permission(u,"moc_maquinas","criar") and sites:
        with st.expander("Cadastrar MOC"):
            with st.form("moc_enh"):
                a,b,c=st.columns(3); site=a.selectbox("Site",list(sites)); maq=a.selectbox("Máquina",["—"]+list(opts)); tipo=a.selectbox("Tipo de mudança",TIPOS_MUDANCA); solic=b.text_input("Solicitante",u.nome); area=b.text_input("Área solicitante"); status=b.selectbox("Status",STATUS_MOC); imp=c.checkbox("Impacta segurança?",tipo in TIPOS_MUDANCA_CRITICA); exige=c.checkbox("Exige MOC?",tipo in TIPOS_MUDANCA_CRITICA or imp); val=c.checkbox("Validação final"); ehs=st.checkbox("Aprovação EHS"); man=st.checkbox("Aprovação Manutenção"); eng=st.checkbox("Aprovação Engenharia"); prod=st.checkbox("Aprovação Produção"); aud=st.checkbox("Necessita auditoria pós-mudança?"); tre=st.checkbox("Necessita treinamento?"); desc=st.text_area("Descrição"); obs=st.text_area("Observações")
                if st.form_submit_button("Salvar MOC",use_container_width=True):
                    crit=tipo in TIPOS_MUDANCA_CRITICA or imp
                    if crit and (not exige or (status in ["Aprovada","Implementada","Validada"] and (not ehs or not (man or eng)))): st.error("Mudança crítica exige MOC, aprovação EHS e aprovação de Manutenção ou Engenharia.")
                    else:
                        mid=None if maq=="—" else opts[maq]; obj=MOCNR12(site_id=sites[site],maquina_id=mid,tipo_mudanca=tipo,descricao=desc,solicitante=solic,area_solicitante=area,data=date.today(),impacta_seguranca=imp,exige_moc=exige,status=status,aprovacao_ehs=ehs,aprovacao_manutencao=man,aprovacao_engenharia=eng,aprovacao_producao=prod,necessita_auditoria_pos_mudanca=aud,necessita_treinamento=tre,observacoes=obs,validacao_final=val); db.add(obj); db.flush()
                        if mid and crit and status=="Implementada" and not val: db.get(MaquinaNR12,mid).status_nr12="Não conforme"
                        registrar_log(db,u,"MOC Máquinas","MOCNR12",obj.id,"criar",observacao=tipo); db.commit(); st.success("MOC salva."); st.rerun()
    df=df_moc(db,ids); section("MOCs registradas"); st.dataframe(df,use_container_width=True,hide_index=True) if not df.empty else empty_state("Nenhuma MOC."); download_excel_button("Exportar MOC Excel","moc_protecoes_maquinas.xlsx",{"MOC":df})

def nr12_calendario(db,u):
    header("Calendário de Auditorias e Inspeções","Visão mensal, próximos vencimentos e histórico de verificações")
    ids=visible_site_ids(u,db); rows=[]
    for m in db.query(MaquinaNR12).filter(MaquinaNR12.site_id.in_(ids)).all():
        cod=site_code_raw(db,m.site_id)
        if m.proxima_auditoria: rows.append({"Data":m.proxima_auditoria,"Tipo":"Próxima auditoria de máquina","Site":site_label(cod),"Grupo":site_grupo(cod),"Responsável":m.responsavel_area,"Status":"Vencida" if m.proxima_auditoria<date.today() else "Prevista","Referência":m.codigo,"Descrição":m.nome})
        if m.ultima_auditoria: rows.append({"Data":m.ultima_auditoria,"Tipo":"Última auditoria de máquina","Site":site_label(cod),"Grupo":site_grupo(cod),"Responsável":m.responsavel_area,"Status":"Realizada","Referência":m.codigo,"Descrição":m.nome})
    for v in db.query(VerificacaoNR12).filter(VerificacaoNR12.site_id.in_(ids)).all():
        cod=site_code_raw(db,v.site_id); rows.append({"Data":v.data_verificacao,"Tipo":v.tipo,"Site":site_label(cod),"Grupo":site_grupo(cod),"Responsável":v.responsavel,"Status":v.resultado,"Referência":v.maquina.codigo if v.maquina else f"Verificação {v.id}","Descrição":v.observacoes})
    df=pd.DataFrame(rows)
    if df.empty: empty_state("Sem eventos de auditoria ou inspeção."); return
    with st.expander("Filtros",expanded=True):
        c1,c2,c3,c4=st.columns(4); site=c1.multiselect("Site",sorted(df["Site"].dropna().unique())); grupo=c2.multiselect("Grupo",sorted(df["Grupo"].dropna().unique())); status=c3.multiselect("Status",sorted(df["Status"].dropna().unique())); tipo=c4.multiselect("Tipo",sorted(df["Tipo"].dropna().unique()))
    if site: df=df[df["Site"].isin(site)]
    if grupo: df=df[df["Grupo"].isin(grupo)]
    if status: df=df[df["Status"].isin(status)]
    if tipo: df=df[df["Tipo"].isin(tipo)]
    df["Mês"]=pd.to_datetime(df["Data"]).dt.to_period("M").astype(str)
    tab1,tab2,tab3=st.tabs(["Visão mensal","Por site/responsável","Próximos vencimentos"])
    with tab1:
        gm=df.groupby(["Mês","Status"],as_index=False).size().rename(columns={"size":"Quantidade"}); st.plotly_chart(px.bar(gm,x="Mês",y="Quantidade",color="Status",barmode="group",title="Calendário mensal").update_layout(template="plotly_white"),use_container_width=True); st.dataframe(df.sort_values("Data"),use_container_width=True,hide_index=True)
    with tab2:
        gs=df.groupby(["Site","Tipo"],as_index=False).size().rename(columns={"size":"Quantidade"}); st.plotly_chart(px.bar(gs,x="Site",y="Quantidade",color="Tipo",barmode="group",title="Eventos por site e tipo").update_layout(template="plotly_white"),use_container_width=True)
    with tab3:
        prox=df[(pd.to_datetime(df["Data"]).dt.date>=date.today()) & (pd.to_datetime(df["Data"]).dt.date<=date.today()+timedelta(days=90))].sort_values("Data"); st.dataframe(prox,use_container_width=True,hide_index=True)
    download_excel_button("Exportar calendário","calendario_auditorias_inspecoes.xlsx",{"Calendário":df})

def nr12_relatorios(db,u):
    header(NOME_RELATORIOS_MAQUINAS,"Exportações em Excel e PDFs")
    ids=visible_site_ids(u,db); d={"Inventário":df_maquinas(db,ids),"Documentos":df_docs(db,ids),"Verificações":df_ver(db,ids),"PAC":df_pac_nr12(db,ids),"MOC":df_moc(db,ids)}
    download_excel_button("Pacote Proteções de Máquinas Excel","pacote_protecoes_maquinas.xlsx",d)
    opts=machine_options(db,ids)
    if opts:
        lab=st.selectbox("Relatório PDF por máquina",list(opts)); m=db.get(MaquinaNR12,opts[lab]); exp=explicar_status_maquina(db,m)
        dados=df_maquinas(db,[m.site_id]); dados=dados[dados["ID"]==m.id]
        docs=df_docs(db,[m.site_id]); pacs=df_pac_nr12(db,[m.site_id]); pacs=pacs[pacs["Máquina"]==m.codigo] if not pacs.empty else pacs
        vers=pd.DataFrame([{"ID":v.id,"Tipo":v.tipo,"Data":fmt_date(v.data_verificacao),"Responsável":v.responsavel,"Resultado":v.resultado,"Pontuação %":v.pontuacao,"NC crítica":"Sim" if v.possui_nc_critica else "Não","Próxima":fmt_date(v.proxima_verificacao),"Observações":v.observacoes} for v in db.query(VerificacaoNR12).filter_by(maquina_id=m.id).order_by(VerificacaoNR12.data_verificacao.desc())])
        justificativa=pd.DataFrame([{"Status calculado":exp["status_calculado"],"Motivos":"; ".join(exp["motivos"]),"Bloqueios críticos":"; ".join(exp["bloqueios_criticos"]),"Recomendação":exp["recomendacao"]}])
        pdf=gerar_pdf(f"Relatório por Máquina — {m.codigo}",f"{m.nome} | Site {site_code(db,m.site_id)}",[("Dados",dados),("Justificativa do Status de Proteção",justificativa),("Auditorias e verificações realizadas",vers),("Documentos",docs),("PACs",pacs)])
        download_pdf_button("Baixar relatório por máquina PDF",f"relatorio_maquina_{m.codigo}.pdf",pdf)

def qualidade_dados_page(db,u):
    header("Qualidade dos Dados","Painel de inconsistências, lacunas e priorização de saneamento da base")
    ids=visible_site_ids(u,db); score,df=calcular_qualidade_dados(db,ids)
    cols=st.columns(4); cols[0].metric("Score de qualidade",f"{score}%"); cols[1].metric("Inconsistências",len(df)); cols[2].metric("Alta prioridade",int((df["Prioridade"]=="Alta").sum()) if not df.empty else 0); cols[3].metric("Sites afetados",df["Site"].nunique() if not df.empty else 0)
    if df.empty: empty_state("Nenhuma inconsistência encontrada."); return
    with st.expander("Filtros",expanded=True):
        c1,c2,c3,c4=st.columns(4); modulo=c1.multiselect("Módulo",sorted(df["Módulo"].unique())); site=c2.multiselect("Site",sorted(df["Site"].unique())); pri=c3.multiselect("Prioridade",sorted(df["Prioridade"].unique())); tipo=c4.multiselect("Tipo",sorted(df["Tipo"].unique()))
    f=df.copy()
    if modulo: f=f[f["Módulo"].isin(modulo)]
    if site: f=f[f["Site"].isin(site)]
    if pri: f=f[f["Prioridade"].isin(pri)]
    if tipo: f=f[f["Tipo"].isin(tipo)]
    c1,c2=st.columns(2)
    with c1: st.plotly_chart(px.bar(f.groupby("Tipo",as_index=False).size().rename(columns={"size":"Quantidade"}),x="Tipo",y="Quantidade",color="Tipo",title="Pendências por tipo").update_layout(template="plotly_white",showlegend=False),use_container_width=True)
    with c2: st.plotly_chart(px.bar(f.groupby("Site",as_index=False).size().rename(columns={"size":"Quantidade"}),x="Site",y="Quantidade",color="Site",title="Pendências por site").update_layout(template="plotly_white",showlegend=False),use_container_width=True)
    st.dataframe(f,use_container_width=True,hide_index=True); download_excel_button("Exportar qualidade dos dados","qualidade_dados_ehs.xlsx",{"Qualidade":f})

def dicionario_dados_page(db,u):
    header("Dicionário de Dados","Definições, fontes, regras de cálculo, periodicidade e responsáveis sugeridos")
    rows=[
        ("Máquina","Equipamento ou sistema produtivo controlado no inventário.","Máquinas","Inventário","Cadastro mestre por código único.","Sempre que houver inclusão/alteração","Manutenção/EHS Local"),
        ("Site","Unidade produtiva padronizada pelo master de sites.","Todos","Cadastro de sites","Código interno convertido para nome padrão.","Na implantação e quando houver alteração organizacional","Admin LAG"),
        ("Grupo","Agrupamento regional/divisional do site.","Todos","SITES_INFO","MSG, EMG, Filtration, FCG.","Na implantação","Admin LAG"),
        ("Status de Proteção","Status calculado da condição de proteção da máquina.","Máquinas","Inventário, documentos, PAC, MOC","Conforme quando não há pendências críticas; não conforme quando há documento essencial ausente/vencido, PAC crítico, MOC sem validação ou status declarado não conforme.","Contínuo","EHS/Manutenção"),
        ("Risco da Máquina","Classificação de risco da máquina após apreciação.","Máquinas","Inventário/Apreciação de risco","Desprezível, Atenção, Significativo, Alto, Extremo ou não realizada.","Após apreciação e revisões","EHS/Engenharia"),
        ("Criticidade","Prioridade operacional/EHS da máquina ou requisito.","Máquinas/Auditoria","Cadastro","Alta, Média ou Baixa.","Revisão periódica","EHS Local"),
        ("Documento essencial","Documentos mínimos para sustentar condição de proteção.","Documentos","Uploads","Laudo NR-12, ART e Apreciação de risco.","Conforme validade","EHS/Manutenção"),
        ("PAC","Plano de ação corretiva/preventiva para desvios.","PAC","Checklists/Auditorias/Manual","Gerado manualmente ou automaticamente por não conformidade.","Contínuo","Responsável da ação"),
        ("Classificação do PAC","Severidade do plano de ação.","PAC","Cadastro do PAC","Crítico, Maior ou Menor.","Na abertura","EHS"),
        ("Status do PAC","Etapa de tratamento da ação.","PAC","Atualização do PAC","Aberta, Em andamento, Aguardando validação, Concluída, Vencida, Cancelada.","Contínuo","Responsável da ação"),
        ("MOC","Gestão de mudança com potencial impacto em segurança.","MOC","Formulário MOC","Mudanças críticas exigem aprovações e validação final.","Sempre que houver mudança","Engenharia/Manutenção/EHS"),
        ("Auditoria Cruzada","Avaliação de diretrizes EHS entre sites.","Auditoria EHS","Planejamento","Ciclo de auditoria com checklist, maturidade, evidência e PAC.","Por ciclo","EHS/Auditores"),
        ("Conformidade %","Percentual de atendimento aos requisitos aplicáveis.","Auditoria EHS","Respostas","Conforme=1, Parcial=0,5, Não Conforme=0, dividido por aplicáveis.","A cada auditoria","Auditor líder"),
        ("Maturidade","Nota média de maturidade dos requisitos aplicáveis.","Auditoria EHS","Respostas","Média das notas 0 a 5.","A cada auditoria","Auditor líder"),
        ("Gaps","Achados, não conformidades ou oportunidades.","Auditoria EHS/PAC","Checklist/PAC","Itens parciais, não conformes ou PACs gerados.","A cada auditoria","EHS"),
        ("Evidência","Registro que comprova atendimento ou execução.","Todos","Uploads/textos","Pode ser documento, foto, entrevista, registro ou verificação em campo.","Contínuo","Responsável pelo processo"),
        ("Verificação de eficácia","Confirma se ação eliminou ou reduziu o risco.","PAC","Atualização do PAC","Descrição da validação pós-conclusão.","Após conclusão","EHS"),
        ("Próxima auditoria","Data planejada para próxima verificação da máquina.","Máquinas","Inventário/Checklist","Atualizada no cadastro e após verificações.","Conforme criticidade","EHS/Manutenção"),
        ("Data prevista de adequação","Prazo de regularização de máquina não conforme.","Máquinas","Inventário","Obrigatória quando status declarado não conforme.","Até adequação","Responsável da área"),
    ]
    df=pd.DataFrame(rows,columns=["Campo/Indicador","Definição","Módulo","Origem/Fonte","Regra de cálculo","Periodicidade","Responsável sugerido"])
    st.dataframe(df,use_container_width=True,hide_index=True); download_excel_button("Exportar dicionário de dados","dicionario_dados_ehs.xlsx",{"Dicionário":df})

def logs_sistema_page(db,u):
    header("Logs do Sistema","Trilha de auditoria das principais ações realizadas no app")
    if not can_admin(u): alert_card("Página restrita a Admin_LAG."); return
    df=df_logs(db)
    if df.empty: empty_state("Nenhum log registrado."); return
    with st.expander("Filtros",expanded=True):
        c1,c2,c3=st.columns(3); usuario=c1.multiselect("Usuário",sorted(df["Usuário"].dropna().unique())); modulo=c2.multiselect("Módulo",sorted(df["Módulo"].dropna().unique())); entidade=c3.multiselect("Entidade",sorted(df["Entidade"].dropna().unique()))
    f=df.copy()
    if usuario: f=f[f["Usuário"].isin(usuario)]
    if modulo: f=f[f["Módulo"].isin(modulo)]
    if entidade: f=f[f["Entidade"].isin(entidade)]
    st.dataframe(f,use_container_width=True,hide_index=True); download_excel_button("Exportar logs","logs_sistema.xlsx",{"Logs":f})

def ehs_dashboard(db,u):
    header("Auditoria Cruzada de Diretrizes de EHS","Dashboard de planejamento, conformidade, maturidade, gaps e plano de ação regional")
    ids=visible_site_ids(u,db); da=df_aud(db,ids); dp=df_pac_ehs(db,ids)
    vals=[(da["Status"]=="Planejada").sum() if not da.empty else 0,(da["Status"]=="Em andamento").sum() if not da.empty else 0,(da["Status"]=="Concluída").sum() if not da.empty else 0,round(da["Conformidade %"].mean(),1) if not da.empty else 0,round(da["Maturidade"].mean(),2) if not da.empty else 0,(dp["Status"].isin(["Aberta","Em andamento","Aguardando validação"])).sum() if not dp.empty else 0,(dp["Status"]=="Vencida").sum() if not dp.empty else 0,(dp["Tipo de achado"]=="Não conformidade crítica").sum() if not dp.empty else 0]
    labs=["Auditorias planejadas","Em andamento","Concluídas","Conformidade média","Maturidade média","PACs abertos","PACs vencidos","NC críticas"]
    for base in range(0,8,4):
        cols=st.columns(4)
        for c,i in zip(cols,range(base,base+4)):
            with c: kpi_card(labs[i],f"{vals[i]}%" if i==3 else vals[i])
    tab1,tab2,tab3=st.tabs(["Resumo","Maturidade e gaps","Plano regional"])
    with tab1:
        c1,c2=st.columns(2)
        with c1:
            if not da.empty: st.plotly_chart(px.bar(da,x="Site auditado",y="Conformidade %",color="Conformidade %",title="Conformidade por site").update_layout(template="plotly_white",yaxis_range=[0,100]),use_container_width=True)
            else: empty_state("Sem auditorias.")
        with c2:
            if not dp.empty: st.plotly_chart(px.histogram(dp,x="Status",color="Prioridade",barmode="group",title="PACs por status e prioridade").update_layout(template="plotly_white"),use_container_width=True)
            else: empty_state("Sem PACs.")
    with tab2:
        respostas=[]
        for a in db.query(AuditoriaCruzada).filter(AuditoriaCruzada.site_auditado_id.in_(ids)).all():
            for r in db.query(RespostaAuditoriaEHS).filter_by(auditoria_id=a.id).all():
                respostas.append({"Auditoria":a.id,"Site":site_code(db,a.site_auditado_id),"Ciclo":a.ciclo,"Categoria":r.requisito.diretiva.categoria if r.requisito and r.requisito.diretiva else "—","Status":r.status,"Maturidade":r.nota_maturidade})
        dfr=pd.DataFrame(respostas)
        c1,c2=st.columns(2)
        with c1:
            if not dfr.empty:
                mat=dfr.groupby("Categoria",as_index=False)["Maturidade"].mean(); st.plotly_chart(px.bar(mat,x="Categoria",y="Maturidade",color="Maturidade",title="Matriz de maturidade por categoria").update_layout(template="plotly_white",yaxis_range=[0,5]),use_container_width=True)
            else: empty_state("Sem respostas para maturidade.")
        with c2:
            if not dp.empty:
                gaps=dp.groupby("Categoria",as_index=False).size().rename(columns={"size":"Quantidade"}).sort_values("Quantidade",ascending=False); st.plotly_chart(px.bar(gaps.head(10),x="Categoria",y="Quantidade",color="Quantidade",title="Top gaps por categoria").update_layout(template="plotly_white",showlegend=False),use_container_width=True)
            else: empty_state("Sem gaps.")
        if not dfr.empty:
            heat=dfr.pivot_table(index="Categoria",columns="Site",values="Maturidade",aggfunc="mean").reset_index()
            st.dataframe(heat,use_container_width=True,hide_index=True)
    with tab3:
        if not dp.empty:
            st.dataframe(dp.sort_values(["Status","Prioridade","Site"]),use_container_width=True,hide_index=True)
        else: empty_state("Nenhum plano regional registrado.")

def ehs_relatorios(db,u):
    header("Relatórios Auditoria Cruzada","Exportações em Excel e PDF")
    ids=visible_site_ids(u,db); da=df_aud(db,ids); dp=df_pac_ehs(db,ids)
    respostas=[]
    for a in db.query(AuditoriaCruzada).filter(AuditoriaCruzada.site_auditado_id.in_(ids)).all():
        for r in db.query(RespostaAuditoriaEHS).filter_by(auditoria_id=a.id).all():
            respostas.append({"Auditoria":a.id,"Site":site_code(db,a.site_auditado_id),"Ciclo":a.ciclo,"Categoria":r.requisito.diretiva.categoria if r.requisito and r.requisito.diretiva else "—","Requisito":r.requisito.pergunta if r.requisito else "—","Status":r.status,"Maturidade":r.nota_maturidade,"Evidência":r.evidencia_verificada,"Comentário":r.comentario_auditor})
    dfr=pd.DataFrame(respostas)
    mat=dfr.groupby(["Site","Categoria"],as_index=False)["Maturidade"].mean() if not dfr.empty else pd.DataFrame()
    gaps=dp.groupby("Categoria",as_index=False).size().rename(columns={"size":"Quantidade"}) if not dp.empty else pd.DataFrame()
    resumo=pd.DataFrame([{"Indicador":"Auditorias","Valor":len(da)},{"Indicador":"Conformidade média","Valor":round(da["Conformidade %"].mean(),1) if not da.empty else 0},{"Indicador":"Maturidade média","Valor":round(da["Maturidade"].mean(),2) if not da.empty else 0},{"Indicador":"PACs abertos/vencidos","Valor":int(dp["Status"].isin(["Aberta","Em andamento","Vencida"]).sum()) if not dp.empty else 0}])
    boas=dfr[dfr["Status"]=="Conforme"].head(50) if not dfr.empty else pd.DataFrame()
    download_excel_button("Pacote Auditoria Excel","auditoria_cruzada_ehs.xlsx",{"Resumo_Executivo":resumo,"Auditorias":da,"Respostas":dfr,"Maturidade_por_Categoria":mat,"Gaps_por_Categoria":gaps,"PAC_EHS":dp,"Boas_Praticas":boas})
    auds=db.query(AuditoriaCruzada).filter(AuditoriaCruzada.site_auditado_id.in_(ids)).order_by(AuditoriaCruzada.id.desc()).all()
    if auds:
        amap={f"{a.id} — {site_code(db,a.site_auditado_id)} — {a.ciclo}":a.id for a in auds}; a=db.get(AuditoriaCruzada,amap[st.selectbox("Relatório PDF",list(amap))]); res=db.query(RespostaAuditoriaEHS).filter_by(auditoria_id=a.id).all(); dfa=pd.DataFrame([{"Categoria":r.requisito.diretiva.categoria,"Requisito":r.requisito.pergunta,"Status":r.status,"Maturidade":r.nota_maturidade,"Evidência":r.evidencia_verificada,"Comentário":r.comentario_auditor} for r in res])
        pdf=gerar_pdf(f"Relatório de Auditoria Cruzada de Diretrizes de EHS — {site_code(db,a.site_auditado_id)}",f"Auditoria {a.id} | {a.ciclo} | Conformidade {calcular_conformidade_ehs(res)}% | Maturidade {calcular_maturidade_ehs(res)}",[("Dados",pd.DataFrame([{"Ano":a.ano,"Ciclo":a.ciclo,"Site":site_code(db,a.site_auditado_id),"Status":a.status,"Auditor líder":a.auditor_lider}])),("Resultado por item",dfa),("PACs vinculados",dp[dp["Auditoria"]==a.id] if not dp.empty else dp)])
        download_pdf_button("Baixar relatório de auditoria PDF",f"relatorio_auditoria_ehs_{a.id}.pdf",pdf)

def render_sidebar(db,u):
    mod=st.session_state.get("modulo","home")
    if mod=="home": return
    st.sidebar.markdown("### Navegação")
    if st.sidebar.button("🏠 Voltar para a tela inicial",use_container_width=True): st.session_state.modulo="home"; st.rerun()
    st.sidebar.divider()
    if mod=="nr12":
        pages=[NOME_DASH_MAQUINAS,"Central de Pendências","Calendário de Auditorias e Inspeções","Inventário de Máquinas",NOME_DOCS_MAQUINAS,"Checklists e Inspeções",NOME_BASE_CHECKLISTS_MAQUINAS,NOME_PAC_MAQUINAS,NOME_MOC_MAQUINAS,"Qualidade dos Dados","Dicionário de Dados",NOME_RELATORIOS_MAQUINAS]
        if can_admin(u): pages.append("Logs do Sistema")
        current=st.session_state.get("page_nr12",pages[0]); current=current if current in pages else pages[0]
        if st.session_state.get("nav_nr12") not in pages: st.session_state.nav_nr12=current
        selected=st.sidebar.radio(NOME_MODULO_MAQUINAS,pages,key="nav_nr12"); st.session_state.page_nr12=selected
    elif mod=="ehs":
        pages=["Dashboard Auditoria Cruzada","Planejamento de Auditorias","Checklist Diretrizes de EHS","PAC Auditoria Cruzada","Base do Checklist EHS","Qualidade dos Dados","Dicionário de Dados","Relatórios Auditoria Cruzada"]
        if can_admin(u): pages.append("Logs do Sistema")
        current=st.session_state.get("page_ehs",pages[0]); current=current if current in pages else pages[0]
        if st.session_state.get("nav_ehs") not in pages: st.session_state.nav_ehs=current
        selected=st.sidebar.radio("Auditoria Cruzada de Diretrizes de EHS",pages,key="nav_ehs"); st.session_state.page_ehs=selected

def route(db,u):
    mod=st.session_state.get("modulo","home")
    if mod=="home": home_page(db,u)
    elif mod=="nr12":
        pages={NOME_DASH_MAQUINAS:nr12_dashboard,"Central de Pendências":nr12_central_pendencias,"Calendário de Auditorias e Inspeções":nr12_calendario,"Inventário de Máquinas":nr12_inventario,NOME_DOCS_MAQUINAS:nr12_documentos,"Checklists e Inspeções":nr12_checklists,NOME_BASE_CHECKLISTS_MAQUINAS:nr12_base_checklists,NOME_PAC_MAQUINAS:nr12_pac,NOME_MOC_MAQUINAS:nr12_moc,"Qualidade dos Dados":qualidade_dados_page,"Dicionário de Dados":dicionario_dados_page,NOME_RELATORIOS_MAQUINAS:nr12_relatorios,"Logs do Sistema":logs_sistema_page}
        pages.get(st.session_state.get("page_nr12",NOME_DASH_MAQUINAS),nr12_dashboard)(db,u)
    elif mod=="ehs":
        pages={"Dashboard Auditoria Cruzada":ehs_dashboard,"Planejamento de Auditorias":ehs_planejamento,"Checklist Diretrizes de EHS":ehs_checklist,"PAC Auditoria Cruzada":ehs_pac,"Base do Checklist EHS":ehs_base_checklist,"Qualidade dos Dados":qualidade_dados_page,"Dicionário de Dados":dicionario_dados_page,"Relatórios Auditoria Cruzada":ehs_relatorios,"Logs do Sistema":logs_sistema_page}
        pages.get(st.session_state.get("page_ehs","Dashboard Auditoria Cruzada"),ehs_dashboard)(db,u)

# ============================================================
# 16. main()
# ============================================================
def main():
    if "modulo" not in st.session_state:
        st.session_state.modulo="home"
    apply_theme(); hide_sidebar_on_home(); init_db(); db=SessionLocal()
    try:
        location="main" if st.session_state.get("modulo","home")=="home" else "sidebar"
        u=user_selector(db,location=location)
        render_sidebar(db,u)
        route(db,u)
    finally:
        db.close()
if __name__=="__main__": main()
