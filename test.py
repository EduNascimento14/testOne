# app.py — Streamlit único
# Novidades:
# - Escopo 3 (resíduos): tipo, destinação, fator (tCO2e/t) e emissões (tCO2e) por MTR
# - CDFs (Certificados de Destinação Final) ligados a MTRs
# - KPIs no Overview: Total tCO2e e % MTRs com CDF
# - Export Excel inclui emissões e CDFs
#
# Execução: streamlit run app.py

import os
import re
import uuid
import json
from io import BytesIO
from pathlib import Path
from datetime import date, timedelta, datetime

import streamlit as st
import plotly.express as px

import bcrypt
from statistics import mean

from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Date, ForeignKey, Enum,
    UniqueConstraint, JSON, func, text
)
from sqlalchemy.orm import sessionmaker, declarative_base, relationship, joinedload, Session
import enum

# ======= (Excel / Data) =======
try:
    import pandas as pd
    HAVE_PANDAS = True
except Exception:
    HAVE_PANDAS = False

# ======= PDF MTR =======
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

def _safe_rerun():
    try:
        st.rerun()
    except Exception:
        try:
            st.experimental_rerun()
        except Exception:
            pass

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

def parse_data_br(valor: str) -> date | None:
    try:
        return datetime.strptime(valor, "%d/%m/%Y").date()
    except Exception:
        return None

def to_float(num_str: str) -> float | None:
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
    return qtd

def kg_to_ton(kg: float | None) -> float:
    return (kg or 0.0) / 1000.0


# =========================
#     FATORES DE EMISSÃO
# =========================
# Exemplos (IPCC/DEFRA) — ajuste conforme suas referências oficiais.
# Unidade: tCO2e / t (tonelada)
EMISSION_FACTORS = {
    # tipo -> destinação -> fator tCO2e/t
    "Plástico": {
        "Incineração c/ recuperação energética": 2.9,
        "Incineração s/ recuperação energética": 3.1,
        "Aterro": 0.1,
        "Reciclagem": -0.7,
    },
    "Papel": {
        "Incineração c/ recuperação energética": 1.2,
        "Aterro": 1.9,
        "Reciclagem": -1.0,
        "Compostagem": 0.1,
    },
    "Orgânico": {
        "Compostagem": 0.1,
        "Aterro": 1.2,
        "Digestão anaeróbia": -0.2,
    },
    "Madeira": {
        "Reciclagem": -0.4,
        "Incineração c/ recuperação energética": 0.6,
        "Aterro": 0.3,
    },
    "Metais": {
        "Reciclagem": -1.5,
        "Aterro": 0.05,
    },
    "Vidro": {
        "Reciclagem": -0.3,
        "Aterro": 0.02,
    },
    "Misto/Outros": {
        "Aterro": 0.3,
        "Incineração c/ recuperação energética": 1.5,
        "Reciclagem": -0.2,
    },
}

TIPOS_RESIDUO = list(EMISSION_FACTORS.keys())

def destinos_para_tipo(tipo: str) -> list[str]:
    return list(EMISSION_FACTORS.get(tipo, EMISSION_FACTORS["Misto/Outros"]).keys())

def fator_default(tipo: str, destino: str) -> float:
    return EMISSION_FACTORS.get(tipo, {}).get(destino, 0.0)


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
    respostas = Column(JSON, nullable=False, default={})  # v2: {"modelo":"v2","respostas":{...},"area_pct":{...}}
    score = Column(Integer, nullable=False, default=0)    # 0-100
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

class MTR(Base):
    __tablename__ = "mtrs"
    id = Column(Integer, primary_key=True)
    fornecedor_id = Column(Integer, ForeignKey('fornecedores.id', ondelete="CASCADE"), nullable=False)
    arquivo = Column(String, nullable=False)
    numero_mtr = Column(String)
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
    qtd_original = Column(String)
    und_original = Column(String)
    qtd_kg = Column(Float)
    dados_raw = Column(JSON)

    # NOVOS CAMPOS (Escopo 3)
    tipo_residuo = Column(String)               # ex.: Plástico, Papel, Orgânico, etc.
    destinacao = Column(String)                 # ex.: Aterro, Incineração...
    fator_tco2e_por_ton = Column(Float)         # tCO2e por t
    emissoes_tco2e = Column(Float)              # calculado: (kg / 1000) * fator
    # Flag denormalizado para facilitar KPI CDF (opcional)
    cdf_count = Column(Integer, default=0)

    created_at = Column(Date, server_default=func.current_date())
    updated_at = Column(Date, server_default=func.current_date(), onupdate=func.current_date())
    updated_by = Column(String(150))
    fornecedor = relationship("Fornecedor", back_populates="mtrs")
    cdfs = relationship("CDF", back_populates="mtr", cascade="all, delete-orphan")

