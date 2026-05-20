from datetime import date, datetime, timedelta
from pathlib import Path
from re import sub

import pandas as pd

from ehs_integrada.models import (
    EHSAuditoria,
    EHSIndicadorDiretiva,
    EHSPAC,
    EHSRequisito,
    EHSResposta,
    NR12ChecklistItem,
    NR12Documento,
    NR12Maquina,
    NR12MOC,
    NR12PAC,
    NR12Resposta,
    NR12Verificacao,
    Site,
)
from ehs_integrada.seed import ensure_ehs_respostas, ensure_nr12_respostas
from ehs_integrada.validations import DOCUMENTOS_ESSENCIAIS, audit_interval_days, document_status, is_open_status


UPLOAD_DIR = Path("uploads_ehs_integrada")


def visible_site_ids(user):
    if not user or user.perfil == "Admin_LAG" or user.site_id is None:
        return None
    return [user.site_id]


def site_options(session, user):
    q = session.query(Site).filter(Site.ativo.is_(True)).order_by(Site.codigo)
    ids = visible_site_ids(user)
    if ids is not None:
        q = q.filter(Site.id.in_(ids))
    return q.all()


def safe_filename(name):
    filename = Path(name).name
    filename = sub(r"[^A-Za-z0-9._-]+", "_", filename).strip("._")
    return filename or "arquivo"


def save_uploaded_file(uploaded_file, prefix):
    UPLOAD_DIR.mkdir(exist_ok=True)
    filename = safe_filename(uploaded_file.name)
    path = UPLOAD_DIR / f"{prefix}_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}_{filename}"
    path.write_bytes(uploaded_file.getbuffer())
    return str(path)


def filter_by_sites(query, column, site_ids):
    if site_ids is not None:
        return query.filter(column.in_(site_ids))
    return query


def nr12_maquinas_df(session, site_ids=None):
    q = session.query(NR12Maquina, Site).select_from(NR12Maquina).join(Site, NR12Maquina.site_id == Site.id)
    q = filter_by_sites(q, NR12Maquina.site_id, site_ids)
    rows = []
    for m, s in q.order_by(Site.codigo, NR12Maquina.codigo).all():
        rows.append({
            "ID": m.id,
            "Código": m.codigo,
            "Site": s.codigo,
            "Área": m.area,
            "Linha/processo": m.linha_processo,
            "Máquina": m.nome,
            "Fabricante": m.fabricante,
            "Modelo": m.modelo,
            "Série": m.numero_serie,
            "Ano": m.ano,
            "Tipo": m.tipo_equipamento,
            "Responsável": m.responsavel_area,
            "Criticidade": m.criticidade,
            "Status NR-12": m.status_nr12,
            "Última auditoria": m.ultima_auditoria,
            "Próxima auditoria": m.proxima_auditoria,
            "Laudo": "Sim" if m.possui_laudo else "Não",
            "ART": "Sim" if m.possui_art else "Não",
            "Apreciação de risco": "Sim" if m.possui_apreciacao_risco else "Não",
            "Manual": "Sim" if m.possui_manual_atualizado else "Não",
            "Treinamento": "Sim" if m.possui_treinamento else "Não",
        })
    return pd.DataFrame(rows)


def nr12_documentos_df(session, site_ids=None):
    q = (
        session.query(NR12Documento, NR12Maquina, Site)
        .select_from(NR12Documento)
        .join(NR12Maquina, NR12Documento.maquina_id == NR12Maquina.id)
        .join(Site, NR12Maquina.site_id == Site.id)
    )
    q = filter_by_sites(q, NR12Maquina.site_id, site_ids)
    rows = []
    for d, m, s in q.order_by(Site.codigo, NR12Maquina.codigo, NR12Documento.tipo_documento).all():
        status = document_status(d.data_validade, d.status)
        rows.append({
            "ID": d.id,
            "Site": s.codigo,
            "Máquina": m.codigo,
            "Tipo": d.tipo_documento,
            "Nome": d.nome,
            "Emissão": d.data_emissao,
            "Validade": d.data_validade,
            "Responsável": d.responsavel,
            "Status": status,
            "Arquivo": d.caminho_arquivo,
        })
    return pd.DataFrame(rows)


