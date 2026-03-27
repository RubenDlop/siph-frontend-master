from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional, List

from boto3.dynamodb.conditions import Attr, Key
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel

from ..core.deps import require_roles
from ..core.dynamo import from_dynamo, next_id, now_iso, table, to_dynamo

router = APIRouter(prefix="/admin/tech/verification", tags=["Admin Tech Verification"])

cases_table = table("verification_cases")
profiles_table = table("technician_profiles")
docs_table = table("verification_documents")
logs_table = table("verification_audit_logs")


def _now() -> datetime:
    return datetime.utcnow()


def _now_iso() -> str:
    return now_iso()


def _enum_value(value: Any) -> Any:
    if hasattr(value, "value"):
        return value.value
    return value


def _get_attr(obj: Any, *names: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        for name in names:
            if name in obj and obj[name] is not None:
                return obj[name]
        return default

    for name in names:
        value = getattr(obj, name, None)
        if value is not None:
            return value
    return default


def _log(case_id: int, actor_id: int, action: str, detail: dict):
    item = {
        "case_id": int(case_id),
        "id": next_id("verification_audit_logs"),
        "actor_id": int(actor_id),
        "action": action,
        "detail": detail or {},
        "created_at": _now_iso(),
    }
    logs_table.put_item(Item=to_dynamo(item))


class ReviewDocPayload(BaseModel):
    result: str  # "ok" | "fail" | "unknown"
    notes: Optional[str] = None


# =========================
# helpers para ubicar archivos
# =========================
def _base_dir() -> Path:
    # backend/app/routers/... -> backend/
    return Path(__file__).resolve().parents[2]


def _uploads_roots() -> List[Path]:
    base = _base_dir()
    return [
        base / "uploads" / "tech_verification",
        base / "uploads",
        base,
    ]


def _normalize_storage_ref(sr: str) -> str:
    sr = (sr or "").strip()
    if not sr:
        return ""

    # encrypted://private/case-1/xxx.png -> private/case-1/xxx.png
    if sr.startswith("encrypted://"):
        return sr.replace("encrypted://", "", 1).lstrip("/")

    # file://abs/path -> se mantiene como absoluto
    if sr.startswith("file://"):
        return sr

    return sr.lstrip("/")


def _resolve_doc_path(d: dict) -> Optional[Path]:
    """
    Devuelve el primer Path existente en disco, o None.
    Soporta:
    - file_path
    - storage_ref:
        - file://ABS_PATH
        - encrypted://private/...
        - rutas relativas tipo private/case-1/...
        - uploads/...
    - url / file_url
    """
    # 0) file_path / url / file_url
    for field_name in ("file_path", "url", "file_url"):
        fp = _get_attr(d, field_name, default=None)
        if isinstance(fp, str) and fp.strip():
            rel = fp.strip()

            if rel.startswith("http://") or rel.startswith("https://"):
                return None

            if rel.startswith("file://"):
                abs_p = Path(rel.replace("file://", "", 1))
                if abs_p.exists():
                    return abs_p.resolve()
                return None

            p0 = Path(rel)
            if p0.is_absolute():
                if p0.exists():
                    return p0.resolve()
                return None

            rel = rel.lstrip("/")
            for root in _uploads_roots():
                cand = (root / rel).resolve()
                if cand.exists():
                    return cand

    # 1) storage_ref
    sr0 = _get_attr(d, "storage_ref", default=None)
    if isinstance(sr0, str) and sr0.strip():
        if sr0.startswith("http://") or sr0.startswith("https://"):
            return None

        if sr0.startswith("file://"):
            abs_p = Path(sr0.replace("file://", "", 1))
            if abs_p.exists():
                return abs_p.resolve()
            return None

        rel = _normalize_storage_ref(sr0)
        if rel:
            for root in _uploads_roots():
                cand = (root / rel).resolve()
                if cand.exists():
                    return cand

    return None


def _doc_has_file(d: dict) -> bool:
    sr = _get_attr(d, "storage_ref", "url", "file_url", default=None)
    if isinstance(sr, str) and (sr.startswith("http://") or sr.startswith("https://")):
        return True
    return _resolve_doc_path(d) is not None


# =========================
# helpers DynamoDB
# =========================
def _get_case(case_id: int) -> Optional[dict]:
    res = cases_table.get_item(Key={"id": int(case_id)})
    item = res.get("Item")
    return from_dynamo(item) if item else None


def _get_doc(case_id: int, doc_id: int) -> Optional[dict]:
    res = docs_table.get_item(Key={"case_id": int(case_id), "id": int(doc_id)})
    item = res.get("Item")
    return from_dynamo(item) if item else None


def _get_profile_by_user_id(user_id: Optional[int]) -> Optional[dict]:
    if user_id is None:
        return None
    res = profiles_table.get_item(Key={"user_id": int(user_id)})
    item = res.get("Item")
    return from_dynamo(item) if item else None


def _get_profile_by_tech_id(tech_id: Optional[int]) -> Optional[dict]:
    if tech_id is None:
        return None

    scan_kwargs = {
        "FilterExpression": Attr("id").eq(int(tech_id)),
        "Limit": 1,
    }
    res = profiles_table.scan(**scan_kwargs)
    items = [from_dynamo(item) for item in res.get("Items", [])]
    return items[0] if items else None


def _resolve_profile_for_case(case: dict) -> Optional[dict]:
    profile = _get_profile_by_user_id(_get_attr(case, "user_id", default=None))
    if profile:
        return profile

    profile = _get_profile_by_tech_id(_get_attr(case, "tech_id", default=None))
    if profile:
        return profile

    return None


def _query_latest_case_by_user_id(user_id: int) -> Optional[dict]:
    try:
        res = cases_table.query(
            IndexName="user_id-created_at-index",
            KeyConditionExpression=Key("user_id").eq(int(user_id)),
            ScanIndexForward=False,
            Limit=1,
        )
        items = [from_dynamo(item) for item in res.get("Items", [])]
        return items[0] if items else None
    except Exception:
        return None


def _query_latest_case_by_tech_id(tech_id: int) -> Optional[dict]:
    try:
        res = cases_table.query(
            IndexName="tech_id-created_at-index",
            KeyConditionExpression=Key("tech_id").eq(int(tech_id)),
            ScanIndexForward=False,
            Limit=1,
        )
        items = [from_dynamo(item) for item in res.get("Items", [])]
        return items[0] if items else None
    except Exception:
        return None


def _get_docs_for_case(case_id: int) -> list[dict]:
    res = docs_table.query(
        KeyConditionExpression=Key("case_id").eq(int(case_id)),
        ScanIndexForward=True,
    )
    items = [from_dynamo(item) for item in res.get("Items", [])]

    def sort_key(d: dict):
        return (
            _get_attr(d, "received_at", default="") or "",
            int(_get_attr(d, "id", default=0) or 0),
        )

    items.sort(key=sort_key)
    return items


def _serialize_case_summary(case: dict, tech: Optional[dict]) -> dict:
    return {
        "caseId": int(_get_attr(case, "id", default=0) or 0),
        "techId": _get_attr(case, "tech_id", default=None),
        "publicName": _get_attr(tech, "public_name", default="—") if tech else "—",
        "targetLevel": _enum_value(_get_attr(case, "target_level")),
        "status": _enum_value(_get_attr(case, "status")),
        "createdAt": _get_attr(case, "created_at"),
    }


def _serialize_case_detail(case: dict, tech: Optional[dict], docs: list[dict]) -> dict:
    return {
        "hasCase": True,
        "caseId": int(_get_attr(case, "id", default=0) or 0),
        "techId": _get_attr(case, "tech_id", default=None),
        "status": _enum_value(_get_attr(case, "status")),
        "targetLevel": _enum_value(_get_attr(case, "target_level")),
        "createdAt": _get_attr(case, "created_at"),
        "updatedAt": _get_attr(case, "updated_at", default=None),
        "reason": _get_attr(case, "reason", default=None),
        "decisionNotes": _get_attr(case, "decision_notes", default=None),
        "verifiedAt": _get_attr(case, "verified_at", default=None),
        "expiresAt": _get_attr(case, "expires_at", default=None),
        "decidedBy": _get_attr(case, "decided_by", default=None),
        "tech": {
            "publicName": _get_attr(tech, "public_name", default="—") if tech else "—",
            "city": _get_attr(tech, "city", default="—") if tech else "—",
            "specialty": _get_attr(tech, "specialty", default="—") if tech else "—",
            "userId": _get_attr(tech, "user_id", default=None) if tech else None,
        },
        "documents": [
            {
                "id": int(_get_attr(d, "id", default=0) or 0),
                "docType": _enum_value(_get_attr(d, "doc_type")),
                "receivedAt": _get_attr(d, "received_at", default=None),
                "verifiedResult": _get_attr(d, "verified_result", default=None),
                "verifiedAt": _get_attr(d, "verified_at", default=None),
                "meta": _get_attr(d, "meta", default={}) or {},
                "originalName": _get_attr(
                    d,
                    "original_filename",
                    "original_name",
                    default=None,
                ),
                "contentType": _get_attr(
                    d,
                    "content_type",
                    "mime_type",
                    default=None,
                ),
                "hasFile": _doc_has_file(d),
                "sizeBytes": _get_attr(d, "size_bytes", default=None),
                "sha256": _get_attr(d, "sha256", default=None),
                "storageRef": _get_attr(d, "storage_ref", default=None),
            }
            for d in docs
        ],
    }


# =========================
# Endpoints
# =========================
@router.get("/cases")
def list_cases(
    status: str = "IN_REVIEW",
    limit: int = 50,
    user: Any = Depends(require_roles("ADMIN", "VERIFIER")),
):
    del user  # solo para validar permisos

    effective_limit = max(1, min(limit, 200))

    filter_expr = None
    if status:
        filter_expr = Attr("status").eq(status)

    items: list[dict] = []
    scan_kwargs: dict[str, Any] = {"Limit": effective_limit}
    if filter_expr is not None:
        scan_kwargs["FilterExpression"] = filter_expr

    while True:
        res = cases_table.scan(**scan_kwargs)
        batch = [from_dynamo(item) for item in res.get("Items", [])]
        items.extend(batch)

        if len(items) >= effective_limit:
            items = items[:effective_limit]
            break

        lek = res.get("LastEvaluatedKey")
        if not lek:
            break

        scan_kwargs["ExclusiveStartKey"] = lek

    items.sort(
        key=lambda c: (_get_attr(c, "created_at", default="") or ""),
        reverse=True,
    )

    out = []
    for c in items:
        tech = _resolve_profile_for_case(c)
        out.append(_serialize_case_summary(c, tech))

    return out


@router.get("/cases/by-user/{user_id}")
def latest_case_by_user(
    user_id: int,
    user: Any = Depends(require_roles("ADMIN", "VERIFIER")),
):
    del user

    case = _query_latest_case_by_user_id(user_id)

    if not case:
        tech = _get_profile_by_user_id(user_id)
        if not tech:
            return {"hasCase": False}

        tech_id = _get_attr(tech, "id", default=None)
        if tech_id is None:
            return {"hasCase": False}

        case = _query_latest_case_by_tech_id(int(tech_id))

    if not case:
        return {"hasCase": False}

    tech = _resolve_profile_for_case(case)
    docs = _get_docs_for_case(int(_get_attr(case, "id")))
    return _serialize_case_detail(case, tech, docs)


@router.get("/cases/{case_id}")
def case_detail(
    case_id: int,
    user: Any = Depends(require_roles("ADMIN", "VERIFIER")),
):
    del user

    case = _get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Caso no encontrado.")

    tech = _resolve_profile_for_case(case)
    docs = _get_docs_for_case(case_id)

    return _serialize_case_detail(case, tech, docs)


@router.get("/cases/{case_id}/documents/{doc_id}/file")
def download_document_file(
    case_id: int,
    doc_id: int,
    user: Any = Depends(require_roles("ADMIN", "VERIFIER")),
):
    del user

    d = _get_doc(case_id, doc_id)
    if not d:
        raise HTTPException(status_code=404, detail="Documento no encontrado para ese caso.")

    sr = _get_attr(d, "storage_ref", "url", "file_url", default=None)
    if isinstance(sr, str) and (sr.startswith("http://") or sr.startswith("https://")):
        return RedirectResponse(url=sr)

    abs_path = _resolve_doc_path(d)
    if not abs_path:
        raise HTTPException(
            status_code=404,
            detail="Archivo no encontrado en disco (storage_ref no resolvió).",
        )

    base = _base_dir().resolve()
    uploads = (base / "uploads").resolve()
    try:
        abs_path.resolve().relative_to(uploads)
    except Exception:
        raise HTTPException(status_code=400, detail="Ruta inválida (fuera de /uploads).")

    raw_doc_type = _enum_value(_get_attr(d, "doc_type"))
    filename = (
        _get_attr(d, "original_filename", "original_name", default=None)
        or f"{raw_doc_type}_{doc_id}"
    )
    media_type = _get_attr(d, "content_type", "mime_type", default=None) or "application/octet-stream"

    return FileResponse(
        path=str(abs_path),
        media_type=media_type,
        filename=filename,
    )


@router.patch("/cases/{case_id}/documents/{doc_id}")
def review_document(
    case_id: int,
    doc_id: int,
    payload: ReviewDocPayload,
    user: Any = Depends(require_roles("ADMIN", "VERIFIER")),
):
    d = _get_doc(case_id, doc_id)
    if not d:
        raise HTTPException(status_code=404, detail="Documento no encontrado para ese caso.")

    res = (payload.result or "").lower().strip()
    if res not in ("ok", "fail", "unknown"):
        raise HTTPException(status_code=400, detail="result inválido: ok|fail|unknown")

    d["verified_result"] = res
    d["verified_at"] = _now_iso()

    meta = _get_attr(d, "meta", default={}) or {}
    if payload.notes:
        meta["admin_notes"] = payload.notes
    d["meta"] = meta

    docs_table.put_item(Item=to_dynamo(d))

    _log(
        case_id,
        int(getattr(user, "id")),
        "REVIEW_DOC",
        {
            "docId": doc_id,
            "docType": _enum_value(_get_attr(d, "doc_type")),
            "result": res,
            "notes": payload.notes,
        },
    )

    return {
        "ok": True,
        "docId": int(_get_attr(d, "id", default=doc_id) or doc_id),
        "result": d.get("verified_result"),
        "verifiedAt": d.get("verified_at"),
    }


@router.patch("/cases/{case_id}/decide")
def decide_case(
    case_id: int,
    decision: str,  # "VERIFY" | "REJECT"
    reason: Optional[str] = None,
    decision_notes: Optional[str] = None,
    user: Any = Depends(require_roles("ADMIN", "VERIFIER")),
):
    c = _get_case(case_id)
    if not c:
        raise HTTPException(status_code=404, detail="Caso no encontrado.")

    dec = (decision or "").upper().strip()

    if dec == "VERIFY":
        c["status"] = "VERIFIED"
        c["reason"] = None
        c["verified_at"] = _now_iso()

        months = 12
        if _enum_value(_get_attr(c, "target_level")) == "TRUST":
            months = 6
        c["expires_at"] = (_now() + timedelta(days=30 * months)).isoformat()

        tech = _resolve_profile_for_case(c)
        if tech:
            tech["badge_level"] = _enum_value(_get_attr(c, "target_level"))
            tech["verification_status"] = "VERIFIED"
            tech["is_verified"] = True
            profiles_table.put_item(Item=to_dynamo(tech))

    elif dec == "REJECT":
        c["status"] = "REJECTED"
        c["reason"] = reason or "Falta información o el documento no coincide."
        c["verified_at"] = None
        c["expires_at"] = None

        tech = _resolve_profile_for_case(c)
        if tech:
            tech["verification_status"] = "REJECTED"
            tech["is_verified"] = False
            profiles_table.put_item(Item=to_dynamo(tech))
    else:
        raise HTTPException(status_code=400, detail="decision inválida (VERIFY/REJECT).")

    c["decided_by"] = int(getattr(user, "id"))
    c["decision_notes"] = decision_notes
    c["updated_at"] = _now_iso()

    cases_table.put_item(Item=to_dynamo(c))

    _log(
        int(_get_attr(c, "id")),
        int(getattr(user, "id")),
        "DECIDE",
        {"decision": dec, "reason": c.get("reason"), "notes": decision_notes},
    )

    return {
        "ok": True,
        "caseId": int(_get_attr(c, "id", default=case_id) or case_id),
        "status": c.get("status"),
        "reason": c.get("reason"),
        "expiresAt": c.get("expires_at"),
    }


@router.get("/cases/{case_id}/logs")
def case_logs(
    case_id: int,
    user: Any = Depends(require_roles("ADMIN", "VERIFIER")),
):
    del user

    res = logs_table.query(
        KeyConditionExpression=Key("case_id").eq(int(case_id)),
        ScanIndexForward=True,
    )
    logs = [from_dynamo(item) for item in res.get("Items", [])]

    return [
        {
            "at": _get_attr(l, "created_at"),
            "action": _get_attr(l, "action"),
            "detail": _get_attr(l, "detail", default={}) or {},
            "actorId": _get_attr(l, "actor_id"),
        }
        for l in logs
    ]
