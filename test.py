# app.py - Streamlit (único arquivo) com Controle de MTR por Fornecedor
# Requisitos principais:
#   streamlit, sqlalchemy>=2.0, bcrypt, plotly, python-dateutil
# Exportação Excel:
#   pandas, openpyxl
# Parsing MTR em PDF:
#   pdfplumber, unidecode
#
# Execução: streamlit run app.py

import os
import re
import uuid
import json
from io import BytesIO
from pathlib import Path
from datetime import date, timedelta, datetime

import bcrypt
import streamlit as st
import plotly.express as px

from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Date, ForeignKey, Enum,
    UniqueConstraint, JSON, func
)
from sqlalchemy.orm import sessionmaker, declarative_base, relationship, joinedload, Session
import enum

# ======= (Opcional) Excel export =======
try:
    import pandas as pd
    HAVE_PANDAS = True
except Exception:
    HAVE_PANDAS = False

# ======= Parsing PDF MTR =======
try:
    import pdfplumber
    HAVE_PDFPLUMBER = True
except Exception:
    HAVE_PDFPLUMBER = False

try:
    import unidecode
    HAVE_UNIDECODE = True
except Exception:
    HAVE_UNIDECODE = False


# =========================
#       CONFIG GERAL
# =========================

st.set_page_config(page_title="Gerenciamento de Fornecedores Ambientais", layout="wide")

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///fornecedores.db")
CONNECT_ARGS = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=CONNECT_ARGS, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
Base = declarative_base()


# =========================
#       UTILITÁRIOS
# =========================

def so_digitos(valor: str) -> str:
    import re as _re
    return _re.sub(r"\D", "", valor or "")

def normalizar_telefone(valor: str) -> str:
    return so_digitos(valor)

def validar_cpf(cpf: str) -> bool:
    cpf = so_digitos(cpf)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
    d1 = (soma * 10) % 11
    d1 = 0 if d1 == 10 else d1
    soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
    d2 = (soma * 10) % 11
    d2 = 0 if d2 == 10 else d2
    return cpf[-2:] == f"{d1}{d2}"

def validar_cnpj(cnpj: str) -> bool:
    cnpj = so_digitos(cnpj)
    if len(cnpj) != 14 or cnpj == cnpj[0] * 14:
        return False
    pesos1 = [5,4,3,2,9,8,7,6,5,4,3,2]
    pesos2 = [6] + pesos1
    soma1 = sum(int(cnpj[i]) * pesos1[i] for i in range(12))
    d1 = 11 - (soma1 % 11)
    d1 = 0 if d1 >= 10 else d1
    soma2 = sum(int(cnpj[i]) * pesos2[i] for i in range(13))
    d2 = 11 - (soma2 % 11)
    d2 = 0 if d2 >= 10 else d2
    return cnpj[-2:] == f"{d1}{d2}"

def validar_cpf_cnpj(valor: str) -> bool:
    d = so_digitos(valor)
    if len(d) == 11:
        return validar_cpf(d)
    if len(d) == 14:
        return validar_cnpj(d)
    return False

def formatar_cpf_cnpj(dig: str) -> str:
    dig = so_digitos(dig)
    if len(dig) == 11:
        return f"{dig[:3]}.{dig[3:6]}.{dig[6:9]}-{dig[9:]}"
    if len(dig) == 14:
        return f"{dig[:2]}.{dig[2:5]}.{dig[5:8]}/{dig[8:12]}-{dig[12:]}"
    return dig

def salvar_arquivo(uploaded_file, pasta_destino: str, nome_prefixo: str) -> str:
    Path(pasta_destino).mkdir(parents=True, exist_ok=True)
    ext = Path(uploaded_file.name).suffix.lower()
    safe_stem = re.sub(r'[^a-zA-Z0-9_-]+', '_', nome_prefixo)[:50] or 'file'
    filename = f"{safe_stem}_{uuid.uuid4().hex}{ext}"
    caminho = Path(pasta_destino) / filename
    caminho.write_bytes(uploaded_file.getbuffer())
    return str(caminho)

def exibir_preview_arquivo(caminho: str, mime_type: str | None):
    ext = Path(caminho).suffix.lower()
    try:
        if mime_type is None:
            if ext in [".png", ".jpg", ".jpeg"]:
                mime_type = "image/jpeg" if ext != ".png" else "image/png"
            elif ext == ".pdf":
                mime_type = "application/pdf"
            else:
                mime_type = "application/octet-stream"
        with open(caminho, "rb") as f:
            data = f.read()
        if mime_type.startswith("image/"):
            st.image(data)
        elif mime_type == "application/pdf":
            st.download_button("Baixar PDF", data=data, file_name=os.path.basename(caminho), key=f"dl_{uuid.uuid4().hex}")
        else:
            st.download_button("Baixar arquivo", data=data, file_name=os.path.basename(caminho), key=f"dl_{uuid.uuid4().hex}")
    except Exception as e:
        st.error(f"Erro ao exibir arquivo: {e}")

def validade_ok(inicio: date, validade: date) -> bool:
    return validade >= inicio

def parse_data_br(valor: str) -> date | None:
    try:
        return datetime.strptime(valor, "%d/%m/%Y").date()
    except Exception:
        return None

def to_float(num_str: str) -> float | None:
    """Converte string numérica brasileira (com vírgula) em float."""
    if not num_str:
        return None
    s = num_str.strip().replace(".", "").replace(",", ".")
    try:
        return float(s)
    except Exception:
        return None

def unidade_to_kg(qtd: float | None, unidade: str | None) -> float | None:
    if qtd is None:
        return None
    u = (unidade or "").strip().upper()
    if u in ("KG", "KGS", "KILOS", "QUILOS"):
        return qtd
    if u in ("T", "TON", "TONS", "TONELADA", "TONELADAS"):
        return qtd * 1000.0
    # fallback: assume kg
    return qtd


# =========================
#          MODELOS
# =========================

class RoleEnum(str, enum.Enum):
    admin = "Admin"
    auditor = "Auditor"
    leitor = "Leitor"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(150), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(RoleEnum), nullable=False, default=RoleEnum.auditor)
    created_at = Column(Date, server_default=func.current_date())

class Fornecedor(Base):
    __tablename__ = "fornecedores"
    id = Column(Integer, primary_key=True)
    nome = Column(String, nullable=False)
    cpf_cnpj = Column(String(14), unique=True, nullable=False)  # armazenar só dígitos
    endereco = Column(String)
    telefone = Column(String(20))
    created_at = Column(Date, server_default=func.current_date())
    updated_at = Column(Date, server_default=func.current_date(), onupdate=func.current_date())
    updated_by = Column(String(150))

    documentos = relationship("Documento", back_populates="fornecedor", cascade="all, delete-orphan")
    auditoria = relationship("Auditoria", uselist=False, back_populates="fornecedor", cascade="all, delete-orphan")
    planos_acao = relationship("PlanoAcao", back_populates="fornecedor", cascade="all, delete-orphan")
    contratos = relationship("Contrato", back_populates="fornecedor", cascade="all, delete-orphan")
    mtrs = relationship("MTR", back_populates="fornecedor", cascade="all, delete-orphan")

