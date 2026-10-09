"""
Módulo de Dependencias de Autenticación y Control de Acceso Basado en Roles (RBAC).

Aplica las directivas de seguridad en el backend para:
1. Extracción e inspección rigurosa de tokens de sesión JWT (Cookies seguras y Header Bearer).
2. Verificación de revocación activa de tokens (Token Revocation List).
3. Verificación de segregación de funciones según jerarquía de roles (RBAC).
4. Aislamiento estricto multi-empresa (Multi-Tenant): Prevención de accesos cruzados entre empresas clientes.
5. Soporte de compatibilidad controlada para suites de prueba automatizadas.
"""

from __future__ import annotations

from typing import Callable, List, Optional, Set
from fastapi import Depends, Header, HTTPException, Path, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import os
from app.core.config import settings
from app.core.database import get_db
from app.core.security import token_revocation_store
from app.core.security_cookies import (
    ACCESS_COOKIE_NAME,
    verify_session_token,
)
from app.models.user import User, UserRole, user_companies


# Jerarquía numérica de roles para evaluación de privilegios mínimos
ROLE_HIERARCHY = {
    UserRole.SUPERADMIN.value: 100,
    UserRole.ADVISOR.value: 80,
    UserRole.COMPANY_ADMIN.value: 70,
    UserRole.ACCOUNTANT.value: 50,
    UserRole.INVOICING.value: 30,
    UserRole.AUDITOR_READONLY.value: 10,
}


def _extract_token_from_request(request: Request) -> Optional[str]:
    """Extrae el token JWT desde la cookie HttpOnly o el header Authorization."""
    # 1. Cookie HttpOnly
    token = request.cookies.get(ACCESS_COOKIE_NAME)
    if token:
        return token

    # 2. Header Authorization Bearer
    auth_header = request.headers.get("authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()

    return None


async def get_current_user_optional(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_dev_user_email: Optional[str] = Header(None, alias="X-Dev-User-Email"),
    x_dev_user_role: Optional[str] = Header(None, alias="X-Dev-User-Role"),
) -> Optional[User]:
    """Resuelve el usuario actual si hay credenciales válidas, o None si no las hay.

    Permite llamadas anónimas seguras en endpoints públicos o con autenticación flexible.
    """
    token = _extract_token_from_request(request)

    if token:
        payload = verify_session_token(token, expected_type="access")
        if payload:
            jti = payload.get("jti")
            if jti and await token_revocation_store.is_revoked_persistent(jti, db=db):
                return None

            user_id = payload.get("sub")
            if user_id:
                # Buscar por ID o por Email
                res = await db.execute(
                    select(User).where((User.id == str(user_id)) | (User.email == str(user_id)))
                )
                user = res.scalars().first()
                if user and user.is_active:
                    return user

    # Modo de compatibilidad exclusivo para tests y desarrollo local (deshabilitado en producción)
    is_prod = getattr(settings, "ENVIRONMENT", os.getenv("ENVIRONMENT", "development")).lower() in ("production", "prod", "staging")
    if not is_prod and x_dev_user_email:
        res = await db.execute(select(User).where(User.email == x_dev_user_email.strip()))
        user = res.scalars().first()
        if user:
            # Nunca sobreescribir el rol de un usuario existente con un header arbitrario
            return user
        # Si se especificó rol en el header de desarrollo para usuario no persistido en tests
        role = x_dev_user_role or UserRole.SUPERADMIN.value
        return User(
            id=f"dev-{x_dev_user_email}",
            email=x_dev_user_email,
            full_name="Usuario de Prueba",
            global_role=role,
            is_active=True,
        )

    return None


async def get_current_user(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_optional),
) -> User:
    """Exige que la petición esté autenticada. Lanza HTTP 401 si no hay sesión válida."""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticación requerida. Por favor, inicie sesión.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user


def require_roles(*allowed_roles: UserRole | str) -> Callable:
    """Generador de dependencias para validar que el rol global del usuario cumpla los privilegios.

    Ejemplo:
        @router.delete("/companies/{id}", dependencies=[Depends(require_roles(UserRole.SUPERADMIN))])
    """
    allowed_values = {r.value if isinstance(r, UserRole) else str(r) for r in allowed_roles}

    async def role_checker(
        request: Request,
        current_user: User = Depends(get_current_user),
    ) -> User:
        # SUPERADMIN siempre tiene acceso irrestricto
        if current_user.global_role == UserRole.SUPERADMIN.value:
            return current_user

        if current_user.global_role not in allowed_values:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permisos insuficientes. Requiere uno de los siguientes roles: {', '.join(allowed_values)}.",
            )
        return current_user

    return role_checker


async def verify_company_access(
    company_id: str,
    user: User,
    db: AsyncSession,
    min_role: Optional[UserRole] = None,
) -> bool:
    """Comprueba en base de datos si el usuario tiene asignada la empresa y el rol suficiente."""
    # 1. SUPERADMIN tiene acceso universal
    if user.global_role == UserRole.SUPERADMIN.value:
        return True

    # 2. Consultar tabla user_companies
    res = await db.execute(
        select(user_companies.c.role).where(
            user_companies.c.user_id == user.id,
            user_companies.c.company_id == company_id,
        )
    )
    row = res.first()

    # Si no tiene vinculación directa con la empresa
    if not row:
        # Asesores pueden tener vinculación global o mediante asesoría
        if user.global_role == UserRole.ADVISOR.value:
            return True
        return False

    user_company_role = row[0]

    # 3. Validar jerarquía si se solicita un rol mínimo
    if min_role:
        min_level = ROLE_HIERARCHY.get(min_role.value, 0)
        user_level = max(
            ROLE_HIERARCHY.get(user_company_role, 0),
            ROLE_HIERARCHY.get(user.global_role, 0),
        )
        return user_level >= min_level

    return True


def require_company_permission(min_role: Optional[UserRole] = None) -> Callable:
    """Valida el aislamiento multi-tenant de la empresa solicitada en la ruta.

    Asegura que el usuario no pueda consultar ni modificar datos de empresas ajenas.
    """
    async def checker(
        company_id: str = Path(..., description="ID de la empresa fiscal"),
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        has_access = await verify_company_access(
            company_id=company_id,
            user=current_user,
            db=db,
            min_role=min_role,
        )
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acceso denegado: No dispone de permisos sobre la empresa {company_id}.",
            )
        return current_user

    return checker
