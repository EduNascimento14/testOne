from __future__ import annotations

from datetime import date

SITES = ["SJC", "DIA", "CAC", "JAC", "JUN", "PER"]
ROLES = ["Admin Corporativo", "EHS Site", "Manutenção", "Produção / Operação", "Visualizador"]
MACHINE_STATUS = ["Conforme", "Conforme com observação", "Pendente de ação não crítica", "Bloqueada por desvio crítico", "Em readequação", "Fora de uso", "Não aplicável"]
CRITICALITIES = ["Alta", "Média", "Baixa"]
DOCUMENT_TYPES = [
    "Inventário NR-12", "Apreciação de risco", "Laudo NR-12", "ART", "Projeto mecânico",
    "Projeto elétrico", "Diagrama de segurança", "Manual de operação", "Manual de manutenção",
    "Registro de treinamento", "Evidência fotográfica", "Checklist de validação", "Termo de liberação para uso",
    "MOC / Gestão de Mudança", "Registro de intervenção", "Registro de bloqueio/liberação", "Termo anual NR-12", "Outros",
]
MANDATORY_DOCUMENTS = ["Laudo NR-12", "ART", "Apreciação de risco"]
DOCUMENT_STATUS = ["Válido", "Vencido", "Próximo do vencimento", "Ausente", "Em revisão"]
AUDIT_TYPES = ["Checklist operacional", "Inspeção de manutenção", "Auditoria EHS", "Auditoria corporativa", "Auditoria pós-MOC", "Auditoria extraordinária após incidente/quase-acidente"]
SCHEDULED_AUDIT_TYPES = ["Checklist operacional", "Inspeção de manutenção", "Auditoria EHS"]
AUDIT_INTERVAL_DAYS = {
    "Alta": {"Checklist operacional": 1, "Inspeção de manutenção": 30, "Auditoria EHS": 90},
    "Média": {"Checklist operacional": 7, "Inspeção de manutenção": 90, "Auditoria EHS": 180},
    "Baixa": {"Checklist operacional": 30, "Inspeção de manutenção": 180, "Auditoria EHS": 365},
}
AUDIT_RESULTS = ["Conforme", "Conforme com observação", "Pendente de ação não crítica", "Bloqueada por desvio crítico"]
ITEM_RESULTS = ["Conforme", "Não conforme", "Não aplicável"]
ACTION_ORIGINS = ["Auditoria", "Inspeção", "Ocorrência", "MOC", "Observação operacional"]
ACTION_CLASSES = ["Crítico", "Maior", "Menor"]
RESPONSIBLE_AREAS = ["EHS", "Manutenção", "Produção", "Engenharia", "Qualidade", "Outro"]
ACTION_STATUS = ["Aberta", "Em andamento", "Aguardando validação", "Concluída", "Vencida", "Cancelada"]
CHANGE_TYPES = ["Alteração mecânica", "Alteração elétrica", "Alteração pneumática/hidráulica", "Alteração de software/PLC", "Mudança de layout", "Substituição de componente de segurança", "Remoção temporária de proteção", "Retrofit", "Manutenção corretiva crítica", "Outro"]
CHANGE_STATUS = ["Solicitada", "Em análise", "Aprovada", "Reprovada", "Implementada", "Encerrada"]
SAFETY_CHANGE_TYPES = {"Alteração de software/PLC", "Substituição de componente de segurança", "Remoção temporária de proteção", "Retrofit", "Manutenção corretiva crítica"}


def audit_interval_days(criticality: str | None, audit_type: str) -> int | None:
    return AUDIT_INTERVAL_DAYS.get(criticality or "Média", {}).get(audit_type)


def audit_periodicity_label(criticality: str | None, audit_type: str) -> str:
    days = audit_interval_days(criticality, audit_type)
    if days is None:
        return "Extraordinária"
    if days == 1:
        return "Diária / por turno"
    if days == 7:
        return "Semanal"
    if days == 30:
        return "Mensal"
    if days == 90:
        return "Trimestral"
    if days == 180:
        return "Semestral"
    if days == 365:
        return "Anual"
    return f"A cada {days} dias"


def is_overdue(d: date | None) -> bool:
    return bool(d and d < date.today())


def is_due_soon(d: date | None, days: int = 60) -> bool:
    return bool(d and 0 <= (d - date.today()).days <= days)


def normalize_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"sim", "s", "yes", "true", "1"}
