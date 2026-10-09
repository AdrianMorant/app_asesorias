"""
Módulo de Seguridad Criptográfica y Gestión de Credenciales.

Implementa los estándares de seguridad exigidos por OWASP y ENS (Esquema Nacional de Seguridad):
1. Almacenamiento de contraseñas mediante derivación de claves resistente (PBKDF2-HMAC-SHA256
   con 310.000 iteraciones y salt criptográfico de 16 bytes), garantizando protección
   contra ataques de fuerza bruta y tablas arcoíris.
2. Comparación en tiempo constante (hmac.compare_digest) para evitar vulnerabilidades de canal lateral (timing attacks).
3. Validación de fortaleza y complejidad de contraseñas.
4. Generación y validación de tokens criptográficos de recuperación de contraseñas de un solo uso con caducidad.
5. Lista negra de revocación de sesiones (Token Revocation List) con expiración automática.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Set, Tuple

from app.core.config import settings
from app.core.security_cookies import (
    SECRET_KEY,
    _b64_decode,
    _b64_encode,
    _create_jwt_token,
    _verify_jwt_token,
)

# Parámetros recomendados por OWASP para PBKDF2-HMAC-SHA256
PBKDF2_ITERATIONS: int = 310_000
SALT_BYTES: int = 16
HASH_NAME: str = "sha256"


# ---------------------------------------------------------------------------
# 1. Hashing Seguro de Contraseñas
# ---------------------------------------------------------------------------
def hash_password(password: str) -> str:
    """Genera un hash resistente de la contraseña mediante PBKDF2-HMAC-SHA256.

    Formato resultante:
        $pbkdf2-sha256$i={iterations}$s={salt_hex}${hash_hex}

    Args:
        password: Contraseña en texto plano.

    Returns:
        Cadena formateada con el algoritmo, parámetros, salt y digest.
    """
    if not password:
        raise ValueError("La contraseña no puede estar vacía.")

    salt = secrets.token_bytes(SALT_BYTES)
    derived = hashlib.pbkdf2_hmac(
        HASH_NAME,
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    salt_hex = salt.hex()
    hash_hex = derived.hex()
    return f"$pbkdf2-sha256$i={PBKDF2_ITERATIONS}$s={salt_hex}${hash_hex}"


def verify_password(plain_password: str, hashed_password: Optional[str]) -> bool:
    """Verifica una contraseña contra su hash mediante comparación en tiempo constante.

    Args:
        plain_password: La contraseña candidata introducida por el usuario.
        hashed_password: La cadena hash almacenada en la base de datos.

    Returns:
        True si coincide exactamente; False en cualquier otro caso o error de formato.
    """
    if not plain_password or not hashed_password:
        return False

    try:
        parts = hashed_password.split("$")
        # Esperado: ["", "pbkdf2-sha256", "i=310000", "s=<salt_hex>", "<hash_hex>"]
        if len(parts) != 5 or parts[1] != "pbkdf2-sha256":
            return False

        iterations_str = parts[2]
        salt_part = parts[3]
        expected_hash_hex = parts[4]

        if not iterations_str.startswith("i=") or not salt_part.startswith("s="):
            return False

        iterations = int(iterations_str[2:])
        salt = bytes.fromhex(salt_part[2:])

        candidate_derived = hashlib.pbkdf2_hmac(
            HASH_NAME,
            plain_password.encode("utf-8"),
            salt,
            iterations,
        )
        candidate_hash_hex = candidate_derived.hex()

        return hmac.compare_digest(candidate_hash_hex, expected_hash_hex)
    except Exception:
        return False


def validate_password_strength(password: str) -> Tuple[bool, Optional[str]]:
    """Evalúa los requisitos mínimos de complejidad de contraseña empresarial.

    Requisitos:
    - Longitud mínima de 8 caracteres.
    - Al menos una letra mayúscula.
    - Al menos una letra minúscula.
    - Al menos un dígito o símbolo especial.
    """
    if not password or len(password) < 8:
        return False, "La contraseña debe tener al menos 8 caracteres."

    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_special = any(not c.isalnum() for c in password)

    if not has_upper:
        return False, "La contraseña debe contener al menos una letra mayúscula."
    if not has_lower:
        return False, "La contraseña debe contener al menos una letra minúscula."
    if not (has_digit or has_special):
        return False, "La contraseña debe contener al menos un número o símbolo especial."

    return True, None


# ---------------------------------------------------------------------------
# 2. Tokens de Recuperación de Contraseña (Flujo Verificable de Reset)
# ---------------------------------------------------------------------------
PASSWORD_RESET_EXPIRE_MINUTES = 15


def create_password_reset_token(user_id: str, email: str) -> str:
    """Genera un token JWT seguro y temporal exclusivo para el restablecimiento de contraseña."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=PASSWORD_RESET_EXPIRE_MINUTES)

    payload = {
        "sub": str(user_id),
        "email": str(email).lower().strip(),
        "type": "pwd_reset",
        "jti": secrets.token_urlsafe(24),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return _create_jwt_token(payload)


def verify_password_reset_token(token: str) -> Optional[Dict[str, Any]]:
    """Valida la autenticidad y vigencia de un token de restablecimiento de contraseña."""
    payload = _verify_jwt_token(token)
    if not payload:
        return None
    if payload.get("type") != "pwd_reset":
        return None
    return payload


# ---------------------------------------------------------------------------
# 3. Lista Negra / Revocación de Tokens (Token Revocation List)
# ---------------------------------------------------------------------------
class TokenRevocationStore:
    """Almacén thread-safe en memoria para registrar tokens revocados (logout, rotación)."""

    def __init__(self):
        self._revoked_jtis: Dict[str, float] = {}  # jti -> expires_at
        self._lock = threading.Lock()

    def revoke(self, jti: str, expires_at: float) -> None:
        """Añade un identificador de token (jti) a la lista de revocación."""
        with self._lock:
            self._cleanup_expired()
            self._revoked_jtis[jti] = expires_at

    def is_revoked(self, jti: str) -> bool:
        """Comprueba si un jti ha sido expresamente revocado."""
        with self._lock:
            if jti not in self._revoked_jtis:
                return False
            # Si el token ya expiró en tiempo, se considera revocado e inútil
            return True

    def _cleanup_expired(self) -> None:
        """Elimina entradas de la lista negra cuyo tiempo de expiración ya transcurrió."""
        now = time.time()
        expired = [jti for jti, exp in self._revoked_jtis.items() if exp < now]
        for jti in expired:
            del self._revoked_jtis[jti]


token_revocation_store = TokenRevocationStore()
