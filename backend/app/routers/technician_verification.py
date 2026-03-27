from __future__ import annotations

import json
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any

from boto3.dynamodb.conditions import Key
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form

from ..core.deps import get_current_user
from ..core.dynamo import from_dynamo, next_id, now_iso, table, to_dynamo
from ..core.storage_paths import tech_verification_root
from ..schemas.technician_verification import (
    UpsertProfilePayload,
    SubmitPayload,
    VerificationMeResponse,
    OkResponse,
    UploadDocResponse,
)

router = APIRouter(prefix="/tech/verification", tags=["Tech Verification"])

MAX_MB = 5
ALLOWED_CT = {"application/pdf", "image/png", "image/jpeg", "image/jpg", "image/webp"}

EXT_BY_CT = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/webp": ".webp",
}

profiles_table = table("technician_profiles")
cases_table = table("verification_cases")
docs_table = table("verification_documents")
logs_table = table("verification_audit_logs")


def _now() -> datetime:
    return datetime.utcnow()


def _now_iso() -> str:
    return now_iso()


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _safe_ext(file: UploadFile) -> str:
    ct = (file.content_type or "").lower().strip()
    if ct in EXT_BY_CT:
        return EXT_BY_CT[ct]
    if file.filename:
        return Path(file.filename).suffix.lower()[:10]
    return ""


def _get_profile(user_id: int) -> Optional[dict]:
    res = profiles_table.get_item(Key={"user_id": int(user_id)})
    item = res.get("Item")
    return from_dynamo(item) if item else None


def _put_profile(profile: dict) -> None:
    profiles_table.put_item(Item=to_dynamo(profile))


def _put_case(case: dict) -> None:
    cases_table.put_item(Item=to_dynamo(case))


def _put_doc(doc: dict) -> None:
    docs_table.put_item(Item=to_dynamo(doc))


def _log(case_id: int, actor_id: Optional[int], action: str, detail: Dict[str, Any]):
    log_item = {
        "case_id": int(case_id),
        "id": next_id("verification_audit_logs"),
        "actor_id": int(actor_id) if actor_id is not None else None,
        "action": action,
        "detail": detail,
        "created_at": _now_iso(),
    }
    logs_table.put_item(Item=to_dynamo(log_item))


def _latest_case(user_id: int, tech_id: Optional[int] = None) -> Optional[dict]:
    # 1) preferimos user_id porque el perfil en DynamoDB está keyed por user_id
    try:
        res = cases_table.query(
            IndexName="user_id-created_at-index",
            KeyConditionExpression=Key("user_id").eq(int(user_id)),
            ScanIndexForward=False,
            Limit=1,
        )
        items = [from_dynamo(item) for item in res.get("Items", [])]
        if items:
            return items[0]
    except Exception:
        pass

    # 2) fallback por tech_id por compatibilidad
    if tech_id is not None:
        try:
            res = cases_table.query(
                IndexName="tech_id-created_at-index",
                KeyConditionExpression=Key("tech_id").eq(int(tech_id)),
                ScanIndexForward=False,
                Limit=1,
            )
            items = [from_dynamo(item) for item in res.get("Items", [])]
            if items:
                return items[0]
        except Exception:
            pass

    return None


def _me_response(profile: dict, case: Optional[dict]) -> VerificationMeResponse:
    current_level = str(profile.get("badge_level") or "BASIC")

    if not case:
        return VerificationMeResponse(
            techId=int(profile.get("user_id") or 0),
            currentLevel=current_level,
            status="PENDING",
            verifiedAt=None,
            expiresAt=None,
            reason=None,
        )

    return VerificationMeResponse(
        techId=int(profile.get("user_id") or 0),
        currentLevel=current_level,
        status=str(case.get("status") or "PENDING"),
        verifiedAt=case.get("verified_at"),
        expiresAt=case.get("expires_at"),
        reason=case.get("reason"),
    )


@router.get("/me", response_model=VerificationMeResponse)
def me(
    user=Depends(get_current_user),
):
    profile = _get_profile(int(user.id))
    if not profile:
        raise HTTPException(status_code=404, detail="Aún no has creado tu perfil de técnico.")

    case = _latest_case(int(user.id), int(profile.get("id")) if profile.get("id") is not None else None)
    return _me_response(profile, case)


