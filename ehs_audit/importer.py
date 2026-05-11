from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from .constants import DIRETIVAS_REFERENCIA
from .models import Diretiva, Requisito

QUESTION_KEYS = ["requirement", "requisito", "question", "pergunta", "shall", "criteria", "critério", "item"]
GUIDANCE_KEYS = ["guidance", "orient", "note", "nota", "evidence", "evid"]


def parse_sheet_name(sheet: str) -> tuple[str | None, str]:
    m = re.search(r"(4\.12\.\d{2})", sheet)
    codigo = m.group(1) if m else None
    titulo = re.sub(r"^.*?4\.12\.\d{2}\s*[-–—_:]*\s*", "", sheet).strip() or (DIRETIVAS_REFERENCIA.get(codigo or "", "") if codigo else sheet)
    return codigo, titulo


def classify_criticidade(text: str) -> str:
    t = (text or "").lower()
    if any(k in t for k in ["fatal", "life", "legal", "permit", "emergency", "lockout", "electrical", "confined", "critical"]):
        return "Crítico"
    if any(k in t for k in ["must", "shall", "required", "training", "incident", "chemical", "hazard"]):
        return "Alto"
    if any(k in t for k in ["review", "document", "procedure", "record"]):
        return "Médio"
    return "Baixo"


def _read_sheet(path: str | Path, sheet: str) -> pd.DataFrame:
    raw = pd.read_excel(path, sheet_name=sheet, header=None, dtype=str).fillna("")
    # Detect header row by keyword density in first 20 rows.
    header_idx = None
    for idx, row in raw.head(20).iterrows():
        joined = " ".join(str(x).lower() for x in row.tolist())
        if sum(k in joined for k in QUESTION_KEYS + GUIDANCE_KEYS) >= 2:
            header_idx = idx
            break
    if header_idx is not None:
        df = pd.read_excel(path, sheet_name=sheet, header=header_idx, dtype=str).fillna("")
    else:
        df = raw
    df = df.dropna(how="all")
    return df


def _find_col(df: pd.DataFrame, keys: list[str]) -> Any | None:
    for col in df.columns:
        normalized = str(col).strip().lower()
        if any(k in normalized for k in keys):
            return col
    return None


def _extract_rows(df: pd.DataFrame, codigo_diretiva: str) -> list[dict[str, str]]:
    if df.empty:
        return []
    q_col = _find_col(df, QUESTION_KEYS)
    g_col = _find_col(df, GUIDANCE_KEYS)
    rows = []
    if q_col is not None:
        for idx, row in df.iterrows():
            pergunta = str(row.get(q_col, "")).strip()
            if len(pergunta) < 12 or pergunta.lower() in ["nan", "none"]:
                continue
            orientacao = str(row.get(g_col, "")).strip() if g_col is not None else ""
            rows.append({"codigo_requisito": f"{codigo_diretiva}.{len(rows)+1:03d}", "pergunta": pergunta, "orientacao": orientacao})
        return rows
    # Heuristic fallback: choose text-heavy cells that look auditable.
    seen = set()
    for _, row in df.iterrows():
        cells = [str(x).strip() for x in row.tolist() if str(x).strip() and str(x).strip().lower() not in ["nan", "none"]]
        candidates = [c for c in cells if len(c) >= 25 and ("?" in c or re.search(r"\b(shall|must|required|procedure|training|record|ensure|establish)\b", c, re.I))]
        if candidates:
            pergunta = max(candidates, key=len)
            norm = re.sub(r"\s+", " ", pergunta.lower())
            if norm not in seen:
                seen.add(norm)
                rows.append({"codigo_requisito": f"{codigo_diretiva}.{len(rows)+1:03d}", "pergunta": pergunta, "orientacao": ""})
    return rows


def import_matrix(session: Session, file_path: str | Path) -> dict:
    xls = pd.ExcelFile(file_path)
    log: list[str] = []
    imported_directives = 0
    imported_requirements = 0
    for sheet in xls.sheet_names:
        codigo, titulo = parse_sheet_name(sheet)
        if not codigo or not codigo.startswith("4.12."):
            continue
        diretiva = session.query(Diretiva).filter_by(codigo=codigo).one_or_none()
        if not diretiva:
            diretiva = Diretiva(codigo=codigo, titulo=titulo or DIRETIVAS_REFERENCIA.get(codigo, sheet), ativa=True)
            session.add(diretiva)
            session.flush()
            imported_directives += 1
        else:
            diretiva.titulo = diretiva.titulo or titulo
        df = _read_sheet(file_path, sheet)
        reqs = _extract_rows(df, codigo)
        if not reqs:
            diretiva.observacao = "lacuna da base de referência — aba sem requisitos auditáveis detectados"
            log.append(f"{codigo}: sem requisitos; registrada lacuna da base de referência.")
            continue
        for req in reqs:
            exists = session.query(Requisito).filter_by(diretiva_id=diretiva.id, codigo_requisito=req["codigo_requisito"]).one_or_none()
            if exists:
                continue
            session.add(Requisito(diretiva_id=diretiva.id, codigo_requisito=req["codigo_requisito"], pergunta=req["pergunta"], orientacao=req["orientacao"], criticidade=classify_criticidade(req["pergunta"]), ativo=True))
            imported_requirements += 1
        log.append(f"{codigo}: {len(reqs)} requisitos detectados.")
    session.commit()
    return {"diretivas_importadas": imported_directives, "requisitos_importados": imported_requirements, "log": log}
