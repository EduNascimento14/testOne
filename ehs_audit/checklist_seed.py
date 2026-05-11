from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from .constants import SITES_PADRAO
from .models import Achado, Auditoria, Diretiva, EvidenciaArquivo, Requisito, RespostaChecklist, Site, Usuario

LACUNA_BASE_REFERENCIA = "Lacuna da base de referência — sem requisitos auditáveis cadastrados"
TOTAL_DIRETIVAS_ESPERADO = 19
TOTAL_REQUISITOS_ESPERADO = 221
EVIDENCIA_PADRAO = "Documento / Registro / Entrevista / Campo"
AREA_PADRAO = "EHS / Área responsável"

DIRECTIVES = [
    ("4.12.01", "Requisitos e Responsabilidades de EHS", None),
    ("4.12.02", "Sistema de Gestão Ambiental", LACUNA_BASE_REFERENCIA),
    ("4.12.03", "Métricas de Desempenho e Análise de Progresso", None),
    ("4.12.04", "Avaliação e Ação Corretiva", None),
    ("4.12.05", "Gestão de Mudanças", None),
    ("4.12.06", "Investigação de Acidentes e Incidentes", None),
    ("4.12.07", "Uso de Produtos Químicos e Gestão de Resíduos", None),
    ("4.12.08", "Segurança Elétrica", None),
    ("4.12.09", "Preparação para Emergências", None),
    ("4.12.10", "Treinamento e Envolvimento dos Empregados", None),
    ("4.12.11", "Segurança de Máquinas e Equipamentos", None),
    ("4.12.12", "Ergonomia", None),
    ("4.12.13", "Permissões para Trabalhos Perigosos", None),
    ("4.12.14", "Análise de Segurança do Trabalho e EPI", None),
    ("4.12.15", "Movimentação e Armazenamento de Materiais", None),
    ("4.12.16", "Visitantes, Contratados e Empregados Temporários", None),
    ("4.12.17", "Ambiente de Trabalho", None),
    ("4.12.18", "Segurança e Competência em Manutenção", None),
    ("4.12.19", "Prevenção e Resposta a Doenças Contagiosas", LACUNA_BASE_REFERENCIA),
]

