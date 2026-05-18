from __future__ import annotations

from datetime import date, timedelta
from sqlalchemy.orm import Session
from auth import hash_password
from models import ActionPlan, Audit, ChecklistTemplate, Document, Machine, Site, User
from utils.validations import SITES

CHECKLIST = [
    (1, "Proteções fixas estão instaladas, íntegras e sem remoção indevida?", True),
    (2, "Proteções móveis/intertravadas funcionam corretamente?", True),
    (3, "Botões de emergência estão acessíveis, identificados e funcionais?", True),
    (4, "Cortinas de luz/sensores/dispositivos optoeletrônicos funcionam corretamente?", True),
    (5, "Relés/controladores de segurança estão íntegros e sem bypass?", True),
    (6, "Não há jampeamento, burla ou neutralização de dispositivos de segurança?", True),
    (7, "Sinalizações de segurança estão visíveis e adequadas?", False),
    (8, "Pontos de esmagamento, corte, aprisionamento ou projeção estão protegidos?", True),
    (9, "Procedimentos de operação segura estão disponíveis?", False),
    (10, "Procedimentos de bloqueio de energia/LOTO estão disponíveis e aplicáveis?", False),
    (11, "Manutenção não realizou alteração sem MOC?", True),
    (12, "Operadores foram treinados na condição atual da máquina?", False),
    (13, "Documentação técnica está disponível e atualizada?", False),
    (14, "Não houve alteração de layout, processo ou componente crítico sem avaliação?", True),
    (15, "Máquina está em condição segura para operação?", True),
]


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
    if session.query(ChecklistTemplate).count() == 0:
        for position, question, critical in CHECKLIST:
            session.add(ChecklistTemplate(position=position, question=question, is_critical=critical))
        session.commit()
    if session.query(Machine).count() == 0:
        sjc = session.query(Site).filter_by(code="SJC").one()
        dia = session.query(Site).filter_by(code="DIA").one()
        m1 = Machine(machine_code="SJC-ENV-001", site_id=sjc.id, area="Envase", line_process="Linha 1", name="Envasadora automática", manufacturer="Fictícia Tech", model="ENV-500", serial_number="FT500-001", manufacturing_year=2018, equipment_type="Envasadora", area_owner="Produção SJC", criticality="Alta", nr12_status="Conforme", suggested_status="Conforme", last_nr12_adequacy_date=date.today()-timedelta(days=220), last_audit_date=date.today()-timedelta(days=40), next_audit_date=date.today()+timedelta(days=140), has_nr12_report=True, has_art=True, has_risk_assessment=True, has_updated_manual=True, has_training=True, notes="Máquina exemplo conforme.")
        m2 = Machine(machine_code="DIA-PRE-002", site_id=dia.id, area="Prensas", line_process="Célula A", name="Prensa hidráulica", manufacturer="Prensas Brasil", model="PH-200", serial_number="PB200-109", manufacturing_year=2012, equipment_type="Prensa", area_owner="Manutenção DIA", criticality="Alta", nr12_status="Não conforme", suggested_status="Não conforme", last_nr12_adequacy_date=date.today()-timedelta(days=400), last_audit_date=date.today()-timedelta(days=95), next_audit_date=date.today()-timedelta(days=5), has_nr12_report=True, has_art=False, has_risk_assessment=True, has_updated_manual=False, has_training=True, notes="Pendência de ART e ação crítica em aberto.")
        session.add_all([m1, m2]); session.commit()
        session.add_all([
            Document(machine_id=m1.id, document_type="Laudo NR-12", name="Laudo NR-12 SJC-ENV-001", issue_date=date.today()-timedelta(days=220), expiry_date=date.today()+timedelta(days=500), responsible="EHS SJC", status="Válido"),
            Document(machine_id=m1.id, document_type="ART", name="ART adequação SJC-ENV-001", issue_date=date.today()-timedelta(days=220), responsible="Engenharia", status="Válido"),
            Document(machine_id=m2.id, document_type="Laudo NR-12", name="Laudo NR-12 DIA-PRE-002", issue_date=date.today()-timedelta(days=400), expiry_date=date.today()-timedelta(days=10), responsible="EHS DIA", status="Vencido"),
        ])
        session.add(Audit(machine_id=m1.id, site_id=sjc.id, audit_type="Auditoria EHS", audit_date=date.today()-timedelta(days=40), auditor="Eduardo", result="Conforme", score=96.0, general_notes="Sem desvios relevantes."))
        session.add(ActionPlan(origin="Auditoria", machine_id=m2.id, deviation_description="Botão de emergência sem evidência de teste funcional e ART ausente.", classification="Crítico", responsible="Manutenção DIA", responsible_area="Manutenção", due_date=date.today()-timedelta(days=2), status="Aberta", comments="Bloqueia status conforme."))
        session.commit()
