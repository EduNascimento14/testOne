

import os, io, re, math, unicodedata, logging, calendar, json, zlib, base64
from datetime import date, datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from sqlalchemy import create_engine, Column, Integer, String, Text, Date, DateTime, Boolean, Float, ForeignKey, UniqueConstraint, LargeBinary, inspect
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

st.set_page_config(page_title="Plataforma Integrada EHS", page_icon="🛡️", layout="wide")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///plataforma_ehs_integrada.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

NOME_MODULO_MAQUINAS = "Sustentação de Proteções de Máquinas"
NOME_DASH_MAQUINAS = "Dashboard de Proteções de Máquinas"
NOME_STATUS_MAQUINA = "Status de Proteção"
NOME_PAC_MAQUINAS = "Plano de Ação - Proteções de Máquinas"
NOME_DOCS_MAQUINAS = "Documentos de Proteções de Máquinas"
NOME_CHECKLISTS_MAQUINAS = "Checklists e Inspeções de Proteções de Máquinas"
NOME_RELATORIOS_MAQUINAS = "Relatórios de Proteções de Máquinas"
NOME_TERMO_MAQUINAS = "Termo de Garantia de Proteções de Máquinas"

SITES_PADRAO = ["SJC", "DIA", "CAC", "JAC", "JUN", "PER"]
SITES_LAG = {
    "CAC": {"nome": "MSG Br CAC - Cachoeirinha", "nome_curto": "Cachoeirinha", "grupo": "MSG", "divisao": "MSG Br"},
    "JAC": {"nome": "MSG Br JAC - Jacareí", "nome_curto": "Jacareí", "grupo": "MSG", "divisao": "MSG Br"},
    "JUN": {"nome": "EMG Br JU - Jundiaí", "nome_curto": "Jundiaí", "grupo": "EMG", "divisao": "EMG Br"},
    "PER": {"nome": "EMG Br SP - Perus", "nome_curto": "Perus", "grupo": "EMG", "divisao": "EMG Br"},
    "SJC": {"nome": "Filtration Br - São José dos Campos", "nome_curto": "São José dos Campos", "grupo": "Filtration", "divisao": "Filtration Br"},
    "DIA": {"nome": "FCG Br - Diadema", "nome_curto": "Diadema", "grupo": "FCG", "divisao": "FCG Br"},
    "Corporativo": {"nome": "Corporativo", "nome_curto": "Corporativo", "grupo": "Corporativo", "divisao": "Corporativo"},
}
SITE_INFO_PADRAO = SITES_LAG
SITE_NOMES_PADRAO = {k: v["nome"] for k, v in SITE_INFO_PADRAO.items()}
SITE_GRUPOS_PADRAO = {k: v["grupo"] for k, v in SITE_INFO_PADRAO.items()}
SITE_DIVISOES_PADRAO = {k: v.get("divisao", v.get("grupo", k)) for k, v in SITE_INFO_PADRAO.items()}
PERFIS = ["Admin_LAG","EHS_Local","Auditor","Manutencao","Producao_Operacao","Engenharia","Responsavel_Acao","Visualizador"]
USUARIOS_PADRAO = [
    ("Eduardo","Admin_LAG","Corporativo"), ("Capitu","Admin_LAG","Corporativo"),
    ("EHS SJC","EHS_Local","SJC"), ("Manutenção SJC","Manutencao","SJC"),
    ("Produção SJC","Producao_Operacao","SJC"), ("Auditor EHS","Auditor","Corporativo")
]
STATUS_MAQUINA = ["Conforme","Não conforme"]
CRITICIDADES = ["Alta","Média","Baixa"]
TIPOS_FREQUENCIA_MAQUINAS = ["Checklist operacional","Inspeção de manutenção","Auditoria EHS","Auditoria corporativa","Auditoria extraordinária após incidente/quase-acidente"]
REGRAS_FREQUENCIA_DEFAULT = {
    "Checklist operacional": {"Alta": 7, "Média": 15, "Baixa": 30},
    "Inspeção de manutenção": {"Alta": 30, "Média": 90, "Baixa": 180},
    "Auditoria EHS": {"Alta": 180, "Média": 365, "Baixa": 730},
    "Auditoria corporativa": {"Alta": 180, "Média": 365, "Baixa": 730},
    "Auditoria extraordinária após incidente/quase-acidente": {"Alta": 0, "Média": 0, "Baixa": 0},
}
MODULO_COLOR_MAP = {
    "maquinas": {"border": "#2563eb", "bg": "#eff6ff", "icon": "⚙️"},
    "energia": {"border": "#16a34a", "bg": "#ecfdf5", "icon": "⚡"},
    "auditoria": {"border": "#7c3aed", "bg": "#f5f3ff", "icon": "🧭"},
    "nearmiss": {"border": "#f97316", "bg": "#fff7ed", "icon": "⚠️"},
}
NR12_HOME_PAGE = "Submódulos da Sustentação"
NR12_SUBMODULOS = {
    "Gestão e Performance": {
        "icone": "📊",
        "descricao": "Indicadores, visão executiva e relatórios consolidados.",
        "cor": "#2563eb",
        "paginas": [NOME_DASH_MAQUINAS, NOME_RELATORIOS_MAQUINAS],
    },
    "Inventário e Documentação": {
        "icone": "🏭",
        "descricao": "Cadastro das máquinas, documentos técnicos, evidências e validade.",
        "cor": "#0f766e",
        "paginas": ["Inventário de Máquinas", NOME_DOCS_MAQUINAS],
    },
    "Inspeções e Auditorias": {
        "icone": "✅",
        "descricao": "Execução de checklists, histórico de inspeções e calendário.",
        "cor": "#ea580c",
        "paginas": ["Checklists e Inspeções", "Calendário de Auditorias e Inspeções"],
    },
    "Gestão de Pendências": {
        "icone": "🛠️",
        "descricao": "Pendências priorizadas e planos de ação corretiva.",
        "cor": "#dc2626",
        "paginas": ["Central de Pendências", NOME_PAC_MAQUINAS],
    },
    "Administração e Governança": {
        "icone": "⚙️",
        "descricao": "Logs, base de checklists e regras de frequência por criticidade.",
        "cor": "#475569",
        "paginas": ["Logs do Sistema", "Base de Checklists de Proteções", "Regras de Frequência de Inspeções"],
    },
}
EHS_HOME_PAGE = "Submódulos da Auditoria Cruzada"
EHS_SUBMODULOS = {
    "Gestão e Performance": {
        "icone": "📊",
        "descricao": "Indicadores executivos, maturidade, conformidade e relatórios consolidados da auditoria cruzada.",
        "cor": "#7c3aed",
        "paginas": ["Dashboard Auditoria Cruzada", "Relatórios Auditoria Cruzada"],
    },
    "Planejamento e Execução": {
        "icone": "📋",
        "descricao": "Planejamento dos ciclos de auditoria, calendário, execução do checklist e registro das evidências.",
        "cor": "#2563eb",
        "paginas": ["Planejamento de Auditorias", "Calendário de Auditorias", "Checklist Diretrizes de EHS"],
    },
    "Gestão de Gaps e Planos de Ação": {
        "icone": "⚠️",
        "descricao": "Tratamento dos gaps encontrados, planos de ação, prazos, responsáveis e eficácia.",
        "cor": "#dc2626",
        "paginas": ["PAC Auditoria Cruzada"],
    },
    "Administração e Governança": {
        "icone": "⚙️",
        "descricao": "Base editável do checklist EHS, versionamento e trilha de auditoria do sistema.",
        "cor": "#475569",
        "paginas": ["Base do Checklist EHS", "Logs do Sistema"],
    },
}

ENERGIA_HOME_PAGE = "Submódulos de Energia e Emissões"
AJUDA_PAGE = "Ajuda rápida"
ENERGIA_SUBMODULOS = {
    "Gestão e Performance": {
        "icone": "📊",
        "descricao": "Dashboard executivo, indicadores, CO₂, eficiência energética e tabela executiva.",
        "cor": "#16a34a",
        "paginas": ["Dashboard Energia e CO₂", "Tabela Executiva"],
    },
    "Atualização de Bases": {
        "icone": "📥",
        "descricao": "Importação da base de energia/gás e manutenção dos Actual Hours.",
        "cor": "#2563eb",
        "paginas": ["Atualizar Base", "Actual Hours"],
    },
    "Análise e Consolidação": {
        "icone": "🔎",
        "descricao": "Consulta da base consolidada mensal com consumo, emissões, custos, horas e R12.",
        "cor": "#0f766e",
        "paginas": ["Base Consolidada"],
    },
    "Relatórios e Exportações": {
        "icone": "📤",
        "descricao": "Exportações do módulo, relatório completo em Excel e dashboard em PDF.",
        "cor": "#ea580c",
        "paginas": ["Relatórios Energia"],
    },
    "Administração e Parâmetros": {
        "icone": "⚙️",
        "descricao": "Fatores de emissão, metas, conversões, FY atual e mês de referência padrão.",
        "cor": "#475569",
        "paginas": ["Parâmetros"],
    },
}

NOME_MODULO_NEARMISS = "Near Miss"
NEARMISS_HOME_PAGE = "Submódulos de Near Miss"
NEARMISS_SUBMODULOS = {
    "Gestão e Performance": {
        "icone": "📊",
        "descricao": "Indicadores executivos, volume de concern reports, taxa de fechamento no prazo e principais desvios.",
        "cor": "#f97316",
        "paginas": ["Dashboard Near Miss"],
    },
    "Atualização da Base": {
        "icone": "📥",
        "descricao": "Importação e sobrescrita da base de Concern Reports.",
        "cor": "#2563eb",
        "paginas": ["Atualizar Base Near Miss"],
    },
    "Gestão de Pendências": {
        "icone": "🚦",
        "descricao": "Central operacional para acompanhar reports vencidos, próximos do prazo e previstos para vencer no mês.",
        "cor": "#dc2626",
        "paginas": ["Central de Pendências Near Miss"],
    },
    "Análise e Relatórios": {
        "icone": "🔎",
        "descricao": "Consulta da base consolidada, itens em acompanhamento e exportações.",
        "cor": "#0f766e",
        "paginas": ["Base de Concern Reports", "Relatórios Near Miss"],
    },
}

NEAR_MISS_META_FECHAMENTO_PRAZO = 95
NEAR_MISS_ALERTA_FECHAMENTO_PRAZO = 85
NEAR_MISS_PRAZO_MAXIMO_DIAS = 45
NEAR_MISS_STATUS_ORDER = ["Aberto no prazo", "Aberto vencido", "Fechado fora do prazo", "Fechado no prazo", "Aberto sem prazo"]
NEAR_MISS_STATUS_COLOR_MAP = {
    "Aberto no prazo": "#fef3c7",
    "Aberto vencido": "#7f1d1d",
    "Fechado fora do prazo": "#ef4444",
    "Fechado no prazo": "#16a34a",
    "Aberto sem prazo": "#94a3b8",
}

RISCOS_MAQUINA = ["Apreciação de risco não realizada", "Desprezível", "Atenção", "Significativo", "Alto", "Extremo"]
STATUS_COLOR_MAP = {
    "Conforme": "#16a34a",
    "Não conforme": "#dc2626",
}
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
    /* Controles da sidebar — fundo geral mantido, componentes em azul-slate para melhor contraste */
    section[data-testid="stSidebar"] [data-baseweb="select"] *{color:#e5edf7!important;}
    section[data-testid="stSidebar"] div[role="radiogroup"] label{
        background:linear-gradient(135deg,rgba(30,41,59,.92),rgba(15,23,42,.88))!important;
        border:1px solid rgba(148,163,184,.30)!important;
        border-radius:14px; padding:.58rem .72rem; margin:.22rem 0;
        transition:all .18s ease; box-shadow:0 8px 22px rgba(0,0,0,.20);
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] label *,
    section[data-testid="stSidebar"] div[role="radiogroup"] label p,
    section[data-testid="stSidebar"] div[role="radiogroup"] label span{
        color:#e5edf7!important;font-weight:800!important;
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] label:hover{
        background:linear-gradient(135deg,rgba(51,65,85,.98),rgba(30,41,59,.96))!important;
        border-color:rgba(245,197,66,.70)!important; transform:translateX(2px);
        box-shadow:0 10px 24px rgba(0,0,0,.25),0 0 0 1px rgba(245,197,66,.20)!important;
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked){
        background:linear-gradient(135deg,#f5c542,#d9a514)!important;
        border-color:#f8d96b!important;
        box-shadow:0 0 0 2px rgba(245,197,66,.20),0 12px 28px rgba(0,0,0,.24)!important;
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) *,
    section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) p,
    section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) span{
        color:#182235!important;font-weight:900!important;
    }
    section[data-testid="stSidebar"] [data-testid="stSelectbox"] label p,
    section[data-testid="stSidebar"] [data-testid="stRadio"] label p{color:#dbeafe!important;font-weight:850!important;}
    section[data-testid="stSidebar"] [data-baseweb="select"] > div{
        background:linear-gradient(135deg,rgba(30,41,59,.96),rgba(15,23,42,.92))!important;
        border-color:rgba(148,163,184,.38)!important;
        box-shadow:0 8px 22px rgba(0,0,0,.20)!important;
    }
    section[data-testid="stSidebar"] [data-baseweb="select"] svg{color:#cbd5e1!important;fill:#cbd5e1!important;}
    section[data-testid="stSidebar"] [data-baseweb="select"] input{color:#e5edf7!important;}
    section[data-testid="stSidebar"] div.stButton>button{
        background:linear-gradient(135deg,rgba(30,41,59,.96),rgba(15,23,42,.92))!important;
        color:#e5edf7!important;
        border:1px solid rgba(148,163,184,.35)!important; box-shadow:0 10px 24px rgba(0,0,0,.22)!important;
    }
    section[data-testid="stSidebar"] div.stButton>button:hover{
        border-color:#f5c542!important;background:linear-gradient(135deg,rgba(51,65,85,.98),rgba(30,41,59,.96))!important;
    }
    section[data-testid="stSidebar"] div.stButton>button *,
    section[data-testid="stSidebar"] div.stButton>button p,
    section[data-testid="stSidebar"] div.stButton>button span{color:#e5edf7!important;font-weight:800!important;}
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
    .breadcrumb-wrap{position:sticky;top:.35rem;z-index:999;background:#ffffff;border:1px solid #e5e7eb;border-radius:16px;padding:.58rem .85rem;margin:.15rem 0 .9rem 0;box-shadow:0 8px 20px rgba(31,41,55,.055);font-size:.84rem;color:#475569;font-weight:800;}
    .breadcrumb-wrap span{color:#0f172a;}
    .breadcrumb-wrap .sep{color:#94a3b8;padding:0 .35rem;}
    .quick-help-card{background:#fff;border:1px solid #e5e7eb;border-radius:18px;padding:1rem;box-shadow:0 10px 25px rgba(31,41,55,.06);min-height:145px;}
    .quick-help-card h4{margin:.1rem 0 .45rem 0;color:#111827;font-weight:900;}
    .quick-help-card p,.quick-help-card li{color:#475569;font-size:.92rem;}
    </style>""", unsafe_allow_html=True)
def hide_sidebar_on_home():
    """Oculta a barra lateral nas telas de escolha principal.

    A tela inicial geral e a tela intermediária de submódulos da Sustentação de
    Proteções de Máquinas devem se comportar como landing pages, sem menu lateral.
    Depois que o usuário escolhe um submódulo/página interna, a barra lateral volta
    a aparecer normalmente.
    """
    mod = st.session_state.get("modulo", "home")
    page_nr12 = st.session_state.get("page_nr12", NR12_HOME_PAGE if "NR12_HOME_PAGE" in globals() else "Submódulos da Sustentação")
    page_ehs = st.session_state.get("page_ehs", EHS_HOME_PAGE if "EHS_HOME_PAGE" in globals() else "Submódulos da Auditoria Cruzada")
    page_energia = st.session_state.get("page_energia", ENERGIA_HOME_PAGE if "ENERGIA_HOME_PAGE" in globals() else "Submódulos de Energia e Emissões")
    page_nearmiss = st.session_state.get("page_nearmiss", NEARMISS_HOME_PAGE if "NEARMISS_HOME_PAGE" in globals() else "Submódulos de Near Miss")
    ocultar = (
        (mod == "home")
        or (mod == "nr12" and page_nr12 == (NR12_HOME_PAGE if "NR12_HOME_PAGE" in globals() else "Submódulos da Sustentação"))
        or (mod == "ehs" and page_ehs == (EHS_HOME_PAGE if "EHS_HOME_PAGE" in globals() else "Submódulos da Auditoria Cruzada"))
        or (mod == "energia" and page_energia == (ENERGIA_HOME_PAGE if "ENERGIA_HOME_PAGE" in globals() else "Submódulos de Energia e Emissões"))
        or (mod == "nearmiss" and page_nearmiss == (NEARMISS_HOME_PAGE if "NEARMISS_HOME_PAGE" in globals() else "Submódulos de Near Miss"))
    )
    if ocultar:
        st.markdown("""
        <style>
        section[data-testid="stSidebar"]{display:none!important;}
        [data-testid="collapsedControl"]{display:none!important;}
        .block-container{padding-left:3rem!important;padding-right:3rem!important;}
        </style>
        """, unsafe_allow_html=True)

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
    __tablename__="verificacoes_nr12"
    id=Column(Integer,primary_key=True); maquina_id=Column(Integer,ForeignKey("maquinas_nr12.id")); site_id=Column(Integer,ForeignKey("sites.id")); tipo=Column(String(120)); data_verificacao=Column(Date); responsavel=Column(String(120)); resultado=Column(String(80)); pontuacao=Column(Float,default=0); possui_nc_critica=Column(Boolean,default=False); observacoes=Column(Text); proxima_verificacao=Column(Date); criado_em=Column(DateTime,default=datetime.utcnow); versao_checklist_id=Column(Integer,ForeignKey("checklist_versoes_maquinas.id")); maquina=relationship("MaquinaNR12")
class ChecklistItemNR12(Base):
    __tablename__="checklist_itens_nr12"; id=Column(Integer,primary_key=True); tipo_checklist=Column(String(120)); ordem=Column(Integer); pergunta=Column(Text); item_critico=Column(Boolean,default=False); gera_pac_automatico=Column(Boolean,default=False); ativo=Column(Boolean,default=True); __table_args__=(UniqueConstraint("tipo_checklist","ordem",name="uq_nr12_tipo_ordem"),)
class ChecklistVersaoMaquinas(Base):
    __tablename__="checklist_versoes_maquinas"
    id=Column(Integer,primary_key=True); tipo_checklist=Column(String(120),nullable=False); versao=Column(Integer,default=1); descricao=Column(Text); ativo=Column(Boolean,default=True); criado_em=Column(DateTime,default=datetime.utcnow); criado_por=Column(String(120));
    perguntas=relationship("ChecklistPerguntaVersaoMaquinas", cascade="all, delete-orphan")
class ChecklistPerguntaVersaoMaquinas(Base):
    __tablename__="checklist_perguntas_versoes_maquinas"
    id=Column(Integer,primary_key=True); checklist_versao_id=Column(Integer,ForeignKey("checklist_versoes_maquinas.id")); item_base_id=Column(Integer,ForeignKey("checklist_itens_nr12.id")); ordem=Column(Integer); pergunta=Column(Text); item_critico=Column(Boolean,default=False); gera_pac_automatico=Column(Boolean,default=False); ativo=Column(Boolean,default=True)
class RespostaNR12(Base):
    __tablename__="respostas_nr12"; id=Column(Integer,primary_key=True); verificacao_id=Column(Integer,ForeignKey("verificacoes_nr12.id")); item_id=Column(Integer,ForeignKey("checklist_itens_nr12.id")); aplicavel=Column(Boolean,default=True); resultado=Column(String(60)); comentario_evidencia=Column(Text); gerar_pac=Column(Boolean,default=False); ordem_snapshot=Column(Integer); pergunta_snapshot=Column(Text); item_critico_snapshot=Column(Boolean,default=False); gera_pac_automatico_snapshot=Column(Boolean,default=False); item=relationship("ChecklistItemNR12")
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
    __tablename__="requisitos_ehs"; id=Column(Integer,primary_key=True); diretiva_id=Column(Integer,ForeignKey("diretivas_ehs.id")); ordem=Column(Integer); pergunta=Column(Text); criticidade=Column(String(40),default="Média"); evidencia_esperada=Column(Text); gera_pac_automatico=Column(Boolean,default=False); ativo=Column(Boolean,default=True); diretiva=relationship("DiretivaEHS"); __table_args__=(UniqueConstraint("diretiva_id","ordem",name="uq_ehs_diretiva_ordem"),)
class ChecklistVersaoEHS(Base):
    __tablename__="checklist_versoes_ehs"
    id=Column(Integer,primary_key=True); descricao=Column(Text); versao=Column(Integer,default=1); ativo=Column(Boolean,default=True); criado_em=Column(DateTime,default=datetime.utcnow); criado_por=Column(String(120))
class ChecklistPerguntaVersaoEHS(Base):
    __tablename__="checklist_perguntas_versoes_ehs"
    id=Column(Integer,primary_key=True); checklist_versao_id=Column(Integer,ForeignKey("checklist_versoes_ehs.id")); requisito_id=Column(Integer,ForeignKey("requisitos_ehs.id")); categoria=Column(String(180)); ordem=Column(Integer); pergunta=Column(Text); criticidade=Column(String(40)); evidencia_esperada=Column(Text); gera_pac_automatico=Column(Boolean,default=False); ativo=Column(Boolean,default=True)
class AuditoriaCruzada(Base):
    __tablename__="auditorias_cruzadas"; id=Column(Integer,primary_key=True); ano=Column(Integer); ciclo=Column(String(80)); site_auditado_id=Column(Integer,ForeignKey("sites.id")); site_auditor_lider_id=Column(Integer,ForeignKey("sites.id")); site_auditor_apoio_id=Column(Integer,ForeignKey("sites.id")); auditor_lider=Column(String(120)); auditor_apoio=Column(String(120)); data_planejada=Column(Date); data_inicio=Column(Date); data_fim=Column(Date); status=Column(String(60)); escopo=Column(Text); observacoes=Column(Text); conformidade_percentual=Column(Float,default=0); maturidade_media=Column(Float,default=0); versao_checklist_id=Column(Integer,ForeignKey("checklist_versoes_ehs.id")); criado_em=Column(DateTime,default=datetime.utcnow)
class RespostaAuditoriaEHS(Base):
    __tablename__="respostas_auditoria_ehs"; id=Column(Integer,primary_key=True); auditoria_id=Column(Integer,ForeignKey("auditorias_cruzadas.id")); requisito_id=Column(Integer,ForeignKey("requisitos_ehs.id")); aplicavel=Column(Boolean,default=True); status=Column(String(60)); nota_maturidade=Column(Float,default=3); evidencia_verificada=Column(Text); comentario_auditor=Column(Text); necessita_pac=Column(Boolean,default=False); versao_checklist_id=Column(Integer,ForeignKey("checklist_versoes_ehs.id")); pergunta_snapshot=Column(Text); criticidade_snapshot=Column(String(40)); evidencia_esperada_snapshot=Column(Text); gera_pac_automatico_snapshot=Column(Boolean,default=False); requisito=relationship("RequisitoEHS"); __table_args__=(UniqueConstraint("auditoria_id","requisito_id",name="uq_resp_auditoria_requisito"),)
class PACEHS(Base):
    __tablename__="pac_ehs"; id=Column(Integer,primary_key=True); auditoria_id=Column(Integer,ForeignKey("auditorias_cruzadas.id")); site_id=Column(Integer,ForeignKey("sites.id")); requisito_id=Column(Integer,ForeignKey("requisitos_ehs.id")); tipo_achado=Column(String(80)); descricao=Column(Text); evidencia=Column(Text); risco=Column(Text); causa_raiz=Column(Text); acao_imediata=Column(Text); acao_corretiva=Column(Text); responsavel=Column(String(120)); area_responsavel=Column(String(120)); prazo=Column(Date); status=Column(String(60)); prioridade_criticidade=Column(String(40)); evidencia_conclusao=Column(Text); validacao_ehs=Column(Boolean,default=False); data_conclusao=Column(Date); verificacao_eficacia=Column(Text); status_eficacia=Column(String(80)); criado_em=Column(DateTime,default=datetime.utcnow); requisito=relationship("RequisitoEHS")
class EvidenciaEHS(Base):
    __tablename__="evidencias_ehs"; id=Column(Integer,primary_key=True); auditoria_id=Column(Integer); requisito_id=Column(Integer); pac_id=Column(Integer); descricao=Column(Text); arquivo_nome=Column(String(260)); arquivo_caminho=Column(String(500)); criado_em=Column(DateTime,default=datetime.utcnow)
class LogAuditoriaSistema(Base):
    __tablename__="logs_auditoria_sistema"
    id=Column(Integer,primary_key=True)
    usuario=Column(String(120))
    perfil=Column(String(60))
    modulo=Column(String(120))
    entidade=Column(String(120))
    entidade_id=Column(Integer)
    campo=Column(String(160))
    valor_anterior=Column(Text)
    valor_novo=Column(Text)
    acao=Column(String(120))
    data_hora=Column(DateTime,default=datetime.utcnow)
    observacao=Column(Text)


class RegraFrequenciaInspecaoMaquinas(Base):
    __tablename__="regras_frequencia_inspecoes_maquinas"
    id=Column(Integer,primary_key=True)
    tipo_evento=Column(String(160),nullable=False)
    criticidade=Column(String(20),nullable=False)
    dias_periodicidade=Column(Integer,default=180)
    ativo=Column(Boolean,default=True)
    atualizado_em=Column(DateTime,default=datetime.utcnow)
    atualizado_por=Column(String(120))
    observacoes=Column(Text)
    __table_args__=(UniqueConstraint("tipo_evento","criticidade",name="uq_freq_tipo_criticidade"),)



class EnergiaRegistro(Base):
    __tablename__ = "energia_registros"
    id = Column(Integer, primary_key=True)
    mes_ref = Column(Date, nullable=False)
    site_codigo = Column(String(30), nullable=False)
    site_nome = Column(String(160))
    grupo = Column(String(80))
    divisao = Column(String(160))
    fonte = Column(String(80))  # Energia elétrica ou Gás natural
    consumo_original = Column(Float, default=0)
    unidade_original = Column(String(40))
    consumo_kwh = Column(Float, default=0)
    custo_brl = Column(Float, default=0)
    unit_cost = Column(Float, default=0)
    emissao_co2_ton = Column(Float, default=0)
    emissao_escopo = Column(String(40))  # Escopo 1 ou Escopo 2
    origem_arquivo = Column(String(260))
    criado_em = Column(DateTime, default=datetime.utcnow)


class NearMissRegistro(Base):
    __tablename__ = "near_miss_registros"
    id = Column(Integer, primary_key=True)
    id_cr = Column(String(80), unique=True, nullable=False)
    data_ocorrencia = Column(Date)
    data_reportada = Column(String(120))
    tipo = Column(String(120))
    grupo_origem = Column(String(160))
    sub_grupo = Column(String(160))
    business_unit = Column(String(160))
    dept = Column(String(180))
    site_codigo = Column(String(30))
    site_nome = Column(String(160))
    grupo = Column(String(80))
    divisao = Column(String(160))
    hazard_type = Column(String(160))
    status = Column(String(120))
    assigned_to = Column(String(160))
    closure_due_date = Column(Date)
    closed_date = Column(Date)
    days_open_to_close = Column(Float)
    days_past_due = Column(Float)
    descricao = Column(Text)
    origem_arquivo = Column(String(260))
    criado_em = Column(DateTime, default=datetime.utcnow)

class NearMissUploadHistorico(Base):
    __tablename__ = "near_miss_upload_historico"
    id = Column(Integer, primary_key=True)
    nome_arquivo = Column(String(260))
    linhas_importadas = Column(Integer, default=0)
    data_upload = Column(DateTime, default=datetime.utcnow)
    usuario = Column(String(120))
    observacoes = Column(Text)

class EnergiaActualHours(Base):
    __tablename__ = "energia_actual_hours"
    id = Column(Integer, primary_key=True)
    mes_ref = Column(Date, nullable=False)
    site_codigo = Column(String(30), nullable=False)
    site_nome = Column(String(160))
    grupo = Column(String(80))
    actual_hours = Column(Float, default=0)
    production_capacity_hours = Column(Float, default=0)
    origem = Column(String(80), default="Manual")
    criado_em = Column(DateTime, default=datetime.utcnow)
    atualizado_em = Column(DateTime, default=datetime.utcnow)

class EnergiaUploadHistorico(Base):
    __tablename__ = "energia_upload_historico"
    id = Column(Integer, primary_key=True)
    tipo_base = Column(String(80))
    nome_arquivo = Column(String(260))
    data_upload = Column(DateTime, default=datetime.utcnow)
    usuario = Column(String(120))
    observacoes = Column(Text)

class EnergiaParametro(Base):
    __tablename__ = "energia_parametros"
    id = Column(Integer, primary_key=True)
    chave = Column(String(120), unique=True, nullable=False)
    valor = Column(String(120))
    descricao = Column(Text)

def table_exists(table_name):
    try:
        return table_name in inspect(engine).get_table_names()
    except Exception as e:
        logging.exception("Falha ao verificar tabela %s", table_name)
        return False

def column_exists(table_name, column_name):
    try:
        if not table_exists(table_name):
            return False
        return column_name in {c["name"] for c in inspect(engine).get_columns(table_name)}
    except Exception as e:
        logging.exception("Falha ao verificar coluna %s.%s", table_name, column_name)
        return False

def safe_add_column(table_name, column_name, sql_definition):
    try:
        if table_exists(table_name) and not column_exists(table_name, column_name):
            with engine.begin() as conn:
                conn.exec_driver_sql(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {sql_definition}")
            logging.info("Coluna adicionada: %s.%s", table_name, column_name)
    except Exception as e:
        logging.exception("Falha ao adicionar coluna %s.%s", table_name, column_name)

def ensure_schema_updates():
    safe_add_column("maquinas_nr12", "risco_maquina", "VARCHAR(80) DEFAULT 'Apreciação de risco não realizada'")
    safe_add_column("maquinas_nr12", "data_prevista_adequacao", "DATE")
    safe_add_column("documentos_nr12", "arquivo_bytes", "BLOB")
    safe_add_column("checklist_itens_nr12", "gera_pac_automatico", "BOOLEAN DEFAULT 0")
    safe_add_column("verificacoes_nr12", "versao_checklist_id", "INTEGER")
    safe_add_column("respostas_nr12", "ordem_snapshot", "INTEGER")
    safe_add_column("respostas_nr12", "pergunta_snapshot", "TEXT")
    safe_add_column("respostas_nr12", "item_critico_snapshot", "BOOLEAN DEFAULT 0")
    safe_add_column("respostas_nr12", "gera_pac_automatico_snapshot", "BOOLEAN DEFAULT 0")
    safe_add_column("requisitos_ehs", "gera_pac_automatico", "BOOLEAN DEFAULT 0")
    safe_add_column("auditorias_cruzadas", "versao_checklist_id", "INTEGER")
    safe_add_column("respostas_auditoria_ehs", "versao_checklist_id", "INTEGER")
    safe_add_column("respostas_auditoria_ehs", "pergunta_snapshot", "TEXT")
    safe_add_column("respostas_auditoria_ehs", "criticidade_snapshot", "VARCHAR(40)")
    safe_add_column("respostas_auditoria_ehs", "evidencia_esperada_snapshot", "TEXT")
    safe_add_column("respostas_auditoria_ehs", "gera_pac_automatico_snapshot", "BOOLEAN DEFAULT 0")

def get_versao_ativa_maquinas(db, tipo_checklist):
    return db.query(ChecklistVersaoMaquinas).filter_by(tipo_checklist=tipo_checklist, ativo=True).order_by(ChecklistVersaoMaquinas.versao.desc(), ChecklistVersaoMaquinas.id.desc()).first()

def criar_versao_checklist_maquinas(db, tipo_checklist, criado_por="Sistema", descricao=None, base_version=None):
    atual = db.query(ChecklistVersaoMaquinas).filter_by(tipo_checklist=tipo_checklist).order_by(ChecklistVersaoMaquinas.versao.desc()).first()
    nova_num = (atual.versao if atual and atual.versao else 0) + 1
    for v in db.query(ChecklistVersaoMaquinas).filter_by(tipo_checklist=tipo_checklist, ativo=True).all():
        v.ativo = False
    v = ChecklistVersaoMaquinas(tipo_checklist=tipo_checklist, versao=nova_num, descricao=descricao or f"Versão {nova_num} de {tipo_checklist}", ativo=True, criado_por=criado_por)
    db.add(v); db.flush()
    if base_version:
        perguntas = db.query(ChecklistPerguntaVersaoMaquinas).filter_by(checklist_versao_id=base_version.id).order_by(ChecklistPerguntaVersaoMaquinas.ordem).all()
        for p in perguntas:
            db.add(ChecklistPerguntaVersaoMaquinas(checklist_versao_id=v.id, item_base_id=p.item_base_id, ordem=p.ordem, pergunta=p.pergunta, item_critico=p.item_critico, gera_pac_automatico=p.gera_pac_automatico, ativo=p.ativo))
    else:
        itens = db.query(ChecklistItemNR12).filter_by(tipo_checklist=tipo_checklist).order_by(ChecklistItemNR12.ordem).all()
        for it in itens:
            db.add(ChecklistPerguntaVersaoMaquinas(checklist_versao_id=v.id, item_base_id=it.id, ordem=it.ordem, pergunta=it.pergunta, item_critico=it.item_critico, gera_pac_automatico=getattr(it, "gera_pac_automatico", False), ativo=it.ativo))
    db.flush()
    return v

def criar_versao_checklist_ehs(db, criado_por="Sistema", descricao=None):
    """Cria uma nova versão ativa do checklist EHS a partir da base editável atual.

    A base inicial continua no código como seed, mas a gestão operacional passa a ser pelo banco.
    Cada nova auditoria recebe um snapshot da versão ativa, preservando rastreabilidade histórica.
    """
    atual = db.query(ChecklistVersaoEHS).order_by(ChecklistVersaoEHS.versao.desc(), ChecklistVersaoEHS.id.desc()).first()
    nova_num = (atual.versao if atual and atual.versao else 0) + 1
    for v in db.query(ChecklistVersaoEHS).filter_by(ativo=True).all():
        v.ativo = False
    nova = ChecklistVersaoEHS(descricao=descricao or f"Versão {nova_num} do checklist de Diretrizes EHS", versao=nova_num, ativo=True, criado_por=criado_por)
    db.add(nova); db.flush()
    reqs = db.query(RequisitoEHS).join(DiretivaEHS).order_by(DiretivaEHS.categoria, RequisitoEHS.ordem).all()
    for r in reqs:
        db.add(ChecklistPerguntaVersaoEHS(
            checklist_versao_id=nova.id,
            requisito_id=r.id,
            categoria=r.diretiva.categoria if r.diretiva else "Sem categoria",
            ordem=r.ordem,
            pergunta=r.pergunta,
            criticidade=r.criticidade,
            evidencia_esperada=r.evidencia_esperada,
            gera_pac_automatico=getattr(r, "gera_pac_automatico", False),
            ativo=r.ativo,
        ))
    db.flush()
    return nova

def seed_checklist_versions(db):
    tipos = {t for t, in db.query(ChecklistItemNR12.tipo_checklist).distinct().all()}
    for tipo in sorted(tipos):
        if not db.query(ChecklistVersaoMaquinas).filter_by(tipo_checklist=tipo).first():
            criar_versao_checklist_maquinas(db, tipo, "Sistema", "Versão inicial migrada do checklist padrão")
    if not db.query(ChecklistVersaoEHS).first():
        criar_versao_checklist_ehs(db, "Sistema", "Versão inicial migrada do checklist de Diretrizes EHS")

def sync_checklists_base(db):
    for tipo, itens in CHECKLIST_NR12.items():
        for i, (pergunta, critico) in enumerate(itens, 1):
            item = db.query(ChecklistItemNR12).filter_by(tipo_checklist=tipo, ordem=i).first()
            if not item:
                db.add(ChecklistItemNR12(tipo_checklist=tipo, ordem=i, pergunta=pergunta, item_critico=critico, gera_pac_automatico=False, ativo=True))
    for cat, pergs in CHECKLIST_EHS.items():
        d = db.query(DiretivaEHS).filter_by(categoria=cat).first()
        if not d:
            d = DiretivaEHS(categoria=cat, descricao=cat, ativo=True)
            db.add(d)
            db.flush()
        for i, p in enumerate(pergs, 1):
            req = db.query(RequisitoEHS).filter_by(diretiva_id=d.id, ordem=i).first()
            if not req:
                db.add(RequisitoEHS(diretiva_id=d.id, ordem=i, pergunta=p, criticidade="Alta" if i in [1,3,7] else "Média", evidencia_esperada="Evidência documental, registros, entrevistas e/ou verificação em campo.", gera_pac_automatico=False, ativo=True))
    db.flush()
    seed_checklist_versions(db)


def seed_regras_frequencia(db):
    for tipo, regras in REGRAS_FREQUENCIA_DEFAULT.items():
        for criticidade, dias in regras.items():
            obj = db.query(RegraFrequenciaInspecaoMaquinas).filter_by(tipo_evento=tipo, criticidade=criticidade).first()
            if not obj:
                db.add(RegraFrequenciaInspecaoMaquinas(
                    tipo_evento=tipo,
                    criticidade=criticidade,
                    dias_periodicidade=int(dias),
                    ativo=True,
                    atualizado_por="Sistema",
                    observacoes="Carga inicial padrão"
                ))
    db.flush()

def regra_frequencia_dias(db, tipo_evento, criticidade):
    criticidade = criticidade if criticidade in CRITICIDADES else "Média"
    obj = db.query(RegraFrequenciaInspecaoMaquinas).filter_by(tipo_evento=tipo_evento, criticidade=criticidade, ativo=True).first()
    if obj and obj.dias_periodicidade is not None:
        return int(obj.dias_periodicidade)
    return int(REGRAS_FREQUENCIA_DEFAULT.get(tipo_evento, {}).get(criticidade, 180))

def data_limite_por_frequencia(db, tipo_evento, criticidade, data_base=None):
    dias = regra_frequencia_dias(db, tipo_evento, criticidade)
    data_base = as_date(data_base) or date.today()
    return data_base + timedelta(days=max(0, dias))

def validar_data_dentro_limite(db, tipo_evento, criticidade, data_alvo, data_base=None):
    data_alvo = as_date(data_alvo)
    limite = data_limite_por_frequencia(db, tipo_evento, criticidade, data_base)
    if not data_alvo:
        return False, limite, f"Informe uma data até {fmt_date(limite)}."
    if data_alvo > limite:
        return False, limite, f"A data selecionada ultrapassa o limite permitido para criticidade {criticidade}: máximo {fmt_date(limite)}."
    return True, limite, ""

def df_regras_frequencia(db):
    rows = []
    regras = db.query(RegraFrequenciaInspecaoMaquinas).order_by(RegraFrequenciaInspecaoMaquinas.tipo_evento, RegraFrequenciaInspecaoMaquinas.criticidade).all()
    for r in regras:
        rows.append({
            "ID": r.id,
            "Tipo de evento": r.tipo_evento,
            "Criticidade": r.criticidade,
            "Dias máximos": r.dias_periodicidade,
            "Ativo": r.ativo,
            "Atualizado em": fmt_date(r.atualizado_em),
            "Atualizado por": r.atualizado_por,
            "Observações": r.observacoes,
        })
    return pd.DataFrame(rows)

def init_db():
    Base.metadata.create_all(engine); ensure_schema_updates(); db=SessionLocal()
    try:
        if not db.query(Site).filter_by(codigo="Corporativo").first(): db.add(Site(codigo="Corporativo",nome="Corporativo"))
        for s in SITES_PADRAO:
            site_obj = db.query(Site).filter_by(codigo=s).first()
            nome_padrao = SITE_NOMES_PADRAO.get(s, s)
            if not site_obj:
                db.add(Site(codigo=s, nome=nome_padrao))
            else:
                site_obj.nome = nome_padrao
        db.flush()
        for nome,perfil,sitecod in USUARIOS_PADRAO:
            if not db.query(Usuario).filter_by(nome=nome).first():
                stt=db.query(Site).filter_by(codigo=sitecod).first(); db.add(Usuario(nome=nome,perfil=perfil,site_id=stt.id if stt else None))
        sync_checklists_base(db)
        seed_regras_frequencia(db)
        seed_energia_parametros(db)
        seed_energia_actual_hours_inicial(db)
        seed_energia_registros_inicial(db)
        seed_near_miss_inicial(db)
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

def registrar_log(db, usuario, modulo, entidade, entidade_id, acao, campo=None, valor_anterior=None, valor_novo=None, observacao=None):
    try:
        nome = usuario.nome if hasattr(usuario, "nome") else str(usuario or "Sistema")
        perfil = getattr(usuario, "perfil", None) if usuario is not None else None
        db.add(LogAuditoriaSistema(
            usuario=nome, perfil=perfil, modulo=modulo, entidade=entidade, entidade_id=entidade_id,
            acao=acao, campo=campo, valor_anterior=None if valor_anterior is None else str(valor_anterior),
            valor_novo=None if valor_novo is None else str(valor_novo), observacao=observacao, data_hora=datetime.utcnow()
        ))
    except Exception:
        logging.exception("Falha ao registrar log de auditoria do sistema")

def df_logs(db):
    rows=[]
    for l in db.query(LogAuditoriaSistema).order_by(LogAuditoriaSistema.data_hora.desc()).limit(2000):
        rows.append({
            "ID": l.id, "Data/hora": l.data_hora.strftime("%d/%m/%Y %H:%M") if l.data_hora else "—",
            "Usuário": l.usuario, "Perfil": l.perfil, "Módulo": l.modulo, "Entidade": l.entidade,
            "ID entidade": l.entidade_id, "Ação": l.acao, "Campo": l.campo,
            "Valor anterior": l.valor_anterior, "Valor novo": l.valor_novo, "Observação": l.observacao
        })
    return pd.DataFrame(rows)

def as_date(v):
    if v in (None,""): return None
    if isinstance(v,datetime): return v.date()
    if isinstance(v,date): return v
    try: return pd.to_datetime(v).date()
    except Exception: return None
def fmt_date(v): v=as_date(v); return v.strftime("%d/%m/%Y") if v else "—"
def site_nome_padrao(codigo):
    cod = normalize_site_code(codigo)
    return SITES_LAG.get(cod, {}).get("nome", str(codigo) if codigo else "—")

def site_nome_curto(codigo):
    cod = normalize_site_code(codigo)
    return SITES_LAG.get(cod, {}).get("nome_curto", str(codigo) if codigo else "—")

def site_grupo(codigo):
    cod = normalize_site_code(codigo)
    return SITES_LAG.get(cod, {}).get("grupo", "—")

def site_divisao(codigo):
    cod = normalize_site_code(codigo)
    return SITES_LAG.get(cod, {}).get("divisao", site_grupo(cod))

def site_label(codigo, formato="padrao"):
    cod = normalize_site_code(codigo)
    if formato == "curto":
        return site_nome_curto(cod)
    if formato == "grupo":
        return site_grupo(cod)
    if formato == "divisao":
        return site_divisao(cod)
    if formato == "codigo_nome":
        return f"{cod} — {site_nome_padrao(cod)}" if cod and cod != "—" else "—"
    return site_nome_padrao(cod)

def normalize_site_code(valor):
    if valor is None:
        return "—"
    raw = str(valor).strip()
    if raw in SITES_LAG:
        return raw
    norm = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode("ascii").lower()
    aliases = {
        "cac": ["cac", "cachoeirinha"],
        "jac": ["jac", "jacarei", "jacarei sp"],
        "jun": ["jun", "jundiai", "jundiai sp"],
        "per": ["per", "perus", "sao paulo", "sao paulo bra"],
        "sjc": ["sjc", "sao jose dos campos", "sao jose"],
        "dia": ["dia", "diadema", "diadema sp"],
        "corporativo": ["corporativo", "corp", "lag"],
    }
    for cod, pats in aliases.items():
        if any(p in norm for p in pats):
            return cod.upper() if cod != "corporativo" else "Corporativo"
    return raw
def site_code(db,id):
    s=db.get(Site,id) if id else None
    return site_label(s.codigo) if s else "—"
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
    crit=any(r.resultado=="Não conforme" and (bool(getattr(r,"item_critico_snapshot",False)) or (r.item and r.item.item_critico)) for r in ap)
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
    pergunta = getattr(r, "pergunta_snapshot", None) or (r.item.pergunta if r.item else "Item de checklist")
    if db.query(PACNR12).filter_by(verificacao_id=ver.id,item_checklist=pergunta).first(): return
    critico = bool(getattr(r,"item_critico_snapshot",False)) or bool(r.item and r.item.item_critico)
    clas="Crítico" if critico else "Maior"
    db.add(PACNR12(origem=ver.tipo,site_id=ver.site_id,maquina_id=ver.maquina_id,verificacao_id=ver.id,item_checklist=pergunta,descricao_desvio=r.comentario_evidencia or pergunta,classificacao=clas,responsavel=resp,area_responsavel="A definir",prazo=date.today()+timedelta(days=15 if clas=="Crítico" else 30),status="Aberta"))
def gerar_pac_automatico_ehs(db,a,r,resp=""):
    if db.query(PACEHS).filter_by(auditoria_id=a.id,requisito_id=r.requisito_id).first(): return
    criticidade = getattr(r, "criticidade_snapshot", None) or (r.requisito.criticidade if r.requisito else "Média")
    pergunta = getattr(r, "pergunta_snapshot", None) or (r.requisito.pergunta if r.requisito else "Requisito de checklist")
    tipo="Não conformidade crítica" if r.status=="Não Conforme" and criticidade=="Alta" else "Não conformidade maior" if r.status=="Não Conforme" else "Observação"
    db.add(PACEHS(auditoria_id=a.id,site_id=a.site_auditado_id,requisito_id=r.requisito_id,tipo_achado=tipo,descricao=r.comentario_auditor or pergunta,evidencia=r.evidencia_verificada,risco="A avaliar",causa_raiz="A definir",acao_imediata="A definir",acao_corretiva="A definir",responsavel=resp,area_responsavel="A definir",prazo=date.today()+timedelta(days=15 if tipo=="Não conformidade crítica" else 30),status="Aberta",prioridade_criticidade="Alta" if tipo=="Não conformidade crítica" else "Média"))
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


def energia_default_r12_mes(df):
    """Usa o mês vigente como padrão; se não existir na base, usa o mês mais próximo anterior."""
    if df is None or df.empty or "Mês" not in df.columns:
        return None
    opts = sorted([energia_first_day(x) for x in df["Mês"].dropna().unique() if energia_first_day(x)])
    if not opts:
        return None
    hoje = date.today().replace(day=1)
    if hoje in opts:
        return hoje
    anteriores = [d for d in opts if d <= hoje]
    if anteriores:
        return max(anteriores)
    return max(opts)

def energia_variacao_periodos(df, metric, r12_mes, fy_base, usar_irec=False):
    """Calcula variação percentual do R12 selecionado contra um FY base."""
    if df is None or df.empty or not r12_mes:
        return None
    sites = ENERGIA_SITE_ORDER
    r12_ini = energia_r12_start(r12_mes)
    base_ini, base_fim = energia_intervalo_fy(fy_base)
    atual = energia_agregar_periodo(df, sites, metric, r12_ini, r12_mes, usar_irec)
    base = energia_agregar_periodo(df, sites, metric, base_ini, base_fim, usar_irec)
    return energia_pct_change(atual, base)

def energia_home_kpi_cards(db):
    """Cards sintéticos de energia para aparecerem dentro da Visão geral integrada."""
    try:
        if db.query(EnergiaRegistro).count() == 0:
            return [
                ("Energia • CO₂ R12 vs FY anterior", "—", "Importe a base de energia"),
                ("Energia • CO₂ R12 vs FY19", "—", "Importe a base de energia"),
                ("Energia • Eficiência R12 vs FY anterior", "—", "Importe a base de energia"),
                ("Energia • Eficiência R12 vs FY19", "—", "Importe a base de energia"),
            ]
        df = energia_consolidado(db)
        if df.empty:
            return []
        r12_mes = energia_default_r12_mes(df)
        fy_atual = int(energia_param_float(db, "fy_atual", 26))
        fy_passado = fy_atual - 1
        co2_vs_passado = energia_variacao_periodos(df, "Emissões de CO₂ considerando I-REC", r12_mes, fy_passado, True)
        co2_vs_fy19 = energia_variacao_periodos(df, "Emissões de CO₂ considerando I-REC", r12_mes, 19, True)
        eff_vs_passado = energia_variacao_periodos(df, "Eficiência energética", r12_mes, fy_passado, True)
        eff_vs_fy19 = energia_variacao_periodos(df, "Eficiência energética", r12_mes, 19, True)
        ref = r12_mes.strftime("%b/%Y") if r12_mes else "mês vigente"
        return [
            ("Energia • CO₂ R12 vs FY anterior", energia_fmt_val(co2_vs_passado, "percent"), f"R12 {ref} vs FY{fy_passado:02d}"),
            ("Energia • CO₂ R12 vs FY19", energia_fmt_val(co2_vs_fy19, "percent"), f"R12 {ref} vs FY19"),
            ("Energia • Eficiência R12 vs FY anterior", energia_fmt_val(eff_vs_passado, "percent"), f"R12 {ref} vs FY{fy_passado:02d}"),
            ("Energia • Eficiência R12 vs FY19", energia_fmt_val(eff_vs_fy19, "percent"), f"R12 {ref} vs FY19"),
        ]
    except Exception:
        return [
            ("Energia • CO₂ R12 vs FY anterior", "—", "Indicador indisponível"),
            ("Energia • CO₂ R12 vs FY19", "—", "Indicador indisponível"),
            ("Energia • Eficiência R12 vs FY anterior", "—", "Indicador indisponível"),
            ("Energia • Eficiência R12 vs FY19", "—", "Indicador indisponível"),
        ]

def energia_bar_sem_decimal(fig):
    """Padroniza rótulos de gráficos de coluna sem casas decimais."""
    fig.update_traces(texttemplate="%{text:,.0f}", textposition="outside", cliponaxis=False)
    fig.update_layout(uniformtext_minsize=8, uniformtext_mode="hide")
    return fig

def energia_localidades_df(r12_site):
    if r12_site is None or r12_site.empty:
        return pd.DataFrame()
    rows = []
    for _, r in r12_site.iterrows():
        site = str(r.get("Site", "")).strip()
        coord = ENERGIA_SITE_COORDS.get(site)
        if not coord:
            continue
        consumo_total = float(r.get("consumo_total_kwh", 0) or 0)
        actual_hours = float(r.get("actual_hours", 0) or 0)
        eficiencia = r.get("eficiencia_energetica", None)
        if eficiencia is None or pd.isna(eficiencia):
            eficiencia = consumo_total / actual_hours if actual_hours else None
        rows.append({
            "Site": site,
            "Unidade": energia_site_nome(site),
            "Cidade/UF": f"{coord['cidade']}/{coord['uf']}",
            "Grupo": energia_site_grupo(site),
            "Latitude": coord["latitude"],
            "Longitude": coord["longitude"],
            "consumo_eletrico_kwh": float(r.get("consumo_eletrico_kwh", 0) or 0),
            "consumo_gas_kwh": float(r.get("consumo_gas_kwh", 0) or 0),
            "consumo_total_kwh": consumo_total,
            "emissao_total_tco2e": float(r.get("emissao_total_tco2e", 0) or 0),
            "emissao_total_com_irec_tco2e": float(r.get("emissao_total_com_irec_tco2e", 0) or 0),
            "custo_total_brl": float(r.get("custo_total_brl", 0) or 0),
            "actual_hours": actual_hours,
            "eficiencia_energetica": eficiencia,
        })
    return pd.DataFrame(rows)

def energia_ranking_localidades_fig(local_df, metrica_label, comparar_df=None, usar_irec=True, titulo=None, height=430):
    if local_df is None or local_df.empty:
        return None
    metric_col, unidade = ENERGIA_MAP_METRICAS.get(metrica_label, ("consumo_total_kwh", "kWh"))
    df = local_df.copy()
    if metric_col not in df.columns:
        df[metric_col] = 0
    df["Localidade"] = df["Cidade/UF"].astype(str).str.split("/").str[0]
    df["Valor R12"] = pd.to_numeric(df[metric_col], errors="coerce").fillna(0)
    menor_melhor = metric_col == "eficiencia_energetica"
    df = df.sort_values("Valor R12", ascending=menor_melhor).copy()

    if comparar_df is not None and not comparar_df.empty:
        comp = comparar_df.copy()
        if metric_col not in comp.columns:
            comp[metric_col] = 0
        comp["Valor FY anterior"] = pd.to_numeric(comp[metric_col], errors="coerce").fillna(0)
        df = df.merge(comp[["Site", "Valor FY anterior"]], on="Site", how="left")
    else:
        df["Valor FY anterior"] = None

    df["Variação %"] = df.apply(
        lambda r: energia_pct_change(r["Valor R12"], r["Valor FY anterior"]) if pd.notna(r.get("Valor FY anterior")) else None,
        axis=1,
    )
    fmt_tipo = "money" if unidade == "BRL" else "numero"
    df["Valor formatado"] = df["Valor R12"].apply(lambda x: energia_fmt_val(x, fmt_tipo))
    df["FY anterior formatado"] = df["Valor FY anterior"].apply(lambda x: energia_fmt_val(x, fmt_tipo) if pd.notna(x) else "—")
    df["Variação formatada"] = df["Variação %"].apply(lambda x: energia_fmt_val(x, "percent") if pd.notna(x) else "—")

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df["Valor R12"],
        y=df["Localidade"],
        orientation="h",
        name="R12 atual",
        text=df["Valor formatado"],
        textposition="outside",
        marker=dict(color="#1d4ed8", line=dict(color="#ffffff", width=1)),
        customdata=df[["Grupo", "Cidade/UF", "Valor formatado", "Variação formatada"]].values,
        hovertemplate="<b>%{y}</b><br>Grupo: %{customdata[0]}<br>Local: %{customdata[1]}<br>R12 atual: %{customdata[2]} " + unidade + "<br>Variação vs FY anterior: %{customdata[3]}<extra></extra>",
    ))

    if df["Valor FY anterior"].notna().any() and float(pd.to_numeric(df["Valor FY anterior"], errors="coerce").fillna(0).abs().sum()) > 0:
        fig.add_trace(go.Scatter(
            x=df["Valor FY anterior"],
            y=df["Localidade"],
            mode="markers",
            name="FY anterior",
            marker=dict(symbol="diamond", size=12, color="#f59e0b", line=dict(color="#92400e", width=1)),
            customdata=df[["FY anterior formatado"]].values,
            hovertemplate="<b>%{y}</b><br>FY anterior: %{customdata[0]} " + unidade + "<extra></extra>",
        ))

    fig.update_yaxes(autorange="reversed", title=None)
    fig.update_xaxes(title=unidade, showgrid=True, gridcolor="rgba(148,163,184,0.22)")
    fig.update_layout(
        template="plotly_white",
        height=height,
        margin=dict(l=8, r=32, t=62, b=24),
        title=dict(text=titulo or f"Ranking por localidade — {metrica_label}", x=0.02, xanchor="left"),
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hoverlabel=dict(bgcolor="#ffffff", font_size=12, font_color="#0f172a"),
        bargap=0.28,
        uniformtext_minsize=9,
        uniformtext_mode="hide",
    )
    if usar_irec and "I-REC" in metrica_label:
        fig.add_annotation(
            text="I-REC considerado",
            x=0.01, y=-0.16, xref="paper", yref="paper", showarrow=False,
            bgcolor="rgba(236,253,245,0.92)", bordercolor="#16a34a", borderwidth=1,
            font=dict(size=10, color="#166534"),
        )
    return fig

def energia_agregar_site_periodo(df_scope, data_ini, data_fim):
    if df_scope is None or df_scope.empty or data_ini is None or data_fim is None:
        return pd.DataFrame()
    periodo = df_scope[(pd.to_datetime(df_scope["Mês"]) >= pd.to_datetime(data_ini)) & (pd.to_datetime(df_scope["Mês"]) <= pd.to_datetime(data_fim))].copy()
    if periodo.empty:
        return pd.DataFrame()
    resumo = periodo.groupby("Site", as_index=False).agg({
        "consumo_eletrico_kwh":"sum", "consumo_gas_kwh":"sum", "consumo_total_kwh":"sum",
        "emissao_total_tco2e":"sum", "emissao_total_com_irec_tco2e":"sum",
        "custo_total_brl":"sum", "actual_hours":"sum"
    })
    resumo["eficiencia_energetica"] = resumo.apply(lambda r: r["consumo_total_kwh"] / r["actual_hours"] if r["actual_hours"] else None, axis=1)
    return resumo

def energia_tendencia_metas(df_scope, usar_irec=False, db=None, limite_mes=None):
    """Gera séries mensais R12 de emissões e eficiência comparadas contra a meta.

    A curva para no menor limite entre: mês de referência usado pelo usuário,
    mês atual e último mês com dados reais de consumo/horas. Isso evita a falsa
    queda causada por meses futuros ou meses ainda não carregados na base.
    """
    if df_scope is None or df_scope.empty:
        return pd.DataFrame()
    work = df_scope.copy()
    work["Mês"] = pd.to_datetime(work["Mês"]).dt.date

    mensal = work.groupby("Mês", as_index=False).agg({
        "consumo_total_kwh": "sum",
        "actual_hours": "sum",
        "emissao_total_tco2e": "sum",
        "emissao_total_com_irec_tco2e": "sum",
    })
    mensal["tem_dado_real"] = (mensal["consumo_total_kwh"].fillna(0) > 0) & (mensal["actual_hours"].fillna(0) > 0)
    meses_validos = sorted(mensal.loc[mensal["tem_dado_real"], "Mês"].dropna().unique())
    if not meses_validos:
        return pd.DataFrame()

    hoje_mes = date.today().replace(day=1)
    limite_usuario = energia_first_day(limite_mes) if limite_mes else hoje_mes
    ultimo_mes_com_dados = max(meses_validos)
    limite_final = min(limite_usuario, hoje_mes, ultimo_mes_com_dados)
    meses = [m for m in sorted(work["Mês"].dropna().unique()) if m <= limite_final]
    if not meses:
        return pd.DataFrame()

    fy_atual = int(energia_param_float(db, "fy_atual", 26)) if db is not None else 26
    fy_base = fy_atual - 1
    meta_co2 = energia_param_float(db, "meta_reducao_co2_percentual", 5) / 100 if db is not None else 0.05
    meta_eff = energia_param_float(db, "meta_reducao_eficiencia_percentual", 5) / 100 if db is not None else 0.05
    base_ini, base_fim = energia_intervalo_fy(fy_base)
    base = work[(pd.to_datetime(work["Mês"]) >= pd.to_datetime(base_ini)) & (pd.to_datetime(work["Mês"]) <= pd.to_datetime(base_fim))]
    base_emissoes = base["emissao_total_com_irec_tco2e"].sum() if usar_irec else base["emissao_total_tco2e"].sum()
    base_energia = base["consumo_total_kwh"].sum()
    base_horas = base["actual_hours"].sum()
    base_eff = base_energia / base_horas if base_horas else None
    meta_emissoes = base_emissoes * (1 - meta_co2) if base_emissoes is not None else None
    meta_eficiencia = base_eff * (1 - meta_eff) if base_eff is not None else None

    primeiro_mes_valido = (pd.Timestamp(min(meses_validos)) + pd.DateOffset(months=11)).date()

    rows = []
    for mes in meses:
        if mes < primeiro_mes_valido:
            continue
        ini = energia_r12_start(mes)
        mensal_12 = mensal[(pd.to_datetime(mensal["Mês"]) >= pd.to_datetime(ini)) & (pd.to_datetime(mensal["Mês"]) <= pd.to_datetime(mes))]
        if mensal_12["tem_dado_real"].sum() < 12:
            continue
        f12 = work[(pd.to_datetime(work["Mês"]) >= pd.to_datetime(ini)) & (pd.to_datetime(work["Mês"]) <= pd.to_datetime(mes))]
        emissao = f12["emissao_total_com_irec_tco2e"].sum() if usar_irec else f12["emissao_total_tco2e"].sum()
        energia = f12["consumo_total_kwh"].sum()
        horas = f12["actual_hours"].sum()
        eficiencia = energia / horas if horas and horas > 0 else None
        rows.append({
            "Mês": mes,
            "Emissões R12": emissao,
            "Meta emissões": meta_emissoes,
            "Eficiência energética R12": eficiencia,
            "Meta eficiência energética": meta_eficiencia,
            "FY base": f"FY{fy_base:02d}",
        })
    out = pd.DataFrame(rows)
    if out.empty or out["Eficiência energética R12"].dropna().empty:
        return out

    vals = out["Eficiência energética R12"].dropna()
    if len(vals) >= 6:
        q1 = vals.quantile(0.25)
        q3 = vals.quantile(0.75)
        iqr = q3 - q1
        if iqr > 0:
            lim_inf = max(0, q1 - 1.5 * iqr)
            lim_sup = q3 + 1.5 * iqr
            out.loc[(out["Eficiência energética R12"] < lim_inf) | (out["Eficiência energética R12"] > lim_sup), "Eficiência energética R12"] = None
    return out

def energia_pdf_dashboard(db, r12_mes=None, usar_irec=True):
    """Gera um PDF executivo com os principais elementos do dashboard de energia."""
    df = energia_consolidado(db)
    if df.empty:
        return gerar_pdf("Dashboard Energia e CO₂", "Sem dados disponíveis.", [("Resumo", "Sem dados para gerar o dashboard.")])
    r12_mes = energia_first_day(r12_mes) or energia_default_r12_mes(df) or max(df["Mês"])
    kpis = energia_df_kpis(df, r12_mes, usar_irec)
    tabela = energia_executive_table(db, "Emissões de CO₂ considerando I-REC" if usar_irec else "Emissões de CO₂", r12_mes, usar_irec)
    r12_ini = energia_r12_start(r12_mes)
    r12 = df[(pd.to_datetime(df["Mês"]) >= pd.to_datetime(r12_ini)) & (pd.to_datetime(df["Mês"]) <= pd.to_datetime(r12_mes))]
    por_site = r12.groupby("Site nome", as_index=False).agg({
        "consumo_total_kwh": "sum",
        "emissao_total_tco2e": "sum",
        "emissao_total_com_irec_tco2e": "sum",
        "custo_total_brl": "sum",
        "actual_hours": "sum"
    }) if not r12.empty else pd.DataFrame()
    if not por_site.empty:
        por_site["eficiencia_energetica"] = por_site.apply(lambda r: r["consumo_total_kwh"] / r["actual_hours"] if r["actual_hours"] else None, axis=1)
        por_site = por_site.rename(columns={
            "Site nome": "Site",
            "consumo_total_kwh": "Consumo total kWh",
            "emissao_total_tco2e": "CO₂ sem I-REC",
            "emissao_total_com_irec_tco2e": "CO₂ com I-REC",
            "custo_total_brl": "Custo BRL",
            "actual_hours": "Actual Hours",
            "eficiencia_energetica": "Eficiência"
        })
    metas = energia_tendencia_metas(df, usar_irec, db, r12_mes)
    if not metas.empty:
        metas_pdf = metas.tail(12).rename(columns={
            "Mês": "Mês",
            "Emissões R12": "Emissões R12",
            "Meta emissões": "Meta emissões",
            "Eficiência energética R12": "Eficiência R12",
            "Meta eficiência energética": "Meta eficiência"
        })
    else:
        metas_pdf = pd.DataFrame()
    return gerar_pdf(
        "Dashboard Energia e CO₂",
        f"Referência R12: {r12_mes.strftime('%m/%Y')} | I-REC: {'considerado' if usar_irec else 'não considerado'}",
        [
            ("KPIs principais", kpis),
            ("Resultado R12 por site", por_site),
            ("Evolução de metas — últimos 12 pontos", metas_pdf),
            ("Tabela executiva", tabela.drop(columns=["_grupo"], errors="ignore")),
        ],
    )



def energia_home_kpis(db):
    """Mostra apenas as variações executivas de energia na tela inicial."""
    section("Indicadores de energia e emissões")
    for base in range(0, 4, 4):
        cols = st.columns(4)
        for c, (lab, val, help_) in zip(cols, energia_home_kpi_cards(db)[base:base+4]):
            with c:
                kpi_card(lab, val, help_)

def header(t,s=""): st.markdown(f"<div class='ehs-header'><h1>{t}</h1><p>{s}</p></div>",unsafe_allow_html=True)
def section(t): st.markdown(f"<div class='section-title'>{t}</div>",unsafe_allow_html=True)
def kpi_card(l,v,h=""): st.markdown(f"<div class='kpi'><div class='kpi-label'>{l}</div><div class='kpi-value'>{v}</div><div class='muted'>{h}</div></div>",unsafe_allow_html=True)
def html_escape(v):
    return str(v).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

def kpi_card_contornado(l, v, h="", border="#e5e7eb", tag_bg="#f8fafc"):
    st.markdown(
        f"""
        <div class='kpi' style='border:2px solid {border}; box-shadow:0 10px 25px rgba(31,41,55,.08);'>
            <div style='display:inline-block;border:1px solid {border};background:{tag_bg};color:{border};border-radius:999px;padding:.10rem .48rem;font-size:.68rem;font-weight:900;margin-bottom:.35rem;'>
                {html_escape(str(l).split('•')[0].strip() if '•' in str(l) else 'Indicador')}
            </div>
            <div class='kpi-label'>{html_escape(l)}</div>
            <div class='kpi-value'>{html_escape(v)}</div>
            <div class='muted'>{html_escape(h)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

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
def module_card(t,d,i,border="#e5e7eb",bg="#ffffff"):
    st.markdown(
        f"<div class='card' style='border:2px solid {border}; background:linear-gradient(135deg,{bg},#ffffff);'>"
        f"<h3 style='margin-top:0;color:#111827;'>{i} {html_escape(t)}</h3>"
        f"<p class='muted'>{html_escape(d)}</p></div>",
        unsafe_allow_html=True,
    )

def submodule_card(t,d,i,border="#2563eb"):
    st.markdown(
        f"<div class='card' style='border:2px solid {border}; min-height:155px; background:linear-gradient(135deg,#ffffff,#f8fafc);'>"
        f"<h3 style='margin-top:0;'>{i} {html_escape(t)}</h3>"
        f"<p class='muted'>{html_escape(d)}</p></div>",
        unsafe_allow_html=True,
    )

def descobrir_submodulo_por_pagina(modulo, pagina):
    if modulo == "nr12":
        for nome, cfg in NR12_SUBMODULOS.items():
            if pagina in cfg.get("paginas", []):
                return nome
    if modulo == "ehs":
        for nome, cfg in EHS_SUBMODULOS.items():
            if pagina in cfg.get("paginas", []):
                return nome
    if modulo == "energia":
        for nome, cfg in ENERGIA_SUBMODULOS.items():
            if pagina in cfg.get("paginas", []):
                return nome
    if modulo == "nearmiss":
        for nome, cfg in NEARMISS_SUBMODULOS.items():
            if pagina in cfg.get("paginas", []):
                return nome
    return None

def nome_modulo_visual(modulo):
    return {
        "nr12": NOME_MODULO_MAQUINAS,
        "ehs": "Auditoria Cruzada de Diretrizes EHS",
        "energia": "Controle de Energia e Emissões",
        "nearmiss": NOME_MODULO_NEARMISS,
        "ajuda": AJUDA_PAGE,
    }.get(modulo, "Página inicial")

def render_breadcrumb():
    modulo = st.session_state.get("modulo", "home")
    if modulo == "home":
        return
    if modulo == "nr12":
        pagina = st.session_state.get("page_nr12", NR12_HOME_PAGE)
        home_mod = NR12_HOME_PAGE
    elif modulo == "ehs":
        pagina = st.session_state.get("page_ehs", EHS_HOME_PAGE)
        home_mod = EHS_HOME_PAGE
    elif modulo == "energia":
        pagina = st.session_state.get("page_energia", ENERGIA_HOME_PAGE)
        home_mod = ENERGIA_HOME_PAGE
    elif modulo == "nearmiss":
        pagina = st.session_state.get("page_nearmiss", NEARMISS_HOME_PAGE)
        home_mod = NEARMISS_HOME_PAGE
    elif modulo == "ajuda":
        pagina = AJUDA_PAGE
        home_mod = AJUDA_PAGE
    else:
        pagina = "—"
        home_mod = "—"
    partes = ["Início", nome_modulo_visual(modulo)]
    sub = descobrir_submodulo_por_pagina(modulo, pagina)
    if sub:
        partes.append(sub)
    if pagina and pagina not in [home_mod, sub]:
        partes.append(pagina)
    html = "<span>" + "</span><span class='sep'>›</span><span>".join(html_escape(x) for x in partes if x) + "</span>"
    st.markdown(f"<div class='breadcrumb-wrap'>{html}</div>", unsafe_allow_html=True)

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
def _auto_streamlit_key(prefix, base=""):
    chave_contador = f"_{prefix}_auto_counter"
    st.session_state[chave_contador] = int(st.session_state.get(chave_contador, 0)) + 1
    base_txt = str(base or prefix).encode("utf-8", errors="ignore")
    return f"{prefix}_{zlib.crc32(base_txt)}_{st.session_state[chave_contador]}"

def plotly_chart_safe(fig, *args, **kwargs):
    if kwargs.get("key") is None:
        kwargs["key"] = _auto_streamlit_key("plotly_chart", getattr(fig, "layout", ""))
    return st.__getattribute__("plotly_chart")(fig, *args, **kwargs)

def download_excel_button(label,file,sheets,key=None):
    if key is None:
        key = _auto_streamlit_key("download_excel", f"{label}|{file}")
    st.download_button(label,gerar_excel(sheets),file,mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True,key=key)

def download_pdf_button(label,file,pdf,key=None):
    if key is None:
        key = _auto_streamlit_key("download_pdf", f"{label}|{file}")
    st.download_button(label,pdf,file,mime="application/pdf",use_container_width=True,key=key)

def df_maquinas(db,ids):
    rows = []
    for m in db.query(MaquinaNR12).filter(MaquinaNR12.site_id.in_(ids)).order_by(MaquinaNR12.codigo):
        risco = m.risco_maquina or ("Desprezível" if m.possui_apreciacao_risco else "Apreciação de risco não realizada")
        rows.append({"ID":m.id,"Código":m.codigo,"Site":site_code(db,m.site_id),"Área":m.area_setor,"Linha":m.linha_processo,"Máquina":m.nome,"Fabricante":m.fabricante,"Modelo":m.modelo,"Série":m.numero_serie,"Ano":m.ano,"Tipo":m.tipo_equipamento,"Responsável":m.responsavel_area,"Criticidade":m.criticidade,"Risco":risco,"Status de Proteção":calcular_status_maquina_nr12(db,m),"Data prevista adequação":fmt_date(getattr(m,"data_prevista_adequacao",None)),"Próxima auditoria":fmt_date(m.proxima_auditoria),"Laudo":"Sim" if m.possui_laudo else "Não","ART":"Sim" if m.possui_art else "Não","Apreciação":"Sim" if m.possui_apreciacao_risco else "Não","Manual":"Sim" if m.possui_manual_atualizado else "Não","Treinamento":"Sim" if m.possui_treinamento else "Não","Observações":m.observacoes})
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


def dashboard_integrado(db,u):
    ids=visible_site_ids(u,db); update_vencidos(db)
    ms=db.query(MaquinaNR12).filter(MaquinaNR12.site_id.in_(ids)).all()
    auds=db.query(AuditoriaCruzada).filter(AuditoriaCruzada.site_auditado_id.in_(ids)).all()
    conf=[calcular_conformidade_ehs(db.query(RespostaAuditoriaEHS).filter_by(auditoria_id=a.id).all()) for a in auds]
    cards = [
        ("Máquinas • Total de máquinas", len(ms), "Sustentação de Proteções de Máquinas"),
        ("Máquinas • Não conformes", sum(1 for m in ms if calcular_status_maquina_nr12(db,m)=="Não conforme"), "Sustentação de Proteções de Máquinas"),
        ("Máquinas • PACs vencidos", db.query(PACNR12).filter(PACNR12.site_id.in_(ids),PACNR12.status=="Vencida").count(), "Sustentação de Proteções de Máquinas"),
        ("Máquinas • PACs abertos", db.query(PACNR12).filter(PACNR12.site_id.in_(ids),PACNR12.status.in_(["Aberta","Em andamento","Aguardando validação"])).count(), "Sustentação de Proteções de Máquinas"),
        ("Auditoria EHS • Em andamento", db.query(AuditoriaCruzada).filter(AuditoriaCruzada.site_auditado_id.in_(ids),AuditoriaCruzada.status=="Em andamento").count(), "Auditoria Cruzada"),
        ("Auditoria EHS • Conformidade média", f"{round(sum(conf)/len(conf),1) if conf else 0}%", "Auditoria Cruzada"),
        ("Auditoria EHS • PACs vencidos", db.query(PACEHS).filter(PACEHS.site_id.in_(ids),PACEHS.status=="Vencida").count(), "Auditoria Cruzada"),
        ("Auditoria EHS • NC críticas", db.query(PACEHS).filter(PACEHS.site_id.in_(ids),PACEHS.tipo_achado=="Não conformidade crítica",PACEHS.status.in_(["Aberta","Em andamento","Vencida"])).count(), "Auditoria Cruzada"),
    ]
    cards.extend(energia_home_kpi_cards(db))
    cards.extend(near_miss_home_kpi_cards(db))
    section("Visão geral integrada")
    module_colors = {
        "Máquinas": ("#2563eb", "#eff6ff"),
        "Auditoria EHS": ("#7c3aed", "#f5f3ff"),
        "Energia": ("#16a34a", "#ecfdf5"),
        "Near Miss": ("#f97316", "#fff7ed"),
    }
    for base in range(0,len(cards),4):
        cols=st.columns(4)
        for c,(lab,val,help_) in zip(cols,cards[base:base+4]):
            with c:
                modulo = str(lab).split("•")[0].strip() if "•" in str(lab) else "Indicador"
                border, tag_bg = module_colors.get(modulo, ("#e5e7eb", "#f8fafc"))
                kpi_card_contornado(lab,val,help_,border,tag_bg)
    alerts=[]
    for p in db.query(PACNR12).filter(PACNR12.site_id.in_(ids),PACNR12.status.in_(["Vencida","Aberta","Em andamento"])).limit(5): 
        if p.status=="Vencida" or p.classificacao=="Crítico": alerts.append({"Módulo":"Proteções de Máquinas","Tipo":p.classificacao,"Site":site_code(db,p.site_id),"Descrição":(p.descricao_desvio or "")[:120],"Prazo":fmt_date(p.prazo),"Status":p.status})
    for p in db.query(PACEHS).filter(PACEHS.site_id.in_(ids),PACEHS.status.in_(["Vencida","Aberta","Em andamento"])).limit(5):
        if p.status=="Vencida" or p.tipo_achado=="Não conformidade crítica": alerts.append({"Módulo":"Auditoria EHS","Tipo":p.tipo_achado,"Site":site_code(db,p.site_id),"Descrição":(p.descricao or "")[:120],"Prazo":fmt_date(p.prazo),"Status":p.status})
    section("Alertas principais")
    if alerts:
        st.dataframe(pd.DataFrame(alerts), use_container_width=True, hide_index=True)
    else:
        empty_state("Nenhum alerta crítico ou vencido identificado.")

def home_page(db,u):
    header("Plataforma Integrada EHS","Sustentação de Proteções de Máquinas, Auditorias Cruzadas, Controle de Energia e Emissões e Near Miss")
    section("Módulos")
    c1,c2=st.columns(2)
    with c1:
        mc=MODULO_COLOR_MAP["maquinas"]
        module_card(NOME_MODULO_MAQUINAS,"Inventário, documentos, checklists, PAC, pendências e relatórios de proteções de máquinas.",mc["icon"],mc["border"],mc["bg"])
        if st.button(f"Acessar {NOME_MODULO_MAQUINAS}",use_container_width=True):
            st.session_state.modulo="nr12"
            st.session_state.page_nr12=NR12_HOME_PAGE
            st.session_state.nav_nr12=NR12_HOME_PAGE
            st.session_state.submodulo_nr12=""
            st.rerun()
        ec=MODULO_COLOR_MAP["energia"]
        module_card("Controle de Energia e Emissões","Consumo de energia, gás natural, CO₂, gastos, eficiência energética, R12, FY e análise I-REC.",ec["icon"],ec["border"],ec["bg"])
        if st.button("Acessar Controle de Energia",use_container_width=True):
            st.session_state.modulo="energia"
            st.session_state.page_energia=ENERGIA_HOME_PAGE
            st.session_state.nav_energia=ENERGIA_HOME_PAGE
            st.session_state.submodulo_energia=""
            st.rerun()
    with c2:
        ac=MODULO_COLOR_MAP["auditoria"]
        module_card("Auditoria Cruzada de Diretrizes de EHS","Planejamento, checklist incorporado, evidências, maturidade, PAC e relatórios.",ac["icon"],ac["border"],ac["bg"])
        if st.button("Acessar Auditoria Cruzada",use_container_width=True):
            st.session_state.modulo="ehs"
            st.session_state.page_ehs=EHS_HOME_PAGE
            st.session_state.nav_ehs=EHS_HOME_PAGE
            st.session_state.submodulo_ehs=""
            st.rerun()
        nm=MODULO_COLOR_MAP["nearmiss"]
        module_card("Near Miss","Concern Reports, near misses, acompanhamento de prazos, fechamento no prazo e pendências por site/divisão.",nm["icon"],nm["border"],nm["bg"])
        if st.button("Acessar Near Miss",use_container_width=True):
            st.session_state.modulo="nearmiss"
            st.session_state.page_nearmiss=NEARMISS_HOME_PAGE
            st.session_state.nav_nearmiss=NEARMISS_HOME_PAGE
            st.session_state.submodulo_nearmiss=""
            st.rerun()

    dashboard_integrado(db,u)

    section("Ajuda")
    c_help, c_empty = st.columns([1,3])
    with c_help:
        if st.button("❔ Abrir ajuda rápida", use_container_width=True, key="home_ajuda_rapida"):
            st.session_state.modulo="ajuda"
            st.rerun()

def nr12_submodulos_home(db,u):
    header(NOME_MODULO_MAQUINAS, "Escolha um submódulo para visualizar, editar ou governar as informações de sustentação.")
    top_back_col, top_spacer_col = st.columns([1.1, 5])
    with top_back_col:
        if st.button("⬅️ Voltar para página inicial", key="nr12_home_voltar_inicio", use_container_width=True):
            st.session_state.modulo = "home"
            st.rerun()
    section("Submódulos")
    nomes=list(NR12_SUBMODULOS.keys())
    for base in range(0, len(nomes), 2):
        cols=st.columns(2)
        for col, nome in zip(cols, nomes[base:base+2]):
            cfg=NR12_SUBMODULOS[nome]
            with col:
                submodule_card(nome, cfg["descricao"], cfg["icone"], cfg["cor"])
                if st.button(f"Acessar {nome}", key=f"btn_submodulo_{nome}", use_container_width=True):
                    destino=cfg["paginas"][0]
                    if destino=="Logs do Sistema" and not can_admin(u):
                        destino=cfg["paginas"][1] if len(cfg["paginas"]) > 1 else NR12_HOME_PAGE
                    st.session_state.submodulo_nr12=nome
                    st.session_state.page_nr12=destino
                    st.session_state.nav_nr12=destino
                    st.rerun()
    section("Resumo rápido")
    ids=visible_site_ids(u,db)
    ms=db.query(MaquinaNR12).filter(MaquinaNR12.site_id.in_(ids)).all()
    dfp=df_pac_nr12(db,ids)
    c1,c2,c3,c4=st.columns(4)
    c1.metric("Máquinas", len(ms))
    c2.metric("Não conformes", sum(1 for m in ms if calcular_status_maquina_nr12(db,m)=="Não conforme"))
    c3.metric("PACs abertos", 0 if dfp.empty else int(dfp["Status"].isin(["Aberta","Em andamento","Aguardando validação"]).sum()))
    c4.metric("Verificações vencidas", sum(1 for m in ms if m.proxima_auditoria and m.proxima_auditoria<date.today()))

def nr12_dashboard(db,u):
    header("Sustentação de Proteções de Máquinas","Dashboard para acompanhamento de máquinas, proteções e dispositivos de segurança")
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
    status_f=f4.multiselect("Status de Proteção", [s for s in STATUS_MAQUINA if s in set(dfm_full["Status de Proteção"].dropna())])
    dfm=dfm_full.copy()
    if unidades: dfm=dfm[dfm["Site"].isin(unidades)]
    if riscos: dfm=dfm[dfm["Risco"].isin(riscos)]
    if crits: dfm=dfm[dfm["Criticidade"].isin(crits)]
    if status_f: dfm=dfm[dfm["Status de Proteção"].isin(status_f)]
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
    cols=st.columns(len(RISCOS_MAQUINA))
    for c,risco_nome in zip(cols,RISCOS_MAQUINA):
        with c:
            estilo=RISCO_CARD_STYLE_MAP.get(risco_nome,{"bg":"#ffffff","fg":"#111827","border":"#e5e7eb"})
            kpi_card_colorido(risco_nome,risco_dict.get(risco_nome,0),"Máquinas nesse nível de risco",estilo["bg"],estilo["fg"],estilo["border"])

    section("Gráficos")
    c1,c2=st.columns(2)
    with c1:
        plotly_chart_safe(px.histogram(dfm, x="Site", color="Status de Proteção", barmode="group", title="Status de conformidade por unidade", color_discrete_map=STATUS_COLOR_MAP).update_layout(template="plotly_white"), use_container_width=True)
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
        plotly_chart_safe(fig_risco, use_container_width=True)
    c3,c4=st.columns(2)
    with c3:
        if not dfp.empty:
            plotly_chart_safe(px.histogram(dfp, x="Status", color="Classificação", barmode="group", title="PAC por status/classificação", color_discrete_map=PAC_COLOR_MAP).update_layout(template="plotly_white"), use_container_width=True)
        else:
            empty_state("Sem PACs para os filtros selecionados.")
    with c4:
        verificacoes_vencidas=sum(1 for m in ms if m.proxima_auditoria and m.proxima_auditoria<date.today())
        verificacoes_proximas=sum(1 for m in ms if m.proxima_auditoria and date.today()<=m.proxima_auditoria<=date.today()+timedelta(days=60))
        dv=pd.DataFrame([{"Tipo":"Vencidas","Qtd":verificacoes_vencidas},{"Tipo":"Próximas","Qtd":verificacoes_proximas}])
        plotly_chart_safe(px.bar(dv,x="Tipo",y="Qtd",color="Tipo",title="Verificações vencidas/próximas", color_discrete_map={"Vencidas":"#dc2626","Próximas":"#f59e0b"}).update_layout(template="plotly_white", showlegend=False),use_container_width=True)

    section("Evolução esperada da adequação de proteções de máquinas")
    evolucao=montar_evolucao_adequacao_nr12(db,ms)
    if not evolucao.empty:
        plotly_chart_safe(
            px.line(evolucao, x="Data", y="% Adequação", color="Série", markers=True,
                    hover_data=["Quantidade"], title="Evolução esperada da adequação com base na Data Prevista para Adequação")
              .update_layout(template="plotly_white", yaxis_range=[0,100], xaxis_title="Data", yaxis_title="% de máquinas adequadas"),
            use_container_width=True
        )
    else:
        empty_state("Sem datas previstas de adequação cadastradas para gerar a evolução esperada.")

    section("Máquinas prioritárias")
    pr=dfm[dfm["Status de Proteção"]=="Não conforme"] if not dfm.empty else pd.DataFrame()
    if not pr.empty:
        st.dataframe(pr, use_container_width=True, hide_index=True)
    else:
        empty_state("Nenhuma máquina prioritária nos filtros selecionados.")

def nr12_inventario(db,u):
    header("Inventário de Máquinas","Cadastro, edição, consulta e exportação")
    ids=visible_site_ids(u,db)
    sites={s.codigo:s.id for s in db.query(Site).filter(Site.id.in_(ids)).order_by(Site.codigo)}

    section("Consulta")
    df=df_maquinas(db,ids)
    if df.empty:
        empty_state("Nenhuma máquina cadastrada.")
    else:
        f1,f2,f3,f4=st.columns(4)
        fs=f1.multiselect("Filtrar status",sorted(df["Status de Proteção"].dropna().unique()))
        fr=f2.multiselect("Filtrar risco",[r for r in RISCOS_MAQUINA if r in set(df["Risco"].dropna())])
        fc=f3.multiselect("Filtrar criticidade",sorted(df["Criticidade"].dropna().unique()))
        fu=f4.multiselect("Filtrar unidade",sorted(df["Site"].dropna().unique()))
        f=df.copy()
        if fs: f=f[f["Status de Proteção"].isin(fs)]
        if fr: f=f[f["Risco"].isin(fr)]
        if fc: f=f[f["Criticidade"].isin(fc)]
        if fu: f=f[f["Site"].isin(fu)]
        st.dataframe(f,use_container_width=True,hide_index=True)
        download_excel_button("Exportar Excel","inventario_maquinas_nr12.xlsx",{"Inventário":f})

    if can_edit(u,"nr12_manutencao"):
        if not sites:
            alert_card("Nenhum site disponível para cadastro conforme o perfil do usuário.")
        else:
            with st.expander("Cadastrar máquina"):
                a,b,c=st.columns(3)
                with a:
                    cod=st.text_input("Código*", key="maq_new_codigo")
                    site=st.selectbox("Site*",list(sites), key="maq_new_site")
                    area=st.text_input("Área/setor", key="maq_new_area")
                    linha=st.text_input("Linha/processo", key="maq_new_linha")
                    nome=st.text_input("Nome*", key="maq_new_nome")
                    fab=st.text_input("Fabricante", key="maq_new_fabricante")
                with b:
                    mod=st.text_input("Modelo", key="maq_new_modelo")
                    serie=st.text_input("Número de série", key="maq_new_serie")
                    ano=st.text_input("Ano", key="maq_new_ano")
                    tipo=st.text_input("Tipo de equipamento", key="maq_new_tipo")
                    resp=st.text_input("Responsável da área", key="maq_new_resp")
                    crit=st.selectbox("Criticidade",CRITICIDADES, key="maq_new_criticidade")
                with c:
                    risco=st.selectbox("Risco da máquina",RISCOS_MAQUINA, key="maq_new_risco")
                    status=st.selectbox("Status de Proteção",STATUS_MAQUINA, key="maq_new_status")
                    limite_prox=data_limite_por_frequencia(db,"Auditoria EHS",crit,date.today())
                    prox=st.date_input("Próxima auditoria prevista",value=limite_prox, max_value=limite_prox, help=f"Limite pela criticidade {crit}: {fmt_date(limite_prox)}.", key="maq_new_prox")
                    data_prevista_adequacao=None
                    if status!="Conforme":
                        data_prevista_adequacao=st.date_input(
                            "Data prevista para adequação",
                            value=date.today()+timedelta(days=90),
                            help="Obrigatória para máquinas com status diferente de Conforme.",
                            key="maq_new_data_prevista_adequacao",
                        )
                    else:
                        st.caption("Máquina conforme: data prevista para adequação não aplicável.")
                st.caption("Laudo, ART, apreciação de risco, manual e treinamento devem ser controlados pela aba Documentos de Proteções de Máquinas.")
                obs=st.text_area("Observações", key="maq_new_obs")
                if st.button("Salvar máquina",use_container_width=True,key="maq_new_salvar"):
                    ok_limite, limite_prox_calc, msg_limite = validar_data_dentro_limite(db,"Auditoria EHS",crit,prox,date.today())
                    if not ok_limite:
                        st.error(msg_limite)
                    elif cod and nome and not db.query(MaquinaNR12).filter_by(codigo=cod).first():
                        nova=MaquinaNR12(
                            codigo=cod,site_id=sites[site],area_setor=area,linha_processo=linha,nome=nome,
                            fabricante=fab,modelo=mod,numero_serie=serie,ano=ano,tipo_equipamento=tipo,
                            responsavel_area=resp,criticidade=crit,risco_maquina=risco,status_nr12=status,
                            proxima_auditoria=prox,data_prevista_adequacao=data_prevista_adequacao,
                            possui_laudo=False,possui_art=False,possui_apreciacao_risco=False,
                            possui_manual_atualizado=False,possui_treinamento=False,observacoes=obs,
                        )
                        db.add(nova); db.flush()
                        registrar_log(db,u,NOME_MODULO_MAQUINAS,"MaquinaNR12",nova.id,"criar",observacao=f"Máquina {cod} cadastrada")
                        db.commit()
                        st.success("Máquina cadastrada.")
                        st.rerun()
                    else:
                        st.error("Preencha código/nome e evite código duplicado.")

    if can_edit(u,"nr12_manutencao"):
        opts=machine_options(db,ids)
        if opts:
            with st.expander("Editar máquina"):
                lab=st.selectbox("Máquina",list(opts),key="nr12_editar_maquina_select")
                m=db.get(MaquinaNR12,opts[lab])
                status_atual=normalizar_status_nr12(m.status_nr12)
                e1,e2,e3=st.columns(3)
                with e1:
                    novo_status=st.selectbox("Status de Proteção",STATUS_MAQUINA,index=STATUS_MAQUINA.index(status_atual),key=f"editmaq_status_{m.id}")
                    nova_criticidade=st.selectbox("Criticidade",CRITICIDADES,index=CRITICIDADES.index(m.criticidade) if m.criticidade in CRITICIDADES else 1,key=f"editmaq_criticidade_{m.id}")
                with e2:
                    risco_atual=m.risco_maquina or "Apreciação de risco não realizada"
                    novo_risco=st.selectbox("Risco da máquina",RISCOS_MAQUINA,index=RISCOS_MAQUINA.index(risco_atual) if risco_atual in RISCOS_MAQUINA else 0,key=f"editmaq_risco_{m.id}")
                    limite_edit=data_limite_por_frequencia(db,"Auditoria EHS",nova_criticidade,m.ultima_auditoria or date.today())
                    valor_prox_atual=m.proxima_auditoria or limite_edit
                    if valor_prox_atual > limite_edit:
                        valor_prox_atual=limite_edit
                    nova_proxima_auditoria=st.date_input("Próxima auditoria prevista",value=valor_prox_atual,max_value=limite_edit,help=f"Limite pela criticidade {nova_criticidade}: {fmt_date(limite_edit)}.",key=f"editmaq_prox_{m.id}")
                with e3:
                    nova_data_prevista=None
                    if novo_status!="Conforme":
                        nova_data_prevista=st.date_input(
                            "Data prevista para adequação",
                            value=m.data_prevista_adequacao or date.today()+timedelta(days=90),
                            help="Use esta data para compor a meta e a evolução esperada de adequação.",
                            key=f"editmaq_data_prevista_{m.id}",
                        )
                    else:
                        st.caption("Máquina conforme: data prevista para adequação será limpa ao salvar.")
                novas_observacoes=st.text_area("Observações",m.observacoes or "",key=f"editmaq_obs_{m.id}")
                if st.button("Atualizar máquina",use_container_width=True,key=f"editmaq_atualizar_{m.id}"):
                    ok_limite, limite_prox_calc, msg_limite = validar_data_dentro_limite(db,"Auditoria EHS",nova_criticidade,nova_proxima_auditoria,m.ultima_auditoria or date.today())
                    if not ok_limite:
                        st.error(msg_limite)
                        st.stop()
                    status_anterior=m.status_nr12
                    m.status_nr12=novo_status
                    m.criticidade=nova_criticidade
                    m.risco_maquina=novo_risco
                    m.proxima_auditoria=nova_proxima_auditoria
                    m.data_prevista_adequacao=None if novo_status=="Conforme" else nova_data_prevista
                    m.observacoes=novas_observacoes
                    registrar_log(db,u,NOME_MODULO_MAQUINAS,"MaquinaNR12",m.id,"editar","status_nr12",status_anterior,novo_status,observacao=f"Máquina {m.codigo} atualizada")
                    db.commit()
                    st.success("Atualizado.")
                    st.rerun()

def nr12_documentos(db,u):
    header("Documentos de Proteções de Máquinas","Controle de documentos essenciais, validade, evidências e anexos")
    ids=visible_site_ids(u,db)
    opts=machine_options(db,ids)

    section("Consulta")
    df=df_docs(db,ids)
    if not df.empty:
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        empty_state("Nenhum documento.")
    download_excel_button("Exportar documentos Excel","documentos_nr12.xlsx",{"Documentos":df})

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
                    registrar_log(db,u,NOME_DOCS_MAQUINAS,"DocumentoNR12",None,"criar",observacao=f"Documento {tipo} salvo para {m.codigo}")
                    db.commit()
                    st.success("Documento salvo.")
                    st.rerun()

def nr12_checklists(db,u):
    header("Checklists e Inspeções de Proteções de Máquinas", "Registro por máquina, pontuação e geração automática de PAC")
    ids = visible_site_ids(u, db)
    opts = machine_options(db, ids)

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
                        "Ordem":getattr(r,"ordem_snapshot",None) or (r.item.ordem if r.item else "—"),
                        "Pergunta":getattr(r,"pergunta_snapshot",None) or (r.item.pergunta if r.item else "—"),
                        "Item crítico":"Sim" if (getattr(r,"item_critico_snapshot",False) or (r.item and r.item.item_critico)) else "Não",
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

    section("Tipo de checklist")
    if not opts:
        empty_state("Cadastre uma máquina antes.")
        return
    if not can_edit(u, "nr12_operacao"):
        alert_card("Seu perfil permite consulta, mas não registro.")
        return

    tipos_db = [t for t in sorted({t for t, in db.query(ChecklistItemNR12.tipo_checklist).distinct().all()} | {t for t, in db.query(ChecklistVersaoMaquinas.tipo_checklist).distinct().all()} | set(TIPOS_VERIFICACAO_NR12)) if t != "Checklist operacional"]
    tipo = st.selectbox("Tipo de checklist", tipos_db, key="nr12_tipo_checklist_selector")
    versao = get_versao_ativa_maquinas(db, tipo)
    if versao:
        itens = db.query(ChecklistPerguntaVersaoMaquinas).filter_by(checklist_versao_id=versao.id, ativo=True).order_by(ChecklistPerguntaVersaoMaquinas.ordem).all()
        st.caption(f"Versão ativa do checklist: v{versao.versao} — {versao.descricao or 'sem descrição'}")
    else:
        itens = db.query(ChecklistItemNR12).filter_by(tipo_checklist=tipo, ativo=True).order_by(ChecklistItemNR12.ordem).all()
        st.warning("Este tipo ainda não possui versão ativa. O checklist atual será usado como base; crie uma versão na Base de Checklists de Proteções.")
    section("Checklist")
    with st.form(f"ver_{tipo}"):
        lab = st.selectbox("Máquina", list(opts), key=f"maq_{tipo}")
        resp = st.text_input("Responsável", u.nome, key=f"resp_{tipo}")
        obs = st.text_area("Observações", key=f"obs_{tipo}")
        temp = []
        for it in itens:
            critico = bool(getattr(it, "item_critico", False))
            gera_auto = bool(getattr(it, "gera_pac_automatico", False))
            st.markdown(
                f"<div class='check-item'><div class='check-q'>{it.ordem}. {it.pergunta}"
                f"{'<span class="check-meta">Crítico</span>' if critico else ''}"
                f"{'<span class="check-meta">PAC auto</span>' if gera_auto else ''}</div></div>",
                unsafe_allow_html=True,
            )
            c1, c2, c3, c4 = st.columns([1, 1.3, 2.6, 1])
            apl = c1.checkbox("Aplicável", True, key=f"nr12_ap_{tipo}_{it.id}")
            res = c2.selectbox("Resultado", RESULTADOS_NR12, key=f"nr12_rr_{tipo}_{it.id}")
            com = c3.text_input("Comentário/evidência", key=f"nr12_co_{tipo}_{it.id}")
            gp = c4.checkbox("Gerar PAC", gera_auto, key=f"nr12_gp_{tipo}_{it.id}")
            temp.append((it, apl, res, com, gp))
        if st.form_submit_button("Salvar verificação", use_container_width=True):
            m = db.get(MaquinaNR12, opts[lab])
            proxima_data = data_limite_por_frequencia(db, tipo, m.criticidade, date.today())
            v = VerificacaoNR12(
                maquina_id=m.id, site_id=m.site_id, tipo=tipo, data_verificacao=date.today(),
                responsavel=resp, observacoes=obs, proxima_verificacao=proxima_data,
                versao_checklist_id=versao.id if versao else None,
            )
            db.add(v); db.flush()
            rs = []
            for it, apl, res, com, gp in temp:
                item_base_id = getattr(it, "item_base_id", None) or (it.id if isinstance(it, ChecklistItemNR12) else None)
                critico = bool(getattr(it, "item_critico", False))
                gera_auto = bool(getattr(it, "gera_pac_automatico", False))
                r = RespostaNR12(
                    verificacao_id=v.id, item_id=item_base_id, aplicavel=apl,
                    resultado="Não aplicável" if not apl else res, comentario_evidencia=com, gerar_pac=gp,
                    ordem_snapshot=getattr(it, "ordem", None), pergunta_snapshot=getattr(it, "pergunta", None),
                    item_critico_snapshot=critico, gera_pac_automatico_snapshot=gera_auto,
                )
                db.add(r); rs.append(r)
            db.flush()
            v.resultado, v.pontuacao, v.possui_nc_critica = calcular_resultado_verificacao_nr12(rs)
            m.ultima_auditoria = date.today(); m.proxima_auditoria = v.proxima_verificacao
            m.status_nr12 = v.resultado if v.resultado in STATUS_MAQUINA else normalizar_status_nr12(m.status_nr12)
            for r in rs:
                if r.resultado == "Não conforme" or r.gerar_pac or getattr(r, "gera_pac_automatico_snapshot", False):
                    gerar_pac_automatico_nr12(db, v, r, resp)
            registrar_log(db,u,NOME_CHECKLISTS_MAQUINAS,"VerificacaoNR12",v.id,"criar",observacao=f"Checklist {tipo} registrado para {m.codigo}")
            db.commit()
            st.success(f"Verificação salva: {v.resultado} | {v.pontuacao}%")
            st.rerun()

def nr12_base_checklists(db,u):
    header("Base de Checklists de Proteções", "Gestão da base editável e versionada de perguntas")
    if not can_edit(u,"nr12_manutencao"):
        alert_card("Seu perfil permite consulta, mas não administração da base de checklists.")
    tipos = sorted({t for t, in db.query(ChecklistItemNR12.tipo_checklist).distinct().all()} | {t for t, in db.query(ChecklistVersaoMaquinas.tipo_checklist).distinct().all()} | set(TIPOS_VERIFICACAO_NR12))
    if not tipos:
        empty_state("Nenhum tipo de checklist cadastrado.")
        return
    c1,c2 = st.columns([2,1])
    tipo = c1.selectbox("Tipo de checklist", tipos, key="base_checklist_tipo")
    versoes = db.query(ChecklistVersaoMaquinas).filter_by(tipo_checklist=tipo).order_by(ChecklistVersaoMaquinas.versao.desc()).all()
    ativa = get_versao_ativa_maquinas(db,tipo)
    c2.metric("Versão ativa", f"v{ativa.versao}" if ativa else "—")

    if can_edit(u,"nr12_manutencao"):
        ac1,ac2 = st.columns(2)
        with ac1:
            if st.button("Criar nova versão a partir da ativa", use_container_width=True):
                nova = criar_versao_checklist_maquinas(db,tipo,u.nome,"Nova versão criada pelo app",ativa)
                registrar_log(db,u,NOME_CHECKLISTS_MAQUINAS,"ChecklistVersaoMaquinas",nova.id,"criar",observacao=f"Nova versão v{nova.versao} para {tipo}")
                db.commit(); st.success(f"Versão v{nova.versao} criada e ativada."); st.rerun()
        with ac2:
            if ativa and st.button("Inativar versão ativa", use_container_width=True):
                ativa.ativo=False
                registrar_log(db,u,NOME_CHECKLISTS_MAQUINAS,"ChecklistVersaoMaquinas",ativa.id,"inativar",observacao=f"Versão v{ativa.versao} inativada")
                db.commit(); st.warning("Versão inativada. Crie/ative outra versão antes de novos registros."); st.rerun()
        with st.expander("Criar novo tipo de checklist", expanded=False):
            nt1,nt2=st.columns([3,1])
            novo_tipo = nt1.text_input("Nome do novo tipo de checklist", key="novo_tipo_checklist")
            if nt2.button("Criar tipo", use_container_width=True) and novo_tipo.strip():
                item = ChecklistItemNR12(tipo_checklist=novo_tipo.strip(), ordem=1, pergunta="Nova pergunta a editar", item_critico=False, gera_pac_automatico=False, ativo=True)
                db.add(item); db.flush()
                nova = criar_versao_checklist_maquinas(db,novo_tipo.strip(),u.nome,"Versão inicial criada pelo app")
                registrar_log(db,u,NOME_CHECKLISTS_MAQUINAS,"ChecklistVersaoMaquinas",nova.id,"criar",observacao=f"Tipo {novo_tipo} criado")
                db.commit(); st.success("Tipo criado."); st.rerun()

    section("Versões cadastradas")
    dfv = pd.DataFrame([{"ID":v.id,"Tipo":v.tipo_checklist,"Versão":v.versao,"Ativo":v.ativo,"Criado por":v.criado_por,"Criado em":fmt_date(v.criado_em),"Descrição":v.descricao} for v in versoes])
    st.dataframe(dfv, use_container_width=True, hide_index=True)
    if ativa:
        section("Perguntas da versão ativa")
        perguntas = db.query(ChecklistPerguntaVersaoMaquinas).filter_by(checklist_versao_id=ativa.id).order_by(ChecklistPerguntaVersaoMaquinas.ordem).all()
        dfp = pd.DataFrame([{"ID":p.id,"Ordem":p.ordem,"Pergunta":p.pergunta,"Crítico":p.item_critico,"Gerar PAC automático":p.gera_pac_automatico,"Ativo":p.ativo} for p in perguntas])
        if dfp.empty:
            empty_state("Versão sem perguntas cadastradas.")
        elif can_edit(u,"nr12_manutencao"):
            ed = st.data_editor(dfp, use_container_width=True, hide_index=True, disabled=["ID"], num_rows="fixed")
            if st.button("Salvar alterações das perguntas", use_container_width=True):
                for _, row in ed.iterrows():
                    obj = db.get(ChecklistPerguntaVersaoMaquinas, int(row["ID"]))
                    if obj:
                        antes = obj.pergunta
                        obj.ordem = int(row["Ordem"]) if pd.notna(row["Ordem"]) else obj.ordem
                        obj.pergunta = str(row["Pergunta"])
                        obj.item_critico = bool(row["Crítico"])
                        obj.gera_pac_automatico = bool(row["Gerar PAC automático"])
                        obj.ativo = bool(row["Ativo"])
                        if obj.item_base_id:
                            base_item = db.get(ChecklistItemNR12, obj.item_base_id)
                            if base_item:
                                base_item.ordem = obj.ordem
                                base_item.pergunta = obj.pergunta
                                base_item.item_critico = obj.item_critico
                                base_item.gera_pac_automatico = obj.gera_pac_automatico
                                base_item.ativo = obj.ativo
                        if antes != obj.pergunta:
                            registrar_log(db,u,NOME_CHECKLISTS_MAQUINAS,"ChecklistPerguntaVersaoMaquinas",obj.id,"editar","pergunta",antes,obj.pergunta)
                db.commit(); st.success("Perguntas atualizadas. A base editável também foi sincronizada para futuras versões."); st.rerun()
            with st.expander("Adicionar pergunta à versão ativa"):
                with st.form("add_pergunta_checklist_maquinas"):
                    prox_ordem = (max([p.ordem or 0 for p in perguntas]) + 1) if perguntas else 1
                    ordem = st.number_input("Ordem", min_value=1, value=prox_ordem)
                    pergunta = st.text_area("Pergunta")
                    crit = st.checkbox("Item crítico")
                    pac_auto = st.checkbox("Gerar PAC automático quando houver não conformidade")
                    if st.form_submit_button("Adicionar", use_container_width=True):
                        if pergunta.strip():
                            base_item = ChecklistItemNR12(tipo_checklist=tipo, ordem=int(ordem), pergunta=pergunta.strip(), item_critico=crit, gera_pac_automatico=pac_auto, ativo=True)
                            db.add(base_item); db.flush()
                            obj = ChecklistPerguntaVersaoMaquinas(checklist_versao_id=ativa.id, item_base_id=base_item.id, ordem=int(ordem), pergunta=pergunta.strip(), item_critico=crit, gera_pac_automatico=pac_auto, ativo=True)
                            db.add(obj); db.flush()
                            registrar_log(db,u,NOME_CHECKLISTS_MAQUINAS,"ChecklistPerguntaVersaoMaquinas",obj.id,"criar",observacao=f"Pergunta adicionada à v{ativa.versao}")
                            db.commit(); st.success("Pergunta adicionada."); st.rerun()
                        else:
                            st.error("Informe a pergunta.")
        else:
            st.dataframe(dfp, use_container_width=True, hide_index=True)
        download_excel_button("Exportar base de checklists", "base_checklists_protecoes.xlsx", {"Versoes": dfv, "Perguntas_Ativas": dfp})

def render_calendario_mensal(df_eventos, mes_ref):
    mes_ref = as_date(mes_ref) or date.today().replace(day=1)
    ano, mes = mes_ref.year, mes_ref.month
    cal = calendar.Calendar(firstweekday=0)
    semanas = cal.monthdatescalendar(ano, mes)
    df = df_eventos.copy() if df_eventos is not None else pd.DataFrame()
    if not df.empty:
        df["Data"] = pd.to_datetime(df["Data"]).dt.date
    eventos_por_data = {}
    for _, row in df.iterrows() if not df.empty else []:
        eventos_por_data.setdefault(row["Data"], []).append(row)
    status_colors = {"Planejada":"#2563eb", "Vencida":"#dc2626", "Concluída":"#16a34a", "Em andamento":"#f59e0b", "Cancelada":"#64748b"}
    dias_semana = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
    html = ["""
    <style>
      .calendar-wrap{background:#fff;border:1px solid #e5e7eb;border-radius:22px;padding:1rem;box-shadow:0 10px 25px rgba(31,41,55,.07);}
      .calendar-title{font-size:1.15rem;font-weight:900;color:#111827;margin-bottom:.7rem;}
      .calendar-grid{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:.55rem;}
      .calendar-head{font-size:.76rem;font-weight:900;color:#475569;text-align:center;padding:.35rem;background:#f8fafc;border-radius:12px;border:1px solid #edf2f7;}
      .calendar-day{min-height:122px;border:1px solid #e5e7eb;border-radius:16px;background:#ffffff;padding:.55rem;overflow:hidden;}
      .calendar-day.off{background:#f8fafc;color:#94a3b8;}
      .calendar-day.today{border:2px solid #d9a514;background:#fff8e3;}
      .day-number{font-weight:900;font-size:.90rem;margin-bottom:.35rem;color:#111827;}
      .event-badge{display:block;border-radius:10px;padding:.24rem .34rem;margin:.22rem 0;font-size:.68rem;font-weight:750;color:#fff;line-height:1.15;white-space:normal;}
      .event-more{font-size:.68rem;color:#475569;font-weight:800;margin-top:.2rem;}
      @media(max-width:900px){.calendar-grid{grid-template-columns:repeat(2,minmax(0,1fr));}.calendar-head{display:none}.calendar-day{min-height:100px;}}
    </style>
    """]
    html.append(f"<div class='calendar-wrap'><div class='calendar-title'>{calendar.month_name[mes].capitalize()} / {ano}</div><div class='calendar-grid'>")
    for dsem in dias_semana:
        html.append(f"<div class='calendar-head'>{dsem}</div>")
    hoje = date.today()
    for semana in semanas:
        for dia in semana:
            classes = ["calendar-day"]
            if dia.month != mes:
                classes.append("off")
            if dia == hoje:
                classes.append("today")
            html.append(f"<div class='{' '.join(classes)}'><div class='day-number'>{dia.day}</div>")
            eventos = eventos_por_data.get(dia, [])
            for ev in eventos[:3]:
                cor = status_colors.get(str(ev.get("Status", "")), "#64748b")
                titulo = f"{ev.get('Máquina','—')} • {ev.get('Status','—')}"
                detalhe = f"{ev.get('Responsável','—')}"
                html.append(f"<span class='event-badge' style='background:{cor};'>{html_escape(titulo)}<br><span style='font-weight:600;opacity:.92'>{html_escape(detalhe)}</span></span>")
            if len(eventos) > 3:
                html.append(f"<div class='event-more'>+{len(eventos)-3} evento(s)</div>")
            html.append("</div>")
    html.append("</div></div>")
    st.markdown("".join(html), unsafe_allow_html=True)

def nr12_calendario(db,u):
    header("Calendário de Auditorias e Inspeções", "Visão mensal, por unidade e por responsável das auditorias e inspeções de proteções de máquinas")
    ids = visible_site_ids(u,db)
    hoje = date.today()
    rows=[]
    for m in db.query(MaquinaNR12).filter(MaquinaNR12.site_id.in_(ids)).all():
        if m.proxima_auditoria:
            d=as_date(m.proxima_auditoria)
            rows.append({"Data":d,"Mês":d.replace(day=1),"Site":site_code(db,m.site_id),"Responsável":m.responsavel_area or "—","Tipo":"Auditoria/inspeção planejada","Máquina":m.codigo,"Status":"Vencida" if d < hoje else "Planejada","Origem":"Inventário","Observação":m.nome})
    for v in db.query(VerificacaoNR12).filter(VerificacaoNR12.site_id.in_(ids)).all():
        d=as_date(v.data_verificacao)
        if d:
            rows.append({"Data":d,"Mês":d.replace(day=1),"Site":site_code(db,v.site_id),"Responsável":v.responsavel or "—","Tipo":v.tipo or "Verificação","Máquina":v.maquina.codigo if v.maquina else "—","Status":"Concluída","Origem":"Verificação registrada","Observação":v.resultado})
    df=pd.DataFrame(rows)
    if df.empty:
        empty_state("Nenhum evento encontrado.")
        return
    with st.expander("Filtros", expanded=True):
        c1,c2,c3,c4=st.columns(4)
        meses=sorted(df["Mês"].dropna().unique())
        mes_ref=c1.selectbox("Mês",meses,index=max(0,len(meses)-1),format_func=lambda d: pd.to_datetime(d).strftime("%m/%Y"))
        sites=c2.multiselect("Site",sorted(df["Site"].dropna().unique()))
        resp=c3.multiselect("Responsável",sorted(df["Responsável"].dropna().unique()))
        status=c4.multiselect("Status",[s for s in ["Planejada","Vencida","Concluída"] if s in set(df["Status"])])
    f=df.copy()
    if mes_ref: f=f[f["Mês"]==mes_ref]
    if sites: f=f[f["Site"].isin(sites)]
    if resp: f=f[f["Responsável"].isin(resp)]
    if status: f=f[f["Status"].isin(status)]
    k1,k2,k3=st.columns(3)
    k1.metric("Planejadas", int((f["Status"]=="Planejada").sum()))
    k2.metric("Vencidas", int((f["Status"]=="Vencida").sum()))
    k3.metric("Concluídas", int((f["Status"]=="Concluída").sum()))
    t1,t2,t3=st.tabs(["Calendário mensal","Por site","Por responsável"])
    with t1:
        render_calendario_mensal(f, mes_ref)
        st.caption("A tabela abaixo mantém a rastreabilidade dos eventos exibidos no calendário.")
        st.dataframe(f.sort_values("Data"), use_container_width=True, hide_index=True)
    with t2:
        agg=f.groupby(["Site","Status"], as_index=False).size().rename(columns={"size":"Quantidade"}) if not f.empty else pd.DataFrame()
        if not agg.empty: plotly_chart_safe(px.bar(agg,x="Site",y="Quantidade",color="Status",barmode="group",title="Eventos por site e status").update_layout(template="plotly_white"), use_container_width=True)
        st.dataframe(agg, use_container_width=True, hide_index=True)
    with t3:
        agg=f.groupby(["Responsável","Status"], as_index=False).size().rename(columns={"size":"Quantidade"}) if not f.empty else pd.DataFrame()
        if not agg.empty: plotly_chart_safe(px.bar(agg,x="Responsável",y="Quantidade",color="Status",barmode="group",title="Eventos por responsável e status").update_layout(template="plotly_white"), use_container_width=True)
        st.dataframe(agg, use_container_width=True, hide_index=True)
    download_excel_button("Exportar calendário", "calendario_auditorias_inspecoes.xlsx", {"Calendario": f})

def logs_sistema_page(db,u):
    header("Logs do Sistema", "Trilha de auditoria de alterações críticas")
    if not can_admin(u):
        alert_card("Acesso restrito ao perfil Admin_LAG.")
        return
    df=df_logs(db)
    if df.empty:
        empty_state("Nenhum log registrado.")
        return
    with st.expander("Filtros", expanded=True):
        c1,c2,c3,c4=st.columns(4)
        usuarios=c1.multiselect("Usuário", sorted(df["Usuário"].dropna().unique()))
        modulos=c2.multiselect("Módulo", sorted(df["Módulo"].dropna().unique()))
        entidades=c3.multiselect("Entidade", sorted(df["Entidade"].dropna().unique()))
        acoes=c4.multiselect("Ação", sorted(df["Ação"].dropna().unique()))
    f=df.copy()
    if usuarios: f=f[f["Usuário"].isin(usuarios)]
    if modulos: f=f[f["Módulo"].isin(modulos)]
    if entidades: f=f[f["Entidade"].isin(entidades)]
    if acoes: f=f[f["Ação"].isin(acoes)]
    st.dataframe(f, use_container_width=True, hide_index=True)
    download_excel_button("Exportar logs", "logs_auditoria_sistema.xlsx", {"Logs": f})


def nr12_regras_frequencia(db,u):
    header("Regras de Frequência de Inspeções", "Matriz configurável de periodicidade máxima por criticidade da máquina")
    if not can_edit(u,"nr12_manutencao"):
        alert_card("Seu perfil permite consulta, mas não administração das regras.")
    section("Matriz de periodicidade máxima")
    st.caption("Essas regras definem a data limite para checklists, inspeções e auditorias. Quanto maior a criticidade, menor deve ser o intervalo permitido.")
    df = df_regras_frequencia(db)
    if df.empty:
        empty_state("Nenhuma regra cadastrada.")
        return
    if can_edit(u,"nr12_manutencao"):
        ed = st.data_editor(
            df,
            use_container_width=True,
            hide_index=True,
            disabled=["ID","Atualizado em","Atualizado por"],
            column_config={
                "Tipo de evento": st.column_config.SelectboxColumn("Tipo de evento", options=TIPOS_FREQUENCIA_MAQUINAS),
                "Criticidade": st.column_config.SelectboxColumn("Criticidade", options=CRITICIDADES),
                "Dias máximos": st.column_config.NumberColumn("Dias máximos", min_value=0, step=1),
            },
            key="editor_regras_frequencia_maquinas",
        )
        if st.button("Salvar regras de frequência", use_container_width=True):
            for _, row in ed.iterrows():
                obj = db.get(RegraFrequenciaInspecaoMaquinas, int(row["ID"]))
                if obj:
                    antes = obj.dias_periodicidade
                    obj.tipo_evento = str(row["Tipo de evento"])
                    obj.criticidade = str(row["Criticidade"])
                    obj.dias_periodicidade = int(row["Dias máximos"]) if pd.notna(row["Dias máximos"]) else 0
                    obj.ativo = bool(row["Ativo"])
                    obj.observacoes = row["Observações"]
                    obj.atualizado_em = datetime.utcnow()
                    obj.atualizado_por = u.nome
                    if antes != obj.dias_periodicidade:
                        registrar_log(db,u,NOME_MODULO_MAQUINAS,"RegraFrequenciaInspecaoMaquinas",obj.id,"editar","dias_periodicidade",antes,obj.dias_periodicidade,observacao=f"{obj.tipo_evento} / {obj.criticidade}")
            db.commit()
            st.success("Regras atualizadas.")
            st.rerun()
        with st.expander("Adicionar nova regra"):
            with st.form("nova_regra_frequencia"):
                tipo = st.selectbox("Tipo de evento", TIPOS_FREQUENCIA_MAQUINAS)
                criticidade = st.selectbox("Criticidade", CRITICIDADES)
                dias = st.number_input("Dias máximos", min_value=0, value=180, step=1)
                obs = st.text_area("Observações")
                if st.form_submit_button("Adicionar regra", use_container_width=True):
                    if db.query(RegraFrequenciaInspecaoMaquinas).filter_by(tipo_evento=tipo, criticidade=criticidade).first():
                        st.error("Já existe regra para esse tipo de evento e criticidade.")
                    else:
                        obj=RegraFrequenciaInspecaoMaquinas(tipo_evento=tipo,criticidade=criticidade,dias_periodicidade=int(dias),ativo=True,atualizado_por=u.nome,observacoes=obs)
                        db.add(obj); db.flush()
                        registrar_log(db,u,NOME_MODULO_MAQUINAS,"RegraFrequenciaInspecaoMaquinas",obj.id,"criar",observacao=f"{tipo} / {criticidade}")
                        db.commit()
                        st.success("Regra adicionada.")
                        st.rerun()
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)
    section("Aplicação prática nas máquinas")
    ids=visible_site_ids(u,db)
    rows=[]
    for m in db.query(MaquinaNR12).filter(MaquinaNR12.site_id.in_(ids)).order_by(MaquinaNR12.codigo):
        for tipo in ["Inspeção de manutenção","Auditoria EHS"]:
            limite = data_limite_por_frequencia(db, tipo, m.criticidade, m.ultima_auditoria or m.criado_em or date.today())
            rows.append({
                "Máquina": m.codigo,
                "Site": site_code(db,m.site_id),
                "Criticidade": m.criticidade,
                "Tipo": tipo,
                "Periodicidade máxima (dias)": regra_frequencia_dias(db,tipo,m.criticidade),
                "Última referência": fmt_date(m.ultima_auditoria or m.criado_em),
                "Data limite": fmt_date(limite),
                "Status": "Vencido" if limite < date.today() else "Em dia",
            })
    dfa=pd.DataFrame(rows)
    if not dfa.empty:
        st.dataframe(dfa, use_container_width=True, hide_index=True)
    else:
        empty_state("Nenhuma máquina para aplicar as regras.")
    download_excel_button("Exportar regras e aplicação", "regras_frequencia_inspecoes.xlsx", {"Regras": df, "Aplicacao": dfa})

def nr12_pac(db,u):
    header("PAC de Proteções de Máquinas","Planos de ação corretiva")
    ids=visible_site_ids(u,db)
    sites={s.codigo:s.id for s in db.query(Site).filter(Site.id.in_(ids))}
    opts=machine_options(db,ids)

    df=df_pac_nr12(db,ids)
    section("Consulta")
    if not df.empty:
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        empty_state("Nenhum PAC.")
    download_excel_button("Exportar PAC Proteções de Máquinas Excel","pac_nr12.xlsx",{"PAC":df})

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
    header("Central de Pendências de Proteções de Máquinas","Próximas auditorias ordenadas por prioridade")
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
            "Status de Proteção":calcular_status_maquina_nr12(db,m),
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
    header("Gestão de Mudanças / MOC de Proteções de Máquinas","Mudanças críticas, aprovações e validação")
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
    header("Termo de Garantia de Proteções de Máquinas","Emissão anual por site")
    ids=visible_site_ids(u,db); sites={s.codigo:s.id for s in db.query(Site).filter(Site.id.in_(ids))}
    with st.form("termo"):
        site=st.selectbox("Site",list(sites)); ano=st.number_input("Ano/ciclo",2020,2100,date.today().year); ehs=st.text_input("Responsável EHS"); man=st.text_input("Responsável Manutenção"); prod=st.text_input("Responsável Produção/Operação"); eng=st.text_input("Responsável Engenharia"); lid=st.text_input("Liderança do site"); res=st.text_area("Ressalvas"); pend=st.text_area("Pendências"); dec=st.text_area("Declaração formal","Declaramos que o site acompanha a sustentação de proteções de máquinas já adequadas, mantendo inventário, controles documentais, inspeções, PAC e MOC.")
        if st.form_submit_button("Gerar termo",use_container_width=True):
            sid=sites[site]; ms=db.query(MaquinaNR12).filter_by(site_id=sid).all(); sts=[calcular_status_maquina_nr12(db,m) for m in ms]
            resumo=pd.DataFrame([{"Indicador":"Total de máquinas","Valor":len(ms)},{"Indicador":"Conformes","Valor":sts.count("Conforme")},{"Indicador":"Não conformes","Valor":sts.count("Não conforme")},{"Indicador":"PACs críticos abertos/vencidos","Valor":db.query(PACNR12).filter(PACNR12.site_id==sid,PACNR12.classificacao=="Crítico",PACNR12.status.in_(["Aberta","Em andamento","Vencida"])).count()},{"Indicador":"MOCs críticas sem validação","Valor":db.query(MOCNR12).filter(MOCNR12.site_id==sid,MOCNR12.exige_moc==True,MOCNR12.validacao_final==False).count()}])
            if can_edit(u,"nr12_manutencao"): db.add(TermoGarantiaNR12(site_id=sid,ano_ciclo=ano,responsavel_ehs=ehs,responsavel_manutencao=man,responsavel_producao=prod,responsavel_engenharia=eng,lideranca_site=lid,ressalvas=res,pendencias=pend,declaracao_formal=dec)); db.commit()
            pdf=gerar_pdf(f"Termo de Garantia de Sustentação de Proteções de Máquinas — {site}",f"Ano/ciclo: {ano} | Emissão: {fmt_date(date.today())}",[("Declaração",dec),("Responsáveis",pd.DataFrame([{"Função":"EHS","Responsável":ehs},{"Função":"Manutenção","Responsável":man},{"Função":"Produção/Operação","Responsável":prod},{"Função":"Engenharia","Responsável":eng},{"Função":"Liderança","Responsável":lid}])),("Consolidação",resumo),("Ressalvas",res or "Sem ressalvas."),("Pendências",pend or "Sem pendências.")])
            download_pdf_button("Baixar termo Proteções de Máquinas PDF",f"termo_nr12_{site}_{ano}.pdf",pdf)
def nr12_relatorios(db,u):
    header("Relatórios de Proteções de Máquinas","Exportações em Excel e PDFs")
    ids=visible_site_ids(u,db)
    d={"Inventário":df_maquinas(db,ids),"Documentos":df_docs(db,ids),"Verificações":df_ver(db,ids),"PAC":df_pac_nr12(db,ids)}
    cols=st.columns(4)
    for (name,df),c in zip(d.items(),cols):
        with c: download_excel_button(f"{name} Excel",f"{name.lower()}_nr12.xlsx",{name:df})
    download_excel_button("Pacote Proteções de Máquinas Excel","pacote_nr12.xlsx",d)
    opts=machine_options(db,ids)
    if opts:
        lab=st.selectbox("Relatório PDF por máquina",list(opts)); m=db.get(MaquinaNR12,opts[lab])
        dados=df_maquinas(db,[m.site_id]); dados=dados[dados["ID"]==m.id]
        docs=df_docs(db,[m.site_id]); docs=docs[docs["ID"].isin([d.id for d in db.query(DocumentoNR12).filter_by(maquina_id=m.id).all()])] if not docs.empty else docs
        pacs=df_pac_nr12(db,[m.site_id]); pacs=pacs[pacs["Máquina"]==m.codigo] if not pacs.empty else pacs
        vers=pd.DataFrame([{"ID":v.id,"Tipo":v.tipo,"Data":fmt_date(v.data_verificacao),"Responsável":v.responsavel,"Resultado":v.resultado,"Pontuação %":v.pontuacao,"NC crítica":"Sim" if v.possui_nc_critica else "Não","Próxima":fmt_date(v.proxima_verificacao),"Observações":v.observacoes} for v in db.query(VerificacaoNR12).filter_by(maquina_id=m.id).order_by(VerificacaoNR12.data_verificacao.desc())])
        pdf=gerar_pdf(f"Relatório por Máquina — {m.codigo}",f"{m.nome} | Site {site_code(db,m.site_id)}",[("Dados",dados),("Auditorias e verificações realizadas",vers),("Documentos",docs),("PACs",pacs)])
        download_pdf_button("Baixar relatório por máquina PDF",f"relatorio_maquina_{m.codigo}.pdf",pdf)

def gerar_checklist_automatico_ehs(db,auditoria_id,commit=True):
    auditoria = db.get(AuditoriaCruzada, auditoria_id)
    versao = db.query(ChecklistVersaoEHS).filter_by(ativo=True).order_by(ChecklistVersaoEHS.versao.desc(), ChecklistVersaoEHS.id.desc()).first()
    if auditoria and versao and not auditoria.versao_checklist_id:
        auditoria.versao_checklist_id = versao.id

    if versao:
        perguntas = db.query(ChecklistPerguntaVersaoEHS).filter_by(checklist_versao_id=versao.id, ativo=True).order_by(ChecklistPerguntaVersaoEHS.categoria, ChecklistPerguntaVersaoEHS.ordem).all()
        for p in perguntas:
            if not p.requisito_id:
                continue
            if not db.query(RespostaAuditoriaEHS).filter_by(auditoria_id=auditoria_id,requisito_id=p.requisito_id).first():
                db.add(RespostaAuditoriaEHS(
                    auditoria_id=auditoria_id, requisito_id=p.requisito_id, aplicavel=True, status="Conforme", nota_maturidade=3,
                    versao_checklist_id=versao.id, pergunta_snapshot=p.pergunta, criticidade_snapshot=p.criticidade,
                    evidencia_esperada_snapshot=p.evidencia_esperada, gera_pac_automatico_snapshot=p.gera_pac_automatico
                ))
    else:
        for r in db.query(RequisitoEHS).join(DiretivaEHS).filter(RequisitoEHS.ativo==True,DiretivaEHS.ativo==True):
            if not db.query(RespostaAuditoriaEHS).filter_by(auditoria_id=auditoria_id,requisito_id=r.id).first():
                db.add(RespostaAuditoriaEHS(auditoria_id=auditoria_id,requisito_id=r.id,aplicavel=True,status="Conforme",nota_maturidade=3,versao_checklist_id=None,pergunta_snapshot=r.pergunta,criticidade_snapshot=r.criticidade,evidencia_esperada_snapshot=r.evidencia_esperada,gera_pac_automatico_snapshot=getattr(r,"gera_pac_automatico",False)))
    if commit: db.commit()

def ehs_submodulos_home(db,u):
    header("Auditoria Cruzada de Diretrizes EHS", "Escolha um submódulo para planejar, executar, tratar gaps ou governar a auditoria cruzada.")
    top_back_col, top_spacer_col = st.columns([1.1, 5])
    with top_back_col:
        if st.button("⬅️ Voltar para página inicial", key="ehs_home_voltar_inicio", use_container_width=True):
            st.session_state.modulo = "home"
            st.rerun()
    section("Submódulos")
    nomes = list(EHS_SUBMODULOS.keys())
    for base in range(0, len(nomes), 2):
        cols = st.columns(2)
        for col, nome in zip(cols, nomes[base:base+2]):
            cfg = EHS_SUBMODULOS[nome]
            with col:
                submodule_card(nome, cfg["descricao"], cfg["icone"], cfg["cor"])
                if st.button(f"Acessar {nome}", key=f"btn_submodulo_ehs_{nome}", use_container_width=True):
                    paginas_validas = [p for p in cfg["paginas"] if p != "Logs do Sistema" or can_admin(u)]
                    destino = paginas_validas[0] if paginas_validas else EHS_HOME_PAGE
                    st.session_state.submodulo_ehs = nome
                    st.session_state.page_ehs = destino
                    st.session_state.nav_ehs = destino
                    st.rerun()
    section("Resumo rápido")
    ids = visible_site_ids(u, db)
    da = df_aud(db, ids)
    dp = df_pac_ehs(db, ids)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Auditorias", 0 if da.empty else len(da))
    c2.metric("Em andamento", 0 if da.empty else int((da["Status"] == "Em andamento").sum()))
    c3.metric("PACs abertos", 0 if dp.empty else int(dp["Status"].isin(["Aberta", "Em andamento", "Aguardando validação"]).sum()))
    c4.metric("PACs vencidos", 0 if dp.empty else int((dp["Status"] == "Vencida").sum()))

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
            plotly_chart_safe(
                px.bar(latest_df, x="Site auditado", y="Conformidade %", color="Conformidade %",
                       hover_data=["Auditoria","Data de referência","Status","Maturidade"],
                       title="Conformidade por site — última auditoria registrada").update_layout(template="plotly_white", yaxis_range=[0,100]),
                use_container_width=True
            )
        else:
            empty_state("Sem auditorias.")
    with c2:
        if not dp.empty:
            plotly_chart_safe(px.histogram(dp, x="Status", color="Prioridade", barmode="group", title="PAC por status").update_layout(template="plotly_white"), use_container_width=True)
        else:
            empty_state("Sem PACs.")


def status_calendario_auditoria_ehs(a):
    """Traduz o status da auditoria para a visão de calendário.

    A data planejada vencida ganha destaque visual como vencida, desde que a auditoria
    ainda não tenha sido concluída ou cancelada.
    """
    if not a:
        return "Planejada"
    if a.status == "Concluída":
        return "Concluída"
    if a.status == "Cancelada":
        return "Cancelada"
    if a.data_planejada and as_date(a.data_planejada) < date.today() and a.status not in ["Concluída", "Cancelada"]:
        return "Vencida"
    if a.status == "Em andamento":
        return "Em andamento"
    return "Planejada"


def ehs_calendario(db,u):
    header("Calendário de Auditorias", "Acompanhamento visual das auditorias cruzadas planejadas, em andamento, vencidas e concluídas")
    ids = visible_site_ids(u, db)
    auds = db.query(AuditoriaCruzada).filter(AuditoriaCruzada.site_auditado_id.in_(ids)).order_by(AuditoriaCruzada.data_planejada.desc(), AuditoriaCruzada.id.desc()).all()
    rows = []
    for a in auds:
        site_txt = site_code(db, a.site_auditado_id)
        resp = a.auditor_lider or "—"
        ciclo = a.ciclo or f"Auditoria {a.id}"
        status_base = status_calendario_auditoria_ehs(a)
        if a.data_planejada:
            d = as_date(a.data_planejada)
            rows.append({
                "Data": d,
                "Mês": d.replace(day=1),
                "Site": site_txt,
                "Responsável": resp,
                "Tipo": "Auditoria planejada",
                "Máquina": ciclo,
                "Auditoria": a.id,
                "Ciclo": ciclo,
                "Status": status_base,
                "Origem": "Data planejada",
                "Observação": a.escopo or a.observacoes or "—",
            })
        if a.data_inicio:
            d = as_date(a.data_inicio)
            rows.append({
                "Data": d,
                "Mês": d.replace(day=1),
                "Site": site_txt,
                "Responsável": resp,
                "Tipo": "Início da auditoria",
                "Máquina": ciclo,
                "Auditoria": a.id,
                "Ciclo": ciclo,
                "Status": "Em andamento" if a.status != "Concluída" else "Concluída",
                "Origem": "Data de início",
                "Observação": a.escopo or a.observacoes or "—",
            })
        if a.data_fim:
            d = as_date(a.data_fim)
            rows.append({
                "Data": d,
                "Mês": d.replace(day=1),
                "Site": site_txt,
                "Responsável": resp,
                "Tipo": "Conclusão da auditoria",
                "Máquina": ciclo,
                "Auditoria": a.id,
                "Ciclo": ciclo,
                "Status": "Concluída",
                "Origem": "Data de fim",
                "Observação": a.escopo or a.observacoes or "—",
            })
    df = pd.DataFrame(rows)
    if df.empty:
        empty_state("Nenhuma auditoria com datas cadastradas para exibir no calendário.")
        return

    with st.expander("Filtros", expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        meses = sorted(df["Mês"].dropna().unique())
        hoje_mes = date.today().replace(day=1)
        meses_ate_hoje = [m for m in meses if m <= hoje_mes]
        mes_default = max(meses_ate_hoje) if meses_ate_hoje else max(meses)
        mes_idx = meses.index(mes_default) if mes_default in meses else max(0, len(meses)-1)
        mes_ref = c1.selectbox("Mês", meses, index=mes_idx, format_func=lambda d: pd.to_datetime(d).strftime("%m/%Y"), key="ehs_calendario_mes")
        sites = c2.multiselect("Site auditado", sorted(df["Site"].dropna().unique()), key="ehs_calendario_sites")
        resp = c3.multiselect("Auditor líder / responsável", sorted(df["Responsável"].dropna().unique()), key="ehs_calendario_resp")
        status = c4.multiselect("Status", [s for s in ["Planejada", "Em andamento", "Vencida", "Concluída", "Cancelada"] if s in set(df["Status"])], key="ehs_calendario_status")
        c5, c6 = st.columns(2)
        tipos = c5.multiselect("Tipo de evento", sorted(df["Tipo"].dropna().unique()), key="ehs_calendario_tipos")
        ciclos = c6.multiselect("Ciclo", sorted(df["Ciclo"].dropna().unique()), key="ehs_calendario_ciclos")

    f = df.copy()
    if mes_ref:
        f = f[f["Mês"] == mes_ref]
    if sites:
        f = f[f["Site"].isin(sites)]
    if resp:
        f = f[f["Responsável"].isin(resp)]
    if status:
        f = f[f["Status"].isin(status)]
    if tipos:
        f = f[f["Tipo"].isin(tipos)]
    if ciclos:
        f = f[f["Ciclo"].isin(ciclos)]

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Planejadas", int((f["Status"] == "Planejada").sum()))
    k2.metric("Em andamento", int((f["Status"] == "Em andamento").sum()))
    k3.metric("Vencidas", int((f["Status"] == "Vencida").sum()))
    k4.metric("Concluídas", int((f["Status"] == "Concluída").sum()))

    t1, t2, t3, t4 = st.tabs(["Calendário mensal", "Por site", "Por responsável", "Lista detalhada"])
    with t1:
        render_calendario_mensal(f, mes_ref)
        st.caption("A tabela abaixo mantém a rastreabilidade dos eventos exibidos no calendário.")
        st.dataframe(f.sort_values("Data"), use_container_width=True, hide_index=True)
    with t2:
        agg = f.groupby(["Site", "Status"], as_index=False).size().rename(columns={"size":"Quantidade"}) if not f.empty else pd.DataFrame()
        if not agg.empty:
            plotly_chart_safe(px.bar(agg, x="Site", y="Quantidade", color="Status", barmode="group", title="Auditorias por site e status").update_layout(template="plotly_white"), use_container_width=True)
        else:
            empty_state("Sem dados para os filtros selecionados.")
        st.dataframe(agg, use_container_width=True, hide_index=True)
    with t3:
        agg = f.groupby(["Responsável", "Status"], as_index=False).size().rename(columns={"size":"Quantidade"}) if not f.empty else pd.DataFrame()
        if not agg.empty:
            plotly_chart_safe(px.bar(agg, x="Responsável", y="Quantidade", color="Status", barmode="group", title="Auditorias por responsável e status").update_layout(template="plotly_white"), use_container_width=True)
        else:
            empty_state("Sem dados para os filtros selecionados.")
        st.dataframe(agg, use_container_width=True, hide_index=True)
    with t4:
        st.dataframe(f.sort_values("Data"), use_container_width=True, hide_index=True)

    proximas = df[(df["Data"] >= date.today()) & (df["Data"] <= date.today() + timedelta(days=90))].sort_values("Data")
    section("Próximas auditorias — 90 dias")
    if not proximas.empty:
        st.dataframe(proximas, use_container_width=True, hide_index=True)
    else:
        empty_state("Nenhuma auditoria prevista para os próximos 90 dias.")
    download_excel_button("Exportar calendário de auditorias", "calendario_auditorias_ehs.xlsx", {"Calendario_Auditorias": f, "Proximas_90_Dias": proximas})

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
                    registrar_log(db,u,"Auditoria Cruzada","AuditoriaCruzada",a.id,"criar",observacao=f"Auditoria {a.ciclo} criada")
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
                pergunta_txt = getattr(r,"pergunta_snapshot",None) or r.requisito.pergunta
                criticidade_txt = getattr(r,"criticidade_snapshot",None) or r.requisito.criticidade
                evidencia_esperada_txt = getattr(r,"evidencia_esperada_snapshot",None) or r.requisito.evidencia_esperada
                if categoria != categoria_atual:
                    st.markdown(f"<div class='check-category'>{categoria}</div>", unsafe_allow_html=True)
                    categoria_atual = categoria
                st.markdown(
                    f"<div class='check-item'><div class='check-q'>{r.requisito.ordem}. {pergunta_txt}"
                    f"<span class='check-meta'>{criticidade_txt}</span></div>"
                    f"<div class='muted'>Evidência esperada: {evidencia_esperada_txt or 'Verificar evidência aplicável.'}</div></div>",
                    unsafe_allow_html=True,
                )
                col1, col2, col3, col4, col5, col6 = st.columns([.85, 1.45, 1, 2.2, 2.2, .9])
                apl = col1.checkbox("Aplicável", value=bool(r.aplicavel), key=f"ehs_ap_{a.id}_{r.id}")
                status_atual = r.status if r.status in STATUS_RESPOSTA_EHS else "Conforme"
                status = col2.selectbox("Status", STATUS_RESPOSTA_EHS, index=STATUS_RESPOSTA_EHS.index(status_atual), key=f"ehs_status_{a.id}_{r.id}")
                maturidade = col3.number_input("Maturidade", min_value=0.0, max_value=5.0, value=float(r.nota_maturidade or 0), step=.5, key=f"ehs_mat_{a.id}_{r.id}")
                evidencia = col4.text_input("Evidência verificada", value=r.evidencia_verificada or "", key=f"ehs_evid_{a.id}_{r.id}")
                comentario = col5.text_input("Comentário do auditor", value=r.comentario_auditor or "", key=f"ehs_com_{a.id}_{r.id}")
                pac = col6.checkbox("PAC", value=bool(r.necessita_pac) or bool(getattr(r,"gera_pac_automatico_snapshot",False)), key=f"ehs_pac_{a.id}_{r.id}")
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
                registrar_log(db,u,"Auditoria Cruzada","AuditoriaCruzada",a.id,"editar",observacao="Checklist EHS atualizado")
                db.commit()
                st.session_state["ehs_checklist_saved_msg"]="Checklist salvo com sucesso. Os PACs necessários foram gerados ou atualizados."
                st.rerun()
    else:
        categoria_atual = None
        for r in res:
            categoria = r.requisito.diretiva.categoria
            pergunta_txt = getattr(r,"pergunta_snapshot",None) or r.requisito.pergunta
            criticidade_txt = getattr(r,"criticidade_snapshot",None) or r.requisito.criticidade
            if categoria != categoria_atual:
                st.markdown(f"<div class='check-category'>{categoria}</div>", unsafe_allow_html=True)
                categoria_atual = categoria
            status_txt = "Não Aplicável" if not r.aplicavel else r.status
            st.markdown(
                f"<div class='check-item'><div class='check-q'>{r.requisito.ordem}. {pergunta_txt}"
                f"<span class='check-meta'>{criticidade_txt}</span></div>"
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
    header("Base do Checklist EHS","Base inicial carregada no banco, editável pelo app e versionada para preservar histórico")
    if not can_edit(u,"auditoria"):
        alert_card("Seu perfil permite consulta, mas não administração da base de checklists.")
    versao_ativa = db.query(ChecklistVersaoEHS).filter_by(ativo=True).order_by(ChecklistVersaoEHS.versao.desc(), ChecklistVersaoEHS.id.desc()).first()
    c1,c2,c3 = st.columns(3)
    with c1:
        kpi_card("Versão ativa", f"v{versao_ativa.versao}" if versao_ativa else "—", "Novas auditorias usarão esta versão")
    with c2:
        kpi_card("Requisitos ativos", db.query(RequisitoEHS).filter_by(ativo=True).count(), "Base editável atual")
    with c3:
        kpi_card("Categorias", db.query(DiretivaEHS).filter_by(ativo=True).count(), "Diretrizes EHS")

    section("Como funciona")
    st.caption("Os checklists padrão continuam dentro do código como carga inicial. Depois que o banco é criado, a base passa a ser editável pelo app; as alterações ficam salvas no banco e novas auditorias recebem snapshots da versão ativa.")

    reqs=db.query(RequisitoEHS).join(DiretivaEHS).order_by(DiretivaEHS.categoria,RequisitoEHS.ordem).all()
    df=pd.DataFrame([{"ID":r.id,"Categoria":r.diretiva.categoria,"Ordem":r.ordem,"Requisito":r.pergunta,"Ativo":r.ativo,"Criticidade":r.criticidade,"Evidência esperada":r.evidencia_esperada,"Gerar PAC automático":getattr(r,"gera_pac_automatico",False)} for r in reqs])
    if can_edit(u,"auditoria"):
        section("Editar base atual")
        ed=st.data_editor(
            df,
            use_container_width=True,
            hide_index=True,
            disabled=["ID"],
            column_config={"Criticidade":st.column_config.SelectboxColumn("Criticidade",options=CRITICIDADES)},
            key="editor_base_checklist_ehs_editavel",
        )
        csave,cversion = st.columns(2)
        with csave:
            if st.button("Salvar base e criar nova versão ativa",use_container_width=True):
                for _,row in ed.iterrows():
                    r=db.get(RequisitoEHS,int(row["ID"]))
                    if not r:
                        continue
                    categoria=str(row["Categoria"]).strip() or "Sem categoria"
                    d=db.query(DiretivaEHS).filter_by(categoria=categoria).first()
                    if not d:
                        d=DiretivaEHS(categoria=categoria,descricao=categoria,ativo=True); db.add(d); db.flush()
                    r.diretiva_id=d.id
                    r.ordem=int(row["Ordem"]) if pd.notna(row["Ordem"]) else r.ordem
                    r.pergunta=str(row["Requisito"]).strip()
                    r.ativo=bool(row["Ativo"])
                    r.criticidade=row["Criticidade"] if row["Criticidade"] in CRITICIDADES else "Média"
                    r.evidencia_esperada=row["Evidência esperada"]
                    r.gera_pac_automatico=bool(row.get("Gerar PAC automático", False))
                nova = criar_versao_checklist_ehs(db,u.nome,"Versão criada após edição da base EHS")
                registrar_log(db,u,"Auditoria Cruzada","ChecklistVersaoEHS",nova.id,"criar",observacao="Base EHS editada e nova versão ativa criada")
                db.commit(); st.success(f"Base atualizada. Nova versão ativa criada: v{nova.versao}."); st.rerun()
        with cversion:
            if st.button("Criar nova versão sem alterar a base",use_container_width=True):
                nova = criar_versao_checklist_ehs(db,u.nome,"Nova versão criada manualmente a partir da base atual")
                registrar_log(db,u,"Auditoria Cruzada","ChecklistVersaoEHS",nova.id,"criar",observacao="Nova versão EHS criada a partir da base atual")
                db.commit(); st.success(f"Nova versão ativa criada: v{nova.versao}."); st.rerun()
        with st.expander("Criar novo requisito EHS"):
            cats = [d.categoria for d in db.query(DiretivaEHS).order_by(DiretivaEHS.categoria).all()]
            with st.form("novo_requisito_ehs"):
                modo_cat = st.radio("Categoria", ["Usar existente", "Criar nova"], horizontal=True)
                if modo_cat == "Usar existente" and cats:
                    categoria = st.selectbox("Categoria existente", cats)
                else:
                    categoria = st.text_input("Nova categoria")
                ordem = st.number_input("Ordem", min_value=1, value=1)
                pergunta = st.text_area("Requisito / pergunta")
                criticidade = st.selectbox("Criticidade", CRITICIDADES)
                evidencia = st.text_area("Evidência esperada")
                pac_auto = st.checkbox("Gerar PAC automático quando houver não conformidade")
                if st.form_submit_button("Adicionar requisito e criar nova versão", use_container_width=True):
                    if not pergunta.strip() or not categoria.strip():
                        st.error("Informe categoria e requisito/pergunta.")
                    else:
                        d = db.query(DiretivaEHS).filter_by(categoria=categoria.strip()).first()
                        if not d:
                            d = DiretivaEHS(categoria=categoria.strip(), descricao=categoria.strip(), ativo=True); db.add(d); db.flush()
                        obj = RequisitoEHS(diretiva_id=d.id, ordem=int(ordem), pergunta=pergunta.strip(), criticidade=criticidade, evidencia_esperada=evidencia, gera_pac_automatico=pac_auto, ativo=True)
                        db.add(obj); db.flush()
                        nova = criar_versao_checklist_ehs(db,u.nome,"Versão criada após inclusão de requisito EHS")
                        registrar_log(db,u,"Auditoria Cruzada","RequisitoEHS",obj.id,"criar",observacao=f"Novo requisito EHS cadastrado e v{nova.versao} criada")
                        db.commit(); st.success(f"Requisito criado. Nova versão ativa: v{nova.versao}."); st.rerun()
    else:
        st.dataframe(df,use_container_width=True,hide_index=True)

    section("Versões EHS cadastradas")
    versoes = db.query(ChecklistVersaoEHS).order_by(ChecklistVersaoEHS.versao.desc(), ChecklistVersaoEHS.id.desc()).all()
    dfv = pd.DataFrame([{"ID":v.id,"Versão":v.versao,"Ativo":v.ativo,"Criado por":v.criado_por,"Criado em":fmt_date(v.criado_em),"Descrição":v.descricao} for v in versoes])
    st.dataframe(dfv, use_container_width=True, hide_index=True)
    download_excel_button("Exportar base do checklist EHS", "base_checklist_ehs.xlsx", {"Base_Atual": df, "Versoes": dfv})

def ehs_relatorios(db,u):
    header("Relatórios Auditoria Cruzada","Exportações em Excel e PDF")
    ids=visible_site_ids(u,db); da=df_aud(db,ids); dp=df_pac_ehs(db,ids)
    base=pd.DataFrame([{"Categoria":r.diretiva.categoria,"Ordem":r.ordem,"Requisito":r.pergunta,"Ativo":"Sim" if r.ativo else "Não","Criticidade":r.criticidade,"Evidência esperada":r.evidencia_esperada} for r in db.query(RequisitoEHS).join(DiretivaEHS).order_by(DiretivaEHS.categoria,RequisitoEHS.ordem)])
    download_excel_button("Checklist Excel","checklist_ehs.xlsx",{"Checklist":base}); download_excel_button("PAC EHS Excel","pac_ehs.xlsx",{"PAC":dp}); download_excel_button("Pacote Auditoria Excel","auditoria_cruzada_ehs.xlsx",{"Auditorias":da,"Checklist":base,"PAC":dp})
    auds=db.query(AuditoriaCruzada).filter(AuditoriaCruzada.site_auditado_id.in_(ids)).order_by(AuditoriaCruzada.id.desc()).all()
    if auds:
        amap={f"{a.id} — {site_code(db,a.site_auditado_id)} — {a.ciclo}":a.id for a in auds}; a=db.get(AuditoriaCruzada,amap[st.selectbox("Relatório PDF",list(amap))]); res=db.query(RespostaAuditoriaEHS).filter_by(auditoria_id=a.id).all()
        dfr=pd.DataFrame([{"Categoria":r.requisito.diretiva.categoria,"Requisito":getattr(r,"pergunta_snapshot",None) or r.requisito.pergunta,"Status":r.status,"Maturidade":r.nota_maturidade,"Evidência":r.evidencia_verificada,"Comentário":r.comentario_auditor} for r in res])
        pdf=gerar_pdf(f"Relatório de Auditoria Cruzada de Diretrizes de EHS — {site_code(db,a.site_auditado_id)}",f"Auditoria {a.id} | {a.ciclo} | Conformidade {calcular_conformidade_ehs(res)}% | Maturidade {calcular_maturidade_ehs(res)}",[("Dados",pd.DataFrame([{"Ano":a.ano,"Ciclo":a.ciclo,"Site":site_code(db,a.site_auditado_id),"Status":a.status,"Auditor líder":a.auditor_lider}])),("Resultado por item",dfr),("PACs vinculados",dp[dp["Auditoria"]==a.id] if not dp.empty else dp)])
        download_pdf_button("Baixar relatório de auditoria PDF",f"relatorio_auditoria_ehs_{a.id}.pdf",pdf)



ENERGIA_SITE_INFO = {
    "CAC": {"nome": "MSG Br CAC - Cachoeirinha", "grupo": "MSG Br", "linha": "MSG Br CAC"},
    "JAC": {"nome": "MSG Br JAC - Jacareí", "grupo": "MSG Br", "linha": "MSG Br JAC"},
    "JUN": {"nome": "EMG Br JU - Jundiaí", "grupo": "EMG Br", "linha": "EMG Br JU"},
    "PER": {"nome": "EMG Br SP - Perus", "grupo": "EMG Br", "linha": "EMG Br SP"},
    "SJC": {"nome": "Filtration Br - São José dos Campos", "grupo": "Filtration Br", "linha": "Filtration Br"},
    "DIA": {"nome": "FCG Br - Diadema", "grupo": "FCG Br", "linha": "FCG Br"},
}
ENERGIA_SITE_ORDER = ["CAC", "JAC", "JUN", "PER", "SJC", "DIA"]
ENERGIA_GROUP_ORDER = ["MSG Br", "EMG Br", "Filtration Br", "FCG Br", "LAG"]
ENERGIA_LINHAS_EXECUTIVAS = [
    ("MSG Br CAC", ["CAC"], False),
    ("MSG Br JAC", ["JAC"], False),
    ("MSG Br", ["CAC", "JAC"], True),
    ("EMG Br SP", ["PER"], False),
    ("EMG Br JU", ["JUN"], False),
    ("EMG Br", ["JUN", "PER"], True),
    ("Filtration Br", ["SJC"], True),
    ("FCG Br", ["DIA"], True),
    ("Brasil", ["CAC", "JAC", "JUN", "PER", "SJC", "DIA"], True),
]
ENERGIA_DEFAULT_PARAMS = {
    "fator_emissao_eletricidade_kgco2_kwh": ("0", "Parâmetro mantido para compatibilidade histórica."),
    "fator_emissao_gas_kgco2_kwh": ("0", "Parâmetro mantido para compatibilidade histórica."),
    "meta_reducao_co2_percentual": ("5", "Meta percentual de redução para emissões de CO₂."),
    "meta_reducao_eficiencia_percentual": ("5", "Meta percentual de redução para taxa de eficiência energética."),
    "conversao_mmbtu_kwh": ("293.071", "Conversão de MMBtu para kWh, usada somente para converter consumo de gás para eficiência energética."),
    "fy_atual": ("26", "Fiscal Year atual. Exemplo: 26 para FY26."),
    "mes_referencia_r12": ("2026-04-01", "Mês de referência padrão para R12."),
    "irec_data_inicio": ("2023-01-01", "Data a partir da qual o I-REC zera as emissões de CO₂ da energia elétrica. Default: 01/01/2023."),
}
ENERGIA_FONTE_MAP = {
    "electric power": ("Energia elétrica", "Escopo 2"),
    "electricity": ("Energia elétrica", "Escopo 2"),
    "energia eletrica": ("Energia elétrica", "Escopo 2"),
    "energia elétrica": ("Energia elétrica", "Escopo 2"),
    "natural gas": ("Gás natural", "Escopo 1"),
    "gas natural": ("Gás natural", "Escopo 1"),
    "gás natural": ("Gás natural", "Escopo 1"),
}
ENERGIA_RESOURCE_SITE_PATTERNS = {
    "CAC": ["cachoeirinha"],
    "JAC": ["jacarei", "jacareí"],
    "SJC": ["sao jose dos campos", "são josé dos campos", "sao jose", "sjc"],
    "DIA": ["diadema"],
    "JUN": ["jundiai", "jundiaí"],
    "PER": ["sao paulo", "são paulo", "perus"],
}
ENERGIA_SITE_COORDS = {
    "CAC": {"latitude": -29.9511, "longitude": -51.0930, "cidade": "Cachoeirinha", "uf": "RS"},
    "JAC": {"latitude": -23.3053, "longitude": -45.9658, "cidade": "Jacareí", "uf": "SP"},
    "JUN": {"latitude": -23.1857, "longitude": -46.8978, "cidade": "Jundiaí", "uf": "SP"},
    "PER": {"latitude": -23.4082, "longitude": -46.7465, "cidade": "Perus", "uf": "SP"},
    "SJC": {"latitude": -23.2237, "longitude": -45.9009, "cidade": "São José dos Campos", "uf": "SP"},
    "DIA": {"latitude": -23.6865, "longitude": -46.6234, "cidade": "Diadema", "uf": "SP"},
}
ENERGIA_MAP_METRICAS = {
    "Consumo elétrico R12": ("consumo_eletrico_kwh", "kWh"),
    "Consumo de gás natural R12": ("consumo_gas_kwh", "kWh"),
    "Consumo total R12": ("consumo_total_kwh", "kWh"),
    "Emissões CO₂ R12": ("emissao_total_tco2e", "tCO₂e"),
    "Emissões CO₂ R12 com I-REC": ("emissao_total_com_irec_tco2e", "tCO₂e"),
    "Custo total R12": ("custo_total_brl", "BRL"),
    "Eficiência energética R12": ("eficiencia_energetica", "kWh/Actual Hour"),
}
ENERGIA_ABSORPTION_SHEETS = {
    "FCG": "DIA",
    "PFG": "SJC",
    "MSG Cachoeirinha": "CAC",
    "MSG Jacarei": "JAC",
    "MSG Jacareí": "JAC",
    "EMG Jundiai": "JUN",
    "EMG Jundiaí": "JUN",
    "EMG Perus": "PER",
}

ENERGIA_ACTUAL_HOURS_SEED = [{'mes_ref': '2023-07-01',
  'site_codigo': 'DIA',
  'site_nome': 'FCG Br - Diadema',
  'grupo': 'FCG Br',
  'actual_hours': 4145.0,
  'production_capacity_hours': 5758.0,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2023-08-01',
  'site_codigo': 'DIA',
  'site_nome': 'FCG Br - Diadema',
  'grupo': 'FCG Br',
  'actual_hours': 5576.0,
  'production_capacity_hours': 6919.0,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2023-09-01',
  'site_codigo': 'DIA',
  'site_nome': 'FCG Br - Diadema',
  'grupo': 'FCG Br',
  'actual_hours': 4904.0,
  'production_capacity_hours': 5955.0,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2023-10-01',
  'site_codigo': 'DIA',
  'site_nome': 'FCG Br - Diadema',
  'grupo': 'FCG Br',
  'actual_hours': 6357.0,
  'production_capacity_hours': 6205.0,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2023-11-01',
  'site_codigo': 'DIA',
  'site_nome': 'FCG Br - Diadema',
  'grupo': 'FCG Br',
  'actual_hours': 6088.0,
  'production_capacity_hours': 6416.0,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2023-12-01',
  'site_codigo': 'DIA',
  'site_nome': 'FCG Br - Diadema',
  'grupo': 'FCG Br',
  'actual_hours': 3536.0,
  'production_capacity_hours': 3681.0,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-01-01',
  'site_codigo': 'DIA',
  'site_nome': 'FCG Br - Diadema',
  'grupo': 'FCG Br',
  'actual_hours': 4509.0,
  'production_capacity_hours': 4039.0,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-02-01',
  'site_codigo': 'DIA',
  'site_nome': 'FCG Br - Diadema',
  'grupo': 'FCG Br',
  'actual_hours': 6900.0,
  'production_capacity_hours': 7031.0,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-03-01',
  'site_codigo': 'DIA',
  'site_nome': 'FCG Br - Diadema',
  'grupo': 'FCG Br',
  'actual_hours': 6988.0,
  'production_capacity_hours': 6976.0,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-04-01',
  'site_codigo': 'DIA',
  'site_nome': 'FCG Br - Diadema',
  'grupo': 'FCG Br',
  'actual_hours': 7481.0,
  'production_capacity_hours': 7420.0,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-05-01',
  'site_codigo': 'DIA',
  'site_nome': 'FCG Br - Diadema',
  'grupo': 'FCG Br',
  'actual_hours': 5965.0,
  'production_capacity_hours': 7110.0,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-06-01',
  'site_codigo': 'DIA',
  'site_nome': 'FCG Br - Diadema',
  'grupo': 'FCG Br',
  'actual_hours': 6091.0,
  'production_capacity_hours': 6561.0,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-07-01',
  'site_codigo': 'DIA',
  'site_nome': 'FCG Br - Diadema',
  'grupo': 'FCG Br',
  'actual_hours': 6364.0,
  'production_capacity_hours': 7091.38,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-08-01',
  'site_codigo': 'DIA',
  'site_nome': 'FCG Br - Diadema',
  'grupo': 'FCG Br',
  'actual_hours': 7114.0,
  'production_capacity_hours': 7598.0,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-09-01',
  'site_codigo': 'DIA',
  'site_nome': 'FCG Br - Diadema',
  'grupo': 'FCG Br',
  'actual_hours': 6854.0,
  'production_capacity_hours': 7098.0,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-10-01',
  'site_codigo': 'DIA',
  'site_nome': 'FCG Br - Diadema',
  'grupo': 'FCG Br',
  'actual_hours': 6877.0,
  'production_capacity_hours': 7383.0,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-11-01',
  'site_codigo': 'DIA',
  'site_nome': 'FCG Br - Diadema',
  'grupo': 'FCG Br',
  'actual_hours': 5956.0,
  'production_capacity_hours': 6792.0,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-12-01',
  'site_codigo': 'DIA',
  'site_nome': 'FCG Br - Diadema',
  'grupo': 'FCG Br',
  'actual_hours': 5371.0,
  'production_capacity_hours': 5281.47,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-01-01',
  'site_codigo': 'DIA',
  'site_nome': 'FCG Br - Diadema',
  'grupo': 'FCG Br',
  'actual_hours': 5953.0,
  'production_capacity_hours': 5893.0255,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-02-01',
  'site_codigo': 'DIA',
  'site_nome': 'FCG Br - Diadema',
  'grupo': 'FCG Br',
  'actual_hours': 5364.0,
  'production_capacity_hours': 5995.22,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-03-01',
  'site_codigo': 'DIA',
  'site_nome': 'FCG Br - Diadema',
  'grupo': 'FCG Br',
  'actual_hours': 4949.0,
  'production_capacity_hours': 5000.0,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-04-01',
  'site_codigo': 'DIA',
  'site_nome': 'FCG Br - Diadema',
  'grupo': 'FCG Br',
  'actual_hours': 6424.0,
  'production_capacity_hours': 6131.0,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-05-01',
  'site_codigo': 'DIA',
  'site_nome': 'FCG Br - Diadema',
  'grupo': 'FCG Br',
  'actual_hours': 6257.0,
  'production_capacity_hours': 6219.0,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-06-01',
  'site_codigo': 'DIA',
  'site_nome': 'FCG Br - Diadema',
  'grupo': 'FCG Br',
  'actual_hours': 7005.0,
  'production_capacity_hours': 6314.0,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-07-01',
  'site_codigo': 'DIA',
  'site_nome': 'FCG Br - Diadema',
  'grupo': 'FCG Br',
  'actual_hours': 6455.0,
  'production_capacity_hours': 6503.0,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-08-01',
  'site_codigo': 'DIA',
  'site_nome': 'FCG Br - Diadema',
  'grupo': 'FCG Br',
  'actual_hours': 6185.0,
  'production_capacity_hours': 6764.55,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-09-01',
  'site_codigo': 'DIA',
  'site_nome': 'FCG Br - Diadema',
  'grupo': 'FCG Br',
  'actual_hours': 6652.0,
  'production_capacity_hours': 6248.0,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-10-01',
  'site_codigo': 'DIA',
  'site_nome': 'FCG Br - Diadema',
  'grupo': 'FCG Br',
  'actual_hours': 4802.0,
  'production_capacity_hours': 4398.0,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-11-01',
  'site_codigo': 'DIA',
  'site_nome': 'FCG Br - Diadema',
  'grupo': 'FCG Br',
  'actual_hours': 5139.0,
  'production_capacity_hours': 5121.0,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-12-01',
  'site_codigo': 'DIA',
  'site_nome': 'FCG Br - Diadema',
  'grupo': 'FCG Br',
  'actual_hours': 4021.0,
  'production_capacity_hours': 3751.0,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2026-01-01',
  'site_codigo': 'DIA',
  'site_nome': 'FCG Br - Diadema',
  'grupo': 'FCG Br',
  'actual_hours': 5461.0,
  'production_capacity_hours': 5460.0,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2026-02-01',
  'site_codigo': 'DIA',
  'site_nome': 'FCG Br - Diadema',
  'grupo': 'FCG Br',
  'actual_hours': 5354.0,
  'production_capacity_hours': 5244.0,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2026-03-01',
  'site_codigo': 'DIA',
  'site_nome': 'FCG Br - Diadema',
  'grupo': 'FCG Br',
  'actual_hours': 5856.0,
  'production_capacity_hours': 6394.0,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2026-04-01',
  'site_codigo': 'DIA',
  'site_nome': 'FCG Br - Diadema',
  'grupo': 'FCG Br',
  'actual_hours': 5488.0,
  'production_capacity_hours': 5441.0,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2023-07-01',
  'site_codigo': 'SJC',
  'site_nome': 'Filtration Br - São José dos Campos',
  'grupo': 'Filtration Br',
  'actual_hours': 9953.0,
  'production_capacity_hours': 9987.72,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2023-08-01',
  'site_codigo': 'SJC',
  'site_nome': 'Filtration Br - São José dos Campos',
  'grupo': 'Filtration Br',
  'actual_hours': 11140.55,
  'production_capacity_hours': 11157.05,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2023-09-01',
  'site_codigo': 'SJC',
  'site_nome': 'Filtration Br - São José dos Campos',
  'grupo': 'Filtration Br',
  'actual_hours': 9855.5,
  'production_capacity_hours': 9880.82,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2023-10-01',
  'site_codigo': 'SJC',
  'site_nome': 'Filtration Br - São José dos Campos',
  'grupo': 'Filtration Br',
  'actual_hours': 10555.24,
  'production_capacity_hours': 10563.07,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2023-11-01',
  'site_codigo': 'SJC',
  'site_nome': 'Filtration Br - São José dos Campos',
  'grupo': 'Filtration Br',
  'actual_hours': 10854.24,
  'production_capacity_hours': 10883.19,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2023-12-01',
  'site_codigo': 'SJC',
  'site_nome': 'Filtration Br - São José dos Campos',
  'grupo': 'Filtration Br',
  'actual_hours': 11580.84,
  'production_capacity_hours': 11697.5,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-01-01',
  'site_codigo': 'SJC',
  'site_nome': 'Filtration Br - São José dos Campos',
  'grupo': 'Filtration Br',
  'actual_hours': 10744.43,
  'production_capacity_hours': 10750.53,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-02-01',
  'site_codigo': 'SJC',
  'site_nome': 'Filtration Br - São José dos Campos',
  'grupo': 'Filtration Br',
  'actual_hours': 11322.93,
  'production_capacity_hours': 11323.95,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-03-01',
  'site_codigo': 'SJC',
  'site_nome': 'Filtration Br - São José dos Campos',
  'grupo': 'Filtration Br',
  'actual_hours': 12053.46,
  'production_capacity_hours': 12090.35,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-04-01',
  'site_codigo': 'SJC',
  'site_nome': 'Filtration Br - São José dos Campos',
  'grupo': 'Filtration Br',
  'actual_hours': 13711.75,
  'production_capacity_hours': 13732.55,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-05-01',
  'site_codigo': 'SJC',
  'site_nome': 'Filtration Br - São José dos Campos',
  'grupo': 'Filtration Br',
  'actual_hours': 12448.44,
  'production_capacity_hours': 12467.87,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-06-01',
  'site_codigo': 'SJC',
  'site_nome': 'Filtration Br - São José dos Campos',
  'grupo': 'Filtration Br',
  'actual_hours': 11604.23,
  'production_capacity_hours': 12101.8,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-07-01',
  'site_codigo': 'SJC',
  'site_nome': 'Filtration Br - São José dos Campos',
  'grupo': 'Filtration Br',
  'actual_hours': 13495.72,
  'production_capacity_hours': 13707.9,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-08-01',
  'site_codigo': 'SJC',
  'site_nome': 'Filtration Br - São José dos Campos',
  'grupo': 'Filtration Br',
  'actual_hours': 12796.64,
  'production_capacity_hours': 12799.0,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-09-01',
  'site_codigo': 'SJC',
  'site_nome': 'Filtration Br - São José dos Campos',
  'grupo': 'Filtration Br',
  'actual_hours': 11839.0,
  'production_capacity_hours': 12146.0,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-10-01',
  'site_codigo': 'SJC',
  'site_nome': 'Filtration Br - São José dos Campos',
  'grupo': 'Filtration Br',
  'actual_hours': 11728.18,
  'production_capacity_hours': 11897.5,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-11-01',
  'site_codigo': 'SJC',
  'site_nome': 'Filtration Br - São José dos Campos',
  'grupo': 'Filtration Br',
  'actual_hours': 11681.7,
  'production_capacity_hours': 11806.25,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-12-01',
  'site_codigo': 'SJC',
  'site_nome': 'Filtration Br - São José dos Campos',
  'grupo': 'Filtration Br',
  'actual_hours': 9203.82,
  'production_capacity_hours': 9230.59615384615,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-01-01',
  'site_codigo': 'SJC',
  'site_nome': 'Filtration Br - São José dos Campos',
  'grupo': 'Filtration Br',
  'actual_hours': 11062.3,
  'production_capacity_hours': 11299.75,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-02-01',
  'site_codigo': 'SJC',
  'site_nome': 'Filtration Br - São José dos Campos',
  'grupo': 'Filtration Br',
  'actual_hours': 11511.7,
  'production_capacity_hours': 11644.6,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-03-01',
  'site_codigo': 'SJC',
  'site_nome': 'Filtration Br - São José dos Campos',
  'grupo': 'Filtration Br',
  'actual_hours': 11349.18,
  'production_capacity_hours': 11368.49,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-04-01',
  'site_codigo': 'SJC',
  'site_nome': 'Filtration Br - São José dos Campos',
  'grupo': 'Filtration Br',
  'actual_hours': 12742.23,
  'production_capacity_hours': 12861.98,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-05-01',
  'site_codigo': 'SJC',
  'site_nome': 'Filtration Br - São José dos Campos',
  'grupo': 'Filtration Br',
  'actual_hours': 12106.0,
  'production_capacity_hours': 12154.6,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-06-01',
  'site_codigo': 'SJC',
  'site_nome': 'Filtration Br - São José dos Campos',
  'grupo': 'Filtration Br',
  'actual_hours': 12986.89,
  'production_capacity_hours': 13035.76,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-07-01',
  'site_codigo': 'SJC',
  'site_nome': 'Filtration Br - São José dos Campos',
  'grupo': 'Filtration Br',
  'actual_hours': 14230.0,
  'production_capacity_hours': 14616.0,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-08-01',
  'site_codigo': 'SJC',
  'site_nome': 'Filtration Br - São José dos Campos',
  'grupo': 'Filtration Br',
  'actual_hours': 13125.0,
  'production_capacity_hours': 13160.0,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-09-01',
  'site_codigo': 'SJC',
  'site_nome': 'Filtration Br - São José dos Campos',
  'grupo': 'Filtration Br',
  'actual_hours': 14138.41,
  'production_capacity_hours': 14438.2,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-10-01',
  'site_codigo': 'SJC',
  'site_nome': 'Filtration Br - São José dos Campos',
  'grupo': 'Filtration Br',
  'actual_hours': 13710.0,
  'production_capacity_hours': 14657.0,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-11-01',
  'site_codigo': 'SJC',
  'site_nome': 'Filtration Br - São José dos Campos',
  'grupo': 'Filtration Br',
  'actual_hours': 13304.0,
  'production_capacity_hours': 13391.0,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-12-01',
  'site_codigo': 'SJC',
  'site_nome': 'Filtration Br - São José dos Campos',
  'grupo': 'Filtration Br',
  'actual_hours': 11325.0,
  'production_capacity_hours': 11389.0,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2026-01-01',
  'site_codigo': 'SJC',
  'site_nome': 'Filtration Br - São José dos Campos',
  'grupo': 'Filtration Br',
  'actual_hours': 11605.0,
  'production_capacity_hours': 11928.0,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2026-02-01',
  'site_codigo': 'SJC',
  'site_nome': 'Filtration Br - São José dos Campos',
  'grupo': 'Filtration Br',
  'actual_hours': 13018.0,
  'production_capacity_hours': 13330.0,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2026-03-01',
  'site_codigo': 'SJC',
  'site_nome': 'Filtration Br - São José dos Campos',
  'grupo': 'Filtration Br',
  'actual_hours': 14185.0,
  'production_capacity_hours': 14498.0,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2026-04-01',
  'site_codigo': 'SJC',
  'site_nome': 'Filtration Br - São José dos Campos',
  'grupo': 'Filtration Br',
  'actual_hours': 12685.0,
  'production_capacity_hours': 12786.0,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2023-07-01',
  'site_codigo': 'CAC',
  'site_nome': 'MSG Br CAC - Cachoeirinha',
  'grupo': 'MSG Br',
  'actual_hours': 7153.11,
  'production_capacity_hours': 9346.68,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2023-08-01',
  'site_codigo': 'CAC',
  'site_nome': 'MSG Br CAC - Cachoeirinha',
  'grupo': 'MSG Br',
  'actual_hours': 8761.75000000001,
  'production_capacity_hours': 10560.96,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2023-09-01',
  'site_codigo': 'CAC',
  'site_nome': 'MSG Br CAC - Cachoeirinha',
  'grupo': 'MSG Br',
  'actual_hours': 9501.25000000001,
  'production_capacity_hours': 10062.89,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2023-10-01',
  'site_codigo': 'CAC',
  'site_nome': 'MSG Br CAC - Cachoeirinha',
  'grupo': 'MSG Br',
  'actual_hours': 10358.69,
  'production_capacity_hours': 10773.72,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2023-11-01',
  'site_codigo': 'CAC',
  'site_nome': 'MSG Br CAC - Cachoeirinha',
  'grupo': 'MSG Br',
  'actual_hours': 9612.04347754168,
  'production_capacity_hours': 10108.67,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2023-12-01',
  'site_codigo': 'CAC',
  'site_nome': 'MSG Br CAC - Cachoeirinha',
  'grupo': 'MSG Br',
  'actual_hours': 5358.24999999998,
  'production_capacity_hours': 6316.28,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-01-01',
  'site_codigo': 'CAC',
  'site_nome': 'MSG Br CAC - Cachoeirinha',
  'grupo': 'MSG Br',
  'actual_hours': 7360.09,
  'production_capacity_hours': 9647.05,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-02-01',
  'site_codigo': 'CAC',
  'site_nome': 'MSG Br CAC - Cachoeirinha',
  'grupo': 'MSG Br',
  'actual_hours': 8166.5221,
  'production_capacity_hours': 9032.28,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-03-01',
  'site_codigo': 'CAC',
  'site_nome': 'MSG Br CAC - Cachoeirinha',
  'grupo': 'MSG Br',
  'actual_hours': 8096.12000000004,
  'production_capacity_hours': 8973.51,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-04-01',
  'site_codigo': 'CAC',
  'site_nome': 'MSG Br CAC - Cachoeirinha',
  'grupo': 'MSG Br',
  'actual_hours': 9095.0,
  'production_capacity_hours': 11091.03,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-05-01',
  'site_codigo': 'CAC',
  'site_nome': 'MSG Br CAC - Cachoeirinha',
  'grupo': 'MSG Br',
  'actual_hours': 8190.57950000003,
  'production_capacity_hours': 10884.36,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-06-01',
  'site_codigo': 'CAC',
  'site_nome': 'MSG Br CAC - Cachoeirinha',
  'grupo': 'MSG Br',
  'actual_hours': 8833.91,
  'production_capacity_hours': 9918.96,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-07-01',
  'site_codigo': 'CAC',
  'site_nome': 'MSG Br CAC - Cachoeirinha',
  'grupo': 'MSG Br',
  'actual_hours': 9593.24000000003,
  'production_capacity_hours': 11405.69,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-08-01',
  'site_codigo': 'CAC',
  'site_nome': 'MSG Br CAC - Cachoeirinha',
  'grupo': 'MSG Br',
  'actual_hours': 9092.48999999998,
  'production_capacity_hours': 10939.31,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-09-01',
  'site_codigo': 'CAC',
  'site_nome': 'MSG Br CAC - Cachoeirinha',
  'grupo': 'MSG Br',
  'actual_hours': 8223.97,
  'production_capacity_hours': 10187.69,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-10-01',
  'site_codigo': 'CAC',
  'site_nome': 'MSG Br CAC - Cachoeirinha',
  'grupo': 'MSG Br',
  'actual_hours': 9896.48000000002,
  'production_capacity_hours': 11359.54,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-11-01',
  'site_codigo': 'CAC',
  'site_nome': 'MSG Br CAC - Cachoeirinha',
  'grupo': 'MSG Br',
  'actual_hours': 7566.92000000003,
  'production_capacity_hours': 9750.77,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-12-01',
  'site_codigo': 'CAC',
  'site_nome': 'MSG Br CAC - Cachoeirinha',
  'grupo': 'MSG Br',
  'actual_hours': 4281.35999999999,
  'production_capacity_hours': 5713.29,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-01-01',
  'site_codigo': 'CAC',
  'site_nome': 'MSG Br CAC - Cachoeirinha',
  'grupo': 'MSG Br',
  'actual_hours': 7708.44000000002,
  'production_capacity_hours': 9508.44,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-02-01',
  'site_codigo': 'CAC',
  'site_nome': 'MSG Br CAC - Cachoeirinha',
  'grupo': 'MSG Br',
  'actual_hours': 7973.05,
  'production_capacity_hours': 9431.28,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-03-01',
  'site_codigo': 'CAC',
  'site_nome': 'MSG Br CAC - Cachoeirinha',
  'grupo': 'MSG Br',
  'actual_hours': 8506.77,
  'production_capacity_hours': 11178.75,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-04-01',
  'site_codigo': 'CAC',
  'site_nome': 'MSG Br CAC - Cachoeirinha',
  'grupo': 'MSG Br',
  'actual_hours': 10065.07,
  'production_capacity_hours': 12803.73,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-05-01',
  'site_codigo': 'CAC',
  'site_nome': 'MSG Br CAC - Cachoeirinha',
  'grupo': 'MSG Br',
  'actual_hours': 10665.3800000001,
  'production_capacity_hours': 12407.72,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-06-01',
  'site_codigo': 'CAC',
  'site_nome': 'MSG Br CAC - Cachoeirinha',
  'grupo': 'MSG Br',
  'actual_hours': 10515.83,
  'production_capacity_hours': 12587.01,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-07-01',
  'site_codigo': 'CAC',
  'site_nome': 'MSG Br CAC - Cachoeirinha',
  'grupo': 'MSG Br',
  'actual_hours': 9992.69999999999,
  'production_capacity_hours': 12545.06,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-08-01',
  'site_codigo': 'CAC',
  'site_nome': 'MSG Br CAC - Cachoeirinha',
  'grupo': 'MSG Br',
  'actual_hours': 9410.51,
  'production_capacity_hours': 11565.77,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-09-01',
  'site_codigo': 'CAC',
  'site_nome': 'MSG Br CAC - Cachoeirinha',
  'grupo': 'MSG Br',
  'actual_hours': 8257.44,
  'production_capacity_hours': 10857.42,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-10-01',
  'site_codigo': 'CAC',
  'site_nome': 'MSG Br CAC - Cachoeirinha',
  'grupo': 'MSG Br',
  'actual_hours': 9664.42,
  'production_capacity_hours': 11235.5,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-11-01',
  'site_codigo': 'CAC',
  'site_nome': 'MSG Br CAC - Cachoeirinha',
  'grupo': 'MSG Br',
  'actual_hours': 8064.97,
  'production_capacity_hours': 9541.54,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-12-01',
  'site_codigo': 'CAC',
  'site_nome': 'MSG Br CAC - Cachoeirinha',
  'grupo': 'MSG Br',
  'actual_hours': 6581.7,
  'production_capacity_hours': 6918.72,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2026-01-01',
  'site_codigo': 'CAC',
  'site_nome': 'MSG Br CAC - Cachoeirinha',
  'grupo': 'MSG Br',
  'actual_hours': 5279.95,
  'production_capacity_hours': 6811.42,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2026-02-01',
  'site_codigo': 'CAC',
  'site_nome': 'MSG Br CAC - Cachoeirinha',
  'grupo': 'MSG Br',
  'actual_hours': 6812.63,
  'production_capacity_hours': 7933.51,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2026-03-01',
  'site_codigo': 'CAC',
  'site_nome': 'MSG Br CAC - Cachoeirinha',
  'grupo': 'MSG Br',
  'actual_hours': 8170.0,
  'production_capacity_hours': 9425.5,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2026-04-01',
  'site_codigo': 'CAC',
  'site_nome': 'MSG Br CAC - Cachoeirinha',
  'grupo': 'MSG Br',
  'actual_hours': 8112.0,
  'production_capacity_hours': 8154.12,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2023-07-01',
  'site_codigo': 'JAC',
  'site_nome': 'MSG Br JAC - Jacareí',
  'grupo': 'MSG Br',
  'actual_hours': 2729.48,
  'production_capacity_hours': 3377.68,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2023-08-01',
  'site_codigo': 'JAC',
  'site_nome': 'MSG Br JAC - Jacareí',
  'grupo': 'MSG Br',
  'actual_hours': 2428.1,
  'production_capacity_hours': 3205.41,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2023-09-01',
  'site_codigo': 'JAC',
  'site_nome': 'MSG Br JAC - Jacareí',
  'grupo': 'MSG Br',
  'actual_hours': 2300.95,
  'production_capacity_hours': 2897.07,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2023-10-01',
  'site_codigo': 'JAC',
  'site_nome': 'MSG Br JAC - Jacareí',
  'grupo': 'MSG Br',
  'actual_hours': 2456.85,
  'production_capacity_hours': 2929.91,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2023-11-01',
  'site_codigo': 'JAC',
  'site_nome': 'MSG Br JAC - Jacareí',
  'grupo': 'MSG Br',
  'actual_hours': 2340.34,
  'production_capacity_hours': 2822.42,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2023-12-01',
  'site_codigo': 'JAC',
  'site_nome': 'MSG Br JAC - Jacareí',
  'grupo': 'MSG Br',
  'actual_hours': 1647.21,
  'production_capacity_hours': 1964.64,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-01-01',
  'site_codigo': 'JAC',
  'site_nome': 'MSG Br JAC - Jacareí',
  'grupo': 'MSG Br',
  'actual_hours': 1819.3,
  'production_capacity_hours': 2310.54,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-02-01',
  'site_codigo': 'JAC',
  'site_nome': 'MSG Br JAC - Jacareí',
  'grupo': 'MSG Br',
  'actual_hours': 2415.6,
  'production_capacity_hours': 3167.4,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-03-01',
  'site_codigo': 'JAC',
  'site_nome': 'MSG Br JAC - Jacareí',
  'grupo': 'MSG Br',
  'actual_hours': 1957.1,
  'production_capacity_hours': 3139.3,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-04-01',
  'site_codigo': 'JAC',
  'site_nome': 'MSG Br JAC - Jacareí',
  'grupo': 'MSG Br',
  'actual_hours': 2623.26,
  'production_capacity_hours': 3049.4,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-05-01',
  'site_codigo': 'JAC',
  'site_nome': 'MSG Br JAC - Jacareí',
  'grupo': 'MSG Br',
  'actual_hours': 2343.7,
  'production_capacity_hours': 2926.2,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-06-01',
  'site_codigo': 'JAC',
  'site_nome': 'MSG Br JAC - Jacareí',
  'grupo': 'MSG Br',
  'actual_hours': 2565.8,
  'production_capacity_hours': 3102.6,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-07-01',
  'site_codigo': 'JAC',
  'site_nome': 'MSG Br JAC - Jacareí',
  'grupo': 'MSG Br',
  'actual_hours': 2727.4,
  'production_capacity_hours': 3441.5,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-08-01',
  'site_codigo': 'JAC',
  'site_nome': 'MSG Br JAC - Jacareí',
  'grupo': 'MSG Br',
  'actual_hours': 2767.6,
  'production_capacity_hours': 3237.0,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-09-01',
  'site_codigo': 'JAC',
  'site_nome': 'MSG Br JAC - Jacareí',
  'grupo': 'MSG Br',
  'actual_hours': 2399.1,
  'production_capacity_hours': 2956.3,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-10-01',
  'site_codigo': 'JAC',
  'site_nome': 'MSG Br JAC - Jacareí',
  'grupo': 'MSG Br',
  'actual_hours': 2939.33,
  'production_capacity_hours': 3544.15,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-11-01',
  'site_codigo': 'JAC',
  'site_nome': 'MSG Br JAC - Jacareí',
  'grupo': 'MSG Br',
  'actual_hours': 2603.8,
  'production_capacity_hours': 3020.9,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-12-01',
  'site_codigo': 'JAC',
  'site_nome': 'MSG Br JAC - Jacareí',
  'grupo': 'MSG Br',
  'actual_hours': 2206.1,
  'production_capacity_hours': 2505.0,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-01-01',
  'site_codigo': 'JAC',
  'site_nome': 'MSG Br JAC - Jacareí',
  'grupo': 'MSG Br',
  'actual_hours': 2045.9,
  'production_capacity_hours': 2538.1,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-02-01',
  'site_codigo': 'JAC',
  'site_nome': 'MSG Br JAC - Jacareí',
  'grupo': 'MSG Br',
  'actual_hours': 2683.7,
  'production_capacity_hours': 3285.2,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-03-01',
  'site_codigo': 'JAC',
  'site_nome': 'MSG Br JAC - Jacareí',
  'grupo': 'MSG Br',
  'actual_hours': 2433.8,
  'production_capacity_hours': 3034.5,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-04-01',
  'site_codigo': 'JAC',
  'site_nome': 'MSG Br JAC - Jacareí',
  'grupo': 'MSG Br',
  'actual_hours': 2056.7,
  'production_capacity_hours': 2624.7,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-05-01',
  'site_codigo': 'JAC',
  'site_nome': 'MSG Br JAC - Jacareí',
  'grupo': 'MSG Br',
  'actual_hours': 2223.8,
  'production_capacity_hours': 2898.2,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-06-01',
  'site_codigo': 'JAC',
  'site_nome': 'MSG Br JAC - Jacareí',
  'grupo': 'MSG Br',
  'actual_hours': 2329.9,
  'production_capacity_hours': 3054.9,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-07-01',
  'site_codigo': 'JAC',
  'site_nome': 'MSG Br JAC - Jacareí',
  'grupo': 'MSG Br',
  'actual_hours': 2338.35,
  'production_capacity_hours': 3632.04,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-08-01',
  'site_codigo': 'JAC',
  'site_nome': 'MSG Br JAC - Jacareí',
  'grupo': 'MSG Br',
  'actual_hours': 1895.0,
  'production_capacity_hours': 2755.2,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-09-01',
  'site_codigo': 'JAC',
  'site_nome': 'MSG Br JAC - Jacareí',
  'grupo': 'MSG Br',
  'actual_hours': 2198.8,
  'production_capacity_hours': 2788.1,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-10-01',
  'site_codigo': 'JAC',
  'site_nome': 'MSG Br JAC - Jacareí',
  'grupo': 'MSG Br',
  'actual_hours': 2064.2,
  'production_capacity_hours': 2932.0,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-11-01',
  'site_codigo': 'JAC',
  'site_nome': 'MSG Br JAC - Jacareí',
  'grupo': 'MSG Br',
  'actual_hours': 1918.5,
  'production_capacity_hours': 2438.2,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-12-01',
  'site_codigo': 'JAC',
  'site_nome': 'MSG Br JAC - Jacareí',
  'grupo': 'MSG Br',
  'actual_hours': 1073.5,
  'production_capacity_hours': 1107.4,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2026-01-01',
  'site_codigo': 'JAC',
  'site_nome': 'MSG Br JAC - Jacareí',
  'grupo': 'MSG Br',
  'actual_hours': 1514.5,
  'production_capacity_hours': 1856.8,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2026-02-01',
  'site_codigo': 'JAC',
  'site_nome': 'MSG Br JAC - Jacareí',
  'grupo': 'MSG Br',
  'actual_hours': 2521.5,
  'production_capacity_hours': 2738.7,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2026-03-01',
  'site_codigo': 'JAC',
  'site_nome': 'MSG Br JAC - Jacareí',
  'grupo': 'MSG Br',
  'actual_hours': 2803.1,
  'production_capacity_hours': 2807.8,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2026-04-01',
  'site_codigo': 'JAC',
  'site_nome': 'MSG Br JAC - Jacareí',
  'grupo': 'MSG Br',
  'actual_hours': 2512.33,
  'production_capacity_hours': 2710.53,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2023-07-01',
  'site_codigo': 'JUN',
  'site_nome': 'EMG Br JU - Jundiaí',
  'grupo': 'EMG Br',
  'actual_hours': 771.065116853774,
  'production_capacity_hours': 815.990432817906,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2023-08-01',
  'site_codigo': 'JUN',
  'site_nome': 'EMG Br JU - Jundiaí',
  'grupo': 'EMG Br',
  'actual_hours': 864.399752877215,
  'production_capacity_hours': 698.542821083104,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2023-09-01',
  'site_codigo': 'JUN',
  'site_nome': 'EMG Br JU - Jundiaí',
  'grupo': 'EMG Br',
  'actual_hours': 576.336793228836,
  'production_capacity_hours': 512.231117877568,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2023-10-01',
  'site_codigo': 'JUN',
  'site_nome': 'EMG Br JU - Jundiaí',
  'grupo': 'EMG Br',
  'actual_hours': 657.376562169032,
  'production_capacity_hours': 566.609087057827,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2023-11-01',
  'site_codigo': 'JUN',
  'site_nome': 'EMG Br JU - Jundiaí',
  'grupo': 'EMG Br',
  'actual_hours': 676.630269010803,
  'production_capacity_hours': 597.378344277342,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2023-12-01',
  'site_codigo': 'JUN',
  'site_nome': 'EMG Br JU - Jundiaí',
  'grupo': 'EMG Br',
  'actual_hours': 451.022666984396,
  'production_capacity_hours': 429.65105239003,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-01-01',
  'site_codigo': 'JUN',
  'site_nome': 'EMG Br JU - Jundiaí',
  'grupo': 'EMG Br',
  'actual_hours': 954.662964237803,
  'production_capacity_hours': 770.789147055709,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-02-01',
  'site_codigo': 'JUN',
  'site_nome': 'EMG Br JU - Jundiaí',
  'grupo': 'EMG Br',
  'actual_hours': 897.818686895432,
  'production_capacity_hours': 810.406857833792,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-03-01',
  'site_codigo': 'JUN',
  'site_nome': 'EMG Br JU - Jundiaí',
  'grupo': 'EMG Br',
  'actual_hours': 736.830192402739,
  'production_capacity_hours': 685.798700840218,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-04-01',
  'site_codigo': 'JUN',
  'site_nome': 'EMG Br JU - Jundiaí',
  'grupo': 'EMG Br',
  'actual_hours': 771.065116853774,
  'production_capacity_hours': 679.380798559627,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-05-01',
  'site_codigo': 'JUN',
  'site_nome': 'EMG Br JU - Jundiaí',
  'grupo': 'EMG Br',
  'actual_hours': 662.877621266681,
  'production_capacity_hours': 713.716575760785,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-06-01',
  'site_codigo': 'JUN',
  'site_nome': 'EMG Br JU - Jundiaí',
  'grupo': 'EMG Br',
  'actual_hours': 921.427398856175,
  'production_capacity_hours': 842.578885123208,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-07-01',
  'site_codigo': 'JUN',
  'site_nome': 'EMG Br JU - Jundiaí',
  'grupo': 'EMG Br',
  'actual_hours': 1026.86436489444,
  'production_capacity_hours': 1010.3611876015,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-08-01',
  'site_codigo': 'JUN',
  'site_nome': 'EMG Br JU - Jundiaí',
  'grupo': 'EMG Br',
  'actual_hours': 746.280370142272,
  'production_capacity_hours': 669.786126334462,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-09-01',
  'site_codigo': 'JUN',
  'site_nome': 'EMG Br JU - Jundiaí',
  'grupo': 'EMG Br',
  'actual_hours': 853.581003318506,
  'production_capacity_hours': 568.44277342371,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-10-01',
  'site_codigo': 'JUN',
  'site_nome': 'EMG Br JU - Jundiaí',
  'grupo': 'EMG Br',
  'actual_hours': 859.341437352609,
  'production_capacity_hours': 799.821169812187,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-11-01',
  'site_codigo': 'JUN',
  'site_nome': 'EMG Br JU - Jundiaí',
  'grupo': 'EMG Br',
  'actual_hours': 726.393766451317,
  'production_capacity_hours': 633.125051452729,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-12-01',
  'site_codigo': 'JUN',
  'site_nome': 'EMG Br JU - Jundiaí',
  'grupo': 'EMG Br',
  'actual_hours': 464.733231626421,
  'production_capacity_hours': 502.911406922968,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-01-01',
  'site_codigo': 'JUN',
  'site_nome': 'EMG Br JU - Jundiaí',
  'grupo': 'EMG Br',
  'actual_hours': 1002.68977732119,
  'production_capacity_hours': 1015.74699951105,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-02-01',
  'site_codigo': 'JUN',
  'site_nome': 'EMG Br JU - Jundiaí',
  'grupo': 'EMG Br',
  'actual_hours': 699.307376613359,
  'production_capacity_hours': 748.565051669844,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-03-01',
  'site_codigo': 'JUN',
  'site_nome': 'EMG Br JU - Jundiaí',
  'grupo': 'EMG Br',
  'actual_hours': 840.40954246805,
  'production_capacity_hours': 713.555211360587,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-04-01',
  'site_codigo': 'JUN',
  'site_nome': 'EMG Br JU - Jundiaí',
  'grupo': 'EMG Br',
  'actual_hours': 929.46389609193,
  'production_capacity_hours': 931.103120018711,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-05-01',
  'site_codigo': 'JUN',
  'site_nome': 'EMG Br JU - Jundiaí',
  'grupo': 'EMG Br',
  'actual_hours': 802.191851230318,
  'production_capacity_hours': 738.613635762198,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-06-01',
  'site_codigo': 'JUN',
  'site_nome': 'EMG Br JU - Jundiaí',
  'grupo': 'EMG Br',
  'actual_hours': 800.511369360305,
  'production_capacity_hours': 711.884906449904,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-07-01',
  'site_codigo': 'JUN',
  'site_nome': 'EMG Br JU - Jundiaí',
  'grupo': 'EMG Br',
  'actual_hours': 813.9671,
  'production_capacity_hours': 677.166399999999,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-08-01',
  'site_codigo': 'JUN',
  'site_nome': 'EMG Br JU - Jundiaí',
  'grupo': 'EMG Br',
  'actual_hours': 748.184,
  'production_capacity_hours': 595.4236,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-09-01',
  'site_codigo': 'JUN',
  'site_nome': 'EMG Br JU - Jundiaí',
  'grupo': 'EMG Br',
  'actual_hours': 924.9167,
  'production_capacity_hours': 891.825800000002,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-10-01',
  'site_codigo': 'JUN',
  'site_nome': 'EMG Br JU - Jundiaí',
  'grupo': 'EMG Br',
  'actual_hours': 959.783,
  'production_capacity_hours': 857.6464,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-11-01',
  'site_codigo': 'JUN',
  'site_nome': 'EMG Br JU - Jundiaí',
  'grupo': 'EMG Br',
  'actual_hours': 919.1668,
  'production_capacity_hours': 765.826500000001,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-12-01',
  'site_codigo': 'JUN',
  'site_nome': 'EMG Br JU - Jundiaí',
  'grupo': 'EMG Br',
  'actual_hours': 774.5327,
  'production_capacity_hours': 669.9414,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2026-01-01',
  'site_codigo': 'JUN',
  'site_nome': 'EMG Br JU - Jundiaí',
  'grupo': 'EMG Br',
  'actual_hours': 1025.4669,
  'production_capacity_hours': 865.9645,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2026-02-01',
  'site_codigo': 'JUN',
  'site_nome': 'EMG Br JU - Jundiaí',
  'grupo': 'EMG Br',
  'actual_hours': 786.487,
  'production_capacity_hours': 789.8827,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2026-03-01',
  'site_codigo': 'JUN',
  'site_nome': 'EMG Br JU - Jundiaí',
  'grupo': 'EMG Br',
  'actual_hours': 1139.01,
  'production_capacity_hours': 927.1059,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2026-04-01',
  'site_codigo': 'JUN',
  'site_nome': 'EMG Br JU - Jundiaí',
  'grupo': 'EMG Br',
  'actual_hours': 836.7159,
  'production_capacity_hours': 694.0899,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2023-07-01',
  'site_codigo': 'PER',
  'site_nome': 'EMG Br SP - Perus',
  'grupo': 'EMG Br',
  'actual_hours': 8287.6,
  'production_capacity_hours': 8370.69,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2023-08-01',
  'site_codigo': 'PER',
  'site_nome': 'EMG Br SP - Perus',
  'grupo': 'EMG Br',
  'actual_hours': 9821.88,
  'production_capacity_hours': 10499.9145333333,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2023-09-01',
  'site_codigo': 'PER',
  'site_nome': 'EMG Br SP - Perus',
  'grupo': 'EMG Br',
  'actual_hours': 9532.91,
  'production_capacity_hours': 9767.38833333333,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2023-10-01',
  'site_codigo': 'PER',
  'site_nome': 'EMG Br SP - Perus',
  'grupo': 'EMG Br',
  'actual_hours': 8762.74,
  'production_capacity_hours': 9765.8,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2023-11-01',
  'site_codigo': 'PER',
  'site_nome': 'EMG Br SP - Perus',
  'grupo': 'EMG Br',
  'actual_hours': 9229.3,
  'production_capacity_hours': 9294.0,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2023-12-01',
  'site_codigo': 'PER',
  'site_nome': 'EMG Br SP - Perus',
  'grupo': 'EMG Br',
  'actual_hours': 8189.0,
  'production_capacity_hours': 9016.84583333333,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-01-01',
  'site_codigo': 'PER',
  'site_nome': 'EMG Br SP - Perus',
  'grupo': 'EMG Br',
  'actual_hours': 9556.74,
  'production_capacity_hours': 10070.4442,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-02-01',
  'site_codigo': 'PER',
  'site_nome': 'EMG Br SP - Perus',
  'grupo': 'EMG Br',
  'actual_hours': 8773.0,
  'production_capacity_hours': 9606.0,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-03-01',
  'site_codigo': 'PER',
  'site_nome': 'EMG Br SP - Perus',
  'grupo': 'EMG Br',
  'actual_hours': 8717.24,
  'production_capacity_hours': 9829.87065,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-04-01',
  'site_codigo': 'PER',
  'site_nome': 'EMG Br SP - Perus',
  'grupo': 'EMG Br',
  'actual_hours': 9136.0,
  'production_capacity_hours': 9364.11,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-05-01',
  'site_codigo': 'PER',
  'site_nome': 'EMG Br SP - Perus',
  'grupo': 'EMG Br',
  'actual_hours': 8126.0,
  'production_capacity_hours': 9259.5,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-06-01',
  'site_codigo': 'PER',
  'site_nome': 'EMG Br SP - Perus',
  'grupo': 'EMG Br',
  'actual_hours': 8781.35,
  'production_capacity_hours': 8700.17,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-07-01',
  'site_codigo': 'PER',
  'site_nome': 'EMG Br SP - Perus',
  'grupo': 'EMG Br',
  'actual_hours': 9647.99,
  'production_capacity_hours': 9251.42,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-08-01',
  'site_codigo': 'PER',
  'site_nome': 'EMG Br SP - Perus',
  'grupo': 'EMG Br',
  'actual_hours': 10069.8,
  'production_capacity_hours': 9274.12,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-09-01',
  'site_codigo': 'PER',
  'site_nome': 'EMG Br SP - Perus',
  'grupo': 'EMG Br',
  'actual_hours': 8458.71,
  'production_capacity_hours': 8979.65,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-10-01',
  'site_codigo': 'PER',
  'site_nome': 'EMG Br SP - Perus',
  'grupo': 'EMG Br',
  'actual_hours': 10529.0,
  'production_capacity_hours': 11245.22,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-11-01',
  'site_codigo': 'PER',
  'site_nome': 'EMG Br SP - Perus',
  'grupo': 'EMG Br',
  'actual_hours': 8349.0,
  'production_capacity_hours': 12326.4828,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2024-12-01',
  'site_codigo': 'PER',
  'site_nome': 'EMG Br SP - Perus',
  'grupo': 'EMG Br',
  'actual_hours': 7245.34,
  'production_capacity_hours': 11429.2528,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-01-01',
  'site_codigo': 'PER',
  'site_nome': 'EMG Br SP - Perus',
  'grupo': 'EMG Br',
  'actual_hours': 8571.49,
  'production_capacity_hours': 13002.962,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-02-01',
  'site_codigo': 'PER',
  'site_nome': 'EMG Br SP - Perus',
  'grupo': 'EMG Br',
  'actual_hours': 8850.09,
  'production_capacity_hours': 13045.854,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-03-01',
  'site_codigo': 'PER',
  'site_nome': 'EMG Br SP - Perus',
  'grupo': 'EMG Br',
  'actual_hours': 9733.29,
  'production_capacity_hours': 11425.3,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-04-01',
  'site_codigo': 'PER',
  'site_nome': 'EMG Br SP - Perus',
  'grupo': 'EMG Br',
  'actual_hours': 10104.44,
  'production_capacity_hours': 10308.46,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-05-01',
  'site_codigo': 'PER',
  'site_nome': 'EMG Br SP - Perus',
  'grupo': 'EMG Br',
  'actual_hours': 8483.47,
  'production_capacity_hours': 8863.275,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-06-01',
  'site_codigo': 'PER',
  'site_nome': 'EMG Br SP - Perus',
  'grupo': 'EMG Br',
  'actual_hours': 10263.02,
  'production_capacity_hours': 10212.21,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-07-01',
  'site_codigo': 'PER',
  'site_nome': 'EMG Br SP - Perus',
  'grupo': 'EMG Br',
  'actual_hours': 10199.6,
  'production_capacity_hours': 11218.66,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-08-01',
  'site_codigo': 'PER',
  'site_nome': 'EMG Br SP - Perus',
  'grupo': 'EMG Br',
  'actual_hours': 10163.56,
  'production_capacity_hours': 10157.65,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-09-01',
  'site_codigo': 'PER',
  'site_nome': 'EMG Br SP - Perus',
  'grupo': 'EMG Br',
  'actual_hours': 9310.96999999999,
  'production_capacity_hours': 12950.8,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-10-01',
  'site_codigo': 'PER',
  'site_nome': 'EMG Br SP - Perus',
  'grupo': 'EMG Br',
  'actual_hours': 10700.44,
  'production_capacity_hours': 12552.31,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-11-01',
  'site_codigo': 'PER',
  'site_nome': 'EMG Br SP - Perus',
  'grupo': 'EMG Br',
  'actual_hours': 7866.52000000057,
  'production_capacity_hours': 10737.35,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2025-12-01',
  'site_codigo': 'PER',
  'site_nome': 'EMG Br SP - Perus',
  'grupo': 'EMG Br',
  'actual_hours': 7570.0,
  'production_capacity_hours': 8771.0,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2026-01-01',
  'site_codigo': 'PER',
  'site_nome': 'EMG Br SP - Perus',
  'grupo': 'EMG Br',
  'actual_hours': 7187.92,
  'production_capacity_hours': 9883.8,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2026-02-01',
  'site_codigo': 'PER',
  'site_nome': 'EMG Br SP - Perus',
  'grupo': 'EMG Br',
  'actual_hours': 7276.51833333333,
  'production_capacity_hours': 8794.335,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2026-03-01',
  'site_codigo': 'PER',
  'site_nome': 'EMG Br SP - Perus',
  'grupo': 'EMG Br',
  'actual_hours': 7557.56999999998,
  'production_capacity_hours': 9425.17,
  'origem': 'Carga inicial Absorption FY26'},
 {'mes_ref': '2026-04-01',
  'site_codigo': 'PER',
  'site_nome': 'EMG Br SP - Perus',
  'grupo': 'EMG Br',
  'actual_hours': 6075.21,
  'production_capacity_hours': 7414.6,
  'origem': 'Carga inicial Absorption FY26'}]



ENERGIA_REGISTROS_SEED_B64 = """eNrsvd2ydEdyHfYqiLm1WFH5n+k7ihoxxDBthSYUvvAFAx5CJEIcQAYwctgOP4zDV7rwU/DFnNVn0L1376qZUxqhd22gZxgk45wvzwd0nVWVtWrlWv/L//Wr3331/d9999V/+NV//8WvsIL9RaW/qPCrf/HFr77/+oev/u633/791//wbfvmX/3lX92/+s23v/uqfe1vf/PXX/zL777Ib33xF1/81Ze//cdvv/r6u6+/+ccv25/8h+9+/5++ffyp9qW///o/f/39lx9f/PaHr7/95ovf/B/f//DV777/4l+177Qv/Mvvvvw/v/6n9of/w7ff/HD7W379zVff/cPXX37x1T/983/54buvf3v76b/99pvvf/+7b//u2+++/oevv/nyn/IPCpswlZrf/f03X//9l3//1fa7v/qP//M/bgv/4//+j/ua3/7++x++/bv/9bv2h8Eqcy3ASuQfP++H/Cy+/yG/VwsBoGN++avfff19/vvkd/Dvfvj2m9s36+brX33/228/PoNf3/6/L7D9E7R/qK9+93dffve//f7r//zx2X753T98+cXX33z926+//Kcv/vovf/N3v/4ff/3v/vrf/OUX/90Xv/7bf/Ob3/xPv/7Nr/7vf/HFFVbrr//5//n+i2++/OH33335T6OFkigWJhUHS/W3f/svf/j9cbFAuWotDGQ1nlYMBSoXtqfFYi7Oomj/NasFr1qtf/Vv/vKwWv/6r26r9Rf5YefH87v9In1882mRPr74Xw0fd/NJ9DxKtktBikIl9IAbrk5MS+PmJ12JT0AjrNSam1LMIQOdMQoHGunTarBaFJRaKzxjwwuShurS2Pib8U72N7ed7G++/O2X3331z//fKWcOBqNaAZyBzbZou1Sei5FwUsEDdDBEkJeGzjkL9QlM1eGm9s2X3xxXpx42tPsP2CxIXRs0//5/PKzFr//2Yy3+fVuK33/z919/+bQUH3/gaSnaF/+HL3/4+psv/vJ3X/0IhGmYrLME+HNbgjcAep/+b/7muBn966//6YfvvvzhYyPJFfjNP/+/337xN99+/8//5Yu///b77Ih/95++/X5/uG8rns/4x/f+fHwgeVQsAlPHyKZou1rZWBOWaEc+du4uXG3tg2SRtfsEsCg/fsfsrGiuXcu+ma1YXmfo+eLJENkCHFo1LdkcsPjSoPu3v/53oy3vN/82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"""

def energia_registros_seed_rows():
    try:
        return json.loads(zlib.decompress(base64.b64decode(ENERGIA_REGISTROS_SEED_B64.encode("ascii"))).decode("utf-8"))
    except Exception:
        logging.exception("Falha ao descompactar carga inicial de EnergiaRegistro")
        return []

def energia_norm_txt(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    s = str(v).strip().lower()
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"\s+", " ", s)
    return s

def energia_safe_float(v, default=0.0):
    if v is None or v == "":
        return default
    if isinstance(v, (int, float)) and not pd.isna(v):
        return float(v)
    s = str(v).strip()
    if s in ["-", "—", "nan", "None", ""]:
        return default
    s = s.replace("R$", "").replace(" ", "")
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except Exception:
        return default

def energia_first_day(v):
    d = as_date(v)
    if not d:
        return None
    return date(d.year, d.month, 1)

def energia_site_nome(site_codigo):
    return ENERGIA_SITE_INFO.get(site_codigo, {}).get("nome", site_codigo or "—")

def energia_site_grupo(site_codigo):
    return ENERGIA_SITE_INFO.get(site_codigo, {}).get("grupo", "LAG")

def energia_map_resource_site(site_value):
    n = energia_norm_txt(site_value)
    for codigo, patterns in ENERGIA_RESOURCE_SITE_PATTERNS.items():
        if any(p in n for p in patterns):
            return codigo
    return None

def energia_map_absorption_site(sheet_name):
    n = energia_norm_txt(sheet_name)
    for label, codigo in ENERGIA_ABSORPTION_SHEETS.items():
        if energia_norm_txt(label) in n or n in energia_norm_txt(label):
            return codigo
    return None

def energia_map_fonte(service_value):
    n = energia_norm_txt(service_value)
    for key, val in ENERGIA_FONTE_MAP.items():
        if energia_norm_txt(key) in n:
            return val
    if "gas" in n:
        return ("Gás natural", "Escopo 1")
    if "power" in n or "electric" in n:
        return ("Energia elétrica", "Escopo 2")
    return ("Outro", "—")

def energia_fiscal_year(mes_ref):
    d = as_date(mes_ref)
    if not d:
        return None
    return d.year + 1 if d.month >= 7 else d.year

def energia_intervalo_fy(fy):
    fy = int(fy)
    if fy < 100:
        fy += 2000
    return date(fy - 1, 7, 1), date(fy, 6, 30)

def energia_fy_label(mes_ref):
    fy = energia_fiscal_year(mes_ref)
    return f"FY{str(fy)[-2:]}" if fy else "—"

def energia_r12_start(mes_ref):
    d = energia_first_day(mes_ref)
    if not d:
        return None
    return (pd.Timestamp(d) - pd.DateOffset(months=11)).date()

def energia_pct_change(atual, base):
    if base is None or pd.isna(base) or abs(float(base)) < 1e-12:
        return None
    if atual is None or pd.isna(atual):
        return None
    return (float(atual) - float(base)) / float(base)

def energia_fmt_val(v, metric_kind="numero"):
    if v is None or pd.isna(v):
        return "—"
    if metric_kind == "percent":
        return f"{v*100:.1f}%".replace(".", ",")
    if metric_kind == "money":
        return f"R$ {v:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if abs(v) >= 1000:
        return f"{v:,.0f}".replace(",", ".")
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def energia_formatar_tabela_visual(df, money_cols=None, percent_cols=None, integer_cols=None, decimal_cols=None):
    """Padroniza casas decimais em tabelas visuais do módulo de energia.

    Mantém exports numéricos intactos em outras funções; esta rotina é usada só para
    exibição em tela, evitando tabelas com muitas casas decimais no dashboard.
    """
    if df is None or df.empty:
        return df
    out = df.copy()
    money_cols = set(money_cols or [])
    percent_cols = set(percent_cols or [])
    integer_cols = set(integer_cols or [])
    decimal_cols = set(decimal_cols or [])
    for col in out.columns:
        if col in money_cols:
            out[col] = out[col].apply(lambda x: energia_fmt_val(x, "money"))
        elif col in percent_cols:
            out[col] = out[col].apply(lambda x: energia_fmt_val(x, "percent"))
        elif col in integer_cols:
            out[col] = pd.to_numeric(out[col], errors="coerce").round(0).astype("Int64").astype(str).replace("<NA>", "—")
        elif col in decimal_cols:
            out[col] = pd.to_numeric(out[col], errors="coerce").map(lambda x: "—" if pd.isna(x) else f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        elif pd.api.types.is_numeric_dtype(out[col]):
            out[col] = pd.to_numeric(out[col], errors="coerce").map(lambda x: "—" if pd.isna(x) else f"{x:,.0f}".replace(",", "."))
    return out

def energia_param(db, chave, default=None):
    p = db.query(EnergiaParametro).filter_by(chave=chave).first()
    if p and p.valor not in [None, ""]:
        return p.valor
    if default is not None:
        return default
    return ENERGIA_DEFAULT_PARAMS.get(chave, ("", ""))[0]

def energia_param_float(db, chave, default=0):
    return energia_safe_float(energia_param(db, chave, default), default)

def energia_set_param(db, chave, valor, descricao=None):
    p = db.query(EnergiaParametro).filter_by(chave=chave).first()
    if not p:
        p = EnergiaParametro(chave=chave, valor=str(valor), descricao=descricao or "")
        db.add(p)
    else:
        p.valor = str(valor)
        if descricao is not None:
            p.descricao = descricao
    db.commit()

def seed_energia_parametros(db):
    """Garante parâmetros iniciais do módulo de energia.

    As emissões não são mais calculadas por fator no app: elas são importadas
    diretamente da planilha EMISSOES. Os fatores permanecem apenas como campos
    legados/referenciais para compatibilidade.
    """
    for chave, (valor, desc) in ENERGIA_DEFAULT_PARAMS.items():
        p = db.query(EnergiaParametro).filter_by(chave=chave).first()
        if not p:
            db.add(EnergiaParametro(chave=chave, valor=valor, descricao=desc))
        else:
            if chave in ["fator_emissao_eletricidade_kgco2_kwh", "fator_emissao_gas_kgco2_kwh"]:
                p.descricao = desc
    db.commit()

def seed_energia_actual_hours_inicial(db):
    """Carrega uma base inicial de Actual Hours já mapeada, sem sobrescrever ajustes manuais futuros."""
    if not ENERGIA_ACTUAL_HOURS_SEED:
        return
    adicionados = 0
    for row in ENERGIA_ACTUAL_HOURS_SEED:
        mes = as_date(row.get("mes_ref"))
        site = row.get("site_codigo")
        if not mes or not site:
            continue
        existente = db.query(EnergiaActualHours).filter(
            EnergiaActualHours.mes_ref == mes,
            EnergiaActualHours.site_codigo == site
        ).first()
        if existente:
            continue
        db.add(EnergiaActualHours(
            mes_ref=mes,
            site_codigo=site,
            site_nome=row.get("site_nome") or energia_site_nome(site),
            grupo=row.get("grupo") or energia_site_grupo(site),
            actual_hours=energia_safe_float(row.get("actual_hours"), 0),
            production_capacity_hours=energia_safe_float(row.get("production_capacity_hours"), 0),
            origem=row.get("origem") or "Carga inicial Absorption FY26",
            atualizado_em=datetime.utcnow(),
        ))
        adicionados += 1
    if adicionados:
        db.add(EnergiaUploadHistorico(
            tipo_base="Actual Hours",
            nome_arquivo="Brazil Absorption Summary FY26.xls",
            usuario="Sistema",
            observacoes=f"Carga inicial bruta de {adicionados} registros de Actual Hours."
        ))
    db.commit()

def seed_energia_registros_inicial(db):
    """Carrega a base inicial de energia/gás/emissões enviada pelo usuário.

    A carga ocorre somente quando EnergiaRegistro ainda está vazio, para não
    sobrescrever atualizações futuras feitas pela tela Atualizar Base.
    """
    if db.query(EnergiaRegistro).count() > 0:
        return
    rows = energia_registros_seed_rows()
    adicionados = 0
    for row in rows:
        mes = as_date(row.get("mes_ref"))
        site = row.get("site_codigo")
        fonte = row.get("fonte")
        if not mes or not site or fonte not in ["Energia elétrica", "Gás natural"]:
            continue
        db.add(EnergiaRegistro(
            mes_ref=mes,
            site_codigo=site,
            site_nome=row.get("site_nome") or energia_site_nome(site),
            grupo=row.get("grupo") or energia_site_grupo(site),
            divisao=row.get("divisao") or "",
            fonte=fonte,
            consumo_original=energia_safe_float(row.get("consumo_original"), 0),
            unidade_original=row.get("unidade_original") or "",
            consumo_kwh=energia_safe_float(row.get("consumo_kwh"), 0),
            custo_brl=energia_safe_float(row.get("custo_brl"), 0),
            unit_cost=energia_safe_float(row.get("unit_cost"), 0),
            emissao_co2_ton=energia_safe_float(row.get("emissao_co2_ton"), 0),
            emissao_escopo=row.get("emissao_escopo") or ("Escopo 2" if fonte == "Energia elétrica" else "Escopo 1"),
            origem_arquivo=row.get("origem_arquivo") or "Carga inicial GAS_ENERGIA + EMISSOES",
        ))
        adicionados += 1
    if adicionados:
        db.add(EnergiaUploadHistorico(
            tipo_base="Energia/Gás/Emissões",
            nome_arquivo="GAS_ENERGIA_CONTROLE_MENSAL + EMISSOES",
            usuario="Sistema",
            observacoes=f"Carga inicial de {adicionados} registros com emissões importadas da planilha EMISSOES."
        ))
    db.commit()

def energia_find_header(raw_df, required_terms):
    for idx in raw_df.index:
        row_norm = [energia_norm_txt(x) for x in raw_df.loc[idx].tolist()]
        joined = " | ".join(row_norm)
        if all(term in joined for term in required_terms):
            return int(idx)
    return None

def energia_read_excel_any(uploaded_or_bytes, filename="arquivo.xlsx", sheet_name=0, header=None, nrows=None):
    data = uploaded_or_bytes.getvalue() if hasattr(uploaded_or_bytes, "getvalue") else uploaded_or_bytes
    try:
        return pd.read_excel(io.BytesIO(data), sheet_name=sheet_name, header=header, nrows=nrows)
    except ImportError as e:
        if str(filename).lower().endswith(".xls"):
            raise RuntimeError("Não foi possível ler .xls porque a dependência xlrd não está disponível. Converta o arquivo para .xlsx e tente novamente.") from e
        raise
    except Exception as e:
        raise RuntimeError(f"Não foi possível ler o arquivo Excel: {e}") from e


def energia_parse_emissoes_resource(uploaded_file, filename="emissoes.xlsx"):
    """Lê a planilha EMISSOES do Resource Advisor.

    Retorna dicionários por (mês, site):
    - total: Source == Total Emissions, coluna Value
    - gas: Source == Natural Gas, coluna Total CO2e Emissions (Primary)
    A emissão elétrica é derivada como Total Emissions - Natural Gas.
    """
    data = uploaded_file.getvalue() if hasattr(uploaded_file, "getvalue") else uploaded_file
    try:
        xls = pd.ExcelFile(io.BytesIO(data))
    except ImportError as e:
        if str(filename).lower().endswith(".xls"):
            raise RuntimeError("Não foi possível ler .xls porque a dependência xlrd não está disponível. Converta para .xlsx e tente novamente.") from e
        raise
    total_emissoes = {}
    gas_emissoes = {}
    for sheet in xls.sheet_names:
        raw = pd.read_excel(io.BytesIO(data), sheet_name=sheet, header=None, nrows=80)
        header_idx = energia_find_header(raw, ["month", "source", "site name"])
        if header_idx is None:
            header_idx = energia_find_header(raw, ["month", "source", "site"])
        if header_idx is None:
            continue
        df = pd.read_excel(io.BytesIO(data), sheet_name=sheet, header=header_idx)
        df.columns = [str(c).strip() for c in df.columns]
        colmap = {energia_norm_txt(c): c for c in df.columns}
        col_month = colmap.get("month")
        col_site = colmap.get("site name") or colmap.get("site")
        col_source = colmap.get("source")
        col_value = colmap.get("value")
        col_primary = colmap.get("total co2e emissions (primary) (mtons co2-e)")
        col_secondary = colmap.get("total co2e emissions (secondary) (mtons co2-e)")
        if not all([col_month, col_site, col_source]):
            continue
        for _, r in df.iterrows():
            mes = energia_first_day(r.get(col_month))
            site_codigo = energia_map_resource_site(r.get(col_site))
            source = energia_norm_txt(r.get(col_source))
            if not mes or not site_codigo:
                continue
            key = (mes, site_codigo)
            if source == "total emissions" and col_value:
                val = energia_safe_float(r.get(col_value), None)
                if val is not None:
                    total_emissoes[key] = float(val)
            elif source == "natural gas":
                val = energia_safe_float(r.get(col_primary), None) if col_primary else None
                if val is None and col_secondary:
                    val = energia_safe_float(r.get(col_secondary), None)
                if val is not None:
                    gas_emissoes[key] = float(val)
    return {"total": total_emissoes, "gas": gas_emissoes}

def energia_parse_base_resource(uploaded_file, db=None, filename="base_energia.xlsx", emissoes_file=None, emissoes_filename="emissoes.xlsx"):
    """Lê a base de energia/gás e, opcionalmente, combina com a planilha EMISSOES.

    Regra atual do app: emissões são importadas da planilha EMISSOES, não calculadas
    por fator dentro da aplicação. Quando a planilha de emissões é enviada:
    - Gás natural recebe a emissão Natural Gas (Scope 1);
    - Energia elétrica recebe Total Emissions - Natural Gas (Scope 2);
    - Total Emissions vem da própria planilha EMISSOES para o mesmo mês/site.
    """
    data = uploaded_file.getvalue() if hasattr(uploaded_file, "getvalue") else uploaded_file
    try:
        xls = pd.ExcelFile(io.BytesIO(data))
    except ImportError as e:
        if str(filename).lower().endswith(".xls"):
            raise RuntimeError("Não foi possível ler .xls porque a dependência xlrd não está disponível. Converta para .xlsx e tente novamente.") from e
        raise
    emiss = {"total": {}, "gas": {}}
    if emissoes_file is not None:
        emiss = energia_parse_emissoes_resource(emissoes_file, emissoes_filename)
    conv = energia_param_float(db, "conversao_mmbtu_kwh", 293.071) if db is not None else 293.071
    rows = []
    for sheet in xls.sheet_names:
        raw = pd.read_excel(io.BytesIO(data), sheet_name=sheet, header=None, nrows=80)
        header_idx = energia_find_header(raw, ["service month", "site"])
        if header_idx is None:
            continue
        df = pd.read_excel(io.BytesIO(data), sheet_name=sheet, header=header_idx)
        df.columns = [str(c).strip() for c in df.columns]
        colmap = {energia_norm_txt(c): c for c in df.columns}
        col_month = colmap.get("service month")
        col_site = colmap.get("site") or colmap.get("site name")
        col_service = colmap.get("services") or colmap.get("service")
        col_uom = colmap.get("usage uom") or colmap.get("uom")
        col_usage = colmap.get("total usage") or colmap.get("total billed usage")
        col_cost = colmap.get("total cost (brl)") or colmap.get("total cost")
        col_unit = colmap.get("unit cost")
        col_div = colmap.get("division")
        if not all([col_month, col_site, col_service, col_usage]):
            continue
        for _, r in df.iterrows():
            mes = energia_first_day(r.get(col_month))
            site_codigo = energia_map_resource_site(r.get(col_site))
            fonte, escopo = energia_map_fonte(r.get(col_service))
            if not mes or not site_codigo or fonte not in ["Energia elétrica", "Gás natural"]:
                continue
            consumo_original = energia_safe_float(r.get(col_usage), 0)
            uom = str(r.get(col_uom) or "").strip()
            consumo_kwh = consumo_original
            if fonte == "Gás natural" and energia_norm_txt(uom) in ["mmbtu", "mm btu", "mmbtus"]:
                consumo_kwh = consumo_original * conv
            elif energia_norm_txt(uom) in ["mwh"]:
                consumo_kwh = consumo_original * 1000
            custo = energia_safe_float(r.get(col_cost), 0) if col_cost else 0
            unit_cost = energia_safe_float(r.get(col_unit), 0) if col_unit else 0
            key = (mes, site_codigo)
            emissao_gas = energia_safe_float(emiss.get("gas", {}).get(key), 0)
            emissao_total = emiss.get("total", {}).get(key)
            if fonte == "Gás natural":
                emissao = emissao_gas
            else:
                emissao = max(energia_safe_float(emissao_total, 0) - emissao_gas, 0)
            rows.append({
                "mes_ref": mes,
                "site_codigo": site_codigo,
                "site_nome": energia_site_nome(site_codigo),
                "grupo": energia_site_grupo(site_codigo),
                "divisao": str(r.get(col_div) or ""),
                "fonte": fonte,
                "consumo_original": consumo_original,
                "unidade_original": uom,
                "consumo_kwh": consumo_kwh,
                "custo_brl": custo,
                "unit_cost": unit_cost,
                "emissao_co2_ton": emissao,
                "emissao_escopo": escopo,
                "origem_arquivo": f"{filename} + {emissoes_filename}" if emissoes_file is not None else filename,
            })
    return pd.DataFrame(rows)

def energia_parse_absorption(uploaded_file, filename="absorption.xlsx"):
    data = uploaded_file.getvalue() if hasattr(uploaded_file, "getvalue") else uploaded_file
    try:
        xls = pd.ExcelFile(io.BytesIO(data))
    except ImportError as e:
        if str(filename).lower().endswith(".xls"):
            raise RuntimeError("Não foi possível ler .xls porque a dependência xlrd não está disponível. Converta o arquivo para .xlsx e tente novamente.") from e
        raise
    rows = []
    for sheet in xls.sheet_names:
        site_codigo = energia_map_absorption_site(sheet)
        if not site_codigo:
            continue
        raw = pd.read_excel(io.BytesIO(data), sheet_name=sheet, header=None)
        header_idx = None
        actual_col = None
        capacity_col = None
        for idx in raw.index[:25]:
            vals = [energia_norm_txt(x) for x in raw.loc[idx].tolist()]
            if "actual hours" in vals:
                header_idx = idx
                actual_col = vals.index("actual hours")
                if "production capacity (hours)" in vals:
                    capacity_col = vals.index("production capacity (hours)")
                break
        if header_idx is None:
            continue
        for ridx in raw.index:
            if ridx <= header_idx:
                continue
            mes = energia_first_day(raw.iat[ridx, 0] if raw.shape[1] > 0 else None)
            if not mes:
                continue
            actual = energia_safe_float(raw.iat[ridx, actual_col], None)
            if actual is None:
                continue
            capacity = energia_safe_float(raw.iat[ridx, capacity_col], 0) if capacity_col is not None else 0
            rows.append({
                "mes_ref": mes,
                "site_codigo": site_codigo,
                "site_nome": energia_site_nome(site_codigo),
                "grupo": energia_site_grupo(site_codigo),
                "actual_hours": actual,
                "production_capacity_hours": capacity,
                "origem": "Importado Absorption",
            })
    return pd.DataFrame(rows)


@st.cache_data(show_spinner=False, ttl=300)
def energia_df_registros(_db):
    regs = _db.query(EnergiaRegistro).order_by(EnergiaRegistro.mes_ref, EnergiaRegistro.site_codigo, EnergiaRegistro.fonte).all()
    rows = []
    for r in regs:
        rows.append({
            "ID": r.id,
            "Mês": r.mes_ref,
            "FY": energia_fy_label(r.mes_ref),
            "Site": r.site_codigo,
            "Site nome": r.site_nome,
            "Grupo": r.grupo,
            "Divisão": r.divisao,
            "Fonte": r.fonte,
            "Consumo original": r.consumo_original,
            "Unidade original": r.unidade_original,
            "Consumo kWh": r.consumo_kwh,
            "Custo BRL": r.custo_brl,
            "Unit cost": r.unit_cost,
            "Emissão tCO₂e": energia_safe_float(r.emissao_co2_ton, 0),
            "Escopo": r.emissao_escopo,
            "Origem": r.origem_arquivo,
        })
    return pd.DataFrame(rows)

@st.cache_data(show_spinner=False, ttl=300)
def energia_df_actual_hours(_db):
    hrs = _db.query(EnergiaActualHours).order_by(EnergiaActualHours.mes_ref, EnergiaActualHours.site_codigo).all()
    return pd.DataFrame([{
        "ID": h.id,
        "Mês": h.mes_ref,
        "FY": energia_fy_label(h.mes_ref),
        "Site": h.site_codigo,
        "Site nome": h.site_nome,
        "Grupo": h.grupo,
        "Actual Hours": h.actual_hours,
        "Production capacity (hours)": h.production_capacity_hours,
        "Origem": h.origem,
    } for h in hrs])

@st.cache_data(show_spinner=False, ttl=300)
def energia_consolidado(_db):
    regs = energia_df_registros(_db)
    hrs = energia_df_actual_hours(_db)
    sites = pd.DataFrame([{"Site": k, "Site nome": v["nome"], "Grupo": v["grupo"]} for k, v in ENERGIA_SITE_INFO.items()])
    if regs.empty and hrs.empty:
        return pd.DataFrame()
    if regs.empty:
        base = hrs[["Mês", "Site", "Site nome", "Grupo"]].drop_duplicates()
    else:
        base = regs[["Mês", "Site", "Site nome", "Grupo"]].drop_duplicates()
    if not hrs.empty:
        base = pd.concat([base, hrs[["Mês", "Site", "Site nome", "Grupo"]].drop_duplicates()], ignore_index=True).drop_duplicates()
    pivot_consumo = pd.DataFrame()
    pivot_custo = pd.DataFrame()
    pivot_emissao = pd.DataFrame()
    gas_original = pd.DataFrame()
    if not regs.empty:
        pivot_consumo = regs.pivot_table(index=["Mês", "Site"], columns="Fonte", values="Consumo kWh", aggfunc="sum", fill_value=0).reset_index()
        pivot_custo = regs.pivot_table(index=["Mês", "Site"], columns="Fonte", values="Custo BRL", aggfunc="sum", fill_value=0).reset_index()
        pivot_emissao = regs.pivot_table(index=["Mês", "Site"], columns="Escopo", values="Emissão tCO₂e", aggfunc="sum", fill_value=0).reset_index()
        gas = regs[regs["Fonte"] == "Gás natural"].groupby(["Mês", "Site"], as_index=False).agg({
            "Consumo original": "sum",
            "Unidade original": lambda x: ", ".join(sorted(set([str(v) for v in x if str(v) != "nan"]))) if len(x) else "",
        })
        gas_original = gas.rename(columns={"Consumo original": "consumo_gas_original", "Unidade original": "consumo_gas_unidade_original"})
    df = base.copy()
    if not pivot_consumo.empty:
        df = df.merge(pivot_consumo, on=["Mês", "Site"], how="left")
    if not pivot_custo.empty:
        pivot_custo = pivot_custo.rename(columns={"Energia elétrica": "custo_eletrico_brl", "Gás natural": "custo_gas_brl"})
        df = df.merge(pivot_custo[["Mês", "Site"] + [c for c in ["custo_eletrico_brl","custo_gas_brl"] if c in pivot_custo.columns]], on=["Mês", "Site"], how="left")
    if not pivot_emissao.empty:
        pivot_emissao = pivot_emissao.rename(columns={"Escopo 1": "emissao_escopo1_tco2e", "Escopo 2": "emissao_escopo2_tco2e"})
        df = df.merge(pivot_emissao[["Mês", "Site"] + [c for c in ["emissao_escopo1_tco2e","emissao_escopo2_tco2e"] if c in pivot_emissao.columns]], on=["Mês", "Site"], how="left")
    if not gas_original.empty:
        df = df.merge(gas_original, on=["Mês", "Site"], how="left")
    if not hrs.empty:
        h = hrs[["Mês", "Site", "Actual Hours", "Production capacity (hours)"]].copy()
        df = df.merge(h, on=["Mês", "Site"], how="left")
    for col in ["Energia elétrica", "Gás natural", "custo_eletrico_brl", "custo_gas_brl", "emissao_escopo1_tco2e", "emissao_escopo2_tco2e", "consumo_gas_original", "Actual Hours", "Production capacity (hours)"]:
        if col not in df.columns:
            df[col] = 0
    df["Mês"] = pd.to_datetime(df["Mês"]).dt.date
    df["fiscal_year"] = df["Mês"].apply(lambda d: f"FY{str(energia_fiscal_year(d))[-2:]}")
    df["consumo_eletrico_kwh"] = df["Energia elétrica"].fillna(0)
    df["consumo_gas_kwh"] = df["Gás natural"].fillna(0)
    df["consumo_total_kwh"] = df["consumo_eletrico_kwh"] + df["consumo_gas_kwh"]
    df["custo_total_brl"] = df["custo_eletrico_brl"].fillna(0) + df["custo_gas_brl"].fillna(0)
    df["emissao_total_tco2e"] = df["emissao_escopo1_tco2e"].fillna(0) + df["emissao_escopo2_tco2e"].fillna(0)
    irec_inicio = energia_first_day(energia_param(_db, "irec_data_inicio", "2023-01-01")) or date(2023, 1, 1)
    df["emissao_total_com_irec_tco2e"] = df.apply(
        lambda r: r["emissao_escopo1_tco2e"] if as_date(r["Mês"]) >= irec_inicio else r["emissao_total_tco2e"],
        axis=1,
    )
    df["actual_hours"] = df["Actual Hours"].fillna(0)
    df["production_capacity_hours"] = df["Production capacity (hours)"].fillna(0)
    df["eficiencia_energetica"] = df.apply(lambda r: (r["consumo_total_kwh"] / r["actual_hours"]) if r["actual_hours"] else None, axis=1)
    df = df.sort_values(["Site", "Mês"]).reset_index(drop=True)

    r12_cols = ["consumo_eletrico_kwh", "consumo_gas_kwh", "consumo_total_kwh", "emissao_total_tco2e", "emissao_total_com_irec_tco2e", "custo_total_brl", "actual_hours"]
    for col in r12_cols:
        df[f"{col}_r12"] = df.groupby("Site")[col].transform(lambda s: s.rolling(window=12, min_periods=1).sum())
    df["eficiencia_energetica_r12"] = df.apply(lambda r: (r["consumo_total_kwh_r12"] / r["actual_hours_r12"]) if r["actual_hours_r12"] else None, axis=1)
    out_cols = [
        "Mês", "fiscal_year", "Site", "Site nome", "Grupo",
        "consumo_eletrico_kwh", "consumo_gas_original", "consumo_gas_unidade_original", "consumo_gas_kwh", "consumo_total_kwh",
        "custo_eletrico_brl", "custo_gas_brl", "custo_total_brl",
        "emissao_escopo1_tco2e", "emissao_escopo2_tco2e", "emissao_total_tco2e", "emissao_total_com_irec_tco2e",
        "actual_hours", "production_capacity_hours", "eficiencia_energetica",
        "consumo_eletrico_kwh_r12", "consumo_gas_kwh_r12", "consumo_total_kwh_r12",
        "emissao_total_tco2e_r12", "emissao_total_com_irec_tco2e_r12", "custo_total_brl_r12",
        "actual_hours_r12", "eficiencia_energetica_r12"
    ]
    for col in out_cols:
        if col not in df.columns:
            df[col] = None
    return df[out_cols].copy()

def energia_filtrar(df, sites=None, grupos=None, data_ini=None, data_fim=None, fy=None):
    if df is None or df.empty:
        return pd.DataFrame()
    f = df.copy()
    if sites:
        f = f[f["Site"].isin(sites)]
    if grupos:
        grupos_validos = [g for g in grupos if g != "LAG"]
        if grupos_validos:
            f = f[f["Grupo"].isin(grupos_validos)]
    if fy and fy != "Custom":
        f = f[f["fiscal_year"] == fy]
    if data_ini:
        f = f[pd.to_datetime(f["Mês"]) >= pd.to_datetime(data_ini)]
    if data_fim:
        f = f[pd.to_datetime(f["Mês"]) <= pd.to_datetime(data_fim)]
    return f

def energia_metric_series(df, metric, usar_irec=False):
    if df.empty:
        return pd.Series(dtype=float)
    if metric == "Consumo de energia elétrica":
        return df["consumo_eletrico_kwh"]
    if metric == "Consumo de gás natural":
        return df["consumo_gas_kwh"]
    if metric == "Consumo total de energia":
        return df["consumo_total_kwh"]
    if metric == "Emissões de CO₂ considerando I-REC":
        return df["emissao_total_com_irec_tco2e"]
    if metric == "Emissões de CO₂":
        return df["emissao_total_com_irec_tco2e"] if usar_irec else df["emissao_total_tco2e"]
    if metric == "Custo":
        return df["custo_total_brl"]
    if metric == "Eficiência energética":
        return df["eficiencia_energetica"]
    return df["consumo_total_kwh"]

def energia_agregar_periodo(df, sites, metric, start=None, end=None, usar_irec=False):
    if df.empty:
        return 0
    f = df[df["Site"].isin(sites)].copy()
    if start:
        f = f[pd.to_datetime(f["Mês"]) >= pd.to_datetime(start)]
    if end:
        f = f[pd.to_datetime(f["Mês"]) <= pd.to_datetime(end)]
    if f.empty:
        return 0
    if metric == "Eficiência energética":
        energia = f["consumo_total_kwh"].sum()
        horas = f["actual_hours"].sum()
        return energia / horas if horas else None
    return energia_metric_series(f, metric, usar_irec=usar_irec).sum()

@st.cache_data(show_spinner=False, ttl=300)
def energia_executive_table(_db, metric, r12_mes, usar_irec=False):
    df = energia_consolidado(_db)
    if df.empty:
        return pd.DataFrame()
    r12_mes = energia_first_day(r12_mes) or df["Mês"].max()
    r12_ini = energia_r12_start(r12_mes)
    fy19 = energia_intervalo_fy(2019)
    fy24 = energia_intervalo_fy(2024)
    fy25 = energia_intervalo_fy(2025)
    rows = []
    for label, sites, is_group in ENERGIA_LINHAS_EXECUTIVAS:
        v19 = energia_agregar_periodo(df, sites, metric, fy19[0], fy19[1], usar_irec)
        v24 = energia_agregar_periodo(df, sites, metric, fy24[0], fy24[1], usar_irec)
        v25 = energia_agregar_periodo(df, sites, metric, fy25[0], fy25[1], usar_irec)
        vr12 = energia_agregar_periodo(df, sites, metric, r12_ini, r12_mes, usar_irec)
        eff_r12 = energia_agregar_periodo(df, sites, "Eficiência energética", r12_ini, r12_mes, usar_irec)
        eff_25 = energia_agregar_periodo(df, sites, "Eficiência energética", fy25[0], fy25[1], usar_irec)
        rows.append({
            "Divisão": label,
            "FY19": v19,
            "FY24": v24,
            "FY25": v25,
            f"R12 YTD {r12_mes.strftime('%b/%y')}": vr12,
            "R12 vs FY25": energia_pct_change(vr12, v25),
            "R12 vs FY19": energia_pct_change(vr12, v19),
            f"Taxa de eficiência energética R12 {r12_mes.strftime('%b/%y')} vs FY25": energia_pct_change(eff_r12, eff_25),
            "_grupo": is_group,
        })
    return pd.DataFrame(rows)

def energia_table_html(df, metric):
    if df.empty:
        return "<div class='empty'>Sem dados para gerar a tabela executiva.</div>"
    title = "Considerando os Certificados de Energia Renovável (I-REC)"
    value_cols = [c for c in df.columns if c not in ["Divisão", "_grupo"]]
    pct_cols = [c for c in value_cols if "vs" in c]
    num_kind = "money" if metric == "Custo" else "numero"
    html = """
    <style>
    .tbl-energy{border-collapse:collapse;width:100%;font-family:Arial, sans-serif;border:2px solid #111827;}
    .tbl-energy th,.tbl-energy td{border:1px solid #111827;padding:8px;text-align:center;font-weight:800;}
    .tbl-energy .title{background:#1f3b68;color:#fff;font-size:20px;text-align:center;}
    .tbl-energy .head{background:#bfbfbf;color:#000;}
    .tbl-energy .grp td{background:#ffc000!important;}
    .tbl-energy .base td{background:#fff2cc;}
    .tbl-energy .good{background:#00b050!important;color:#000;}
    .tbl-energy .mid{background:#ffd966!important;color:#000;}
    .tbl-energy .bad{background:#ff0000!important;color:#000;}
    </style>
    """
    html += f"<table class='tbl-energy'><tr><th class='title' colspan='{len(value_cols)+1}'>{title}</th></tr>"
    html += "<tr><th class='head'>Divisão</th>" + "".join(f"<th class='head'>{html_escape(c)}</th>" for c in value_cols) + "</tr>"
    for _, r in df.iterrows():
        tr_class = "grp" if bool(r.get("_grupo")) else "base"
        html += f"<tr class='{tr_class}'><td>{html_escape(r['Divisão'])}</td>"
        for c in value_cols:
            val = r[c]
            cls = ""
            if c in pct_cols:
                if val is None or pd.isna(val):
                    txt = "—"
                else:
                    txt = energia_fmt_val(val, "percent")
                    meta = 0.05
                    if val <= -meta:
                        cls = "good"
                    elif val < 0:
                        cls = "mid"
                    else:
                        cls = "bad"
            else:
                txt = energia_fmt_val(val, num_kind)
            html += f"<td class='{cls}'>{txt}</td>"
        html += "</tr>"
    html += "</table>"
    return html

def energia_df_kpis(df, r12_mes, usar_irec=False):
    if df.empty:
        return pd.DataFrame()
    r12_mes = energia_first_day(r12_mes) or df["Mês"].max()
    r12_ini = energia_r12_start(r12_mes)
    f = df[(pd.to_datetime(df["Mês"]) >= pd.to_datetime(r12_ini)) & (pd.to_datetime(df["Mês"]) <= pd.to_datetime(r12_mes))]
    if f.empty:
        return pd.DataFrame()
    consumo_eletrico = f["consumo_eletrico_kwh"].sum()
    consumo_gas = f["consumo_gas_kwh"].sum()
    consumo_total = f["consumo_total_kwh"].sum()
    emissao1 = f["emissao_escopo1_tco2e"].sum()
    emissao2 = f["emissao_escopo2_tco2e"].sum()
    emissao_total = emissao1 + emissao2
    emissao_irec = f["emissao_total_com_irec_tco2e"].sum() if "emissao_total_com_irec_tco2e" in f.columns else emissao1
    custo = f["custo_total_brl"].sum()
    horas = f["actual_hours"].sum()
    eficiencia = consumo_total / horas if horas else None
    custo_medio = custo / consumo_total if consumo_total else None
    rows = [
        ("Consumo elétrico R12 kWh", consumo_eletrico),
        ("Consumo de gás R12 kWh", consumo_gas),
        ("Consumo total R12 kWh", consumo_total),
        ("Emissões Escopo 1 R12 tCO₂e", emissao1),
        ("Emissões Escopo 2 R12 tCO₂e", emissao2),
        ("Emissões CO₂ R12 tCO₂e", emissao_irec if usar_irec else emissao_total),
        ("Emissões CO₂ R12 com I-REC tCO₂e", emissao_irec),
        ("Custo total R12 BRL", custo),
        ("Custo médio BRL/kWh", custo_medio),
        ("Actual Hours R12", horas),
        ("Eficiência energética R12", eficiencia),
    ]
    return pd.DataFrame(rows, columns=["Indicador", "Valor"])


def energia_dash_filters(df, prefix="energia"):
    if df.empty:
        return df, None, False
    section("Filtros")
    min_date = min(df["Mês"])
    max_date = max(df["Mês"])
    fy_data = sorted(df["fiscal_year"].dropna().unique().tolist(), key=lambda x: int(str(x).replace("FY","")) if str(x).replace("FY","").isdigit() else 999)
    fy_opts = ["Todos"] + fy_data + ["Custom"]
    c1,c2,c3,c4 = st.columns(4)
    default_fy = ["FY26"] if "FY26" in fy_data else (["Todos"] if fy_data else [])
    fys = c1.multiselect("Fiscal Year", fy_opts, default=default_fy, key=f"{prefix}_fy")
    data_ini = c2.date_input("Período inicial", min_date, key=f"{prefix}_ini")
    data_fim = c3.date_input("Período final", max_date, key=f"{prefix}_fim")
    r12_opts = sorted(df["Mês"].unique())
    default_r12 = energia_default_r12_mes(df) or max_date
    r12_idx = r12_opts.index(default_r12) if default_r12 in r12_opts else len(r12_opts)-1
    r12_mes = c4.selectbox("Mês de referência R12", r12_opts, index=r12_idx, format_func=lambda d: d.strftime("%b/%Y"), key=f"{prefix}_r12")
    c5,c6,c7,c8 = st.columns(4)
    sites = c5.multiselect("Site", ENERGIA_SITE_ORDER, default=[], key=f"{prefix}_sites")
    grupos = c6.multiselect("Grupo", ENERGIA_GROUP_ORDER, default=[], key=f"{prefix}_grupos")
    visao = c7.selectbox("Visão", ["Site", "Grupo", "LAG"], key=f"{prefix}_visao")
    usar_irec = c8.toggle("Considerar I-REC", value=True, key=f"{prefix}_irec")
    f = df.copy()
    selected_fys = [fy for fy in (fys or []) if fy not in ["Todos", "Custom"]]
    if selected_fys and "Todos" not in (fys or []):
        f = f[f["fiscal_year"].isin(selected_fys)]
    if data_ini:
        f = f[pd.to_datetime(f["Mês"]) >= pd.to_datetime(data_ini)]
    if data_fim:
        f = f[pd.to_datetime(f["Mês"]) <= pd.to_datetime(data_fim)]
    if sites:
        f = f[f["Site"].isin(sites)]
    if grupos and "LAG" not in grupos:
        f = f[f["Grupo"].isin(grupos)]
    return f, r12_mes, usar_irec


def energia_submodulos_home(db,u):
    header("Controle de Energia e Emissões", "Escolha um submódulo para analisar, atualizar bases, consolidar dados, exportar relatórios ou configurar parâmetros.")
    top_back_col, top_spacer_col = st.columns([1.1, 5])
    with top_back_col:
        if st.button("⬅️ Voltar para página inicial", key="energia_home_voltar_inicio", use_container_width=True):
            st.session_state.modulo = "home"
            st.rerun()
    section("Submódulos")
    nomes = list(ENERGIA_SUBMODULOS.keys())
    for base in range(0, len(nomes), 2):
        cols = st.columns(2)
        for col, nome in zip(cols, nomes[base:base+2]):
            cfg = ENERGIA_SUBMODULOS[nome]
            with col:
                submodule_card(nome, cfg["descricao"], cfg["icone"], cfg["cor"])
                if st.button(f"Acessar {nome}", key=f"btn_submodulo_energia_{nome}", use_container_width=True):
                    destino = cfg["paginas"][0] if cfg["paginas"] else ENERGIA_HOME_PAGE
                    st.session_state.submodulo_energia = nome
                    st.session_state.page_energia = destino
                    st.session_state.nav_energia = destino
                    st.rerun()
    section("Resumo rápido")
    try:
        df = energia_consolidado(db)
        c1, c2, c3, c4 = st.columns(4)
        if df.empty:
            c1.metric("Meses consolidados", 0)
            c2.metric("Sites com dados", 0)
            c3.metric("CO₂ R12", "—")
            c4.metric("Eficiência R12", "—")
        else:
            r12_mes = energia_default_r12_mes(df) or max(df["Mês"])
            kpis = energia_df_kpis(df, r12_mes, True)
            vals = dict(zip(kpis["Indicador"], kpis["Valor"])) if not kpis.empty else {}
            c1.metric("Meses consolidados", df["Mês"].nunique())
            c2.metric("Sites com dados", df["Site"].nunique())
            c3.metric("CO₂ R12 com I-REC", energia_fmt_val(vals.get("Emissões CO₂ R12 com I-REC tCO₂e"), "numero"))
            c4.metric("Eficiência R12", energia_fmt_val(vals.get("Eficiência energética R12"), "numero"))
    except Exception:
        empty_state("Resumo de energia indisponível no momento.")


def energia_dashboard(db,u):
    header("Controle de Energia e Emissões", "Consumo elétrico, gás natural, CO₂, custos, Actual Hours, R12, FY e I-REC")
    df = energia_consolidado(db)
    if df.empty:
        empty_state("Nenhuma base de energia carregada. Acesse 'Atualizar Base' para importar os arquivos GAS_ENERGIA_CONTROLE_MENSAL e EMISSOES.")
        return
    f, r12_mes, usar_irec = energia_dash_filters(df, "energia_dash")
    if f.empty:
        empty_state("Sem dados para os filtros selecionados.")
        return
    kpis = energia_df_kpis(f, r12_mes, usar_irec)
    vals = {r["Indicador"]: r["Valor"] for _, r in kpis.iterrows()}
    cards = [
        ("Consumo elétrico R12", energia_fmt_val(vals.get("Consumo elétrico R12 kWh"), "numero"), "kWh"),
        ("Consumo de gás R12", energia_fmt_val(vals.get("Consumo de gás R12 kWh"), "numero"), "kWh"),
        ("Consumo total R12", energia_fmt_val(vals.get("Consumo total R12 kWh"), "numero"), "kWh"),
        ("CO₂ R12", energia_fmt_val(vals.get("Emissões CO₂ R12 tCO₂e"), "numero"), "tCO₂e"),
        ("CO₂ R12 com I-REC", energia_fmt_val(vals.get("Emissões CO₂ R12 com I-REC tCO₂e"), "numero"), "tCO₂e"),
        ("Custo total R12", energia_fmt_val(vals.get("Custo total R12 BRL"), "money"), ""),
        ("Actual Hours R12", energia_fmt_val(vals.get("Actual Hours R12"), "numero"), "h"),
        ("Eficiência energética R12", energia_fmt_val(vals.get("Eficiência energética R12"), "numero"), "kWh/h"),
    ]
    for i in range(0, len(cards), 4):
        cols = st.columns(4)
        for c, (lab, val, help_) in zip(cols, cards[i:i+4]):
            with c:
                kpi_card(lab, val, help_)

    mensal_site = f.groupby(["Mês", "Site"], as_index=False).agg({
        "consumo_eletrico_kwh": "sum", "consumo_gas_kwh": "sum", "emissao_total_tco2e": "sum", "emissao_total_com_irec_tco2e": "sum", "custo_total_brl": "sum", "consumo_total_kwh": "sum", "actual_hours": "sum"
    })
    mensal_site["eficiencia_energetica"] = mensal_site.apply(lambda r: r["consumo_total_kwh"]/r["actual_hours"] if r["actual_hours"] else None, axis=1)
    ref_ini = energia_r12_start(r12_mes)
    r12 = f[(pd.to_datetime(f["Mês"]) >= pd.to_datetime(ref_ini)) & (pd.to_datetime(f["Mês"]) <= pd.to_datetime(r12_mes))]
    r12_site = r12.groupby("Site", as_index=False).agg({
        "consumo_eletrico_kwh":"sum", "consumo_gas_kwh":"sum", "consumo_total_kwh":"sum",
        "emissao_total_tco2e":"sum", "emissao_total_com_irec_tco2e":"sum",
        "custo_total_brl":"sum", "actual_hours":"sum"
    }) if not r12.empty else pd.DataFrame()
    if not r12_site.empty:
        r12_site["eficiencia_energetica"] = r12_site.apply(lambda r: r["consumo_total_kwh"]/r["actual_hours"] if r["actual_hours"] else None, axis=1)
    local_df = energia_localidades_df(r12_site)

    section("Ranking por localidade")
    metrica_localidade = st.selectbox(
        "Métrica do ranking",
        list(ENERGIA_MAP_METRICAS.keys()),
        index=list(ENERGIA_MAP_METRICAS.keys()).index("Emissões CO₂ R12 com I-REC") if usar_irec else list(ENERGIA_MAP_METRICAS.keys()).index("Emissões CO₂ R12"),
        key="energia_mapa_metrica",
    )

    base_scope = df.copy()
    sites_sel = st.session_state.get("energia_dash_sites", [])
    grupos_sel = st.session_state.get("energia_dash_grupos", [])
    if sites_sel:
        base_scope = base_scope[base_scope["Site"].isin(sites_sel)]
    if grupos_sel and "LAG" not in grupos_sel:
        base_scope = base_scope[base_scope["Grupo"].isin(grupos_sel)]
    fy_ref = energia_fiscal_year(r12_mes) or int(energia_param_float(db, "fy_atual", 26)) + 2000
    fy_anterior = int(str(fy_ref)[-2:]) - 1
    base_ini, base_fim = energia_intervalo_fy(fy_anterior)
    comparativo_df = energia_localidades_df(energia_agregar_site_periodo(base_scope, base_ini, base_fim))

    fig_ranking_local = energia_ranking_localidades_fig(
        local_df,
        metrica_localidade,
        comparativo_df,
        usar_irec,
        titulo=f"Ranking por localidade — {metrica_localidade}",
        height=430,
    )
    if fig_ranking_local is not None:
        plotly_chart_safe(fig_ranking_local, use_container_width=True, config={"displayModeBar": False})
    else:
        empty_state("Sem dados suficientes para o ranking por localidade.")

    if not local_df.empty:
        map_col, map_unit = ENERGIA_MAP_METRICAS.get(st.session_state.get("energia_mapa_metrica", "Consumo total R12"), ("consumo_total_kwh", "kWh"))
        ranking_local = local_df.sort_values(map_col, ascending=(map_col == "eficiencia_energetica")).copy()
        destaque_maior = ranking_local.iloc[0] if map_col == "eficiencia_energetica" else ranking_local.sort_values(map_col, ascending=False).iloc[0]
        destaque_menor = ranking_local.iloc[0] if map_col != "eficiencia_energetica" else ranking_local.sort_values(map_col, ascending=False).iloc[0]
        r1, r2 = st.columns(2)
        with r1:
            kpi_card("Maior valor", destaque_maior["Cidade/UF"], f"{energia_fmt_val(destaque_maior[map_col], 'money' if map_unit == 'BRL' else 'numero')} {map_unit}")
        with r2:
            kpi_card("Menor valor", destaque_menor["Cidade/UF"], f"{energia_fmt_val(destaque_menor[map_col], 'money' if map_unit == 'BRL' else 'numero')} {map_unit}")
        ranking_cols = ["Unidade", "Cidade/UF", map_col]
        ranking_show = ranking_local[ranking_cols].rename(columns={map_col: st.session_state.get("energia_mapa_metrica", "Métrica")}).head(6)
        metrica_nome = st.session_state.get("energia_mapa_metrica", "Métrica")
        ranking_show = energia_formatar_tabela_visual(
            ranking_show,
            money_cols=[metrica_nome] if map_unit == "BRL" else [],
            integer_cols=[metrica_nome] if map_unit in ["kWh", "tCO₂e"] else [],
            decimal_cols=[metrica_nome] if map_unit not in ["BRL", "kWh", "tCO₂e"] else [],
        )
        st.dataframe(ranking_show, use_container_width=True, hide_index=True)
    else:
        empty_state("Sem dados para ranking por localidade.")

    aba_dash = st.radio(
        "Seção do dashboard",
        ["Tendências mensais", "Ranking R12", "Metas", "Exportação"],
        horizontal=True,
        key="energia_dash_secao",
    )
    if aba_dash == "Tendências mensais":
        c1, c2 = st.columns(2)
        with c1:
            plotly_chart_safe(px.line(mensal_site, x="Mês", y="consumo_eletrico_kwh", color="Site", markers=True, title="Consumo elétrico mensal por site").update_layout(template="plotly_white", yaxis_title="kWh"), use_container_width=True)
        with c2:
            plotly_chart_safe(px.line(mensal_site, x="Mês", y="consumo_gas_kwh", color="Site", markers=True, title="Consumo de gás natural mensal por site").update_layout(template="plotly_white", yaxis_title="kWh"), use_container_width=True)
        c3, c4 = st.columns(2)
        with c3:
            emis = mensal_site.groupby("Mês", as_index=False)[["emissao_total_tco2e", "emissao_total_com_irec_tco2e"]].sum()
            emis_long = emis.melt(id_vars="Mês", value_vars=["emissao_total_tco2e", "emissao_total_com_irec_tco2e"], var_name="Cenário", value_name="tCO₂e")
            emis_long["Cenário"] = emis_long["Cenário"].map({"emissao_total_tco2e": "Sem I-REC", "emissao_total_com_irec_tco2e": "Com I-REC"})
            plotly_chart_safe(px.line(emis_long, x="Mês", y="tCO₂e", color="Cenário", markers=True, title="Emissões mensais de CO₂ — com e sem I-REC").update_layout(template="plotly_white"), use_container_width=True)
        with c4:
            if not r12_site.empty:
                fig = px.bar(r12_site.sort_values("consumo_total_kwh", ascending=False), x="Site", y="consumo_total_kwh", text="consumo_total_kwh", title="Consumo total R12 por site").update_layout(template="plotly_white", yaxis_title="kWh")
                plotly_chart_safe(energia_bar_sem_decimal(fig), use_container_width=True)
            else:
                empty_state("Sem dados R12 para consumo por site.")
    if aba_dash == "Ranking R12":
        c5, c6 = st.columns(2)
        with c5:
            if not r12_site.empty:
                fig = px.bar(r12_site.sort_values("custo_total_brl", ascending=False), x="Site", y="custo_total_brl", text="custo_total_brl", title="Custo total R12 por site").update_layout(template="plotly_white", yaxis_title="BRL")
                plotly_chart_safe(energia_bar_sem_decimal(fig), use_container_width=True)
            else:
                empty_state("Sem dados R12 para custo por site.")
        with c6:
            if not r12_site.empty:
                fig = px.bar(r12_site.sort_values("eficiencia_energetica", ascending=True), x="Site", y="eficiencia_energetica", text="eficiencia_energetica", title="Eficiência energética R12 por site — menor é melhor").update_layout(template="plotly_white", yaxis_title="kWh/Actual Hour")
                plotly_chart_safe(energia_bar_sem_decimal(fig), use_container_width=True)
            else:
                empty_state("Sem dados R12 para eficiência por site.")
        if not r12_site.empty:
            ranking = r12_site.copy()
            ranking["Site nome"] = ranking["Site"].map(lambda x: energia_site_nome(x))
            ranking["CO₂ considerado"] = ranking["emissao_total_com_irec_tco2e"] if usar_irec else ranking["emissao_total_tco2e"]
            ranking_visual = ranking[["Site", "Site nome", "consumo_eletrico_kwh", "consumo_gas_kwh", "consumo_total_kwh", "CO₂ considerado", "custo_total_brl", "eficiencia_energetica"]]
            ranking_visual = ranking_visual.rename(columns={
                "consumo_eletrico_kwh": "Consumo elétrico kWh",
                "consumo_gas_kwh": "Consumo gás kWh",
                "consumo_total_kwh": "Consumo total kWh",
                "custo_total_brl": "Custo BRL",
                "eficiencia_energetica": "Eficiência kWh/h",
            }).sort_values("Consumo total kWh", ascending=False)
            ranking_visual = energia_formatar_tabela_visual(
                ranking_visual,
                money_cols=["Custo BRL"],
                integer_cols=["Consumo elétrico kWh", "Consumo gás kWh", "Consumo total kWh", "CO₂ considerado"],
                decimal_cols=["Eficiência kWh/h"],
            )
            st.dataframe(ranking_visual, use_container_width=True, hide_index=True)

    if aba_dash == "Metas":
        section("Metas ao longo do tempo")
        df_scope = df.copy()
        sites_sel = st.session_state.get("energia_dash_sites", [])
        grupos_sel = st.session_state.get("energia_dash_grupos", [])
        if sites_sel:
            df_scope = df_scope[df_scope["Site"].isin(sites_sel)]
        if grupos_sel and "LAG" not in grupos_sel:
            df_scope = df_scope[df_scope["Grupo"].isin(grupos_sel)]
        metas = energia_tendencia_metas(df_scope, usar_irec, db, r12_mes)
        if metas.empty:
            empty_state("Sem dados suficientes para gerar a tendência de metas.")
        else:
            c7, c8 = st.columns(2)
            with c7:
                emis_meta = metas[["Mês","Emissões R12","Meta emissões"]].melt(id_vars="Mês", var_name="Série", value_name="tCO₂e")
                plotly_chart_safe(px.line(emis_meta, x="Mês", y="tCO₂e", color="Série", markers=True, title="Emissões R12 vs meta ao longo do tempo").update_layout(template="plotly_white"), use_container_width=True)
            with c8:
                eff_meta = metas[["Mês","Eficiência energética R12","Meta eficiência energética"]].melt(id_vars="Mês", var_name="Série", value_name="kWh/Actual Hour")
                plotly_chart_safe(px.line(eff_meta, x="Mês", y="kWh/Actual Hour", color="Série", markers=True, title="Eficiência energética R12 vs meta ao longo do tempo").update_layout(template="plotly_white"), use_container_width=True)

    if aba_dash == "Exportação":
        section("Exportação")
        tabela_exec = energia_executive_table(db, "Emissões de CO₂ considerando I-REC" if usar_irec else "Emissões de CO₂", r12_mes, usar_irec)
        download_excel_button("Exportar relatório Excel", "relatorio_energia_co2.xlsx", {
            "Consolidado_Filtrado": f,
            "KPIs": kpis,
            "Tabela_Executiva": tabela_exec.drop(columns=["_grupo"], errors="ignore"),
            "Ranking_Localidades": local_df,
            "Base_Energia": energia_df_registros(db),
            "Base_Actual_Hours": energia_df_actual_hours(db),
            "Premissas": pd.DataFrame([{"Parâmetro": p.chave, "Valor": p.valor, "Descrição": p.descricao} for p in db.query(EnergiaParametro).all()]),
        })


def energia_atualizar_base(db,u):
    header("Atualizar Base de Energia, Gás e Emissões", "Importe os dois arquivos oficiais e sobrescreva a base atual do módulo")
    st.info("Envie os arquivos de consumo/custo e emissões para atualizar a base do módulo.")
    c1, c2 = st.columns(2)
    with c1:
        up_energia = st.file_uploader("1) Arquivo de consumo e custo — GAS_ENERGIA_CONTROLE_MENSAL", type=["xlsx","xls"], key="energia_upload_base_consumo")
    with c2:
        up_emissoes = st.file_uploader("2) Arquivo de emissões — EMISSOES", type=["xlsx","xls"], key="energia_upload_base_emissoes")
    if not up_energia and not up_emissoes:
        empty_state("Envie os dois arquivos Excel para iniciar a atualização.")
        return
    if not up_energia or not up_emissoes:
        st.warning("Para atualizar a base oficial, envie os dois arquivos: consumo/custo e emissões.")
        return
    try:
        parsed = energia_parse_base_resource(up_energia, db, up_energia.name, up_emissoes, up_emissoes.name)
    except Exception as e:
        st.error(str(e))
        return
    if parsed.empty:
        st.warning("Nenhum registro produtivo reconhecido nos arquivos. Verifique cabeçalho, sites, serviços e período.")
        return
    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("Linhas reconhecidas", len(parsed))
    c2.metric("Meses", parsed["mes_ref"].nunique())
    c3.metric("Sites", parsed["site_codigo"].nunique())
    c4.metric("Serviços", parsed["fonte"].nunique())
    c5.metric("CO₂ importado", energia_fmt_val(parsed["emissao_co2_ton"].sum(), "numero"))
    resumo = parsed.groupby(["site_codigo","fonte"], as_index=False).agg({"consumo_kwh":"sum", "custo_brl":"sum", "emissao_co2_ton":"sum"})
    abas = st.tabs(["Prévia consolidada", "Prévia detalhada"])
    with abas[0]:
        st.dataframe(resumo, use_container_width=True, hide_index=True)
    with abas[1]:
        st.dataframe(parsed.head(200), use_container_width=True, hide_index=True)
    st.warning("Ao confirmar, a tabela EnergiaRegistro será apagada e substituída pela base tratada acima.")
    if st.button("Confirmar atualização e sobrescrever base", use_container_width=True):
        db.query(EnergiaRegistro).delete()
        for _, r in parsed.iterrows():
            db.add(EnergiaRegistro(**r.to_dict()))
        db.add(EnergiaUploadHistorico(tipo_base="Energia/Gás/Emissões", nome_arquivo=f"{up_energia.name} + {up_emissoes.name}", usuario=u.nome if u else "", observacoes=f"{len(parsed)} linhas importadas; emissões vindas da planilha EMISSOES."))
        db.commit()
        st.cache_data.clear()
        st.success("Base de energia, gás e emissões atualizada com sucesso.")
        st.rerun()

def energia_actual_hours_page(db,u):
    header("Actual Hours", "Importação, edição manual e manutenção da base de horas trabalhadas")
    up = st.file_uploader("Importar Brazil Absorption Summary FY26 (.xls ou .xlsx)", type=["xlsx","xls"], key="energia_upload_absorption")
    if up:
        try:
            parsed = energia_parse_absorption(up, up.name)
            if parsed.empty:
                st.warning("Nenhum Actual Hours foi reconhecido nas abas mapeadas.")
            else:
                st.dataframe(parsed.head(120), use_container_width=True, hide_index=True)
                if st.button("Confirmar importação de Actual Hours", use_container_width=True):
                    for _, r in parsed.iterrows():
                        db.query(EnergiaActualHours).filter(
                            EnergiaActualHours.mes_ref == r["mes_ref"],
                            EnergiaActualHours.site_codigo == r["site_codigo"]
                        ).delete()
                        db.add(EnergiaActualHours(**r.to_dict()))
                    db.add(EnergiaUploadHistorico(tipo_base="Actual Hours", nome_arquivo=up.name, usuario=u.nome if u else "", observacoes=f"{len(parsed)} linhas importadas"))
                    db.commit()
                    st.cache_data.clear()
                    st.success("Actual Hours importado/atualizado.")
                    st.rerun()
        except Exception as e:
            st.error(str(e))

    section("Adicionar novo mês manualmente")
    with st.form("energia_add_hours"):
        c1,c2,c3,c4 = st.columns(4)
        mes = c1.date_input("Mês", value=date.today().replace(day=1))
        site = c2.selectbox("Site", ENERGIA_SITE_ORDER)
        actual = c3.number_input("Actual Hours", min_value=0.0, step=100.0)
        capacity = c4.number_input("Production capacity (hours)", min_value=0.0, step=100.0)
        if st.form_submit_button("Salvar novo valor", use_container_width=True):
            mes = energia_first_day(mes)
            db.query(EnergiaActualHours).filter(EnergiaActualHours.mes_ref==mes, EnergiaActualHours.site_codigo==site).delete()
            db.add(EnergiaActualHours(mes_ref=mes, site_codigo=site, site_nome=energia_site_nome(site), grupo=energia_site_grupo(site), actual_hours=actual, production_capacity_hours=capacity, origem="Manual", atualizado_em=datetime.utcnow()))
            db.commit()
            st.cache_data.clear()
            st.success("Actual Hours salvo.")
            st.rerun()

    section("Base atual")
    df = energia_df_actual_hours(db)
    if df.empty:
        empty_state("Nenhum Actual Hours cadastrado.")
        return
    f1,f2,f3 = st.columns(3)
    sites = f1.multiselect("Filtrar site", ENERGIA_SITE_ORDER, key="ah_site")
    grupos = f2.multiselect("Filtrar grupo", ENERGIA_GROUP_ORDER, key="ah_grupo")
    fys = sorted(df["FY"].dropna().unique().tolist())
    fy = f3.multiselect("Filtrar FY", fys, key="ah_fy")
    f = df.copy()
    if sites: f = f[f["Site"].isin(sites)]
    if grupos and "LAG" not in grupos: f = f[f["Grupo"].isin(grupos)]
    if fy: f = f[f["FY"].isin(fy)]
    st.dataframe(f, use_container_width=True, hide_index=True)
    download_excel_button("Exportar Actual Hours", "actual_hours.xlsx", {"Actual_Hours": f})

def energia_tabela_executiva_page(db,u):
    header("Tabela Executiva", "Tabela no padrão executivo para FY, R12, I-REC e eficiência energética")
    df = energia_consolidado(db)
    if df.empty:
        empty_state("Sem base consolidada. Importe energia/gás e Actual Hours.")
        return
    metricas = ["Consumo de energia elétrica", "Consumo de gás natural", "Consumo total de energia", "Emissões de CO₂", "Emissões de CO₂ considerando I-REC", "Custo", "Eficiência energética"]
    c1,c2,c3 = st.columns(3)
    metrica = c1.selectbox("Métrica", metricas, index=metricas.index("Emissões de CO₂ considerando I-REC"))
    usar_irec = c2.toggle("Considerar I-REC", value=True)
    r12_opts = sorted(df["Mês"].unique())
    default_r12 = energia_default_r12_mes(df) or max(r12_opts)
    r12_idx = r12_opts.index(default_r12) if default_r12 in r12_opts else len(r12_opts)-1
    r12_mes = c3.selectbox("Mês R12/YTD", r12_opts, index=r12_idx, format_func=lambda d: d.strftime("%b/%Y"))
    tabela = energia_executive_table(db, metrica, r12_mes, usar_irec)
    subt = "Emissões de energia elétrica zeradas; emissões de gás natural mantidas." if usar_irec else "Sem abatimento de emissões por I-REC."
    st.caption(subt)
    st.markdown(energia_table_html(tabela, metrica), unsafe_allow_html=True)
    download_excel_button("Exportar tabela executiva Excel", "tabela_executiva_energia.xlsx", {"Tabela_Executiva": tabela.drop(columns=["_grupo"], errors="ignore")})

def energia_base_consolidada_page(db,u):
    header("Base Consolidada", "Tabela mensal consolidada de energia, gás, CO₂, custos, Actual Hours e R12")
    df = energia_consolidado(db)
    if df.empty:
        empty_state("Sem dados consolidados.")
        return
    f, r12_mes, usar_irec = energia_dash_filters(df, "energia_base")
    st.dataframe(f, use_container_width=True, hide_index=True)
    download_excel_button("Exportar base consolidada", "base_consolidada_energia.xlsx", {"Consolidado": f})

def energia_parametros_page(db,u):
    header("Parâmetros", "I-REC, metas, conversões e referência fiscal")
    seed_energia_parametros(db)
    ps = db.query(EnergiaParametro).order_by(EnergiaParametro.chave).all()
    with st.form("energia_parametros_form"):
        values = {}
        for p in ps:
            values[p.chave] = st.text_input(p.chave, value=p.valor or "", help=p.descricao or "")
        if st.form_submit_button("Salvar parâmetros", use_container_width=True):
            for chave, valor in values.items():
                energia_set_param(db, chave, valor)
            st.cache_data.clear()
            st.success("Parâmetros atualizados.")
            st.rerun()
    df = pd.DataFrame([{"Parâmetro": p.chave, "Valor": p.valor, "Descrição": p.descricao} for p in ps])
    st.dataframe(df, use_container_width=True, hide_index=True)


def energia_relatorios_page(db,u):
    header("Relatórios Energia", "Exportações completas do módulo de energia e emissões")
    df_cons = energia_consolidado(db)
    df_reg = energia_df_registros(db)
    df_hrs = energia_df_actual_hours(db)
    if df_cons.empty:
        empty_state("Sem dados para exportar.")
        return
    r12_mes = energia_default_r12_mes(df_cons) or max(df_cons["Mês"])
    tabela = energia_executive_table(db, "Emissões de CO₂ considerando I-REC", r12_mes, True)
    kpis = energia_df_kpis(df_cons, r12_mes, True)
    prem = pd.DataFrame([{"Parâmetro": p.chave, "Valor": p.valor, "Descrição": p.descricao} for p in db.query(EnergiaParametro).order_by(EnergiaParametro.chave).all()])
    dados_graficos = df_cons.groupby(["Mês","Site","Grupo"], as_index=False).agg({
        "consumo_eletrico_kwh":"sum", "consumo_gas_kwh":"sum", "consumo_total_kwh":"sum",
        "emissao_total_tco2e":"sum", "emissao_total_com_irec_tco2e":"sum",
        "custo_total_brl":"sum", "actual_hours":"sum"
    })
    section("Relatório completo")
    download_excel_button("Baixar relatório completo Excel", "relatorio_completo_energia.xlsx", {
        "Base_Energia": df_reg,
        "Base_Actual_Hours": df_hrs,
        "Consolidado": df_cons,
        "KPIs": kpis,
        "Tabela_Executiva": tabela.drop(columns=["_grupo"], errors="ignore"),
        "Premissas": prem,
        "Dados_Graficos": dados_graficos,
    })
    pdf_dashboard = energia_pdf_dashboard(db, r12_mes, True)
    download_pdf_button("Baixar todo o dashboard em PDF", "dashboard_energia_co2.pdf", pdf_dashboard)

    section("Bases individuais")
    c1,c2,c3 = st.columns(3)
    with c1:
        download_excel_button("Base energia", "base_energia.xlsx", {"Base_Energia": df_reg})
    with c2:
        download_excel_button("Actual Hours", "actual_hours.xlsx", {"Base_Actual_Hours": df_hrs})
    with c3:
        download_excel_button("Consolidado", "consolidado_energia.xlsx", {"Consolidado": df_cons})



def ajuda_rapida_page(db,u):
    header("Ajuda rápida", "Guia simples para usar a Plataforma Integrada EHS")
    section("Como navegar")
    c1,c2,c3=st.columns(3)
    with c1:
        st.markdown("""
        <div class='quick-help-card'>
        <h4>1. Escolha o módulo</h4>
        <p>Na página inicial, entre em Sustentação de Proteções de Máquinas, Auditoria Cruzada ou Controle de Energia e Emissões.</p>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown("""
        <div class='quick-help-card'>
        <h4>2. Escolha o submódulo</h4>
        <p>Cada módulo possui uma tela intermediária com áreas como Gestão e Performance, Execução, Pendências e Administração.</p>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown("""
        <div class='quick-help-card'>
        <h4>3. Use filtros e exportações</h4>
        <p>Nos dashboards e tabelas, filtre por site, período, status, responsável ou criticidade e exporte quando necessário.</p>
        </div>
        """, unsafe_allow_html=True)

    section("Guia por módulo")
    tabs=st.tabs(["Proteções de Máquinas", "Auditoria Cruzada EHS", "Energia e Emissões", "Dicas gerais"])
    with tabs[0]:
        st.markdown(f"""
        **Objetivo:** sustentar a conformidade de proteções de máquinas por meio de inventário, documentos, checklists, calendário e PACs.

        **Fluxo recomendado:**
        1. Cadastre ou revise a máquina em **Inventário de Máquinas**.
        2. Anexe laudos, ARTs e apreciações em **{NOME_DOCS_MAQUINAS}**.
        3. Registre inspeções em **Checklists e Inspeções**.
        4. Acompanhe prazos no **Calendário de Auditorias e Inspeções**.
        5. Trate desvios no **{NOME_PAC_MAQUINAS}**.
        """)
    with tabs[1]:
        st.markdown("""
        **Objetivo:** planejar, executar e acompanhar auditorias cruzadas de Diretrizes EHS entre sites.

        **Fluxo recomendado:**
        1. Crie o ciclo em **Planejamento de Auditorias**.
        2. Acompanhe datas no **Calendário de Auditorias**.
        3. Preencha o **Checklist Diretrizes de EHS** com evidências e maturidade.
        4. Trate gaps no **PAC Auditoria Cruzada**.
        5. Acompanhe desempenho no **Dashboard Auditoria Cruzada**.
        """)
    with tabs[2]:
        st.markdown("""
        **Objetivo:** acompanhar consumo de energia, gás natural, emissões, custos, eficiência energética, R12, FY e análise com I-REC.

        **Fluxo recomendado:**
        1. Atualize os arquivos em **Atualizar Base**.
        2. Revise horas trabalhadas em **Actual Hours**.
        3. Analise indicadores no **Dashboard Energia e CO₂**.
        4. Use a **Tabela Executiva** para visão comparativa por FY/R12.
        5. Baixe bases e relatórios em **Relatórios Energia**.
        """)
    with tabs[3]:
        st.markdown("""
        - Use o breadcrumb no topo para entender onde você está.
        - Use o botão **Voltar aos submódulos** na barra lateral para trocar de área dentro do mesmo módulo.
        - Campos críticos como máquina não conforme, PAC crítico e datas vencidas exigem mais atenção.
        - Quando houver dúvida sobre um indicador, confira filtros, período de referência e base utilizada.
        - Para auditoria e governança, prefira sempre registrar evidências e observações objetivas.
        """)

    section("Ações rápidas")
    c1,c2,c3,c4=st.columns(4)
    with c1:
        if st.button("🏠 Página inicial",use_container_width=True,key="ajuda_voltar_home"):
            st.session_state.modulo="home"
            st.rerun()
    with c2:
        if st.button(f"⚙️ {NOME_MODULO_MAQUINAS}",use_container_width=True,key="ajuda_ir_maquinas"):
            st.session_state.modulo="nr12"
            st.session_state.page_nr12=NR12_HOME_PAGE
            st.rerun()
    with c3:
        if st.button("🧭 Auditoria EHS",use_container_width=True,key="ajuda_ir_ehs"):
            st.session_state.modulo="ehs"
            st.session_state.page_ehs=EHS_HOME_PAGE
            st.rerun()
    with c4:
        if st.button("⚡ Energia e Emissões",use_container_width=True,key="ajuda_ir_energia"):
            st.session_state.modulo="energia"
            st.session_state.page_energia=ENERGIA_HOME_PAGE
            st.rerun()



NEAR_MISS_SEED_B64 = """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"""

def near_miss_seed_records():
    try:
        raw = zlib.decompress(base64.b64decode(NEAR_MISS_SEED_B64.encode("ascii")))
        return json.loads(raw.decode("utf-8"))
    except Exception:
        logging.exception("Falha ao carregar base inicial de Near Miss")
        return []

def near_miss_site_code(valor):
    cod = normalize_site_code(valor)
    return cod if cod in SITES_LAG and cod != "Corporativo" else "—"

def near_miss_float(v):
    try:
        if v is None or v == "": return None
        return float(v)
    except Exception:
        return None

def near_miss_dt(v):
    return as_date(v)

def near_miss_status_prazo(row):
    status = str(row.get("Status") or row.get("status") or "").lower()
    due = near_miss_dt(row.get("Closure Due Date") or row.get("closure_due_date"))
    closed = near_miss_dt(row.get("Closed Date") or row.get("closed_date"))
    days_past = near_miss_float(row.get("Days Past Closure Due/Days to closure") or row.get("days_past_due"))
    if closed:
        if due and closed > due:
            return "Fechado fora do prazo"
        if days_past is not None and days_past > 0:
            return "Fechado fora do prazo"
        return "Fechado no prazo"
    if not due:
        return "Aberto sem prazo"
    if due < date.today():
        return "Aberto vencido"
    return "Aberto no prazo"

def near_miss_acompanhamento(row):
    stp = near_miss_status_prazo(row)
    if stp in ["Aberto vencido", "Aberto sem prazo", "Fechado fora do prazo"]:
        return "Acompanhar"
    return "Regular"

def near_miss_is_near_miss(tipo):
    return "near" in str(tipo or "").lower() and "miss" in str(tipo or "").lower()

def near_miss_mapping_from_record(r):
    bu = r.get("Business Unit") or r.get("business_unit")
    site_codigo = near_miss_site_code(bu)
    site_nome = site_nome_curto(site_codigo) if site_codigo != "—" else str(bu or "—")
    return {
        "id_cr": str(r.get("ID") or r.get("id_cr") or "").strip(),
        "data_ocorrencia": near_miss_dt(r.get("Dates") or r.get("data_ocorrencia")),
        "data_reportada": str(r.get("Date Reported") or r.get("data_reportada") or "")[:120],
        "tipo": str(r.get("Type") or r.get("tipo") or "—")[:120],
        "grupo_origem": str(r.get("Group") or r.get("grupo_origem") or "")[:160],
        "sub_grupo": str(r.get("Sub-Group") or r.get("sub_grupo") or "")[:160],
        "business_unit": str(bu or "")[:160],
        "dept": str(r.get("Dept") or r.get("dept") or "")[:180],
        "site_codigo": site_codigo,
        "site_nome": site_nome,
        "grupo": site_grupo(site_codigo) if site_codigo != "—" else "—",
        "divisao": site_divisao(site_codigo) if site_codigo != "—" else "—",
        "hazard_type": str(r.get("Hazard Type") or r.get("hazard_type") or "")[:160],
        "status": str(r.get("Status") or r.get("status") or "")[:120],
        "assigned_to": str(r.get("Assigned To") or r.get("assigned_to") or "")[:160],
        "closure_due_date": near_miss_dt(r.get("Closure Due Date") or r.get("closure_due_date")),
        "closed_date": near_miss_dt(r.get("Closed Date") or r.get("closed_date")),
        "days_open_to_close": near_miss_float(r.get("Days Open / To Close") or r.get("days_open_to_close")),
        "days_past_due": near_miss_float(r.get("Days Past Closure Due/Days to closure") or r.get("days_past_due")),
        "descricao": str(r.get("Description") or r.get("descricao") or "")[:500],
        "origem_arquivo": str(r.get("Origem Arquivo") or r.get("origem_arquivo") or "Base inicial")[:260],
    }

def seed_near_miss_inicial(db):
    try:
        if db.query(NearMissRegistro).count() > 0:
            return
        regs=[]
        for r in near_miss_seed_records():
            m = near_miss_mapping_from_record(r)
            if m["id_cr"]:
                regs.append(m)
        if regs:
            db.bulk_insert_mappings(NearMissRegistro, regs)
            db.add(NearMissUploadHistorico(nome_arquivo="Base inicial", linhas_importadas=len(regs), usuario="Sistema", observacoes="Carga inicial"))
            db.commit()
    except Exception:
        db.rollback()
        logging.exception("Falha ao inserir base inicial de Near Miss")

def parse_near_miss_excel(file_obj, origem_nome="upload.xlsx"):
    try:
        xls = pd.ExcelFile(file_obj)
    except Exception as e:
        raise ValueError(f"Não foi possível ler o arquivo {origem_nome}: {e}")
    frames=[]
    for sheet in xls.sheet_names:
        preview = pd.read_excel(xls, sheet_name=sheet, header=None, nrows=12)
        header_row = None
        for i in range(len(preview)):
            vals = [str(v).strip() for v in preview.iloc[i].tolist()]
            if "Group" in vals and "ID" in vals and "Status" in vals:
                header_row = i
                break
        if header_row is None:
            continue
        df = pd.read_excel(xls, sheet_name=sheet, header=header_row)
        if "ID" not in df.columns:
            continue
        df = df.dropna(subset=["ID"])
        df["Origem Arquivo"] = origem_nome
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    df = df.drop_duplicates(subset=["ID"])
    registros=[]
    for _, r in df.iterrows():
        d = r.to_dict()
        m = near_miss_mapping_from_record(d)
        if m["id_cr"]:
            registros.append(m)
    return pd.DataFrame(registros)

def near_miss_df(db):
    rows=[]
    for r in db.query(NearMissRegistro).order_by(NearMissRegistro.data_ocorrencia.desc().nullslast(), NearMissRegistro.id.desc()).all():
        base = {
            "ID": r.id_cr,
            "Data": r.data_ocorrencia,
            "Mês": r.data_ocorrencia.replace(day=1) if r.data_ocorrencia else None,
            "Tipo": r.tipo or "—",
            "Concern Report?": "Near Miss" if near_miss_is_near_miss(r.tipo) else "Concern Report",
            "Site código": r.site_codigo or "—",
            "Site": r.site_nome or "—",
            "Grupo": r.grupo or "—",
            "Divisão": r.divisao or "—",
            "Business Unit": r.business_unit or "—",
            "Departamento": r.dept or "—",
            "Hazard Type": r.hazard_type or "—",
            "Status": r.status or "—",
            "Responsável": r.assigned_to or "—",
            "Prazo": r.closure_due_date,
            "Fechamento": r.closed_date,
            "Dias aberto/fechamento": r.days_open_to_close,
            "Dias após prazo": r.days_past_due,
            "Descrição": r.descricao or "",
            "Origem": r.origem_arquivo or "—",
        }
        base["Status do prazo"] = near_miss_status_prazo({
            "Status": base["Status"], "Closure Due Date": base["Prazo"], "Closed Date": base["Fechamento"], "Days Past Closure Due/Days to closure": base["Dias após prazo"]
        })
        base["Acompanhamento"] = "Acompanhar" if base["Status do prazo"] in ["Aberto vencido", "Aberto sem prazo", "Fechado fora do prazo"] else "Regular"
        rows.append(base)
    df = pd.DataFrame(rows)
    if not df.empty:
        for c in ["Data","Mês","Prazo","Fechamento"]:
            df[c] = pd.to_datetime(df[c], errors="coerce")
        df["Prazo atribuído (dias)"] = (df["Prazo"] - df["Data"]).dt.days
        df["Prazo superior a 45 dias"] = df["Prazo atribuído (dias)"].fillna(0).gt(NEAR_MISS_PRAZO_MAXIMO_DIAS)
        df.loc[df["Prazo superior a 45 dias"], "Acompanhamento"] = "Acompanhar"
    return df

def near_miss_filtrar_df(df, periodo=None, sites=None, divisoes=None, tipos=None, status_prazo=None, somente_nearmiss=False):
    if df.empty: return df
    out=df.copy()
    if periodo:
        ini,fim=periodo
        out=out[(out["Data"].isna()) | ((out["Data"]>=pd.to_datetime(ini)) & (out["Data"]<=pd.to_datetime(fim)))]
    if sites:
        out=out[out["Site código"].isin(sites)]
    if divisoes:
        out=out[out["Divisão"].isin(divisoes)]
    if tipos:
        out=out[out["Tipo"].isin(tipos)]
    if status_prazo:
        out=out[out["Status do prazo"].isin(status_prazo)]
    if somente_nearmiss:
        out=out[out["Concern Report?"]=="Near Miss"]
    return out

def near_miss_fy_num(d):
    d = pd.to_datetime(d, errors="coerce")
    if pd.isna(d):
        d = pd.Timestamp(date.today())
    return int(d.year + 1 if d.month >= 7 else d.year)

def near_miss_fy_label(ano_fy):
    return f"FY{str(int(ano_fy))[-2:]}"

def near_miss_fy_range(label):
    yy = int(str(label).replace("FY", ""))
    ano_fy = 2000 + yy if yy < 70 else 1900 + yy
    return date(ano_fy - 1, 7, 1), date(ano_fy, 6, 30)

def near_miss_fy_options(min_data, max_data):
    ini = near_miss_fy_num(min_data)
    fim = max(near_miss_fy_num(max_data), near_miss_fy_num(date.today()))
    return [near_miss_fy_label(y) for y in range(fim, ini - 1, -1)]

def near_miss_r12_range(max_data):
    fim = pd.to_datetime(max_data, errors="coerce")
    if pd.isna(fim):
        fim = pd.Timestamp(date.today())
    ini = fim - pd.DateOffset(months=12) + pd.DateOffset(days=1)
    return ini.date(), fim.date()

def near_miss_cor_taxa(valor):
    if valor >= NEAR_MISS_META_FECHAMENTO_PRAZO:
        return "#16a34a"
    if valor >= NEAR_MISS_ALERTA_FECHAMENTO_PRAZO:
        return "#facc15"
    return "#dc2626"

def near_miss_taxa_site_df(df, incluir_lag=False):
    if df.empty or "Fechamento" not in df:
        return pd.DataFrame()
    rows=[]
    fechados=df[df["Fechamento"].notna()]
    for site,g in fechados.groupby("Site", dropna=False):
        total=len(g)
        no_prazo=int((g["Status do prazo"]=="Fechado no prazo").sum())
        taxa=round(no_prazo/total*100,1) if total else 0
        rows.append({"Site":site,"Taxa no prazo %":taxa,"Fechados":total,"No prazo":no_prazo,"Cor":near_miss_cor_taxa(taxa)})
    if not rows:
        return pd.DataFrame()
    out=pd.DataFrame(rows).sort_values("Taxa no prazo %", ascending=True)
    if incluir_lag and not fechados.empty:
        total=len(fechados)
        no_prazo=int((fechados["Status do prazo"]=="Fechado no prazo").sum())
        taxa=round(no_prazo/total*100,1) if total else 0
        lag=pd.DataFrame([{"Site":"LAG","Taxa no prazo %":taxa,"Fechados":total,"No prazo":no_prazo,"Cor":near_miss_cor_taxa(taxa)}])
        out=pd.concat([out, lag], ignore_index=True)
    return out

def near_miss_taxa_divisao_df(df):
    if df.empty or "Fechamento" not in df or "Divisão" not in df:
        return pd.DataFrame()
    fechados=df[df["Fechamento"].notna()]
    if fechados.empty:
        return pd.DataFrame()
    rows=[]
    for divisao,g in fechados.groupby("Divisão", dropna=False):
        total=len(g)
        no_prazo=int((g["Status do prazo"]=="Fechado no prazo").sum())
        taxa=round(no_prazo/total*100,1) if total else 0
        rows.append({"Divisão":divisao,"Taxa no prazo %":taxa,"Fechados":total,"No prazo":no_prazo,"Cor":near_miss_cor_taxa(taxa)})
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values("Taxa no prazo %", ascending=True)

def near_miss_fig_taxa_fechamento_divisao(tdf, titulo="Taxa de fechamento no prazo por divisão — meta > 95%", altura=360):
    if tdf.empty:
        return None
    fig=px.bar(tdf,x="Taxa no prazo %",y="Divisão",orientation="h",text="Taxa no prazo %",title=titulo, custom_data=["Fechados","No prazo"])
    fig.update_traces(texttemplate="%{text:.1f}%",textposition="outside", marker_color=tdf["Cor"].tolist(), hovertemplate="%{y}<br>Taxa no prazo: %{x:.1f}%<br>Fechados: %{customdata[0]}<br>No prazo: %{customdata[1]}<extra></extra>")
    fig.add_vline(x=NEAR_MISS_META_FECHAMENTO_PRAZO, line_dash="dash", line_color="#16a34a", annotation_text="Meta > 95%", annotation_position="top")
    fig.update_layout(height=altura,xaxis_range=[0,105],margin=dict(l=10,r=50,t=50,b=10),showlegend=False)
    return fig

def near_miss_fig_taxa_fechamento_site(tdf, titulo="Taxa de fechamento no prazo por site — meta > 95%", altura=380):
    if tdf.empty:
        return None
    fig=px.bar(tdf,x="Taxa no prazo %",y="Site",orientation="h",text="Taxa no prazo %",title=titulo, custom_data=["Fechados","No prazo"])
    fig.update_traces(texttemplate="%{text:.1f}%",textposition="outside", marker_color=tdf["Cor"].tolist(), hovertemplate="%{y}<br>Taxa no prazo: %{x:.1f}%<br>Fechados: %{customdata[0]}<br>No prazo: %{customdata[1]}<extra></extra>")
    fig.add_vline(x=NEAR_MISS_META_FECHAMENTO_PRAZO, line_dash="dash", line_color="#16a34a", annotation_text="Meta > 95%", annotation_position="top")
    fig.update_yaxes(categoryorder="array", categoryarray=tdf["Site"].tolist())
    fig.update_layout(height=altura,xaxis_range=[0,105],margin=dict(l=10,r=50,t=50,b=10),showlegend=False)
    return fig

def near_miss_criticos_prazo_df(df):
    if df.empty:
        return df
    return df[df["Status do prazo"].isin(["Aberto vencido", "Aberto sem prazo", "Fechado fora do prazo"])].copy()

def near_miss_fig_sites_criticos(df, titulo="Sites com mais itens críticos de prazo", altura=360):
    criticos=near_miss_criticos_prazo_df(df)
    if criticos.empty:
        return None
    top=criticos.groupby("Site", dropna=False).size().reset_index(name="Quantidade").sort_values("Quantidade", ascending=True).tail(10)
    if top.empty:
        return None
    fig=px.bar(top,x="Quantidade",y="Site",orientation="h",text="Quantidade",title=titulo)
    fig.update_traces(texttemplate="%{text:.0f}",textposition="outside",marker_color="#dc2626",hovertemplate="%{y}<br>Itens críticos: %{x}<extra></extra>")
    fig.update_layout(height=altura,margin=dict(l=10,r=30,t=50,b=10),showlegend=False)
    return fig

def near_miss_prazo_superior_45_df(df):
    if df.empty or "Prazo superior a 45 dias" not in df:
        return pd.DataFrame()
    return df[df["Prazo superior a 45 dias"].fillna(False)].copy()

def near_miss_fig_prazo_superior_45_site(df, titulo="Reports com prazo atribuído acima de 45 dias", altura=340):
    excesso = near_miss_prazo_superior_45_df(df)
    if excesso.empty:
        return None
    top = excesso.groupby("Site", dropna=False).size().reset_index(name="Quantidade").sort_values("Quantidade", ascending=True).tail(10)
    if top.empty:
        return None
    fig = px.bar(top, x="Quantidade", y="Site", orientation="h", text="Quantidade", title=titulo)
    fig.update_traces(texttemplate="%{text:.0f}", textposition="outside", marker_color="#ea580c", hovertemplate="%{y}<br>Prazo > 45 dias: %{x}<extra></extra>")
    fig.update_layout(height=altura, margin=dict(l=10, r=30, t=50, b=10), showlegend=False)
    return fig

def near_miss_pendencias_abertas_df(df):
    if df.empty:
        return df
    pend=df[df["Fechamento"].isna()].copy()
    if pend.empty:
        return pend
    hoje=pd.Timestamp(date.today())
    pend["Dias para vencer"]=(pend["Prazo"]-hoje).dt.days
    pend["Dias em aberto"]=(hoje-pend["Data"]).dt.days
    mes_atual=hoje.month
    ano_atual=hoje.year
    def categoria(row):
        stp=row.get("Status do prazo")
        dias=row.get("Dias para vencer")
        prazo=row.get("Prazo")
        if stp=="Aberto vencido":
            return "Vencido"
        if stp=="Aberto sem prazo" or pd.isna(prazo):
            return "Sem prazo"
        if pd.notna(prazo) and prazo.month==mes_atual and prazo.year==ano_atual:
            return "Vence este mês"
        if pd.notna(dias) and 0 <= dias <= 15:
            return "Próximo do vencimento"
        return "Em prazo"
    pend["Categoria de pendência"]=pend.apply(categoria, axis=1)
    return pend

def near_miss_formata_tabela_pendencias(df):
    if df.empty:
        return df
    cols=["Descrição","Categoria de pendência","Status do prazo","Prazo","Fechamento","Data","Dias para vencer","Dias em aberto","ID","Tipo","Site","Divisão","Status","Responsável","Hazard Type"]
    cols=[c for c in cols if c in df.columns]
    show=df[cols].copy().rename(columns={"Data":"Data da abertura"})
    for c in ["Prazo","Fechamento","Data da abertura"]:
        if c in show.columns:
            show[c]=pd.to_datetime(show[c], errors="coerce").dt.strftime("%d/%m/%Y").fillna("—")
    return show

def near_miss_home_kpi_cards(db):
    df=near_miss_df(db)
    if df.empty:
        return [("Near Miss • Reports", 0, "Base não carregada")]
    total=len(df)
    acompanhar=int((df["Acompanhamento"]=="Acompanhar").sum())
    abertos=int(df["Fechamento"].isna().sum())
    fechados=df[df["Fechamento"].notna()]
    taxa=round((fechados["Status do prazo"].eq("Fechado no prazo").sum()/len(fechados)*100),1) if len(fechados) else 0
    return [
        ("Near Miss • Reports", total, "Concern Reports carregados"),
        ("Near Miss • Acompanhar", acompanhar, "Abertos vencidos, sem prazo ou fechados fora do prazo"),
        ("Near Miss • Abertos", abertos, "Sem data de fechamento"),
        ("Near Miss • Fechamento no prazo", f"{taxa}%", "Itens fechados dentro do prazo"),
    ]

def near_miss_submodulos_home(db,u):
    header("Near Miss", "Escolha um submódulo para analisar Concern Reports, atualizar a base ou exportar informações.")
    c_back, c_spacer = st.columns([1.1,5])
    with c_back:
        if st.button("⬅️ Voltar para página inicial", key="nearmiss_home_voltar_inicio", use_container_width=True):
            st.session_state.modulo="home"
            st.rerun()
    section("Submódulos")
    nomes=list(NEARMISS_SUBMODULOS.keys())
    for base in range(0,len(nomes),2):
        cols=st.columns(2)
        for col,nome in zip(cols,nomes[base:base+2]):
            cfg=NEARMISS_SUBMODULOS[nome]
            with col:
                submodule_card(nome,cfg["descricao"],cfg["icone"],cfg["cor"])
                if st.button(f"Acessar {nome}",key=f"nearmiss_sub_{nome}",use_container_width=True):
                    st.session_state.page_nearmiss=cfg["paginas"][0]
                    st.session_state.submodulo_nearmiss=nome
                    st.rerun()

def near_miss_dashboard(db,u):
    header("Dashboard Near Miss", "Acompanhamento de Concern Reports, prazos, volume por site/divisão e taxa de fechamento no prazo.")
    df=near_miss_df(db)
    if df.empty:
        empty_state("Base de Concern Reports ainda não carregada.")
        return
    min_data=df["Data"].dropna().min().date() if df["Data"].notna().any() else date.today()-timedelta(days=365)
    max_data=df["Data"].dropna().max().date() if df["Data"].notna().any() else date.today()
    opcoes_periodo=["R12 (últimos 12 meses)"] + near_miss_fy_options(min_data, max_data) + ["Personalizado"]
    with st.expander("Filtros", expanded=True):
        c1,c2,c3,c4=st.columns(4)
        with c1:
            modo_periodo=st.selectbox("Período de análise", opcoes_periodo, index=0, key="nm_modo_periodo")
        with c2:
            sites=st.multiselect("Site", sorted(df["Site código"].dropna().unique()), default=sorted(df["Site código"].dropna().unique()), key="nm_sites")
        with c3:
            tipos=st.multiselect("Tipo", sorted(df["Tipo"].dropna().unique()), key="nm_tipos")
        with c4:
            status_prazo=st.multiselect("Status do prazo", sorted(df["Status do prazo"].dropna().unique()), key="nm_status_prazo")
        c5,c6=st.columns(2)
        with c5:
            divisoes=st.multiselect("Divisão", sorted(df["Divisão"].dropna().unique()), key="nm_divisoes")
        with c6:
            somente_nearmiss=st.toggle("Mostrar somente tipo Near Miss", value=False, key="nm_only")
        if modo_periodo == "R12 (últimos 12 meses)":
            periodo_tuple = near_miss_r12_range(max_data)
        elif modo_periodo == "Personalizado":
            periodo=st.date_input("Período personalizado", value=(min_data,max_data), key="nm_periodo_custom")
            periodo_tuple = periodo if isinstance(periodo, tuple) and len(periodo)==2 else (min_data,max_data)
        else:
            periodo_tuple = near_miss_fy_range(modo_periodo)
        st.caption(f"Período aplicado: {periodo_tuple[0].strftime('%d/%m/%Y')} a {periodo_tuple[1].strftime('%d/%m/%Y')}")
    fdf=near_miss_filtrar_df(df, periodo_tuple, sites, divisoes, tipos, status_prazo, somente_nearmiss)
    total=len(fdf)
    fechados=fdf[fdf["Fechamento"].notna()]
    taxa=round((fechados["Status do prazo"].eq("Fechado no prazo").sum()/len(fechados)*100),1) if len(fechados) else 0
    abertos=int(fdf["Fechamento"].isna().sum()) if total else 0
    vencidos=int((fdf["Status do prazo"]=="Aberto vencido").sum()) if total else 0
    sem_prazo=int((fdf["Status do prazo"]=="Aberto sem prazo").sum()) if total else 0
    fechados_fora=int((fdf["Status do prazo"]=="Fechado fora do prazo").sum()) if total else 0
    prazo_excessivo=int(fdf.get("Prazo superior a 45 dias", pd.Series(dtype=bool)).fillna(False).sum()) if total else 0
    cols=st.columns(7)
    vals=[("Total",total,"Concern Reports"),("Abertos",abertos,"Sem data de fechamento"),("Abertos vencidos",vencidos,"Prazo excedido"),("Abertos sem prazo",sem_prazo,"Sem prazo informado"),("Fechados fora",fechados_fora,"Fechamento excedeu prazo"),("Prazo >45 dias",prazo_excessivo,"Prazo atribuído acima do limite do procedimento"),("Fechamento no prazo",f"{taxa}%","Entre itens fechados")]
    for c,(l,v,h) in zip(cols,vals):
        with c: kpi_card(l,v,h)
    tabs=st.tabs(["Resumo", "Prazos", "Insights", "Tendência", "Detalhamento"])
    with tabs[0]:
        section("Resumo executivo")
        excesso_prazo = near_miss_prazo_superior_45_df(fdf)
        pct_excesso = round(len(excesso_prazo) / total * 100, 1) if total else 0
        pior_site_excesso = excesso_prazo.groupby("Site").size().sort_values(ascending=False) if not excesso_prazo.empty else pd.Series(dtype=int)
        r1,r2,r3 = st.columns(3)
        with r1:
            kpi_card("Prazo acima de 45 dias", len(excesso_prazo), "Reports com prazo atribuído acima do limite máximo")
        with r2:
            kpi_card("Representatividade", f"{pct_excesso}%", "Percentual sobre os reports filtrados")
        with r3:
            kpi_card("Site com mais prazo >45d", pior_site_excesso.index[0] if len(pior_site_excesso) else "—", f"{int(pior_site_excesso.iloc[0])} itens" if len(pior_site_excesso) else "Sem ocorrência")
        tdf_resumo=near_miss_taxa_site_df(fdf, incluir_lag=True)
        c1,c2=st.columns(2)
        with c1:
            fig=near_miss_fig_taxa_fechamento_site(tdf_resumo, altura=390)
            if fig is not None:
                plotly_chart_safe(fig,use_container_width=True)
            else:
                empty_state("Ainda não há itens fechados para calcular a taxa por site.")
        with c2:
            fig=near_miss_fig_sites_criticos(fdf, altura=390)
            if fig is not None:
                plotly_chart_safe(fig,use_container_width=True)
            else:
                empty_state("Nenhum item crítico de prazo nos filtros aplicados.")
        tdf_divisao_resumo=near_miss_taxa_divisao_df(fdf)
        fig_div=near_miss_fig_taxa_fechamento_divisao(tdf_divisao_resumo, altura=340)
        if fig_div is not None:
            plotly_chart_safe(fig_div,use_container_width=True)
        else:
            empty_state("Ainda não há itens fechados para calcular a taxa consolidada por divisão.")
        fig_excesso = near_miss_fig_prazo_superior_45_site(fdf, altura=340)
        if fig_excesso is not None:
            plotly_chart_safe(fig_excesso, use_container_width=True)
        c3,c4=st.columns(2)
        with c3:
            by_site=fdf.groupby("Site",dropna=False).size().reset_index(name="Quantidade").sort_values("Quantidade",ascending=True)
            if not by_site.empty:
                fig=px.bar(by_site,x="Quantidade",y="Site",orientation="h",text="Quantidade",title="Quantidade de reports por site")
                fig.update_traces(texttemplate="%{text:.0f}",textposition="outside", marker_color="#2563eb")
                fig.update_layout(height=360,margin=dict(l=10,r=30,t=50,b=10),showlegend=False)
                plotly_chart_safe(fig,use_container_width=True)
        with c4:
            by_div=fdf.groupby("Divisão",dropna=False).size().reset_index(name="Quantidade").sort_values("Quantidade",ascending=True)
            if not by_div.empty:
                fig=px.bar(by_div,x="Quantidade",y="Divisão",orientation="h",text="Quantidade",title="Quantidade de reports por divisão")
                fig.update_traces(texttemplate="%{text:.0f}",textposition="outside", marker_color="#0f766e")
                fig.update_layout(height=360,margin=dict(l=10,r=30,t=50,b=10),showlegend=False)
                plotly_chart_safe(fig,use_container_width=True)

    with tabs[1]:
        prazo=fdf.groupby(["Site","Status do prazo"],dropna=False).size().reset_index(name="Quantidade")
        if not prazo.empty:
            fig=px.bar(prazo,x="Site",y="Quantidade",color="Status do prazo",text="Quantidade",title="Classificação por prazo e site", color_discrete_map=NEAR_MISS_STATUS_COLOR_MAP, category_orders={"Status do prazo": NEAR_MISS_STATUS_ORDER})
            fig.update_traces(texttemplate="%{text:.0f}",textposition="outside")
            fig.update_layout(height=430,margin=dict(l=10,r=10,t=50,b=70),xaxis_tickangle=-25)
            plotly_chart_safe(fig,use_container_width=True)
        tdf=near_miss_taxa_site_df(fdf)
        fig=near_miss_fig_taxa_fechamento_site(tdf, altura=380)
        if fig is not None:
            plotly_chart_safe(fig,use_container_width=True)
        fig_excesso=near_miss_fig_prazo_superior_45_site(fdf, altura=340)
        if fig_excesso is not None:
            plotly_chart_safe(fig_excesso,use_container_width=True)
    with tabs[2]:
        section("Insights executivos")
        criticos = near_miss_criticos_prazo_df(fdf)
        site_critico = criticos.groupby("Site").size().sort_values(ascending=False)
        hazard_critico = criticos.groupby("Hazard Type").size().sort_values(ascending=False)
        dept_critico = criticos.groupby("Departamento").size().sort_values(ascending=False)
        abertos_base = fdf[fdf["Fechamento"].isna()].copy()
        if not abertos_base.empty:
            hoje_ts = pd.Timestamp(date.today())
            abertos_base["Dias em aberto"] = (hoje_ts - abertos_base["Data"]).dt.days
        i1,i2,i3,i4,i5 = st.columns(5)
        with i1:
            kpi_card("Site com mais desvios", site_critico.index[0] if len(site_critico) else "—", f"{int(site_critico.iloc[0])} itens" if len(site_critico) else "Sem desvios críticos")
        with i2:
            kpi_card("Hazard mais recorrente", hazard_critico.index[0] if len(hazard_critico) else "—", f"{int(hazard_critico.iloc[0])} itens" if len(hazard_critico) else "Sem recorrência crítica")
        with i3:
            kpi_card("Departamento crítico", dept_critico.index[0] if len(dept_critico) else "—", f"{int(dept_critico.iloc[0])} itens" if len(dept_critico) else "Sem recorrência crítica")
        with i4:
            maior_aberto = int(abertos_base["Dias em aberto"].max()) if not abertos_base.empty and abertos_base["Dias em aberto"].notna().any() else 0
            kpi_card("Maior tempo aberto", f"{maior_aberto} dias", "Entre itens sem fechamento")
        with i5:
            kpi_card("Prazo >45 dias", len(near_miss_prazo_superior_45_df(fdf)), "Limite máximo do procedimento")
        c1,c2 = st.columns(2)
        with c1:
            pareto_status = fdf.groupby("Status do prazo", dropna=False).size().reset_index(name="Quantidade")
            if not pareto_status.empty:
                pareto_status["Status do prazo"] = pd.Categorical(pareto_status["Status do prazo"], categories=NEAR_MISS_STATUS_ORDER, ordered=True)
                pareto_status = pareto_status.sort_values("Status do prazo")
                fig = px.bar(pareto_status, x="Status do prazo", y="Quantidade", color="Status do prazo", text="Quantidade", title="Distribuição por status do prazo", color_discrete_map=NEAR_MISS_STATUS_COLOR_MAP, category_orders={"Status do prazo": NEAR_MISS_STATUS_ORDER})
                fig.update_traces(texttemplate="%{text:.0f}", textposition="outside")
                fig.update_layout(height=360, margin=dict(l=10,r=10,t=50,b=60), showlegend=False, xaxis_tickangle=-20)
                plotly_chart_safe(fig, use_container_width=True)
        with c2:
            fig=near_miss_fig_sites_criticos(fdf, altura=360)
            if fig is not None:
                plotly_chart_safe(fig, use_container_width=True)
        c3,c4 = st.columns(2)
        with c3:
            top_dept = fdf.groupby("Departamento", dropna=False).size().reset_index(name="Quantidade").sort_values("Quantidade", ascending=True).tail(10)
            if not top_dept.empty:
                fig = px.bar(top_dept, x="Quantidade", y="Departamento", orientation="h", text="Quantidade", title="Top departamentos por volume")
                fig.update_traces(texttemplate="%{text:.0f}", textposition="outside", marker_color="#0f766e")
                fig.update_layout(height=380, margin=dict(l=10,r=30,t=50,b=10), showlegend=False)
                plotly_chart_safe(fig, use_container_width=True)
        with c4:
            top_hazard = fdf.groupby("Hazard Type", dropna=False).size().reset_index(name="Quantidade").sort_values("Quantidade", ascending=True).tail(10)
            if not top_hazard.empty:
                fig = px.bar(top_hazard, x="Quantidade", y="Hazard Type", orientation="h", text="Quantidade", title="Top hazards por volume")
                fig.update_traces(texttemplate="%{text:.0f}", textposition="outside", marker_color="#7c3aed")
                fig.update_layout(height=380, margin=dict(l=10,r=30,t=50,b=10), showlegend=False, yaxis_title="")
                plotly_chart_safe(fig, use_container_width=True)
    with tabs[3]:
        mensal=fdf.dropna(subset=["Mês"]).groupby("Mês").size().reset_index(name="Quantidade")
        if not mensal.empty:
            fig=px.line(mensal,x="Mês",y="Quantidade",markers=True,title="Evolução mensal de Concern Reports")
            fig.update_layout(height=400,margin=dict(l=10,r=10,t=50,b=10))
            plotly_chart_safe(fig,use_container_width=True)
        mensal_status=fdf.dropna(subset=["Mês"]).groupby(["Mês","Status do prazo"]).size().reset_index(name="Quantidade")
        if not mensal_status.empty:
            fig=px.bar(mensal_status,x="Mês",y="Quantidade",color="Status do prazo",title="Evolução mensal por status do prazo", color_discrete_map=NEAR_MISS_STATUS_COLOR_MAP, category_orders={"Status do prazo": NEAR_MISS_STATUS_ORDER})
            fig.update_layout(height=420,margin=dict(l=10,r=10,t=50,b=10))
            plotly_chart_safe(fig,use_container_width=True)
    with tabs[4]:
        crit=fdf[fdf["Acompanhamento"]=="Acompanhar"].copy()
        section("Itens para acompanhamento")
        if crit.empty:
            empty_state("Nenhum item crítico de prazo nos filtros aplicados.")
        else:
            show=crit.sort_values(["Status do prazo","Prazo"],na_position="last")[["Descrição","Status do prazo","Prazo","Prazo atribuído (dias)","Prazo superior a 45 dias","Fechamento","Data","ID","Tipo","Site","Divisão","Status","Responsável","Hazard Type"]].copy()
            show = show.rename(columns={"Data": "Data da abertura"})
            for c in ["Prazo","Fechamento","Data da abertura"]:
                show[c]=show[c].dt.strftime("%d/%m/%Y").fillna("—")
            st.dataframe(show, use_container_width=True, hide_index=True)
            download_excel_button("Baixar itens para acompanhamento", "near_miss_acompanhamento.xlsx", {"Acompanhamento": show})

def near_miss_central_pendencias(db,u):
    header("Central de Pendências Near Miss", "Acompanhamento operacional de Concern Reports abertos, vencidos, próximos do prazo e previstos para vencer no mês.")
    df=near_miss_df(db)
    if df.empty:
        empty_state("Base de Concern Reports ainda não carregada.")
        return
    pend=near_miss_pendencias_abertas_df(df)
    if pend.empty:
        kpi_card("Pendências abertas", 0, "Nenhum Concern Report aberto")
        empty_state("Não há itens abertos para acompanhamento.")
        return
    with st.expander("Filtros", expanded=True):
        c1,c2,c3=st.columns(3)
        with c1:
            sites=st.multiselect("Site", sorted(pend["Site código"].dropna().unique()), default=sorted(pend["Site código"].dropna().unique()), key="nm_pend_sites")
        with c2:
            categorias=st.multiselect("Categoria", ["Vencido","Próximo do vencimento","Vence este mês","Sem prazo","Em prazo"], default=["Vencido","Próximo do vencimento","Vence este mês","Sem prazo"], key="nm_pend_categorias")
        with c3:
            responsaveis=st.multiselect("Responsável", sorted(pend["Responsável"].dropna().unique()), key="nm_pend_resp")
    if sites:
        pend=pend[pend["Site código"].isin(sites)]
    if categorias:
        pend=pend[pend["Categoria de pendência"].isin(categorias)]
    if responsaveis:
        pend=pend[pend["Responsável"].isin(responsaveis)]
    total=len(pend)
    vencidos=int((pend["Categoria de pendência"]=="Vencido").sum())
    prox=int((pend["Categoria de pendência"]=="Próximo do vencimento").sum())
    mes=int((pend["Categoria de pendência"]=="Vence este mês").sum())
    sem=int((pend["Categoria de pendência"]=="Sem prazo").sum())
    cols=st.columns(5)
    for col,(label,val,help_txt) in zip(cols,[
        ("Abertos monitorados",total,"Itens sem data de fechamento"),
        ("Vencidos",vencidos,"Prazo já excedido"),
        ("Próximos 15 dias",prox,"Itens próximos do vencimento"),
        ("Vencem no mês",mes,"Prazo dentro do mês atual"),
        ("Sem prazo",sem,"Itens abertos sem prazo informado"),
    ]):
        with col:
            kpi_card(label,val,help_txt)
    c1,c2=st.columns(2)
    with c1:
        cat=pend.groupby("Categoria de pendência", dropna=False).size().reset_index(name="Quantidade")
        ordem=["Vencido","Próximo do vencimento","Vence este mês","Sem prazo","Em prazo"]
        cat["Categoria de pendência"]=pd.Categorical(cat["Categoria de pendência"], categories=ordem, ordered=True)
        cat=cat.sort_values("Categoria de pendência")
        cores={"Vencido":"#7f1d1d","Próximo do vencimento":"#facc15","Vence este mês":"#fb923c","Sem prazo":"#94a3b8","Em prazo":"#fde68a"}
        fig=px.bar(cat,x="Categoria de pendência",y="Quantidade",color="Categoria de pendência",text="Quantidade",title="Pendências por criticidade",color_discrete_map=cores)
        fig.update_traces(texttemplate="%{text:.0f}",textposition="outside")
        fig.update_layout(height=360,margin=dict(l=10,r=10,t=50,b=70),showlegend=False,xaxis_tickangle=-25)
        plotly_chart_safe(fig,use_container_width=True)
    with c2:
        site=pend[pend["Categoria de pendência"].isin(["Vencido","Próximo do vencimento","Vence este mês","Sem prazo"])].groupby("Site", dropna=False).size().reset_index(name="Quantidade").sort_values("Quantidade", ascending=True).tail(10)
        if not site.empty:
            fig=px.bar(site,x="Quantidade",y="Site",orientation="h",text="Quantidade",title="Sites com mais pendências")
            fig.update_traces(texttemplate="%{text:.0f}",textposition="outside",marker_color="#dc2626")
            fig.update_layout(height=360,margin=dict(l=10,r=30,t=50,b=10),showlegend=False)
            plotly_chart_safe(fig,use_container_width=True)
    tabs=st.tabs(["Vencidos", "Próximos do vencimento", "Vencem no mês", "Todos os abertos"])
    conjuntos=[
        pend[pend["Categoria de pendência"]=="Vencido"],
        pend[pend["Categoria de pendência"]=="Próximo do vencimento"],
        pend[pend["Categoria de pendência"]=="Vence este mês"],
        pend,
    ]
    for i,(tab,base) in enumerate(zip(tabs,conjuntos)):
        with tab:
            if base.empty:
                empty_state("Nenhum item nesta categoria.")
            else:
                base=base.sort_values(["Categoria de pendência","Prazo","Dias em aberto"], ascending=[True, True, False], na_position="last")
                show=near_miss_formata_tabela_pendencias(base)
                st.dataframe(show,use_container_width=True,hide_index=True)
                download_excel_button("Baixar lista", f"near_miss_pendencias_{i+1}.xlsx", {"Pendencias": show}, key=f"nm_pend_download_{i}")

def near_miss_atualizar_base(db,u):
    header("Atualizar Base Near Miss", "Importe um ou mais arquivos Excel de Concern Reports para sobrescrever a base atual do módulo.")
    if not can_edit(u):
        st.warning("Usuário sem permissão para atualizar a base.")
        return
    files=st.file_uploader("Selecione os arquivos Excel", type=["xlsx","xls"], accept_multiple_files=True, key="nm_upload_files")
    if not files:
        empty_state("Selecione os arquivos de Concern Reports para pré-visualizar a atualização.")
        return
    frames=[]; erros=[]
    for f in files:
        try:
            frames.append(parse_near_miss_excel(f, f.name))
        except Exception as e:
            erros.append(f"{f.name}: {e}")
    if erros:
        st.error("\n".join(erros))
    df=pd.concat([x for x in frames if x is not None and not x.empty],ignore_index=True).drop_duplicates("id_cr") if frames else pd.DataFrame()
    if df.empty:
        st.warning("Nenhuma linha válida foi reconhecida.")
        return
    c1,c2,c3,c4=st.columns(4)
    c1.metric("Linhas reconhecidas", len(df))
    c2.metric("Sites", df["site_codigo"].nunique())
    c3.metric("Tipos", df["tipo"].nunique())
    c4.metric("Arquivos", len(files))
    preview=df.copy().head(80)
    for c in ["data_ocorrencia","closure_due_date","closed_date"]:
        preview[c]=pd.to_datetime(preview[c],errors="coerce").dt.strftime("%d/%m/%Y").fillna("—")
    st.dataframe(preview, use_container_width=True, hide_index=True)
    if st.button("Confirmar atualização e sobrescrever base", type="primary", use_container_width=True):
        try:
            db.query(NearMissRegistro).delete()
            db.flush()
            records=[]
            for rec in df.to_dict(orient="records"):
                clean={}
                for k,v in rec.items():
                    if pd.isna(v): clean[k]=None
                    elif isinstance(v,pd.Timestamp): clean[k]=v.date()
                    else: clean[k]=v
                records.append(clean)
            db.bulk_insert_mappings(NearMissRegistro, records)
            for f in files:
                db.add(NearMissUploadHistorico(nome_arquivo=f.name, linhas_importadas=len(records), usuario=u.nome if u else "Sistema", observacoes="Base sobrescrita"))
            registrar_log(db,u,"Near Miss","NearMissRegistro",None,"atualizar_base",observacao=f"{len(records)} registros importados")
            db.commit()
            st.cache_data.clear()
            st.success(f"Base atualizada com {len(records)} registros.")
            st.rerun()
        except Exception as e:
            db.rollback()
            st.error(f"Erro ao atualizar base: {e}")

def near_miss_base_page(db,u):
    header("Base de Concern Reports", "Consulta analítica da base importada no módulo Near Miss.")
    df=near_miss_df(db)
    if df.empty:
        empty_state("Sem dados na base.")
        return
    with st.expander("Filtros", expanded=True):
        sites=st.multiselect("Site", sorted(df["Site código"].dropna().unique()), key="nm_base_sites")
        status=st.multiselect("Status do prazo", sorted(df["Status do prazo"].dropna().unique()), key="nm_base_status")
        tipos=st.multiselect("Tipo", sorted(df["Tipo"].dropna().unique()), key="nm_base_tipo")
    fdf=near_miss_filtrar_df(df, sites=sites, tipos=tipos, status_prazo=status)
    show=fdf.copy()
    for c in ["Data","Mês","Prazo","Fechamento"]:
        show[c]=show[c].dt.strftime("%d/%m/%Y").fillna("—")
    st.dataframe(show, use_container_width=True, hide_index=True)
    download_excel_button("Exportar base filtrada", "base_near_miss.xlsx", {"Base": show})

def near_miss_relatorios_page(db,u):
    header("Relatórios Near Miss", "Exportações consolidadas do módulo de Concern Reports.")
    df=near_miss_df(db)
    if df.empty:
        empty_state("Sem dados para exportar.")
        return
    base=df.copy()
    for c in ["Data","Mês","Prazo","Fechamento"]:
        base[c]=base[c].dt.strftime("%d/%m/%Y").fillna("—")
    resumo_site=df.groupby(["Site","Status do prazo"],dropna=False).size().reset_index(name="Quantidade")
    resumo_div=df.groupby(["Divisão","Status do prazo"],dropna=False).size().reset_index(name="Quantidade")
    acompanhamento=base[base["Acompanhamento"]=="Acompanhar"].copy()
    download_excel_button("Baixar relatório completo", "relatorio_near_miss.xlsx", {"Base": base, "Resumo_Site": resumo_site, "Resumo_Divisao": resumo_div, "Acompanhamento": acompanhamento})

def render_sidebar(db,u):
    mod=st.session_state.get("modulo","home")
    if (
        mod=="home"
        or (mod=="nr12" and st.session_state.get("page_nr12",NR12_HOME_PAGE)==NR12_HOME_PAGE)
        or (mod=="ehs" and st.session_state.get("page_ehs",EHS_HOME_PAGE)==EHS_HOME_PAGE)
        or (mod=="energia" and st.session_state.get("page_energia",ENERGIA_HOME_PAGE)==ENERGIA_HOME_PAGE)
        or (mod=="nearmiss" and st.session_state.get("page_nearmiss",NEARMISS_HOME_PAGE)==NEARMISS_HOME_PAGE)
    ):
        return
    st.sidebar.markdown("### Navegação")
    if st.sidebar.button("🏠 Voltar para a tela inicial",use_container_width=True):
        st.session_state.modulo="home"
        st.rerun()
    if st.sidebar.button("❔ Ajuda rápida", use_container_width=True, key="sidebar_ajuda_rapida"):
        st.session_state.modulo="ajuda"
        st.rerun()
    st.sidebar.divider()
    if mod=="ajuda":
        return
    if mod=="nr12":
        all_pages=[NR12_HOME_PAGE]
        for nome,cfg in NR12_SUBMODULOS.items():
            for p in cfg["paginas"]:
                if p=="Logs do Sistema" and not can_admin(u):
                    continue
                if p not in all_pages:
                    all_pages.append(p)
        current=st.session_state.get("page_nr12",NR12_HOME_PAGE)
        if current not in all_pages:
            current=NR12_HOME_PAGE
            st.session_state.page_nr12=current
        if current==NR12_HOME_PAGE:
            st.sidebar.info("Selecione um submódulo na tela principal.")
            selected=st.sidebar.radio(NOME_MODULO_MAQUINAS,[NR12_HOME_PAGE],key="nav_nr12_home")
            st.session_state.page_nr12=selected
        else:
            sub_atual=None
            for nome,cfg in NR12_SUBMODULOS.items():
                if current in cfg["paginas"]:
                    sub_atual=nome
                    break
            sub_opcoes=list(NR12_SUBMODULOS.keys())
            idx=sub_opcoes.index(sub_atual) if sub_atual in sub_opcoes else 0
            sub=st.sidebar.selectbox("Submódulo",sub_opcoes,index=idx,key="submodulo_nr12")
            pages=[p for p in NR12_SUBMODULOS[sub]["paginas"] if p!="Logs do Sistema" or can_admin(u)]
            if current not in pages:
                current=pages[0] if pages else NR12_HOME_PAGE
                st.session_state.page_nr12=current
            selected=st.sidebar.radio(sub,pages,key="nav_nr12")
            st.session_state.page_nr12=selected
            if st.sidebar.button("⬅️ Voltar aos submódulos",use_container_width=True):
                st.session_state.page_nr12=NR12_HOME_PAGE
                st.rerun()
    elif mod=="ehs":
        all_pages=[EHS_HOME_PAGE]
        for nome,cfg in EHS_SUBMODULOS.items():
            for p in cfg["paginas"]:
                if p=="Logs do Sistema" and not can_admin(u):
                    continue
                if p not in all_pages:
                    all_pages.append(p)
        current=st.session_state.get("page_ehs",EHS_HOME_PAGE)
        if current not in all_pages:
            current=EHS_HOME_PAGE
            st.session_state.page_ehs=current
        if current==EHS_HOME_PAGE:
            st.sidebar.info("Selecione um submódulo na tela principal.")
            selected=st.sidebar.radio("Auditoria Cruzada de Diretrizes EHS",[EHS_HOME_PAGE],key="nav_ehs_home")
            st.session_state.page_ehs=selected
        else:
            sub_atual=None
            for nome,cfg in EHS_SUBMODULOS.items():
                if current in cfg["paginas"]:
                    sub_atual=nome
                    break
            sub_opcoes=list(EHS_SUBMODULOS.keys())
            idx=sub_opcoes.index(sub_atual) if sub_atual in sub_opcoes else 0
            sub=st.sidebar.selectbox("Submódulo",sub_opcoes,index=idx,key="submodulo_ehs")
            pages=[p for p in EHS_SUBMODULOS[sub]["paginas"] if p!="Logs do Sistema" or can_admin(u)]
            if current not in pages:
                current=pages[0] if pages else EHS_HOME_PAGE
                st.session_state.page_ehs=current
            selected=st.sidebar.radio(sub,pages,key="nav_ehs")
            st.session_state.page_ehs=selected
            if st.sidebar.button("⬅️ Voltar aos submódulos",use_container_width=True,key="btn_voltar_submodulos_ehs"):
                st.session_state.page_ehs=EHS_HOME_PAGE
                st.rerun()
    elif mod=="energia":
        all_pages=[ENERGIA_HOME_PAGE]
        for nome,cfg in ENERGIA_SUBMODULOS.items():
            for p in cfg["paginas"]:
                if p not in all_pages:
                    all_pages.append(p)
        current=st.session_state.get("page_energia",ENERGIA_HOME_PAGE)
        if current not in all_pages:
            current=ENERGIA_HOME_PAGE
            st.session_state.page_energia=current
        if current==ENERGIA_HOME_PAGE:
            st.sidebar.info("Selecione um submódulo na tela principal.")
            selected=st.sidebar.radio("Controle de Energia e Emissões",[ENERGIA_HOME_PAGE],key="nav_energia_home")
            st.session_state.page_energia=selected
        else:
            sub_atual=None
            for nome,cfg in ENERGIA_SUBMODULOS.items():
                if current in cfg["paginas"]:
                    sub_atual=nome
                    break
            sub_opcoes=list(ENERGIA_SUBMODULOS.keys())
            idx=sub_opcoes.index(sub_atual) if sub_atual in sub_opcoes else 0
            sub=st.sidebar.selectbox("Submódulo",sub_opcoes,index=idx,key="submodulo_energia")
            pages=ENERGIA_SUBMODULOS[sub]["paginas"]
            if current not in pages:
                current=pages[0] if pages else ENERGIA_HOME_PAGE
                st.session_state.page_energia=current
            selected=st.sidebar.radio(sub,pages,key="nav_energia")
            st.session_state.page_energia=selected
            if st.sidebar.button("⬅️ Voltar aos submódulos",use_container_width=True,key="btn_voltar_submodulos_energia"):
                st.session_state.page_energia=ENERGIA_HOME_PAGE
                st.rerun()

    elif mod=="nearmiss":
        all_pages=[NEARMISS_HOME_PAGE]
        for nome,cfg in NEARMISS_SUBMODULOS.items():
            for p in cfg["paginas"]:
                if p not in all_pages:
                    all_pages.append(p)
        current=st.session_state.get("page_nearmiss",NEARMISS_HOME_PAGE)
        if current not in all_pages:
            current=NEARMISS_HOME_PAGE
            st.session_state.page_nearmiss=current
        if current==NEARMISS_HOME_PAGE:
            st.sidebar.info("Selecione um submódulo na tela principal.")
            selected=st.sidebar.radio("Near Miss",[NEARMISS_HOME_PAGE],key="nav_nearmiss_home")
            st.session_state.page_nearmiss=selected
        else:
            sub_atual=None
            for nome,cfg in NEARMISS_SUBMODULOS.items():
                if current in cfg["paginas"]:
                    sub_atual=nome
                    break
            sub_opcoes=list(NEARMISS_SUBMODULOS.keys())
            idx=sub_opcoes.index(sub_atual) if sub_atual in sub_opcoes else 0
            sub=st.sidebar.selectbox("Submódulo",sub_opcoes,index=idx,key="submodulo_nearmiss")
            pages=NEARMISS_SUBMODULOS[sub]["paginas"]
            if current not in pages:
                current=pages[0] if pages else NEARMISS_HOME_PAGE
                st.session_state.page_nearmiss=current
            selected=st.sidebar.radio(sub,pages,key="nav_nearmiss")
            st.session_state.page_nearmiss=selected
            if st.sidebar.button("⬅️ Voltar aos submódulos",use_container_width=True,key="btn_voltar_submodulos_nearmiss"):
                st.session_state.page_nearmiss=NEARMISS_HOME_PAGE
                st.rerun()

def route(db,u):
    mod=st.session_state.get("modulo","home")
    if mod != "home":
        render_breadcrumb()
    if mod=="home": home_page(db,u)
    elif mod=="ajuda":
        ajuda_rapida_page(db,u)
    elif mod=="nr12":
        paginas={
            NR12_HOME_PAGE:nr12_submodulos_home,
            NOME_DASH_MAQUINAS:nr12_dashboard,
            "Central de Pendências":nr12_central_pendencias,
            "Calendário de Auditorias e Inspeções":nr12_calendario,
            "Inventário de Máquinas":nr12_inventario,
            NOME_DOCS_MAQUINAS:nr12_documentos,
            "Checklists e Inspeções":nr12_checklists,
            "Base de Checklists de Proteções":nr12_base_checklists,
            "Regras de Frequência de Inspeções":nr12_regras_frequencia,
            NOME_PAC_MAQUINAS:nr12_pac,
            NOME_RELATORIOS_MAQUINAS:nr12_relatorios,
            "Logs do Sistema":logs_sistema_page,
        }
        page=st.session_state.get("page_nr12",NR12_HOME_PAGE)
        paginas.get(page,nr12_submodulos_home)(db,u)
    elif mod=="ehs":
        paginas={
            EHS_HOME_PAGE: ehs_submodulos_home,
            "Dashboard Auditoria Cruzada": ehs_dashboard,
            "Planejamento de Auditorias": ehs_planejamento,
            "Calendário de Auditorias": ehs_calendario,
            "Checklist Diretrizes de EHS": ehs_checklist,
            "PAC Auditoria Cruzada": ehs_pac,
            "Base do Checklist EHS": ehs_base_checklist,
            "Relatórios Auditoria Cruzada": ehs_relatorios,
            "Logs do Sistema": logs_sistema_page,
        }
        page=st.session_state.get("page_ehs",EHS_HOME_PAGE)
        paginas.get(page,ehs_submodulos_home)(db,u)
    elif mod=="energia":
        paginas={
            ENERGIA_HOME_PAGE: energia_submodulos_home,
            "Dashboard Energia e CO₂": energia_dashboard,
            "Atualizar Base": energia_atualizar_base,
            "Actual Hours": energia_actual_hours_page,
            "Tabela Executiva": energia_tabela_executiva_page,
            "Base Consolidada": energia_base_consolidada_page,
            "Relatórios Energia": energia_relatorios_page,
            "Parâmetros": energia_parametros_page,
        }
        page=st.session_state.get("page_energia",ENERGIA_HOME_PAGE)
        paginas.get(page,energia_submodulos_home)(db,u)

    elif mod=="nearmiss":
        paginas={
            NEARMISS_HOME_PAGE: near_miss_submodulos_home,
            "Dashboard Near Miss": near_miss_dashboard,
            "Central de Pendências Near Miss": near_miss_central_pendencias,
            "Atualizar Base Near Miss": near_miss_atualizar_base,
            "Base de Concern Reports": near_miss_base_page,
            "Relatórios Near Miss": near_miss_relatorios_page,
        }
        page=st.session_state.get("page_nearmiss",NEARMISS_HOME_PAGE)
        paginas.get(page,near_miss_submodulos_home)(db,u)

def main():
    if "modulo" not in st.session_state:
        st.session_state.modulo="home"
    apply_theme(); hide_sidebar_on_home()
    if not st.session_state.get("_db_initialized"):
        init_db()
        st.session_state["_db_initialized"] = True
    db=SessionLocal()
    try:
        mod_atual = st.session_state.get("modulo", "home")
        page_nr12_atual = st.session_state.get("page_nr12", NR12_HOME_PAGE)
        page_ehs_atual = st.session_state.get("page_ehs", EHS_HOME_PAGE)
        page_energia_atual = st.session_state.get("page_energia", ENERGIA_HOME_PAGE)
        page_nearmiss_atual = st.session_state.get("page_nearmiss", NEARMISS_HOME_PAGE)
        tela_landing = (
            (mod_atual == "home")
            or (mod_atual == "nr12" and page_nr12_atual == NR12_HOME_PAGE)
            or (mod_atual == "ehs" and page_ehs_atual == EHS_HOME_PAGE)
            or (mod_atual == "energia" and page_energia_atual == ENERGIA_HOME_PAGE)
            or (mod_atual == "nearmiss" and page_nearmiss_atual == NEARMISS_HOME_PAGE)
        )
        location="main" if tela_landing else "sidebar"
        u=user_selector(db,location=location)
        render_sidebar(db,u)
        route(db,u)
    finally:
        db.close()
if __name__=="__main__": main()
