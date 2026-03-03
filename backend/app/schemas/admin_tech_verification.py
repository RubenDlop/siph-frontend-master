from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Literal

from pydantic import BaseModel, ConfigDict, Field

TechLevel = Literal["BASIC", "TRUST", "PRO", "PAY"]
TechStatus = Literal["PENDING", "IN_REVIEW", "VERIFIED", "REJECTED"]


class AdminCaseDocOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int

    # DB: doc_type -> API: docType
    docType: str = Field(alias="doc_type")

    # DB: received_at -> API: receivedAt
    receivedAt: Optional[datetime] = Field(default=None, alias="received_at")

    # DB: verified_result -> API: verifiedResult
    verifiedResult: Optional[str] = Field(default=None, alias="verified_result")

    # DB: verified_at -> API: verifiedAt
    verifiedAt: Optional[datetime] = Field(default=None, alias="verified_at")

    meta: Dict[str, Any] = Field(default_factory=dict)

    # DB: original_name -> API: originalName
    originalName: Optional[str] = Field(default=None, alias="original_name")

    # DB: mime_type -> API: contentType
    contentType: Optional[str] = Field(default=None, alias="mime_type")

    # ✅ CLAVE para que NO salga "Sin archivo"
    hasFile: bool


class AdminCaseDetailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    caseId: int
    techId: int
    status: TechStatus
    targetLevel: TechLevel
    createdAt: datetime

    tech: Dict[str, Any] = Field(default_factory=dict)
    documents: List[AdminCaseDocOut] = Field(default_factory=list)


class NoCaseOut(BaseModel):
    hasCase: bool = False
