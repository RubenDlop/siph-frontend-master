from __future__ import annotations

from typing import Any, Optional

from boto3.dynamodb.conditions import Key
from fastapi import APIRouter, Depends, HTTPException, status

from ..core.deps import get_current_user
from ..core.dynamo import from_dynamo, next_id, now_iso, table, to_dynamo
from ..repositories.users_repo import get_user_by_id
from ..schemas.review import (
    RequestReviewCreate,
    RequestReviewOut,
    RequestReviewSummaryOut,
)

router = APIRouter(prefix="/reviews", tags=["reviews"])

reviews_table = table("request_reviews")
requests_table = table("service_requests")
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


def _serialize_review(row: dict) -> dict:
    reviewer = (
        get_user_by_id(int(row["reviewer_user_id"]))
        if row.get("reviewer_user_id") is not None
        else None
    )
    reviewee = (
        get_user_by_id(int(row["reviewee_user_id"]))
        if row.get("reviewee_user_id") is not None
        else None
    )

    return {
        "id": row.get("id"),
        "request_id": row.get("request_id"),
        "reviewer_user_id": row.get("reviewer_user_id"),
        "reviewee_user_id": row.get("reviewee_user_id"),
        "reviewer_role": row.get("reviewer_role"),
        "rating": row.get("rating"),
        "comment": row.get("comment"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "reviewer": _serialize_user(reviewer),
        "reviewee": _serialize_user(reviewee),
    }


def _emit_event(
    *,
    req: dict,
    actor: Optional[Any],
    event_type: str,
    title: str,
    message: Optional[str] = None,
    meta: Optional[dict] = None,
) -> None:
    evt = {
        "request_id": int(req["id"]),
        "id": next_id("request_events"),
        "actor_user_id": int(getattr(actor, "id")) if actor else None,
        "event_type": event_type,
        "title": title,
        "message": message,
        "status_from": None,
        "status_to": None,
        "meta": meta or {},
        "created_at": now_iso(),
    }
    events_table.put_item(Item=to_dynamo(evt))


def _load_request(request_id: int) -> dict:
    res = requests_table.get_item(Key={"id": int(request_id)})
    item = res.get("Item")
    req = from_dynamo(item) if item else None

    if not req:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada.")

    return req


def _ensure_participant(req: dict, user: Any) -> str:
    role = str(getattr(user, "role", "USER") or "USER").upper()

    if role == "ADMIN":
        return "ADMIN"

    if req.get("user_id") == getattr(user, "id", None):
        return "CUSTOMER"

    if req.get("assigned_worker_id") == getattr(user, "id", None):
        return "WORKER"

    raise HTTPException(status_code=403, detail="No tienes acceso a esta reseña.")


def _get_reviews_for_request(request_id: int) -> list[dict]:
    res = reviews_table.query(
        KeyConditionExpression=Key("request_id").eq(int(request_id)),
        ScanIndexForward=True,
    )
    rows = [from_dynamo(item) for item in res.get("Items", [])]

    rows.sort(
        key=lambda r: (
            str(r.get("created_at") or ""),
            int(r.get("reviewer_user_id") or 0),
        )
    )
    return rows


def _put_request(req: dict) -> None:
    requests_table.put_item(Item=to_dynamo(req))


def _status_str(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "value"):
        return str(value.value)
    return str(value)


@router.get("/request/{request_id}/summary", response_model=RequestReviewSummaryOut)
def get_request_review_summary(
    request_id: int,
    current_user: Any = Depends(get_current_user),
):
    req = _load_request(request_id)
    actor_kind = _ensure_participant(req, current_user)

    rows = _get_reviews_for_request(request_id)

    customer_review = next(
        (r for r in rows if r.get("reviewer_role") == "CUSTOMER"),
        None,
    )
    worker_review = next(
        (r for r in rows if r.get("reviewer_role") == "WORKER"),
        None,
    )
    my_review = next(
        (r for r in rows if r.get("reviewer_user_id") == getattr(current_user, "id", None)),
        None,
    )

    req_status = _status_str(req.get("status"))

    return {
        "request_id": int(req["id"]),
        "status": req_status,
        "customer_review_done": customer_review is not None,
        "worker_review_done": worker_review is not None,
        "can_review_as_customer": (
            actor_kind == "CUSTOMER"
            and req_status == "DONE"
            and req.get("assigned_worker_id") is not None
        ),
        "can_review_as_worker": (
            actor_kind == "WORKER"
            and req_status == "DONE"
        ),
        "my_review": _serialize_review(my_review) if my_review else None,
        "customer_review": _serialize_review(customer_review) if customer_review else None,
        "worker_review": _serialize_review(worker_review) if worker_review else None,
    }


@router.post("/request/{request_id}", response_model=RequestReviewOut)
def create_or_update_request_review(
    request_id: int,
    payload: RequestReviewCreate,
    current_user: Any = Depends(get_current_user),
):
    req = _load_request(request_id)
    actor_kind = _ensure_participant(req, current_user)

    if actor_kind == "ADMIN":
        raise HTTPException(
            status_code=403,
            detail="El administrador no puede calificar en nombre de las partes.",
        )

    req_status = _status_str(req.get("status"))
    if req_status != "DONE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se puede calificar cuando la solicitud esté finalizada.",
        )

    if actor_kind == "CUSTOMER":
        if not req.get("assigned_worker_id"):
            raise HTTPException(
                status_code=400,
                detail="No hay trabajador asignado para calificar.",
            )
        reviewer_role = "CUSTOMER"
        reviewee_user_id = int(req["assigned_worker_id"])
        event_type = "CUSTOMER_LEFT_REVIEW"
        title = "Cliente calificó al técnico"
        message = f"El cliente dejó una calificación de {payload.rating}/5 para el técnico."
    else:
        reviewer_role = "WORKER"
        reviewee_user_id = int(req["user_id"])
        event_type = "WORKER_LEFT_REVIEW"
        title = "Técnico calificó al cliente"
        message = f"El técnico dejó una calificación de {payload.rating}/5 para el cliente."

    reviewer_user_id = int(getattr(current_user, "id"))

    existing_res = reviews_table.get_item(
        Key={
            "request_id": int(req["id"]),
            "reviewer_user_id": reviewer_user_id,
        }
    )
    existing_item = existing_res.get("Item")
    row = from_dynamo(existing_item) if existing_item else None

    now = now_iso()

    if row:
        row["rating"] = payload.rating
        row["comment"] = payload.comment
        row["updated_at"] = now
    else:
        row = {
            "request_id": int(req["id"]),
            "reviewer_user_id": reviewer_user_id,
            "id": next_id("request_reviews"),
            "reviewee_user_id": reviewee_user_id,
            "reviewer_role": reviewer_role,
            "rating": payload.rating,
            "comment": payload.comment,
            "created_at": now,
            "updated_at": now,
        }

    reviews_table.put_item(Item=to_dynamo(row))

    req["updated_at"] = now
    _put_request(req)

    _emit_event(
        req=req,
        actor=current_user,
        event_type=event_type,
        title=title,
        message=message,
        meta={
            "rating": payload.rating,
            "reviewer_role": reviewer_role,
            "reviewee_user_id": reviewee_user_id,
        },
    )

    return _serialize_review(row)


@router.get("/worker/{worker_id}/public")
def public_worker_reviews(worker_id: int):
    res = reviews_table.query(
        IndexName="reviewee_user_id-created_at-index",
        KeyConditionExpression=Key("reviewee_user_id").eq(int(worker_id)),
        ScanIndexForward=False,
    )
    rows = [from_dynamo(item) for item in res.get("Items", [])]

    rows = [r for r in rows if r.get("reviewer_role") == "CUSTOMER"]

    count = len(rows)
    avg = round(sum(int(r.get("rating", 0)) for r in rows) / count, 2) if count else None

    return {
        "worker_id": worker_id,
        "average_rating": avg,
        "reviews_count": count,
        "items": [
            {
                "id": r.get("id"),
                "rating": r.get("rating"),
                "comment": r.get("comment"),
                "created_at": r.get("created_at"),
                "reviewer": _serialize_user(
                    get_user_by_id(int(r["reviewer_user_id"]))
                    if r.get("reviewer_user_id") is not None
                    else None
                ),
            }
            for r in rows
        ],
    }
