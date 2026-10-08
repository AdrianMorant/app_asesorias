from typing import List, Optional, Dict, Any
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.company import Company
from app.models.invoice import Invoice
from app.models.sales_invoice import SalesInvoice
from app.models.accounting_entry import AccountingEntryLine
from app.models.account import Account

router = APIRouter()

@router.get("/{company_id}/journal")
async def get_journal_entries(
    company_id: str,
    from_date: Optional[date] = Query(None, description="Fecha desde"),
    to_date: Optional[date] = Query(None, description="Fecha hasta"),
    search: Optional[str] = Query(None, description="Filtro por subcuenta o concepto"),
    db: AsyncSession = Depends(get_db)
):
    """
    Devuelve los asientos contables en partida doble del Libro Diario,
    agrupados por número de asiento y fecha, verificando el cuadre.
    """
    comp = await db.get(Company, company_id)
    if not comp:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    # Recuperar líneas de asientos asociados a esta empresa
    # (ya sea directamente por company_id, por factura de gasto o por factura de venta)
    stmt = (
        select(AccountingEntryLine)
        .outerjoin(Invoice, AccountingEntryLine.invoice_id == Invoice.id)
        .outerjoin(SalesInvoice, AccountingEntryLine.sales_invoice_id == SalesInvoice.id)
        .where(
            or_(
                AccountingEntryLine.company_id == company_id,
                Invoice.company_id == company_id,
                SalesInvoice.company_id == company_id
            )
        )
    )

    if from_date:
        stmt = stmt.where(AccountingEntryLine.fecha >= from_date)
    if to_date:
        stmt = stmt.where(AccountingEntryLine.fecha <= to_date)
    if search:
        pattern = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                AccountingEntryLine.subcuenta.ilike(pattern),
                AccountingEntryLine.concepto.ilike(pattern),
                AccountingEntryLine.documento.ilike(pattern)
            )
        )

    stmt = stmt.order_by(AccountingEntryLine.fecha.asc(), AccountingEntryLine.entry_number.asc(), AccountingEntryLine.id.asc())
    res = await db.execute(stmt)
    lines = res.scalars().all()

    # Agrupar por asiento
    entries_map: Dict[str, Dict[str, Any]] = {}
    for line in lines:
        group_key = f"{line.fecha.isoformat()}_{line.entry_number}"
        if group_key not in entries_map:
            entries_map[group_key] = {
                "entry_number": line.entry_number,
                "fecha": line.fecha.isoformat(),
                "documento": line.documento,
                "exported_to_erp": line.exported_to_erp,
                "export_batch_id": line.export_batch_id,
                "total_debe": 0.0,
                "total_haber": 0.0,
                "is_balanced": True,
                "lines": []
            }
        
        entries_map[group_key]["total_debe"] += line.debe
        entries_map[group_key]["total_haber"] += line.haber
        entries_map[group_key]["lines"].append({
            "id": line.id,
            "subcuenta": line.subcuenta,
            "concepto": line.concepto,
            "debe": line.debe,
            "haber": line.haber,
            "documento": line.documento,
            "exported_to_erp": line.exported_to_erp
        })

    # Verificar cuadre y redondear
    grouped_entries = list(entries_map.values())
    for e in grouped_entries:
        e["total_debe"] = round(e["total_debe"], 2)
        e["total_haber"] = round(e["total_haber"], 2)
        e["is_balanced"] = abs(e["total_debe"] - e["total_haber"]) < 0.01

    return {
        "company_id": company_id,
        "total_asientos": len(grouped_entries),
        "total_apuntes": len(lines),
        "asientos": grouped_entries
    }


