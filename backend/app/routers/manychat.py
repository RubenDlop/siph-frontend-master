# backend/app/routers/manychat.py
from __future__ import annotations

import re
import secrets
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.database import get_db
from ..core.security import hash_password
from ..models import User
from ..models.service_request import (
    ServiceRequest,
    RequestStatus,
    RequestUrgency,
    ContactPref,
)

router = APIRouter(prefix="/integrations/manychat", tags=["manychat"])


# =========================================================
# Helpers
# =========================================================
def _now() -> datetime:
    return datetime.utcnow()


def _normalize_text(value: Optional[str]) -> str:
    return (value or "").strip()


def _normalize_phone(value: Optional[str]) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    raw = re.sub(r"[^\d+]", "", raw)

    if raw.startswith("00"):
        raw = "+" + raw[2:]

    if raw.startswith("+"):
        return raw

    # Si viene solo numérico, asumimos +57 por defecto
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return ""

    if digits.startswith("57"):
        return f"+{digits}"

    return f"+57{digits}"


def _split_full_name(full_name: Optional[str]) -> tuple[str, str]:
    text = _normalize_text(full_name)
    if not text:
        return "Usuario", "WhatsApp"

    parts = text.split()
    if len(parts) == 1:
        return parts[0], "WhatsApp"
    return parts[0], " ".join(parts[1:])


def _manychat_email_from_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    if not digits:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ManyChat requiere phone o email para identificar al usuario.",
        )
    return f"wa_{digits}@manychat.siph.local"


def _require_manychat_secret(
    x_manychat_secret: Optional[str] = Header(default=None),
) -> None:
    expected = (settings.manychat_shared_secret or "").strip()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Falta configurar MANYCHAT_SHARED_SECRET en el backend.",
        )

    if not x_manychat_secret or x_manychat_secret != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="ManyChat secret inválido.",
        )


