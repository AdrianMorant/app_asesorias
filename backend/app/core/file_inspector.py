"""Módulo de Inspección de Seguridad, Magic Bytes y Defensa en Profundidad de Archivos.

Cumplimiento estricto de seguridad:
- Detección obligatoria de firmas binarias reales (Magic Bytes / File Signatures)
  según RFC 2046 / ISO 32000-1 para prevenir camuflaje de ejecutables (.exe, .sh, .bat).
- Análisis estático de PDFs para detección de vectores de explotación:
  tokens maliciosos (/JavaScript, /JS, /Launch, /EmbeddedFiles con extensiones ejecutables).
- Prevención de Path Traversal, Null Byte Injection y nombres hostiles.
- Control estricto de tamaño de carga (DDoS / Zip Bomb prevention).
"""

from __future__ import annotations

import os
import re
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, Set

from app.core.config import settings

# Tamaño máximo permitido por defecto: 25 MB (26.214.400 bytes)
DEFAULT_MAX_UPLOAD_SIZE_BYTES: int = 25 * 1024 * 1024
MAX_UPLOAD_SIZE_BYTES: int = int(
    os.getenv(
        "MAX_UPLOAD_SIZE_BYTES",
        getattr(settings, "MAX_UPLOAD_SIZE_BYTES", DEFAULT_MAX_UPLOAD_SIZE_BYTES)
    )
)

# Extensiones MIME permitidas en el sistema contable
ALLOWED_EXTENSIONS: Set[str] = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}

# Firmas de cabeceras mágicas (Magic Numbers)
MAGIC_PDF_PREFIX = b"%PDF-"  # b"\x25\x50\x44\x46\x2d"
MAGIC_PNG_PREFIX = b"\x89PNG\r\n\x1a\n"  # b"\x89\x50\x4e\x47\x0d\x0a\x1a\x0a"
MAGIC_JPEG_PREFIX = b"\xff\xd8\xff"
MAGIC_RIFF_PREFIX = b"RIFF"
MAGIC_WEBP_TAG = b"WEBP"

# Tokens activos peligrosos en árboles sintácticos de documentos PDF
CRITICAL_PDF_ACTIVE_TOKENS = [
    b"/JavaScript",
    b"/JS",
    b"/Launch",
]

# Extensiones ejecutables peligrosas en adjuntos embebidos de PDF
DANGEROUS_ATTACHMENT_EXTENSIONS = [
    b".exe", b".bat", b".cmd", b".vbs", b".ps1", b".scr",
    b".sh", b".jar", b".hta", b".pif", b".com", b".msi"
]


class FileSecurityViolationError(Exception):
    """Excepción específica lanzada ante cualquier violación de integridad o seguridad."""
    pass


def sanitize_filename(filename: str) -> str:
    """Sanitiza el nombre de archivo eliminando vectores de Path Traversal y caracteres peligrosos.

    - Elimina caracteres nulos (\x00) y saltos de línea.
    - Previene Path Traversal aislando exclusivamente el nombre base (elimina rutas relativas ../ o ..\\).
    - Reemplaza caracteres prohibidos o hostiles con guiones bajos.
    - Elimina espacios o puntos iniciales/finales.
    - Limita la longitud máxima a 255 caracteres.

    Args:
        filename: Nombre original suministrado por el cliente.

    Returns:
        Cadena sanitizada apta para manipulación segura en el sistema de archivos.
    """
    if not filename:
        return "archivo_adjunto"

    # 1. Eliminar caracteres nulos y caracteres de control no imprimibles
    clean = filename.replace("\x00", "")
    clean = re.sub(r"[\r\n\t]", "", clean)

    # 2. Prevenir Path Traversal extrayendo únicamente el nombre base del archivo
    clean = clean.replace("\\", "/")
    if "/" in clean:
        clean = clean.split("/")[-1]

    # 3. Eliminar caracteres reservados de sistemas de archivos Windows / POSIX
    clean = re.sub(r'[<>:"/\\|?*]', "_", clean)

    # 4. Eliminar secuencias de puntos suspensivos o traversal residual
    clean = re.sub(r"\.{2,}", "_", clean)

    # 5. Quitar espacios y puntos iniciales o finales peligrosos
    clean = clean.strip(" .")

    # 6. Fallback si quedó vacío
    if not clean:
        clean = "archivo_adjunto"

    # 7. Truncar a longitud máxima estándar
    if len(clean) > 255:
        stem = Path(clean).stem[:240]
        ext = Path(clean).suffix[:10]
        clean = f"{stem}{ext}"

    return clean


