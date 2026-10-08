from typing import Dict, Any, List
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, extract, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.company import Company
from app.models.invoice import Invoice, InvoiceTaxBreakdown
from app.models.sales_invoice import SalesInvoice, SalesInvoiceTaxBreakdown
from app.models.accounting_entry import AccountingEntryLine

router = APIRouter()

def get_period_date_range(year: int, period: str):
    """Devuelve las fechas de inicio y fin para un trimestre o mes."""
    if period == "1T":
        return date(year, 1, 1), date(year, 3, 31)
    elif period == "2T":
        return date(year, 4, 1), date(year, 6, 30)
    elif period == "3T":
        return date(year, 7, 1), date(year, 9, 30)
    elif period == "4T":
        return date(year, 10, 1), date(year, 12, 31)
    elif period.startswith("M"):
        # M01 a M12
        month = int(period[1:])
        import calendar
        last_day = calendar.monthrange(year, month)[1]
        return date(year, month, 1), date(year, month, last_day)
    else: # Anual
        return date(year, 1, 1), date(year, 12, 31)


@router.get("/{company_id}/taxes/summary")
async def get_tax_summary(
    company_id: str,
    year: int = Query(default=2026, description="Año fiscal"),
    period: str = Query(default="1T", description="1T, 2T, 3T, 4T o ANUAL"),
    db: AsyncSession = Depends(get_db)
):
    """
    Calcula en tiempo real los borradores oficiales de los Modelos 303, 111, 115
    y el informe preventivo del Modelo 347 para la empresa seleccionada.
    """
    comp = await db.get(Company, company_id)
    if not comp:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    start_date, end_date = get_period_date_range(year, period)

    # -------------------------------------------------------------
    # 1. MODELO 303 (IVA)
    # -------------------------------------------------------------
    # IVA Devengado (Ventas)
    sales_stmt = (
        select(SalesInvoice)
        .options(selectinload(SalesInvoice.tax_breakdown))
        .where(
            SalesInvoice.company_id == company_id,
            SalesInvoice.issue_date >= start_date,
            SalesInvoice.issue_date <= end_date,
            SalesInvoice.status.in_(["ISSUED", "PAID"])
        )
    )
    sales_res = await db.execute(sales_stmt)
    sales_invoices = sales_res.scalars().all()

    devengado_21 = {"base": 0.0, "cuota": 0.0}
    devengado_10 = {"base": 0.0, "cuota": 0.0}
    devengado_4  = {"base": 0.0, "cuota": 0.0}
    devengado_0  = {"base": 0.0, "cuota": 0.0}

    for inv in sales_invoices:
        for tb in inv.tax_breakdown:
            if abs(tb.tax_rate - 21.0) < 0.5:
                devengado_21["base"] += tb.tax_base
                devengado_21["cuota"] += tb.tax_amount
            elif abs(tb.tax_rate - 10.0) < 0.5:
                devengado_10["base"] += tb.tax_base
                devengado_10["cuota"] += tb.tax_amount
            elif abs(tb.tax_rate - 4.0) < 0.5:
                devengado_4["base"] += tb.tax_base
                devengado_4["cuota"] += tb.tax_amount
            else:
                devengado_0["base"] += tb.tax_base

    total_cuota_devengada = round(
        devengado_21["cuota"] + devengado_10["cuota"] + devengado_4["cuota"], 2
    )

    # IVA Deducible / Soportado (Gastos)
    purchases_stmt = (
        select(Invoice)
        .options(selectinload(Invoice.tax_breakdown))
        .where(
            Invoice.company_id == company_id,
            Invoice.issue_date >= start_date,
            Invoice.issue_date <= end_date,
            Invoice.is_processed == True
        )
    )
    purch_res = await db.execute(purchases_stmt)
    purchase_invoices = purch_res.scalars().all()

    total_base_deducible = sum(inv.total_base for inv in purchase_invoices)
    total_cuota_deducible = sum(inv.total_tax for inv in purchase_invoices)

    resultado_303 = round(total_cuota_devengada - total_cuota_deducible, 2)

    modelo_303 = {
        "periodo": period,
        "ejercicio": year,
        "devengado": {
            "r21": {"base": round(devengado_21["base"], 2), "cuota": round(devengado_21["cuota"], 2)},
            "r10": {"base": round(devengado_10["base"], 2), "cuota": round(devengado_10["cuota"], 2)},
            "r4":  {"base": round(devengado_4["base"], 2),  "cuota": round(devengado_4["cuota"], 2)},
            "total_cuota": total_cuota_devengada,
        },
        "deducible": {
            "base_interior": round(total_base_deducible, 2),
            "cuota_interior": round(total_cuota_deducible, 2),
            "total_cuota": round(total_cuota_deducible, 2),
        },
        "resultado": resultado_303,
        "tipo_resultado": "A INGRESAR" if resultado_303 > 0 else "A COMPENSAR" if resultado_303 < 0 else "CERO"
    }

    # -------------------------------------------------------------
    # 2. MODELO 111 (Retenciones Profesionales y del Trabajo)
    # -------------------------------------------------------------
    ret_prof_base = 0.0
    ret_prof_cuota = 0.0
    perceptores_set = set()

    for inv in purchase_invoices:
        if inv.total_retention > 0:
            ret_prof_base += inv.total_base
            ret_prof_cuota += inv.total_retention
            perceptores_set.add(inv.issuer_cif)

    modelo_111 = {
        "periodo": period,
        "ejercicio": year,
        "numero_perceptores": len(perceptores_set),
        "base_retenciones": round(ret_prof_base, 2),
        "importe_retenciones": round(ret_prof_cuota, 2),
    }

    # -------------------------------------------------------------
    # 3. MODELO 115 (Arrendamientos Inmuebles Urbanos - Cuentas 621)
    # -------------------------------------------------------------
    rent_entries_stmt = select(AccountingEntryLine).where(
        AccountingEntryLine.company_id == company_id,
        AccountingEntryLine.fecha >= start_date,
        AccountingEntryLine.fecha <= end_date,
        AccountingEntryLine.subcuenta.like("621%")
    )
    rent_res = await db.execute(rent_entries_stmt)
    rent_entries = rent_res.scalars().all()

    rent_base = sum(e.debe for e in rent_entries)
    # Estimar retención típica 19% del alquiler si no viene desglosado
    rent_retention = round(rent_base * 0.19, 2) if rent_base > 0 else 0.0

    modelo_115 = {
        "periodo": period,
        "ejercicio": year,
        "numero_perceptores": 1 if rent_base > 0 else 0,
        "base_retenciones": round(rent_base, 2),
        "importe_retenciones": rent_retention,
    }

    # -------------------------------------------------------------
    # 4. CONTROL MODELO 347 (Operaciones anuales > 3.005,06 €)
    # -------------------------------------------------------------
    # Agrupamos compras de todo el año
    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)

    all_year_purchases_stmt = (
        select(Invoice)
        .where(
            Invoice.company_id == company_id,
            Invoice.issue_date >= year_start,
            Invoice.issue_date <= year_end,
            Invoice.is_processed == True
        )
    )
    all_purchases = (await db.execute(all_year_purchases_stmt)).scalars().all()

    contacts_summary: Dict[str, Dict[str, Any]] = {}
    for inv in all_purchases:
        cif = inv.issuer_cif
        if cif not in contacts_summary:
            contacts_summary[cif] = {
                "cif": cif,
                "nombre": inv.issuer_name,
                "tipo": "PROVEEDOR",
                "t1": 0.0, "t2": 0.0, "t3": 0.0, "t4": 0.0,
                "total_anual": 0.0
            }
        
        m = inv.issue_date.month
        t_key = "t1" if m <= 3 else "t2" if m <= 6 else "t3" if m <= 9 else "t4"
        contacts_summary[cif][t_key] += inv.total_amount
        contacts_summary[cif]["total_anual"] += inv.total_amount

    # Agrupar ventas de todo el año
    all_year_sales_stmt = (
        select(SalesInvoice)
        .where(
            SalesInvoice.company_id == company_id,
            SalesInvoice.issue_date >= year_start,
            SalesInvoice.issue_date <= year_end,
            SalesInvoice.status.in_(["ISSUED", "PAID"])
        )
    )
    all_sales = (await db.execute(all_year_sales_stmt)).scalars().all()

    for sinv in all_sales:
        cif = sinv.customer_cif
        if cif not in contacts_summary:
            contacts_summary[cif] = {
                "cif": cif,
                "nombre": sinv.customer_name,
                "tipo": "CLIENTE",
                "t1": 0.0, "t2": 0.0, "t3": 0.0, "t4": 0.0,
                "total_anual": 0.0
            }
        m = sinv.issue_date.month
        t_key = "t1" if m <= 3 else "t2" if m <= 6 else "t3" if m <= 9 else "t4"
        contacts_summary[cif][t_key] += sinv.total_amount
        contacts_summary[cif]["total_anual"] += sinv.total_amount

    # Filtrar aquellos con total_anual > 3005.06 €
    threshold = 3005.06
    superan_347 = []
    candidatos_cercanos = []

    for item in contacts_summary.values():
        item["total_anual"] = round(item["total_anual"], 2)
        item["t1"] = round(item["t1"], 2)
        item["t2"] = round(item["t2"], 2)
        item["t3"] = round(item["t3"], 2)
        item["t4"] = round(item["t4"], 2)

        if item["total_anual"] >= threshold:
            superan_347.append(item)
        elif item["total_anual"] >= (threshold * 0.75):
            candidatos_cercanos.append(item)

    superan_347.sort(key=lambda x: x["total_anual"], reverse=True)

    modelo_347 = {
        "ejercicio": year,
        "umbral_declarable": threshold,
        "total_declarables": len(superan_347),
        "total_proximos": len(candidatos_cercanos),
        "declarables": superan_347,
        "en_seguimiento": candidatos_cercanos
    }

    return {
        "company_id": company_id,
        "year": year,
        "period": period,
        "modelo_303": modelo_303,
        "modelo_111": modelo_111,
        "modelo_115": modelo_115,
        "modelo_347": modelo_347
    }