class CDF(Base):
    __tablename__ = "cdfs"
    id = Column(Integer, primary_key=True)
    mtr_id = Column(Integer, ForeignKey('mtrs.id', ondelete="CASCADE"), nullable=False)
    arquivo = Column(String, nullable=False)
    data_emissao = Column(Date, nullable=True)
    observacao = Column(String)
    created_at = Column(Date, server_default=func.current_date())
    updated_at = Column(Date, server_default=func.current_date(), onupdate=func.current_date())
    updated_by = Column(String(150))
    mtr = relationship("MTR", back_populates="cdfs")


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


# =========================
#      MIGRAÇÃO SIMPLES
# =========================

def safe_add_column_sqlite(table: str, column: str, coltype: str):
    if not DATABASE_URL.startswith("sqlite"):
        return
    # Verifica se coluna existe
    with engine.connect() as conn:
        res = conn.execute(text(f"PRAGMA table_info({table})")).mappings().all()
        names = [r['name'] for r in res]
        if column not in names:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}"))

def run_light_migrations():
    Base.metadata.create_all(bind=engine)
    # Adiciona colunas novas da MTR (se faltarem)
    safe_add_column_sqlite("mtrs", "tipo_residuo", "TEXT")
    safe_add_column_sqlite("mtrs", "destinacao", "TEXT")
    safe_add_column_sqlite("mtrs", "fator_tco2e_por_ton", "REAL")
    safe_add_column_sqlite("mtrs", "emissoes_tco2e", "REAL")
    safe_add_column_sqlite("mtrs", "cdf_count", "INTEGER DEFAULT 0")
    # Cria Tabela CDF (se não existir): Base.metadata.create_all já cuida disso.


# =========================
#   PARSER DA MTR (PDF)
# =========================

def extract_pdf_data(pdf_path: str) -> dict:
    if not HAVE_PDFPLUMBER:
        raise RuntimeError("pdfplumber não está instalado. Adicione ao requirements.")
    dados = {}
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[0]
        text = page.extract_text() or ""

        mtr_match = re.search(r"MTR nº (\d+)", text)
        dados["MTR - Número"] = mtr_match.group(1).strip() if mtr_match else "N/A"

        g0 = text.find("Identificação do Gerador")
        g1 = text.find("Observações do Gerador")
        generator = text[g0:g1] if g0 != -1 and g1 != -1 else ""
        dados["Gerador - Razão Social"] = (re.search(r"Razão Social: (.*?) - \d+ CPF/CNPJ:", generator).group(1).strip()
                                           if re.search(r"Razão Social: (.*?) - \d+ CPF/CNPJ:", generator) else "N/A")
        dados["Gerador - CPF/CNPJ"] = (re.search(r"CPF/CNPJ: (\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})", generator).group(1).strip()
                                       if re.search(r"CPF/CNPJ: (\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})", generator) else "N/A")
        dados["Gerador - Data da emissão"] = (re.search(r"Data da emissão: (\d{2}/\d{2}/\d{4})", generator).group(1).strip()
                                              if re.search(r"Data da emissão: (\d{2}/\d{2}/\d{4})", generator) else "N/A")
        dados["Gerador - Município"] = (re.search(r"Município: (.*?) UF:", generator).group(1).strip()
                                        if re.search(r"Município: (.*?) UF:", generator) else "N/A")
        dados["Gerador - UF"] = (re.search(r"UF: (\w{2})", generator).group(1).strip()
                                 if re.search(r"UF: (\w{2})", generator) else "N/A")

        t0 = text.find("Identificação do Transportador")
        t1 = text.find("Nome do Motorista")
        transport = text[t0:t1] if t0 != -1 and t1 != -1 else ""
        dados["Transportador - Razão Social"] = (re.search(r"Razão Social: (.*?) - \d+ CPF/CNPJ:", transport).group(1).strip()
                                                 if re.search(r"Razão Social: (.*?) - \d+ CPF/CNPJ:", transport) else "N/A")
        dados["Transportador - CPF/CNPJ"] = (re.search(r"CPF/CNPJ: (\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})", transport).group(1).strip()
                                             if re.search(r"CPF/CNPJ: (\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})", transport) else "N/A")
        _dttr = re.search(r"Data do transporte:\s*(\d{2}/\d{2}/\d{4})?", transport)
        dados["Transportador - Data do transporte"] = _dttr.group(1).strip() if _dttr and _dttr.group(1) else "N/A"

        d0 = text.find("Identificação do Destinador")
        d1 = text.find("Identificação dos Resíduos")
        destin = text[d0:d1] if d0 != -1 and d1 != -1 else ""
        dados["Destinador - Razão Social"] = (re.search(r"Razão Social: (.*?) - \d+ CPF/CNPJ:", destin).group(1).strip()
                                              if re.search(r"Razão Social: (.*?) - \d+ CPF/CNPJ:", destin) else "N/A")
        dados["Destinador - CPF/CNPJ"] = (re.search(r"CPF/CNPJ: (\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})", destin).group(1).strip()
                                          if re.search(r"CPF/CNPJ: (\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})", destin) else "N/A")
        _dtrc = re.search(r"Data do recebimento:\s*(\d{2}/\d{2}/\d{4})?", destin)
        dados["Destinador - Data do recebimento"] = _dtrc.group(1).strip() if _dtrc and _dtrc.group(1) else "N/A"

        # Resíduos (primeiro item)
        waste_start = text.find("Identificação dos Resíduos")
        waste_info_raw = text[waste_start:] if waste_start != -1 else text
        waste_line_match = re.search(
            r"^1\s+([\d-]+)-(.+?)\s+([A-Z]+)\s+CLASSE\s+(.+?)\s+([0-9,.]+)\s+([A-Z]+)\s+(.+)$",
            waste_info_raw, re.MULTILINE
        )
        if waste_line_match:
            codigo_completo = f"{waste_line_match.group(1)}-{waste_line_match.group(2).strip()}"
            dados["Resíduos - Código IBAMA e Denominação"] = codigo_completo[:6]
            dados["Resíduos - Qtde"] = waste_line_match.group(5).strip()
            dados["Resíduos - Unidade"] = waste_line_match.group(6).strip()
        else:
            dados["Resíduos - Código IBAMA e Denominação"] = ""
            dados["Resíduos - Qtde"] = ""
            dados["Resíduos - Unidade"] = ""

    return dados