class Documento(Base):
    __tablename__ = "documentos"
    __table_args__ = (UniqueConstraint('fornecedor_id', 'tipo', name='uq_doc_fornecedor_tipo'),)
    id = Column(Integer, primary_key=True)
    fornecedor_id = Column(Integer, ForeignKey('fornecedores.id', ondelete="CASCADE"), nullable=False)
    tipo = Column(String, nullable=False)
    arquivo = Column(String, nullable=False)
    data_inicio = Column(Date, nullable=False)
    data_validade = Column(Date, nullable=False)
    created_at = Column(Date, server_default=func.current_date())
    updated_at = Column(Date, server_default=func.current_date(), onupdate=func.current_date())
    updated_by = Column(String(150))
    fornecedor = relationship("Fornecedor", back_populates="documentos")

class Auditoria(Base):
    __tablename__ = "auditorias"
    id = Column(Integer, primary_key=True)
    fornecedor_id = Column(Integer, ForeignKey('fornecedores.id', ondelete="CASCADE"), nullable=False)
    respostas = Column(JSON, nullable=False, default={})  # {"1": "Sim", ...}
    score = Column(Integer, nullable=False, default=0)
    classificado = Column(String, nullable=False, default="Não Conforme")
    created_at = Column(Date, server_default=func.current_date())
    updated_at = Column(Date, server_default=func.current_date(), onupdate=func.current_date())
    updated_by = Column(String(150))
    fornecedor = relationship("Fornecedor", back_populates="auditoria")

class PlanoStatusEnum(str, enum.Enum):
    andamento = "Em andamento"
    concluido = "Concluído"
    atrasado = "Atrasado"

class PlanoAcao(Base):
    __tablename__ = "planos_acao"
    id = Column(Integer, primary_key=True)
    fornecedor_id = Column(Integer, ForeignKey('fornecedores.id', ondelete="CASCADE"), nullable=False)
    descricao = Column(String, nullable=False)
    data_inicio = Column(Date, nullable=False)
    data_fim = Column(Date, nullable=False)
    status = Column(Enum(PlanoStatusEnum), nullable=False, default=PlanoStatusEnum.andamento)
    evidencias = Column(JSON, nullable=False, default=list)  # lista de caminhos
    created_at = Column(Date, server_default=func.current_date())
    updated_at = Column(Date, server_default=func.current_date(), onupdate=func.current_date())
    updated_by = Column(String(150))
    fornecedor = relationship("Fornecedor", back_populates="planos_acao")

class Contrato(Base):
    __tablename__ = "contratos"
    id = Column(Integer, primary_key=True)
    fornecedor_id = Column(Integer, ForeignKey('fornecedores.id', ondelete="CASCADE"), nullable=False)
    arquivo = Column(String, nullable=False)
    data_assinatura = Column(Date, nullable=False)
    data_validade = Column(Date, nullable=False)
    created_at = Column(Date, server_default=func.current_date())
    updated_at = Column(Date, server_default=func.current_date(), onupdate=func.current_date())
    updated_by = Column(String(150))
    fornecedor = relationship("Fornecedor", back_populates="contratos")

# ---------- NOVO: Tabela de MTR ----------
class MTR(Base):
    __tablename__ = "mtrs"
    id = Column(Integer, primary_key=True)
    fornecedor_id = Column(Integer, ForeignKey('fornecedores.id', ondelete="CASCADE"), nullable=False)
    arquivo = Column(String, nullable=False)
    numero_mtr = Column(String)                   # ex: "123456"
    gerador_razao = Column(String)
    gerador_cnpj = Column(String)
    gerador_municipio = Column(String)
    gerador_uf = Column(String)
    gerador_data_emissao = Column(Date, nullable=True)

    transportador_razao = Column(String)
    transportador_cnpj = Column(String)
    transportador_data_transporte = Column(Date, nullable=True)

    destinador_razao = Column(String)
    destinador_cnpj = Column(String)
    destinador_data_recebimento = Column(Date, nullable=True)

    codigo_ibama_denom = Column(String)
    estado_fisico = Column(String)
    classe = Column(String)
    acondicionamento = Column(String)
    qtd_original = Column(String)                 # ex: "1.234,50"
    und_original = Column(String)                 # ex: "KG" | "T"
    qtd_kg = Column(Float)                        # convertido p/ kg

    dados_raw = Column(JSON)                      # JSON completo extraído
    created_at = Column(Date, server_default=func.current_date())
    updated_at = Column(Date, server_default=func.current_date(), onupdate=func.current_date())
    updated_by = Column(String(150))

    fornecedor = relationship("Fornecedor", back_populates="mtrs")


# =========================
#     SEGURANÇA / USUÁRIO
# =========================

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()

def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False

def get_user_by_username(db: Session, username: str) -> User | None:
    return db.query(User).filter(User.username == username).first()

def create_user(db: Session, username: str, password: str, role: RoleEnum) -> User:
    u = User(username=username, password_hash=hash_password(password), role=role)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u

def documentos_status(docs) -> tuple[int, int]:
    hoje = date.today()
    limite = hoje + timedelta(days=30)
    vencidos = sum(1 for d in docs if d.data_validade and d.data_validade < hoje)
    a_vencer = sum(1 for d in docs if d.data_validade and hoje <= d.data_validade <= limite)
    return vencidos, a_vencer

def kpis_gerais(db: Session) -> dict:
    total_fornecedores = db.query(Fornecedor).count()
    conformes = db.query(Auditoria).filter(Auditoria.classificado == "Conforme").count()
    nao_conformes = db.query(Auditoria).filter(Auditoria.classificado == "Não Conforme").count()
    fornecedores_com_contrato = db.query(Fornecedor).join(Contrato).distinct().count()
    fornecedores_sem_contrato = total_fornecedores - fornecedores_com_contrato
    docs = db.query(Documento).all()
    vencidos, a_vencer = documentos_status(docs)
    # NOVO: total kg MTR e por fornecedor
    mtr_total_kg = (db.query(func.coalesce(func.sum(MTR.qtd_kg), 0.0)).scalar() or 0.0)
    # ranking por fornecedor
    mtr_por_forn = db.query(Fornecedor.nome, func.coalesce(func.sum(MTR.qtd_kg), 0.0))\
                     .join(MTR, MTR.fornecedor_id == Fornecedor.id, isouter=True)\
                     .group_by(Fornecedor.id).all()
    return {
        "total_fornecedores": total_fornecedores,
        "conformes": conformes,
        "nao_conformes": nao_conformes,
        "forn_com_contrato": fornecedores_com_contrato,
        "forn_sem_contrato": fornecedores_sem_contrato,
        "docs_vencidos": vencidos,
        "docs_a_vencer": a_vencer,
        "mtr_total_kg": float(mtr_total_kg),
        "mtr_por_forn": [(n, float(v or 0.0)) for n, v in mtr_por_forn],
    }