REQUIREMENTS_RAW = """
4.12.01 | Requisitos e Responsabilidades de EHS | 01 | A unidade designou uma pessoa responsável por todas as obrigações de EHS identificadas, em consulta com os líderes de EHS da divisão/unidade e Recursos Humanos?
4.12.01 | Requisitos e Responsabilidades de EHS | 02 | A unidade desenvolveu e mantém um registro de requisitos legais e outros requisitos externos de meio ambiente, saúde e segurança?
4.12.01 | Requisitos e Responsabilidades de EHS | 03 | Para cada atividade ou obrigação identificada no registro de requisitos de EHS, existe uma pessoa designada para cumprir e monitorar o requisito?
4.12.01 | Requisitos e Responsabilidades de EHS | 04 | O registro de requisitos de EHS é revisado anualmente?
4.12.01 | Requisitos e Responsabilidades de EHS | 05 | O registro de requisitos de EHS é armazenado de forma acessível a todos os indivíduos com responsabilidades definidas?
4.12.03 | Métricas de Desempenho e Análise de Progresso | 01 | O gerente geral ou representante designado da gestão agenda e realiza análises periódicas de desempenho de EHS?
4.12.03 | Métricas de Desempenho e Análise de Progresso | 02 | O líder de EHS ou outro empregado designado pela gestão da unidade definiu objetivos apropriados de desempenho de EHS para a localidade?
4.12.03 | Métricas de Desempenho e Análise de Progresso | 03 | Os objetivos de desempenho estão claramente definidos? Existem metas e marcos estabelecidos? A unidade está no caminho para atingir as metas e objetivos definidos?
4.12.03 | Métricas de Desempenho e Análise de Progresso | 04 | Foi estabelecido um quadro de melhoria da equipe de EHS? As métricas são significativas para a unidade e estão atualizadas?
4.12.03 | Métricas de Desempenho e Análise de Progresso | 05 | A unidade identificou de 3 a 5 métricas adicionais relevantes além das métricas corporativas obrigatórias do ano fiscal?
4.12.03 | Métricas de Desempenho e Análise de Progresso | 06 | As métricas estão claramente definidas? Existem metas e marcos estabelecidos? A unidade está no caminho para atingir as metas e objetivos definidos?
4.12.03 | Métricas de Desempenho e Análise de Progresso | 07 | A unidade implementou um meio para coletar, armazenar e reportar dados de métricas de EHS?
4.12.03 | Métricas de Desempenho e Análise de Progresso | 08 | A responsabilidade pela coleta, inserção e reporte de dados foi atribuída? O sistema está atualizado?
4.12.03 | Métricas de Desempenho e Análise de Progresso | 09 | O desempenho de EHS é revisado periodicamente, no mínimo trimestralmente, pelo gerente geral ou representante designado da gestão?
4.12.03 | Métricas de Desempenho e Análise de Progresso | 10 | Se a unidade for sede de divisão, foi estabelecido um quadro de melhoria da equipe de EHS? Ele está atualizado?
4.12.04 | Avaliação e Ação Corretiva | 01 | Com apoio da gestão da divisão, o líder de EHS da unidade implementou métodos internos de avaliação de EHS?
4.12.04 | Avaliação e Ação Corretiva | 02 | Em conjunto com o departamento de Qualidade, o líder de EHS da unidade estabeleceu um meio de registro e acompanhamento de não conformidades e ações corretivas de EHS?
4.12.04 | Avaliação e Ação Corretiva | 03 | O líder de EHS da divisão compartilha não conformidades relevantes e ações corretivas dentro da divisão?
4.12.04 | Avaliação e Ação Corretiva | 04 | A unidade implementou um método para avaliar a conformidade com requisitos ambientais e de segurança?
4.12.04 | Avaliação e Ação Corretiva | 05 | A unidade desenvolveu um processo para garantir que ações corretivas sejam concluídas e implementadas?
4.12.04 | Avaliação e Ação Corretiva | 06 | A unidade implementou um processo para avaliar a eficácia das ações corretivas implementadas?
4.12.04 | Avaliação e Ação Corretiva | 07 | A unidade implementou um meio de registrar e acompanhar não conformidades identificadas, causas raiz de acidentes/incidentes e ações corretivas?
4.12.05 | Gestão de Mudanças | 01 | O líder de EHS da unidade retém a documentação concluída de Gestão de Mudanças?
4.12.05 | Gestão de Mudanças | 02 | A unidade desenvolveu um procedimento de Gestão de Mudanças para garantir que questões de EHS associadas a mudanças propostas sejam comunicadas e envolvam os departamentos funcionais afetados ou empregados impactados?
4.12.05 | Gestão de Mudanças | 03 | O procedimento de Gestão de Mudanças da localidade contempla iniciação, avaliação, aprovação da gestão, implementação, verificação/partida e documentação/conclusão?
4.12.05 | Gestão de Mudanças | 04 | O processo de Gestão de Mudanças da localidade é eficaz na identificação de riscos e/ou impactos associados à mudança?
4.12.05 | Gestão de Mudanças | 05 | O processo de Gestão de Mudanças da localidade controla adequadamente os riscos/impactos associados à mudança, desde a iniciação até a conclusão?
4.12.06 | Investigação de Acidentes e Incidentes | 01 | O líder de EHS da unidade estabeleceu e gerencia o programa de quase acidentes da localidade?
4.12.06 | Investigação de Acidentes e Incidentes | 02 | O gerente geral da divisão revisa todas as investigações significativas de acidentes/incidentes?
4.12.06 | Investigação de Acidentes e Incidentes | 03 | A unidade realiza investigações para todos os acidentes/incidentes significativos? As conclusões e ações corretivas são documentadas e recuperáveis?
4.12.06 | Investigação de Acidentes e Incidentes | 04 | A unidade desenvolveu e implementou um procedimento de investigação de acidentes/incidentes contendo requisitos de notificação, coleta de informações, solução de problemas, implementação e monitoramento de ações corretivas e documentação?
4.12.06 | Investigação de Acidentes e Incidentes | 05 | A unidade determinou requisitos de notificação para acidentes/incidentes? Eles estão identificados no Plano de Preparação para Emergências da unidade?
4.12.06 | Investigação de Acidentes e Incidentes | 06 | A unidade desenvolveu e implementou um programa de quase acidentes contendo etapas de reporte, resolução, feedback e treinamento de empregados?
4.12.06 | Investigação de Acidentes e Incidentes | 07 | Os resultados do programa de quase acidentes são comunicados periodicamente a toda a força de trabalho da unidade?
4.12.06 | Investigação de Acidentes e Incidentes | 08 | É realizado treinamento anual de conscientização sobre reporte de quase acidentes? Esse treinamento é documentado?
4.12.06 | Investigação de Acidentes e Incidentes | 09 | Anualmente, a unidade revisa os dados coletados no processo de investigação de acidentes/incidentes e no programa de quase acidentes para identificar oportunidades sistêmicas e causas raiz de melhoria?
4.12.07 | Uso de Produtos Químicos e Gestão de Resíduos | 01 | A responsabilidade por avaliar perigos e exposições químicas e por implementar práticas adequadas de uso e armazenamento de produtos químicos, incluindo treinamento de empregados, está claramente definida?
4.12.07 | Uso de Produtos Químicos e Gestão de Resíduos | 02 | A responsabilidade por informar o líder de EHS sobre novas solicitações de compra de produtos químicos está claramente definida?
4.12.07 | Uso de Produtos Químicos e Gestão de Resíduos | 03 | A responsabilidade por verificar que produtos químicos novos ou existentes no local de trabalho não contenham substâncias proibidas ou restritas pela Parker está claramente definida?
4.12.07 | Uso de Produtos Químicos e Gestão de Resíduos | 04 | A unidade mantém inventário atual e documentado dos produtos químicos utilizados no local e possui Ficha de Dados de Segurança atualizada para cada produto?
4.12.07 | Uso de Produtos Químicos e Gestão de Resíduos | 05 | A unidade possui procedimento para introdução de novos produtos químicos para uso no local?
4.12.07 | Uso de Produtos Químicos e Gestão de Resíduos | 06 | A unidade possui processo para avaliar propriedades e perigos químicos, garantindo que equipamentos e controles adequados sejam estabelecidos e mantidos durante o uso e armazenamento?
4.12.07 | Uso de Produtos Químicos e Gestão de Resíduos | 07 | A unidade avalia o uso de produtos químicos e trabalhos rotineiros por meio de Análise de Segurança do Trabalho ou prática equivalente de proteção?
4.12.07 | Uso de Produtos Químicos e Gestão de Resíduos | 08 | Produtos químicos que apresentam riscos específicos são considerados na definição de resposta de primeiros socorros e necessidades de vigilância médica para empregados expostos durante uso normal e cenários de emergência?
4.12.07 | Uso de Produtos Químicos e Gestão de Resíduos | 09 | Produtos químicos inflamáveis são utilizados em recipientes, equipamentos e práticas de trabalho apropriados, incluindo equipotencialização e aterramento quando aplicável?
4.12.07 | Uso de Produtos Químicos e Gestão de Resíduos | 10 | A unidade possui áreas eletricamente classificadas, como Classe I Divisão 1 ou Classe I Divisão 2? Os equipamentos são apropriados para uso nessas áreas?
4.12.07 | Uso de Produtos Químicos e Gestão de Resíduos | 11 | Todos os empregados recebem treinamento sobre os perigos dos produtos químicos utilizados em sua área de trabalho?
4.12.07 | Uso de Produtos Químicos e Gestão de Resíduos | 12 | Todos os empregados recebem treinamento sobre a disponibilidade e o conteúdo das Fichas de Dados de Segurança?
4.12.07 | Uso de Produtos Químicos e Gestão de Resíduos | 13 | O treinamento sobre perigos químicos é fornecido antes da exposição inicial aos produtos químicos e periodicamente depois disso?
4.12.07 | Uso de Produtos Químicos e Gestão de Resíduos | 14 | A unidade identificou informações de notificação a órgãos aplicáveis e requisitos de reporte relacionados ao uso e gestão de produtos químicos?
4.12.07 | Uso de Produtos Químicos e Gestão de Resíduos | 15 | Processos que envolvem uso de produtos químicos aquecidos para acabamento metálico foram avaliados conforme o padrão de processo de acabamento metálico?
4.12.07 | Uso de Produtos Químicos e Gestão de Resíduos | 16 | As propriedades químicas são avaliadas para garantir que equipamentos e controles adequados sejam estabelecidos e mantidos durante o armazenamento?
4.12.07 | Uso de Produtos Químicos e Gestão de Resíduos | 17 | Produtos químicos são armazenados em recipientes de materiais compatíveis e apropriados para as condições ambientais previstas, como calor, frio e umidade?
4.12.07 | Uso de Produtos Químicos e Gestão de Resíduos | 18 | Todos os recipientes de produtos químicos, incluindo recipientes de uso e armazenamento a granel, estão identificados com o conteúdo e os perigos associados?
4.12.07 | Uso de Produtos Químicos e Gestão de Resíduos | 19 | Produtos químicos com perigos especiais são gerenciados e armazenados conforme requisitos legais locais?
4.12.07 | Uso de Produtos Químicos e Gestão de Resíduos | 20 | Produtos químicos inflamáveis são equipotencializados e aterrados durante armazenamento e transferência quando aplicável?
4.12.07 | Uso de Produtos Químicos e Gestão de Resíduos | 21 | Produtos químicos incompatíveis são armazenados com contenção secundária e distâncias de separação apropriadas?
4.12.07 | Uso de Produtos Químicos e Gestão de Resíduos | 22 | Todos os produtos químicos são armazenados e gerenciados de forma a prevenir liberações ao meio ambiente e exposições inaceitáveis aos empregados?
4.12.07 | Uso de Produtos Químicos e Gestão de Resíduos | 23 | Todos os tanques subterrâneos possuem contenção secundária ou mecanismo eficaz de detecção de vazamento?
4.12.07 | Uso de Produtos Químicos e Gestão de Resíduos | 24 | Os locais permanentes de armazenamento acima do solo de materiais líquidos possuem superfície impermeável?
4.12.07 | Uso de Produtos Químicos e Gestão de Resíduos | 25 | Há contenção secundária em áreas onde vazamento ou ruptura de recipiente possa fazer com que líquido alcance drenos, águas superficiais ou solo?
4.12.07 | Uso de Produtos Químicos e Gestão de Resíduos | 26 | Poços, fossas ou caixas de concreto utilizados para armazenamento de materiais líquidos possuem revestimento ou impermeabilização?
4.12.07 | Uso de Produtos Químicos e Gestão de Resíduos | 27 | Quando aplicável, revestimentos ou impermeabilizações foram inspecionados periodicamente nos últimos cinco anos?
4.12.07 | Uso de Produtos Químicos e Gestão de Resíduos | 28 | O armazenamento de substâncias perigosas no ponto de uso não excede os volumes previstos para uso diário?
4.12.07 | Uso de Produtos Químicos e Gestão de Resíduos | 29 | A unidade identificou todos os tipos de resíduos criados/gerados?
4.12.07 | Uso de Produtos Químicos e Gestão de Resíduos | 30 | Para cada tipo de resíduo, a unidade possui conhecimento adequado das características físicas e químicas para determinar o gerenciamento no local e a destinação externa apropriada?
4.12.07 | Uso de Produtos Químicos e Gestão de Resíduos | 31 | Os perfis de resíduos estão atualizados e disponíveis?
4.12.07 | Uso de Produtos Químicos e Gestão de Resíduos | 32 | A unidade implementou um processo de responsabilização para armazenamento e gestão de resíduos no local?
4.12.07 | Uso de Produtos Químicos e Gestão de Resíduos | 33 | A unidade controla a quantidade de resíduos perigosos para gerenciar volume acumulado e tempo de armazenamento conforme requisitos legais locais?
4.12.07 | Uso de Produtos Químicos e Gestão de Resíduos | 34 | Os resíduos perigosos são rastreados e monitorados desde a geração até o envio para destinação?
4.12.07 | Uso de Produtos Químicos e Gestão de Resíduos | 35 | Os recipientes de resíduos perigosos permanecem fechados, exceto durante adição ou remoção de resíduos?
4.12.07 | Uso de Produtos Químicos e Gestão de Resíduos | 36 | Os resíduos são armazenados separadamente de produtos químicos recebidos? Eles estão claramente identificados para evitar confusão com produtos químicos de entrada?
4.12.07 | Uso de Produtos Químicos e Gestão de Resíduos | 37 | O nível adequado de segurança é fornecido para os perigos apresentados pelos materiais residuais?
4.12.07 | Uso de Produtos Químicos e Gestão de Resíduos | 38 | Quando exigido por requisitos legais locais, a unidade armazena resíduos subterraneamente de acordo com os requisitos legais?
4.12.07 | Uso de Produtos Químicos e Gestão de Resíduos | 39 | A unidade forneceu treinamento adequado de gestão e destinação de resíduos aos empregados com responsabilidades designadas nessa atividade?
4.12.07 | Uso de Produtos Químicos e Gestão de Resíduos | 40 | A unidade garante que resíduos não sejam diluídos como substituto de tratamento adequado?
4.12.07 | Uso de Produtos Químicos e Gestão de Resíduos | 41 | A unidade utiliza transportadores de resíduos certificados e/ou empresas certificadas de disposição, tratamento, reciclagem ou reutilização?
4.12.07 | Uso de Produtos Químicos e Gestão de Resíduos | 42 | A unidade mantém documentação de todos os envios de resíduos perigosos conforme requisitos locais e política global de retenção e proteção de registros?
4.12.07 | Uso de Produtos Químicos e Gestão de Resíduos | 43 | Como parte do Plano de Preparação para Emergências, a unidade avaliou o potencial de liberações de produtos químicos e resíduos e as ações apropriadas de resposta para conter e limpar a liberação?
4.12.07 | Uso de Produtos Químicos e Gestão de Resíduos | 44 | A unidade identificou e disponibilizou materiais apropriados de contenção de derramamentos conforme referenciado no Plano de Preparação para Emergências?
4.12.07 | Uso de Produtos Químicos e Gestão de Resíduos | 45 | Para cenários previsíveis de derramamento, a unidade determinou e documentou possíveis requisitos de notificação a órgãos governamentais?
4.12.07 | Uso de Produtos Químicos e Gestão de Resíduos | 46 | A unidade treinou os empregados designados para responder a cenários de derramamento?
4.12.07 | Uso de Produtos Químicos e Gestão de Resíduos | 47 | Quando aplicável, para produtos químicos de alto risco, a unidade contratou ou estabeleceu resposta a derramamentos com prestador externo qualificado?
4.12.08 | Segurança Elétrica | 01 | A unidade implementou um programa de segurança elétrica consistente com os requisitos da Diretiva EHS 4.12.08?
4.12.08 | Segurança Elétrica | 02 | Empregados que inspecionam, testam, modificam ou instalam componentes, fiações ou sistemas elétricos possuem conhecimento e habilidade necessários para executar o trabalho com segurança?
4.12.08 | Segurança Elétrica | 03 | Se regulamentos locais exigirem licença ou certificação para realizar o trabalho com segurança, os empregados que executam trabalho elétrico atendem a esse requisito?
4.12.08 | Segurança Elétrica | 04 | É possível demonstrar que empregados qualificados são capazes de compreender, reconhecer e evitar perigos elétricos; conhecem operações, instalações e equipamentos elétricos; conhecem códigos e regulamentos elétricos aplicáveis; e compreendem a hierarquia de controles, incluindo controles de engenharia, administrativos e EPI?
4.12.08 | Segurança Elétrica | 05 | Se trabalhos em circuitos elétricos energizados e expostos forem realizados por empregados da empresa, a unidade realizou estudo de curto-circuito e interrupção por falta à terra para determinar potencial de arco elétrico e níveis potenciais de incidente?
4.12.08 | Segurança Elétrica | 06 | Para serviços ou manutenção em circuitos elétricos energizados acima de 50 V, a unidade implementou processo de permissão de trabalho energizado?
4.12.08 | Segurança Elétrica | 07 | A unidade treinou indivíduos que realizam trabalho elétrico energizado sobre os perigos da atividade e sobre o processo de permissão de trabalho energizado?
4.12.08 | Segurança Elétrica | 08 | A unidade identificou as medidas de controle apropriadas para trabalho em circuitos elétricos, como ferramentas não faiscantes, EPI para arco elétrico, entre outros?
4.12.08 | Segurança Elétrica | 09 | Empregados que trabalham em ou próximos a equipamentos ou circuitos elétricos energizados expostos são treinados em proteção contra choque e arco elétrico? O treinamento está atualizado?
4.12.08 | Segurança Elétrica | 10 | A unidade considera fatores ambientais na instalação de sistemas elétricos, como ambientes úmidos, molhados ou atmosferas perigosas, inclusive via Gestão de Mudanças?
4.12.09 | Preparação para Emergências | 01 | A unidade determinou quais tipos de cenários de emergência são razoavelmente previsíveis em seu Plano de Preparação para Emergências?
4.12.09 | Preparação para Emergências | 02 | Para cada cenário de emergência razoavelmente previsível, a unidade possui Plano de Preparação para Emergências escrito com atividades necessárias para resposta imediata e recuperação?
4.12.09 | Preparação para Emergências | 03 | As funções e responsabilidades dos respondentes estão identificadas no Plano de Preparação para Emergências?
4.12.09 | Preparação para Emergências | 04 | O Plano de Preparação para Emergências identifica os equipamentos de emergência necessários no local?
4.12.09 | Preparação para Emergências | 05 | Todos os equipamentos necessários de resposta a emergências são mantidos e inspecionados periodicamente?
4.12.09 | Preparação para Emergências | 06 | A unidade especificou requisitos de notificação a partes internas e externas no Plano de Preparação para Emergências?
4.12.09 | Preparação para Emergências | 07 | Foi fornecido treinamento geral a todos os empregados sobre o Plano de Preparação para Emergências na admissão e periodicamente depois disso?
4.12.09 | Preparação para Emergências | 08 | Empregados com responsabilidades específicas listadas no Plano de Preparação para Emergências foram treinados em suas responsabilidades?
4.12.09 | Preparação para Emergências | 09 | Evacuações de incêndio e outras ações de resposta a emergências de maior risco e probabilidade foram praticadas no último ano?
4.12.09 | Preparação para Emergências | 10 | A unidade é capaz de fornecer resposta inicial de primeiros socorros apropriada à natureza das atividades no local?
4.12.09 | Preparação para Emergências | 11 | Os respondentes de primeiros socorros receberam treinamento reconhecido localmente, como primeiros socorros e DEA, e treinamento de conscientização sobre patógenos transmitidos pelo sangue? O treinamento está atualizado?
4.12.09 | Preparação para Emergências | 12 | O treinamento de primeiros socorros considera os riscos presentes e aplicáveis à localidade?
4.12.09 | Preparação para Emergências | 13 | A unidade disponibilizou número suficiente de respondentes de primeiros socorros treinados para atender emergências médicas previsíveis, considerando turnos, escritório, equipes de fim de semana etc.?
4.12.09 | Preparação para Emergências | 14 | O Plano de Preparação para Emergências escrito foi revisado/atualizado no último ano?
4.12.10 | Treinamento e Envolvimento dos Empregados | 01 | A unidade implementou processo para identificar, gerenciar e documentar necessidades de treinamento na unidade/divisão?
4.12.10 | Treinamento e Envolvimento dos Empregados | 02 | A unidade implementou processo ou mecanismo para garantir que os requisitos de treinamento sejam cumpridos e que tempo e recursos adequados sejam fornecidos para sua conclusão?
4.12.10 | Treinamento e Envolvimento dos Empregados | 03 | Os membros do EHS Star Point HPT da unidade participam das reuniões e atividades programadas?
4.12.10 | Treinamento e Envolvimento dos Empregados | 04 | As necessidades de treinamento de EHS da unidade foram identificadas e documentadas?
4.12.10 | Treinamento e Envolvimento dos Empregados | 05 | O treinamento de EHS da unidade é ministrado por instrutor competente ou por outro meio igualmente eficaz?
4.12.10 | Treinamento e Envolvimento dos Empregados | 06 | A localidade considerou meios para garantir que o treinamento seja compreendido pelos empregados, incluindo compreensão de idioma, alfabetização e habilidades técnicas?
4.12.10 | Treinamento e Envolvimento dos Empregados | 07 | Todo treinamento de EHS é documentado?
4.12.10 | Treinamento e Envolvimento dos Empregados | 08 | As necessidades e materiais de treinamento são revisados anualmente para garantir conformidade com requisitos aplicáveis do registro de EHS?
4.12.10 | Treinamento e Envolvimento dos Empregados | 09 | As necessidades de treinamento para trabalhadores temporários, contratados e visitantes foram identificadas, implementadas e documentadas?
4.12.10 | Treinamento e Envolvimento dos Empregados | 10 | Foi identificado e formalizado um EHS Star Point Team na unidade?
4.12.10 | Treinamento e Envolvimento dos Empregados | 11 | O termo/charter do EHS Star Point Team da unidade está atualizado para o ano fiscal vigente?
4.12.10 | Treinamento e Envolvimento dos Empregados | 12 | O EHS Star Point Team da unidade é multifuncional e inclui representação da gestão, líderes de EHS e representantes dos HPTs de produção natural?
4.12.10 | Treinamento e Envolvimento dos Empregados | 13 | A composição do EHS Star Point Team é revisada periodicamente para garantir representação de todos os departamentos, turnos e empregados de escritório?
4.12.10 | Treinamento e Envolvimento dos Empregados | 14 | Existe processo definido para rotação da representação dos times naturais de produção no EHS Star Point Team?
4.12.10 | Treinamento e Envolvimento dos Empregados | 15 | Foi estabelecido plano de treinamento para todos os membros do EHS Star Point Team, garantindo conhecimento adequado para executar tarefas ou responsabilidades assumidas pelo HPT?
4.12.10 | Treinamento e Envolvimento dos Empregados | 16 | O EHS Star Point Team possui frequência estabelecida de reuniões, no mínimo trimestral?
4.12.10 | Treinamento e Envolvimento dos Empregados | 17 | As atas de reunião são documentadas e retidas para todas as reuniões do EHS Star Point Team?
4.12.10 | Treinamento e Envolvimento dos Empregados | 18 | Existe processo para comunicar as iniciativas do EHS Star Point HPT à força de trabalho?
4.12.11 | Segurança de Máquinas e Equipamentos | 01 | A unidade implementou um Programa de Avaliação de Segurança de Máquinas e Equipamentos? Ele está atualizado?
4.12.11 | Segurança de Máquinas e Equipamentos | 02 | A unidade desenvolveu processo para garantir que todos os equipamentos e máquinas estejam adequadamente protegidos contra lesões quando operação, manutenção ou setup puderem potencialmente ferir operadores ou outros trabalhadores?
4.12.11 | Segurança de Máquinas e Equipamentos | 03 | Com base nas avaliações de proteções concluídas, EHS e líderes de Operações desenvolveram, revisaram e aprovaram um plano para proteção efetiva de todas as máquinas?
4.12.11 | Segurança de Máquinas e Equipamentos | 04 | As melhorias de proteções foram priorizadas com base no risco para impulsionar plano anual de redução de risco?
4.12.11 | Segurança de Máquinas e Equipamentos | 05 | A unidade realiza avaliações de proteções como parte do processo de Gestão de Mudanças?
4.12.11 | Segurança de Máquinas e Equipamentos | 06 | A unidade exige avaliações de proteções quando equipamentos são modificados ou alterados em relação à especificação original?
4.12.11 | Segurança de Máquinas e Equipamentos | 07 | Se a localidade possuir potencial de liberação de ar ou fluido em alta pressão, segue as diretrizes de proteção de máquinas especificadas no padrão de processo de equipamentos pressurizados?
4.12.11 | Segurança de Máquinas e Equipamentos | 08 | A localidade documentou treinamento dos empregados sobre operação segura de todas as máquinas e equipamentos utilizados em suas responsabilidades de trabalho?
4.12.11 | Segurança de Máquinas e Equipamentos | 09 | A localidade documentou treinamento para empregados que realizam setup, troca de ferramentas e atividades de manutenção?
4.12.11 | Segurança de Máquinas e Equipamentos | 10 | A localidade desenvolveu método ou processo para inspecionar periodicamente equipamentos e máquinas, garantindo que as proteções estejam presentes e funcionando?
4.12.12 | Ergonomia | 01 | A unidade estabeleceu e mantém um processo de melhoria ergonômica apropriado para a organização?
4.12.12 | Ergonomia | 02 | Foi nomeado um coordenador de ergonomia da divisão para supervisionar, implementar e atualizar o plano ergonômico da divisão?
4.12.12 | Ergonomia | 03 | Foi implementado um processo de melhoria ergonômica na divisão?
4.12.12 | Ergonomia | 04 | A localidade identificou e tratou regulamentos aplicáveis relacionados ao controle de distúrbios musculoesqueléticos?
4.12.12 | Ergonomia | 05 | A localidade estabeleceu metas mensuráveis de melhoria para o processo de ergonomia?
4.12.12 | Ergonomia | 06 | A localidade forneceu recursos adequados, infraestrutura de suporte, tempo e orçamento para atingir as metas da unidade?
4.12.12 | Ergonomia | 07 | A divisão estabeleceu um roadmap que inclui planos e metas de melhoria com base nos resultados de avaliação de risco, incluindo metas orientadas por dados, prazos e responsabilidades?
4.12.12 | Ergonomia | 08 | A localidade estabeleceu e mantém uma infraestrutura de suporte, como equipe, apropriada às necessidades ergonômicas da localidade?
4.12.12 | Ergonomia | 09 | A localidade forneceu treinamento para apoiar habilidades e conscientização apropriadas às necessidades e papéis da unidade?
4.12.12 | Ergonomia | 10 | A localidade forneceu ao coordenador de ergonomia da divisão nível adequado de treinamento para compreender o processo de ergonomia, estabelecer planos da unidade e identificar recursos?
4.12.12 | Ergonomia | 11 | A localidade forneceu treinamento de habilidades ergonômicas ao pessoal selecionado que realiza avaliações de risco ergonômico?
4.12.12 | Ergonomia | 12 | A localidade forneceu treinamento de conscientização ergonômica a todos os empregados?
4.12.12 | Ergonomia | 13 | A localidade estabeleceu processo para avaliar e tratar fatores de risco associados a todos os incidentes registráveis de distúrbios musculoesqueléticos?
4.12.12 | Ergonomia | 14 | A localidade estabeleceu processo e ferramentas para avaliar e controlar fatores de risco ergonômico antes da liberação de novos equipamentos, ferramentas e postos de trabalho para produção?
4.12.12 | Ergonomia | 15 | A unidade estabeleceu processo eficaz para gerenciar efeitos à saúde relacionados a distúrbios musculoesqueléticos, incluindo reconhecimento precoce, avaliação, tratamento, reabilitação e retorno ao trabalho?
4.12.12 | Ergonomia | 16 | A localidade implementou sistema para validar e monitorar a eficácia de controles de engenharia e práticas de trabalho na redução de fatores de risco ergonômico?
4.12.12 | Ergonomia | 17 | A localidade implementou processo de revisão anual para confirmar a eficácia de todos os componentes do processo de ergonomia?
4.12.12 | Ergonomia | 18 | O líder de EHS da unidade reportou os resultados da revisão anual à gestão da unidade/divisão, destacando deficiências e ações corretivas tomadas para confirmar o fechamento?
4.12.12 | Ergonomia | 19 | A gestão da unidade/divisão forneceu os meios e orçamento necessários para implementar e apoiar o processo, cumprir as metas estabelecidas e apoiar soluções viáveis para reduzir fatores de risco ergonômico?
4.12.12 | Ergonomia | 20 | A gestão da unidade/divisão revisou o processo de ergonomia e o plano do roadmap no último trimestre?
4.12.13 | Permissões para Trabalhos Perigosos | 01 | A localidade designou um indivíduo para gerenciar o sistema de permissão de trabalho e o programa de trabalhos perigosos?
4.12.13 | Permissões para Trabalhos Perigosos | 02 | A localidade implementou sistema de permissão para avaliar e controlar riscos à segurança humana durante a execução de trabalhos perigosos, como trabalho a quente, espaço confinado e trabalho em altura?
4.12.13 | Permissões para Trabalhos Perigosos | 03 | A localidade implementou processo para revisar permissões a fim de tratar a causa raiz de acidente/incidente ou perigo observado durante trabalhos perigosos?
4.12.13 | Permissões para Trabalhos Perigosos | 04 | Todo trabalho que requer permissão de trabalho é executado por pessoas ou empresas competentes?
4.12.14 | Análise de Segurança do Trabalho e EPI | 01 | A localidade implementou sistema de Análise de Segurança do Trabalho e avaliações dinâmicas de risco?
4.12.14 | Análise de Segurança do Trabalho e EPI | 02 | A localidade implementou sistema de gestão documental para ASTs/JSAs e avaliações dinâmicas de risco?
4.12.14 | Análise de Segurança do Trabalho e EPI | 03 | Por meio da AST/JSA, a localidade determinou os EPIs necessários para reduzir o risco a níveis aceitáveis?
4.12.14 | Análise de Segurança do Trabalho e EPI | 04 | A localidade identificou empregados que executam trabalhos não rotineiros ou em campo? A lista está atualizada no último trimestre?
4.12.14 | Análise de Segurança do Trabalho e EPI | 05 | A localidade concluiu ASTs/JSAs para todos os processos de trabalho rotineiros que possam apresentar risco de segurança?
4.12.14 | Análise de Segurança do Trabalho e EPI | 06 | Para todos os perigos identificados, a unidade avaliou se os meios de controle atuais são suficientes?
4.12.14 | Análise de Segurança do Trabalho e EPI | 07 | As ASTs/JSAs são documentadas e recuperáveis?
4.12.14 | Análise de Segurança do Trabalho e EPI | 08 | A localidade comunicou os resultados da AST/JSA aos empregados que executam os processos de trabalho rotineiros correspondentes?
4.12.14 | Análise de Segurança do Trabalho e EPI | 09 | A localidade revisa periodicamente as ASTs/JSAs?
4.12.14 | Análise de Segurança do Trabalho e EPI | 10 | A localidade realiza ASTs/JSAs para todos os equipamentos ou processos novos ou realocados antes da partida ou execução da tarefa?
4.12.14 | Análise de Segurança do Trabalho e EPI | 11 | A unidade desenvolveu e implementou procedimento para avaliação de risco de segurança em processos de trabalho não rotineiros, como avaliação dinâmica de risco?
4.12.14 | Análise de Segurança do Trabalho e EPI | 12 | A unidade realizou e documentou treinamento para empregados que executam trabalho não rotineiro?
4.12.15 | Movimentação e Armazenamento de Materiais | 01 | Fatores de risco ergonômico foram avaliados e considerados na seleção de equipamentos?
4.12.15 | Movimentação e Armazenamento de Materiais | 02 | O peso previsto das cargas a serem levantadas, movimentadas ou armazenadas é identificado e considerado?
4.12.15 | Movimentação e Armazenamento de Materiais | 03 | As configurações das cargas a serem levantadas, movimentadas ou armazenadas foram analisadas para garantir compatibilidade com o equipamento escolhido?
4.12.15 | Movimentação e Armazenamento de Materiais | 04 | As capacidades de carga dos equipamentos ou estruturas de armazenamento utilizadas são conhecidas e verificadas para suportar as cargas pretendidas?
4.12.15 | Movimentação e Armazenamento de Materiais | 05 | A frequência de levantamento, movimentação ou armazenamento foi avaliada para garantir que o equipamento suporte a carga de trabalho?
4.12.15 | Movimentação e Armazenamento de Materiais | 06 | O ambiente de trabalho, incluindo superfície, atmosfera e limitações de espaço, é considerado na seleção de equipamentos ou estruturas de armazenamento?
4.12.15 | Movimentação e Armazenamento de Materiais | 07 | Inspeções diárias pré-uso são realizadas em todos os equipamentos de movimentação de materiais e estruturas industriais de armazenamento?
4.12.15 | Movimentação e Armazenamento de Materiais | 08 | As inspeções pré-uso são documentadas e realizadas por indivíduos qualificados conforme recomendações do fabricante e requisitos legais locais?
4.12.15 | Movimentação e Armazenamento de Materiais | 09 | Inspeções periódicas são realizadas em equipamentos de movimentação de materiais e estruturas industriais de armazenamento conforme padrão de processo da Parker?
4.12.15 | Movimentação e Armazenamento de Materiais | 10 | Todas as deficiências identificadas durante inspeções pré-turno ou periódicas são tratadas prontamente, e o equipamento ou estrutura é retirado de serviço até reparo? As cargas são avaliadas sempre que serão movimentadas com equipamento de movimentação de materiais, considerando peso, capacidade, tamanho, centro de gravidade, condição do pallet, condição do equipamento, condição do veículo e fatores ambientais?
4.12.15 | Movimentação e Armazenamento de Materiais | 11 | Uma Permissão de Trabalho para Carga Não Padrão é utilizada quando uma carga é considerada insegura ou não padronizada, conforme padrão de processo de atividades de carregamento e descarregamento?
4.12.15 | Movimentação e Armazenamento de Materiais | 12 | Cargas inseguras são quarentenadas até que possam ser movimentadas com segurança?
4.12.15 | Movimentação e Armazenamento de Materiais | 13 | Instruções de trabalho, formulários associados, permissões de trabalho e recursos visuais estão disponíveis no ponto de uso, quando praticável, conforme padrões de processo de equipamentos de movimentação, estruturas de armazenamento e atividades de carregamento/descarregamento?
4.12.15 | Movimentação e Armazenamento de Materiais | 14 | Auditorias de Processo em Camadas são utilizadas para garantir conformidade com requisitos e padrões de processo definidos nesta diretiva e nos padrões associados?
4.12.15 | Movimentação e Armazenamento de Materiais | 15 | A manutenção de equipamentos de movimentação de materiais e estruturas industriais de armazenamento é conduzida conforme padrão de processo aplicável, além das recomendações do fabricante e requisitos legais locais?
4.12.15 | Movimentação e Armazenamento de Materiais | 16 | Todas as atividades de manutenção e serviço são realizadas por indivíduos qualificados?
4.12.15 | Movimentação e Armazenamento de Materiais | 17 | Componentes danificados são identificados e substituídos prontamente, sem tentativas de soldagem ou modificações?
4.12.15 | Movimentação e Armazenamento de Materiais | 18 | Todas as peças e componentes utilizados na manutenção são aprovados pelo fabricante?
4.12.15 | Movimentação e Armazenamento de Materiais | 19 | Modificações e acréscimos, incluindo acessórios, que possam impactar capacidade, uso seguro e operação são avaliados e aprovados pelo fabricante?
4.12.15 | Movimentação e Armazenamento de Materiais | 20 | Todos os operadores de equipamentos de movimentação de materiais são treinados?
4.12.15 | Movimentação e Armazenamento de Materiais | 21 | O treinamento é conduzido por instrutor competente, com experiência e conhecimento adequados?
4.12.15 | Movimentação e Armazenamento de Materiais | 22 | O treinamento é específico para os tipos de equipamentos, tipos de carga e ambiente de trabalho?
4.12.15 | Movimentação e Armazenamento de Materiais | 23 | O treinamento é documentado e fornecido antes da operação do equipamento, incluindo os elementos exigidos pela Diretiva Global de Processo EHS 4.12.15?
4.12.15 | Movimentação e Armazenamento de Materiais | 24 | O retreinamento é fornecido periodicamente conforme requisitos legais locais?
4.12.15 | Movimentação e Armazenamento de Materiais | 25 | O retreinamento é conduzido após qualquer incidente de segurança ou comportamento inseguro observado?
4.12.15 | Movimentação e Armazenamento de Materiais | 26 | O treinamento de empilhadeira/equipamento industrial motorizado inclui instrução teórica e prática?
4.12.15 | Movimentação e Armazenamento de Materiais | 27 | Demonstrações são realizadas pelo instrutor e exercícios práticos pelo treinando durante o treinamento de equipamento industrial motorizado?
4.12.15 | Movimentação e Armazenamento de Materiais | 28 | O desempenho do operador no local de trabalho é avaliado durante o treinamento de equipamento industrial motorizado?
4.12.15 | Movimentação e Armazenamento de Materiais | 29 | A documentação do treinamento especifica os tipos de equipamento que o indivíduo está aprovado para operar?
4.12.16 | Visitantes, Contratados e Empregados Temporários | 01 | A unidade implementou procedimento para gerenciar questões de EHS relacionadas a visitantes?
4.12.16 | Visitantes, Contratados e Empregados Temporários | 02 | A unidade implementou procedimento para gerenciar questões de EHS relacionadas a empresas contratadas e empregados contratados?
4.12.16 | Visitantes, Contratados e Empregados Temporários | 03 | A unidade implementou procedimento para gerenciar questões de EHS relacionadas a empregados temporários?
4.12.17 | Ambiente de Trabalho | 01 | A unidade estabeleceu e mantém meios adequados de saída/egresso?
4.12.17 | Ambiente de Trabalho | 02 | As rotas de saída da unidade são mantidas livres de obstruções?
4.12.17 | Ambiente de Trabalho | 03 | A unidade mantém adequadamente superfícies de circulação e trabalho para prevenir escorregões, tropeços e quedas no piso da unidade ou de altura?
4.12.17 | Ambiente de Trabalho | 04 | A unidade é mantida em condição limpa, organizada e sanitária?
4.12.17 | Ambiente de Trabalho | 05 | A iluminação da unidade é adequada para as tarefas rotineiras e não rotineiras executadas?
4.12.17 | Ambiente de Trabalho | 06 | A ventilação da unidade é suficiente para minimizar ou eliminar, em conjunto com controles administrativos e EPI, a exposição dos empregados a perigos?
4.12.17 | Ambiente de Trabalho | 07 | Quando aplicável, operações ou atividades de alto risco, como jateamento abrasivo, cabines de pintura e espaços confinados, possuem ventilação adequada para eliminar, em conjunto com controles administrativos e EPI, a exposição dos empregados a perigos?
4.12.17 | Ambiente de Trabalho | 08 | Quando aplicável, a unidade implementou medidas ou controles apropriados para proteger empregados contra riscos de estressores térmicos, como calor e frio extremos?
4.12.18 | Segurança e Competência em Manutenção | 01 | Empregados que executam atividades e tarefas de manutenção possuem conhecimento e habilidade necessários para realizar o trabalho com segurança?
4.12.18 | Segurança e Competência em Manutenção | 02 | A unidade mantém registro de treinamento e qualificações para cada empregado que executa atividades de manutenção?
4.12.18 | Segurança e Competência em Manutenção | 03 | A unidade mantém matriz de treinamento e qualificações para todos os empregados de manutenção? Ela está disponível?
4.12.18 | Segurança e Competência em Manutenção | 04 | Todos os empregados que executam atividades de manutenção receberam treinamento anual de competência em segurança sobre tópicos aplicáveis de segurança e sistema de gestão?
4.12.18 | Segurança e Competência em Manutenção | 05 | Todos os empregados que executam atividades de manutenção receberam treinamento periódico sobre fatores humanos?
4.12.18 | Segurança e Competência em Manutenção | 06 | Avaliações de risco são realizadas antes do início das atividades de manutenção?
4.12.18 | Segurança e Competência em Manutenção | 07 | A unidade realizou avaliações de risco, como AST/JSA, para atividades de TPM e manutenção preventiva?
4.12.18 | Segurança e Competência em Manutenção | 08 | A unidade implementou sistema de permissão para trabalhos perigosos, como trabalho a quente, espaço confinado, trabalho energizado e trabalho em altura?
4.12.18 | Segurança e Competência em Manutenção | 09 | O gerente de Manutenção/Facilities da localidade trabalha com RH para avaliar anualmente as qualificações e competências de todos os empregados de manutenção?
4.12.18 | Segurança e Competência em Manutenção | 10 | O gerente de Manutenção/Facilities da localidade iniciou e mantém uma cadência de análise pré-trabalho e verificação de sistemas seguros de trabalho?
""".strip()


