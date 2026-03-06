# app.py — Streamlit único com:
# - Importação/parse de MTR robusto (todas as páginas + fallbacks)
# - Fluxo de importação de MTR com revisão e confirmação antes de salvar
# - Planos de Ação com painel de status (editar status no cartão)
# - Restante das features existentes (login, docs com download, auditoria, CDF, KPIs, export Excel)

import os, re, uuid, json, traceback
from io import BytesIO
from pathlib import Path
from datetime import date, timedelta, datetime

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import bcrypt
from statistics import mean
from decimal import Decimal

from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Date, ForeignKey, Enum,
    UniqueConstraint, JSON, func, text
)
from sqlalchemy.orm import sessionmaker, declarative_base, relationship, joinedload, Session
from sqlalchemy.orm import selectinload
import enum

# ===== (Excel/Data) =====
try:
    import pandas as pd
    HAVE_PANDAS = True
except Exception:
    HAVE_PANDAS = False

# ===== (PDF/MTR) =====
try:
    import pdfplumber
    HAVE_PDFPLUMBER = True
except Exception:
    HAVE_PDFPLUMBER = False

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
    try: st.rerun()
    except Exception:
        try: st.experimental_rerun()
        except Exception: pass

def so_digitos(s:str) -> str:
    return re.sub(r"\D", "", s or "")

def normalizar_telefone(s:str) -> str:
    return so_digitos(s)

def validar_cpf(cpf:str)->bool:
    cpf = so_digitos(cpf)
    if len(cpf)!=11 or cpf==cpf[0]*11: return False
    soma=sum(int(cpf[i])*(10-i) for i in range(9)); d1=(soma*10)%11; d1=0 if d1==10 else d1
    soma=sum(int(cpf[i])*(11-i) for i in range(10)); d2=(soma*10)%11; d2=0 if d2==10 else d2
    return cpf[-2:]==f"{d1}{d2}"

def validar_cnpj(cnpj:str)->bool:
    cnpj=so_digitos(cnpj)
    if len(cnpj)!=14 or cnpj==cnpj[0]*14: return False
    p1=[5,4,3,2,9,8,7,6,5,4,3,2]; p2=[6]+p1
    s1=sum(int(cnpj[i])*p1[i] for i in range(12)); d1=11-(s1%11); d1=0 if d1>=10 else d1
    s2=sum(int(cnpj[i])*p2[i] for i in range(13)); d2=11-(s2%11); d2=0 if d2>=10 else d2
    return cnpj[-2:]==f"{d1}{d2}"

def validar_cpf_cnpj(v:str)->bool:
    d=so_digitos(v)
    return (len(d)==11 and validar_cpf(d)) or (len(d)==14 and validar_cnpj(d))

def formatar_cpf_cnpj(dig:str)->str:
    dig=so_digitos(dig)
    if len(dig)==11: return f"{dig[:3]}.{dig[3:6]}.{dig[6:9]}-{dig[9:]}"
    if len(dig)==14: return f"{dig[:2]}.{dig[2:5]}.{dig[5:8]}/{dig[8:12]}-{dig[12:]}"
    return dig

def salvar_arquivo(uploaded_file, pasta:str, prefixo:str)->str:
    Path(pasta).mkdir(parents=True, exist_ok=True)
    ext = Path(uploaded_file.name).suffix.lower()
    safe_stem = re.sub(r"[^a-zA-Z0-9_-]+","_", prefixo)[:50] or "file"
    fn = f"{safe_stem}_{uuid.uuid4().hex}{ext}"
    caminho = Path(pasta)/fn
    caminho.write_bytes(uploaded_file.getbuffer())
    return str(caminho)

def exibir_preview_arquivo(caminho: str, mime_type: str | None):
    try:
        p=Path(caminho)
        if not p.exists(): st.caption("Arquivo não encontrado."); return
        data = p.read_bytes()
        ext = p.suffix.lower()
        if not mime_type:
            if ext in [".png",".jpg",".jpeg"]: mime_type="image/jpeg" if ext!=".png" else "image/png"
            elif ext==".pdf": mime_type="application/pdf"
            else: mime_type="application/octet-stream"
        if mime_type.startswith("image/"): st.image(data)
        elif mime_type=="application/pdf":
            st.download_button("Baixar PDF", data=data, file_name=p.name, key=f"dl_{uuid.uuid4().hex}")
        else:
            st.download_button("Baixar arquivo", data=data, file_name=p.name, key=f"dl_{uuid.uuid4().hex}")
    except Exception as e:
        st.warning(f"Não foi possível preparar o download: {e}")

def parse_data_br(s:str)->date|None:
    try: return datetime.strptime(s, "%d/%m/%Y").date()
    except Exception: return None

def parse_data_flex(s:str)->date|None:
    txt = (s or "").strip()
    if not txt:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(txt, fmt).date()
        except Exception:
            pass
    return None

def to_float(s:str)->float|None:
    if not s: return None
    s = s.strip().replace(".","").replace(",",".")
    try: return float(s)
    except Exception: return None

def unidade_to_kg(qtd:float|None, und:str|None)->float|None:
    if qtd is None: return None
    u=(und or "").strip().upper()
    if u in ("KG","KGS","KILOS","QUILOS"): return qtd
    if u in ("T","TON","TONS","TONELADA","TONELADAS"): return qtd*1000.0
    return qtd

def kg_to_ton(kg:float|None)->float:
    return (kg or 0.0)/1000.0

def _make_json_safe(obj):
    """Normaliza estruturas para serem serializáveis em JSON."""
    if isinstance(obj, (str, int, float)) or obj is None:
        return obj
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {str(_make_json_safe(k)): _make_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_make_json_safe(v) for v in obj]
    try:
        return json.loads(json.dumps(obj, ensure_ascii=False))
    except Exception:
        return str(obj)

# =========================
#          MODELOS
# =========================
class RoleEnum(str, enum.Enum):
    admin="Admin"; auditor="Auditor"; leitor="Leitor"

class SiteEnum(str, enum.Enum):
    CAC = "CAC"
    SJC = "SJC"
    PER = "PER"
    JUN = "JUN"
    JAC = "JAC"
    DIA = "DIA"
    LAG = "LAG"

SITES_PRODUTIVOS = (
    SiteEnum.CAC.value,
    SiteEnum.SJC.value,
    SiteEnum.PER.value,
    SiteEnum.JUN.value,
    SiteEnum.JAC.value,
    SiteEnum.DIA.value,
)
TODOS_SITES = SITES_PRODUTIVOS + (SiteEnum.LAG.value,)

class User(Base):
    __tablename__="users"
    id = Column(Integer, primary_key=True)
    username = Column(String(150), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(RoleEnum), nullable=False, default=RoleEnum.auditor)
    site = Column(Enum(SiteEnum), nullable=False, default=SiteEnum.CAC)
    created_at = Column(Date, server_default=func.current_date())

class Fornecedor(Base):
    __tablename__="fornecedores"
    id = Column(Integer, primary_key=True)
    nome = Column(String, nullable=False)
    cpf_cnpj = Column(String(14), unique=True, nullable=False)
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
    __tablename__="documentos"
    __table_args__=(UniqueConstraint('fornecedor_id','tipo',name='uq_doc_fornecedor_tipo'),)
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
    __tablename__="auditorias"
    id = Column(Integer, primary_key=True)
    fornecedor_id = Column(Integer, ForeignKey('fornecedores.id', ondelete="CASCADE"), nullable=False)
    respostas = Column(JSON, nullable=False, default=dict)  # <- evitar default mutável
    score = Column(Integer, nullable=False, default=0)
    classificado = Column(String, nullable=False, default="Não Conforme")
    created_at = Column(Date, server_default=func.current_date())
    updated_at = Column(Date, server_default=func.current_date(), onupdate=func.current_date())
    updated_by = Column(String(150))
    fornecedor = relationship("Fornecedor", back_populates="auditoria")

class PlanoStatusEnum(str, enum.Enum):
    andamento="Em andamento"; concluido="Concluído"; atrasado="Atrasado"

class PlanoAcao(Base):
    __tablename__="planos_acao"
    id = Column(Integer, primary_key=True)
    fornecedor_id = Column(Integer, ForeignKey('fornecedores.id', ondelete="CASCADE"), nullable=False)
    descricao = Column(String, nullable=False)
    data_inicio = Column(Date, nullable=False)
    data_fim = Column(Date, nullable=False)
    status = Column(Enum(PlanoStatusEnum), nullable=False, default=PlanoStatusEnum.andamento)
    evidencias = Column(JSON, nullable=False, default=list)
    created_at = Column(Date, server_default=func.current_date())
    updated_at = Column(Date, server_default=func.current_date(), onupdate=func.current_date())
    updated_by = Column(String(150))
    fornecedor = relationship("Fornecedor", back_populates="planos_acao")

class Contrato(Base):
    __tablename__="contratos"
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
    __tablename__="mtrs"
    id = Column(Integer, primary_key=True)
    fornecedor_id = Column(Integer, ForeignKey('fornecedores.id', ondelete="CASCADE"), nullable=False)
    arquivo = Column(String, nullable=False)
    numero_mtr = Column(String)
    gerador_razao = Column(String); gerador_cnpj = Column(String)
    gerador_municipio = Column(String); gerador_uf = Column(String)
    gerador_data_emissao = Column(Date, nullable=True)
    transportador_razao = Column(String); transportador_cnpj = Column(String)
    transportador_data_transporte = Column(Date, nullable=True)
    destinador_razao = Column(String); destinador_cnpj = Column(String)
    destinador_data_recebimento = Column(Date, nullable=True)
    codigo_ibama_denom = Column(String)
    estado_fisico = Column(String); classe = Column(String); acondicionamento = Column(String)
    qtd_original = Column(String); und_original = Column(String)
    qtd_kg = Column(Float)
    dados_raw = Column(JSON)
    cdf_count = Column(Integer, default=0)
    site = Column(Enum(SiteEnum), nullable=False, default=SiteEnum.CAC)
    created_at = Column(Date, server_default=func.current_date())
    updated_at = Column(Date, server_default=func.current_date(), onupdate=func.current_date())
    updated_by = Column(String(150))
    fornecedor = relationship("Fornecedor", back_populates="mtrs")
    cdfs = relationship("CDF", back_populates="mtr", cascade="all, delete-orphan")

class CDF(Base):
    __tablename__="cdfs"
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
def hash_password(p:str)->str: return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()
def verify_password(p:str,h:str)->bool:
    try: return bcrypt.checkpw(p.encode(), h.encode())
    except Exception: return False

def get_user_by_username(db:Session, username:str)->User|None:
    return db.query(User).filter(User.username==username).first()

def create_user(db:Session, username:str, password:str, role:RoleEnum, site:SiteEnum)->User:
    u=User(username=username, password_hash=hash_password(password), role=role, site=site)
    db.add(u); db.commit(); db.refresh(u); return u

