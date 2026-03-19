from __future__ import annotations

import os
from datetime import datetime
from typing import Optional, Any, Dict, List, Tuple

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from jwt import PyJWKClient
from jwt.exceptions import InvalidTokenError
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.database import get_db
from ..core.deps import get_current_user
from ..core.security import create_access_token, hash_password, verify_password
from ..models import User
from ..schemas.auth import AuthResponse, LoginRequest, RegisterRequest

router = APIRouter(prefix="/auth", tags=["auth"])


class GoogleLoginRequest(BaseModel):
    credential: str


class AzureExchangeRequest(BaseModel):
    access_token: str


class MeResponse(BaseModel):
    id: int
    first_name: str
    last_name: str
    email: str
    role: str
    is_active: bool
    created_at: Optional[datetime] = None
    auth_provider: Optional[str] = None
    azure_oid: Optional[str] = None

    class Config:
        from_attributes = True


# =========================================================
# HELPERS
# =========================================================
def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _normalize_email(value: Optional[str]) -> str:
    return (value or "").strip().lower()


def _split_name(
    full_name: str,
    given_name: Optional[str] = None,
    family_name: Optional[str] = None,
) -> Tuple[str, str]:
    gn = (given_name or "").strip()
    fn = (family_name or "").strip()

    if gn or fn:
        return gn or "Usuario", fn or "Microsoft"

    full = (full_name or "").strip()
    if not full:
        return "Usuario", "Microsoft"

    parts = full.split()
    if len(parts) == 1:
        return parts[0], "Microsoft"

    return parts[0], " ".join(parts[1:])


def _resolve_siph_role(roles: List[str], existing_user: Optional[User] = None) -> str:
    normalized = {str(r).strip().upper() for r in (roles or []) if str(r).strip()}

    if "ADMIN" in normalized:
        return "ADMIN"
    if "WORKER" in normalized:
        return "WORKER"
    if "USER" in normalized:
        return "USER"

    if existing_user and existing_user.role:
        return str(existing_user.role).strip().upper()

    return "USER"


def _verify_azure_access_token(access_token: str) -> Dict[str, Any]:
    tenant_id = _env("AZURE_TENANT_ID")
    api_client_id = _env("AZURE_API_CLIENT_ID")
    spa_client_id = _env("AZURE_SPA_CLIENT_ID")

    if not tenant_id or not api_client_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Falta configurar AZURE_TENANT_ID o AZURE_API_CLIENT_ID en el backend.",
        )

    jwks_url = f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys"
    allowed_audiences = [api_client_id, f"api://{api_client_id}"]
    allowed_issuers = {
        f"https://login.microsoftonline.com/{tenant_id}/v2.0",
        f"https://sts.windows.net/{tenant_id}/",
    }

    try:
        jwk_client = PyJWKClient(jwks_url)
        signing_key = jwk_client.get_signing_key_from_jwt(access_token)

        claims = jwt.decode(
            access_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=allowed_audiences,
            options={
                "require": ["exp", "aud", "iss"],
                "verify_signature": True,
                "verify_exp": True,
                "verify_aud": True,
                "verify_iss": False,
            },
        )
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de Azure inválido.",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No se pudo validar el token de Azure.",
        ) from exc

    iss = str(claims.get("iss") or "").strip()
    tid = str(claims.get("tid") or "").strip()
    actor_app = str(claims.get("azp") or claims.get("appid") or "").strip()

    if iss not in allowed_issuers:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Issuer de Azure no permitido.",
        )

    if tid != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tenant de Azure no permitido.",
        )

    if spa_client_id and actor_app and actor_app != spa_client_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El token no fue emitido para el cliente SPA configurado.",
        )

    scp_raw = str(claims.get("scp") or "").strip()
    scopes = set(scp_raw.split()) if scp_raw else set()
    if "access_as_user" not in scopes:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El token de Azure no contiene el scope access_as_user.",
        )

    return claims


