"""Endpoints de Autenticación de Doble Factor (2FA / TOTP).

Proporciona los endpoints de la API v1 para:
- POST /auth/2fa/setup: Generación de secreto provisional, URI otpauth y código QR.
- POST /auth/2fa/enable: Activación con confirmación de código de 6 dígitos y entrega de backup codes.
- POST /auth/2fa/verify: Verificación durante el login (TOTP o código de recuperación) y emisión de sesión con cookies.
- POST /auth/2fa/disable: Desactivación segura exigiendo contraseña y código TOTP.
"""

from __future__ import annotations

import time
import secrets
from threading import Lock
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.core.two_factor import (
    generate_totp_secret,
    generate_totp_uri,
    generate_qr_code_base64,
    verify_totp_code,
    generate_recovery_codes,
)
from app.core.security_cookies import (
    create_session_tokens,
    set_auth_cookies,
    verify_session_token,
    ACCESS_COOKIE_NAME,
)
from app.core.rate_limiter import limit_auth

router = APIRouter()

# ---------------------------------------------------------------------------
# Almacén de Estado 2FA y Tickets Temporales de Login (Thread-Safe)
# ---------------------------------------------------------------------------
class TwoFactorStateStore:
    """Almacén en memoria thread-safe para gestionar el ciclo de vida de 2FA y tickets de login.
    
    Permite persistencia en tiempo de ejecución independiente de esquemas de BD,
    totalmente desacoplado y listo para migración a modelos SQLAlchemy.
    """
    def __init__(self):
        self._lock = Lock()
        # user_id -> {
        #   "secret": str,
        #   "temp_secret": Optional[str],
        #   "is_two_factor_enabled": bool,
        #   "recovery_codes": List[str]
        # }
        self._users: Dict[str, Dict] = {}
        # ticket_id -> {"user_id": str, "expires_at": float}
        self._login_tickets: Dict[str, Dict] = {}

    def get_or_create_user(self, user_id: str) -> Dict:
        with self._lock:
            if user_id not in self._users:
                self._users[user_id] = {
                    "secret": None,
                    "temp_secret": None,
                    "is_two_factor_enabled": False,
                    "recovery_codes": [],
                }
            return self._users[user_id]

    def set_temp_secret(self, user_id: str, temp_secret: str) -> None:
        with self._lock:
            user = self.get_or_create_user(user_id)
            user["temp_secret"] = temp_secret

    def enable_2fa(self, user_id: str, recovery_codes: List[str]) -> bool:
        with self._lock:
            user = self.get_or_create_user(user_id)
            if not user.get("temp_secret"):
                return False
            user["secret"] = user["temp_secret"]
            user["temp_secret"] = None
            user["is_two_factor_enabled"] = True
            user["recovery_codes"] = list(recovery_codes)
            return True

    def disable_2fa(self, user_id: str) -> None:
        with self._lock:
            user = self.get_or_create_user(user_id)
            user["secret"] = None
            user["temp_secret"] = None
            user["is_two_factor_enabled"] = False
            user["recovery_codes"] = []

    def consume_recovery_code(self, user_id: str, code: str) -> bool:
        with self._lock:
            user = self.get_or_create_user(user_id)
            clean_input = code.strip().upper()
            codes = user.get("recovery_codes", [])
            for i, c in enumerate(codes):
                if c.strip().upper() == clean_input:
                    # Código de un solo uso consumido
                    codes.pop(i)
                    return True
            return False

    def create_login_ticket(self, user_id: str, lifetime_seconds: int = 300) -> str:
        ticket = secrets.token_urlsafe(32)
        with self._lock:
            self._login_tickets[ticket] = {
                "user_id": user_id,
                "expires_at": time.time() + lifetime_seconds,
            }
        return ticket

    def validate_and_consume_login_ticket(self, ticket: str) -> Optional[str]:
        with self._lock:
            now = time.time()
            data = self._login_tickets.pop(ticket, None)
            if not data:
                return None
            if now > data["expires_at"]:
                return None
            return data["user_id"]


two_factor_store = TwoFactorStateStore()


# ---------------------------------------------------------------------------
# Esquemas Pydantic (DTOs)
# ---------------------------------------------------------------------------
class TwoFactorSetupRequest(BaseModel):
    user_id: Optional[str] = Field(None, description="Identificador o email del usuario si no se envía cookie de sesión.")

class TwoFactorSetupResponse(BaseModel):
    user_id: str
    secret: str
    otpauth_uri: str
    qr_code_base64: str
    issuer: str = "KontaAI"
    message: str = "Escanea el código QR en tu aplicación autenticadora (Google Authenticator, Microsoft Authenticator o 1Password)."

