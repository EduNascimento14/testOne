from __future__ import annotations

from datetime import date

import pandas as pd
from sqlalchemy.orm import Session

from .models import Achado, Auditoria, Diretiva, Requisito, RespostaChecklist, Site

PONTOS_STATUS = {"Conforme": 1.0, "Parcialmente Conforme": 0.5, "Não Conforme": 0.0}
VERIFICADOS = set(PONTOS_STATUS)


def respostas_df(session: Session, auditoria_id: int | None = None) -> pd.DataFrame:
    query = (session.query(RespostaChecklist, Requisito, Diretiva, Auditoria, Site)
             .select_from(RespostaChecklist)
             .join(Requisito, RespostaChecklist.requisito_id == Requisito.id)
             .join(Diretiva, Requisito.diretiva_id == Diretiva.id)
             .join(Auditoria, RespostaChecklist.auditoria_id == Auditoria.id)
             .join(Site, Auditoria.site_auditado_id == Site.id))
    if auditoria_id:
        query = query.filter(RespostaChecklist.auditoria_id == auditoria_id)
    rows = []
    for r, req, d, a, s in query.all():
        rows.append({
            "resposta_id": r.id, "auditoria_id": a.id, "auditoria": a.nome, "ano": a.ano, "ciclo": a.ciclo,
            "site": s.codigo, "diretiva": d.codigo, "diretiva_titulo": d.titulo, "requisito_id": req.id,
            "codigo_requisito": req.codigo_requisito, "pergunta": req.pergunta, "criticidade": req.criticidade,
            "aplicavel": r.aplicavel, "status": r.status_conformidade, "nota_maturidade": r.nota_maturidade,
            "necessita_acao": r.necessita_acao, "evidencia_verificada": r.evidencia_verificada or "", "comentario_auditor": r.comentario_auditor or "",
        })
    return pd.DataFrame(rows)


def conformidade_percentual(df: pd.DataFrame) -> float:
    if df.empty:
        return 0.0
    base = df[(df["aplicavel"] == True) & (df["status"].isin(VERIFICADOS))].copy()  # noqa: E712
    if base.empty:
        return 0.0
    return round(base["status"].map(PONTOS_STATUS).mean() * 100, 1)


def maturidade_media(df: pd.DataFrame) -> float:
    if df.empty:
        return 0.0
    base = df[(df["aplicavel"] == True) & (df["status"].isin(VERIFICADOS)) & (df["nota_maturidade"].notna())]  # noqa: E712
    if base.empty:
        return 0.0
    return round(float(base["nota_maturidade"].mean()), 2)


def classificar_resultado(percentual: float, nc_critica_aberta: int = 0) -> str:
    if percentual >= 90 and nc_critica_aberta == 0:
        return "Referência / Maduro"
    if percentual >= 75:
        return "Conforme com oportunidades de melhoria"
    if percentual >= 50:
        return "Parcialmente conforme / requer plano robusto"
    return "Não conforme / requer intervenção"


def resumo_auditoria(session: Session, auditoria_id: int) -> dict:
    df = respostas_df(session, auditoria_id)
    criticas = session.query(Achado).filter(Achado.auditoria_id == auditoria_id, Achado.tipo_achado == "Não conformidade crítica", Achado.status.in_(["Aberto", "Em andamento", "Vencido"])).count()
    pct = conformidade_percentual(df)
    return {"conformidade": pct, "maturidade": maturidade_media(df), "classificacao": classificar_resultado(pct, criticas), "nc_criticas_abertas": criticas}


def pontuacao_por(df: pd.DataFrame, campo: str) -> pd.DataFrame:
    if df.empty or campo not in df:
        return pd.DataFrame(columns=[campo, "conformidade", "maturidade"])
    rows = []
    for valor, grupo in df.groupby(campo):
        rows.append({campo: valor, "conformidade": conformidade_percentual(grupo), "maturidade": maturidade_media(grupo)})
    return pd.DataFrame(rows)


def achados_df(session: Session) -> pd.DataFrame:
    rows = []
    for a, aud, site, req in (session.query(Achado, Auditoria, Site, Requisito)
                              .select_from(Achado)
                              .join(Auditoria, Achado.auditoria_id == Auditoria.id)
                              .join(Site, Achado.site_id == Site.id)
                              .join(Requisito, Achado.requisito_id == Requisito.id)
                              .all()):
        vencido = bool(a.prazo and a.prazo < date.today() and a.status not in ["Concluído", "Cancelado"])
        rows.append({"id": a.id, "auditoria_id": aud.id, "auditoria": aud.nome, "site": site.codigo, "requisito": req.codigo_requisito, "tipo_achado": a.tipo_achado, "descricao": a.descricao, "responsavel": a.responsavel or "", "prazo": a.prazo, "status": "Vencido" if vencido else a.status, "prioridade": a.prioridade, "vencido": vencido})
    return pd.DataFrame(rows)


def dashboard_kpis(session: Session) -> dict:
    df = respostas_df(session)
    ach = achados_df(session)
    return {
        "planejadas": session.query(Auditoria).filter_by(status="Planejada").count(),
        "em_andamento": session.query(Auditoria).filter_by(status="Em andamento").count(),
        "concluidas": session.query(Auditoria).filter_by(status="Concluída").count(),
        "conformidade_media": conformidade_percentual(df),
        "maturidade_media": maturidade_media(df),
        "achados_abertos": 0 if ach.empty else int(ach[ach["status"].isin(["Aberto", "Em andamento", "Vencido"])].shape[0]),
        "achados_vencidos": 0 if ach.empty else int(ach["vencido"].sum()),
        "nc_criticas_abertas": session.query(Achado).filter(Achado.tipo_achado == "Não conformidade crítica", Achado.status.in_(["Aberto", "Em andamento", "Vencido"])).count(),
    }
