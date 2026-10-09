"""
Endpoints de Fiabilidad Operativa, Copias de Seguridad (Backup & Restore) y Diagnóstico.

Proporciona soporte para:
- POST /api/v1/operations/backup: Generación atómica de copia de seguridad con hash SHA-256.
- POST /api/v1/operations/backup/verify: Verificación estructural y criptográfica del respaldo.
- POST /api/v1/operations/backup/restore-test: Ensayo y prueba de restauración verificada con PRAGMA quick_check.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.auth_deps import get_current_user_optional
from app.models.user import User, UserRole
from app.services.backup_service import (
    create_system_backup,
    verify_backup_integrity,
    restore_system_backup,
    get_backups_dir,
)

router = APIRouter()


class BackupVerifyRequest(BaseModel):
    backup_filename: str = Field(..., description="Nombre del fichero ZIP de backup en storage/backups/")


class RestoreTestRequest(BaseModel):
    backup_filename: str = Field(..., description="Nombre del fichero ZIP de backup a ensayar")


@router.post(
    "/backup",
    summary="Crear copia de seguridad integral del sistema (BD, documentos y logs)",
)
async def create_backup(
    include_documents: bool = Query(True, description="Incluir documentos físicos de facturas"),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Genera una copia de seguridad empaquetada con manifiesto de huellas SHA-256."""
    if current_user:
        allowed = {UserRole.SUPERADMIN.value, UserRole.COMPANY_ADMIN.value, UserRole.ADVISOR.value}
        if current_user.global_role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permisos insuficientes: solo Administradores o Asesores pueden generar copias de seguridad.",
            )

    backup_info = create_system_backup(include_documents=include_documents)
    return backup_info


@router.post(
    "/backup/verify",
    summary="Verificar integridad estructural y SHA-256 de una copia de seguridad",
)
async def verify_backup(
    payload: BackupVerifyRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Valida que el archivo ZIP no esté corrupto y coincidan todos los hashes del manifiesto."""
    if current_user:
        allowed = {UserRole.SUPERADMIN.value, UserRole.COMPANY_ADMIN.value, UserRole.ADVISOR.value}
        if current_user.global_role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permisos insuficientes.",
            )

    zip_path = get_backups_dir() / payload.backup_filename
    if not zip_path.is_file():
        raise HTTPException(status_code=404, detail="Archivo de respaldo no encontrado.")

    is_valid, error, manifest = verify_backup_integrity(zip_path)
    return {
        "is_valid": is_valid,
        "backup_filename": payload.backup_filename,
        "error": error,
        "manifest": manifest,
    }


@router.post(
    "/backup/restore-test",
    summary="Procedimiento de restauración probado en entorno de ensayo",
)
async def test_restore_backup(
    payload: RestoreTestRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Desempaqueta el respaldo en staging y ejecuta PRAGMA quick_check en la base de datos."""
    if current_user:
        allowed = {UserRole.SUPERADMIN.value, UserRole.COMPANY_ADMIN.value, UserRole.ADVISOR.value}
        if current_user.global_role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permisos insuficientes.",
            )

    zip_path = get_backups_dir() / payload.backup_filename
    if not zip_path.is_file():
        raise HTTPException(status_code=404, detail="Archivo de respaldo no encontrado.")

    try:
        result = restore_system_backup(zip_path)
        return result
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Fallo durante la restauración de prueba: {str(exc)}",
        )
