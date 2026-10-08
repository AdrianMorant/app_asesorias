"""
Endpoints de Conciliación Bancaria Inteligente.
Proporciona endpoints para emparejamiento automático con facturas,
previsualización de asientos en partida doble y contabilización en el Libro Diario.
"""

import os
import json
import uuid
from typing import Any, Dict, List, Optional
from datetime import date, datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.models.company import Company
from app.models.invoice import Invoice
from app.models.accounting_entry import AccountingEntryLine
from app.services.bank_reconciliation import (
    match_bank_transactions,
    build_bank_entry,
    suggest_account_by_concept,
)

router = APIRouter()

# Directorio de persistencia para transacciones bancarias
BANKING_DIR = os.path.join(settings.STORAGE_DIR, "banking")
os.makedirs(BANKING_DIR, exist_ok=True)


class PreviewEntryRequest(BaseModel):
    transaction: Dict[str, Any]
    counterpart_account: Optional[str] = None
    bank_account: Optional[str] = "57200000"


class ReconcileRequest(BaseModel):
    counterpart_account: Optional[str] = None
    bank_account: Optional[str] = "57200000"
    concept: Optional[str] = None
    invoice_id: Optional[str] = None


def _get_company_transactions_path(company_id: str) -> str:
    return os.path.join(BANKING_DIR, f"{company_id}_transactions.json")


