from typing import List, Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
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

router = APIRouter()

@router.get("/{company_id}/sales-invoices", response_model=List[SalesInvoiceResponse])
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
    return res.scalars().all()


@router.post("/{company_id}/sales-invoices", response_model=SalesInvoiceResponse)
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

    # 3. Crear cabecera de la factura de venta
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
        notes=payload.notes,
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
    return res.scalar_one()


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