# =========================================================
# AUTH LOCAL
# =========================================================
@router.post("/register", response_model=AuthResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> AuthResponse:
    email = _normalize_email(payload.email)

    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El correo ya está registrado.",
        )

    user = User(
        first_name=payload.first_name.strip(),
        last_name=payload.last_name.strip(),
        email=email,
        password_hash=hash_password(payload.password),
        auth_provider="LOCAL",
        role="USER",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.email)
    return AuthResponse(access_token=token)


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
    email = _normalize_email(payload.email)
    user = db.query(User).filter(User.email == email).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas.",
        )

    if user.auth_provider == "AZURE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Esta cuenta debe iniciar sesión con Microsoft.",
        )

    if user.auth_provider == "GOOGLE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Esta cuenta debe iniciar sesión con Google.",
        )

    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario inactivo.",
        )

    token = create_access_token(user.email)
    return AuthResponse(access_token=token)


# =========================================================
# AUTH GOOGLE
# =========================================================
@router.post("/google", response_model=AuthResponse)
def login_with_google(payload: GoogleLoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
    google_client_id = (settings.google_client_id or "").strip()
    if not google_client_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GOOGLE_CLIENT_ID no está configurado en el backend.",
        )

    try:
        info = id_token.verify_oauth2_token(
            payload.credential,
            google_requests.Request(),
            google_client_id,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de Google inválido.",
        ) from exc

    email = _normalize_email(info.get("email"))
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google no devolvió email.",
        )

    first_name = (info.get("given_name") or "").strip()
    last_name = (info.get("family_name") or "").strip()
    google_sub = str(info.get("sub") or "").strip()

    user = db.query(User).filter(User.email == email).first()

    if not user:
        user = User(
            first_name=first_name or "Usuario",
            last_name=last_name or "Google",
            email=email,
            password_hash=hash_password(f"GOOGLE::{google_sub}"),
            auth_provider="GOOGLE",
            role="USER",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        user.first_name = first_name or user.first_name
        user.last_name = last_name or user.last_name
        user.auth_provider = "GOOGLE"
        db.commit()
        db.refresh(user)

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario inactivo.",
        )

    token = create_access_token(user.email)
    return AuthResponse(access_token=token)


# =========================================================
# AUTH AZURE / MICROSOFT ENTRA ID
# =========================================================
@router.post("/azure/exchange", response_model=AuthResponse)
def exchange_azure_token(
    payload: AzureExchangeRequest,
    db: Session = Depends(get_db),
) -> AuthResponse:
    claims = _verify_azure_access_token(payload.access_token)

    oid = str(claims.get("oid") or "").strip()
    email = _normalize_email(
        claims.get("preferred_username")
        or claims.get("upn")
        or claims.get("email")
    )

    if not oid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El token de Azure no trae oid.",
        )

    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El token de Azure no trae email utilizable.",
        )

    user = (
        db.query(User)
        .filter(or_(User.azure_oid == oid, User.email == email))
        .first()
    )

    first_name, last_name = _split_name(
        full_name=str(claims.get("name") or "").strip(),
        given_name=claims.get("given_name"),
        family_name=claims.get("family_name"),
    )

    roles = claims.get("roles") or []
    if not isinstance(roles, list):
        roles = [str(roles)]

    siph_role = _resolve_siph_role(roles, user)

    if not user:
        user = User(
            first_name=first_name,
            last_name=last_name,
            email=email,
            password_hash=hash_password(f"AZURE::{oid}"),
            azure_oid=oid,
            auth_provider="AZURE",
            role=siph_role,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        user.azure_oid = oid
        user.auth_provider = "AZURE"
        user.first_name = first_name or user.first_name
        user.last_name = last_name or user.last_name
        user.email = email or user.email
        user.role = siph_role
        db.commit()
        db.refresh(user)

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario inactivo.",
        )

    token = create_access_token(user.email)
    return AuthResponse(access_token=token)


@router.get("/me", response_model=MeResponse)
def me(current_user: User = Depends(get_current_user)) -> MeResponse:
    return current_user
