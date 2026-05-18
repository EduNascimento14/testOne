from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Site(Base):
    __tablename__ = "sites"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    nome: Mapped[str] = mapped_column(String(120))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)


class Usuario(Base):
    __tablename__ = "usuarios"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(160))
    email: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    site_id: Mapped[int | None] = mapped_column(ForeignKey("sites.id"), nullable=True)
    perfil: Mapped[str] = mapped_column(String(40), default="Visualizador")
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    site: Mapped[Site | None] = relationship()


class Diretiva(Base):
    __tablename__ = "diretivas"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    titulo: Mapped[str] = mapped_column(String(240))
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)
    observacao: Mapped[str | None] = mapped_column(Text, nullable=True)
    requisitos: Mapped[list["Requisito"]] = relationship(back_populates="diretiva")


class Requisito(Base):
    __tablename__ = "requisitos"
    __table_args__ = (UniqueConstraint("diretiva_id", "codigo_requisito", name="uq_requisito_codigo"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    diretiva_id: Mapped[int] = mapped_column(ForeignKey("diretivas.id"))
    codigo_requisito: Mapped[str] = mapped_column(String(60), index=True)
    pergunta: Mapped[str] = mapped_column(Text)
    orientacao: Mapped[str | None] = mapped_column(Text, nullable=True)
    criticidade: Mapped[str] = mapped_column(String(20), default="Médio")
    tipo_evidencia_esperada: Mapped[str | None] = mapped_column(String(240), nullable=True)
    area_responsavel_sugerida: Mapped[str | None] = mapped_column(String(160), nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    diretiva: Mapped[Diretiva] = relationship(back_populates="requisitos")


class Auditoria(Base):
    __tablename__ = "auditorias"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(220))
    ano: Mapped[int] = mapped_column(Integer)
    ciclo: Mapped[str] = mapped_column(String(80))
    site_auditado_id: Mapped[int] = mapped_column(ForeignKey("sites.id"))
    site_auditor_lider_id: Mapped[int] = mapped_column(ForeignKey("sites.id"))
    site_auditor_apoio_id: Mapped[int | None] = mapped_column(ForeignKey("sites.id"), nullable=True)
    auditor_lider: Mapped[str] = mapped_column(String(160))
    auditor_apoio: Mapped[str | None] = mapped_column(String(160), nullable=True)
    data_planejada: Mapped[date | None] = mapped_column(Date, nullable=True)
    data_inicio: Mapped[date | None] = mapped_column(Date, nullable=True)
    data_fim: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="Planejada")
    escopo: Mapped[str | None] = mapped_column(Text, nullable=True)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    site_auditado: Mapped[Site] = relationship(foreign_keys=[site_auditado_id])
    site_auditor_lider: Mapped[Site] = relationship(foreign_keys=[site_auditor_lider_id])
    site_auditor_apoio: Mapped[Site | None] = relationship(foreign_keys=[site_auditor_apoio_id])


class RespostaChecklist(Base):
    __tablename__ = "respostas_checklist"
    __table_args__ = (UniqueConstraint("auditoria_id", "requisito_id", name="uq_resposta_aud_req"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    auditoria_id: Mapped[int] = mapped_column(ForeignKey("auditorias.id"))
    requisito_id: Mapped[int] = mapped_column(ForeignKey("requisitos.id"))
    aplicavel: Mapped[bool] = mapped_column(Boolean, default=True)
    status_conformidade: Mapped[str] = mapped_column(String(40), default="Não Verificado")
    nota_maturidade: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evidencia_verificada: Mapped[str | None] = mapped_column(Text, nullable=True)
    comentario_auditor: Mapped[str | None] = mapped_column(Text, nullable=True)
    necessita_acao: Mapped[bool] = mapped_column(Boolean, default=False)
    data_avaliacao: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    avaliado_por: Mapped[str | None] = mapped_column(String(160), nullable=True)
    auditoria: Mapped[Auditoria] = relationship()
    requisito: Mapped[Requisito] = relationship()


class Achado(Base):
    __tablename__ = "achados"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    auditoria_id: Mapped[int] = mapped_column(ForeignKey("auditorias.id"))
    requisito_id: Mapped[int] = mapped_column(ForeignKey("requisitos.id"))
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"))
    tipo_achado: Mapped[str] = mapped_column(String(60))
    descricao: Mapped[str] = mapped_column(Text)
    evidencia: Mapped[str | None] = mapped_column(Text, nullable=True)
    risco: Mapped[str | None] = mapped_column(Text, nullable=True)
    causa_raiz: Mapped[str | None] = mapped_column(Text, nullable=True)
    acao_imediata: Mapped[str | None] = mapped_column(Text, nullable=True)
    acao_corretiva: Mapped[str | None] = mapped_column(Text, nullable=True)
    responsavel: Mapped[str | None] = mapped_column(String(160), nullable=True)
    prazo: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="Aberto")
    prioridade: Mapped[str] = mapped_column(String(20), default="Média")
    data_abertura: Mapped[date] = mapped_column(Date, default=date.today)
    data_conclusao: Mapped[date | None] = mapped_column(Date, nullable=True)
    verificacao_eficacia: Mapped[str | None] = mapped_column(Text, nullable=True)
    status_eficacia: Mapped[str | None] = mapped_column(String(60), nullable=True)
    auditoria: Mapped[Auditoria] = relationship()
    requisito: Mapped[Requisito] = relationship()
    site: Mapped[Site] = relationship()


class EvidenciaArquivo(Base):
    __tablename__ = "evidencias_arquivos"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    auditoria_id: Mapped[int] = mapped_column(ForeignKey("auditorias.id"))
    requisito_id: Mapped[int] = mapped_column(ForeignKey("requisitos.id"))
    achado_id: Mapped[int | None] = mapped_column(ForeignKey("achados.id"), nullable=True)
    nome_arquivo: Mapped[str] = mapped_column(String(255))
    caminho_arquivo: Mapped[str] = mapped_column(String(500))
    tipo_arquivo: Mapped[str | None] = mapped_column(String(120), nullable=True)
    data_upload: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    enviado_por: Mapped[str | None] = mapped_column(String(160), nullable=True)
