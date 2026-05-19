from datetime import date, datetime

from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
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
    area_responsavel = Column(String(120))
    prazo = Column(Date)
    status = Column(String(40), default="Aberto")
    prioridade = Column(String(20), default="Média")
    evidencia_conclusao = Column(Text)
    validacao_ehs = Column(String(80))
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
    auditoria_id = Column(Integer, ForeignKey("auditorias.id"))
    requisito_id = Column(Integer, ForeignKey("requisitos.id"))
    achado_id = Column(Integer, ForeignKey("achados.id"))
    nome_arquivo = Column(String(240), nullable=False)
    caminho_arquivo = Column(String(500), nullable=False)
    tipo_arquivo = Column(String(120))
    data_upload = Column(DateTime, default=datetime.utcnow)
    enviado_por = Column(String(120))


class MaquinaNR12(Base):
    __tablename__ = "nr12_maquinas"
    id = Column(Integer, primary_key=True)
    codigo = Column(String(60), unique=True, nullable=False)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False)
    area_setor = Column(String(120))
    linha_processo = Column(String(120))
    nome = Column(String(180), nullable=False)
    fabricante = Column(String(120))
    modelo = Column(String(120))
    numero_serie = Column(String(120))
    ano = Column(Integer)
    tipo_equipamento = Column(String(120))
    responsavel_area = Column(String(120))
    criticidade = Column(String(20), default="Médio")
    status_nr12 = Column(String(80), default="Conforme com observação")
    ultima_adequacao_nr12 = Column(Date)
    ultima_auditoria = Column(Date)
    proxima_auditoria_prevista = Column(Date)
    possui_laudo_nr12 = Column(Boolean, default=False)
    possui_art = Column(Boolean, default=False)
    possui_apreciacao_risco = Column(Boolean, default=False)
    possui_manual_atualizado = Column(Boolean, default=False)
    possui_treinamento = Column(Boolean, default=False)
    observacoes = Column(Text)
    ativa = Column(Boolean, default=True)
    site = relationship("Site")


class DocumentoNR12(Base):
    __tablename__ = "nr12_documentos"
    id = Column(Integer, primary_key=True)
    maquina_id = Column(Integer, ForeignKey("nr12_maquinas.id"), nullable=False)
    tipo_documento = Column(String(120), nullable=False)
    titulo = Column(String(180), nullable=False)
    numero_referencia = Column(String(120))
    data_emissao = Column(Date)
    data_validade = Column(Date)
    responsavel = Column(String(120))
    nome_arquivo = Column(String(240))
    caminho_arquivo = Column(String(500))
    observacoes = Column(Text)
    ativo = Column(Boolean, default=True)
    criado_em = Column(DateTime, default=datetime.utcnow)
    maquina = relationship("MaquinaNR12")


class ChecklistItemNR12(Base):
    __tablename__ = "nr12_checklist_itens"
    id = Column(Integer, primary_key=True)
    tipo_verificacao = Column(String(120), nullable=False)
    codigo = Column(String(60), unique=True, nullable=False)
    pergunta = Column(Text, nullable=False)
    criticidade = Column(String(20), default="Médio")
    evidencia_esperada = Column(String(180))
    ativo = Column(Boolean, default=True)


class VerificacaoNR12(Base):
    __tablename__ = "nr12_verificacoes"
    id = Column(Integer, primary_key=True)
    maquina_id = Column(Integer, ForeignKey("nr12_maquinas.id"), nullable=False)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False)
    tipo_verificacao = Column(String(120), nullable=False)
    data_verificacao = Column(Date, default=date.today)
    responsavel = Column(String(120))
    pontuacao = Column(Float, default=0)
    resultado = Column(String(80))
    observacoes = Column(Text)
    proxima_verificacao = Column(Date)
    criado_em = Column(DateTime, default=datetime.utcnow)
    maquina = relationship("MaquinaNR12")
    site = relationship("Site")


class RespostaNR12(Base):
    __tablename__ = "nr12_respostas"
    __table_args__ = (UniqueConstraint("verificacao_id", "item_id", name="uq_nr12_verificacao_item"),)
    id = Column(Integer, primary_key=True)
    verificacao_id = Column(Integer, ForeignKey("nr12_verificacoes.id"), nullable=False)
    item_id = Column(Integer, ForeignKey("nr12_checklist_itens.id"), nullable=False)
    aplicavel = Column(Boolean, default=True)
    status = Column(String(40), default="Conforme")
    comentario = Column(Text)
    evidencia = Column(Text)
    verificacao = relationship("VerificacaoNR12")
    item = relationship("ChecklistItemNR12")


class PACNR12(Base):
    __tablename__ = "nr12_pacs"
    id = Column(Integer, primary_key=True)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False)
    maquina_id = Column(Integer, ForeignKey("nr12_maquinas.id"))
    verificacao_id = Column(Integer, ForeignKey("nr12_verificacoes.id"))
    item_codigo = Column(String(60))
    tipo_desvio = Column(String(120))
    criticidade = Column(String(20), default="Média")
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
    evidencia_conclusao = Column(Text)
    validacao_ehs = Column(String(80))
    data_abertura = Column(Date, default=date.today)
    data_conclusao = Column(Date)
    verificacao_eficacia = Column(Text)
    status_eficacia = Column(String(80))
    site = relationship("Site")
    maquina = relationship("MaquinaNR12")
    verificacao = relationship("VerificacaoNR12")


class MOCNR12(Base):
    __tablename__ = "nr12_mocs"
    id = Column(Integer, primary_key=True)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False)
    maquina_id = Column(Integer, ForeignKey("nr12_maquinas.id"), nullable=False)
    titulo = Column(String(180), nullable=False)
    tipo_mudanca = Column(String(160), nullable=False)
    descricao = Column(Text)
    impacta_seguranca = Column(Boolean, default=True)
    exige_moc = Column(Boolean, default=True)
    exige_treinamento = Column(Boolean, default=False)
    exige_auditoria_pos_moc = Column(Boolean, default=True)
    aprovacao_ehs = Column(String(40), default="Pendente")
    aprovacao_manutencao_engenharia = Column(String(40), default="Pendente")
    aprovacao_producao = Column(String(40), default="Não aplicável")
    validacao_final = Column(String(40), default="Pendente")
    status = Column(String(60), default="Em análise")
    responsavel = Column(String(120))
    data_abertura = Column(Date, default=date.today)
    data_prevista = Column(Date)
    data_conclusao = Column(Date)
    site = relationship("Site")
    maquina = relationship("MaquinaNR12")


class TermoGarantiaNR12(Base):
    __tablename__ = "nr12_termos_garantia"
    id = Column(Integer, primary_key=True)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False)
    ano = Column(Integer, nullable=False)
    ciclo = Column(String(80), nullable=False)
    responsavel_ehs = Column(String(120))
    responsavel_manutencao = Column(String(120))
    responsavel_operacao = Column(String(120))
    responsavel_engenharia = Column(String(120))
    lideranca_site = Column(String(120))
    declaracao = Column(Text)
    ressalvas = Column(Text)
    criado_em = Column(DateTime, default=datetime.utcnow)
    site = relationship("Site")
