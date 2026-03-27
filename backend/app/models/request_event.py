from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship

from ..core.database import Base


class RequestEvent(Base):
    __tablename__ = "request_events"

    id = Column(Integer, primary_key=True, index=True)

    request_id = Column(
        Integer,
        ForeignKey("service_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    actor_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    event_type = Column(String(60), nullable=False, index=True)
    title = Column(String(160), nullable=False)
    message = Column(Text, nullable=True)

    status_from = Column(String(30), nullable=True)
    status_to = Column(String(30), nullable=True)

    meta = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    request = relationship("ServiceRequest", back_populates="events")
    actor = relationship("User", foreign_keys=[actor_user_id], lazy="joined")
