"""Módulo de Registro Inmutable de Auditoría de Seguridad (Security Audit Logger).

Cumplimiento estricto con:
- RGPD (Reglamento General de Protección de Datos, Art. 30 y Art. 32): Trazabilidad de accesos
  y operaciones sobre datos fiscales de carácter personal.
- AEAT (Normativa Tributaria y Ley Antifraude 11/2021): Inalterabilidad, trazabilidad
  e integridad de los registros de facturación electrónica.

Implementa un registro de auditoría estructurado en formato JSON Lines (JSONL),
con encadenamiento criptográfico SHA-256 (estilo blockchain / WORM - Write Once, Read Many).
Cada registro contiene el hash del registro inmediatamente anterior (prev_hash),
garantizando matemáticamente que ninguna entrada pueda ser eliminada o alterada retroactivamente
sin invalidar la integridad de toda la cadena de custodia.
"""

from __future__ import annotations

import os
import json
import hashlib
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, Union
from pydantic import BaseModel, Field
from fastapi import Request

from app.core.config import settings

# Bloqueo para escrituras thread-safe en entornos multihilo / asíncronos
_audit_lock = threading.Lock()

# Hash génesis para el primer evento de la cadena (64 ceros SHA-256)
GENESIS_HASH: str = "0" * 64


def get_audit_log_path() -> Path:
    """Devuelve la ruta canónica del archivo de log de auditoría."""
    custom_path = os.getenv("SECURITY_AUDIT_LOG_PATH")
    if custom_path:
        return Path(custom_path).resolve()
    return (settings.STORAGE_DIR / "logs" / "security_audit.log").resolve()


class AuditEvent(BaseModel):
    """Modelo de datos para eventos de seguridad y trazabilidad normativa."""
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Marca de tiempo en formato UTC ISO 8601"
    )
    user_id: str = Field(
        default="anonymous",
        description="Identificador del usuario actuante (o 'anonymous')"
    )
    empresa_id: Optional[str] = Field(
        default=None,
        description="ID opcional de la empresa fiscal asociada al recurso"
    )
    action: str = Field(
        ...,
        description="Acción realizada (ej. INVOICE_VIEW, INVOICE_DOWNLOAD, INVOICE_SPLIT, EXPORT_ERP)"
    )
    resource_id: Optional[str] = Field(
        default=None,
        description="Identificador del recurso afectado (ID factura, remesa, extracto)"
    )
    ip_address: str = Field(
        default="127.0.0.1",
        description="Dirección IP de origen del cliente"
    )
    user_agent: str = Field(
        default="unknown",
        description="Encabezado User-Agent del cliente HTTP"
    )
    status: str = Field(
        default="SUCCESS",
        description="Resultado de la operación ('SUCCESS' o 'DENIED')"
    )
    details: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Metadatos complementarios contextuales en formato clave-valor"
    )
    prev_hash: str = Field(
        default=GENESIS_HASH,
        description="Hash SHA-256 del registro inmediatamente anterior en la cadena"
    )
    hash: str = Field(
        default="",
        description="Hash SHA-256 inmutable de este registro con prev_hash incorporado"
    )


def compute_event_hash(event_data: Dict[str, Any], prev_hash: str) -> str:
    """Calcula el hash SHA-256 determinista y canónico de un evento de auditoría.

    Asegura que el orden de claves y la codificación UTF-8 sean estrictamente reproducibles.
    """
    canonical_payload = {
        "timestamp": event_data["timestamp"],
        "user_id": event_data.get("user_id", "anonymous"),
        "empresa_id": event_data.get("empresa_id"),
        "action": event_data["action"],
        "resource_id": event_data.get("resource_id"),
        "ip_address": event_data.get("ip_address", "127.0.0.1"),
        "user_agent": event_data.get("user_agent", "unknown"),
        "status": event_data.get("status", "SUCCESS"),
        "details": event_data.get("details"),
        "prev_hash": prev_hash,
    }
    raw_bytes = json.dumps(canonical_payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw_bytes).hexdigest()


def extract_client_ip(request: Optional[Request]) -> str:
    """Extrae la IP real del cliente, contemplando proxies reversos (X-Forwarded-For)."""
    if not request:
        return "127.0.0.1"

    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        # Puede contener lista separada por comas: "client, proxy1, proxy2"
        first_ip = forwarded_for.split(",")[0].strip()
        if first_ip:
            return first_ip

    real_ip = request.headers.get("x-real-ip")
    if real_ip and real_ip.strip():
        return real_ip.strip()

    if request.client and request.client.host:
        return request.client.host

    return "127.0.0.1"


def extract_user_agent(request: Optional[Request]) -> str:
    """Extrae el User-Agent desde la petición HTTP."""
    if not request:
        return "internal"
    return request.headers.get("user-agent", "unknown")