# =========================
#      MIGRAÇÃO/SEED
# =========================
def run_light_migrations():
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        try:
            cols = [r[1] for r in conn.execute(text("PRAGMA table_info(users)"))]
            if "site" not in cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN site VARCHAR(3) DEFAULT 'CAC' NOT NULL"))
                conn.execute(text("UPDATE users SET site='LAG' WHERE username='Eduardo'"))
                conn.execute(text("UPDATE users SET site='CAC' WHERE site IS NULL OR site=''"))
        except Exception:
            pass
        try:
            cols = [r[1] for r in conn.execute(text("PRAGMA table_info(mtrs)"))]
            if "site" not in cols:
                conn.execute(text("ALTER TABLE mtrs ADD COLUMN site VARCHAR(3) DEFAULT 'CAC' NOT NULL"))
                conn.execute(text("UPDATE mtrs SET site='CAC' WHERE site IS NULL OR site=''"))
        except Exception:
            pass

def seed_users():
    with SessionLocal() as db:
        if not get_user_by_username(db, "Eduardo"):
            create_user(db, "Eduardo", "Capitu", RoleEnum.admin, SiteEnum.LAG)

# =========================
#   PARSER DA MTR (PDF)
# =========================
def _load_pdf_text_all_pages(pdf_path:str) -> str:
    """
    Concatena o texto de todas as páginas, lidando com páginas sem OCR.
    """
    if not HAVE_PDFPLUMBER:
        raise RuntimeError("pdfplumber não está instalado.")
    texts=[]
    with pdfplumber.open(pdf_path) as pdf:
        for p in pdf.pages:
            try:
                t = p.extract_text() or ""
            except Exception:
                t = ""
            texts.append(t)
    full = "\n".join(texts).strip()
    return full

def _find(pattern, src, flags=0):
    m = re.search(pattern, src, flags)
    return m.group(1).strip() if m else None

def extract_pdf_data(pdf_path:str)->dict:
    """
    Parser tolerante ao layout do MTR (inclui formato do exemplo enviado).
    - Procura MTR nº
    - Extrai blocos de Gerador/Transportador/Destinador quando possível
    - Na seção de resíduos, procura linha de código 'NNNNNN-...' e pares 'Qtde Unid'
    """
    dados={}
    try:
        text = _load_pdf_text_all_pages(pdf_path)

        # --- MTR nº (aceita variações: nº, n°, número)
        mtr_match = re.search(r"MTR\s*(?:n[\W_]*[ºo°]?|n[uú]mero)?\s*[:\-]?\s*([0-9]{6,})", text, flags=re.IGNORECASE)
        dados["MTR - Número"] = (mtr_match.group(1).strip() if mtr_match else "N/A")

        # --- Gerador
        g0=text.find("Identificação do Gerador"); g1=text.find("Observações do Gerador")
        generator = text[g0:g1] if (g0!=-1 and g1!=-1 and g1>g0) else text
        dados["Gerador - Razão Social"] = _find(r"Identificação do Gerador.*?Razão Social:\s*(.*)", generator, re.IGNORECASE|re.DOTALL) or \
                                          _find(r"Razão Social:\s*(.*)", generator)
        dados["Gerador - CPF/CNPJ"] = _find(r"CPF/CNPJ:\s*([\d\.\-\/]+)", generator)
        dados["Gerador - Data da emissão"] = _find(r"Data da emissão:\s*(\d{2}/\d{2}/\d{4})", text)
        dados["Gerador - Município"] = _find(r"Município:\s*([A-ZÇÃÕÂÊÉÍÓÚ\s]+)\s*UF:", generator)
        dados["Gerador - UF"] = _find(r"UF:\s*([A-Z]{2})", generator)

        # --- Transportador
        t0=text.find("Identificação do Transportador"); t1=text.find("Identificação do Destinador")
        transport = text[t0:t1] if (t0!=-1 and t1!=-1 and t1>t0) else text
        dados["Transportador - Razão Social"] = _find(r"Identificação do Transportador.*?Razão Social:\s*(.*)", transport, re.IGNORECASE|re.DOTALL) or \
                                                _find(r"Razão Social:\s*(.*)", transport)
        dados["Transportador - CPF/CNPJ"] = _find(r"CPF/CNPJ:\s*([\d\.\-\/]+)", transport)
        dados["Transportador - Data do transporte"] = _find(r"Data do transporte:\s*(\d{2}/\d{2}/\d{4})", text)

        # --- Destinador
        d0=text.find("Identificação do Destinador"); d1=text.find("Identificação dos Resíduos")
        destin = text[d0:d1] if (d0!=-1 and d1!=-1 and d1>d0) else text
        dados["Destinador - Razão Social"] = _find(r"Identificação do Destinador.*?Razão Social:\s*(.*)", destin, re.IGNORECASE|re.DOTALL) or \
                                             _find(r"Razão Social:\s*(.*)", destin)
        dados["Destinador - CPF/CNPJ"] = _find(r"CPF/CNPJ:\s*([\d\.\-\/]+)", destin)
        dados["Destinador - Data do recebimento"] = _find(r"Data do recebimento:\s*(\d{2}/\d{2}/\d{4})", text)

        # --- Resíduos
        waste_start = text.find("Identificação dos Resíduos")
        waste_info_raw = text[waste_start:] if waste_start!=-1 else text

        # Código IBAMA + denominação (ex.: 200301-Outros resíduos ...)
        m_code = re.search(r"\b(\d{6})\s*[-–]\s*([^\n]+)", waste_info_raw)
        if m_code:
            dados["Resíduos - Código IBAMA e Denominação"] = f"{m_code.group(1)}-{m_code.group(2).strip()}"
        else:
            dados["Resíduos - Código IBAMA e Denominação"] = ""

        # Classe (ex.: CLASSE II A) e estado físico (ex.: SOLIDO)
        m_estado = re.search(r"\b(S[ÓO]LID[OA]|L[ÍI]QUID[OA]|GASOS[OA])\b", waste_info_raw, re.IGNORECASE)
        dados["Resíduos - Estado Físico"] = (m_estado.group(1).upper() if m_estado else "")
        m_class = re.search(r"\bCLASSE\s+([IVX]+(?:\s*[AB])?)\b", waste_info_raw, re.IGNORECASE)
        dados["Resíduos - Classe"] = (m_class.group(1).upper() if m_class else "")

        # Acondicionamento (ex.: CAÇAMBA FECHADA)
        m_acond = re.search(r"\b(CA[ÇC]AMBA\s+[A-Z ]+|BOMBONA|TAMBOR|BIG\s*BAG|SACO\s*PL[ÁA]STICO)\b", waste_info_raw, re.IGNORECASE)
        dados["Resíduos - Acondicionamento"] = (m_acond.group(1).strip().upper() if m_acond else "")

        # Quantidade e Unidade — tenta padrão "0,4800 TON" primeiro (compatível com o exemplo)
        m_qty_inline = re.search(r"(\d{1,3}(?:\.\d{3})*,\d+|\d+,\d+)\s*([A-Za-z]{2,})", waste_info_raw)
        if m_qty_inline:
            dados["Resíduos - Qtde"] = m_qty_inline.group(1).strip()
            dados["Resíduos - Unidade"] = m_qty_inline.group(2).strip().upper()
        else:
            # fallbacks: "Qtde: NNN KG" ou "Peso: NNN KG"
            m_qty = re.search(r"Qtde[:\s]+([0-9\.\,]+)\s*([A-Za-z]+)", waste_info_raw, re.IGNORECASE)
            m_qty2 = re.search(r"Peso[:\s]+([0-9\.\,]+)\s*([A-Za-z]+)", waste_info_raw, re.IGNORECASE)
            if m_qty:
                dados["Resíduos - Qtde"] = m_qty.group(1).strip()
                dados["Resíduos - Unidade"] = m_qty.group(2).strip().upper()
            elif m_qty2:
                dados["Resíduos - Qtde"] = m_qty2.group(1).strip()
                dados["Resíduos - Unidade"] = m_qty2.group(2).strip().upper()
            else:
                dados["Resíduos - Qtde"] = ""
                dados["Resíduos - Unidade"] = ""

    except Exception as e:
        st.error(f"Falha ao ler PDF (parser): {Path(pdf_path).name} — {e}")
        st.caption("Dica: verifique se o PDF possui texto (OCR) e formatação esperada.")
        dados.setdefault("MTR - Número", "N/A")
        for k in ("Gerador - Razão Social","Gerador - CPF/CNPJ","Gerador - Data da emissão","Gerador - Município","Gerador - UF",
                  "Transportador - Razão Social","Transportador - CPF/CNPJ","Transportador - Data do transporte",
                  "Destinador - Razão Social","Destinador - CPF/CNPJ","Destinador - Data do recebimento",
                  "Resíduos - Código IBAMA e Denominação","Resíduos - Qtde","Resíduos - Unidade",
                  "Resíduos - Estado Físico","Resíduos - Classe","Resíduos - Acondicionamento"):
            dados.setdefault(k, "")
    return dados

def extract_and_normalize_mtr(pdf_path:str)->dict:
    d=extract_pdf_data(pdf_path)
    qtd=to_float(d.get("Resíduos - Qtde") or "")
    und=(d.get("Resíduos - Unidade") or "")
    qtd_kg=unidade_to_kg(qtd, und)
    return {
        "numero_mtr": d.get("MTR - Número") or None,
        "gerador_razao": d.get("Gerador - Razão Social") or None,
        "gerador_cnpj": so_digitos(d.get("Gerador - CPF/CNPJ") or ""),
        "gerador_municipio": d.get("Gerador - Município") or None,
        "gerador_uf": d.get("Gerador - UF") or None,
        "gerador_data_emissao": parse_data_br(d.get("Gerador - Data da emissão") or ""),
        "transportador_razao": d.get("Transportador - Razão Social") or None,
        "transportador_cnpj": so_digitos(d.get("Transportador - CPF/CNPJ") or ""),
        "transportador_data_transporte": parse_data_br(d.get("Transportador - Data do transporte") or ""),
        "destinador_razao": d.get("Destinador - Razão Social") or None,
        "destinador_cnpj": so_digitos(d.get("Destinador - CPF/CNPJ") or ""),
        "destinador_data_recebimento": parse_data_br(d.get("Destinador - Data do recebimento") or ""),
        "codigo_ibama_denom": d.get("Resíduos - Código IBAMA e Denominação") or None,
        "estado_fisico": d.get("Resíduos - Estado Físico") or None,
        "classe": d.get("Resíduos - Classe") or None,
        "acondicionamento": d.get("Resíduos - Acondicionamento") or None,
        "qtd_original": d.get("Resíduos - Qtde") or None,
        "und_original": und or None,
        "qtd_kg": qtd_kg,
        "dados_raw": _make_json_safe(d)  # <- garante JSON serializable
    }

