from __future__ import annotations

from typing import Any, Optional

from boto3.dynamodb.conditions import Key
from fastapi import APIRouter, Depends, HTTPException, status

from ..core.deps import get_current_user
from ..core.dynamo import from_dynamo, next_id, now_iso, table, to_dynamo
from ..repositories.users_repo import get_user_by_id
from ..schemas.request import (
    RequestEventOut,
    RequestMessageCreate,
    RequestMessageOut,
    ServiceRequestCreate,
    ServiceRequestListItem,
    ServiceRequestOut,
)

router = APIRouter(prefix="/requests", tags=["requests"])

requests_table = table("service_requests")
messages_table = table("request_messages")
events_table = table("request_events")


def _serialize_user(user: Optional[dict]) -> Optional[dict]:
    if not user:
        return None
    return {
        "id": user.get("id"),
        "first_name": user.get("first_name"),
        "last_name": user.get("last_name"),
        "email": user.get("email"),
        "role": user.get("role"),
        "is_active": user.get("is_active", True),
    }


def _full_name(user: Optional[dict]) -> Optional[str]:
    if not user:
        return None
    return f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() or None


def _status_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    if hasattr(value, "value"):
        return value.value
    return str(value)


def _get_request(request_id: int) -> Optional[dict]:
    res = requests_table.get_item(Key={"id": request_id})
    item = res.get("Item")
    return from_dynamo(item) if item else None


def _put_request(req: dict) -> None:
    requests_table.put_item(Item=to_dynamo(req))


def _attach_request_relations(req: dict) -> dict:
    customer = get_user_by_id(int(req["user_id"])) if req.get("user_id") is not None else None
    assigned_worker = (
        get_user_by_id(int(req["assigned_worker_id"]))
        if req.get("assigned_worker_id") is not None
        else None
    )

    return {
        **req,
        "customer": _serialize_user(customer),
        "assigned_worker": _serialize_user(assigned_worker),
        "client_name": _full_name(customer),
        "client_email": customer.get("email") if customer else None,
        "assigned_worker_name": _full_name(assigned_worker),
        "assigned_worker_email": assigned_worker.get("email") if assigned_worker else None,
    }


def _can_access_request(req: dict, user: Any) -> bool:
    role = str(getattr(user, "role", "USER") or "USER").upper()
    if role == "ADMIN":
        return True
    return req.get("user_id") == getattr(user, "id", None) or req.get("assigned_worker_id") == getattr(user, "id", None)


def _emit_event(
    *,
    req: dict,
    actor: Optional[Any],
    event_type: str,
    title: str,
    message: Optional[str] = None,
    status_from: Optional[str] = None,
    status_to: Optional[str] = None,
    meta: Optional[dict] = None,
) -> dict:
    event = {
        "request_id": int(req["id"]),
        "id": next_id("request_events"),
        "actor_user_id": getattr(actor, "id", None) if actor else None,
        "event_type": event_type,
        "title": title,
        "message": message,
        "status_from": status_from,
        "status_to": status_to,
        "meta": meta or {},
        "created_at": now_iso(),
    }
    events_table.put_item(Item=to_dynamo(event))
    return event


def _serialize_request(req: dict) -> dict:
    req = _attach_request_relations(req)
    return {
        "id": req.get("id"),
        "user_id": req.get("user_id"),
        "assigned_worker_id": req.get("assigned_worker_id"),
        "category": req.get("category"),
        "title": req.get("title"),
        "description": req.get("description"),
        "urgency": _status_str(req.get("urgency")),
        "city": req.get("city"),
        "neighborhood": req.get("neighborhood"),
        "address": req.get("address"),
        "address_ref": req.get("address_ref"),
        "lat": req.get("lat"),
        "lng": req.get("lng"),
        "accuracy_m": req.get("accuracy_m"),
        "schedule_date": req.get("schedule_date"),
        "time_window": req.get("time_window"),
        "budget_min": req.get("budget_min"),
        "budget_max": req.get("budget_max"),
        "contact_name": req.get("contact_name"),
        "contact_phone": req.get("contact_phone"),
        "contact_pref": _status_str(req.get("contact_pref")),
        "status": _status_str(req.get("status")),
        "assigned_at": req.get("assigned_at"),
        "accepted_at": req.get("accepted_at"),
        "started_at": req.get("started_at"),
        "completed_at": req.get("completed_at"),
        "created_at": req.get("created_at"),
        "updated_at": req.get("updated_at"),
        "customer": req.get("customer"),
        "assigned_worker": req.get("assigned_worker"),
        "client_name": req.get("client_name"),
        "client_email": req.get("client_email"),
        "assigned_worker_name": req.get("assigned_worker_name"),
        "assigned_worker_email": req.get("assigned_worker_email"),
    }


