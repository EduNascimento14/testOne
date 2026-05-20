from datetime import date, datetime

from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from ehs_integrada.database import Base


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
    perfil = Column(String(40), nullable=False)
    site_id = Column(Integer, ForeignKey("sites.id"))
    ativo = Column(Boolean, default=True)
    site = relationship("Site")


class NR12Maquina(Base):
    __tablename__ = "nr12_maquinas"
    id = Column(Integer, primary_key=True)
    codigo = Column(String(60), unique=True, nullable=False)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False)
    area = Column(String(120), nullable=False)
    linha_processo = Column(String(120))
    nome = Column(String(160), nullable=False)
    fabricante = Column(String(120))
    modelo = Column(String(120))
    numero_serie = Column(String(120))
    ano = Column(Integer)
    tipo_equipamento = Column(String(120))
    responsavel_area = Column(String(120))
    criticidade = Column(String(20), default="Médio")
    status_nr12 = Column(String(50), default="Pendente de ação não crítica")
    status_sugerido = Column(String(50))
    ultima_adequacao = Column(Date)
    ultima_auditoria = Column(Date)
    proxima_auditoria = Column(Date)
    possui_laudo = Column(Boolean, default=False)
    possui_art = Column(Boolean, default=False)
    possui_apreciacao_risco = Column(Boolean, default=False)
    possui_manual_atualizado = Column(Boolean, default=False)
    possui_treinamento = Column(Boolean, default=False)
    observacoes = Column(Text)
    criado_em = Column(DateTime, default=datetime.utcnow)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    site = relationship("Site")
    documentos = relationship("NR12Documento", back_populates="maquina", cascade="all, delete-orphan")
    verificacoes = relationship("NR12Verificacao", back_populates="maquina", cascade="all, delete-orphan")
    pacs = relationship("NR12PAC", back_populates="maquina", cascade="all, delete-orphan")
    mocs = relationship("NR12MOC", back_populates="maquina", cascade="all, delete-orphan")


class NR12Documento(Base):
    __tablename__ = "nr12_documentos"
    id = Column(Integer, primary_key=True)
    maquina_id = Column(Integer, ForeignKey("nr12_maquinas.id"), nullable=False)
    tipo_documento = Column(String(100), nullable=False)
    nome = Column(String(180), nullable=False)
    data_emissao = Column(Date)
    data_validade = Column(Date)
    responsavel = Column(String(120))
    status = Column(String(40), default="Válido")
    caminho_arquivo = Column(String(500))
    observacoes = Column(Text)
    criado_em = Column(DateTime, default=datetime.utcnow)
    maquina = relationship("NR12Maquina", back_populates="documentos")


class NR12ChecklistItem(Base):
    __tablename__ = "nr12_checklist_itens"
    id = Column(Integer, primary_key=True)
    codigo = Column(String(40), unique=True, nullable=False)
    tipo_verificacao = Column(String(100), nullable=False)
    pergunta = Column(Text, nullable=False)
    evidencia_esperada = Column(Text)
    critico = Column(Boolean, default=False)
    ativo = Column(Boolean, default=True)
    posicao = Column(Integer, nullable=False)


class NR12Verificacao(Base):
    __tablename__ = "nr12_verificacoes"
    id = Column(Integer, primary_key=True)
    maquina_id = Column(Integer, ForeignKey("nr12_maquinas.id"), nullable=False)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False)
    tipo_verificacao = Column(String(100), nullable=False)
    data_verificacao = Column(Date, default=date.today)
    auditor = Column(String(120), nullable=False)
    participantes = Column(Text)
    resultado = Column(String(50), default="Conforme")
    pontuacao = Column(Float, default=0.0)
    observacoes = Column(Text)
    criado_em = Column(DateTime, default=datetime.utcnow)
    maquina = relationship("NR12Maquina", back_populates="verificacoes")
    site = relationship("Site")
    respostas = relationship("NR12Resposta", back_populates="verificacao", cascade="all, delete-orphan")