# =========================
#      INICIALIZAÇÃO DB
# =========================

def init_db_and_seed():
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        # Seed exigido: admin Eduardo / Capitu
        admin_user = "Eduardo"
        admin_pass = "Capitu"
        if not get_user_by_username(db, admin_user):
            create_user(db, admin_user, admin_pass, RoleEnum.admin)


# =========================
#   PARSER DA MTR (PDF)
# =========================

def extract_pdf_data(pdf_path: str) -> dict:
    """Extrai campos principais da MTR (1ª página), inspirado no seu script."""
    if not HAVE_PDFPLUMBER:
        raise RuntimeError("pdfplumber não está instalado. Adicione ao requirements.")

    dados = {}
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[0]
        text = page.extract_text() or ""

        # MTR número
        mtr_match = re.search(r"MTR nº (\d+)", text)
        dados["MTR - Número"] = mtr_match.group(1).strip() if mtr_match else "N/A"

        # Bloco Gerador
        g0 = text.find("Identificação do Gerador")
        g1 = text.find("Observações do Gerador")
        generator = text[g0:g1] if g0 != -1 and g1 != -1 else ""

        dados["Gerador - Razão Social"] = (re.search(r"Razão Social: (.*?) - \d+ CPF/CNPJ:", generator).group(1).strip()
                                           if re.search(r"Razão Social: (.*?) - \d+ CPF/CNPJ:", generator) else "N/A")
        dados["Gerador - CPF/CNPJ"] = (re.search(r"CPF/CNPJ: (\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})", generator).group(1).strip()
                                       if re.search(r"CPF/CNPJ: (\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})", generator) else "N/A")
        dados["Gerador - Endereço"] = (re.search(r"Endereço: (.*?)(?:\nTelefone:|Data da emissão:)", generator, re.DOTALL).group(1).replace("\n", " ").strip()
                                       if re.search(r"Endereço: (.*?)(?:\nTelefone:|Data da emissão:)", generator, re.DOTALL) else "N/A")
        dados["Gerador - Data da emissão"] = (re.search(r"Data da emissão: (\d{2}/\d{2}/\d{4})", generator).group(1).strip()
                                              if re.search(r"Data da emissão: (\d{2}/\d{2}/\d{4})", generator) else "N/A")
        dados["Gerador - Telefone"] = (re.search(r"Telefone: (\d+)", generator).group(1).strip()
                                       if re.search(r"Telefone: (\d+)", generator) else "N/A")
        dados["Gerador - Município"] = (re.search(r"Município: (.*?) UF:", generator).group(1).strip()
                                        if re.search(r"Município: (.*?) UF:", generator) else "N/A")
        dados["Gerador - UF"] = (re.search(r"UF: (\w{2})", generator).group(1).strip()
                                 if re.search(r"UF: (\w{2})", generator) else "N/A")

        # Transportador
        t0 = text.find("Identificação do Transportador")
        t1 = text.find("Nome do Motorista")
        transport = text[t0:t1] if t0 != -1 and t1 != -1 else ""

        dados["Transportador - Razão Social"] = (re.search(r"Razão Social: (.*?) - \d+ CPF/CNPJ:", transport).group(1).strip()
                                                 if re.search(r"Razão Social: (.*?) - \d+ CPF/CNPJ:", transport) else "N/A")
        dados["Transportador - CPF/CNPJ"] = (re.search(r"CPF/CNPJ: (\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})", transport).group(1).strip()
                                             if re.search(r"CPF/CNPJ: (\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})", transport) else "N/A")
        dados["Transportador - Endereço"] = (re.search(r"Endereço: (.*?)(?:\nTelefone:|Data do transporte:)", transport, re.DOTALL).group(1).replace("\n", " ").strip()
                                             if re.search(r"Endereço: (.*?)(?:\nTelefone:|Data do transporte:)", transport, re.DOTALL) else "N/A")
        # data transporte pode vir vazia
        _dttr = re.search(r"Data do transporte:\s*(\d{2}/\d{2}/\d{4})?", transport)
        dados["Transportador - Data do transporte"] = _dttr.group(1).strip() if _dttr and _dttr.group(1) else "N/A"
        dados["Transportador - Telefone"] = (re.search(r"Telefone: (\d+)", transport).group(1).strip()
                                             if re.search(r"Telefone: (\d+)", transport) else "N/A")
        dados["Transportador - Município"] = (re.search(r"Município: (.*?) UF:", transport).group(1).strip()
                                              if re.search(r"Município: (.*?) UF:", transport) else "N/A")
        dados["Transportador - UF"] = (re.search(r"UF: (\w{2})", transport).group(1).strip()
                                       if re.search(r"UF: (\w{2})", transport) else "N/A")

        # Destinador
        d0 = text.find("Identificação do Destinador")
        d1 = text.find("Identificação dos Resíduos")
        destin = text[d0:d1] if d0 != -1 and d1 != -1 else ""

        dados["Destinador - Razão Social"] = (re.search(r"Razão Social: (.*?) - \d+ CPF/CNPJ:", destin).group(1).strip()
                                              if re.search(r"Razão Social: (.*?) - \d+ CPF/CNPJ:", destin) else "N/A")
        dados["Destinador - CPF/CNPJ"] = (re.search(r"CPF/CNPJ: (\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})", destin).group(1).strip()
                                          if re.search(r"CPF/CNPJ: (\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})", destin) else "N/A")
        dados["Destinador - Endereço"] = (re.search(r"Endereço: (.*?)(?:\nTelefone:|Data do recebimento:)", destin, re.DOTALL).group(1).replace("\n", " ").strip()
                                          if re.search(r"Endereço: (.*?)(?:\nTelefone:|Data do recebimento:)", destin, re.DOTALL) else "N/A")
        _dtrc = re.search(r"Data do recebimento:\s*(\d{2}/\d{2}/\d{4})?", destin)
        dados["Destinador - Data do recebimento"] = _dtrc.group(1).strip() if _dtrc and _dtrc.group(1) else "N/A"
        dados["Destinador - Telefone"] = (re.search(r"Telefone: (\d+)", destin).group(1).strip()
                                          if re.search(r"Telefone: (\d+)", destin) else "N/A")
        dados["Destinador - Município"] = (re.search(r"Município: (.*?) UF:", destin).group(1).strip()
                                           if re.search(r"Município: (.*?) UF:", destin) else "N/A")
        dados["Destinador - UF"] = (re.search(r"UF: (\w{2})", destin).group(1).strip()
                                    if re.search(r"UF: (\w{2})", destin) else "N/A")

        # Linha dos resíduos (primeiro item)
        waste_start = text.find("Identificação dos Resíduos")
        waste_info_raw = text[waste_start:] if waste_start != -1 else text

        waste_line_match = re.search(
            r"^1\s+([\d-]+)-(.+?)\s+([A-Z]+)\s+CLASSE\s+(.+?)\s+([0-9,.]+)\s+([A-Z]+)\s+(.+)$",
            waste_info_raw, re.MULTILINE
        )
        if waste_line_match:
            codigo_completo = f"{waste_line_match.group(1)}-{waste_line_match.group(2).strip()}"
            dados["Resíduos - Item"] = "1"
            dados["Resíduos - Código IBAMA e Denominação"] = codigo_completo[:6]
            dados["Resíduos - Estado Físico"] = waste_line_match.group(3).strip()
            dados["Resíduos - Classe"] = f"CLASSE {waste_line_match.group(4).strip()}"
            dados["Resíduos - Acondicionamento"] = waste_line_match.group(4).strip()
            dados["Resíduos - Qtde"] = waste_line_match.group(5).strip()
            dados["Resíduos - Unidade"] = waste_line_match.group(6).strip()
            dados["Resíduos - Tratamento"] = waste_line_match.group(7).strip()
        else:
            dados["Resíduos - Item"] = ""
            dados["Resíduos - Código IBAMA e Denominação"] = ""
            dados["Resíduos - Estado Físico"] = ""
            dados["Resíduos - Classe"] = ""
            dados["Resíduos - Acondicionamento"] = ""
            dados["Resíduos - Qtde"] = ""
            dados["Resíduos - Unidade"] = ""
            dados["Resíduos - Tratamento"] = ""

    return dados

