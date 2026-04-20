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
st.markdown(
    """
    <style>
    :root {
        --brand-bg: #f6f8fb;
        --card-bg: #ffffff;
        --muted: #5f6b7a;
        --border: #e7ebf3;
        --title: #12263f;
        --accent: #1f4bb8;
    }
    .stApp {
        background: var(--brand-bg);
    }
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #ffcd61 0%, #ffb91d 100%) !important;
        border-right: 1px solid rgba(18, 38, 63, 0.12);
    }
    section[data-testid="stSidebar"] * {
        color: #1f1f1f !important;
    }
    .page-header {
        background: var(--card-bg);
        border: 1px solid var(--border);
        border-radius: 14px;
        padding: 1rem 1.2rem;
        margin-bottom: 1rem;
        box-shadow: 0 4px 16px rgba(18, 38, 63, 0.05);
    }
    .page-header h1 {
        margin: 0;
        font-size: 1.55rem;
        color: var(--title);
    }
    .page-header p {
        margin: 0.35rem 0 0;
        color: var(--muted);
        font-size: 0.94rem;
    }
    .section-title {
        margin: 1.1rem 0 0.55rem;
        color: var(--title);
        font-size: 1.08rem;
        font-weight: 600;
    }
    .kpi-card {
        border: 1px solid var(--border);
        background: var(--card-bg);
        border-radius: 12px;
        padding: 0.8rem 0.95rem;
        box-shadow: 0 2px 8px rgba(18, 38, 63, 0.04);
    }
    .kpi-label {
        color: var(--muted);
        font-size: 0.8rem;
        margin-bottom: 0.15rem;
    }
    .kpi-value {
        color: var(--title);
        font-size: 1.35rem;
        font-weight: 700;
    }
    .status-badge {
        border-radius: 999px;
        font-size: 0.78rem;
        padding: 0.22rem 0.56rem;
        display: inline-block;
        font-weight: 600;
    }
    .block-shell {
        background: var(--card-bg);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 0.85rem 1rem;
        margin-bottom: 0.9rem;
    }
    div[data-testid="stDateInput"]:has(input:disabled) {
        opacity: 0.65;
    }
    </style>
    """,
    unsafe_allow_html=True,
)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///fornecedores.db")
CONNECT_ARGS = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=CONNECT_ARGS, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
Base = declarative_base()

# =========================
#       UTILITÁRIOS
# =========================


def render_page_header(title:str, subtitle:str|None=None):
    subtitle_html = f"<p>{subtitle}</p>" if subtitle else ""
    st.markdown(
        f"<div class='page-header'><h1>{title}</h1>{subtitle_html}</div>",
        unsafe_allow_html=True,
    )


def render_section_title(title:str):
    st.markdown(f"<div class='section-title'>{title}</div>", unsafe_allow_html=True)


def render_kpi_card(label:str, value:str):
    st.markdown(
        f"<div class='kpi-card'><div class='kpi-label'>{label}</div><div class='kpi-value'>{value}</div></div>",
        unsafe_allow_html=True,
    )


def status_badge(status:str)->str:
    s=(status or '').lower()
    palette={
        'vencido': ('#7f1d1d','#fee2e2'),
        'próximo do vencimento': ('#92400e','#fef3c7'),
        'próximo de vencer': ('#92400e','#fef3c7'),
        'vigente': ('#065f46','#d1fae5'),
        'sem validade': ('#334155','#e2e8f0'),
        'excelente': ('#065f46','#d1fae5'),
        'bom': ('#166534','#dcfce7'),
        'condicionado': ('#92400e','#fef3c7'),
        'crítico': ('#7f1d1d','#fee2e2'),
        'pendente': ('#92400e','#fef3c7'),
        'aprovado': ('#065f46','#d1fae5'),
        'reprovado': ('#7f1d1d','#fee2e2'),
    }
    fg,bg=palette.get(s, ('#1e293b','#e2e8f0'))
    return f"<span class='status-badge' style='color:{fg};background:{bg};'>{status}</span>"
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
    admin="Admin"; auditor="Auditor"; leitor="Leitor"; fornecedor="Fornecedor"

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
    fornecedor_id = Column(Integer, ForeignKey('fornecedores.id', ondelete="SET NULL"), nullable=True)
    created_at = Column(Date, server_default=func.current_date())
    fornecedor = relationship("Fornecedor")

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
    data_validade = Column(Date, nullable=True)
    sem_validade = Column(Integer, nullable=False, default=0)
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
    responsavel = Column(String, nullable=True)
    data_inicio = Column(Date, nullable=False)
    data_fim = Column(Date, nullable=False)
    status = Column(Enum(PlanoStatusEnum), nullable=False, default=PlanoStatusEnum.andamento)
    evidencias = Column(JSON, nullable=False, default=list)
    atualizacoes = Column(JSON, nullable=False, default=list)
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

def create_user(db:Session, username:str, password:str, role:RoleEnum, site:SiteEnum, fornecedor_id:int|None=None)->User:
    u=User(username=username, password_hash=hash_password(password), role=role, site=site, fornecedor_id=fornecedor_id)
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
            if "fornecedor_id" not in cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN fornecedor_id INTEGER"))
        except Exception:
            pass
        try:
            cols = [r[1] for r in conn.execute(text("PRAGMA table_info(planos_acao)"))]
            if "responsavel" not in cols:
                conn.execute(text("ALTER TABLE planos_acao ADD COLUMN responsavel VARCHAR"))
            if "atualizacoes" not in cols:
                conn.execute(text("ALTER TABLE planos_acao ADD COLUMN atualizacoes JSON"))
                conn.execute(text("UPDATE planos_acao SET atualizacoes='[]' WHERE atualizacoes IS NULL"))
        except Exception:
            pass
        try:
            cols = [r[1] for r in conn.execute(text("PRAGMA table_info(documentos)"))]
            if "sem_validade" not in cols:
                conn.execute(text("ALTER TABLE documentos ADD COLUMN sem_validade INTEGER DEFAULT 0 NOT NULL"))
                conn.execute(text("UPDATE documentos SET sem_validade=0 WHERE sem_validade IS NULL"))
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
    st.session_state.logado=False; st.session_state.usuario=None; st.session_state.role=None; st.session_state.site=None; st.session_state.fornecedor_id=None
if "sel_forn_id" not in st.session_state:
    st.session_state.sel_forn_id=None

# =========================
#         LOGIN
# =========================
def pagina_login():
    render_page_header("Sistema de Gerenciamento de Fornecedores", "Acesse com suas credenciais corporativas para continuar.")
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
                st.session_state.fornecedor_id=u.fornecedor_id
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
st.sidebar.title(f"Usuário: {st.session_state.usuario} ({st.session_state.role})")
site_logado = st.session_state.site
acesso_corporativo = site_logado == SiteEnum.LAG.value
st.sidebar.caption(f"Site: {site_logado}")

if st.session_state.role=="Leitor":
    nivel = st.sidebar.radio("Nível de navegação", ["Executivo", "Sessão"], index=0)
    if nivel == "Executivo":
        menu = st.sidebar.selectbox(
            "Menu",
            ["Overview", "Visão Geral Fornecedores", "Central de Pendências", "Sair"]
        )
    else:
        menu = st.sidebar.selectbox("Menu", ["Sair"])
elif st.session_state.role=="Fornecedor":
    nivel = "Fornecedor"
    st.sidebar.caption("Acesso restrito ao próprio cadastro, auditoria e documentos")
    menu = st.sidebar.selectbox(
        "Menu",
        ["Meu Portal", "Sair"]
    )
else:
    nivel = st.sidebar.radio("Nível de navegação", ["Executivo", "Operacional", "Administrativo"], index=0)
    if nivel == "Executivo":
        st.sidebar.caption("Visão estratégica, indicadores e pendências críticas")
        menu = st.sidebar.selectbox(
            "Menu",
            ["Overview", "Visão Geral Fornecedores", "Central de Pendências", "Sair"]
        )
    elif nivel == "Operacional":
        st.sidebar.caption("Execução diária: documentos, auditorias, contratos e MTR/CDF")
        menu = st.sidebar.selectbox(
            "Menu",
            ["Visualizar Fornecedores", "MTRs", "Contratos", "Central de Pendências", "Sair"]
        )
    else:
        st.sidebar.caption("Cadastros e administração")
        menu = st.sidebar.selectbox(
            "Menu",
            ["Cadastrar Fornecedor", "Admin (Usuários)", "Sair"]
        )

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

