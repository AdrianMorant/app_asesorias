"""
Endpoints Centralizados de Autenticación, Sesión, Recuperación y Auditoría WORM.

Proporciona la interfaz de la API REST para:
- POST /api/v1/auth/register: Registro con validación de complejidad y hash PBKDF2.
- POST /api/v1/auth/login: Inicio de sesión protegido contra fuerza bruta con soporte 2FA y cookies HttpOnly.
- POST /api/v1/auth/logout: Cierre de sesión con revocación activa de tokens en lista negra y eliminación de cookies.
- POST /api/v1/auth/refresh: Rotación segura de refresh tokens.
- GET  /api/v1/auth/me: Perfil del usuario autenticado y sus empresas asociadas.
- POST /api/v1/auth/forgot-password: Flujo de recuperación de contraseña verificable.
- POST /api/v1/auth/reset-password: Restablecimiento seguro con validación de token temporal.
- GET  /api/v1/auth/audit/verify: Comprobación criptográfica de integridad de la cadena WORM SHA-256.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional
import re
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_logger import log_security_event, verify_audit_log_integrity
from app.core.auth_deps import get_current_user, require_roles
from app.core.database import get_db
from app.core.rate_limiter import limit_auth
from app.core.security import (
    create_password_reset_token,
    hash_password,
    token_revocation_store,
    validate_password_strength,
    verify_password,
    verify_password_reset_token,
)
from app.core.security_cookies import (
    ACCESS_COOKIE_NAME,
    REFRESH_COOKIE_NAME,
    clear_auth_cookies,
    create_session_tokens,
    set_auth_cookies,
    verify_session_token,
)
from app.api.v1.endpoints.two_factor import two_factor_store
from app.models.company import Company
from app.models.user import User, UserRole, user_companies

router = APIRouter()


# ---------------------------------------------------------------------------
# Esquemas Pydantic (DTOs)
# ---------------------------------------------------------------------------
class UserRegisterRequest(BaseModel):
    email: str = Field(..., description="Correo electrónico del usuario")
    password: str = Field(..., min_length=8, description="Contraseña con mayúscula, minúscula y número/símbolo")
    full_name: str = Field(..., min_length=2)
    role: Optional[UserRole] = Field(default=UserRole.ADVISOR, description="Rol global inicial")
    advisor_firm_name: Optional[str] = Field(None, description="Nombre del despacho o gestoría")
    initial_company_cif: Optional[str] = None
    initial_company_name: Optional[str] = None

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        clean = v.strip().lower()
        if not re.match(r"^[\w\.\+\-]+@[\w\.\-]+\.[a-zA-Z]{2,}$", clean):
            raise ValueError("Formato de correo electrónico no válido.")
        return clean


class UserLoginRequest(BaseModel):
    email: str
    password: str


class RefreshTokenRequest(BaseModel):
    refresh_token: Optional[str] = None


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8)


class UserCompanySummary(BaseModel):
    company_id: str
    company_name: str
    cif: str
    role: str


class UserMeResponse(BaseModel):
    id: str
    email: str
    full_name: str
    global_role: str
    advisor_firm_name: Optional[str] = None
    is_active: bool
    companies: List[UserCompanySummary] = []


# ---------------------------------------------------------------------------
# Endpoints de Autenticación
# ---------------------------------------------------------------------------
@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(limit_auth)],
    summary="Registro de nuevo usuario con hash resistente PBKDF2",
)
async def register_user(
    payload: UserRegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    # 1. Validar complejidad de contraseña
    is_strong, error_msg = validate_password_strength(payload.password)
    if not is_strong:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg,
        )

    # 2. Comprobar si ya existe el correo
    clean_email = payload.email.lower().strip()
    res = await db.execute(select(User).where(User.email == clean_email))
    existing = res.scalars().first()
    if existing:
        log_security_event(
            action="USER_REGISTER_DUPLICATE_ATTEMPT",
            request=request,
            user_id=clean_email,
            status="DENIED",
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe una cuenta registrada con este correo electrónico.",
        )

    # 3. Hashear contraseña mediante PBKDF2-HMAC-SHA256
    pwd_hash = hash_password(payload.password)

    # 4. Crear entidad de usuario
    user_id = str(uuid.uuid4())
    new_user = User(
        id=user_id,
        email=clean_email,
        full_name=payload.full_name.strip(),
        hashed_password=pwd_hash,
        global_role=payload.role.value if payload.role else UserRole.ADVISOR.value,
        advisor_firm_name=payload.advisor_firm_name,
        is_active=True,
    )
    db.add(new_user)
    await db.commit()

    # 5. Si se indicó empresa inicial, crearla o vincularla
    if payload.initial_company_cif and payload.initial_company_name:
        comp_res = await db.execute(
            select(Company).where(Company.cif == payload.initial_company_cif.strip().upper())
        )
        comp = comp_res.scalars().first()
        if not comp:
            comp = Company(
                id=f"comp-{uuid.uuid4().hex[:8]}",
                cif=payload.initial_company_cif.strip().upper(),
                razon_social=payload.initial_company_name.strip(),
                domicilio_fiscal="Domicilio no especificado",
                is_active=True,
                plan_cuentas_longitud=9,
            )
            db.add(comp)
            await db.commit()

        # Insertar vinculación en user_companies
        await db.execute(
            user_companies.insert().values(
                user_id=user_id,
                company_id=comp.id,
                role=new_user.global_role,
            )
        )
        await db.commit()

    log_security_event(
        action="USER_REGISTER_SUCCESS",
        resource_id=user_id,
        request=request,
        user_id=user_id,
        status="SUCCESS",
        details={"email": clean_email, "role": new_user.global_role},
    )

    return {
        "success": True,
        "message": "Usuario registrado correctamente.",
        "user_id": user_id,
        "email": clean_email,
        "role": new_user.global_role,
    }


@router.post(
    "/login",
    dependencies=[Depends(limit_auth)],
    summary="Inicio de sesión seguro con detección 2FA y emisión de tokens/cookies",
)
async def login_user(
    payload: UserLoginRequest,
    response: Response,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    clean_email = payload.email.lower().strip()

    # 1. Buscar usuario
    res = await db.execute(select(User).where(User.email == clean_email))
    user = res.scalars().first()

    # 2. Verificar existencia y contraseña
    if not user or not verify_password(payload.password, user.hashed_password):
        log_security_event(
            action="LOGIN_FAILED",
            request=request,
            user_id=clean_email,
            status="DENIED",
            details={"reason": "Credenciales inválidas"},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales de acceso incorrectas.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. Comprobar cuenta activa
    if not user.is_active:
        log_security_event(
            action="LOGIN_ACCOUNT_INACTIVE",
            request=request,
            user_id=user.id,
            status="DENIED",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La cuenta se encuentra inactiva o bloqueada. Contacte con soporte.",
        )

    # 4. Comprobar si requiere 2FA (TOTP)
    user_state = two_factor_store.get_or_create_user(user.id)
    is_2fa_enabled = user_state.get("is_two_factor_enabled", False)

    # Si es SUPERADMIN y 2FA está activo (o se requiere segundo factor)
    if is_2fa_enabled:
        ticket = two_factor_store.create_login_ticket(user.id)
        log_security_event(
            action="LOGIN_2FA_CHALLENGE_ISSUED",
            request=request,
            user_id=user.id,
            status="SUCCESS",
        )
        return {
            "requires_2fa": True,
            "login_ticket": ticket,
            "message": "Se requiere verificación en dos pasos (código de 6 dígitos de tu app autenticadora).",
        }

    # 5. Generar par de tokens JWT
    tokens = create_session_tokens(
        subject=user.id,
        extra_claims={
            "email": user.email,
            "role": user.global_role,
            "name": user.full_name,
        },
    )

    # 6. Escribir cookies seguras (HttpOnly, SameSite=Strict)
    set_auth_cookies(
        response=response,
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
    )

    log_security_event(
        action="LOGIN_SUCCESS",
        resource_id=user.id,
        request=request,
        user_id=user.id,
        status="SUCCESS",
        details={"role": user.global_role},
    )

    return {
        "requires_2fa": False,
        "success": True,
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.global_role,
            "advisor_firm_name": user.advisor_firm_name,
        },
    }


@router.post(
    "/logout",
    summary="Cierre de sesión, revocación activa de token y eliminación de cookies",
)
async def logout_user(
    response: Response,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    # 1. Extraer y revocar token si está presente
    token = request.cookies.get(ACCESS_COOKIE_NAME)
    if not token:
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.lower().startswith("bearer "):
            token = auth_header[7:].strip()

    user_id = "anonymous"
    if token:
        payload = verify_session_token(token, expected_type="access")
        if payload:
            user_id = payload.get("sub", "anonymous")
            jti = payload.get("jti")
            exp = payload.get("exp", time.time() + 3600)
            if jti:
                token_revocation_store.revoke(jti, exp)

    # 2. Borrar cookies HttpOnly
    clear_auth_cookies(response)

    log_security_event(
        action="LOGOUT",
        request=request,
        user_id=user_id,
        status="SUCCESS",
    )

    return {"success": True, "message": "Sesión cerrada correctamente."}


@router.post(
    "/refresh",
    summary="Refresco y rotación de Access Token",
)
async def refresh_session(
    response: Response,
    request: Request,
    payload: Optional[RefreshTokenRequest] = None,
    db: AsyncSession = Depends(get_db),
):
    # Obtener token de refresco de cookie o body
    token = request.cookies.get(REFRESH_COOKIE_NAME)
    if not token and payload and payload.refresh_token:
        token = payload.refresh_token

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de refresco ausente o inválido.",
        )

    decoded = verify_session_token(token, expected_type="refresh")
    if not decoded:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de refresco inválido o expirado.",
        )

    jti = decoded.get("jti")
    if jti and token_revocation_store.is_revoked(jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El token de refresco ya ha sido revocado.",
        )

    # Rotar: revocar el refresh token anterior
    if jti:
        token_revocation_store.revoke(jti, decoded.get("exp", time.time() + 86400 * 7))

    user_id = decoded["sub"]
    res = await db.execute(select(User).where(User.id == user_id))
    user = res.scalars().first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado o inactivo.",
        )

    # Generar nuevo par de tokens
    tokens = create_session_tokens(
        subject=user.id,
        extra_claims={
            "email": user.email,
            "role": user.global_role,
            "name": user.full_name,
        },
    )

    set_auth_cookies(
        response=response,
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
    )

    return {
        "success": True,
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "token_type": "bearer",
    }


@router.get(
    "/me",
    response_model=UserMeResponse,
    summary="Obtener perfil del usuario autenticado y empresas asignadas",
)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Obtener empresas asignadas y sus roles específicos
    res = await db.execute(
        select(
            Company.id,
            Company.razon_social,
            Company.cif,
            user_companies.c.role,
        )
        .join(user_companies, Company.id == user_companies.c.company_id)
        .where(user_companies.c.user_id == current_user.id)
    )
    rows = res.all()

    companies_list = [
        UserCompanySummary(
            company_id=r[0],
            company_name=r[1],
            cif=r[2],
            role=r[3],
        )
        for r in rows
    ]

    return UserMeResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        global_role=current_user.global_role,
        advisor_firm_name=current_user.advisor_firm_name,
        is_active=current_user.is_active,
        companies=companies_list,
    )


@router.post(
    "/forgot-password",
    dependencies=[Depends(limit_auth)],
    summary="Solicitar restablecimiento de contraseña mediante token firmado",
)
async def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    clean_email = payload.email.lower().strip()
    res = await db.execute(select(User).where(User.email == clean_email))
    user = res.scalars().first()

    # Por seguridad, no revelar si el email existe o no si no lo encuentra
    if not user:
        return {
            "success": True,
            "message": "Si el correo está registrado, se ha generado el enlace de recuperación.",
        }

    reset_token = create_password_reset_token(user.id, user.email)
    log_security_event(
        action="PASSWORD_RESET_REQUESTED",
        request=request,
        user_id=user.id,
        status="SUCCESS",
    )

    return {
        "success": True,
        "message": "Token de recuperación generado con éxito (válido durante 15 minutos).",
        "reset_token": reset_token,
    }


@router.post(
    "/reset-password",
    dependencies=[Depends(limit_auth)],
    summary="Restablecer contraseña mediante token de recuperación",
)
async def reset_password(
    payload: ResetPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    # 1. Validar token
    decoded = verify_password_reset_token(payload.token)
    if not decoded:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El token de recuperación es inválido o ha expirado.",
        )

    # 2. Validar fortaleza de la nueva contraseña
    is_strong, err = validate_password_strength(payload.new_password)
    if not is_strong:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err,
        )

    user_id = decoded["sub"]
    res = await db.execute(select(User).where(User.id == user_id))
    user = res.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado.",
        )

    # 3. Actualizar hash
    user.hashed_password = hash_password(payload.new_password)
    await db.commit()

    log_security_event(
        action="PASSWORD_RESET_COMPLETED",
        resource_id=user.id,
        request=request,
        user_id=user.id,
        status="SUCCESS",
    )

    return {
        "success": True,
        "message": "Contraseña actualizada correctamente. Puede iniciar sesión ahora.",
    }


# ---------------------------------------------------------------------------
# Diagnóstico y Verificación Criptográfica de Auditoría WORM (SHA-256)
# ---------------------------------------------------------------------------
@router.get(
    "/audit/verify",
    summary="Verificación matemática de integridad de la cadena WORM SHA-256",
)
async def verify_audit_chain(
    current_user: User = Depends(get_current_user),
):
    # Exigir rol de auditoría, asesoría o superadministración
    privileged_roles = {
        UserRole.SUPERADMIN.value,
        UserRole.ADVISOR.value,
        UserRole.AUDITOR_READONLY.value,
    }
    if current_user.global_role not in privileged_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los roles de Auditoría, Asesoría o Administración pueden verificar la cadena de logs.",
        )

    is_valid, count, error = verify_audit_log_integrity()

    return {
        "is_valid": is_valid,
        "total_records_checked": count,
        "chain_status": "INTACT" if is_valid else "COMPROMISED",
        "cryptographic_algorithm": "SHA-256 Chained WORM",
        "error_details": error,
        "verified_by_user": current_user.email,
    }
