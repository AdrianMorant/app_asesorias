"""
Módulo de Enlace Contable para Wolters Kluwer A3 (A3eco / A3innuva / A3con)
Generación del fichero estándar de ancho fijo SUENLACE.DAT con codificación CP1252/ANSI.
Incluye el algoritmo A3SeatSplitter para división en 2 asientos si hay más de 3 tipos de IVA.
"""

from typing import Any, Dict, List, Optional, Union
from datetime import date, datetime


def build_a3_record(fields: List[str], expected_len: int = 96) -> str:
    """
    Concatena los campos y garantiza una longitud fija estricta de 96 caracteres
    rellenando con espacios a la derecha o truncando si excede.
    """
    record = "".join(fields)
    if len(record) < expected_len:
        record = record.ljust(expected_len, " ")
    elif len(record) > expected_len:
        record = record[:expected_len]
    return record


def _extract_factura_data(factura: Any, account_digits: int = 9) -> Dict[str, Any]:
    """
    Normaliza los datos de la factura admitiendo modelos SQLAlchemy (Invoice),
    diccionarios o cualquier objeto DTO con atributos.
    """
    def _get(key: str, default: Any = None):
        if isinstance(factura, dict):
            return factura.get(key, default)
        return getattr(factura, key, default)

    # Fecha contable o de emisión
    fecha_val = _get("fecha_contable") or _get("issue_date") or _get("fecha")
    if isinstance(fecha_val, (date, datetime)):
        fecha_str = fecha_val.strftime("%d%m%Y")
    elif isinstance(fecha_val, str) and fecha_val:
        # Intentar normalizar formatos YYYY-MM-DD o DD/MM/YYYY
        cleaned = fecha_val.strip().replace("-", "").replace("/", "")
        if len(cleaned) == 8:
            if fecha_val.find("-") == 4:  # YYYYMMDD
                fecha_str = f"{cleaned[6:8]}{cleaned[4:6]}{cleaned[0:4]}"
            else:  # DDMMAAAA
                fecha_str = cleaned
        else:
            fecha_str = "01012026"
    else:
        fecha_str = "01012026"

    doc_num = str(_get("invoice_number") or _get("documento") or _get("numero") or "S/N").strip()
    doc_str = doc_num.ljust(10)[:10]

    cif_val = str(_get("issuer_cif") or _get("cif") or _get("nif") or "").strip()
    cif_str = cif_val.ljust(10)[:10]

    name_val = str(_get("issuer_name") or _get("nombre") or _get("proveedor") or "Proveedor").strip()

    # Cuentas contables
    zeros_cta = "0" * max(0, account_digits - 4)
    cta_prov = str(_get("supplier_account") or _get("cta_prov") or f"400{zeros_cta}1").strip()
    cta_gasto = str(_get("expense_account") or _get("cta_gasto") or f"629{zeros_cta}0").strip()

    # Si vienen accounting_entries, intentar detectar subcuentas
    entries = _get("accounting_entries")
    if entries:
        for e in entries:
            sc = getattr(e, "subcuenta", "") or (e.get("subcuenta", "") if isinstance(e, dict) else "")
            if sc.startswith("400") or sc.startswith("410"):
                cta_prov = sc
            elif sc.startswith("6"):
                cta_gasto = sc

    # Desglose de impuestos / IVA
    raw_taxes = _get("tax_breakdown") or _get("taxes") or _get("iva_lines") or []
    taxes_list = []
    for t in raw_taxes:
        if isinstance(t, dict):
            rate = float(t.get("tax_rate", 21.0) or 21.0)
            base = float(t.get("tax_base", 0.0) or 0.0)
            amount = float(t.get("tax_amount", 0.0) or 0.0)
        else:
            rate = float(getattr(t, "tax_rate", 21.0) or 21.0)
            base = float(getattr(t, "tax_base", 0.0) or 0.0)
            amount = float(getattr(t, "tax_amount", 0.0) or 0.0)
        taxes_list.append({"rate": rate, "base": base, "amount": amount})

    # Si no hay lista explícita, construir con totales si existen
    total_base = float(_get("total_base", 0.0) or 0.0)
    total_tax = float(_get("total_tax", 0.0) or 0.0)
    total_ret = float(_get("total_retention", 0.0) or 0.0)
    total_amount = float(_get("total_amount", 0.0) or 0.0)

    if not taxes_list:
        if total_base > 0 or total_tax > 0:
            taxes_list.append({
                "rate": 21.0,
                "base": total_base,
                "amount": total_tax
            })
        else:
            taxes_list.append({
                "rate": 21.0,
                "base": 0.0,
                "amount": 0.0
            })

    # Si total_amount no está fijado, calcularlo
    if total_amount == 0.0 and taxes_list:
        calc_base = sum(t["base"] for t in taxes_list)
        calc_tax = sum(t["amount"] for t in taxes_list)
        total_amount = round(calc_base + calc_tax - total_ret, 2)

    concept_summary = str(_get("concept_summary") or _get("concepto") or "Compra").strip()

    return {
        "fecha_str": fecha_str,
        "doc_str": doc_str,
        "cif_str": cif_str,
        "name_str": name_val,
        "cta_prov": cta_prov,
        "cta_gasto": cta_gasto,
        "taxes": taxes_list,
        "total_base": total_base,
        "total_tax": total_tax,
        "total_retention": total_ret,
        "total_amount": total_amount,
        "concept_summary": concept_summary,
        "account_digits": account_digits,
    }


