# backend/app/main.py
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.database import Base, engine

# =========================
# Importar modelos (side effects: registrar tablas)
# =========================
from .models.user import User  # noqa: F401
from .models.service_request import ServiceRequest  # noqa: F401
from .models.worker_application import WorkerApplication  # noqa: F401
from .models.technician_verification import (  # noqa: F401
    TechnicianProfile,
    VerificationCase,
    VerificationDocument,
    VerificationAuditLog,
)

# =========================
# Importar routers
# =========================
from .routers import (
    auth,
    requests,
    worker_applications,
    technician_verification,
    admin_technician_verification,
    admin_worker_applications,
    manychat,
)

app = FastAPI(title="SIPH API")


def parse_origins(raw: str) -> list[str]:
    return [item.strip().rstrip("/") for item in raw.split(",") if item.strip()]


# =========================
# CORS
# =========================
raw = os.getenv("CORS_ORIGINS", "").strip()
allow_origins = parse_origins(raw)

# fallback robusto
if not allow_origins:
    allow_origins = [
        "http://localhost:4200",
        "http://127.0.0.1:4200",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://siph-frontend-master.netlify.app",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# =========================
# Crear tablas (modo prototipo/dev)
# =========================
Base.metadata.create_all(bind=engine)

# =========================
# Routers públicos / auth
# =========================
app.include_router(auth.router)
app.include_router(requests.router)

# =========================
# USER routes
# =========================
app.include_router(worker_applications.router)
app.include_router(technician_verification.router)

# =========================
# ADMIN routes
# =========================
app.include_router(admin_worker_applications.router)
app.include_router(admin_technician_verification.router)

# =========================
# MANYCHAT routes
# =========================
app.include_router(manychat.router)

# =========================
# Healthchecks
# =========================
@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "siph-api",
    }


@app.get("/")
def root():
    return {
        "message": "SIPH API running",
        "health": "/health",
    }