class NR12Resposta(Base):
    __tablename__ = "nr12_respostas"
    __table_args__ = (UniqueConstraint("verificacao_id", "item_id", name="uq_nr12_verificacao_item"),)
    id = Column(Integer, primary_key=True)
    verificacao_id = Column(Integer, ForeignKey("nr12_verificacoes.id"), nullable=False)
    item_id = Column(Integer, ForeignKey("nr12_checklist_itens.id"), nullable=False)
    aplicavel = Column(Boolean, default=True)
    resultado = Column(String(40), default="Conforme")
    comentario = Column(Text)
    evidencia = Column(Text)
    gerar_pac = Column(Boolean, default=False)
    verificacao = relationship("NR12Verificacao", back_populates="respostas")
    item = relationship("NR12ChecklistItem")


class NR12PAC(Base):
    __tablename__ = "nr12_pacs"
    id = Column(Integer, primary_key=True)
    origem = Column(String(80), nullable=False)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False)
    maquina_id = Column(Integer, ForeignKey("nr12_maquinas.id"), nullable=False)
    verificacao_id = Column(Integer, ForeignKey("nr12_verificacoes.id"))
    item_id = Column(Integer, ForeignKey("nr12_checklist_itens.id"))
    descricao_desvio = Column(Text, nullable=False)
    classificacao = Column(String(20), default="Menor")
    responsavel = Column(String(120))
    area_responsavel = Column(String(80))
    prazo = Column(Date)
    status = Column(String(40), default="Aberto")
    evidencia_conclusao = Column(Text)
    validacao_ehs = Column(Boolean, default=False)
    data_conclusao = Column(Date)
    comentarios = Column(Text)
    verificacao_eficacia = Column(Text)
    criado_em = Column(Date, default=date.today)
    site = relationship("Site")
    maquina = relationship("NR12Maquina", back_populates="pacs")
    verificacao = relationship("NR12Verificacao")
    item = relationship("NR12ChecklistItem")


class NR12MOC(Base):
    __tablename__ = "nr12_mocs"
    id = Column(Integer, primary_key=True)
    maquina_id = Column(Integer, ForeignKey("nr12_maquinas.id"), nullable=False)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False)
    tipo_mudanca = Column(String(120), nullable=False)
    descricao = Column(Text, nullable=False)
    solicitante = Column(String(120), nullable=False)
    area_solicitante = Column(String(100))
    data_mudanca = Column(Date, default=date.today)
    impacta_seguranca = Column(Boolean, default=False)
    exige_moc = Column(Boolean, default=False)
    status = Column(String(50), default="Solicitada")
    aprovacao_ehs = Column(Boolean, default=False)
    aprovacao_manutencao = Column(Boolean, default=False)
    aprovacao_engenharia = Column(Boolean, default=False)
    aprovacao_producao = Column(Boolean, default=False)
    exige_auditoria_pos_mudanca = Column(Boolean, default=False)
    exige_treinamento = Column(Boolean, default=False)
    caminho_anexo = Column(String(500))
    observacoes = Column(Text)
    maquina = relationship("NR12Maquina", back_populates="mocs")
    site = relationship("Site")


class NR12TermoGarantia(Base):
    __tablename__ = "nr12_termos_garantia"
    id = Column(Integer, primary_key=True)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False)
    ciclo = Column(String(20), nullable=False)
    responsavel_ehs = Column(String(120))
    responsavel_manutencao = Column(String(120))
    responsavel_operacao = Column(String(120))
    responsavel_engenharia = Column(String(120))
    lideranca_site = Column(String(120))
    declaracao = Column(Text)
    ressalvas = Column(Text)
    plano_acao = Column(Text)
    data_emissao = Column(Date, default=date.today)
    site = relationship("Site")


class EHSIndicadorDiretiva(Base):
    __tablename__ = "ehs_diretivas"
    id = Column(Integer, primary_key=True)
    codigo = Column(String(30), unique=True, nullable=False)
    titulo = Column(String(220), nullable=False)
    descricao = Column(Text)
    ativa = Column(Boolean, default=True)
    requisitos = relationship("EHSRequisito", back_populates="diretiva")