def extract_and_normalize_mtr(pdf_path: str) -> dict:
    """Extrai MTR e normaliza campos-chave, converte quantidade para kg."""
    dados = extract_pdf_data(pdf_path)
    qtd_str = dados.get("Resíduos - Qtde") or ""
    und = dados.get("Resíduos - Unidade") or ""
    qtd = to_float(qtd_str)
    qtd_kg = unidade_to_kg(qtd, und)

    return {
        "numero_mtr": dados.get("MTR - Número") or None,
        "gerador_razao": dados.get("Gerador - Razão Social") or None,
        "gerador_cnpj": so_digitos(dados.get("Gerador - CPF/CNPJ") or ""),
        "gerador_municipio": dados.get("Gerador - Município") or None,
        "gerador_uf": dados.get("Gerador - UF") or None,
        "gerador_data_emissao": parse_data_br(dados.get("Gerador - Data da emissão") or ""),

        "transportador_razao": dados.get("Transportador - Razão Social") or None,
        "transportador_cnpj": so_digitos(dados.get("Transportador - CPF/CNPJ") or ""),
        "transportador_data_transporte": parse_data_br(dados.get("Transportador - Data do transporte") or ""),

        "destinador_razao": dados.get("Destinador - Razão Social") or None,
        "destinador_cnpj": so_digitos(dados.get("Destinador - CPF/CNPJ") or ""),
        "destinador_data_recebimento": parse_data_br(dados.get("Destinador - Data do recebimento") or ""),

        "codigo_ibama_denom": dados.get("Resíduos - Código IBAMA e Denominação") or None,
        "estado_fisico": dados.get("Resíduos - Estado Físico") or None,
        "classe": dados.get("Resíduos - Classe") or None,
        "acondicionamento": dados.get("Resíduos - Acondicionamento") or None,
        "qtd_original": qtd_str or None,
        "und_original": und or None,
        "qtd_kg": qtd_kg,

        "dados_raw": dados
    }

# =========================
#         CONSTANTES
# =========================

try:
    PERGUNTAS_AUDITORIA
except NameError:
    PERGUNTAS_AUDITORIA = [
        "A empresa possui o sistema de gestão ISO 14001?",
        "A empresa possui licença do órgão ambiental responsável? (Licença Instalação/Operação/polícia federal/CADRI/ Outorga)",
        "Há evidências de que as restrições da licença estão sendo cumpridas?",
        "A empresa sofreu alguma autuação ambiental nos últimos anos?",
        "Há evidências de visitas fiscalizadoras do órgão ambiental? (3 últimos laudos de inspeção)",
        "Existe alguma estrutura de documentação do sistema de gestão e de controle de registros?",
        "A empresa possui uma Política (Qualidade, Meio Ambiente, Segurança) com objetivos e metas estabelecidos?",
        "A empresa realizou levantamento de seus aspectos e impactos ambientais estabelecendo controle sobre os significativos?",
        "O espaço físico é suficiente para receber a quantidade de material gerado?",
        "A empresa possui ETE para tratar seus resíduos líquidos?",
        "Caso exista ETE, são realizadas análises do efluente tratado?",
        "A empresa possui área coberta para armazenagem dos resíduos?",
        "A empresa possui área impermeabilizada?",
        "Os equipamentos de transporte estão em bom estado? Controle de fumaça preta?",
        "A empresa possui licença do IBAMA?",
        "A empresa destina seus resíduos sólidos adequadamente?",
        "A empresa possui Alvará do Corpo de Bombeiros e alvará municipal?",
        "Todos os funcionários da empresa são registrados?",
        "Os funcionários trabalham uniformizados e com EPIs pertinentes?",
        "A empresa atende as chamadas para retiradas com pontualidade?",
        "Os funcionários recebem treinamentos sobre saúde, segurança e meio ambiente?",
    ]
    
# =========================
#        UI / PÁGINAS
# =========================

init_db_and_seed()

if "logado" not in st.session_state:
    st.session_state.logado = False
    st.session_state.usuario = None
    st.session_state.role = None
if "sel_forn_id" not in st.session_state:
    st.session_state.sel_forn_id = None

def pagina_login():
    st.title("Sistema de Gerenciamento de Fornecedores - Login")
    with st.form("form_login"):
        usuario = st.text_input("Usuário").strip()
        senha = st.text_input("Senha", type="password").strip()
        enviar = st.form_submit_button("Entrar")

    if enviar:
        with SessionLocal() as db:
            u = get_user_by_username(db, usuario)
            if u and verify_password(senha, u.password_hash):
                st.session_state.logado = True
                st.session_state.usuario = u.username
                st.session_state.role = u.role.value
                st.success(f"Bem-vindo, {u.username}!")
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos.")

