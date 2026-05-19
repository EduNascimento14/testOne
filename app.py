import os
from contextlib import contextmanager
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

import pandas as pd
import plotly.express as px
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

APP_TITLE = "Auditoria Cruzada de EHS Directives"
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///ehs_audit.db")
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "uploads"))
UPLOAD_DIR.mkdir(exist_ok=True)

SITES_PADRAO = ["SJC", "DIA", "CAC", "JAC", "JUN", "PER"]
STATUS_AUDITORIA = ["Planejada", "Em andamento", "Concluída", "Cancelada"]
STATUS_CONFORMIDADE = ["Conforme", "Parcialmente Conforme", "Não Conforme", "Não Aplicável"]
STATUS_ACHADO = ["Aberto", "Em andamento", "Concluído", "Vencido", "Cancelado"]
TIPOS_ACHADO = ["Não conformidade crítica", "Não conformidade maior", "Não conformidade menor", "Observação", "Oportunidade de melhoria", "Boa prática"]
PRIORIDADES = ["Alta", "Média", "Baixa"]
CRITICIDADES = ["Crítico", "Alto", "Médio", "Baixo"]
PERFIS = ["Admin_LAG", "EHS_Local", "Auditor", "Visualizador", "Responsavel_Acao"]

RESPOSTAS_COLUMNS = ["id", "auditoria_id", "auditoria", "site", "ciclo", "diretiva", "codigo_requisito", "pergunta", "criticidade", "aplicavel", "status", "nota_maturidade", "evidencia_verificada", "comentario_auditor", "necessita_acao"]
ACHADOS_COLUMNS = ["id", "auditoria", "site", "requisito", "tipo_achado", "descricao", "responsavel", "prazo", "status", "prioridade", "vencido"]

CHECKLIST_BASE = [
    {"codigo": "EHS-01", "titulo": "Liderança e Gestão EHS", "descricao": "Governança, responsabilidades, indicadores e cultura de EHS.", "perguntas": ["Existe política de EHS formalizada e comunicada?", "A liderança participa ativamente das ações de EHS?", "Existem metas e indicadores de EHS definidos?", "Os indicadores são monitorados periodicamente?", "Existem reuniões periódicas de EHS?", "Existe definição clara de responsabilidades EHS?", "A organização promove cultura de reporte sem culpa?", "Existem mecanismos formais de melhoria contínua?", "Os riscos críticos são acompanhados pela liderança?", "Existe integração entre EHS e operação?"]},
    {"codigo": "EHS-02", "titulo": "Conformidade Legal", "descricao": "Gestão de requisitos legais, licenças, evidências e prazos.", "perguntas": ["Existe levantamento atualizado de requisitos legais?", "As licenças ambientais estão válidas?", "Existem controles para condicionantes legais?", "Os requisitos legais possuem evidências documentadas?", "Existe monitoramento periódico de atendimento legal?", "Há gestão de prazos legais?", "Existe plano para adequação de não conformidades legais?", "Existem auditorias legais periódicas?", "Há rastreabilidade documental?", "Os responsáveis legais estão definidos?"]},
    {"codigo": "EHS-03", "titulo": "Gestão de Riscos", "descricao": "Identificação de perigos, avaliação de riscos e eficácia dos controles.", "perguntas": ["Existe processo formal de identificação de perigos?", "Os riscos ocupacionais estão avaliados?", "Existem controles implementados para riscos críticos?", "Há hierarquia de controles aplicada?", "Existe revisão periódica das análises de risco?", "Mudanças operacionais passam por avaliação de risco?", "Existe gestão de mudanças formal?", "Há participação dos trabalhadores nas análises?", "Os riscos ambientais estão avaliados?", "Existe monitoramento de eficácia dos controles?"]},
    {"codigo": "EHS-04", "titulo": "Investigação de Incidentes", "descricao": "Reporte, investigação, causas sistêmicas e ações corretivas.", "perguntas": ["Existe processo formal de investigação?", "Os incidentes são reportados adequadamente?", "As causas sistêmicas são avaliadas?", "Há definição de ações corretivas?", "Existe acompanhamento das ações?", "Os aprendizados são compartilhados?", "Há foco em melhoria do sistema e não culpabilização?", "Near misses são investigados?", "Existe rastreabilidade das investigações?", "Indicadores de incidentes são monitorados?"]},
    {"codigo": "EHS-05", "titulo": "Treinamentos e Competências", "descricao": "Matriz de treinamento, competências críticas e reciclagens.", "perguntas": ["Existe matriz de treinamento atualizada?", "Os treinamentos obrigatórios estão válidos?", "Há avaliação de eficácia dos treinamentos?", "Os terceiros recebem treinamentos adequados?", "Existe controle de vencimentos?", "As competências críticas estão mapeadas?", "Há registros formais dos treinamentos?", "Existe integração EHS para novos colaboradores?", "Os líderes recebem treinamento em EHS?", "Existe reciclagem periódica?"]},
    {"codigo": "EHS-06", "titulo": "Gestão Ambiental", "descricao": "Resíduos, MTR, CDF, emissões, efluentes e resposta ambiental.", "perguntas": ["Existe segregação adequada de resíduos?", "Os resíduos possuem identificação?", "Existe controle de MTR?", "Os CDFs são controlados?", "Há controle de empresas destinadoras?", "Existem inspeções ambientais periódicas?", "Há controle de emissões atmosféricas?", "Existe controle de efluentes?", "Existe plano de resposta ambiental?", "Há monitoramento de indicadores ambientais?"]},
    {"codigo": "EHS-07", "titulo": "Segurança Operacional", "descricao": "Máquinas, NR-12, bloqueio, EPI, permissões e controles críticos.", "perguntas": ["Máquinas possuem proteções adequadas?", "Existe atendimento à NR-12?", "Há bloqueio e etiquetagem implementados?", "Os EPIs estão adequados?", "Existe inspeção periódica de segurança?", "Há controle de permissões de trabalho?", "Existe controle de trabalho em altura?", "Espaços confinados possuem gestão adequada?", "Existe controle de energia perigosa?", "Há inspeções comportamentais estruturadas?"]},
    {"codigo": "EHS-08", "titulo": "Preparação e Resposta a Emergências", "descricao": "Plano de emergência, brigada, simulados e equipamentos críticos.", "perguntas": ["Existe plano de emergência atualizado?", "Há brigada treinada?", "Existem simulados periódicos?", "Os equipamentos de emergência estão inspecionados?", "Existe controle de produtos perigosos?", "Há rotas de fuga sinalizadas?", "Existe comunicação de emergência definida?", "Os cenários críticos foram avaliados?", "Existe integração com serviços externos?", "Há registros dos simulados?"]},
]