def generate_a3_suenlace(
    factura: Any,
    company_code: str = "00001",
    journal_code: str = "00",
    account_digits: int = 9,
    start_seat_number: int = 1
) -> str:
    """
    Genera el contenido de ancho fijo SUENLACE.DAT para una factura en formato Wolters Kluwer A3:
    
    ALGORITMO A3SEATSPLITTER:
    - Dado que A3 (A3eco / A3innuva / A3con) solo admite un máximo de 3 líneas de desglose de IVA por asiento:
      * Si la factura tiene <= 3 tipos de IVA: genera 1 único asiento contable.
      * Si la factura tiene > 3 tipos de IVA: fragmenta la operación en 2 asientos contables vinculados:
        - Asiento 1: primeras 3 líneas de IVA, sus gastos (6XX), IVA soportado (472) y su proporción al Haber del proveedor (400/410).
        - Asiento 2: líneas restantes de IVA, sus gastos (6XX), IVA soportado (472) y el resto del saldo al Haber del proveedor.
    
    ESTRUCTURA DE REGISTROS DE ANCHO FIJO (96 caracteres):
    - Tipo 1: Cabecera de asiento (Empresa 5, Diario 2, Fecha 8 DDMMAAAA, Documento 10, Concepto 30).
    - Tipo 2: Apunte contable Debe / Haber (Empresa 5, Diario 2, Asiento 6, Fecha 8, Cuenta 12, Concepto 28, Debe 12, Haber 12, Documento 10).
    - Tipo 3: Registro fiscal de IVA (Empresa 5, Diario 2, Asiento 6, Fecha 8, Cuenta IVA 12, CIF 10, Base 12, %IVA 5, Cuota 12, Documento 10).
    
    Retorna el string completo delimitado con saltos de línea CRLF (\r\n) apto para codificar en CP1252/ANSI.
    """
    if isinstance(factura, list):
        total_content: List[str] = []
        current_seat = start_seat_number
        for inv in factura:
            seat_text = generate_a3_suenlace(
                factura=inv,
                company_code=company_code,
                journal_code=journal_code,
                account_digits=account_digits,
                start_seat_number=current_seat,
            )
            cabeceras = sum(1 for line in seat_text.splitlines() if line.startswith("1"))
            current_seat += max(1, cabeceras)
            total_content.append(seat_text)
        return "".join(total_content)

    comp_code = str(company_code).zfill(5)[:5]
    j_code = str(journal_code).zfill(2)[:2]
    data = _extract_factura_data(factura, account_digits=account_digits)

    fecha_str = data["fecha_str"]
    doc_str = data["doc_str"]
    cif_str = data["cif_str"]
    name_str = data["name_str"]
    cta_prov = data["cta_prov"]
    cta_gasto = data["cta_gasto"]
    taxes = data["taxes"]
    concept_summary = data["concept_summary"]
    digits = data["account_digits"]
    total_ret = data["total_retention"]

    lines: List[str] = []
    seat_num = start_seat_number

    # CASO 1: Más de 3 tipos de IVA -> A3SeatSplitter (Divide en 2 asientos vinculados)
    if len(taxes) > 3:
        chunks = [taxes[:3], taxes[3:]]
        total_all_base = sum(t["base"] for t in taxes) or 1.0

        for chunk_idx, chunk_taxes in enumerate(chunks, start=1):
            asiento_str = f"{seat_num:06d}"
            suffix_part = f" ({chunk_idx}/2)"
            concepto_cabecera = f"Fra. {doc_str.strip()} {name_str}{suffix_part}".ljust(30)[:30]

            # 1. Cabecera Tipo 1
            lines.append(build_a3_record([
                "1",
                comp_code,
                j_code,
                fecha_str,
                doc_str,
                concepto_cabecera
            ], 96))

            # Calcular importes del bloque
            chunk_base = sum(t["base"] for t in chunk_taxes)
            chunk_tax = sum(t["amount"] for t in chunk_taxes)

            # Retención proporcional al bloque
            if total_ret > 0:
                chunk_ret = round(total_ret * (chunk_base / total_all_base), 2)
            else:
                chunk_ret = 0.0

            chunk_prov = round(chunk_base + chunk_tax - chunk_ret, 2)

            haber_cero = f"{0.0:012.2f}"
            debe_cero = f"{0.0:012.2f}"

            # 2. Apunte de Gasto Tipo 2 (Debe)
            lines.append(build_a3_record([
                "2",
                comp_code,
                j_code,
                asiento_str,
                fecha_str,
                cta_gasto.ljust(12)[:12],
                f"Gasto {concept_summary}{suffix_part}".ljust(28)[:28],
                f"{chunk_base:012.2f}",
                haber_cero,
                doc_str
            ], 96))

            # 3. Apuntes de IVA Tipo 2 (Debe)
            for t in chunk_taxes:
                rate_val = t["rate"]
                rate_int = int(round(rate_val))
                padding_zeros = "0" * max(0, digits - 3 - len(str(rate_int)))
                cta_iva = f"472{padding_zeros}{rate_int}".ljust(12)[:12]

                lines.append(build_a3_record([
                    "2",
                    comp_code,
                    j_code,
                    asiento_str,
                    fecha_str,
                    cta_iva,
                    f"IVA Soportado {rate_int}%".ljust(28)[:28],
                    f"{t['amount']:012.2f}",
                    haber_cero,
                    doc_str
                ], 96))

            # 4. Apunte de Retención IRPF Tipo 2 (Haber) si aplica
            if chunk_ret > 0:
                zeros_ret = "0" * max(0, digits - 4)
                cta_ret = f"4751{zeros_ret}"[:digits].ljust(12)[:12]
                lines.append(build_a3_record([
                    "2",
                    comp_code,
                    j_code,
                    asiento_str,
                    fecha_str,
                    cta_ret,
                    f"Retencion IRPF{suffix_part}".ljust(28)[:28],
                    debe_cero,
                    f"{chunk_ret:012.2f}",
                    doc_str
                ], 96))

            # 5. Apunte Proveedor Tipo 2 (Haber) -> Cuadre exacto
            lines.append(build_a3_record([
                "2",
                comp_code,
                j_code,
                asiento_str,
                fecha_str,
                cta_prov.ljust(12)[:12],
                f"{name_str}{suffix_part}".ljust(28)[:28],
                debe_cero,
                f"{chunk_prov:012.2f}",
                doc_str
            ], 96))

            # 6. Registros Fiscales Tipo 3 (Máximo 3 líneas por asiento)
            for t in chunk_taxes:
                rate_val = t["rate"]
                rate_int = int(round(rate_val))
                padding_zeros = "0" * max(0, digits - 3 - len(str(rate_int)))
                cta_iva = f"472{padding_zeros}{rate_int}".ljust(12)[:12]

                lines.append(build_a3_record([
                    "3",
                    comp_code,
                    j_code,
                    asiento_str,
                    fecha_str,
                    cta_iva,
                    cif_str,
                    f"{t['base']:012.2f}",
                    f"{rate_val:05.2f}",
                    f"{t['amount']:012.2f}",
                    doc_str
                ], 96))

            seat_num += 1

    # CASO 2: 3 o menos tipos de IVA -> 1 Único Asiento
    else:
        asiento_str = f"{seat_num:06d}"
        concepto_cabecera = f"Fra. {doc_str.strip()} {name_str}".ljust(30)[:30]

        # 1. Cabecera Tipo 1
        lines.append(build_a3_record([
            "1",
            comp_code,
            j_code,
            fecha_str,
            doc_str,
            concepto_cabecera
        ], 96))

        tot_base = sum(t["base"] for t in taxes)
        tot_tax = sum(t["amount"] for t in taxes)
        prov_total = round(tot_base + tot_tax - total_ret, 2)

        haber_cero = f"{0.0:012.2f}"
        debe_cero = f"{0.0:012.2f}"

        # 2. Apunte de Gasto Tipo 2 (Debe)
        lines.append(build_a3_record([
            "2",
            comp_code,
            j_code,
            asiento_str,
            fecha_str,
            cta_gasto.ljust(12)[:12],
            f"Gasto {concept_summary}".ljust(28)[:28],
            f"{tot_base:012.2f}",
            haber_cero,
            doc_str
        ], 96))

        # 3. Apuntes de IVA Tipo 2 (Debe)
        for t in taxes:
            rate_val = t["rate"]
            rate_int = int(round(rate_val))
            padding_zeros = "0" * max(0, digits - 3 - len(str(rate_int)))
            cta_iva = f"472{padding_zeros}{rate_int}".ljust(12)[:12]

            lines.append(build_a3_record([
                "2",
                comp_code,
                j_code,
                asiento_str,
                fecha_str,
                cta_iva,
                f"IVA Soportado {rate_int}%".ljust(28)[:28],
                f"{t['amount']:012.2f}",
                haber_cero,
                doc_str
            ], 96))

        # 4. Apunte Retención IRPF (Haber) si aplica
        if total_ret > 0:
            zeros_ret = "0" * max(0, digits - 4)
            cta_ret = f"4751{zeros_ret}"[:digits].ljust(12)[:12]
            lines.append(build_a3_record([
                "2",
                comp_code,
                j_code,
                asiento_str,
                fecha_str,
                cta_ret,
                "Retencion IRPF".ljust(28)[:28],
                debe_cero,
                f"{total_ret:012.2f}",
                doc_str
            ], 96))

        # 5. Apunte Proveedor (Haber) -> Cuadre exacto
        lines.append(build_a3_record([
            "2",
            comp_code,
            j_code,
            asiento_str,
            fecha_str,
            cta_prov.ljust(12)[:12],
            name_str.ljust(28)[:28],
            debe_cero,
            f"{prov_total:012.2f}",
            doc_str
        ], 96))

        # 6. Registros Fiscales Tipo 3 (Máximo 3 líneas)
        for t in taxes:
            rate_val = t["rate"]
            rate_int = int(round(rate_val))
            padding_zeros = "0" * max(0, digits - 3 - len(str(rate_int)))
            cta_iva = f"472{padding_zeros}{rate_int}".ljust(12)[:12]

            lines.append(build_a3_record([
                "3",
                comp_code,
                j_code,
                asiento_str,
                fecha_str,
                cta_iva,
                cif_str,
                f"{t['base']:012.2f}",
                f"{rate_val:05.2f}",
                f"{t['amount']:012.2f}",
                doc_str
            ], 96))

    return "\r\n".join(lines) + "\r\n"


