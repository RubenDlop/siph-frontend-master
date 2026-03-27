from __future__ import annotations

from typing import Any, Optional, List

from boto3.dynamodb.conditions import Key
from fastapi import APIRouter, Depends, HTTPException, status

from ..core.deps import get_current_user, require_roles
from ..core.dynamo import from_dynamo, next_id, now_iso, table, to_dynamo
from ..repositories.users_repo import get_user_by_id
from ..schemas.worker_application import (
    WorkerApplicationCreate,
    WorkerApplicationOut,
    WorkerApplicationAdminOut,
    WorkerApplicationDecision,
)

router = APIRouter(prefix="/worker-applications", tags=["worker-applications"])
admin_router = APIRouter(prefix="/admin/worker-applications", tags=["admin-worker-applications"])

apps_table = table("worker_applications")
users_table = table("users")


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


def _serialize_app(app: dict, include_user: bool = False) -> dict:
    out = {
        "id": app.get("id"),
        "user_id": app.get("user_id"),
        "phone": app.get("phone"),
        "city": app.get("city"),
        "specialty": app.get("specialty"),
        "bio": app.get("bio"),
        "years_experience": app.get("years_experience"),
        "status": app.get("status"),
        "admin_notes": app.get("admin_notes"),
        "reviewed_by": app.get("reviewed_by"),
        "reviewed_at": app.get("reviewed_at"),
        "created_at": app.get("created_at"),
        "updated_at": app.get("updated_at"),
    }

    if include_user:
        user = get_user_by_id(int(app["user_id"])) if app.get("user_id") is not None else None
        out["user"] = _serialize_user(user)

    return out


def _get_app(app_id: int) -> Optional[dict]:
    res = apps_table.get_item(Key={"id": int(app_id)})
    item = res.get("Item")
    return from_dynamo(item) if item else None


def _put_app(app: dict) -> None:
    apps_table.put_item(Item=to_dynamo(app))


def _latest_app_for_user(user_id: int) -> Optional[dict]:
    res = apps_table.query(
        IndexName="user_id-created_at-index",
        KeyConditionExpression=Key("user_id").eq(int(user_id)),
        ScanIndexForward=False,
        Limit=1,
    )
    items = [from_dynamo(item) for item in res.get("Items", [])]
    return items[0] if items else None


def _normalize_status_from_decision(payload: WorkerApplicationDecision) -> str:
    if hasattr(payload, "normalized_status"):
        value = payload.normalized_status()
        return str(value).upper().strip()

    if getattr(payload, "status", None):
        return str(payload.status).upper().strip()

    if getattr(payload, "decision", None):
        dec = str(payload.decision).upper().strip()
        if dec == "APPROVE":
            return "APPROVED"
        if dec == "REJECT":
            return "REJECTED"

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Estado inválido. Usa APPROVED/REJECTED (o decision APPROVE/REJECT).",
    )


@router.post("", response_model=WorkerApplicationOut, status_code=status.HTTP_201_CREATED)
def apply_as_worker(
    payload: WorkerApplicationCreate,
    current_user: Any = Depends(get_current_user),
):
    current_role = str(getattr(current_user, "role", "USER") or "USER").upper()
    if current_role != "USER":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo usuarios con rol USER pueden postularse.",
        )

    now = now_iso()
    app = {
        "id": next_id("worker_applications"),
        "user_id": int(getattr(current_user, "id")),
        "phone": payload.phone,
        "city": payload.city,
        "specialty": payload.specialty,
        "bio": payload.bio,
        "years_experience": payload.years_experience,
        "status": "PENDING",
        "admin_notes": None,
        "reviewed_by": None,
        "reviewed_at": None,
        "created_at": now,
        "updated_at": now,
    }

    _put_app(app)
    return _serialize_app(app)


@router.get("/me", response_model=WorkerApplicationOut)
def my_application(
    current_user: Any = Depends(get_current_user),
):
    app = _latest_app_for_user(int(getattr(current_user, "id")))
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No tienes solicitudes.",
        )
    return _serialize_app(app)


@admin_router.get("", response_model=List[WorkerApplicationAdminOut])
def admin_list_applications(
    status_filter: Optional[str] = None,
    _: Any = Depends(require_roles("ADMIN")),
):
    items: list[dict] = []

    if status_filter:
        st = status_filter.upper().strip()
        if st not in ("PENDING", "APPROVED", "REJECTED"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="status_filter inválido. Usa PENDING, APPROVED o REJECTED.",
            )

        res = apps_table.query(
            IndexName="status-created_at-index",
            KeyConditionExpression=Key("status").eq(st),
            ScanIndexForward=False,
        )
        items = [from_dynamo(item) for item in res.get("Items", [])]
    else:
        scan_kwargs: dict[str, Any] = {}
        while True:
            res = apps_table.scan(**scan_kwargs)
            items.extend(from_dynamo(item) for item in res.get("Items", []))

            last_key = res.get("LastEvaluatedKey")
            if not last_key:
                break
            scan_kwargs["ExclusiveStartKey"] = last_key

        items.sort(key=lambda x: str(x.get("created_at") or ""), reverse=True)

    return [_serialize_app(item, include_user=True) for item in items]


@admin_router.patch("/{app_id}", response_model=WorkerApplicationAdminOut)
def admin_decide_application(
    app_id: int,
    decision: WorkerApplicationDecision,
    current_admin: Any = Depends(require_roles("ADMIN")),
):
    app = _get_app(app_id)
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Solicitud no encontrada.",
        )

    new_status = _normalize_status_from_decision(decision)
    if new_status not in ("APPROVED", "REJECTED"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Estado inválido. Usa APPROVED/REJECTED (o decision APPROVE/REJECT).",
        )

    app["status"] = new_status
    app["admin_notes"] = getattr(decision, "admin_notes", None)
    app["reviewed_by"] = int(getattr(current_admin, "id"))
    app["reviewed_at"] = now_iso()
    app["updated_at"] = now_iso()

    _put_app(app)

    if new_status == "APPROVED":
        user = get_user_by_id(int(app["user_id"])) if app.get("user_id") is not None else None
        if user and str(user.get("role") or "").upper() != "ADMIN":
            users_table.update_item(
                Key={"email": user["email"]},
                UpdateExpression="SET #role = :role",
                ExpressionAttributeNames={"#role": "role"},
                ExpressionAttributeValues={":role": "WORKER"},
            )

    updated = _get_app(app_id) or app
    return _serialize_app(updated, include_user=True)