@router.put("/profile", response_model=OkResponse)
def upsert_profile(
    payload: UpsertProfilePayload,
    user=Depends(get_current_user),
):
    pub = payload.public or {}
    priv = payload.private or {}
    tech = payload.technician or {}
    cons = payload.consents or {}

    required = [
        ("public.name", pub.get("name")),
        ("public.city", pub.get("city")),
        ("private.doc_type", priv.get("doc_type")),
        ("private.doc_number", priv.get("doc_number")),
        ("private.phone", priv.get("phone")),
        ("private.email", priv.get("email")),
        ("technician.specialty", tech.get("specialty")),
        ("technician.bio", tech.get("bio")),
    ]
    missing = [k for k, v in required if not v]
    if missing:
        raise HTTPException(status_code=400, detail=f"Faltan campos: {', '.join(missing)}")

    if not cons.get("terms") or not cons.get("privacy") or not cons.get("sensitive"):
        raise HTTPException(
            status_code=400,
            detail="Debes aceptar Términos, Privacidad y autorizar verificación de documentos.",
        )

    profile = _get_profile(int(user.id))
    now = _now_iso()

    if not profile:
        profile = {
            # PK real en DynamoDB
            "user_id": int(user.id),
            # id opcional por compatibilidad con código viejo
            "id": int(user.id),
            "created_at": now,
            "badge_level": "BASIC",
            "verification_status": "PENDING",
            "is_verified": False,
        }

    profile["public_name"] = pub["name"]
    profile["public_photo_url"] = pub.get("photo_url")
    profile["city"] = pub["city"]
    profile["radius_km"] = int(pub.get("radius_km") or 5)
    profile["categories"] = pub.get("categories") or []

    profile["doc_type"] = priv["doc_type"]
    profile["doc_number"] = priv["doc_number"]
    profile["phone"] = priv["phone"]
    profile["email"] = priv["email"]

    profile["specialty"] = tech["specialty"]
    profile["years_experience"] = int(tech.get("years_experience") or 0)
    profile["bio"] = tech["bio"]
    profile["activities"] = tech.get("activities") or []
    profile["wants_payments"] = bool(tech.get("wants_payments") or False)

    profile["consent_terms"] = True
    profile["consent_privacy"] = True
    profile["consent_sensitive"] = True
    profile["consent_text_version"] = str(cons.get("version") or "v1")
    profile["updated_at"] = now

    _put_profile(profile)

    case = _latest_case(int(user.id), int(profile.get("id")) if profile.get("id") is not None else None)
    if case:
        _log(
            int(case["id"]),
            int(user.id),
            "UPSERT_PROFILE",
            {"categories": profile.get("categories") or [], "activities": profile.get("activities") or []},
        )

    return OkResponse(ok=True)


