"""Módulo de Scoring Preventivo Antifraude y Auditoría de Riesgo Tributario AEAT.

Ejecuta análisis de control interno y auditoría fiscal previa a la presentación oficial:
1. Ratio de gastos deducibles vs ingresos (detección de desproporción anómala).
2. Volumen de facturas simplificadas (tickets) sin NIF vs límites del RD 1619/2012 (3.000 € / 400 €).
3. Desviación en cuotas de IVA soportado deducible sin correlación con ventas o bienes de inversión.
4. Detección de retenciones IRPF indebidas aplicadas a personas jurídicas (sociedades CIF letra A/B).
5. Evaluación del riesgo fiscal global (LOW, MEDIUM, HIGH) con recomendaciones de regularización preventiva.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any, Dict, List, Optional
from sqlalchemy import select, extract, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company
from app.models.invoice import Invoice
from app.models.sales_invoice import SalesInvoice


async def assess_company_tax_risk(
    company_id: str,
    year: int,
    period: str,
    db: AsyncSession,
) -> Dict[str, Any]:
    """Evalúa de forma integral los indicadores de riesgo fiscal de la empresa para un trimestre o ejercicio.

    Args:
        company_id: Identificador de la empresa auditada.
        year: Ejercicio fiscal (ej. 2026).
        period: Periodo impositivo (1T, 2T, 3T, 4T o ANUAL).
        db: Sesión de base de datos asíncrona.

    Returns:
        Diccionario con 'risk_score' (0-100), 'risk_level' ('LOW', 'MEDIUM', 'HIGH'),
        'risk_factors' (lista de irregularidades detectadas) y 'recommendations' operativas.
    """
    comp = await db.get(Company, company_id)
    if not comp:
        raise ValueError(f"No se encontró la empresa con ID: {company_id}")

    # Determinar meses del periodo
    period_upper = str(period).upper().strip()
    if period_upper == "1T":
        months = [1, 2, 3]
    elif period_upper == "2T":
        months = [4, 5, 6]
    elif period_upper == "3T":
        months = [7, 8, 9]
    elif period_upper == "4T":
        months = [10, 11, 12]
    else:
        months = list(range(1, 13))

    # 1. Recuperar facturas de compras del periodo
    purch_stmt = select(Invoice).where(
        Invoice.company_id == str(company_id),
        extract("year", Invoice.issue_date) == year,
        extract("month", Invoice.issue_date).in_(months),
        Invoice.is_processed == True
    )
    purch_res = await db.execute(purch_stmt)
    purchase_invoices = purch_res.scalars().all()

    # 2. Recuperar facturas de ventas emitidas del periodo
    sales_stmt = select(SalesInvoice).where(
        SalesInvoice.company_id == str(company_id),
        extract("year", SalesInvoice.issue_date) == year,
        extract("month", SalesInvoice.issue_date).in_(months)
    )
    sales_res = await db.execute(sales_stmt)
    sales_invoices = sales_res.scalars().all()

    total_sales_base = sum(float(s.total_base or 0.0) for s in sales_invoices)
    total_sales_tax = sum(float(s.total_tax or 0.0) for s in sales_invoices)
    total_purch_base = sum(float(p.total_base or 0.0) for p in purchase_invoices)
    total_purch_tax = sum(float(p.total_tax or 0.0) for p in purchase_invoices)

    risk_factors: List[Dict[str, Any]] = []
    penalty_points = 0

    # -------------------------------------------------------------
    # CONTROL 1: Ratio de Gastos vs Ingresos (Anomalía de pérdidas)
    # -------------------------------------------------------------
    if total_sales_base > 0:
        expense_ratio = total_purch_base / total_sales_base
        if expense_ratio > 1.30:
            penalty = 25
            penalty_points += penalty
            risk_factors.append({
                "code": "EXPENSE_REVENUE_RATIO_EXCESSIVE",
                "severity": "HIGH",
                "penalty": penalty,
                "title": "Ratio de gastos sobre ingresos desproporcionado (> 130%)",
                "description": f"Los gastos del periodo ({total_purch_base:.2f} €) superan ampliamente a los ingresos ({total_sales_base:.2f} €), arrojando ratio de {expense_ratio:.2f}.",
                "recommendation": "Verificar si existen gastos no afectos a la actividad o inversiones amortizables indebidamente registradas como gasto corriente."
            })
    elif total_purch_base > 5000:
        penalty = 20
        penalty_points += penalty
        risk_factors.append({
            "code": "ZERO_SALES_SIGNIFICANT_EXPENSES",
            "severity": "MEDIUM",
            "penalty": penalty,
            "title": "Gastos significativos sin actividad de ventas declarada",
            "description": f"Se han contabilizado {total_purch_base:.2f} € de gastos sin reflejar ninguna venta en el trimestre.",
            "recommendation": "Comprobar si la empresa está en fase inicial de establecimiento o si faltan facturas de venta por emitir."
        })

    # -------------------------------------------------------------
    # CONTROL 2: Facturas simplificadas (Tickets sin NIF identificado)
    # -------------------------------------------------------------
    simplified_tickets_amount = 0.0
    simplified_tickets_count = 0
    for p in purchase_invoices:
        cif = (p.issuer_cif or "").upper().strip()
        # Si no tiene CIF o es un identificador provisional
        if not cif or cif.startswith("TICKET") or len(cif) < 5:
            simplified_tickets_amount += float(p.total_amount or 0.0)
            simplified_tickets_count += 1

    if simplified_tickets_amount > 3000.0:
        penalty = 30
        penalty_points += penalty
        risk_factors.append({
            "code": "SIMPLIFIED_INVOICES_LIMIT_EXCEEDED",
            "severity": "HIGH",
            "penalty": penalty,
            "title": "Volumen de tickets sin NIF superior al límite del RD 1619/2012",
            "description": f"Suma de facturas simplificadas de {simplified_tickets_amount:.2f} € en {simplified_tickets_count} tickets supera el umbral máximo de 3.000 €.",
            "recommendation": "Solicitar factura completa nominativa con NIF a los proveedores para no perder la deducibilidad en IVA/IRPF."
        })
    elif simplified_tickets_amount > 400.0:
        penalty = 10
        penalty_points += penalty
        risk_factors.append({
            "code": "SIMPLIFIED_INVOICES_WARNING",
            "severity": "LOW",
            "penalty": penalty,
            "title": "Gasto relevante en tickets no nominativos",
            "description": f"Se registran {simplified_tickets_amount:.2f} € en facturas simplificadas.",
            "recommendation": "Priorizar facturas completas con desglose identificativo del receptor."
        })

    # -------------------------------------------------------------
    # CONTROL 3: Desviación de IVA deducible vs Devengado
    # -------------------------------------------------------------
    if total_purch_tax > total_sales_tax and total_sales_tax > 0:
        excess_tax = total_purch_tax - total_sales_tax
        if excess_tax > 2000.0:
            penalty = 15
            penalty_points += penalty
            risk_factors.append({
                "code": "NEGATIVE_VAT_POSITION",
                "severity": "MEDIUM",
                "penalty": penalty,
                "title": "Autoliquidación con saldo a compensar/devolver elevado en IVA",
                "description": f"El IVA deducible ({total_purch_tax:.2f} €) excede al devengado ({total_sales_tax:.2f} €) en {excess_tax:.2f} €.",
                "recommendation": "La solicitud de devolución o compensación sistemática activa requerimientos preventivos de los libros registro de IVA."
            })

    # -------------------------------------------------------------
    # CONTROL 4: Retenciones de profesionales aplicadas a Sociedades (CIF A/B)
    # -------------------------------------------------------------
    corporate_retentions = []
    for p in purchase_invoices:
        ret_val = float(p.total_retention or 0.0)
        cif = (p.issuer_cif or "").upper().strip()
        if ret_val > 0 and cif:
            # En España, las letras A, B, C, D, E, F, G, J son personas jurídicas
            if re.match(r"^[A-HJ]", cif):
                corporate_retentions.append({
                    "invoice_number": p.invoice_number,
                    "cif": cif,
                    "issuer_name": p.issuer_name,
                    "retention_amount": ret_val,
                })

    if corporate_retentions:
        penalty = 25
        penalty_points += penalty
        risk_factors.append({
            "code": "CORPORATE_ENTITY_IRPF_RETENTION_DETECTED",
            "severity": "HIGH",
            "penalty": penalty,
            "title": "Retención de IRPF aplicada erróneamente a Persona Jurídica (Sociedad)",
            "description": f"Se han detectado {len(corporate_retentions)} facturas de sociedades (SL/SA) con retención de profesional, la cual solo es jurídicamente aplicable a personas físicas (autónomos).",
            "affected_invoices": corporate_retentions,
            "recommendation": "Corregir inmediatamente estas facturas eliminando la retención indebida antes de emitir el Modelo 111 oficial."
        })

    # Puntuación final de riesgo (0 = impecable, 100 = riesgo crítico)
    final_score = min(100, penalty_points)
    if final_score < 25:
        risk_level = "LOW"
    elif final_score < 60:
        risk_level = "MEDIUM"
    else:
        risk_level = "HIGH"

    return {
        "company_id": str(company_id),
        "cif": comp.cif,
        "razon_social": comp.razon_social,
        "year": year,
        "period": period_upper,
        "risk_score": final_score,
        "risk_level": risk_level,
        "financial_snapshot": {
            "sales_base": round(total_sales_base, 2),
            "sales_tax": round(total_sales_tax, 2),
            "purchases_base": round(total_purch_base, 2),
            "purchases_tax": round(total_purch_tax, 2),
            "simplified_tickets_total": round(simplified_tickets_amount, 2),
        },
        "total_risk_factors": len(risk_factors),
        "risk_factors": risk_factors,
        "is_safe_for_official_filing": risk_level == "LOW",
    }