class Base(DeclarativeBase):
    pass


class Site(Base):
    __tablename__ = "sites"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)


class Usuario(Base):
    __tablename__ = "usuarios"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    site_id: Mapped[int | None] = mapped_column(ForeignKey("sites.id"))
    perfil: Mapped[str] = mapped_column(String(40), nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    site: Mapped[Site | None] = relationship()


class Diretiva(Base):
    __tablename__ = "diretivas"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    titulo: Mapped[str] = mapped_column(String(220), nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text)
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)
    observacao: Mapped[str | None] = mapped_column(Text)
    requisitos: Mapped[list["Requisito"]] = relationship(back_populates="diretiva")


class Requisito(Base):
    __tablename__ = "requisitos"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    diretiva_id: Mapped[int] = mapped_column(ForeignKey("diretivas.id"), nullable=False)
    codigo_requisito: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    pergunta: Mapped[str] = mapped_column(Text, nullable=False)
    orientacao: Mapped[str | None] = mapped_column(Text)
    criticidade: Mapped[str] = mapped_column(String(20), default="Médio")
    tipo_evidencia_esperada: Mapped[str | None] = mapped_column(String(160))
    area_responsavel_sugerida: Mapped[str | None] = mapped_column(String(160))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    diretiva: Mapped[Diretiva] = relationship(back_populates="requisitos")


class Auditoria(Base):
    __tablename__ = "auditorias"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(180), nullable=False)
    ano: Mapped[int] = mapped_column(Integer, nullable=False)
    ciclo: Mapped[str] = mapped_column(String(80), nullable=False)
    site_auditado_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), nullable=False)
    site_auditor_lider_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), nullable=False)
    site_auditor_apoio_id: Mapped[int | None] = mapped_column(ForeignKey("sites.id"))
    auditor_lider: Mapped[str | None] = mapped_column(String(120))
    auditor_apoio: Mapped[str | None] = mapped_column(String(120))
    data_planejada: Mapped[date | None] = mapped_column(Date)
    data_inicio: Mapped[date | None] = mapped_column(Date)
    data_fim: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(40), default="Planejada")
    escopo: Mapped[str | None] = mapped_column(Text)
    observacoes: Mapped[str | None] = mapped_column(Text)
    site_auditado: Mapped[Site] = relationship(foreign_keys=[site_auditado_id])
    site_auditor_lider: Mapped[Site] = relationship(foreign_keys=[site_auditor_lider_id])
    site_auditor_apoio: Mapped[Site | None] = relationship(foreign_keys=[site_auditor_apoio_id])


class RespostaChecklist(Base):
    __tablename__ = "respostas_checklist"
    __table_args__ = (UniqueConstraint("auditoria_id", "requisito_id", name="uq_auditoria_requisito"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    auditoria_id: Mapped[int] = mapped_column(ForeignKey("auditorias.id"), nullable=False)
    requisito_id: Mapped[int] = mapped_column(ForeignKey("requisitos.id"), nullable=False)
    aplicavel: Mapped[bool] = mapped_column(Boolean, default=True)
    status_conformidade: Mapped[str] = mapped_column(String(40), default="Conforme")
    nota_maturidade: Mapped[int | None] = mapped_column(Integer)
    evidencia_verificada: Mapped[str | None] = mapped_column(Text)
    comentario_auditor: Mapped[str | None] = mapped_column(Text)
    necessita_acao: Mapped[bool] = mapped_column(Boolean, default=False)
    data_avaliacao: Mapped[datetime | None] = mapped_column(DateTime)
    avaliado_por: Mapped[str | None] = mapped_column(String(120))
    auditoria: Mapped[Auditoria] = relationship()
    requisito: Mapped[Requisito] = relationship()


class Achado(Base):
    __tablename__ = "achados"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    auditoria_id: Mapped[int] = mapped_column(ForeignKey("auditorias.id"), nullable=False)
    requisito_id: Mapped[int | None] = mapped_column(ForeignKey("requisitos.id"))
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), nullable=False)
    tipo_achado: Mapped[str] = mapped_column(String(80), nullable=False)
    descricao: Mapped[str] = mapped_column(Text, nullable=False)
    evidencia: Mapped[str | None] = mapped_column(Text)
    risco: Mapped[str | None] = mapped_column(Text)
    causa_raiz: Mapped[str | None] = mapped_column(Text)
    acao_imediata: Mapped[str | None] = mapped_column(Text)
    acao_corretiva: Mapped[str | None] = mapped_column(Text)
    responsavel: Mapped[str | None] = mapped_column(String(120))
    prazo: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(40), default="Aberto")
    prioridade: Mapped[str] = mapped_column(String(20), default="Média")
    data_abertura: Mapped[date] = mapped_column(Date, default=date.today)
    data_conclusao: Mapped[date | None] = mapped_column(Date)
    verificacao_eficacia: Mapped[str | None] = mapped_column(Text)
    status_eficacia: Mapped[str | None] = mapped_column(String(80))
    auditoria: Mapped[Auditoria] = relationship()
    requisito: Mapped[Requisito | None] = relationship()
    site: Mapped[Site] = relationship()


class EvidenciaArquivo(Base):
    __tablename__ = "evidencias_arquivos"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    auditoria_id: Mapped[int] = mapped_column(ForeignKey("auditorias.id"), nullable=False)
    requisito_id: Mapped[int] = mapped_column(ForeignKey("requisitos.id"), nullable=False)
    achado_id: Mapped[int | None] = mapped_column(ForeignKey("achados.id"))
    nome_arquivo: Mapped[str] = mapped_column(String(240), nullable=False)
    caminho_arquivo: Mapped[str] = mapped_column(String(500), nullable=False)
    tipo_arquivo: Mapped[str | None] = mapped_column(String(120))
    data_upload: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    enviado_por: Mapped[str | None] = mapped_column(String(120))


engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


@contextmanager
def get_session():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def logical_requisito_codes() -> set[str]:
    return {f"{cat['codigo']}-{idx:02d}" for cat in CHECKLIST_BASE for idx, _ in enumerate(cat["perguntas"], 1)}


