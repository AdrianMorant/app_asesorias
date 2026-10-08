import re
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional, Tuple
from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company
from app.models.account import Account
from app.models.supplier import Supplier
from app.models.contact import Contact
from app.models.invoice import Invoice
from app.schemas.invoice_extraction import InvoiceExtractionResult
from app.schemas.rules_result import (
    TrafficLightStatus,
    RuleCheckDetail,
    RulesEvaluationResult,
)
from app.services.nif_validator import validate_spanish_id, normalize_nif
from app.services.accounting_engine import format_subcuenta


def to_decimal(val: Optional[float]) -> Decimal:
    """Convierte un float/int a Decimal con 2 decimales exactos sin artefactos de coma flotante."""
    if val is None:
        return Decimal("0.00")
    return Decimal(f"{val:.2f}")


def get_generic_supplier_account(prefix: str, length: int) -> str:
    """Devuelve la subcuenta genérica formateada según la longitud del plan contable (ej. 41000000 o 410000000)."""
    return format_subcuenta(prefix, "0", length)


# Festivos nacionales fijos oficiales en España (mes, día)
SPANISH_NATIONAL_HOLIDAYS = {
    (1, 1),   # Año Nuevo
    (1, 6),   # Epifanía del Señor / Reyes
    (5, 1),   # Fiesta del Trabajo
    (8, 15),  # Asunción de la Virgen
    (10, 12), # Fiesta Nacional de España
    (11, 1),  # Todos los Santos
    (12, 6),  # Día de la Constitución
    (12, 8),  # Inmaculada Concepción
    (12, 25), # Natividad del Señor
}


def get_first_open_business_day(closure_date: date) -> date:
    """
    Calcula el primer día hábil posterior a una fecha de cierre contable,
    omitiendo fines de semana (sábados y domingos) y festivos nacionales oficiales.
    """
    candidate = closure_date + timedelta(days=1)
    while candidate.weekday() >= 5 or (candidate.month, candidate.day) in SPANISH_NATIONAL_HOLIDAYS:
        candidate += timedelta(days=1)
    return candidate


async def find_next_free_supplier_account(
    company_id: str,
    length: int,
    db: AsyncSession,
    prefix: str = "410"
) -> str:
    """
    Inspecciona el maestro de cuentas de la empresa y calcula la siguiente subcuenta
    correlativa libre respetando la longitud configurada y el prefijo (ej. 41000004 si son 8 dígitos
    o 410000004 si son 9 dígitos).
    """
    num_digits = length - len(prefix)

    stmt = select(Account.codigo).where(
        Account.company_id == company_id,
        Account.codigo.like(f"{prefix}%")
    )
    res = await db.execute(stmt)
    existing_codes = set(res.scalars().all())

    # Buscar el mayor correlativo numérico existente
    max_num = 0
    for code in existing_codes:
        suffix = code[len(prefix):]
        if suffix.isdigit():
            val = int(suffix)
            if val > max_num:
                max_num = val

    next_num = max_num + 1
    correlativo = str(next_num).zfill(num_digits)
    return f"{prefix}{correlativo}"


def infer_suggested_expense_account(
    concept: Optional[str],
    issuer_name: Optional[str],
    has_retention: bool,
    length: int
) -> str:
    """
    Asigna por inferencia del concepto y emisor la subcuenta de gasto PGC más probable:
    - 623: Profesionales independientes (abogados, consultores, notaría o con IRPF)
    - 628: Suministros (electricidad, agua, gas, telefonía, fibra)
    - 621: Arrendamientos y cánones (alquiler de oficinas, naves, locales)
    - 622: Reparaciones y conservación
    - 625: Primas de seguros
    - 600: Compras de existencias y mercaderías
    - 629: Otros servicios exteriores y generales
    """
    text = f"{concept or ''} {issuer_name or ''}".lower()

    if has_retention or any(w in text for w in ["abogad", "asesor", "notari", "juridic", "consultor", "honorari"]):
        return format_subcuenta("623", "0", length)

    if any(w in text for w in [
        "electric", "luz", "gas", "agua", "suministr", "telef", "fibra", "internet",
        "movistar", "vodafone", "orange", "iberdrola", "endesa", "naturgy", "totalenergies"
    ]):
        return format_subcuenta("628", "0", length)

    if any(w in text for w in ["alquiler", "arrendam", "renta", "local", "oficina", "nave"]):
        return format_subcuenta("621", "0", length)

    if any(w in text for w in ["reparac", "mantenim", "taller", "revision"]):
        return format_subcuenta("622", "0", length)

    if any(w in text for w in ["seguro", "poliza", "asegura"]):
        return format_subcuenta("625", "0", length)

    if any(w in text for w in ["mercaderia", "compra material", "producto"]):
        return format_subcuenta("600", "0", length)

    return format_subcuenta("629", "0", length)


