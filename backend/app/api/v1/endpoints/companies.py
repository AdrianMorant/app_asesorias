import os
from pathlib import Path
from typing import List, Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query, Response, Request, status, Body
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.company import Company
from app.models.invoice import Invoice
from app.models.sales_invoice import SalesInvoice
from app.models.contact import Contact
from app.models.accounting_entry import AccountingEntryLine
from app.schemas.company_dto import (
    CompanyCreateDTO,
    CompanyUpdateDTO,
    CompanyResponseDTO,
)
from app.services.nif_validator import normalize_nif, validate_spanish_id
from app.core.gdpr_export import generate_gdpr_data_export
from app.core.gdpr_forget import process_company_gdpr_forget, GDPRForgetResult, anonymize_text
from app.core.audit_logger import log_security_event
from app.api.v1.endpoints.banking import _load_transactions

router = APIRouter()

@router.post("", response_model=CompanyResponseDTO, status_code=status.HTTP_201_CREATED)
async def create_company(
    payload: CompanyCreateDTO,
    db: AsyncSession = Depends(get_db)
):
    """Crea una nueva empresa cliente en la asesoría."""
    norm_cif = normalize_nif(payload.cif)
    nif_val = validate_spanish_id(norm_cif)
    if not nif_val.is_valid:
        raise HTTPException(
            status_code=400,
            detail=f"CIF de la empresa no válido: {nif_val.error_message}"
        )

    # Comprobar duplicado
    stmt = select(Company).where(Company.cif == norm_cif)
    res = await db.execute(stmt)
    if res.scalars().first():
        raise HTTPException(status_code=400, detail="Ya existe una empresa registrada con este CIF.")

    company = Company(
        cif=norm_cif,
        razon_social=payload.razon_social,
        plan_cuentas_longitud=payload.plan_cuentas_longitud,
        storage_base_path=payload.storage_base_path or "storage",
        iva_periodicity=payload.iva_periodicity or "Trimestral",
        modalidad_uso=payload.modalidad_uso or "copiloto_contable",
        regimen_tributario=payload.regimen_tributario or "general",
        software_destino=payload.software_destino or "a3",
        domicilio_fiscal=payload.domicilio_fiscal.strip() if payload.domicilio_fiscal else None,
        email_contacto=payload.email_contacto.strip() if payload.email_contacto else None,
        telefono_contacto=payload.telefono_contacto.strip() if payload.telefono_contacto else None,
        is_active=True,
    )
    db.add(company)
    await db.commit()
    await db.refresh(company)

    # Precargar automáticamente el catálogo completo del PGC PYMES adaptado a su longitud
    try:
        from app.services.pyme_pgc_seed import seed_company_chart_of_accounts
        await seed_company_chart_of_accounts(db, company.id, company.plan_cuentas_longitud)
    except Exception as e:
        pass

    return company

@router.get("", response_model=List[CompanyResponseDTO])
async def list_companies(db: AsyncSession = Depends(get_db)):
    """Lista todas las empresas asesoradas."""
    res = await db.execute(select(Company).order_by(Company.razon_social))
    return res.scalars().all()

@router.get("/{company_id}", response_model=CompanyResponseDTO)
async def get_company(company_id: str, db: AsyncSession = Depends(get_db)):
    """Obtiene una empresa por ID."""
    res = await db.execute(select(Company).where(Company.id == company_id))
    company = res.scalars().first()
    if not company:
        raise HTTPException(status_code=404, detail="Empresa no encontrada.")
    return company

@router.put("/{company_id}", response_model=CompanyResponseDTO)
async def update_company(
    company_id: str,
    payload: CompanyUpdateDTO,
    db: AsyncSession = Depends(get_db)
):
    """Edita los datos de la empresa: razón social, dígitos de cuentas, ruta de almacenamiento, periodicidad de IVA, modalidad o software de destino."""
    res = await db.execute(select(Company).where(Company.id == company_id))
    company = res.scalars().first()
    if not company:
        raise HTTPException(status_code=404, detail="Empresa no encontrada.")

    if payload.razon_social is not None:
        company.razon_social = payload.razon_social.strip()
    if payload.plan_cuentas_longitud is not None:
        company.plan_cuentas_longitud = payload.plan_cuentas_longitud
    if payload.storage_base_path is not None:
        company.storage_base_path = payload.storage_base_path.strip()
    if payload.iva_periodicity is not None:
        company.iva_periodicity = payload.iva_periodicity.strip()
    if payload.modalidad_uso is not None:
        company.modalidad_uso = payload.modalidad_uso.strip()
    if payload.regimen_tributario is not None:
        company.regimen_tributario = payload.regimen_tributario.strip()
    if payload.software_destino is not None:
        company.software_destino = payload.software_destino.strip()
    if payload.domicilio_fiscal is not None:
        company.domicilio_fiscal = payload.domicilio_fiscal.strip() if payload.domicilio_fiscal else None
    if payload.email_contacto is not None:
        company.email_contacto = payload.email_contacto.strip() if payload.email_contacto else None
    if payload.telefono_contacto is not None:
        company.telefono_contacto = payload.telefono_contacto.strip() if payload.telefono_contacto else None
    if payload.is_active is not None:
        company.is_active = payload.is_active

    await db.commit()
    await db.refresh(company)
    return company

