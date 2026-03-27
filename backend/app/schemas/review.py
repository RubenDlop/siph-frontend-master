from __future__ import annotations

from datetime import datetime
from typing import Optional, Literal

from pydantic import BaseModel, Field, ConfigDict, field_validator


class ReviewUserLite(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str
    email: str
    role: str
    is_active: bool


class RequestReviewCreate(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = Field(default=None, max_length=1500)

    @field_validator("comment", mode="before")
    @classmethod
    def clean_comment(cls, v):
        if v is None:
            return None
        s = str(v).strip()
        return s or None


class RequestReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    request_id: int
    reviewer_user_id: int
    reviewee_user_id: int
    reviewer_role: Literal["CUSTOMER", "WORKER"]
    rating: int
    comment: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    reviewer: Optional[ReviewUserLite] = None
    reviewee: Optional[ReviewUserLite] = None


class RequestReviewSummaryOut(BaseModel):
    request_id: int
    status: str

    customer_review_done: bool = False
    worker_review_done: bool = False

    can_review_as_customer: bool = False
    can_review_as_worker: bool = False

    my_review: Optional[RequestReviewOut] = None
    customer_review: Optional[RequestReviewOut] = None
    worker_review: Optional[RequestReviewOut] = None