def extract_and_normalize_mtr(pdf_path: str) -> dict:
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
        "qtd_original": qtd_str or None,
        "und_original": und or None,
        "qtd_kg": qtd_kg,
        "dados_raw": dados
    }


# =========================
# AUDITORIA v2 (0–2 ponderado)
# =========================

AREAS = {
    "licenciamento": {"titulo": "Licenciamento e Conformidade Legal", "peso": 0.30,
        "perguntas": ["Licença válida?", "Ocorrência de autuações?", "Condição e registros de condicionantes?"]},
    "gestao": {"titulo": "Gestão Ambiental", "peso": 0.25,
        "perguntas": ["SGA/ISO 14001 ou equivalente?", "Procedimentos escritos (segregação/transporte/destino)?", "Indicadores e registros?"]},
    "infraestrutura": {"titulo": "Infraestrutura e Operação", "peso": 0.20,
        "perguntas": ["Armazenamento adequado (coberto/impermeável)?", "Plano de contingência?", "Manutenção de frota/emissões?"]},
    "seguranca": {"titulo": "Saúde, Segurança e Trabalhadores", "peso": 0.15,
        "perguntas": ["Trabalhadores registrados?", "EPIs entregues/usados (evidências)?", "Treinamentos periódicos de SSMA?"]},
    "desempenho": {"titulo": "Relacionamento e Desempenho", "peso": 0.10,
        "perguntas": ["Cumpre prazos?", "Trata N/C com plano?", "Relatórios/MTRs regulares?"]},
}
OPCOES = ["Não atende (0)", "Atende parcialmente (1)", "Atende plenamente (2)"]

def calcular_score_v2(respostas_v2: dict) -> tuple[int, dict]:
    area_percentuais = {}
    total_ponderado = 0.0
    for area_key, meta in AREAS.items():
        qs = meta["perguntas"]
        vals = []
        for i in range(1, len(qs)+1):
            k = f"{area_key}.{i}"
            v = respostas_v2.get(k, 0)
            try:
                v = int(v)
            except Exception:
                v = 0
            v = max(0, min(2, v))
            vals.append(v)
        media_area = mean(vals) if vals else 0.0
        pct_area = (media_area / 2.0) * 100.0
        area_percentuais[area_key] = pct_area
        total_ponderado += pct_area * meta["peso"]
    score = int(round(total_ponderado))
    return score, area_percentuais

def classificar(score: int) -> str:
    if score >= 80:
        return "Conforme/Adequado"
    if score >= 60:
        return "Parcialmente Conforme"
    return "Não Conforme/Inadequado"


# =========================
#      INICIALIZAÇÃO DB
# =========================

def init_db_and_seed():
    run_light_migrations()
    with SessionLocal() as db:
        admin_user = "Eduardo"
        admin_pass = "Capitu"
        if not get_user_by_username(db, admin_user):
            create_user(db, admin_user, admin_pass, RoleEnum.admin)


# =========================
#        KPIs / HELPERS
# =========================

def documentos_status(docs) -> tuple[int, int]:
    hoje = date.today()
    limite = hoje + timedelta(days=30)
    vencidos = sum(1 for d in docs if d.data_validade and d.data_validade < hoje)
    a_vencer = sum(1 for d in docs if d.data_validade and hoje <= d.data_validade <= limite)
    return vencidos, a_vencer

