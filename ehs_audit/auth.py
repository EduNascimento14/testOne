from __future__ import annotations

from .models import Achado, Auditoria, Usuario


def can_edit_admin(user: Usuario | None) -> bool:
    return bool(user and user.perfil == "Admin_LAG")


def can_edit_auditoria(user: Usuario | None, auditoria: Auditoria) -> bool:
    if not user or user.perfil == "Visualizador":
        return False
    if user.perfil == "Admin_LAG":
        return True
    if user.perfil == "EHS_Local" and user.site_id == auditoria.site_auditado_id:
        return True
    if user.perfil == "Auditor":
        nome = (user.nome or "").strip().lower()
        return nome in {(auditoria.auditor_lider or "").strip().lower(), (auditoria.auditor_apoio or "").strip().lower()}
    return False


def can_edit_achado(user: Usuario | None, achado: Achado) -> bool:
    if not user or user.perfil == "Visualizador":
        return False
    if user.perfil == "Admin_LAG":
        return True
    if user.perfil == "EHS_Local" and user.site_id == achado.site_id:
        return True
    if user.perfil == "Responsavel_Acao":
        return (achado.responsavel or "").strip().lower() in {(user.nome or "").strip().lower(), (user.email or "").strip().lower()}
    return user.perfil == "Auditor"
