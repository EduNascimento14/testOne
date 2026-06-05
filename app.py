
# -*- coding: utf-8 -*-
"""
Plataforma Integrada EHS — NR-12 e Auditorias Cruzadas
Arquivo monolítico Streamlit. Renomeie para plataforma_ehs_integrada.py e rode:
streamlit run plataforma_ehs_integrada.py
"""

# ============================================================
# 1. Imports
# ============================================================
import os, io, re, math, unicodedata, logging, calendar, json, zlib, base64
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

# ============================================================
# 3. Constantes
# ============================================================
# Camada de nomenclatura visual — mantém nomes técnicos internos para compatibilidade de banco/código.
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
    ocultar = (
        (mod == "home")
        or (mod == "nr12" and page_nr12 == (NR12_HOME_PAGE if "NR12_HOME_PAGE" in globals() else "Submódulos da Sustentação"))
        or (mod == "ehs" and page_ehs == (EHS_HOME_PAGE if "EHS_HOME_PAGE" in globals() else "Submódulos da Auditoria Cruzada"))
        or (mod == "energia" and page_energia == (ENERGIA_HOME_PAGE if "ENERGIA_HOME_PAGE" in globals() else "Submódulos de Energia e Emissões"))
    )
    if ocultar:
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



# ============================================================
# 5B. Modelos SQLAlchemy — Controle de Energia e Emissões
# ============================================================
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

# ============================================================
# 6. Seed inicial
# ============================================================
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
    # Migrações idempotentes para bancos SQLite já existentes.
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
    # Cria versões iniciais somente quando ainda não existem. Depois disso, as alterações
    # feitas pelo usuário no app são preservadas e não são sobrescritas pelo hardcoded.
    tipos = {t for t, in db.query(ChecklistItemNR12.tipo_checklist).distinct().all()}
    for tipo in sorted(tipos):
        if not db.query(ChecklistVersaoMaquinas).filter_by(tipo_checklist=tipo).first():
            criar_versao_checklist_maquinas(db, tipo, "Sistema", "Versão inicial migrada do checklist padrão")
    if not db.query(ChecklistVersaoEHS).first():
        criar_versao_checklist_ehs(db, "Sistema", "Versão inicial migrada do checklist de Diretrizes EHS")

def sync_checklists_base(db):
    # Usa CHECKLIST_NR12/CHECKLIST_EHS apenas como seed inicial. Não sobrescreve perguntas editadas no app.
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

def energia_mapa_sites_df(r12_site):
    """Monta a base geográfica por site para o mapa executivo de energia e emissões."""
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