def status_contrato(data_validade:date|None)->str:
    if not data_validade:
        return "Sem validade"
    hoje = date.today()
    limite = hoje + timedelta(days=30)
    if data_validade < hoje:
        return "Vencido"
    if data_validade <= limite:
        return "Próximo do vencimento"
    return "Vigente"

def status_documento(data_validade:date|None)->str:
    if not data_validade:
        return "Sem validade"
    hoje = date.today()
    limite = hoje + timedelta(days=30)
    if data_validade < hoje:
        return "Vencido"
    if data_validade <= limite:
        return "Próximo de vencer"
    return "Vigente"


def auditoria_status(score:int|None)->str:
    if score is None:
        return "Sem auditoria"
    if score >= 76:
        return "Excelente"
    if score >= 51:
        return "Bom"
    if score >= 21:
        return "Condicionado"
    return "Crítico"


def calcular_tempo_mtr_cdf(mtr:MTR)->int|None:
    if not mtr or not mtr.gerador_data_emissao:
        return None
    base = mtr.gerador_data_emissao
    if mtr.cdfs:
        datas = [c.data_emissao for c in mtr.cdfs if c.data_emissao]
        if datas:
            return (min(datas) - base).days
    return (date.today() - base).days


def media_tempo_mtr_cdf(mtrs:list[MTR])->float|None:
    if not mtrs:
        return None
    tempos = []
    for mtr in mtrs:
        if not mtr or not mtr.gerador_data_emissao:
            continue
        if not mtr.cdfs:
            continue
        datas_cdf = [c.data_emissao for c in mtr.cdfs if c.data_emissao]
        if not datas_cdf:
            continue
        tempos.append((min(datas_cdf) - mtr.gerador_data_emissao).days)
    if not tempos:
        return None
    return sum(tempos) / len(tempos)


TIPOS_DOCUMENTOS_OBRIGATORIOS = [
    "Licença Ambiental de Operação",
    "Consulta de Área Contaminada",
    "Alvará de Funcionamento",
    "Comprovante de regularidade (CETESB ou órgão estadual)",
    "Condicionantes ambientais vigentes",
    "AVCB (Auto de Vistoria do Corpo de Bombeiros)",
    "CTF - IBAMA",
]


def docs_faltantes_fornecedor(documentos:list[Documento])->list[str]:
    docs_por_tipo = {d.tipo: d for d in documentos}
    faltantes = []
    for tipo in TIPOS_DOCUMENTOS_OBRIGATORIOS:
        doc = docs_por_tipo.get(tipo)
        if not doc or not doc.arquivo:
            faltantes.append(tipo)
    return faltantes


def indicador_tempo_mtr_cdf(mtrs:list[MTR])->str:
    if not mtrs:
        return "Sem MTR"
    com_cdf = [m for m in mtrs if m.cdfs and m.gerador_data_emissao]
    sem_cdf = [m for m in mtrs if not m.cdfs]
    media = media_tempo_mtr_cdf(com_cdf)
    if media is None:
        return f"Sem CDF ({len(sem_cdf)} pendente{'s' if len(sem_cdf) != 1 else ''})"
    if media <= 5:
        base = f"🟢 {media:.1f} dias"
    elif media <= 10:
        base = f"🟡 {media:.1f} dias"
    else:
        base = f"🔴 {media:.1f} dias"
    if sem_cdf:
        base += f" | {len(sem_cdf)} MTR sem CDF"
    return base


def indicador_mtr_cdf_fornecedor(mtrs:list[MTR])->str:
    if not mtrs:
        return "Sem MTR"
    tempos = [calcular_tempo_mtr_cdf(m) for m in mtrs]
    tempos_validos = [t for t in tempos if t is not None]
    if not tempos_validos:
        return "Sem data de emissão"
    media_dias = sum(tempos_validos) / len(tempos_validos)
    return f"{media_dias:.1f} dias"


def parse_auditoria_itens(auditoria_obj:Auditoria|None)->dict:
    if not auditoria_obj or not isinstance(auditoria_obj.respostas, dict):
        return {}
    return auditoria_obj.respostas.get("itens_detalhes", {}) or {}


def criticidade_rank(status:str)->int:
    s = (status or "").lower()
    if any(x in s for x in ["vencido", "crítico", "atrasado", "não conforme"]):
        return 3
    if any(x in s for x in ["próximo", "condicionado", "pendente"]):
        return 2
    if any(x in s for x in ["sem auditoria", "sem cdf"]):
        return 2
    return 1


def criticidade_label(rank:int)->str:
    return {3: "Alta", 2: "Média", 1: "Baixa"}.get(rank, "Baixa")


def build_pendencias(db:Session, site:str, acesso_total:bool)->list[dict]:
    hoje = date.today()
    limite = hoje + timedelta(days=30)
    pendencias = []
    fornecedores = db.query(Fornecedor).options(
        joinedload(Fornecedor.documentos),
        joinedload(Fornecedor.contratos),
        joinedload(Fornecedor.auditoria),
        joinedload(Fornecedor.planos_acao),
        joinedload(Fornecedor.mtrs).joinedload(MTR.cdfs),
    ).all()
    for f in fornecedores:
        faltantes = docs_faltantes_fornecedor(f.documentos)
        for tipo_doc in faltantes:
            pendencias.append({"Fornecedor": f.nome, "Site": site, "Tipo": "Documento faltante", "Item": tipo_doc, "Criticidade": "Alta", "Prioridade": 3, "Origem": "Fornecedor"})

        for d in f.documentos:
            if d.sem_validade or not d.data_validade:
                continue
            if d.data_validade < hoje:
                pendencias.append({"Fornecedor": f.nome, "Site": site, "Tipo": "Documento vencido", "Item": d.tipo, "Criticidade": "Alta", "Prioridade": 3, "Origem": "Documentos"})
            elif d.data_validade <= limite:
                pendencias.append({"Fornecedor": f.nome, "Site": site, "Tipo": "Documento próximo do vencimento", "Item": d.tipo, "Criticidade": "Média", "Prioridade": 2, "Origem": "Documentos"})

        contrato = sorted(f.contratos, key=lambda c: c.data_validade or date.max)[0] if f.contratos else None
        if contrato:
            if contrato.data_validade < hoje:
                pendencias.append({"Fornecedor": f.nome, "Site": site, "Tipo": "Contrato vencido", "Item": "Contrato", "Criticidade": "Alta", "Prioridade": 3, "Origem": "Contratos"})
            elif contrato.data_validade <= limite:
                pendencias.append({"Fornecedor": f.nome, "Site": site, "Tipo": "Contrato próximo do vencimento", "Item": "Contrato", "Criticidade": "Média", "Prioridade": 2, "Origem": "Contratos"})

        aud = f.auditoria
        if not aud:
            pendencias.append({"Fornecedor": f.nome, "Site": site, "Tipo": "Fornecedor sem auditoria", "Item": "Sem auditoria", "Criticidade": "Alta", "Prioridade": 3, "Origem": "Auditorias"})
        elif (aud.score or 0) < 51:
            pendencias.append({"Fornecedor": f.nome, "Site": site, "Tipo": "Auditoria com score baixo", "Item": f"Score {aud.score or 0}", "Criticidade": "Alta", "Prioridade": 3, "Origem": "Auditorias"})

        for p in f.planos_acao:
            if p.status != PlanoStatusEnum.concluido and p.data_fim and p.data_fim < hoje:
                pendencias.append({"Fornecedor": f.nome, "Site": site, "Tipo": "Plano de ação em atraso", "Item": p.descricao[:60], "Criticidade": "Alta", "Prioridade": 3, "Origem": "Planos de Ação"})

        mtrs = f.mtrs
        if not acesso_total:
            mtrs = [m for m in mtrs if m.site and m.site.value == site]
        for m in mtrs:
            tempo = calcular_tempo_mtr_cdf(m)
            if not m.cdfs:
                pendencias.append({"Fornecedor": f.nome, "Site": m.site.value if m.site else site, "Tipo": "MTR sem CDF", "Item": m.numero_mtr or "MTR sem número", "Criticidade": "Média", "Prioridade": 2, "Origem": "MTRs"})
            if tempo is not None and tempo > 10:
                pendencias.append({"Fornecedor": f.nome, "Site": m.site.value if m.site else site, "Tipo": "Tempo MTR → CDF acima do limite", "Item": f"{m.numero_mtr or '-'} ({tempo} dias)", "Criticidade": "Média", "Prioridade": 2, "Origem": "MTRs"})
    return pendencias