def criticidade_por_texto(pergunta: str) -> str:
    p = pergunta.lower()
    if any(t in p for t in ["legal", "licença", "nr-12", "emergência", "bloqueio", "energia perigosa", "produtos perigosos"]):
        return "Crítico"
    if any(t in p for t in ["risco", "incidente", "treinamento", "máquinas", "altura", "confinados"]):
        return "Alto"
    return "Médio"


def seed_base(session: Session) -> None:
    for codigo in SITES_PADRAO:
        site = session.query(Site).filter_by(codigo=codigo).one_or_none()
        if site is None:
            session.add(Site(codigo=codigo, nome=codigo, ativo=True))
        else:
            site.ativo = True
            site.nome = site.nome or codigo
    session.flush()

    primeiro_site = session.query(Site).filter_by(codigo="SJC").one_or_none()
    for nome, email, perfil in [("Admin EHS", "admin.ehs@empresa.local", "Admin_LAG"), ("Auditor EHS", "auditor.ehs@empresa.local", "Auditor"), ("Visualizador EHS", "visualizador.ehs@empresa.local", "Visualizador")]:
        user = session.query(Usuario).filter_by(email=email).one_or_none()
        if user is None:
            session.add(Usuario(nome=nome, email=email, perfil=perfil, site_id=primeiro_site.id if primeiro_site else None, ativo=True))
        else:
            user.ativo = True
            user.perfil = perfil
    session.flush()

    valid_codes = logical_requisito_codes()
    for cat in CHECKLIST_BASE:
        diretiva = session.query(Diretiva).filter_by(codigo=cat["codigo"]).one_or_none()
        if diretiva is None:
            diretiva = Diretiva(codigo=cat["codigo"], titulo=cat["titulo"], descricao=cat["descricao"], ativa=True)
            session.add(diretiva)
            session.flush()
        else:
            diretiva.titulo = cat["titulo"]
            diretiva.descricao = cat["descricao"]
            diretiva.ativa = True
            diretiva.observacao = None
        for idx, pergunta in enumerate(cat["perguntas"], 1):
            codigo_req = f"{cat['codigo']}-{idx:02d}"
            requisito = session.query(Requisito).filter_by(codigo_requisito=codigo_req).one_or_none()
            if requisito is None:
                session.add(Requisito(diretiva_id=diretiva.id, codigo_requisito=codigo_req, pergunta=pergunta, orientacao="Avaliar documentos, registros, entrevistas e verificação em campo.", criticidade=criticidade_por_texto(pergunta), tipo_evidencia_esperada="Documento / Registro / Entrevista / Campo", area_responsavel_sugerida="EHS / Área responsável", ativo=True))
            else:
                requisito.diretiva_id = diretiva.id
                requisito.pergunta = pergunta
                requisito.orientacao = requisito.orientacao or "Avaliar documentos, registros, entrevistas e verificação em campo."
                requisito.criticidade = requisito.criticidade if requisito.criticidade in CRITICIDADES else criticidade_por_texto(pergunta)
                requisito.tipo_evidencia_esperada = requisito.tipo_evidencia_esperada or "Documento / Registro / Entrevista / Campo"
                requisito.area_responsavel_sugerida = requisito.area_responsavel_sugerida or "EHS / Área responsável"
                requisito.ativo = True
    for requisito in session.query(Requisito).all():
        if requisito.codigo_requisito not in valid_codes:
            requisito.ativo = False
    for auditoria in session.query(Auditoria).all():
        ensure_auditoria_checklist(session, auditoria.id)


def init_db() -> None:
    Base.metadata.create_all(engine)
    with get_session() as session:
        seed_base(session)


def validate_seed(session: Session) -> dict[str, int | bool]:
    total_categorias = session.query(Diretiva).filter(Diretiva.codigo.in_([c["codigo"] for c in CHECKLIST_BASE]), Diretiva.ativa.is_(True)).count()
    total_requisitos = session.query(Requisito).filter(Requisito.codigo_requisito.in_(logical_requisito_codes()), Requisito.ativo.is_(True)).count()
    return {"categorias": total_categorias, "requisitos_ativos": total_requisitos, "base_ok": total_categorias == 8 and total_requisitos == 80}


def ensure_auditoria_checklist(session: Session, auditoria_id: int) -> int:
    existentes = {r.requisito_id for r in session.query(RespostaChecklist).filter_by(auditoria_id=auditoria_id).all()}
    criados = 0
    for requisito in session.query(Requisito).filter_by(ativo=True).all():
        if requisito.id not in existentes:
            session.add(RespostaChecklist(auditoria_id=auditoria_id, requisito_id=requisito.id, aplicavel=True, status_conformidade="Conforme", nota_maturidade=3))
            criados += 1
    return criados


def can_admin(user: Usuario | None) -> bool:
    return bool(user and user.perfil == "Admin_LAG")


def can_edit_audit(user: Usuario | None, auditoria: Auditoria | None = None) -> bool:
    if not user or user.perfil == "Visualizador":
        return False
    if user.perfil in ["Admin_LAG", "Auditor"]:
        return True
    if user.perfil == "EHS_Local" and auditoria and user.site_id == auditoria.site_auditado_id:
        return True
    return user.perfil == "EHS_Local" and auditoria is None


def can_edit_action(user: Usuario | None, achado: Achado | None = None) -> bool:
    if not user or user.perfil == "Visualizador":
        return False
    if user.perfil in ["Admin_LAG", "Auditor", "EHS_Local"]:
        return True
    return bool(achado and user.perfil == "Responsavel_Acao" and achado.responsavel and achado.responsavel.lower() == user.nome.lower())


def conformidade_percentual(df: pd.DataFrame) -> float:
    if df.empty or "status" not in df:
        return 0.0
    valid = df[df["status"] != "Não Aplicável"]
    if valid.empty:
        return 0.0
    pontos = valid["status"].map({"Conforme": 1, "Parcialmente Conforme": 0.5, "Não Conforme": 0, "Não Aplicável": None}).fillna(0)
    return round(float(pontos.mean() * 100), 1)


def maturidade_media(df: pd.DataFrame) -> float:
    if df.empty or "nota_maturidade" not in df or "status" not in df:
        return 0.0
    valid = df[(df["status"] != "Não Aplicável") & (df["nota_maturidade"].notna())]
    return round(float(valid["nota_maturidade"].mean()), 2) if not valid.empty else 0.0


