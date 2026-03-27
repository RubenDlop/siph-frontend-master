from __future__ import annotations

from pathlib import Path
from typing import Optional, Any

from boto3.dynamodb.conditions import Key
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, RedirectResponse

from ..core.dynamo import from_dynamo, table
from ..repositories.users_repo import get_user_by_id
from ..schemas.worker_public import WorkerPublicOut

router = APIRouter(prefix="/workers", tags=["workers-public"])

profiles_table = table("technician_profiles")
cases_table = table("verification_cases")
docs_table = table("verification_documents")
reviews_table = table("request_reviews")

# ⚠️ OJO:
# Esta versión hace visibles TODOS los tipos de documentos soportados.
# Úsala si eso es exactamente lo que quieres ver en el catálogo/perfil público.
VISIBLE_DOC_TYPES = {
    "ID_PHOTO": "Foto de identidad",
    "POLICE_CERT": "Certificado de antecedentes policiales",
    "PROCURADURIA_CERT": "Certificado Procuraduría",
    "RNMC_CERT": "Certificado RNMC",
    "REFERENCES": "Referencias",
    "PRO_LICENSE": "Licencia profesional",
    "STUDY_CERT": "Certificado de estudio",
    "HEIGHTS_CERT": "Certificación de alturas",
    "GAS_CERT": "Certificación de gas",
    "RUT": "RUT",
    "BANK_CERT": "Certificación bancaria",
}

PUBLIC_CASE_STATUSES = {"VERIFIED", "IN_REVIEW", "PENDING"}

BADGE_ORDER = {
    "PAY": 4,
    "PRO": 3,
    "TRUST": 2,
    "BASIC": 1,
}


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _uploads_roots() -> list[Path]:
    base = _backend_root()
    return [
        base / "uploads" / "tech_verification",
        base / "uploads",
        base,
    ]


def _normalize_storage_ref(sr: str) -> str:
    sr = (sr or "").strip()
    if not sr:
        return ""

    if sr.startswith("encrypted://"):
        return sr.replace("encrypted://", "", 1).lstrip("/")

    if sr.startswith("file://"):
        return sr

    return sr.lstrip("/")


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


def _safe_str_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(x).strip() for x in value if str(x).strip()]


def _resolve_doc_path(d: dict) -> Optional[Path]:
    fp = _get_attr(d, "file_path", default=None)
    if isinstance(fp, str) and fp.strip():
        rel = fp.strip().lstrip("/")
        for root in _uploads_roots():
            cand = (root / rel).resolve()
            if cand.exists() and cand.is_file():
                return cand

    sr0 = _get_attr(d, "storage_ref", "url", "file_url", default=None)
    if isinstance(sr0, str) and sr0.strip():
        if sr0.startswith("http://") or sr0.startswith("https://"):
            return None

        if sr0.startswith("file://"):
            abs_p = Path(sr0.replace("file://", "", 1))
            if abs_p.exists() and abs_p.is_file():
                return abs_p.resolve()
            return None

        rel = _normalize_storage_ref(sr0)
        if rel:
            for root in _uploads_roots():
                cand = (root / rel).resolve()
                if cand.exists() and cand.is_file():
                    return cand

    return None


def _doc_has_file(d: dict) -> bool:
    sr = _get_attr(d, "storage_ref", "url", "file_url", default=None)
    if isinstance(sr, str) and (sr.startswith("http://") or sr.startswith("https://")):
        return True
    return _resolve_doc_path(d) is not None


def _doc_public_url(user_id: int, doc_id: int, d: dict) -> Optional[str]:
    if not _doc_has_file(d):
        return None
    return f"/workers/{user_id}/documents/{doc_id}/file"


def _query_public_cases_by_user(user_id: int) -> list[dict]:
    try:
        res = cases_table.query(
            IndexName="user_id-created_at-index",
            KeyConditionExpression=Key("user_id").eq(int(user_id)),
            ScanIndexForward=False,
        )
        items = [from_dynamo(item) for item in res.get("Items", [])]
    except Exception:
        items = []

    return [
        item
        for item in items
        if str(_get_attr(item, "status", default="") or "").upper() in PUBLIC_CASE_STATUSES
    ]


def _latest_case(user_id: int) -> Optional[dict]:
    cases = _query_public_cases_by_user(user_id)
    return cases[0] if cases else None