def energia_mapa_brasil_fig(map_df, metrica_label, usar_irec=True):
    """Cria mapa do Brasil com bolhas por unidade produtiva.

    Usa scatter_geo para não depender de token de mapa ou internet.
    """
    if map_df is None or map_df.empty:
        return None
    metric_col, unidade = ENERGIA_MAP_METRICAS.get(metrica_label, ("consumo_total_kwh", "kWh"))
    df = map_df.copy()
    if metric_col not in df.columns:
        df[metric_col] = 0
    df["Valor selecionado"] = pd.to_numeric(df[metric_col], errors="coerce").fillna(0)
    # Para eficiência, a cor representa a taxa e o tamanho representa consumo total, evitando bolha nula/invertida.
    df["Tamanho da bolha"] = df["Valor selecionado"].abs()
    if metrica_label == "Eficiência energética R12":
        df["Tamanho da bolha"] = pd.to_numeric(df["consumo_total_kwh"], errors="coerce").fillna(0).abs()
    if float(df["Tamanho da bolha"].max() or 0) <= 0:
        df["Tamanho da bolha"] = 1
    df["Valor formatado"] = df["Valor selecionado"].apply(lambda x: energia_fmt_val(x, "money" if unidade == "BRL" else "numero"))
    fig = px.scatter_geo(
        df,
        lat="Latitude",
        lon="Longitude",
        size="Tamanho da bolha",
        color="Valor selecionado",
        text="Site",
        hover_name="Unidade",
        hover_data={
            "Site": True,
            "Cidade/UF": True,
            "Grupo": True,
            "Valor formatado": True,
            "Latitude": False,
            "Longitude": False,
            "Tamanho da bolha": False,
            "Valor selecionado": False,
        },
        color_continuous_scale="YlOrRd",
        size_max=54,
        title=f"Mapa Brasil — {metrica_label}",
    )
    fig.update_traces(
        textposition="top center",
        marker=dict(line=dict(width=1.2, color="#ffffff"), opacity=0.88),
        hovertemplate="<b>%{hovertext}</b><br>Site: %{customdata[0]}<br>Local: %{customdata[1]}<br>Grupo: %{customdata[2]}<br>Valor: %{customdata[3]} " + unidade + "<extra></extra>",
    )
    fig.update_geos(
        projection_type="mercator",
        showland=True,
        landcolor="#f8fafc",
        showocean=True,
        oceancolor="#e0f2fe",
        showcountries=True,
        countrycolor="#94a3b8",
        showsubunits=True,
        subunitcolor="#cbd5e1",
        showframe=False,
        showcoastlines=True,
        coastlinecolor="#94a3b8",
        lataxis_range=[-35, 6],
        lonaxis_range=[-75, -33],
    )
    fig.update_layout(
        template="plotly_white",
        height=560,
        margin=dict(l=0, r=0, t=60, b=0),
        coloraxis_colorbar=dict(title=unidade),
        title=dict(x=0.02, xanchor="left"),
    )
    if usar_irec and "I-REC" in metrica_label:
        fig.add_annotation(
            text="I-REC considerado conforme data configurada nos parâmetros.",
            x=0.01, y=0.02, xref="paper", yref="paper", showarrow=False,
            bgcolor="rgba(236,253,245,0.92)", bordercolor="#16a34a", borderwidth=1,
            font=dict(size=11, color="#166534"),
        )
    return fig

def energia_tendencia_metas(df_scope, usar_irec=False, db=None):
    """Gera séries mensais R12 de emissões e eficiência comparadas contra a meta.

    Para evitar distorções no início da série, a eficiência só é exibida quando há
    janela R12 completa com consumo e Actual Hours. Também remove outliers fortes
    de eficiência por IQR, preservando a tendência operacional.
    """
    if df_scope is None or df_scope.empty:
        return pd.DataFrame()
    work = df_scope.copy()
    work["Mês"] = pd.to_datetime(work["Mês"]).dt.date
    meses = sorted(work["Mês"].dropna().unique())
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

    # Só considera meses a partir da primeira janela R12 completa de energia e horas.
    meses_com_energia = sorted(work.loc[work["consumo_total_kwh"].fillna(0) > 0, "Mês"].dropna().unique())
    meses_com_horas = sorted(work.loc[work["actual_hours"].fillna(0) > 0, "Mês"].dropna().unique())
    primeiro_mes_valido = None
    candidatos = []
    if meses_com_energia:
        candidatos.append((pd.Timestamp(min(meses_com_energia)) + pd.DateOffset(months=11)).date())
    if meses_com_horas:
        candidatos.append((pd.Timestamp(min(meses_com_horas)) + pd.DateOffset(months=11)).date())
    if candidatos:
        primeiro_mes_valido = max(candidatos)

    rows = []
    for mes in meses:
        if primeiro_mes_valido and mes < primeiro_mes_valido:
            continue
        ini = energia_r12_start(mes)
        f12 = work[(pd.to_datetime(work["Mês"]) >= pd.to_datetime(ini)) & (pd.to_datetime(work["Mês"]) <= pd.to_datetime(mes))]
        # Exige janela R12 completa. Evita valores iniciais inflados/instáveis por poucas horas ou poucos meses.
        if f12["Mês"].nunique() < 12:
            continue
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
    metas = energia_tendencia_metas(df, usar_irec, db)
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

# ============================================================
# 11. Componentes de UI
# ============================================================
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

