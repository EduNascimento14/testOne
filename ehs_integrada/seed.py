from datetime import date, timedelta

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
    Usuario,
)
from ehs_integrada.validations import SITES_PADRAO


NR12_CHECKLIST = [
    ("OP-01", "Checklist operacional", "Proteções fixas e móveis estão instaladas, íntegras e sem remoção indevida?", "Verificação visual antes do uso.", True),
    ("OP-02", "Checklist operacional", "Botões de emergência estão acessíveis, identificados e sem obstrução?", "Inspeção visual e teste conforme rotina local.", True),
    ("OP-03", "Checklist operacional", "Não há bypass, jumper, calço, fita ou improviso em dispositivos de segurança?", "Inspeção visual de proteções, sensores, chaves e comandos.", True),
    ("OP-04", "Checklist operacional", "Sinalizações de segurança e identificação da máquina estão legíveis?", "Placas, etiquetas, pictogramas e identificação patrimonial.", False),
    ("OP-05", "Checklist operacional", "Painéis, cabos, conexões e mangueiras não apresentam condição anormal aparente?", "Sem danos, vazamentos, cabos expostos ou partes soltas.", False),
    ("MAN-01", "Inspeção de manutenção", "Proteções fixas e móveis permanecem presentes, fixadas e alinhadas conforme projeto/laudo?", "Comparação com projeto, laudo ou condição validada.", True),
    ("MAN-02", "Inspeção de manutenção", "Intertravamentos, sensores, chaves, cortinas ou scanners funcionam conforme teste previsto?", "Teste funcional registrado.", True),
    ("MAN-03", "Inspeção de manutenção", "Botões de emergência geram parada segura e não provocam partida inesperada no rearme?", "Teste funcional nos pontos aplicáveis.", True),
    ("MAN-04", "Inspeção de manutenção", "Relé/controlador/PLC de segurança não apresenta falha ou alteração sem MOC?", "Diagnóstico, painel, programa ou registro de mudança.", True),
    ("MAN-05", "Inspeção de manutenção", "Pontos de bloqueio e procedimento LOTO estão disponíveis e funcionais?", "Procedimento de bloqueio, pontos físicos e teste de energia zero.", True),
    ("EHS-01", "Auditoria EHS", "Inventário NR-12 está atualizado com status, criticidade, responsável e próximas inspeções?", "Inventário vigente e coerente com campo.", False),
    ("EHS-02", "Auditoria EHS", "Laudo NR-12, ART e apreciação de risco estão disponíveis e compatíveis com a condição atual?", "Pacote documental da máquina/amostra auditada.", True),
    ("EHS-03", "Auditoria EHS", "Proteções, intertravamentos, sensores/cortinas e emergências permanecem funcionais em campo?", "Inspeção amostral e testes funcionais aplicáveis.", True),
    ("EHS-04", "Auditoria EHS", "Não há evidência de bypass, descaracterização ou alteração sem aprovação?", "Campo, painel, entrevistas e registros de MOC.", True),
    ("EHS-05", "Auditoria EHS", "MOCs NR-12 foram aprovadas e encerradas com testes, treinamento e atualização documental?", "Registros de MOC e pacote de encerramento.", True),
    ("EHS-06", "Auditoria EHS", "PACs possuem responsável, prazo, classificação e acompanhamento de vencidos/reincidentes?", "PAC e análise de pendências.", False),
]

EHS_CHECKLIST = [
    ("EHS-01", "Liderança e Gestão EHS", "Governança, responsabilidades, indicadores e cultura de EHS.", [
        "Existe política de EHS formalizada e comunicada?",
        "A liderança participa ativamente das ações de EHS?",
        "Existem metas e indicadores de EHS definidos?",
        "Os riscos críticos são acompanhados pela liderança?",
    ]),
    ("EHS-02", "Conformidade Legal", "Gestão de requisitos legais, licenças, evidências e prazos.", [
        "Existe levantamento atualizado de requisitos legais?",
        "As licenças ambientais estão válidas?",
        "Existem controles para condicionantes legais?",
        "Há gestão de prazos legais?",
    ]),
    ("EHS-03", "Gestão de Riscos", "Identificação de perigos, avaliação de riscos e eficácia dos controles.", [
        "Existe processo formal de identificação de perigos?",
        "Os riscos ocupacionais estão avaliados?",
        "Existem controles implementados para riscos críticos?",
        "Mudanças operacionais passam por avaliação de risco?",
    ]),
    ("EHS-04", "Investigação de Incidentes", "Reporte, investigação, causas sistêmicas e ações corretivas.", [
        "Existe processo formal de investigação de incidentes?",
        "As causas sistêmicas são avaliadas?",
        "Os aprendizados são compartilhados?",
        "Near misses são investigados?",
    ]),
    ("EHS-05", "Treinamentos e Competências", "Matriz de treinamento, competências críticas e reciclagens.", [
        "Existe matriz de treinamento atualizada?",
        "Os treinamentos obrigatórios estão válidos?",
        "Há avaliação de eficácia dos treinamentos?",
        "As competências críticas estão mapeadas?",
    ]),
    ("EHS-06", "Gestão Ambiental", "Resíduos, emissões, efluentes e resposta ambiental.", [
        "Existe segregação adequada de resíduos?",
        "Existe controle de MTR e CDF?",
        "Há controle de emissões atmosféricas e efluentes?",
        "Existe plano de resposta ambiental?",
    ]),
    ("EHS-07", "Segurança Operacional", "Máquinas, NR-12, bloqueio, EPI, permissões e controles críticos.", [
        "Máquinas possuem proteções adequadas?",
        "Existe atendimento à NR-12?",
        "Há bloqueio e etiquetagem implementados?",
        "Existe controle de energia perigosa?",
    ]),
    ("EHS-08", "Preparação e Resposta a Emergências", "Plano de emergência, brigada, simulados e equipamentos críticos.", [
        "Existe plano de emergência atualizado?",
        "Há brigada treinada?",
        "Existem simulados periódicos?",
        "Os equipamentos de emergência estão inspecionados?",
    ]),
]


