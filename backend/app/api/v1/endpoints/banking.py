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
from fastapi import APIRouter, Depends, HTTPException, Query, Body, status, UploadFile, File, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.core.iban_security import mask_iban, validate_iban
from app.core.norma43_parser import parse_norma43, Norma43File
from app.core.file_inspector import sanitize_filename
from app.core.audit_logger import log_security_event
from app.services.banking_psd2_service import (
    GoCardlessPSD2Client,
    normalize_psd2_transaction,
    PSD2IntegrationError,
)
from app.core.sepa_generator import (
    generate_sepa_direct_debit_xml,
    generate_sepa_credit_transfer_xml,
    SEPAGeneratorError,
)

gocardless_client = GoCardlessPSD2Client()
from app.models.company import Company
from app.models.invoice import Invoice
from app.models.sales_invoice import SalesInvoice
from app.models.accounting_entry import AccountingEntryLine
from app.services.treasury_forecast_service import calculate_treasury_forecast, TreasuryForecastReport
from app.services.bank_reconciliation import (
    match_bank_transactions,
    build_bank_entry,
    suggest_account_by_concept,
)

router = APIRouter()

# Directorio de persistencia para transacciones bancarias
BANKING_DIR = os.path.join(settings.STORAGE_DIR, "banking")
os.makedirs(BANKING_DIR, exist_ok=True)


class BankAccountLinkRequest(BaseModel):
    iban: str = Field(..., description="Código IBAN de la cuenta bancaria")
    bank_name: Optional[str] = Field(None, description="Nombre de la entidad bancaria")
    subcuenta: Optional[str] = Field("57200000", description="Subcuenta contable PGC")
    alias: Optional[str] = Field(None, description="Alias descriptivo")


class BankAccountResponse(BaseModel):
    id: str
    iban: str
    bank_name: Optional[str] = None
    subcuenta: Optional[str] = "57200000"
    alias: Optional[str] = None
    created_at: Optional[str] = None


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


def _get_company_accounts_path(company_id: str) -> str:
    return os.path.join(BANKING_DIR, f"{company_id}_accounts.json")


def _load_bank_accounts(company_id: str) -> List[Dict[str, Any]]:
    path = _get_company_accounts_path(company_id)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return [
        {
            "id": f"acc-{company_id[:8]}",
            "iban": "ES9121000418450200051332",
            "bank_name": "CaixaBank - Cuenta Operativa",
            "subcuenta": "57200000",
            "alias": "Cuenta Principal",
            "created_at": datetime.now().isoformat(),
        }
    ]


