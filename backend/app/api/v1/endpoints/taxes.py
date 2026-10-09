import re
from typing import Dict, Any, List, Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query, Response, Request, status
from sqlalchemy import select, extract, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.company import Company
from app.models.invoice import Invoice, InvoiceTaxBreakdown
from app.models.sales_invoice import SalesInvoice, SalesInvoiceTaxBreakdown
from app.models.accounting_entry import AccountingEntryLine
from app.core.aeat_models import (
    generate_modelo_303_file,
    validate_modelo_303_data,
    generate_modelo_111_file,
    validate_modelo_111_data,
    generate_modelo_115_file,
    validate_modelo_115_data,
    generate_modelo_347_file,
    validate_modelo_347_data,
)
from app.core.audit_logger import log_security_event

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


@router.get("/{company_id}/export/modelo-303")
async def export_modelo_303(
    company_id: str,
    request: Request,
    year: int = Query(..., description="Año fiscal de la autoliquidación (ej. 2026)"),
    period: str = Query(..., description="Periodo de liquidación: 1T, 2T, 3T, 4T"),
    forma_pago: Optional[str] = Query("I", description="I = Ingreso, C = Compensación, D = Devolución (solo 4T)"),
    iban: Optional[str] = Query(None, description="IBAN para domiciliación bancaria o devolución"),
    db: AsyncSession = Depends(get_db)
):
    """
    Exporta el fichero plano de autoliquidación oficial del Modelo 303 (IVA)
    conforme al diseño de registro publicado en el BOE por la AEAT.
    """
    comp = await db.get(Company, company_id)
    if not comp:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    period_clean = period.upper().strip()
    start_date, end_date = get_period_date_range(year, period_clean)

    # 1. Recuperar IVA Devengado en ventas del periodo
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

    devengado_21["base"] = round(devengado_21["base"], 2)
    devengado_21["cuota"] = round(devengado_21["cuota"], 2)
    devengado_10["base"] = round(devengado_10["base"], 2)
    devengado_10["cuota"] = round(devengado_10["cuota"], 2)
    devengado_4["base"] = round(devengado_4["base"], 2)
    devengado_4["cuota"] = round(devengado_4["cuota"], 2)

    total_cuota_devengada = round(
        devengado_21["cuota"] + devengado_10["cuota"] + devengado_4["cuota"], 2
    )

    # 2. Recuperar IVA Deducible en compras/gastos del periodo
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

    total_base_deducible = round(sum(inv.total_base for inv in purchase_invoices), 2)
    total_cuota_deducible = round(sum(inv.total_tax for inv in purchase_invoices), 2)

    # 3. Resultado de la liquidación (casilla [71])
    resultado_303 = round(total_cuota_devengada - total_cuota_deducible, 2)

    # Determinar tipo de resultado según saldo
    tipo_res = (forma_pago or "I").upper().strip()
    if resultado_303 > 0:
        tipo_res = "I"
    elif resultado_303 < 0:
        if tipo_res == "D" and period_clean != "4T":
            tipo_res = "C"
        elif tipo_res not in ("C", "D"):
            tipo_res = "C"
    else:
        tipo_res = "N"

    declarante = {
        "nif": comp.cif,
        "razon_social": comp.razon_social,
        "telefono": getattr(comp, "telefono", "") or "",
        "contacto": getattr(comp, "contacto", "") or ""
    }

    liquidacion = {
        "base_superreducido": devengado_4["base"],
        "cuota_superreducido": devengado_4["cuota"],
        "base_reducido": devengado_10["base"],
        "cuota_reducido": devengado_10["cuota"],
        "base_general": devengado_21["base"],
        "cuota_general": devengado_21["cuota"],
        "total_cuotas_devengadas": total_cuota_devengada,
        "base_deducible_corrientes": total_base_deducible,
        "cuota_deducible_corrientes": total_cuota_deducible,
        "base_deducible_inversion": 0.0,
        "cuota_deducible_inversion": 0.0,
        "total_cuotas_deducibles": total_cuota_deducible,
        "diferencia": resultado_303,
        "compensacion_periodos_anteriores": 0.0,
        "resultado_autoliquidacion": resultado_303,
        "tipo_resultado": tipo_res,
        "iban": iban
    }

    # 4. Validación técnica previa y cuadre contable
    payload_val = {
        "declarante": declarante,
        "liquidacion": liquidacion,
        "periodo": period_clean,
        "ejercicio": year
    }
    is_valid, validation_errors = validate_modelo_303_data(payload_val)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Error de validación y cuadre contable en la autoliquidación del Modelo 303.",
                "errors": validation_errors
            }
        )

    # 5. Generar archivo plano oficial BOE
    try:
        file_content = generate_modelo_303_file(declarante, liquidacion, period_clean, year)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generando fichero del Modelo 303: {str(exc)}"
        )

    # 6. Trazabilidad RGPD y auditoría de exportación fiscal
    log_security_event(
        action="AEAT_MODELO_303_EXPORT",
        resource_id=f"MOD303_{comp.cif}_{year}_{period_clean}",
        request=request,
        empresa_id=str(company_id),
        status="SUCCESS",
        details={
            "year": year,
            "period": period_clean,
            "resultado_303": resultado_303,
            "tipo_resultado": tipo_res
        }
    )

    clean_cif = re.sub(r"[^A-Za-z0-9]", "", comp.cif)
    filename = f"303_{clean_cif}_{year}_{period_clean}.txt"

    return Response(
        content=file_content,
        media_type="text/plain; charset=iso-8859-1",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


@router.get("/{company_id}/export/modelo-111")
async def export_modelo_111(
    company_id: str,
    request: Request,
    year: int = Query(default=2026, description="Ejercicio fiscal (ej. 2026)"),
    period: str = Query(default="1T", description="1T, 2T, 3T, 4T o M01 a M12"),
    forma_pago: str = Query(default="I", description="I=Ingreso, U=Domiciliación, N=Negativa"),
    iban: Optional[str] = Query(default=None, description="IBAN si forma de pago es domiciliación"),
    nrc: Optional[str] = Query(default=None, description="Número de Referencia Completo (NRC)"),
    db: AsyncSession = Depends(get_db)
):
    """Genera y descarga el fichero oficial de autoliquidación del Modelo 111 (IRPF) en diseño de registro BOE."""
    comp = await db.get(Company, company_id)
    if not comp:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    period_clean = period.upper().strip()
    if period_clean.startswith("M"):
        period_clean = period_clean[1:].zfill(2)

    start_date, end_date = get_period_date_range(year, period)

    # Facturas de proveedores con retención practicada
    purchases_stmt = select(Invoice).where(
        Invoice.company_id == company_id,
        Invoice.issue_date >= start_date,
        Invoice.issue_date <= end_date,
        Invoice.is_processed == True
    )
    purch_res = await db.execute(purchases_stmt)
    purchase_invoices = purch_res.scalars().all()

    ret_prof_base = 0.0
    ret_prof_cuota = 0.0
    perceptores_set = set()

    for inv in purchase_invoices:
        if inv.total_retention and inv.total_retention > 0:
            ret_prof_base += float(inv.total_base or 0.0)
            ret_prof_cuota += float(inv.total_retention)
            if inv.issuer_cif:
                perceptores_set.add(inv.issuer_cif)

    declarante = {
        "nif": comp.cif,
        "razon_social": comp.razon_social,
        "telefono": getattr(comp, "telefono", "") or "",
        "contacto": getattr(comp, "contacto", "") or ""
    }

    liquidacion = {
        "num_perceptores_trabajo": 0,
        "base_trabajo": 0.0,
        "retenciones_trabajo": 0.0,
        "num_perceptores_profesionales": len(perceptores_set),
        "base_profesionales": round(ret_prof_base, 2),
        "retenciones_profesionales": round(ret_prof_cuota, 2),
        "a_deducir": 0.0,
        "resultado_autoliquidacion": round(ret_prof_cuota, 2),
        "tipo_resultado": forma_pago.upper() if round(ret_prof_cuota, 2) > 0 else "N",
        "iban": iban,
        "nrc": nrc
    }

    is_valid, validation_errors = validate_modelo_111_data({
        "declarante": declarante,
        "liquidacion": liquidacion,
        "periodo": period_clean,
        "ejercicio": year
    })
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Error validando autoliquidación Modelo 111", "errors": validation_errors}
        )

    try:
        file_content = generate_modelo_111_file(declarante, liquidacion, period_clean, year)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error generando fichero del Modelo 111: {str(exc)}")

    log_security_event(
        action="AEAT_MODELO_111_EXPORT",
        resource_id=f"MOD111_{comp.cif}_{year}_{period_clean}",
        request=request,
        empresa_id=str(company_id),
        status="SUCCESS",
        details={"year": year, "period": period_clean, "resultado": round(ret_prof_cuota, 2)}
    )

    clean_cif = re.sub(r"[^A-Za-z0-9]", "", comp.cif)
    filename = f"111_{clean_cif}_{year}_{period_clean}.txt"
    return Response(
        content=file_content,
        media_type="text/plain; charset=iso-8859-1",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.get("/{company_id}/export/modelo-115")
async def export_modelo_115(
    company_id: str,
    request: Request,
    year: int = Query(default=2026, description="Ejercicio fiscal"),
    period: str = Query(default="1T", description="1T, 2T, 3T, 4T o M01 a M12"),
    forma_pago: str = Query(default="I", description="I=Ingreso, U=Domiciliación, N=Negativa"),
    iban: Optional[str] = Query(default=None, description="IBAN si forma de pago es domiciliación"),
    nrc: Optional[str] = Query(default=None, description="NRC"),
    db: AsyncSession = Depends(get_db)
):
    """Genera y descarga el fichero oficial de autoliquidación del Modelo 115 (Arrendamientos) en diseño BOE."""
    comp = await db.get(Company, company_id)
    if not comp:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    period_clean = period.upper().strip()
    if period_clean.startswith("M"):
        period_clean = period_clean[1:].zfill(2)

    start_date, end_date = get_period_date_range(year, period)

    rent_entries_stmt = select(AccountingEntryLine).where(
        AccountingEntryLine.company_id == company_id,
        AccountingEntryLine.fecha >= start_date,
        AccountingEntryLine.fecha <= end_date,
        AccountingEntryLine.subcuenta.like("621%")
    )
    rent_res = await db.execute(rent_entries_stmt)
    rent_entries = rent_res.scalars().all()

    rent_base = sum(e.debe for e in rent_entries)
    rent_retention = round(rent_base * 0.19, 2) if rent_base > 0 else 0.0

    declarante = {
        "nif": comp.cif,
        "razon_social": comp.razon_social,
        "telefono": getattr(comp, "telefono", "") or "",
        "contacto": getattr(comp, "contacto", "") or ""
    }

    liquidacion = {
        "num_perceptores": 1 if rent_base > 0 else 0,
        "base_retenciones": round(rent_base, 2),
        "retenciones_practicadas": rent_retention,
        "a_deducir": 0.0,
        "resultado_autoliquidacion": rent_retention,
        "tipo_resultado": forma_pago.upper() if rent_retention > 0 else "N",
        "iban": iban,
        "nrc": nrc
    }

    is_valid, validation_errors = validate_modelo_115_data({
        "declarante": declarante,
        "liquidacion": liquidacion,
        "periodo": period_clean,
        "ejercicio": year
    })
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Error validando autoliquidación Modelo 115", "errors": validation_errors}
        )

    try:
        file_content = generate_modelo_115_file(declarante, liquidacion, period_clean, year)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error generando fichero del Modelo 115: {str(exc)}")

    log_security_event(
        action="AEAT_MODELO_115_EXPORT",
        resource_id=f"MOD115_{comp.cif}_{year}_{period_clean}",
        request=request,
        empresa_id=str(company_id),
        status="SUCCESS",
        details={"year": year, "period": period_clean, "resultado": rent_retention}
    )

    clean_cif = re.sub(r"[^A-Za-z0-9]", "", comp.cif)
    filename = f"115_{clean_cif}_{year}_{period_clean}.txt"
    return Response(
        content=file_content,
        media_type="text/plain; charset=iso-8859-1",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.get("/{company_id}/export/modelo-347")
async def export_modelo_347(
    company_id: str,
    request: Request,
    year: int = Query(default=2026, description="Año fiscal a declarar"),
    db: AsyncSession = Depends(get_db)
):
    """Genera y descarga el fichero de declaración anual de operaciones con terceros (Modelo 347) en diseño BOE."""
    comp = await db.get(Company, company_id)
    if not comp:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    # Consolidación anual agrupando por NIF/CIF
    from collections import defaultdict
    suppliers_ops = defaultdict(lambda: {"razon_social": "", "quarters": [0.0, 0.0, 0.0, 0.0], "total": 0.0})

    inv_stmt = select(Invoice).where(
        Invoice.company_id == company_id,
        extract("year", Invoice.issue_date) == year,
        Invoice.is_processed == True
    )
    inv_res = await db.execute(inv_stmt)
    invoices = inv_res.scalars().all()

    for inv in invoices:
        cif = (inv.issuer_cif or "").upper().strip()
        if not cif:
            continue
        amt = float(inv.total_amount or 0.0)
        m = inv.issue_date.month
        q_idx = 0 if m <= 3 else (1 if m <= 6 else (2 if m <= 9 else 3))
        suppliers_ops[cif]["quarters"][q_idx] += amt
        suppliers_ops[cif]["total"] += amt
        if not suppliers_ops[cif]["razon_social"]:
            suppliers_ops[cif]["razon_social"] = inv.issuer_name or cif

    # Filtrar solo terceros cuyo volumen supere el umbral legal de 3.005,06 €
    operaciones_347 = []
    for cif, data in suppliers_ops.items():
        if data["total"] > 3005.06:
            operaciones_347.append({
                "nif": cif,
                "razon_social": data["razon_social"],
                "clave_operacion": "A",  # A=Compras/Adquisiciones
                "importe_anual": round(data["total"], 2),
                "trimestre_1": round(data["quarters"][0], 2),
                "trimestre_2": round(data["quarters"][1], 2),
                "trimestre_3": round(data["quarters"][2], 2),
                "trimestre_4": round(data["quarters"][3], 2),
            })

    # También ventas a clientes > 3005.06 €
    sales_ops = defaultdict(lambda: {"razon_social": "", "quarters": [0.0, 0.0, 0.0, 0.0], "total": 0.0})
    sales_stmt = select(SalesInvoice).where(
        SalesInvoice.company_id == company_id,
        extract("year", SalesInvoice.issue_date) == year
    )
    sales_res = await db.execute(sales_stmt)
    sales_invoices = sales_res.scalars().all()

    for sinv in sales_invoices:
        cif = (sinv.client_cif or "").upper().strip()
        if not cif:
            continue
        amt = float(sinv.total_amount or 0.0)
        m = sinv.issue_date.month
        q_idx = 0 if m <= 3 else (1 if m <= 6 else (2 if m <= 9 else 3))
        sales_ops[cif]["quarters"][q_idx] += amt
        sales_ops[cif]["total"] += amt
        if not sales_ops[cif]["razon_social"]:
            sales_ops[cif]["razon_social"] = sinv.client_name or cif

    for cif, data in sales_ops.items():
        if data["total"] > 3005.06:
            operaciones_347.append({
                "nif": cif,
                "razon_social": data["razon_social"],
                "clave_operacion": "B",  # B=Ventas/Entregas
                "importe_anual": round(data["total"], 2),
                "trimestre_1": round(data["quarters"][0], 2),
                "trimestre_2": round(data["quarters"][1], 2),
                "trimestre_3": round(data["quarters"][2], 2),
                "trimestre_4": round(data["quarters"][3], 2),
            })

    declarante = {
        "nif": comp.cif,
        "razon_social": comp.razon_social,
        "telefono": getattr(comp, "telefono", "") or "",
        "contacto": getattr(comp, "contacto", "") or ""
    }

    try:
        file_content = generate_modelo_347_file(declarante, operaciones_347, year)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error generando fichero del Modelo 347: {str(exc)}")

    log_security_event(
        action="AEAT_MODELO_347_EXPORT",
        resource_id=f"MOD347_{comp.cif}_{year}",
        request=request,
        empresa_id=str(company_id),
        status="SUCCESS",
        details={"year": year, "total_operaciones_declaradas": len(operaciones_347)}
    )

    clean_cif = re.sub(r"[^A-Za-z0-9]", "", comp.cif)
    filename = f"347_{clean_cif}_{year}.txt"
    return Response(
        content=file_content,
        media_type="text/plain; charset=iso-8859-1",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.get("/{company_id}/audit-risk-score")
async def get_tax_audit_risk_score(
    company_id: str,
    request: Request,
    year: int = Query(default=2026, description="Ejercicio fiscal"),
    period: str = Query(default="1T", description="1T, 2T, 3T, 4T o ANUAL"),
    db: AsyncSession = Depends(get_db),
):
    """Diagnóstico preventivo de riesgo tributario e inspección AEAT antes de la presentación oficial."""
    from app.services.tax_risk_auditor import assess_company_tax_risk
    try:
        report = await assess_company_tax_risk(
            company_id=company_id,
            year=year,
            period=period,
            db=db,
        )
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error evaluando riesgo fiscal: {str(exc)}")

    log_security_event(
        action="TAX_RISK_AUDIT_ASSESSED",
        resource_id=f"RISK_{company_id}_{year}_{period}",
        request=request,
        empresa_id=str(company_id),
        status="SUCCESS",
        details={"risk_score": report["risk_score"], "risk_level": report["risk_level"]}
    )

    return report