def get_last_audit_hash(log_file: Path) -> str:
    """Lee el hash del último registro en el archivo de log para encadenamiento.

    Si el archivo no existe o está vacío, retorna el GENESIS_HASH.
    """
    if not log_file.is_file() or log_file.stat().st_size == 0:
        return GENESIS_HASH

    try:
        with open(log_file, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            buffer_size = min(8192, size)
            f.seek(size - buffer_size, os.SEEK_SET)
            lines = f.read().decode("utf-8", errors="ignore").splitlines()
            for line in reversed(lines):
                cleaned = line.strip()
                if cleaned:
                    data = json.loads(cleaned)
                    return data.get("hash", GENESIS_HASH)
    except Exception:
        pass

    return GENESIS_HASH


def log_security_event(
    action: str,
    resource_id: Optional[str] = None,
    request: Optional[Request] = None,
    user_id: Optional[str] = None,
    empresa_id: Optional[str] = None,
    status: str = "SUCCESS",
    details: Optional[Dict[str, Any]] = None,
) -> AuditEvent:
    """Registra de forma atómica e inmutable un evento de auditoría de seguridad.

    1. Resuelve IP y User-Agent de la Request.
    2. Obtiene el hash del último evento registrado (encadenamiento criptográfico).
    3. Calcula el nuevo hash SHA-256 del evento actual.
    4. Escribe en modo append-only en storage/logs/security_audit.log de forma thread-safe.

    Args:
        action: Código de acción (ej. 'INVOICE_VIEW', 'INVOICE_DOWNLOAD', 'INVOICE_SPLIT', 'EXPORT_ERP').
        resource_id: Identificador del recurso sujeto de la acción (ej. ID factura).
        request: Objeto FastAPI Request opcional para extracción contextual de red.
        user_id: Identificador del usuario autenticado (por defecto 'anonymous').
        empresa_id: ID opcional de la empresa fiscal en cuestión.
        status: Resultado del evento ('SUCCESS' o 'DENIED').
        details: Diccionario opcional con detalles contextuales adicionales.

    Returns:
        AuditEvent: Instancia serializada del evento registrado con sus hashes inmutables.
    """
    log_file = get_audit_log_path()
    ip_address = extract_client_ip(request)
    user_agent = extract_user_agent(request)
    normalized_status = status.upper().strip() if status else "SUCCESS"
    active_user_id = str(user_id).strip() if user_id else "anonymous"

    with _audit_lock:
        # Asegurar creación del directorio contenedor si no existe
        log_file.parent.mkdir(parents=True, exist_ok=True)

        prev_hash = get_last_audit_hash(log_file)
        timestamp_str = datetime.now(timezone.utc).isoformat()

        event_payload = {
            "timestamp": timestamp_str,
            "user_id": active_user_id,
            "empresa_id": empresa_id,
            "action": action,
            "resource_id": resource_id,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "status": normalized_status,
            "details": details,
        }

        current_hash = compute_event_hash(event_payload, prev_hash)

        event = AuditEvent(
            timestamp=timestamp_str,
            user_id=active_user_id,
            empresa_id=empresa_id,
            action=action,
            resource_id=resource_id,
            ip_address=ip_address,
            user_agent=user_agent,
            status=normalized_status,
            details=details,
            prev_hash=prev_hash,
            hash=current_hash,
        )

        # Escritura atómica append-only con flush inmediato
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(event.model_dump_json() + "\n")
            f.flush()

    return event


def verify_audit_log_integrity(log_file: Optional[Path] = None) -> Tuple[bool, int, Optional[str]]:
    """Verifica matemáticamente la integridad de la cadena criptográfica del log de auditoría.

    Recorre secuencialmente todos los registros del archivo:
    - Comprueba que prev_hash de cada línea coincide exactamente con el hash de la línea anterior.
    - Recalcula el SHA-256 de los datos para garantizar que no hubo alteración de texto.

    Returns:
        (is_valid: bool, total_events: int, error_message: Optional[str])
    """
    target_path = log_file or get_audit_log_path()
    if not target_path.is_file():
        return True, 0, None

    expected_prev_hash = GENESIS_HASH
    count = 0

    with _audit_lock:
        with open(target_path, "r", encoding="utf-8") as f:
            for line_number, line in enumerate(f, start=1):
                raw_line = line.strip()
                if not raw_line:
                    continue

                try:
                    data = json.loads(raw_line)
                except Exception as exc:
                    return False, count, f"Línea {line_number} no es un JSON válido: {str(exc)}"

                recorded_prev_hash = data.get("prev_hash")
                recorded_hash = data.get("hash")

                if recorded_prev_hash != expected_prev_hash:
                    return (
                        False,
                        count,
                        f"Ruptura de cadena en línea {line_number}: prev_hash esperado "
                        f"'{expected_prev_hash}', encontrado '{recorded_prev_hash}'"
                    )

                recalculated_hash = compute_event_hash(data, expected_prev_hash)
                if recalculated_hash != recorded_hash:
                    return (
                        False,
                        count,
                        f"Alteración de datos detectada en línea {line_number}: hash grabado "
                        f"'{recorded_hash}' no coincide con el hash recalculado '{recalculated_hash}'"
                    )

                expected_prev_hash = recorded_hash
                count += 1

    return True, count, None
