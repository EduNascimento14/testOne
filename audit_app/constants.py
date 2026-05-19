import os
from pathlib import Path

APP_TITLE = "Auditoria Cruzada de EHS Directives"
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///ehs_audit.db")
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "uploads"))

SITES_PADRAO = ["SJC", "DIA", "CAC", "JAC", "JUN", "PER"]
STATUS_AUDITORIA = ["Planejada", "Em andamento", "Concluída", "Cancelada"]
STATUS_CONFORMIDADE = ["Conforme", "Parcialmente Conforme", "Não Conforme", "Não Aplicável"]
STATUS_ACHADO = ["Aberto", "Em andamento", "Concluído", "Vencido", "Cancelado"]
TIPOS_ACHADO = ["Não conformidade crítica", "Não conformidade maior", "Não conformidade menor", "Observação", "Oportunidade de melhoria", "Boa prática"]
PRIORIDADES = ["Alta", "Média", "Baixa"]
CRITICIDADES = ["Crítico", "Alto", "Médio", "Baixo"]
PERFIS = ["Admin_LAG", "EHS_Local", "Auditor", "Visualizador", "Responsavel_Acao"]

RESPOSTAS_COLUMNS = ["id", "auditoria_id", "auditoria", "site", "ciclo", "diretiva", "codigo_requisito", "pergunta", "criticidade", "aplicavel", "status", "nota_maturidade", "evidencia_verificada", "comentario_auditor", "necessita_acao"]
ACHADOS_COLUMNS = ["id", "auditoria", "site", "requisito", "tipo_achado", "descricao", "responsavel", "prazo", "status", "prioridade", "vencido"]

CHECKLIST_BASE = [
    {
        "codigo": "EHS-01",
        "titulo": "Liderança e Gestão EHS",
        "descricao": "Governança, responsabilidades, indicadores e cultura de EHS.",
        "perguntas": [
            "Existe política de EHS formalizada e comunicada?",
            "A liderança participa ativamente das ações de EHS?",
            "Existem metas e indicadores de EHS definidos?",
            "Os indicadores são monitorados periodicamente?",
            "Existem reuniões periódicas de EHS?",
            "Existe definição clara de responsabilidades EHS?",
            "A organização promove cultura de reporte sem culpa?",
            "Existem mecanismos formais de melhoria contínua?",
            "Os riscos críticos são acompanhados pela liderança?",
            "Existe integração entre EHS e operação?",
        ],
    },
    {
        "codigo": "EHS-02",
        "titulo": "Conformidade Legal",
        "descricao": "Gestão de requisitos legais, licenças, evidências e prazos.",
        "perguntas": [
            "Existe levantamento atualizado de requisitos legais?",
            "As licenças ambientais estão válidas?",
            "Existem controles para condicionantes legais?",
            "Os requisitos legais possuem evidências documentadas?",
            "Existe monitoramento periódico de atendimento legal?",
            "Há gestão de prazos legais?",
            "Existe plano para adequação de não conformidades legais?",
            "Existem auditorias legais periódicas?",
            "Há rastreabilidade documental?",
            "Os responsáveis legais estão definidos?",
        ],
    },
    {
        "codigo": "EHS-03",
        "titulo": "Gestão de Riscos",
        "descricao": "Identificação de perigos, avaliação de riscos e eficácia dos controles.",
        "perguntas": [
            "Existe processo formal de identificação de perigos?",
            "Os riscos ocupacionais estão avaliados?",
            "Existem controles implementados para riscos críticos?",
            "Há hierarquia de controles aplicada?",
            "Existe revisão periódica das análises de risco?",
            "Mudanças operacionais passam por avaliação de risco?",
            "Existe gestão de mudanças formal?",
            "Há participação dos trabalhadores nas análises?",
            "Os riscos ambientais estão avaliados?",
            "Existe monitoramento de eficácia dos controles?",
        ],
    },
    {
        "codigo": "EHS-04",
        "titulo": "Investigação de Incidentes",
        "descricao": "Reporte, investigação, causas sistêmicas e ações corretivas.",
        "perguntas": [
            "Existe processo formal de investigação?",
            "Os incidentes são reportados adequadamente?",
            "As causas sistêmicas são avaliadas?",
            "Há definição de ações corretivas?",
            "Existe acompanhamento das ações?",
            "Os aprendizados são compartilhados?",
            "Há foco em melhoria do sistema e não culpabilização?",
            "Near misses são investigados?",
            "Existe rastreabilidade das investigações?",
            "Indicadores de incidentes são monitorados?",
        ],
    },
    {
        "codigo": "EHS-05",
        "titulo": "Treinamentos e Competências",
        "descricao": "Matriz de treinamento, competências críticas e reciclagens.",
        "perguntas": [
            "Existe matriz de treinamento atualizada?",
            "Os treinamentos obrigatórios estão válidos?",
            "Há avaliação de eficácia dos treinamentos?",
            "Os terceiros recebem treinamentos adequados?",
            "Existe controle de vencimentos?",
            "As competências críticas estão mapeadas?",
            "Há registros formais dos treinamentos?",
            "Existe integração EHS para novos colaboradores?",
            "Os líderes recebem treinamento em EHS?",
            "Existe reciclagem periódica?",
        ],
    },
    {
        "codigo": "EHS-06",
        "titulo": "Gestão Ambiental",
        "descricao": "Resíduos, MTR, CDF, emissões, efluentes e resposta ambiental.",
        "perguntas": [
            "Existe segregação adequada de resíduos?",
            "Os resíduos possuem identificação?",
            "Existe controle de MTR?",
            "Os CDFs são controlados?",
            "Há controle de empresas destinadoras?",
            "Existem inspeções ambientais periódicas?",
            "Há controle de emissões atmosféricas?",
            "Existe controle de efluentes?",
            "Existe plano de resposta ambiental?",
            "Há monitoramento de indicadores ambientais?",
        ],
    },
    {
        "codigo": "EHS-07",
        "titulo": "Segurança Operacional",
        "descricao": "Máquinas, NR-12, bloqueio, EPI, permissões e controles críticos.",
        "perguntas": [
            "Máquinas possuem proteções adequadas?",
            "Existe atendimento à NR-12?",
            "Há bloqueio e etiquetagem implementados?",
            "Os EPIs estão adequados?",
            "Existe inspeção periódica de segurança?",
            "Há controle de permissões de trabalho?",
            "Existe controle de trabalho em altura?",
            "Espaços confinados possuem gestão adequada?",
            "Existe controle de energia perigosa?",
            "Há inspeções comportamentais estruturadas?",
        ],
    },
    {
        "codigo": "EHS-08",
        "titulo": "Preparação e Resposta a Emergências",
        "descricao": "Plano de emergência, brigada, simulados e equipamentos críticos.",
        "perguntas": [
            "Existe plano de emergência atualizado?",
            "Há brigada treinada?",
            "Existem simulados periódicos?",
            "Os equipamentos de emergência estão inspecionados?",
            "Existe controle de produtos perigosos?",
            "Há rotas de fuga sinalizadas?",
            "Existe comunicação de emergência definida?",
            "Os cenários críticos foram avaliados?",
            "Existe integração com serviços externos?",
            "Há registros dos simulados?",
        ],
    },
]