# ============================================================
# 12. Páginas comuns
# ============================================================

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
    section("Visão geral integrada")
    module_colors = {
        "Máquinas": ("#2563eb", "#eff6ff"),
        "Auditoria EHS": ("#7c3aed", "#f5f3ff"),
        "Energia": ("#16a34a", "#ecfdf5"),
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
    header("Plataforma Integrada EHS","Sustentação de Proteções de Máquinas, Auditorias Cruzadas e Controle de Energia e Emissões")
    dashboard_integrado(db,u)
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
        st.plotly_chart(px.histogram(dfm, x="Site", color="Status de Proteção", barmode="group", title="Status de conformidade por unidade", color_discrete_map=STATUS_COLOR_MAP).update_layout(template="plotly_white"), use_container_width=True)
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

    section("Evolução esperada da adequação de proteções de máquinas")
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
    pr=dfm[dfm["Status de Proteção"]=="Não conforme"] if not dfm.empty else pd.DataFrame()
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

    # 2) Cadastrar máquina
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

    # 3) Editar máquina
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
                    registrar_log(db,u,NOME_DOCS_MAQUINAS,"DocumentoNR12",None,"criar",observacao=f"Documento {tipo} salvo para {m.codigo}")
                    db.commit()
                    st.success("Documento salvo.")
                    st.rerun()

def nr12_checklists(db,u):
    header("Checklists e Inspeções de Proteções de Máquinas", "Registro por máquina, pontuação e geração automática de PAC")
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

    # 2) Tipo de checklist e checklist
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
        if not agg.empty: st.plotly_chart(px.bar(agg,x="Site",y="Quantidade",color="Status",barmode="group",title="Eventos por site e status").update_layout(template="plotly_white"), use_container_width=True)
        st.dataframe(agg, use_container_width=True, hide_index=True)
    with t3:
        agg=f.groupby(["Responsável","Status"], as_index=False).size().rename(columns={"size":"Quantidade"}) if not f.empty else pd.DataFrame()
        if not agg.empty: st.plotly_chart(px.bar(agg,x="Responsável",y="Quantidade",color="Status",barmode="group",title="Eventos por responsável e status").update_layout(template="plotly_white"), use_container_width=True)
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

    # 1) Consulta
    df=df_pac_nr12(db,ids)
    section("Consulta")
    if not df.empty:
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        empty_state("Nenhum PAC.")
    download_excel_button("Exportar PAC Proteções de Máquinas Excel","pac_nr12.xlsx",{"PAC":df})

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

# ============================================================
# 14. Páginas Auditoria Cruzada
# ============================================================
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
        # Fallback para bases antigas: usa RequisitoEHS diretamente, ainda com snapshot.
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
            st.plotly_chart(px.bar(agg, x="Site", y="Quantidade", color="Status", barmode="group", title="Auditorias por site e status").update_layout(template="plotly_white"), use_container_width=True)
        else:
            empty_state("Sem dados para os filtros selecionados.")
        st.dataframe(agg, use_container_width=True, hide_index=True)
    with t3:
        agg = f.groupby(["Responsável", "Status"], as_index=False).size().rename(columns={"size":"Quantidade"}) if not f.empty else pd.DataFrame()
        if not agg.empty:
            st.plotly_chart(px.bar(agg, x="Responsável", y="Quantidade", color="Status", barmode="group", title="Auditorias por responsável e status").update_layout(template="plotly_white"), use_container_width=True)
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


# ============================================================
# 14B. Módulo Controle de Energia e Emissões
# ============================================================

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
    # Os fatores abaixo ficam apenas como referência/legado. As emissões oficiais são importadas da planilha EMISSOES.
    "fator_emissao_eletricidade_kgco2_kwh": ("0", "Legado: não utilizado no cálculo. As emissões de energia elétrica são importadas da planilha EMISSOES."),
    "fator_emissao_gas_kgco2_kwh": ("0", "Legado: não utilizado no cálculo. As emissões de gás natural são importadas da planilha EMISSOES."),
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
    # Coordenadas aproximadas das unidades produtivas para visualização geográfica executiva.
    "CAC": {"latitude": -29.9511, "longitude": -51.0930, "cidade": "Cachoeirinha", "uf": "RS"},
    "JAC": {"latitude": -23.3053, "longitude": -45.9658, "cidade": "Jacareí", "uf": "SP"},
    "JUN": {"latitude": -23.1857, "longitude": -46.8978, "cidade": "Jundiaí", "uf": "SP"},
    "PER": {"latitude": -23.4082, "longitude": -46.7465, "cidade": "Perus", "uf": "SP"},
    "SJC": {"latitude": -23.2237, "longitude": -45.9009, "cidade": "São José dos Campos", "uf": "SP"},
    "DIA": {"latitude": -23.6865, "longitude": -46.6234, "cidade": "Diadema", "uf": "SP"},
}
ENERGIA_MAP_METRICAS = {
    "Consumo elétrico R12": ("consumo_eletrico_kwh", "kWh"),
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

# Carga inicial bruta de Actual Hours extraída da planilha Brazil Absorption Summary FY26.xls.
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



# Carga inicial de energia, gás e emissões extraída dos arquivos enviados:
# - GAS_ENERGIA_CONTROLE_MENSAL 01-06-2026 19-27-03.xlsx
# - EMISSOES 04-06-2026 18-34-53.xlsx
# Mantida comprimida para preservar o app monolítico e permitir primeira execução já populada.
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


def energia_df_registros(db):
    regs = db.query(EnergiaRegistro).order_by(EnergiaRegistro.mes_ref, EnergiaRegistro.site_codigo, EnergiaRegistro.fonte).all()
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
            # Emissões oficiais importadas da planilha EMISSOES.
            # Não recalcular por fator dentro do app.
            "Emissão tCO₂e": energia_safe_float(r.emissao_co2_ton, 0),
            "Escopo": r.emissao_escopo,
            "Origem": r.origem_arquivo,
        })
    return pd.DataFrame(rows)