# =========================
# AUDITORIA v2 (0–2 ponderado)
# =========================
AREAS = {
    "licenciamento": {"titulo":"Licenciamento e Conformidade Legal","peso":0.30,
        "perguntas":["Licença válida?","Ocorrência de autuações?","Condição e registros de condicionantes?"]},
    "gestao": {"titulo":"Gestão Ambiental","peso":0.25,
        "perguntas":["SGA/ISO 14001 ou equivalente?","Procedimentos escritos (segregação/transporte/destino)?","Indicadores e registros?"]},
    "infraestrutura": {"titulo":"Infraestrutura e Operação","peso":0.20,
        "perguntas":["Armazenamento adequado (coberto/impermeável)?","Plano de contingência?","Manutenção de frota/emissões?"]},
    "seguranca": {"titulo":"Saúde, Segurança e Trabalhadores","peso":0.15,
        "perguntas":["Trabalhadores registrados?","EPIs entregues/usados (evidências)?","Treinamentos periódicos de SSMA?"]},
    "desempenho": {"titulo":"Relacionamento e Desempenho","peso":0.10,
        "perguntas":["Cumpre prazos?","Trata N/C com plano?","Relatórios/MTRs regulares?"]},
}
OPCOES = ["Não atende (0)","Atende parcialmente (1)","Atende plenamente (2)"]

def calcular_score_v2(respostas_v2:dict)->tuple[int,dict]:
    area_pct={}; total=0.0
    for k,meta in AREAS.items():
        vals=[]
        for i in range(1, len(meta["perguntas"])+1):
            v=int(respostas_v2.get(f"{k}.{i}",0)); v=max(0,min(2,v)); vals.append(v)
        media=(mean(vals) if vals else 0.0)
        pct=(media/2.0)*100.0; area_pct[k]=pct
        total += pct*meta["peso"]
    score=int(round(total)); return score, area_pct

def classificar(score:int)->str:
    if score>=80: return "Conforme/Adequado"
    if score>=60: return "Parcialmente Conforme"
    return "Não Conforme/Inadequado"

# =============== CHECKLIST IQA (baseado na planilha) ===============
CHECKLIST_ITEMS = [
    {"chave":"q1_iso","titulo":"A empresa possui sistema de gestão ISO 14001?",
     "opcoes":{"NÃO":0, "EM PROCESSO DE CERTIFICAÇÃO":1, "SIM":2}, "max":2},
    {"chave":"q2_licenca_orgaos","titulo":"A empresa possui licença do órgão ambiental responsável? (Licença Instalação/Operação/polícia federal/CADRI/Outorga)",
     "opcoes":{"NÃO":0, "SÓ PROTOCOLO":1, "SIM":3}, "max":3},
    {"chave":"q3_condicionantes","titulo":"Há evidências de que as restrições/condicionantes da licença estão cumpridas?",
     "opcoes":{"NÃO":0, "PARCIALMENTE":1, "SIM":2}, "max":2},
    {"chave":"q4_autuacoes","titulo":"A empresa sofreu alguma autuação ambiental nos últimos anos?",
     "opcoes":{"SIM":0, "NÃO":2}, "max":2},
    {"chave":"q5_visitas_laudos","titulo":"Há evidências de visitas fiscalizatórias do órgão ambiental? (últimos 3 laudos de inspeção)",
     "opcoes":{"NÃO":0, "SIM":1}, "max":1},
    {"chave":"q6_documentacao_sga","titulo":"Existe estrutura de documentação do sistema (manual, procedimentos, instruções, controles de registros)?",
     "opcoes":{"NÃO":0, "SIM, PORÉM SEM REGISTROS":1, "SIM":2}, "max":2},
    {"chave":"q7_politica_objetivos","titulo":"Possui Política (Qualidade, Meio Ambiente, Segurança) com objetivos e metas?",
     "opcoes":{"NÃO":0, "SIM":1}, "max":1},
    {"chave":"q8_aspectos_controles","titulo":"Levantou aspectos/impactos e controla os significativos?",
     "opcoes":{"NÃO":0, "SIM, PORÉM SEM OS CONTROLES":1, "SIM":2}, "max":2},
    {"chave":"q9_espaco_fisico","titulo":"Espaço físico é suficiente para receber a quantidade de materiais gerados?",
     "opcoes":{"NÃO":0, "SIM":1}, "max":1},
    {"chave":"q10_ete","titulo":"Possui ETE para tratar efluentes líquidos?",
     "opcoes":{"NÃO":0, "SIM":3}, "max":3},
    {"chave":"q11_analises_ete","titulo":"Se ETE existir, realiza análises do efluente tratado?",
     "opcoes":{"NÃO":0, "SIM":2}, "max":2},
    {"chave":"q12_area_coberta","titulo":"Área de armazenamento de resíduos é coberta?",
     "opcoes":{"NÃO":0, "SIM":2}, "max":2},
    {"chave":"q13_area_impermeavel","titulo":"Área de armazenamento de resíduos é impermeabilizada?",
     "opcoes":{"NÃO":0, "SIM":2}, "max":2},
    {"chave":"q14_frota_condicao","titulo":"Caminhões/caçambas em bom estado? Controle de fumaça preta/MOPP?",
     "opcoes":{"NÃO":0, "ALGUNS":1, "TODOS":2}, "max":2},
    {"chave":"q15_ibama","titulo":"Possui licença/registro no IBAMA (CTF/APP)?",
     "opcoes":{"NÃO":0, "PROTOCOLO DE ENTRADA":1, "SIM":2}, "max":2},
    {"chave":"q16_destinacao_correta","titulo":"Destina adequadamente os resíduos sólidos, quando gera?",
     "opcoes":{"NÃO":0, "SIM":2}, "max":2},
    {"chave":"q17_avcb_alvara","titulo":"Possui AVCB e alvará municipal de funcionamento?",
     "opcoes":{"NÃO":0, "SIM":2}, "max":2},
    {"chave":"q18_registros_func","titulo":"Todos os funcionários possuem registros?",
     "opcoes":{"NÃO":0, "SIM":1}, "max":1},
    {"chave":"q19_epi_uniforme","titulo":"Funcionários trabalham uniformizados e com EPIs pertinentes?",
     "opcoes":{"NÃO":0, "SIM":2}, "max":2},
    {"chave":"q20_pontualidade","titulo":"Atende às chamadas para retiradas com pontualidade?",
     "opcoes":{"NÃO":0, "PARCIALMENTE":1, "SIM":2}, "max":2},
    {"chave":"q21_treinamentos_ssma","titulo":"Recebem treinamentos frequentes de saúde/segurança/meio ambiente?",
     "opcoes":{"NÃO":0, "SIM, COM POUCA FREQUÊNCIA":1, "SIM, FREQUENTEMENTE":3}, "max":3},
]

def calcular_iqa(respostas_dict):
    obt, maxp = 0, 0
    for item in CHECKLIST_ITEMS:
        maxp += item["max"]
        val = respostas_dict.get(item["chave"])
        if isinstance(val, int):
            obt += max(0, min(item["max"], val))
    iqa = (obt / maxp * 100.0) if maxp > 0 else 0.0
    return obt, maxp, iqa

def classificar_iqa(iqa_pct):
    if iqa_pct >= 76:
        return {"classe":"Excelente", "condicionamento":"Condicionado", "reavaliacao":"2 anos",
                "acao":"Manter e melhorar o nível alcançado", "status_conformidade":"Conforme"}
    elif iqa_pct >= 51:
        return {"classe":"Bom", "condicionamento":"Condicionado", "reavaliacao":"1 ano",
                "acao":"Eliminar alguns pontos fracos", "status_conformidade":"Conforme"}
    elif iqa_pct >= 21:
        return {"classe":"Regular", "condicionamento":"Desqualificado", "reavaliacao":"6 meses",
                "acao":"Executar melhorias consideráveis", "status_conformidade":"Não conforme"}
    else:
        return {"classe":"Desqualificado", "condicionamento":"Desqualificado", "reavaliacao":"-",
                "acao":"Bloqueio de cadastro", "status_conformidade":"Não conforme"}

# ========================= INICIALIZAÇÃO =========================
run_light_migrations()
seed_users()

if "logado" not in st.session_state:
    st.session_state.logado=False; st.session_state.usuario=None; st.session_state.role=None; st.session_state.site=None
if "sel_forn_id" not in st.session_state:
    st.session_state.sel_forn_id=None

# =========================
#         LOGIN
# =========================
def pagina_login():
    st.title("Sistema de Gerenciamento de Fornecedores - Login")
    with st.form("form_login"):
        usuario = st.text_input("Usuário").strip()
        senha = st.text_input("Senha", type="password").strip()
        enviar = st.form_submit_button("Entrar")
    if enviar:
        with SessionLocal() as db:
            u=get_user_by_username(db, usuario)
            if u and verify_password(senha, u.password_hash):
                st.session_state.logado=True
                st.session_state.usuario=u.username
                st.session_state.role=u.role.value
                st.session_state.site=u.site.value
                st.success(f"Bem-vindo, {u.username}!")
                _safe_rerun()
            else:
                st.error("Usuário ou senha incorretos.")

if not st.session_state.logado:
    pagina_login()
    st.stop()

# =========================
#          MENU
# =========================
if st.session_state.role=="Leitor":
    menu = st.sidebar.selectbox("Menu", ["Overview","Sair"])
else:
    menu = st.sidebar.selectbox(
        "Menu",
        ["Overview","Cadastrar Fornecedor","Visualizar Fornecedores","MTRs","Admin (Usuários)","Sair"]
    )
st.sidebar.title(f"Usuário: {st.session_state.usuario} ({st.session_state.role})")
site_logado = st.session_state.site
acesso_corporativo = site_logado == SiteEnum.LAG.value
st.sidebar.caption(f"Site: {site_logado}")

# =========================
#        KPIs / HELPERS
# =========================
def mtr_query_por_site(db:Session):
    q = db.query(MTR)
    if not acesso_corporativo:
        q = q.filter(MTR.site==site_logado)
    return q

def mtrs_do_fornecedor_query(db:Session, fornecedor_id:int):
    q = db.query(MTR).options(selectinload(MTR.cdfs)).filter(MTR.fornecedor_id==fornecedor_id)
    if not acesso_corporativo:
        q = q.filter(MTR.site==site_logado)
    return q

def documentos_status(docs)->tuple[int,int]:
    hoje=date.today(); limite=hoje+timedelta(days=30)
    vencidos=sum(1 for d in docs if d.data_validade and d.data_validade<hoje)
    a_vencer=sum(1 for d in docs if d.data_validade and hoje<=d.data_validade<=limite)
    return vencidos, a_vencer

