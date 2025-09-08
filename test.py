# app.py — Streamlit único com:
# - Importação/parse de MTR robusto (todas as páginas + fallbacks)
# - Tabela "Fatores de Emissão" editável (st.data_editor + salvar alterações + excluir)
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

from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Date, ForeignKey, Enum,
    UniqueConstraint, JSON, func, text
)
from sqlalchemy.orm import sessionmaker, declarative_base, relationship, joinedload, Session
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

def exibir_preview_arquivo(caminho:str, mime_type:str|None):
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

# =========================
#          MODELOS
# =========================
class RoleEnum(str, enum.Enum):
    admin="Admin"; auditor="Auditor"; leitor="Leitor"

class User(Base):
    __tablename__="users"
    id = Column(Integer, primary_key=True)
    username = Column(String(150), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(RoleEnum), nullable=False, default=RoleEnum.auditor)
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
    respostas = Column(JSON, nullable=False, default={})
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
    # Escopo 3
    tipo_residuo = Column(String)
    destinacao = Column(String)
    fator_tco2e_por_ton = Column(Float)
    emissoes_tco2e = Column(Float)
    cdf_count = Column(Integer, default=0)
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

# ===== Fatores de Emissão (tabela SQL editável) =====
class FatorEmissao(Base):
    __tablename__="fatores_emissao"
    id = Column(Integer, primary_key=True)
    tipo_residuo = Column(String, nullable=False)
    destinacao = Column(String, nullable=False)
    fator_tco2e_por_ton = Column(Float, nullable=False)
    fonte = Column(String)
    ano_ref = Column(Integer)
    __table_args__=(UniqueConstraint('tipo_residuo','destinacao',name='uq_tipo_destinacao'),)

# =========================
#     SEGURANÇA / USUÁRIO
# =========================
def hash_password(p:str)->str: return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()
def verify_password(p:str,h:str)->bool:
    try: return bcrypt.checkpw(p.encode(), h.encode())
    except Exception: return False

def get_user_by_username(db:Session, username:str)->User|None:
    return db.query(User).filter(User.username==username).first()

def create_user(db:Session, username:str, password:str, role:RoleEnum)->User:
    u=User(username=username, password_hash=hash_password(password), role=role)
    db.add(u); db.commit(); db.refresh(u); return u

# =========================
#      MIGRAÇÃO/SEED
# =========================
def run_light_migrations():
    Base.metadata.create_all(bind=engine)