@dataclass(frozen=True)
class ChecklistRequirement:
    codigo_gdt: str
    tema: str
    item: str
    pergunta: str

    @property
    def codigo_requisito(self) -> str:
        return f"{self.codigo_gdt}.{self.item}"


def parse_requirements() -> list[ChecklistRequirement]:
    requirements: list[ChecklistRequirement] = []
    for line in REQUIREMENTS_RAW.splitlines():
        parts = [part.strip() for part in line.split(" | ", 3)]
        if len(parts) != 4:
            raise ValueError(f"Linha inválida na base do checklist: {line}")
        requirements.append(ChecklistRequirement(*parts))
    return requirements


CHECKLIST_REQUIREMENTS = parse_requirements()


def classify_criticidade(pergunta: str) -> str:
    texto = pergunta.lower()
    if any(term in texto for term in ["fatal", "emergência", "energizado", "arco elétrico", "espaço confinado", "trabalho em altura", "inflam", "derramamento", "perigosos"]):
        return "Crítico"
    if any(term in texto for term in ["treinamento", "incidente", "acidente", "químic", "resíduo", "risco", "permissão", "legal"]):
        return "Alto"
    return "Médio"


def seed_sites_and_users(session: Session) -> dict[str, int]:
    created = {"sites": 0, "usuarios": 0}
    sites: dict[str, Site] = {}
    for codigo in SITES_PADRAO:
        site = session.query(Site).filter_by(codigo=codigo).one_or_none()
        if not site:
            site = Site(codigo=codigo, nome=f"Unidade {codigo}", ativo=True)
            session.add(site)
            session.flush()
            created["sites"] += 1
        sites[codigo] = site
    if not session.query(Usuario).filter_by(email="admin.lag@empresa.local").one_or_none():
        session.add(Usuario(nome="Admin LAG", email="admin.lag@empresa.local", perfil="Admin_LAG", ativo=True))
        created["usuarios"] += 1
    for codigo, site in sites.items():
        email = f"ehs.{codigo.lower()}@empresa.local"
        if not session.query(Usuario).filter_by(email=email).one_or_none():
            session.add(Usuario(nome=f"EHS Local {codigo}", email=email, site_id=site.id, perfil="EHS_Local", ativo=True))
            created["usuarios"] += 1
    return created


