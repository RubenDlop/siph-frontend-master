# backend/app/routers/technician_verification.py
import json
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.deps import get_current_user
from ..core.storage_paths import tech_verification_root  # ✅ NUEVO (ruta uploads)
from ..models.user import User
from ..models.technician_verification import (
    TechnicianProfile,
    VerificationCase,
    VerificationDocument,
    VerificationAuditLog,
    TechLevel,
    TechStatus,
    DocType,
)
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


def _now():
    return datetime.utcnow()


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _safe_ext(file: UploadFile) -> str:
    ct = (file.content_type or "").lower().strip()
    if ct in EXT_BY_CT:
        return EXT_BY_CT[ct]
    if file.filename:
        return Path(file.filename).suffix.lower()[:10]
    return ""


def _log(db: Session, case_id: int, actor_id: Optional[int], action: str, detail: Dict[str, Any]):
    db.add(
        VerificationAuditLog(
            case_id=case_id,
            actor_id=actor_id,
            action=action,
            detail=detail,
            created_at=_now(),
        )
    )


def _latest_case_db(db: Session, tech_id: int) -> Optional[VerificationCase]:
    return (
        db.query(VerificationCase)
        .filter(VerificationCase.tech_id == tech_id)
        .order_by(VerificationCase.created_at.desc())
        .first()
    )


def _me_response(profile: TechnicianProfile, case: Optional[VerificationCase]) -> VerificationMeResponse:
    if not case:
        return VerificationMeResponse(
            techId=profile.id,
            currentLevel=profile.badge_level.value,
            status=TechStatus.PENDING.value,
            verifiedAt=None,
            expiresAt=None,
            reason=None,
        )

    return VerificationMeResponse(
        techId=profile.id,
        currentLevel=profile.badge_level.value,
        status=case.status.value,
        verifiedAt=case.verified_at.isoformat() if case.verified_at else None,
        expiresAt=case.expires_at.isoformat() if case.expires_at else None,
        reason=case.reason,
    )


