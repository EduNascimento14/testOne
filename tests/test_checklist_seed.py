from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ehs_audit.checklist_seed import LACUNA_BASE_REFERENCIA, ensure_seed_data, validate_checklist_seed
from ehs_audit.models import Base, Diretiva, Requisito, Site


def make_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)()


def test_seed_base_incorpora_19_gdts_e_221_requisitos_sem_lacunas_auditaveis():
    session = make_session()
    result = ensure_seed_data(session)
    assert result["valido"] is True
    assert session.query(Site).count() == 6
    assert session.query(Diretiva).count() == 19
    assert session.query(Requisito).filter_by(ativo=True).count() == 221
    for codigo in ["4.12.02", "4.12.19"]:
        diretiva = session.query(Diretiva).filter_by(codigo=codigo).one()
        assert diretiva.observacao == LACUNA_BASE_REFERENCIA
        assert session.query(Requisito).filter_by(diretiva_id=diretiva.id, ativo=True).count() == 0


def test_seed_e_idempotente_e_nao_duplica_requisitos():
    session = make_session()
    ensure_seed_data(session)
    ensure_seed_data(session)
    validation = validate_checklist_seed(session)
    assert validation == {"diretivas": 19, "requisitos": 221, "req_41202": 0, "req_41219": 0, "valido": True}


def test_seed_sincroniza_checklists_de_auditorias_existentes():
    from datetime import date

    from ehs_audit.checklist_seed import ensure_auditoria_checklists
    from ehs_audit.models import RespostaChecklist
    from ehs_audit.services import criar_auditoria

    session = make_session()
    ensure_seed_data(session)
    sites = {site.codigo: site for site in session.query(Site).all()}
    auditoria = criar_auditoria(
        session,
        nome="Auditoria Teste SJC",
        ano=2026,
        ciclo="Ciclo Teste",
        site_auditado_id=sites["SJC"].id,
        site_auditor_lider_id=sites["DIA"].id,
        site_auditor_apoio_id=None,
        auditor_lider="Auditor Teste",
        auditor_apoio="",
        data_planejada=date.today(),
        status="Planejada",
        escopo="Checklist completo",
        observacoes="",
    )
    resposta = session.query(RespostaChecklist).filter_by(auditoria_id=auditoria.id).first()
    session.delete(resposta)
    session.commit()

    assert session.query(RespostaChecklist).filter_by(auditoria_id=auditoria.id).count() == 220
    assert ensure_auditoria_checklists(session) == 1
    session.commit()
    assert session.query(RespostaChecklist).filter_by(auditoria_id=auditoria.id).count() == 221
