from __future__ import annotations

from datetime import date, datetime
from typing import Optional, Literal

from pydantic import BaseModel, Field, ConfigDict, field_validator


class ServiceRequestCreate(BaseModel):
    category: str = Field(default="GENERAL", min_length=2, max_length=60)
    title: str = Field(..., min_length=3, max_length=120)
    description: str = Field(..., min_length=10)

    urgency: Literal["NORMAL", "URGENT"] = "NORMAL"

    city: Optional[str] = None
    neighborhood: Optional[str] = None
    address: Optional[str] = None
    address_ref: Optional[str] = None

    lat: Optional[float] = Field(default=None, ge=-90, le=90)
    lng: Optional[float] = Field(default=None, ge=-180, le=180)
    accuracy_m: Optional[int] = Field(default=None, ge=0)

    schedule_date: Optional[date] = None
    time_window: Optional[str] = None

    budget_min: Optional[int] = Field(default=None, ge=0)
    budget_max: Optional[int] = Field(default=None, ge=0)

    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_pref: Optional[Literal["WHATSAPP", "CALL", "CHAT"]] = None

    @field_validator("category", mode="before")
    @classmethod
    def normalize_category(cls, v):
        if v is None:
            return "GENERAL"
        s = str(v).strip()
        return s if s else "GENERAL"

    @field_validator(
        "title",
        "description",
        "city",
        "neighborhood",
        "address",
        "address_ref",
        "time_window",
        "contact_name",
        "contact_phone",
        mode="before",
    )
    @classmethod
    def strip_strings(cls, v):
        if v is None:
            return None
        return str(v).strip()


class ServiceRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int

    category: str
    title: str
    description: str

    urgency: str

    city: Optional[str] = None
    neighborhood: Optional[str] = None
    address: Optional[str] = None
    address_ref: Optional[str] = None

    lat: Optional[float] = None
    lng: Optional[float] = None
    accuracy_m: Optional[int] = None

    schedule_date: Optional[date] = None
    time_window: Optional[str] = None

    budget_min: Optional[int] = None
    budget_max: Optional[int] = None

    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_pref: Optional[str] = None

    status: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ✅ /requests/me devuelve TODO (no resumen)
class ServiceRequestListItem(ServiceRequestOut):
    pass
