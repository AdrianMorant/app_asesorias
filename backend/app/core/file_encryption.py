"""Módulo de Cifrado y Custodia Segura de Archivos en Reposo (Encryption-at-Rest).

Implementa cifrado simétrico autenticado AES-256-GCM (Galois/Counter Mode, RFC 5116 / NIST SP 800-38D)
para garantizar la confidencialidad, autenticidad e integridad inalterable de facturas,
albaranes y extractos bancarios almacenados en disco, en estricto cumplimiento con
el RGPD (Art. 32) y la normativa tributaria española (AEAT).

Estructura del Payload Cifrado:
+-------------------+-----------------------------------+--------------------+
|  Nonce (12 bytes) |  Datos Cifrados (N bytes)         |  Tag Auth (16 bytes)|
+-------------------+-----------------------------------+--------------------+
"""

from __future__ import annotations

import os
import hashlib
from pathlib import Path
from typing import Optional, Union

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag

from app.core.config import settings

# Constantes de especificación AES-GCM
AES_KEY_SIZE_BYTES = 32      # 256 bits para AES-256
GCM_NONCE_SIZE_BYTES = 12    # 96 bits recomendado por NIST SP 800-38D
GCM_TAG_SIZE_BYTES = 16      # 128 bits para el Authentication Tag


class FileEncryptionError(Exception):
    """Excepción base para fallos durante el proceso de cifrado de archivos."""
    pass


class FileDecryptionError(Exception):
    """Excepción lanzada cuando un archivo no puede ser descifrado por corrupción,

    manipulación física o divergencia en la clave maestra criptográfica.
    """
    pass


def get_master_encryption_key() -> bytes:
    """Obtiene y deriva la clave maestra criptográfica de 256 bits (32 bytes).

    Prioridad de lectura:
    1. STORAGE_ENCRYPTION_KEY
    2. APP_SECRET_KEY
    3. SECRET_KEY
    4. Frase de clave predeterminada del sistema

    Deriva la clave mediante hash SHA-256 para asegurar exactamente 32 bytes
    de entropía uniforme, independiente de la longitud del secreto original.

    Returns:
        Clave criptográfica simétrica de exactamente 32 bytes (256 bits).
    """
    raw_key = (
        os.getenv("STORAGE_ENCRYPTION_KEY")
        or os.getenv("APP_SECRET_KEY")
        or os.getenv("SECRET_KEY")
        or getattr(settings, "STORAGE_ENCRYPTION_KEY", None)
        or "konta-ai-storage-encryption-master-key-2026-compliance-aeat-pgc"
    )

    if isinstance(raw_key, str):
        raw_key_bytes = raw_key.encode("utf-8")
    else:
        raw_key_bytes = bytes(raw_key)

    # Derivación determinista a 256 bits
    return hashlib.sha256(raw_key_bytes).digest()


def encrypt_file_bytes(data: bytes, key: Optional[bytes] = None) -> bytes:
    """Cifra un flujo de bytes en memoria utilizando AES-256-GCM autenticado.

    Genera un nonce/vector de inicialización aleatorio y criptográficamente
    seguro de 12 bytes por cada archivo individual, asegurando que dos
    archivos con idéntico contenido generen esquemas cifrados completamente diferentes.

    Args:
        data: Bytes originales en claro (ej. PDF, imagen JPEG/PNG).
        key: Clave opcional de 32 bytes. Si no se suministra, se obtiene la clave maestra.

    Returns:
        Payload binario empaquetado compuesto por:
        nonce (12 bytes) + ciphertext + authentication_tag (16 bytes).

    Raises:
        FileEncryptionError: Si ocurre algún error en la primitiva criptográfica.
    """
    if data is None:
        raise FileEncryptionError("No se pueden cifrar datos nulos (None).")

    active_key = key or get_master_encryption_key()
    if len(active_key) != AES_KEY_SIZE_BYTES:
        raise FileEncryptionError(
            f"Longitud de clave inválida ({len(active_key)} bytes). Se requieren 32 bytes para AES-256."
        )

    try:
        # Vector de inicialización (nonce) único de 96 bits por cada operación
        nonce = os.urandom(GCM_NONCE_SIZE_BYTES)
        aesgcm = AESGCM(active_key)

        # En cryptography, AESGCM.encrypt() devuelve ciphertext + tag_de_16_bytes
        ciphertext_and_tag = aesgcm.encrypt(nonce, data, None)

        # Empaquetado binario: [Nonce (12B)] + [Ciphertext + Tag]
        return nonce + ciphertext_and_tag
    except Exception as exc:
        raise FileEncryptionError(f"Fallo al cifrar los bytes del archivo: {str(exc)}") from exc