def _serialize_message(msg: dict, current_user_id: int) -> dict:
    sender = get_user_by_id(int(msg["sender_user_id"])) if msg.get("sender_user_id") is not None else None
    return {
        "id": msg.get("id"),
        "request_id": msg.get("request_id"),
        "sender_user_id": msg.get("sender_user_id"),
        "body": msg.get("body"),
        "created_at": msg.get("created_at"),
        "read_at": msg.get("read_at"),
        "sender": _serialize_user(sender),
        "is_mine": msg.get("sender_user_id") == current_user_id,
    }


def _serialize_event(evt: dict) -> dict:
    actor = get_user_by_id(int(evt["actor_user_id"])) if evt.get("actor_user_id") is not None else None
    return {
        "id": evt.get("id"),
        "request_id": evt.get("request_id"),
        "actor_user_id": evt.get("actor_user_id"),
        "event_type": evt.get("event_type"),
        "title": evt.get("title"),
        "message": evt.get("message"),
        "status_from": evt.get("status_from"),
        "status_to": evt.get("status_to"),
        "meta": evt.get("meta") or {},
        "created_at": evt.get("created_at"),
        "actor": _serialize_user(actor),
    }


@router.post("", response_model=ServiceRequestOut, status_code=status.HTTP_201_CREATED)
def create_request(
    payload: ServiceRequestCreate,
    user: Any = Depends(get_current_user),
):
    now = now_iso()
    request_id = next_id("service_requests")

    req = {
        "id": request_id,
        "user_id": getattr(user, "id"),
        "assigned_worker_id": None,
        "category": (payload.category or "GENERAL").strip().upper(),
        "title": payload.title.strip(),
        "description": payload.description.strip(),
        "urgency": _status_str(payload.urgency),
        "city": payload.city,
        "neighborhood": payload.neighborhood,
        "address": payload.address,
        "address_ref": payload.address_ref,
        "lat": payload.lat,
        "lng": payload.lng,
        "accuracy_m": payload.accuracy_m,
        "schedule_date": payload.schedule_date.isoformat() if payload.schedule_date else None,
        "time_window": payload.time_window,
        "budget_min": payload.budget_min,
        "budget_max": payload.budget_max,
        "contact_name": payload.contact_name,
        "contact_phone": payload.contact_phone,
        "contact_pref": _status_str(payload.contact_pref),
        "status": "CREATED",
        "assigned_at": None,
        "accepted_at": None,
        "started_at": None,
        "completed_at": None,
        "created_at": now,
        "updated_at": now,
    }

    _put_request(req)

    _emit_event(
        req=req,
        actor=user,
        event_type="REQUEST_CREATED",
        title="Solicitud creada",
        message="Tu solicitud fue registrada correctamente y está lista para búsqueda de técnico.",
        status_to="CREATED",
    )

    return _serialize_request(req)


@router.get("/me", response_model=list[ServiceRequestListItem])
def my_requests(
    user: Any = Depends(get_current_user),
):
    res = requests_table.query(
        IndexName="user_id-updated_at-index",
        KeyConditionExpression=Key("user_id").eq(int(getattr(user, "id"))),
        ScanIndexForward=False,
    )
    rows = [from_dynamo(item) for item in res.get("Items", [])]
    return [_serialize_request(row) for row in rows]


@router.get("/{request_id}", response_model=ServiceRequestOut)
def get_request(
    request_id: int,
    user: Any = Depends(get_current_user),
):
    req = _get_request(request_id)
    if not req or not _can_access_request(req, user):
        raise HTTPException(status_code=404, detail="Solicitud no encontrada.")
    return _serialize_request(req)