async def validate_invoice_integrity(
    extraction: InvoiceExtractionResult,
    company_id: str,
    db: AsyncSession,
    current_invoice_id: Optional[str] = None,
    file_hash: Optional[str] = None
) -> RulesEvaluationResult:
    """
    Motor semafórico estricto conforme a la normativa fiscal y contable española:
    - 🔴 ROJO: Bloqueo preventivo por anomalía crítica (Duplicada, Descuadre > 0.01 €, CIF AEAT inválido, Ilegible).
    - 🟡 AMARILLO: Triaje asistido con propuesta automática de subcuentas para creación al aprobar.
    - 🟢 VERDE: Certificada para aprobación desatendida en 1 clic.
    """
    reasons: List[str] = []
    rule_details: List[RuleCheckDetail] = []

    has_red = False
    has_yellow = False

    is_duplicate = False
    duplicate_of_id = None
    cif_valid = True
    math_valid = True
    adjusted_fecha_contable = None
    date_lock_applied = False

    # Obtener configuración de empresa
    comp_res = await db.execute(select(Company).where(Company.id == company_id))
    company = comp_res.scalars().first()
    plan_longitud = company.plan_cuentas_longitud if company else 9

    # -------------------------------------------------------------------------
    # 1. BLOQUEO PREVENTIVO POR ANOMALÍAS CRÍTICAS (🔴 ROJO)
    # -------------------------------------------------------------------------

    # R1: Validación de legibilidad mínima del documento
    raw_cif = (extraction.issuer_tax_id or "").strip()
    raw_inv_num = (extraction.invoice_number or "").strip()
    if not raw_cif:
        has_red = True
        cif_valid = False
        msg = "ERROR: Fallo de extracción visual o archivo ilegible (no se detectó CIF/NIF del emisor)."
        reasons.append(msg)
        rule_details.append(RuleCheckDetail(
            rule_name="DOCUMENTO_ILEGIBLE_CIF",
            severity=TrafficLightStatus.RED,
            passed=False,
            message=msg
        ))

    # R2: Validación formal ante el algoritmo oficial de la AEAT
    norm_cif = normalize_nif(raw_cif)
    if norm_cif:
        nif_result = validate_spanish_id(norm_cif)
        if not nif_result.is_valid:
            has_red = True
            cif_valid = False
            msg = f"ERROR: CIF {raw_cif} no cumple algoritmo AEAT ({nif_result.error_message or 'formato incorrecto'})."
            reasons.append(msg)
            rule_details.append(RuleCheckDetail(
                rule_name="VALIDEZ_NIF_EMISOR",
                severity=TrafficLightStatus.RED,
                passed=False,
                message=msg
            ))
        else:
            rule_details.append(RuleCheckDetail(
                rule_name="VALIDEZ_NIF_EMISOR",
                severity=TrafficLightStatus.GREEN,
                passed=True,
                message=f"Documento fiscal verificado ({nif_result.document_type}: {norm_cif})."
            ))

    # R3: Cuadre Aritmético Exacto al céntimo (Precisión Decimal Absoluta)
    base_dec = to_decimal(extraction.total_base)
    tax_dec = to_decimal(extraction.total_tax)
    ret_dec = to_decimal(extraction.retention_amount)
    total_dec = to_decimal(extraction.total_amount)

    expected_total_dec = base_dec + tax_dec - ret_dec
    arithmetic_diff_dec = abs(expected_total_dec - total_dec)
    arithmetic_diff_float = float(arithmetic_diff_dec)

    if arithmetic_diff_dec > Decimal("0.01"):
        has_red = True
        math_valid = False
        msg = (
            f"ERROR: Descuadre aritmético de {arithmetic_diff_dec:.2f} € "
            f"(Base: {base_dec:.2f} € + IVA: {tax_dec:.2f} € - Retención: {ret_dec:.2f} € = {expected_total_dec:.2f} € "
            f"vs Total: {total_dec:.2f} €)."
        )
        reasons.append(msg)
        rule_details.append(RuleCheckDetail(
            rule_name="CUADRE_ARITMETICO",
            severity=TrafficLightStatus.RED,
            passed=False,
            message=msg
        ))
    else:
        rule_details.append(RuleCheckDetail(
            rule_name="CUADRE_ARITMETICO",
            severity=TrafficLightStatus.GREEN,
            passed=True,
            message="Cuadre fiscal exacto al céntimo (Base + IVA - Retención = Total)."
        ))

    # R4: Detección de Factura Duplicada en Tiempo Real (Hash SHA-256 o Tupla CIF + Nº Factura + Fecha)
    duplicate_invoice = None

    # A. Chequeo por Hash SHA-256 de fichero idéntico
    if file_hash:
        hash_stmt = select(Invoice).where(
            Invoice.company_id == company_id,
            Invoice.file_hash == file_hash
        )
        if current_invoice_id:
            hash_stmt = hash_stmt.where(Invoice.id != current_invoice_id)
        hash_res = await db.execute(hash_stmt)
        duplicate_invoice = hash_res.scalars().first()

    # B. Chequeo por Tupla (CIF emisor + Número de Factura)
    if not duplicate_invoice and norm_cif and raw_inv_num and raw_inv_num != "S/N":
        dup_stmt = select(Invoice).where(
            Invoice.company_id == company_id,
            Invoice.issuer_cif == norm_cif,
            Invoice.invoice_number == raw_inv_num
        )
        if current_invoice_id:
            dup_stmt = dup_stmt.where(Invoice.id != current_invoice_id)

        dup_res = await db.execute(dup_stmt)
        duplicate_invoice = dup_res.scalars().first()

    if duplicate_invoice:
        has_red = True
        is_duplicate = True
        duplicate_of_id = duplicate_invoice.id
        msg = f"ERROR: Factura duplicada ({raw_inv_num} del emisor {norm_cif} ya existe registrada con ID {duplicate_invoice.id[:8]})."
        reasons.append(msg)
        rule_details.append(RuleCheckDetail(
            rule_name="FACTURA_DUPLICADA",
            severity=TrafficLightStatus.RED,
            passed=False,
            message=msg
        ))
    else:
        rule_details.append(RuleCheckDetail(
            rule_name="FACTURA_DUPLICADA",
            severity=TrafficLightStatus.GREEN,
            passed=True,
            message="No se detecta duplicidad previa en la base de datos."
        ))

    # R5: Bloqueo Contable de Fechas (Cierre de Ejercicio o Periodo)
    if company and getattr(company, "fecha_cierre_contable", None):
        try:
            issue_date_obj = datetime.strptime(extraction.issue_date, "%Y-%m-%d").date()
        except Exception:
            issue_date_obj = date.today()

        if issue_date_obj <= company.fecha_cierre_contable:
            first_open = get_first_open_business_day(company.fecha_cierre_contable)
            adjusted_fecha_contable = first_open.isoformat()
            date_lock_applied = True
            msg_lock = (
                f"Bloqueo Contable de Fechas: Fecha de emisión ({issue_date_obj}) anterior al cierre contable "
                f"({company.fecha_cierre_contable}). Se traslada la fecha contable al primer día hábil abierto: {first_open}."
            )
            reasons.append(msg_lock)
            rule_details.append(RuleCheckDetail(
                rule_name="BLOQUEO_FECHA_CONTABLE",
                severity=TrafficLightStatus.YELLOW if not has_red else TrafficLightStatus.RED,
                passed=False,
                message=msg_lock
            ))

    # -------------------------------------------------------------------------
    # 2. EVALUACIÓN DE PROVEEDOR Y CUENTAS PGC (🟢 VERDE VS 🟡 AMARILLO)
    # -------------------------------------------------------------------------
    supplier_found = False
    supplier_id = None
    suggested_supplier_account = None
    suggested_expense_account = None

    if norm_cif:
        # A. Buscar en maestro de Proveedores (Supplier)
        supp_res = await db.execute(
            select(Supplier).where(Supplier.company_id == company_id, Supplier.cif == norm_cif)
        )
        existing_supplier = supp_res.scalars().first()

        # B. Buscar en Directorio de Contactos (Contact)
        contact_res = await db.execute(
            select(Contact).where(Contact.company_id == company_id, Contact.cif == norm_cif)
        )
        existing_contact = contact_res.scalars().first()

        # C. Buscar en Plan General Contable (Account 400/410 con este CIF)
        acc_res = await db.execute(
            select(Account).where(
                Account.company_id == company_id,
                Account.cif_asociado == norm_cif
            )
        )
        existing_account = acc_res.scalars().first()

        if existing_supplier or existing_contact or existing_account:
            supplier_found = True
            if existing_supplier:
                supplier_id = existing_supplier.id
                suggested_supplier_account = existing_supplier.subcuenta_proveedor
                suggested_expense_account = existing_supplier.subcuenta_gasto_defecto
            elif existing_contact:
                suggested_supplier_account = existing_contact.subcuenta_default
                suggested_expense_account = infer_suggested_expense_account(
                    extraction.concept_summary, extraction.issuer_name, ret_dec > Decimal("0.00"), plan_longitud
                )
            elif existing_account:
                suggested_supplier_account = existing_account.codigo
                suggested_expense_account = infer_suggested_expense_account(
                    extraction.concept_summary, extraction.issuer_name, ret_dec > Decimal("0.00"), plan_longitud
                )

            # Verificar si la subcuenta de gasto existe y está activa en el Plan Contable PYME
            expense_account_exists = False
            if suggested_expense_account:
                exp_stmt = select(Account).where(
                    Account.company_id == company_id,
                    Account.codigo == suggested_expense_account
                )
                exp_res = await db.execute(exp_stmt)
                expense_account_exists = exp_res.scalars().first() is not None

            if not expense_account_exists:
                has_yellow = True
                msg = f"La subcuenta de gasto {suggested_expense_account} no figura en el Plan Contable. Se creará automáticamente al aprobar."
                reasons.append(msg)
                rule_details.append(RuleCheckDetail(
                    rule_name="CUENTA_GASTO_NUEVA",
                    severity=TrafficLightStatus.YELLOW,
                    passed=False,
                    message=msg
                ))
            else:
                rule_details.append(RuleCheckDetail(
                    rule_name="PROVEEDOR_MAPEA_PGC",
                    severity=TrafficLightStatus.GREEN,
                    passed=True,
                    message=f"Proveedor y gasto identificados en el PGC: '{extraction.issuer_name}' (Prov: {suggested_supplier_account}, Gasto: {suggested_expense_account})."
                ))
        else:
            # Emisor es un PROVEEDOR NUEVO -> Asistencia Inteligente (AMARILLO)
            has_yellow = True
            suggested_supplier_account = await find_next_free_supplier_account(company_id, plan_longitud, db)
            suggested_expense_account = infer_suggested_expense_account(
                extraction.concept_summary, extraction.issuer_name, ret_dec > Decimal("0.00"), plan_longitud
            )

            msg = (
                f"Proveedor nuevo detectado (CIF {norm_cif}). "
                f"Propuesta asistida: Subcuenta {suggested_supplier_account} / Gasto {suggested_expense_account}. "
                "Al pulsar 'Aprobar' se dará de alta automáticamente en el Plan Contable y en Contactos."
            )
            reasons.append(msg)
            rule_details.append(RuleCheckDetail(
                rule_name="PROVEEDOR_NUEVO_ASISTIDO",
                severity=TrafficLightStatus.YELLOW,
                passed=False,
                message=msg
            ))

    # Control informativo de Modelo 347 (>3.000 €)
    if total_dec > Decimal("3000.00"):
        rule_details.append(RuleCheckDetail(
            rule_name="AVISO_MODELO_347",
            severity=TrafficLightStatus.YELLOW if not has_red else TrafficLightStatus.RED,
            passed=True,
            message=f"Operación relevante para Modelo 347 (>3.000 €: {total_dec:,.2f} €)."
        ))

    # -------------------------------------------------------------------------
    # 3. DETERMINACIÓN DEL ESTADO FINAL
    # -------------------------------------------------------------------------
    if has_red:
        final_status = TrafficLightStatus.RED
    elif has_yellow:
        final_status = TrafficLightStatus.YELLOW
    else:
        final_status = TrafficLightStatus.GREEN
        reasons.append("Factura 100% cuadrada, CIF certificado ante la AEAT y cuentas mapeadas en el Plan Contable.")

    return RulesEvaluationResult(
        status=final_status,
        passed=(final_status == TrafficLightStatus.GREEN),
        reasons=reasons,
        rule_details=rule_details,
        arithmetic_difference=arithmetic_diff_float,
        supplier_found=supplier_found,
        supplier_id=supplier_id,
        suggested_supplier_account=suggested_supplier_account,
        suggested_expense_account=suggested_expense_account,
        is_duplicate=is_duplicate,
        duplicate_of_id=duplicate_of_id,
        cif_valid=cif_valid,
        math_valid=math_valid,
        adjusted_fecha_contable=adjusted_fecha_contable,
        date_lock_applied=date_lock_applied
    )


# Alias canónico
evaluate_invoice_rules = validate_invoice_integrity