def nr12_pacs_df(session, site_ids=None):
    q = (
        session.query(NR12PAC, NR12Maquina, Site)
        .select_from(NR12PAC)
        .join(NR12Maquina, NR12PAC.maquina_id == NR12Maquina.id)
        .join(Site, NR12PAC.site_id == Site.id)
    )
    q = filter_by_sites(q, NR12PAC.site_id, site_ids)
    rows = []
    today = date.today()
    for p, m, s in q.order_by(NR12PAC.prazo).all():
        vencido = bool(p.prazo and p.prazo < today and is_open_status(p.status))
        rows.append({
            "ID": p.id,
            "Site": s.codigo,
            "Máquina": m.codigo,
            "Origem": p.origem,
            "Descrição": p.descricao_desvio,
            "Classificação": p.classificacao,
            "Responsável": p.responsavel,
            "Área": p.area_responsavel,
            "Prazo": p.prazo,
            "Status": "Vencido" if vencido else p.status,
            "Vencido": vencido,
            "Validação EHS": p.validacao_ehs,
        })
    return pd.DataFrame(rows)


def nr12_mocs_df(session, site_ids=None):
    q = (
        session.query(NR12MOC, NR12Maquina, Site)
        .select_from(NR12MOC)
        .join(NR12Maquina, NR12MOC.maquina_id == NR12Maquina.id)
        .join(Site, NR12MOC.site_id == Site.id)
    )
    q = filter_by_sites(q, NR12MOC.site_id, site_ids)
    rows = []
    for c, m, s in q.order_by(NR12MOC.data_mudanca.desc()).all():
        sem_validacao = c.impacta_seguranca and is_open_status(c.status) and not (c.aprovacao_ehs and (c.aprovacao_manutencao or c.aprovacao_engenharia))
        rows.append({
            "ID": c.id,
            "Site": s.codigo,
            "Máquina": m.codigo,
            "Tipo": c.tipo_mudanca,
            "Data": c.data_mudanca,
            "Status": c.status,
            "Impacta segurança": c.impacta_seguranca,
            "Exige MOC": c.exige_moc,
            "Sem validação": sem_validacao,
        })
    return pd.DataFrame(rows)


def nr12_verificacoes_df(session, site_ids=None):
    q = (
        session.query(NR12Verificacao, NR12Maquina, Site)
        .select_from(NR12Verificacao)
        .join(NR12Maquina, NR12Verificacao.maquina_id == NR12Maquina.id)
        .join(Site, NR12Verificacao.site_id == Site.id)
    )
    q = filter_by_sites(q, NR12Verificacao.site_id, site_ids)
    rows = []
    for v, m, s in q.order_by(NR12Verificacao.data_verificacao.desc()).all():
        rows.append({
            "ID": v.id,
            "Site": s.codigo,
            "Máquina": m.codigo,
            "Tipo": v.tipo_verificacao,
            "Data": v.data_verificacao,
            "Auditor": v.auditor,
            "Resultado": v.resultado,
            "Pontuação": v.pontuacao,
        })
    return pd.DataFrame(rows)


def nr12_schedule_df(session, site_ids=None):
    rows = []
    today = date.today()
    q = session.query(NR12Maquina, Site).select_from(NR12Maquina).join(Site, NR12Maquina.site_id == Site.id)
    q = filter_by_sites(q, NR12Maquina.site_id, site_ids)
    for m, s in q.all():
        for audit_type in ["Checklist operacional", "Inspeção de manutenção", "Auditoria EHS"]:
            interval = audit_interval_days(m.criticidade, audit_type)
            if interval is None:
                continue
            latest = (
                session.query(NR12Verificacao)
                .filter(NR12Verificacao.maquina_id == m.id, NR12Verificacao.tipo_verificacao == audit_type)
                .order_by(NR12Verificacao.data_verificacao.desc(), NR12Verificacao.id.desc())
                .first()
            )
            base = latest.data_verificacao if latest else (m.ultima_adequacao or m.criado_em.date() if m.criado_em else today)
            due = base + timedelta(days=interval)
            days = (due - today).days
            rows.append({
                "Site": s.codigo,
                "Máquina": m.codigo,
                "Área": m.area,
                "Criticidade": m.criticidade,
                "Tipo": audit_type,
                "Próxima verificação": due,
                "Status": "Vencida" if days < 0 else "Próxima" if days <= 30 else "Programada",
                "Dias": days,
            })
    return pd.DataFrame(rows)


