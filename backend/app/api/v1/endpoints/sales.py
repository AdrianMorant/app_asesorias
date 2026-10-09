import re
from typing import List, Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query, Response, Request, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.company import Company
from app.models.contact import Contact
from app.models.sales_invoice import SalesInvoice, SalesInvoiceLineItem, SalesInvoiceTaxBreakdown
from app.models.accounting_entry import AccountingEntryLine
from app.schemas.sales_invoice_dto import (
    SalesInvoiceCreate,
    SalesInvoiceResponse,
    UpdateSalesInvoiceStatus
)
from app.core.verifactu import create_verifactu_record, compute_verifactu_hash
from app.core.facturae_generator import (
    generate_facturae_from_sales_invoice as generate_facturae_xml,
    validate_facturae_syntax
)
from app.core.audit_logger import log_security_event

router = APIRouter()


class SalesInvoiceWithVerifactuResponse(SalesInvoiceResponse):
    huella: Optional[str] = None
    qr_payload: Optional[str] = None
    qr_base64: Optional[str] = None

@router.get("/{company_id}/sales-invoices", response_model=List[SalesInvoiceWithVerifactuResponse])
async def list_sales_invoices(
    company_id: str,
    doc_type: Optional[str] = Query(None, description="INVOICE, ESTIMATE, PROFORMA"),
    status: Optional[str] = Query(None, description="DRAFT, ISSUED, SENT, PAID, CANCELLED"),
    db: AsyncSession = Depends(get_db)
):
    """Lista las facturas de venta y presupuestos emitidos por una empresa."""
    stmt = (
        select(SalesInvoice)
        .options(
            selectinload(SalesInvoice.lines),
            selectinload(SalesInvoice.tax_breakdown),
        )
        .where(SalesInvoice.company_id == company_id)
    )

    if doc_type:
        stmt = stmt.where(SalesInvoice.doc_type == doc_type.upper())
    if status:
        stmt = stmt.where(SalesInvoice.status == status.upper())

    stmt = stmt.order_by(SalesInvoice.issue_date.desc(), SalesInvoice.invoice_number.desc())
    res = await db.execute(stmt)
    invoices = res.scalars().all()

    output = []
    for inv in invoices:
        inv_dict = SalesInvoiceResponse.model_validate(inv).model_dump()
        huella_val = getattr(inv, "huella", None)
        if not huella_val and inv.notes and "[VERIFACTU_HUELLA:" in inv.notes:
            m = re.search(r"\[VERIFACTU_HUELLA:([A-F0-9]{64})\]", inv.notes)
            if m:
                huella_val = m.group(1)
        inv_dict["huella"] = huella_val
        output.append(inv_dict)
    return output


