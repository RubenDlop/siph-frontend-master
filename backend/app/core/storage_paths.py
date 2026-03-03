from pathlib import Path


def backend_root() -> Path:
    # backend/app/core/storage_paths.py -> parents[2] = backend/
    return Path(__file__).resolve().parents[2]


def uploads_root() -> Path:
    # backend/uploads/
    root = backend_root() / "uploads"
    root.mkdir(parents=True, exist_ok=True)
    return root


def tech_verification_root() -> Path:
    # backend/uploads/tech_verification/
    root = uploads_root() / "tech_verification"
    root.mkdir(parents=True, exist_ok=True)
    return root