def _docs_for_case(case_id: int) -> list[dict]:
    res = docs_table.query(
        KeyConditionExpression=Key("case_id").eq(int(case_id)),
        ScanIndexForward=True,
    )
    docs = [from_dynamo(item) for item in res.get("Items", [])]

    visible: list[dict] = []
    for d in docs:
        deleted_at = _get_attr(d, "deleted_at", default=None)
        doc_type = str(_get_attr(d, "doc_type", default="") or "").upper()
        if deleted_at:
            continue
        if doc_type not in VISIBLE_DOC_TYPES:
            continue
        visible.append(d)

    visible.sort(
        key=lambda d: (
            str(_get_attr(d, "received_at", default="") or ""),
            int(_get_attr(d, "id", default=0) or 0),
        )
    )
    return visible


def _latest_public_case_with_docs(user_id: int) -> Optional[dict]:
    cases = _query_public_cases_by_user(user_id)

    for case in cases:
        docs = _docs_for_case(int(_get_attr(case, "id", default=0) or 0))
        if docs:
            return case

    return None


def _public_docs_for_case(case: dict, user_id: int) -> list[dict]:
    docs = _docs_for_case(int(_get_attr(case, "id", default=0) or 0))

    out: list[dict] = []
    for d in docs:
        doc_type = str(_get_attr(d, "doc_type", default="") or "").upper()
        out.append(
            {
                "id": int(_get_attr(d, "id", default=0) or 0),
                "doc_type": doc_type,
                "label": VISIBLE_DOC_TYPES[doc_type],
                "original_name": _get_attr(d, "original_filename", "original_name", default=None),
                "content_type": _get_attr(d, "content_type", "mime_type", default=None),
                "has_file": _doc_has_file(d),
                "file_url": _doc_public_url(user_id, int(_get_attr(d, "id", default=0) or 0), d),
            }
        )

    return out


def _public_rating_stats(worker_user_id: int) -> tuple[Optional[float], int]:
    try:
        res = reviews_table.query(
            IndexName="reviewee_user_id-created_at-index",
            KeyConditionExpression=Key("reviewee_user_id").eq(int(worker_user_id)),
            ScanIndexForward=False,
        )
        rows = [from_dynamo(item) for item in res.get("Items", [])]
    except Exception:
        rows = []

    rows = [
        r for r in rows
        if str(_get_attr(r, "reviewer_role", default="") or "").upper() == "CUSTOMER"
    ]

    count = len(rows)
    avg = round(sum(int(_get_attr(r, "rating", default=0) or 0) for r in rows) / count, 2) if count else None
    return avg, count


def _serialize_worker(profile: dict) -> dict:
    user_id = int(_get_attr(profile, "user_id", default=0) or 0)
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario del técnico no encontrado.")

    latest = _latest_case(user_id)
    public_case = _latest_public_case_with_docs(user_id)

    verification_status = "UNVERIFIED"
    is_verified = False

    if latest:
        verification_status = str(_get_attr(latest, "status", default="UNVERIFIED") or "UNVERIFIED")
        is_verified = verification_status.upper() == "VERIFIED"

    badge_level = str(_get_attr(profile, "badge_level", default="BASIC") or "BASIC").upper()

    visible_documents = (
        _public_docs_for_case(public_case, user_id)
        if public_case
        else []
    )

    average_rating, reviews_count = _public_rating_stats(user_id)

    return {
        "id": user_id,
        "user_id": user_id,
        "public_name": (
            str(_get_attr(profile, "public_name", default="") or "").strip()
            or f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
        ),
        "photo_url": _get_attr(profile, "public_photo_url", "photo_url", default=None),
        "city": _get_attr(profile, "city", default=None),
        "specialty": _get_attr(profile, "specialty", default=None),
        "years_experience": _get_attr(profile, "years_experience", default=None),
        "bio": _get_attr(profile, "bio", default=None),
        "categories": _safe_str_list(_get_attr(profile, "categories", default=[])),
        "badge_level": badge_level,
        "verification_status": verification_status,
        "is_verified": is_verified,
        "visible_documents": visible_documents,
        "average_rating": average_rating,
        "reviews_count": reviews_count,
    }