def seed_users_and_factors():
    with SessionLocal() as db:
        if not get_user_by_username(db, "Eduardo"):
            create_user(db, "Eduardo", "Capitu", RoleEnum.admin)
    SEED = {
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
    with SessionLocal() as db:
        cnt = db.query(func.count(FatorEmissao.id)).scalar() or 0
        if cnt == 0:
            for tipo, dests in SEED.items():
                for dest, fator in dests.items():
                    db.add(FatorEmissao(
                        tipo_residuo=tipo,
                        destinacao=dest,
                        fator_tco2e_por_ton=float(fator),
                        fonte="Seed inicial",
                        ano_ref=None
                    ))
            db.commit()

# =========================
#   FATORES (helpers DB)
# =========================
def listar_tipos_residuo(db:Session)->list[str]:
    q = db.query(FatorEmissao.tipo_residuo).distinct().order_by(FatorEmissao.tipo_residuo.asc()).all()
    tipos=[r[0] for r in q]
    if "Misto/Outros" not in tipos: tipos.append("Misto/Outros")
    return tipos

def listar_destinos_para_tipo(db:Session, tipo:str)->list[str]:
    q = db.query(FatorEmissao.destinacao).filter(FatorEmissao.tipo_residuo==tipo).distinct().order_by(FatorEmissao.destinacao.asc()).all()
    dests=[r[0] for r in q]
    if not dests:
        q2 = db.query(FatorEmissao.destinacao).filter(FatorEmissao.tipo_residuo=="Misto/Outros").distinct().all()
        dests=[r[0] for r in q2]
    return dests

def obter_fator(db:Session, tipo:str, destino:str)->float|None:
    fe = db.query(FatorEmissao).filter(
        FatorEmissao.tipo_residuo==tipo,
        FatorEmissao.destinacao==destino
    ).first()
    return fe.fator_tco2e_por_ton if fe else None

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

def extract_pdf_data(pdf_path:str)->dict:
    """
    Parser mais tolerante: usa o texto completo do PDF; tenta regex principal
    e, em falha, tenta alternativas para quantidade/unidade.
    """
    dados={}
    try:
        text = _load_pdf_text_all_pages(pdf_path)
        # --- MTR nº
        mtr_match = re.search(r"(?:MTR\s*n[ºo]|MTR\s*-\s*n[ºo]|MTR\s*número)\s*[:\-]?\s*(\d+)", text, flags=re.IGNORECASE)
        dados["MTR - Número"] = (mtr_match.group(1).strip() if mtr_match else "N/A")

        # --- Gerador
        g0=text.find("Identificação do Gerador"); g1=text.find("Observações do Gerador")
        generator = text[g0:g1] if (g0!=-1 and g1!=-1 and g1>g0) else ""
        def _find(pattern, src, flags=0):
            m = re.search(pattern, src, flags)
            return m.group(1).strip() if m else None

        dados["Gerador - Razão Social"] = _find(r"Razão Social:\s*(.*?)\s*-\s*\d+\s*CPF/CNPJ:", generator) or _find(r"Razão Social:\s*(.*)", generator)
        dados["Gerador - CPF/CNPJ"] = _find(r"CPF/CNPJ:\s*([\d\.\-\/]+)", generator)
        dados["Gerador - Data da emissão"] = _find(r"Data da emissão:\s*(\d{2}/\d{2}/\d{4})", generator)
        dados["Gerador - Município"] = _find(r"Município:\s*(.*?)\s*UF:", generator)
        dados["Gerador - UF"] = _find(r"UF:\s*([A-Z]{2})", generator)

        # --- Transportador
        t0=text.find("Identificação do Transportador"); t1=text.find("Nome do Motorista")
        transport = text[t0:t1] if (t0!=-1 and t1!=-1 and t1>t0) else ""
        dados["Transportador - Razão Social"] = _find(r"Razão Social:\s*(.*?)\s*-\s*\d+\s*CPF/CNPJ:", transport) or _find(r"Razão Social:\s*(.*)", transport)
        dados["Transportador - CPF/CNPJ"] = _find(r"CPF/CNPJ:\s*([\d\.\-\/]+)", transport)
        dados["Transportador - Data do transporte"] = _find(r"Data do transporte:\s*(\d{2}/\d{2}/\d{4})", transport)

        # --- Destinador
        d0=text.find("Identificação do Destinador"); d1=text.find("Identificação dos Resíduos")
        destin = text[d0:d1] if (d0!=-1 and d1!=-1 and d1>d0) else ""
        dados["Destinador - Razão Social"] = _find(r"Razão Social:\s*(.*?)\s*-\s*\d+\s*CPF/CNPJ:", destin) or _find(r"Razão Social:\s*(.*)", destin)
        dados["Destinador - CPF/CNPJ"] = _find(r"CPF/CNPJ:\s*([\d\.\-\/]+)", destin)
        dados["Destinador - Data do recebimento"] = _find(r"Data do recebimento:\s*(\d{2}/\d{2}/\d{4})", destin)

        # --- Resíduos (linha 1 padrão + fallbacks)
        waste_start = text.find("Identificação dos Resíduos")
        waste_info_raw = text[waste_start:] if waste_start!=-1 else text

        # padrão principal (seu regex original)
        m = re.search(
            r"^1\s+([\d-]+)-(.+?)\s+([A-Z]+)\s+CLASSE\s+(.+?)\s+([0-9\.,]+)\s+([A-Z]+)\s+(.+)$",
            waste_info_raw, re.MULTILINE
        )
        if not m:
            # fallback simples: “Qtde: 1.234,56 KG” em algum lugar
            m_qty = re.search(r"Qtde[:\s]+([0-9\.\,]+)\s*([A-Za-z]+)", waste_info_raw)
            if m_qty:
                dados["Resíduos - Qtde"] = m_qty.group(1).strip()
                dados["Resíduos - Unidade"] = m_qty.group(2).strip()
            else:
                # outro fallback: “Peso ... 1.234,56 KG”
                m_qty2 = re.search(r"Peso[:\s]+([0-9\.\,]+)\s*([A-Za-z]+)", waste_info_raw, re.IGNORECASE)
                if m_qty2:
                    dados["Resíduos - Qtde"] = m_qty2.group(1).strip()
                    dados["Resíduos - Unidade"] = m_qty2.group(2).strip()
        else:
            codigo_completo = f"{m.group(1)}-{m.group(2).strip()}"
            dados["Resíduos - Código IBAMA e Denominação"] = codigo_completo[:6]
            dados["Resíduos - Qtde"] = m.group(5).strip()
            dados["Resíduos - Unidade"] = m.group(6).strip()

        # normaliza nulos
        for k in ("Resíduos - Qtde", "Resíduos - Unidade", "Resíduos - Código IBAMA e Denominação"):
            if k not in dados: dados[k] = ""

    except Exception as e:
        # Nunca quebra — retorna mínimo viável + erro no log do app
        st.error(f"Falha ao ler PDF (parser): {Path(pdf_path).name} — {e}")
        st.caption("Dica: verifique se o PDF possui texto (OCR) e formatação esperada.")
        dados.setdefault("MTR - Número", "N/A")
        for k in ("Gerador - Razão Social","Gerador - CPF/CNPJ","Gerador - Data da emissão","Gerador - Município","Gerador - UF",
                  "Transportador - Razão Social","Transportador - CPF/CNPJ","Transportador - Data do transporte",
                  "Destinador - Razão Social","Destinador - CPF/CNPJ","Destinador - Data do recebimento",
                  "Resíduos - Código IBAMA e Denominação","Resíduos - Qtde","Resíduos - Unidade"):
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
        "qtd_original": d.get("Resíduos - Qtde") or None,
        "und_original": und or None,
        "qtd_kg": qtd_kg,
        "dados_raw": d
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

# =========================
#      INICIALIZAÇÃO
# =========================
run_light_migrations()
seed_users_and_factors()

if "logado" not in st.session_state:
    st.session_state.logado=False; st.session_state.usuario=None; st.session_state.role=None
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
        ["Overview","Cadastrar Fornecedor","Visualizar Fornecedores","MTRs","Fatores de Emissão","Admin (Usuários)","Sair"]
    )
st.sidebar.title(f"Usuário: {st.session_state.usuario} ({st.session_state.role})")

# =========================
#        KPIs / HELPERS
# =========================
def documentos_status(docs)->tuple[int,int]:
    hoje=date.today(); limite=hoje+timedelta(days=30)
    vencidos=sum(1 for d in docs if d.data_validade and d.data_validade<hoje)
    a_vencer=sum(1 for d in docs if d.data_validade and hoje<=d.data_validade<=limite)
    return vencidos, a_vencer

