from datetime import date, timedelta


SITES_PADRAO = ["SJC", "DIA", "CAC", "JAC", "JUN", "PER"]
PERFIS = [
    "Admin_LAG",
    "EHS_Local",
    "Auditor",
    "Manutencao",
    "Producao_Operacao",
    "Engenharia",
    "Responsavel_Acao",
    "Visualizador",
]

CRITICIDADES = ["Crítico", "Alto", "Médio", "Baixo"]
STATUS_NR12 = [
    "Conforme",
    "Conforme com observação",
    "Pendente de ação não crítica",
    "Bloqueada por desvio crítico",
    "Em readequação",
    "Fora de uso",
    "Não aplicável",
]
DOCUMENTOS_NR12 = [
    "Inventário NR-12",
    "Apreciação de risco",
    "Laudo NR-12",
    "ART",
    "Projeto mecânico",
    "Projeto elétrico",
    "Diagrama de segurança",
    "Manual de operação",
    "Manual de manutenção",
    "Registro de treinamento",
    "Evidência fotográfica",
    "Checklist de validação",
    "Termo de liberação para uso",
    "MOC / Gestão de Mudança",
    "Registro de intervenção",
    "Registro de bloqueio/liberação",
    "Termo anual NR-12",
    "Outros",
]
DOCUMENTOS_ESSENCIAIS = ["Laudo NR-12", "ART", "Apreciação de risco"]
TIPOS_VERIFICACAO_NR12 = [
    "Checklist operacional",
    "Inspeção de manutenção",
    "Auditoria EHS",
    "Auditoria corporativa",
    "Auditoria pós-MOC",
    "Auditoria extraordinária após incidente/quase-acidente",
]
TIPOS_MUDANCA_CRITICA = [
    "Alteração de software/PLC",
    "Alteração de relé/controlador de segurança",
    "Substituição de componente de segurança",
    "Remoção temporária de proteção",
    "Alteração de proteção fixa/móvel",
    "Alteração de sensores, cortinas, scanners ou intertravamentos",
    "Mudança de layout com impacto em segurança",
    "Retrofit",
    "Manutenção corretiva crítica",
    "Alteração mecânica, elétrica, pneumática ou hidráulica",
]

STATUS_PAC = ["Aberto", "Em andamento", "Concluído", "Cancelado"]
CLASSIFICACOES = ["Crítico", "Maior", "Menor"]
STATUS_CONFORMIDADE_EHS = ["Conforme", "Parcialmente Conforme", "Não Conforme", "Não Aplicável"]
STATUS_AUDITORIA = ["Planejada", "Em andamento", "Concluída", "Cancelada"]


def document_status(expiry_date, explicit_status="Válido"):
    if explicit_status in {"Ausente", "Em revisão"}:
        return explicit_status
    if expiry_date and expiry_date < date.today():
        return "Vencido"
    if expiry_date and expiry_date <= date.today() + timedelta(days=60):
        return "Próximo do vencimento"
    return "Válido"


def audit_interval_days(criticality, audit_type):
    if audit_type == "Checklist operacional":
        return 7 if criticality in {"Crítico", "Alto"} else 30
    if audit_type == "Inspeção de manutenção":
        return 30 if criticality in {"Crítico", "Alto"} else 90
    if audit_type in {"Auditoria EHS", "Auditoria corporativa"}:
        return 180 if criticality in {"Crítico", "Alto"} else 365
    return None


def is_open_status(status):
    return status not in {"Concluído", "Cancelado", "Encerrada", "Reprovada"}
