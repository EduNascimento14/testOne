from datetime import date, timedelta

from audit_app.constants import CHECKLIST_BASE, CHECKLIST_NR12, CRITICIDADES, SITES_PADRAO
from audit_app.models import Auditoria, ChecklistItemNR12, Diretiva, MaquinaNR12, Requisito, RespostaChecklist, Site, Usuario


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


def seed_sites(session):
    for codigo in SITES_PADRAO:
        site = session.query(Site).filter_by(codigo=codigo).one_or_none()
        if site is None:
            session.add(Site(codigo=codigo, nome=codigo, ativo=True))
        else:
            site.nome = site.nome or codigo
            site.ativo = True
    session.flush()


def seed_usuarios(session):
    sjc = session.query(Site).filter_by(codigo="SJC").one_or_none()
    usuarios = [
        ("Eduardo", "eduardo@empresa.local", "Admin_LAG", None),
        ("Capitu", "capitu@empresa.local", "Admin_LAG", None),
        ("EHS Local SJC", "ehs.sjc@empresa.local", "EHS_Local", sjc),
        ("Auditor Corporativo", "auditor.corporativo@empresa.local", "Auditor", None),
        ("Manutenção SJC", "manutencao.sjc@empresa.local", "Manutencao", sjc),
        ("Operação SJC", "operacao.sjc@empresa.local", "Producao_Operacao", sjc),
    ]
    for nome, email, perfil, site in usuarios:
        user = session.query(Usuario).filter_by(email=email).one_or_none()
        if user is None:
            session.add(Usuario(nome=nome, email=email, perfil=perfil, site_id=site.id if site else None, ativo=True))
        else:
            user.nome = nome
            user.perfil = perfil
            user.site_id = site.id if site else None
            user.ativo = True
    session.flush()


def seed_checklist_ehs(session):
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
        for idx, pergunta in enumerate(cat["perguntas"], 1):
            codigo_req = f"{cat['codigo']}-{idx:02d}"
            requisito = session.query(Requisito).filter_by(codigo_requisito=codigo_req).one_or_none()
            data = {
                "diretiva_id": diretiva.id,
                "pergunta": pergunta,
                "orientacao": "Avaliar documentos, registros, entrevistas e verificação em campo.",
                "criticidade": criticidade_por_texto(pergunta),
                "tipo_evidencia_esperada": "Documento / Registro / Entrevista / Campo",
                "area_responsavel_sugerida": "EHS / Área responsável",
                "ativo": True,
            }
            if requisito is None:
                session.add(Requisito(codigo_requisito=codigo_req, **data))
            else:
                for key, value in data.items():
                    setattr(requisito, key, value if key != "criticidade" or requisito.criticidade not in CRITICIDADES else requisito.criticidade)
    for requisito in session.query(Requisito).all():
        if requisito.codigo_requisito not in valid_codes:
            requisito.ativo = False


def seed_checklist_nr12(session):
    valid_codes = set()
    for tipo, itens in CHECKLIST_NR12.items():
        for codigo, pergunta, criticidade in itens:
            valid_codes.add(codigo)
            item = session.query(ChecklistItemNR12).filter_by(codigo=codigo).one_or_none()
            if item is None:
                session.add(ChecklistItemNR12(tipo_verificacao=tipo, codigo=codigo, pergunta=pergunta, criticidade=criticidade, evidencia_esperada="Registro, inspeção visual, teste funcional ou evidência documental", ativo=True))
            else:
                item.tipo_verificacao = tipo
                item.pergunta = pergunta
                item.criticidade = criticidade
                item.ativo = True
    for item in session.query(ChecklistItemNR12).all():
        if item.codigo not in valid_codes:
            item.ativo = False


def seed_maquinas_minimas(session):
    if session.query(MaquinaNR12).count():
        return
    sjc = session.query(Site).filter_by(codigo="SJC").one_or_none()
    dia = session.query(Site).filter_by(codigo="DIA").one_or_none()
    if not sjc:
        return
    maquinas = [
        {"codigo": "SJC-PR-001", "site_id": sjc.id, "area_setor": "Manufatura", "linha_processo": "Linha A", "nome": "Prensa hidráulica 01", "fabricante": "Fabricante A", "modelo": "PH-500", "ano": 2018, "tipo_equipamento": "Prensa", "responsavel_area": "Produção", "criticidade": "Crítico", "status_nr12": "Conforme com observação", "ultima_adequacao_nr12": date.today() - timedelta(days=300), "ultima_auditoria": date.today() - timedelta(days=90), "proxima_auditoria_prevista": date.today() + timedelta(days=90), "possui_laudo_nr12": True, "possui_art": True, "possui_apreciacao_risco": True, "possui_manual_atualizado": True, "possui_treinamento": True},
        {"codigo": "DIA-CV-002", "site_id": dia.id if dia else sjc.id, "area_setor": "Embalagem", "linha_processo": "Linha B", "nome": "Transportador de caixas", "fabricante": "Fabricante B", "modelo": "TC-200", "ano": 2020, "tipo_equipamento": "Transportador", "responsavel_area": "Operação", "criticidade": "Alto", "status_nr12": "Pendente de ação não crítica", "proxima_auditoria_prevista": date.today() - timedelta(days=10), "possui_laudo_nr12": False, "possui_art": True, "possui_apreciacao_risco": True, "possui_manual_atualizado": False, "possui_treinamento": True},
    ]
    for data in maquinas:
        session.add(MaquinaNR12(**data))


def seed_base(session):
    seed_sites(session)
    seed_usuarios(session)
    seed_checklist_ehs(session)
    seed_checklist_nr12(session)
    seed_maquinas_minimas(session)
    for auditoria in session.query(Auditoria).all():
        ensure_auditoria_checklist(session, auditoria.id)


def validate_seed(session):
    total_categorias = session.query(Diretiva).filter(Diretiva.ativa.is_(True)).count()
    total_requisitos = session.query(Requisito).filter(Requisito.ativo.is_(True)).count()
    total_nr12 = session.query(ChecklistItemNR12).filter(ChecklistItemNR12.ativo.is_(True)).count()
    return {"categorias": total_categorias, "requisitos_ativos": total_requisitos, "itens_nr12": total_nr12, "base_ok": total_categorias >= 8 and total_requisitos >= 80 and total_nr12 >= 15}