@router.delete("/{company_id}")
async def delete_company(
    company_id: str,
    cif_confirmation: Optional[str] = Query(None, description="Confirmación tecleando el CIF de la empresa"),
    payload: Optional[dict] = Body(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Elimina una empresa con confirmación estricta por CIF.
    Borra en cascada facturas, asientos, proveedores, catálogo contable
    y elimina físicamente los archivos del disco para evitar huérfanos.
    """
    token_confirmation = cif_confirmation or (payload.get("cif_confirmation") if isinstance(payload, dict) else None)
    if not token_confirmation:
        raise HTTPException(
            status_code=400,
            detail="Debe proporcionar 'cif_confirmation' como parámetro de consulta o en el cuerpo JSON."
        )

    res = await db.execute(
        select(Company)
        .where(Company.id == company_id)
        .options(selectinload(Company.invoices))
    )
    company = res.scalars().first()
    if not company:
        raise HTTPException(status_code=404, detail="Empresa no encontrada.")

    # Validación de seguridad estricta
    if normalize_nif(token_confirmation) != normalize_nif(company.cif):
        raise HTTPException(
            status_code=400,
            detail=f"Confirmación incorrecta. Debe escribir exactamente el CIF '{company.cif}' para confirmar la eliminación."
        )

    # 1. Borrar físicamente los archivos de facturas asociadas
    deleted_files_count = 0
    for inv in company.invoices:
        if inv.file_path:
            p = Path(inv.file_path)
            if p.exists():
                try:
                    p.unlink()
                    deleted_files_count += 1
                except Exception:
                    pass

    # 2. Borrar empresa en base de datos (cascada automática a invoices, suppliers, accounts, entries)
    await db.delete(company)
    await db.commit()

    return {
        "success": True,
        "message": f"Empresa '{company.razon_social}' y sus datos asociados eliminados correctamente.",
        "deleted_files_count": deleted_files_count
    }


@router.post("/{company_id}/export/gdpr-archive")
async def export_company_gdpr_archive(
    company_id: str,
    password: Optional[str] = Query(None, description="Clave opcional para cifrar el archivo ZIP con AES-256-GCM"),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Genera el paquete oficial de portabilidad de datos (Art. 20 RGPD):
    - Exporta en formato estructurado (JSON + CSV UTF-8 con BOM para Excel).
    - Descifra y empaqueta en memoria los documentos originales de facturas.
    - Incluye el Libro Diario contable PGC y los movimientos bancarios.
    - Genera el manifiesto de integridad con huellas SHA-256.
    - Registra el evento en la auditoría inmutable de seguridad.
    """
    comp = await db.get(Company, company_id)
    if not comp:
        raise HTTPException(status_code=404, detail="Empresa no encontrada.")

    # 1. Datos de perfil de la empresa
    company_data = {
        "id": str(comp.id),
        "cif": comp.cif,
        "razon_social": comp.razon_social,
        "plan_cuentas_longitud": comp.plan_cuentas_longitud,
        "storage_base_path": comp.storage_base_path,
        "iva_periodicity": comp.iva_periodicity,
        "created_at": comp.created_at.isoformat() if hasattr(comp, "created_at") and comp.created_at else None,
    }

    # 2. Facturas de compra (recibidas)
    purch_res = await db.execute(select(Invoice).where(Invoice.company_id == company_id))
    purch_invoices = purch_res.scalars().all()

    invoices_files = []
    for inv in purch_invoices:
        inv_meta = {
            "id": str(inv.id),
            "doc_type": "PURCHASE_INVOICE",
            "invoice_number": inv.invoice_number,
            "issue_date": inv.issue_date.isoformat() if inv.issue_date else None,
            "due_date": inv.due_date.isoformat() if hasattr(inv, "due_date") and inv.due_date else None,
            "issuer_name": inv.issuer_name,
            "issuer_cif": inv.issuer_cif,
            "total_base": float(inv.total_base or 0.0),
            "total_tax": float(inv.total_tax or 0.0),
            "total_retention": float(getattr(inv, "total_retention", 0.0) or 0.0),
            "total_amount": float(inv.total_amount or 0.0),
            "status": inv.status,
            "storage_path": inv.file_path,
        }
        invoices_files.append({
            "file_path": inv.file_path,
            "filename": inv.file_name or f"factura_compra_{str(inv.id)[:8]}.pdf",
            "metadata": inv_meta,
        })

    # 3. Facturas de venta (emitidas)
    sales_res = await db.execute(select(SalesInvoice).where(SalesInvoice.company_id == company_id))
    sales_invoices = sales_res.scalars().all()

    for sinv in sales_invoices:
        sinv_meta = {
            "id": str(sinv.id),
            "doc_type": "SALES_INVOICE",
            "invoice_number": sinv.invoice_number,
            "series": sinv.series,
            "issue_date": sinv.issue_date.isoformat() if sinv.issue_date else None,
            "due_date": sinv.due_date.isoformat() if sinv.due_date else None,
            "customer_name": sinv.customer_name,
            "customer_cif": sinv.customer_cif,
            "total_base": float(sinv.total_base or 0.0),
            "total_tax": float(sinv.total_tax or 0.0),
            "total_retention": float(sinv.total_retention or 0.0),
            "total_amount": float(sinv.total_amount or 0.0),
            "status": sinv.status,
            "huella_verifactu": getattr(sinv, "huella", None),
        }
        invoices_files.append({
            "filename": f"factura_venta_{sinv.invoice_number}.pdf",
            "metadata": sinv_meta,
        })

    # 4. Asientos contables del Libro Diario
    entries_res = await db.execute(
        select(AccountingEntryLine)
        .where(AccountingEntryLine.company_id == company_id)
        .order_by(AccountingEntryLine.entry_number, AccountingEntryLine.id)
    )
    entries = entries_res.scalars().all()
    accounting_ledger = [
        {
            "entry_number": e.entry_number,
            "fecha": e.fecha.isoformat() if e.fecha else None,
            "subcuenta": e.subcuenta,
            "concepto": e.concepto,
            "debe": float(e.debe or 0.0),
            "haber": float(e.haber or 0.0),
            "documento": e.documento,
        }
        for e in entries
    ]

    # 5. Movimientos bancarios
    bank_txs = _load_transactions(company_id)

    # 6. Generar paquete ZIP en memoria
    try:
        zip_bytes, filename = generate_gdpr_data_export(
            company_data=company_data,
            invoices_files=invoices_files,
            accounting_ledger=accounting_ledger,
            bank_transactions=bank_txs,
            export_password=password,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generando el paquete de portabilidad RGPD: {str(exc)}"
        )

    # 7. Trazabilidad RGPD y auditoría inmutable
    log_security_event(
        action="GDPR_DATA_PORTABILITY_EXPORT",
        resource_id=str(company_id),
        request=request,
        empresa_id=str(company_id),
        status="SUCCESS",
        details={
            "cif": comp.cif,
            "is_encrypted": bool(password and password.strip()),
            "filename": filename,
            "total_invoices": len(invoices_files),
            "total_entries": len(accounting_ledger),
            "total_bank_txs": len(bank_txs),
        }
    )

    media_type = "application/octet-stream" if filename.endswith(".enc") else "application/zip"

    return Response(
        content=zip_bytes,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


@router.post("/{company_id}/gdpr-forget", response_model=GDPRForgetResult)
async def company_gdpr_forget_and_block(
    company_id: str,
    confirm: bool = Query(False, description="Confirmación explícita para ejecutar el procedimiento de derecho al olvido"),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Ejecuta el procedimiento legal de Derecho al Olvido y Bloqueo Tributario (Art. 17 RGPD vs Art. 66 LGT):
    - Anonimiza de forma irreversible datos personales de usuarios y contactos.
    - Bloquea facturas vigentes bajo retención legal ('BLOCKED_TAX_RETENTION') calculando plazos de prescripción.
    - Purga físicamente solo aquellos ejercicios prescritos ('ELIGIBLE_FOR_PURGE').
    - Emite y firma el Certificado de Bloqueo Legal auditable con huella SHA-256.
    """
    if not confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Se requiere confirmación expresa (confirm=True) para ejecutar el procedimiento de derecho al olvido y bloqueo normativo RGPD."
        )

    comp = await db.get(Company, company_id)
    if not comp:
        raise HTTPException(status_code=404, detail="Empresa no encontrada.")

    # 1. Recuperar facturas y contactos asociados
    purch_res = await db.execute(select(Invoice).where(Invoice.company_id == company_id))
    purch_invoices = purch_res.scalars().all()

    sales_res = await db.execute(select(SalesInvoice).where(SalesInvoice.company_id == company_id))
    sales_invoices = sales_res.scalars().all()

    contacts_res = await db.execute(select(Contact).where(Contact.company_id == company_id))
    contacts = contacts_res.scalars().all()

    invoices_payload = []
    for p in purch_invoices:
        invoices_payload.append({
            "id": str(p.id),
            "doc_type": "PURCHASE",
            "invoice_number": p.invoice_number,
            "issue_date": p.issue_date.isoformat() if p.issue_date else None,
            "total_amount": float(p.total_amount or 0.0),
            "file_path": p.file_path,
        })
    for s in sales_invoices:
        invoices_payload.append({
            "id": str(s.id),
            "doc_type": "SALES",
            "invoice_number": s.invoice_number,
            "issue_date": s.issue_date.isoformat() if s.issue_date else None,
            "total_amount": float(s.total_amount or 0.0),
        })

    users_payload = [
        {
            "id": str(c.id),
            "name": c.razon_social,
            "email": c.email,
            "phone": c.phone,
        }
        for c in contacts
    ]
    if not users_payload:
        users_payload = [
            {
                "id": f"usr-{company_id[:8]}",
                "name": comp.razon_social,
                "email": f"contacto@{comp.cif.lower()}.local",
            }
        ]

    company_data = {
        "id": str(comp.id),
        "cif": comp.cif,
        "razon_social": comp.razon_social,
    }

    # 2. Procesar algoritmo normativo de olvido y bloqueo legal
    result = process_company_gdpr_forget(
        company_data=company_data,
        invoices=invoices_payload,
        users=users_payload,
    )

    # 3. Aplicar anonimización de contactos en base de datos
    for c in contacts:
        anon_tok = anonymize_text(str(c.id), prefix="ANON_CONTACT")
        c.razon_social = f"Contacto Seudonimizado {anon_tok}"
        c.nombre_comercial = None
        c.email = f"{anon_tok.lower()}@anon.local"
        c.phone = None
        c.address = "Domicilio suprimido (Art. 17 RGPD)"
        c.notes = None

    # 4. Aplicar bloqueo y purga en facturas
    year_status_map = {s.tax_year: s.status for s in result.invoices_retention_summary}

    for p in purch_invoices:
        inv_year = p.issue_date.year if p.issue_date else date.today().year
        st = year_status_map.get(inv_year, "BLOCKED_TAX_RETENTION")
        if st == "ELIGIBLE_FOR_PURGE":
            if p.file_path and os.path.exists(p.file_path):
                try:
                    os.unlink(p.file_path)
                except Exception:
                    pass
            await db.delete(p)
        else:
            p.status = "BLOCKED_TAX_RETENTION"

    for s in sales_invoices:
        inv_year = s.issue_date.year if s.issue_date else date.today().year
        st = year_status_map.get(inv_year, "BLOCKED_TAX_RETENTION")
        if st == "ELIGIBLE_FOR_PURGE":
            await db.delete(s)
        else:
            s.status = "BLOCKED_TAX_RETENTION"

    await db.commit()

    # 5. Registrar evento en auditoría inmutable de seguridad
    log_security_event(
        action="GDPR_FORGET_AND_LEGAL_BLOCK",
        resource_id=str(company_id),
        request=request,
        empresa_id=str(company_id),
        status="SUCCESS",
        details={
            "cif": comp.cif,
            "certificate_id": result.certificate.certificate_id,
            "sha256_fingerprint": result.certificate.sha256_fingerprint,
            "blocked_invoices_count": result.blocked_invoices_count,
            "purged_invoices_count": result.purged_invoices_count,
            "users_anonymized_count": len(result.users_anonymized),
        }
    )

    return result