if not st.session_state.logado:
    pagina_login()
    st.stop()

# Menu adaptado por perfil
if st.session_state.role == RoleEnum.leitor.value:
    menu = st.sidebar.selectbox("Menu", ["Overview", "Sair"])
else:
    menu = st.sidebar.selectbox(
        "Menu",
        ["Overview", "Cadastrar Fornecedor", "Visualizar Fornecedores", "MTRs", "Admin (Usuários)", "Sair"]
    )

st.sidebar.title(f"Usuário: {st.session_state.usuario} ({st.session_state.role})")

# ---- Overview ----
if menu == "Overview":
    st.header("Resumo Geral dos Fornecedores")
    with SessionLocal() as db:
        k = kpis_gerais(db)

    # Paleta verde/vermelho
    fig_total = px.pie(
        names=["Conforme", "Não Conforme"],
        values=[k["conformes"], k["nao_conformes"]],
        title="Classificação da Auditoria",
        color=["Conforme", "Não Conforme"],
        color_discrete_map={"Conforme": "green", "Não Conforme": "red"},
    )
    fig_contrato = px.pie(
        names=["Com Contrato", "Sem Contrato"],
        values=[k["forn_com_contrato"], k["forn_sem_contrato"]],
        title="Situação Contratual",
        color=["Com Contrato", "Sem Contrato"],
        color_discrete_map={"Com Contrato": "green", "Sem Contrato": "red"},
    )

    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(fig_total, use_container_width=True)
    with c2:
        st.plotly_chart(fig_contrato, use_container_width=True)

    # Indicadores coloridos (HTML simples)
    def badge(label, value, good=True):
        color = "#2e7d32" if good else "#c62828"  # verde/vermelho
        bg = "#e8f5e9" if good else "#ffebee"
        return f"""
        <div style="padding:10px;border-radius:8px;background:{bg};margin-bottom:8px;">
            <span style="color:{color};font-weight:600;">{label}:</span>
            <span style="margin-left:6px;color:#111;font-weight:700;">{value}</span>
        </div>
        """

    colA, colB, colC = st.columns(3)
    with colA:
        st.markdown(badge("Total de Fornecedores", k["total_fornecedores"], good=True), unsafe_allow_html=True)
        st.markdown(badge("Conformes", k["conformes"], good=True), unsafe_allow_html=True)
    with colB:
        st.markdown(badge("Não Conformes", k["nao_conformes"], good=False), unsafe_allow_html=True)
        st.markdown(badge("Doc. a vencer (30d)", k["docs_a_vencer"], good=False), unsafe_allow_html=True)
    with colC:
        st.markdown(badge("Documentos vencidos", k["docs_vencidos"], good=False), unsafe_allow_html=True)
        st.markdown(badge("Total kg (MTR)", f"{k['mtr_total_kg']:.1f} kg", good=True), unsafe_allow_html=True)

    st.markdown("### Kg destinados por fornecedor (MTR)")
    # Ordena por kg desc, exibe gráfico de barras verde
    nomes = [n for n, v in k["mtr_por_forn"]]
    valores = [v for n, v in k["mtr_por_forn"]]
    fig_bar = px.bar(x=nomes, y=valores, labels={"x": "Fornecedor", "y": "Kg destinados"},
                     title="Total de kg destinados por fornecedor (MTR)")
    fig_bar.update_traces(marker_color="green")
    st.plotly_chart(fig_bar, use_container_width=True)

    st.markdown("### Insights")
    if k["nao_conformes"] > 0:
        st.error(f"Existem {k['nao_conformes']} fornecedores 'Não Conforme'. Recomenda-se planos de ação e nova auditoria.")
    else:
        st.success("Todos os fornecedores estão 'Conforme'.")
    if k["forn_sem_contrato"] > 0:
        st.error(f"Existem {k['forn_sem_contrato']} fornecedores sem contrato formalizado.")
    else:
        st.success("Todos os fornecedores possuem contrato formalizado.")

# ---- Cadastrar Fornecedor ----
elif menu == "Cadastrar Fornecedor":
    if st.session_state.role not in (RoleEnum.admin.value, RoleEnum.auditor.value):
        st.error("Você não tem permissão para cadastrar fornecedores.")
        st.stop()

    st.header("Cadastrar novo fornecedor")
    with st.form("form_cadastro"):
        nome = st.text_input("Nome do fornecedor")
        cpf_cnpj = st.text_input("CPF ou CNPJ")
        endereco = st.text_area("Endereço")
        telefone = st.text_input("Telefone")
        enviar = st.form_submit_button("Cadastrar")

    if enviar:
        if not nome or not cpf_cnpj:
            st.error("Nome e CPF/CNPJ são obrigatórios.")
            st.stop()
        if not validar_cpf_cnpj(cpf_cnpj):
            st.error("CPF/CNPJ inválido.")
            st.stop()
        with SessionLocal() as db:
            dig = so_digitos(cpf_cnpj)
            existe = db.query(Fornecedor).filter_by(cpf_cnpj=dig).first()
            if existe:
                st.warning("Fornecedor já cadastrado.")
            else:
                f = Fornecedor(
                    nome=nome.strip(),
                    cpf_cnpj=dig,
                    endereco=endereco.strip() if endereco else None,
                    telefone=normalizar_telefone(telefone),
                    updated_by=st.session_state.usuario,
                )
                db.add(f)
                db.commit()
                st.success(f"Fornecedor '{f.nome}' cadastrado com sucesso!")

