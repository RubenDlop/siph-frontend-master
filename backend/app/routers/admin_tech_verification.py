from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from boto3.dynamodb.conditions import Key
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from ..core.deps import require_roles
from ..core.dynamo import from_dynamo, table
from ..schemas.admin_tech_verification import (
    AdminCaseDetailOut,
    AdminCaseDocOut,
    NoCaseOut,
)

router = APIRouter(prefix="/admin/tech/verification", tags=["admin-tech-verification"])

# routers/ está en backend/app/routers -> parents[2] = backend/
BASE_DIR = Path(__file__).resolve().parents[2]  # backend/

cases_table = table("verification_cases")
docs_table = table("verification_documents")


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


def _resolve_doc_path(doc: dict) -> Path | None:
    """
    Soporta varios formatos posibles guardados en DynamoDB:
      - url: /uploads/xxx.pdf | uploads/xxx.pdf | URL completa
      - file_url
      - file_path
      - storage_ref
    También soporta ruta absoluta en disco.
    """
    raw = (
        _get_attr(doc, "url", "file_url", "file_path", "storage_ref", default="") or ""
    ).strip()

    if not raw:
        return None

    # Ruta absoluta en disco
    p0 = Path(raw)
    if p0.is_absolute():
        return p0

    # URL completa -> quedarse solo con el path
    if "://" in raw:
        try:
            raw = raw.split("://", 1)[1]
            raw = raw[raw.find("/") :] if "/" in raw else ""
        except Exception:
            pass

    raw = raw.lstrip("/")
    if not raw:
        return None

    return BASE_DIR / raw


@router.get("/cases/by-user/{user_id}", response_model=AdminCaseDetailOut | NoCaseOut)
def latest_case_by_user(
    user_id: int,
    _: Any = Depends(require_roles("ADMIN")),
):
    res = cases_table.query(
        IndexName="user_id-created_at-index",
        KeyConditionExpression=Key("user_id").eq(user_id),
        ScanIndexForward=False,
        Limit=1,
    )
    items = [from_dynamo(item) for item in res.get("Items", [])]
    case = items[0] if items else None

    if not case:
        return NoCaseOut(hasCase=False)

    docs_res = docs_table.query(
        KeyConditionExpression=Key("case_id").eq(int(case["id"])),
        ScanIndexForward=True,
    )
    docs = [from_dynamo(item) for item in docs_res.get("Items", [])]

    out_docs: list[AdminCaseDocOut] = []
    for d in docs:
        p = _resolve_doc_path(d)
        has_file = bool(p and p.exists() and p.is_file())

        out_docs.append(
            AdminCaseDocOut(
                id=int(_get_attr(d, "id")),
                doc_type=_get_attr(d, "doc_type", default=""),
                received_at=_get_attr(d, "received_at"),
                verified_result=_get_attr(d, "verified_result"),
                verified_at=_get_attr(d, "verified_at"),
                meta=_get_attr(d, "meta", default={}) or {},
                original_name=_get_attr(
                    d,
                    "original_name",
                    "original_filename",
                    default=None,
                ),
                mime_type=_get_attr(
                    d,
                    "mime_type",
                    "content_type",
                    default=None,
                ),
                hasFile=has_file,
            )
        )

    tech_payload: dict[str, Any] = {
        "publicName": _get_attr(case, "public_name", "name", default="") or "",
        "city": _get_attr(case, "city", default="") or "",
        "specialty": _get_attr(case, "specialty", default="") or "",
        "userId": user_id,
    }

    return AdminCaseDetailOut(
        caseId=int(_get_attr(case, "id")),
        techId=int(_get_attr(case, "tech_id", default=user_id) or user_id),
        status=_get_attr(case, "status"),
        targetLevel=_get_attr(case, "target_level"),
        createdAt=_get_attr(case, "created_at"),
        tech=tech_payload,
        documents=out_docs,
    )


@router.get("/cases/{case_id}/documents/{doc_id}/file")
def download_doc_file(
    case_id: int,
    doc_id: int,
    _: Any = Depends(require_roles("ADMIN")),
):
    res = docs_table.get_item(
        Key={
            "case_id": case_id,
            "id": doc_id,
        }
    )
    raw_doc = res.get("Item")
    doc = from_dynamo(raw_doc) if raw_doc else None

    if not doc:
        raise HTTPException(
            status_code=404,
            detail="Documento no encontrado para este caso.",
        )

    p = _resolve_doc_path(doc)
    if not p or not p.exists() or not p.is_file():
        raise HTTPException(
            status_code=404,
            detail="El documento no tiene archivo físico asociado.",
        )

    media_type = _get_attr(doc, "mime_type", "content_type", default=None) or "application/octet-stream"
    filename = (
        _get_attr(doc, "original_name", "original_filename", default=None)
        or p.name
    )

    return FileResponse(
        path=str(p),
        media_type=media_type,
        filename=filename,
    )