def classificar_resultado(conformidade: float, nc_critica_aberta: bool = False) -> str:
    if conformidade >= 90 and not nc_critica_aberta:
        return "Referência / Maduro"
    if conformidade >= 75:
        return "Conforme com oportunidades de melhoria"
    if conformidade >= 50:
        return "Parcialmente conforme / requer plano robusto"
    return "Não conforme / requer intervenção"


def respostas_df(session: Session, auditoria_id: int | None = None) -> pd.DataFrame:
    q = session.query(RespostaChecklist, Auditoria, Requisito, Diretiva, Site).join(Auditoria, RespostaChecklist.auditoria_id == Auditoria.id).join(Requisito, RespostaChecklist.requisito_id == Requisito.id).join(Diretiva, Requisito.diretiva_id == Diretiva.id).join(Site, Auditoria.site_auditado_id == Site.id)
    if auditoria_id:
        q = q.filter(Auditoria.id == auditoria_id)
    rows = []
    for resp, aud, req, dir_, site in q.all():
        rows.append({"id": resp.id, "auditoria_id": aud.id, "auditoria": aud.nome, "site": site.codigo, "ciclo": aud.ciclo, "diretiva": dir_.titulo, "codigo_requisito": req.codigo_requisito, "pergunta": req.pergunta, "criticidade": req.criticidade, "aplicavel": resp.aplicavel, "status": resp.status_conformidade, "nota_maturidade": resp.nota_maturidade, "evidencia_verificada": resp.evidencia_verificada or "", "comentario_auditor": resp.comentario_auditor or "", "necessita_acao": resp.necessita_acao})
    return pd.DataFrame(rows, columns=RESPOSTAS_COLUMNS)


def achados_df(session: Session, auditoria_id: int | None = None) -> pd.DataFrame:
    q = session.query(Achado, Auditoria, Site, Requisito).join(Auditoria, Achado.auditoria_id == Auditoria.id).join(Site, Achado.site_id == Site.id).outerjoin(Requisito, Achado.requisito_id == Requisito.id)
    if auditoria_id:
        q = q.filter(Auditoria.id == auditoria_id)
    rows = []
    today = date.today()
    for ach, aud, site, req in q.all():
        vencido = bool(ach.prazo and ach.prazo < today and ach.status not in ["Concluído", "Cancelado"])
        rows.append({"id": ach.id, "auditoria": aud.nome, "site": site.codigo, "requisito": req.codigo_requisito if req else "-", "tipo_achado": ach.tipo_achado, "descricao": ach.descricao, "responsavel": ach.responsavel or "", "prazo": ach.prazo, "status": "Vencido" if vencido else ach.status, "prioridade": ach.prioridade, "vencido": vencido})
    return pd.DataFrame(rows, columns=ACHADOS_COLUMNS)


def pontuacao_por(df: pd.DataFrame, coluna: str) -> pd.DataFrame:
    if df.empty or coluna not in df:
        return pd.DataFrame(columns=[coluna, "conformidade", "maturidade"])
    return pd.DataFrame([{coluna: valor, "conformidade": conformidade_percentual(grupo), "maturidade": maturidade_media(grupo)} for valor, grupo in df.groupby(coluna)], columns=[coluna, "conformidade", "maturidade"])


def dashboard_kpis(session: Session) -> dict[str, int | float]:
    df = respostas_df(session)
    ach = achados_df(session)
    return {"planejadas": session.query(Auditoria).filter_by(status="Planejada").count(), "em_andamento": session.query(Auditoria).filter_by(status="Em andamento").count(), "concluidas": session.query(Auditoria).filter_by(status="Concluída").count(), "conformidade_media": conformidade_percentual(df), "maturidade_media": maturidade_media(df), "achados_abertos": int(ach["status"].isin(["Aberto", "Em andamento", "Vencido"]).sum()) if not ach.empty else 0, "achados_vencidos": int(ach["vencido"].sum()) if not ach.empty else 0, "nc_criticas_abertas": session.query(Achado).filter(Achado.tipo_achado == "Não conformidade crítica", Achado.status.in_(["Aberto", "Em andamento", "Vencido"])).count()}


def criar_auditoria(session: Session, **data) -> Auditoria:
    if data["site_auditado_id"] == data["site_auditor_lider_id"]:
        raise ValueError("O site auditado deve ser diferente do site auditor líder.")
    auditoria = Auditoria(**data)
    session.add(auditoria)
    session.flush()
    ensure_auditoria_checklist(session, auditoria.id)
    return auditoria


def salvar_respostas(session: Session, edited_df: pd.DataFrame, avaliado_por: str | None) -> None:
    for row in edited_df.to_dict("records"):
        resp = session.get(RespostaChecklist, int(row["id"]))
        if not resp:
            continue
        nota = row.get("nota_maturidade")
        resp.aplicavel = bool(row.get("aplicavel", True))
        resp.status_conformidade = "Não Aplicável" if not resp.aplicavel else row.get("status", "Conforme")
        resp.nota_maturidade = None if pd.isna(nota) else max(0, min(5, int(nota)))
        resp.evidencia_verificada = row.get("evidencia_verificada", "")
        resp.comentario_auditor = row.get("comentario_auditor", "")
        resp.necessita_acao = bool(row.get("necessita_acao", False))
        resp.avaliado_por = avaliado_por
        resp.data_avaliacao = datetime.utcnow()


def salvar_upload(uploaded_file, auditoria_id: int, requisito_id: int, achado_id: int | None, enviado_por: str | None, session: Session) -> None:
    safe_name = Path(uploaded_file.name).name
    path = UPLOAD_DIR / f"aud{auditoria_id}_req{requisito_id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}_{safe_name}"
    path.write_bytes(uploaded_file.getbuffer())
    session.add(EvidenciaArquivo(auditoria_id=auditoria_id, requisito_id=requisito_id, achado_id=achado_id, nome_arquivo=safe_name, caminho_arquivo=str(path), tipo_arquivo=getattr(uploaded_file, "type", None), enviado_por=enviado_por))


def pdf_text(value: object) -> str:
    return escape("" if value is None else str(value))


def export_checklist_excel(session: Session, auditoria_id: int) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        respostas_df(session, auditoria_id).to_excel(writer, index=False, sheet_name="Checklist")
    output.seek(0)
    return output.read()


def export_plano_acao_excel(session: Session, auditoria_id: int) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        achados_df(session, auditoria_id).to_excel(writer, index=False, sheet_name="PAC")
    output.seek(0)
    return output.read()