def seed_sites(session):
    for codigo in SITES_PADRAO:
        site = session.query(Site).filter_by(codigo=codigo).one_or_none()
        if site is None:
            session.add(Site(codigo=codigo, nome=f"Site {codigo}", ativo=True))
    session.flush()


def seed_usuarios(session):
    for nome, email in [("Eduardo", "eduardo@empresa.local"), ("Capitu", "capitu@empresa.local")]:
        user = session.query(Usuario).filter_by(email=email).one_or_none()
        if user is None:
            session.add(Usuario(nome=nome, email=email, perfil="Admin_LAG", ativo=True))
    sjc = session.query(Site).filter_by(codigo="SJC").one_or_none()
    if sjc and session.query(Usuario).filter_by(email="ehs.sjc@empresa.local").one_or_none() is None:
        session.add(Usuario(nome="EHS Local SJC", email="ehs.sjc@empresa.local", perfil="EHS_Local", site_id=sjc.id, ativo=True))
    session.flush()


def seed_nr12_checklist(session):
    for pos, item in enumerate(NR12_CHECKLIST, 1):
        codigo, tipo, pergunta, evidencia, critico = item
        obj = session.query(NR12ChecklistItem).filter_by(codigo=codigo).one_or_none()
        if obj is None:
            obj = NR12ChecklistItem(codigo=codigo, posicao=pos)
            session.add(obj)
        obj.tipo_verificacao = tipo
        obj.pergunta = pergunta
        obj.evidencia_esperada = evidencia
        obj.critico = critico
        obj.ativo = True


def criticidade_por_pergunta(pergunta):
    texto = pergunta.lower()
    if any(token in texto for token in ["legal", "nr-12", "emergência", "energia perigosa", "risco crítico"]):
        return "Crítico"
    if any(token in texto for token in ["risco", "incidente", "treinamento", "máquinas"]):
        return "Alto"
    return "Médio"


def seed_ehs_checklist(session):
    for codigo, titulo, descricao, perguntas in EHS_CHECKLIST:
        diretiva = session.query(EHSIndicadorDiretiva).filter_by(codigo=codigo).one_or_none()
        if diretiva is None:
            diretiva = EHSIndicadorDiretiva(codigo=codigo)
            session.add(diretiva)
            session.flush()
        diretiva.titulo = titulo
        diretiva.descricao = descricao
        diretiva.ativa = True
        for idx, pergunta in enumerate(perguntas, 1):
            req_codigo = f"{codigo}-{idx:02d}"
            req = session.query(EHSRequisito).filter_by(codigo=req_codigo).one_or_none()
            if req is None:
                req = EHSRequisito(codigo=req_codigo, diretiva_id=diretiva.id)
                session.add(req)
            req.pergunta = pergunta
            req.orientacao = "Avaliar documentos, registros, entrevistas e verificação em campo."
            req.criticidade = criticidade_por_pergunta(pergunta)
            req.evidencia_esperada = "Documento / Registro / Entrevista / Campo"
            req.ativo = True


def ensure_nr12_respostas(session, verificacao_id):
    verificacao = session.get(NR12Verificacao, verificacao_id)
    if not verificacao:
        return
    existentes = {r.item_id for r in session.query(NR12Resposta).filter_by(verificacao_id=verificacao_id)}
    itens = session.query(NR12ChecklistItem).filter_by(tipo_verificacao=verificacao.tipo_verificacao, ativo=True).order_by(NR12ChecklistItem.posicao).all()
    for item in itens:
        if item.id not in existentes:
            session.add(NR12Resposta(verificacao_id=verificacao_id, item_id=item.id, aplicavel=True, resultado="Conforme"))


def ensure_ehs_respostas(session, auditoria_id):
    existentes = {r.requisito_id for r in session.query(EHSResposta).filter_by(auditoria_id=auditoria_id)}
    for req in session.query(EHSRequisito).filter_by(ativo=True).all():
        if req.id not in existentes:
            session.add(EHSResposta(auditoria_id=auditoria_id, requisito_id=req.id, aplicavel=True, status="Conforme", nota_maturidade=3))