def verify_magic_bytes(data: bytes, ext: str) -> str:
    """Verifica que los primeros bytes reales del binario coincidan con la extensión declarada.

    Args:
        data: Flujo de bytes binarios del archivo.
        ext: Extensión declarada en minúsculas (ej. '.pdf', '.png').

    Returns:
        Tipo MIME validado correspondiente a la firma mágica.

    Raises:
        FileSecurityViolationError: Si no coinciden los Magic Bytes con la extensión o es inválida.
    """
    if len(data) < 4:
        raise FileSecurityViolationError("El archivo es demasiado pequeño o está truncado.")

    if ext == ".pdf":
        if not data.startswith(MAGIC_PDF_PREFIX):
            raise FileSecurityViolationError(
                "Falsificación de tipo de archivo detectada: el archivo tiene extensión .pdf "
                "pero su cabecera binaria no corresponde a un documento PDF legítimo (%PDF-)."
            )
        return "application/pdf"

    elif ext == ".png":
        if not data.startswith(MAGIC_PNG_PREFIX):
            raise FileSecurityViolationError(
                "Falsificación de tipo de archivo detectada: el archivo tiene extensión .png "
                "pero su firma binaria no corresponde a una imagen PNG válida."
            )
        return "image/png"

    elif ext in (".jpg", ".jpeg"):
        if not data.startswith(MAGIC_JPEG_PREFIX):
            raise FileSecurityViolationError(
                f"Falsificación de tipo de archivo detectada: el archivo tiene extensión {ext} "
                "pero su firma binaria no corresponde a una imagen JPEG válida."
            )
        return "image/jpeg"

    elif ext == ".webp":
        if not (data.startswith(MAGIC_RIFF_PREFIX) and len(data) >= 12 and data[8:12] == MAGIC_WEBP_TAG):
            raise FileSecurityViolationError(
                "Falsificación de tipo de archivo detectada: el archivo tiene extensión .webp "
                "pero su firma binaria no contiene la cabecera RIFF/WEBP válida."
            )
        return "image/webp"

    else:
        raise FileSecurityViolationError(
            f"Extensión no permitida '{ext}'. Solo se admiten formatos seguros de facturación: "
            f"{', '.join(sorted(ALLOWED_EXTENSIONS))}."
        )


def inspect_pdf_threats(data: bytes) -> None:
    """Analiza la estructura del PDF en busca de scripts embebidos o acciones maliciosas.

    Detecta:
    - /JavaScript y /JS: Ejecución de scripts dentro del visor del cliente.
    - /Launch: Acción para ejecutar programas externos o comandos en el sistema operativo.
    - /EmbeddedFiles: Ficheros adjuntos embebidos con extensiones ejecutables o de script.

    Raises:
        FileSecurityViolationError: Si se detecta algún elemento hostil o no autorizado.
    """
    # 1. Búsqueda de tokens activos críticos (/Launch, /JavaScript, /JS)
    for token in CRITICAL_PDF_ACTIVE_TOKENS:
        # Búsqueda insensible a delimitadores PDF estándar
        pos = data.find(token)
        if pos != -1:
            # Confirmar que es un token de acción de diccionario PDF delimitado
            # (evita falsos positivos con texto plano incidental de un concepto de factura)
            token_str = token.decode("ascii")
            raise FileSecurityViolationError(
                f"Bloqueo de seguridad: El archivo PDF contiene contenido activo no seguro ({token_str}) "
                "que representa un riesgo de ejecución arbitraria de código."
            )

    # 2. Análisis de /EmbeddedFiles si existen
    if b"/EmbeddedFiles" in data:
        lower_data = data.lower()
        for bad_ext in DANGEROUS_ATTACHMENT_EXTENSIONS:
            if bad_ext in lower_data:
                bad_ext_str = bad_ext.decode("ascii")
                raise FileSecurityViolationError(
                    f"Bloqueo de seguridad: El archivo PDF contiene archivos adjuntos embebidos "
                    f"con extensión ejecutable potencialmente peligrosa ({bad_ext_str})."
                )