def resumo_fornecedor_dict(f:Fornecedor, site:str, acesso_total:bool)->dict:
    mtrs = f.mtrs if acesso_total else [m for m in f.mtrs if m.site and m.site.value == site]
    docs_total = len(TIPOS_DOCUMENTOS_OBRIGATORIOS)
    docs_falt = len(docs_faltantes_fornecedor(f.documentos))
    docs_pct = int(round(((docs_total - docs_falt) / docs_total) * 100)) if docs_total else 0
    score = f.auditoria.score if f.auditoria else None
    mtr_sem_cdf = sum(1 for m in mtrs if not m.cdfs)
    media_mtr_cdf = media_tempo_mtr_cdf(mtrs)
    contrato_atual = sorted(f.contratos, key=lambda c: c.data_validade or date.max)[0] if f.contratos else None
    pendencias_prioritarias = 0
    for p in f.planos_acao:
        if p.status != PlanoStatusEnum.concluido and p.data_fim and p.data_fim < date.today():
            pendencias_prioritarias += 1
    pendencias_prioritarias += docs_falt
    pendencias_prioritarias += sum(1 for d in f.documentos if d.data_validade and d.data_validade < date.today())
    return {
        "status_geral": auditoria_status(score),
        "score_auditoria": "-" if score is None else str(score),
        "documentacao_pct": docs_pct,
        "status_contrato": status_contrato(contrato_atual.data_validade) if contrato_atual else "Sem contrato",
        "mtrs_total": len(mtrs),
        "mtrs_sem_cdf": mtr_sem_cdf,
        "tempo_medio_mtr_cdf": "-" if media_mtr_cdf is None else f"{media_mtr_cdf:.1f} dias",
        "pendencias_prioritarias": pendencias_prioritarias,
    }


def gerar_relatorio_fornecedor_html(f:Fornecedor, resumo:dict, site:str, acesso_total:bool)->str:
    mtrs = f.mtrs if acesso_total else [m for m in f.mtrs if m.site and m.site.value == site]
    docs_linhas = "".join(
        f"<li>{d.tipo}: {status_documento(d.data_validade) if not d.sem_validade else 'Sem validade'}</li>" for d in f.documentos
    ) or "<li>Sem documentos cadastrados.</li>"
    planos_linhas = "".join(
        f"<li>{p.descricao} — {p.status.value} (prazo: {p.data_fim})</li>" for p in f.planos_acao
    ) or "<li>Sem planos de ação.</li>"
    contratos_linhas = "".join(
        f"<li>Assinatura: {c.data_assinatura} | Vencimento: {c.data_validade} | {status_contrato(c.data_validade)}</li>" for c in f.contratos
    ) or "<li>Sem contratos cadastrados.</li>"
    return f"""
    <html><head><meta charset='utf-8'><title>Relatório do Fornecedor</title></head><body>
    <h1>Relatório consolidado do fornecedor</h1>
    <h2>{f.nome}</h2>
    <p><b>CPF/CNPJ:</b> {formatar_cpf_cnpj(f.cpf_cnpj)} | <b>Telefone:</b> {f.telefone or '-'} | <b>Endereço:</b> {f.endereco or '-'}</p>
    <h3>Resumo executivo-operacional</h3>
    <ul>
      <li>Status geral: {resumo['status_geral']}</li>
      <li>Score da auditoria: {resumo['score_auditoria']}</li>
      <li>Documentação completa: {resumo['documentacao_pct']}%</li>
      <li>Status do contrato: {resumo['status_contrato']}</li>
      <li>MTRs vinculadas: {resumo['mtrs_total']}</li>
      <li>MTRs sem CDF: {resumo['mtrs_sem_cdf']}</li>
      <li>Tempo médio MTR → CDF: {resumo['tempo_medio_mtr_cdf']}</li>
      <li>Pendências prioritárias: {resumo['pendencias_prioritarias']}</li>
    </ul>
    <h3>Situação documental</h3><ul>{docs_linhas}</ul>
    <h3>Situação contratual</h3><ul>{contratos_linhas}</ul>
    <h3>Resultado de auditoria</h3><p>{f.auditoria.classificado if f.auditoria else 'Sem auditoria'} (score: {f.auditoria.score if f.auditoria else '-'})</p>
    <h3>Planos de ação</h3><ul>{planos_linhas}</ul>
    <h3>Resumo MTR/CDF</h3><p>Total de MTRs: {len(mtrs)}</p>
    </body></html>
    """

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
    render_page_header("Overview de Conformidade e Riscos", "Monitoramento consolidado de contratos, documentos e indicadores operacionais dos fornecedores.")
    render_section_title("Parâmetros de visualização")
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

    render_section_title("Indicadores consolidados")
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

    render_section_title("Tabelas operacionais")
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







# ---- Visão Geral Fornecedores ----
if menu=="Visão Geral Fornecedores":
    if st.session_state.role not in ("Admin","Auditor"):
        st.error("Acesso restrito.")
        st.stop()
    render_page_header("Visão Geral de Fornecedores", "Panorama executivo com foco documental, auditoria e indicadores operacionais de MTR/CDF.")
    with SessionLocal() as db:
        fornecedores = db.query(Fornecedor).options(
            joinedload(Fornecedor.documentos),
            joinedload(Fornecedor.contratos),
            joinedload(Fornecedor.auditoria),
            joinedload(Fornecedor.mtrs).joinedload(MTR.cdfs)
        ).order_by(Fornecedor.nome.asc()).all()

    if not fornecedores:
        st.info("Nenhum fornecedor cadastrado.")
    else:
        linhas = []
        total_faltantes = total_proximo = total_vencidos = 0
        for f in fornecedores:
            docs_faltantes = docs_faltantes_fornecedor(f.documentos)
            docs_validade = [d for d in f.documentos if not d.sem_validade]
            docs_prox_vencer = sum(1 for d in docs_validade if status_documento(d.data_validade)=="Próximo de vencer")
            docs_vencidos = sum(1 for d in docs_validade if status_documento(d.data_validade)=="Vencido")
            total_faltantes += len(docs_faltantes)
            total_proximo += docs_prox_vencer
            total_vencidos += docs_vencidos

            score = f.auditoria.score if f.auditoria else None
            status_auditoria = auditoria_status(score)
            score_txt = "-" if score is None else f"{score}"
            kg_total = sum((m.qtd_kg or 0.0) for m in f.mtrs)
            docs_txt = "Todos os obrigatórios enviados" if not docs_faltantes else " • ".join(docs_faltantes)
            alerta_txt = (
                f"🔴 Faltantes: {len(docs_faltantes)} | "
                f"🟡 Próx. do vencimento: {docs_prox_vencer} | "
                f"🚨 Vencidos: {docs_vencidos}"
            )

            linhas.append({
                "Fornecedor": f.nome,
                "Documentação (faltantes)": docs_txt,
                "Alerta de documentação": alerta_txt,
                "Auditoria": f"{status_auditoria} | Score: {score_txt}",
                "Indicador MTR → CDF": indicador_mtr_cdf_fornecedor(f.mtrs),
                "Resíduos enviados (kg)": round(kg_total, 2),
            })

        c1, c2, c3 = st.columns(3)
        with c1:
            render_kpi_card("Documentos obrigatórios faltantes", str(total_faltantes))
        with c2:
            render_kpi_card("Documentos próximos do vencimento", str(total_proximo))
        with c3:
            render_kpi_card("Documentos vencidos", str(total_vencidos))

        st.markdown("#### Lista geral")
        if HAVE_PANDAS:
            df_visao = pd.DataFrame(linhas)
            st.dataframe(df_visao, use_container_width=True, hide_index=True)
        else:
            for linha in linhas:
                with st.container(border=True):
                    st.markdown(f"### {linha['Fornecedor']}")
                    st.markdown(f"**Documentação (faltantes):** {linha['Documentação (faltantes)']}")
                    st.markdown(f"**Alerta de documentação:** {linha['Alerta de documentação']}")
                    st.markdown(f"**Auditoria:** {linha['Auditoria']}")
                    st.markdown(f"**Indicador MTR → CDF:** {linha['Indicador MTR → CDF']}")
                    st.markdown(f"**Resíduos enviados (kg):** {linha['Resíduos enviados (kg)']}")