def _save_bank_accounts(company_id: str, accounts: List[Dict[str, Any]]) -> None:
    path = _get_company_accounts_path(company_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(accounts, f, ensure_ascii=False, indent=2)


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


@router.get("/{company_id}/bank-accounts", response_model=List[BankAccountResponse])
async def list_bank_accounts(
    company_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Lista las cuentas bancarias de la empresa aplicando enmascaramiento oficial de IBAN
    para asegurar que las cuentas nunca viajen en texto plano completo al frontend.
    """
    comp = await db.get(Company, company_id)
    if not comp:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    raw_accounts = _load_bank_accounts(company_id)
    masked_accounts = []
    for acc in raw_accounts:
        masked_acc = dict(acc)
        raw_iban = acc.get("iban") or acc.get("raw_iban") or ""
        masked_acc["iban"] = mask_iban(raw_iban)
        masked_accounts.append(masked_acc)

    return masked_accounts


@router.post("/{company_id}/bank-accounts", response_model=BankAccountResponse, status_code=status.HTTP_201_CREATED)
async def link_bank_account(
    company_id: str,
    payload: BankAccountLinkRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Crea o vincula manualmente una cuenta bancaria tras validar rigurosamente
    el IBAN conforme al algoritmo oficial ISO 13616 / MOD-97.
    """
    comp = await db.get(Company, company_id)
    if not comp:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    if not validate_iban(payload.iban):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El IBAN introducido no es válido conforme al algoritmo oficial ISO 13616."
        )

    clean_iban = payload.iban.strip().upper()
    accounts = _load_bank_accounts(company_id)

    # Si ya existía, retornar con IBAN enmascarado
    existing = next((a for a in accounts if (a.get("iban") == clean_iban or a.get("raw_iban") == clean_iban)), None)
    if existing:
        return BankAccountResponse(
            id=existing.get("id"),
            iban=mask_iban(clean_iban),
            bank_name=existing.get("bank_name"),
            subcuenta=existing.get("subcuenta"),
            alias=existing.get("alias"),
            created_at=existing.get("created_at"),
        )

    new_acc = {
        "id": f"acc-{uuid.uuid4().hex[:8]}",
        "iban": clean_iban,
        "raw_iban": clean_iban,
        "bank_name": payload.bank_name or "Cuenta Bancaria",
        "subcuenta": payload.subcuenta or "57200000",
        "alias": payload.alias,
        "created_at": datetime.now().isoformat(),
    }
    accounts.append(new_acc)
    _save_bank_accounts(company_id, accounts)

    return BankAccountResponse(
        id=new_acc["id"],
        iban=mask_iban(clean_iban),
        bank_name=new_acc["bank_name"],
        subcuenta=new_acc["subcuenta"],
        alias=new_acc["alias"],
        created_at=new_acc["created_at"],
    )


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

    # Aplicar enmascaramiento de seguridad en los movimientos bancarios
    for t in all_output:
        if t.get("iban"):
            t["iban"] = mask_iban(t["iban"])
        if t.get("bank_account_iban"):
            t["bank_account_iban"] = mask_iban(t["bank_account_iban"])
        if t.get("account_iban"):
            t["account_iban"] = mask_iban(t["account_iban"])

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


@router.post("/{company_id}/upload-norma43")
async def upload_norma43_statement(
    company_id: str,
    file: UploadFile = File(...),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Importa y procesa un archivo de extracto bancario oficial en formato Norma 43 (CSB 43 / AEB).
    - Extrae cuentas bancarias (calculando IBAN oficial).
    - Registra transacciones con descripciones complementarias multilínea.
    - Audita cuadre matemático (Saldo Inicial + Haberes - Debes == Saldo Final).
    - Registra la trazabilidad de la importación en auditoría de seguridad RGPD.
    """
    comp = await db.get(Company, company_id)
    if not comp:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    safe_filename = sanitize_filename(file.filename or "extracto.csb43")
    file_bytes = await file.read()

    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo proporcionado está vacío."
        )

    # 1. Parsear el archivo Norma 43
    try:
        parsed_file = parse_norma43(file_bytes)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al analizar el archivo Norma 43: {str(exc)}"
        )

    if parsed_file.total_accounts == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo no contiene registros válidos de Norma 43 (CSB 43) o no se reconocen cabeceras de cuenta."
        )

    # 2. Persistir cuentas bancarias y transacciones para la empresa
    existing_accounts = _load_bank_accounts(company_id)
    existing_ibans = {acc.get("iban") for acc in existing_accounts if acc.get("iban")}
    existing_txs = _load_transactions(company_id)

    accounts_summary = []
    total_new_transactions = 0

    for acc in parsed_file.accounts:
        # Si la cuenta no existe en la empresa, crearla
        if acc.iban not in existing_ibans:
            new_acc_id = f"acc-{uuid.uuid4().hex[:8]}"
            bank_title = acc.account_name or f"Entidad {acc.bank_code} - Suc. {acc.branch_code}"
            account_record = {
                "id": new_acc_id,
                "iban": acc.iban,
                "bank_name": bank_title,
                "subcuenta": "57200000",
                "alias": acc.account_name or f"Cuenta ...{acc.iban[-4:]}",
                "created_at": datetime.now().isoformat(),
            }
            existing_accounts.append(account_record)
            existing_ibans.add(acc.iban)

        # Registrar transacciones
        acc_txs_count = 0
        for tx in acc.transactions:
            tx_id = f"tx-n43-{uuid.uuid4().hex[:8]}"
            tx_dict = {
                "id": tx_id,
                "account_iban": acc.iban,
                "date": tx.operation_date.isoformat(),
                "value_date": tx.value_date.isoformat(),
                "amount": tx.balance_impact,  # Negativo para DEBE (salida), Positivo para HABER (ingreso)
                "entry_type": tx.entry_type,
                "description": tx.description,
                "document_number": tx.document_number,
                "reference_1": tx.reference_1,
                "reference_2": tx.reference_2,
                "status": "PENDIENTE",
                "currency": acc.currency,
                "source": "NORMA43",
                "created_at": datetime.now().isoformat(),
            }
            existing_txs.append(tx_dict)
            acc_txs_count += 1
            total_new_transactions += 1

        accounts_summary.append({
            "iban_masked": mask_iban(acc.iban),
            "bank_code": acc.bank_code,
            "branch_code": acc.branch_code,
            "currency": acc.currency,
            "initial_balance": acc.initial_balance,
            "final_balance": acc.final_balance,
            "is_balanced": acc.is_balanced,
            "balance_difference": acc.balance_difference,
            "transactions_imported": acc_txs_count,
        })

    # Guardar cambios en el almacenamiento
    _save_bank_accounts(company_id, existing_accounts)
    _save_transactions(company_id, existing_txs)

    # 3. Trazabilidad RGPD y auditoría inmutable
    log_security_event(
        action="NORMA43_IMPORT",
        resource_id=f"N43_{safe_filename}",
        request=request,
        empresa_id=str(company_id),
        status="SUCCESS",
        details={
            "filename": safe_filename,
            "total_accounts": parsed_file.total_accounts,
            "total_transactions": total_new_transactions,
            "is_valid": parsed_file.is_valid,
            "warnings_count": len(parsed_file.validation_warnings),
        }
    )

    return {
        "success": True,
        "message": f"Extracto Norma 43 procesado: {total_new_transactions} transacciones importadas en {parsed_file.total_accounts} cuenta(s).",
        "filename": safe_filename,
        "total_accounts": parsed_file.total_accounts,
        "total_transactions": total_new_transactions,
        "is_balanced": parsed_file.is_valid,
        "validation_warnings": parsed_file.validation_warnings,
        "accounts": accounts_summary,
    }


class PSD2ConnectRequest(BaseModel):
    institution_id: str = Field(..., description="ID de la entidad financiera en GoCardless (ej. SANTANDER_ES_...)")
    redirect_uri: str = Field(..., description="URI de retorno del frontend tras la autorización bancaria")


class PSD2SyncRequest(BaseModel):
    requisition_id: str = Field(..., description="ID de la requisition vinculada tras el consentimiento")


@router.get("/{company_id}/banking/institutions")
async def list_psd2_institutions(
    company_id: str,
    country: str = Query("ES", description="Código ISO de país (ej. ES)"),
    db: AsyncSession = Depends(get_db),
):
    """Consulta el catálogo oficial de entidades bancarias compatibles bajo PSD2 (España)."""
    comp = await db.get(Company, company_id)
    if not comp:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    try:
        institutions = await gocardless_client.get_institutions(country=country)
        return {
            "country": country,
            "total": len(institutions),
            "institutions": institutions,
        }
    except PSD2IntegrationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error en la pasarela bancaria PSD2: {exc.message}"
        )


@router.post("/{company_id}/banking/connect")
async def connect_psd2_bank(
    company_id: str,
    payload: PSD2ConnectRequest,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Inicia el flujo de consentimiento bancario seguro (EUA + Requisition).
    Devuelve la URL oficial de redirección (`initiation_url`) al portal del banco.
    """
    comp = await db.get(Company, company_id)
    if not comp:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    ref = f"comp_{company_id[:8]}_{uuid.uuid4().hex[:6]}"

    try:
        res = await gocardless_client.create_requisition(
            institution_id=payload.institution_id,
            redirect_uri=payload.redirect_uri,
            reference=ref,
            max_historical_days=90,
        )
    except PSD2IntegrationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error al iniciar el enlace de autorización bancaria: {exc.message}"
        )

    log_security_event(
        action="PSD2_CONNECT_INIT",
        resource_id=res.get("requisition_id"),
        request=request,
        empresa_id=str(company_id),
        status="SUCCESS",
        details={
            "institution_id": payload.institution_id,
            "reference": ref,
        }
    )

    return {
        "success": True,
        "initiation_url": res["initiation_url"],
        "requisition_id": res["requisition_id"],
        "reference": ref,
    }


@router.post("/{company_id}/banking/sync")
async def sync_psd2_accounts(
    company_id: str,
    payload: PSD2SyncRequest,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Sincroniza cuentas y movimientos bancarios autorizados mediante PSD2:
    - Recupera cuentas asociadas al consentimiento.
    - Consulta saldos disponibles y contables.
    - Descarga movimientos incrementales y los normaliza para el motor de conciliación.
    - Registra la trazabilidad en auditoría inmutable RGPD.
    """
    comp = await db.get(Company, company_id)
    if not comp:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    try:
        account_ids = await gocardless_client.get_requisition_accounts(payload.requisition_id)
        if not account_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No hay cuentas bancarias autorizadas para la requisition proporcionada o el usuario no completó el acceso."
            )

        existing_accounts = _load_bank_accounts(company_id)
        existing_ibans = {acc.get("iban") for acc in existing_accounts if acc.get("iban")}
        existing_txs = _load_transactions(company_id)
        existing_tx_ids = {tx.get("id") for tx in existing_txs}

        synced_accounts = []
        total_imported_txs = 0

        for acc_id in account_ids:
            details = await gocardless_client.get_account_details(acc_id)
            iban_val = details.get("iban") or f"ES000000{acc_id[:16]}"
            clean_iban = re.sub(r"\s+", "", iban_val.upper())

            # Registrar cuenta si no existía en el almacén de la empresa
            if clean_iban not in existing_ibans:
                acc_record = {
                    "id": f"acc-psd2-{acc_id[:8]}",
                    "iban": clean_iban,
                    "bank_name": details.get("name") or "Cuenta Bancaria PSD2",
                    "subcuenta": "57200000",
                    "alias": details.get("name") or f"Cuenta ...{clean_iban[-4:]}",
                    "created_at": datetime.now().isoformat(),
                }
                existing_accounts.append(acc_record)
                existing_ibans.add(clean_iban)

            # Obtener saldos y movimientos
            balances = await gocardless_client.get_account_balances(acc_id)
            raw_txs = await gocardless_client.get_account_transactions(acc_id)

            acc_imported_count = 0
            for raw_tx in raw_txs:
                normalized = normalize_psd2_transaction(raw_tx, clean_iban)
                if normalized["id"] not in existing_tx_ids:
                    existing_txs.append(normalized)
                    existing_tx_ids.add(normalized["id"])
                    acc_imported_count += 1
                    total_imported_txs += 1

            synced_accounts.append({
                "account_id": acc_id,
                "iban_masked": mask_iban(clean_iban),
                "current_balance": balances.get("current_balance", 0.0),
                "available_balance": balances.get("available_balance", 0.0),
                "currency": details.get("currency", "EUR"),
                "transactions_imported": acc_imported_count,
            })

        _save_bank_accounts(company_id, existing_accounts)
        _save_transactions(company_id, existing_txs)

    except PSD2IntegrationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Fallo durante la sincronización bancaria PSD2: {exc.message}"
        )

    log_security_event(
        action="PSD2_SYNC_SUCCESS",
        resource_id=payload.requisition_id,
        request=request,
        empresa_id=str(company_id),
        status="SUCCESS",
        details={
            "requisition_id": payload.requisition_id,
            "total_accounts": len(synced_accounts),
            "total_transactions": total_imported_txs,
        }
    )

    return {
        "success": True,
        "message": f"Sincronización bancaria completada: {total_imported_txs} movimientos importados en {len(synced_accounts)} cuenta(s).",
        "total_accounts": len(synced_accounts),
        "total_transactions": total_imported_txs,
        "accounts": synced_accounts,
    }


@router.get("/{company_id}/treasury/forecast", response_model=TreasuryForecastReport)
async def get_treasury_forecast(
    company_id: str,
    safety_threshold: float = Query(1000.0, description="Colchón mínimo de seguridad para alertas de liquidez"),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Genera el informe predictivo de tesorería y flujo de caja a 30, 60 y 90 días.
    - Consolida saldo bancario actual (apuntes en cuenta 572 y extractos).
    - Cruza facturas de venta pendientes de cobro y de compra pendientes de pago.
    - Proyecta compromisos tributarios trimestrales de la AEAT (IVA 303 e IRPF).
    - Modela gastos fijos recurrentes y evalúa alertas de liquidez y descubiertos.
    """
    comp = await db.get(Company, company_id)
    if not comp:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    # 1. Saldo bancario consolidado actual
    # Consulta el saldo contable en cuentas 572 (Bancos)
    entries_stmt = select(
        func.coalesce(func.sum(AccountingEntryLine.debe - AccountingEntryLine.haber), 0.0)
    ).where(
        AccountingEntryLine.company_id == company_id,
        AccountingEntryLine.subcuenta.like("572%")
    )
    book_balance = float((await db.execute(entries_stmt)).scalar() or 0.0)

    # Consulta el saldo transaccional del almacén bancario
    stored_txs = _load_transactions(company_id)
    tx_balance = sum(t.get("amount", 0.0) for t in stored_txs)

    current_balance = book_balance if book_balance != 0.0 else (tx_balance if tx_balance != 0.0 else 5000.0)

    # 2. Facturas de venta pendientes de cobro (INFLOW)
    sales_stmt = select(SalesInvoice).where(
        SalesInvoice.company_id == company_id,
        SalesInvoice.status.in_(["ISSUED", "SENT", "DRAFT"])
    )
    sales_db = (await db.execute(sales_stmt)).scalars().all()
    sales_data = [
        {
            "id": str(s.id),
            "invoice_number": s.invoice_number,
            "total_amount": float(s.total_amount),
            "due_date": s.due_date.isoformat() if s.due_date else (s.issue_date.isoformat() if s.issue_date else None),
            "customer_name": s.customer_name,
        }
        for s in sales_db
    ]

    # 3. Facturas de compra pendientes de pago (OUTFLOW)
    purch_stmt = select(Invoice).where(
        Invoice.company_id == company_id,
        Invoice.status.in_(["PENDIENTE", "PROCESADA", "ISSUED", "PENDING"]),
        Invoice.is_processed == True
    )
    purch_db = (await db.execute(purch_stmt)).scalars().all()
    purch_data = [
        {
            "id": str(p.id),
            "invoice_number": p.invoice_number or f"FRA-{str(p.id)[:6]}",
            "total_amount": float(p.total_amount),
            "due_date": p.due_date.isoformat() if hasattr(p, "due_date") and p.due_date else (p.issue_date.isoformat() if p.issue_date else None),
            "issuer_name": p.issuer_name,
        }
        for p in purch_db
    ]

    # 4. Estimación de compromisos tributarios trimestrales (IVA e IRPF)
    today = date.today()
    current_q = "4T" if today.month >= 10 else "3T" if today.month >= 7 else "2T" if today.month >= 4 else "1T"

    total_sales_tax = sum(float(s.total_tax) for s in sales_db if hasattr(s, "total_tax"))
    total_purch_tax = sum(float(p.total_tax) for p in purch_db if hasattr(p, "total_tax"))
    net_tax_estimate = max(0.0, round(total_sales_tax - total_purch_tax, 2))
    if net_tax_estimate == 0.0:
        net_tax_estimate = 1200.0  # Estimación base preventiva si no hay histórico

    tax_liabilities = [
        {
            "period": current_q,
            "year": today.year,
            "estimated_amount": net_tax_estimate,
        }
    ]

    # 5. Gastos fijos recurrentes habituales
    recurring_expenses = [
        {"description": "Nóminas y retribuciones", "amount": 2200.0, "day_of_month": 28, "counterparty": "Empleados"},
        {"description": "Seguridad Social (TCs)", "amount": 750.0, "day_of_month": 28, "counterparty": "TGSS"},
        {"description": "Suministros y telecomunicaciones", "amount": 250.0, "day_of_month": 15, "counterparty": "Operadores"},
    ]

    # 6. Invocar motor predictivo
    report = calculate_treasury_forecast(
        current_bank_balance=current_balance,
        sales_invoices=sales_data,
        purchase_invoices=purch_data,
        estimated_tax_liabilities=tax_liabilities,
        recurring_expenses=recurring_expenses,
        minimum_safety_threshold=safety_threshold,
        reference_date=today,
    )

    # 7. Auditoría de seguridad y trazabilidad RGPD
    log_security_event(
        action="TREASURY_FORECAST_VIEW",
        resource_id=f"FORECAST_{company_id}",
        request=request,
        empresa_id=str(company_id),
        status="SUCCESS",
        details={
            "current_balance": report.current_bank_balance,
            "status_30d": report.horizon_30_days.status,
            "status_60d": report.horizon_60_days.status,
            "status_90d": report.horizon_90_days.status,
            "events_count": len(report.events),
        }
    )

    return report


# =============================================================================
# FINTECH SEPA XML ISO 20022 (Norma 19 Direct Debit y Norma 34 Credit Transfer)
# =============================================================================

class SEPADirectDebitItem(BaseModel):
    debtor_name: str = Field(..., description="Nombre o razón social del cliente deudor")
    debtor_iban: str = Field(..., description="IBAN del cliente deudor")
    debtor_bic: Optional[str] = Field(None, description="BIC de la entidad del cliente")
    amount: float = Field(..., description="Importe del adeudo en euros")
    mandate_id: Optional[str] = Field(None, description="Referencia única del mandato SEPA firmado")
    mandate_date: Optional[str] = Field(None, description="Fecha de firma del mandato (YYYY-MM-DD)")
    end_to_end_id: Optional[str] = Field(None, description="Identificador único / Referencia factura")
    concept: Optional[str] = Field(None, description="Concepto del cobro")


class SEPADirectDebitRequest(BaseModel):
    creditor_iban: Optional[str] = Field(None, description="IBAN de abono de la empresa")
    creditor_name: Optional[str] = Field(None, description="Razón social acreedora")
    creditor_id: Optional[str] = Field(None, description="Código de acreedor AT-02 (ej. ES02000B12345678)")
    collection_date: Optional[str] = Field(None, description="Fecha solicitada de cobro (YYYY-MM-DD)")
    is_b2b: bool = Field(False, description="True para adeudos B2B, False para CORE")
    debits: Optional[List[SEPADirectDebitItem]] = Field(None, description="Lista de cobros individuales")


class SEPACreditTransferItem(BaseModel):
    creditor_name: str = Field(..., description="Nombre o razón social del beneficiario")
    creditor_iban: str = Field(..., description="IBAN de destino del beneficiario")
    creditor_bic: Optional[str] = Field(None, description="BIC del banco del beneficiario")
    amount: float = Field(..., description="Importe de la transferencia en euros")
    end_to_end_id: Optional[str] = Field(None, description="Referencia de pago / Nº Factura")
    concept: Optional[str] = Field(None, description="Concepto de la transferencia")


class SEPACreditTransferRequest(BaseModel):
    debtor_iban: Optional[str] = Field(None, description="IBAN de la cuenta de cargo de la empresa")
    debtor_name: Optional[str] = Field(None, description="Razón social ordenante")
    execution_date: Optional[str] = Field(None, description="Fecha solicitada de ejecución bancaria")
    transfers: Optional[List[SEPACreditTransferItem]] = Field(None, description="Lista de transferencias")


@router.post("/{company_id}/sepa/direct-debit-remittance")
async def create_sepa_direct_debit_remittance(
    company_id: str,
    payload: SEPADirectDebitRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Genera una remesa SEPA XML ISO 20022 pain.008.001.02 (Norma 19 - Adeudos Directos)."""
    comp = await db.get(Company, company_id)
    if not comp:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    # Obtener cuenta bancaria activa de la empresa si no se especifica
    creditor_iban = payload.creditor_iban
    if not creditor_iban:
        accounts = _get_bank_accounts(company_id)
        if accounts:
            creditor_iban = accounts[0].get("iban")
    
    if not creditor_iban:
        creditor_iban = "ES9121000418450200051332"  # Fallback simulado para pruebas

    creditor_info = {
        "name": payload.creditor_name or comp.razon_social,
        "iban": creditor_iban,
        "creditor_id": payload.creditor_id or f"ES02000{re.sub(r'[^A-Za-z0-9]', '', comp.cif)}",
        "cif": comp.cif,
    }

    debits_data = []
    if payload.debits:
        for d in payload.debits:
            debits_data.append(d.model_dump())
    else:
        # Recuperar facturas de venta pendientes
        sales_stmt = select(SalesInvoice).where(
            SalesInvoice.company_id == company_id,
            SalesInvoice.payment_status.in_(["PENDING", "UNPAID", "EMITIDA"])
        ).limit(50)
        res_sales = await db.execute(sales_stmt)
        sales_invoices = res_sales.scalars().all()
        for s in sales_invoices:
            debits_data.append({
                "debtor_name": s.client_name or "Cliente",
                "debtor_iban": getattr(s, "client_iban", None) or "ES9121000418450200051332",
                "amount": float(s.total_amount or 0.0),
                "mandate_id": f"MNDT-{s.client_cif or 'CLI'}",
                "mandate_date": "2024-01-01",
                "end_to_end_id": s.invoice_number or str(s.id),
                "concept": f"Cobro Factura {s.invoice_number}",
            })

    if not debits_data:
        raise HTTPException(status_code=400, detail="No hay adeudos para incluir en la remesa de cobro.")

    try:
        xml_content = generate_sepa_direct_debit_xml(
            creditor=creditor_info,
            debits=debits_data,
            collection_date=payload.collection_date,
            is_b2b=payload.is_b2b,
        )
    except SEPAGeneratorError as s_err:
        raise HTTPException(status_code=422, detail=str(s_err))

    log_security_event(
        action="SEPA_DIRECT_DEBIT_REMITTANCE_GENERATED",
        resource_id=f"SEPA_DD_{company_id}",
        request=request,
        empresa_id=str(company_id),
        status="SUCCESS",
        details={"total_debits": len(debits_data), "is_b2b": payload.is_b2b}
    )

    filename = f"sepa_direct_debit_19_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xml"
    return Response(
        content=xml_content,
        media_type="application/xml; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.post("/{company_id}/sepa/credit-transfer-remittance")
async def create_sepa_credit_transfer_remittance(
    company_id: str,
    payload: SEPACreditTransferRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Genera una remesa SEPA XML ISO 20022 pain.001.001.03 (Norma 34 - Pagos a Proveedores y Nóminas)."""
    comp = await db.get(Company, company_id)
    if not comp:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    debtor_iban = payload.debtor_iban
    if not debtor_iban:
        accounts = _get_bank_accounts(company_id)
        if accounts:
            debtor_iban = accounts[0].get("iban")
    if not debtor_iban:
        debtor_iban = "ES9121000418450200051332"

    debtor_info = {
        "name": payload.debtor_name or comp.razon_social,
        "iban": debtor_iban,
    }

    transfers_data = []
    if payload.transfers:
        for t in payload.transfers:
            transfers_data.append(t.model_dump())
    else:
        # Recuperar facturas de compra pendientes de pago
        purch_stmt = select(Invoice).where(
            Invoice.company_id == company_id,
            Invoice.payment_status.in_(["PENDING", "UNPAID"]),
            Invoice.is_processed == True
        ).limit(50)
        res_purch = await db.execute(purch_stmt)
        purch_invoices = res_purch.scalars().all()
        for p in purch_invoices:
            transfers_data.append({
                "creditor_name": p.issuer_name or "Proveedor",
                "creditor_iban": getattr(p, "supplier_iban", None) or "ES9121000418450200051332",
                "amount": float(p.total_amount or 0.0),
                "end_to_end_id": p.invoice_number or str(p.id),
                "concept": f"Pago Factura {p.invoice_number or p.id}",
            })

    if not transfers_data:
        raise HTTPException(status_code=400, detail="No hay pagos para incluir en la remesa de transferencias.")

    try:
        xml_content = generate_sepa_credit_transfer_xml(
            debtor=debtor_info,
            transfers=transfers_data,
            execution_date=payload.execution_date,
        )
    except SEPAGeneratorError as s_err:
        raise HTTPException(status_code=422, detail=str(s_err))

    log_security_event(
        action="SEPA_CREDIT_TRANSFER_REMITTANCE_GENERATED",
        resource_id=f"SEPA_TRF_{company_id}",
        request=request,
        empresa_id=str(company_id),
        status="SUCCESS",
        details={"total_transfers": len(transfers_data)}
    )

    filename = f"sepa_credit_transfer_34_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xml"
    return Response(
        content=xml_content,
        media_type="application/xml; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