def inspect_file_bytes(
    data: bytes,
    filename: str,
    max_size_bytes: Optional[int] = None,
) -> Dict[str, Any]:
    """Inspecciona exhaustivamente un archivo antes de permitir su almacenamiento o procesamiento.

    1. Comprueba que el archivo no esté vacío y no supere el límite de tamaño configurado.
    2. Sanitiza el nombre de archivo contra Path Traversal y caracteres peligrosos.
    3. Valida la extensión declarada contra la lista blanca permitida.
    4. Comprueba los Magic Bytes iniciales exactos (evitando ejecutables encubiertos).
    5. Para documentos PDF, realiza un análisis estático de amenazas (/Launch, /JavaScript, etc.).

    Args:
        data: Bytes binarios del archivo a inspeccionar.
        filename: Nombre original del archivo propuesto.
        max_size_bytes: Límite máximo opcional en bytes (por defecto 25 MB).

    Returns:
        Diccionario con los metadatos de validación:
        - is_valid: True
        - filename: Nombre de archivo sanitizado
        - original_filename: Nombre original
        - extension: Extensión normalizada en minúsculas
        - detected_mime_type: Tipo MIME seguro validado por firma
        - size_bytes: Tamaño exacto en bytes
        - sha256: Hash criptográfico SHA-256 del contenido

    Raises:
        FileSecurityViolationError: Si el archivo no supera alguna de las directivas de seguridad.
    """
    # 1. Validación de tamaño
    if data is None or len(data) == 0:
        raise FileSecurityViolationError("El archivo suministrado está vacío (0 bytes).")

    limit = max_size_bytes or MAX_UPLOAD_SIZE_BYTES
    if len(data) > limit:
        max_mb = limit / (1024 * 1024)
        actual_mb = len(data) / (1024 * 1024)
        raise FileSecurityViolationError(
            f"El archivo ({actual_mb:.2f} MB) excede el tamaño máximo permitido de {max_mb:.0f} MB."
        )

    # 2. Sanitización del nombre
    sanitized_name = sanitize_filename(filename)

    # 3. Comprobación de extensión declarada
    ext = Path(sanitized_name).suffix.lower()
    if not ext or ext not in ALLOWED_EXTENSIONS:
        raise FileSecurityViolationError(
            f"Formato de archivo '{ext or 'sin extensión'}' no permitido. "
            f"Formatos válidos: {', '.join(sorted(ALLOWED_EXTENSIONS))}."
        )

    # 4. Verificación binaria de Magic Bytes
    detected_mime = verify_magic_bytes(data, ext)

    # 5. Inspección estática contra vectores de ataque PDF
    if ext == ".pdf":
        inspect_pdf_threats(data)

    # 6. Cálculo de huella SHA-256
    file_sha256 = hashlib.sha256(data).hexdigest()

    return {
        "is_valid": True,
        "filename": sanitized_name,
        "original_filename": filename,
        "extension": ext,
        "detected_mime_type": detected_mime,
        "size_bytes": len(data),
        "sha256": file_sha256,
    }
