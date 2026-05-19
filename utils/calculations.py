from __future__ import annotations

from datetime import date, timedelta
import pandas as pd
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session, selectinload
from models import ActionPlan, Audit, ChangeManagement, Document, Machine, Site, StatusHistory
from utils.validations import MANDATORY_DOCUMENTS, SCHEDULED_AUDIT_TYPES, audit_interval_days, audit_periodicity_label


def document_status(expiry_date, explicit_status: str = "Válido") -> str:
    if explicit_status in {"Ausente", "Em revisão"}:
        return explicit_status
    if expiry_date and expiry_date < date.today():
        return "Vencido"
    if expiry_date and (expiry_date - date.today()).days <= 60:
        return "Próximo do vencimento"
    return "Válido"


def calculate_audit_result(items: list[dict]) -> tuple[float, str, bool]:
    applicable = [i for i in items if i.get("result") != "Não aplicável"]
    conforming = [i for i in applicable if i.get("result") == "Conforme"]
    critical_nc = any(i.get("is_critical") and i.get("result") == "Não conforme" for i in applicable)
    score = round((len(conforming) / len(applicable) * 100), 1) if applicable else 100.0
    if critical_nc or score < 70:
        result = "Bloqueada por desvio crítico" if critical_nc else "Pendente de ação não crítica"
    elif score < 90:
        result = "Conforme com observação"
    else:
        result = "Conforme"
    return score, result, critical_nc


def _machine_identity(machine: Machine) -> int:
    identity = sa_inspect(machine).identity
    if identity:
        return int(identity[0])
    return int(machine.id)


def _load_machine_for_status(session: Session, machine: Machine) -> Machine:
    return (
        session.query(Machine)
        .options(
            selectinload(Machine.documents),
            selectinload(Machine.audits),
            selectinload(Machine.actions),
            selectinload(Machine.changes),
        )
        .filter(Machine.id == _machine_identity(machine))
        .one()
    )


def latest_audit_date(session: Session, machine: Machine, audit_type: str) -> date | None:
    audit = (
        session.query(Audit)
        .filter(Audit.machine_id == machine.id, Audit.audit_type == audit_type)
        .order_by(Audit.audit_date.desc(), Audit.id.desc())
        .first()
    )
    return audit.audit_date if audit else None


def next_due_date(session: Session, machine: Machine, audit_type: str) -> date | None:
    interval = audit_interval_days(machine.criticality, audit_type)
    if interval is None:
        return None
    latest = latest_audit_date(session, machine, audit_type)
    if latest:
        base = latest
    elif machine.last_nr12_adequacy_date:
        base = machine.last_nr12_adequacy_date
    elif machine.created_at:
        base = machine.created_at.date()
    else:
        base = date.today()
    return base + timedelta(days=interval)


def suggest_machine_status(session: Session, machine: Machine) -> tuple[str, list[str]]:
    machine = _load_machine_for_status(session, machine)
    reasons: list[str] = []
    today = date.today()
    open_actions = [a for a in machine.actions if a.status not in {"Concluída", "Cancelada"}]
    if any(a.classification == "Crítico" and (a.status == "Vencida" or (a.due_date and a.due_date < today)) for a in open_actions):
        return "Bloqueada por desvio crítico", ["Ação crítica vencida"]
    if any(a.classification == "Crítico" for a in open_actions):
        return "Bloqueada por desvio crítico", ["Ação crítica aberta"]

    docs_by_type = {d.document_type: document_status(d.expiry_date, d.status) for d in machine.documents}
    missing = [doc for doc in MANDATORY_DOCUMENTS if not getattr(machine, {"Laudo NR-12": "has_nr12_report", "ART": "has_art", "Apreciação de risco": "has_risk_assessment"}[doc]) and doc not in docs_by_type]
    expired = [doc for doc, status in docs_by_type.items() if doc in MANDATORY_DOCUMENTS and status == "Vencido"]
    if missing or expired:
        return "Pendente de ação não crítica", ["Documentação legal essencial ausente ou vencida"]

    latest_audit = session.query(Audit).filter_by(machine_id=machine.id).order_by(Audit.audit_date.desc(), Audit.id.desc()).first()
    if latest_audit and latest_audit.result == "Bloqueada por desvio crítico":
        return "Bloqueada por desvio crítico", ["Última auditoria exigiu bloqueio"]
    if latest_audit and latest_audit.result == "Pendente de ação não crítica":
        return "Pendente de ação não crítica", ["Última auditoria com pendência não crítica"]

    critical_pending_change = any(c.impacts_safety and c.status in {"Solicitada", "Em análise", "Implementada"} and not (c.ehs_approval and (c.maintenance_approval or c.engineering_approval)) for c in machine.changes)
    if critical_pending_change:
        return "Bloqueada por desvio crítico", ["Mudança crítica sem validação/aprovação"]

    if open_actions:
        reasons.append("Ações maiores/menores abertas")
    if not latest_audit:
        reasons.append("Sem auditoria registrada")
    elif latest_audit.result == "Conforme com observação":
        reasons.append("Última auditoria com observação")

    ehs_due = next_due_date(session, machine, "Auditoria EHS")
    if ehs_due and ehs_due < today:
        return "Pendente de ação não crítica", ["Auditoria EHS vencida"]
    if ehs_due and ehs_due <= today + timedelta(days=60):
        reasons.append("Auditoria EHS próxima do vencimento")

    if any(c.status == "Implementada" and c.needs_post_change_audit for c in machine.changes):
        reasons.append("Mudança implementada aguardando auditoria pós-MOC")
    if reasons:
        return "Conforme com observação", reasons
    return "Conforme", ["Requisitos essenciais atendidos"]