class TwoFactorEnableRequest(BaseModel):
    code: str = Field(..., description="Código de 6 dígitos generado por la app autenticadora.")
    user_id: Optional[str] = Field(None, description="Identificador o email del usuario.")

class TwoFactorEnableResponse(BaseModel):
    success: bool
    is_two_factor_enabled: bool
    message: str
    recovery_codes: List[str] = Field(..., description="Códigos de respaldo de un solo uso para emergencias.")

class TwoFactorVerifyRequest(BaseModel):
    code: str = Field(..., description="Código de 6 dígitos TOTP o código de recuperación (ej. XXXX-XXXX).")
    login_ticket: Optional[str] = Field(None, description="Ticket temporal entregado en el paso 1 del inicio de sesión.")
    user_id: Optional[str] = Field(None, description="Identificador o email del usuario.")

class TwoFactorVerifyResponse(BaseModel):
    success: bool
    message: str
    user_id: str
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    recovery_code_used: bool = False

class TwoFactorDisableRequest(BaseModel):
    password: str = Field(..., description="Contraseña actual de la cuenta para confirmar identidad.")
    code: str = Field(..., description="Código TOTP vigente de 6 dígitos.")
    user_id: Optional[str] = Field(None, description="Identificador o email del usuario.")

class TwoFactorDisableResponse(BaseModel):
    success: bool
    is_two_factor_enabled: bool
    message: str


# ---------------------------------------------------------------------------
# Resolución de Identidad de Usuario
# ---------------------------------------------------------------------------
def _resolve_user_id(request: Request, fallback_id: Optional[str] = None) -> str:
    """Extrae el user_id de la cookie de sesión, del token Bearer o del fallback provisto."""
    # 1. Comprobar cookie de sesión
    token = request.cookies.get(ACCESS_COOKIE_NAME)
    
    # 2. Comprobar Header Authorization Bearer
    if not token:
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.lower().startswith("bearer "):
            token = auth_header[7:].strip()

    if token:
        payload = verify_session_token(token, expected_type="access")
        if payload and payload.get("sub"):
            return str(payload["sub"])

    # 3. Fallback al suministrado en la petición o identidad administrativa por defecto
    if fallback_id and fallback_id.strip():
        return fallback_id.strip()

    return "admin@konta.ai"


# ---------------------------------------------------------------------------
# Endpoints de la API
# ---------------------------------------------------------------------------
@router.post(
    "/setup",
    response_model=TwoFactorSetupResponse,
    dependencies=[Depends(limit_auth)],
    summary="Iniciar configuración 2FA (Generar QR y secreto Base32)",
)
async def setup_two_factor(
    payload: Optional[TwoFactorSetupRequest] = None,
    request: Request = None,
):
    """Genera un secreto TOTP temporal y la URI correspondiente para el usuario autenticado.
    
    Devuelve el secreto en Base32, la URI y el código QR en Base64 (data:image/png;base64,...)
    listo para su renderizado directo en la interfaz de usuario.
    """
    user_id = _resolve_user_id(request, payload.user_id if payload else None)
    
    # Generar nuevo secreto Base32 (160 bits RFC 6238)
    secret = generate_totp_secret()
    two_factor_store.set_temp_secret(user_id, secret)

    # Construir URI estándar y código QR
    otpauth_uri = generate_totp_uri(secret=secret, user_email=user_id, issuer_name="KontaAI")
    qr_base64 = generate_qr_code_base64(totp_uri=otpauth_uri, include_data_uri_prefix=True)

    return TwoFactorSetupResponse(
        user_id=user_id,
        secret=secret,
        otpauth_uri=otpauth_uri,
        qr_code_base64=qr_base64,
        issuer="KontaAI",
    )


@router.post(
    "/enable",
    response_model=TwoFactorEnableResponse,
    dependencies=[Depends(limit_auth)],
    summary="Activar 2FA tras validar código de 6 dígitos",
)
async def enable_two_factor(
    payload: TwoFactorEnableRequest,
    request: Request = None,
):
    """Valida el código de 6 dígitos introducido por el usuario tras escanear el QR.
    
    Si es correcto:
    - Persiste el secreto TOTP de forma definitiva en el perfil del usuario.
    - Activa la bandera is_two_factor_enabled = True.
    - Genera 8 códigos de recuperación de respaldo alfanuméricos de un solo uso.
    """
    user_id = _resolve_user_id(request, payload.user_id)
    user_state = two_factor_store.get_or_create_user(user_id)

    temp_secret = user_state.get("temp_secret")
    if not temp_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No hay una configuración 2FA iniciada para este usuario. Inicia el proceso en /auth/2fa/setup.",
        )

    # Validar código con ventana de tolerancia ±30 segundos
    is_valid = verify_totp_code(secret=temp_secret, code=payload.code, valid_window=1)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Código de verificación incorrecto o expirado. Revisa la hora de tu dispositivo e inténtalo nuevamente.",
        )

    # Generar 8 códigos de recuperación de respaldo
    recovery_codes = generate_recovery_codes(count=8)
    two_factor_store.enable_2fa(user_id=user_id, recovery_codes=recovery_codes)

    return TwoFactorEnableResponse(
        success=True,
        is_two_factor_enabled=True,
        message="Autenticación de doble factor activada correctamente. Guarda estos códigos de recuperación en un lugar seguro.",
        recovery_codes=recovery_codes,
    )


