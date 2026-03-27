from __future__ import annotations

from datetime import date, datetime
from typing import Optional, Literal, Any

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


class RequestUserLite(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str
    email: str
    role: str
    is_active: bool


class ServiceRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    assigned_worker_id: Optional[int] = None

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

    assigned_at: Optional[datetime] = None
    accepted_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    customer: Optional[RequestUserLite] = None
    assigned_worker: Optional[RequestUserLite] = None

    client_name: Optional[str] = None
    client_email: Optional[str] = None
    assigned_worker_name: Optional[str] = None
    assigned_worker_email: Optional[str] = None


class ServiceRequestListItem(ServiceRequestOut):
    pass


class RequestMessageCreate(BaseModel):
    body: str = Field(..., min_length=1, max_length=2000)

    @field_validator("body", mode="before")
    @classmethod
    def strip_body(cls, v):
        if v is None:
            return ""
        return str(v).strip()


class RequestMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    request_id: int
    sender_user_id: int
    body: str
    created_at: datetime
    read_at: Optional[datetime] = None

    sender: Optional[RequestUserLite] = None
    is_mine: bool = False


class RequestEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    request_id: int
    actor_user_id: Optional[int] = None
    event_type: str
    title: str
    message: Optional[str] = None
    status_from: Optional[str] = None
    status_to: Optional[str] = None
    meta: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    actor: Optional[RequestUserLite] = None