def kpis_gerais(db:Session, site:str, acesso_total:bool)->dict:
    total_fornecedores=db.query(Fornecedor).count()
    conformes=db.query(Auditoria).filter(Auditoria.classificado=="Conforme/Adequado").count()
    parcialmente=db.query(Auditoria).filter(Auditoria.classificado=="Parcialmente Conforme").count()
    nao_conformes=db.query(Auditoria).filter(Auditoria.classificado=="Não Conforme/Inadequado").count()
    forn_com_contrato=db.query(Fornecedor).join(Contrato).distinct().count()
    forn_sem_contrato=total_fornecedores - forn_com_contrato
    docs=db.query(Documento).all()
    vencidos,a_vencer=documentos_status(docs)
    mtr_q = db.query(MTR)
    if not acesso_total:
        mtr_q = mtr_q.filter(MTR.site==site)
    mtr_total_kg=float(mtr_q.with_entities(func.coalesce(func.sum(MTR.qtd_kg),0.0)).scalar() or 0.0)

    mtr_por_forn_q=db.query(Fornecedor.nome, func.coalesce(func.sum(MTR.qtd_kg),0.0))        .join(MTR, MTR.fornecedor_id==Fornecedor.id, isouter=False)
    if not acesso_total:
        mtr_por_forn_q = mtr_por_forn_q.filter(MTR.site==site)
    mtr_por_forn=mtr_por_forn_q.group_by(Fornecedor.id).all()

    total_mtrs=int(mtr_q.count())
    mtrs_com_cdf=int(mtr_q.filter(MTR.cdf_count>0).count())
    return {
        "total_fornecedores": total_fornecedores,
        "conformes": conformes, "parcial": parcialmente, "nao_conformes": nao_conformes,
        "forn_com_contrato": forn_com_contrato, "forn_sem_contrato": forn_sem_contrato,
        "docs_vencidos": vencidos, "docs_a_vencer": a_vencer,
        "mtr_total_kg": mtr_total_kg, "mtr_por_forn":[(n,float(v or 0.0)) for n,v in mtr_por_forn],
        "total_mtrs": total_mtrs, "mtrs_com_cdf": mtrs_com_cdf,
    }

# =========================
#           PÁGINAS
# =========================


# ---- Overview ----
if menu=="Overview":
    st.header("📊 Overview — Conformidade & Riscos de Fornecedores")
    # ====== Parâmetros de visão ======
    colp1, colp2, colp3 = st.columns([0.35, 0.35, 0.3])
    with colp1:
        janela_dias = st.slider("Janela de alerta (dias)", 7, 120, 45, help="Período futuro usado para 'a vencer'.")
    with colp2:
        crit_only = st.toggle("Mostrar apenas itens críticos", value=False, help="Filtra as tabelas para focar nos casos urgentes/atrasados.")
    with colp3:
        st.caption(f"Usuário: **{st.session_state.usuario}**  •  Perfil: **{st.session_state.role}**  •  Site: **{site_logado}**")

    hoje = date.today()
    limite = hoje + timedelta(days=janela_dias)

    # ====== KPIs tradicionais (mantidos) ======
    with SessionLocal() as db:
        k = kpis_gerais(db, site_logado, acesso_corporativo)

    fig_total = px.pie(
        names=["Conforme/Adequado","Parcialmente Conforme","Não Conforme/Inadequado"],
        values=[k["conformes"], k["parcial"], k["nao_conformes"]],
        title="Classificação de Auditoria (IQA v2)",
        color=["Conforme/Adequado","Parcialmente Conforme","Não Conforme/Inadequado"],
        color_discrete_map={"Conforme/Adequado":"green","Parcialmente Conforme":"orange","Não Conforme/Inadequado":"red"},
    )
    fig_contrato = px.pie(
        names=["Com Contrato","Sem Contrato"],
        values=[k["forn_com_contrato"], k["forn_sem_contrato"]],
        title="Situação Contratual",
        color=["Com Contrato","Sem Contrato"],
        color_discrete_map={"Com Contrato":"green","Sem Contrato":"red"},
    )
    c1,c2 = st.columns(2)
    with c1: st.plotly_chart(fig_total, use_container_width=True)
    with c2: st.plotly_chart(fig_contrato, use_container_width=True)

    # ====== Coleta de dados para alertas ======
    with SessionLocal() as db:
        # Documentos + Fornecedor
        docs_rows = db.query(Documento, Fornecedor.nome, Fornecedor.id).join(Fornecedor, Documento.fornecedor_id==Fornecedor.id).all()
        # Contratos + Fornecedor
        ctr_rows = db.query(Contrato, Fornecedor.nome, Fornecedor.id).join(Fornecedor, Contrato.fornecedor_id==Fornecedor.id).all()
        # Auditorias (para status geral)
        aud_rows = db.query(Auditoria, Fornecedor.nome, Fornecedor.id).join(Fornecedor, Auditoria.fornecedor_id==Fornecedor.id).all()

    # Documentos
    docs_vencidos = []
    docs_a_vencer = []
    for d, forn_nome, forn_id in docs_rows:
        if d.data_validade:
            if d.data_validade < hoje:
                docs_vencidos.append((forn_id, forn_nome, d))
            elif hoje <= d.data_validade <= limite:
                docs_a_vencer.append((forn_id, forn_nome, d))

    # Contratos
    contratos_vencidos = []
    contratos_a_vencer = []
    for c, forn_nome, forn_id in ctr_rows:
        if c.data_validade:
            if c.data_validade < hoje:
                contratos_vencidos.append((forn_id, forn_nome, c))
            elif hoje <= c.data_validade <= limite:
                contratos_a_vencer.append((forn_id, forn_nome, c))

    # Fornecedores críticos (qualquer documento/contrato vencido)
    forn_docs_venc = {fid for fid, _, _ in docs_vencidos}
    forn_ctr_venc = {fid for fid, _, _ in contratos_vencidos}
    fornecedores_criticos = forn_docs_venc.union(forn_ctr_venc)

    # Fornecedores com atenção (a vencer na janela)
    forn_docs_av = {fid for fid, _, _ in docs_a_vencer}
    forn_ctr_av = {fid for fid, _, _ in contratos_a_vencer}
    fornecedores_atencao = forn_docs_av.union(forn_ctr_av)

    # Auditorias por status (mapa auxiliar)
    aud_status = {}
    for a, forn_nome, forn_id in aud_rows:
        aud_status[forn_id] = a.classificado if a else "N/A"

    # ====== Cartões de risco ======
    def badge(label, val, ok=True):
        color = "#2e7d32" if ok else "#c62828"
        bg = "#e8f5e9" if ok else "#ffebee"
        return f"<div style='padding:12px;border-radius:10px;background:{bg};margin-bottom:10px;'>"\
               f"<span style='color:{color};font-weight:700;'>{label}:</span>"\
               f"<span style='margin-left:8px;color:#111;font-weight:800;'>{val}</span></div>"

    colA, colB, colC, colD = st.columns(4)
    with colA:
        st.markdown(badge("Documentos vencidos", len(docs_vencidos), ok=False), unsafe_allow_html=True)
    with colB:
        st.markdown(badge(f"Docs a vencer (≤{janela_dias}d)", len(docs_a_vencer), ok=False), unsafe_allow_html=True)
    with colC:
        st.markdown(badge("Contratos vencidos", len(contratos_vencidos), ok=False), unsafe_allow_html=True)
    with colD:
        st.markdown(badge(f"Contratos a vencer (≤{janela_dias}d)", len(contratos_a_vencer), ok=False), unsafe_allow_html=True)

    # ====== Gráficos de tendência ======
    # 1) Itens a vencer por semana (docs + contratos)
    if HAVE_PANDAS:
        import pandas as pd
        future_items = []
        for fid, fn, d in docs_a_vencer:
            future_items.append({"Fornecedor": fn, "Tipo": "Documento", "Data": d.data_validade, "Dias": (d.data_validade - hoje).days, "Detalhe": d.tipo})
        for fid, fn, c in contratos_a_vencer:
            future_items.append({"Fornecedor": fn, "Tipo": "Contrato", "Data": c.data_validade, "Dias": (c.data_validade - hoje).days, "Detalhe": "Contrato"})
        df_future = pd.DataFrame(future_items)
        if not df_future.empty:
            df_future["Semana"] = df_future["Data"].apply(lambda x: x.isocalendar()[1])
            grp = df_future.groupby(["Semana","Tipo"]).size().reset_index(name="Qtde")
            if not grp.empty:
                fig_line = px.bar(grp, x="Semana", y="Qtde", color="Tipo", title=f"Itens a vencer por semana (próx. {janela_dias} dias)")
                st.plotly_chart(fig_line, use_container_width=True)
            else:
                st.caption("Sem itens a vencer na janela para exibir por semana.")
    else:
        st.caption("Instale pandas para gráficos de tendência semanais.")

    # 2) Fornecedores com maior número de pendências (vencidos)
    if HAVE_PANDAS:
        import pandas as pd
        pend = []
        for fid, fn, d in docs_vencidos:
            pend.append({"Fornecedor": fn, "Item": "Documento"})
        for fid, fn, c in contratos_vencidos:
            pend.append({"Fornecedor": fn, "Item": "Contrato"})
        df_pend = pd.DataFrame(pend)
        if not df_pend.empty:
            top = df_pend.groupby("Fornecedor").size().reset_index(name="Pendências")
            if not top.empty and "Pendências" in top.columns:
                top = top.sort_values("Pendências", ascending=False).head(10)
            fig_top = px.bar(top, x="Fornecedor", y="Pendências", title="TOP fornecedores com pendências vencidas")
            st.plotly_chart(fig_top, use_container_width=True)

    # ====== Tabelas operacionais ======
    def _table_docs(rows, titulo, critico=False):
        st.markdown(f"### {titulo}")
        if not rows:
            st.info("Nenhum registro.")
            return
        data = []
        for fid, fn, d in rows:
            dias = (d.data_validade - hoje).days if d.data_validade else None
            data.append({
                "Fornecedor": fn,
                "Tipo Documento": d.tipo,
                "Início": d.data_inicio,
                "Validade": d.data_validade,
                "Dias para vencer": dias,
                "Arquivo": Path(d.arquivo).name if d.arquivo else "-"
            })
        if HAVE_PANDAS:
            import pandas as pd
            df = pd.DataFrame(data)
            if not df.empty:
                sort_cols = [c for c in ["Dias para vencer","Fornecedor"] if c in df.columns]
                if sort_cols:
                    df = df.sort_values(sort_cols, na_position="last")
            if crit_only:
                df = df[df["Dias para vencer"].fillna(-999) <= 7] if not critico else df
            st.dataframe(df, use_container_width=True, hide_index=True)
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button(f"Baixar CSV — {titulo}", data=csv, file_name=f"{titulo.replace(' ','_')}.csv", mime="text/csv", use_container_width=True)
        else:
            for r in data[:200]:
                st.write(r)

    def _table_contratos(rows, titulo, critico=False):
        st.markdown(f"### {titulo}")
        if not rows:
            st.info("Nenhum registro.")
            return
        data = []
        for fid, fn, c in rows:
            dias = (c.data_validade - hoje).days if c.data_validade else None
            data.append({
                "Fornecedor": fn,
                "Assinatura": c.data_assinatura,
                "Validade": c.data_validade,
                "Dias para vencer": dias,
                "Arquivo": Path(c.arquivo).name if c.arquivo else "-"
            })
        if HAVE_PANDAS:
            import pandas as pd
            df = pd.DataFrame(data)
            if not df.empty:
                sort_cols = [c for c in ["Dias para vencer","Fornecedor"] if c in df.columns]
                if sort_cols:
                    df = df.sort_values(sort_cols, na_position="last")
            if crit_only:
                df = df[df["Dias para vencer"].fillna(-999) <= 7] if not critico else df
            st.dataframe(df, use_container_width=True, hide_index=True)
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button(f"Baixar CSV — {titulo}", data=csv, file_name=f"{titulo.replace(' ','_')}.csv", mime="text/csv", use_container_width=True)
        else:
            for r in data[:200]:
                st.write(r)

    # Abas com foco operacional
    t1, t2, t3, t4, t5 = st.tabs([
        "📄 Docs vencidos",
        f"⏳ Docs a vencer (≤{janela_dias}d)",
        "📃 Contratos vencidos",
        f"🗓️ Contratos a vencer (≤{janela_dias}d)",
        "🚨 Fornecedores que exigem notificação"
    ])

    with t1:
        _table_docs(docs_vencidos, "Documentos vencidos", critico=True)

    with t2:
        _table_docs(docs_a_vencer, f"Documentos a vencer (≤{janela_dias} dias)")

    with t3:
        _table_contratos(contratos_vencidos, "Contratos vencidos", critico=True)

    with t4:
        _table_contratos(contratos_a_vencer, f"Contratos a vencer (≤{janela_dias} dias)")

    with t5:
        # Regra simples: doc vencido OU contrato vencido => notificar imediatamente
        # A vencer (≤janela) => programar notificação preventiva
        coln1, coln2 = st.columns(2)
        with coln1:
            st.subheader("Notificação imediata (vencidos)")
            lista_crit = []
            for fid in sorted(fornecedores_criticos):
                # Buscar nome na primeira ocorrência
                nome = next((fn for (idc, fn, _) in docs_vencidos if idc==fid), None) \
                    or next((fn for (idc, fn, _) in contratos_vencidos if idc==fid), None) \
                    or f"Fornecedor #{fid}"
                lista_crit.append({"Fornecedor": nome, "Status Auditoria": aud_status.get(fid, "N/A")})
            if HAVE_PANDAS:
                import pandas as pd
                dfc = pd.DataFrame(lista_crit)
                if not dfc.empty and "Fornecedor" in dfc.columns:
                    dfc = dfc.sort_values("Fornecedor")
                else:
                    st.info("Nenhum fornecedor para notificação imediata.")
                    dfc = pd.DataFrame(columns=["Fornecedor","Status Auditoria"])
                st.dataframe(dfc, use_container_width=True, hide_index=True)
                csv = dfc.to_csv(index=False).encode("utf-8")
                st.download_button("Baixar CSV — Notificação imediata", data=csv, file_name="fornecedores_notificar_imediato.csv", mime="text/csv", use_container_width=True)
            else:
                for r in lista_crit[:200]:
                    st.write(r)

        with coln2:
            st.subheader(f"Notificação preventiva (≤{janela_dias}d)")
            lista_prev = []
            for fid in sorted(fornecedores_atencao - fornecedores_criticos):
                nome = next((fn for (idc, fn, _) in docs_a_vencer if idc==fid), None) \
                    or next((fn for (idc, fn, _) in contratos_a_vencer if idc==fid), None) \
                    or f"Fornecedor #{fid}"
                lista_prev.append({"Fornecedor": nome, "Status Auditoria": aud_status.get(fid, "N/A")})
            if HAVE_PANDAS:
                import pandas as pd
                dfp = pd.DataFrame(lista_prev)
                if not dfp.empty and "Fornecedor" in dfp.columns:
                    dfp = dfp.sort_values("Fornecedor")
                else:
                    st.info("Nenhum fornecedor para notificação preventiva.")
                    dfp = pd.DataFrame(columns=["Fornecedor","Status Auditoria"])
                st.dataframe(dfp, use_container_width=True, hide_index=True)
                csv = dfp.to_csv(index=False).encode("utf-8")
                st.download_button("Baixar CSV — Notificação preventiva", data=csv, file_name="fornecedores_notificar_preventivo.csv", mime="text/csv", use_container_width=True)
            else:
                for r in lista_prev[:200]:
                    st.write(r)

    st.markdown("---")
    # ====== Visões ambientais (mantidas/ajustadas) ======
    # kg por fornecedor (MTR)
    st.markdown("### ♻️ Kg destinados por fornecedor (MTR)")
    rows = [{"Fornecedor": n, "Kg_destinados": v} for n, v in k.get("mtr_por_forn", [])]
    if rows:
        if HAVE_PANDAS:
            import pandas as pd
            df = pd.DataFrame(rows)
            if not df.empty and "Kg_destinados" in df.columns:
                df = df.sort_values("Kg_destinados", ascending=False)
            fig_bar = px.bar(df, x="Fornecedor", y="Kg_destinados", title="Total de kg por fornecedor (MTR)")
        else:
            xs = [r["Fornecedor"] for r in rows]; ys = [r["Kg_destinados"] for r in rows]
            fig_bar = go.Figure(go.Bar(x=xs, y=ys)); fig_bar.update_layout(title="Total de kg por fornecedor (MTR)")
        fig_bar.update_traces(marker_color="green")
        st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.info("Sem dados de MTR por fornecedor para exibir.")






