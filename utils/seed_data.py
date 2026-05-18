from __future__ import annotations

from datetime import date, timedelta
from sqlalchemy.orm import Session
from auth import hash_password
from models import ActionPlan, Audit, ChecklistTemplate, Document, Machine, Site, User
from utils.validations import SITES

CHECKLISTS = [
    (1, "Checklist operacional", "Proteções fixas e móveis estão instaladas, visivelmente íntegras e sem remoção indevida?", "Verificação visual antes do uso.", True),
    (2, "Checklist operacional", "Botões de emergência estão acessíveis, identificados e sem obstrução?", "Inspeção visual e teste conforme rotina local, quando aplicável.", True),
    (3, "Checklist operacional", "Não há bypass visível, jumper, calço, fita, amarração ou improviso em dispositivos de segurança?", "Inspeção visual de proteções, sensores, chaves e comandos.", True),
    (4, "Checklist operacional", "Sinalizações de segurança e identificação da máquina estão legíveis e preservadas?", "Placas, etiquetas, pictogramas e identificação patrimonial.", False),
    (5, "Checklist operacional", "Painéis, cabos, conexões e mangueiras não apresentam condição anormal aparente?", "Sem danos, vazamentos, cabos expostos ou partes soltas.", False),
    (6, "Checklist operacional", "A máquina está sem ruído, vibração, vazamento ou condição insegura aparente?", "Observação do equipamento em condição normal de operação.", False),
    (7, "Checklist operacional", "Operador está treinado/autorizado e conhece a comunicação de desvios?", "Registro de treinamento/autorização ou confirmação da liderança.", False),
    (8, "Checklist operacional", "Desvios identificados foram comunicados imediatamente à liderança, Manutenção ou EHS?", "Registro de comunicação, contenção ou abertura de ação.", True),

    (101, "Inspeção de manutenção", "Proteções fixas e móveis estão presentes, íntegras, fixadas e alinhadas conforme projeto/laudo?", "Inspeção técnica contra condição prevista no projeto, laudo ou inventário.", True),
    (102, "Inspeção de manutenção", "Intertravamentos, sensores, chaves, cortinas ou scanners funcionam conforme teste previsto?", "Teste funcional registrado com resultado.", True),
    (103, "Inspeção de manutenção", "Botões de emergência geram parada segura e não provocam partida inesperada no desacionamento?", "Teste funcional em pontos aplicáveis.", True),
    (104, "Inspeção de manutenção", "Relé/controlador/PLC de segurança não apresenta falha, alarme ou alteração sem MOC?", "Diagnóstico, painel, programa ou registro de mudança.", True),
    (105, "Inspeção de manutenção", "Não há bypass, atuador avulso, jumper, imã externo, fita, calço ou anulação de dispositivo?", "Inspeção técnica de campo e painel.", True),
    (106, "Inspeção de manutenção", "Partida, rearme, modos de operação e parada segura permanecem conforme condição validada?", "Teste funcional e comparação com condição aprovada.", True),
    (107, "Inspeção de manutenção", "Painéis elétricos estão fechados, identificados, sem dano e com documentação rastreável?", "Inspeção NR-10, diagramas e identificação.", False),
    (108, "Inspeção de manutenção", "Fontes de energia, pontos de bloqueio e procedimento LOTO estão disponíveis e funcionais?", "Procedimento de bloqueio, pontos físicos e teste de energia zero.", True),
    (109, "Inspeção de manutenção", "Intervenções em proteção/dispositivo de segurança possuem ordem, registro e teste funcional pós-intervenção?", "Ordem de manutenção, formulário de intervenção e liberação.", True),
    (110, "Inspeção de manutenção", "Componentes substituídos são equivalentes ou tiveram avaliação formal/MOC quando diferentes?", "Especificação técnica, aprovação ou MOC.", True),
    (111, "Inspeção de manutenção", "Proteções removidas para manutenção foram reinstaladas antes do retorno à operação?", "Registro de liberação e aceite operacional quando aplicável.", True),
    (112, "Inspeção de manutenção", "Pendências, desvios e necessidade de bloqueio foram registrados e encaminhados?", "Plano de ação, bloqueio, comunicação à liderança/EHS.", True),

    (201, "Auditoria EHS", "Inventário NR-12 está atualizado com status, criticidade, periodicidade, responsável e próximas inspeções?", "Inventário vigente e coerente com campo.", False),
    (202, "Auditoria EHS", "Periodicidades de pré-uso, manutenção e auditoria EHS estão planejadas conforme criticidade?", "Calendário, plano de inspeção ou registros no sistema.", False),
    (203, "Auditoria EHS", "Laudo NR-12, ART e apreciação de risco estão disponíveis e compatíveis com a condição atual?", "Pacote documental da máquina/amostra auditada.", True),
    (204, "Auditoria EHS", "Treinamentos de operadores e manutenção estão disponíveis para máquinas aplicáveis?", "Registros de treinamento e autorização.", False),
    (205, "Auditoria EHS", "Checklists operacionais e inspeções de manutenção estão sendo executados no prazo?", "Registros recentes e aderência à periodicidade.", False),
    (206, "Auditoria EHS", "Proteções, intertravamentos, sensores/cortinas e emergências permanecem funcionais em campo?", "Inspeção amostral e testes funcionais aplicáveis.", True),
    (207, "Auditoria EHS", "Não há evidência de bypass, descaracterização de segurança ou alteração sem aprovação?", "Campo, painel, entrevistas e registros de MOC.", True),
    (208, "Auditoria EHS", "MOCs NR-12 foram abertos, aprovados e encerrados com testes, treinamento e atualização documental quando aplicável?", "Registros de MOC e pacote de encerramento.", True),
    (209, "Auditoria EHS", "Desvios críticos geraram bloqueio imediato e liberação formal após correção/teste funcional?", "Registro de bloqueio/liberação e evidência de teste.", True),
    (210, "Auditoria EHS", "Planos de ação possuem responsável, prazo, classificação e acompanhamento de vencidos/reincidentes?", "Plano de ação e análise de pendências.", False),
    (211, "Auditoria EHS", "Comitê Local NR-12 acompanha indicadores, desvios, bloqueios, MOCs e pendências?", "Ata, pauta, relatório ou evidência de governança.", False),
    (212, "Auditoria EHS", "Termo anual de garantia de sustentação NR-12 do site foi emitido ou planejado?", "Termo assinado ou cronograma formal.", False),
]