# ---- Cadastrar Fornecedor ----
if menu=="Cadastrar Fornecedor":
    if st.session_state.role not in ("Admin","Auditor"):
        st.error("Você não tem permissão para cadastrar fornecedores."); st.stop()
    render_page_header("Cadastro de Fornecedor", "Registre um novo fornecedor preservando os dados cadastrais obrigatórios.")
    render_section_title("Dados cadastrais")
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
    render_page_header("Gestão de Fornecedores", "Consulte, atualize documentos, auditorias, planos de ação, contratos e MTRs.")
    render_section_title("Busca e seleção")
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
        render_section_title("Lista de fornecedores")
        for f in fornecedores:
            is_selected=(st.session_state.sel_forn_id==f.id)
            style = "background:#e8f5e9;border:1px solid #2e7d32;" if is_selected else "background:#f6f6f6;border:1px solid #ddd;"
            if st.button(f"📁 {f.nome} — {formatar_cpf_cnpj(f.cpf_cnpj)}", key=f"btn_f_{f.id}"):
                st.session_state.sel_forn_id=f.id
            st.markdown(f"<div style='height:6px;border-radius:0 0 8px 8px;{style}'></div>", unsafe_allow_html=True)

    with col_right:
        sel = next((f for f in fornecedores if f.id==st.session_state.sel_forn_id), None)
        if sel is None: st.info("Selecione um fornecedor na lista ao lado para visualizar/editar.")
        else:
            render_section_title(f"Dossiê do fornecedor — {sel.nome}")
            resumo = resumo_fornecedor_dict(sel, site_logado, acesso_corporativo)
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                render_kpi_card("Status geral", resumo["status_geral"])
                render_kpi_card("Score da auditoria", resumo["score_auditoria"])
            with c2:
                render_kpi_card("Documentação completa", f"{resumo['documentacao_pct']}%")
                render_kpi_card("Status do contrato", resumo["status_contrato"])
            with c3:
                render_kpi_card("MTRs vinculadas", str(resumo["mtrs_total"]))
                render_kpi_card("MTRs sem CDF", str(resumo["mtrs_sem_cdf"]))
            with c4:
                render_kpi_card("Tempo médio MTR → CDF", resumo["tempo_medio_mtr_cdf"])
                render_kpi_card("Pendências prioritárias", str(resumo["pendencias_prioritarias"]))

            rel_html = gerar_relatorio_fornecedor_html(sel, resumo, site_logado, acesso_corporativo)
            st.download_button(
                "📄 Gerar relatório consolidado (HTML)",
                data=rel_html.encode("utf-8"),
                file_name=f"relatorio_fornecedor_{sel.id}.html",
                mime="text/html",
                key=f"rep_forn_{sel.id}",
            )

            tabs=st.tabs(["Dados gerais","Documentos","Auditorias","Planos de ação","Contratos","MTRs / CDFs","Pendências / histórico"])

            # Informações
            with tabs[0]:
                st.write(f"**CPF/CNPJ:** {formatar_cpf_cnpj(sel.cpf_cnpj)}")
                st.write(f"**Endereço:** {sel.endereco or '-'}")
                st.write(f"**Telefone:** {sel.telefone or '-' }")
            # Documentos
            with tabs[1]:
                st.markdown("#### Documentos do fornecedor")
                docs_existentes = {d.tipo: d for d in sel.documentos}
                docs_ordenados = sorted(sel.documentos, key=lambda x: (x.data_validade or date.max, x.tipo or ""))
                tipos_documentos = TIPOS_DOCUMENTOS_OBRIGATORIOS

                st.markdown("##### Lista de documentos cadastrados")
                if not docs_ordenados:
                    st.info("Nenhum documento cadastrado para este fornecedor.")
                else:
                    head = st.columns([2.0, 1.1, 1.1, 1.0, 0.8])
                    head[0].markdown("**Nome do documento**")
                    head[1].markdown("**Início de vigência**")
                    head[2].markdown("**Vencimento**")
                    head[3].markdown("**Status**")
                    head[4].markdown("**Arquivo**")
                    for d in docs_ordenados:
                        row = st.columns([2.0, 1.1, 1.1, 1.0, 0.8])
                        row[0].write(d.tipo)
                        row[1].write(str(d.data_inicio or "-"))
                        row[2].write("Sem validade" if d.sem_validade else str(d.data_validade or "-"))
                        row[3].markdown(status_badge("Vigente" if d.sem_validade else status_documento(d.data_validade)), unsafe_allow_html=True)
                        if d.arquivo and Path(d.arquivo).exists():
                            with open(d.arquivo, "rb") as f:
                                data_atual = f.read()
                            row[4].download_button("Baixar", data=data_atual, file_name=os.path.basename(d.arquivo), key=f"doc_dl_{d.id}")
                        else:
                            row[4].caption("-")

                st.divider()
                st.markdown("##### Ações de gerenciamento")

                if "novo_doc_tipos" not in st.session_state:
                    st.session_state.novo_doc_tipos = {}
                if sel.id not in st.session_state.novo_doc_tipos:
                    faltantes = [t for t in tipos_documentos if t not in docs_existentes]
                    st.session_state.novo_doc_tipos[sel.id] = faltantes[:1] if faltantes else []

                st.caption("Adicione novos documentos abaixo ou edite documentos já cadastrados.")
                if st.button("Adicionar documento", key=f"btn_add_doc_item_{sel.id}"):
                    faltantes = [t for t in tipos_documentos if t not in docs_existentes and t not in st.session_state.novo_doc_tipos[sel.id]]
                    if faltantes:
                        st.session_state.novo_doc_tipos[sel.id].append(faltantes[0])
                    else:
                        st.warning("Todos os tipos de documentos já foram adicionados.")

                novos_itens = [{"id": f"novo_{idx}", "tipo": tipo_tmp} for idx, tipo_tmp in enumerate(st.session_state.novo_doc_tipos[sel.id])]

                for item in novos_itens:
                    with st.container(border=True):
                        tipo_opts = [t for t in tipos_documentos if t not in docs_existentes or t == item["tipo"]]
                        tipo_escolhido = st.selectbox(
                            "Tipo",
                            tipo_opts,
                            index=tipo_opts.index(item["tipo"]) if item["tipo"] in tipo_opts else 0,
                            key=f"novo_tipo_{sel.id}_{item['id']}"
                        )
                        c1, c2, c3 = st.columns([0.35, 0.25, 0.25])
                        with c1:
                            novo_up = st.file_uploader("Arquivo", type=["pdf", "jpg", "png", "jpeg"], key=f"novo_arq_{sel.id}_{item['id']}")
                        with c2:
                            novo_ini = st.date_input("Início", value=date.today(), key=f"novo_ini_{sel.id}_{item['id']}")
                        with c3:
                            sem_validade = st.checkbox("Documento sem data de validade", key=f"novo_sem_val_{sel.id}_{item['id']}")
                            novo_val = st.date_input("Validade", value=date.today(), key=f"novo_val_{sel.id}_{item['id']}", disabled=sem_validade)
                        csave, crem = st.columns([0.5, 0.5])
                        if csave.button("Salvar documento", key=f"btn_save_doc_{sel.id}_{item['id']}"):
                            if novo_up is None:
                                st.error("Envie um arquivo.")
                            elif (not sem_validade) and novo_val < novo_ini:
                                st.error("Validade não pode ser anterior ao início.")
                            else:
                                caminho = salvar_arquivo(novo_up, "uploads/documentos", f"{sel.id}_{tipo_escolhido}")
                                with SessionLocal() as db:
                                    try:
                                        d = Documento(
                                            fornecedor_id=sel.id,
                                            tipo=tipo_escolhido,
                                            arquivo=caminho,
                                            data_inicio=novo_ini,
                                            data_validade=None if sem_validade else novo_val,
                                            sem_validade=1 if sem_validade else 0,
                                            updated_by=st.session_state.usuario
                                        )
                                        db.add(d)
                                        db.commit()
                                        st.success("Documento adicionado com sucesso!")
                                        st.session_state.novo_doc_tipos[sel.id] = [t for t in st.session_state.novo_doc_tipos[sel.id] if t != item["tipo"]]
                                        _safe_rerun()
                                    except Exception as e:
                                        db.rollback()
                                        st.error(f"Erro ao salvar documento: {e}")
                        if crem.button("Remover item", key=f"btn_rm_doc_{sel.id}_{item['id']}"):
                            st.session_state.novo_doc_tipos[sel.id] = [t for t in st.session_state.novo_doc_tipos[sel.id] if t != item["tipo"]]
                            _safe_rerun()

                if docs_ordenados:
                    st.markdown("##### Editar documento existente")
                    doc_opts = [f"{d.id} — {d.tipo}" for d in docs_ordenados]
                    doc_sel = st.selectbox("Selecione o documento", doc_opts, key=f"doc_sel_{sel.id}")
                    doc_id = int(doc_sel.split(" — ", 1)[0])
                    d = next((x for x in docs_ordenados if x.id == doc_id), None)
                    if d:
                        with st.container(border=True):
                            c1, c2, c3 = st.columns([0.4, 0.3, 0.3])
                            with c1:
                                up = st.file_uploader("Substituir arquivo (opcional)", type=["pdf", "jpg", "png", "jpeg"], key=f"doc_up_{d.id}")
                            with c2:
                                dt_ini = st.date_input("Início", value=d.data_inicio, key=f"doc_ini_{d.id}")
                            with c3:
                                doc_sem_validade = st.checkbox("Documento sem data de validade", value=bool(d.sem_validade), key=f"doc_sem_val_{d.id}")
                                dt_default = d.data_validade or date.today()
                                dt_val = st.date_input("Validade", value=dt_default, key=f"doc_val_{d.id}", disabled=doc_sem_validade)
                            if st.button("Salvar alterações", key=f"doc_save_{d.id}"):
                                if (not doc_sem_validade) and dt_val < dt_ini:
                                    st.error("Validade não pode ser anterior ao início.")
                                else:
                                    caminho = d.arquivo
                                    if up is not None:
                                        caminho = salvar_arquivo(up, "uploads/documentos", f"{sel.id}_{d.tipo}")
                                    with SessionLocal() as db:
                                        doc_db = db.query(Documento).filter(Documento.id == d.id).first()
                                        doc_db.arquivo = caminho
                                        doc_db.data_inicio = dt_ini
                                        doc_db.data_validade = None if doc_sem_validade else dt_val
                                        doc_db.sem_validade = 1 if doc_sem_validade else 0
                                        doc_db.updated_by = st.session_state.usuario
                                        db.commit()
                                        st.success("Documento atualizado com sucesso!")
                                        _safe_rerun()
            # Auditoria
            with tabs[2]:
                st.subheader("Auditorias — Checklist IQA")
                st.caption("Checklist organizado por seções para reduzir fadiga e destacar riscos críticos.")
                respostas_form = {}
                aud_exist = sel.auditoria
                prev = {}
                anexos_prev = []
                if aud_exist and isinstance(aud_exist.respostas, dict):
                    prev = aud_exist.respostas.get("checklist_respostas", {}) or {}
                    anexos_prev = aud_exist.respostas.get("anexos", []) or []
                itens_prev = parse_auditoria_itens(aud_exist)
                itens_detalhes = {}

                for idx_item, it in enumerate(CHECKLIST_ITEMS, start=1):
                    st.markdown(f"##### Bloco {idx_item}: {it['titulo']}")
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
                    if escolha == "Não Conforme":
                        st.error("Item crítico identificado: requer plano de ação e acompanhamento.")
                    with st.container(border=True):
                        obs = st.text_area("Observação", value=itens_prev.get(it["chave"], {}).get("observacao", ""), key=f"aud_obs_{sel.id}_{it['chave']}")
                        reaval_padrao = parse_data_flex(itens_prev.get(it["chave"], {}).get("data_reavaliacao", "")) or date.today()
                        cda, cup = st.columns([1,1])
                        sem_reavaliacao = cda.checkbox(
                            "Sem data de reavaliação",
                            value=(itens_prev.get(it["chave"], {}).get("data_reavaliacao") in (None, "")),
                            key=f"aud_sem_reav_{sel.id}_{it['chave']}"
                        )
                        data_reavaliacao = cda.date_input(
                            "Data de reavaliação (opcional)",
                            value=reaval_padrao,
                            key=f"aud_reav_{sel.id}_{it['chave']}",
                            disabled=sem_reavaliacao
                        )
                        up_item = cup.file_uploader("Anexar evidência do item", type=["pdf","jpg","jpeg","png"], key=f"aud_item_up_{sel.id}_{it['chave']}")

                        anexos_item_prev = itens_prev.get(it["chave"], {}).get("anexos", []) or []
                        novos_anexos = []
                        if up_item is not None:
                            novos_anexos.append(salvar_arquivo(up_item, "uploads/auditorias_itens", f"{sel.id}_{it['chave']}"))

                        itens_detalhes[it["chave"]] = {
                            "status": escolha,
                            "observacao": (obs or "").strip() or None,
                            "data_reavaliacao": None if sem_reavaliacao else data_reavaliacao.isoformat(),
                            "anexos": anexos_item_prev + novos_anexos,
                        }

                total_itens = len(CHECKLIST_ITEMS)
                respondidos = len([v for v in respostas_form.values() if v is not None])
                progresso = int((respondidos / total_itens) * 100) if total_itens else 0
                st.progress(progresso, text=f"Progresso da auditoria: {progresso}%")

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
                        "itens_detalhes": itens_detalhes,
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
                    criticos = [k for k, v in itens_detalhes.items() if v.get("status") == "Não Conforme"]
                    fortes = [k for k, v in itens_detalhes.items() if v.get("status") == "Conforme"]
                    st.success(f"IQA: {iqa:.1f}% — {regra['classe']} | Reavaliação: {regra['reavaliacao']} | Ação: {regra['acao']}")
                    st.markdown("#### Resumo da auditoria")
                    st.markdown(f"- **Pontos fortes:** {len(fortes)} itens conformes")
                    st.markdown(f"- **Pontos frágeis:** {len(criticos)} itens não conformes")
                    st.markdown(f"- **Itens críticos:** {', '.join(criticos) if criticos else 'Nenhum'}")
                    st.markdown(f"- **Exigem plano de ação:** {'Sim' if criticos else 'Não'}")
                    st.markdown(f"- **Recomendação de reavaliação:** {regra['reavaliacao']}")
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
                    itens = r.get("itens_detalhes", {}) or {}
                    if itens:
                        st.markdown("**Detalhamento por item auditado:**")
                        for item in CHECKLIST_ITEMS:
                            det = itens.get(item["chave"]) or {}
                            with st.expander(item["titulo"]):
                                st.write(f"Status: {det.get('status','-')}")
                                st.write(f"Observação: {det.get('observacao') or '-'}")
                                st.write(f"Reavaliação: {det.get('data_reavaliacao') or '-'}")
                                for arq in det.get("anexos", []) or []:
                                    exibir_preview_arquivo(arq, None)
            # Planos de Ação
            with tabs[3]:
                st.subheader("Planos de Ação")

                with st.form(f"form_plano_{sel.id}"):
                    descricao = st.text_area("Descrição da ação")
                    responsavel = st.text_input("Responsável")
                    prazo = st.date_input("Prazo", value=date.today())
                    enviar = st.form_submit_button("Criar ação")

                if enviar:
                    if not descricao.strip():
                        st.error("Descreva a ação.")
                    else:
                        with SessionLocal() as db:
                            plano = PlanoAcao(
                                fornecedor_id=sel.id,
                                descricao=descricao.strip(),
                                responsavel=responsavel.strip() or None,
                                data_inicio=date.today(),
                                data_fim=prazo,
                                status=PlanoStatusEnum.andamento,
                                evidencias=[],
                                atualizacoes=[],
                                updated_by=st.session_state.usuario
                            )
                            db.add(plano)
                            db.commit()
                            st.success("Ação criada com sucesso.")
                            _safe_rerun()

                st.markdown("#### Ações cadastradas")
                if not sel.planos_acao:
                    st.info("Nenhuma ação cadastrada.")
                else:
                    acoes_ordenadas = sorted(sel.planos_acao, key=lambda x: x.data_fim or date.max)
                    for p in acoes_ordenadas:
                        with st.container(border=True):
                            st.write(f"**Descrição:** {p.descricao}")
                            st.write(f"**Responsável:** {p.responsavel or '-'}")
                            st.write(f"**Prazo:** {p.data_fim or '-'}")

                            novo_desc = st.text_area("Descrição da ação", value=p.descricao or "", key=f"pl_desc_{p.id}")
                            c1, c2 = st.columns(2)
                            novo_resp = c1.text_input("Responsável", value=p.responsavel or "", key=f"pl_resp_{p.id}")
                            novo_prazo = c2.date_input("Prazo", value=p.data_fim, key=f"pl_prazo_{p.id}")

                            if st.button("Salvar ação", key=f"pl_save_{p.id}"):
                                if not novo_desc.strip():
                                    st.error("Descrição da ação é obrigatória.")
                                else:
                                    with SessionLocal() as db:
                                        plano_db = db.query(PlanoAcao).filter(PlanoAcao.id == p.id).first()
                                        plano_db.descricao = novo_desc.strip()
                                        plano_db.responsavel = novo_resp.strip() or None
                                        plano_db.data_fim = novo_prazo
                                        plano_db.updated_by = st.session_state.usuario
                                        db.commit()
                                    st.success("Ação atualizada.")
                                    _safe_rerun()
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
                            novo = Contrato(
                                fornecedor_id=sel.id,
                                arquivo=caminho,
                                data_assinatura=data_assinatura,
                                data_validade=data_validade,
                                updated_by=st.session_state.usuario
                            )
                            db.add(novo)
                            db.commit()
                        st.success("Contrato salvo!")
                        _safe_rerun()

                st.markdown("#### Contratos cadastrados")
                if sel.contratos:
                    for c in sorted(sel.contratos, key=lambda x: x.data_validade or date.max):
                        with st.container(border=True):
                            st.write(f"**Início:** {c.data_assinatura or '-'} | **Vencimento:** {c.data_validade or '-'} | **Status:** {status_contrato(c.data_validade)}")
                            if c.arquivo and Path(c.arquivo).exists():
                                with open(c.arquivo, "rb") as f:
                                    dados = f.read()
                                st.download_button("Baixar contrato", data=dados, file_name=os.path.basename(c.arquivo), key=f"contr_dl_{c.id}")
                            novo_arq = st.file_uploader("Substituir arquivo (opcional)", type=["pdf", "docx", "doc"], key=f"contr_up_{c.id}")
                            c1, c2 = st.columns(2)
                            novo_ini = c1.date_input("Data de início", value=c.data_assinatura, key=f"contr_ini_{c.id}")
                            novo_val = c2.date_input("Data de vencimento", value=c.data_validade, key=f"contr_venc_{c.id}")
                            if st.button("Salvar alterações do contrato", key=f"contr_edit_{c.id}"):
                                if novo_val < novo_ini:
                                    st.error("Vencimento não pode ser anterior ao início.")
                                else:
                                    caminho = c.arquivo
                                    if novo_arq is not None:
                                        caminho = salvar_arquivo(novo_arq, "uploads/contratos", f"{sel.id}_contrato")
                                    with SessionLocal() as db:
                                        contrato_db = db.query(Contrato).filter(Contrato.id == c.id).first()
                                        contrato_db.arquivo = caminho
                                        contrato_db.data_assinatura = novo_ini
                                        contrato_db.data_validade = novo_val
                                        contrato_db.updated_by = st.session_state.usuario
                                        db.commit()
                                    st.success("Contrato atualizado com sucesso.")
                                    _safe_rerun()
                else:
                    st.info("Nenhum contrato anexado.")

            # MTRs do fornecedor
            with tabs[5]:
                st.subheader("MTRs do fornecedor")
                with SessionLocal() as db:
                    mtrs_visiveis = mtrs_do_fornecedor_query(db, sel.id).order_by(MTR.id.desc()).all()

                if not mtrs_visiveis:
                    st.info("Nenhuma MTR associada ao fornecedor.")
                else:
                    head = st.columns([1.0, 1.0, 1.4, 1.0, 1.2, 0.8])
                    head[0].markdown("**Número da MTR**")
                    head[1].markdown("**Data**")
                    head[2].markdown("**Tipo de resíduo**")
                    head[3].markdown("**Quantidade (kg)**")
                    head[4].markdown("**Tempo MTR → CDF**")
                    head[5].markdown("**Arquivo**")
                    for m in mtrs_visiveis:
                        row = st.columns([1.0, 1.0, 1.4, 1.0, 1.2, 0.8])
                        row[0].write(m.numero_mtr or "-")
                        row[1].write(m.destinador_data_recebimento or "-")
                        row[2].write(m.codigo_ibama_denom or "-")
                        row[3].write(f"{m.qtd_kg or 0.0:.1f}")
                        dias_mtr_cdf = calcular_tempo_mtr_cdf(m)
                        row[4].write("-" if dias_mtr_cdf is None else f"{dias_mtr_cdf} dias")
                        if m.arquivo and Path(m.arquivo).exists():
                            with open(m.arquivo, "rb") as f:
                                arquivo_mtr = f.read()
                            row[5].download_button("Baixar", data=arquivo_mtr, file_name=os.path.basename(m.arquivo), key=f"mtr_vis_dl_{m.id}")
                        else:
                            row[5].caption("-")


            with tabs[6]:
                st.subheader("Pendências e histórico operacional")
                with SessionLocal() as db:
                    pendencias = [p for p in build_pendencias(db, site_logado, acesso_corporativo) if p["Fornecedor"] == sel.nome]
                if not pendencias:
                    st.success("Fornecedor sem pendências prioritárias no momento.")
                else:
                    if HAVE_PANDAS:
                        df_p = pd.DataFrame(pendencias).sort_values(["Prioridade", "Tipo"], ascending=[False, True])
                        st.dataframe(df_p[["Tipo", "Item", "Criticidade", "Origem"]], use_container_width=True, hide_index=True)
                    else:
                        for p_item in sorted(pendencias, key=lambda x: x["Prioridade"], reverse=True):
                            st.markdown(f"- **{p_item['Tipo']}** | {p_item['Item']} | {p_item['Criticidade']}")