def kpis_gerais(db:Session)->dict:
    total_fornecedores=db.query(Fornecedor).count()
    conformes=db.query(Auditoria).filter(Auditoria.classificado=="Conforme/Adequado").count()
    parcialmente=db.query(Auditoria).filter(Auditoria.classificado=="Parcialmente Conforme").count()
    nao_conformes=db.query(Auditoria).filter(Auditoria.classificado=="Não Conforme/Inadequado").count()
    forn_com_contrato=db.query(Fornecedor).join(Contrato).distinct().count()
    forn_sem_contrato=total_fornecedores - forn_com_contrato
    docs=db.query(Documento).all()
    vencidos,a_vencer=documentos_status(docs)
    mtr_total_kg=float(db.query(func.coalesce(func.sum(MTR.qtd_kg),0.0)).scalar() or 0.0)
    mtr_por_forn=db.query(Fornecedor.nome, func.coalesce(func.sum(MTR.qtd_kg),0.0))\
        .join(MTR, MTR.fornecedor_id==Fornecedor.id, isouter=True).group_by(Fornecedor.id).all()
    total_tco2e=float(db.query(func.coalesce(func.sum(MTR.emissoes_tco2e),0.0)).scalar() or 0.0)
    tco2e_por_forn=db.query(Fornecedor.nome, func.coalesce(func.sum(MTR.emissoes_tco2e),0.0))\
        .join(MTR, MTR.fornecedor_id==Fornecedor.id, isouter=True).group_by(Fornecedor.id).all()
    total_mtrs=int(db.query(MTR).count())
    mtrs_com_cdf=int(db.query(MTR).filter(MTR.cdf_count>0).count())
    return {
        "total_fornecedores": total_fornecedores,
        "conformes": conformes, "parcial": parcialmente, "nao_conformes": nao_conformes,
        "forn_com_contrato": forn_com_contrato, "forn_sem_contrato": forn_sem_contrato,
        "docs_vencidos": vencidos, "docs_a_vencer": a_vencer,
        "mtr_total_kg": mtr_total_kg, "mtr_por_forn":[(n,float(v or 0.0)) for n,v in mtr_por_forn],
        "total_tco2e": total_tco2e, "tco2e_por_forn":[(n,float(v or 0.0)) for n,v in tco2e_por_forn],
        "total_mtrs": total_mtrs, "mtrs_com_cdf": mtrs_com_cdf,
    }

# =========================
#           PÁGINAS
# =========================

# ---- Overview ----
if menu=="Overview":
    st.header("Resumo Geral dos Fornecedores")
    with SessionLocal() as db:
        k=kpis_gerais(db)

    fig_total = px.pie(
        names=["Conforme/Adequado","Parcialmente Conforme","Não Conforme/Inadequado"],
        values=[k["conformes"], k["parcial"], k["nao_conformes"]],
        title="Classificação da Auditoria (v2)",
        color=["Conforme/Adequado","Parcialmente Conforme","Não Conforme/Inadequado"],
        color_discrete_map={"Conforme/Adequado":"green","Parcialmente Conforme":"orange","Não Conforme/Inadequado":"red"},
    )
    fig_contrato = px.pie(
        names=["Com Contrato","Sem Contrato"], values=[k["forn_com_contrato"],k["forn_sem_contrato"]],
        title="Situação Contratual",
        color=["Com Contrato","Sem Contrato"],
        color_discrete_map={"Com Contrato":"green","Sem Contrato":"red"},
    )
    c1,c2=st.columns(2)
    with c1: st.plotly_chart(fig_total, use_container_width=True)
    with c2: st.plotly_chart(fig_contrato, use_container_width=True)

    def badge(label,val,good=True):
        color="#2e7d32" if good else "#c62828"; bg="#e8f5e9" if good else "#ffebee"
        return f"<div style='padding:10px;border-radius:8px;background:{bg};margin-bottom:8px;'><span style='color:{color};font-weight:600;'>{label}:</span><span style='margin-left:6px;color:#111;font-weight:700;'>{val}</span></div>"

    colA,colB,colC=st.columns(3)
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

    # kg por fornecedor
    st.markdown("### Kg destinados por fornecedor (MTR)")
    rows = [{"Fornecedor":n,"Kg_destinados":v} for n,v in k["mtr_por_forn"]]
    if HAVE_PANDAS and rows:
        df=pd.DataFrame(rows).sort_values("Kg_destinados", ascending=False)
        fig_bar=px.bar(df, x="Fornecedor", y="Kg_destinados", title="Total de kg por fornecedor (MTR)")
    else:
        xs=[r["Fornecedor"] for r in rows]; ys=[r["Kg_destinados"] for r in rows]
        fig_bar=go.Figure(go.Bar(x=xs,y=ys)); fig_bar.update_layout(title="Total de kg por fornecedor (MTR)")
    fig_bar.update_traces(marker_color="green")
    st.plotly_chart(fig_bar, use_container_width=True)

    # tCO2e por fornecedor
    st.markdown("### Emissões de Escopo 3 (resíduos) por fornecedor")
    rows = [{"Fornecedor":n,"tCO2e":v} for n,v in k["tco2e_por_forn"]]
    if HAVE_PANDAS and rows:
        df=pd.DataFrame(rows).sort_values("tCO2e", ascending=False)
        fig_em=px.bar(df, x="Fornecedor", y="tCO2e", title="tCO₂e por fornecedor (resíduos)")
    else:
        xs=[r["Fornecedor"] for r in rows]; ys=[r["tCO2e"] for r in rows]
        fig_em=go.Figure(go.Bar(x=xs,y=ys)); fig_em.update_layout(title="tCO₂e por fornecedor (resíduos)")
    fig_em.update_traces(marker_color="red")
    st.plotly_chart(fig_em, use_container_width=True)