@router.get("", response_model=list[WorkerPublicOut])
def list_workers(
    q: Optional[str] = Query(default=None),
    city: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
):
    rows: list[dict] = []
    scan_kwargs: dict[str, Any] = {}

    while True:
        res = profiles_table.scan(**scan_kwargs)
        rows.extend(from_dynamo(item) for item in res.get("Items", []))

        last_key = res.get("LastEvaluatedKey")
        if not last_key:
            break
        scan_kwargs["ExclusiveStartKey"] = last_key

    q_norm = (q or "").strip().lower()
    city_norm = (city or "").strip().lower()
    category_norm = (category or "").strip().lower()

    filtered: list[dict] = []
    for profile in rows:
        user_id = int(_get_attr(profile, "user_id", default=0) or 0)
        user = get_user_by_id(user_id)
        if not user:
            continue

        if str(user.get("role") or "").upper() != "WORKER":
            continue
        if not bool(user.get("is_active", True)):
            continue

        haystack = " ".join(
            [
                str(_get_attr(profile, "public_name", default="") or ""),
                str(_get_attr(profile, "city", default="") or ""),
                str(_get_attr(profile, "specialty", default="") or ""),
                str(_get_attr(profile, "bio", default="") or ""),
                str(user.get("first_name") or ""),
                str(user.get("last_name") or ""),
            ]
        ).lower()

        cats = [str(x).strip().lower() for x in _safe_str_list(_get_attr(profile, "categories", default=[]))]

        if q_norm and q_norm not in haystack:
            continue

        if city_norm and city_norm != str(_get_attr(profile, "city", default="") or "").strip().lower():
            continue

        if category_norm and category_norm not in cats:
            continue

        filtered.append(profile)

    payload = [_serialize_worker(profile) for profile in filtered]

    payload.sort(
        key=lambda item: (
            0 if item["is_verified"] else 1,
            -BADGE_ORDER.get(str(item["badge_level"]).upper(), 0),
            -(item["years_experience"] or 0),
            str(item["public_name"]).lower(),
        )
    )

    return payload


@router.get("/{worker_id}", response_model=WorkerPublicOut)
def get_worker(worker_id: int):
    res = profiles_table.get_item(Key={"user_id": int(worker_id)})
    item = res.get("Item")
    profile = from_dynamo(item) if item else None

    if not profile:
        raise HTTPException(status_code=404, detail="Trabajador no encontrado.")

    user = get_user_by_id(int(worker_id))
    if not user or str(user.get("role") or "").upper() != "WORKER" or not bool(user.get("is_active", True)):
        raise HTTPException(status_code=404, detail="Trabajador no encontrado.")

    return _serialize_worker(profile)


@router.get("/{worker_id}/documents/{doc_id}/file")
def public_worker_document(worker_id: int, doc_id: int):
    res = profiles_table.get_item(Key={"user_id": int(worker_id)})
    item = res.get("Item")
    profile = from_dynamo(item) if item else None

    if not profile:
        raise HTTPException(status_code=404, detail="Trabajador no encontrado.")

    user = get_user_by_id(int(worker_id))
    if not user or str(user.get("role") or "").upper() != "WORKER" or not bool(user.get("is_active", True)):
        raise HTTPException(status_code=404, detail="Trabajador no encontrado.")

    public_cases = _query_public_cases_by_user(int(worker_id))
    if not public_cases:
        raise HTTPException(status_code=404, detail="Documento público no encontrado.")

    found_doc: Optional[dict] = None
    for case in public_cases:
        docs = _docs_for_case(int(_get_attr(case, "id", default=0) or 0))
        candidate = next(
            (d for d in docs if int(_get_attr(d, "id", default=0) or 0) == int(doc_id)),
            None,
        )
        if candidate:
            found_doc = candidate
            break

    if not found_doc:
        raise HTTPException(status_code=404, detail="Documento público no encontrado.")

    sr = _get_attr(found_doc, "storage_ref", "url", "file_url", default=None)
    if isinstance(sr, str) and (sr.startswith("http://") or sr.startswith("https://")):
        return RedirectResponse(url=sr)

    abs_path = _resolve_doc_path(found_doc)
    if not abs_path:
        raise HTTPException(status_code=404, detail="Archivo no encontrado.")

    base = _backend_root().resolve()
    uploads = (base / "uploads").resolve()

    try:
        abs_path.resolve().relative_to(uploads)
    except Exception:
        raise HTTPException(status_code=400, detail="Ruta inválida.")

    filename = (
        _get_attr(found_doc, "original_filename", "original_name", default=None)
        or f"{_get_attr(found_doc, 'doc_type', default='documento')}_{_get_attr(found_doc, 'id', default=doc_id)}"
    )
    media_type = _get_attr(found_doc, "content_type", "mime_type", default=None) or "application/octet-stream"
    safe_filename = str(filename).replace('"', "")

    return FileResponse(
        path=str(abs_path),
        media_type=media_type,
        headers={
            "Content-Disposition": f'inline; filename="{safe_filename}"',
            "Cache-Control": "no-store",
        },
    )
