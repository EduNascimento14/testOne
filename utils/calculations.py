from __future__ import annotations

from datetime import date, timedelta
import pandas as pd
from sqlalchemy.orm import Session
from models import ActionPlan, Audit, ChangeManagement, Document, Machine, Site, StatusHistory
from utils.validations import MANDATORY_DOCUMENTS, SAFETY_CHANGE_TYPES, is_due_soon, is_overdue


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
        result = "Não conforme"
    elif score < 90:
        result = "Conforme com ressalvas"
    else:
        result = "Conforme"
    return score, result, critical_nc


def suggest_machine_status(session: Session, machine: Machine) -> tuple[str, list[str]]:
    reasons: list[str] = []
    today = date.today()
    open_actions = [a for a in machine.actions if a.status not in {"Concluída", "Cancelada"}]
    if any(a.classification == "Crítico" and (a.status == "Vencida" or (a.due_date and a.due_date < today)) for a in open_actions):
        reasons.append("Ação crítica vencida")
        return "Não conforme", reasons
    if any(a.classification == "Crítico" for a in open_actions):
        reasons.append("Ação crítica aberta")
    docs_by_type = {d.document_type: document_status(d.expiry_date, d.status) for d in machine.documents}
    missing = [doc for doc in MANDATORY_DOCUMENTS if not getattr(machine, {"Laudo NR-12": "has_nr12_report", "ART": "has_art", "Apreciação de risco": "has_risk_assessment"}[doc]) and doc not in docs_by_type]
    expired = [doc for doc, status in docs_by_type.items() if doc in MANDATORY_DOCUMENTS and status == "Vencido"]
    if missing or expired:
        reasons.append("Documentação legal essencial ausente ou vencida")
        return "Não conforme", reasons
    latest_audit = session.query(Audit).filter_by(machine_id=machine.id).order_by(Audit.audit_date.desc(), Audit.id.desc()).first()
    if latest_audit and latest_audit.result == "Não conforme":
        reasons.append("Última auditoria não conforme")
        return "Não conforme", reasons
    critical_pending_change = any(c.impacts_safety and c.status in {"Solicitada", "Em análise", "Implementada"} and not (c.ehs_approval and (c.maintenance_approval or c.engineering_approval)) for c in machine.changes)
    if critical_pending_change:
        reasons.append("Mudança crítica sem validação/aprovação")
        return "Não conforme", reasons
    if open_actions:
        reasons.append("Ações médias/baixas abertas")
    if not latest_audit:
        reasons.append("Sem auditoria registrada")
    elif latest_audit.result == "Conforme com ressalvas":
        reasons.append("Última auditoria com ressalvas")
    if machine.next_audit_date and machine.next_audit_date < today:
        reasons.append("Auditoria vencida")
        return "Não conforme", reasons
    if machine.next_audit_date and machine.next_audit_date <= today + timedelta(days=60):
        reasons.append("Auditoria próxima do vencimento")
    post_moc_pending = any(c.status == "Implementada" and c.needs_post_change_audit for c in machine.changes)
    if post_moc_pending:
        reasons.append("Mudança implementada aguardando auditoria pós-MOC")
    if reasons:
        return "Conforme com ressalvas", reasons
    return "Conforme", ["Requisitos essenciais atendidos"]


def update_machine_suggestion(session: Session, machine: Machine, changed_by: str | None = None) -> str:
    new_status, reasons = suggest_machine_status(session, machine)
    previous = machine.suggested_status or machine.nr12_status
    machine.suggested_status = new_status
    if machine.nr12_status == "Conforme" and new_status != "Conforme":
        machine.nr12_status = new_status
    if previous != new_status:
        session.add(StatusHistory(machine_id=machine.id, previous_status=previous, new_status=new_status, reason="; ".join(reasons), changed_by=changed_by))
    return new_status


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
    return {
        "total_machines": len(machines),
        "conformes": sum(1 for m in machines if m.nr12_status == "Conforme"),
        "ressalvas": sum(1 for m in machines if m.nr12_status == "Conforme com ressalvas"),
        "nao_conformes": sum(1 for m in machines if m.nr12_status == "Não conforme"),
        "em_adequacao": sum(1 for m in machines if m.nr12_status == "Em adequação"),
        "acoes_abertas": sum(1 for a in actions if a.status not in {"Concluída", "Cancelada"}),
        "acoes_vencidas": sum(1 for a in actions if a.status not in {"Concluída", "Cancelada"} and a.due_date and a.due_date < today),
        "acoes_criticas": sum(1 for a in actions if a.classification == "Crítico" and a.status not in {"Concluída", "Cancelada"}),
        "auditorias_vencidas": sum(1 for m in machines if m.next_audit_date and m.next_audit_date < today),
        "documentos_vencidos": sum(1 for d in docs if document_status(d.expiry_date, d.status) == "Vencido"),
        "sem_laudo": sum(1 for m in machines if not m.has_nr12_report),
        "sem_art": sum(1 for m in machines if not m.has_art),
        "sem_apreciacao": sum(1 for m in machines if not m.has_risk_assessment),
        "mudancas_abertas": sum(1 for c in changes if c.status not in {"Encerrada", "Reprovada"}),
        "mudancas_criticas_sem_validacao": sum(1 for c in changes if c.impacts_safety and c.status not in {"Encerrada", "Reprovada"} and not (c.ehs_approval and (c.maintenance_approval or c.engineering_approval))),
    }
