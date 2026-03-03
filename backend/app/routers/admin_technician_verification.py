# backend/app/routers/admin_technician_verification.py

from datetime import datetime, timedelta
from typing import Optional, List
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.deps import get_current_user, require_roles
from ..models.user import User
from ..models.technician_verification import (
    VerificationCase,
    TechnicianProfile,
    VerificationAuditLog,
    VerificationDocument,
    TechStatus,
    TechLevel,
)

router = APIRouter(prefix="/admin/tech/verification", tags=["Admin Tech Verification"])


def _now():
    return datetime.utcnow()


def _log(db: Session, case_id: int, actor_id: int, action: str, detail: dict):
    db.add(
        VerificationAuditLog(
            case_id=case_id,
            actor_id=actor_id,
            action=action,
            detail=detail,
            created_at=_now(),
        )
    )


class ReviewDocPayload(BaseModel):
    result: str  # "ok" | "fail" | "unknown"
    notes: Optional[str] = None


# =========================
# ✅ helpers para ubicar archivos
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

    # encrypted://private/case-1/xxx.png  -> private/case-1/xxx.png
    if sr.startswith("encrypted://"):
        return sr.replace("encrypted://", "", 1).lstrip("/")

    # file://abs/path -> mantenemos indicador de abs
    if sr.startswith("file://"):
        return sr

    return sr.lstrip("/")


def _resolve_doc_path(d: VerificationDocument) -> Optional[Path]:
    """
    Devuelve el primer Path existente en disco, o None.
    Soporta:
    - d.file_path
    - d.storage_ref:
        - file://ABS_PATH
        - encrypted://private/...
        - rutas relativas tipo private/case-1/...
        - uploads/...
    """
    # 0) file_path
    fp = getattr(d, "file_path", None)
    if isinstance(fp, str) and fp.strip():
        rel = fp.strip().lstrip("/")
        for root in _uploads_roots():
            cand = (root / rel).resolve()
            if cand.exists():
                return cand

    # 1) storage_ref
    sr0 = getattr(d, "storage_ref", None)
    if isinstance(sr0, str) and sr0.strip():
        # URLs públicas: no es archivo local
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


def _doc_has_file(d: VerificationDocument) -> bool:
    sr = getattr(d, "storage_ref", None)
    if isinstance(sr, str) and (sr.startswith("http://") or sr.startswith("https://")):
        return True
    return _resolve_doc_path(d) is not None


