import uuid
import hashlib
import mimetypes
from datetime import datetime, date
from pathlib import Path
from typing import List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, status, Response, Request
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.core.file_encryption import save_encrypted_file, read_decrypted_file, decrypt_file_bytes
from app.core.audit_logger import log_security_event
from app.core.file_inspector import inspect_file_bytes, sanitize_filename, FileSecurityViolationError
from app.models.company import Company
from app.models.supplier import Supplier
from app.models.invoice import Invoice, InvoiceTaxBreakdown
from app.models.accounting_entry import AccountingEntryLine
from app.models.account import Account
from app.models.contact import Contact
from app.schemas.invoice_dto import (
    InvoiceResponseDTO,
    InvoiceUpdateDTO,
    ApproveInvoiceDTO,
    BulkDeleteInvoicesDTO,
    PageThumbnailDTO,
    InvoicePagesResponseDTO,
    SplitInvoiceRequestDTO,
    SplitGroupDTO,
    NextSubaccountResponseDTO,
)
from app.schemas.invoice_extraction import InvoiceExtractionResult
from app.services.extractor_llm import extract_invoice_data
from app.services.validator import (
    validate_invoice_integrity,
    evaluate_invoice_rules,
    find_next_free_supplier_account,
    get_generic_supplier_account,
)
from app.services.accounting_engine import generate_accounting_entry_lines, format_subcuenta
from app.services.archiver import archive_invoice_file, get_proposed_archive_path
from app.services.nif_validator import normalize_nif

router = APIRouter()

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp"
}


def read_invoice_bytes_with_fallback(file_path: Union[str, Path]) -> bytes:
    """Lee un archivo de factura descifrándolo en memoria al vuelo (AES-256-GCM).
    
    Proporciona tolerancia y retrocompatibilidad total:
    Si el archivo ya estaba almacenado en texto plano (previo al cifrado en reposo
    o con cabecera estándar %PDF-), se retorna directamente como fallback sin fallar.
    De lo contrario, se descifra de forma segura con AES-256-GCM.
    """
    path = Path(file_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Archivo físico no encontrado: {path}")

    with open(path, "rb") as f:
        data = f.read()

    # Tolerancia/retrocompatibilidad: si ya era un PDF en claro o imagen sin cifrar
    if (
        data.startswith(b"%PDF-")
        or data.startswith(b"\x89PNG")
        or data.startswith(b"\xff\xd8")
        or data.startswith(b"RIFF")
    ):
        return data

    try:
        return decrypt_file_bytes(data)
    except Exception:
        # Fallback de seguridad si no era descifrable pero es legible
        return data


@router.post("/upload", response_model=InvoiceResponseDTO, status_code=status.HTTP_201_CREATED)
async def upload_and_process_invoice(
    file: UploadFile = File(..., description="Fichero de factura en formato PDF o imagen (PNG/JPEG)"),
    company_id: str = Form(..., description="ID de la empresa cliente en la asesoría"),
    db: AsyncSession = Depends(get_db)
):
    """
    Endpoint principal de ingesta:
    1. Recibe el archivo de la factura (PDF / Imagen).
    2. Extrae los datos fiscales mediante LLM multimodal estructurado (Gemini / OpenAI).
    3. Evalúa el motor de reglas semafórico (ROJO, AMARILLO, VERDE).
    4. Genera la propuesta de asiento contable en partida doble.
    5. Guarda el registro completo en la base de datos y lo devuelve para triaje.
    """
    # 1. Validar empresa
    comp_stmt = select(Company).where(Company.id == company_id)
    comp_res = await db.execute(comp_stmt)
    company = comp_res.scalars().first()
    
    if not company:
        # Para conveniencia en fase de desarrollo, si no existe la empresa buscada,
        # verificar si existe alguna empresa por defecto o crear una empresa demo
        all_comp_res = await db.execute(select(Company))
        company = all_comp_res.scalars().first()
        if not company:
            company = Company(
                id=company_id,
                cif="B12345678",
                razon_social="Asesoría Contable Demo S.L.",
                plan_cuentas_longitud=9
            )
            db.add(company)
            await db.commit()
            await db.refresh(company)

    # 2. Validar tipo de archivo y seguridad binaria profunda
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="El archivo subido está vacío.")

    try:
        inspection = inspect_file_bytes(file_bytes, file.filename or "factura.pdf")
        safe_filename = inspection["filename"]
    except FileSecurityViolationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Archivo rechazado por seguridad: {str(exc)}"
        )
    
    mime_type = file.content_type
    if not mime_type or mime_type == "application/octet-stream":
        guessed_type, _ = mimetypes.guess_type(safe_filename)
        mime_type = guessed_type or inspection.get("detected_mime_type") or "application/pdf"
    
    if mime_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Formato no compatible ({mime_type}). Debe ser PDF o imagen (PNG, JPG, WEBP)."
        )

    # 3. Guardar archivo cifrado en disco mediante AES-256-GCM (Encryption at Rest)
    orig_name = safe_filename
    enc_name = orig_name if orig_name.endswith(".enc") else f"{orig_name}.enc"
    unique_filename = f"{uuid.uuid4()}_{enc_name}"
    saved_file_path = settings.UPLOAD_DIR / unique_filename
    save_encrypted_file(saved_file_path, file_bytes)

    # 4.1 Cálculo del Hash SHA-256 del archivo para detección en tiempo real de duplicados
    file_hash = hashlib.sha256(file_bytes).hexdigest()

    # 4.2 Extracción de información mediante LLM multimodal estructurado
    try:
        extraction: InvoiceExtractionResult = await extract_invoice_data(
            file_bytes=file_bytes,
            mime_type=mime_type,
            file_name=file.filename
        )
    except ValueError as ve:
        if saved_file_path.exists():
            try:
                saved_file_path.unlink()
            except Exception:
                pass
        raise HTTPException(
            status_code=400,
            detail=str(ve)
        )
    except Exception as e:
        if saved_file_path.exists():
            try:
                saved_file_path.unlink()
            except Exception:
                pass
        raise HTTPException(
            status_code=400,
            detail=f"Error durante la extracción de datos con IA: {str(e)}"
        )

    # 5. Evaluación de Reglas Semafóricas (Rojo, Amarillo, Verde) con detección de duplicados y bloqueo contable
    rules_result = await evaluate_invoice_rules(
        extraction=extraction,
        company_id=company.id,
        db=db,
        file_hash=file_hash
    )

    # 5.1 Conteo de páginas e inspección de Multi-Factura (MF)
    num_paginas = 1
    if mime_type == "application/pdf" or file.filename.lower().endswith(".pdf"):
        try:
            import pymupdf
            # Análisis del PDF directamente en memoria sin leer disco cifrado
            pdf_doc = pymupdf.open(stream=file_bytes, filetype="pdf")
            num_paginas = len(pdf_doc)
            pdf_doc.close()
        except Exception:
            num_paginas = 1

    # Regla PRD: Si el archivo subido tiene más de 1 página o la IA detecta varias facturas, marca es_multifactura = True y estado a_revisar con badge visual 'MF'
    es_multifactura = (num_paginas > 1)
    if es_multifactura:
        workflow_status = "a_revisar"
        mf_reason = f"Documento multi-página ({num_paginas} págs) detectado como Multi-Factura (MF). Requiere separación o corte documental."
        if mf_reason not in rules_result.reasons:
            rules_result.reasons.append(mf_reason)
    else:
        if rules_result.status.value == "GREEN":
            workflow_status = "prevalidado"
        else:
            workflow_status = "a_revisar"

    # 6. Parseo de fecha de emisión y ajuste contable por bloqueo de cierre
    try:
        parsed_issue_date = datetime.strptime(extraction.issue_date, "%Y-%m-%d").date()
    except Exception:
        parsed_issue_date = date.today()

    parsed_accounting_date = parsed_issue_date
    if rules_result.adjusted_fecha_contable:
        try:
            parsed_accounting_date = datetime.strptime(rules_result.adjusted_fecha_contable, "%Y-%m-%d").date()
        except Exception:
            parsed_accounting_date = parsed_issue_date

    parsed_due_date = None
    if extraction.due_date:
        try:
            parsed_due_date = datetime.strptime(extraction.due_date, "%Y-%m-%d").date()
        except Exception:
            parsed_due_date = None

    has_ret = (extraction.retention_amount or 0.0) > 0 or (extraction.retention_rate or 0.0) > 0
    ret_pct = float(extraction.retention_rate or (15.0 if has_ret else 0.0))

    # 7. Crear entidad Invoice en DB con máquina de estados y casuísticas de Fase 2
    invoice = Invoice(
        company_id=company.id,
        supplier_id=rules_result.supplier_id,
        file_path=str(saved_file_path),
        file_name=file.filename,
        file_hash=file_hash,
        invoice_number=extraction.invoice_number,
        issue_date=parsed_issue_date,
        due_date=parsed_due_date,
        fecha_contable=parsed_accounting_date,
        issuer_name=extraction.issuer_name,
        issuer_cif=normalize_nif(extraction.issuer_tax_id),
        recipient_name=extraction.recipient_name,
        recipient_cif=normalize_nif(extraction.recipient_tax_id) if extraction.recipient_tax_id else None,
        total_base=round(extraction.total_base or 0.0, 2),
        total_tax=round(extraction.total_tax or 0.0, 2),
        total_retention=round(extraction.retention_amount or 0.0, 2),
        total_amount=round(extraction.total_amount or 0.0, 2),
        currency=extraction.currency or "EUR",
        concept_summary=extraction.concept_summary,
        has_retention=has_ret,
        retention_percentage=ret_pct,
        retention_model="111/190",
        has_suplidos=False,
        suplidos_amount=0.0,
        is_rectificativa=False,
        country_code="ES",
        is_duplicate=rules_result.is_duplicate,
        duplicate_of_id=rules_result.duplicate_of_id,
        status=rules_result.status.value,
        status_reasons=rules_result.reasons,
        workflow_status=workflow_status,
        es_multifactura=es_multifactura,
        num_paginas=num_paginas,
        raw_extraction=extraction.model_dump(),
        is_processed=False
    )
    db.add(invoice)
    await db.flush()  # Obtener invoice.id

    # 8. Guardar desglose de impuestos
    if extraction.taxes:
        for t in extraction.taxes:
            tax_record = InvoiceTaxBreakdown(
                invoice_id=invoice.id,
                tax_rate=t.tax_rate,
                tax_base=round(t.base_amount, 2),
                tax_amount=round(t.tax_amount, 2)
            )
            db.add(tax_record)

    # 9. Obtener proveedor para generar apuntes con sus cuentas configuradas
    supplier = None
    if rules_result.supplier_id:
        supp_res = await db.execute(select(Supplier).where(Supplier.id == rules_result.supplier_id))
        supplier = supp_res.scalars().first()

    # 10. Generar asiento contable automático (con fecha contable ajustada y cuentas del PGC)
    entry_lines = generate_accounting_entry_lines(
        extraction=extraction,
        plan_longitud=company.plan_cuentas_longitud,
        supplier=supplier,
        entry_date=parsed_accounting_date,
        custom_supplier_account=rules_result.suggested_supplier_account,
        custom_expense_account=rules_result.suggested_expense_account,
        is_rectificativa=False,
        retention_model="111/190"
    )
    for line in entry_lines:
        entry_record = AccountingEntryLine(
            invoice_id=invoice.id,
            company_id=company.id,
            entry_number=line.entry_number,
            fecha=line.fecha,
            subcuenta=line.subcuenta,
            concepto=line.concepto,
            debe=line.debe,
            haber=line.haber,
            documento=line.documento
        )
        db.add(entry_record)

    # 10.1 Si la factura es VERDE automática y NO es multifactura, marcar procesada y archivar
    if rules_result.status.value == "GREEN" and not es_multifactura:
        archive_invoice_file(invoice, company.cif)
        invoice.is_processed = True
        invoice.workflow_status = "archivado"
    else:
        invoice.is_processed = False

    await db.commit()

    # 11. Cargar factura completa con relaciones para la respuesta
    final_stmt = (
        select(Invoice)
        .where(Invoice.id == invoice.id)
        .options(
            selectinload(Invoice.tax_breakdown),
            selectinload(Invoice.accounting_entries)
        )
    )
    final_res = await db.execute(final_stmt)
    full_invoice = final_res.scalars().first()

    return full_invoice