def export_relatorio_pdf(session: Session, auditoria_id: int) -> bytes:
    auditoria = session.get(Auditoria, auditoria_id)
    df = respostas_df(session, auditoria_id)
    ach = achados_df(session, auditoria_id)
    conformidade = conformidade_percentual(df)
    maturidade = maturidade_media(df)
    nc_critica = bool(not ach.empty and ((ach["tipo_achado"] == "Não conformidade crítica") & (ach["status"].isin(["Aberto", "Em andamento", "Vencido"]))).any())
    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4)
    styles = getSampleStyleSheet()
    story = [Paragraph(APP_TITLE, styles["Title"]), Spacer(1, 10)]
    story.append(Paragraph(f"Auditoria: {pdf_text(auditoria.nome if auditoria else auditoria_id)}", styles["Heading2"]))
    story.append(Paragraph(f"Conformidade: {conformidade}% | Maturidade: {maturidade} | Resultado: {pdf_text(classificar_resultado(conformidade, nc_critica))}", styles["BodyText"]))
    story.append(Spacer(1, 12))
    resultado = pontuacao_por(df, "diretiva")
    table_data = [["Categoria", "Conformidade", "Maturidade"]] + resultado.round(2).astype(str).values.tolist() if not resultado.empty else [["Categoria", "Conformidade", "Maturidade"]]
    table = Table(table_data, repeatRows=1)
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#12263f")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("GRID", (0, 0), (-1, -1), 0.25, colors.grey), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold")]))
    story.append(table)
    story.append(Spacer(1, 12))
    story.append(Paragraph("Principais registros do PAC", styles["Heading2"]))
    if ach.empty:
        story.append(Paragraph("Não há registros de PAC para esta auditoria.", styles["BodyText"]))
    else:
        for item in ach.head(10).to_dict("records"):
            story.append(Paragraph(f"{pdf_text(item['tipo_achado'])} - {pdf_text(item['descricao'])} - {pdf_text(item['status'])}", styles["BodyText"]))
    story.append(Spacer(1, 12))
    story.append(Paragraph("Conclusão: utilizar este relatório como base para reunião de fechamento, priorização do PAC e acompanhamento de EHS.", styles["BodyText"]))
    doc.build(story)
    output.seek(0)
    return output.read()


def apply_theme() -> None:
    st.markdown("""
        <style>
        :root {--brand-bg:#f6f8fb;--card-bg:#ffffff;--muted:#5f6b7a;--border:#e7ebf3;--title:#12263f;--accent:#1f4bb8;--gold-1:#ffcd61;--gold-2:#ffb91d;}
        .stApp {background:var(--brand-bg);} .block-container {padding-top:1.4rem;padding-bottom:2.2rem;}
        section[data-testid="stSidebar"] {background:linear-gradient(180deg,var(--gold-1) 0%,var(--gold-2) 100%) !important;border-right:1px solid rgba(18,38,63,.12);}
        section[data-testid="stSidebar"] * {color:#1f1f1f !important;} section[data-testid="stSidebar"] [data-testid="stRadio"] label {font-weight:700;}
        .page-header {background:var(--card-bg);border:1px solid var(--border);border-radius:14px;padding:1rem 1.2rem;margin-bottom:1rem;box-shadow:0 4px 16px rgba(18,38,63,.05);} .page-header h1 {margin:0;font-size:1.55rem;color:var(--title);} .page-header p {margin:.35rem 0 0;color:var(--muted);font-size:.94rem;}
        div[data-testid="stForm"], div[data-testid="stExpander"] {background:var(--card-bg);border:1px solid var(--border);border-radius:12px;padding:.85rem 1rem;box-shadow:0 2px 8px rgba(18,38,63,.04);} .section-title {margin:1.1rem 0 .55rem;color:var(--title);font-size:1.08rem;font-weight:700;}
        .kpi-card {border:1px solid var(--border);background:var(--card-bg);border-radius:12px;padding:.9rem 1rem;box-shadow:0 2px 8px rgba(18,38,63,.04);min-height:88px;} .kpi-label {color:var(--muted);font-size:.78rem;margin-bottom:.15rem;} .kpi-value {color:var(--title);font-size:1.25rem;font-weight:800;}
        .stButton button, .stDownloadButton button {border-radius:10px !important;border:1px solid #d9e0ec !important;font-weight:700 !important;} .stButton button[kind="primary"] {background:var(--accent) !important;color:white !important;} div[data-testid="stDataFrame"], div[data-testid="stDataEditor"] {border-radius:12px;overflow:hidden;}
        </style>
    """, unsafe_allow_html=True)


def header(title: str, subtitle: str = "") -> None:
    st.markdown(f"<div class='page-header'><h1>{escape(title)}</h1><p>{escape(subtitle)}</p></div>", unsafe_allow_html=True)


def section(title: str) -> None:
    st.markdown(f"<div class='section-title'>{escape(title)}</div>", unsafe_allow_html=True)


def kpi_card(label: str, value: str | int | float) -> None:
    st.markdown(f"<div class='kpi-card'><div class='kpi-label'>{escape(str(label))}</div><div class='kpi-value'>{escape(str(value))}</div></div>", unsafe_allow_html=True)


def sidebar_user(session: Session) -> Usuario | None:
    st.sidebar.markdown("### Auditoria EHS")
    st.sidebar.caption("Gestão corporativa de auditorias cruzadas")
    usuarios = session.query(Usuario).filter_by(ativo=True).order_by(Usuario.nome).all()
    if not usuarios:
        st.sidebar.warning("Nenhum usuário ativo.")
        return None
    labels = {u.id: f"{u.nome} · {u.perfil}" for u in usuarios}
    selected_id = st.sidebar.selectbox("Usuário", list(labels), format_func=lambda user_id: labels[user_id])
    return session.get(Usuario, selected_id)


def select_auditoria(session: Session, label: str = "Auditoria") -> Auditoria | None:
    auditorias = session.query(Auditoria).order_by(Auditoria.ano.desc(), Auditoria.id.desc()).all()
    if not auditorias:
        st.info("Crie uma auditoria para utilizar esta tela.")
        return None
    labels = {a.id: f"#{a.id} · {a.nome} · {a.status}" for a in auditorias}
    selected_id = st.selectbox(label, list(labels), format_func=lambda audit_id: labels[audit_id])
    return session.get(Auditoria, selected_id)


