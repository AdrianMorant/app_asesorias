"""
Módulo de Seguridad Avanzada: Gestión de Tokens de Sesión y Cookies Seguras.
Proporciona generación de pares de tokens (Access y Refresh con jti), firma criptográfica HMAC-SHA256
y manejo de cookies HttpOnly con directivas de máxima seguridad (Strict, Secure, Paths dedicados).
"""

import os
import hmac
import json
import base64
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple
from fastapi import Response

from app.core.config import settings

# ---------------------------------------------------------------------------
# Configuración Criptográfica y de Expiración
# ---------------------------------------------------------------------------
SECRET_KEY: str = os.getenv(
    "SECRET_KEY",
    "konta-ai-advanced-security-session-secret-key-2026-compliance-pgc-aeat"
)

ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
REFRESH_TOKEN_EXPIRE_DAYS: int = 7

ACCESS_COOKIE_NAME: str = "access_token"
REFRESH_COOKIE_NAME: str = "refresh_token"
REFRESH_COOKIE_PATH: str = "/api/v1/auth/refresh"

# Determinación de directiva Secure según entorno
ENVIRONMENT: str = getattr(settings, "ENVIRONMENT", os.getenv("ENVIRONMENT", "development")).lower()
IS_PRODUCTION: bool = ENVIRONMENT in ("production", "prod", "staging")
COOKIE_SECURE: bool = os.getenv("COOKIE_SECURE", str(IS_PRODUCTION)).lower() in ("true", "1", "yes")
COOKIE_SAMESITE: str = "strict"


# ---------------------------------------------------------------------------
# Implementación Nativa de Tokens JWT (RFC 7519) sin Dependencias Externas
# ---------------------------------------------------------------------------
def _b64_encode(data: bytes) -> str:
    """Codifica en Base64 URL-safe sin padding."""
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64_decode(data: str) -> bytes:
    """Decodifica Base64 URL-safe restaurando el padding si es necesario."""
    rem = len(data) % 4
    if rem > 0:
        data += "=" * (4 - rem)
    return base64.urlsafe_b64decode(data.encode("utf-8"))


def _create_jwt_token(payload: Dict[str, Any], secret_key: str = SECRET_KEY) -> str:
    """Genera un token JWT firmado con algoritmo HS256."""
    header = {"alg": "HS256", "typ": "JWT"}
    header_b64 = _b64_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    
    signature_base = f"{header_b64}.{payload_b64}".encode("utf-8")
    signature = hmac.new(secret_key.encode("utf-8"), signature_base, hashlib.sha256).digest()
    signature_b64 = _b64_encode(signature)
    
    return f"{header_b64}.{payload_b64}.{signature_b64}"


def _verify_jwt_token(token: str, secret_key: str = SECRET_KEY) -> Optional[Dict[str, Any]]:
    """Verifica la firma y expiración de un token JWT HS256."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header_b64, payload_b64, signature_b64 = parts
        
        signature_base = f"{header_b64}.{payload_b64}".encode("utf-8")
        expected_sig = hmac.new(secret_key.encode("utf-8"), signature_base, hashlib.sha256).digest()
        actual_sig = _b64_decode(signature_b64)
        
        if not hmac.compare_digest(expected_sig, actual_sig):
            return None
            
        payload = json.loads(_b64_decode(payload_b64).decode("utf-8"))
        
        # Validar expiración (exp)
        exp = payload.get("exp")
        if exp is not None:
            now_ts = datetime.now(timezone.utc).timestamp()
            if now_ts > exp:
                return None  # Token expirado
                
        return payload
    except Exception:
        return None


# ---------------------------------------------------------------------------
# 1. Gestión de Tokens de Sesión
# ---------------------------------------------------------------------------
def create_access_token(
    subject: str,
    extra_claims: Optional[Dict[str, Any]] = None,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Crea un Access Token con vida útil corta (por defecto: 15 minutos).
    """
    now = datetime.now(timezone.utc)
    delta = expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    expire = now + delta
    
    payload: Dict[str, Any] = {
        "sub": str(subject),
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    if extra_claims:
        payload.update(extra_claims)
        
    return _create_jwt_token(payload)


def create_refresh_token(
    subject: str,
    extra_claims: Optional[Dict[str, Any]] = None,
    expires_delta: Optional[timedelta] = None
) -> Tuple[str, str]:
    """
    Crea un Refresh Token con vida útil larga (por defecto: 7 días) y un
    identificador criptográfico único jti para revocación y rotación.
    Retorna (token: str, jti: str).
    """
    now = datetime.now(timezone.utc)
    delta = expires_delta or timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    expire = now + delta
    
    jti = secrets.token_urlsafe(32)
    payload: Dict[str, Any] = {
        "sub": str(subject),
        "type": "refresh",
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    if extra_claims:
        payload.update(extra_claims)
        
    token = _create_jwt_token(payload)
    return token, jti


def create_session_tokens(
    subject: str,
    extra_claims: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Genera el par completo de tokens de sesión: Access Token (15 min)
    y Refresh Token (7 días con jti).
    """
    access_token = create_access_token(subject, extra_claims=extra_claims)
    refresh_token, jti = create_refresh_token(subject, extra_claims=extra_claims)
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "jti": jti,
        "token_type": "bearer",
        "access_expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "refresh_expires_in": REFRESH_TOKEN_EXPIRE_DAYS * 86400,
    }


def verify_session_token(
    token: str,
    expected_type: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Verifica un token de sesión. Si se especifica expected_type ('access' o 'refresh'),
    valida que coincida con el claim 'type'.
    """
    payload = _verify_jwt_token(token)
    if not payload:
        return None
    if expected_type and payload.get("type") != expected_type:
        return None
    return payload


# ---------------------------------------------------------------------------
# 2. Manejador de Cookies Seguras
# ---------------------------------------------------------------------------
def set_auth_cookies(
    response: Response,
    access_token: str,
    refresh_token: str,
    secure: Optional[bool] = None,
) -> None:
    """
    Configura las cookies de autenticación con directivas de máxima seguridad:
    - httponly=True (mitiga ataques XSS al impedir lectura desde JavaScript).
    - samesite="strict" (protección estricta contra ataques CSRF).
    - secure=True en producción o si se especifica explícitamente.
    - Refresh token con ruta restringida: path="/api/v1/auth/refresh".
    """
    is_secure = COOKIE_SECURE if secure is None else secure
    
    access_max_age = ACCESS_TOKEN_EXPIRE_MINUTES * 60
    refresh_max_age = REFRESH_TOKEN_EXPIRE_DAYS * 86400
    
    # 1. Cookie para el Access Token (disponible para todo el dominio)
    response.set_cookie(
        key=ACCESS_COOKIE_NAME,
        value=access_token,
        max_age=access_max_age,
        expires=access_max_age,
        path="/",
        httponly=True,
        secure=is_secure,
        samesite=COOKIE_SAMESITE,
    )
    
    # 2. Cookie para el Refresh Token (restringida exclusivamente al endpoint de refresco)
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        max_age=refresh_max_age,
        expires=refresh_max_age,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=is_secure,
        samesite=COOKIE_SAMESITE,
    )


def clear_auth_cookies(response: Response) -> None:
    """
    Elimina ambas cookies de sesión de forma inmediata (Max-Age=0, valor vacío)
    al cerrar sesión o revocar credenciales.
    """
    response.delete_cookie(
        key=ACCESS_COOKIE_NAME,
        path="/",
        httponly=True,
        samesite=COOKIE_SAMESITE,
    )
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        samesite=COOKIE_SAMESITE,
    )