# ---- Cadastrar Fornecedor ----
if menu=="Cadastrar Fornecedor":
    if st.session_state.role not in ("Admin","Auditor"):
        st.error("Você não tem permissão para cadastrar fornecedores."); st.stop()
    st.header("Cadastrar novo fornecedor")
    with st.form("form_cadastro"):
        nome=st.text_input("Nome do fornecedor")
        cpf_cnpj=st.text_input("CPF ou CNPJ")
        endereco=st.text_area("Endereço")
        telefone=st.text_input("Telefone")
        enviar=st.form_submit_button("Cadastrar")
    if enviar:
        if not nome or not cpf_cnpj: st.error("Nome e CPF/CNPJ são obrigatórios."); st.stop()
        if not validar_cpf_cnpj(cpf_cnpj): st.error("CPF/CNPJ inválido."); st.stop()
        with SessionLocal() as db:
            dig=so_digitos(cpf_cnpj)
            existe=db.query(Fornecedor).filter_by(cpf_cnpj=dig).first()
            if existe: st.warning("Fornecedor já cadastrado.")
            else:
                f=Fornecedor(nome=nome.strip(), cpf_cnpj=dig, endereco=endereco.strip() if endereco else None,
                             telefone=normalizar_telefone(telefone), updated_by=st.session_state.usuario)
                db.add(f); db.commit()
                st.success(f"Fornecedor '{f.nome}' cadastrado com sucesso!")