def generate_a3_suenlace_bytes(
    factura: Any,
    company_code: str = "00001",
    journal_code: str = "00",
    account_digits: int = 9,
    start_seat_number: int = 1
) -> bytes:
    """Retorna el contenido de generate_a3_suenlace codificado en CP1252/ANSI."""
    content_str = generate_a3_suenlace(
        factura=factura,
        company_code=company_code,
        journal_code=journal_code,
        account_digits=account_digits,
        start_seat_number=start_seat_number,
    )
    return content_str.encode("cp1252", errors="replace")


def export_invoices_to_a3_suenlace(
    invoices: List[Any],
    company_code: str = "00001",
    journal_code: str = "00",
    account_digits: int = 9
) -> str:
    """
    Exporta una colección completa de facturas procesándolas secuencialmente
    y manteniendo la numeración correlativa de asientos contables.
    """
    total_content: List[str] = []
    current_seat = 1

    for inv in invoices:
        seat_text = generate_a3_suenlace(
            factura=inv,
            company_code=company_code,
            journal_code=journal_code,
            account_digits=account_digits,
            start_seat_number=current_seat,
        )
        # Contar cuántos asientos (Tipo 1) se generaron para avanzar el contador
        cabeceras = sum(1 for line in seat_text.splitlines() if line.startswith("1"))
        current_seat += max(1, cabeceras)
        total_content.append(seat_text)

    return "".join(total_content)


def export_entries_to_a3_suenlace(
    entries: List[Any],
    company_code: str = "00001",
    journal_code: str = "00",
    account_digits: int = 9
) -> str:
    """Compatibilidad directa para exportar listas de AccountingEntryLine."""
    from app.services.exporters.a3_suenlace import export_entries_to_a3_suenlace as _exp
    return _exp(entries, company_code=company_code, journal_code=journal_code, account_digits=account_digits)


__all__ = [
    "build_a3_record",
    "generate_a3_suenlace",
    "generate_a3_suenlace_bytes",
    "export_invoices_to_a3_suenlace",
    "export_entries_to_a3_suenlace",
]
