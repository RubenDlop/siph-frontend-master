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

# =========================
# CORS (DEV / Angular / ManyChat)
# =========================
# Puedes definir CORS_ORIGINS en backend/.env separadas por coma
# Ej:
# CORS_ORIGINS=http://localhost:4200,http://127.0.0.1:4200,https://tu-dominio.com
raw = os.getenv("CORS_ORIGINS", "").strip()
allow_origins = [o.strip() for o in  raw.split(",") if o.strip()]

# fallback robusto
if not allow_origins:
    allow_origins = [
        "http://localhost:4200",
        "http://127.0.0.1:4200",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    # Permite localhost/127.0.0.1 con cualquier puerto en DEV
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
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
app.include_router(worker_applications.router)      # /worker-applications
app.include_router(technician_verification.router)  # /tech/verification

# =========================
# ADMIN routes
# =========================
app.include_router(admin_worker_applications.router)       # /admin/worker-applications
app.include_router(admin_technician_verification.router)   # /admin/tech/verification

# =========================
# MANYCHAT routes
# =========================
app.include_router(manychat.router)  # /integrations/manychat/*

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