# ---- Visualizar Fornecedores (lista clicável) ----
elif menu == "Visualizar Fornecedores":
    if st.session_state.role not in (RoleEnum.admin.value, RoleEnum.auditor.value):
        st.error("Acesso restrito. Seu perfil é Leitor e possui acesso apenas ao Overview.")
        st.stop()

    st.header("Fornecedores")
    termo = st.text_input("Buscar por nome", key="busca_forn")

    with SessionLocal() as db:
        fornecedores = db.query(Fornecedor).options(
            joinedload(Fornecedor.documentos),
            joinedload(Fornecedor.auditoria),
            joinedload(Fornecedor.planos_acao),
            joinedload(Fornecedor.contratos),
            joinedload(Fornecedor.mtrs),
        )
        if termo:
            fornecedores = fornecedores.filter(Fornecedor.nome.ilike(f"%{termo.strip()}%"))
        fornecedores = fornecedores.order_by(Fornecedor.nome.asc()).all()

    if not fornecedores:
        st.info("Nenhum fornecedor encontrado.")
        st.stop()

    col_left, col_right = st.columns([0.35, 0.65])

    # Lista clicável na esquerda
    with col_left:
        st.subheader("Lista")
        for f in fornecedores:
            is_selected = (st.session_state.sel_forn_id == f.id)
            style = "background:#e8f5e9;border:1px solid #2e7d32;" if is_selected else "background:#f6f6f6;border:1px solid #ddd;"
            if st.button(f"📁 {f.nome} — {formatar_cpf_cnpj(f.cpf_cnpj)}", key=f"btn_f_{f.id}"):
                st.session_state.sel_forn_id = f.id
            st.markdown(f"<div style='height:6px;{style}'></div>", unsafe_allow_html=True)

    # Painel de detalhes à direita
    with col_right:
        sel = next((f for f in fornecedores if f.id == st.session_state.sel_forn_id), None)
        if sel is None:
            st.info("Selecione um fornecedor na lista ao lado para visualizar/editar.")
        else:
            st.subheader(f"Detalhes — {sel.nome}")
            tabs = st.tabs(["Informações", "Documentos", "Auditoria", "Planos de Ação", "Contratos", "MTRs"])

            # --- Informações
            with tabs[0]:
                st.write(f"**CPF/CNPJ:** {formatar_cpf_cnpj(sel.cpf_cnpj)}")
                st.write(f"**Endereço:** {sel.endereco or '-'}")
                st.write(f"**Telefone:** {sel.telefone or '-'}")

            # --- Documentos (linha editável)
            with tabs[1]:
                st.markdown("#### Documentos do fornecedor")
                if not sel.documentos:
                    st.info("Nenhum documento. Use o bloco 'Adicionar novo documento' abaixo.")

                for d in sel.documentos:
                    with st.container(border=True):
                        st.write(f"**Tipo:** {d.tipo}")
                        c1, c2, c3 = st.columns([0.4, 0.3, 0.3])
                        with c1:
                            up = st.file_uploader("Substituir arquivo (opcional)", type=["pdf", "jpg", "png", "jpeg"], key=f"doc_up_{d.id}")
                        with c2:
                            dt_ini = st.date_input("Início", value=d.data_inicio, key=f"doc_ini_{d.id}")
                        with c3:
                            dt_val = st.date_input("Validade", value=d.data_validade, key=f"doc_val_{d.id}")
                        if st.button("Salvar alterações", key=f"doc_save_{d.id}"):
                            if dt_val < dt_ini:
                                st.error("Validade não pode ser anterior ao início.")
                            else:
                                caminho = d.arquivo
                                if up is not None:
                                    caminho = salvar_arquivo(up, "uploads/documentos", f"{sel.id}_{d.tipo}")
                                with SessionLocal() as db:
                                    doc_db = db.query(Documento).get(d.id)
                                    doc_db.arquivo = caminho
                                    doc_db.data_inicio = dt_ini
                                    doc_db.data_validade = dt_val
                                    doc_db.updated_by = st.session_state.usuario
                                    db.commit()
                                    st.success("Documento atualizado com sucesso!")
                                    if Path(caminho).exists():
                                        exibir_preview_arquivo(caminho, up.type if up else None)

                st.markdown("#### Adicionar novo documento")
                tipos_documentos = [
                    "Licença Ambiental de Operação",
                    "Alvará de Funcionamento",
                    "Comprovante de regularidade (CETESB ou órgão estadual)",
                    "Certificado de regularidade do IBAMA CTF/APP",
                    "Consulta de Área Contaminada"
                ]
                c1, c2, c3, c4 = st.columns([0.35, 0.25, 0.2, 0.2])
                with c1:
                    novo_tipo = st.selectbox("Tipo", tipos_documentos, key="novo_tipo")
                with c2:
                    novo_ini = st.date_input("Início", value=date.today(), key="novo_ini")
                with c3:
                    novo_val = st.date_input("Validade", value=date.today(), key="novo_val")
                with c4:
                    novo_up = st.file_uploader("Arquivo", type=["pdf", "jpg", "png", "jpeg"], key="novo_arq")

                if st.button("Adicionar documento", key="btn_add_doc"):
                    if novo_up is None:
                        st.error("Envie um arquivo.")
                    elif novo_val < novo_ini:
                        st.error("Validade não pode ser anterior ao início.")
                    else:
                        caminho = salvar_arquivo(novo_up, "uploads/documentos", f"{sel.id}_{novo_tipo}")
                        with SessionLocal() as db:
                            try:
                                d = Documento(
                                    fornecedor_id=sel.id,
                                    tipo=novo_tipo,
                                    arquivo=caminho,
                                    data_inicio=novo_ini,
                                    data_validade=novo_val,
                                    updated_by=st.session_state.usuario,
                                )
                                db.add(d)
                                db.commit()
                                st.success("Documento adicionado com sucesso!")
                            except Exception as e:
                                db.rollback()
                                st.error(f"Erro ao salvar documento: {e}")

            # --- Auditoria
            with tabs[2]:
                st.subheader("Auditoria")
                aud_exist = sel.auditoria
                respostas_prev = aud_exist.respostas if aud_exist else {}

                with st.form(f"form_auditoria_{sel.id}"):
                    respostas_form = {}
                    for i, pergunta in enumerate(PERGUNTAS_AUDITORIA, 1):
                        default = respostas_prev.get(str(i), "Sim")
                        idx = 0 if default == "Sim" else 1
                        respostas_form[str(i)] = st.radio(f"{i}) {pergunta}", ["Sim", "Não"], index=idx, key=f"aud_{sel.id}_{i}")
                    enviar_aud = st.form_submit_button("Salvar Auditoria")

                if enviar_aud:
                    total = len(respostas_form)
                    aprovados = sum(1 for v in respostas_form.values() if v == "Sim")
                    score = int((aprovados / total) * 100) if total else 0
                    classificado = "Conforme" if score >= 80 else "Não Conforme"
                    with SessionLocal() as db:
                        aud = db.query(Auditoria).filter_by(fornecedor_id=sel.id).first()
                        if not aud:
                            aud = Auditoria(
                                fornecedor_id=sel.id,
                                respostas=respostas_form,
                                score=score,
                                classificado=classificado,
                                updated_by=st.session_state.usuario,
                            )
                            db.add(aud)
                        else:
                            aud.respostas = respostas_form
                            aud.score = score
                            aud.classificado = classificado
                            aud.updated_by = st.session_state.usuario
                        db.commit()
                        st.success(f"Auditoria salva. Score: {score}%. Classificação: {classificado}")

                if sel.auditoria:
                    st.markdown(f"**Última auditoria:** Score {sel.auditoria.score}%, Classificação: {sel.auditoria.classificado}")

            # --- Planos de Ação
            with tabs[3]:
                st.subheader("Planos de Ação")
                descricao = st.text_area("Descrição da Ação")
                data_inicio = st.date_input("Início", value=date.today())
                data_fim = st.date_input("Fim", value=date.today())
                status = st.selectbox("Status", [PlanoStatusEnum.andamento.value, PlanoStatusEnum.concluido.value, PlanoStatusEnum.atrasado.value])

                ev_upload = st.file_uploader("Anexar evidência (opcional)", type=["pdf", "jpg", "png", "jpeg"], key=f"evid_up_{sel.id}")
                evidencias = []
                if ev_upload is not None:
                    ev_path = salvar_arquivo(ev_upload, "uploads/evidencias", f"{sel.id}_plano")
                    evidencias.append(ev_path)

                if st.button("Adicionar Plano de Ação", key=f"add_plano_{sel.id}"):
                    if not descricao:
                        st.error("Descreva a ação.")
                    elif data_fim < data_inicio:
                        st.error("Data final deve ser maior ou igual à data inicial.")
                    else:
                        with SessionLocal() as db:
                            plano = PlanoAcao(
                                fornecedor_id=sel.id,
                                descricao=descricao.strip(),
                                data_inicio=data_inicio,
                                data_fim=data_fim,
                                status=PlanoStatusEnum(status),
                                evidencias=evidencias or [],
                                updated_by=st.session_state.usuario,
                            )
                            db.add(plano)
                            db.commit()
                            st.success("Plano de ação adicionado.")

                for p in sel.planos_acao:
                    with st.container(border=True):
                        st.markdown(f"**{p.descricao}** — {p.status} — {p.data_inicio} → {p.data_fim}")
                        if p.evidencias:
                            st.write("Evidências:")
                            for ev in p.evidencias:
                                if Path(ev).exists():
                                    exibir_preview_arquivo(ev, None)

            # --- Contratos
            with tabs[4]:
                st.subheader("Contratos")
                arquivo_contrato = st.file_uploader("Anexar Contrato", type=["pdf", "docx", "doc"], key=f"contr_{sel.id}")
                data_assinatura = st.date_input("Assinatura", value=date.today(), key=f"contr_ass_{sel.id}")
                data_validade = st.date_input("Validade", value=date.today(), key=f"contr_val_{sel.id}")

                if st.button("Salvar Contrato", key=f"contr_save_{sel.id}"):
                    if not arquivo_contrato:
                        st.error("Envie um arquivo.")
                    elif data_validade < data_assinatura:
                        st.error("Validade não pode ser anterior à assinatura.")
                    else:
                        caminho = salvar_arquivo(arquivo_contrato, "uploads/contratos", f"{sel.id}_contrato")
                        with SessionLocal() as db:
                            try:
                                c = Contrato(
                                    fornecedor_id=sel.id,
                                    arquivo=caminho,
                                    data_assinatura=data_assinatura,
                                    data_validade=data_validade,
                                    updated_by=st.session_state.usuario,
                                )
                                db.add(c)
                                db.commit()
                                st.success("Contrato salvo com sucesso!")
                                exibir_preview_arquivo(caminho, arquivo_contrato.type)
                            except Exception as e:
                                db.rollback()
                                st.error(f"Erro ao salvar contrato: {e}")

                for c in sel.contratos:
                    with st.container(border=True):
                        st.write(f"- Assinado em: {c.data_assinatura}, Validade: {c.data_validade}")
                        if Path(c.arquivo).exists():
                            exibir_preview_arquivo(c.arquivo, None)

            # --- MTRs do fornecedor (lista)
            with tabs[5]:
                st.subheader("MTRs do fornecedor")
                total_kg = sum(m.qtd_kg or 0.0 for m in sel.mtrs)
                st.write(f"**Total destinado (kg):** {total_kg:.1f}")
                if not sel.mtrs:
                    st.info("Nenhuma MTR para este fornecedor.")
                else:
                    for m in sel.mtrs:
                        with st.container(border=True):
                            st.write(f"**MTR nº**: {m.numero_mtr or '-'} | **Recebimento**: {m.destinador_data_recebimento or '-'} | **Qtd (kg)**: {m.qtd_kg if m.qtd_kg is not None else '-'}")
                            if Path(m.arquivo).exists():
                                exibir_preview_arquivo(m.arquivo, "application/pdf")

