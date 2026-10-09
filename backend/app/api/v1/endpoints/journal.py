from typing import List, Optional, Dict, Any
from datetime import date, datetime
import io
import csv
from fastapi import APIRouter, Depends, HTTPException, Query, Response, Body, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func, or_, and_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.company import Company
from app.models.invoice import Invoice
from app.models.sales_invoice import SalesInvoice
from app.models.accounting_entry import AccountingEntryLine
from app.models.account import Account
from app.core.audit_logger import log_security_event
from app.services.nif_validator import normalize_nif
from app.core.auth_deps import get_current_user_optional
from app.models.user import User, UserRole
from fastapi import Request

router = APIRouter()

# Grupos maestros oficiales del PGC español (RD 1514/2007 y RD 1515/2007)
PGC_GRUPOS_NOMBRES = {
    "1": "Grupo 1: Financiación Básica",
    "2": "Grupo 2: Inmovilizado / Activo No Corriente",
    "3": "Grupo 3: Existencias",
    "4": "Grupo 4: Acreedores y Deudores por Operaciones Comerciales",
    "5": "Grupo 5: Cuentas Financieras",
    "6": "Grupo 6: Compras y Gastos",
    "7": "Grupo 7: Ventas e Ingresos",
}

# ---------------------------------------------------------------------------
# ESQUEMAS DTO
# ---------------------------------------------------------------------------
class ReverseEntryRequest(BaseModel):
    reason: str = Field(..., min_length=5, description="Motivo auditable de la reversión contable")
    reversal_date: Optional[date] = Field(None, description="Fecha del apunte de reversión (por defecto hoy)")

class CloseFiscalYearRequest(BaseModel):
    year: int = Field(..., ge=2000, le=2100, description="Ejercicio fiscal a regularizar y cerrar")
    closing_date: Optional[date] = Field(None, description="Fecha de cierre contable (por defecto 31 de diciembre del año)")

class ReopenFiscalYearRequest(BaseModel):
    cif_confirmation: str = Field(..., description="CIF de la empresa requerido para autorizar la reapertura del ejercicio")
    new_closing_date: Optional[date] = Field(None, description="Nueva fecha de cierre contable")