# ---- Página Contratos (lista geral) ----
if menu=="Contratos":
    if st.session_state.role not in ("Admin","Auditor"):
        st.error("Acesso restrito.")
        st.stop()
    render_page_header("Gestão de Contratos", "Acompanhe vigências, vencimentos e arquivos contratuais dos fornecedores.")
    with SessionLocal() as db:
        q = db.query(Contrato, Fornecedor).join(Fornecedor, Contrato.fornecedor_id == Fornecedor.id)
        contratos = q.all()

    st.markdown("### Lista geral de contratos cadastrados")
    if not contratos:
        st.info("Nenhum contrato cadastrado.")
    else:
        fornecedores_opts = ["Todos"] + sorted({f.nome for _, f in contratos})
        status_opts = ["Todos", "Vencido", "Próximo do vencimento", "Vigente"]
        fc1, fc2 = st.columns(2)
        filtro_fornecedor = fc1.selectbox("Filtro por fornecedor", fornecedores_opts, key="ctr_forn")
        filtro_status = fc2.selectbox("Filtro por status", status_opts, key="ctr_status")

        rows = []
        for c, f in contratos:
            st_status = status_contrato(c.data_validade)
            if filtro_fornecedor != "Todos" and f.nome != filtro_fornecedor:
                continue
            if filtro_status != "Todos" and st_status != filtro_status:
                continue
            rows.append((c, f, st_status, criticidade_rank(st_status)))
        rows = sorted(rows, key=lambda x: (-x[3], x[0].data_validade or date.max))

        head = st.columns([1.5, 1.0, 1.0, 1.0, 1.1, 0.7])
        head[0].markdown("**Fornecedor**")
        head[1].markdown("**Data de início**")
        head[2].markdown("**Data de vencimento**")
        head[3].markdown("**Última atualização**")
        head[4].markdown("**Status / criticidade**")
        head[5].markdown("**Ação**")

        for c, f, st_status, rank in rows:
            row = st.columns([1.5, 1.0, 1.0, 1.0, 1.1, 0.7])
            row[0].write(f.nome)
            row[1].write(c.data_assinatura or "-")
            row[2].write(c.data_validade or "-")
            row[3].write(c.updated_at or "-")
            row[4].markdown(status_badge(f"{st_status} ({criticidade_label(rank)})"), unsafe_allow_html=True)
            if c.arquivo and Path(c.arquivo).exists():
                with open(c.arquivo, "rb") as arq:
                    row[5].download_button("Ver detalhes", data=arq.read(), file_name=os.path.basename(c.arquivo), key=f"contr_geral_dl_{c.id}")
            else:
                row[5].caption("-")