@router.post("/documents", response_model=UploadDocResponse)
def upload_document(
    docType: str = Form(...),
    consent: str = Form(...),
    file: UploadFile = File(...),
    extra: Optional[str] = Form(None),
    user=Depends(get_current_user),
):
    if str(consent).lower() != "true":
        raise HTTPException(status_code=400, detail="Debes autorizar el uso del documento solo para verificación.")

    ct = (file.content_type or "").lower().strip()
    if ct not in ALLOWED_CT:
        raise HTTPException(status_code=400, detail="Formato no válido (solo PDF/PNG/JPG/WEBP).")

    data = file.file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Archivo vacío.")
    if len(data) > MAX_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Archivo >5 MB")

    profile = _get_profile(int(user.id))
    if not profile:
        raise HTTPException(status_code=400, detail="Primero completa tu perfil.")

    # reutiliza draft PENDING
    case = _latest_case(int(user.id), int(profile.get("id")) if profile.get("id") is not None else None)
    if not case or str(case.get("status")) != "PENDING":
        case = {
            "id": next_id("verification_cases"),
            "user_id": int(user.id),
            "tech_id": int(profile.get("id") or user.id),
            "target_level": "BASIC",
            "status": "PENDING",
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
            "verified_at": None,
            "expires_at": None,
            "reason": None,
            "decision_notes": None,
            "decided_by": None,
            # snapshots útiles
            "public_name": profile.get("public_name"),
            "city": profile.get("city"),
            "specialty": profile.get("specialty"),
        }
        _put_case(case)

    extra_obj: Dict[str, Any] = {}
    if extra:
        try:
            extra_obj = json.loads(extra)
        except Exception:
            raise HTTPException(status_code=400, detail="Extra inválido (JSON).")

    allowed_doc_types = {
        "ID_PHOTO",
        "POLICE_CERT",
        "PROCURADURIA_CERT",
        "RNMC_CERT",
        "REFERENCES",
        "PRO_LICENSE",
        "STUDY_CERT",
        "HEIGHTS_CERT",
        "GAS_CERT",
        "RUT",
        "BANK_CERT",
    }
    dt = str(docType).strip().upper()
    if dt not in allowed_doc_types:
        raise HTTPException(status_code=400, detail="docType no válido")

    sha = _sha256_bytes(data)
    ext = _safe_ext(file)

    root = tech_verification_root().resolve()
    case_dir = (root / f"case-{case['id']}").resolve()
    case_dir.mkdir(parents=True, exist_ok=True)

    safe_name = dt.lower()
    filename = f"{safe_name}-{sha}{ext}"
    abs_path = (case_dir / filename).resolve()

    if root not in abs_path.parents:
        raise HTTPException(status_code=400, detail="Ruta inválida.")

    abs_path.write_bytes(data)

    rel_path = str(abs_path.relative_to(root))  # case-1/xxx.pdf
    now = _now_iso()

    doc = {
        "case_id": int(case["id"]),
        "id": next_id("verification_documents"),
        "doc_type": dt,
        "content_type": ct,
        "original_filename": file.filename,
        "original_name": file.filename,
        "mime_type": ct,
        "size_bytes": len(data),
        "sha256": sha,
        "meta": extra_obj or {},
        "received_at": now,
        "verified_result": None,
        "verified_at": None,
        "file_path": rel_path,
        "storage_ref": rel_path,
        "url": f"/uploads/tech_verification/{rel_path}",
        "file_url": f"/uploads/tech_verification/{rel_path}",
        "retained_until": (_now() + timedelta(days=30)).isoformat() if dt == "ID_PHOTO" else None,
    }

    _put_doc(doc)

    _log(
        int(case["id"]),
        int(user.id),
        "UPLOAD_DOC",
        {"docType": dt, "size": len(data), "stored": True, "path": rel_path},
    )

    return UploadDocResponse(ok=True, docType=dt, receivedAt=now)


@router.post("/submit", response_model=VerificationMeResponse)
def submit_for_verification(
    payload: SubmitPayload,
    user=Depends(get_current_user),
):
    profile = _get_profile(int(user.id))
    if not profile:
        raise HTTPException(status_code=400, detail="Primero completa tu perfil.")

    last = _latest_case(int(user.id), int(profile.get("id")) if profile.get("id") is not None else None)
    target_level = str(payload.targetLevel).strip().upper()

    if last and str(last.get("status")) == "PENDING":
        case = last
        case["target_level"] = target_level
        case["status"] = "IN_REVIEW"
        case["updated_at"] = _now_iso()
    else:
        case = {
            "id": next_id("verification_cases"),
            "user_id": int(user.id),
            "tech_id": int(profile.get("id") or user.id),
            "target_level": target_level,
            "status": "IN_REVIEW",
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
            "verified_at": None,
            "reason": None,
            "decision_notes": None,
            "decided_by": None,
            "public_name": profile.get("public_name"),
            "city": profile.get("city"),
            "specialty": profile.get("specialty"),
        }

    months = 12
    if target_level == "TRUST":
        months = 6

    case["expires_at"] = (_now() + timedelta(days=30 * months)).isoformat()
    case["updated_at"] = _now_iso()

    _put_case(case)

    profile["verification_status"] = "IN_REVIEW"
    profile["updated_at"] = _now_iso()
    _put_profile(profile)

    _log(
        int(case["id"]),
        int(user.id),
        "SUBMIT",
        {"targetLevel": target_level, "extra": payload.extra or {}},
    )

    return _me_response(profile, case)
