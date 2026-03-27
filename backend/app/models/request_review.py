from __future__ import annotations

from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
)
from sqlalchemy.orm import relationship

from ..core.database import Base


class ReviewRole(str, PyEnum):
    CUSTOMER = "CUSTOMER"
    WORKER = "WORKER"


class RequestReview(Base):
    __tablename__ = "request_reviews"

    __table_args__ = (
        UniqueConstraint("request_id", "reviewer_user_id", name="uq_request_reviews_request_reviewer"),
        CheckConstraint("rating >= 1 AND rating <= 5", name="ck_request_reviews_rating_range"),
    )

    id = Column(Integer, primary_key=True, index=True)

    request_id = Column(
        Integer,
        ForeignKey("service_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    reviewer_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    reviewee_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    reviewer_role = Column(String(20), nullable=False, index=True)  # CUSTOMER | WORKER

    rating = Column(Integer, nullable=False)
    comment = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    request = relationship("ServiceRequest", back_populates="reviews")
    reviewer = relationship("User", foreign_keys=[reviewer_user_id], back_populates="given_request_reviews")
    reviewee = relationship("User", foreign_keys=[reviewee_user_id], back_populates="received_request_reviews")

    def touch(self):
        self.updated_at = datetime.utcnow()
