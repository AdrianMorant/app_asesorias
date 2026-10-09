"""Módulo de Autenticación de Doble Factor (2FA / TOTP).

Implementa las directivas de seguridad para verificación de dos pasos basadas
en el estándar RFC 6238 (TOTP - Time-Based One-Time Password Algorithm):
1. Generación de secretos seguros en Base32 (160 bits de entropía).
2. Construcción de URIs estándar de aprovisionamiento 'otpauth://totp/...'.
3. Generación y renderizado de códigos QR en formato PNG codificados en base64
   para su consumo directo en componentes frontend.
4. Verificación de códigos de 6 dígitos con ventana de tolerancia configurable
   (±30 segundos / valid_window=1 por defecto) para mitigar desfases horarios.
5. Generación criptográficamente segura de códigos de recuperación de un solo uso
   (códigos alfanuméricos de respaldo).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import io
import re
import secrets
import struct
import time
import urllib.parse
from typing import List, Optional

try:
    import pyotp
except ImportError:  # pragma: no cover
    pyotp = None

try:
    import qrcode
    from qrcode.image.pure import PyPNGImage
except ImportError:  # pragma: no cover
    qrcode = None
    PyPNGImage = None

# Alfabeto alfanumérico no ambiguo para códigos de recuperación (excluye 0, O, 1, I, L)
RECOVERY_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"


def generate_totp_secret() -> str:
    """Genera una clave secreta aleatoria en base32 compatible con RFC 6238.
    
    Genera 20 bytes (160 bits) de entropía criptográfica, la recomendación oficial
    para algoritmos HMAC-SHA1 en TOTP, codificados en formato Base32 sin padding.
    
    Returns:
        Cadena de texto en Base32 de 32 caracteres (alfabeto A-Z, 2-7).
    """
    if pyotp is not None:
        return pyotp.random_base32(length=32)
    
    # Fallback criptográfico nativo utilizando secrets
    random_bytes = secrets.token_bytes(20)
    return base64.b32encode(random_bytes).decode("ascii").rstrip("=").upper()


def generate_totp_uri(
    secret: str,
    user_email: str,
    issuer_name: str = "KontaAI",
) -> str:
    """Genera la URI estándar de aprovisionamiento 'otpauth://totp/...'.
    
    Compatible con Google Authenticator, Microsoft Authenticator, 1Password, etc.
    
    Args:
        secret: Clave secreta en Base32.
        user_email: Correo electrónico o identificador del usuario.
        issuer_name: Nombre del emisor o plataforma (por defecto "KontaAI").
        
    Returns:
        URI formateada según la especificación otpauth.
    """
    clean_secret = secret.strip().replace(" ", "").upper()
    clean_email = user_email.strip()
    clean_issuer = issuer_name.strip()
    
    if pyotp is not None:
        totp = pyotp.TOTP(clean_secret, interval=30, digits=6)
        return totp.provisioning_uri(name=clean_email, issuer_name=clean_issuer)
    
    # Construcción nativa de la URI estándar
    label = f"{urllib.parse.quote(clean_issuer)}:{urllib.parse.quote(clean_email)}"
    query_params = urllib.parse.urlencode({
        "secret": clean_secret,
        "issuer": clean_issuer,
        "algorithm": "SHA1",
        "digits": 6,
        "period": 30,
    })
    return f"otpauth://totp/{label}?{query_params}"


def generate_qr_code_base64(
    totp_uri: str,
    include_data_uri_prefix: bool = True,
) -> str:
    """Convierte la URI TOTP en una imagen PNG codificada en base64.
    
    Permite mostrar el código QR directamente en el navegador del usuario
    mediante un elemento <img src="data:image/png;base64,..." />.
    
    Args:
        totp_uri: URI de aprovisionamiento 'otpauth://totp/...'.
        include_data_uri_prefix: Si es True, incluye el prefijo
            'data:image/png;base64,' para uso directo en etiquetas img HTML.
            
    Returns:
        Cadena con la imagen PNG codificada en base64.
    """
    if qrcode is None:
        raise RuntimeError(
            "El paquete 'qrcode' no está instalado en el entorno. "
            "Ejecuta 'pip install qrcode[pil]' para habilitar la generación de QR."
        )

    # Intentar generar imagen PNG con PIL o PyPNGImage
    buffer = io.BytesIO()
    try:
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=8,
            border=3,
        )
        qr.add_data(totp_uri)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        img.save(buffer, format="PNG")
    except Exception:
        # Fallback usando PyPNGImage si PIL no estuviese presente
        if PyPNGImage is not None:
            qr = qrcode.QRCode(
                version=None,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=8,
                border=3,
                image_factory=PyPNGImage,
            )
            qr.add_data(totp_uri)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buffer = io.BytesIO()
            img.save(buffer)
        else:
            raise

    png_bytes = buffer.getvalue()
    b64_string = base64.b64encode(png_bytes).decode("ascii")

    if include_data_uri_prefix:
        return f"data:image/png;base64,{b64_string}"
    return b64_string


def _verify_native_totp(
    secret: str,
    code: str,
    valid_window: int = 1,
    period: int = 30,
) -> bool:
    """Implementación matemática pura de verificación RFC 6238 (TOTP)."""
    try:
        # Ajustar padding a múltiplo de 8 para base32decode
        padding_needed = (8 - len(secret) % 8) % 8
        padded_secret = secret + ("=" * padding_needed)
        key = base64.b32decode(padded_secret, casefold=True)

        current_time = int(time.time())
        current_counter = current_time // period

        for offset in range(-valid_window, valid_window + 1):
            counter = current_counter + offset
            counter_bytes = struct.pack(">Q", counter)
            hmac_digest = hmac.new(key, counter_bytes, hashlib.sha1).digest()
            dynamic_offset = hmac_digest[-1] & 0x0F
            truncated_hash = (
                struct.unpack(">I", hmac_digest[dynamic_offset : dynamic_offset + 4])[0]
                & 0x7FFFFFFF
            )
            expected_code = f"{(truncated_hash % 1000000):06d}"
            if hmac.compare_digest(expected_code, code):
                return True
        return False
    except Exception:
        return False


def verify_totp_code(
    secret: str,
    code: str,
    valid_window: int = 1,
) -> bool:
    """Verifica un código de 6 dígitos introducido por el usuario.
    
    Aplica una ventana de tolerancia de ±30 segundos por defecto (valid_window = 1),
    comprobando la marca de tiempo actual, el intervalo previo (-30s) y el
    posterior (+30s), para compensar posibles desfases horarios entre el
    dispositivo móvil del usuario y el servidor.
    
    Args:
        secret: Clave secreta TOTP en Base32.
        code: Código de 6 dígitos numéricos ingresado por el usuario.
        valid_window: Ventana de tolerancia en periodos de 30s (default: 1 = ±30s).
        
    Returns:
        True si el código es válido para la ventana temporal; False de lo contrario.
    """
    if not secret or not code:
        return False

    # Sanitizar código (remover espacios, guiones)
    clean_code = re.sub(r"[\s\-]", "", str(code))
    if not clean_code.isdigit() or len(clean_code) != 6:
        return False

    clean_secret = secret.strip().replace(" ", "").upper()

    if pyotp is not None:
        try:
            totp = pyotp.TOTP(clean_secret, interval=30, digits=6)
            return bool(totp.verify(clean_code, valid_window=valid_window))
        except Exception:
            # Reintentar con verificación nativa si pyotp falla en formato
            return _verify_native_totp(clean_secret, clean_code, valid_window=valid_window)

    return _verify_native_totp(clean_secret, clean_code, valid_window=valid_window)


def generate_recovery_codes(count: int = 8) -> List[str]:
    """Genera códigos alfanuméricos de respaldo de un solo uso.
    
    Diseñados para permitir el acceso de emergencia a la cuenta si el usuario
    pierde o no tiene acceso a su dispositivo móvil o app autenticadora.
    
    Cada código consta de 8 caracteres alfanuméricos no ambiguos distribuidos
    en dos bloques de 4 caracteres (formato: 'XXXX-XXXX') para facilitar
    su lectura y almacenamiento seguro.
    
    Args:
        count: Número de códigos de respaldo a generar (por defecto: 8).
        
    Returns:
        Lista de cadenas de texto únicas con los códigos generados.
    """
    if count <= 0:
        return []

    generated_codes: set[str] = set()
    while len(generated_codes) < count:
        part1 = "".join(secrets.choice(RECOVERY_ALPHABET) for _ in range(4))
        part2 = "".join(secrets.choice(RECOVERY_ALPHABET) for _ in range(4))
        code = f"{part1}-{part2}"
        generated_codes.add(code)

    return list(generated_codes)
