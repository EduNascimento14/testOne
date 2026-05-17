from __future__ import annotations

from datetime import date

SITES = ["SJC", "DIA", "CAC", "JAC", "JUN", "PER"]
ROLES = ["Admin Corporativo", "EHS Site", "Manutenção", "Produção / Operação", "Visualizador"]
MACHINE_STATUS = ["Conforme", "Conforme com ressalvas", "Não conforme", "Em adequação", "Fora de operação"]
CRITICALITIES = ["Alta", "Média", "Baixa"]
DOCUMENT_TYPES = [
    "Inventário NR-12", "Apreciação de risco", "Laudo NR-12", "ART", "Projeto mecânico",
    "Projeto elétrico", "Diagrama de segurança", "Manual de operação", "Manual de manutenção",
    "Registro de treinamento", "Evidência fotográfica", "Checklist de validação", "Termo de liberação para uso",
    "MOC / Gestão de Mudança", "Outros",
]
MANDATORY_DOCUMENTS = ["Laudo NR-12", "ART", "Apreciação de risco"]
DOCUMENT_STATUS = ["Válido", "Vencido", "Próximo do vencimento", "Ausente", "Em revisão"]
AUDIT_TYPES = ["Auditoria EHS", "Inspeção de manutenção", "Checklist operacional", "Auditoria corporativa", "Auditoria pós-MOC", "Auditoria extraordinária após incidente/quase-acidente"]
AUDIT_RESULTS = ["Conforme", "Conforme com ressalvas", "Não conforme"]
ITEM_RESULTS = ["Conforme", "Não conforme", "Não aplicável"]
ACTION_ORIGINS = ["Auditoria", "Inspeção", "Ocorrência", "MOC", "Observação operacional"]
ACTION_CLASSES = ["Crítico", "Alto", "Médio", "Baixo"]
RESPONSIBLE_AREAS = ["EHS", "Manutenção", "Produção", "Engenharia", "Qualidade", "Outro"]
ACTION_STATUS = ["Aberta", "Em andamento", "Aguardando validação", "Concluída", "Vencida", "Cancelada"]
CHANGE_TYPES = ["Alteração mecânica", "Alteração elétrica", "Alteração pneumática/hidráulica", "Alteração de software/PLC", "Mudança de layout", "Substituição de componente de segurança", "Remoção temporária de proteção", "Retrofit", "Manutenção corretiva crítica", "Outro"]
CHANGE_STATUS = ["Solicitada", "Em análise", "Aprovada", "Reprovada", "Implementada", "Encerrada"]
SAFETY_CHANGE_TYPES = {"Alteração de software/PLC", "Substituição de componente de segurança", "Remoção temporária de proteção", "Retrofit", "Manutenção corretiva crítica"}


def is_overdue(d: date | None) -> bool:
    return bool(d and d < date.today())


def is_due_soon(d: date | None, days: int = 60) -> bool:
    return bool(d and 0 <= (d - date.today()).days <= days)


def normalize_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"sim", "s", "yes", "true", "1"}