def page_dashboard(session: Session) -> None:
    header("Dashboard EHS", "Visão consolidada de auditorias, conformidade, maturidade e PAC.")
    k = dashboard_kpis(session)
    cols = st.columns(8)
    metrics = [("Planejadas", k["planejadas"]), ("Em andamento", k["em_andamento"]), ("Concluídas", k["concluidas"]), ("Conformidade média", f"{k['conformidade_media']}%"), ("Maturidade média", k["maturidade_media"]), ("PAC aberto", k["achados_abertos"]), ("PAC vencido", k["achados_vencidos"]), ("NC críticas", k["nc_criticas_abertas"])]
    for col, (label, value) in zip(cols, metrics):
        with col:
            kpi_card(label, value)
    if k["achados_vencidos"] or k["nc_criticas_abertas"]:
        st.error("Há ações vencidas ou não conformidades críticas abertas que exigem priorização.")
    df = respostas_df(session)
    ach = achados_df(session)
    if df.empty:
        st.info("Crie uma auditoria para habilitar os gráficos.")
        return
    site_score = pontuacao_por(df, "site")
    cat_score = pontuacao_por(df, "diretiva")
    c1, c2 = st.columns(2)
    c1.plotly_chart(px.bar(site_score, x="site", y="conformidade", title="Conformidade por site", text_auto=True, range_y=[0, 100], color_discrete_sequence=["#1f4bb8"]), use_container_width=True)
    c2.plotly_chart(px.bar(site_score, x="site", y="maturidade", title="Maturidade por site", text_auto=True, range_y=[0, 5], color_discrete_sequence=["#ffb91d"]), use_container_width=True)
    c3, c4 = st.columns(2)
    c3.plotly_chart(px.bar(cat_score, x="diretiva", y="conformidade", title="Conformidade por categoria", text_auto=True, range_y=[0, 100], color_discrete_sequence=["#12263f"]), use_container_width=True)
    if not ach.empty:
        c4.plotly_chart(px.pie(ach, names="tipo_achado", title="Registros por tipo"), use_container_width=True)
        st.plotly_chart(px.bar(ach.groupby("status", as_index=False).size(), x="status", y="size", title="PAC por status", text_auto=True, color_discrete_sequence=["#1f4bb8"]), use_container_width=True)
    heat_rows = [{"site": site_, "diretiva": diretiva, "conformidade": conformidade_percentual(group)} for (site_, diretiva), group in df.groupby(["site", "diretiva"])]
    hdf = pd.DataFrame(heat_rows)
    if not hdf.empty:
        st.plotly_chart(px.imshow(hdf.pivot(index="site", columns="diretiva", values="conformidade"), title="Heatmap site x categoria", aspect="auto", color_continuous_scale="RdYlGn", zmin=0, zmax=100), use_container_width=True)
    section("Top 10 maiores gaps")
    gaps = df[df["status"].isin(["Não Conforme", "Parcialmente Conforme"])].head(10)
    st.dataframe(gaps[["site", "diretiva", "codigo_requisito", "criticidade", "status", "pergunta"]], use_container_width=True, hide_index=True)


def page_planejamento(session: Session, user: Usuario | None) -> None:
    header("Planejar auditoria", "Crie a auditoria e gere automaticamente o checklist corporativo.")
    sites = session.query(Site).filter_by(ativo=True).order_by(Site.codigo).all()
    total_reqs = session.query(Requisito).filter_by(ativo=True).count()
    cinfo1, cinfo2, cinfo3 = st.columns(3)
    with cinfo1: kpi_card("Sites disponíveis", len(sites))
    with cinfo2: kpi_card("Itens do checklist", total_reqs)
    with cinfo3: kpi_card("Categorias", len(CHECKLIST_BASE))
    if not sites:
        st.error("Cadastre ao menos um site ativo antes de criar auditorias.")
        return
    section("Nova auditoria")
    with st.form("nova_auditoria"):
        c1, c2, c3 = st.columns([1, 1.2, 1])
        ano = c1.number_input("Ano", min_value=2020, max_value=2100, value=date.today().year)
        ciclo = c2.text_input("Ciclo", value=f"Ciclo {date.today().year}-1")
        data_planejada = c3.date_input("Data planejada", value=date.today())
        c4, c5, c6 = st.columns(3)
        site_auditado = c4.selectbox("Site auditado", sites, format_func=lambda s: s.codigo)
        site_lider = c5.selectbox("Site auditor líder", sites, index=1 if len(sites) > 1 else 0, format_func=lambda s: s.codigo)
        site_apoio = c6.selectbox("Site auditor apoio", [None] + sites, format_func=lambda s: "Sem apoio" if s is None else s.codigo)
        c7, c8 = st.columns(2)
        auditor_lider = c7.text_input("Auditor líder", value=user.nome if user else "")
        auditor_apoio = c8.text_input("Auditor apoio")
        escopo = st.text_area("Escopo", value="Checklist corporativo de Auditoria Cruzada de EHS Directives.", height=80)
        observacoes = st.text_area("Observações", height=80)
        submitted = st.form_submit_button("Criar auditoria", type="primary", disabled=not can_edit_audit(user))
    if submitted:
        try:
            auditoria = criar_auditoria(session, nome=f"Auditoria Cruzada {site_auditado.codigo} - {ciclo}", ano=int(ano), ciclo=ciclo, site_auditado_id=site_auditado.id, site_auditor_lider_id=site_lider.id, site_auditor_apoio_id=site_apoio.id if site_apoio else None, auditor_lider=auditor_lider, auditor_apoio=auditor_apoio, data_planejada=data_planejada, status="Planejada", escopo=escopo, observacoes=observacoes)
            st.success(f"Auditoria #{auditoria.id} criada com {total_reqs} itens de checklist.")
        except ValueError as exc:
            st.error(str(exc))
    section("Auditorias cadastradas")
    auds = session.query(Auditoria).order_by(Auditoria.id.desc()).all()
    aud_cols = ["ID", "Nome", "Site", "Ciclo", "Data planejada", "Status"]
    st.dataframe(pd.DataFrame([{"ID": a.id, "Nome": a.nome, "Site": a.site_auditado.codigo, "Ciclo": a.ciclo, "Data planejada": a.data_planejada, "Status": a.status} for a in auds], columns=aud_cols), use_container_width=True, hide_index=True)