# ---- Visualizar Fornecedores ----
if menu=="Visualizar Fornecedores":
    if st.session_state.role not in ("Admin","Auditor"):
        st.error("Acesso restrito. Seu perfil é Leitor e possui acesso apenas ao Overview."); st.stop()
    st.header("Fornecedores")
    termo=st.text_input("Buscar por nome", key="busca_forn")
    with SessionLocal() as db:
        fornecedores=db.query(Fornecedor).options(
            joinedload(Fornecedor.documentos),
            joinedload(Fornecedor.auditoria),
            joinedload(Fornecedor.planos_acao),
            joinedload(Fornecedor.contratos),
            joinedload(Fornecedor.mtrs).joinedload(MTR.cdfs)
        )
        if termo: fornecedores=fornecedores.filter(Fornecedor.nome.ilike(f"%{termo.strip()}%"))
        fornecedores=fornecedores.order_by(Fornecedor.nome.asc()).all()
    if not fornecedores: st.info("Nenhum fornecedor encontrado."); st.stop()

    col_left, col_right = st.columns([0.35,0.65])
    with col_left:
        st.subheader("Lista")
        for f in fornecedores:
            is_selected=(st.session_state.sel_forn_id==f.id)
            style = "background:#e8f5e9;border:1px solid #2e7d32;" if is_selected else "background:#f6f6f6;border:1px solid #ddd;"
            if st.button(f"📁 {f.nome} — {formatar_cpf_cnpj(f.cpf_cnpj)}", key=f"btn_f_{f.id}"):
                st.session_state.sel_forn_id=f.id
            st.markdown(f"<div style='height:6px;{style}'></div>", unsafe_allow_html=True)

    with col_right:
        sel = next((f for f in fornecedores if f.id==st.session_state.sel_forn_id), None)
        if sel is None: st.info("Selecione um fornecedor na lista ao lado para visualizar/editar.")
        else:
            st.subheader(f"Detalhes — {sel.nome}")
            tabs=st.tabs(["Informações","Documentos","Auditoria","Planos de Ação","Contratos","MTRs"])

            # Informações
            with tabs[0]:
                st.write(f"**CPF/CNPJ:** {formatar_cpf_cnpj(sel.cpf_cnpj)}")
                st.write(f"**Endereço:** {sel.endereco or '-'}")
                st.write(f"**Telefone:** {sel.telefone or '-' }")

            # Documentos
            with tabs[1]:
                st.markdown("#### Documentos do fornecedor")
                if not sel.documentos:
                    st.info("Nenhum documento. Use o bloco 'Adicionar novo documento' abaixo.")
                for d in sel.documentos:
                    with st.container(border=True):
                        st.write(f"**Tipo:** {d.tipo}")
                        # botão para baixar o arquivo atual
                        try:
                            if d.arquivo and Path(d.arquivo).exists():
                                with open(d.arquivo,"rb") as f: data_atual=f.read()
                                st.download_button("Baixar arquivo atual", data=data_atual,
                                                   file_name=os.path.basename(d.arquivo), key=f"doc_dl_{d.id}")
                            else:
                                st.caption("Nenhum arquivo atual encontrado para este documento.")
                        except Exception:
                            st.warning("Não foi possível preparar o download do arquivo atual.")

                        c1,c2,c3=st.columns([0.4,0.3,0.3])
                        with c1:
                            up=st.file_uploader("Substituir arquivo (opcional)", type=["pdf","jpg","png","jpeg"], key=f"doc_up_{d.id}")
                        with c2:
                            dt_ini=st.date_input("Início", value=d.data_inicio, key=f"doc_ini_{d.id}")
                        with c3:
                            dt_val=st.date_input("Validade", value=d.data_validade, key=f"doc_val_{d.id}")
                        if st.button("Salvar alterações", key=f"doc_save_{d.id}"):
                            if dt_val<dt_ini: st.error("Validade não pode ser anterior ao início.")
                            else:
                                caminho=d.arquivo
                                if up is not None:
                                    caminho=salvar_arquivo(up, "uploads/documentos", f"{sel.id}_{d.tipo}")
                                with SessionLocal() as db:
                                    doc_db=db.query(Documento).filter(Documento.id==d.id).first()
                                    doc_db.arquivo=caminho; doc_db.data_inicio=dt_ini; doc_db.data_validade=dt_val
                                    doc_db.updated_by=st.session_state.usuario
                                    db.commit(); st.success("Documento atualizado com sucesso!"); _safe_rerun()

                st.markdown("#### Adicionar novo documento")
                tipos_documentos = [
                    "Licença Ambiental de Operação",
                    "Consulta de Área Contaminada",
                    "Alvará de Funcionamento",
                    "Comprovante de regularidade (CETESB ou órgão estadual)",
                    "Condicionantes ambientais vigentes",
                    "AVCB (Auto de Vistoria do Corpo de Bombeiros)",
                    "CTF - IBAMA"
                ]
                c1,c2,c3,c4=st.columns([0.35,0.25,0.2,0.2])
                with c1: novo_tipo=st.selectbox("Tipo", tipos_documentos, key="novo_tipo")
                with c2: novo_ini=st.date_input("Início", value=date.today(), key="novo_ini")
                with c3: novo_val=st.date_input("Validade", value=date.today(), key="novo_val")
                with c4: novo_up=st.file_uploader("Arquivo", type=["pdf","jpg","png","jpeg"], key="novo_arq")
                if st.button("Adicionar documento", key="btn_add_doc"):
                    if novo_up is None: st.error("Envie um arquivo.")
                    elif novo_val<novo_ini: st.error("Validade não pode ser anterior ao início.")
                    else:
                        caminho=salvar_arquivo(novo_up, "uploads/documentos", f"{sel.id}_{novo_tipo}")
                        with SessionLocal() as db:
                            try:
                                d=Documento(fornecedor_id=sel.id, tipo=novo_tipo, arquivo=caminho,
                                            data_inicio=novo_ini, data_validade=novo_val,
                                            updated_by=st.session_state.usuario)
                                db.add(d); db.commit(); st.success("Documento adicionado com sucesso!"); _safe_rerun()
                            except Exception as e:
                                db.rollback(); st.error(f"Erro ao salvar documento: {e}")

            # Auditoria
            with tabs[2]:
                st.subheader("Auditoria — Checklist IQA")
                respostas_form = {}
                aud_exist = sel.auditoria
                prev = {}
                anexos_prev = []
                if aud_exist and isinstance(aud_exist.respostas, dict):
                    prev = aud_exist.respostas.get("checklist_respostas", {}) or {}
                    anexos_prev = aud_exist.respostas.get("anexos", []) or []

                for it in CHECKLIST_ITEMS:
                    opcoes = list(it["opcoes"].keys())
                    valores = list(it["opcoes"].values())
                    default_val = prev.get(it["chave"], None)
                    try:
                        idx = valores.index(default_val)
                    except ValueError:
                        idx = 0
                    escolha = st.radio(
                        it["titulo"],
                        options=opcoes,
                        index=idx,
                        key=f"aud_{sel.id}_{it['chave']}",
                        horizontal=True
                    )
                    respostas_form[it["chave"]] = it["opcoes"][escolha]

                st.markdown("#### Anexar documento da auditoria (opcional)")
                up_aud = st.file_uploader("Relatório/Check-list (PDF/JPG/PNG)", type=["pdf","jpg","jpeg","png"], key=f"aud_up_{sel.id}")

                if st.button("Salvar Auditoria (calcular IQA)", key=f"save_aud_{sel.id}"):
                    obt, maxp, iqa = calcular_iqa(respostas_form)
                    regra = classificar_iqa(iqa)
                    anexos = list(anexos_prev)
                    if up_aud is not None:
                        p_arquivo = salvar_arquivo(up_aud, "uploads/auditorias", f"{sel.id}_auditoria")
                        anexos.append(p_arquivo)

                    payload = {
                        "modelo": "checklist_iqa_v1",
                        "checklist_respostas": respostas_form,
                        "pontos_obtidos": obt,
                        "pontos_max": maxp,
                        "iqa_pct": iqa,
                        "regra_aplicada": regra,
                        "anexos": anexos,
                    }

                    with SessionLocal() as db:
                        a = db.query(Auditoria).filter_by(fornecedor_id=sel.id).first()
                        if not a:
                            a = Auditoria(fornecedor_id=sel.id)
                            db.add(a)
                        a.respostas = payload
                        a.score = int(round(iqa))
                        a.classificado = "Conforme/Adequado" if regra["status_conformidade"] == "Conforme" else "Não Conforme/Inadequado"
                        a.updated_by = st.session_state.usuario
                        db.commit()
                    st.success(f"IQA: {iqa:.1f}% — {regra['classe']} | Reavaliação: {regra['reavaliacao']} | Ação: {regra['acao']}")
                    _safe_rerun()

                with SessionLocal() as db:
                    show = db.query(Auditoria).filter_by(fornecedor_id=sel.id).first()

                if show and isinstance(show.respostas, dict) and show.respostas.get("modelo") == "checklist_iqa_v1":
                    r = show.respostas
                    st.markdown(
                        f"**IQA:** {r.get('iqa_pct',0):.1f}% — **Classe:** {r.get('regra_aplicada',{}).get('classe','-')} | "
                        f"**Condição:** {r.get('regra_aplicada',{}).get('condicionamento','-')} | "
                        f"**Reavaliação:** {r.get('regra_aplicada',{}).get('reavaliacao','-')}"
                    )
                    if r.get("anexos"):
                        st.markdown("**Anexos da auditoria:**")
                        for path in r["anexos"]:
                            exibir_preview_arquivo(path, None)

            # Planos de Ação
            with tabs[3]:
                st.subheader("Planos de Ação")
                with st.form(f"form_plano_{sel.id}"):
                    descricao = st.text_area("Descrição da Ação")
                    data_inicio = st.date_input("Início", value=date.today())
                    data_fim = st.date_input("Fim", value=date.today())
                    status = st.selectbox("Status", [PlanoStatusEnum.andamento.value, PlanoStatusEnum.concluido.value, PlanoStatusEnum.atrasado.value])
                    ev_upload = st.file_uploader("Anexar evidência (opcional)", type=["pdf","jpg","png","jpeg"])
                    enviar = st.form_submit_button("Adicionar Plano de Ação")

                evidencias = []
                if enviar:
                    if not descricao:
                        st.error("Descreva a ação.")
                    elif data_fim < data_inicio:
                        st.error("Data final deve ser maior ou igual à data inicial.")
                    else:
                        if ev_upload is not None:
                            ev_path = salvar_arquivo(ev_upload, "uploads/evidencias", f"{sel.id}_plano")
                            evidencias.append(ev_path)
                        with SessionLocal() as db:
                            plano = PlanoAcao(fornecedor_id=sel.id, descricao=descricao.strip(),
                                              data_inicio=data_inicio, data_fim=data_fim, status=PlanoStatusEnum(status),
                                              evidencias=evidencias or [], updated_by=st.session_state.usuario)
                            db.add(plano); db.commit(); st.success("Plano de ação adicionado."); _safe_rerun()

                st.markdown("#### Ações cadastradas")
                if not sel.planos_acao:
                    st.info("Nenhuma ação cadastrada.")
                else:
                    hoje = date.today()
                    for p in sorted(sel.planos_acao, key=lambda x: x.data_fim):
                        atrasado = (p.data_fim and p.data_fim < hoje and (getattr(p.status, "value", p.status) != PlanoStatusEnum.concluido.value))
                        with st.container(border=True):
                            st.write(f"- {p.descricao} | {getattr(p.status, 'value', p.status)} | {p.data_inicio or '-'} → {p.data_fim or '-' }")
                            if p.evidencias:
                                for ev in p.evidencias:
                                    if Path(ev).exists():
                                        exibir_preview_arquivo(ev, None)

            # Contratos
            with tabs[4]:
                st.subheader("Contratos")
                arquivo_contrato = st.file_uploader("Anexar Contrato", type=["pdf","docx","doc","pdf"], key=f"contr_{sel.id}")
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
                            novo = Contrato(fornecedor_id=sel.id, arquivo=caminho,
                                            data_assinatura=data_assinatura, data_validade=data_validade,
                                            updated_by=st.session_state.usuario)
                            db.add(novo); db.commit()
                        st.success("Contrato salvo!")
                        _safe_rerun()

                st.markdown("#### Contratos cadastrados")
                if sel.contratos:
                    for c in sel.contratos:
                        st.write(f"- Ass.: {c.data_assinatura or '-'} | Val.: {c.data_validade or '-'}")
                        if c.arquivo:
                            try:
                                exibir_preview_arquivo(c.arquivo, None)
                            except Exception:
                                pass
                else:
                    st.info("Nenhum contrato anexado.")

            # MTRs do fornecedor
            with tabs[5]:
                st.subheader("MTRs do fornecedor")
                with SessionLocal() as db:
                    mtrs_visiveis = mtrs_do_fornecedor_query(db, sel.id).order_by(MTR.id.desc()).all()
                total_kg = sum(m.qtd_kg or 0.0 for m in mtrs_visiveis)
                st.write(f"**Total destinado (kg):** {total_kg:.1f}")
                for m in mtrs_visiveis:
                    with st.container(border=True):
                        st.write(f"**MTR nº**: {m.numero_mtr or '-'} | **Site:** {m.site.value if m.site else '-'} | **Receb.:** {m.destinador_data_recebimento or '-'} | **kg:** {m.qtd_kg or 0.0:.1f}")

                        st.markdown("**CDF(s):**")
                        if m.cdfs:
                            for cdf in m.cdfs:
                                with st.container():
                                    st.write(f"- Emissão: {cdf.data_emissao or '-'} | Obs: {cdf.observacao or '-'}")
                                    if Path(cdf.arquivo).exists(): exibir_preview_arquivo(cdf.arquivo, None)
                        up_cdf = st.file_uploader("Anexar CDF (PDF/JPG/PNG)", type=["pdf","jpg","jpeg","png"], key=f"cdf_up_{m.id}")
                        cdf_data = st.date_input("Data de emissão do CDF", value=date.today(), key=f"cdf_dt_{m.id}")
                        cdf_obs = st.text_input("Observação (opcional)", key=f"cdf_obs_{m.id}")
                        if st.button("Adicionar CDF", key=f"cdf_add_{m.id}"):
                            if not up_cdf: st.error("Envie um arquivo de CDF.")
                            else:
                                caminho = salvar_arquivo(up_cdf, "uploads/cdfs", f"{m.id}_cdf")
                                with SessionLocal() as db:
                                    novo = CDF(mtr_id=m.id, arquivo=caminho, data_emissao=cdf_data,
                                               observacao=cdf_obs.strip() or None, updated_by=st.session_state.usuario)
                                    db.add(novo)
                                    mm=mtr_query_por_site(db).filter(MTR.id==m.id).first()
                                    if not mm:
                                        st.error("MTR não encontrada para o seu site.")
                                        st.stop()
                                    mm.cdf_count=(mm.cdf_count or 0)+1
                                    db.commit(); st.success("CDF anexado com sucesso!"); _safe_rerun()