# ---- Página MTRs (importação com revisão e confirmação) ----
if menu=="MTRs":
    if st.session_state.role not in ("Admin","Auditor"):
        st.error("Acesso restrito."); st.stop()
    render_page_header("Controle de MTRs por Fornecedor", "Gerencie importações de MTR, associação de CDF e performance operacional por site.")

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
        f_fornecedor = ["Todos"] + sorted({(m.fornecedor.nome if m.fornecedor else "-") for m in mtrs_all})
        f_site = ["Todos"] + sorted({(m.site.value if m.site else "-") for m in mtrs_all})
        f_status = ["Todos", "Aprovado", "Pendente"]
        mf1, mf2, mf3 = st.columns(3)
        filtro_fornecedor = mf1.selectbox("Filtro por fornecedor", f_fornecedor, key="mtr_f_forn")
        filtro_site = mf2.selectbox("Filtro por site", f_site, key="mtr_f_site")
        filtro_status = mf3.selectbox("Filtro por status", f_status, key="mtr_f_status")

        filtradas = []
        for m in mtrs_all:
            nome_f = m.fornecedor.nome if m.fornecedor else "-"
            site_m = m.site.value if m.site else "-"
            st_m = "Aprovado" if (m.cdf_count or 0) > 0 else "Pendente"
            rank = 3 if st_m == "Pendente" else 1
            if filtro_fornecedor != "Todos" and nome_f != filtro_fornecedor:
                continue
            if filtro_site != "Todos" and site_m != filtro_site:
                continue
            if filtro_status != "Todos" and st_m != filtro_status:
                continue
            filtradas.append((m, st_m, rank))
        filtradas = sorted(filtradas, key=lambda x: (-x[2], -(calcular_tempo_mtr_cdf(x[0]) or -1)))

        head = st.columns([0.9, 1.2, 0.6, 1.0, 0.9, 0.8, 0.6, 0.6, 0.4])
        head[0].markdown("**MTR nº**")
        head[1].markdown("**Fornecedor**")
        head[2].markdown("**Site**")
        head[3].markdown("**Status CDF**")
        head[4].markdown("**Tempo MTR → CDF**")
        head[5].markdown("**Última atualização**")
        head[6].markdown("**MTR**")
        head[7].markdown("**CDF**")
        head[8].markdown("**Ação**")

        for m, st_m, rank in filtradas:
            cols = st.columns([0.9, 1.2, 0.6, 1.0, 0.9, 0.8, 0.6, 0.6, 0.4])
            cols[0].write(m.numero_mtr or "-")
            cols[1].write(m.fornecedor.nome if m.fornecedor else "-")
            cols[2].write(m.site.value if m.site else "-")
            cols[3].markdown(status_badge(f"{st_m} ({criticidade_label(rank)})"), unsafe_allow_html=True)
            dias_mtr_cdf = calcular_tempo_mtr_cdf(m)
            cols[4].write("-" if dias_mtr_cdf is None else f"{dias_mtr_cdf} dias")
            cols[5].write(m.updated_at or "-")
            if m.arquivo and Path(m.arquivo).exists():
                with open(m.arquivo, "rb") as f:
                    arquivo_mtr = f.read()
                cols[6].download_button("Baixar", data=arquivo_mtr, file_name=os.path.basename(m.arquivo), key=f"mtr_geral_dl_{m.id}")
            else:
                cols[6].caption("-")

            primeiro_cdf = m.cdfs[0] if m.cdfs else None
            if primeiro_cdf and primeiro_cdf.arquivo and Path(primeiro_cdf.arquivo).exists():
                with open(primeiro_cdf.arquivo, "rb") as f:
                    arquivo_cdf = f.read()
                nome_cdf = os.path.basename(primeiro_cdf.arquivo)
                label_cdf = "Baixar" if (m.cdf_count or 0) <= 1 else f"Baixar 1º/{m.cdf_count}"
                cols[7].download_button(label_cdf, data=arquivo_cdf, file_name=nome_cdf, key=f"cdf_geral_dl_{m.id}")
            else:
                cols[7].button("Sem CDF", key=f"cdf_disabled_{m.id}", disabled=True, use_container_width=True)

            if cols[8].button("Ver detalhes", key=f"view_mtr_{m.id}"):
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
        st.markdown("### Cadastro de MTR")
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