def calculate_nr12_score(rows):
    applicable = [r for r in rows if r.get("resultado") != "Não aplicável" and r.get("aplicavel", True)]
    if not applicable:
        return 100.0, "Conforme", False
    conformes = [r for r in applicable if r.get("resultado") == "Conforme"]
    critical_nc = any(r.get("critico") and r.get("resultado") == "Não conforme" for r in applicable)
    score = round(len(conformes) / len(applicable) * 100, 1)
    if critical_nc:
        return score, "Bloqueada por desvio crítico", True
    if score < 70:
        return score, "Pendente de ação não crítica", False
    if score < 90:
        return score, "Conforme com observação", False
    return score, "Conforme", False


def suggest_machine_status(session, machine):
    today = date.today()
    pacs_open = [p for p in machine.pacs if is_open_status(p.status)]
    if any(p.classificacao == "Crítico" for p in pacs_open):
        return "Bloqueada por desvio crítico"
    docs = {d.tipo_documento: document_status(d.data_validade, d.status) for d in machine.documentos}
    missing_flags = [
        ("Laudo NR-12", machine.possui_laudo),
        ("ART", machine.possui_art),
        ("Apreciação de risco", machine.possui_apreciacao_risco),
    ]
    if any((not flag and tipo not in docs) for tipo, flag in missing_flags):
        return "Pendente de ação não crítica"
    if any(docs.get(tipo) == "Vencido" for tipo in DOCUMENTOS_ESSENCIAIS):
        return "Pendente de ação não crítica"
    if any(m.impacta_seguranca and is_open_status(m.status) and not (m.aprovacao_ehs and (m.aprovacao_manutencao or m.aprovacao_engenharia)) for m in machine.mocs):
        return "Bloqueada por desvio crítico"
    schedule = nr12_schedule_df(session, [machine.site_id])
    if not schedule.empty:
        expired = schedule[(schedule["Máquina"] == machine.codigo) & (schedule["Status"] == "Vencida")]
        if not expired.empty:
            return "Pendente de ação não crítica"
    if any(p.prazo and p.prazo < today for p in pacs_open):
        return "Pendente de ação não crítica"
    if pacs_open:
        return "Conforme com observação"
    return "Conforme"


def update_machine_status(session, machine):
    if machine.status_nr12 in {"Fora de uso", "Não aplicável", "Em readequação"}:
        return machine.status_nr12
    status = suggest_machine_status(session, machine)
    machine.status_sugerido = status
    machine.status_nr12 = status
    return status


