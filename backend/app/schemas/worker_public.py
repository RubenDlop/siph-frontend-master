from __future__ import annotations

from typing import Optional, List, Literal
from pydantic import BaseModel, ConfigDict

WorkerBadgeLevel = Literal["BASIC", "TRUST", "PRO", "PAY"]
WorkerVerificationStatus = Literal["UNVERIFIED", "PENDING", "IN_REVIEW", "VERIFIED", "REJECTED"]


class WorkerPublicDocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    doc_type: str
    label: str
    original_name: Optional[str] = None
    content_type: Optional[str] = None
    has_file: bool = False
    file_url: Optional[str] = None


class WorkerPublicOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    public_name: str
    photo_url: Optional[str] = None
    city: Optional[str] = None
    specialty: Optional[str] = None
    years_experience: Optional[int] = None
    bio: Optional[str] = None

    categories: List[str] = []
    badge_level: WorkerBadgeLevel = "BASIC"
    verification_status: WorkerVerificationStatus = "UNVERIFIED"
    is_verified: bool = False

    visible_documents: List[WorkerPublicDocumentOut] = []

    average_rating: Optional[float] = None
    reviews_count: int = 0