# ---- Central de Pendências ----
if menu=="Central de Pendências":
    if st.session_state.role not in ("Admin", "Auditor", "Leitor"):
        st.error("Acesso restrito.")
        st.stop()
    render_page_header("Central de Pendências", "Página operacional única para priorização e tratativa diária.")
    with SessionLocal() as db:
        pendencias = build_pendencias(db, site_logado, acesso_corporativo)

    if not pendencias:
        st.success("Nenhuma pendência encontrada para os filtros atuais.")
    else:
        if HAVE_PANDAS:
            df = pd.DataFrame(pendencias)
            f1, f2, f3, f4 = st.columns(4)
            op_site = ["Todos"] + sorted(df["Site"].dropna().astype(str).unique().tolist())
            op_forn = ["Todos"] + sorted(df["Fornecedor"].dropna().astype(str).unique().tolist())
            op_tipo = ["Todos"] + sorted(df["Tipo"].dropna().astype(str).unique().tolist())
            op_crit = ["Todos", "Alta", "Média", "Baixa"]
            v_site = f1.selectbox("Filtro por site", op_site)
            v_forn = f2.selectbox("Filtro por fornecedor", op_forn)
            v_tipo = f3.selectbox("Filtro por tipo de pendência", op_tipo)
            v_crit = f4.selectbox("Filtro por criticidade", op_crit)

            if v_site != "Todos":
                df = df[df["Site"] == v_site]
            if v_forn != "Todos":
                df = df[df["Fornecedor"] == v_forn]
            if v_tipo != "Todos":
                df = df[df["Tipo"] == v_tipo]
            if v_crit != "Todos":
                df = df[df["Criticidade"] == v_crit]

            df = df.sort_values(["Prioridade", "Tipo"], ascending=[False, True])

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Pendências totais", int(len(df)))
            c2.metric("Críticas", int((df["Criticidade"] == "Alta").sum()))
            c3.metric("Médias", int((df["Criticidade"] == "Média").sum()))
            c4.metric("Baixas", int((df["Criticidade"] == "Baixa").sum()))

            st.dataframe(df[["Fornecedor", "Site", "Tipo", "Item", "Criticidade", "Origem"]], use_container_width=True, hide_index=True)
        else:
            st.warning("Pandas indisponível para visualização tabular avançada.")
            for p_item in pendencias:
                st.markdown(f"- **{p_item['Fornecedor']}** | {p_item['Tipo']} | {p_item['Criticidade']}")

