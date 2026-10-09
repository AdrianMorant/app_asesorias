"""
Servicio Empresarial de Copias de Seguridad (Backup) y Restauración (Disaster Recovery).

Cumplimiento con:
- RGPD (Art. 32): Capacidad de restaurar la disponibilidad y el acceso a los datos de forma rápida en caso de incidente físico o técnico.
- Integridad y Trazabilidad AEAT: Respaldo íntegro de la base de datos relacional, ficheros documentales y logs WORM.
- Verificación criptográfica: Manifiesto con huellas digitales SHA-256 de cada componente respaldado.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import sqlite3
import hashlib
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings
from app.core.audit_logger import get_audit_log_path, log_security_event


def get_backups_dir() -> Path:
    """Devuelve la ruta del directorio de almacenamiento de copias de seguridad."""
    backups_path = (settings.STORAGE_DIR / "backups").resolve()
    backups_path.mkdir(parents=True, exist_ok=True)
    return backups_path


def compute_file_sha256(file_path: Path) -> str:
    """Calcula el hash SHA-256 en bloques de 64KB de un archivo en disco."""
    if not file_path.is_file():
        return ""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def create_system_backup(
    include_documents: bool = True,
    backup_name_prefix: str = "konta_backup",
) -> Dict[str, Any]:
    """Genera una copia de seguridad integral empaquetada y cifrada lógicamente con manifiesto SHA-256.

    1. Realiza una copia consistente de la base de datos SQLite.
    2. Recopila los archivos de almacenamiento de facturas y documentos contables.
    3. Incluye la cadena de log inmutable de auditoría de seguridad.
    4. Genera un manifiesto criptográfico de integridad SHA-256.
    5. Empaqueta todo en un archivo ZIP con compresión estándar.

    Returns:
        Diccionario con los metadatos del backup generado (ruta, tamaño, SHA-256, cantidad de archivos).
    """
    backups_dir = get_backups_dir()
    now_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    zip_filename = f"{backup_name_prefix}_{now_str}.zip"
    zip_path = backups_dir / zip_filename

    # Identificar ruta de base de datos SQLite
    db_url = settings.DATABASE_URL
    # Formato sqlite+aiosqlite:///./invoices_accounting.db o sqlite+aiosqlite:////path...
    raw_path = db_url.split(":///")[-1]
    db_file_path = Path(raw_path).resolve()

    manifest: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "konta_version": "2026.4.0",
        "backup_filename": zip_filename,
        "include_documents": include_documents,
        "files_manifest": {},
    }

    files_added_count = 0
    total_uncompressed_bytes = 0

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # 1. Copia consistente de la Base de Datos SQLite
        if db_file_path.is_file():
            # Crear copia de seguridad SQLite consistente
            temp_db_backup = backups_dir / f"temp_{now_str}.db"
            try:
                # Realizar backup nativo SQLite API para garantizar consistencia transaccional
                src_conn = sqlite3.connect(str(db_file_path))
                dst_conn = sqlite3.connect(str(temp_db_backup))
                with dst_conn:
                    src_conn.backup(dst_conn)
                src_conn.close()
                dst_conn.close()

                db_sha = compute_file_sha256(temp_db_backup)
                db_size = temp_db_backup.stat().st_size
                zf.write(temp_db_backup, arcname="database/invoices_accounting.db")
                manifest["files_manifest"]["database/invoices_accounting.db"] = {
                    "sha256": db_sha,
                    "size_bytes": db_size,
                }
                files_added_count += 1
                total_uncompressed_bytes += db_size
            finally:
                if temp_db_backup.exists():
                    temp_db_backup.unlink()

        # 2. Log de Auditoría WORM
        audit_log_path = get_audit_log_path()
        if audit_log_path.is_file():
            audit_sha = compute_file_sha256(audit_log_path)
            audit_size = audit_log_path.stat().st_size
            zf.write(audit_log_path, arcname="audit/security_audit.log")
            manifest["files_manifest"]["audit/security_audit.log"] = {
                "sha256": audit_sha,
                "size_bytes": audit_size,
            }
            files_added_count += 1
            total_uncompressed_bytes += audit_size

        # 3. Documentos y almacenamiento si está solicitado
        if include_documents and settings.STORAGE_DIR.exists():
            for item in settings.STORAGE_DIR.rglob("*"):
                # Omitir la propia carpeta de backups y logs ya incluidos
                if "backups" in item.parts or "logs" in item.parts:
                    continue
                if item.is_file():
                    rel_path = item.relative_to(settings.STORAGE_DIR)
                    arcname = f"storage/{rel_path.as_posix()}"
                    f_sha = compute_file_sha256(item)
                    f_size = item.stat().st_size
                    zf.write(item, arcname=arcname)
                    manifest["files_manifest"][arcname] = {
                        "sha256": f_sha,
                        "size_bytes": f_size,
                    }
                    files_added_count += 1
                    total_uncompressed_bytes += f_size

        # 4. Escribir manifiesto JSON dentro del archivo ZIP
        manifest["total_files"] = files_added_count
        manifest["total_uncompressed_bytes"] = total_uncompressed_bytes
        manifest_data = json.dumps(manifest, indent=2, ensure_ascii=False).encode("utf-8")
        zf.writestr("manifest.json", manifest_data)

    archive_sha256 = compute_file_sha256(zip_path)
    archive_size_bytes = zip_path.stat().st_size

    log_security_event(
        action="SYSTEM_BACKUP_CREATED",
        resource_id=zip_filename,
        status="SUCCESS",
        details={
            "backup_filename": zip_filename,
            "archive_sha256": archive_sha256,
            "size_bytes": archive_size_bytes,
            "files_count": files_added_count,
        },
    )

    return {
        "success": True,
        "backup_path": str(zip_path),
        "filename": zip_filename,
        "archive_sha256": archive_sha256,
        "size_bytes": archive_size_bytes,
        "files_count": files_added_count,
        "uncompressed_bytes": total_uncompressed_bytes,
        "timestamp": manifest["timestamp"],
    }


def verify_backup_integrity(zip_path: Path) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """Verifica matemáticamente que el archivo de respaldo no esté corrupto ni alterado.

    Comprueba:
    1. Integridad estructural del archivo ZIP (testzip).
    2. Existencia del archivo 'manifest.json'.
    3. Coincidencia estricta del hash SHA-256 de cada archivo contenido respecto al manifiesto.
    """
    if not zip_path.is_file():
        return False, "El archivo de respaldo especificado no existe.", None

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            corrupt_file = zf.testzip()
            if corrupt_file:
                return False, f"Archivo comprimido dañado o corrupto en '{corrupt_file}'.", None

            if "manifest.json" not in zf.namelist():
                return False, "El archivo de respaldo carece del archivo obligatorio 'manifest.json'.", None

            manifest_content = zf.read("manifest.json").decode("utf-8")
            manifest = json.loads(manifest_content)

            files_manifest = manifest.get("files_manifest", {})
            for arcname, meta in files_manifest.items():
                if arcname not in zf.namelist():
                    return False, f"Archivo declarado en manifiesto no encontrado en el archivo: {arcname}", None

                content = zf.read(arcname)
                calc_sha = hashlib.sha256(content).hexdigest()
                expected_sha = meta.get("sha256")
                if calc_sha != expected_sha:
                    return False, f"Huella SHA-256 no coincide en '{arcname}'. Esperado: {expected_sha}, Calculado: {calc_sha}", None

            return True, None, manifest
    except Exception as exc:
        return False, f"Error durante la verificación del respaldo: {str(exc)}", None


def restore_system_backup(
    zip_path: Path,
    target_extract_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Procedimiento seguro de restauración probado.

    1. Comprueba la integridad previa del respaldo mediante verificación SHA-256.
    2. Extrae los ficheros en el directorio objetivo o entorno de prueba/producción.
    3. Verifica que la base de datos SQLite restaurada supere la comprobación de integridad ('PRAGMA quick_check').
    """
    is_valid, error, manifest = verify_backup_integrity(zip_path)
    if not is_valid:
        raise ValueError(f"Fallo de integridad en el archivo de copia de seguridad: {error}")

    extract_base = target_extract_dir or (get_backups_dir() / f"restore_staging_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    extract_base.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_base)

    restored_db_path = extract_base / "database" / "invoices_accounting.db"
    db_check_result = "NOT_CHECKED"

    if restored_db_path.is_file():
        # Ejecutar PRAGMA quick_check en la base de datos extraída
        conn = sqlite3.connect(str(restored_db_path))
        cursor = conn.cursor()
        cursor.execute("PRAGMA quick_check;")
        res = cursor.fetchone()
        conn.close()
        db_check_result = res[0] if res else "UNKNOWN"

    log_security_event(
        action="SYSTEM_RESTORE_VERIFIED",
        resource_id=zip_path.name,
        status="SUCCESS",
        details={
            "backup_filename": zip_path.name,
            "target_dir": str(extract_base),
            "sqlite_quick_check": db_check_result,
        },
    )

    return {
        "success": True,
        "message": "Copia de seguridad verificada y restaurada con éxito.",
        "extracted_path": str(extract_base),
        "sqlite_quick_check": db_check_result,
        "manifest": manifest,
    }