def _ensure_manychat_user(
    db: Session,
    *,
    full_name: Optional[str],
    phone: Optional[str],
    email: Optional[str],
) -> User:
    normalized_phone = _normalize_phone(phone)
    normalized_email = (_normalize_text(email) or "").lower()

    user: Optional[User] = None

    if normalized_email:
        user = db.query(User).filter(User.email == normalized_email).first()

    if not user and normalized_phone:
        pseudo_email = _manychat_email_from_phone(normalized_phone)
        user = db.query(User).filter(User.email == pseudo_email).first()

    first_name, last_name = _split_full_name(full_name)

    if user:
        if first_name:
            user.first_name = first_name
        if last_name:
            user.last_name = last_name
        db.commit()
        db.refresh(user)
        return user

    if not normalized_email:
        normalized_email = _manychat_email_from_phone(normalized_phone)

    user = User(
        first_name=first_name,
        last_name=last_name,
        email=normalized_email,
        password_hash=hash_password(secrets.token_urlsafe(24)),
        auth_provider="MANYCHAT",
        role="USER",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _status_label(status_value: str) -> str:
    value = (status_value or "").upper().strip()
    mapping = {
        "CREATED": "Creada",
        "MATCHING": "Buscando técnico",
        "ASSIGNED": "Asignada",
        "IN_PROGRESS": "En proceso",
        "DONE": "Finalizada",
        "CANCELED": "Cancelada",
    }
    return mapping.get(value, value or "Sin estado")


def _to_request_urgency(value: Optional[str]) -> RequestUrgency:
    raw = (value or "NORMAL").strip().upper()
    try:
        return RequestUrgency(raw)
    except Exception:
        return RequestUrgency.NORMAL


# =========================================================
# Schemas
# =========================================================
class ManychatCreateRequestIn(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None

    category: str = Field(default="GENERAL")
    title: str
    description: str

    urgency: Optional[str] = "NORMAL"

    city: Optional[str] = None
    neighborhood: Optional[str] = None
    address: Optional[str] = None
    address_ref: Optional[str] = None

    lat: Optional[float] = None
    lng: Optional[float] = None
    accuracy_m: Optional[int] = None

    schedule_date: Optional[str] = None
    time_window: Optional[str] = None

    budget_min: Optional[int] = None
    budget_max: Optional[int] = None


class ManychatStatusRequestIn(BaseModel):
    request_id: Optional[int] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None


# =========================================================
# Endpoints
# =========================================================
@router.get("/health")
def manychat_health(_: None = Depends(_require_manychat_secret)):
    return {"ok": True, "service": "manychat-siph"}


@router.post("/requests/create")
def manychat_create_request(
    payload: ManychatCreateRequestIn,
    db: Session = Depends(get_db),
    _: None = Depends(_require_manychat_secret),
):
    normalized_phone = _normalize_phone(payload.phone)
    normalized_email = (payload.email or "").strip().lower() if payload.email else None

    if not normalized_phone and not normalized_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debes enviar phone o email desde ManyChat.",
        )

    user = _ensure_manychat_user(
        db,
        full_name=payload.full_name,
        phone=normalized_phone,
        email=normalized_email,
    )

    req = ServiceRequest(
        user_id=user.id,
        category=_normalize_text(payload.category or "GENERAL").upper() or "GENERAL",
        title=_normalize_text(payload.title),
        description=_normalize_text(payload.description),
        urgency=_to_request_urgency(payload.urgency),

        city=_normalize_text(payload.city) or None,
        neighborhood=_normalize_text(payload.neighborhood) or None,
        address=_normalize_text(payload.address) or None,
        address_ref=_normalize_text(payload.address_ref) or None,

        lat=payload.lat,
        lng=payload.lng,
        accuracy_m=payload.accuracy_m,

        schedule_date=payload.schedule_date,
        time_window=_normalize_text(payload.time_window) or None,

        budget_min=payload.budget_min,
        budget_max=payload.budget_max,

        contact_name=_normalize_text(payload.full_name) or f"{user.first_name} {user.last_name}".strip(),
        contact_phone=normalized_phone or None,
        contact_pref=ContactPref.WHATSAPP,
        status=RequestStatus.CREATED,
        created_at=_now(),
        updated_at=_now(),
    )

    db.add(req)
    db.commit()
    db.refresh(req)

    summary = (
        f"Solicitud #{req.id} creada. "
        f"Categoría: {req.category}. "
        f"Estado: {_status_label(req.status.value)}."
    )

    return {
        "ok": True,
        "request_id": req.id,
        "request_status": req.status.value,
        "request_status_label": _status_label(req.status.value),
        "request_title": req.title,
        "request_category": req.category,
        "request_summary": summary,
        "user_id": user.id,
    }


@router.post("/requests/status")
def manychat_request_status(
    payload: ManychatStatusRequestIn,
    db: Session = Depends(get_db),
    _: None = Depends(_require_manychat_secret),
):
    req: Optional[ServiceRequest] = None

    if payload.request_id:
        req = db.query(ServiceRequest).filter(ServiceRequest.id == payload.request_id).first()

    if not req and payload.phone:
        normalized_phone = _normalize_phone(payload.phone)
        req = (
            db.query(ServiceRequest)
            .filter(ServiceRequest.contact_phone == normalized_phone)
            .order_by(ServiceRequest.created_at.desc())
            .first()
        )

    if not req and payload.email:
        user = (
            db.query(User)
            .filter(User.email == payload.email.strip().lower())
            .first()
        )
        if user:
            req = (
                db.query(ServiceRequest)
                .filter(ServiceRequest.user_id == user.id)
                .order_by(ServiceRequest.created_at.desc())
                .first()
            )

    if not req:
        return {
            "ok": False,
            "found": False,
            "request_id": None,
            "request_status": None,
            "request_status_label": None,
            "request_summary": "No encontré solicitudes con los datos enviados.",
        }

    return {
        "ok": True,
        "found": True,
        "request_id": req.id,
        "request_status": req.status.value,
        "request_status_label": _status_label(req.status.value),
        "request_title": req.title,
        "request_category": req.category,
        "request_city": req.city,
        "request_neighborhood": req.neighborhood,
        "request_created_at": req.created_at.isoformat() if req.created_at else None,
        "request_updated_at": req.updated_at.isoformat() if req.updated_at else None,
        "request_summary": (
            f"Solicitud #{req.id}: {req.title}. "
            f"Estado actual: {_status_label(req.status.value)}."
        ),
    }
