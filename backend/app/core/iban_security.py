"""Módulo de Seguridad, Validación y Criptografía de Cuentas Bancarias (IBAN Security).

Cumplimiento con:
- Estándar Bancario Internacional ISO 13616 / ISO 7064 (MOD 97-10)
- RGPD (Protección de Datos Financieros y Bancarios - PII)
- Trazabilidad y Seguridad Financiera (Encriptación en reposo y Blind Index para búsquedas seguras)

Componentes:
1. Validación Algorítmica Oficial MOD-97 (ISO 13616).
2. Enmascaramiento y Ofuscación Visual para Interfaces de Usuario (Data Masking).
3. Cifrado Simétrico AES-256-GCM en Base de Datos (Encryption at Rest).
4. Índice Ciego Determinista HMAC-SHA256 (Blind Index) para conciliación bancaria y búsquedas SQL sin descifrar.
"""

from __future__ import annotations

import os
import re
import hmac
import base64
import hashlib
from typing import Optional, Dict
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag

from app.core.file_encryption import get_master_encryption_key

# Longitudes oficiales ISO 13616 por código de país (SEPA e internacional)
IBAN_COUNTRY_LENGTHS: Dict[str, int] = {
    "ES": 24, "AD": 24, "AT": 20, "BE": 16, "BG": 22, "CH": 21,
    "CY": 28, "CZ": 24, "DE": 22, "DK": 18, "EE": 20, "FI": 18,
    "FR": 27, "GB": 22, "GI": 23, "GR": 27, "HR": 21, "HU": 28,
    "IE": 22, "IS": 26, "IT": 27, "LI": 21, "LT": 20, "LU": 20,
    "LV": 21, "MC": 27, "MT": 31, "NL": 18, "NO": 15, "PL": 28,
    "PT": 25, "RO": 24, "SE": 24, "SI": 19, "SK": 24, "SM": 27,
    "VA": 22,
}

# Prefijo distintivo para cadenas cifradas
ENCRYPTED_IBAN_PREFIX = "enc:v1:"


class IBANError(Exception):
    """Excepción base para errores en el procesamiento de IBAN."""
    pass


class IBANValidationError(IBANError):
    """Lanzada cuando un IBAN no supera la validación formal o el algoritmo MOD-97."""
    pass


class IBANEncryptionError(IBANError):
    """Lanzada ante fallos en el cifrado simétrico del IBAN."""
    pass


class IBANDecryptionError(IBANError):
    """Lanzada ante manipulaciones, corrupción o claves erróneas al descifrar el IBAN."""
    pass


def clean_iban_str(iban: Optional[str]) -> str:
    """Limpia caracteres de formato (espacios, guiones, puntos) y normaliza a mayúsculas."""
    if not iban:
        return ""
    return re.sub(r"[^A-Za-z0-9]", "", str(iban)).upper().strip()


def validate_iban(iban: str) -> bool:
    """Valida formal y algorítmicamente un IBAN según el estándar ISO 13616 / MOD-97.

    Pasos de validación:
    1. Limpieza de separadores y conversión a mayúsculas.
    2. Comprobación de longitud según país (ej. 24 caracteres para España 'ES').
    3. Verificación de formato alfanumérico (2 letras de país + 2 dígitos de control + BBAN).
    4. Algoritmo matemático MOD-97 (ISO 7064 MOD 97-10):
       - Traslada los 4 primeros caracteres al final.
       - Sustituye letras por su valor numérico (A=10, B=11 ... Z=35).
       - Verifica que el residuo de la división entre 97 sea exactamente 1.

    Args:
        iban: Cadena con el IBAN a verificar.

    Returns:
        True si el IBAN es matemáticamente válido, False en caso contrario.
    """
    clean = clean_iban_str(iban)
    if not clean or len(clean) < 15 or len(clean) > 34:
        return False

    country_code = clean[:2]
    check_digits = clean[2:4]

    # Los dos primeros deben ser letras y los dos siguientes dígitos
    if not country_code.isalpha() or not check_digits.isdigit():
        return False

    # Comprobación de longitud esperada si el país está registrado en SEPA/ISO
    expected_len = IBAN_COUNTRY_LENGTHS.get(country_code)
    if expected_len and len(clean) != expected_len:
        return False

    # Validación adicional específica para cuentas españolas: el BBAN debe ser puramente numérico
    if country_code == "ES":
        if not clean[4:].isdigit():
            return False

    # Algoritmo MOD-97: mover los 4 primeros caracteres al final
    rearranged = clean[4:] + clean[:4]

    # Convertir letras a sus equivalentes numéricos (A=10, B=11, ..., Z=35)
    numeric_parts = []
    for char in rearranged:
        if char.isdigit():
            numeric_parts.append(char)
        elif char.isalpha():
            numeric_parts.append(str(ord(char) - ord("A") + 10))
        else:
            return False

    numeric_str = "".join(numeric_parts)

    try:
        # El residuo de la división entera entre 97 debe ser estrictamente 1
        return int(numeric_str) % 97 == 1
    except (ValueError, OverflowError):
        return False


def mask_iban(iban: str, mask_char: str = "•") -> str:
    """Enmascara visualmente un IBAN para presentación segura en interfaces de usuario.

    Preserva visibles los primeros 4 caracteres (país + control) y los últimos 4 dígitos,
    ofuscando el bloque central en grupos de 4 con viñetas o asteriscos.
    Ejemplo para España: 'ES91 •••• •••• •••• •••• 1234'.

    Maneja entradas inválidas, nulas o truncadas de forma segura y sin excepciones.

    Args:
        iban: Cadena con el IBAN a enmascarar.
        mask_char: Carácter utilizado para ofuscar (por defecto '•', o '*').

    Returns:
        Cadena formateada y enmascarada para presentación visual.
    """
    if not iban:
        return ""

    clean = clean_iban_str(iban)
    if len(clean) < 8:
        # Si es demasiado corto para ocultar el medio de forma segura
        return clean

    first4 = clean[:4]
    last4 = clean[-4:]
    mid_length = len(clean) - 8

    # Formar bloques de 4 caracteres enmascarados para el segmento central
    num_blocks = (mid_length + 3) // 4
    masked_blocks = ["".join([mask_char] * 4) for _ in range(num_blocks)]
    mid_str = " ".join(masked_blocks)

    return f"{first4} {mid_str} {last4}"