@router.post("/{company_id}/sales-invoices", response_model=SalesInvoiceWithVerifactuResponse)
async def create_sales_invoice(
    company_id: str,
    payload: SalesInvoiceCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Crea una nueva factura de venta o presupuesto, calculando bases, desglose de IVA,
    retenciones y generando automáticamente el asiento contable en el Libro Diario.
    """
    comp = await db.get(Company, company_id)
    if not comp:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    # 1. Determinar número correlativo de serie si no viene
    series = payload.series or f"F{payload.issue_date.year}"
    inv_num = payload.invoice_number
    if not inv_num:
        count_stmt = select(func.count(SalesInvoice.id)).where(
            SalesInvoice.company_id == company_id,
            SalesInvoice.series == series
        )
        count = (await db.execute(count_stmt)).scalar() or 0
        inv_num = f"{series}-{str(count + 1).zfill(4)}"

    # 2. Calcular importes a partir de las líneas
    total_base = 0.0
    total_tax = 0.0
    total_retention = 0.0
    taxes_map = {}  # tax_rate -> {base, amount}

    processed_lines = []
    for line in payload.lines:
        line_subtotal = round(line.quantity * line.unit_price, 2)
        total_base += line_subtotal
        
        tax_amount = round(line_subtotal * (line.tax_rate / 100.0), 2)
        ret_amount = round(line_subtotal * (line.retention_rate / 100.0), 2) if line.retention_rate else 0.0

        total_tax += tax_amount
        total_retention += ret_amount

        if line.tax_rate not in taxes_map:
            taxes_map[line.tax_rate] = {"base": 0.0, "amount": 0.0}
        taxes_map[line.tax_rate]["base"] += line_subtotal
        taxes_map[line.tax_rate]["amount"] += tax_amount

        processed_lines.append(
            SalesInvoiceLineItem(
                description=line.description,
                quantity=line.quantity,
                unit_price=line.unit_price,
                tax_rate=line.tax_rate,
                retention_rate=line.retention_rate,
                subtotal=line_subtotal
            )
        )

    total_base = round(total_base, 2)
    total_tax = round(total_tax, 2)
    total_retention = round(total_retention, 2)
    total_amount = round(total_base + total_tax - total_retention, 2)

    # 2.1 Cumplimiento Verifactu: Obtener huella de la última factura emitida de la empresa (prev_hash)
    prev_hash = ""
    verifactu_rec = None
    if payload.doc_type.upper() == "INVOICE":
        last_inv_stmt = (
            select(SalesInvoice)
            .where(
                SalesInvoice.company_id == company_id,
                SalesInvoice.doc_type == "INVOICE"
            )
            .order_by(SalesInvoice.created_at.desc())
        )
        last_inv_res = await db.execute(last_inv_stmt)
        last_inv = last_inv_res.scalars().first()

        if last_inv:
            if getattr(last_inv, "huella", None):
                prev_hash = last_inv.huella
            elif last_inv.notes and "[VERIFACTU_HUELLA:" in last_inv.notes:
                m = re.search(r"\[VERIFACTU_HUELLA:([A-F0-9]{64})\]", last_inv.notes)
                if m:
                    prev_hash = m.group(1)
            else:
                prev_hash = compute_verifactu_hash(
                    nif_emisor=comp.cif,
                    num_serie_factura=last_inv.invoice_number,
                    fecha_expedicion=last_inv.issue_date,
                    tipo_factura="F1",
                    cuota_total=last_inv.total_tax,
                    importe_total=last_inv.total_amount,
                    prev_hash="",
                )

        verifactu_rec = create_verifactu_record(
            nif_emisor=comp.cif,
            num_serie_factura=inv_num,
            fecha_expedicion=payload.issue_date,
            cuota_total=total_tax,
            importe_total=total_amount,
            tipo_factura="F1",
            descripcion_operacion=f"Factura emitida {inv_num} a {payload.customer_name}",
            prev_hash=prev_hash,
            is_verifactu_mode=True,
        )

    # 3. Crear cabecera de la factura de venta
    notes_val = payload.notes
    if verifactu_rec:
        huella_tag = f"[VERIFACTU_HUELLA:{verifactu_rec.huella}]"
        notes_val = f"{notes_val} {huella_tag}".strip() if notes_val else huella_tag

    sales_inv = SalesInvoice(
        company_id=company_id,
        contact_id=payload.contact_id,
        doc_type=payload.doc_type.upper(),
        series=series,
        invoice_number=inv_num,
        issue_date=payload.issue_date,
        due_date=payload.due_date,
        customer_name=payload.customer_name.strip(),
        customer_cif=payload.customer_cif.strip().upper(),
        customer_address=payload.customer_address.strip() if payload.customer_address else None,
        total_base=total_base,
        total_tax=total_tax,
        total_retention=total_retention,
        total_amount=total_amount,
        status="ISSUED" if payload.doc_type.upper() == "INVOICE" else "DRAFT",
        notes=notes_val,
        lines=processed_lines,
        tax_breakdown=[
            SalesInvoiceTaxBreakdown(
                tax_rate=rate,
                tax_base=round(data["base"], 2),
                tax_amount=round(data["amount"], 2)
            )
            for rate, data in taxes_map.items()
        ]
    )
    if verifactu_rec:
        sales_inv.huella = verifactu_rec.huella

    db.add(sales_inv)
    await db.flush()

    # 4. Generar Asiento Contable automático en el Libro Diario (PGC)
    # Sólo para facturas formales de venta (INVOICE), no presupuestos
    if payload.doc_type.upper() == "INVOICE" and total_amount > 0:
        digits = comp.plan_cuentas_longitud or 9
        # Subcuenta de cliente 430...
        customer_account = "430" + "1".zfill(digits - 3)
        if payload.contact_id:
            c = await db.get(Contact, payload.contact_id)
            if c and c.subcuenta_default:
                customer_account = c.subcuenta_default

        sales_account = "700" + "0".zfill(digits - 3)   # Ventas de mercaderías / servicios
        vat_account = "477" + "0".zfill(digits - 3)     # H.P. IVA repercutido
        ret_account = "473" + "0".zfill(digits - 3)     # H.P. Retenciones y pagos a cuenta

        # Número de asiento
        last_entry_stmt = select(func.max(AccountingEntryLine.entry_number)).where(
            AccountingEntryLine.company_id == company_id
        )
        max_entry = (await db.execute(last_entry_stmt)).scalar() or 0
        new_entry_num = max_entry + 1

        # Apunte 1: Cliente al Debe (Total a percibir)
        entry_lines = [
            AccountingEntryLine(
                company_id=company_id,
                sales_invoice_id=sales_inv.id,
                entry_number=new_entry_num,
                fecha=sales_inv.issue_date,
                subcuenta=customer_account,
                concepto=f"Venta Fra. {sales_inv.invoice_number} - {sales_inv.customer_name}"[:255],
                debe=total_amount,
                haber=0.0,
                documento=sales_inv.invoice_number
            )
        ]

        # Apunte de Retención soportada si existe (Debe 473)
        if total_retention > 0:
            entry_lines.append(
                AccountingEntryLine(
                    company_id=company_id,
                    sales_invoice_id=sales_inv.id,
                    entry_number=new_entry_num,
                    fecha=sales_inv.issue_date,
                    subcuenta=ret_account,
                    concepto=f"Retención IRPF Fra. {sales_inv.invoice_number}",
                    debe=total_retention,
                    haber=0.0,
                    documento=sales_inv.invoice_number
                )
            )

        # Apunte de Ingresos de Venta al Haber (Base imponible 700)
        entry_lines.append(
            AccountingEntryLine(
                company_id=company_id,
                sales_invoice_id=sales_inv.id,
                entry_number=new_entry_num,
                fecha=sales_inv.issue_date,
                subcuenta=sales_account,
                concepto=f"Venta Fra. {sales_inv.invoice_number} - Base Imponible",
                debe=0.0,
                haber=total_base,
                documento=sales_inv.invoice_number
            )
        )

        # Apunte de IVA Repercutido al Haber (Cuota IVA 477)
        if total_tax > 0:
            entry_lines.append(
                AccountingEntryLine(
                    company_id=company_id,
                    sales_invoice_id=sales_inv.id,
                    entry_number=new_entry_num,
                    fecha=sales_inv.issue_date,
                    subcuenta=vat_account,
                    concepto=f"IVA Repercutido Fra. {sales_inv.invoice_number}",
                    debe=0.0,
                    haber=total_tax,
                    documento=sales_inv.invoice_number
                )
            )

        db.add_all(entry_lines)

    await db.commit()
    await db.refresh(sales_inv)

    # Cargar relaciones completas
    full_stmt = (
        select(SalesInvoice)
        .options(
            selectinload(SalesInvoice.lines),
            selectinload(SalesInvoice.tax_breakdown),
        )
        .where(SalesInvoice.id == sales_inv.id)
    )
    res = await db.execute(full_stmt)
    inv_obj = res.scalar_one()

    # Retornar respuesta enriquecida con metadatos Verifactu (huella, QR payload y QR Base64)
    inv_dict = SalesInvoiceResponse.model_validate(inv_obj).model_dump()
    if verifactu_rec:
        inv_dict["huella"] = verifactu_rec.huella
        inv_dict["qr_payload"] = verifactu_rec.qr_payload
        inv_dict["qr_base64"] = verifactu_rec.qr_base64
    return inv_dict


@router.put("/sales-invoices/{invoice_id}/status")
async def update_sales_invoice_status(
    invoice_id: str,
    payload: UpdateSalesInvoiceStatus,
    db: AsyncSession = Depends(get_db)
):
    """Actualiza el estado de una factura de venta (ISSUED, PAID, CANCELLED, etc.)."""
    inv = await db.get(SalesInvoice, invoice_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Factura de venta no encontrada")

    inv.status = payload.status.upper()
    await db.commit()
    return {"status": "ok", "invoice_id": invoice_id, "new_status": inv.status}


@router.delete("/sales-invoices/{invoice_id}")
async def delete_sales_invoice(invoice_id: str, db: AsyncSession = Depends(get_db)):
    """Elimina una factura de venta y sus apuntes asociados."""
    inv = await db.get(SalesInvoice, invoice_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Factura de venta no encontrada")

    await db.delete(inv)
    await db.commit()
    return {"status": "ok", "message": "Factura de venta eliminada correctamente"}


@router.get("/{company_id}/sales-invoices/{invoice_id}/facturae")
async def get_sales_invoice_facturae(
    company_id: str,
    invoice_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Genera y descarga la factura electrónica oficial en formato Facturae 3.2.2 (XML).
    Cumplimiento normativo Ley Crea y Crece (Ley 18/2022) y FACe (Ley 25/2013).
    """
    comp = await db.get(Company, company_id)
    if not comp:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    stmt = (
        select(SalesInvoice)
        .options(
            selectinload(SalesInvoice.lines),
            selectinload(SalesInvoice.tax_breakdown),
        )
        .where(
            SalesInvoice.id == invoice_id,
            SalesInvoice.company_id == company_id
        )
    )
    res = await db.execute(stmt)
    inv = res.scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail="Factura de venta no encontrada")

    # 1. Generar el documento XML estructurado Facturae 3.2.2
    try:
        xml_str = generate_facturae_xml(inv, comp)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generando documento Facturae: {str(exc)}"
        )

    # 2. Validar sintaxis, estructura y cuadre aritmético
    validation = validate_facturae_syntax(xml_str)
    if not validation.get("is_valid"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Facturae inválido según las especificaciones técnicas oficiales.",
                "errors": validation.get("errors", [])
            }
        )

    # 3. Registro inmutable en auditoría de seguridad y trazabilidad RGPD
    log_security_event(
        action="FACTURAE_DOWNLOAD",
        resource_id=str(invoice_id),
        request=request,
        empresa_id=str(company_id),
        status="SUCCESS",
        details={
            "invoice_number": inv.invoice_number,
            "customer_cif": inv.customer_cif,
            "total_amount": inv.total_amount
        }
    )

    clean_num = re.sub(r"[^A-Za-z0-9_-]", "_", inv.invoice_number)
    filename = f"facturae_{clean_num}.xml"

    return Response(
        content=xml_str,
        media_type="application/xml",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )
