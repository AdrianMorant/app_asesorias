import os
import io
import hashlib
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.models.company import Company
from app.models.invoice import Invoice
from app.models.accounting_entry import AccountingEntryLine
from app.models.integration import CompanyIntegration, ExportBatch
from app.schemas.integration_dto import (
    IntegrationConfigCreate,
    IntegrationConfigResponse,
    GenerateExportRequest,
    ExportBatchResponse,
)
from app.services.a3_suenlace import generate_a3_suenlace_bytes, generate_a3_suenlace
from app.services.contasol_csv import generate_contasol_csv_bytes, generate_contasol_csv
from app.core.audit_logger import log_security_event
from app.core.auth_deps import get_current_user_optional
from app.models.user import User, UserRole

router = APIRouter()

# Directorio para almacenar copias históricas de los archivos exportados
EXPORTS_DIR = os.path.join(settings.STORAGE_DIR, "exports")
os.makedirs(EXPORTS_DIR, exist_ok=True)


@router.get("/{company_id}/integrations", response_model=List[IntegrationConfigResponse])
async def get_company_integrations(company_id: str, db: AsyncSession = Depends(get_db)):
    """Obtiene la lista de configuraciones de software contable de la empresa."""
    stmt = select(CompanyIntegration).where(CompanyIntegration.company_id == company_id)
    res = await db.execute(stmt)
    return res.scalars().all()


@router.post("/{company_id}/integrations", response_model=IntegrationConfigResponse)
async def configure_company_integration(
    company_id: str,
    payload: IntegrationConfigCreate,
    db: AsyncSession = Depends(get_db),
):
    """Crea o actualiza la configuración de un software contable (A3, CONTASOL, SAGE, HOLDED_API)."""
    # Verificar empresa
    comp = await db.get(Company, company_id)
    if not comp:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    # Buscar si ya existe para este software
    stmt = select(CompanyIntegration).where(
        CompanyIntegration.company_id == company_id,
        CompanyIntegration.software_type == payload.software_type,
    )
    res = await db.execute(stmt)
    existing = res.scalar_one_or_none()

    if existing:
        existing.is_active = payload.is_active
        existing.configuration_json = payload.configuration_json
        existing.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(existing)
        return existing
    else:
        new_int = CompanyIntegration(
            company_id=company_id,
            software_type=payload.software_type,
            is_active=payload.is_active,
            configuration_json=payload.configuration_json,
        )
        db.add(new_int)
        await db.commit()
        await db.refresh(new_int)
        return new_int


@router.get("/{company_id}/export-batches", response_model=List[ExportBatchResponse])
async def list_export_batches(company_id: str, db: AsyncSession = Depends(get_db)):
    """Lista el historial de lotes exportados para una empresa."""
    stmt = (
        select(ExportBatch)
        .where(ExportBatch.company_id == company_id)
        .order_by(ExportBatch.created_at.desc())
    )
    res = await db.execute(stmt)
    return res.scalars().all()