def seed_directives(session: Session) -> int:
    created = 0
    for codigo, titulo, observacao in DIRECTIVES:
        diretiva = session.query(Diretiva).filter_by(codigo=codigo).one_or_none()
        if not diretiva:
            diretiva = Diretiva(codigo=codigo, titulo=titulo, observacao=observacao, ativa=True)
            session.add(diretiva)
            created += 1
        else:
            diretiva.titulo = titulo
            diretiva.ativa = True
            if observacao:
                diretiva.observacao = observacao
    return created


def seed_requirements(session: Session) -> int:
    created = 0
    directives = {d.codigo: d for d in session.query(Diretiva).all()}
    expected_codes = {item.codigo_requisito for item in CHECKLIST_REQUIREMENTS}
    for item in CHECKLIST_REQUIREMENTS:
        diretiva = directives[item.codigo_gdt]
        requisito = session.query(Requisito).filter_by(diretiva_id=diretiva.id, codigo_requisito=item.codigo_requisito).one_or_none()
        if requisito:
            requisito.pergunta = item.pergunta
            requisito.tipo_evidencia_esperada = requisito.tipo_evidencia_esperada or EVIDENCIA_PADRAO
            requisito.area_responsavel_sugerida = requisito.area_responsavel_sugerida or AREA_PADRAO
            continue
        session.add(
            Requisito(
                diretiva_id=diretiva.id,
                codigo_requisito=item.codigo_requisito,
                pergunta=item.pergunta,
                orientacao="",
                criticidade=classify_criticidade(item.pergunta),
                tipo_evidencia_esperada=EVIDENCIA_PADRAO,
                area_responsavel_sugerida=AREA_PADRAO,
                ativo=True,
            )
        )
        created += 1

    for requisito in session.query(Requisito).join(Diretiva).filter(Diretiva.codigo.like("4.12.%")).all():
        if requisito.codigo_requisito in expected_codes:
            continue
        has_links = (
            session.query(RespostaChecklist).filter_by(requisito_id=requisito.id).first()
            or session.query(Achado).filter_by(requisito_id=requisito.id).first()
            or session.query(EvidenciaArquivo).filter_by(requisito_id=requisito.id).first()
        )
        if has_links:
            requisito.ativo = False
        else:
            session.delete(requisito)
    session.flush()
    return created