def seed_checklists(session: Session) -> None:
    desired_positions = {position for position, *_ in CHECKLISTS}
    for template in session.query(ChecklistTemplate).all():
        if template.position not in desired_positions:
            template.active = False
    for position, audit_type, question, evidence, critical in CHECKLISTS:
        template = session.query(ChecklistTemplate).filter_by(position=position).first()
        if template is None:
            template = ChecklistTemplate(position=position)
            session.add(template)
        template.audit_type = audit_type
        template.question = question
        template.evidence_expected = evidence
        template.is_critical = critical
        template.active = True
    session.commit()


def seed_initial_data(session: Session) -> None:
    if session.query(Site).count() == 0:
        for code in SITES:
            session.add(Site(code=code, name=f"Site {code}"))
        session.commit()
    if session.query(User).count() == 0:
        session.add_all([
            User(name="Eduardo", email="eduardo@example.com", role="Admin Corporativo", password_hash=hash_password("admin123")),
            User(name="Capitu", email="capitu@example.com", role="Admin Corporativo", password_hash=hash_password("admin123")),
        ])
        session.commit()
    seed_checklists(session)
    if session.query(Machine).count() == 0:
        sjc = session.query(Site).filter_by(code="SJC").one()
        dia = session.query(Site).filter_by(code="DIA").one()
        m1 = Machine(machine_code="SJC-ENV-001", site_id=sjc.id, area="Envase", line_process="Linha 1", name="Envasadora automática", manufacturer="Fictícia Tech", model="ENV-500", serial_number="FT500-001", manufacturing_year=2018, equipment_type="Envasadora", area_owner="Produção SJC", criticality="Alta", nr12_status="Conforme", suggested_status="Conforme", last_nr12_adequacy_date=date.today()-timedelta(days=220), last_audit_date=date.today()-timedelta(days=40), next_audit_date=date.today()+timedelta(days=50), has_nr12_report=True, has_art=True, has_risk_assessment=True, has_updated_manual=True, has_training=True, notes="Máquina exemplo conforme.")
        m2 = Machine(machine_code="DIA-PRE-002", site_id=dia.id, area="Prensas", line_process="Célula A", name="Prensa hidráulica", manufacturer="Prensas Brasil", model="PH-200", serial_number="PB200-109", manufacturing_year=2012, equipment_type="Prensa", area_owner="Manutenção DIA", criticality="Alta", nr12_status="Bloqueada por desvio crítico", suggested_status="Bloqueada por desvio crítico", last_nr12_adequacy_date=date.today()-timedelta(days=400), last_audit_date=date.today()-timedelta(days=95), next_audit_date=date.today()-timedelta(days=5), has_nr12_report=True, has_art=False, has_risk_assessment=True, has_updated_manual=False, has_training=True, notes="Pendência de ART e ação crítica em aberto.")
        session.add_all([m1, m2]); session.commit()
        session.add_all([
            Document(machine_id=m1.id, document_type="Laudo NR-12", name="Laudo NR-12 SJC-ENV-001", issue_date=date.today()-timedelta(days=220), expiry_date=date.today()+timedelta(days=500), responsible="EHS SJC", status="Válido"),
            Document(machine_id=m1.id, document_type="ART", name="ART adequação SJC-ENV-001", issue_date=date.today()-timedelta(days=220), responsible="Engenharia", status="Válido"),
            Document(machine_id=m2.id, document_type="Laudo NR-12", name="Laudo NR-12 DIA-PRE-002", issue_date=date.today()-timedelta(days=400), expiry_date=date.today()-timedelta(days=10), responsible="EHS DIA", status="Vencido"),
        ])
        session.add(Audit(machine_id=m1.id, site_id=sjc.id, audit_type="Auditoria EHS", audit_date=date.today()-timedelta(days=40), auditor="Eduardo", result="Conforme", score=96.0, general_notes="Sem desvios relevantes."))
        session.add(ActionPlan(origin="Auditoria", machine_id=m2.id, deviation_description="Botão de emergência sem evidência de teste funcional e ART ausente.", classification="Crítico", responsible="Manutenção DIA", responsible_area="Manutenção", due_date=date.today()-timedelta(days=2), status="Aberta", comments="Bloqueia status conforme."))
        session.commit()