def nr12_kpis(session, site_ids=None):
    machines = filter_by_sites(session.query(NR12Maquina), NR12Maquina.site_id, site_ids).all()
    docs = nr12_documentos_df(session, site_ids)
    pacs = nr12_pacs_df(session, site_ids)
    mocs = nr12_mocs_df(session, site_ids)
    schedule = nr12_schedule_df(session, site_ids)
    total = len(machines)
    conformes = sum(1 for m in machines if m.status_nr12 == "Conforme")
    return {
        "total": total,
        "conformes_pct": round((conformes / total * 100), 1) if total else 0,
        "observacao": sum(1 for m in machines if m.status_nr12 == "Conforme com observação"),
        "pendentes": sum(1 for m in machines if m.status_nr12 == "Pendente de ação não crítica"),
        "bloqueadas": sum(1 for m in machines if m.status_nr12 == "Bloqueada por desvio crítico"),
        "auditorias_vencidas": int((schedule["Status"] == "Vencida").sum()) if not schedule.empty else 0,
        "auditorias_proximas": int((schedule["Status"] == "Próxima").sum()) if not schedule.empty else 0,
        "docs_vencidos": int((docs["Status"] == "Vencido").sum()) if not docs.empty else 0,
        "docs_ausentes": sum(1 for m in machines for tipo, flag in [("Laudo NR-12", m.possui_laudo), ("ART", m.possui_art), ("Apreciação de risco", m.possui_apreciacao_risco)] if not flag),
        "pacs_abertos": int((~pacs["Status"].isin(["Concluído", "Cancelado"])).sum()) if not pacs.empty else 0,
        "pacs_vencidos": int(pacs["Vencido"].sum()) if not pacs.empty else 0,
        "pacs_criticos": int((pacs["Classificação"] == "Crítico").sum()) if not pacs.empty else 0,
        "mocs_sem_validacao": int(mocs["Sem validação"].sum()) if not mocs.empty else 0,
    }


def create_nr12_verificacao(session, maquina, tipo, auditor, data_verificacao, participantes=""):
    verificacao = NR12Verificacao(
        maquina_id=maquina.id,
        site_id=maquina.site_id,
        tipo_verificacao=tipo,
        data_verificacao=data_verificacao,
        auditor=auditor,
        participantes=participantes,
        resultado="Conforme",
        pontuacao=100,
    )
    session.add(verificacao)
    session.flush()
    ensure_nr12_respostas(session, verificacao.id)
    return verificacao


def apply_nr12_respostas(session, verificacao_id, edited_rows):
    verificacao = session.get(NR12Verificacao, verificacao_id)
    rows_for_score = []
    for row in edited_rows:
        resp = session.get(NR12Resposta, int(row["ID"]))
        if not resp:
            continue
        resp.aplicavel = bool(row.get("Aplicável", True))
        resp.resultado = "Não aplicável" if not resp.aplicavel else row.get("Resultado", "Conforme")
        resp.comentario = row.get("Comentário", "")
        resp.evidencia = row.get("Evidência", "")
        resp.gerar_pac = bool(row.get("Gerar PAC", False))
        rows_for_score.append({"resultado": resp.resultado, "aplicavel": resp.aplicavel, "critico": resp.item.critico})
    score, result, _ = calculate_nr12_score(rows_for_score)
    verificacao.pontuacao = score
    verificacao.resultado = result
    machine = verificacao.maquina
    machine.ultima_auditoria = verificacao.data_verificacao
    machine.status_nr12 = result if result != "Conforme" else suggest_machine_status(session, machine)
    return result


def ehs_respostas_df(session, auditoria_id=None, site_ids=None):
    q = (
        session.query(EHSResposta, EHSAuditoria, EHSRequisito, EHSIndicadorDiretiva, Site)
        .select_from(EHSResposta)
        .join(EHSAuditoria, EHSResposta.auditoria_id == EHSAuditoria.id)
        .join(EHSRequisito, EHSResposta.requisito_id == EHSRequisito.id)
        .join(EHSIndicadorDiretiva, EHSRequisito.diretiva_id == EHSIndicadorDiretiva.id)
        .join(Site, EHSAuditoria.site_auditado_id == Site.id)
    )
    if auditoria_id:
        q = q.filter(EHSAuditoria.id == auditoria_id)
    q = filter_by_sites(q, EHSAuditoria.site_auditado_id, site_ids)
    rows = []
    for resp, aud, req, diretiva, site in q.all():
        rows.append({
            "ID": resp.id,
            "Auditoria ID": aud.id,
            "Auditoria": aud.nome,
            "Site": site.codigo,
            "Diretiva": diretiva.titulo,
            "Código": req.codigo,
            "Pergunta": req.pergunta,
            "Criticidade": req.criticidade,
            "Aplicável": resp.aplicavel,
            "Status": resp.status,
            "Maturidade": resp.nota_maturidade,
            "Evidência": resp.evidencia_verificada or "",
            "Comentário": resp.comentario_auditor or "",
            "Necessita PAC": resp.necessita_pac,
        })
    return pd.DataFrame(rows)