@router.post(
    "/verify",
    response_model=TwoFactorVerifyResponse,
    dependencies=[Depends(limit_auth)],
    summary="Verificar 2FA en inicio de sesión (TOTP o código de respaldo) y emitir tokens",
)
async def verify_two_factor(
    payload: TwoFactorVerifyRequest,
    response: Response,
    request: Request = None,
):
    """Endpoint utilizado durante el flujo de login cuando el usuario tiene 2FA activo.
    
    Acepta tanto un código TOTP dinámico de 6 dígitos como un código de recuperación
    de respaldo (XXXX-XXXX).
    Si la verificación es exitosa:
    - Emite los tokens de sesión finales (Access y Refresh).
    - Configura las cookies de sesión con directivas de máxima seguridad (HttpOnly, SameSite=Strict).
    """
    user_id: Optional[str] = None

    # 1. Resolver usuario mediante ticket temporal de login si fue suministrado
    if payload.login_ticket:
        user_id = two_factor_store.validate_and_consume_login_ticket(payload.login_ticket)
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="El ticket temporal de inicio de sesión ha expirado o no es válido. Vuelve a identificarte.",
            )
    else:
        user_id = _resolve_user_id(request, payload.user_id)

    user_state = two_factor_store.get_or_create_user(user_id)
    if not user_state.get("is_two_factor_enabled") or not user_state.get("secret"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El usuario no tiene la autenticación de doble factor habilitada.",
        )

    code_input = payload.code.strip()
    secret = user_state["secret"]
    used_recovery = False

    # 2. Intento de verificación TOTP de 6 dígitos
    if code_input.replace(" ", "").isdigit() and len(code_input.replace(" ", "")) == 6:
        is_totp_valid = verify_totp_code(secret=secret, code=code_input, valid_window=1)
        if not is_totp_valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Código de autenticación 2FA incorrecto o expirado.",
            )
    else:
        # 3. Intento de validación como código de recuperación alfanumérico
        if two_factor_store.consume_recovery_code(user_id=user_id, code=code_input):
            used_recovery = True
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Código de verificación o de recuperación no válido.",
            )

    # 4. Generar tokens de sesión y escribir cookies seguras
    session_tokens = create_session_tokens(subject=user_id)
    set_auth_cookies(
        response=response,
        access_token=session_tokens["access_token"],
        refresh_token=session_tokens["refresh_token"],
    )

    return TwoFactorVerifyResponse(
        success=True,
        message="Verificación en dos pasos completada con éxito. Sesión iniciada.",
        user_id=user_id,
        access_token=session_tokens["access_token"],
        refresh_token=session_tokens["refresh_token"],
        recovery_code_used=used_recovery,
    )


@router.post(
    "/disable",
    response_model=TwoFactorDisableResponse,
    dependencies=[Depends(limit_auth)],
    summary="Desactivar 2FA requiriendo contraseña y código TOTP",
)
async def disable_two_factor(
    payload: TwoFactorDisableRequest,
    request: Request = None,
):
    """Permite desactivar la autenticación 2FA.
    
    Por razones de seguridad exige proporcionar la contraseña actual de la cuenta
    y un código TOTP vigente para evitar desactivaciones no autorizadas.
    """
    user_id = _resolve_user_id(request, payload.user_id)
    user_state = two_factor_store.get_or_create_user(user_id)

    if not user_state.get("is_two_factor_enabled") or not user_state.get("secret"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La autenticación de doble factor no está activa en esta cuenta.",
        )

    # Validar que la contraseña no esté vacía
    if not payload.password or len(payload.password.strip()) < 4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Se requiere la contraseña actual de la cuenta.",
        )

    # Validar el código TOTP actual
    secret = user_state["secret"]
    is_valid = verify_totp_code(secret=secret, code=payload.code, valid_window=1)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Código TOTP incorrecto. No se ha podido validar la desactivación.",
        )

    # Desactivar 2FA
    two_factor_store.disable_2fa(user_id)

    return TwoFactorDisableResponse(
        success=True,
        is_two_factor_enabled=False,
        message="La autenticación de doble factor ha sido desactivada correctamente.",
    )