def seed_demo(session):
    if session.query(NR12Maquina).count() > 0 or session.query(EHSAuditoria).count() > 0:
        return
    sjc = session.query(Site).filter_by(codigo="SJC").one()
    dia = session.query(Site).filter_by(codigo="DIA").one()
    m1 = NR12Maquina(
        codigo="SJC-ENV-001", site_id=sjc.id, area="Envase", linha_processo="Linha 1", nome="Envasadora automática",
        fabricante="Fictícia Tech", modelo="ENV-500", numero_serie="FT500-001", ano=2018, tipo_equipamento="Envasadora",
        responsavel_area="Produção SJC", criticidade="Alto", status_nr12="Conforme", status_sugerido="Conforme",
        ultima_adequacao=date.today() - timedelta(days=220), ultima_auditoria=date.today() - timedelta(days=40),
        proxima_auditoria=date.today() + timedelta(days=50), possui_laudo=True, possui_art=True,
        possui_apreciacao_risco=True, possui_manual_atualizado=True, possui_treinamento=True,
    )
    m2 = NR12Maquina(
        codigo="DIA-PRE-002", site_id=dia.id, area="Prensas", linha_processo="Célula A", nome="Prensa hidráulica",
        fabricante="Prensas Brasil", modelo="PH-200", numero_serie="PB200-109", ano=2012, tipo_equipamento="Prensa",
        responsavel_area="Manutenção DIA", criticidade="Crítico", status_nr12="Bloqueada por desvio crítico",
        status_sugerido="Bloqueada por desvio crítico", ultima_adequacao=date.today() - timedelta(days=400),
        ultima_auditoria=date.today() - timedelta(days=95), proxima_auditoria=date.today() - timedelta(days=5),
        possui_laudo=True, possui_art=False, possui_apreciacao_risco=True, possui_manual_atualizado=False, possui_treinamento=True,
        observacoes="Pendência documental e PAC crítico em aberto.",
    )
    session.add_all([m1, m2])
    session.flush()
    session.add_all([
        NR12Documento(maquina_id=m1.id, tipo_documento="Laudo NR-12", nome="Laudo NR-12 SJC-ENV-001", data_emissao=date.today() - timedelta(days=220), data_validade=date.today() + timedelta(days=500), responsavel="EHS SJC", status="Válido"),
        NR12Documento(maquina_id=m1.id, tipo_documento="ART", nome="ART SJC-ENV-001", data_emissao=date.today() - timedelta(days=220), responsavel="Engenharia", status="Válido"),
        NR12Documento(maquina_id=m2.id, tipo_documento="Laudo NR-12", nome="Laudo NR-12 DIA-PRE-002", data_emissao=date.today() - timedelta(days=400), data_validade=date.today() - timedelta(days=10), responsavel="EHS DIA", status="Vencido"),
        NR12PAC(origem="Auditoria EHS", site_id=dia.id, maquina_id=m2.id, descricao_desvio="Botão de emergência sem evidência de teste funcional e ART ausente.", classificacao="Crítico", responsavel="Manutenção DIA", area_responsavel="Manutenção", prazo=date.today() - timedelta(days=2), status="Aberto"),
        NR12MOC(maquina_id=m2.id, site_id=dia.id, tipo_mudanca="Substituição de componente de segurança", descricao="Troca de sensor de segurança por componente alternativo.", solicitante="Manutenção DIA", area_solicitante="Manutenção", impacta_seguranca=True, exige_moc=True, status="Implementada", aprovacao_ehs=False, aprovacao_manutencao=True, exige_auditoria_pos_mudanca=True),
    ])
    aud = EHSAuditoria(nome="Auditoria Cruzada SJC 2026", ano=date.today().year, ciclo="Ciclo 1", site_auditado_id=sjc.id, site_auditor_lider_id=dia.id, auditor_lider="Eduardo", data_planejada=date.today() + timedelta(days=20), status="Planejada", escopo="Diretrizes EHS corporativas")
    session.add(aud)
    session.flush()
    ensure_ehs_respostas(session, aud.id)
    session.add(EHSPAC(auditoria_id=aud.id, site_id=sjc.id, tipo_achado="Observação", descricao="Fortalecer evidências de acompanhamento de indicadores EHS.", criticidade="Média", responsavel="EHS SJC", area_responsavel="EHS", prazo=date.today() + timedelta(days=30), status="Aberto"))


def seed_base(session):
    seed_sites(session)
    seed_usuarios(session)
    seed_nr12_checklist(session)
    seed_ehs_checklist(session)
    seed_demo(session)
    for verificacao in session.query(NR12Verificacao).all():
        ensure_nr12_respostas(session, verificacao.id)
    for auditoria in session.query(EHSAuditoria).all():
        ensure_ehs_respostas(session, auditoria.id)
    session.commit()
