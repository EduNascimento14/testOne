import os
from pathlib import Path

APP_TITLE = "Plataforma Corporativa EHS"
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///ehs_integrado.db")
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "uploads"))

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

STATUS_AUDITORIA = ["Planejada", "Em andamento", "Concluída", "Cancelada"]
STATUS_CONFORMIDADE = ["Conforme", "Parcialmente Conforme", "Não Conforme", "Não Aplicável"]
STATUS_PAC = ["Aberto", "Em andamento", "Concluído", "Cancelado"]
TIPOS_ACHADO = [
    "Não conformidade crítica",
    "Não conformidade maior",
    "Não conformidade menor",
    "Observação",
    "Oportunidade de melhoria",
    "Boa prática",
]
PRIORIDADES = ["Crítica", "Alta", "Média", "Baixa"]
CRITICIDADES = ["Crítico", "Alto", "Médio", "Baixo"]

STATUS_MAQUINA = [
    "Conforme",
    "Conforme com observação",
    "Pendente de ação não crítica",
    "Bloqueada por desvio crítico",
    "Fora de uso",
    "Não aplicável",
]
TIPOS_EQUIPAMENTO = [
    "Máquina operatriz",
    "Prensa",
    "Injetora",
    "Transportador",
    "Robô / célula automatizada",
    "Caldeiraria / utilidade",
    "Equipamento de elevação",
    "Outro",
]
TIPOS_DOCUMENTO_NR12 = [
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
DOCUMENTOS_ESSENCIAIS_NR12 = ["Apreciação de risco", "Laudo NR-12", "ART"]
TIPOS_VERIFICACAO_NR12 = [
    "Checklist operacional",
    "Inspeção de manutenção",
    "Auditoria EHS",
    "Auditoria corporativa",
    "Auditoria pós-MOC",
    "Auditoria extraordinária após incidente/quase-acidente",
]
TIPOS_MOC_CRITICA = [
    "Alteração de software/PLC",
    "Substituição de componente de segurança",
    "Remoção temporária de proteção",
    "Retrofit",
    "Manutenção corretiva crítica",
    "Mudança de layout com impacto em segurança",
    "Alteração mecânica, elétrica, pneumática ou hidráulica",
]

CHECKLIST_BASE = [
    {"codigo": "EHS-01", "titulo": "Liderança e Gestão EHS", "descricao": "Governança, responsabilidades, indicadores e cultura de EHS.", "perguntas": ["Existe política de EHS formalizada e comunicada?", "A liderança participa ativamente das ações de EHS?", "Existem metas e indicadores de EHS definidos?", "Os indicadores são monitorados periodicamente?", "Existem reuniões periódicas de EHS?", "Existe definição clara de responsabilidades EHS?", "A organização promove cultura de reporte sem culpa?", "Existem mecanismos formais de melhoria contínua?", "Os riscos críticos são acompanhados pela liderança?", "Existe integração entre EHS e operação?"]},
    {"codigo": "EHS-02", "titulo": "Conformidade Legal", "descricao": "Gestão de requisitos legais, licenças, evidências e prazos.", "perguntas": ["Existe levantamento atualizado de requisitos legais?", "As licenças ambientais estão válidas?", "Existem controles para condicionantes legais?", "Os requisitos legais possuem evidências documentadas?", "Existe monitoramento periódico de atendimento legal?", "Há gestão de prazos legais?", "Existe plano para adequação de não conformidades legais?", "Existem auditorias legais periódicas?", "Há rastreabilidade documental?", "Os responsáveis legais estão definidos?"]},
    {"codigo": "EHS-03", "titulo": "Gestão de Riscos", "descricao": "Identificação de perigos, avaliação de riscos e eficácia dos controles.", "perguntas": ["Existe processo formal de identificação de perigos?", "Os riscos ocupacionais estão avaliados?", "Existem controles implementados para riscos críticos?", "Há hierarquia de controles aplicada?", "Existe revisão periódica das análises de risco?", "Mudanças operacionais passam por avaliação de risco?", "Existe gestão de mudanças formal?", "Há participação dos trabalhadores nas análises?", "Os riscos ambientais estão avaliados?", "Existe monitoramento de eficácia dos controles?"]},
    {"codigo": "EHS-04", "titulo": "Investigação de Incidentes", "descricao": "Reporte, investigação, causas sistêmicas e ações corretivas.", "perguntas": ["Existe processo formal de investigação?", "Os incidentes são reportados adequadamente?", "As causas sistêmicas são avaliadas?", "Há definição de ações corretivas?", "Existe acompanhamento das ações?", "Os aprendizados são compartilhados?", "Há foco em melhoria do sistema e não culpabilização?", "Near misses são investigados?", "Existe rastreabilidade das investigações?", "Indicadores de incidentes são monitorados?"]},
    {"codigo": "EHS-05", "titulo": "Treinamentos e Competências", "descricao": "Matriz de treinamento, competências críticas e reciclagens.", "perguntas": ["Existe matriz de treinamento atualizada?", "Os treinamentos obrigatórios estão válidos?", "Há avaliação de eficácia dos treinamentos?", "Os terceiros recebem treinamentos adequados?", "Existe controle de vencimentos?", "As competências críticas estão mapeadas?", "Há registros formais dos treinamentos?", "Existe integração EHS para novos colaboradores?", "Os líderes recebem treinamento em EHS?", "Existe reciclagem periódica?"]},
    {"codigo": "EHS-06", "titulo": "Gestão Ambiental", "descricao": "Resíduos, MTR, CDF, emissões, efluentes e resposta ambiental.", "perguntas": ["Existe segregação adequada de resíduos?", "Os resíduos possuem identificação?", "Existe controle de MTR?", "Os CDFs são controlados?", "Há controle de empresas destinadoras?", "Existem inspeções ambientais periódicas?", "Há controle de emissões atmosféricas?", "Existe controle de efluentes?", "Existe plano de resposta ambiental?", "Há monitoramento de indicadores ambientais?"]},
    {"codigo": "EHS-07", "titulo": "Segurança Operacional", "descricao": "Máquinas, NR-12, bloqueio, EPI, permissões e controles críticos.", "perguntas": ["Máquinas possuem proteções adequadas?", "Existe atendimento à NR-12?", "Há bloqueio e etiquetagem implementados?", "Os EPIs estão adequados?", "Existe inspeção periódica de segurança?", "Há controle de permissões de trabalho?", "Existe controle de trabalho em altura?", "Espaços confinados possuem gestão adequada?", "Existe controle de energia perigosa?", "Há inspeções comportamentais estruturadas?"]},
    {"codigo": "EHS-08", "titulo": "Preparação e Resposta a Emergências", "descricao": "Plano de emergência, brigada, simulados e equipamentos críticos.", "perguntas": ["Existe plano de emergência atualizado?", "Há brigada treinada?", "Existem simulados periódicos?", "Os equipamentos de emergência estão inspecionados?", "Existe controle de produtos perigosos?", "Há rotas de fuga sinalizadas?", "Existe comunicação de emergência definida?", "Os cenários críticos foram avaliados?", "Existe integração com serviços externos?", "Há registros dos simulados?"]},
]

CHECKLIST_NR12 = {
    "Checklist operacional": [
        ("OP-01", "Proteções fixas e móveis estão íntegras e posicionadas.", "Crítico"),
        ("OP-02", "Intertravamentos e sensores aparentam condição normal de operação.", "Crítico"),
        ("OP-03", "Botões de emergência estão acessíveis e identificados.", "Crítico"),
        ("OP-04", "Não há bypass, improviso ou remoção de dispositivo de segurança.", "Crítico"),
        ("OP-05", "Operadores comunicaram desvios e preservaram proteções.", "Alto"),
    ],
    "Inspeção de manutenção": [
        ("MN-01", "Teste funcional dos dispositivos de segurança foi executado.", "Crítico"),
        ("MN-02", "Relés, PLCs e sensores de segurança mantêm configuração validada.", "Crítico"),
        ("MN-03", "Intervenções possuem registro técnico e liberação segura.", "Alto"),
        ("MN-04", "Componentes substituídos preservam função de segurança.", "Crítico"),
        ("MN-05", "Não há pendência técnica que comprometa a operação segura.", "Alto"),
    ],
    "Auditoria EHS": [
        ("EHS-12-01", "Máquina possui documentos essenciais NR-12 válidos.", "Crítico"),
        ("EHS-12-02", "PACs críticos estão tratados dentro do prazo.", "Crítico"),
        ("EHS-12-03", "MOCs com impacto em segurança foram aprovadas e validadas.", "Crítico"),
        ("EHS-12-04", "Treinamentos e evidências de operação segura estão vigentes.", "Alto"),
        ("EHS-12-05", "Próxima verificação está planejada conforme criticidade.", "Médio"),
    ],
}