def energia_df_actual_hours(db):
    hrs = db.query(EnergiaActualHours).order_by(EnergiaActualHours.mes_ref, EnergiaActualHours.site_codigo).all()
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

def energia_consolidado(db):
    regs = energia_df_registros(db)
    hrs = energia_df_actual_hours(db)
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
    irec_inicio = energia_first_day(energia_param(db, "irec_data_inicio", "2023-01-01")) or date(2023, 1, 1)
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
        # Grupo "LAG" significa todos.
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

def energia_executive_table(db, metric, r12_mes, usar_irec=False):
    df = energia_consolidado(db)
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
    st.caption("Emissões importadas da planilha EMISSOES; o app não recalcula CO₂ por fator de emissão.")
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
    map_df = energia_mapa_sites_df(r12_site)

    section("Mapa geográfico e visão executiva")
    st.caption("As bolhas mostram a distribuição local por unidade produtiva no Brasil. Use o seletor para alternar entre consumo, emissões, custo e eficiência.")
    mapa_col, resumo_col = st.columns([2.25, 1])
    with mapa_col:
        metrica_mapa = st.selectbox(
            "Métrica do mapa",
            list(ENERGIA_MAP_METRICAS.keys()),
            index=list(ENERGIA_MAP_METRICAS.keys()).index("Emissões CO₂ R12 com I-REC") if usar_irec else list(ENERGIA_MAP_METRICAS.keys()).index("Emissões CO₂ R12"),
            key="energia_mapa_metrica",
        )
        fig_mapa = energia_mapa_brasil_fig(map_df, metrica_mapa, usar_irec)
        if fig_mapa is not None:
            st.plotly_chart(fig_mapa, use_container_width=True)
        else:
            empty_state("Sem coordenadas ou dados suficientes para gerar o mapa geográfico.")
    with resumo_col:
        if not map_df.empty:
            map_col, map_unit = ENERGIA_MAP_METRICAS.get(st.session_state.get("energia_mapa_metrica", "Consumo total R12"), ("consumo_total_kwh", "kWh"))
            ranking_map = map_df.sort_values(map_col, ascending=(map_col == "eficiencia_energetica")).copy()
            maior = ranking_map.iloc[0] if map_col == "eficiencia_energetica" else ranking_map.sort_values(map_col, ascending=False).iloc[0]
            menor = ranking_map.iloc[0] if map_col != "eficiencia_energetica" else ranking_map.sort_values(map_col, ascending=False).iloc[0]
            kpi_card("Maior contribuição", maior["Site"], f"{energia_fmt_val(maior[map_col], 'money' if map_unit == 'BRL' else 'numero')} {map_unit}")
            kpi_card("Menor contribuição", menor["Site"], f"{energia_fmt_val(menor[map_col], 'money' if map_unit == 'BRL' else 'numero')} {map_unit}")
            ranking_cols = ["Site", "Unidade", map_col]
            ranking_show = ranking_map[ranking_cols].rename(columns={map_col: st.session_state.get("energia_mapa_metrica", "Métrica")}).head(6)
            st.dataframe(ranking_show, use_container_width=True, hide_index=True)
        else:
            empty_state("Sem dados para ranking geográfico.")

    abas_dash = st.tabs(["Tendências mensais", "Ranking R12", "Metas", "Exportação"])
    with abas_dash[0]:
        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(px.line(mensal_site, x="Mês", y="consumo_eletrico_kwh", color="Site", markers=True, title="Consumo elétrico mensal por site").update_layout(template="plotly_white", yaxis_title="kWh"), use_container_width=True)
        with c2:
            st.plotly_chart(px.line(mensal_site, x="Mês", y="consumo_gas_kwh", color="Site", markers=True, title="Consumo de gás natural mensal por site").update_layout(template="plotly_white", yaxis_title="kWh"), use_container_width=True)
        c3, c4 = st.columns(2)
        with c3:
            emis = mensal_site.groupby("Mês", as_index=False)[["emissao_total_tco2e", "emissao_total_com_irec_tco2e"]].sum()
            emis_long = emis.melt(id_vars="Mês", value_vars=["emissao_total_tco2e", "emissao_total_com_irec_tco2e"], var_name="Cenário", value_name="tCO₂e")
            emis_long["Cenário"] = emis_long["Cenário"].map({"emissao_total_tco2e": "Sem I-REC", "emissao_total_com_irec_tco2e": "Com I-REC"})
            st.plotly_chart(px.line(emis_long, x="Mês", y="tCO₂e", color="Cenário", markers=True, title="Emissões mensais de CO₂ — com e sem I-REC").update_layout(template="plotly_white"), use_container_width=True)
        with c4:
            if not r12_site.empty:
                fig = px.bar(r12_site.sort_values("consumo_total_kwh", ascending=False), x="Site", y="consumo_total_kwh", text="consumo_total_kwh", title="Consumo total R12 por site").update_layout(template="plotly_white", yaxis_title="kWh")
                st.plotly_chart(energia_bar_sem_decimal(fig), use_container_width=True)
            else:
                empty_state("Sem dados R12 para consumo por site.")
    with abas_dash[1]:
        c5, c6 = st.columns(2)
        with c5:
            if not r12_site.empty:
                fig = px.bar(r12_site.sort_values("custo_total_brl", ascending=False), x="Site", y="custo_total_brl", text="custo_total_brl", title="Custo total R12 por site").update_layout(template="plotly_white", yaxis_title="BRL")
                st.plotly_chart(energia_bar_sem_decimal(fig), use_container_width=True)
            else:
                empty_state("Sem dados R12 para custo por site.")
        with c6:
            if not r12_site.empty:
                fig = px.bar(r12_site.sort_values("eficiencia_energetica", ascending=True), x="Site", y="eficiencia_energetica", text="eficiencia_energetica", title="Eficiência energética R12 por site — menor é melhor").update_layout(template="plotly_white", yaxis_title="kWh/Actual Hour")
                st.plotly_chart(energia_bar_sem_decimal(fig), use_container_width=True)
            else:
                empty_state("Sem dados R12 para eficiência por site.")
        if not r12_site.empty:
            ranking = r12_site.copy()
            ranking["Site nome"] = ranking["Site"].map(lambda x: energia_site_nome(x))
            ranking["CO₂ considerado"] = ranking["emissao_total_com_irec_tco2e"] if usar_irec else ranking["emissao_total_tco2e"]
            st.dataframe(
                ranking[["Site", "Site nome", "consumo_eletrico_kwh", "consumo_gas_kwh", "consumo_total_kwh", "CO₂ considerado", "custo_total_brl", "eficiencia_energetica"]]
                    .sort_values("consumo_total_kwh", ascending=False),
                use_container_width=True, hide_index=True
            )

    with abas_dash[2]:
        section("Metas ao longo do tempo")
        df_scope = df.copy()
        sites_sel = st.session_state.get("energia_dash_sites", [])
        grupos_sel = st.session_state.get("energia_dash_grupos", [])
        if sites_sel:
            df_scope = df_scope[df_scope["Site"].isin(sites_sel)]
        if grupos_sel and "LAG" not in grupos_sel:
            df_scope = df_scope[df_scope["Grupo"].isin(grupos_sel)]
        metas = energia_tendencia_metas(df_scope, usar_irec, db)
        if metas.empty:
            empty_state("Sem dados suficientes para gerar a tendência de metas.")
        else:
            c7, c8 = st.columns(2)
            with c7:
                emis_meta = metas[["Mês","Emissões R12","Meta emissões"]].melt(id_vars="Mês", var_name="Série", value_name="tCO₂e")
                st.plotly_chart(px.line(emis_meta, x="Mês", y="tCO₂e", color="Série", markers=True, title="Emissões R12 vs meta ao longo do tempo").update_layout(template="plotly_white"), use_container_width=True)
            with c8:
                eff_meta = metas[["Mês","Eficiência energética R12","Meta eficiência energética"]].melt(id_vars="Mês", var_name="Série", value_name="kWh/Actual Hour")
                st.plotly_chart(px.line(eff_meta, x="Mês", y="kWh/Actual Hour", color="Série", markers=True, title="Eficiência energética R12 vs meta ao longo do tempo").update_layout(template="plotly_white"), use_container_width=True)

    with abas_dash[3]:
        section("Exportação")
        tabela_exec = energia_executive_table(db, "Emissões de CO₂ considerando I-REC" if usar_irec else "Emissões de CO₂", r12_mes, usar_irec)
        download_excel_button("Exportar relatório Excel", "relatorio_energia_co2.xlsx", {
            "Consolidado_Filtrado": f,
            "KPIs": kpis,
            "Tabela_Executiva": tabela_exec.drop(columns=["_grupo"], errors="ignore"),
            "Mapa_Geografico": map_df,
            "Base_Energia": energia_df_registros(db),
            "Base_Actual_Hours": energia_df_actual_hours(db),
            "Premissas": pd.DataFrame([{"Parâmetro": p.chave, "Valor": p.valor, "Descrição": p.descricao} for p in db.query(EnergiaParametro).all()]),
        })