# ---- Página MTRs (importação com revisão e confirmação) ----
if menu=="MTRs":
    if st.session_state.role not in ("Admin","Auditor"):
        st.error("Acesso restrito."); st.stop()
    st.header("Controle de MTRs por Fornecedor")

    if "mtr_pending" not in st.session_state:
        st.session_state.mtr_pending = []
    if "mtr_action" not in st.session_state:
        st.session_state.mtr_action = "cadastro"

    with SessionLocal() as db:
        fornecedores=db.query(Fornecedor).order_by(Fornecedor.nome.asc()).all()
        mtrs_all=mtr_query_por_site(db).options(joinedload(MTR.fornecedor), selectinload(MTR.cdfs)).order_by(MTR.id.desc()).all()

    if not fornecedores:
        st.info("Cadastre fornecedores antes de gerenciar MTRs.")
        st.stop()

    st.markdown("### Lista geral de MTRs cadastradas")
    if not mtrs_all:
        st.info("Nenhuma MTR cadastrada ainda.")
    else:
        head = st.columns([1.0, 1.1, 0.6, 0.8, 0.8, 0.6, 0.3])
        head[0].markdown("**MTR nº**")
        head[1].markdown("**Fornecedor**")
        head[2].markdown("**Site**")
        head[3].markdown("**Recebimento**")
        head[4].markdown("**Status CDF**")
        head[5].markdown("**CDF(s)**")
        head[6].markdown("**Doc**")

        for m in mtrs_all:
            cols = st.columns([1.0, 1.1, 0.6, 0.8, 0.8, 0.6, 0.3])
            cols[0].write(m.numero_mtr or "-")
            cols[1].write(m.fornecedor.nome if m.fornecedor else "-")
            cols[2].write(m.site.value if m.site else "-")
            cols[3].write(str(m.destinador_data_recebimento or "-"))
            cols[4].write("Com CDF" if (m.cdf_count or 0) > 0 else "Sem CDF")
            cols[5].write(m.cdf_count or 0)
            if cols[6].button("📎", key=f"view_mtr_{m.id}", help="Visualizar documento da MTR"):
                st.session_state.mtr_doc_view_id = m.id

        mtr_doc_view_id = st.session_state.get("mtr_doc_view_id")
        if mtr_doc_view_id:
            selected = next((x for x in mtrs_all if x.id == mtr_doc_view_id), None)
            if selected:
                st.markdown(f"**Documento da MTR {selected.numero_mtr or '-'}**")
                exibir_preview_arquivo(selected.arquivo, None)

    st.markdown("### Ações")
    c1, c2, c3 = st.columns(3)
    if c1.button("Cadastrar MTR", use_container_width=True):
        st.session_state.mtr_action = "cadastro"
    if c2.button("Adicionar CDF", use_container_width=True):
        st.session_state.mtr_action = "cdf"
    if c3.button("Editar MTR e CDF", use_container_width=True):
        st.session_state.mtr_action = "edicao"

    forn_map={f"{f.nome} — {formatar_cpf_cnpj(f.cpf_cnpj)}":f.id for f in fornecedores}

    if st.session_state.mtr_action == "cadastro":
        st.markdown("### Cadastro de MTR (metodologia atual)")
        if not HAVE_PDFPLUMBER:
            st.error("pdfplumber não está instalado. Adicione ao requirements.")
            st.stop()

        forn_label=st.selectbox("Associar MTRs ao fornecedor", list(forn_map.keys()), key="forn_cad_mtr")
        fornecedor_id=forn_map[forn_label]

        if acesso_corporativo:
            site_gerador = st.selectbox("Site gerador do resíduo", SITES_PRODUTIVOS, key="site_gerador_mtr")
        else:
            site_gerador = site_logado
            st.caption(f"Site gerador fixado pelo seu acesso: **{site_gerador}**")

        uploads=st.file_uploader("Enviar PDFs de MTR", type=["pdf"], accept_multiple_files=True, key="up_mtr_cad")
        if uploads and st.button("Processar MTRs"):
            pendentes=[]
            for up in uploads:
                try:
                    caminho=salvar_arquivo(up, "uploads/mtrs", f"{fornecedor_id}_mtr")
                    dados=extract_and_normalize_mtr(caminho)
                    pendentes.append({
                        "arquivo": caminho,
                        "arquivo_nome": up.name,
                        "fornecedor_id": fornecedor_id,
                        "numero_mtr": dados.get("numero_mtr") or "",
                        "gerador_razao": dados.get("gerador_razao") or "",
                        "gerador_cnpj": dados.get("gerador_cnpj") or "",
                        "gerador_municipio": dados.get("gerador_municipio") or "",
                        "gerador_uf": dados.get("gerador_uf") or "",
                        "gerador_data_emissao": (dados.get("gerador_data_emissao").isoformat() if dados.get("gerador_data_emissao") else ""),
                        "transportador_razao": dados.get("transportador_razao") or "",
                        "transportador_cnpj": dados.get("transportador_cnpj") or "",
                        "transportador_data_transporte": (dados.get("transportador_data_transporte").isoformat() if dados.get("transportador_data_transporte") else ""),
                        "destinador_razao": dados.get("destinador_razao") or "",
                        "destinador_cnpj": dados.get("destinador_cnpj") or "",
                        "destinador_data_recebimento": (dados.get("destinador_data_recebimento").isoformat() if dados.get("destinador_data_recebimento") else ""),
                        "codigo_ibama_denom": dados.get("codigo_ibama_denom") or "",
                        "estado_fisico": dados.get("estado_fisico") or "",
                        "classe": dados.get("classe") or "",
                        "acondicionamento": dados.get("acondicionamento") or "",
                        "qtd_original": dados.get("qtd_original") or "",
                        "und_original": dados.get("und_original") or "",
                        "qtd_kg": float(dados.get("qtd_kg") or 0.0),
                        "dados_raw": _make_json_safe(dados),
                        "_idx": len(pendentes),
                    })
                except Exception as e:
                    st.error(f"Erro ao processar {up.name}: {e}")
            st.session_state.mtr_pending = pendentes

        if st.session_state.mtr_pending:
            st.markdown("#### Revisar dados processados antes de salvar")
            if HAVE_PANDAS:
                import pandas as pd
                df_preview = pd.DataFrame(st.session_state.mtr_pending)
                cols = [
                    "arquivo_nome","numero_mtr","gerador_razao","gerador_cnpj","gerador_municipio","gerador_uf",
                    "gerador_data_emissao","transportador_razao","transportador_cnpj","transportador_data_transporte",
                    "destinador_razao","destinador_cnpj","destinador_data_recebimento","codigo_ibama_denom",
                    "estado_fisico","classe","acondicionamento","qtd_original","und_original","qtd_kg"
                ]
                edited = st.data_editor(df_preview[["_idx"] + cols], use_container_width=True, num_rows="dynamic", key="mtr_preview_editor")
                cprev1, cprev2 = st.columns(2)
                with cprev1:
                    if st.button("Confirmar e salvar MTRs"):
                        ok, fail = 0, 0
                        for _, r in edited.iterrows():
                            try:
                                original = next((x for x in st.session_state.mtr_pending if x.get("_idx") == int(r.get("_idx", -1))), None)
                                if not original:
                                    fail += 1
                                    continue
                                with SessionLocal() as db:
                                    m=MTR(
                                        fornecedor_id=int(r.get("fornecedor_id") or original.get("fornecedor_id")),
                                        arquivo=original.get("arquivo"),
                                        numero_mtr=str(r.get("numero_mtr") or "").strip() or None,
                                        gerador_razao=str(r.get("gerador_razao") or "").strip() or None,
                                        gerador_cnpj=str(r.get("gerador_cnpj") or "").strip() or None,
                                        gerador_municipio=str(r.get("gerador_municipio") or "").strip() or None,
                                        gerador_uf=str(r.get("gerador_uf") or "").strip() or None,
                                        gerador_data_emissao=parse_data_flex(str(r.get("gerador_data_emissao") or "")),
                                        transportador_razao=str(r.get("transportador_razao") or "").strip() or None,
                                        transportador_cnpj=str(r.get("transportador_cnpj") or "").strip() or None,
                                        transportador_data_transporte=parse_data_flex(str(r.get("transportador_data_transporte") or "")),
                                        destinador_razao=str(r.get("destinador_razao") or "").strip() or None,
                                        destinador_cnpj=str(r.get("destinador_cnpj") or "").strip() or None,
                                        destinador_data_recebimento=parse_data_flex(str(r.get("destinador_data_recebimento") or "")),
                                        codigo_ibama_denom=str(r.get("codigo_ibama_denom") or "").strip() or None,
                                        estado_fisico=str(r.get("estado_fisico") or "").strip() or None,
                                        classe=str(r.get("classe") or "").strip() or None,
                                        acondicionamento=str(r.get("acondicionamento") or "").strip() or None,
                                        qtd_original=str(r.get("qtd_original") or "").strip() or None,
                                        und_original=str(r.get("und_original") or "").strip() or None,
                                        qtd_kg=float(r.get("qtd_kg") or 0.0),
                                        dados_raw=_make_json_safe(original.get("dados_raw") or {}),
                                        site=SiteEnum(site_gerador),
                                        updated_by=st.session_state.usuario
                                    )
                                    db.add(m); db.commit(); ok += 1
                            except Exception:
                                fail += 1
                        st.success(f"Processo finalizado. Sucesso: {ok} | Falhas: {fail}")
                        st.session_state.mtr_pending = []
                        _safe_rerun()
                with cprev2:
                    if st.button("Cancelar revisão"):
                        st.session_state.mtr_pending = []
                        _safe_rerun()
            else:
                st.warning("Instale pandas para revisar/editar os dados processados antes de confirmar.")

    elif st.session_state.mtr_action == "cdf":
        st.markdown("### Adicionar CDF em MTR já cadastrada")
        forn_label=st.selectbox("Fornecedor", list(forn_map.keys()), key="forn_add_cdf")
        fornecedor_id=forn_map[forn_label]
        with SessionLocal() as db:
            mtrs = mtrs_do_fornecedor_query(db, fornecedor_id).order_by(MTR.id.desc()).all()

        if not mtrs:
            st.info("Nenhuma MTR cadastrada para este fornecedor.")
        else:
            lista = [f"{m.id} - MTR {m.numero_mtr or '-'} | CDF(s): {m.cdf_count or 0}" for m in mtrs]
            escolha = st.selectbox("Selecione a MTR", lista, key=f"sel_mtr_cdf_{fornecedor_id}")
            mid = int(escolha.split(" - ")[0])
            m = next(mm for mm in mtrs if mm.id == mid)

            if m.cdfs:
                st.markdown("#### CDF(s) já vinculados")
                for cdf in m.cdfs:
                    st.write(f"- #{cdf.id} | Emissão: {cdf.data_emissao or '-'} | Obs: {cdf.observacao or '-'}")

            up_cdf = st.file_uploader("Anexar CDF (PDF/JPG/PNG)", type=["pdf","jpg","jpeg","png"], key=f"cdf_up_batch_{mid}")
            cdf_data = st.date_input("Data de emissão do CDF", value=date.today(), key=f"cdf_dt_batch_{mid}")
            cdf_obs = st.text_input("Observação (opcional)", key=f"cdf_obs_batch_{mid}")
            if st.button("Salvar CDF nesta MTR", key=f"cdf_add_batch_{mid}"):
                if not up_cdf:
                    st.error("Envie um arquivo de CDF.")
                else:
                    caminho = salvar_arquivo(up_cdf, "uploads/cdfs", f"{mid}_cdf")
                    with SessionLocal() as db:
                        novo = CDF(mtr_id=mid, arquivo=caminho, data_emissao=cdf_data,
                                   observacao=cdf_obs.strip() or None, updated_by=st.session_state.usuario)
                        db.add(novo)
                        mm = mtr_query_por_site(db).filter(MTR.id==mid).first()
                        if not mm:
                            st.error("MTR não encontrada para o seu site.")
                            st.stop()
                        mm.cdf_count = (mm.cdf_count or 0) + 1
                        db.commit()
                    st.success("CDF anexado com sucesso!")
                    _safe_rerun()

    else:
        st.markdown("### Editar MTR e CDF")
        forn_label=st.selectbox("Fornecedor", list(forn_map.keys()), key="forn_edit_mtr")
        fornecedor_id=forn_map[forn_label]
        with SessionLocal() as db:
            mtrs = mtrs_do_fornecedor_query(db, fornecedor_id).order_by(MTR.id.desc()).all()

        if not mtrs:
            st.info("Nenhuma MTR cadastrada para este fornecedor.")
        else:
            lista = [f"{m.id} - MTR {m.numero_mtr or '-'} | kg={m.qtd_kg or 0:.1f}" for m in mtrs]
            escolha = st.selectbox("Escolha a MTR para editar", lista, key=f"sel_mtr_edit_{fornecedor_id}")
            mid = int(escolha.split(" - ")[0])
            m = next(mm for mm in mtrs if mm.id == mid)

            with st.form(f"form_edit_mtr_{mid}"):
                numero_mtr = st.text_input("Número da MTR", value=m.numero_mtr or "")
                qtd_kg = st.number_input("Quantidade (kg)", min_value=0.0, value=float(m.qtd_kg or 0.0), step=1.0)
                dt_emissao = st.text_input("Data emissão gerador (YYYY-MM-DD)", value=(m.gerador_data_emissao.isoformat() if m.gerador_data_emissao else ""))
                dt_receb = st.text_input("Data recebimento destinador (YYYY-MM-DD)", value=(m.destinador_data_recebimento.isoformat() if m.destinador_data_recebimento else ""))
                edit_obs = st.form_submit_button("Salvar alterações da MTR")

            if edit_obs:
                with SessionLocal() as db:
                    me = mtr_query_por_site(db).filter(MTR.id==mid).first()
                    if not me:
                        st.error("MTR não encontrada para o seu site.")
                        st.stop()
                    me.numero_mtr = numero_mtr.strip() or None
                    me.qtd_kg = float(qtd_kg or 0.0)
                    me.gerador_data_emissao = parse_data_flex(dt_emissao)
                    me.destinador_data_recebimento = parse_data_flex(dt_receb)
                    me.updated_by = st.session_state.usuario
                    db.commit()
                st.success("MTR atualizada com sucesso!")
                _safe_rerun()

            if m.cdfs:
                st.markdown("#### Editar CDF vinculado")
                cdf_opt = [f"{c.id} - Emissão {c.data_emissao or '-'}" for c in m.cdfs]
                cdf_sel = st.selectbox("Selecione o CDF", cdf_opt, key=f"cdf_sel_edit_{mid}")
                cdf_id = int(cdf_sel.split(" - ")[0])
                cdf_obj = next(c for c in m.cdfs if c.id == cdf_id)
                with st.form(f"form_edit_cdf_{cdf_id}"):
                    cdf_dt = st.text_input("Data de emissão (YYYY-MM-DD)", value=(cdf_obj.data_emissao.isoformat() if cdf_obj.data_emissao else ""))
                    cdf_ob = st.text_input("Observação", value=cdf_obj.observacao or "")
                    save_cdf = st.form_submit_button("Salvar alterações do CDF")
                if save_cdf:
                    with SessionLocal() as db:
                        ce = db.query(CDF).filter(CDF.id==cdf_id).first()
                        ce.data_emissao = parse_data_flex(cdf_dt)
                        ce.observacao = cdf_ob.strip() or None
                        ce.updated_by = st.session_state.usuario
                        db.commit()
                    st.success("CDF atualizado com sucesso!")
                    _safe_rerun()
            else:
                st.caption("Esta MTR ainda não possui CDF para edição.")