@router.get("/{company_id}/ledger/{subcuenta}")
async def get_account_ledger(
    company_id: str,
    subcuenta: str,
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Devuelve los movimientos del Libro Mayor para una subcuenta individual,
    con saldo progresivo cronológico.
    """
    comp = await db.get(Company, company_id)
    if not comp:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    # Saldo inicial de la cuenta en el plan de cuentas
    acc_stmt = select(Account).where(Account.company_id == company_id, Account.codigo == subcuenta)
    acc = (await db.execute(acc_stmt)).scalar_one_or_none()
    debe_inicial = acc.debe_inicial if acc else 0.0
    haber_inicial = acc.haber_inicial if acc else 0.0
    saldo_acumulado = round(debe_inicial - haber_inicial, 2)

    # Recuperar movimientos
    stmt = (
        select(AccountingEntryLine)
        .outerjoin(Invoice, AccountingEntryLine.invoice_id == Invoice.id)
        .outerjoin(SalesInvoice, AccountingEntryLine.sales_invoice_id == SalesInvoice.id)
        .where(
            AccountingEntryLine.subcuenta == subcuenta,
            or_(
                AccountingEntryLine.company_id == company_id,
                Invoice.company_id == company_id,
                SalesInvoice.company_id == company_id
            )
        )
    )

    if from_date:
        stmt = stmt.where(AccountingEntryLine.fecha >= from_date)
    if to_date:
        stmt = stmt.where(AccountingEntryLine.fecha <= to_date)

    stmt = stmt.order_by(AccountingEntryLine.fecha.asc(), AccountingEntryLine.entry_number.asc())
    res = await db.execute(stmt)
    lines = res.scalars().all()

    total_debe = debe_inicial
    total_haber = haber_inicial
    movements = []

    for l in lines:
        total_debe += l.debe
        total_haber += l.haber
        saldo_acumulado = round(saldo_acumulado + l.debe - l.haber, 2)
        movements.append({
            "id": l.id,
            "entry_number": l.entry_number,
            "fecha": l.fecha.isoformat(),
            "concepto": l.concepto,
            "documento": l.documento,
            "debe": l.debe,
            "haber": l.haber,
            "saldo_progresivo": saldo_acumulado,
            "signo": "D" if saldo_acumulado > 0 else "H" if saldo_acumulado < 0 else "0"
        })

    return {
        "company_id": company_id,
        "subcuenta": subcuenta,
        "descripcion": acc.descripcion if acc else "",
        "debe_inicial": debe_inicial,
        "haber_inicial": haber_inicial,
        "total_debe": round(total_debe, 2),
        "total_haber": round(total_haber, 2),
        "saldo_final": round(total_debe - total_haber, 2),
        "tipo_saldo": "DEUDOR" if (total_debe - total_haber) > 0 else "ACREEDOR" if (total_debe - total_haber) < 0 else "CERO",
        "movimientos": movements
    }


@router.get("/{company_id}/trial-balance")
async def get_trial_balance(company_id: str, db: AsyncSession = Depends(get_db)):
    """
    Genera el Balance de Sumas y Saldos completo para la empresa,
    verificando el principio de partida doble (Suma Debe == Suma Haber, Saldo Deudor == Saldo Acreedor).
    """
    comp = await db.get(Company, company_id)
    if not comp:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    # Todas las cuentas
    acc_stmt = select(Account).where(Account.company_id == company_id).order_by(Account.codigo.asc())
    accounts = (await db.execute(acc_stmt)).scalars().all()

    # Todos los apuntes
    entries_stmt = (
        select(
            AccountingEntryLine.subcuenta,
            func.sum(AccountingEntryLine.debe).label("sum_debe"),
            func.sum(AccountingEntryLine.haber).label("sum_haber")
        )
        .outerjoin(Invoice, AccountingEntryLine.invoice_id == Invoice.id)
        .outerjoin(SalesInvoice, AccountingEntryLine.sales_invoice_id == SalesInvoice.id)
        .where(
            or_(
                AccountingEntryLine.company_id == company_id,
                Invoice.company_id == company_id,
                SalesInvoice.company_id == company_id
            )
        )
        .group_by(AccountingEntryLine.subcuenta)
    )
    entries_res = await db.execute(entries_stmt)
    entries_map = {row.subcuenta: (row.sum_debe or 0.0, row.sum_haber or 0.0) for row in entries_res}

    items = []
    total_suma_debe = 0.0
    total_suma_haber = 0.0
    total_saldo_deudor = 0.0
    total_saldo_acreedor = 0.0

    # Construir tabla
    for acc in accounts:
        mov_debe, mov_haber = entries_map.get(acc.codigo, (0.0, 0.0))
        suma_debe = round((acc.debe_inicial or 0.0) + mov_debe, 2)
        suma_haber = round((acc.haber_inicial or 0.0) + mov_haber, 2)

        # Mostrar sólo cuentas con saldo o movimientos
        if suma_debe == 0.0 and suma_haber == 0.0:
            continue

        neto = round(suma_debe - suma_haber, 2)
        saldo_deudor = neto if neto > 0 else 0.0
        saldo_acreedor = abs(neto) if neto < 0 else 0.0

        total_suma_debe += suma_debe
        total_suma_haber += suma_haber
        total_saldo_deudor += saldo_deudor
        total_saldo_acreedor += saldo_acreedor

        items.append({
            "codigo": acc.codigo,
            "descripcion": acc.descripcion,
            "nivel": len(acc.codigo) if acc.codigo else 1,
            "es_titulo": False,
            "suma_debe": suma_debe,
            "suma_haber": suma_haber,
            "saldo_deudor": saldo_deudor,
            "saldo_acreedor": saldo_acreedor
        })

    total_suma_debe = round(total_suma_debe, 2)
    total_suma_haber = round(total_suma_haber, 2)
    total_saldo_deudor = round(total_saldo_deudor, 2)
    total_saldo_acreedor = round(total_saldo_acreedor, 2)

    return {
        "company_id": company_id,
        "items": items,
        "totales": {
            "suma_debe": total_suma_debe,
            "suma_haber": total_suma_haber,
            "saldo_deudor": total_saldo_deudor,
            "saldo_acreedor": total_saldo_acreedor,
            "descuadre_sumas": round(abs(total_suma_debe - total_suma_haber), 2),
            "descuadre_saldos": round(abs(total_saldo_deudor - total_saldo_acreedor), 2),
            "cuadrado": abs(total_suma_debe - total_suma_haber) < 0.01 and abs(total_saldo_deudor - total_saldo_acreedor) < 0.01
        }
    }