def kpis_gerais(db: Session) -> dict:
    total_fornecedores = db.query(Fornecedor).count()
    conformes = db.query(Auditoria).filter(Auditoria.classificado == "Conforme/Adequado").count()
    parcialmente = db.query(Auditoria).filter(Auditoria.classificado == "Parcialmente Conforme").count()
    nao_conformes = db.query(Auditoria).filter(Auditoria.classificado == "Não Conforme/Inadequado").count()
    fornecedores_com_contrato = db.query(Fornecedor).join(Contrato).distinct().count()
    fornecedores_sem_contrato = total_fornecedores - fornecedores_com_contrato

    docs = db.query(Documento).all()
    vencidos, a_vencer = documentos_status(docs)

    mtr_total_kg = float(db.query(func.coalesce(func.sum(MTR.qtd_kg), 0.0)).scalar() or 0.0)
    mtr_por_forn = db.query(Fornecedor.nome, func.coalesce(func.sum(MTR.qtd_kg), 0.0))\
                     .join(MTR, MTR.fornecedor_id == Fornecedor.id, isouter=True)\
                     .group_by(Fornecedor.id).all()

    # NOVO: emissões tCO2e
    total_tco2e = float(db.query(func.coalesce(func.sum(MTR.emissoes_tco2e), 0.0)).scalar() or 0.0)
    tco2e_por_forn = db.query(Fornecedor.nome, func.coalesce(func.sum(MTR.emissoes_tco2e), 0.0))\
                       .join(MTR, MTR.fornecedor_id == Fornecedor.id, isouter=True)\
                       .group_by(Fornecedor.id).all()

    # KPI de CDFs: quantas MTRs já possuem pelo menos 1 CDF
    total_mtrs = int(db.query(MTR).count())
    mtrs_com_cdf = int(db.query(MTR).filter(MTR.cdf_count > 0).count())

    return {
        "total_fornecedores": total_fornecedores,
        "conformes": conformes,
        "parcial": parcialmente,
        "nao_conformes": nao_conformes,
        "forn_com_contrato": fornecedores_com_contrato,
        "forn_sem_contrato": fornecedores_sem_contrato,
        "docs_vencidos": vencidos,
        "docs_a_vencer": a_vencer,
        "mtr_total_kg": mtr_total_kg,
        "mtr_por_forn": [(n, float(v or 0.0)) for n, v in mtr_por_forn],
        "total_tco2e": total_tco2e,
        "tco2e_por_forn": [(n, float(v or 0.0)) for n, v in tco2e_por_forn],
        "total_mtrs": total_mtrs,
        "mtrs_com_cdf": mtrs_com_cdf,
    }


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
                _safe_rerun()
            else:
                st.error("Usuário ou senha incorretos.")

if not st.session_state.logado:
    pagina_login()
    st.stop()

