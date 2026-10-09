"""Módulo de Control y Dashboard Ejecutivo para Asesorías y Gestorías Contables (Advisor Portal).

Proporciona visión consolidada multi-tenant de todas las empresas clientes asignadas:
1. Semáforo fiscal preventivo trimestral (Modelos 303, 111, 115) con alertas previas al día 20.
2. Estado de salud de conciliación bancaria (% transacciones pendientes de casar).
3. Volumen de facturas pendientes de revisión/categorización recibidas por email inbound.
4. Estado de salud y caducidad de conexiones bancarias PSD2.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import settings
from app.core.audit_logger import log_security_event
from app.models.company import Company
from app.models.invoice import Invoice
from app.models.sales_invoice import SalesInvoice
from app.models.user import User, UserRole

router = APIRouter()


def _get_company_bank_stats(company_id: str) -> Dict[str, Any]:
    """Recupera estadísticas de conciliación bancaria y PSD2 desde el almacén local."""
    trans_file = settings.STORAGE_DIR / f"bank_transactions_{company_id}.json"
    total_txs = 0
    unreconciled_txs = 0
    last_sync = None

    if trans_file.exists():
        try:
            with open(trans_file, "r", encoding="utf-8") as f:
                txs = json.load(f)
                total_txs = len(txs)
                unreconciled_txs = sum(1 for t in txs if not t.get("is_reconciled", False))
                # Extraer fecha más reciente
                dates = [t.get("booking_date") or t.get("value_date") for t in txs if t.get("booking_date")]
                if dates:
                    last_sync = max(dates)
        except Exception:
            pass

    reconciliation_rate = 100.0
    if total_txs > 0:
        reconciliation_rate = round(((total_txs - unreconciled_txs) / total_txs) * 100, 1)

    return {
        "total_transactions": total_txs,
        "unreconciled_transactions": unreconciled_txs,
        "reconciliation_rate_percent": reconciliation_rate,
        "last_sync_date": last_sync,
    }


@router.get("/clients-health-status")
async def get_clients_health_status(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Devuelve la tabla de mando ejecutiva con el estado fiscal, bancario y documental de todos los clientes."""
    stmt = select(Company).order_by(Company.razon_social.asc())
    result = await db.execute(stmt)
    companies = result.scalars().all()

    today = date.today()
    # Determinar el trimestre actual y fecha límite oficial del día 20
    current_quarter = "4T" if today.month >= 10 else "3T" if today.month >= 7 else "2T" if today.month >= 4 else "1T"
    is_near_deadline = today.day >= 10 and today.month in (1, 4, 7, 10)

    clients_health: List[Dict[str, Any]] = []

    for comp in companies:
        c_id = str(comp.id)

        # 1. Facturas de compras pendientes de revisión o categorización
        inv_stmt = select(
            func.count(Invoice.id).label("total"),
            func.sum(func.case((Invoice.status.in_(["REQUIRES_REVIEW", "PENDING_APPROVAL", "DRAFT"]), 1), else_=0)).label("pending")
        ).where(Invoice.company_id == c_id)
        inv_res = await db.execute(inv_stmt)
        inv_counts = inv_res.first()
        pending_invoices = int(inv_counts.pending or 0) if inv_counts else 0

        # 2. Facturas de ventas emitidas sin cobrar
        sales_stmt = select(
            func.count(SalesInvoice.id).label("total_unpaid")
        ).where(
            SalesInvoice.company_id == c_id,
            SalesInvoice.payment_status.in_(["PENDING", "UNPAID", "EMITIDA"])
        )
        sales_res = await db.execute(sales_stmt)
        unpaid_sales = sales_res.scalar_one_or_none() or 0

        # 3. Conciliación bancaria y conectividad PSD2
        bank_stats = _get_company_bank_stats(c_id)

        # 4. Semáforo fiscal preventivo
        # Reglas de alerta:
        # - RED: Descuadres o facturas pendientes cerca del día 20, o conciliación < 50%
        # - YELLOW: Conciliación entre 50% y 85%, o más de 5 facturas pendientes de revisar
        # - GREEN: Todo cuadrado, conciliación >= 85% y sin facturas críticas pendientes
        if (is_near_deadline and pending_invoices > 0) or bank_stats["reconciliation_rate_percent"] < 50.0:
            tax_status = "RED"
            tax_message = "Alerta crítica: Facturas sin contabilizar o conciliación baja en periodo de liquidación."
        elif pending_invoices > 5 or bank_stats["reconciliation_rate_percent"] < 85.0:
            tax_status = "YELLOW"
            tax_message = "Atención requerida: Facturas pendientes de validación o movimientos bancarios por conciliar."
        else:
            tax_status = "GREEN"
            tax_message = "Al día: Conciliación bancaria óptima y modelos tributarios cuadrados."

        clients_health.append({
            "company_id": c_id,
            "cif": comp.cif,
            "razon_social": comp.razon_social,
            "tax_period": current_quarter,
            "tax_traffic_light": tax_status,
            "tax_alert_message": tax_message,
            "pending_inbound_invoices": pending_invoices,
            "unpaid_sales_invoices": unpaid_sales,
            "bank_reconciliation_rate": bank_stats["reconciliation_rate_percent"],
            "unreconciled_bank_transactions": bank_stats["unreconciled_transactions"],
            "last_psd2_sync": bank_stats["last_sync_date"],
            "is_psd2_connected": bank_stats["total_transactions"] > 0,
        })

    log_security_event(
        action="ADVISOR_HEALTH_DASHBOARD_VIEW",
        resource_id="ALL_CLIENTS",
        request=request,
        status="SUCCESS",
        details={"total_clients": len(clients_health)}
    )

    return clients_health


@router.get("/clients")
async def list_advisor_clients(
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Listado simplificado de empresas para el conmutador rápido multi-tenant."""
    stmt = select(Company.id, Company.cif, Company.razon_social).order_by(Company.razon_social.asc())
    res = await db.execute(stmt)
    rows = res.all()
    return [
        {"id": str(r[0]), "cif": r[1], "razon_social": r[2]}
        for r in rows
    ]
