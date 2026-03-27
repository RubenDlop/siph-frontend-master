from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from ..core.database import Base


class RequestMessage(Base):
    __tablename__ = "request_messages"

    id = Column(Integer, primary_key=True, index=True)

    request_id = Column(
        Integer,
        ForeignKey("service_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    sender_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    body = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    read_at = Column(DateTime, nullable=True)

    request = relationship("ServiceRequest", back_populates="messages")
    sender = relationship(
        "User",
        foreign_keys=[sender_user_id],
        back_populates="sent_request_messages",
    )
