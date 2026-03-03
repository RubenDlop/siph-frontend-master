from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.deps import require_roles
from ..models import User

# ✅ tus modelos reales (según tu main.py)
from ..models.technician_verification import VerificationCase, VerificationDocument

from ..schemas.admin_tech_verification import AdminCaseDetailOut, AdminCaseDocOut, NoCaseOut

router = APIRouter(prefix="/admin/tech/verification", tags=["admin-tech-verification"])

# routers/ está en backend/app/routers -> parents[2] = backend/
BASE_DIR = Path(__file__).resolve().parents[2]  # backend/


def _resolve_doc_path(doc: VerificationDocument) -> Path | None:
    """
    Espera que doc.url sea algo como:
      /uploads/xxx.pdf   o   uploads/xxx.pdf
    También soporta:
      - URL completa: http://localhost:8000/uploads/xxx.pdf
      - Ruta absoluta en disco
    """
    raw = (getattr(doc, "url", None) or "").strip()
    if not raw:
        return None

    # si es ruta absoluta en disco
    p0 = Path(raw)
    if p0.is_absolute():
        return p0

    # si es URL completa, nos quedamos con el path
    if "://" in raw:
        # sin depender de urlparse: recorta desde el primer "/"
        try:
            raw = raw.split("://", 1)[1]
            raw = raw[raw.find("/") :] if "/" in raw else ""
        except Exception:
            pass

    raw = raw.lstrip("/")  # "uploads/xxx.pdf"
    if not raw:
        return None

    return BASE_DIR / raw  # backend/uploads/xxx.pdf


@router.get("/cases/by-user/{user_id}", response_model=AdminCaseDetailOut | NoCaseOut)
def latest_case_by_user(
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("ADMIN")),
):
    case = (
        db.query(VerificationCase)
        .filter(VerificationCase.user_id == user_id)
        .order_by(VerificationCase.created_at.desc())
        .first()
    )

    if not case:
        return NoCaseOut(hasCase=False)

    docs = (
        db.query(VerificationDocument)
        .filter(VerificationDocument.case_id == case.id)
        .order_by(VerificationDocument.id.asc())
        .all()
    )

    out_docs: list[AdminCaseDocOut] = []
    for d in docs:
        p = _resolve_doc_path(d)
        has_file = bool(p and p.exists() and p.is_file())

        out_docs.append(
            AdminCaseDocOut(
                id=d.id,
                doc_type=getattr(d, "doc_type", None),  # alias -> docType
                received_at=getattr(d, "received_at", None),
                verified_result=getattr(d, "verified_result", None),
                verified_at=getattr(d, "verified_at", None),
                meta=getattr(d, "meta", {}) or {},
                original_name=getattr(d, "original_name", None),
                mime_type=getattr(d, "mime_type", None),
                hasFile=has_file,  # ✅ clave
            )
        )

    tech_payload: dict[str, Any] = {
        "publicName": getattr(case, "public_name", None) or getattr(case, "name", None) or "",
        "city": getattr(case, "city", None) or "",
        "specialty": getattr(case, "specialty", None) or "",
        "userId": user_id,
    }

    return AdminCaseDetailOut(
        caseId=case.id,
        techId=getattr(case, "tech_id", user_id),
        status=case.status,
        targetLevel=case.target_level,
        createdAt=case.created_at,
        tech=tech_payload,
        documents=out_docs,
    )


@router.get("/cases/{case_id}/documents/{doc_id}/file")
def download_doc_file(
    case_id: int,
    doc_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("ADMIN")),
):
    doc = (
        db.query(VerificationDocument)
        .filter(
            VerificationDocument.id == doc_id,
            VerificationDocument.case_id == case_id,
        )
        .first()
    )

    if not doc:
        raise HTTPException(status_code=404, detail="Documento no encontrado para este caso.")

    p = _resolve_doc_path(doc)
    if not p or not p.exists() or not p.is_file():
        raise HTTPException(status_code=404, detail="El documento no tiene archivo físico asociado.")

    media_type = getattr(doc, "mime_type", None) or "application/octet-stream"
    filename = getattr(doc, "original_name", None) or p.name

    return FileResponse(path=str(p), media_type=media_type, filename=filename)
