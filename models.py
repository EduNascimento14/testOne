from __future__ import annotations

from datetime import date, datetime
from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base


class Site(Base):
    __tablename__ = "sites"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    machines = relationship("Machine", back_populates="site")


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    email: Mapped[str | None] = mapped_column(String(160))
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[str] = mapped_column(String(40), nullable=False)
    site_id: Mapped[int | None] = mapped_column(ForeignKey("sites.id"))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    site = relationship("Site")


class Machine(Base):
    __tablename__ = "machines"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    machine_code: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), nullable=False)
    area: Mapped[str] = mapped_column(String(120), nullable=False)
    line_process: Mapped[str | None] = mapped_column(String(120))
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    manufacturer: Mapped[str | None] = mapped_column(String(120))
    model: Mapped[str | None] = mapped_column(String(120))
    serial_number: Mapped[str | None] = mapped_column(String(120))
    manufacturing_year: Mapped[int | None] = mapped_column(Integer)
    equipment_type: Mapped[str | None] = mapped_column(String(120))
    area_owner: Mapped[str | None] = mapped_column(String(120))
    criticality: Mapped[str] = mapped_column(String(20), default="Média")
    nr12_status: Mapped[str] = mapped_column(String(40), default="Pendente de ação não crítica")
    suggested_status: Mapped[str | None] = mapped_column(String(40))
    last_nr12_adequacy_date: Mapped[date | None] = mapped_column(Date)
    last_audit_date: Mapped[date | None] = mapped_column(Date)
    next_audit_date: Mapped[date | None] = mapped_column(Date)
    has_nr12_report: Mapped[bool] = mapped_column(Boolean, default=False)
    has_art: Mapped[bool] = mapped_column(Boolean, default=False)
    has_risk_assessment: Mapped[bool] = mapped_column(Boolean, default=False)
    has_updated_manual: Mapped[bool] = mapped_column(Boolean, default=False)
    has_training: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    site = relationship("Site", back_populates="machines")
    documents = relationship("Document", back_populates="machine", cascade="all, delete-orphan")
    audits = relationship("Audit", back_populates="machine", cascade="all, delete-orphan")
    actions = relationship("ActionPlan", back_populates="machine", cascade="all, delete-orphan")
    changes = relationship("ChangeManagement", back_populates="machine", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    machine_id: Mapped[int] = mapped_column(ForeignKey("machines.id"), nullable=False)
    document_type: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    issue_date: Mapped[date | None] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    responsible: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(40), default="Válido")
    file_path: Mapped[str | None] = mapped_column(String(300))
    notes: Mapped[str | None] = mapped_column(Text)
    machine = relationship("Machine", back_populates="documents")


class Audit(Base):
    __tablename__ = "audits"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    machine_id: Mapped[int] = mapped_column(ForeignKey("machines.id"), nullable=False)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), nullable=False)
    audit_type: Mapped[str] = mapped_column(String(80), nullable=False)
    audit_date: Mapped[date] = mapped_column(Date, default=date.today)
    auditor: Mapped[str] = mapped_column(String(120), nullable=False)
    participants: Mapped[str | None] = mapped_column(Text)
    result: Mapped[str] = mapped_column(String(40), default="Conforme")
    score: Mapped[float] = mapped_column(Float, default=0.0)
    general_notes: Mapped[str | None] = mapped_column(Text)
    evidence_path: Mapped[str | None] = mapped_column(String(300))
    machine = relationship("Machine", back_populates="audits")
    site = relationship("Site")
    items = relationship("AuditItem", back_populates="audit", cascade="all, delete-orphan")


class AuditItem(Base):
    __tablename__ = "audit_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    audit_id: Mapped[int] = mapped_column(ForeignKey("audits.id"), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    is_critical: Mapped[bool] = mapped_column(Boolean, default=False)
    result: Mapped[str] = mapped_column(String(30), default="Conforme")
    comment: Mapped[str | None] = mapped_column(Text)
    evidence_path: Mapped[str | None] = mapped_column(String(300))
    generate_action: Mapped[bool] = mapped_column(Boolean, default=False)
    audit = relationship("Audit", back_populates="items")


class ActionPlan(Base):
    __tablename__ = "action_plans"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    origin: Mapped[str] = mapped_column(String(60), nullable=False)
    machine_id: Mapped[int] = mapped_column(ForeignKey("machines.id"), nullable=False)
    audit_id: Mapped[int | None] = mapped_column(ForeignKey("audits.id"))
    deviation_description: Mapped[str] = mapped_column(Text, nullable=False)
    classification: Mapped[str] = mapped_column(String(20), default="Menor")
    responsible: Mapped[str | None] = mapped_column(String(120))
    responsible_area: Mapped[str] = mapped_column(String(40), default="EHS")
    due_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(40), default="Aberta")
    completion_evidence: Mapped[str | None] = mapped_column(String(300))
    ehs_validation: Mapped[bool] = mapped_column(Boolean, default=False)
    completion_date: Mapped[date | None] = mapped_column(Date)
    comments: Mapped[str | None] = mapped_column(Text)
    machine = relationship("Machine", back_populates="actions")
    audit = relationship("Audit")


class ChangeManagement(Base):
    __tablename__ = "change_management"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    machine_id: Mapped[int] = mapped_column(ForeignKey("machines.id"), nullable=False)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), nullable=False)
    change_type: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    requester: Mapped[str] = mapped_column(String(120), nullable=False)
    requester_area: Mapped[str] = mapped_column(String(80), nullable=False)
    change_date: Mapped[date] = mapped_column(Date, default=date.today)
    impacts_safety: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_moc: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(40), default="Solicitada")
    ehs_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    maintenance_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    engineering_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    production_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    attached_documents: Mapped[str | None] = mapped_column(String(300))
    needs_post_change_audit: Mapped[bool] = mapped_column(Boolean, default=False)
    needs_training: Mapped[bool] = mapped_column(Boolean, default=False)
    observations: Mapped[str | None] = mapped_column(Text)
    machine = relationship("Machine", back_populates="changes")
    site = relationship("Site")


class Attachment(Base):
    __tablename__ = "attachments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    file_name: Mapped[str] = mapped_column(String(200), nullable=False)
    file_path: Mapped[str] = mapped_column(String(300), nullable=False)
    uploaded_by: Mapped[str | None] = mapped_column(String(120))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class StatusHistory(Base):
    __tablename__ = "status_history"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    machine_id: Mapped[int] = mapped_column(ForeignKey("machines.id"), nullable=False)
    previous_status: Mapped[str | None] = mapped_column(String(40))
    new_status: Mapped[str] = mapped_column(String(40), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    changed_by: Mapped[str | None] = mapped_column(String(120))
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    machine = relationship("Machine")


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    site_id: Mapped[int | None] = mapped_column(ForeignKey("sites.id"))
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="info")
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ChecklistTemplate(Base):
    __tablename__ = "checklist_templates"
    __table_args__ = (UniqueConstraint("position", name="uq_checklist_position"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    audit_type: Mapped[str] = mapped_column(String(80), default="Auditoria EHS")
    question: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_expected: Mapped[str | None] = mapped_column(Text)
    is_critical: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