@router.get("/me", response_model=VerificationMeResponse)
def me(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    profile = db.query(TechnicianProfile).filter(TechnicianProfile.user_id == user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Aún no has creado tu perfil de técnico.")

    case = _latest_case_db(db, profile.id)
    return _me_response(profile, case)


@router.put("/profile", response_model=OkResponse)
def upsert_profile(
    payload: UpsertProfilePayload,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
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

    profile = db.query(TechnicianProfile).filter(TechnicianProfile.user_id == user.id).first()
    if not profile:
        profile = TechnicianProfile(user_id=user.id)

    profile.public_name = pub["name"]
    profile.public_photo_url = pub.get("photo_url")
    profile.city = pub["city"]
    profile.radius_km = int(pub.get("radius_km") or 5)
    profile.categories = pub.get("categories") or []

    profile.doc_type = priv["doc_type"]
    profile.doc_number = priv["doc_number"]
    profile.phone = priv["phone"]
    profile.email = priv["email"]

    profile.specialty = tech["specialty"]
    profile.years_experience = int(tech.get("years_experience") or 0)
    profile.bio = tech["bio"]
    profile.activities = tech.get("activities") or []
    profile.wants_payments = bool(tech.get("wants_payments") or False)

    profile.consent_terms = True
    profile.consent_privacy = True
    profile.consent_sensitive = True
    profile.consent_text_version = str(cons.get("version") or "v1")
    profile.updated_at = _now()

    db.add(profile)
    db.commit()
    db.refresh(profile)

    case = _latest_case_db(db, profile.id)
    if case:
        _log(
            db,
            case.id,
            user.id,
            "UPSERT_PROFILE",
            {"categories": profile.categories, "activities": profile.activities},
        )
        db.commit()

    return OkResponse(ok=True)


@router.post("/documents", response_model=UploadDocResponse)
def upload_document(
    docType: str = Form(...),
    consent: str = Form(...),
    file: UploadFile = File(...),
    extra: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # ✅ consentimiento
    if str(consent).lower() != "true":
        raise HTTPException(status_code=400, detail="Debes autorizar el uso del documento solo para verificación.")

    # ✅ valida content-type
    ct = (file.content_type or "").lower().strip()
    if ct not in ALLOWED_CT:
        raise HTTPException(status_code=400, detail="Formato no válido (solo PDF/PNG/JPG/WEBP).")

    # ✅ lee bytes + valida tamaño
    data = file.file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Archivo vacío.")
    if len(data) > MAX_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Archivo >5 MB")

    profile = db.query(TechnicianProfile).filter(TechnicianProfile.user_id == user.id).first()
    if not profile:
        raise HTTPException(status_code=400, detail="Primero completa tu perfil.")

    # ✅ Draft PENDING para guardar docs
    case = _latest_case_db(db, profile.id)
    if not case or case.status != TechStatus.PENDING:
        case = VerificationCase(
            tech_id=profile.id,
            target_level=TechLevel.BASIC,
            status=TechStatus.PENDING,
            created_at=_now(),
            updated_at=_now(),
        )
        db.add(case)
        db.commit()
        db.refresh(case)

    # ✅ extra JSON
    extra_obj: Dict[str, Any] = {}
    if extra:
        try:
            extra_obj = json.loads(extra)
        except Exception:
            raise HTTPException(status_code=400, detail="Extra inválido (JSON).")

    # ✅ docType enum
    try:
        dt = DocType(docType)
    except Exception:
        raise HTTPException(status_code=400, detail="docType no válido")

    sha = _sha256_bytes(data)
    ext = _safe_ext(file)

    # ✅ GUARDA ARCHIVO FÍSICO (esto es lo que faltaba)
    root = tech_verification_root().resolve()  # /app/uploads/tech_verification (según tu core/storage_paths.py)
    case_dir = (root / f"case-{case.id}").resolve()
    case_dir.mkdir(parents=True, exist_ok=True)

    safe_name = dt.value.lower()
    filename = f"{safe_name}-{sha}{ext}"
    abs_path = (case_dir / filename).resolve()

    # seguridad: evita path traversal
    if root not in abs_path.parents:
        raise HTTPException(status_code=400, detail="Ruta inválida.")

    abs_path.write_bytes(data)

    # ruta relativa para guardar en DB (portable)
    rel_path = str(abs_path.relative_to(root))  # ej: "case-1/id_photo-<sha>.jpg"

    doc = VerificationDocument(
        case_id=case.id,
        doc_type=dt,
        content_type=ct,
        original_filename=file.filename,
        size_bytes=len(data),
        sha256=sha,
        meta=extra_obj or {},
        received_at=_now(),
        file_path=rel_path,   # ✅ CLAVE: Admin podrá abrirlo
        storage_ref=rel_path, # ✅ compatibilidad con resolvers existentes
    )

    # Retención (si quieres mantener tu regla)
    if dt == DocType.ID_PHOTO:
        doc.retained_until = _now() + timedelta(days=30)
    else:
        doc.retained_until = None

    db.add(doc)
    _log(
        db,
        case.id,
        user.id,
        "UPLOAD_DOC",
        {"docType": dt.value, "size": len(data), "stored": True, "path": rel_path},
    )
    db.commit()
    db.refresh(doc)

    return UploadDocResponse(ok=True, docType=dt.value, receivedAt=doc.received_at.isoformat())


@router.post("/submit", response_model=VerificationMeResponse)
def submit_for_verification(
    payload: SubmitPayload,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    profile = db.query(TechnicianProfile).filter(TechnicianProfile.user_id == user.id).first()
    if not profile:
        raise HTTPException(status_code=400, detail="Primero completa tu perfil.")

    last = _latest_case_db(db, profile.id)

    # ✅ Reutiliza draft PENDING (donde están los docs) -> IN_REVIEW
    if last and last.status == TechStatus.PENDING:
        case = last
        case.target_level = TechLevel(payload.targetLevel)
        case.status = TechStatus.IN_REVIEW
        case.updated_at = _now()
    else:
        case = VerificationCase(
            tech_id=profile.id,
            target_level=TechLevel(payload.targetLevel),
            status=TechStatus.IN_REVIEW,
            created_at=_now(),
            updated_at=_now(),
        )
        db.add(case)
        db.flush()

    _log(db, case.id, user.id, "SUBMIT", {"targetLevel": payload.targetLevel, "extra": payload.extra or {}})

    months = 12
    if payload.targetLevel == "TRUST":
        months = 6

    case.expires_at = _now() + timedelta(days=30 * months)
    case.updated_at = _now()

    db.commit()
    db.refresh(case)

    return _me_response(profile, case)