def page_checklist(session: Session, user: Usuario | None) -> None:
    header("Executar checklist", "Responda os itens, registre evidências e indique necessidade de PAC.")
    auditoria = select_auditoria(session)
    if not auditoria:
        return
    ensure_auditoria_checklist(session, auditoria.id)
    editable = can_edit_audit(user, auditoria)
    df = respostas_df(session, auditoria.id)
    if df.empty:
        st.warning("Não há requisitos ativos para esta auditoria. Reexecute o seed da base ou revise a Base do Checklist.")
        return
    c1, c2, c3 = st.columns(3)
    categoria = c1.selectbox("Categoria", ["Todas"] + sorted(df["diretiva"].unique().tolist()))
    status = c2.selectbox("Status", ["Todos"] + STATUS_CONFORMIDADE)
    criticidade = c3.selectbox("Criticidade", ["Todas"] + CRITICIDADES)
    filtered = df.copy()
    if categoria != "Todas": filtered = filtered[filtered["diretiva"] == categoria]
    if status != "Todos": filtered = filtered[filtered["status"] == status]
    if criticidade != "Todas": filtered = filtered[filtered["criticidade"] == criticidade]
    display_cols = ["id", "diretiva", "codigo_requisito", "criticidade", "pergunta", "aplicavel", "status", "nota_maturidade", "evidencia_verificada", "comentario_auditor", "necessita_acao"]
    edited = st.data_editor(filtered[display_cols], hide_index=True, use_container_width=True, disabled=["id", "diretiva", "codigo_requisito", "criticidade", "pergunta"] if editable else display_cols, column_config={"status": st.column_config.SelectboxColumn("Status", options=STATUS_CONFORMIDADE), "nota_maturidade": st.column_config.NumberColumn("Maturidade", min_value=0, max_value=5, step=1), "necessita_acao": st.column_config.CheckboxColumn("Gerar PAC?"), "evidencia_verificada": st.column_config.TextColumn("Evidência"), "comentario_auditor": st.column_config.TextColumn("Observação")}, key=f"editor_{auditoria.id}")
    if st.button("Salvar respostas", type="primary", disabled=not editable):
        salvar_respostas(session, edited, user.nome if user else None)
        st.success("Respostas salvas.")
    desvios = edited[(edited["status"].isin(["Não Conforme", "Parcialmente Conforme"])) | (edited["necessita_acao"] == True)]
    with st.expander(f"Itens com indicação de PAC ({len(desvios)})"):
        st.dataframe(desvios[["codigo_requisito", "criticidade", "status", "pergunta"]], use_container_width=True, hide_index=True)
        if not desvios.empty:
            selected_id = st.selectbox("Item para registrar PAC", desvios["id"].tolist(), format_func=lambda rid: f"Resposta #{rid}")
            resp = session.get(RespostaChecklist, int(selected_id))
            if resp:
                with st.form("novo_pac_checklist"):
                    tipo = st.selectbox("Tipo", TIPOS_ACHADO)
                    descricao = st.text_area("Descrição", value=resp.requisito.pergunta)
                    evidencia = st.text_area("Evidência")
                    acao = st.text_area("Ação corretiva")
                    c1, c2, c3 = st.columns(3)
                    responsavel = c1.text_input("Responsável")
                    prazo = c2.date_input("Prazo", value=date.today())
                    prioridade = c3.selectbox("Prioridade", PRIORIDADES)
                    if st.form_submit_button("Criar PAC", disabled=not editable):
                        session.add(Achado(auditoria_id=auditoria.id, requisito_id=resp.requisito_id, site_id=auditoria.site_auditado_id, tipo_achado=tipo, descricao=descricao, evidencia=evidencia, acao_corretiva=acao, responsavel=responsavel, prazo=prazo, prioridade=prioridade, status="Aberto"))
                        st.success("PAC criado.")
    with st.expander("Anexar evidência ao item"):
        reqs = session.query(Requisito).filter_by(ativo=True).order_by(Requisito.codigo_requisito).all()
        if not reqs:
            st.info("Não há requisitos ativos para anexar evidências.")
        else:
            req_labels = {r.id: f"{r.codigo_requisito} · {r.pergunta[:80]}" for r in reqs}
            req_id = st.selectbox("Item", list(req_labels), format_func=lambda item_id: req_labels[item_id])
            uploaded = st.file_uploader("Arquivo de evidência")
            if uploaded and st.button("Salvar evidência", disabled=not editable):
                salvar_upload(uploaded, auditoria.id, req_id, None, user.nome if user else None, session)
                st.success("Evidência salva.")