@router.patch("/{request_id}/cancel", response_model=ServiceRequestOut)
def cancel_request(
    request_id: int,
    user: Any = Depends(get_current_user),
):
    req = _get_request(request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada.")

    role = str(getattr(user, "role", "USER") or "USER").upper()
    if req.get("user_id") != getattr(user, "id") and role != "ADMIN":
        raise HTTPException(status_code=403, detail="No puedes cancelar esta solicitud.")

    if req.get("status") in ("DONE", "CANCELED"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes cancelar una solicitud finalizada.",
        )

    if req.get("status") == "IN_PROGRESS":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes cancelar una solicitud en progreso. Primero coordina el cierre con el técnico.",
        )

    old_status = req.get("status")
    req["status"] = "CANCELED"
    req["updated_at"] = now_iso()
    _put_request(req)

    _emit_event(
        req=req,
        actor=user,
        event_type="REQUEST_CANCELED",
        title="Solicitud cancelada",
        message="La solicitud fue cancelada y ya no seguirá en el flujo.",
        status_from=old_status,
        status_to="CANCELED",
    )

    return _serialize_request(req)


@router.patch("/{request_id}/cancel-acceptance", response_model=ServiceRequestOut)
def cancel_acceptance(
    request_id: int,
    user: Any = Depends(get_current_user),
):
    req = _get_request(request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada.")

    role = str(getattr(user, "role", "USER") or "USER").upper()
    if req.get("user_id") != getattr(user, "id") and role != "ADMIN":
        raise HTTPException(status_code=403, detail="No puedes modificar esta solicitud.")

    if req.get("status") != "ASSIGNED" or not req.get("assigned_worker_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo puedes cancelar la aceptación cuando la solicitud esté asignada.",
        )

    if req.get("started_at") or req.get("status") == "IN_PROGRESS":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La aceptación ya no puede cancelarse porque el servicio ya fue iniciado.",
        )

    previous_worker = get_user_by_id(int(req["assigned_worker_id"])) if req.get("assigned_worker_id") else None
    previous_worker_name = _full_name(previous_worker)
    old_status = req.get("status")

    req["assigned_worker_id"] = None
    req["assigned_at"] = None
    req["accepted_at"] = None
    req["status"] = "MATCHING"
    req["updated_at"] = now_iso()
    _put_request(req)

    _emit_event(
        req=req,
        actor=user,
        event_type="CUSTOMER_CANCELED_ACCEPTANCE",
        title="Aceptación cancelada",
        message=(
            f"Se retiró la asignación"
            f"{f' de {previous_worker_name}' if previous_worker_name else ''}"
            f" y la solicitud volvió a búsqueda."
        ),
        status_from=old_status,
        status_to="MATCHING",
    )

    return _serialize_request(req)


@router.get("/{request_id}/events", response_model=list[RequestEventOut])
def get_request_events(
    request_id: int,
    current_user: Any = Depends(get_current_user),
):
    req = _get_request(request_id)
    if not req or not _can_access_request(req, current_user):
        raise HTTPException(status_code=404, detail="Solicitud no encontrada.")

    res = events_table.query(
        KeyConditionExpression=Key("request_id").eq(request_id),
        ScanIndexForward=False,
    )
    rows = [from_dynamo(item) for item in res.get("Items", [])]
    return [_serialize_event(row) for row in rows]


@router.get("/{request_id}/messages", response_model=list[RequestMessageOut])
def get_request_messages(
    request_id: int,
    current_user: Any = Depends(get_current_user),
):
    req = _get_request(request_id)
    if not req or not _can_access_request(req, current_user):
        raise HTTPException(status_code=404, detail="Solicitud no encontrada.")

    res = messages_table.query(
        KeyConditionExpression=Key("request_id").eq(request_id),
        ScanIndexForward=True,
    )
    rows = [from_dynamo(item) for item in res.get("Items", [])]
    return [_serialize_message(row, int(getattr(current_user, "id"))) for row in rows]


@router.post("/{request_id}/messages", response_model=RequestMessageOut, status_code=status.HTTP_201_CREATED)
def send_request_message(
    request_id: int,
    payload: RequestMessageCreate,
    current_user: Any = Depends(get_current_user),
):
    req = _get_request(request_id)
    if not req or not _can_access_request(req, current_user):
        raise HTTPException(status_code=404, detail="Solicitud no encontrada.")

    msg = {
        "request_id": request_id,
        "id": next_id("request_messages"),
        "sender_user_id": int(getattr(current_user, "id")),
        "body": payload.body.strip(),
        "created_at": now_iso(),
        "read_at": None,
    }
    messages_table.put_item(Item=to_dynamo(msg))

    req["updated_at"] = now_iso()
    _put_request(req)

    return _serialize_message(msg, int(getattr(current_user, "id")))