def _load_transactions(company_id: str) -> List[Dict[str, Any]]:
    path = _get_company_transactions_path(company_id)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def _save_transactions(company_id: str, txs: List[Dict[str, Any]]) -> None:
    path = _get_company_transactions_path(company_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(txs, f, ensure_ascii=False, indent=2)


def _seed_sample_transactions_for_company(company_id: str, invoices: List[Invoice]) -> List[Dict[str, Any]]:
    """Genera un lote inicial de transacciones bancarias realistas si no existen aún."""
    now = date.today()
    txs = []

    # 1. Movimientos derivados de facturas existentes (para generar casos 'PREVALIDADO')
    for idx, inv in enumerate(invoices[:3]):
        inv_date = inv.issue_date or now
        # Simular pago 2 días después de la factura
        tx_date = inv_date + timedelta(days=2)
        txs.append({
            "id": f"tx-inv-{inv.id[:8]}",
            "date": tx_date.isoformat(),
            "amount": -round(float(inv.total_amount), 2),
            "description": f"Transf. Pago Fra. {inv.invoice_number} {inv.issuer_name}",
            "status": "PENDIENTE",
            "currency": "EUR",
        })

    # 2. Movimientos típicos recurrentes (para probar el motor de patrones 'SUGERIDO')
    txs.extend([
        {
            "id": f"tx-tgss-{uuid.uuid4().hex[:6]}",
            "date": (now - timedelta(days=5)).isoformat(),
            "amount": -1450.75,
            "description": "TGSS SEGURIDAD SOCIAL COTIZACIONES REG. GENERAL",
            "status": "PENDIENTE",
            "currency": "EUR",
        },
        {
            "id": f"tx-iber-{uuid.uuid4().hex[:6]}",
            "date": (now - timedelta(days=12)).isoformat(),
            "amount": -320.40,
            "description": "ADEUDO SEPA IBERDROLA CLIENTES S.A.U.",
            "status": "PENDIENTE",
            "currency": "EUR",
        },
        {
            "id": f"tx-comis-{uuid.uuid4().hex[:6]}",
            "date": (now - timedelta(days=1)).isoformat(),
            "amount": -25.00,
            "description": "COMISION MANTENIMIENTO Y GASTOS CUENTA TRIMESTRAL",
            "status": "PENDIENTE",
            "currency": "EUR",
        },
        {
            "id": f"tx-unmatched-{uuid.uuid4().hex[:6]}",
            "date": (now - timedelta(days=8)).isoformat(),
            "amount": 750.00,
            "description": "TRANSFERENCIA RECIBIDA CLIENTE VARIOS 99823",
            "status": "PENDIENTE",
            "currency": "EUR",
        },
    ])

    _save_transactions(company_id, txs)
    return txs


@router.get("/{company_id}/bank-transactions")
async def get_bank_transactions(
    company_id: str,
    date_margin_days: int = Query(5, description="Margen en días para coincidencia con facturas"),
    db: AsyncSession = Depends(get_db),
):
    """
    Lista las transacciones bancarias de la empresa y ejecuta match_bank_transactions
    para devolverlas con su estado ('PREVALIDADO', 'SUGERIDO', 'PENDIENTE') y su propuesta de contrapartida.
    """
    comp = await db.get(Company, company_id)
    if not comp:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    # Recuperar facturas aprobadas de la empresa
    stmt = (
        select(Invoice)
        .options(
            selectinload(Invoice.accounting_entries),
            selectinload(Invoice.tax_breakdown),
        )
        .where(
            Invoice.company_id == company_id,
            (Invoice.is_processed == True) | (Invoice.workflow_status.in_(["validado", "contabilizado"]))
        )
    )
    res = await db.execute(stmt)
    invoices = res.scalars().all()

    # Cargar transacciones persistidas o inicializarlas
    txs = _load_transactions(company_id)
    if not txs:
        txs = _seed_sample_transactions_for_company(company_id, invoices)

    # Filtrar aquellas que no estén ya conciliadas para emparejamiento dinámico
    pending_or_suggested_txs = [t for t in txs if t.get("status") != "CONCILIADO"]
    reconciled_txs = [t for t in txs if t.get("status") == "CONCILIADO"]

    matched_results = match_bank_transactions(
        transactions=pending_or_suggested_txs,
        invoices=invoices,
        date_margin_days=date_margin_days,
        account_digits=comp.plan_cuentas_longitud or 9,
    )

    # Combinar resultados conservando las ya conciliadas
    all_output = matched_results + reconciled_txs

    return {
        "company_id": company_id,
        "total_count": len(all_output),
        "prevalidated_count": sum(1 for t in all_output if t.get("status") == "PREVALIDADO"),
        "suggested_count": sum(1 for t in all_output if t.get("status") == "SUGERIDO"),
        "pending_count": sum(1 for t in all_output if t.get("status") == "PENDIENTE"),
        "reconciled_count": sum(1 for t in all_output if t.get("status") == "CONCILIADO"),
        "transactions": all_output,
    }


@router.post("/{company_id}/bank-transactions/preview-entry")
async def preview_bank_entry(
    company_id: str,
    payload: PreviewEntryRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Recibe los datos de una transacción (y una subcuenta opcional si el usuario la modificó)
    y llama a build_bank_entry para devolver el asiento contable en partida doble (Debe/Haber contra 572).
    """
    comp = await db.get(Company, company_id)
    if not comp:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    tx_data = payload.transaction
    if payload.counterpart_account:
        tx_data["counterpart_account"] = payload.counterpart_account

    entry = build_bank_entry(
        transaction=tx_data,
        account_number=payload.bank_account or "57200000",
        account_digits=comp.plan_cuentas_longitud or 9,
    )

    return entry


@router.post("/{company_id}/bank-transactions/{transaction_id}/reconcile")
async def reconcile_bank_transaction(
    company_id: str,
    transaction_id: str,
    payload: ReconcileRequest = Body(default_factory=ReconcileRequest),
    db: AsyncSession = Depends(get_db),
):
    """
    Confirma la conciliación bancaria:
    1. Genera el asiento contable oficial en partida doble (Debe/Haber contra 572).
    2. Guarda las líneas de apunte en el Libro Diario (AccountingEntryLine).
    3. Actualiza el estado de la transacción a 'CONCILIADO'.
    """
    comp = await db.get(Company, company_id)
    if not comp:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    txs = _load_transactions(company_id)
    target_tx = next((t for t in txs if t.get("id") == transaction_id), None)

    if not target_tx:
        # Si no está en el almacén local, construirlo desde el payload
        target_tx = {
            "id": transaction_id,
            "date": date.today().isoformat(),
            "amount": 0.0,
            "description": payload.concept or "Movimiento bancario",
            "status": "PENDIENTE",
        }
        txs.append(target_tx)

    # Actualizar datos con el payload si se proporcionaron
    if payload.counterpart_account:
        target_tx["counterpart_account"] = payload.counterpart_account
    if payload.concept:
        target_tx["suggested_concept"] = payload.concept
    if payload.invoice_id:
        target_tx["invoice_id"] = payload.invoice_id

    # 1. Obtener el siguiente número de asiento contable correlativo en el Diario
    max_entry_stmt = select(func.max(AccountingEntryLine.entry_number)).where(
        AccountingEntryLine.company_id == company_id
    )
    max_res = await db.execute(max_entry_stmt)
    current_max = max_res.scalar_one_or_none() or 0
    next_entry_number = current_max + 1

    # 2. Construir el asiento de banco
    entry_dict = build_bank_entry(
        transaction=target_tx,
        account_number=payload.bank_account or "57200000",
        account_digits=comp.plan_cuentas_longitud or 9,
        entry_number=next_entry_number,
    )

    tx_date_obj = date.today()
    if target_tx.get("date"):
        try:
            tx_date_obj = datetime.fromisoformat(target_tx["date"][:10]).date()
        except Exception:
            pass

    # 3. Guardar las líneas en AccountingEntryLine
    created_lines = []
    for line in entry_dict["lines"]:
        db_line = AccountingEntryLine(
            company_id=company_id,
            invoice_id=payload.invoice_id or target_tx.get("invoice_id"),
            entry_number=next_entry_number,
            fecha=tx_date_obj,
            subcuenta=line["subcuenta"],
            concepto=line["concepto"],
            debe=line["debe"],
            haber=line["haber"],
            documento=line["documento"],
            exported_to_erp=False,
        )
        db.add(db_line)
        created_lines.append(db_line)

    await db.commit()

    # 4. Actualizar el estado de la transacción a 'CONCILIADO'
    target_tx["status"] = "CONCILIADO"
    target_tx["reconciled_at"] = datetime.now().isoformat()
    target_tx["entry_number"] = next_entry_number
    _save_transactions(company_id, txs)

    return {
        "success": True,
        "message": f"Transacción {transaction_id} conciliada con éxito. Asiento #{next_entry_number} registrado en el Libro Diario.",
        "entry_number": next_entry_number,
        "entry": entry_dict,
        "transaction": target_tx,
    }