@router.get("", response_model=List[InvoiceResponseDTO])
async def list_invoices(
    company_id: Optional[str] = Query(None, description="Filtrar por empresa"),
    status: Optional[str] = Query(None, description="Filtrar por estado: GREEN, YELLOW, RED"),
    is_processed: Optional[bool] = Query(None, description="Filtrar por procesadas/pendientes"),
    db: AsyncSession = Depends(get_db)
):
    """Lista facturas con filtros para el panel de triaje."""
    stmt = select(Invoice).options(
        selectinload(Invoice.tax_breakdown),
        selectinload(Invoice.accounting_entries)
    ).order_by(Invoice.created_at.desc())

    if company_id:
        stmt = stmt.where(Invoice.company_id == company_id)
    if status:
        stmt = stmt.where(Invoice.status == status.upper())
    if is_processed is not None:
        stmt = stmt.where(Invoice.is_processed == is_processed)

    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{invoice_id}", response_model=InvoiceResponseDTO)
async def get_invoice(
    invoice_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Obtiene los detalles de una factura específica."""
    stmt = (
        select(Invoice)
        .where(Invoice.id == invoice_id)
        .options(
            selectinload(Invoice.tax_breakdown),
            selectinload(Invoice.accounting_entries)
        )
    )
    result = await db.execute(stmt)
    invoice = result.scalars().first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Factura no encontrada.")
    return invoice


@router.get("/{invoice_id}/file")
@router.get("/{invoice_id}/download")
async def get_invoice_file(
    invoice_id: str,
    download: bool = Query(False, description="Si es True, fuerza descarga como archivo adjunto"),
    request: Request = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Descarga o visualiza en memoria el documento original descifrado al vuelo (AES-256-GCM).
    
    Descifra los bytes directamente en memoria sin dejar copias en texto plano en el servidor.
    Cuenta con retrocompatibilidad automática si el archivo ya fue almacenado en claro previamente.
    """
    invoice = await db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Factura no encontrada.")

    if not invoice.file_path:
        raise HTTPException(status_code=404, detail="La factura no tiene una ruta de archivo asociada.")

    file_p = Path(invoice.file_path)
    if not file_p.exists():
        raise HTTPException(status_code=404, detail="Archivo físico no encontrado en el servidor.")

    try:
        decrypted_bytes = read_decrypted_file(file_p)
    except Exception:
        # Tolerancia y retrocompatibilidad: si el archivo ya era un PDF en claro previo al cifrado
        with open(file_p, "rb") as f:
            raw_bytes = f.read()
        if raw_bytes.startswith(b"%PDF-") or raw_bytes.startswith(b"\x89PNG") or raw_bytes.startswith(b"\xff\xd8"):
            decrypted_bytes = raw_bytes
        else:
            try:
                decrypted_bytes = decrypt_file_bytes(raw_bytes)
            except Exception:
                decrypted_bytes = raw_bytes

    mime, _ = mimetypes.guess_type(invoice.file_name or str(file_p))
    media_type = mime or "application/pdf"
    disposition = "attachment" if download else "inline"
    safe_filename = invoice.file_name or file_p.name
    if safe_filename.endswith(".enc"):
        safe_filename = safe_filename[:-4]

    # Registro de auditoría de seguridad y trazabilidad RGPD / AEAT
    action_type = "INVOICE_DOWNLOAD" if download else "INVOICE_VIEW"
    log_security_event(
        action=action_type,
        resource_id=str(invoice_id),
        request=request,
        user_id=getattr(current_user, "id", None) if "current_user" in locals() else None,
        empresa_id=str(getattr(invoice, "company_id", getattr(invoice, "empresa_id", None))) if "invoice" in locals() else None,
        status="SUCCESS",
        details={"filename": getattr(invoice, "file_name", None)}
    )

    return Response(
        content=decrypted_bytes,
        media_type=media_type,
        headers={
            "Content-Disposition": f'{disposition}; filename="{safe_filename}"',
            "Cache-Control": "private, no-cache, no-store, must-revalidate",
            "X-Content-Type-Options": "nosniff",
        }
    )


@router.get("/companies/{company_id}/next-subaccount", response_model=NextSubaccountResponseDTO)
async def get_next_subaccount(
    company_id: str,
    prefix: str = Query("410", pattern="^(400|410)$"),
    db: AsyncSession = Depends(get_db)
):
    """
    Calcula y reserva la siguiente subcuenta correlativa libre de proveedor/acreedor
    según la longitud configurada en la empresa (ej. 41000004 o 410000004).
    """
    comp = await db.get(Company, company_id)
    if not comp:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    digits = comp.plan_cuentas_longitud or 9
    next_sub = await find_next_free_supplier_account(company_id, digits, db, prefix=prefix)
    gen_sub = get_generic_supplier_account(prefix, digits)
    return NextSubaccountResponseDTO(
        next_subaccount=next_sub,
        generic_subaccount=gen_sub,
        prefix=prefix,
        digits=digits
    )


@router.put("/{invoice_id}", response_model=InvoiceResponseDTO)
async def update_invoice(
    invoice_id: str,
    payload: InvoiceUpdateDTO,
    db: AsyncSession = Depends(get_db)
):
    """
    Actualiza los datos de la factura tras la revisión del asesor contable en el panel de triaje,
    reevaluando las reglas semafóricas y actualizando el asiento.
    """
    stmt = (
        select(Invoice)
        .where(Invoice.id == invoice_id)
        .options(
            selectinload(Invoice.tax_breakdown),
            selectinload(Invoice.accounting_entries)
        )
    )
    res = await db.execute(stmt)
    invoice = res.scalars().first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Factura no encontrada.")

    # Actualizar campos proporcionados
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(invoice, field, value)

    # Reevaluar reglas con los nuevos importes/proveedor
    extracted_obj = InvoiceExtractionResult(
        issuer_name=invoice.issuer_name,
        issuer_tax_id=invoice.issuer_cif,
        invoice_number=invoice.invoice_number,
        issue_date=str(invoice.issue_date),
        total_base=invoice.total_base,
        total_tax=invoice.total_tax,
        retention_amount=invoice.total_retention,
        total_amount=invoice.total_amount,
        concept_summary=invoice.concept_summary
    )

    rules_eval = await evaluate_invoice_rules(
        extraction=extracted_obj,
        company_id=invoice.company_id,
        db=db,
        current_invoice_id=invoice.id,
        file_hash=invoice.file_hash
    )

    invoice.status = rules_eval.status.value
    invoice.status_reasons = rules_eval.reasons
    invoice.is_duplicate = rules_eval.is_duplicate
    invoice.duplicate_of_id = rules_eval.duplicate_of_id

    if payload.supplier_id:
        invoice.supplier_id = payload.supplier_id

    # Si se ajustó la fecha contable por bloqueo de cierre y no venía fijada manualmente
    if rules_eval.adjusted_fecha_contable and not payload.fecha_contable:
        try:
            invoice.fecha_contable = datetime.strptime(rules_eval.adjusted_fecha_contable, "%Y-%m-%d").date()
        except Exception:
            pass

    # Regenerar el asiento contable para reflejar suplidos, retenciones, rectificativa o cambios de importes
    comp_res = await db.execute(select(Company).where(Company.id == invoice.company_id))
    company = comp_res.scalars().first()
    plan_long = company.plan_cuentas_longitud if company else 9

    supplier = None
    if invoice.supplier_id:
        supp_res = await db.execute(select(Supplier).where(Supplier.id == invoice.supplier_id))
        supplier = supp_res.scalars().first()

    # Limpiar líneas de asiento existentes
    await db.execute(delete(AccountingEntryLine).where(AccountingEntryLine.invoice_id == invoice.id))

    new_entries = generate_accounting_entry_lines(
        extraction=extracted_obj,
        plan_longitud=plan_long,
        supplier=supplier,
        entry_date=invoice.fecha_contable or invoice.issue_date,
        custom_supplier_account=rules_eval.suggested_supplier_account,
        custom_expense_account=rules_eval.suggested_expense_account,
        suplidos_amount=invoice.suplidos_amount or 0.0,
        custom_suplidos_account=invoice.suplidos_account,
        is_rectificativa=invoice.is_rectificativa or False,
        retention_model=invoice.retention_model or "111/190"
    )

    for line in new_entries:
        db.add(AccountingEntryLine(
            invoice_id=invoice.id,
            company_id=invoice.company_id,
            entry_number=line.entry_number,
            fecha=line.fecha,
            subcuenta=line.subcuenta,
            concepto=line.concepto,
            debe=line.debe,
            haber=line.haber,
            documento=line.documento
        ))

    await db.commit()

    # Recargar relaciones
    refreshed_stmt = (
        select(Invoice)
        .where(Invoice.id == invoice_id)
        .options(
            selectinload(Invoice.tax_breakdown),
            selectinload(Invoice.accounting_entries)
        )
    )
    refreshed_res = await db.execute(refreshed_stmt)
    return refreshed_res.scalars().first()


@router.get("/companies/{company_id}/next-subaccount", response_model=NextSubaccountResponseDTO)
async def get_next_subaccount(
    company_id: str,
    prefix: str = Query("410", description="Prefijo contable (ej. 410 o 400)"),
    db: AsyncSession = Depends(get_db)
):
    """
    Calcula y reserva la siguiente subcuenta correlativa libre para un proveedor/acreedor nuevo
    (ej. 41000004 si son 8 dígitos o 410000004 si son 9 dígitos) y devuelve la genérica (41000000).
    """
    comp = await db.get(Company, company_id)
    if not comp:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    plan_len = comp.plan_cuentas_longitud or 9
    clean_prefix = prefix.strip()[:3]
    if not clean_prefix.isdigit():
        clean_prefix = "410"

    next_sub = await find_next_free_supplier_account(company_id, plan_len, db, prefix=clean_prefix)
    gen_sub = get_generic_supplier_account(clean_prefix, plan_len)

    return NextSubaccountResponseDTO(
        prefix=clean_prefix,
        next_subaccount=next_sub,
        generic_subaccount=gen_sub,
        company_plan_longitud=plan_len
    )


@router.get("/{invoice_id}/proposed-archive-path")
async def get_invoice_proposed_path(
    invoice_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Devuelve la ruta y nombre propuestos por el sistema para visualización/edición previa al archivado."""
    res = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    invoice = res.scalars().first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Factura no encontrada.")

    comp_res = await db.execute(select(Company).where(Company.id == invoice.company_id))
    company = comp_res.scalars().first()
    company_cif = company.cif if company else "EMPRESA"
    storage_base = company.storage_base_path if company else "storage"
    company_periodicity = getattr(company, "iva_periodicity", "Trimestral") if company else "Trimestral"

    proposed = get_proposed_archive_path(
        invoice,
        company_cif,
        base_path_str=storage_base,
        iva_periodicity=company_periodicity
    )
    return proposed


@router.post("/{invoice_id}/approve", response_model=InvoiceResponseDTO)
async def approve_invoice(
    invoice_id: str,
    payload: Optional[ApproveInvoiceDTO] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Marca la factura como contabilizada/aprobada definitivamente y
    la mueve y renombra a la ruta destino (por defecto o personalizada por el usuario).
    """
    stmt = (
        select(Invoice)
        .where(Invoice.id == invoice_id)
        .options(
            selectinload(Invoice.tax_breakdown),
            selectinload(Invoice.accounting_entries)
        )
    )
    res = await db.execute(stmt)
    invoice = res.scalars().first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Factura no encontrada.")

    # 1. Bloqueo estricto de seguridad: No se puede aprobar si está en ROJO
    if invoice.status == "RED":
        reasons_str = "; ".join(invoice.status_reasons or ["Factura con anomalías graves"])
        raise HTTPException(
            status_code=400,
            detail=f"Bloqueo estricto de seguridad: No se puede aprobar ni contabilizar una factura con semáforo ROJO ({reasons_str}). Debe corregir las incidencias antes de continuar."
        )

    # 2. Obtener la empresa para conocer su CIF fiscal, ruta base, longitud de plan contable y periodicidad de IVA
    comp_res = await db.execute(select(Company).where(Company.id == invoice.company_id))
    company = comp_res.scalars().first()
    company_cif = company.cif if company else "EMPRESA_GENERAL"
    storage_base = company.storage_base_path if company else "storage"
    company_periodicity = getattr(company, "iva_periodicity", "Trimestral") if company else "Trimestral"
    plan_longitud = company.plan_cuentas_longitud if company else 9

    # 3. Identificar subcuentas contables de proveedor (400/410) y gasto (6XX) asociadas
    subcuenta_prov = None
    subcuenta_gasto = None
    if invoice.accounting_entries:
        for entry in invoice.accounting_entries:
            if entry.subcuenta.startswith("400") or entry.subcuenta.startswith("410"):
                subcuenta_prov = entry.subcuenta
            elif entry.subcuenta.startswith("6"):
                subcuenta_gasto = entry.subcuenta

    if not subcuenta_prov:
        subcuenta_prov = format_subcuenta("400", "1", plan_longitud)
    if not subcuenta_gasto:
        subcuenta_gasto = format_subcuenta("629", "0", plan_longitud)

    # 4. Asistencia Inteligente: Alta automática en el Plan General Contable (Account), Proveedores y Contactos
    if invoice.issuer_cif:
        # A. Asegurar subcuenta de Proveedor en Account
        acc_prov_res = await db.execute(
            select(Account).where(
                Account.company_id == invoice.company_id,
                Account.codigo == subcuenta_prov
            )
        )
        if not acc_prov_res.scalars().first():
            db.add(Account(
                company_id=invoice.company_id,
                codigo=subcuenta_prov,
                descripcion=invoice.issuer_name or "Proveedor",
                tipo="PROVEEDOR",
                cif_asociado=invoice.issuer_cif,
                debe_inicial=0.0,
                haber_inicial=0.0
            ))

        # B. Asegurar subcuenta de Gasto en Account
        acc_exp_res = await db.execute(
            select(Account).where(
                Account.company_id == invoice.company_id,
                Account.codigo == subcuenta_gasto
            )
        )
        if not acc_exp_res.scalars().first():
            db.add(Account(
                company_id=invoice.company_id,
                codigo=subcuenta_gasto,
                descripcion=f"Gasto - {invoice.concept_summary or 'Servicios exteriores'}",
                tipo="GASTO",
                debe_inicial=0.0,
                haber_inicial=0.0
            ))

        # C. Asegurar en maestro de Proveedores (Supplier)
        supp_res = await db.execute(
            select(Supplier).where(
                Supplier.company_id == invoice.company_id,
                Supplier.cif == invoice.issuer_cif
            )
        )
        existing_supp = supp_res.scalars().first()
        if not existing_supp:
            new_supp = Supplier(
                company_id=invoice.company_id,
                cif=invoice.issuer_cif,
                nombre=invoice.issuer_name or "Proveedor",
                subcuenta_proveedor=subcuenta_prov,
                subcuenta_gasto_defecto=subcuenta_gasto
            )
            db.add(new_supp)
            await db.flush()
            invoice.supplier_id = new_supp.id
        else:
            invoice.supplier_id = existing_supp.id

        # D. Asegurar en directorio de Contactos (Contact)
        contact_res = await db.execute(
            select(Contact).where(
                Contact.company_id == invoice.company_id,
                Contact.cif == invoice.issuer_cif
            )
        )
        if not contact_res.scalars().first():
            db.add(Contact(
                company_id=invoice.company_id,
                contact_type="SUPPLIER",
                cif=invoice.issuer_cif,
                razon_social=invoice.issuer_name or "Proveedor",
                subcuenta_default=subcuenta_prov
            ))

        # E. Transición de estado a VERDE tras la aprobación
        invoice.status = "GREEN"
        invoice.status_reasons = ["Factura aprobada y proveedor registrado en el Plan Contable."]

    # 5. Mover y renombrar a la carpeta destino oficial
    custom_subfolder = payload.custom_subfolder if payload else None
    custom_filename = payload.custom_filename if payload else None

    archive_invoice_file(
        invoice=invoice,
        company_cif=company_cif,
        custom_subfolder=custom_subfolder,
        custom_filename=custom_filename,
        base_path_str=storage_base,
        iva_periodicity=company_periodicity
    )

    invoice.is_processed = True
    invoice.workflow_status = "archivado"
    await db.commit()
    
    # Recargar la factura con todas sus relaciones para serialización Pydantic garantizada
    reload_stmt = (
        select(Invoice)
        .where(Invoice.id == invoice.id)
        .options(
            selectinload(Invoice.tax_breakdown),
            selectinload(Invoice.accounting_entries)
        )
    )
    reload_res = await db.execute(reload_stmt)
    full_invoice = reload_res.scalars().first()
    return full_invoice


@router.delete("/{invoice_id}")
async def delete_invoice(
    invoice_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Elimina una factura individualmente:
    1. Borra físicamente el archivo del disco (en uploads/ o storage/).
    2. Borra los registros relacionales (factura, desgloses y apuntes) en cascada.
    """
    res = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    invoice = res.scalars().first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Factura no encontrada.")

    # Borrar archivo físico si existe
    file_deleted = False
    if invoice.file_path:
        p = Path(invoice.file_path)
        if p.exists():
            try:
                p.unlink()
                file_deleted = True
            except Exception:
                pass

    await db.delete(invoice)
    await db.commit()

    return {
        "success": True,
        "message": "Factura y archivo físico eliminados correctamente.",
        "deleted_id": invoice_id,
        "file_deleted": file_deleted
    }


@router.post("/bulk-delete")
@router.delete("/bulk")
async def bulk_delete_invoices(
    payload: BulkDeleteInvoicesDTO,
    db: AsyncSession = Depends(get_db)
):
    """
    Elimina múltiples facturas por lotes:
    Borra físicamente cada archivo del disco y elimina los registros de la base de datos.
    """
    if not payload.invoice_ids:
        return {"success": True, "deleted_count": 0, "deleted_ids": []}

    stmt = select(Invoice).where(Invoice.id.in_(payload.invoice_ids))
    res = await db.execute(stmt)
    invoices = res.scalars().all()

    deleted_files = 0
    deleted_ids = []

    for inv in invoices:
        if inv.file_path:
            p = Path(inv.file_path)
            if p.exists():
                try:
                    p.unlink()
                    deleted_files += 1
                except Exception:
                    pass
        deleted_ids.append(inv.id)
        await db.delete(inv)

    await db.commit()

    return {
        "success": True,
        "deleted_count": len(deleted_ids),
        "deleted_files_count": deleted_files,
        "deleted_ids": deleted_ids
    }


# ==============================================================================
# MAQUETADOR VISUAL DE CORTE MULTI-FACTURA (MF) - PRD FASE 1
# ==============================================================================

@router.get("/{invoice_id}/pages", response_model=InvoicePagesResponseDTO)
async def get_invoice_pages(
    invoice_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Obtiene el listado de páginas de un documento para el Maquetador Visual de Corte.
    """
    invoice = await db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Factura no encontrada")

    file_p = Path(invoice.file_path)
    num_paginas = invoice.num_paginas or 1

    if file_p.exists():
        try:
            raw_bytes = read_invoice_bytes_with_fallback(file_p)
            import pymupdf
            doc = pymupdf.open(stream=raw_bytes, filetype="pdf")
            num_paginas = len(doc)
            doc.close()
        except Exception:
            pass

    pages = [
        PageThumbnailDTO(
            page_number=i + 1,
            thumbnail_url=f"/api/v1/invoices/{invoice_id}/pages/{i + 1}/thumbnail"
        )
        for i in range(num_paginas)
    ]

    return InvoicePagesResponseDTO(
        invoice_id=invoice.id,
        file_name=invoice.file_name,
        num_paginas=num_paginas,
        es_multifactura=invoice.es_multifactura,
        pages=pages
    )


@router.get("/{invoice_id}/pages/{page_number}/thumbnail")
async def get_page_thumbnail(
    invoice_id: str,
    page_number: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Genera y devuelve la miniatura visual en alta resolución de una página de la factura.
    """
    invoice = await db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Factura no encontrada")

    file_p = Path(invoice.file_path)
    if not file_p.exists():
        raise HTTPException(status_code=404, detail="Archivo físico no encontrado en el servidor")

    try:
        raw_bytes = read_invoice_bytes_with_fallback(file_p)
        import pymupdf
        doc = pymupdf.open(stream=raw_bytes, filetype="pdf")
        if page_number < 1 or page_number > len(doc):
            doc.close()
            raise HTTPException(status_code=400, detail=f"Página {page_number} fuera de rango (1..{len(doc)})")
        page = doc.load_page(page_number - 1)
        pix = page.get_pixmap(dpi=120)
        img_bytes = pix.tobytes("png")
        doc.close()
        return Response(content=img_bytes, media_type="image/png")
    except HTTPException:
        raise
    except Exception:
        # Fallback para imágenes directas (PNG/JPEG/WEBP)
        try:
            raw_bytes = read_invoice_bytes_with_fallback(file_p)
            mime, _ = mimetypes.guess_type(invoice.file_name or str(file_p))
            return Response(content=raw_bytes, media_type=mime or "image/jpeg")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error renderizando página {page_number}: {str(e)}")



@router.post("/{invoice_id}/split", response_model=List[InvoiceResponseDTO])
async def split_invoice(
    invoice_id: str,
    payload: SplitInvoiceRequestDTO,
    request: Request = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Disgrega un documento Multi-Factura (MF) en sub-documentos independientes nombrados:
    [original]_factura_[index].pdf
    Procesa cada sub-documento con extracción de IA y motor semafórico.
    """
    orig_invoice = await db.get(Invoice, invoice_id)
    if not orig_invoice:
        raise HTTPException(status_code=404, detail="Factura original no encontrada")

    if not payload.splits:
        raise HTTPException(status_code=400, detail="Debe especificar al menos un grupo de páginas a separar.")

    orig_path = Path(orig_invoice.file_path)
    if not orig_path.exists():
        raise HTTPException(status_code=404, detail="El archivo original no existe en el disco.")

    company = await db.get(Company, orig_invoice.company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    import pymupdf
    try:
        orig_bytes = read_invoice_bytes_with_fallback(orig_path)
        orig_doc = pymupdf.open(stream=orig_bytes, filetype="pdf")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"No se pudo abrir el PDF original: {str(e)}")

    total_orig_pages = len(orig_doc)
    original_stem = Path(orig_invoice.file_name).stem
    # Eliminar posibles prefijos de uuid del nombre para que quede limpio
    clean_stem = original_stem
    if "_" in clean_stem and len(clean_stem.split("_")[0]) == 36:
        clean_stem = clean_stem.split("_", 1)[1]

    created_sub_invoices = []

    try:
        for idx, split_item in enumerate(payload.splits):
            pages_to_extract = split_item.page_numbers
            if not pages_to_extract:
                continue

            # Validar páginas
            valid_pages = [p for p in pages_to_extract if 1 <= p <= total_orig_pages]
            if not valid_pages:
                continue

            # Crear nuevo PDF para este sub-documento
            sub_doc = pymupdf.open()
            for p_num in valid_pages:
                sub_doc.insert_pdf(orig_doc, from_page=p_num - 1, to_page=p_num - 1)

            # Nombre oficial: [original]_factura_[index].pdf
            sub_clean_name = f"{clean_stem}_factura_{idx + 1}.pdf"
            sub_unique_name = f"{uuid.uuid4()}_{sub_clean_name}.enc"
            sub_file_path = settings.UPLOAD_DIR / sub_unique_name

            # Obtener bytes del nuevo sub-documento en memoria y guardar cifrado
            sub_bytes = sub_doc.tobytes()
            sub_doc.close()

            save_encrypted_file(sub_file_path, sub_bytes)

            # Extracción con IA
            try:
                extraction: InvoiceExtractionResult = await extract_invoice_data(
                    file_bytes=sub_bytes,
                    mime_type="application/pdf",
                    file_name=sub_clean_name
                )
            except Exception:
                # Si falla la extracción LLM para esta página, fallback genérico
                extraction = InvoiceExtractionResult(
                    issuer_name=orig_invoice.issuer_name or "Proveedor Desconocido",
                    issuer_tax_id=orig_invoice.issuer_cif or "",
                    invoice_number=f"{orig_invoice.invoice_number or 'DOC'}-{idx + 1}",
                    issue_date=str(orig_invoice.issue_date or date.today()),
                    total_base=0.0,
                    total_tax=0.0,
                    total_amount=0.0,
                    concept_summary=f"Sub-documento separado (págs {', '.join(map(str, valid_pages))})"
                )

            # Evaluación de reglas semafóricas
            rules_result = await evaluate_invoice_rules(
                extraction=extraction,
                company_id=company.id,
                db=db
            )

            # Parseo de fechas
            try:
                parsed_issue = datetime.strptime(extraction.issue_date, "%Y-%m-%d").date()
            except Exception:
                parsed_issue = date.today()

            parsed_due = None
            if extraction.due_date:
                try:
                    parsed_due = datetime.strptime(extraction.due_date, "%Y-%m-%d").date()
                except Exception:
                    parsed_due = None

            sub_num_p = len(valid_pages)
            sub_is_mf = (sub_num_p > 1)
            sub_wf = "prevalidado" if rules_result.status.value == "GREEN" and not sub_is_mf else "a_revisar"

            # Crear Invoice en DB
            sub_invoice = Invoice(
                company_id=company.id,
                supplier_id=rules_result.supplier_id,
                parent_invoice_id=orig_invoice.id,
                file_path=str(sub_file_path),
                file_name=sub_clean_name,
                invoice_number=extraction.invoice_number or f"{clean_stem}_{idx + 1}",
                issue_date=parsed_issue,
                due_date=parsed_due,
                issuer_name=extraction.issuer_name or orig_invoice.issuer_name,
                issuer_cif=normalize_nif(extraction.issuer_tax_id) if extraction.issuer_tax_id else orig_invoice.issuer_cif,
                recipient_name=extraction.recipient_name or orig_invoice.recipient_name,
                recipient_cif=normalize_nif(extraction.recipient_tax_id) if extraction.recipient_tax_id else orig_invoice.recipient_cif,
                total_base=round(extraction.total_base or 0.0, 2),
                total_tax=round(extraction.total_tax or 0.0, 2),
                total_retention=round(extraction.retention_amount or 0.0, 2),
                total_amount=round(extraction.total_amount or 0.0, 2),
                currency=extraction.currency or "EUR",
                concept_summary=extraction.concept_summary or f"Factura {idx + 1} segregada de {orig_invoice.file_name}",
                status=rules_result.status.value,
                status_reasons=rules_result.reasons,
                workflow_status=sub_wf,
                es_multifactura=sub_is_mf,
                num_paginas=sub_num_p,
                raw_extraction=extraction.model_dump(),
                is_processed=False
            )
            db.add(sub_invoice)
            await db.flush()

            # Desglose de impuestos
            if extraction.taxes:
                for t in extraction.taxes:
                    db.add(InvoiceTaxBreakdown(
                        invoice_id=sub_invoice.id,
                        tax_rate=t.tax_rate,
                        tax_base=round(t.base_amount, 2),
                        tax_amount=round(t.tax_amount, 2)
                    ))

            # Proveedor y apuntes contables
            supplier = None
            if rules_result.supplier_id:
                supp_res = await db.execute(select(Supplier).where(Supplier.id == rules_result.supplier_id))
                supplier = supp_res.scalars().first()

            entry_lines = generate_accounting_entry_lines(
                extraction=extraction,
                plan_longitud=company.plan_cuentas_longitud,
                supplier=supplier,
                entry_date=parsed_issue,
                custom_supplier_account=rules_result.suggested_supplier_account,
                custom_expense_account=rules_result.suggested_expense_account
            )
            for line in entry_lines:
                db.add(AccountingEntryLine(
                    invoice_id=sub_invoice.id,
                    company_id=company.id,
                    entry_number=line.entry_number,
                    fecha=line.fecha,
                    subcuenta=line.subcuenta,
                    concepto=line.concepto,
                    debe=line.debe,
                    haber=line.haber,
                    documento=line.documento
                ))

            created_sub_invoices.append(sub_invoice)

        # Marcar la factura padre original como archivada / disgregada
        orig_invoice.is_processed = True
        orig_invoice.workflow_status = "archivado"
        orig_invoice.status_reasons = [f"Documento original disgregado en {len(created_sub_invoices)} sub-facturas independientes."]

        await db.commit()

    finally:
        orig_doc.close()

    # Recargar con relaciones para la respuesta
    sub_ids = [inv.id for inv in created_sub_invoices]
    final_res = await db.execute(
        select(Invoice)
        .where(Invoice.id.in_(sub_ids))
        .options(
            selectinload(Invoice.tax_breakdown),
            selectinload(Invoice.accounting_entries)
        )
        .order_by(Invoice.created_at.asc())
    )

    # Registro de auditoría para la disgregación de documento
    log_security_event(
        action="INVOICE_SPLIT",
        resource_id=str(invoice_id),
        request=request,
        user_id=getattr(current_user, "id", None) if "current_user" in locals() else None,
        empresa_id=str(getattr(company, "id", getattr(orig_invoice, "company_id", None))) if "company" in locals() else None,
        status="SUCCESS",
        details={
            "sub_invoices_count": len(created_sub_invoices),
            "sub_invoice_ids": [inv.id for inv in created_sub_invoices],
            "original_filename": orig_invoice.file_name,
        }
    )

    return final_res.scalars().all()


