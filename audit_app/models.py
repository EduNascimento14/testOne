from datetime import date, datetime

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Site(Base):
    __tablename__ = "sites"

    id = Column(Integer, primary_key=True)
    codigo = Column(String(20), unique=True, nullable=False)
    nome = Column(String(120), nullable=False)
    ativo = Column(Boolean, default=True)


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True)
    nome = Column(String(120), nullable=False)
    email = Column(String(160), unique=True, nullable=False)
    site_id = Column(Integer, ForeignKey("sites.id"))
    perfil = Column(String(40), nullable=False)
    ativo = Column(Boolean, default=True)
    site = relationship("Site")


class Diretiva(Base):
    __tablename__ = "diretivas"

    id = Column(Integer, primary_key=True)
    codigo = Column(String(30), unique=True, nullable=False)
    titulo = Column(String(220), nullable=False)
    descricao = Column(Text)
    ativa = Column(Boolean, default=True)
    observacao = Column(Text)
    requisitos = relationship("Requisito", back_populates="diretiva")


class Requisito(Base):
    __tablename__ = "requisitos"

    id = Column(Integer, primary_key=True)
    diretiva_id = Column(Integer, ForeignKey("diretivas.id"), nullable=False)
    codigo_requisito = Column(String(60), unique=True, nullable=False)
    pergunta = Column(Text, nullable=False)
    orientacao = Column(Text)
    criticidade = Column(String(20), default="Médio")
    tipo_evidencia_esperada = Column(String(160))
    area_responsavel_sugerida = Column(String(160))
    ativo = Column(Boolean, default=True)
    diretiva = relationship("Diretiva", back_populates="requisitos")


class Auditoria(Base):
    __tablename__ = "auditorias"

    id = Column(Integer, primary_key=True)
    nome = Column(String(180), nullable=False)
    ano = Column(Integer, nullable=False)
    ciclo = Column(String(80), nullable=False)
    site_auditado_id = Column(Integer, ForeignKey("sites.id"), nullable=False)
    site_auditor_lider_id = Column(Integer, ForeignKey("sites.id"), nullable=False)
    site_auditor_apoio_id = Column(Integer, ForeignKey("sites.id"))
    auditor_lider = Column(String(120))
    auditor_apoio = Column(String(120))
    data_planejada = Column(Date)
    data_inicio = Column(Date)
    data_fim = Column(Date)
    status = Column(String(40), default="Planejada")
    escopo = Column(Text)
    observacoes = Column(Text)
    site_auditado = relationship("Site", foreign_keys=[site_auditado_id])
    site_auditor_lider = relationship("Site", foreign_keys=[site_auditor_lider_id])
    site_auditor_apoio = relationship("Site", foreign_keys=[site_auditor_apoio_id])


class RespostaChecklist(Base):
    __tablename__ = "respostas_checklist"
    __table_args__ = (UniqueConstraint("auditoria_id", "requisito_id", name="uq_auditoria_requisito"),)

    id = Column(Integer, primary_key=True)
    auditoria_id = Column(Integer, ForeignKey("auditorias.id"), nullable=False)
    requisito_id = Column(Integer, ForeignKey("requisitos.id"), nullable=False)
    aplicavel = Column(Boolean, default=True)
    status_conformidade = Column(String(40), default="Conforme")
    nota_maturidade = Column(Integer)
    evidencia_verificada = Column(Text)
    comentario_auditor = Column(Text)
    necessita_acao = Column(Boolean, default=False)
    data_avaliacao = Column(DateTime)
    avaliado_por = Column(String(120))
    auditoria = relationship("Auditoria")
    requisito = relationship("Requisito")


class Achado(Base):
    __tablename__ = "achados"

    id = Column(Integer, primary_key=True)
    auditoria_id = Column(Integer, ForeignKey("auditorias.id"), nullable=False)
    requisito_id = Column(Integer, ForeignKey("requisitos.id"))
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False)
    tipo_achado = Column(String(80), nullable=False)
    descricao = Column(Text, nullable=False)
    evidencia = Column(Text)
    risco = Column(Text)
    causa_raiz = Column(Text)
    acao_imediata = Column(Text)
    acao_corretiva = Column(Text)
    responsavel = Column(String(120))
    prazo = Column(Date)
    status = Column(String(40), default="Aberto")
    prioridade = Column(String(20), default="Média")
    data_abertura = Column(Date, default=date.today)
    data_conclusao = Column(Date)
    verificacao_eficacia = Column(Text)
    status_eficacia = Column(String(80))
    auditoria = relationship("Auditoria")
    requisito = relationship("Requisito")
    site = relationship("Site")


class EvidenciaArquivo(Base):
    __tablename__ = "evidencias_arquivos"

    id = Column(Integer, primary_key=True)
    auditoria_id = Column(Integer, ForeignKey("auditorias.id"), nullable=False)
    requisito_id = Column(Integer, ForeignKey("requisitos.id"), nullable=False)
    achado_id = Column(Integer, ForeignKey("achados.id"))
    nome_arquivo = Column(String(240), nullable=False)
    caminho_arquivo = Column(String(500), nullable=False)
    tipo_arquivo = Column(String(120))
    data_upload = Column(DateTime, default=datetime.utcnow)
    enviado_por = Column(String(120))