def format_iban(iban: str) -> str:
    """Formatea un IBAN legible separando los caracteres en bloques de 4.

    Ejemplo: 'ES91 2100 0418 4502 0005 1332'.
    """
    clean = clean_iban_str(iban)
    if not clean:
        return ""
    return " ".join(clean[i:i + 4] for i in range(0, len(clean), 4))


def _get_iban_encryption_key(key: Optional[bytes] = None) -> bytes:
    """Deriva una clave de 256 bits exclusiva para cifrado de datos bancarios."""
    base_key = key or get_master_encryption_key()
    return hashlib.sha256(base_key + b":iban_encryption_domain").digest()


def _get_blind_index_key(key: Optional[bytes] = None) -> bytes:
    """Deriva una clave HMAC de 256 bits exclusiva para el índice ciego de búsqueda."""
    base_key = key or get_master_encryption_key()
    return hashlib.sha256(base_key + b":iban_blind_index_domain").digest()


def encrypt_iban(iban: str, key: Optional[bytes] = None) -> str:
    """Cifra simétricamente un IBAN con AES-256-GCM para almacenamiento seguro en BD.

    Genera un nonce criptográfico aleatorio de 96 bits por cada operación, asegurando
    que el mismo IBAN cifrado múltiples veces resulte en cadenas criptográficas distintas.

    Args:
        iban: Número de cuenta bancaria o IBAN a cifrar.
        key: Clave maestra opcional de cifrado.

    Returns:
        Cadena serializada y codificada en Base64 con prefijo de versión ('enc:v1:...').
    """
    if not iban:
        return ""

    clean = clean_iban_str(iban)
    if not clean:
        return ""

    try:
        active_key = _get_iban_encryption_key(key)
        nonce = os.urandom(12)
        aesgcm = AESGCM(active_key)
        ciphertext = aesgcm.encrypt(nonce, clean.encode("utf-8"), None)
        encoded_payload = base64.b64encode(nonce + ciphertext).decode("ascii")
        return f"{ENCRYPTED_IBAN_PREFIX}{encoded_payload}"
    except Exception as exc:
        raise IBANEncryptionError(f"Error al cifrar el IBAN: {str(exc)}") from exc


def decrypt_iban(encrypted_iban: str, key: Optional[bytes] = None) -> str:
    """Descifra un IBAN almacenado en formato seguro AES-256-GCM.

    Proporciona retrocompatibilidad transparente: si la cadena recibida no está
    cifrada (datos legados planos), la retorna de forma segura tras normalizarla.

    Args:
        encrypted_iban: Token cifrado generado previamente por encrypt_iban.
        key: Clave maestra opcional de descifrado.

    Returns:
        IBAN en claro normalizado en mayúsculas.

    Raises:
        IBANDecryptionError: Si el token está corrupto o la clave no coincide.
    """
    if not encrypted_iban:
        return ""

    token = str(encrypted_iban).strip()

    # Si no tiene el prefijo de cifrado, intentar verificar si es un IBAN en claro legado
    if not token.startswith(ENCRYPTED_IBAN_PREFIX):
        clean_plain = clean_iban_str(token)
        if clean_plain:
            return clean_plain
        return token

    raw_b64 = token[len(ENCRYPTED_IBAN_PREFIX):]

    try:
        raw_bytes = base64.b64decode(raw_b64)
        if len(raw_bytes) < 28:  # 12 bytes nonce + 16 bytes tag mínimo
            raise IBANDecryptionError("Payload cifrado de IBAN corrupto o longitud insuficiente.")

        nonce = raw_bytes[:12]
        ciphertext = raw_bytes[12:]
        active_key = _get_iban_encryption_key(key)
        aesgcm = AESGCM(active_key)
        decrypted_bytes = aesgcm.decrypt(nonce, ciphertext, None)
        return decrypted_bytes.decode("utf-8")
    except InvalidTag as exc:
        raise IBANDecryptionError(
            "Fallo de integridad criptográfica: el IBAN cifrado ha sido manipulado o la clave es incorrecta."
        ) from exc
    except Exception as exc:
        raise IBANDecryptionError(f"Fallo inesperado al descifrar el IBAN: {str(exc)}") from exc


def compute_iban_hash(iban: str, key: Optional[bytes] = None) -> str:
    """Calcula una huella HMAC-SHA256 determinista e irreversible (Blind Index).

    Permite indexar y buscar cuentas bancarias en la base de datos mediante
    consultas SQL directas ('WHERE iban_hash = :hash') sin comprometer la
    confidencialidad del IBAN original ni almacenar hashes MD5/SHA directos
    vulnerables a ataques de diccionario o tablas arcoíris.

    Args:
        iban: IBAN del cual calcular la huella determinista.
        key: Clave maestra opcional.

    Returns:
        Cadena hexadecimal de 64 caracteres correspondiente al HMAC-SHA256.
    """
    if not iban:
        return ""

    clean = clean_iban_str(iban)
    if not clean:
        return ""

    blind_key = _get_blind_index_key(key)
    return hmac.new(blind_key, clean.encode("utf-8"), hashlib.sha256).hexdigest()