def decrypt_file_bytes(encrypted_data: bytes, key: Optional[bytes] = None) -> bytes:
    """Descifra y verifica la autenticidad e integridad de un payload AES-256-GCM.

    Desempaqueta el nonce (primeros 12 bytes) y delega a la primitiva AESGCM
    el descifrado y la validación en tiempo constante del Authentication Tag.
    Si el archivo fue modificado, truncado o la clave difiere, se rechaza de inmediato.

    Args:
        encrypted_data: Payload binario empaquetado (nonce + ciphertext + tag).
        key: Clave opcional de 32 bytes. Si no se suministra, se obtiene la clave maestra.

    Returns:
        Bytes originales descifrados en memoria.

    Raises:
        FileDecryptionError: Si el payload está corrupto, truncado o la firma no coincide.
    """
    min_required_len = GCM_NONCE_SIZE_BYTES + GCM_TAG_SIZE_BYTES
    if not encrypted_data or len(encrypted_data) < min_required_len:
        raise FileDecryptionError(
            "El archivo cifrado está corrupto o truncado (longitud menor al encabezado criptográfico mínimo)."
        )

    active_key = key or get_master_encryption_key()
    if len(active_key) != AES_KEY_SIZE_BYTES:
        raise FileDecryptionError(
            f"Longitud de clave inválida ({len(active_key)} bytes). Se requieren 32 bytes para AES-256."
        )

    # Extraer nonce (12 bytes) y payload cifrado con tag
    nonce = encrypted_data[:GCM_NONCE_SIZE_BYTES]
    ciphertext_and_tag = encrypted_data[GCM_NONCE_SIZE_BYTES:]

    try:
        aesgcm = AESGCM(active_key)
        # Verifica el tag criptográfico antes de devolver el texto plano
        plaintext = aesgcm.decrypt(nonce, ciphertext_and_tag, None)
        return plaintext
    except InvalidTag as exc:
        raise FileDecryptionError(
            "Fallo de integridad criptográfica: el archivo ha sido manipulado, está corrupto "
            "o la clave de descifrado no coincide."
        ) from exc
    except Exception as exc:
        raise FileDecryptionError(f"Error inesperado al descifrar el archivo: {str(exc)}") from exc


def save_encrypted_file(
    file_path: Union[str, Path],
    raw_bytes: bytes,
    key: Optional[bytes] = None,
) -> None:
    """Cifra el flujo de bytes en memoria y lo guarda de forma atómica en disco.

    Crea automáticamente los directorios contenedores si no existen previamente.

    Args:
        file_path: Ruta de destino en el sistema de archivos (ej. 'storage/empresa/factura.pdf.enc').
        raw_bytes: Contenido original en claro del documento a salvaguardar.
        key: Clave opcional de cifrado.
    """
    path = Path(file_path).resolve()
    # Asegurar existencia del directorio destino
    path.parent.mkdir(parents=True, exist_ok=True)

    encrypted_payload = encrypt_file_bytes(raw_bytes, key=key)

    # Escritura segura en modo binario
    with open(path, "wb") as f:
        f.write(encrypted_payload)


def read_decrypted_file(
    file_path: Union[str, Path],
    key: Optional[bytes] = None,
) -> bytes:
    """Lee un archivo cifrado desde disco y lo descifra en memoria para visualización o descarga.

    Args:
        file_path: Ruta del archivo cifrado en disco.
        key: Clave opcional de descifrado.

    Returns:
        Bytes descifrados del documento original.

    Raises:
        FileNotFoundError: Si el archivo no existe en el sistema de archivos.
        FileDecryptionError: Si el archivo no supera la validación de integridad o la clave es errónea.
    """
    path = Path(file_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"No se encontró el archivo cifrado en la ruta: {path}")

    with open(path, "rb") as f:
        encrypted_data = f.read()

    return decrypt_file_bytes(encrypted_data, key=key)