# ---- Admin (Usuários) ----
if menu=="Meu Portal":
    if st.session_state.role!="Fornecedor":
        st.error("Acesso restrito ao perfil Fornecedor."); st.stop()
    fornecedor_id = st.session_state.fornecedor_id
    if not fornecedor_id:
        st.error("Seu usuário não está vinculado a um fornecedor. Contate o administrador."); st.stop()

    with SessionLocal() as db:
        sel = db.query(Fornecedor).options(
            joinedload(Fornecedor.documentos),
            joinedload(Fornecedor.auditoria),
        ).filter(Fornecedor.id == fornecedor_id).first()
    if not sel:
        st.error("Fornecedor vinculado não encontrado."); st.stop()

    render_page_header("Portal do Fornecedor", "Acompanhe sua situação de compliance e mantenha seus documentos atualizados.")
    render_section_title("Minha auditoria")
    score = sel.auditoria.score if sel.auditoria else None
    c1, c2 = st.columns(2)
    with c1:
        render_kpi_card("Score de auditoria", str(score if score is not None else "Sem auditoria"))
    with c2:
        render_kpi_card("Status da auditoria", auditoria_status(score))

    if sel.auditoria and isinstance(sel.auditoria.respostas, dict):
        respostas = sel.auditoria.respostas
        regra = respostas.get("regra_aplicada", {}) or {}
        st.markdown(
            f"**Classificação:** {regra.get('classe','-')}  \n"
            f"**Condição:** {regra.get('condicionamento','-')}  \n"
            f"**Reavaliação:** {regra.get('reavaliacao','-')}"
        )
        if respostas.get("itens_detalhes"):
            with st.expander("Ver resultados detalhados da auditoria"):
                for item in CHECKLIST_ITEMS:
                    det = respostas["itens_detalhes"].get(item["chave"]) or {}
                    st.markdown(f"**{item['titulo']}**")
                    st.caption(
                        f"Status: {det.get('status','-')} | "
                        f"Reavaliação: {det.get('data_reavaliacao') or '-'} | "
                        f"Observação: {det.get('observacao') or '-'}"
                    )

    st.divider()
    render_section_title("Meus dados cadastrais")
    st.write(f"**Nome:** {sel.nome}")
    st.write(f"**CPF/CNPJ:** {formatar_cpf_cnpj(sel.cpf_cnpj)}")
    st.write(f"**Endereço:** {sel.endereco or '-'}")
    st.write(f"**Telefone:** {sel.telefone or '-'}")

    st.divider()
    render_section_title("Meus documentos")
    docs_ordenados = sorted(sel.documentos, key=lambda x: (x.tipo or "", x.data_validade or date.max))
    if not docs_ordenados:
        st.info("Nenhum documento cadastrado para seu fornecedor.")
    else:
        head = st.columns([1.8, 1.0, 1.0, 1.0, 0.8])
        head[0].markdown("**Documento**")
        head[1].markdown("**Início**")
        head[2].markdown("**Validade**")
        head[3].markdown("**Status**")
        head[4].markdown("**Arquivo**")
        for d in docs_ordenados:
            row = st.columns([1.8, 1.0, 1.0, 1.0, 0.8])
            row[0].write(d.tipo)
            row[1].write(str(d.data_inicio or "-"))
            row[2].write("Sem validade" if d.sem_validade else str(d.data_validade or "-"))
            row[3].markdown(status_badge("Vigente" if d.sem_validade else status_documento(d.data_validade)), unsafe_allow_html=True)
            if d.arquivo and Path(d.arquivo).exists():
                with open(d.arquivo, "rb") as f:
                    row[4].download_button("Baixar", data=f.read(), file_name=os.path.basename(d.arquivo), key=f"forn_doc_dl_{d.id}")
            else:
                row[4].caption("-")

    st.markdown("#### Enviar novo documento")
    tipos_existentes = {d.tipo for d in sel.documentos}
    tipos_disponiveis = [t for t in TIPOS_DOCUMENTOS_OBRIGATORIOS if t not in tipos_existentes]
    with st.form("forn_novo_doc"):
        tipo_novo = st.selectbox("Tipo", tipos_disponiveis if tipos_disponiveis else TIPOS_DOCUMENTOS_OBRIGATORIOS)
        novo_up = st.file_uploader("Arquivo", type=["pdf", "jpg", "png", "jpeg"])
        novo_ini = st.date_input("Início de vigência", value=date.today())
        novo_sem_validade = st.checkbox("Documento sem data de validade")
        novo_val = st.date_input("Validade", value=date.today(), disabled=novo_sem_validade)
        enviar_novo = st.form_submit_button("Salvar novo documento")
    if enviar_novo:
        if not novo_up:
            st.error("Envie um arquivo para cadastrar o documento.")
        elif tipo_novo in tipos_existentes:
            st.error("Esse tipo já existe. Use a opção de substituição de versão abaixo.")
        elif (not novo_sem_validade) and novo_val < novo_ini:
            st.error("Validade não pode ser anterior ao início.")
        else:
            caminho = salvar_arquivo(novo_up, "uploads/documentos", f"{sel.id}_{tipo_novo}")
            with SessionLocal() as db:
                db.add(Documento(
                    fornecedor_id=sel.id,
                    tipo=tipo_novo,
                    arquivo=caminho,
                    data_inicio=novo_ini,
                    data_validade=None if novo_sem_validade else novo_val,
                    sem_validade=1 if novo_sem_validade else 0,
                    updated_by=st.session_state.usuario
                ))
                db.commit()
            st.success("Documento enviado com sucesso!")
            _safe_rerun()

    st.markdown("#### Atualizar documento existente (nova versão)")
    if not docs_ordenados:
        st.caption("Cadastre ao menos um documento para habilitar a atualização de versão.")
    else:
        with st.form("forn_replace_doc"):
            doc_opts = [f"{d.id} — {d.tipo}" for d in docs_ordenados]
            doc_sel = st.selectbox("Documento", doc_opts)
            up_replace = st.file_uploader("Nova versão do arquivo", type=["pdf", "jpg", "png", "jpeg"])
            enviar_replace = st.form_submit_button("Substituir versão")
        if enviar_replace:
            if up_replace is None:
                st.error("Envie o novo arquivo para substituir a versão atual.")
            else:
                doc_id = int(doc_sel.split(" — ", 1)[0])
                caminho = salvar_arquivo(up_replace, "uploads/documentos", f"{sel.id}_{doc_id}_v2")
                with SessionLocal() as db:
                    doc_db = db.query(Documento).filter(Documento.id == doc_id, Documento.fornecedor_id == sel.id).first()
                    if not doc_db:
                        st.error("Documento não encontrado.")
                    else:
                        doc_db.arquivo = caminho
                        doc_db.updated_by = st.session_state.usuario
                        db.commit()
                        st.success("Versão do documento atualizada com sucesso!")
                        _safe_rerun()

# ---- Admin (Usuários) ----
if menu=="Admin (Usuários)":
    if st.session_state.role!="Admin":
        st.error("Apenas Admin pode acessar esta página."); st.stop()
    render_page_header("Administração", "Gerencie usuários e exportações de dados da plataforma.")
    with SessionLocal() as db: usuarios=db.query(User).all()
    render_section_title("Usuários")
    for u in usuarios:
        vinculo = f" — fornecedor_id {u.fornecedor_id}" if u.fornecedor_id else ""
        st.write(f"- **{u.username}** — {u.role.value} — site {u.site.value}{vinculo}")
    render_section_title("Criar novo usuário")
    with SessionLocal() as db:
        fornecedores_opts = db.query(Fornecedor).order_by(Fornecedor.nome.asc()).all()
    with st.form("form_user"):
        username=st.text_input("Usuário").strip()
        password=st.text_input("Senha", type="password").strip()
        role=st.selectbox("Papel", [RoleEnum.admin.value, RoleEnum.auditor.value, RoleEnum.leitor.value, RoleEnum.fornecedor.value])
        site=st.selectbox("Site", TODOS_SITES, index=0)
        fornecedor_labels = ["Nenhum"] + [f"{f.id} — {f.nome}" for f in fornecedores_opts]
        fornecedor_label = st.selectbox("Fornecedor vinculado (obrigatório para papel Fornecedor)", fornecedor_labels, index=0)
        enviar=st.form_submit_button("Criar")
    if enviar:
        if not username or not password: st.error("Preencha usuário e senha.")
        else:
            with SessionLocal() as db:
                if get_user_by_username(db, username): st.error("Usuário já existe.")
                else:
                    fornecedor_id = None if fornecedor_label == "Nenhum" else int(fornecedor_label.split(" — ", 1)[0])
                    if role == RoleEnum.fornecedor.value and not fornecedor_id:
                        st.error("Para papel Fornecedor, selecione um fornecedor vinculado.")
                    else:
                        create_user(db, username, password, RoleEnum(role), SiteEnum(site), fornecedor_id=fornecedor_id); st.success("Usuário criado com sucesso!"); _safe_rerun()

    render_section_title("Exportar dados (Excel)")
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
    st.session_state.logado=False; st.session_state.usuario=None; st.session_state.role=None; st.session_state.site=None; st.session_state.fornecedor_id=None
    st.session_state.sel_forn_id=None; _safe_rerun()