# ---- Cadastrar Fornecedor ----
elif menu=="Cadastrar Fornecedor":
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
elif menu=="Visualizar Fornecedores":
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
                st.write(f"**Telefone:** {sel.telefone or '-'}")

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
                                    doc_db=db.query(Documento).get(d.id)
                                    doc_db.arquivo=caminho; doc_db.data_inicio=dt_ini; doc_db.data_validade=dt_val
                                    doc_db.updated_by=st.session_state.usuario
                                    db.commit(); st.success("Documento atualizado com sucesso!"); _safe_rerun()

                st.markdown("#### Adicionar novo documento")
                tipos_documentos=[
                    "Licença Ambiental de Operação",
                    "Alvará de Funcionamento",
                    "Comprovante de regularidade (CETESB ou órgão estadual)",
                    "Certificado de regularidade do IBAMA CTF/APP",
                    "Consulta de Área Contaminada"
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
                st.subheader("Auditoria (0–2 ponderada)")
                aud_exist=sel.auditoria; prev={}
                if aud_exist and isinstance(aud_exist.respostas, dict) and aud_exist.respostas.get("modelo")=="v2":
                    prev=aud_exist.respostas.get("respostas",{}) or {}
                respostas_form={}
                for area_key, meta in AREAS.items():
                    with st.expander(f"{meta['titulo']} — peso {int(meta['peso']*100)}%"):
                        for i, pergunta in enumerate(meta["perguntas"], start=1):
                            k=f"{area_key}.{i}"; default=int(prev.get(k,0)); idx=default if 0<=default<len(OPCOES) else 0
                            escolha=st.radio(pergunta, OPCOES, index=idx, key=f"aud_{sel.id}_{k}", horizontal=True)
                            respostas_form[k]=OPCOES.index(escolha)
                if st.button("Salvar Auditoria", key=f"save_aud_{sel.id}"):
                    score, area_pct = calcular_score_v2(respostas_form); classific = classificar(score)
                    payload={"modelo":"v2","respostas":respostas_form,"area_pct":area_pct}
                    with SessionLocal() as db:
                        aud=db.query(Auditoria).filter_by(fornecedor_id=sel.id).first()
                        if not aud:
                            aud=Auditoria(fornecedor_id=sel.id, respostas=payload, score=score, classificado=classific,
                                          updated_by=st.session_state.usuario); db.add(aud)
                        else:
                            aud.respostas=payload; aud.score=score; aud.classificado=classific; aud.updated_by=st.session_state.usuario
                        db.commit(); st.success(f"Auditoria salva. Score: {score}%. Classificação: {classific}"); _safe_rerun()

                with SessionLocal() as db:
                    aud_show=db.query(Auditoria).filter_by(fornecedor_id=sel.id).first()
                if aud_show and isinstance(aud_show.respostas, dict) and aud_show.respostas.get("modelo")=="v2":
                    area_pct=aud_show.respostas.get("area_pct",{})
                    if area_pct:
                        if HAVE_PANDAS:
                            df=pd.DataFrame({"Área":[AREAS[k]["titulo"] for k in AREAS.keys()],
                                             "% atendimento":[area_pct.get(k,0.0) for k in AREAS.keys()]})
                            fig_area=px.bar(df, x="Área", y="% atendimento", title="Atendimento por área (%)")
                        else:
                            nomes=[AREAS[k]["titulo"] for k in AREAS.keys()]
                            valores=[area_pct.get(k,0.0) for k in AREAS.keys()]
                            fig_area=px.bar(x=nomes, y=valores, labels={"x":"Área","y":"%"},
                                            title="Atendimento por área (%)")
                        fig_area.update_traces(marker_color="green"); st.plotly_chart(fig_area, use_container_width=True)
                    st.markdown(f"**Última auditoria:** Score {aud_show.score}%, Classificação: {aud_show.classificado}")

            # Planos — agora com painel de status
            with tabs[3]:
                st.subheader("Planos de Ação")
                # Form para criar novo
                with st.form(f"form_plano_{sel.id}"):
                    descricao=st.text_area("Descrição da Ação")
                    data_inicio=st.date_input("Início", value=date.today())
                    data_fim=st.date_input("Fim", value=date.today())
                    status=st.selectbox("Status", [PlanoStatusEnum.andamento.value, PlanoStatusEnum.concluido.value, PlanoStatusEnum.atrasado.value])
                    ev_upload=st.file_uploader("Anexar evidência (opcional)", type=["pdf","jpg","png","jpeg"])
                    enviar=st.form_submit_button("Adicionar Plano de Ação")
                evidencias=[]
                if enviar:
                    if not descricao: st.error("Descreva a ação.")
                    elif data_fim<data_inicio: st.error("Data final deve ser maior ou igual à data inicial.")
                    else:
                        if ev_upload is not None:
                            ev_path=salvar_arquivo(ev_upload, "uploads/evidencias", f"{sel.id}_plano"); evidencias.append(ev_path)
                        with SessionLocal() as db:
                            plano=PlanoAcao(fornecedor_id=sel.id, descricao=descricao.strip(),
                                            data_inicio=data_inicio, data_fim=data_fim, status=PlanoStatusEnum(status),
                                            evidencias=evidencias or [], updated_by=st.session_state.usuario)
                            db.add(plano); db.commit(); st.success("Plano de ação adicionado."); _safe_rerun()

                # Painel de ações existentes (com status editável)
                st.markdown("#### Ações cadastradas")
                if not sel.planos_acao:
                    st.info("Nenhuma ação cadastrada.")
                else:
                    hoje = date.today()
                    for p in sorted(sel.planos_acao, key=lambda x: x.data_fim):
                        atrasado = (p.status != PlanoStatusEnum.concluido and p.data_fim < hoje)
                        bg = "#ffebee" if atrasado else "#e8f5e9" if p.status==PlanoStatusEnum.concluido else "#fffde7"
                        with st.container():
                            st.markdown(f"<div style='padding:10px;border-radius:8px;background:{bg};'>"
                                        f"<b>{p.descricao}</b><br>"
                                        f"Início: {p.data_inicio} | Fim: {p.data_fim} | Status atual: <b>{p.status}</b>"
                                        f"</div>", unsafe_allow_html=True)
                            c1,c2,c3 = st.columns([0.35,0.35,0.3])
                            with c1:
                                novo_status = st.selectbox("Atualizar status:", [PlanoStatusEnum.andamento.value, PlanoStatusEnum.concluido.value, PlanoStatusEnum.atrasado.value],
                                                           index=[PlanoStatusEnum.andamento.value, PlanoStatusEnum.concluido.value, PlanoStatusEnum.atrasado.value].index(p.status.value),
                                                           key=f"pl_st_{p.id}")
                            with c2:
                                ev2 = st.file_uploader("Anexar nova evidência (opcional)", type=["pdf","jpg","png","jpeg"], key=f"pl_ev_{p.id}")
                            with c3:
                                if st.button("Salvar", key=f"pl_save_{p.id}"):
                                    with SessionLocal() as db:
                                        pp = db.query(PlanoAcao).get(p.id)
                                        pp.status = PlanoStatusEnum(novo_status)
                                        if ev2 is not None:
                                            ev_path = salvar_arquivo(ev2, "uploads/evidencias", f"{sel.id}_plano")
                                            lst = list(pp.evidencias or [])
                                            lst.append(ev_path)
                                            pp.evidencias = lst
                                        pp.updated_by = st.session_state.usuario
                                        db.commit()
                                    st.success("Plano atualizado."); _safe_rerun()
                            if p.evidencias:
                                st.caption("Evidências:")
                                for ev in p.evidencias:
                                    if Path(ev).exists(): exibir_preview_arquivo(ev, None)

            # Contratos
            with tabs[4]:
                st.subheader("Contratos")
                arquivo_contrato=st.file_uploader("Anexar Contrato", type=["pdf","docx","doc"], key=f"contr_{sel.id}")
                data_assinatura=st.date_input("Assinatura", value=date.today(), key=f"contr_ass_{sel.id}")
                data_validade=st.date_input("Validade", value=date.today(), key=f"contr_val_{sel.id}")
                if st.button("Salvar Contrato", key=f"contr_save_{sel.id}"):
                    if not arquivo_contrato: st.error("Envie um arquivo.")
                    elif data_validade<data_assinatura: st.error("Validade não pode ser anterior à assinatura.")
                    else:
                        caminho=salvar_arquivo(arquivo_contrato, "uploads/contratos", f"{sel.id}_contrato")
                        with SessionLocal() as db:
                            try:
                                c=Contrato(fornecedor_id=sel.id, arquivo=caminho,
                                           data_assinatura=data_assinatura, data_validade=data_validade,
                                           updated_by=st.session_state.usuario)
                                db.add(c); db.commit(); st.success("Contrato salvo com sucesso!")
                                exibir_preview_arquivo(caminho, arquivo_contrato.type); _safe_rerun()
                            except Exception as e:
                                db.rollback(); st.error(f"Erro ao salvar contrato: {e}")
                for c in sel.contratos:
                    with st.container(border=True):
                        st.write(f"- Assinado em: {c.data_assinatura}, Validade: {c.data_validade}")
                        if Path(c.arquivo).exists(): exibir_preview_arquivo(c.arquivo, None)

            # MTRs (do fornecedor)
            with tabs[5]:
                st.subheader("MTRs do fornecedor")
                total_kg = sum(m.qtd_kg or 0.0 for m in sel.mtrs)
                total_t = sum(m.emissoes_tco2e or 0.0 for m in sel.mtrs)
                st.write(f"**Total destinado (kg):** {total_kg:.1f} | **Total tCO₂e:** {total_t:.2f}")
                for m in sel.mtrs:
                    with st.container(border=True):
                        st.write(f"**MTR nº**: {m.numero_mtr or '-'} | **Receb.:** {m.destinador_data_recebimento or '-'} | **kg:** {m.qtd_kg or 0.0:.1f}")
                        with SessionLocal() as db:
                            tipos = listar_tipos_residuo(db)
                            tipo_idx = tipos.index(m.tipo_residuo) if (m.tipo_residuo in tipos) else (tipos.index("Misto/Outros") if "Misto/Outros" in tipos else 0)
                            c1,c2,c3,c4=st.columns(4)
                            with c1: tipo_sel = st.selectbox("Tipo de resíduo", tipos, index=tipo_idx, key=f"tipo_{m.id}")
                            destinos = listar_destinos_para_tipo(db, tipo_sel)
                            dest_idx = destinos.index(m.destinacao) if (m.destinacao in destinos) else (0 if destinos else 0)
                            with c2: dest_sel = st.selectbox("Destinação", destinos or ["(cadastre na página 'Fatores de Emissão')"], index=dest_idx, key=f"dest_{m.id}")
                            default_fator = obter_fator(db, tipo_sel, dest_sel) if destinos else None
                        with c3:
                            fator = st.number_input("Fator (tCO₂e/t)", value=float(m.fator_tco2e_por_ton if m.fator_tco2e_por_ton is not None else (default_fator or 0.0)),
                                                    step=0.01, format="%.4f", key=f"fator_{m.id}")
                        with c4:
                            em_calc = kg_to_ton(m.qtd_kg) * (fator or 0.0)
                            st.write(f"**tCO₂e calc.:** {em_calc:.4f}")

                        if st.button("Salvar MTR (Escopo 3)", key=f"salvar_mtr_{m.id}"):
                            with SessionLocal() as db:
                                mm=db.query(MTR).get(m.id)
                                mm.tipo_residuo=tipo_sel; mm.destinacao=dest_sel
                                mm.fator_tco2e_por_ton=float(fator or 0.0)
                                mm.emissoes_tco2e=kg_to_ton(mm.qtd_kg) * (mm.fator_tco2e_por_ton or 0.0)
                                mm.updated_by=st.session_state.usuario
                                db.commit(); st.success("MTR atualizada (escopo 3)."); _safe_rerun()

                        # CDFs
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
                                    mm=db.query(MTR).get(m.id); mm.cdf_count=(mm.cdf_count or 0)+1
                                    db.commit(); st.success("CDF anexado com sucesso!"); _safe_rerun()

# ---- Página MTRs (importação e edição em lote) ----
elif menu=="MTRs":
    if st.session_state.role not in ("Admin","Auditor"):
        st.error("Acesso restrito."); st.stop()
    st.header("Controle de MTRs por Fornecedor")
    if not HAVE_PDFPLUMBER: st.error("pdfplumber não está instalado. Adicione ao requirements."); st.stop()
    with SessionLocal() as db:
        fornecedores=db.query(Fornecedor).order_by(Fornecedor.nome.asc()).all()
    if not fornecedores: st.info("Cadastre fornecedores antes de importar MTRs."); st.stop()
    forn_map={f"{f.nome} — {formatar_cpf_cnpj(f.cpf_cnpj)}":f.id for f in fornecedores}
    forn_label=st.selectbox("Associar MTRs ao fornecedor", list(forn_map.keys()))
    fornecedor_id=forn_map[forn_label]
    uploads=st.file_uploader("Enviar PDFs de MTR", type=["pdf"], accept_multiple_files=True)
    if uploads and st.button("Processar MTRs"):
        ok, fail = 0, 0
        for up in uploads:
            try:
                caminho=salvar_arquivo(up, "uploads/mtrs", f"{fornecedor_id}_mtr")
                dados=extract_and_normalize_mtr(caminho)
                with SessionLocal() as db:
                    m=MTR(fornecedor_id=fornecedor_id, arquivo=caminho,
                          numero_mtr=dados["numero_mtr"],
                          gerador_razao=dados["gerador_razao"], gerador_cnpj=dados["gerador_cnpj"],
                          gerador_municipio=dados["gerador_municipio"], gerador_uf=dados["gerador_uf"],
                          gerador_data_emissao=dados["gerador_data_emissao"],
                          transportador_razao=dados["transportador_razao"], transportador_cnpj=dados["transportador_cnpj"],
                          transportador_data_transporte=dados["transportador_data_transporte"],
                          destinador_razao=dados["destinador_razao"], destinador_cnpj=dados["destinador_cnpj"],
                          destinador_data_recebimento=dados["destinador_data_recebimento"],
                          codigo_ibama_denom=dados["codigo_ibama_denom"],
                          qtd_original=dados["qtd_original"], und_original=dados["und_original"],
                          qtd_kg=dados["qtd_kg"], dados_raw=dados, updated_by=st.session_state.usuario)
                    db.add(m); db.commit(); ok+=1
            except Exception as e:
                fail+=1
                st.error(f"Erro ao processar {up.name}: {e}")
        st.success(f"Processo finalizado. Sucesso: {ok} | Falhas: {fail}")
        _safe_rerun()

    st.markdown("### Edição em lote (Escopo 3)")
    with SessionLocal() as db:
        mtrs=db.query(MTR).filter(MTR.fornecedor_id==fornecedor_id).order_by(MTR.created_at.desc()).all()
    if not mtrs:
        st.info("Nenhuma MTR cadastrada para este fornecedor.")
    else:
        for m in mtrs:
            with st.container(border=True):
                st.write(f"**MTR:** {m.numero_mtr or '-'} | **kg:** {m.qtd_kg or 0.0:.1f}")
                with SessionLocal() as db:
                    tipos=listar_tipos_residuo(db)
                    tipo_idx = tipos.index(m.tipo_residuo) if (m.tipo_residuo in tipos) else (tipos.index("Misto/Outros") if "Misto/Outros" in tipos else 0)
                    c1,c2,c3,c4=st.columns(4)
                    with c1: tipo_sel=st.selectbox("Tipo de resíduo", tipos, index=tipo_idx, key=f"tipo_mtrs_{m.id}")
                    destinos=listar_destinos_para_tipo(db, tipo_sel)
                    dest_idx = destinos.index(m.destinacao) if (m.destinacao in destinos) else (0 if destinos else 0)
                    with c2: dest_sel=st.selectbox("Destinação", destinos or ["(cadastre na página 'Fatores de Emissão')"], index=dest_idx, key=f"dest_mtrs_{m.id}")
                    default_fator = obter_fator(db, tipo_sel, dest_sel) if destinos else None
                with c3:
                    fator=st.number_input("Fator (tCO₂e/t)", value=float(m.fator_tco2e_por_ton if m.fator_tco2e_por_ton is not None else (default_fator or 0.0)),
                                          step=0.01, format="%.4f", key=f"fator_mtrs_{m.id}")
                with c4:
                    em_calc=kg_to_ton(m.qtd_kg) * (fator or 0.0)
                    st.write(f"**tCO₂e calc.:** {em_calc:.4f}")
                if st.button("Salvar (Escopo 3)", key=f"save_mtrs_{m.id}"):
                    with SessionLocal() as db:
                        mm=db.query(MTR).get(m.id)
                        mm.tipo_residuo=tipo_sel; mm.destinacao=dest_sel
                        mm.fator_tco2e_por_ton=float(fator or 0.0)
                        mm.emissoes_tco2e=kg_to_ton(mm.qtd_kg) * (mm.fator_tco2e_por_ton or 0.0)
                        mm.updated_by=st.session_state.usuario
                        db.commit(); st.success("MTR atualizada (escopo 3)."); _safe_rerun()

                # upload rápido de CDF
                up_cdf=st.file_uploader("Anexar CDF (PDF/JPG/PNG)", type=["pdf","jpg","jpeg","png"], key=f"cdf_up_list_{m.id}")
                cdf_data=st.date_input("Data de emissão do CDF", value=date.today(), key=f"cdf_dt_list_{m.id}")
                cdf_obs=st.text_input("Observação (opcional)", key=f"cdf_obs_list_{m.id}")
                if st.button("Adicionar CDF", key=f"cdf_add_list_{m.id}"):
                    if not up_cdf: st.error("Envie um arquivo de CDF.")
                    else:
                        caminho=salvar_arquivo(up_cdf, "uploads/cdfs", f"{m.id}_cdf")
                        with SessionLocal() as db:
                            novo=CDF(mtr_id=m.id, arquivo=caminho, data_emissao=cdf_data,
                                     observacao=cdf_obs.strip() or None, updated_by=st.session_state.usuario)
                            db.add(novo)
                            mm=db.query(MTR).get(m.id); mm.cdf_count=(mm.cdf_count or 0)+1
                            db.commit(); st.success("CDF anexado."); _safe_rerun()

    st.markdown("### MTRs cadastradas")
    with SessionLocal() as db:
        mtrs_all=db.query(MTR).join(Fornecedor).add_columns(Fornecedor.nome).order_by(MTR.created_at.desc()).all()
    if not mtrs_all:
        st.info("Nenhuma MTR cadastrada ainda.")
    else:
        rows=[]
        for m, nome_f in mtrs_all:
            rows.append({
                "Fornecedor": nome_f, "MTR nº": m.numero_mtr or "-",
                "Recebimento": m.destinador_data_recebimento or "",
                "Qtde (kg)": m.qtd_kg if m.qtd_kg is not None else "",
                "Tipo": m.tipo_residuo or "", "Destinação": m.destinacao or "",
                "Fator (tCO₂e/t)": m.fator_tco2e_por_ton if m.fator_tco2e_por_ton is not None else "",
                "tCO₂e": m.emissoes_tco2e if m.emissoes_tco2e is not None else "",
                "CDF(s)": m.cdf_count or 0, "Arquivo": os.path.basename(m.arquivo),
            })
        if HAVE_PANDAS:
            st.dataframe(pd.DataFrame(rows), use_container_width=True)
        else:
            for r in rows[:200]: st.write(r)

# ---- Fatores de Emissão (EDITÁVEL) ----
elif menu=="Fatores de Emissão":
    if st.session_state.role not in ("Admin","Auditor"):
        st.error("Acesso restrito."); st.stop()

    st.header("Fatores de Emissão (tCO₂e por tonelada)")
    with SessionLocal() as db:
        fatores = db.query(FatorEmissao).order_by(FatorEmissao.tipo_residuo.asc(), FatorEmissao.destinacao.asc()).all()

    st.markdown("#### Editar existentes (tabela editável)")
    if fatores:
        # DataFrame com coluna id oculta, mas preservada
        rows = [{
            "id": f.id,
            "Tipo de resíduo": f.tipo_residuo,
            "Destinação": f.destinacao,
            "Fator (tCO₂e/t)": float(f.fator_tco2e_por_ton or 0.0),
            "Fonte": f.fonte or "",
            "Ano ref.": int(f.ano_ref or 0),
            "Selecionar": False
        } for f in fatores]
        if HAVE_PANDAS:
            df = pd.DataFrame(rows)
            edited = st.data_editor(
                df,
                use_container_width=True,
                key="fe_editor",
                column_config={
                    "id": st.column_config.Column("id", disabled=True),
                    "Fator (tCO₂e/t)": st.column_config.NumberColumn(format="%.4f"),
                    "Ano ref.": st.column_config.NumberColumn(step=1, min_value=0),
                    "Selecionar": st.column_config.CheckboxColumn(help="Marque para excluir"),
                },
                hide_index=True
            )
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Salvar alterações"):
                    try:
                        with SessionLocal() as db:
                            for _, r in edited.iterrows():
                                fe = db.query(FatorEmissao).get(int(r["id"]))
                                if not fe: continue
                                # Evita colisão (tipo,dest)
                                novo_tipo = str(r["Tipo de resíduo"]).strip()
                                novo_dest = str(r["Destinação"]).strip()
                                if (fe.tipo_residuo!=novo_tipo or fe.destinacao!=novo_dest):
                                    exists = db.query(FatorEmissao).filter(
                                        FatorEmissao.tipo_residuo==novo_tipo,
                                        FatorEmissao.destinacao==novo_dest
                                    ).first()
                                    if exists and exists.id != fe.id:
                                        st.error(f"Conflito: já existe fator para ({novo_tipo}, {novo_dest}).")
                                        continue
                                fe.tipo_residuo = novo_tipo
                                fe.destinacao = novo_dest
                                fe.fator_tco2e_por_ton = float(r["Fator (tCO₂e/t)"])
                                fe.fonte = (str(r["Fonte"]).strip() or None)
                                ano = int(r["Ano ref."] or 0)
                                fe.ano_ref = ano if ano>0 else None
                            db.commit()
                        st.success("Alterações salvas.")
                        _safe_rerun()
                    except Exception as e:
                        st.error(f"Erro ao salvar: {e}")
            with col2:
                if st.button("Excluir selecionados"):
                    ids_sel = edited.loc[edited["Selecionar"]==True, "id"].tolist()
                    if not ids_sel:
                        st.info("Nenhuma linha marcada.")
                    else:
                        try:
                            with SessionLocal() as db:
                                for i in ids_sel:
                                    fe = db.query(FatorEmissao).get(int(i))
                                    if fe: db.delete(fe)
                                db.commit()
                            st.success(f"Excluídos: {len(ids_sel)} registro(s).")
                            _safe_rerun()
                        except Exception as e:
                            st.error(f"Erro ao excluir: {e}")
        else:
            st.info("Para edição em tabela, instale pandas.")
    else:
        st.info("Nenhum fator cadastrado. Use o formulário abaixo para adicionar.")

    st.markdown("---")
    st.subheader("Adicionar novo fator")
    with st.form("form_add_fator"):
        tipo_new = st.text_input("Tipo de resíduo *")
        dest_new = st.text_input("Destinação *")
        fator_new = st.number_input("Fator (tCO₂e/t) *", value=0.0, step=0.01, format="%.4f")
        fonte_new = st.text_input("Fonte (ex.: IPCC 2019)")
        ano_new = st.number_input("Ano de referência", value=0, step=1, min_value=0)
        enviar = st.form_submit_button("Adicionar")
    if enviar:
        if not tipo_new or not dest_new:
            st.error("Preencha tipo e destinação.")
        else:
            with SessionLocal() as db:
                try:
                    já = db.query(FatorEmissao).filter(
                        FatorEmissao.tipo_residuo==tipo_new.strip(),
                        FatorEmissao.destinacao==dest_new.strip()
                    ).first()
                    if já:
                        st.error("Já existe um fator para esse (tipo, destinação).")
                    else:
                        db.add(FatorEmissao(
                            tipo_residuo=tipo_new.strip(),
                            destinacao=dest_new.strip(),
                            fator_tco2e_por_ton=float(fator_new),
                            fonte=fonte_new.strip() or None,
                            ano_ref=int(ano_new) if ano_new>0 else None
                        ))
                        db.commit()
                        st.success("Fator adicionado com sucesso!")
                        _safe_rerun()
                except Exception as e:
                    st.error(f"Erro ao adicionar fator: {e}")

# ---- Admin (Usuários) ----
elif menu=="Admin (Usuários)":
    if st.session_state.role!="Admin":
        st.error("Apenas Admin pode acessar esta página."); st.stop()
    st.header("Administração")
    with SessionLocal() as db: usuarios=db.query(User).all()
    st.subheader("Usuários")
    for u in usuarios: st.write(f"- **{u.username}** — {u.role.value}")
    st.subheader("Criar novo usuário")
    with st.form("form_user"):
        username=st.text_input("Usuário").strip()
        password=st.text_input("Senha", type="password").strip()
        role=st.selectbox("Papel", [RoleEnum.admin.value, RoleEnum.auditor.value, RoleEnum.leitor.value])
        enviar=st.form_submit_button("Criar")
    if enviar:
        if not username or not password: st.error("Preencha usuário e senha.")
        else:
            with SessionLocal() as db:
                if get_user_by_username(db, username): st.error("Usuário já existe.")
                else:
                    create_user(db, username, password, RoleEnum(role)); st.success("Usuário criado com sucesso!"); _safe_rerun()

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
                            "modelo":modelo,"area_pct_json":json.dumps(area_pct,ensure_ascii=False) if area_pct else "",
                            "respostas_json":json.dumps(a.respostas,ensure_ascii=False),"updated_by":a.updated_by
                        })
                pd.DataFrame(rows_a).to_excel(writer, sheet_name="Auditorias", index=False)

                rows_p=[]
                for f in fornecedores:
                    for p in f.planos_acao:
                        rows_p.append({
                            "fornecedor_id":f.id,"fornecedor":f.nome,"descricao":p.descricao,
                            "inicio":p.data_inicio,"fim":p.data_fim,"status":p.status,
                            "evidencias":json.dumps(p.evidencias,ensure_ascii=False),"updated_by":p.updated_by
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
                            "tipo_residuo":m.tipo_residuo,"destinacao":m.destinacao,
                            "fator_tco2e_t":m.fator_tco2e_por_ton,"tco2e":m.emissoes_tco2e,
                            "cdf_count":m.cdf_count,"arquivo":m.arquivo
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

                # Fatores de Emissão
                with SessionLocal() as db:
                    fac=db.query(FatorEmissao).order_by(FatorEmissao.tipo_residuo.asc(),FatorEmissao.destinacao.asc()).all()
                rows_fe=[{
                    "id":fe.id,"tipo":fe.tipo_residuo,"destinacao":fe.destinacao,
                    "fator_tco2e_t":fe.fator_tco2e_por_ton,"fonte":fe.fonte,"ano_ref":fe.ano_ref
                } for fe in fac]
                pd.DataFrame(rows_fe).to_excel(writer, sheet_name="FatoresEmissao", index=False)

            output.seek(0)
            st.download_button("Baixar Excel", data=output.read(),
                               file_name="fornecedores_export.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ---- Sair ----
elif menu=="Sair":
    st.session_state.logado=False; st.session_state.usuario=None; st.session_state.role=None
    st.session_state.sel_forn_id=None; _safe_rerun()