def energia_atualizar_base(db,u):
    header("Atualizar Base de Energia, Gás e Emissões", "Importe os dois arquivos oficiais e sobrescreva a base atual do módulo")
    st.info("Envie sempre os dois arquivos no mesmo ciclo: GAS_ENERGIA_CONTROLE_MENSAL e EMISSOES. O app usa consumo/custo do primeiro arquivo e emissões de CO₂ do segundo, sem recalcular CO₂ por fator.")
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
                    # Substitui os meses/sites importados para evitar duplicidade.
                    for _, r in parsed.iterrows():
                        db.query(EnergiaActualHours).filter(
                            EnergiaActualHours.mes_ref == r["mes_ref"],
                            EnergiaActualHours.site_codigo == r["site_codigo"]
                        ).delete()
                        db.add(EnergiaActualHours(**r.to_dict()))
                    db.add(EnergiaUploadHistorico(tipo_base="Actual Hours", nome_arquivo=up.name, usuario=u.nome if u else "", observacoes=f"{len(parsed)} linhas importadas"))
                    db.commit()
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
    header("Parâmetros", "I-REC, metas, conversões, referência fiscal e campos legados")
    st.info("As emissões de CO₂ são importadas da planilha EMISSOES. Os fatores de emissão ficam apenas como referência legada e não são usados no cálculo.")
    seed_energia_parametros(db)
    ps = db.query(EnergiaParametro).order_by(EnergiaParametro.chave).all()
    with st.form("energia_parametros_form"):
        values = {}
        for p in ps:
            values[p.chave] = st.text_input(p.chave, value=p.valor or "", help=p.descricao or "")
        if st.form_submit_button("Salvar parâmetros", use_container_width=True):
            for chave, valor in values.items():
                energia_set_param(db, chave, valor)
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

