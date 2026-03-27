from sqlalchemy import Column, Integer, String, DateTime, func, Boolean
from sqlalchemy.orm import relationship

from ..core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String(80), nullable=False)
    last_name = Column(String(80), nullable=False)
    email = Column(String(120), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)

    azure_oid = Column(String(100), unique=True, index=True, nullable=True)
    azure_tid = Column(String(100), index=True, nullable=True)
    auth_provider = Column(String(30), nullable=False, default="LOCAL")

    role = Column(String(30), nullable=False, default="USER")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    requests = relationship(
        "ServiceRequest",
        foreign_keys="ServiceRequest.user_id",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    assigned_requests = relationship(
        "ServiceRequest",
        foreign_keys="ServiceRequest.assigned_worker_id",
        back_populates="assigned_worker",
    )

    sent_request_messages = relationship(
        "RequestMessage",
        foreign_keys="RequestMessage.sender_user_id",
        back_populates="sender",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    given_request_reviews = relationship(
        "RequestReview",
        foreign_keys="RequestReview.reviewer_user_id",
        back_populates="reviewer",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    received_request_reviews = relationship(
        "RequestReview",
        foreign_keys="RequestReview.reviewee_user_id",
        back_populates="reviewee",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
