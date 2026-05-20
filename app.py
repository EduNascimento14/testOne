
# -*- coding: utf-8 -*-
"""
Plataforma Integrada EHS — NR-12 e Auditorias Cruzadas
Arquivo monolítico Streamlit. Renomeie para plataforma_ehs_integrada.py e rode:
streamlit run plataforma_ehs_integrada.py
"""

# ============================================================
# 1. Imports
# ============================================================
import os, io
from datetime import date, datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import create_engine, Column, Integer, String, Text, Date, DateTime, Boolean, Float, ForeignKey, UniqueConstraint
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
SITES_PADRAO = ["SJC", "DIA", "CAC", "JAC", "JUN", "PER"]
PERFIS = ["Admin_LAG","EHS_Local","Auditor","Manutencao","Producao_Operacao","Engenharia","Responsavel_Acao","Visualizador"]
USUARIOS_PADRAO = [
    ("Eduardo","Admin_LAG","Corporativo"), ("Capitu","Admin_LAG","Corporativo"),
    ("EHS SJC","EHS_Local","SJC"), ("Manutenção SJC","Manutencao","SJC"),
    ("Produção SJC","Producao_Operacao","SJC"), ("Auditor EHS","Auditor","Corporativo")
]
STATUS_MAQUINA = ["Conforme","Conforme com observação","Pendente de ação não crítica","Bloqueada por desvio crítico","Em readequação","Fora de uso","Não aplicável"]
CRITICIDADES = ["Alta","Média","Baixa"]
DOCUMENTOS_ESSENCIAIS = ["Laudo NR-12","ART","Apreciação de risco"]
TIPOS_DOC_NR12 = ["Inventário NR-12","Apreciação de risco","Laudo NR-12","ART","Projeto mecânico","Projeto elétrico","Diagrama de segurança","Manual de operação","Manual de manutenção","Registro de treinamento","Evidência fotográfica","Checklist de validação","Termo de liberação para uso","MOC / Gestão de Mudança","Registro de intervenção","Registro de bloqueio/liberação","Termo anual NR-12","Outros"]
TIPOS_VERIFICACAO_NR12 = ["Checklist operacional","Inspeção de manutenção","Auditoria EHS","Auditoria corporativa","Auditoria pós-MOC","Auditoria extraordinária após incidente/quase-acidente"]
RESULTADOS_NR12 = ["Conforme","Não conforme","Não aplicável"]
STATUS_PAC = ["Aberta","Em andamento","Aguardando validação","Concluída","Vencida","Cancelada"]
CLASSIFICACAO_PAC = ["Crítico","Maior","Menor"]
TIPOS_MUDANCA_CRITICA = ["Alteração de software/PLC","Alteração de relé/controlador de segurança","Substituição de componente de segurança","Remoção temporária de proteção","Alteração de proteção fixa/móvel","Alteração de sensores, cortinas, scanners ou intertravamentos","Mudança de layout com impacto em segurança","Retrofit","Manutenção corretiva crítica","Alteração mecânica, elétrica, pneumática ou hidráulica com impacto na condição segura"]
TIPOS_MUDANCA = TIPOS_MUDANCA_CRITICA + ["Ajuste operacional sem impacto em segurança","Atualização documental","Manutenção preventiva","Melhoria ergonômica sem impacto em segurança","Outro"]
STATUS_MOC = ["Aberta","Em análise","Aprovada","Implementada","Validada","Reprovada","Cancelada"]
STATUS_AUDITORIA = ["Planejada","Em andamento","Concluída","Cancelada"]
STATUS_RESPOSTA_EHS = ["Conforme","Parcialmente Conforme","Não Conforme","Não Aplicável"]
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
("Relé/controlador/PLC de segurança não apresenta falha, alarme ou alteração sem MOC?",True),
("Não há bypass, atuador avulso, jumper, imã externo, fita, calço ou anulação de dispositivo?",True),
("Partida, rearme, modos de operação e parada segura permanecem conforme condição validada?",True),
("Painéis elétricos estão fechados, identificados, sem dano e com documentação rastreável?",False),
("Fontes de energia, pontos de bloqueio e procedimento LOTO estão disponíveis e funcionais?",False),
("Intervenções em proteção/dispositivo de segurança possuem ordem, registro e teste funcional pós-intervenção?",False),
("Componentes substituídos são equivalentes ou tiveram avaliação formal/MOC quando diferentes?",True),
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
("MOCs NR-12 foram abertos, aprovados e encerrados com testes, treinamento e atualização documental quando aplicável?",True),
("Desvios críticos geraram bloqueio imediato e liberação formal após correção/teste funcional?",True),
("Planos de ação possuem responsável, prazo, classificação e acompanhamento de vencidos/reincidentes?",False),
("Comitê Local NR-12 acompanha indicadores, desvios, bloqueios, MOCs e pendências?",False),
("Termo anual de garantia de sustentação NR-12 do site foi emitido ou planejado?",False)]}
CHECKLIST_NR12["Auditoria corporativa"] = CHECKLIST_NR12["Auditoria EHS"]
CHECKLIST_NR12["Auditoria pós-MOC"] = CHECKLIST_NR12["Auditoria EHS"]
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
    .stApp{background:#f6f8fb}.block-container{padding-top:1.4rem}
    section[data-testid="stSidebar"]{background:linear-gradient(180deg,#f5c542,#d9a514,#8a6510)}
    section[data-testid="stSidebar"] *{color:#1f2937!important}
    div.stButton>button,div.stDownloadButton>button{border-radius:14px;border:1px solid #d7dde8;background:#fff;font-weight:700;box-shadow:0 6px 18px rgba(31,41,55,.07)}
    .ehs-header,.card,.kpi{background:#fff;border:1px solid #e6eaf0;border-radius:22px;box-shadow:0 10px 25px rgba(31,41,55,.07);padding:1rem;margin-bottom:.8rem}
    .ehs-header{background:linear-gradient(135deg,#fff,#fff8e3)} .ehs-header h1{margin:0;color:#111827}.ehs-header p{margin:.2rem 0;color:#5b6575}
    .kpi-label{color:#697386;font-size:.78rem;font-weight:800;text-transform:uppercase}.kpi-value{font-size:1.8rem;font-weight:900;color:#111827}.muted{color:#697386;font-size:.85rem}
    .section-title{font-size:1.2rem;font-weight:900;color:#1f2937;margin:1rem 0 .5rem}
    .empty{border:1px dashed #c9d1df;border-radius:18px;background:#fff;padding:1rem;text-align:center;color:#697386}
    .alert{background:#fff7df;border-left:6px solid #d9a514;border-radius:16px;padding:.8rem;margin:.5rem 0}
    </style>""", unsafe_allow_html=True)

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
    criticidade=Column(String(20),default="Média"); status_nr12=Column(String(80),default="Conforme"); ultima_adequacao=Column(Date); ultima_auditoria=Column(Date); proxima_auditoria=Column(Date)
    possui_laudo=Column(Boolean,default=False); possui_art=Column(Boolean,default=False); possui_apreciacao_risco=Column(Boolean,default=False); possui_manual_atualizado=Column(Boolean,default=False); possui_treinamento=Column(Boolean,default=False)
    observacoes=Column(Text); criado_em=Column(DateTime,default=datetime.utcnow); site=relationship("Site")
class DocumentoNR12(Base):
    __tablename__="documentos_nr12"; id=Column(Integer,primary_key=True); maquina_id=Column(Integer,ForeignKey("maquinas_nr12.id")); site_id=Column(Integer,ForeignKey("sites.id")); tipo=Column(String(120)); descricao=Column(Text); data_emissao=Column(Date); data_validade=Column(Date); arquivo_nome=Column(String(260)); arquivo_caminho=Column(String(500)); responsavel=Column(String(120)); observacoes=Column(Text); criado_em=Column(DateTime,default=datetime.utcnow); maquina=relationship("MaquinaNR12"); site=relationship("Site")
class VerificacaoNR12(Base):
    __tablename__="verificacoes_nr12"; id=Column(Integer,primary_key=True); maquina_id=Column(Integer,ForeignKey("maquinas_nr12.id")); site_id=Column(Integer,ForeignKey("sites.id")); tipo=Column(String(120)); data_verificacao=Column(Date); responsavel=Column(String(120)); resultado=Column(String(80)); pontuacao=Column(Float,default=0); possui_nc_critica=Column(Boolean,default=False); observacoes=Column(Text); proxima_verificacao=Column(Date); criado_em=Column(DateTime,default=datetime.utcnow); maquina=relationship("MaquinaNR12")
class ChecklistItemNR12(Base):
    __tablename__="checklist_itens_nr12"; id=Column(Integer,primary_key=True); tipo_checklist=Column(String(120)); ordem=Column(Integer); pergunta=Column(Text); item_critico=Column(Boolean,default=False); ativo=Column(Boolean,default=True); __table_args__=(UniqueConstraint("tipo_checklist","ordem",name="uq_nr12_tipo_ordem"),)
class RespostaNR12(Base):
    __tablename__="respostas_nr12"; id=Column(Integer,primary_key=True); verificacao_id=Column(Integer,ForeignKey("verificacoes_nr12.id")); item_id=Column(Integer,ForeignKey("checklist_itens_nr12.id")); aplicavel=Column(Boolean,default=True); resultado=Column(String(60)); comentario_evidencia=Column(Text); gerar_pac=Column(Boolean,default=False); item=relationship("ChecklistItemNR12")
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

# ============================================================
# 6. Seed inicial
# ============================================================
def init_db():
    Base.metadata.create_all(engine); db=SessionLocal()
    try:
        if not db.query(Site).filter_by(codigo="Corporativo").first(): db.add(Site(codigo="Corporativo",nome="Corporativo"))
        for s in SITES_PADRAO:
            if not db.query(Site).filter_by(codigo=s).first(): db.add(Site(codigo=s,nome=s))
        db.flush()
        for nome,perfil,sitecod in USUARIOS_PADRAO:
            if not db.query(Usuario).filter_by(nome=nome).first():
                stt=db.query(Site).filter_by(codigo=sitecod).first(); db.add(Usuario(nome=nome,perfil=perfil,site_id=stt.id if stt else None))
        for tipo,itens in CHECKLIST_NR12.items():
            for i,(pergunta,critico) in enumerate(itens,1):
                if not db.query(ChecklistItemNR12).filter_by(tipo_checklist=tipo,ordem=i).first():
                    db.add(ChecklistItemNR12(tipo_checklist=tipo,ordem=i,pergunta=pergunta,item_critico=critico,ativo=True))
        for cat,pergs in CHECKLIST_EHS.items():
            d=db.query(DiretivaEHS).filter_by(categoria=cat).first()
            if not d: d=DiretivaEHS(categoria=cat,descricao=cat,ativo=True); db.add(d); db.flush()
            for i,p in enumerate(pergs,1):
                if not db.query(RequisitoEHS).filter_by(diretiva_id=d.id,ordem=i).first():
                    db.add(RequisitoEHS(diretiva_id=d.id,ordem=i,pergunta=p,criticidade="Alta" if i in [1,3,7] else "Média",evidencia_esperada="Evidência documental, registros, entrevistas e/ou verificação em campo.",ativo=True))
        db.commit()
        if db.query(MaquinaNR12).count()==0:
            sjc=db.query(Site).filter_by(codigo="SJC").first()
            m=MaquinaNR12(codigo="SJC-PRENSA-001",site_id=sjc.id,area_setor="Produção",linha_processo="Linha 1",nome="Prensa hidráulica 001",fabricante="Fabricante A",modelo="PH-100",numero_serie="PH100",ano="2020",tipo_equipamento="Prensa",responsavel_area="Produção",criticidade="Alta",status_nr12="Conforme com observação",ultima_adequacao=date.today()-timedelta(days=180),ultima_auditoria=date.today()-timedelta(days=90),proxima_auditoria=date.today()+timedelta(days=40),possui_laudo=True,possui_art=True,possui_apreciacao_risco=True,possui_manual_atualizado=True,possui_treinamento=True)
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
def calcular_status_maquina_nr12(db,m):
    if not m: return "Não aplicável"
    if m.status_nr12 in ["Fora de uso","Não aplicável","Em readequação"]: return m.status_nr12
    docs={d.tipo:d for d in db.query(DocumentoNR12).filter_by(maquina_id=m.id)}
    if any((t not in docs) or calcular_status_documento(docs[t])=="Vencido" for t in DOCUMENTOS_ESSENCIAIS): return "Pendente de ação não crítica"
    if db.query(PACNR12).filter(PACNR12.maquina_id==m.id,PACNR12.classificacao=="Crítico",PACNR12.status.in_(["Aberta","Em andamento","Aguardando validação","Vencida"])).first(): return "Bloqueada por desvio crítico"
    if db.query(MOCNR12).filter(MOCNR12.maquina_id==m.id,MOCNR12.exige_moc==True,MOCNR12.validacao_final==False,MOCNR12.status.in_(["Implementada","Aprovada"])).first(): return "Bloqueada por desvio crítico"
    return m.status_nr12 or "Conforme"
def calcular_resultado_verificacao_nr12(resps):
    ap=[r for r in resps if r.aplicavel and r.resultado!="Não aplicável"]
    if not ap: return "Não aplicável",0,False
    pct=round(sum(1 for r in ap if r.resultado=="Conforme")/len(ap)*100,1); crit=any(r.resultado=="Não conforme" and r.item and r.item.item_critico for r in ap)
    if crit: return "Crítico",pct,True
    if pct<70: return "Pendente de ação não crítica",pct,False
    if pct<90: return "Conforme com observação",pct,False
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
def module_card(t,d,i): st.markdown(f"<div class='card'><h3>{i} {t}</h3><p class='muted'>{d}</p></div>",unsafe_allow_html=True)
def empty_state(t): st.markdown(f"<div class='empty'>{t}</div>",unsafe_allow_html=True)
def alert_card(t): st.markdown(f"<div class='alert'>{t}</div>",unsafe_allow_html=True)
def user_selector(db):
    us=db.query(Usuario).filter_by(ativo=True).order_by(Usuario.nome).all(); nomes=[u.nome for u in us]
    if "usuario_nome" not in st.session_state: st.session_state.usuario_nome="Eduardo" if "Eduardo" in nomes else nomes[0]
    sel=st.sidebar.selectbox("Usuário",nomes,index=nomes.index(st.session_state.usuario_nome) if st.session_state.usuario_nome in nomes else 0)
    st.session_state.usuario_nome=sel; u=db.query(Usuario).filter_by(nome=sel).first()
    st.sidebar.caption(f"Perfil: {u.perfil} | Site: {u.site.codigo if u and u.site else '—'}"); return u
def download_excel_button(label,file,sheets): st.download_button(label,gerar_excel(sheets),file,mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True)
def download_pdf_button(label,file,pdf): st.download_button(label,pdf,file,mime="application/pdf",use_container_width=True)

# DataFrames
def df_maquinas(db,ids):
    return pd.DataFrame([{"ID":m.id,"Código":m.codigo,"Site":site_code(db,m.site_id),"Área":m.area_setor,"Linha":m.linha_processo,"Máquina":m.nome,"Fabricante":m.fabricante,"Modelo":m.modelo,"Série":m.numero_serie,"Ano":m.ano,"Tipo":m.tipo_equipamento,"Responsável":m.responsavel_area,"Criticidade":m.criticidade,"Status NR-12":calcular_status_maquina_nr12(db,m),"Próxima auditoria":fmt_date(m.proxima_auditoria),"Laudo":"Sim" if m.possui_laudo else "Não","ART":"Sim" if m.possui_art else "Não","Apreciação":"Sim" if m.possui_apreciacao_risco else "Não","Manual":"Sim" if m.possui_manual_atualizado else "Não","Treinamento":"Sim" if m.possui_treinamento else "Não","Observações":m.observacoes} for m in db.query(MaquinaNR12).filter(MaquinaNR12.site_id.in_(ids)).order_by(MaquinaNR12.codigo)])
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
    vals=[len(ms),sum(1 for m in ms if calcular_status_maquina_nr12(db,m)=="Bloqueada por desvio crítico"),db.query(PACNR12).filter(PACNR12.site_id.in_(ids),PACNR12.status=="Vencida").count(),db.query(MOCNR12).filter(MOCNR12.site_id.in_(ids),MOCNR12.exige_moc==True,MOCNR12.validacao_final==False).count(),db.query(AuditoriaCruzada).filter(AuditoriaCruzada.site_auditado_id.in_(ids),AuditoriaCruzada.status=="Em andamento").count(),f"{round(sum(conf)/len(conf),1) if conf else 0}%",db.query(PACEHS).filter(PACEHS.site_id.in_(ids),PACEHS.status=="Vencida").count(),db.query(PACEHS).filter(PACEHS.site_id.in_(ids),PACEHS.tipo_achado=="Não conformidade crítica",PACEHS.status.in_(["Aberta","Em andamento","Vencida"])).count()]
    labs=["Total de máquinas NR-12","Máquinas bloqueadas","PACs NR-12 vencidos","MOCs críticas sem validação","Auditorias em andamento","Conformidade média EHS","PACs EHS vencidos","NC críticas EHS"]
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
    st.dataframe(pd.DataFrame(alerts),use_container_width=True,hide_index=True) if alerts else empty_state("Nenhum alerta crítico ou vencido identificado.")
def home_page(db,u):
    header("Plataforma Integrada EHS","NR-12 e Auditorias Cruzadas de EHS Directives em uma única aplicação")
    dashboard_integrado(db,u); section("Módulos")
    c1,c2=st.columns(2)
    with c1:
        module_card("Sustentação NR-12","Inventário, documentos, checklists, PAC, MOC, termo anual e relatórios.","⚙️")
        if st.button("Acessar Sustentação NR-12",use_container_width=True): st.session_state.modulo="nr12"; st.rerun()
    with c2:
        module_card("Auditoria Cruzada EHS Directives","Planejamento, checklist incorporado, evidências, maturidade, PAC e relatórios.","🧭")
        if st.button("Acessar Auditoria Cruzada",use_container_width=True): st.session_state.modulo="ehs"; st.rerun()

# ============================================================
# 13. Páginas NR-12
# ============================================================
def nr12_dashboard(db,u):
    header("Sustentação da Conformidade NR-12","Dashboard objetivo para máquinas já adequadas à NR-12")
    ids=visible_site_ids(u,db); ms=db.query(MaquinaNR12).filter(MaquinaNR12.site_id.in_(ids)).all(); sts=[calcular_status_maquina_nr12(db,m) for m in ms]; total=len(ms)
    docs=db.query(DocumentoNR12).filter(DocumentoNR12.site_id.in_(ids)).all(); dfm=df_maquinas(db,ids); dfp=df_pac_nr12(db,ids)
    cards=[("Total de máquinas",total),("% máquinas conformes",f"{round(sts.count('Conforme')/total*100,1) if total else 0}%"),("Máquinas com observação",sts.count("Conforme com observação")),("Máquinas pendentes",sts.count("Pendente de ação não crítica")),("Máquinas bloqueadas",sts.count("Bloqueada por desvio crítico")),("Docs essenciais vencidos",sum(1 for d in docs if d.tipo in DOCUMENTOS_ESSENCIAIS and calcular_status_documento(d)=="Vencido")),("Docs essenciais ausentes",sum(sum(1 for t in DOCUMENTOS_ESSENCIAIS if t not in {d.tipo for d in db.query(DocumentoNR12).filter_by(maquina_id=m.id)}) for m in ms)),("Verificações vencidas",sum(1 for m in ms if m.proxima_auditoria and m.proxima_auditoria<date.today())),("Verificações próximas",sum(1 for m in ms if m.proxima_auditoria and date.today()<=m.proxima_auditoria<=date.today()+timedelta(days=60))),("PACs abertos",db.query(PACNR12).filter(PACNR12.site_id.in_(ids),PACNR12.status.in_(["Aberta","Em andamento","Aguardando validação"])).count()),("PACs vencidos",db.query(PACNR12).filter(PACNR12.site_id.in_(ids),PACNR12.status=="Vencida").count()),("MOCs críticas sem validação",db.query(MOCNR12).filter(MOCNR12.site_id.in_(ids),MOCNR12.exige_moc==True,MOCNR12.validacao_final==False).count())]
    for base in [0,4,8]:
        cols=st.columns(4)
        for c,(l,v) in zip(cols,cards[base:base+4]):
            with c: kpi_card(l,v)
    section("Gráficos")
    c1,c2=st.columns(2)
    with c1: st.plotly_chart(px.histogram(dfm,x="Site",color="Status NR-12",barmode="group",title="Status NR-12 por site").update_layout(template="plotly_white"),use_container_width=True) if not dfm.empty else empty_state("Sem máquinas.")
    with c2: st.plotly_chart(px.pie(dfm,names="Criticidade",title="Máquinas por criticidade",hole=.45).update_layout(template="plotly_white"),use_container_width=True) if not dfm.empty else empty_state("Sem dados.")
    c3,c4=st.columns(2)
    with c3: st.plotly_chart(px.histogram(dfp,x="Status",color="Classificação",barmode="group",title="PAC por status/classificação").update_layout(template="plotly_white"),use_container_width=True) if not dfp.empty else empty_state("Sem PACs.")
    with c4:
        dv=pd.DataFrame([{"Tipo":"Vencidas","Qtd":cards[7][1]},{"Tipo":"Próximas","Qtd":cards[8][1]}]); st.plotly_chart(px.bar(dv,x="Tipo",y="Qtd",title="Verificações vencidas/próximas").update_layout(template="plotly_white"),use_container_width=True)
    section("Máquinas prioritárias")
    pr=dfm[dfm["Status NR-12"].isin(["Bloqueada por desvio crítico","Pendente de ação não crítica","Conforme com observação"])] if not dfm.empty else pd.DataFrame()
    st.dataframe(pr,use_container_width=True,hide_index=True) if not pr.empty else empty_state("Nenhuma máquina prioritária.")
def nr12_inventario(db,u):
    header("Inventário de Máquinas","Cadastro, edição, consulta e exportação")
    ids=visible_site_ids(u,db); sites={s.codigo:s.id for s in db.query(Site).filter(Site.id.in_(ids)).order_by(Site.codigo)}
    if can_edit(u,"nr12_manutencao"):
        with st.expander("Cadastrar máquina"):
            with st.form("maq"):
                a,b,c=st.columns(3)
                with a: cod=st.text_input("Código*"); site=st.selectbox("Site*",list(sites)); area=st.text_input("Área/setor"); linha=st.text_input("Linha/processo"); nome=st.text_input("Nome*"); fab=st.text_input("Fabricante")
                with b: mod=st.text_input("Modelo"); serie=st.text_input("Número de série"); ano=st.text_input("Ano"); tipo=st.text_input("Tipo de equipamento"); resp=st.text_input("Responsável da área"); crit=st.selectbox("Criticidade",CRITICIDADES)
                with c: status=st.selectbox("Status NR-12",STATUS_MAQUINA); prox=st.date_input("Próxima auditoria prevista",value=date.today()+timedelta(days=180))
                ck=st.columns(5); laudo=ck[0].checkbox("Laudo"); art=ck[1].checkbox("ART"); apr=ck[2].checkbox("Apreciação"); man=ck[3].checkbox("Manual"); tre=ck[4].checkbox("Treinamento"); obs=st.text_area("Observações")
                if st.form_submit_button("Salvar",use_container_width=True):
                    if cod and nome and not db.query(MaquinaNR12).filter_by(codigo=cod).first():
                        db.add(MaquinaNR12(codigo=cod,site_id=sites[site],area_setor=area,linha_processo=linha,nome=nome,fabricante=fab,modelo=mod,numero_serie=serie,ano=ano,tipo_equipamento=tipo,responsavel_area=resp,criticidade=crit,status_nr12=status,proxima_auditoria=prox,possui_laudo=laudo,possui_art=art,possui_apreciacao_risco=apr,possui_manual_atualizado=man,possui_treinamento=tre,observacoes=obs)); db.commit(); st.success("Máquina cadastrada."); st.rerun()
                    else: st.error("Preencha código/nome e evite código duplicado.")
    df=df_maquinas(db,ids); section("Consulta")
    if df.empty: empty_state("Nenhuma máquina cadastrada."); return
    s=st.multiselect("Filtrar status",sorted(df["Status NR-12"].unique())); f=df[df["Status NR-12"].isin(s)] if s else df
    st.dataframe(f,use_container_width=True,hide_index=True); download_excel_button("Exportar Excel","inventario_maquinas_nr12.xlsx",{"Inventário":f})
    if can_edit(u,"nr12_manutencao"):
        opts=machine_options(db,ids); section("Editar máquina")
        lab=st.selectbox("Máquina",list(opts)); m=db.get(MaquinaNR12,opts[lab])
        with st.form("editmaq"):
            m.status_nr12=st.selectbox("Status",STATUS_MAQUINA,index=STATUS_MAQUINA.index(m.status_nr12) if m.status_nr12 in STATUS_MAQUINA else 0); m.criticidade=st.selectbox("Criticidade",CRITICIDADES,index=CRITICIDADES.index(m.criticidade) if m.criticidade in CRITICIDADES else 1); m.observacoes=st.text_area("Observações",m.observacoes or "")
            if st.form_submit_button("Atualizar",use_container_width=True): db.commit(); st.success("Atualizado."); st.rerun()
def nr12_documentos(db,u):
    header("Documentos NR-12","Controle de documentos essenciais, validade e evidências")
    ids=visible_site_ids(u,db); opts=machine_options(db,ids)
    if can_edit(u,"nr12_manutencao") and opts:
        with st.expander("Cadastrar documento"):
            with st.form("doc"):
                lab=st.selectbox("Máquina",list(opts)); tipo=st.selectbox("Tipo",TIPOS_DOC_NR12); emiss=st.date_input("Emissão",date.today()); valid=st.date_input("Validade",date.today()+timedelta(days=365)); resp=st.text_input("Responsável"); up=st.file_uploader("Arquivo"); desc=st.text_area("Descrição")
                if st.form_submit_button("Salvar",use_container_width=True):
                    m=db.get(MaquinaNR12,opts[lab]); fname=up.name if up else ""
                    db.add(DocumentoNR12(maquina_id=m.id,site_id=m.site_id,tipo=tipo,descricao=desc,data_emissao=emiss,data_validade=valid,arquivo_nome=fname,arquivo_caminho=fname,responsavel=resp))
                    if tipo=="Laudo NR-12": m.possui_laudo=True
                    if tipo=="ART": m.possui_art=True
                    if tipo=="Apreciação de risco": m.possui_apreciacao_risco=True
                    db.commit(); st.success("Documento salvo."); st.rerun()
    df=df_docs(db,ids); section("Consulta")
    st.dataframe(df,use_container_width=True,hide_index=True) if not df.empty else empty_state("Nenhum documento.")
    download_excel_button("Exportar documentos Excel","documentos_nr12.xlsx",{"Documentos":df})
def nr12_checklists(db,u):
    header("Checklists e Inspeções NR-12","Registro por máquina, pontuação e geração automática de PAC")
    ids=visible_site_ids(u,db); opts=machine_options(db,ids)
    if can_edit(u,"nr12_operacao") and opts:
        with st.form("ver"):
            tipo=st.selectbox("Tipo",TIPOS_VERIFICACAO_NR12); lab=st.selectbox("Máquina",list(opts)); resp=st.text_input("Responsável",u.nome); obs=st.text_area("Observações")
            temp=[]
            for it in db.query(ChecklistItemNR12).filter_by(tipo_checklist=tipo,ativo=True).order_by(ChecklistItemNR12.ordem):
                st.markdown(f"**{it.ordem}. {it.pergunta}** {'⚠️ Crítico' if it.item_critico else ''}")
                c1,c2,c3,c4=st.columns([1,1.2,2,1])
                apl=c1.checkbox("Aplicável",True,key=f"ap{it.id}"); res=c2.selectbox("Resultado",RESULTADOS_NR12,key=f"rr{it.id}"); com=c3.text_input("Comentário/evidência",key=f"co{it.id}"); gp=c4.checkbox("Gerar PAC",res=="Não conforme",key=f"gp{it.id}")
                temp.append((it,apl,res,com,gp))
            if st.form_submit_button("Salvar verificação",use_container_width=True):
                m=db.get(MaquinaNR12,opts[lab]); v=VerificacaoNR12(maquina_id=m.id,site_id=m.site_id,tipo=tipo,data_verificacao=date.today(),responsavel=resp,observacoes=obs,proxima_verificacao=date.today()+timedelta(days=180)); db.add(v); db.flush(); rs=[]
                for it,apl,res,com,gp in temp:
                    r=RespostaNR12(verificacao_id=v.id,item_id=it.id,aplicavel=apl,resultado="Não aplicável" if not apl else res,comentario_evidencia=com,gerar_pac=gp); db.add(r); rs.append(r)
                db.flush(); v.resultado,v.pontuacao,v.possui_nc_critica=calcular_resultado_verificacao_nr12(rs); m.ultima_auditoria=date.today(); m.proxima_auditoria=v.proxima_verificacao; m.status_nr12="Bloqueada por desvio crítico" if v.resultado=="Crítico" else v.resultado if v.resultado in STATUS_MAQUINA else m.status_nr12
                for r in rs:
                    if r.resultado=="Não conforme" or r.gerar_pac: gerar_pac_automatico_nr12(db,v,r,resp)
                db.commit(); st.success(f"Verificação salva: {v.resultado} | {v.pontuacao}%"); st.rerun()
    elif not opts: empty_state("Cadastre uma máquina antes.")
    else: alert_card("Seu perfil permite consulta, mas não registro.")
    df=df_ver(db,ids); section("Verificações registradas"); st.dataframe(df,use_container_width=True,hide_index=True) if not df.empty else empty_state("Nenhuma verificação."); download_excel_button("Exportar verificações Excel","verificacoes_nr12.xlsx",{"Verificações":df})
def nr12_pac(db,u):
    header("PAC NR-12","Planos de ação corretiva")
    ids=visible_site_ids(u,db); sites={s.codigo:s.id for s in db.query(Site).filter(Site.id.in_(ids))}; opts=machine_options(db,ids)
    if can_edit(u,"nr12_manutencao"):
        with st.expander("Cadastrar PAC manual"):
            with st.form("pacn"):
                site=st.selectbox("Site",list(sites)); maq=st.selectbox("Máquina",["—"]+list(opts)); clas=st.selectbox("Classificação",CLASSIFICACAO_PAC); stat=st.selectbox("Status",STATUS_PAC); prazo=st.date_input("Prazo",date.today()+timedelta(days=30)); resp=st.text_input("Responsável"); area=st.text_input("Área"); desc=st.text_area("Descrição do desvio")
                if st.form_submit_button("Salvar",use_container_width=True): db.add(PACNR12(origem="Manual",site_id=sites[site],maquina_id=None if maq=="—" else opts[maq],classificacao=clas,status=stat,prazo=prazo,responsavel=resp,area_responsavel=area,descricao_desvio=desc)); db.commit(); st.success("PAC salvo."); st.rerun()
    df=df_pac_nr12(db,ids); section("Consulta")
    st.dataframe(df,use_container_width=True,hide_index=True) if not df.empty else empty_state("Nenhum PAC.")
    download_excel_button("Exportar PAC NR-12 Excel","pac_nr12.xlsx",{"PAC":df})
    if can_edit(u,"nr12_manutencao") and not df.empty:
        p=db.get(PACNR12,int(st.selectbox("Atualizar PAC",df["ID"].tolist())))
        with st.form("editpacn"):
            p.status=st.selectbox("Status",STATUS_PAC,index=STATUS_PAC.index(p.status) if p.status in STATUS_PAC else 0); p.evidencia_conclusao=st.text_area("Evidência de conclusão",p.evidencia_conclusao or ""); p.validacao_ehs=st.checkbox("Validação EHS",p.validacao_ehs); p.verificacao_eficacia=st.text_area("Verificação de eficácia",p.verificacao_eficacia or "")
            if st.form_submit_button("Atualizar",use_container_width=True):
                if p.status=="Concluída" and not p.evidencia_conclusao: st.error("PAC concluído exige evidência.")
                elif p.status=="Concluída" and p.classificacao=="Crítico" and not p.validacao_ehs: st.error("PAC crítico concluído exige validação EHS.")
                else: db.commit(); st.success("Atualizado."); st.rerun()
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
                    if mid and crit and status=="Implementada" and not val: db.get(MaquinaNR12,mid).status_nr12="Bloqueada por desvio crítico"
                    db.commit(); st.success("MOC salva."); st.rerun()
    df=df_moc(db,ids); section("MOCs registradas"); st.dataframe(df,use_container_width=True,hide_index=True) if not df.empty else empty_state("Nenhuma MOC."); download_excel_button("Exportar MOC Excel","moc_nr12.xlsx",{"MOC":df})
def nr12_termo(db,u):
    header("Termo de Garantia NR-12","Emissão anual por site")
    ids=visible_site_ids(u,db); sites={s.codigo:s.id for s in db.query(Site).filter(Site.id.in_(ids))}
    with st.form("termo"):
        site=st.selectbox("Site",list(sites)); ano=st.number_input("Ano/ciclo",2020,2100,date.today().year); ehs=st.text_input("Responsável EHS"); man=st.text_input("Responsável Manutenção"); prod=st.text_input("Responsável Produção/Operação"); eng=st.text_input("Responsável Engenharia"); lid=st.text_input("Liderança do site"); res=st.text_area("Ressalvas"); pend=st.text_area("Pendências"); dec=st.text_area("Declaração formal","Declaramos que o site acompanha a sustentação da conformidade NR-12 das máquinas já adequadas, mantendo inventário, controles documentais, inspeções, PAC e MOC.")
        if st.form_submit_button("Gerar termo",use_container_width=True):
            sid=sites[site]; ms=db.query(MaquinaNR12).filter_by(site_id=sid).all(); sts=[calcular_status_maquina_nr12(db,m) for m in ms]
            resumo=pd.DataFrame([{"Indicador":"Total de máquinas","Valor":len(ms)},{"Indicador":"Conformes","Valor":sts.count("Conforme")},{"Indicador":"Com observação","Valor":sts.count("Conforme com observação")},{"Indicador":"Pendentes","Valor":sts.count("Pendente de ação não crítica")},{"Indicador":"Bloqueadas","Valor":sts.count("Bloqueada por desvio crítico")},{"Indicador":"PACs críticos abertos/vencidos","Valor":db.query(PACNR12).filter(PACNR12.site_id==sid,PACNR12.classificacao=="Crítico",PACNR12.status.in_(["Aberta","Em andamento","Vencida"])).count()},{"Indicador":"MOCs críticas sem validação","Valor":db.query(MOCNR12).filter(MOCNR12.site_id==sid,MOCNR12.exige_moc==True,MOCNR12.validacao_final==False).count()}])
            if can_edit(u,"nr12_manutencao"): db.add(TermoGarantiaNR12(site_id=sid,ano_ciclo=ano,responsavel_ehs=ehs,responsavel_manutencao=man,responsavel_producao=prod,responsavel_engenharia=eng,lideranca_site=lid,ressalvas=res,pendencias=pend,declaracao_formal=dec)); db.commit()
            pdf=gerar_pdf(f"Termo de Garantia de Sustentação NR-12 — {site}",f"Ano/ciclo: {ano} | Emissão: {fmt_date(date.today())}",[("Declaração",dec),("Responsáveis",pd.DataFrame([{"Função":"EHS","Responsável":ehs},{"Função":"Manutenção","Responsável":man},{"Função":"Produção/Operação","Responsável":prod},{"Função":"Engenharia","Responsável":eng},{"Função":"Liderança","Responsável":lid}])),("Consolidação",resumo),("Ressalvas",res or "Sem ressalvas."),("Pendências",pend or "Sem pendências.")])
            download_pdf_button("Baixar termo NR-12 PDF",f"termo_nr12_{site}_{ano}.pdf",pdf)
def nr12_relatorios(db,u):
    header("Relatórios NR-12","Exportações em Excel e PDFs")
    ids=visible_site_ids(u,db); d={"Inventário":df_maquinas(db,ids),"Documentos":df_docs(db,ids),"Verificações":df_ver(db,ids),"PAC":df_pac_nr12(db,ids),"MOC":df_moc(db,ids)}
    cols=st.columns(5)
    for (name,df),c in zip(d.items(),cols):
        with c: download_excel_button(f"{name} Excel",f"{name.lower()}_nr12.xlsx",{name:df})
    download_excel_button("Pacote NR-12 Excel","pacote_nr12.xlsx",d)
    opts=machine_options(db,ids)
    if opts:
        lab=st.selectbox("Relatório PDF por máquina",list(opts)); m=db.get(MaquinaNR12,opts[lab])
        pdf=gerar_pdf(f"Relatório por Máquina — {m.codigo}",f"{m.nome} | Site {site_code(db,m.site_id)}",[("Dados",df_maquinas(db,[m.site_id]).query("ID == @m.id")),("Documentos",df_docs(db,[m.site_id])),("PACs",df_pac_nr12(db,[m.site_id]))])
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
    header("Auditoria Cruzada EHS Directives","Dashboard de planejamento, conformidade, maturidade e PAC")
    ids=visible_site_ids(u,db); da=df_aud(db,ids); dp=df_pac_ehs(db,ids)
    vals=[(da["Status"]=="Planejada").sum() if not da.empty else 0,(da["Status"]=="Em andamento").sum() if not da.empty else 0,(da["Status"]=="Concluída").sum() if not da.empty else 0,round(da["Conformidade %"].mean(),1) if not da.empty else 0,round(da["Maturidade"].mean(),2) if not da.empty else 0,(dp["Status"].isin(["Aberta","Em andamento","Aguardando validação"])).sum() if not dp.empty else 0,(dp["Status"]=="Vencida").sum() if not dp.empty else 0,(dp["Tipo de achado"]=="Não conformidade crítica").sum() if not dp.empty else 0]
    labs=["Auditorias planejadas","Em andamento","Concluídas","Conformidade média","Maturidade média","PACs abertos","PACs vencidos","NC críticas"]
    for chunk in [range(4),range(4,8)]:
        cols=st.columns(4)
        for c,i in zip(cols,chunk):
            with c: kpi_card(labs[i],f"{vals[i]}%" if i==3 else vals[i])
    section("Gráficos")
    c1,c2=st.columns(2)
    with c1: st.plotly_chart(px.bar(da,x="Site auditado",y="Conformidade %",color="Status",title="Conformidade por site").update_layout(template="plotly_white"),use_container_width=True) if not da.empty else empty_state("Sem auditorias.")
    with c2: st.plotly_chart(px.histogram(dp,x="Status",color="Prioridade",barmode="group",title="PAC por status").update_layout(template="plotly_white"),use_container_width=True) if not dp.empty else empty_state("Sem PACs.")
    section("Principais gaps"); st.dataframe(dp.head(20),use_container_width=True,hide_index=True) if not dp.empty else empty_state("Nenhum gap registrado.")
def ehs_planejamento(db,u):
    header("Planejamento de Auditorias","Cadastro de ciclos e geração automática do checklist")
    ids=visible_site_ids(u,db); sv={s.codigo:s.id for s in db.query(Site).filter(Site.id.in_(ids))}; sall={s.codigo:s.id for s in db.query(Site).filter(Site.codigo!="Corporativo")}
    if can_edit(u,"auditoria"):
        with st.form("aud"):
            ano=st.number_input("Ano",2020,2100,date.today().year); ciclo=st.text_input("Ciclo","Ciclo 1"); site=st.selectbox("Site auditado",list(sv)); lider=st.selectbox("Site auditor líder",["—"]+list(sall)); apoio=st.selectbox("Site auditor apoio",["—"]+list(sall)); aud_l=st.text_input("Auditor líder",u.nome); aud_a=st.text_input("Auditor apoio"); data=st.date_input("Data planejada",date.today()+timedelta(days=30)); status=st.selectbox("Status",STATUS_AUDITORIA); esc=st.text_area("Escopo"); obs=st.text_area("Observações")
            if st.form_submit_button("Criar auditoria e checklist",use_container_width=True):
                a=AuditoriaCruzada(ano=ano,ciclo=ciclo,site_auditado_id=sv[site],site_auditor_lider_id=None if lider=="—" else sall[lider],site_auditor_apoio_id=None if apoio=="—" else sall[apoio],auditor_lider=aud_l,auditor_apoio=aud_a,data_planejada=data,status=status,escopo=esc,observacoes=obs); db.add(a); db.flush(); gerar_checklist_automatico_ehs(db,a.id,False); db.commit(); st.success("Auditoria criada."); st.rerun()
    da=df_aud(db,ids); st.dataframe(da,use_container_width=True,hide_index=True) if not da.empty else empty_state("Nenhuma auditoria."); download_excel_button("Exportar auditorias Excel","auditorias_cruzadas.xlsx",{"Auditorias":da})
def ehs_checklist(db,u):
    header("Checklist EHS Directives","Checklist incorporado, pontuação e maturidade")
    ids=visible_site_ids(u,db); auds=db.query(AuditoriaCruzada).filter(AuditoriaCruzada.site_auditado_id.in_(ids)).order_by(AuditoriaCruzada.id.desc()).all()
    if not auds: empty_state("Crie uma auditoria no planejamento."); return
    amap={f"{a.id} — {site_code(db,a.site_auditado_id)} — {a.ciclo} — {a.status}":a.id for a in auds}; a=db.get(AuditoriaCruzada,amap[st.selectbox("Auditoria",list(amap))]); gerar_checklist_automatico_ehs(db,a.id)
    res=db.query(RespostaAuditoriaEHS).join(RequisitoEHS).join(DiretivaEHS).filter(RespostaAuditoriaEHS.auditoria_id==a.id).order_by(DiretivaEHS.categoria,RequisitoEHS.ordem).all()
    rows=[{"ID":r.id,"Categoria":r.requisito.diretiva.categoria,"Ordem":r.requisito.ordem,"Requisito":r.requisito.pergunta,"Aplicável":r.aplicavel,"Status":r.status,"Maturidade 0-5":r.nota_maturidade,"Evidência verificada":r.evidencia_verificada or "","Comentário do auditor":r.comentario_auditor or "","Necessita PAC":r.necessita_pac} for r in res]
    df=pd.DataFrame(rows); c1,c2,c3=st.columns(3)
    with c1: kpi_card("Conformidade",f"{calcular_conformidade_ehs(res)}%")
    with c2: kpi_card("Maturidade média",calcular_maturidade_ehs(res))
    with c3: kpi_card("Itens",len(df))
    if can_edit(u,"auditoria"):
        ed=st.data_editor(df,use_container_width=True,hide_index=True,disabled=["ID","Categoria","Ordem","Requisito"],column_config={"Status":st.column_config.SelectboxColumn("Status",options=STATUS_RESPOSTA_EHS),"Maturidade 0-5":st.column_config.NumberColumn("Maturidade 0-5",min_value=0,max_value=5,step=.5)})
        if st.button("Salvar respostas e gerar PACs marcados",use_container_width=True):
            for _,row in ed.iterrows():
                r=db.get(RespostaAuditoriaEHS,int(row["ID"])); r.aplicavel=bool(row["Aplicável"]); r.status="Não Aplicável" if not r.aplicavel else row["Status"]; r.nota_maturidade=float(row["Maturidade 0-5"]); r.evidencia_verificada=row["Evidência verificada"]; r.comentario_auditor=row["Comentário do auditor"]; r.necessita_pac=bool(row["Necessita PAC"])
            db.flush(); res=db.query(RespostaAuditoriaEHS).filter_by(auditoria_id=a.id).all(); a.conformidade_percentual=calcular_conformidade_ehs(res); a.maturidade_media=calcular_maturidade_ehs(res)
            for r in res:
                if r.necessita_pac or r.status in ["Não Conforme","Parcialmente Conforme"]: gerar_pac_automatico_ehs(db,a,r,a.auditor_lider)
            db.commit(); st.success("Checklist salvo."); st.rerun()
    else: st.dataframe(df,use_container_width=True,hide_index=True)
def ehs_pac(db,u):
    header("PAC Auditoria Cruzada","Tratamento de achados e verificação de eficácia")
    ids=visible_site_ids(u,db); sites={s.codigo:s.id for s in db.query(Site).filter(Site.id.in_(ids))}
    if can_edit(u,"pac_ehs"):
        with st.expander("Cadastrar PAC EHS manual"):
            with st.form("pace"):
                site=st.selectbox("Site",list(sites)); tipo=st.selectbox("Tipo de achado",TIPOS_ACHADO_EHS); pr=st.selectbox("Prioridade/criticidade",["Alta","Média","Baixa"]); stat=st.selectbox("Status",STATUS_PAC); prazo=st.date_input("Prazo",date.today()+timedelta(days=30)); resp=st.text_input("Responsável"); area=st.text_input("Área responsável"); desc=st.text_area("Descrição"); evid=st.text_area("Evidência"); risco=st.text_area("Risco"); causa=st.text_area("Causa raiz"); aci=st.text_area("Ação imediata"); acc=st.text_area("Ação corretiva")
                if st.form_submit_button("Salvar PAC EHS",use_container_width=True): db.add(PACEHS(site_id=sites[site],tipo_achado=tipo,prioridade_criticidade=pr,status=stat,prazo=prazo,responsavel=resp,area_responsavel=area,descricao=desc,evidencia=evid,risco=risco,causa_raiz=causa,acao_imediata=aci,acao_corretiva=acc)); db.commit(); st.success("PAC salvo."); st.rerun()
    df=df_pac_ehs(db,ids); st.dataframe(df,use_container_width=True,hide_index=True) if not df.empty else empty_state("Nenhum PAC EHS."); download_excel_button("Exportar PAC EHS Excel","pac_ehs.xlsx",{"PAC EHS":df})
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
        pdf=gerar_pdf(f"Relatório de Auditoria Cruzada EHS — {site_code(db,a.site_auditado_id)}",f"Auditoria {a.id} | {a.ciclo} | Conformidade {calcular_conformidade_ehs(res)}% | Maturidade {calcular_maturidade_ehs(res)}",[("Dados",pd.DataFrame([{"Ano":a.ano,"Ciclo":a.ciclo,"Site":site_code(db,a.site_auditado_id),"Status":a.status,"Auditor líder":a.auditor_lider}])),("Resultado por item",dfr),("PACs vinculados",dp[dp["Auditoria"]==a.id] if not dp.empty else dp)])
        download_pdf_button("Baixar relatório de auditoria PDF",f"relatorio_auditoria_ehs_{a.id}.pdf",pdf)

# ============================================================
# 15. Roteamento principal
# ============================================================
def render_sidebar(db,u):
    st.sidebar.markdown("### Navegação")
    if st.sidebar.button("🏠 Tela inicial",use_container_width=True): st.session_state.modulo="home"; st.rerun()
    if st.session_state.get("modulo","home")=="nr12":
        pages=["Dashboard NR-12","Inventário de Máquinas","Documentos NR-12","Checklists e Inspeções","PAC NR-12","Gestão de Mudanças / MOC","Termo de Garantia","Relatórios NR-12"]
        st.session_state.page_nr12=st.sidebar.radio("Sustentação NR-12",pages,index=pages.index(st.session_state.get("page_nr12",pages[0])) if st.session_state.get("page_nr12",pages[0]) in pages else 0)
    elif st.session_state.get("modulo")=="ehs":
        pages=["Dashboard Auditoria Cruzada","Planejamento de Auditorias","Checklist EHS Directives","PAC Auditoria Cruzada","Base do Checklist EHS","Relatórios Auditoria Cruzada"]
        st.session_state.page_ehs=st.sidebar.radio("Auditoria Cruzada",pages,index=pages.index(st.session_state.get("page_ehs",pages[0])) if st.session_state.get("page_ehs",pages[0]) in pages else 0)
def route(db,u):
    mod=st.session_state.get("modulo","home")
    if mod=="home": home_page(db,u)
    elif mod=="nr12":
        {"Dashboard NR-12":nr12_dashboard,"Inventário de Máquinas":nr12_inventario,"Documentos NR-12":nr12_documentos,"Checklists e Inspeções":nr12_checklists,"PAC NR-12":nr12_pac,"Gestão de Mudanças / MOC":nr12_moc,"Termo de Garantia":nr12_termo,"Relatórios NR-12":nr12_relatorios}[st.session_state.get("page_nr12","Dashboard NR-12")](db,u)
    elif mod=="ehs":
        {"Dashboard Auditoria Cruzada":ehs_dashboard,"Planejamento de Auditorias":ehs_planejamento,"Checklist EHS Directives":ehs_checklist,"PAC Auditoria Cruzada":ehs_pac,"Base do Checklist EHS":ehs_base_checklist,"Relatórios Auditoria Cruzada":ehs_relatorios}[st.session_state.get("page_ehs","Dashboard Auditoria Cruzada")](db,u)

# ============================================================
# 16. main()
# ============================================================
def main():
    apply_theme(); init_db(); db=SessionLocal()
    try:
        if "modulo" not in st.session_state: st.session_state.modulo="home"
        u=user_selector(db); render_sidebar(db,u); route(db,u)
    finally: db.close()
if __name__=="__main__": main()
