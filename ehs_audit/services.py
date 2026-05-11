from __future__ import annotations

from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from .config import UPLOAD_DIR
from .models import Auditoria, EvidenciaArquivo, Requisito, RespostaChecklist


def criar_auditoria(session: Session, **data) -> Auditoria:
    if data["site_auditado_id"] == data["site_auditor_lider_id"]:
        raise ValueError("O site auditado não pode ser igual ao site auditor líder.")
    auditoria = Auditoria(**data)
    session.add(auditoria)
    session.flush()
    requisitos = session.query(Requisito).filter_by(ativo=True).all()
    for req in requisitos:
        session.add(RespostaChecklist(auditoria_id=auditoria.id, requisito_id=req.id, aplicavel=True, status_conformidade="Não Verificado"))
    session.commit()
    return auditoria


def salvar_respostas(session: Session, edited_df, avaliado_por: str | None = None) -> int:
    count = 0
    for row in edited_df.to_dict("records"):
        resposta = session.get(RespostaChecklist, int(row["resposta_id"]))
        if not resposta:
            continue
        resposta.aplicavel = bool(row.get("aplicavel"))
        resposta.status_conformidade = row.get("status") or "Não Verificado"
        resposta.nota_maturidade = None if row.get("nota_maturidade") in ("", None) else int(row.get("nota_maturidade"))
        resposta.evidencia_verificada = row.get("evidencia_verificada") or None
        resposta.comentario_auditor = row.get("comentario_auditor") or None
        resposta.necessita_acao = bool(row.get("necessita_acao"))
        resposta.data_avaliacao = datetime.utcnow()
        resposta.avaliado_por = avaliado_por
        count += 1
    session.commit()
    return count


def salvar_upload(uploaded_file, auditoria_id: int, requisito_id: int, achado_id: int | None, enviado_por: str | None, session: Session) -> EvidenciaArquivo:
    target_dir = UPLOAD_DIR / str(auditoria_id) / str(requisito_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(uploaded_file.name).name
    path = target_dir / f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{safe_name}"
    path.write_bytes(uploaded_file.getbuffer())
    evidencia = EvidenciaArquivo(auditoria_id=auditoria_id, requisito_id=requisito_id, achado_id=achado_id, nome_arquivo=safe_name, caminho_arquivo=str(path), tipo_arquivo=getattr(uploaded_file, "type", None), enviado_por=enviado_por)
    session.add(evidencia)
    session.commit()
    return evidencia
