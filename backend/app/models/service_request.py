from __future__ import annotations

from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Float,
    BigInteger,
)
from sqlalchemy.orm import relationship

from ..core.database import Base


class RequestStatus(str, PyEnum):
    CREATED = "CREATED"
    MATCHING = "MATCHING"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"
    CANCELED = "CANCELED"


class RequestUrgency(str, PyEnum):
    NORMAL = "NORMAL"
    URGENT = "URGENT"


class ContactPref(str, PyEnum):
    WHATSAPP = "WHATSAPP"
    CALL = "CALL"
    CHAT = "CHAT"


class ServiceRequest(Base):
    __tablename__ = "service_requests"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    assigned_worker_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    category = Column(String(60), nullable=False, default="GENERAL")
    title = Column(String(120), nullable=False)
    description = Column(Text, nullable=False)

    urgency = Column(Enum(RequestUrgency), nullable=False, default=RequestUrgency.NORMAL)

    city = Column(String(80), nullable=True)
    neighborhood = Column(String(120), nullable=True)
    address = Column(String(200), nullable=True)
    address_ref = Column(String(200), nullable=True)

    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    accuracy_m = Column(Integer, nullable=True)

    schedule_date = Column(Date, nullable=True)
    time_window = Column(String(40), nullable=True)

    budget_min = Column(BigInteger, nullable=True)
    budget_max = Column(BigInteger, nullable=True)

    contact_name = Column(String(120), nullable=True)
    contact_phone = Column(String(40), nullable=True)
    contact_pref = Column(Enum(ContactPref), nullable=True)

    status = Column(Enum(RequestStatus), nullable=False, default=RequestStatus.CREATED)

    assigned_at = Column(DateTime, nullable=True)
    accepted_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    user = relationship(
        "User",
        foreign_keys=[user_id],
        back_populates="requests",
    )

    assigned_worker = relationship(
        "User",
        foreign_keys=[assigned_worker_id],
        back_populates="assigned_requests",
    )

    messages = relationship(
        "RequestMessage",
        back_populates="request",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="RequestMessage.created_at.asc()",
    )

    events = relationship(
        "RequestEvent",
        back_populates="request",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="RequestEvent.created_at.desc()",
    )

    reviews = relationship(
        "RequestReview",
        back_populates="request",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="RequestReview.created_at.desc()",
    )
