# backend/app/models/technician_verification.py
import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
    Index,
)
from sqlalchemy.orm import relationship

from ..core.database import Base


# =========================
# ENUMS
# =========================
class Role(str, enum.Enum):
    USER = "USER"
    WORKER = "WORKER"
    VERIFIER = "VERIFIER"
    ADMIN = "ADMIN"


class TechLevel(str, enum.Enum):
    BASIC = "BASIC"
    TRUST = "TRUST"
    PRO = "PRO"
    PAY = "PAY"


class TechStatus(str, enum.Enum):
    PENDING = "PENDING"
    IN_REVIEW = "IN_REVIEW"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class DocType(str, enum.Enum):
    ID_PHOTO = "ID_PHOTO"
    POLICE_CERT = "POLICE_CERT"
    PROCURADURIA_CERT = "PROCURADURIA_CERT"
    RNMC_CERT = "RNMC_CERT"
    REFERENCES = "REFERENCES"
    PRO_LICENSE = "PRO_LICENSE"
    STUDY_CERT = "STUDY_CERT"
    HEIGHTS_CERT = "HEIGHTS_CERT"
    GAS_CERT = "GAS_CERT"
    RUT = "RUT"
    BANK_CERT = "BANK_CERT"


# =========================
# MODELS
# =========================
class TechnicianProfile(Base):
    __tablename__ = "technician_profiles"

    id = Column(Integer, primary_key=True, index=True)

    # Relación con users
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    user = relationship("User", foreign_keys=[user_id], lazy="joined")

    # Público
    public_name = Column(String(120), nullable=True)
    public_photo_url = Column(String(500), nullable=True)
    city = Column(String(80), nullable=True)
    radius_km = Column(Integer, default=5, nullable=False)
    categories = Column(JSON, default=list, nullable=False)

    badge_level = Column(Enum(TechLevel), default=TechLevel.BASIC, nullable=False)

    # Privado
    doc_type = Column(String(40), nullable=True)
    doc_number = Column(String(40), nullable=True)
    phone = Column(String(40), nullable=True)
    email = Column(String(120), nullable=True)

    # Técnico
    specialty = Column(String(120), nullable=True)
    years_experience = Column(Integer, nullable=True)
    bio = Column(Text, nullable=True)
    activities = Column(JSON, default=list, nullable=False)
    wants_payments = Column(Boolean, default=False, nullable=False)

    # Consentimientos
    consent_terms = Column(Boolean, default=False, nullable=False)
    consent_privacy = Column(Boolean, default=False, nullable=False)
    consent_sensitive = Column(Boolean, default=False, nullable=False)
    consent_text_version = Column(String(20), default="v1", nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Cases
    cases = relationship(
        "VerificationCase",
        back_populates="tech",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def touch(self):
        self.updated_at = datetime.utcnow()


class VerificationCase(Base):
    __tablename__ = "verification_cases"

    id = Column(Integer, primary_key=True, index=True)

    tech_id = Column(
        Integer, ForeignKey("technician_profiles.id"), nullable=False, index=True
    )
    tech = relationship(
        "TechnicianProfile", back_populates="cases", foreign_keys=[tech_id]
    )

    target_level = Column(Enum(TechLevel), default=TechLevel.BASIC, nullable=False)
    status = Column(Enum(TechStatus), default=TechStatus.PENDING, nullable=False, index=True)

    reason = Column(Text, nullable=True)

    verified_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)

    decided_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    decided_by_user = relationship("User", foreign_keys=[decided_by], lazy="joined")

    decision_notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    documents = relationship(
        "VerificationDocument",
        back_populates="case",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    logs = relationship(
        "VerificationAuditLog",
        back_populates="case",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def touch(self):
        self.updated_at = datetime.utcnow()


class VerificationDocument(Base):
    __tablename__ = "verification_documents"

    id = Column(Integer, primary_key=True, index=True)

    case_id = Column(Integer, ForeignKey("verification_cases.id"), nullable=False, index=True)
    case = relationship("VerificationCase", back_populates="documents", foreign_keys=[case_id])

    doc_type = Column(Enum(DocType), nullable=False, index=True)
    content_type = Column(String(80), nullable=True)
    original_filename = Column(String(255), nullable=True)

    size_bytes = Column(Integer, nullable=True)
    sha256 = Column(String(64), nullable=True, index=True)

    meta = Column(JSON, default=dict, nullable=False)

    received_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Minimización / Retención
    storage_ref = Column(String(500), nullable=True)  # antes: placeholder/encrypted://...
    # ✅ NUEVO: ruta RELATIVA dentro de uploads/tech_verification
    # Ej: "case-1/police_cert-<sha>.png"
    file_path = Column(String(500), nullable=True)

    retained_until = Column(DateTime, nullable=True)  # solo ID_PHOTO (<=30d)
    deleted_at = Column(DateTime, nullable=True)

    verified_result = Column(String(40), nullable=True)
    verified_at = Column(DateTime, nullable=True)

    def mark_deleted(self):
        self.deleted_at = datetime.utcnow()


class VerificationAuditLog(Base):
    __tablename__ = "verification_audit_logs"

    id = Column(Integer, primary_key=True, index=True)

    case_id = Column(Integer, ForeignKey("verification_cases.id"), nullable=False, index=True)
    case = relationship("VerificationCase", back_populates="logs", foreign_keys=[case_id])

    actor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    actor = relationship("User", foreign_keys=[actor_id], lazy="joined")

    action = Column(String(60), nullable=False, index=True)
    detail = Column(JSON, default=dict, nullable=False)

    ip = Column(String(80), nullable=True)
    user_agent = Column(String(255), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


# Índices útiles
Index("ix_cases_tech_status", VerificationCase.tech_id, VerificationCase.status)
Index("ix_docs_case_doctype", VerificationDocument.case_id, VerificationDocument.doc_type)
