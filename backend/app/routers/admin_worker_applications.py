from __future__ import annotations

from typing import Any, List, Optional

from boto3.dynamodb.conditions import Attr, Key
from fastapi import APIRouter, Depends, HTTPException, Query

from ..core.deps import require_roles
from ..core.dynamo import from_dynamo, now_iso, table, to_dynamo
from ..repositories.users_repo import get_user_by_id
from ..schemas.worker_application import (
    AdminWorkerApplicationOut,
    WorkerApplicationDecision,
)

router = APIRouter(prefix="/admin/worker-applications", tags=["admin-worker-applications"])

apps_table = table("worker_applications")
users_table = table("users")


def _get_attr(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


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


def _serialize_app(app: dict) -> dict:
    user = get_user_by_id(int(app["user_id"])) if app.get("user_id") is not None else None

    return {
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
        "user": _serialize_user(user),
    }


def _get_app(app_id: int) -> Optional[dict]:
    res = apps_table.get_item(Key={"id": int(app_id)})
    item = res.get("Item")
    return from_dynamo(item) if item else None


def _put_app(app: dict) -> None:
    apps_table.put_item(Item=to_dynamo(app))


def _normalize_decision(payload: WorkerApplicationDecision) -> str:
    if hasattr(payload, "normalized_status"):
        return str(payload.normalized_status()).upper().strip()

    status_value = _get_attr(payload, "status")
    if status_value:
        return str(status_value).upper().strip()

    decision_value = _get_attr(payload, "decision")
    if decision_value:
        dec = str(decision_value).upper().strip()
        if dec == "APPROVE":
            return "APPROVED"
        if dec == "REJECT":
            return "REJECTED"

    raise HTTPException(
        status_code=400,
        detail="Debes enviar status=APPROVED/REJECTED o decision=APPROVE/REJECT.",
    )


@router.get("", response_model=List[AdminWorkerApplicationOut])
def list_apps(
    status_filter: Optional[str] = Query(default=None, description="PENDING|APPROVED|REJECTED"),
    _: Any = Depends(require_roles("ADMIN")),
):
    items: list[dict] = []

    if status_filter:
        st = status_filter.upper().strip()
        if st not in ("PENDING", "APPROVED", "REJECTED"):
            raise HTTPException(status_code=400, detail="status_filter inválido")

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

    return [_serialize_app(item) for item in items]


@router.patch("/{app_id}", response_model=AdminWorkerApplicationOut)
def decide_app(
    app_id: int,
    payload: WorkerApplicationDecision,
    admin: Any = Depends(require_roles("ADMIN")),
):
    app = _get_app(app_id)
    if not app:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada.")

    new_status = _normalize_decision(payload)
    admin_notes = _get_attr(payload, "admin_notes")

    if new_status not in ("APPROVED", "REJECTED"):
        raise HTTPException(
            status_code=400,
            detail="decision inválida (APPROVE|REJECT) o status inválido (APPROVED|REJECTED).",
        )

    app["status"] = new_status
    app["admin_notes"] = admin_notes
    app["reviewed_by"] = int(getattr(admin, "id"))
    app["reviewed_at"] = now_iso()
    app["updated_at"] = now_iso()

    _put_app(app)

    # ✅ PROMOVER A WORKER si fue aprobada
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
    return _serialize_app(updated)