def update_machine_suggestion(session: Session, machine: Machine, changed_by: str | None = None) -> str:
    machine = _load_machine_for_status(session, machine)
    new_status, reasons = suggest_machine_status(session, machine)
    previous = machine.suggested_status or machine.nr12_status
    machine.suggested_status = new_status
    if machine.nr12_status not in {"Fora de uso", "Não aplicável", "Em readequação"}:
        machine.nr12_status = new_status
    if previous != new_status:
        session.add(StatusHistory(machine_id=machine.id, previous_status=previous, new_status=new_status, reason="; ".join(reasons), changed_by=changed_by))
    return new_status


def audit_schedule_df(session: Session, machine_ids: list[int] | None = None) -> pd.DataFrame:
    rows = []
    today = date.today()
    query = session.query(Machine).join(Site).order_by(Site.code, Machine.machine_code)
    if machine_ids is not None:
        if not machine_ids:
            return pd.DataFrame(rows)
        query = query.filter(Machine.id.in_(machine_ids))
    for machine in query.all():
        for audit_type in SCHEDULED_AUDIT_TYPES:
            due = next_due_date(session, machine, audit_type)
            if due is None:
                continue
            latest = latest_audit_date(session, machine, audit_type)
            days = (due - today).days
            status = "Vencida" if days < 0 else "Próxima" if days <= 30 else "Programada"
            rows.append({
                "ID": machine.id,
                "Site": machine.site.code,
                "Área": machine.area,
                "Máquina": machine.machine_code,
                "Nome": machine.name,
                "Criticidade": machine.criticality,
                "Tipo": audit_type,
                "Periodicidade": audit_periodicity_label(machine.criticality, audit_type),
                "Última auditoria": latest,
                "Próxima auditoria": due,
                "Dias": days,
                "Status do prazo": status,
                "Status NR-12": machine.nr12_status,
                "Responsável": machine.area_owner,
            })
    return pd.DataFrame(rows)


def machines_df(session: Session) -> pd.DataFrame:
    rows = []
    for m in session.query(Machine).join(Site).all():
        rows.append({"ID": m.id, "Código": m.machine_code, "Site": m.site.code, "Área": m.area, "Linha/Processo": m.line_process, "Máquina": m.name, "Fabricante": m.manufacturer, "Modelo": m.model, "Série": m.serial_number, "Ano": m.manufacturing_year, "Tipo": m.equipment_type, "Responsável": m.area_owner, "Criticidade": m.criticality, "Status NR-12": m.nr12_status, "Status sugerido": m.suggested_status, "Última auditoria": m.last_audit_date, "Próxima auditoria": m.next_audit_date, "Laudo": "Sim" if m.has_nr12_report else "Não", "ART": "Sim" if m.has_art else "Não", "Apreciação risco": "Sim" if m.has_risk_assessment else "Não", "Manual": "Sim" if m.has_updated_manual else "Não", "Treinamento": "Sim" if m.has_training else "Não"})
    return pd.DataFrame(rows)


def actions_df(session: Session) -> pd.DataFrame:
    rows = []
    for a in session.query(ActionPlan).join(Machine).join(Site).all():
        vencida = a.status not in {"Concluída", "Cancelada"} and bool(a.due_date and a.due_date < date.today())
        rows.append({"ID": a.id, "Site": a.machine.site.code, "Máquina": a.machine.machine_code, "Origem": a.origin, "Desvio": a.deviation_description, "Classificação": a.classification, "Responsável": a.responsible, "Área": a.responsible_area, "Prazo": a.due_date, "Status": "Vencida" if vencida else a.status, "Vencida": vencida, "Validação EHS": a.ehs_validation})
    return pd.DataFrame(rows)


def dashboard_kpis(session: Session) -> dict:
    today = date.today()
    machines = session.query(Machine).all()
    actions = session.query(ActionPlan).all()
    docs = session.query(Document).all()
    changes = session.query(ChangeManagement).all()
    schedule = audit_schedule_df(session)
    return {
        "total_machines": len(machines),
        "conformes": sum(1 for m in machines if m.nr12_status == "Conforme"),
        "observacao": sum(1 for m in machines if m.nr12_status == "Conforme com observação"),
        "pendentes": sum(1 for m in machines if m.nr12_status == "Pendente de ação não crítica"),
        "bloqueadas": sum(1 for m in machines if m.nr12_status == "Bloqueada por desvio crítico"),
        "em_readequacao": sum(1 for m in machines if m.nr12_status == "Em readequação"),
        "acoes_abertas": sum(1 for a in actions if a.status not in {"Concluída", "Cancelada"}),
        "acoes_vencidas": sum(1 for a in actions if a.status not in {"Concluída", "Cancelada"} and a.due_date and a.due_date < today),
        "acoes_criticas": sum(1 for a in actions if a.classification == "Crítico" and a.status not in {"Concluída", "Cancelada"}),
        "auditorias_vencidas": int((schedule["Status do prazo"] == "Vencida").sum()) if not schedule.empty else 0,
        "auditorias_30d": int((schedule["Status do prazo"] == "Próxima").sum()) if not schedule.empty else 0,
        "documentos_vencidos": sum(1 for d in docs if document_status(d.expiry_date, d.status) == "Vencido"),
        "sem_laudo": sum(1 for m in machines if not m.has_nr12_report),
        "sem_art": sum(1 for m in machines if not m.has_art),
        "sem_apreciacao": sum(1 for m in machines if not m.has_risk_assessment),
        "mudancas_abertas": sum(1 for c in changes if c.status not in {"Encerrada", "Reprovada"}),
        "mudancas_criticas_sem_validacao": sum(1 for c in changes if c.impacts_safety and c.status not in {"Encerrada", "Reprovada"} and not (c.ehs_approval and (c.maintenance_approval or c.engineering_approval))),
    }