def ehs_pacs_df(session, site_ids=None):
    q = (
        session.query(EHSPAC, EHSAuditoria, Site, EHSRequisito)
        .select_from(EHSPAC)
        .join(EHSAuditoria, EHSPAC.auditoria_id == EHSAuditoria.id)
        .join(Site, EHSPAC.site_id == Site.id)
        .outerjoin(EHSRequisito, EHSPAC.requisito_id == EHSRequisito.id)
    )
    q = filter_by_sites(q, EHSPAC.site_id, site_ids)
    rows = []
    today = date.today()
    for pac, aud, site, req in q.all():
        vencido = bool(pac.prazo and pac.prazo < today and is_open_status(pac.status))
        rows.append({
            "ID": pac.id,
            "Auditoria": aud.nome,
            "Site": site.codigo,
            "Requisito": req.codigo if req else "-",
            "Tipo": pac.tipo_achado,
            "Descrição": pac.descricao,
            "Criticidade": pac.criticidade,
            "Responsável": pac.responsavel,
            "Área": pac.area_responsavel,
            "Prazo": pac.prazo,
            "Status": "Vencido" if vencido else pac.status,
            "Vencido": vencido,
        })
    return pd.DataFrame(rows)


def conformidade_percentual(df):
    if df.empty:
        return 0.0
    valid = df[df["Status"] != "Não Aplicável"]
    if valid.empty:
        return 0.0
    score = valid["Status"].map({"Conforme": 1.0, "Parcialmente Conforme": 0.5, "Não Conforme": 0.0}).fillna(0)
    return round(float(score.mean() * 100), 1)


def maturidade_media(df):
    if df.empty:
        return 0.0
    valid = df[(df["Status"] != "Não Aplicável") & (df["Maturidade"].notna())]
    return round(float(valid["Maturidade"].mean()), 2) if not valid.empty else 0.0


def ehs_kpis(session, site_ids=None):
    audits = filter_by_sites(session.query(EHSAuditoria), EHSAuditoria.site_auditado_id, site_ids).all()
    respostas = ehs_respostas_df(session, site_ids=site_ids)
    pacs = ehs_pacs_df(session, site_ids=site_ids)
    return {
        "planejadas": sum(1 for a in audits if a.status == "Planejada"),
        "andamento": sum(1 for a in audits if a.status == "Em andamento"),
        "concluidas": sum(1 for a in audits if a.status == "Concluída"),
        "conformidade": conformidade_percentual(respostas),
        "maturidade": maturidade_media(respostas),
        "pacs_abertos": int((~pacs["Status"].isin(["Concluído", "Cancelado"])).sum()) if not pacs.empty else 0,
        "pacs_vencidos": int(pacs["Vencido"].sum()) if not pacs.empty else 0,
        "criticas": int((pacs["Criticidade"].isin(["Crítica", "Crítico", "Alta"])).sum()) if not pacs.empty else 0,
        "sites_auditados": len({a.site_auditado_id for a in audits}),
    }


def create_ehs_auditoria(session, data):
    aud = EHSAuditoria(**data)
    session.add(aud)
    session.flush()
    ensure_ehs_respostas(session, aud.id)
    return aud


def apply_ehs_respostas(session, edited_rows):
    for row in edited_rows:
        resp = session.get(EHSResposta, int(row["ID"]))
        if not resp:
            continue
        resp.aplicavel = bool(row.get("Aplicável", True))
        resp.status = "Não Aplicável" if not resp.aplicavel else row.get("Status", "Conforme")
        try:
            resp.nota_maturidade = max(0, min(5, int(row.get("Maturidade", 3))))
        except (TypeError, ValueError):
            resp.nota_maturidade = 3
        resp.evidencia_verificada = row.get("Evidência", "")
        resp.comentario_auditor = row.get("Comentário", "")
        resp.necessita_pac = bool(row.get("Necessita PAC", False))
        resp.data_avaliacao = datetime.utcnow()