# ============================================================
# 15. Roteamento principal
# ============================================================

def render_sidebar(db,u):
    mod=st.session_state.get("modulo","home")
    # A tela inicial e a tela intermediária de Sustentação funcionam como landing pages.
    # Nelas, a navegação deve ocorrer pelos cards centrais, mantendo a barra lateral oculta.
    if (
        mod=="home"
        or (mod=="nr12" and st.session_state.get("page_nr12",NR12_HOME_PAGE)==NR12_HOME_PAGE)
        or (mod=="ehs" and st.session_state.get("page_ehs",EHS_HOME_PAGE)==EHS_HOME_PAGE)
        or (mod=="energia" and st.session_state.get("page_energia",ENERGIA_HOME_PAGE)==ENERGIA_HOME_PAGE)
    ):
        return
    st.sidebar.markdown("### Navegação")
    if st.sidebar.button("🏠 Voltar para a tela inicial",use_container_width=True):
        st.session_state.modulo="home"
        st.rerun()
    st.sidebar.divider()
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
                # Não atualizar st.session_state.nav_nr12 aqui: essa chave pertence a um widget
                # já instanciado nesta execução e causaria StreamlitAPIException.
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
                # Não atualizar st.session_state.nav_ehs aqui: essa chave pertence a um widget
                # já instanciado nesta execução e causaria StreamlitAPIException.
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
                # Não atualizar st.session_state.nav_energia aqui: essa chave pertence a um widget
                # já instanciado nesta execução e causaria StreamlitAPIException.
                st.session_state.page_energia=ENERGIA_HOME_PAGE
                st.rerun()

def route(db,u):
    mod=st.session_state.get("modulo","home")
    if mod=="home": home_page(db,u)
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

# ============================================================
# 16. main()
# ============================================================
def main():
    if "modulo" not in st.session_state:
        st.session_state.modulo="home"
    apply_theme(); hide_sidebar_on_home(); init_db(); db=SessionLocal()
    try:
        mod_atual = st.session_state.get("modulo", "home")
        page_nr12_atual = st.session_state.get("page_nr12", NR12_HOME_PAGE)
        page_ehs_atual = st.session_state.get("page_ehs", EHS_HOME_PAGE)
        page_energia_atual = st.session_state.get("page_energia", ENERGIA_HOME_PAGE)
        tela_landing = (
            (mod_atual == "home")
            or (mod_atual == "nr12" and page_nr12_atual == NR12_HOME_PAGE)
            or (mod_atual == "ehs" and page_ehs_atual == EHS_HOME_PAGE)
            or (mod_atual == "energia" and page_energia_atual == ENERGIA_HOME_PAGE)
        )
        location="main" if tela_landing else "sidebar"
        u=user_selector(db,location=location)
        render_sidebar(db,u)
        route(db,u)
    finally:
        db.close()
if __name__=="__main__": main()