# ---- Página MTRs (controle centralizado) ----
elif menu == "MTRs":
    if st.session_state.role not in (RoleEnum.admin.value, RoleEnum.auditor.value):
        st.error("Acesso restrito. Seu perfil é Leitor e possui acesso apenas ao Overview.")
        st.stop()

    st.header("Controle de MTRs por Fornecedor")
    if not HAVE_PDFPLUMBER:
        st.error("pdfplumber não está instalado. Adicione no requirements: pdfplumber>=0.11,<1")
        st.stop()

    with SessionLocal() as db:
        fornecedores = db.query(Fornecedor).order_by(Fornecedor.nome.asc()).all()
    if not fornecedores:
        st.info("Cadastre fornecedores antes de importar MTRs.")
        st.stop()

    forn_map = {f"{f.nome} — {formatar_cpf_cnpj(f.cpf_cnpj)}": f.id for f in fornecedores}
    forn_label = st.selectbox("Selecione o fornecedor para associar as MTRs", list(forn_map.keys()))
    fornecedor_id = forn_map[forn_label]

    uploads = st.file_uploader("Enviar PDFs de MTR", type=["pdf"], accept_multiple_files=True)
    if uploads and st.button("Processar MTRs"):
        ok = 0
        fail = 0
        for up in uploads:
            try:
                # Salva PDF
                caminho = salvar_arquivo(up, "uploads/mtrs", f"{fornecedor_id}_mtr")
                # Extrai e normaliza
                dados = extract_and_normalize_mtr(caminho)
                with SessionLocal() as db:
                    m = MTR(
                        fornecedor_id=fornecedor_id,
                        arquivo=caminho,
                        numero_mtr=dados["numero_mtr"],
                        gerador_razao=dados["gerador_razao"],
                        gerador_cnpj=dados["gerador_cnpj"],
                        gerador_municipio=dados["gerador_municipio"],
                        gerador_uf=dados["gerador_uf"],
                        gerador_data_emissao=dados["gerador_data_emissao"],
                        transportador_razao=dados["transportador_razao"],
                        transportador_cnpj=dados["transportador_cnpj"],
                        transportador_data_transporte=dados["transportador_data_transporte"],
                        destinador_razao=dados["destinador_razao"],
                        destinador_cnpj=dados["destinador_cnpj"],
                        destinador_data_recebimento=dados["destinador_data_recebimento"],
                        codigo_ibama_denom=dados["codigo_ibama_denom"],
                        estado_fisico=dados["estado_fisico"],
                        classe=dados["classe"],
                        acondicionamento=dados["acondicionamento"],
                        qtd_original=dados["qtd_original"],
                        und_original=dados["und_original"],
                        qtd_kg=dados["qtd_kg"],
                        dados_raw=dados["dados_raw"],
                        updated_by=st.session_state.usuario,
                    )
                    db.add(m)
                    db.commit()
                    ok += 1
            except Exception as e:
                fail += 1
                st.error(f"Erro ao processar um PDF: {e}")
        st.success(f"Processo finalizado. Sucesso: {ok} | Falhas: {fail}")
        st.rerun()

    # Tabela geral de MTRs
    st.markdown("### MTRs cadastradas")
    with SessionLocal() as db:
        mtrs = db.query(MTR).join(Fornecedor).add_columns(Fornecedor.nome).order_by(MTR.created_at.desc()).all()

    if not mtrs:
        st.info("Nenhuma MTR cadastrada ainda.")
    else:
        # Mostrar resumo em tabela simples
        rows = []
        for m, nome_f in mtrs:
            rows.append({
                "Fornecedor": nome_f,
                "MTR nº": m.numero_mtr or "-",
                "Recebimento": m.destinador_data_recebimento or "",
                "Qtde (kg)": m.qtd_kg if m.qtd_kg is not None else "",
                "Unidade original": m.und_original or "",
                "Arquivo": os.path.basename(m.arquivo),
            })
        if HAVE_PANDAS:
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True)
        else:
            for r in rows[:200]:
                st.write(r)