def page_pac(session: Session, user: Usuario | None) -> None:
    header("Achados / PAC", "Plano de Ação Corretiva para desvios, observações e oportunidades de melhoria.")
    ach = achados_df(session)
    if ach.empty:
        st.info("Nenhum registro de PAC cadastrado.")
    else:
        c1, c2, c3, c4 = st.columns(4)
        sites = ["Todos"] + sorted(ach["site"].unique().tolist())
        tipos = ["Todos"] + TIPOS_ACHADO
        status_opts = ["Todos"] + list(dict.fromkeys(STATUS_ACHADO + ["Vencido"]))
        site_filter = c1.selectbox("Site", sites)
        tipo_filter = c2.selectbox("Tipo", tipos)
        status_filter = c3.selectbox("Status", status_opts)
        vencidos = c4.checkbox("Somente vencidos")
        filtered = ach.copy()
        if site_filter != "Todos": filtered = filtered[filtered["site"] == site_filter]
        if tipo_filter != "Todos": filtered = filtered[filtered["tipo_achado"] == tipo_filter]
        if status_filter != "Todos": filtered = filtered[filtered["status"] == status_filter]
        if vencidos: filtered = filtered[filtered["vencido"] == True]
        st.dataframe(filtered, use_container_width=True, hide_index=True)
    registros = session.query(Achado).order_by(Achado.id.desc()).all()
    if registros:
        section("Editar PAC")
        labels = {a.id: f"#{a.id} · {a.tipo_achado} · {a.status}" for a in registros}
        achado_id = st.selectbox("Registro", list(labels), format_func=lambda item_id: labels[item_id])
        achado = session.get(Achado, achado_id)
        if not achado:
            st.warning("Registro de PAC não encontrado.")
            return
        with st.form("editar_pac"):
            tipo = st.selectbox("Tipo", TIPOS_ACHADO, index=TIPOS_ACHADO.index(achado.tipo_achado) if achado.tipo_achado in TIPOS_ACHADO else 0)
            descricao = st.text_area("Descrição", value=achado.descricao)
            evidencia = st.text_area("Evidência", value=achado.evidencia or "")
            risco = st.text_area("Risco", value=achado.risco or "")
            causa = st.text_area("Causa raiz", value=achado.causa_raiz or "")
            acao_imediata = st.text_area("Ação imediata", value=achado.acao_imediata or "")
            acao_corretiva = st.text_area("Ação corretiva", value=achado.acao_corretiva or "")
            c1, c2, c3 = st.columns(3)
            responsavel = c1.text_input("Responsável", value=achado.responsavel or "")
            prazo = c2.date_input("Prazo", value=achado.prazo or date.today())
            prioridade = c3.selectbox("Prioridade", PRIORIDADES, index=PRIORIDADES.index(achado.prioridade) if achado.prioridade in PRIORIDADES else 1)
            c4, c5 = st.columns(2)
            status = c4.selectbox("Status", STATUS_ACHADO, index=STATUS_ACHADO.index(achado.status) if achado.status in STATUS_ACHADO else 0)
            data_conclusao = c5.date_input("Data de conclusão", value=achado.data_conclusao or date.today())
            eficacia = st.text_area("Verificação de eficácia", value=achado.verificacao_eficacia or "")
            status_eficacia = st.text_input("Status da eficácia", value=achado.status_eficacia or "")
            if st.form_submit_button("Salvar PAC", type="primary", disabled=not can_edit_action(user, achado)):
                achado.tipo_achado = tipo
                achado.descricao = descricao
                achado.evidencia = evidencia
                achado.risco = risco
                achado.causa_raiz = causa
                achado.acao_imediata = acao_imediata
                achado.acao_corretiva = acao_corretiva
                achado.responsavel = responsavel
                achado.prazo = prazo
                achado.prioridade = prioridade
                achado.status = status
                achado.data_conclusao = data_conclusao if status == "Concluído" else None
                achado.verificacao_eficacia = eficacia
                achado.status_eficacia = status_eficacia
                st.success("PAC atualizado.")


def page_relatorios(session: Session) -> None:
    header("Relatórios e exportações", "Gere relatório PDF, checklist e plano de ação por auditoria.")
    auditoria = select_auditoria(session)
    if not auditoria:
        return
    df = respostas_df(session, auditoria.id)
    ach = achados_df(session, auditoria.id)
    c1, c2, c3 = st.columns(3)
    with c1: kpi_card("Conformidade", f"{conformidade_percentual(df)}%")
    with c2: kpi_card("Maturidade", maturidade_media(df))
    with c3: kpi_card("Registros PAC", len(ach))
    st.download_button("Exportar relatório PDF", export_relatorio_pdf(session, auditoria.id), file_name=f"relatorio_auditoria_{auditoria.id}.pdf", mime="application/pdf")
    st.download_button("Exportar checklist Excel", export_checklist_excel(session, auditoria.id), file_name=f"checklist_auditoria_{auditoria.id}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    st.download_button("Exportar plano de ação Excel", export_plano_acao_excel(session, auditoria.id), file_name=f"plano_acao_auditoria_{auditoria.id}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    section("Resultado por categoria")
    st.dataframe(pontuacao_por(df, "diretiva"), use_container_width=True, hide_index=True)


def page_base(session: Session, user: Usuario | None) -> None:
    header("Base do Checklist", "Categorias e perguntas incorporadas ao sistema.")
    valid = validate_seed(session)
    c1, c2, c3 = st.columns(3)
    with c1: kpi_card("Categorias", valid["categorias"])
    with c2: kpi_card("Requisitos ativos", valid["requisitos_ativos"])
    with c3: kpi_card("Base", "OK" if valid["base_ok"] else "Revisar")
    if st.button("Reexecutar seed da base", disabled=not can_admin(user)):
        seed_base(session)
        st.success("Base sincronizada.")
    section("Categorias")
    dirs = session.query(Diretiva).filter(Diretiva.codigo.in_([c["codigo"] for c in CHECKLIST_BASE])).order_by(Diretiva.codigo).all()
    st.dataframe(pd.DataFrame([{"Código": d.codigo, "Título": d.titulo, "Descrição": d.descricao, "Ativa": d.ativa} for d in dirs], columns=["Código", "Título", "Descrição", "Ativa"]), use_container_width=True, hide_index=True)
    section("Requisitos")
    reqs = session.query(Requisito).filter(Requisito.codigo_requisito.in_(logical_requisito_codes())).order_by(Requisito.codigo_requisito).all()
    req_df = pd.DataFrame([{"id": r.id, "Código": r.codigo_requisito, "Categoria": r.diretiva.titulo, "Pergunta": r.pergunta, "Criticidade": r.criticidade, "Ativo": r.ativo} for r in reqs], columns=["id", "Código", "Categoria", "Pergunta", "Criticidade", "Ativo"])
    edited = st.data_editor(req_df, hide_index=True, use_container_width=True, disabled=["id", "Código", "Categoria", "Pergunta"], column_config={"Criticidade": st.column_config.SelectboxColumn("Criticidade", options=CRITICIDADES), "Ativo": st.column_config.CheckboxColumn("Ativo")})
    if st.button("Salvar ajustes", type="primary", disabled=not can_admin(user)):
        for row in edited.to_dict("records"):
            req = session.get(Requisito, int(row["id"]))
            if req:
                req.criticidade = row["Criticidade"]
                req.ativo = bool(row["Ativo"])
        st.success("Ajustes salvos.")


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, page_icon="🛡️", layout="wide")
    apply_theme()
    try:
        init_db()
    except Exception as exc:
        st.error("Erro ao inicializar o banco de dados da auditoria cruzada.")
        st.exception(exc)
        st.stop()
    with get_session() as session:
        user = sidebar_user(session)
        page = st.sidebar.radio("Navegação", ["Dashboard", "Planejar auditoria", "Executar checklist", "Achados / PAC", "Relatórios", "Base do Checklist"])
        if page == "Dashboard":
            page_dashboard(session)
        elif page == "Planejar auditoria":
            page_planejamento(session, user)
        elif page == "Executar checklist":
            page_checklist(session, user)
        elif page == "Achados / PAC":
            page_pac(session, user)
        elif page == "Relatórios":
            page_relatorios(session)
        elif page == "Base do Checklist":
            page_base(session, user)


if __name__ == "__main__":
    main()