def ensure_auditoria_checklists(session: Session) -> int:
    """Garante que auditorias existentes tenham respostas para toda a base ativa atual."""
    created = 0
    requisito_ids = [req.id for req in session.query(Requisito).filter_by(ativo=True).all()]
    auditoria_ids = [aud.id for aud in session.query(Auditoria).all()]
    for auditoria_id in auditoria_ids:
        existing = {
            row[0]
            for row in session.query(RespostaChecklist.requisito_id)
            .filter(RespostaChecklist.auditoria_id == auditoria_id)
            .all()
        }
        for requisito_id in requisito_ids:
            if requisito_id not in existing:
                session.add(
                    RespostaChecklist(
                        auditoria_id=auditoria_id,
                        requisito_id=requisito_id,
                        aplicavel=True,
                        status_conformidade="Não Verificado",
                    )
                )
                created += 1
    session.flush()
    return created


def validate_checklist_seed(session: Session) -> dict[str, int | bool]:
    total_diretivas = session.query(Diretiva).filter(Diretiva.codigo.like("4.12.%")).count()
    total_requisitos = session.query(Requisito).join(Diretiva).filter(Diretiva.codigo.like("4.12.%"), Requisito.ativo == True).count()  # noqa: E712
    req_41202 = session.query(Requisito).join(Diretiva).filter(Diretiva.codigo == "4.12.02", Requisito.ativo == True).count()  # noqa: E712
    req_41219 = session.query(Requisito).join(Diretiva).filter(Diretiva.codigo == "4.12.19", Requisito.ativo == True).count()  # noqa: E712
    valid = total_diretivas == TOTAL_DIRETIVAS_ESPERADO and total_requisitos == TOTAL_REQUISITOS_ESPERADO and req_41202 == 0 and req_41219 == 0
    return {"diretivas": total_diretivas, "requisitos": total_requisitos, "req_41202": req_41202, "req_41219": req_41219, "valido": valid}


def seed_checklist_base(session: Session) -> dict[str, int | bool]:
    if len(DIRECTIVES) != TOTAL_DIRETIVAS_ESPERADO:
        raise ValueError("Base interna de diretivas inconsistente.")
    if len(CHECKLIST_REQUIREMENTS) != TOTAL_REQUISITOS_ESPERADO:
        raise ValueError(f"Base interna de requisitos inconsistente: {len(CHECKLIST_REQUIREMENTS)}")
    created = seed_sites_and_users(session)
    created["diretivas"] = seed_directives(session)
    session.flush()
    created["requisitos"] = seed_requirements(session)
    session.flush()
    created["respostas_checklist"] = ensure_auditoria_checklists(session)
    validation = validate_checklist_seed(session)
    if not validation["valido"]:
        raise ValueError(f"Seed da base do checklist inválido: {validation}")
    session.commit()
    return {**created, **validation}


def ensure_seed_data(session: Session) -> dict[str, int | bool]:
    return seed_checklist_base(session)
