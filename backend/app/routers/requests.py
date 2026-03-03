# backend/app/routers/requests.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.deps import get_current_user
from ..models.service_request import ServiceRequest, RequestStatus
from ..schemas.request import ServiceRequestCreate, ServiceRequestOut, ServiceRequestListItem

router = APIRouter(prefix="/requests", tags=["requests"])


@router.post("", response_model=ServiceRequestOut, status_code=status.HTTP_201_CREATED)
def create_request(
    payload: ServiceRequestCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    req = ServiceRequest(
        user_id=user.id,
        category=(payload.category or "GENERAL").strip().upper(),
        title=payload.title.strip(),
        description=payload.description.strip(),
        urgency=payload.urgency,

        city=payload.city,
        neighborhood=payload.neighborhood,
        address=payload.address,
        address_ref=payload.address_ref,

        lat=payload.lat,
        lng=payload.lng,
        accuracy_m=payload.accuracy_m,

        schedule_date=payload.schedule_date,
        time_window=payload.time_window,

        budget_min=payload.budget_min,
        budget_max=payload.budget_max,

        contact_name=payload.contact_name,
        contact_phone=payload.contact_phone,
        contact_pref=payload.contact_pref,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


@router.get("/me", response_model=list[ServiceRequestListItem])
def my_requests(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    rows = (
        db.query(ServiceRequest)
        .filter(ServiceRequest.user_id == user.id)
        .order_by(ServiceRequest.created_at.desc())
        .all()
    )
    return rows


@router.get("/{request_id}", response_model=ServiceRequestOut)
def get_request(
    request_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    req = (
        db.query(ServiceRequest)
        .filter(ServiceRequest.id == request_id, ServiceRequest.user_id == user.id)
        .first()
    )
    if not req:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada.")
    return req


@router.patch("/{request_id}/cancel", response_model=ServiceRequestOut)
def cancel_request(
    request_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    req = (
        db.query(ServiceRequest)
        .filter(ServiceRequest.id == request_id, ServiceRequest.user_id == user.id)
        .first()
    )
    if not req:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada.")

    if req.status in (RequestStatus.DONE, RequestStatus.CANCELED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes cancelar una solicitud finalizada.",
        )

    req.status = RequestStatus.CANCELED
    db.commit()
    db.refresh(req)
    return req