class EHSRequisito(Base):
    __tablename__ = "ehs_requisitos"
    id = Column(Integer, primary_key=True)
    diretiva_id = Column(Integer, ForeignKey("ehs_diretivas.id"), nullable=False)
    codigo = Column(String(60), unique=True, nullable=False)
    pergunta = Column(Text, nullable=False)
    orientacao = Column(Text)
    criticidade = Column(String(20), default="Médio")
    evidencia_esperada = Column(Text)
    ativo = Column(Boolean, default=True)
    diretiva = relationship("EHSIndicadorDiretiva", back_populates="requisitos")


class EHSAuditoria(Base):
    __tablename__ = "ehs_auditorias"
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
    status = Column(String(40), default="Planejada")
    escopo = Column(Text)
    observacoes = Column(Text)
    site_auditado = relationship("Site", foreign_keys=[site_auditado_id])
    site_auditor_lider = relationship("Site", foreign_keys=[site_auditor_lider_id])
    site_auditor_apoio = relationship("Site", foreign_keys=[site_auditor_apoio_id])
    respostas = relationship("EHSResposta", back_populates="auditoria", cascade="all, delete-orphan")


class EHSResposta(Base):
    __tablename__ = "ehs_respostas"
    __table_args__ = (UniqueConstraint("auditoria_id", "requisito_id", name="uq_ehs_auditoria_requisito"),)
    id = Column(Integer, primary_key=True)
    auditoria_id = Column(Integer, ForeignKey("ehs_auditorias.id"), nullable=False)
    requisito_id = Column(Integer, ForeignKey("ehs_requisitos.id"), nullable=False)
    aplicavel = Column(Boolean, default=True)
    status = Column(String(40), default="Conforme")
    nota_maturidade = Column(Integer, default=3)
    evidencia_verificada = Column(Text)
    comentario_auditor = Column(Text)
    necessita_pac = Column(Boolean, default=False)
    data_avaliacao = Column(DateTime)
    auditoria = relationship("EHSAuditoria", back_populates="respostas")
    requisito = relationship("EHSRequisito")


class EHSPAC(Base):
    __tablename__ = "ehs_pacs"
    id = Column(Integer, primary_key=True)
    auditoria_id = Column(Integer, ForeignKey("ehs_auditorias.id"), nullable=False)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False)
    requisito_id = Column(Integer, ForeignKey("ehs_requisitos.id"))
    tipo_achado = Column(String(80), nullable=False)
    descricao = Column(Text, nullable=False)
    evidencia = Column(Text)
    risco = Column(Text)
    causa_raiz = Column(Text)
    acao_imediata = Column(Text)
    acao_corretiva = Column(Text)
    responsavel = Column(String(120))
    area_responsavel = Column(String(120))
    prazo = Column(Date)
    status = Column(String(40), default="Aberto")
    criticidade = Column(String(20), default="Média")
    evidencia_conclusao = Column(Text)
    validacao_ehs = Column(Boolean, default=False)
    data_conclusao = Column(Date)
    verificacao_eficacia = Column(Text)
    status_eficacia = Column(String(80))
    data_abertura = Column(Date, default=date.today)
    auditoria = relationship("EHSAuditoria")
    site = relationship("Site")
    requisito = relationship("EHSRequisito")


class EHSEvidencia(Base):
    __tablename__ = "ehs_evidencias"
    id = Column(Integer, primary_key=True)
    auditoria_id = Column(Integer, ForeignKey("ehs_auditorias.id"))
    requisito_id = Column(Integer, ForeignKey("ehs_requisitos.id"))
    pac_id = Column(Integer, ForeignKey("ehs_pacs.id"))
    nome_arquivo = Column(String(240), nullable=False)
    caminho_arquivo = Column(String(500), nullable=False)
    enviado_por = Column(String(120))
    enviado_em = Column(DateTime, default=datetime.utcnow)
