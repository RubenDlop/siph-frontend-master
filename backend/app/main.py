import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import (
    auth,
    requests,
    reviews,
    worker_requests,
    worker_applications,
    workers_public,
    technician_verification,
    admin_technician_verification,
    admin_worker_applications,
    manychat,
)

app = FastAPI(title="SIPH API")


def _split_csv(value: str) -> list[str]:
    return [item.strip().rstrip("/") for item in value.split(",") if item.strip()]


raw_origins = os.getenv("CORS_ORIGINS", "").strip()
allow_origins = _split_csv(raw_origins) if raw_origins else []

if not allow_origins:
    allow_origins = [
        "http://localhost:4200",
        "http://127.0.0.1:4200",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://siph-frontend-master.netlify.app",
    ]

allow_origin_regex = (
    r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"
    r"|^https://.*\.netlify\.app$"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_origin_regex=allow_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

# =========================
# ROUTERS
# =========================
app.include_router(auth.router)
app.include_router(requests.router)
app.include_router(reviews.router)
app.include_router(workers_public.router)

app.include_router(worker_requests.router)
app.include_router(worker_applications.router)
app.include_router(technician_verification.router)

app.include_router(admin_worker_applications.router)
app.include_router(admin_technician_verification.router)

app.include_router(manychat.router)


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
