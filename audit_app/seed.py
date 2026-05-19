from audit_app.constants import CHECKLIST_BASE, CRITICIDADES, SITES_PADRAO
from audit_app.models import Auditoria, Diretiva, Requisito, RespostaChecklist, Site, Usuario


def logical_requisito_codes():
    return {f"{cat['codigo']}-{idx:02d}" for cat in CHECKLIST_BASE for idx, _ in enumerate(cat["perguntas"], 1)}


def criticidade_por_texto(pergunta):
    p = pergunta.lower()
    if any(t in p for t in ["legal", "licença", "nr-12", "emergência", "bloqueio", "energia perigosa", "produtos perigosos"]):
        return "Crítico"
    if any(t in p for t in ["risco", "incidente", "treinamento", "máquinas", "altura", "confinados"]):
        return "Alto"
    return "Médio"


def ensure_auditoria_checklist(session, auditoria_id):
    existentes = {r.requisito_id for r in session.query(RespostaChecklist).filter_by(auditoria_id=auditoria_id).all()}
    criados = 0
    for requisito in session.query(Requisito).filter_by(ativo=True).all():
        if requisito.id not in existentes:
            session.add(RespostaChecklist(auditoria_id=auditoria_id, requisito_id=requisito.id, aplicavel=True, status_conformidade="Conforme", nota_maturidade=3))
            criados += 1
    return criados


def seed_base(session):
    for codigo in SITES_PADRAO:
        site = session.query(Site).filter_by(codigo=codigo).one_or_none()
        if site is None:
            session.add(Site(codigo=codigo, nome=codigo, ativo=True))
        else:
            site.ativo = True
            site.nome = site.nome or codigo
    session.flush()

    primeiro_site = session.query(Site).filter_by(codigo="SJC").one_or_none()
    usuarios = [
        ("Admin EHS", "admin.ehs@empresa.local", "Admin_LAG", primeiro_site),
        ("Auditor EHS", "auditor.ehs@empresa.local", "Auditor", primeiro_site),
        ("Visualizador EHS", "visualizador.ehs@empresa.local", "Visualizador", primeiro_site),
    ]
    for nome, email, perfil, site in usuarios:
        user = session.query(Usuario).filter_by(email=email).one_or_none()
        if user is None:
            session.add(Usuario(nome=nome, email=email, perfil=perfil, site_id=site.id if site else None, ativo=True))
        else:
            user.ativo = True
            user.perfil = perfil
    session.flush()

    valid_codes = logical_requisito_codes()
    for cat in CHECKLIST_BASE:
        diretiva = session.query(Diretiva).filter_by(codigo=cat["codigo"]).one_or_none()
        if diretiva is None:
            diretiva = Diretiva(codigo=cat["codigo"], titulo=cat["titulo"], descricao=cat["descricao"], ativa=True)
            session.add(diretiva)
            session.flush()
        else:
            diretiva.titulo = cat["titulo"]
            diretiva.descricao = cat["descricao"]
            diretiva.ativa = True
            diretiva.observacao = None
        for idx, pergunta in enumerate(cat["perguntas"], 1):
            codigo_req = f"{cat['codigo']}-{idx:02d}"
            requisito = session.query(Requisito).filter_by(codigo_requisito=codigo_req).one_or_none()
            if requisito is None:
                session.add(Requisito(diretiva_id=diretiva.id, codigo_requisito=codigo_req, pergunta=pergunta, orientacao="Avaliar documentos, registros, entrevistas e verificação em campo.", criticidade=criticidade_por_texto(pergunta), tipo_evidencia_esperada="Documento / Registro / Entrevista / Campo", area_responsavel_sugerida="EHS / Área responsável", ativo=True))
            else:
                requisito.diretiva_id = diretiva.id
                requisito.pergunta = pergunta
                requisito.orientacao = requisito.orientacao or "Avaliar documentos, registros, entrevistas e verificação em campo."
                requisito.criticidade = requisito.criticidade if requisito.criticidade in CRITICIDADES else criticidade_por_texto(pergunta)
                requisito.tipo_evidencia_esperada = requisito.tipo_evidencia_esperada or "Documento / Registro / Entrevista / Campo"
                requisito.area_responsavel_sugerida = requisito.area_responsavel_sugerida or "EHS / Área responsável"
                requisito.ativo = True

    for requisito in session.query(Requisito).all():
        if requisito.codigo_requisito not in valid_codes:
            requisito.ativo = False
    for auditoria in session.query(Auditoria).all():
        ensure_auditoria_checklist(session, auditoria.id)


def validate_seed(session):
    total_categorias = session.query(Diretiva).filter(Diretiva.codigo.in_([c["codigo"] for c in CHECKLIST_BASE]), Diretiva.ativa.is_(True)).count()
    total_requisitos = session.query(Requisito).filter(Requisito.codigo_requisito.in_(logical_requisito_codes()), Requisito.ativo.is_(True)).count()
    return {"categorias": total_categorias, "requisitos_ativos": total_requisitos, "base_ok": total_categorias == 8 and total_requisitos == 80}