# ---------------------------------------------------------------------------
# ENDPOINTS LIBRO DIARIO
# ---------------------------------------------------------------------------
@router.get("/{company_id}/journal")
async def get_journal_entries(
    company_id: str,
    from_date: Optional[date] = Query(None, description="Fecha desde"),
    to_date: Optional[date] = Query(None, description="Fecha hasta"),
    search: Optional[str] = Query(None, description="Filtro por subcuenta, concepto o documento"),
    entry_number: Optional[int] = Query(None, description="Filtrar por número de asiento concreto"),
    subcuenta: Optional[str] = Query(None, description="Filtrar por código de subcuenta específico"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filtrar por estado contable: contabilizado, revertido, borrador"),
    exported_filter: Optional[bool] = Query(None, alias="exported", description="Filtrar por estado de exportación a ERP"),
    fiscal_year: Optional[int] = Query(None, description="Filtrar por ejercicio fiscal (año de la fecha)"),
    page: int = Query(1, ge=1, description="Número de página"),
    page_size: int = Query(50, ge=1, le=200, description="Tamaño de página"),
    db: AsyncSession = Depends(get_db)
):
    """
    Devuelve los asientos contables en partida doble del Libro Diario,
    agrupados por número de asiento y fecha, verificando el cuadre y el estado contable.
    """
    comp = await db.get(Company, company_id)
    if not comp:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    # Recuperar líneas de asientos asociados a esta empresa
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
    if fiscal_year:
        stmt = stmt.where(func.extract('year', AccountingEntryLine.fecha) == fiscal_year)
    if entry_number is not None:
        stmt = stmt.where(AccountingEntryLine.entry_number == entry_number)
    if subcuenta:
        stmt = stmt.where(AccountingEntryLine.subcuenta.startswith(subcuenta.strip()))
    if status_filter:
        stmt = stmt.where(AccountingEntryLine.status == status_filter.strip())
    if exported_filter is not None:
        stmt = stmt.where(AccountingEntryLine.exported_to_erp == exported_filter)
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

    # Cargar metadatos de documentos asociados para trazabilidad
    inv_ids = list({l.invoice_id for l in lines if l.invoice_id})
    sales_ids = list({l.sales_invoice_id for l in lines if l.sales_invoice_id})
    invoices_map = {}
    sales_map = {}

    if inv_ids:
        inv_stmt = select(Invoice).where(Invoice.id.in_(inv_ids))
        invoices_map = {inv.id: inv for inv in (await db.execute(inv_stmt)).scalars().all()}
    if sales_ids:
        sales_stmt = select(SalesInvoice).where(SalesInvoice.id.in_(sales_ids))
        sales_map = {sinv.id: sinv for sinv in (await db.execute(sales_stmt)).scalars().all()}

    # Agrupar por asiento
    entries_map: Dict[str, Dict[str, Any]] = {}
    for line in lines:
        group_key = f"{line.fecha.isoformat()}_{line.entry_number}"
        if group_key not in entries_map:
            # Documento de origen
            doc_id = line.invoice_id or line.sales_invoice_id
            doc_type = "expense" if line.invoice_id else "sales" if line.sales_invoice_id else "manual"
            doc_obj = invoices_map.get(line.invoice_id) or sales_map.get(line.sales_invoice_id)
            doc_file_name = getattr(doc_obj, "file_name", None) if doc_obj else None
            doc_number = getattr(doc_obj, "invoice_number", None) if doc_obj else line.documento

            is_closed = False
            if comp.fecha_cierre_contable and line.fecha <= comp.fecha_cierre_contable:
                is_closed = True

            entries_map[group_key] = {
                "entry_number": line.entry_number,
                "fecha": line.fecha.isoformat(),
                "documento": line.documento or doc_number,
                "document_id": doc_id,
                "document_type": doc_type,
                "document_file_name": doc_file_name,
                "status": getattr(line, "status", "contabilizado"),
                "is_reversal": getattr(line, "is_reversal", False),
                "reversal_of_entry_number": getattr(line, "reversal_of_entry_number", None),
                "created_by": getattr(line, "created_by", "sistema"),
                "is_closed_period": is_closed,
                "exported_to_erp": line.exported_to_erp,
                "export_batch_id": line.export_batch_id,
                "total_debe": 0.0,
                "total_haber": 0.0,
                "is_balanced": True,
                "lines": []
            }
        
        # Si alguna línea del asiento está revertida, el asiento global se refleja como revertido
        if getattr(line, "status", None) == "revertido":
            entries_map[group_key]["status"] = "revertido"

        entries_map[group_key]["total_debe"] += line.debe
        entries_map[group_key]["total_haber"] += line.haber
        entries_map[group_key]["lines"].append({
            "id": line.id,
            "subcuenta": line.subcuenta,
            "concepto": line.concepto,
            "debe": line.debe,
            "haber": line.haber,
            "documento": line.documento,
            "exported_to_erp": line.exported_to_erp,
            "status": getattr(line, "status", "contabilizado")
        })

    # Verificar cuadre y redondear
    all_grouped_entries = list(entries_map.values())
    for e in all_grouped_entries:
        e["total_debe"] = round(e["total_debe"], 2)
        e["total_haber"] = round(e["total_haber"], 2)
        e["is_balanced"] = abs(e["total_debe"] - e["total_haber"]) < 0.01

    # Aplicar paginación sobre los asientos completos
    total_asientos = len(all_grouped_entries)
    total_pages = max(1, (total_asientos + page_size - 1) // page_size)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paged_entries = all_grouped_entries[start_idx:end_idx]

    # Calcular totales agregados de la consulta
    total_general_debe = round(sum(e["total_debe"] for e in all_grouped_entries), 2)
    total_general_haber = round(sum(e["total_haber"] for e in all_grouped_entries), 2)

    return {
        "company_id": company_id,
        "total_asientos": total_asientos,
        "total_apuntes": len(lines),
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "total_general_debe": total_general_debe,
        "total_general_haber": total_general_haber,
        "cuadre_general": abs(total_general_debe - total_general_haber) < 0.01,
        "fecha_cierre_contable": comp.fecha_cierre_contable.isoformat() if comp.fecha_cierre_contable else None,
        "asientos": paged_entries
    }


# ---------------------------------------------------------------------------
# REVERSIÓN AUDITABLE DE ASIENTOS
# ---------------------------------------------------------------------------
@router.post("/{company_id}/journal/{entry_number}/reverse")
async def reverse_journal_entry(
    company_id: str,
    entry_number: int,
    payload: ReverseEntryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
    request: Request = None,
):
    """
    Revierte de forma auditable e inmutable un asiento contable.
    1. Verifica que el asiento exista y pertenezca a la empresa.
    2. Comprueba permisos RBAC (solo Contables, Asesores o Administradores).
    3. Comprueba que el ejercicio contable no esté cerrado.
    4. Impide revertir dos veces el mismo asiento.
    5. Genera un contra-asiento en partida doble (invirtiendo Debe y Haber) con correlativo libre.
    6. Marca las líneas originales como 'revertido' y registra el evento de seguridad.
    """
    if current_user:
        allowed_roles = {
            UserRole.SUPERADMIN.value,
            UserRole.COMPANY_ADMIN.value,
            UserRole.ADVISOR.value,
            UserRole.ACCOUNTANT.value,
        }
        if current_user.global_role not in allowed_roles:
            log_security_event(
                action="JOURNAL_REVERSAL_UNAUTHORIZED",
                empresa_id=company_id,
                request=request,
                user_id=current_user.id,
                status="DENIED",
                details={"role": current_user.global_role, "entry_number": entry_number},
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permisos insuficientes: solo Contables, Asesores o Administradores pueden revertir asientos.",
            )

    comp = await db.get(Company, company_id)
    if not comp:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    # Localizar líneas del asiento
    stmt = (
        select(AccountingEntryLine)
        .outerjoin(Invoice, AccountingEntryLine.invoice_id == Invoice.id)
        .outerjoin(SalesInvoice, AccountingEntryLine.sales_invoice_id == SalesInvoice.id)
        .where(
            AccountingEntryLine.entry_number == entry_number,
            or_(
                AccountingEntryLine.company_id == company_id,
                Invoice.company_id == company_id,
                SalesInvoice.company_id == company_id
            )
        )
    )
    res = await db.execute(stmt)
    lines = res.scalars().all()

    if not lines:
        raise HTTPException(status_code=404, detail=f"No se encontró el asiento #{entry_number} para esta empresa.")

    # Comprobar si ya estaba revertido
    if any(getattr(l, "status", None) == "revertido" for l in lines):
        raise HTTPException(status_code=400, detail=f"El asiento #{entry_number} ya ha sido revertido previamente.")

    # Comprobar si pertenece a un ejercicio cerrado
    asiento_fecha = lines[0].fecha
    rev_date = payload.reversal_date or date.today()

    if comp.fecha_cierre_contable:
        if asiento_fecha <= comp.fecha_cierre_contable:
            raise HTTPException(
                status_code=400,
                detail=f"Bloqueo contable: El asiento #{entry_number} corresponde al ejercicio cerrado a fecha {comp.fecha_cierre_contable.isoformat()}. No se puede revertir directamente."
            )
        if rev_date <= comp.fecha_cierre_contable:
            raise HTTPException(
                status_code=400,
                detail=f"La fecha de reversión ({rev_date.isoformat()}) no puede ser anterior o igual a la fecha de cierre ({comp.fecha_cierre_contable.isoformat()})."
            )

    # Calcular siguiente número de asiento disponible para la empresa
    max_num_stmt = (
        select(func.max(AccountingEntryLine.entry_number))
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
    max_res = await db.execute(max_num_stmt)
    next_entry_num = (max_res.scalar() or 0) + 1

    # Crear contra-apuntes (invirtiendo Debe y Haber)
    reversal_lines = []
    for l in lines:
        rev_line = AccountingEntryLine(
            company_id=company_id,
            invoice_id=l.invoice_id,
            sales_invoice_id=l.sales_invoice_id,
            entry_number=next_entry_num,
            fecha=rev_date,
            subcuenta=l.subcuenta,
            concepto=f"Reversión Asiento #{entry_number}: {payload.reason.strip()}",
            debe=l.haber,  # Inversión de Debe y Haber
            haber=l.debe,
            documento=l.documento,
            status="contabilizado",
            is_reversal=True,
            reversal_of_entry_number=entry_number,
            created_by="usuario_autorizado",
        )
        db.add(rev_line)
        reversal_lines.append(rev_line)

        # Actualizar apunte original a revertido
        l.status = "revertido"

    await db.commit()

    log_security_event(
        action="JOURNAL_ENTRY_REVERSED",
        empresa_id=company_id,
        details={
            "company_id": company_id,
            "original_entry": entry_number,
            "reversal_entry": next_entry_num,
            "reason": payload.reason,
            "lines_count": len(reversal_lines),
        }
    )

    return {
        "success": True,
        "status": "revertido",
        "message": f"Asiento #{entry_number} revertido correctamente mediante el nuevo Asiento #{next_entry_num}.",
        "original_entry_number": entry_number,
        "reversal_entry_number": next_entry_num,
        "reversal_date": rev_date.isoformat(),
        "lines_count": len(reversal_lines),
    }


# ---------------------------------------------------------------------------
# CIERRE Y REGULARIZACIÓN DEL EJERCICIO
# ---------------------------------------------------------------------------
@router.post("/{company_id}/journal/close-fiscal-year")
async def close_fiscal_year(
    company_id: str,
    payload: CloseFiscalYearRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
    request: Request = None,
):
    """
    Ejecuta el cierre contable del ejercicio:
    1. Verifica permisos RBAC (solo Administradores o Asesores).
    2. Calcula el saldo de ingresos (Grupo 7) y gastos (Grupo 6).
    3. Genera el asiento de regularización contable contra la cuenta 129000000 (Resultado del Ejercicio).
    4. Fija la fecha de cierre contable en la empresa para impedir asientos posteriores.
    """
    if current_user:
        allowed_roles = {UserRole.SUPERADMIN.value, UserRole.COMPANY_ADMIN.value, UserRole.ADVISOR.value}
        if current_user.global_role not in allowed_roles:
            log_security_event(
                action="FISCAL_YEAR_CLOSE_UNAUTHORIZED",
                empresa_id=company_id,
                request=request,
                user_id=current_user.id,
                status="DENIED",
                details={"role": current_user.global_role, "year": payload.year},
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permisos insuficientes: solo Administradores o Asesores pueden realizar el cierre del ejercicio contable.",
            )

    comp = await db.get(Company, company_id)
    if not comp:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    closing_date = payload.closing_date or date(payload.year, 12, 31)

    if comp.fecha_cierre_contable and comp.fecha_cierre_contable >= closing_date:
        raise HTTPException(
            status_code=400,
            detail=f"El ejercicio {payload.year} ya se encuentra cerrado (fecha de cierre: {comp.fecha_cierre_contable.isoformat()})."
        )

    # Buscar cuentas de gastos (6) e ingresos (7) con saldo en el año
    start_date = date(payload.year, 1, 1)
    end_date = date(payload.year, 12, 31)

    stmt = (
        select(
            AccountingEntryLine.subcuenta,
            func.sum(AccountingEntryLine.debe).label("total_debe"),
            func.sum(AccountingEntryLine.haber).label("total_haber")
        )
        .outerjoin(Invoice, AccountingEntryLine.invoice_id == Invoice.id)
        .outerjoin(SalesInvoice, AccountingEntryLine.sales_invoice_id == SalesInvoice.id)
        .where(
            or_(
                AccountingEntryLine.company_id == company_id,
                Invoice.company_id == company_id,
                SalesInvoice.company_id == company_id
            ),
            AccountingEntryLine.fecha >= start_date,
            AccountingEntryLine.fecha <= end_date,
            AccountingEntryLine.status != "revertido",
            or_(
                AccountingEntryLine.subcuenta.startswith("6"),
                AccountingEntryLine.subcuenta.startswith("7")
            )
        )
        .group_by(AccountingEntryLine.subcuenta)
    )
    res = await db.execute(stmt)
    rows = res.all()

    # Siguiente número de asiento
    max_num_stmt = (
        select(func.max(AccountingEntryLine.entry_number))
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
    max_res = await db.execute(max_num_stmt)
    next_entry_num = (max_res.scalar() or 0) + 1

    # Crear líneas de saldado
    reg_lines = []
    total_gastos = 0.0
    total_ingresos = 0.0

    account_digits = comp.plan_cuentas_longitud or 9
    cuenta_129 = "129".ljust(account_digits, "0")

    for r in rows:
        subcta = r.subcuenta
        s_debe = r.total_debe or 0.0
        s_haber = r.total_haber or 0.0
        neto = round(s_debe - s_haber, 2)

        if neto > 0:
            # Saldo deudor (gasto): para saldarlo se anota al Haber
            reg_lines.append(
                AccountingEntryLine(
                    company_id=company_id,
                    entry_number=next_entry_num,
                    fecha=closing_date,
                    subcuenta=subcta,
                    concepto=f"Regularización ejercicio {payload.year} - Saldo de cuenta",
                    debe=0.0,
                    haber=neto,
                    status="contabilizado",
                    created_by="cierre_ejercicio",
                )
            )
            total_gastos += neto
        elif neto < 0:
            # Saldo acreedor (ingreso): para saldarlo se anota al Debe
            reg_lines.append(
                AccountingEntryLine(
                    company_id=company_id,
                    entry_number=next_entry_num,
                    fecha=closing_date,
                    subcuenta=subcta,
                    concepto=f"Regularización ejercicio {payload.year} - Saldo de cuenta",
                    debe=abs(neto),
                    haber=0.0,
                    status="contabilizado",
                    created_by="cierre_ejercicio",
                )
            )
            total_ingresos += abs(neto)

    # Línea de contrapartida en la cuenta 129
    resultado_neto = round(total_ingresos - total_gastos, 2)
    if resultado_neto >= 0:
        # Beneficio neto: la 129 recibe al Haber el beneficio
        reg_lines.append(
            AccountingEntryLine(
                company_id=company_id,
                entry_number=next_entry_num,
                fecha=closing_date,
                subcuenta=cuenta_129,
                concepto=f"Regularización {payload.year} - Beneficio del ejercicio",
                debe=0.0,
                haber=resultado_neto,
                status="contabilizado",
                created_by="cierre_ejercicio",
            )
        )
    else:
        # Pérdida neta: la 129 recibe al Debe la pérdida
        reg_lines.append(
            AccountingEntryLine(
                company_id=company_id,
                entry_number=next_entry_num,
                fecha=closing_date,
                subcuenta=cuenta_129,
                concepto=f"Regularización {payload.year} - Pérdidas del ejercicio",
                debe=abs(resultado_neto),
                haber=0.0,
                status="contabilizado",
                created_by="cierre_ejercicio",
            )
        )

    for l in reg_lines:
        db.add(l)

    # Actualizar fecha de cierre en la empresa
    comp.fecha_cierre_contable = closing_date
    await db.commit()

    return {
        "success": True,
        "message": f"Ejercicio {payload.year} regularizado y cerrado con éxito a fecha {closing_date.isoformat()}.",
        "entry_number": next_entry_num,
        "closing_date": closing_date.isoformat(),
        "total_ingresos": round(total_ingresos, 2),
        "total_gastos": round(total_gastos, 2),
        "resultado_neto": resultado_neto,
        "tipo_resultado": "BENEFICIO" if resultado_neto >= 0 else "PÉRDIDA",
        "cuenta_resultado": cuenta_129,
        "lines_generated": len(reg_lines),
    }


# ---------------------------------------------------------------------------
# REAPERTURA DE EJERCICIO
# ---------------------------------------------------------------------------
@router.post("/{company_id}/journal/reopen-fiscal-year")
async def reopen_fiscal_year(
    company_id: str,
    payload: ReopenFiscalYearRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
    request: Request = None,
):
    """Reabre el ejercicio contable retrocediendo la fecha de cierre previa autorización RBAC y confirmación estricta de CIF."""
    if current_user:
        allowed_roles = {UserRole.SUPERADMIN.value, UserRole.COMPANY_ADMIN.value, UserRole.ADVISOR.value}
        if current_user.global_role not in allowed_roles:
            log_security_event(
                action="FISCAL_YEAR_REOPEN_UNAUTHORIZED",
                empresa_id=company_id,
                request=request,
                user_id=current_user.id,
                status="DENIED",
                details={"role": current_user.global_role},
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permisos insuficientes: solo Administradores o Asesores pueden reabrir ejercicios cerrados.",
            )

    comp = await db.get(Company, company_id)
    if not comp:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    if normalize_nif(payload.cif_confirmation) != normalize_nif(comp.cif):
        raise HTTPException(
            status_code=400,
            detail=f"Confirmación incorrecta. Debe teclear exactamente el CIF '{comp.cif}' para autorizar la reapertura."
        )

    old_date = comp.fecha_cierre_contable
    comp.fecha_cierre_contable = payload.new_closing_date
    await db.commit()

    log_security_event(
        action="FISCAL_YEAR_REOPENED",
        empresa_id=company_id,
        details={
            "company_id": company_id,
            "old_closing_date": old_date.isoformat() if old_date else None,
            "new_closing_date": payload.new_closing_date.isoformat() if payload.new_closing_date else None,
        }
    )

    return {
        "success": True,
        "message": "Ejercicio reabierto correctamente.",
        "previous_closing_date": old_date.isoformat() if old_date else None,
        "current_closing_date": payload.new_closing_date.isoformat() if payload.new_closing_date else None,
    }


# ---------------------------------------------------------------------------
# EXTRACTO DE MAYOR POR SUBCUENTA
# ---------------------------------------------------------------------------
@router.get("/{company_id}/ledger/{subcuenta}")
async def get_account_ledger(
    company_id: str,
    subcuenta: str,
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    fiscal_year: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Devuelve los movimientos del Libro Mayor para una subcuenta individual,
    con saldo progresivo cronológico y determinación exacta de naturaleza deudora/acreedora.
    """
    comp = await db.get(Company, company_id)
    if not comp:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    # Saldo inicial de la cuenta en el plan de cuentas
    acc_stmt = select(Account).where(Account.company_id == company_id, Account.codigo == subcuenta.strip())
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
            AccountingEntryLine.subcuenta == subcuenta.strip(),
            or_(
                AccountingEntryLine.company_id == company_id,
                Invoice.company_id == company_id,
                SalesInvoice.company_id == company_id
            )
        )
    )

    actual_from = from_date if isinstance(from_date, (date, datetime)) else None
    actual_to = to_date if isinstance(to_date, (date, datetime)) else None
    actual_year = fiscal_year if isinstance(fiscal_year, int) else None

    if actual_from:
        stmt = stmt.where(AccountingEntryLine.fecha >= actual_from)
    if actual_to:
        stmt = stmt.where(AccountingEntryLine.fecha <= actual_to)
    if actual_year:
        stmt = stmt.where(func.extract('year', AccountingEntryLine.fecha) == actual_year)

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
            "signo": "D" if saldo_acumulado > 0 else "H" if saldo_acumulado < 0 else "0",
            "status": getattr(l, "status", "contabilizado"),
            "is_reversal": getattr(l, "is_reversal", False),
        })

    # Naturaleza contable esperada según el grupo inicial PGC
    primer_digito = subcuenta.strip()[:1]
    naturaleza_esperada = "DEUDORA" if primer_digito in ("2", "3", "6") else "ACREEDORA" if primer_digito in ("1", "7") else "MIXTA"

    return {
        "company_id": company_id,
        "subcuenta": subcuenta.strip(),
        "descripcion": acc.descripcion if acc else "",
        "naturaleza_esperada": naturaleza_esperada,
        "debe_inicial": debe_inicial,
        "haber_inicial": haber_inicial,
        "total_debe": round(total_debe, 2),
        "total_haber": round(total_haber, 2),
        "saldo_final": round(total_debe - total_haber, 2),
        "tipo_saldo": "DEUDOR" if (total_debe - total_haber) > 0 else "ACREEDOR" if (total_debe - total_haber) < 0 else "CERO",
        "movimientos_count": len(movements),
        "movimientos": movements
    }


# ---------------------------------------------------------------------------
# BALANCE DE SUMAS Y SALDOS CON SUBTOTOLES PGC
# ---------------------------------------------------------------------------
@router.get("/{company_id}/trial-balance")
async def get_trial_balance(
    company_id: str,
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    fiscal_year: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Genera el Balance de Sumas y Saldos completo, agrupando por subcuentas
    y generando subtotales oficiales por los 7 Grupos del PGC.
    """
    comp = await db.get(Company, company_id)
    if not comp:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    # Todas las cuentas
    acc_stmt = select(Account).where(Account.company_id == company_id).order_by(Account.codigo.asc())
    accounts = (await db.execute(acc_stmt)).scalars().all()

    # Todos los apuntes con filtros de fecha
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
            ),
            AccountingEntryLine.status != "revertido"
        )
    )

    # Normalizar parámetros para prevenir inyección de objetos Query al llamarse internamente
    actual_from = from_date if isinstance(from_date, (date, datetime)) else None
    actual_to = to_date if isinstance(to_date, (date, datetime)) else None
    actual_year = fiscal_year if isinstance(fiscal_year, int) else None

    if actual_from:
        entries_stmt = entries_stmt.where(AccountingEntryLine.fecha >= actual_from)
    if actual_to:
        entries_stmt = entries_stmt.where(AccountingEntryLine.fecha <= actual_to)
    if actual_year:
        entries_stmt = entries_stmt.where(func.extract('year', AccountingEntryLine.fecha) == actual_year)

    entries_stmt = entries_stmt.group_by(AccountingEntryLine.subcuenta)
    entries_res = await db.execute(entries_stmt)
    entries_map = {row.subcuenta: (row.sum_debe or 0.0, row.sum_haber or 0.0) for row in entries_res}

    items = []
    total_suma_debe = 0.0
    total_suma_haber = 0.0
    total_saldo_deudor = 0.0
    total_saldo_acreedor = 0.0

    # Diccionario de agregación por Grupo PGC (1..7)
    grupos_agg: Dict[str, Dict[str, float]] = {
        str(i): {"suma_debe": 0.0, "suma_haber": 0.0, "saldo_deudor": 0.0, "saldo_acreedor": 0.0, "cuentas_count": 0}
        for i in range(1, 8)
    }

    for acc in accounts:
        mov_debe, mov_haber = entries_map.get(acc.codigo, (0.0, 0.0))
        suma_debe = round((acc.debe_inicial or 0.0) + mov_debe, 2)
        suma_haber = round((acc.haber_inicial or 0.0) + mov_haber, 2)

        # Omitir cuentas sin movimientos ni saldo
        if suma_debe == 0.0 and suma_haber == 0.0:
            continue

        neto = round(suma_debe - suma_haber, 2)
        saldo_deudor = neto if neto > 0 else 0.0
        saldo_acreedor = abs(neto) if neto < 0 else 0.0

        total_suma_debe += suma_debe
        total_suma_haber += suma_haber
        total_saldo_deudor += saldo_deudor
        total_saldo_acreedor += saldo_acreedor

        primer_digito = acc.codigo[:1]
        if primer_digito in grupos_agg:
            grupos_agg[primer_digito]["suma_debe"] += suma_debe
            grupos_agg[primer_digito]["suma_haber"] += suma_haber
            grupos_agg[primer_digito]["saldo_deudor"] += saldo_deudor
            grupos_agg[primer_digito]["saldo_acreedor"] += saldo_acreedor
            grupos_agg[primer_digito]["cuentas_count"] += 1

        items.append({
            "codigo": acc.codigo,
            "descripcion": acc.descripcion,
            "grupo": primer_digito,
            "nivel": len(acc.codigo) if acc.codigo else 1,
            "suma_debe": suma_debe,
            "suma_haber": suma_haber,
            "saldo_deudor": saldo_deudor,
            "saldo_acreedor": saldo_acreedor
        })

    total_suma_debe = round(total_suma_debe, 2)
    total_suma_haber = round(total_suma_haber, 2)
    total_saldo_deudor = round(total_saldo_deudor, 2)
    total_saldo_acreedor = round(total_saldo_acreedor, 2)

    # Construir lista de resumen de grupos PGC
    grupos_resumen = []
    for g_num, g_data in sorted(grupos_agg.items()):
        if g_data["cuentas_count"] > 0:
            grupos_resumen.append({
                "grupo": g_num,
                "nombre": PGC_GRUPOS_NOMBRES.get(g_num, f"Grupo {g_num}"),
                "suma_debe": round(g_data["suma_debe"], 2),
                "suma_haber": round(g_data["suma_haber"], 2),
                "saldo_deudor": round(g_data["saldo_deudor"], 2),
                "saldo_acreedor": round(g_data["saldo_acreedor"], 2),
                "cuentas_activas": int(g_data["cuentas_count"]),
            })

    return {
        "company_id": company_id,
        "items_count": len(items),
        "items": items,
        "grupos_resumen": grupos_resumen,
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


# ---------------------------------------------------------------------------
# EXPORTACIÓN DEL BALANCE DE SUMAS Y SALDOS A CSV (EXCEL)
# ---------------------------------------------------------------------------
@router.get("/{company_id}/trial-balance/export-csv")
async def export_trial_balance_csv(
    company_id: str,
    fiscal_year: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Exporta el Balance de Sumas y Saldos a formato CSV delimitado por ';'
    con codificación UTF-8 con BOM para apertura inmediata y correcta en Microsoft Excel.
    """
    comp = await db.get(Company, company_id)
    if not comp:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    balance = await get_trial_balance(company_id=company_id, fiscal_year=fiscal_year, db=db)

    output = io.StringIO()
    # Escribir BOM UTF-8 para Excel
    output.write('\ufeff')
    writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_MINIMAL)

    # Cabecera de informe
    writer.writerow(["EMPRESA", comp.razon_social, "CIF", comp.cif, "FECHA", date.today().strftime("%d/%m/%Y")])
    writer.writerow(["INFORME", "BALANCE DE COMPROBACIÓN DE SUMAS Y SALDOS (PGC PYMES)"])
    writer.writerow([])

    # Cabeceras de columnas
    writer.writerow(["CUENTA", "DESCRIPCIÓN", "SUMA DEBE (€)", "SUMA HABER (€)", "SALDO DEUDOR (€)", "SALDO ACREEDOR (€)"])

    # Filas de subcuentas
    for it in balance["items"]:
        writer.writerow([
            it["codigo"],
            it["descripcion"],
            f"{it['suma_debe']:.2f}".replace('.', ','),
            f"{it['suma_haber']:.2f}".replace('.', ','),
            f"{it['saldo_deudor']:.2f}".replace('.', ',') if it['saldo_deudor'] > 0 else "0,00",
            f"{it['saldo_acreedor']:.2f}".replace('.', ',') if it['saldo_acreedor'] > 0 else "0,00",
        ])

    # Totales generales
    tot = balance["totales"]
    writer.writerow([])
    writer.writerow([
        "TOTALES GENERALES",
        "",
        f"{tot['suma_debe']:.2f}".replace('.', ','),
        f"{tot['suma_haber']:.2f}".replace('.', ','),
        f"{tot['saldo_deudor']:.2f}".replace('.', ','),
        f"{tot['saldo_acreedor']:.2f}".replace('.', ','),
    ])

    csv_data = output.getvalue().encode('utf-8')
    filename = f"balance_sumas_saldos_{comp.cif}_{date.today().strftime('%Y%m%d')}.csv"

    return Response(
        content=csv_data,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
