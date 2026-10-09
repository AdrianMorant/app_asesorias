"""Módulo de Recepción y Procesamiento de Webhooks Inbound (SendGrid, Postmark, Mailgun).

Procesa correos electrónicos entrantes con facturas adjuntas:
1. Valida el remitente contra directivas de seguridad y listas negras.
2. Identifica automáticamente la empresa destinataria (por alias o token).
3. Inspecciona Magic Bytes y sanea nombres contra Path Traversal.
4. Cifra los ficheros en reposo (AES-256-GCM) sin persistencia en claro.
5. Encola de manera asíncrona el procesamiento con el motor de OCR y autoaprendizaje contable.
6. Registra trazabilidad de seguridad inmutable (RGPD / LGT).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status, UploadFile, File, Form
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db, AsyncSessionLocal
from app.core.audit_logger import log_security_event
from app.models.company import Company
from app.models.invoice import Invoice, InvoiceTaxBreakdown
from app.services.email_ingestion_service import (
    parse_inbound_email,
    process_email_attachments,
    EmailIngestionError,
)
from app.services.ocr_extraction_service import extract_invoice_data

logger = logging.getLogger(__name__)

router = APIRouter()


async def process_inbound_invoice_background(
    file_metadata: Dict[str, Any],
    company_id: str,
    email_subject: str,
    from_email: str,
) -> None:
    """Tarea asíncrona de fondo para extraer datos OCR, validar y persistir la factura."""
    logger.info(f"Iniciando procesamiento OCR en segundo plano para: {file_metadata.get('filename')}")
    async with AsyncSessionLocal() as session:
        try:
            extraction = await extract_invoice_data(
                file_path=file_metadata["encrypted_path"],
                company_id=company_id,
                db=session,
            )

            # Crear factura en base de datos en estado de revisión o aprobada según confianza
            requires_review = extraction.get("requires_review", False) or extraction.get("duplicate_analysis", {}).get("is_duplicate", False)

            invoice = Invoice(
                company_id=str(company_id),
                invoice_number=extraction.get("invoice_number") or "S/N",
                file_path=file_metadata["encrypted_path"],
                file_hash=file_metadata.get("sha256"),
                issuer_name=extraction.get("issuer_name") or "Proveedor Desconocido",
                issuer_cif=extraction.get("issuer_cif") or "",
                issue_date=extraction.get("issue_date"),
                due_date=extraction.get("due_date"),
                total_base=float(extraction.get("total_base") or 0.0),
                total_tax=float(extraction.get("total_tax") or 0.0),
                retention_amount=float(extraction.get("retention_amount") or 0.0),
                retention_rate=float(extraction.get("retention_rate") or 0.0),
                total_amount=float(extraction.get("total_amount") or 0.0),
                suggested_account=extraction.get("suggested_account") or "629000000",
                concept=extraction.get("concept_summary") or f"Factura recibida vía email ({email_subject[:50]})",
                status="REQUIRES_REVIEW" if requires_review else "PENDING_APPROVAL",
            )
            session.add(invoice)
            await session.commit()
            await session.refresh(invoice)

            # Persistir desglose tributario si existe
            tax_breakdown = extraction.get("tax_breakdown") or []
            for item in tax_breakdown:
                if isinstance(item, dict):
                    bd = InvoiceTaxBreakdown(
                        invoice_id=invoice.id,
                        base_amount=float(item.get("base_amount") or 0.0),
                        tax_rate=float(item.get("tax_rate") or 0.0),
                        tax_amount=float(item.get("tax_amount") or 0.0),
                    )
                    session.add(bd)
            if tax_breakdown:
                await session.commit()

            logger.info(f"Factura #{invoice.id} registrada con éxito desde email ({from_email}).")

        except Exception as exc:
            logger.error(f"Error procesando adjunto de email en segundo plano: {exc}", exc_info=True)


@router.post("/inbound-email", status_code=status.HTTP_200_OK)
async def handle_inbound_email_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Endpoint unificado receptor de webhooks de correo inbound (SendGrid, Postmark, Mailgun).

    Admite cargas JSON directas o formularios multipart con adjuntos binarios.
    """
    content_type = request.headers.get("content-type", "").lower()
    payload: Dict[str, Any] = {}
    raw_attachments: List[Dict[str, Any]] = []

    # 1. Parsing según el formato de envío del proveedor
    if "application/json" in content_type:
        try:
            payload = await request.json()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Cuerpo JSON no válido: {str(exc)}")
    else:
        # Multipart / Form data (SendGrid Inbound Parse o Mailgun)
        form = await request.form()
        for key, value in form.items():
            if isinstance(value, UploadFile):
                file_bytes = await value.read()
                raw_attachments.append({
                    "filename": value.filename,
                    "content": file_bytes,
                    "content_type": value.content_type,
                    "size": len(file_bytes),
                })
            else:
                payload[key] = value

    # 2. Ingesta y normalización del correo
    try:
        parsed_email = parse_inbound_email(payload=payload, raw_attachments=raw_attachments)
    except EmailIngestionError as ing_err:
        log_security_event(
            action="EMAIL_INBOUND_REJECTED",
            resource_id="WEBHOOK_INBOUND",
            request=request,
            status="DENIED",
            details={"error": str(ing_err), "headers": dict(request.headers)}
        )
        raise HTTPException(status_code=400, detail=str(ing_err))

    # 3. Localizar la empresa destinataria en la base de datos
    target_company: Optional[Company] = None
    if parsed_email["company_id"]:
        target_company = await db.get(Company, str(parsed_email["company_id"]))
    elif parsed_email["company_slug"]:
        # Buscar por CIF o razón social si coincide con el slug
        slug = parsed_email["company_slug"].lower().replace("-", "")
        stmt = select(Company).where(
            (Company.cif.ilike(f"%{slug}%")) | (Company.razon_social.ilike(f"%{slug}%"))
        ).limit(1)
        res = await db.execute(stmt)
        target_company = res.scalar_one_or_none()

    if not target_company:
        # Si no se encuentra empresa registrada para ese token, recuperar la primera disponible como fallback o rechazar
        stmt_first = select(Company).limit(1)
        res_first = await db.execute(stmt_first)
        target_company = res_first.scalar_one_or_none()
        if not target_company:
            raise HTTPException(
                status_code=404,
                detail=f"No se encontró ninguna empresa asociada al buzón '{parsed_email['to_email']}'."
            )

    company_id_str = str(target_company.id)

    # 4. Pipeline de seguridad y custodia cifrada de adjuntos
    try:
        processed_attachments = process_email_attachments(
            attachments=parsed_email["attachments"],
            company_id=company_id_str,
        )
    except EmailIngestionError as sec_err:
        log_security_event(
            action="EMAIL_ATTACHMENT_SECURITY_VIOLATION",
            resource_id=f"COMPANY_{company_id_str}",
            request=request,
            empresa_id=company_id_str,
            status="DENIED",
            details={"error": str(sec_err), "sender": parsed_email["from_email"]}
        )
        raise HTTPException(status_code=422, detail=str(sec_err))

    # 5. Encolar tareas en segundo plano para OCR y extracción contable
    for att in processed_attachments:
        background_tasks.add_task(
            process_inbound_invoice_background,
            file_metadata=att,
            company_id=company_id_str,
            email_subject=parsed_email["subject"],
            from_email=parsed_email["from_email"],
        )

    # 6. Trazabilidad de seguridad inmutable
    log_security_event(
        action="EMAIL_INBOUND_RECEIVED",
        resource_id=f"EMAIL_{parsed_email['from_email']}",
        request=request,
        empresa_id=company_id_str,
        status="SUCCESS",
        details={
            "from_email": parsed_email["from_email"],
            "to_email": parsed_email["to_email"],
            "subject": parsed_email["subject"],
            "total_attachments_received": len(parsed_email["attachments"]),
            "attachments_queued": len(processed_attachments),
        }
    )

    return {
        "status": "success",
        "message": f"Correo recibido con éxito. {len(processed_attachments)} facturas encoladas para extracción OCR.",
        "company_id": company_id_str,
        "company_name": target_company.razon_social,
        "sender": parsed_email["from_email"],
        "queued_files": [f["filename"] for f in processed_attachments],
    }