# ---- Admin (Usuários) ----
if menu=="Admin (Usuários)":
    if st.session_state.role!="Admin":
        st.error("Apenas Admin pode acessar esta página."); st.stop()
    st.header("Administração")
    with SessionLocal() as db: usuarios=db.query(User).all()
    st.subheader("Usuários")
    for u in usuarios: st.write(f"- **{u.username}** — {u.role.value} — site {u.site.value}")
    st.subheader("Criar novo usuário")
    with st.form("form_user"):
        username=st.text_input("Usuário").strip()
        password=st.text_input("Senha", type="password").strip()
        role=st.selectbox("Papel", [RoleEnum.admin.value, RoleEnum.auditor.value, RoleEnum.leitor.value])
        site=st.selectbox("Site", TODOS_SITES, index=0)
        enviar=st.form_submit_button("Criar")
    if enviar:
        if not username or not password: st.error("Preencha usuário e senha.")
        else:
            with SessionLocal() as db:
                if get_user_by_username(db, username): st.error("Usuário já existe.")
                else:
                    create_user(db, username, password, RoleEnum(role), SiteEnum(site)); st.success("Usuário criado com sucesso!"); _safe_rerun()

    st.subheader("Exportar dados (Excel)")
    if not HAVE_PANDAS:
        st.info("Para exportar, instale: pandas e openpyxl.")
    else:
        if st.button("Gerar arquivo .xlsx"):
            with SessionLocal() as db:
                fornecedores=db.query(Fornecedor).options(
                    joinedload(Fornecedor.documentos),
                    joinedload(Fornecedor.auditoria),
                    joinedload(Fornecedor.planos_acao),
                    joinedload(Fornecedor.contratos),
                    joinedload(Fornecedor.mtrs).joinedload(MTR.cdfs)
                ).all()
            output=BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                df_f = pd.DataFrame([{
                    "id":f.id,"nome":f.nome,"cpf_cnpj":f.cpf_cnpj,"endereco":f.endereco,"telefone":f.telefone,
                    "updated_by":f.updated_by,"created_at":f.created_at,"updated_at":f.updated_at
                } for f in fornecedores])
                if not df_f.empty: df_f["cpf_cnpj_fmt"]=df_f["cpf_cnpj"].apply(formatar_cpf_cnpj)
                df_f.to_excel(writer, sheet_name="Fornecedores", index=False)

                rows_d=[]
                for f in fornecedores:
                    for d in f.documentos:
                        rows_d.append({
                            "fornecedor_id":f.id,"fornecedor":f.nome,"tipo":d.tipo,
                            "data_inicio":d.data_inicio,"data_validade":d.data_validade,
                            "arquivo":d.arquivo,"updated_by":d.updated_by
                        })
                pd.DataFrame(rows_d).to_excel(writer, sheet_name="Documentos", index=False)

                rows_a=[]
                for f in fornecedores:
                    a=f.auditoria
                    if a:
                        modelo=a.respostas.get("modelo") if isinstance(a.respostas,dict) else "v1"
                        area_pct=a.respostas.get("area_pct") if isinstance(a.respostas,dict) else None
                        rows_a.append({
                            "fornecedor_id":f.id,"fornecedor":f.nome,"score":a.score,"classificado":a.classificado,
                            "modelo":modelo,"area_pct_json":json.dumps(_make_json_safe(area_pct),ensure_ascii=False) if area_pct else "",
                            "respostas_json":json.dumps(_make_json_safe(a.respostas),ensure_ascii=False),"updated_by":a.updated_by
                        })
                pd.DataFrame(rows_a).to_excel(writer, sheet_name="Auditorias", index=False)

                rows_p=[]
                for f in fornecedores:
                    for p in f.planos_acao:
                        rows_p.append({
                            "fornecedor_id":f.id,"fornecedor":f.nome,"descricao":p.descricao,
                            "inicio":p.data_inicio,"fim":p.data_fim,"status":p.status,
                            "evidencias":json.dumps(_make_json_safe(p.evidencias),ensure_ascii=False),"updated_by":p.updated_by
                        })
                pd.DataFrame(rows_p).to_excel(writer, sheet_name="Planos", index=False)

                rows_c=[]
                for f in fornecedores:
                    for c in f.contratos:
                        rows_c.append({
                            "fornecedor_id":f.id,"fornecedor":f.nome,"assinatura":c.data_assinatura,
                            "validade":c.data_validade,"arquivo":c.arquivo,"updated_by":c.updated_by
                        })
                pd.DataFrame(rows_c).to_excel(writer, sheet_name="Contratos", index=False)

                rows_m=[]
                for f in fornecedores:
                    for m in f.mtrs:
                        rows_m.append({
                            "fornecedor_id":f.id,"fornecedor":f.nome,"mtr_numero":m.numero_mtr,
                            "recebimento":m.destinador_data_recebimento,"qtd_kg":m.qtd_kg,
                            "und_origem":m.und_original,"qtd_original":m.qtd_original,
                            "cdf_count":m.cdf_count,"arquivo":m.arquivo,"site":m.site.value if m.site else None
                        })
                pd.DataFrame(rows_m).to_excel(writer, sheet_name="MTRs", index=False)

                rows_cdf=[]
                for f in fornecedores:
                    for m in f.mtrs:
                        for cdf in m.cdfs:
                            rows_cdf.append({
                                "fornecedor_id":f.id,"fornecedor":f.nome,"mtr_numero":m.numero_mtr,
                                "cdf_data":cdf.data_emissao,"observacao":cdf.observacao,"arquivo":cdf.arquivo
                            })
                pd.DataFrame(rows_cdf).to_excel(writer, sheet_name="CDFs", index=False)



            output.seek(0)
            st.download_button("Baixar Excel", data=output.read(),
                               file_name="fornecedores_export.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ---- Sair ----
if menu=="Sair":
    st.session_state.logado=False; st.session_state.usuario=None; st.session_state.role=None; st.session_state.site=None
    st.session_state.sel_forn_id=None; _safe_rerun()