# ---- Admin (Usuários) ----
elif menu == "Admin (Usuários)":
    if st.session_state.role != RoleEnum.admin.value:
        st.error("Apenas Admin pode acessar esta página.")
        st.stop()

    st.header("Administração")

    # --- Lista de usuários
    with SessionLocal() as db:
        usuarios = db.query(User).all()

    st.subheader("Usuários")
    for u in usuarios:
        st.write(f"- **{u.username}** — {u.role.value}")

    # --- Criar usuário
    st.subheader("Criar novo usuário")
    with st.form("form_user"):
        username = st.text_input("Usuário").strip()
        password = st.text_input("Senha", type="password").strip()
        role = st.selectbox("Papel", [RoleEnum.admin.value, RoleEnum.auditor.value, RoleEnum.leitor.value])
        enviar = st.form_submit_button("Criar")
    if enviar:
        if not username or not password:
            st.error("Preencha usuário e senha.")
        else:
            with SessionLocal() as db:
                if get_user_by_username(db, username):
                    st.error("Usuário já existe.")
                else:
                    create_user(db, username, password, RoleEnum(role))
                    st.success("Usuário criado com sucesso!")
                    st.rerun()

    # --- Exportação de dados (Excel)
    st.subheader("Exportar dados (Excel)")
    if not HAVE_PANDAS:
        st.info("Para exportar, instale: pandas e openpyxl (adicione no requirements.txt).")
    else:
        if st.button("Gerar arquivo .xlsx"):
            with SessionLocal() as db:
                fornecedores = db.query(Fornecedor).options(
                    joinedload(Fornecedor.documentos),
                    joinedload(Fornecedor.auditoria),
                    joinedload(Fornecedor.planos_acao),
                    joinedload(Fornecedor.contratos),
                    joinedload(Fornecedor.mtrs),
                ).all()

            output = BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                # Fornecedores
                df_f = pd.DataFrame([{
                    "id": f.id, "nome": f.nome, "cpf_cnpj": f.cpf_cnpj,
                    "endereco": f.endereco, "telefone": f.telefone,
                    "updated_by": f.updated_by, "created_at": f.created_at, "updated_at": f.updated_at
                } for f in fornecedores])
                if not df_f.empty:
                    df_f["cpf_cnpj_fmt"] = df_f["cpf_cnpj"].apply(formatar_cpf_cnpj)
                df_f.to_excel(writer, sheet_name="Fornecedores", index=False)

                # Documentos
                rows_d = []
                for f in fornecedores:
                    for d in f.documentos:
                        rows_d.append({
                            "fornecedor_id": f.id, "fornecedor": f.nome, "tipo": d.tipo,
                            "data_inicio": d.data_inicio, "data_validade": d.data_validade,
                            "arquivo": d.arquivo, "updated_by": d.updated_by
                        })
                pd.DataFrame(rows_d).to_excel(writer, sheet_name="Documentos", index=False)

                # Auditorias
                rows_a = []
                for f in fornecedores:
                    a = f.auditoria
                    if a:
                        rows_a.append({
                            "fornecedor_id": f.id, "fornecedor": f.nome,
                            "score": a.score, "classificado": a.classificado,
                            "respostas_json": json.dumps(a.respostas, ensure_ascii=False),
                            "updated_by": a.updated_by
                        })
                pd.DataFrame(rows_a).to_excel(writer, sheet_name="Auditorias", index=False)

                # Planos de Ação
                rows_p = []
                for f in fornecedores:
                    for p in f.planos_acao:
                        rows_p.append({
                            "fornecedor_id": f.id, "fornecedor": f.nome,
                            "descricao": p.descricao, "inicio": p.data_inicio, "fim": p.data_fim,
                            "status": p.status, "evidencias": json.dumps(p.evidencias, ensure_ascii=False),
                            "updated_by": p.updated_by
                        })
                pd.DataFrame(rows_p).to_excel(writer, sheet_name="Planos", index=False)

                # Contratos
                rows_c = []
                for f in fornecedores:
                    for c in f.contratos:
                        rows_c.append({
                            "fornecedor_id": f.id, "fornecedor": f.nome,
                            "assinatura": c.data_assinatura, "validade": c.data_validade,
                            "arquivo": c.arquivo, "updated_by": c.updated_by
                        })
                pd.DataFrame(rows_c).to_excel(writer, sheet_name="Contratos", index=False)

                # MTRs
                rows_m = []
                for f in fornecedores:
                    for m in f.mtrs:
                        rows_m.append({
                            "fornecedor_id": f.id, "fornecedor": f.nome,
                            "mtr_numero": m.numero_mtr, "recebimento": m.destinador_data_recebimento,
                            "qtd_kg": m.qtd_kg, "und_origem": m.und_original, "qtd_original": m.qtd_original,
                            "arquivo": m.arquivo
                        })
                pd.DataFrame(rows_m).to_excel(writer, sheet_name="MTRs", index=False)

            output.seek(0)
            st.download_button(
                "Baixar Excel",
                data=output.read(),
                file_name="fornecedores_export.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

# ---- Sair ----
elif menu == "Sair":
    st.session_state.logado = False
    st.session_state.usuario = None
    st.session_state.role = None
    st.session_state.sel_forn_id = None
    st.rerun()

