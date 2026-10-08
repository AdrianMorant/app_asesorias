from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.invoice import Invoice
from app.services.exporters.contasol_csv import export_invoices_to_contasol_csv
from app.services.exporters.a3_suenlace import export_invoices_to_a3_suenlace

router = APIRouter()

@router.get("/contasol")
async def export_contasol(
    company_id: Optional[str] = Query(None, description="Filtrar por empresa"),
    only_processed: bool = Query(True, description="Exportar sólo facturas revisadas/aprobadas"),
    db: AsyncSession = Depends(get_db)
):
    """Descarga el fichero CSV para importar en el Diario de Contasol."""
    stmt = (
        select(Invoice)
        .options(selectinload(Invoice.accounting_entries))
        .order_by(Invoice.issue_date.asc())
    )
    if company_id:
        stmt = stmt.where(Invoice.company_id == company_id)
    if only_processed:
        stmt = stmt.where(Invoice.is_processed == True)

    res = await db.execute(stmt)
    invoices = res.scalars().all()

    if not invoices:
        raise HTTPException(
            status_code=404,
            detail="No hay facturas aprobadas disponibles para exportar."
        )

    csv_content = export_invoices_to_contasol_csv(invoices)
    
    return Response(
        content=csv_content.encode("latin-1", errors="replace"),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=diario_contasol.csv"
        }
    )

@router.get("/a3-suenlace")
async def export_a3(
    company_id: Optional[str] = Query(None, description="Filtrar por empresa"),
    company_code: str = Query("00001", description="Código de empresa en A3ASESOR"),
    only_processed: bool = Query(True, description="Exportar sólo facturas revisadas/aprobadas"),
    db: AsyncSession = Depends(get_db)
):
    """Descarga el fichero SUENLACE.DAT para importar en A3ASESOR / A3CON."""
    stmt = (
        select(Invoice)
        .options(selectinload(Invoice.accounting_entries))
        .order_by(Invoice.issue_date.asc())
    )
    if company_id:
        stmt = stmt.where(Invoice.company_id == company_id)
    if only_processed:
        stmt = stmt.where(Invoice.is_processed == True)

    res = await db.execute(stmt)
    invoices = res.scalars().all()

    if not invoices:
        raise HTTPException(
            status_code=404,
            detail="No hay facturas aprobadas disponibles para exportar."
        )

    dat_content = export_invoices_to_a3_suenlace(invoices, company_code=company_code)

    return Response(
        content=dat_content.encode("cp1252", errors="replace"),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": "attachment; filename=SUENLACE.DAT"
        }
    )