# Menu por perfil
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

    # Pizza classif auditoria
    fig_total = px.pie(
        names=["Conforme/Adequado", "Parcialmente Conforme", "Não Conforme/Inadequado"],
        values=[k["conformes"], k["parcial"], k["nao_conformes"]],
        title="Classificação da Auditoria (v2)",
        color=["Conforme/Adequado", "Parcialmente Conforme", "Não Conforme/Inadequado"],
        color_discrete_map={
            "Conforme/Adequado": "green", "Parcialmente Conforme": "orange", "Não Conforme/Inadequado": "red",
        },
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

    # Badges
    def badge(label, value, good=True):
        color = "#2e7d32" if good else "#c62828"
        bg = "#e8f5e9" if good else "#ffebee"
        return f"""
        <div style="padding:10px;border-radius:8px;background:{bg};margin-bottom:8px;">
            <span style="color:{color};font-weight:600;">{label}:</span>
            <span style="margin-left:6px;color:#111;font-weight:700;">{value}</span>
        </div>
        """

    colA, colB, colC = st.columns(3)
    with colA:
        st.markdown(badge("Total de Fornecedores", k["total_fornecedores"], True), unsafe_allow_html=True)
        st.markdown(badge("Conformes/Adequados", k["conformes"], True), unsafe_allow_html=True)
        st.markdown(badge("MTRs com CDF", f"{k['mtrs_com_cdf']}/{k['total_mtrs']}", True), unsafe_allow_html=True)
    with colB:
        st.markdown(badge("Parcialmente Conforme", k["parcial"], False), unsafe_allow_html=True)
        st.markdown(badge("Não Conformes/Inadequados", k["nao_conformes"], False), unsafe_allow_html=True)
        st.markdown(badge("Doc. a vencer (30d)", k["docs_a_vencer"], False), unsafe_allow_html=True)
    with colC:
        st.markdown(badge("Documentos vencidos", k["docs_vencidos"], False), unsafe_allow_html=True)
        st.markdown(badge("Total kg (MTR)", f"{k['mtr_total_kg']:.1f} kg", True), unsafe_allow_html=True)
        st.markdown(badge("Total tCO₂e (MTR - Escopo 3)", f"{k['total_tco2e']:.2f} t", True), unsafe_allow_html=True)

    # Kg por fornecedor
    st.markdown("### Kg destinados por fornecedor (MTR)")
    mtr_rows = [{"Fornecedor": str(n), "Kg destinados": float(v or 0.0)} for n, v in k["mtr_por_forn"]]
    if HAVE_PANDAS and mtr_rows:
        df_mtr = pd.DataFrame(mtr_rows).sort_values("Kg destinados", ascending=False)
        fig_bar = px.bar(df_mtr, x="Fornecedor", y="Kg destinados", title="Total de kg por fornecedor (MTR)")
    else:
        fig_bar = px.bar(x=[r["Fornecedor"] for r in mtr_rows], y=[r["Kg destinados"] for r in mtr_rows],
                         labels={"x": "Fornecedor", "y": "Kg destinados"},
                         title="Total de kg por fornecedor (MTR)")
    fig_bar.update_traces(marker_color="green")
    st.plotly_chart(fig_bar, use_container_width=True)

    # tCO2e por fornecedor
    st.markdown("### Emissões de Escopo 3 (resíduos) por fornecedor")
    em_rows = [{"Fornecedor": str(n), "tCO₂e": float(v or 0.0)} for n, v in k["tco2e_por_forn"]]
    if HAVE_PANDAS and em_rows:
        df_em = pd.DataFrame(em_rows).sort_values("tCO₂e", ascending=False)
        fig_em = px.bar(df_em, x="Fornecedor", y="tCO₂e", title="tCO₂e por fornecedor (resíduos)")
    else:
        fig_em = px.bar(x=[r["Fornecedor"] for r in em_rows], y=[r["tCO₂e"] for r in em_rows],
                        labels={"x": "Fornecedor", "y": "tCO₂e"},
                        title="tCO₂e por fornecedor (resíduos)")
    fig_em.update_traces(marker_color="red")
    st.plotly_chart(fig_em, use_container_width=True)

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

# ---- Visualizar Fornecedores ----
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
            joinedload(Fornecedor.mtrs).joinedload(MTR.cdfs),
        )
        if termo:
            fornecedores = fornecedores.filter(Fornecedor.nome.ilike(f"%{termo.strip()}%"))
        fornecedores = fornecedores.order_by(Fornecedor.nome.asc()).all()

    if not fornecedores:
        st.info("Nenhum fornecedor encontrado.")
        st.stop()

    col_left, col_right = st.columns([0.35, 0.65])
    with col_left:
        st.subheader("Lista")
        for f in fornecedores:
            is_selected = (st.session_state.sel_forn_id == f.id)
            style = "background:#e8f5e9;border:1px solid #2e7d32;" if is_selected else "background:#f6f6f6;border:1px solid #ddd;"
            if st.button(f"📁 {f.nome} — {formatar_cpf_cnpj(f.cpf_cnpj)}", key=f"btn_f_{f.id}"):
                st.session_state.sel_forn_id = f.id
            st.markdown(f"<div style='height:6px;{style}'></div>", unsafe_allow_html=True)

    with col_right:
        sel = next((f for f in fornecedores if f.id == st.session_state.sel_forn_id), None)
        if sel is None:
            st.info("Selecione um fornecedor na lista ao lado para visualizar/editar.")
        else:
            st.subheader(f"Detalhes — {sel.nome}")
            tabs = st.tabs(["Informações", "Documentos", "Auditoria", "Planos de Ação", "Contratos", "MTRs"])

            # Info
            with tabs[0]:
                st.write(f"**CPF/CNPJ:** {formatar_cpf_cnpj(sel.cpf_cnpj)}")
                st.write(f"**Endereço:** {sel.endereco or '-'}")
                st.write(f"**Telefone:** {sel.telefone or '-'}")

            # Documentos
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

            # Auditoria
            with tabs[2]:
                st.subheader("Auditoria (0–2 ponderada)")
                aud_exist = sel.auditoria
                prev = {}
                if aud_exist and isinstance(aud_exist.respostas, dict) and aud_exist.respostas.get("modelo") == "v2":
                    prev = aud_exist.respostas.get("respostas", {}) or {}
                respostas_form = {}
                for area_key, meta in AREAS.items():
                    with st.expander(f"{meta['titulo']} — peso {int(meta['peso']*100)}%"):
                        for i, pergunta in enumerate(meta["perguntas"], start=1):
                            k = f"{area_key}.{i}"
                            default = int(prev.get(k, 0))
                            escolha = st.radio(pergunta, OPCOES, index=default, key=f"aud_{sel.id}_{k}", horizontal=True)
                            respostas_form[k] = OPCOES.index(escolha)
                if st.button("Salvar Auditoria", key=f"save_aud_{sel.id}"):
                    score, area_pct = calcular_score_v2(respostas_form)
                    classific = classificar(score)
                    payload = {"modelo": "v2", "respostas": respostas_form, "area_pct": area_pct}
                    with SessionLocal() as db:
                        aud = db.query(Auditoria).filter_by(fornecedor_id=sel.id).first()
                        if not aud:
                            aud = Auditoria(
                                fornecedor_id=sel.id,
                                respostas=payload,
                                score=score,
                                classificado=classific,
                                updated_by=st.session_state.usuario,
                            )
                            db.add(aud)
                        else:
                            aud.respostas = payload
                            aud.score = score
                            aud.classificado = classific
                            aud.updated_by = st.session_state.usuario
                        db.commit()
                        st.success(f"Auditoria salva. Score: {score}%. Classificação: {classific}")
                        _safe_rerun()

                with SessionLocal() as db:
                    aud_show = db.query(Auditoria).filter_by(fornecedor_id=sel.id).first()
                if aud_show and isinstance(aud_show.respostas, dict) and aud_show.respostas.get("modelo") == "v2":
                    area_pct = aud_show.respostas.get("area_pct", {})
                    if area_pct:
                        if HAVE_PANDAS:
                            df_area = pd.DataFrame({
                                "Área": [AREAS[k]["titulo"] for k in AREAS.keys()],
                                "% atendimento": [area_pct.get(k, 0.0) for k in AREAS.keys()],
                            })
                            fig_area = px.bar(df_area, x="Área", y="% atendimento", title="Atendimento por área (%)")
                        else:
                            nomes = [AREAS[k]["titulo"] for k in AREAS.keys()]
                            valores = [area_pct.get(k, 0.0) for k in AREAS.keys()]
                            fig_area = px.bar(x=nomes, y=valores, labels={"x": "Área", "y": "%"}, title="Atendimento por área (%)")
                        fig_area.update_traces(marker_color="green")
                        st.plotly_chart(fig_area, use_container_width=True)
                    st.markdown(f"**Última auditoria:** Score {aud_show.score}%, Classificação: {aud_show.classificado}")

            # Planos de ação
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
                            _safe_rerun()

                for p in sel.planos_acao:
                    with st.container(border=True):
                        st.markdown(f"**{p.descricao}** — {p.status} — {p.data_inicio} → {p.data_fim}")
                        if p.evidencias:
                            st.write("Evidências:")
                            for ev in p.evidencias:
                                if Path(ev).exists():
                                    exibir_preview_arquivo(ev, None)

            # Contratos
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
                                _safe_rerun()
                            except Exception as e:
                                db.rollback()
                                st.error(f"Erro ao salvar contrato: {e}")

                for c in sel.contratos:
                    with st.container(border=True):
                        st.write(f"- Assinado em: {c.data_assinatura}, Validade: {c.data_validade}")
                        if Path(c.arquivo).exists():
                            exibir_preview_arquivo(c.arquivo, None)

            # MTRs do fornecedor
            with tabs[5]:
                st.subheader("MTRs do fornecedor")
                total_kg = sum(m.qtd_kg or 0.0 for m in sel.mtrs)
                total_t = sum(m.emissoes_tco2e or 0.0 for m in sel.mtrs)
                st.write(f"**Total destinado (kg):** {total_kg:.1f} | **Total tCO₂e:** {total_t:.2f}")

                for m in sel.mtrs:
                    with st.container(border=True):
                        st.write(f"**MTR nº**: {m.numero_mtr or '-'} | **Receb.:** {m.destinador_data_recebimento or '-'} | **kg:** {m.qtd_kg or 0.0:.1f}")

                        # Edição escopo 3
                        c1, c2, c3, c4 = st.columns([0.25, 0.25, 0.25, 0.25])
                        with c1:
                            tipo_sel = st.selectbox("Tipo de resíduo", TIPOS_RESIDUO, index=TIPOS_RESIDUO.index(m.tipo_residuo) if m.tipo_residuo in TIPOS_RESIDUO else TIPOS_RESIDUO.index("Misto/Outros"), key=f"tipo_{m.id}")
                        with c2:
                            destinos_opts = destinos_para_tipo(tipo_sel)
                            dest_sel = st.selectbox("Destinação", destinos_opts, index=(destinos_opts.index(m.destinacao) if m.destinacao in destinos_opts else 0), key=f"dest_{m.id}")
                        with c3:
                            default_fator = fator_default(tipo_sel, dest_sel)
                            fator = st.number_input("Fator (tCO₂e/t)", value=float(m.fator_tco2e_por_ton or default_fator), step=0.01, format="%.4f", key=f"fator_{m.id}")
                        with c4:
                            # cálculo on the fly
                            em_calc = kg_to_ton(m.qtd_kg) * (fator or 0.0)
                            st.write(f"**tCO₂e calc.:** {em_calc:.4f}")

                        if st.button("Salvar MTR (Escopo 3)", key=f"salvar_mtr_{m.id}"):
                            with SessionLocal() as db:
                                mm = db.query(MTR).get(m.id)
                                mm.tipo_residuo = tipo_sel
                                mm.destinacao = dest_sel
                                mm.fator_tco2e_por_ton = float(fator or 0.0)
                                mm.emissoes_tco2e = kg_to_ton(mm.qtd_kg) * (mm.fator_tco2e_por_ton or 0.0)
                                mm.updated_by = st.session_state.usuario
                                db.commit()
                                st.success("MTR atualizada (escopo 3).")
                                _safe_rerun()

                        # CDFs
                        st.markdown("**CDF(s):**")
                        if m.cdfs:
                            for cdf in m.cdfs:
                                with st.container():
                                    st.write(f"- Emissão: {cdf.data_emissao or '-'} | Obs: {cdf.observacao or '-'}")
                                    if Path(cdf.arquivo).exists():
                                        exibir_preview_arquivo(cdf.arquivo, None)
                        up_cdf = st.file_uploader("Anexar CDF (PDF/JPG/PNG)", type=["pdf", "jpg", "jpeg", "png"], key=f"cdf_up_{m.id}")
                        cdf_data = st.date_input("Data de emissão do CDF", value=date.today(), key=f"cdf_dt_{m.id}")
                        cdf_obs = st.text_input("Observação (opcional)", key=f"cdf_obs_{m.id}")
                        if st.button("Adicionar CDF", key=f"cdf_add_{m.id}"):
                            if not up_cdf:
                                st.error("Envie um arquivo de CDF.")
                            else:
                                caminho = salvar_arquivo(up_cdf, "uploads/cdfs", f"{m.id}_cdf")
                                with SessionLocal() as db:
                                    try:
                                        novo = CDF(
                                            mtr_id=m.id,
                                            arquivo=caminho,
                                            data_emissao=cdf_data,
                                            observacao=cdf_obs.strip() or None,
                                            updated_by=st.session_state.usuario,
                                        )
                                        db.add(novo)
                                        # atualiza contador
                                        mm = db.query(MTR).get(m.id)
                                        mm.cdf_count = (mm.cdf_count or 0) + 1
                                        db.commit()
                                        st.success("CDF anexado com sucesso!")
                                        _safe_rerun()
                                    except Exception as e:
                                        db.rollback()
                                        st.error(f"Erro ao salvar CDF: {e}")

# ---- Página MTRs ----
elif menu == "MTRs":
    if st.session_state.role not in (RoleEnum.admin.value, RoleEnum.auditor.value):
        st.error("Acesso restrito. Seu perfil é Leitor e possui acesso apenas ao Overview.")
        st.stop()

    st.header("Controle de MTRs por Fornecedor")
    if not HAVE_PDFPLUMBER:
        st.error("pdfplumber não está instalado. Adicione no requirements.")
        st.stop()

    with SessionLocal() as db:
        fornecedores = db.query(Fornecedor).order_by(Fornecedor.nome.asc()).all()
    if not fornecedores:
        st.info("Cadastre fornecedores antes de importar MTRs.")
        st.stop()

    forn_map = {f"{f.nome} — {formatar_cpf_cnpj(f.cpf_cnpj)}": f.id for f in fornecedores}
    forn_label = st.selectbox("Associar MTRs ao fornecedor", list(forn_map.keys()))
    fornecedor_id = forn_map[forn_label]

    uploads = st.file_uploader("Enviar PDFs de MTR", type=["pdf"], accept_multiple_files=True)
    if uploads and st.button("Processar MTRs"):
        ok, fail = 0, 0
        for up in uploads:
            try:
                caminho = salvar_arquivo(up, "uploads/mtrs", f"{fornecedor_id}_mtr")
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
                        qtd_original=dados["qtd_original"],
                        und_original=dados["und_original"],
                        qtd_kg=dados["qtd_kg"],
                        dados_raw=dados["dados_raw"],
                        updated_by=st.session_state.usuario,
                    )
                    # inicialmente sem escopo 3 definido
                    db.add(m)
                    db.commit()
                    ok += 1
            except Exception as e:
                fail += 1
                st.error(f"Erro ao processar um PDF: {e}")
        st.success(f"Processo finalizado. Sucesso: {ok} | Falhas: {fail}")
        _safe_rerun()

    # Edição em lote: tipo/destino/fator
    st.markdown("### Edição em lote (Escopo 3)")
    with SessionLocal() as db:
        mtrs = db.query(MTR).filter(MTR.fornecedor_id == fornecedor_id).order_by(MTR.created_at.desc()).all()

    if not mtrs:
        st.info("Nenhuma MTR cadastrada para este fornecedor.")
    else:
        for m in mtrs:
            with st.container(border=True):
                st.write(f"**MTR:** {m.numero_mtr or '-'} | **kg:** {m.qtd_kg or 0.0:.1f}")
                c1, c2, c3, c4 = st.columns([0.25, 0.25, 0.25, 0.25])
                with c1:
                    tipo_sel = st.selectbox("Tipo de resíduo", TIPOS_RESIDUO, index=(TIPOS_RESIDUO.index(m.tipo_residuo) if m.tipo_residuo in TIPOS_RESIDUO else TIPOS_RESIDUO.index("Misto/Outros")), key=f"tipo_mtrs_{m.id}")
                with c2:
                    destinos_opts = destinos_para_tipo(tipo_sel)
                    dest_sel = st.selectbox("Destinação", destinos_opts, index=(destinos_opts.index(m.destinacao) if m.destinacao in destinos_opts else 0), key=f"dest_mtrs_{m.id}")
                with c3:
                    default_fator = fator_default(tipo_sel, dest_sel)
                    fator = st.number_input("Fator (tCO₂e/t)", value=float(m.fator_tco2e_por_ton or default_fator), step=0.01, format="%.4f", key=f"fator_mtrs_{m.id}")
                with c4:
                    em_calc = kg_to_ton(m.qtd_kg) * (fator or 0.0)
                    st.write(f"**tCO₂e calc.:** {em_calc:.4f}")

                if st.button("Salvar (Escopo 3)", key=f"save_mtrs_{m.id}"):
                    with SessionLocal() as db:
                        mm = db.query(MTR).get(m.id)
                        mm.tipo_residuo = tipo_sel
                        mm.destinacao = dest_sel
                        mm.fator_tco2e_por_ton = float(fator or 0.0)
                        mm.emissoes_tco2e = kg_to_ton(mm.qtd_kg) * (mm.fator_tco2e_por_ton or 0.0)
                        mm.updated_by = st.session_state.usuario
                        db.commit()
                        st.success("MTR atualizada (escopo 3).")
                        _safe_rerun()

                # CDF upload rápido
                up_cdf = st.file_uploader("Anexar CDF (PDF/JPG/PNG)", type=["pdf", "jpg", "jpeg", "png"], key=f"cdf_up_list_{m.id}")
                cdf_data = st.date_input("Data de emissão do CDF", value=date.today(), key=f"cdf_dt_list_{m.id}")
                cdf_obs = st.text_input("Observação (opcional)", key=f"cdf_obs_list_{m.id}")
                if st.button("Adicionar CDF", key=f"cdf_add_list_{m.id}"):
                    if not up_cdf:
                        st.error("Envie um arquivo de CDF.")
                    else:
                        caminho = salvar_arquivo(up_cdf, "uploads/cdfs", f"{m.id}_cdf")
                        with SessionLocal() as db:
                            novo = CDF(mtr_id=m.id, arquivo=caminho, data_emissao=cdf_data, observacao=cdf_obs.strip() or None, updated_by=st.session_state.usuario)
                            db.add(novo)
                            mm = db.query(MTR).get(m.id)
                            mm.cdf_count = (mm.cdf_count or 0) + 1
                            db.commit()
                            st.success("CDF anexado.")
                            _safe_rerun()

    st.markdown("### MTRs cadastradas")
    with SessionLocal() as db:
        mtrs_all = db.query(MTR).join(Fornecedor).add_columns(Fornecedor.nome).order_by(MTR.created_at.desc()).all()
    if not mtrs_all:
        st.info("Nenhuma MTR cadastrada ainda.")
    else:
        rows = []
        for m, nome_f in mtrs_all:
            rows.append({
                "Fornecedor": nome_f,
                "MTR nº": m.numero_mtr or "-",
                "Recebimento": m.destinador_data_recebimento or "",
                "Qtde (kg)": m.qtd_kg if m.qtd_kg is not None else "",
                "Tipo": m.tipo_residuo or "",
                "Destinação": m.destinacao or "",
                "Fator (tCO₂e/t)": m.fator_tco2e_por_ton if m.fator_tco2e_por_ton is not None else "",
                "tCO₂e": m.emissoes_tco2e if m.emissoes_tco2e is not None else "",
                "CDF(s)": m.cdf_count or 0,
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
    with SessionLocal() as db:
        usuarios = db.query(User).all()
    st.subheader("Usuários")
    for u in usuarios:
        st.write(f"- **{u.username}** — {u.role.value}")

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
                    _safe_rerun()

    # Export Excel
    st.subheader("Exportar dados (Excel)")
    if not HAVE_PANDAS:
        st.info("Para exportar, instale: pandas e openpyxl.")
    else:
        if st.button("Gerar arquivo .xlsx"):
            with SessionLocal() as db:
                fornecedores = db.query(Fornecedor).options(
                    joinedload(Fornecedor.documentos),
                    joinedload(Fornecedor.auditoria),
                    joinedload(Fornecedor.planos_acao),
                    joinedload(Fornecedor.contratos),
                    joinedload(Fornecedor.mtrs).joinedload(MTR.cdfs),
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
                        modelo = a.respostas.get("modelo") if isinstance(a.respostas, dict) else "v1"
                        area_pct = a.respostas.get("area_pct") if isinstance(a.respostas, dict) else None
                        rows_a.append({
                            "fornecedor_id": f.id, "fornecedor": f.nome,
                            "score": a.score, "classificado": a.classificado,
                            "modelo": modelo,
                            "area_pct_json": json.dumps(area_pct, ensure_ascii=False) if area_pct else "",
                            "respostas_json": json.dumps(a.respostas, ensure_ascii=False),
                            "updated_by": a.updated_by
                        })
                pd.DataFrame(rows_a).to_excel(writer, sheet_name="Auditorias", index=False)

                # Planos
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
                            "tipo_residuo": m.tipo_residuo, "destinacao": m.destinacao,
                            "fator_tco2e_t": m.fator_tco2e_por_ton, "tco2e": m.emissoes_tco2e,
                            "cdf_count": m.cdf_count,
                            "arquivo": m.arquivo
                        })
                pd.DataFrame(rows_m).to_excel(writer, sheet_name="MTRs", index=False)

                # CDFs
                rows_cdf = []
                for f in fornecedores:
                    for m in f.mtrs:
                        for cdf in m.cdfs:
                            rows_cdf.append({
                                "fornecedor_id": f.id, "fornecedor": f.nome,
                                "mtr_numero": m.numero_mtr,
                                "cdf_data": cdf.data_emissao, "observacao": cdf.observacao,
                                "arquivo": cdf.arquivo
                            })
                pd.DataFrame(rows_cdf).to_excel(writer, sheet_name="CDFs", index=False)

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
    _safe_rerun()
