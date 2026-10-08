from typing import List, Optional
from datetime import date
from app.models.supplier import Supplier
from app.schemas.invoice_extraction import InvoiceExtractionResult
from app.schemas.invoice_dto import AccountingEntryLineDTO

def format_subcuenta(root: str, default_tail: str, length: int) -> str:
    """
    Rellena una subcuenta contable con ceros intermedios según la longitud
    del plan contable de la empresa (8, 9 o 10 dígitos).
    Ejemplo para 9 dígitos:
      root='629', default_tail='0' -> '629000000'
      root='472', default_tail='21' -> '472000021'
      root='400', default_tail='1' -> '400000001'
    """
    if len(root) + len(default_tail) >= length:
        return (root + default_tail)[:length]
    padding_zeros = "0" * (length - len(root) - len(default_tail))
    return f"{root}{padding_zeros}{default_tail}"

def generate_accounting_entry_lines(
    extraction: InvoiceExtractionResult,
    plan_longitud: int = 9,
    supplier: Optional[Supplier] = None,
    entry_date: Optional[date] = None,
    custom_supplier_account: Optional[str] = None,
    custom_expense_account: Optional[str] = None,
    suplidos_amount: float = 0.0,
    custom_suplidos_account: Optional[str] = None,
    is_rectificativa: bool = False,
    retention_model: str = "111/190"
) -> List[AccountingEntryLineDTO]:
    """
    Genera el asiento contable en partida doble según el Plan General Contable (PGC) español.
    
    Estructura típica de factura recibida de gasto:
    - DEBE: (6XX) Cuenta de Gasto por la Base Imponible
    - DEBE: (472.XX) HP IVA Soportado por la Cuota de IVA
    - DEBE: (554.X) Suplidos / Provisiones de Fondos (si aplica)
    - HABER: (4751) HP Acreedora por Retenciones IRPF (si aplica, Modelo 111/190 o 115/180)
    - HABER: (400.X / 410.X) Proveedores o Acreedores por el Total Factura
    
    Si es Factura Rectificativa, los importes se generan con signo negativo reflejando la minoración contable.
    """
    lines: List[AccountingEntryLineDTO] = []
    fecha = entry_date or date.today()
    doc = extraction.invoice_number or "S/N"
    prov_name = extraction.issuer_name or "Proveedor"
    prefix_rect = "Rectificativa " if is_rectificativa else ""
    concepto_base = f"Fra. {prefix_rect}{doc} - {prov_name}"
    sign = -1.0 if is_rectificativa else 1.0

    # 1. CUENTA DE GASTO (DEBE)
    cuenta_gasto = (
        custom_expense_account
        or (supplier.subcuenta_gasto_defecto if supplier and supplier.subcuenta_gasto_defecto else None)
        or format_subcuenta("629", "0", plan_longitud)  # 629 = Otros servicios
    )
    
    total_base = round(float(extraction.total_base or 0.0), 2)
    if total_base > 0 or is_rectificativa:
        base_val = round(abs(total_base) * sign, 2)
        lines.append(AccountingEntryLineDTO(
            entry_number=1,
            fecha=fecha,
            subcuenta=cuenta_gasto,
            concepto=f"{concepto_base} (Gasto)",
            debe=base_val,
            haber=0.0,
            documento=doc
        ))

    # 2. CUENTAS DE IVA SOPORTADO (DEBE)
    if extraction.taxes:
        for t in extraction.taxes:
            rate_int = int(round(float(t.tax_rate or 0.0)))
            cuenta_iva = format_subcuenta("472", str(rate_int), plan_longitud)
            tax_amount = round(float(t.tax_amount or 0.0), 2)
            if tax_amount > 0 or is_rectificativa:
                tax_val = round(abs(tax_amount) * sign, 2)
                lines.append(AccountingEntryLineDTO(
                    entry_number=1,
                    fecha=fecha,
                    subcuenta=cuenta_iva,
                    concepto=f"{concepto_base} (IVA {rate_int}%)",
                    debe=tax_val,
                    haber=0.0,
                    documento=doc
                ))
    else:
        total_tax = round(float(extraction.total_tax or 0.0), 2)
        if total_tax > 0 or is_rectificativa:
            tax_val = round(abs(total_tax) * sign, 2)
            cuenta_iva = format_subcuenta("472", "21", plan_longitud)
            lines.append(AccountingEntryLineDTO(
                entry_number=1,
                fecha=fecha,
                subcuenta=cuenta_iva,
                concepto=f"{concepto_base} (IVA)",
                debe=tax_val,
                haber=0.0,
                documento=doc
            ))

    # 3. SUPLIDOS (DEBE, cuenta 554 de pagos por cuenta de terceros)
    suplidos_val_raw = round(float(suplidos_amount or 0.0), 2)
    if suplidos_val_raw > 0:
        cuenta_suplidos = (
            custom_suplidos_account
            or format_subcuenta("554", "0", plan_longitud)
        )
        suplidos_val = round(abs(suplidos_val_raw) * sign, 2)
        lines.append(AccountingEntryLineDTO(
            entry_number=1,
            fecha=fecha,
            subcuenta=cuenta_suplidos,
            concepto=f"{concepto_base} (Suplidos)",
            debe=suplidos_val,
            haber=0.0,
            documento=doc
        ))

    # 4. RETENCIÓN IRPF (HABER, si existe retención profesional / alquiler)
    ret_amount_raw = getattr(extraction, "retention_amount", 0.0) or getattr(extraction, "total_retention", 0.0) or 0.0
    retention_amount = round(float(ret_amount_raw or 0.0), 2)
    if retention_amount > 0:
        ret_val_raw = retention_amount
        # Cuenta 4751 para Modelo 111 (profesionales) o 4751.1 para Modelo 115 (arrendamientos)
        sub_ret_tail = "15" if "115" in str(retention_model) else "0"
        cuenta_retencion = format_subcuenta("4751", sub_ret_tail, plan_longitud)
        rate_ret_val = getattr(extraction, "retention_rate", 15.0) or 15.0
        rate_ret = int(round(float(rate_ret_val)))
        ret_val = round(abs(ret_val_raw) * sign, 2)
        lines.append(AccountingEntryLineDTO(
            entry_number=1,
            fecha=fecha,
            subcuenta=cuenta_retencion,
            concepto=f"{concepto_base} (Retención {retention_model} {rate_ret}%)",
            debe=0.0,
            haber=ret_val,
            documento=doc
        ))

    # 5. CUENTA DE PROVEEDOR / ACREEDOR (HABER)
    cuenta_proveedor = (
        custom_supplier_account
        or (supplier.subcuenta_proveedor if supplier and supplier.subcuenta_proveedor else None)
        or format_subcuenta("400", "1", plan_longitud)
    )
    total_amount = round(float(extraction.total_amount or 0.0), 2)
    total_val = round(abs(total_amount) * sign, 2)
    
    lines.append(AccountingEntryLineDTO(
        entry_number=1,
        fecha=fecha,
        subcuenta=cuenta_proveedor,
        concepto=f"{concepto_base}",
        debe=0.0,
        haber=total_val,
        documento=doc
    ))

    return lines
