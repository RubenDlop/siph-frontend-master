import hashlib
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.storage_paths import tech_verification_root
from ..models.technician_verification import VerificationCase, VerificationDocument

router = APIRouter()

EXT_BY_CT = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/webp": ".webp",
}


@router.post("/tech/verification/cases/{case_id}/documents/{doc_type}")
async def upload_document(
    case_id: int,
    doc_type: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    # 1) valida case
    case = db.query(VerificationCase).filter(VerificationCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case no encontrado.")

    # 2) lee bytes
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Archivo vacío.")

    # 3) hash
    sha256 = hashlib.sha256(data).hexdigest()

    # 4) define extensión
    ext = EXT_BY_CT.get(file.content_type or "", "")
    if not ext and file.filename:
        ext = Path(file.filename).suffix.lower()[:10]  # fallback
    if ext and len(ext) > 10:
        ext = ""

    # 5) construye ruta segura
    root = tech_verification_root()                     # backend/uploads/tech_verification
    case_dir = root / f"case-{case_id}"
    case_dir.mkdir(parents=True, exist_ok=True)

    safe_doc_type = (doc_type or "document").strip().lower()
    filename = f"{safe_doc_type}-{sha256}{ext}"
    abs_path = (case_dir / filename).resolve()

    # seguridad anti path traversal
    root_resolved = root.resolve()
    if root_resolved not in abs_path.parents:
        raise HTTPException(status_code=400, detail="Ruta inválida.")

    # 6) escribe archivo
    abs_path.write_bytes(data)

    # 7) guarda registro en DB
    rel_path = str(abs_path.relative_to(root_resolved))  # ej: "case-1/police_cert-xxx.png"

    doc = VerificationDocument(
        case_id=case_id,
        doc_type=doc_type,
        content_type=file.content_type,
        original_name=file.filename,
        size_bytes=len(data),
        sha256=sha256,
        storage_ref=rel_path,   # opcional (compatibilidad)
        file_path=rel_path,     # ✅ lo importante
    )

    db.add(doc)
    db.commit()
    db.refresh(doc)

    # 8) respuesta (si tu frontend espera hasFile, lo mandamos)
    return {
        "id": doc.id,
        "case_id": doc.case_id,
        "doc_type": doc.doc_type,
        "content_type": doc.content_type,
        "original_name": doc.original_name,
        "size_bytes": doc.size_bytes,
        "sha256": doc.sha256,
        "file_path": doc.file_path,
        "hasFile": bool(doc.file_path),
        "created_at": doc.created_at,
    }