# =========================
# Endpoints
# =========================
@router.get("/cases")
def list_cases(
    status: str = "IN_REVIEW",
    limit: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_roles("ADMIN", "VERIFIER")(user)

    q = db.query(VerificationCase)
    if status:
        try:
            q = q.filter(VerificationCase.status == TechStatus(status))
        except Exception:
            raise HTTPException(
                status_code=400,
                detail="status inválido (PENDING|IN_REVIEW|VERIFIED|REJECTED).",
            )

    cases = q.order_by(VerificationCase.created_at.desc()).limit(min(limit, 200)).all()

    out = []
    for c in cases:
        tech = (
            db.query(TechnicianProfile)
            .filter(TechnicianProfile.id == c.tech_id)
            .first()
        )
        out.append(
            {
                "caseId": c.id,
                "techId": c.tech_id,
                "publicName": tech.public_name if tech else "—",
                "targetLevel": c.target_level.value,
                "status": c.status.value,
                "createdAt": c.created_at.isoformat(),
            }
        )
    return out


@router.get("/cases/by-user/{user_id}")
def latest_case_by_user(
    user_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_roles("ADMIN", "VERIFIER")(user)

    tech = (
        db.query(TechnicianProfile)
        .filter(TechnicianProfile.user_id == user_id)
        .first()
    )
    if not tech:
        return {"hasCase": False}

    c = (
        db.query(VerificationCase)
        .filter(VerificationCase.tech_id == tech.id)
        .order_by(VerificationCase.created_at.desc())
        .first()
    )
    if not c:
        return {"hasCase": False}

    return case_detail(c.id, db, user)


@router.get("/cases/{case_id}")
def case_detail(
    case_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_roles("ADMIN", "VERIFIER")(user)

    c = db.query(VerificationCase).filter(VerificationCase.id == case_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Caso no encontrado.")

    tech = (
        db.query(TechnicianProfile)
        .filter(TechnicianProfile.id == c.tech_id)
        .first()
    )

    docs = (
        db.query(VerificationDocument)
        .filter(VerificationDocument.case_id == c.id)
        .order_by(VerificationDocument.received_at.asc())
        .all()
    )

    return {
        "hasCase": True,
        "caseId": c.id,
        "techId": c.tech_id,
        "status": c.status.value,
        "targetLevel": c.target_level.value,
        "createdAt": c.created_at.isoformat(),
        "updatedAt": c.updated_at.isoformat() if getattr(c, "updated_at", None) else None,
        "reason": getattr(c, "reason", None),
        "decisionNotes": getattr(c, "decision_notes", None),
        "verifiedAt": c.verified_at.isoformat() if getattr(c, "verified_at", None) else None,
        "expiresAt": c.expires_at.isoformat() if getattr(c, "expires_at", None) else None,
        "decidedBy": getattr(c, "decided_by", None),
        "tech": {
            "publicName": tech.public_name if tech else "—",
            "city": tech.city if tech else "—",
            "specialty": tech.specialty if tech else "—",
            "userId": tech.user_id if tech else None,
        },
        "documents": [
            {
                "id": d.id,
                "docType": d.doc_type.value,
                "receivedAt": d.received_at.isoformat() if d.received_at else None,
                "verifiedResult": d.verified_result,
                "verifiedAt": d.verified_at.isoformat() if d.verified_at else None,
                "meta": d.meta or {},
                "originalName": getattr(d, "original_filename", None),
                "contentType": d.content_type,
                "hasFile": _doc_has_file(d),
                "sizeBytes": getattr(d, "size_bytes", None),
                "sha256": getattr(d, "sha256", None),
                "storageRef": getattr(d, "storage_ref", None),
            }
            for d in docs
        ],
    }


@router.get("/cases/{case_id}/documents/{doc_id}/file")
def download_document_file(
    case_id: int,
    doc_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_roles("ADMIN", "VERIFIER")(user)

    d = (
        db.query(VerificationDocument)
        .filter(
            VerificationDocument.id == doc_id,
            VerificationDocument.case_id == case_id,
        )
        .first()
    )
    if not d:
        raise HTTPException(status_code=404, detail="Documento no encontrado para ese caso.")

    # ✅ Si storage_ref es URL, redirigimos
    sr = getattr(d, "storage_ref", None)
    if isinstance(sr, str) and (sr.startswith("http://") or sr.startswith("https://")):
        return RedirectResponse(url=sr)

    abs_path = _resolve_doc_path(d)
    if not abs_path:
        raise HTTPException(status_code=404, detail="Archivo no encontrado en disco (storage_ref no resolvió).")

    # ✅ seguridad: restringe a backend/uploads
    base = _base_dir().resolve()
    uploads = (base / "uploads").resolve()
    try:
        abs_path.resolve().relative_to(uploads)
    except Exception:
        raise HTTPException(status_code=400, detail="Ruta inválida (fuera de /uploads).")

    filename = getattr(d, "original_filename", None) or f"{d.doc_type.value}_{d.id}"
    media_type = d.content_type or "application/octet-stream"

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
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_roles("ADMIN", "VERIFIER")(user)

    d = (
        db.query(VerificationDocument)
        .filter(
            VerificationDocument.id == doc_id,
            VerificationDocument.case_id == case_id,
        )
        .first()
    )
    if not d:
        raise HTTPException(status_code=404, detail="Documento no encontrado para ese caso.")

    res = (payload.result or "").lower().strip()
    if res not in ("ok", "fail", "unknown"):
        raise HTTPException(status_code=400, detail="result inválido: ok|fail|unknown")

    d.verified_result = res
    d.verified_at = _now()

    meta = d.meta or {}
    if payload.notes:
        meta["admin_notes"] = payload.notes
    d.meta = meta

    _log(
        db,
        case_id,
        user.id,
        "REVIEW_DOC",
        {
            "docId": doc_id,
            "docType": d.doc_type.value,
            "result": res,
            "notes": payload.notes,
        },
    )

    db.commit()
    db.refresh(d)

    return {
        "ok": True,
        "docId": d.id,
        "result": d.verified_result,
        "verifiedAt": d.verified_at.isoformat() if d.verified_at else None,
    }


@router.patch("/cases/{case_id}/decide")
def decide_case(
    case_id: int,
    decision: str,  # "VERIFY"|"REJECT"
    reason: Optional[str] = None,
    decision_notes: Optional[str] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_roles("ADMIN", "VERIFIER")(user)

    c = db.query(VerificationCase).filter(VerificationCase.id == case_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Caso no encontrado.")

    dec = (decision or "").upper().strip()

    if dec == "VERIFY":
        c.status = TechStatus.VERIFIED
        c.reason = None
        c.verified_at = _now()

        tech = db.query(TechnicianProfile).filter(TechnicianProfile.id == c.tech_id).first()
        if tech:
            tech.badge_level = c.target_level

        months = 12
        if c.target_level == TechLevel.TRUST:
            months = 6
        c.expires_at = _now() + timedelta(days=30 * months)

    elif dec == "REJECT":
        c.status = TechStatus.REJECTED
        c.reason = reason or "Falta información o el documento no coincide."
        c.verified_at = None
        c.expires_at = None
    else:
        raise HTTPException(status_code=400, detail="decision inválida (VERIFY/REJECT).")

    c.decided_by = user.id
    c.decision_notes = decision_notes
    c.updated_at = _now()

    _log(
        db,
        c.id,
        user.id,
        "DECIDE",
        {"decision": dec, "reason": c.reason, "notes": decision_notes},
    )
    db.commit()

    return {
        "ok": True,
        "caseId": c.id,
        "status": c.status.value,
        "reason": c.reason,
        "expiresAt": c.expires_at.isoformat() if c.expires_at else None,
    }


@router.get("/cases/{case_id}/logs")
def case_logs(
    case_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_roles("ADMIN", "VERIFIER")(user)

    logs = (
        db.query(VerificationAuditLog)
        .filter(VerificationAuditLog.case_id == case_id)
        .order_by(VerificationAuditLog.created_at.asc())
        .all()
    )
    return [
        {
            "at": l.created_at.isoformat(),
            "action": l.action,
            "detail": l.detail,
            "actorId": l.actor_id,
        }
        for l in logs
    ]