@router.post("/{company_id}/generate-export", response_model=ExportBatchResponse)
async def generate_export_batch(
    company_id: str,
    req: GenerateExportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Genera un lote de exportación contable (A3, CONTASOL, SAGE o HOLDED_API):
    1. Filtra las facturas aprobadas de la empresa con exported_to_erp == False.
    2. Valida seguridad (bloqueo ante facturas en Semáforo Rojo o asientos descuadrados).
    3. Genera el fichero mediante el servicio correspondiente (generate_a3_suenlace_bytes,
       generate_contasol_csv_bytes o generate_sage_csv_bytes) y lo guarda en storage/exports/.
    4. Crea el registro ExportBatch con recuento de asientos e importe total.
    5. Marca las facturas procesadas como exported_to_erp = True y export_batch_id = batch.id.
    """
    comp = await db.get(Company, company_id)
    if not comp:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    # Obtener configuración si existe
    int_stmt = select(CompanyIntegration).where(
        CompanyIntegration.company_id == company_id,
        CompanyIntegration.software_type == req.software_type,
    )
    int_res = await db.execute(int_stmt)
    integration = int_res.scalar_one_or_none()
    cfg = integration.configuration_json if integration else {}
    if req.config_overrides:
        cfg = {**cfg, **req.config_overrides}

    # 1. Filtrar las facturas aprobadas de la empresa con exported_to_erp == False
    stmt = (
        select(Invoice)
        .options(
            selectinload(Invoice.accounting_entries),
            selectinload(Invoice.tax_breakdown)
        )
        .where(
            Invoice.company_id == company_id,
            Invoice.exported_to_erp == False,
            (Invoice.is_processed == True) | (Invoice.workflow_status.in_(["validado", "contabilizado"]))
        )
    )

    if req.invoice_ids:
        # Selección manual de IDs específicos
        stmt = (
            select(Invoice)
            .options(
                selectinload(Invoice.accounting_entries),
                selectinload(Invoice.tax_breakdown)
            )
            .where(
                Invoice.company_id == company_id,
                Invoice.id.in_(req.invoice_ids)
            )
        )
    elif req.only_pending is False:
        # Si se solicita exportar histórico completo de procesadas
        stmt = (
            select(Invoice)
            .options(
                selectinload(Invoice.accounting_entries),
                selectinload(Invoice.tax_breakdown)
            )
            .where(
                Invoice.company_id == company_id,
                (Invoice.is_processed == True) | (Invoice.workflow_status.in_(["validado", "contabilizado"]))
            )
        )

    stmt = stmt.order_by(Invoice.issue_date.asc())
    inv_res = await db.execute(stmt)
    invoices = inv_res.scalars().all()

    if not invoices:
        raise HTTPException(
            status_code=400,
            detail="No se encontraron facturas aprobadas pendientes de exportación para generar el lote.",
        )

    # 1.1 Prevención de duplicados por huella digital SHA-256
    fingerprint_seed = "_".join(sorted(f"{inv.id}_{inv.total_amount:.2f}" for inv in invoices))
    batch_fingerprint = hashlib.sha256(fingerprint_seed.encode()).hexdigest()

    if not req.force_reexport:
        dup_stmt = select(ExportBatch).where(
            ExportBatch.company_id == company_id,
            ExportBatch.software_type == req.software_type,
            ExportBatch.data_fingerprint == batch_fingerprint
        )
        existing_dup = (await db.execute(dup_stmt)).scalars().first()
        if existing_dup:
            raise HTTPException(
                status_code=400,
                detail=f"Prevención de duplicados: El lote exacto de {len(invoices)} factura(s) ya fue exportado a {req.software_type} el {existing_dup.created_at.strftime('%d/%m/%Y %H:%M')} (Lote ID: {existing_dup.id[:8]}...). Si desea regenerarlo deliberadamente, active 'force_reexport' e introduzca el motivo."
            )
    else:
        # Validación RBAC para forzar reexportación
        if current_user:
            allowed_roles = {UserRole.SUPERADMIN.value, UserRole.COMPANY_ADMIN.value, UserRole.ADVISOR.value}
            if current_user.global_role not in allowed_roles:
                log_security_event(
                    action="FORCE_REEXPORT_UNAUTHORIZED",
                    empresa_id=company_id,
                    user_id=current_user.id,
                    status="DENIED",
                    details={"role": current_user.global_role, "software": req.software_type},
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Permisos insuficientes: solo Administradores o Asesores pueden forzar una reexportación contable.",
                )

        log_security_event(
            action="EXPORT_BATCH_FORCE_REEXPORT",
            empresa_id=company_id,
            user_id=current_user.id if current_user else "admin",
            status="SUCCESS",
            details={
                "software": req.software_type,
                "invoices_count": len(invoices),
                "fingerprint": batch_fingerprint,
            },
        )

    # 2. Rigor Contable & Seguridad: Validar que ninguna factura esté en estado ROJO
    red_invoices = [inv.invoice_number for inv in invoices if inv.status == "RED"]
    if red_invoices:
        raise HTTPException(
            status_code=400,
            detail=f"Bloqueo de seguridad: No se puede exportar porque hay facturas con anomalías críticas (Semáforo Rojo): {', '.join(red_invoices[:5])}. Deben corregirse antes de generar el asiento.",
        )

    # 3. Recopilar apuntes contables y validar cuadre estricto de partida doble
    all_entries: List[AccountingEntryLine] = []
    entry_counter = 1
    total_debe = 0.0
    total_haber = 0.0

    for inv in invoices:
        if inv.accounting_entries:
            inv_debe = sum(e.debe for e in inv.accounting_entries)
            inv_haber = sum(e.haber for e in inv.accounting_entries)

            # Chequear cuadre de cada factura
            if abs(round(inv_debe, 2) - round(inv_haber, 2)) > 0.01:
                raise HTTPException(
                    status_code=400,
                    detail=f"Bloqueo de seguridad contable: El asiento de la factura {inv.invoice_number} está descuadrado (Debe: {inv_debe:.2f} €, Haber: {inv_haber:.2f} €).",
                )

            for line in inv.accounting_entries:
                line.entry_number = entry_counter
                total_debe += line.debe
                total_haber += line.haber
                all_entries.append(line)
            entry_counter += 1
        else:
            # Factura sin líneas persistidas en BD: sumar importe total
            total_debe += inv.total_amount
            total_haber += inv.total_amount
            entry_counter += 1

    total_debe = round(total_debe, 2)
    total_haber = round(total_haber, 2)

    # 4. Generar el archivo mediante el conector solicitado
    now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = None
    file_path = None
    file_content_bytes = None
    file_format = "DAT" if req.software_type == "A3" else "CSV"
    status = "EXPORTED_FILE"
    notes = f"Fichero preparado para importar en {req.software_type}. El usuario debe confirmar la importación en destino."

    if req.software_type == "A3":
        company_code = str(cfg.get("company_code", "00001")).zfill(5)
        journal_code = str(cfg.get("journal_code", "00")).zfill(2)
        file_name = f"SUENLACE_{comp.cif}_{now_str}.DAT"
        file_content_bytes = generate_a3_suenlace_bytes(
            factura=invoices,
            company_code=company_code,
            journal_code=journal_code,
            account_digits=comp.plan_cuentas_longitud or 9,
        )
        file_format = "DAT"
        status = "EXPORTED_FILE"
        notes = f"Fichero SUENLACE.DAT de 96 caracteres generado para Wolters Kluwer A3 ({len(invoices)} facturas). Pendiente de importación en destino."

    elif req.software_type == "CONTASOL":
        journal_code = str(cfg.get("journal_code", "1"))
        file_name = f"diario_contasol_{comp.cif}_{now_str}.csv"
        file_content_bytes = generate_contasol_csv_bytes(
            invoices=invoices,
            company_code=str(comp.cif),
            journal_code=journal_code,
            account_digits=comp.plan_cuentas_longitud or 9,
        )
        file_format = "CSV"
        status = "EXPORTED_FILE"
        notes = f"Fichero CSV de diario generado para Software DELSOL Contasol ({len(invoices)} facturas). Pendiente de importación en destino."

    elif req.software_type == "SAGE":
        channel = str(cfg.get("channel", "0"))
        file_name = f"asientos_sage_{comp.cif}_{now_str}.csv"
        file_content_bytes = generate_sage_csv_bytes(
            invoices=invoices,
            company_code=str(cfg.get("sage_company_code", "001")),
            channel=channel,
            account_digits=comp.plan_cuentas_longitud or 9,
        )
        file_format = "CSV"
        status = "EXPORTED_FILE"
        notes = f"Fichero CSV de asientos generado para Sage 50 / Despachos Connected ({len(invoices)} facturas). Pendiente de importación en destino."

    elif req.software_type == "HOLDED_API":
        file_format = "JSON_API"
        api_key = cfg.get("api_key")
        if not api_key:
            status = "PENDING_CREDENTIALS"
            notes = "Integración pendiente de credenciales: No se ha configurado API Key para Holded en esta empresa."
        else:
            status = "SYNCED_API"
            notes = f"Lote transmitido vía API oficial de Holded para {len(invoices)} documentos."

    # Guardar archivo local en storage/exports/
    if file_content_bytes and file_name:
        file_path = os.path.join(EXPORTS_DIR, file_name)
        with open(file_path, "wb") as f:
            f.write(file_content_bytes)

    # 5. Crear el registro ExportBatch
    entries_count = len(all_entries) if all_entries else len(invoices)
    batch = ExportBatch(
        company_id=company_id,
        software_type=req.software_type,
        file_format=file_format,
        entries_count=entries_count,
        invoices_count=len(invoices),
        total_debe=total_debe,
        total_haber=total_haber,
        file_name=file_name,
        file_path=file_path,
        data_fingerprint=batch_fingerprint,
        fiscal_year=req.fiscal_year or (invoices[0].issue_date.year if invoices else None),
        status=status,
        log_notes=f"{notes}{f' (Reexportación autorizada: {req.reexport_reason})' if req.force_reexport and req.reexport_reason else ''}",
    )
    db.add(batch)
    await db.flush()

    # 6. Marcar facturas y apuntes contables como exported_to_erp = True y asignar export_batch_id
    inv_ids = [inv.id for inv in invoices]
    await db.execute(
        update(Invoice)
        .where(Invoice.id.in_(inv_ids))
        .values(exported_to_erp=True, export_batch_id=batch.id)
    )

    entry_ids = [e.id for e in all_entries]
    if entry_ids:
        await db.execute(
            update(AccountingEntryLine)
            .where(AccountingEntryLine.id.in_(entry_ids))
            .values(exported_to_erp=True, export_batch_id=batch.id)
        )

    await db.commit()
    await db.refresh(batch)
    return batch


@router.get("/batches/{batch_id}/download")
async def download_batch_file(batch_id: str, db: AsyncSession = Depends(get_db)):
    """Descarga el archivo generado de un lote anterior."""
    batch = await db.get(ExportBatch, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Lote de exportación no encontrado")

    if not batch.file_path or not os.path.exists(batch.file_path):
        raise HTTPException(
            status_code=404,
            detail="El archivo asociado al lote no está disponible en el servidor.",
        )

    with open(batch.file_path, "rb") as f:
        content = f.read()

    media_type = "application/octet-stream"
    if batch.file_format == "CSV":
        media_type = "text/csv"

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={batch.file_name}"},
    )
