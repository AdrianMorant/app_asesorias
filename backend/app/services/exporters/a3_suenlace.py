from typing import List
from app.models.accounting_entry import AccountingEntryLine
from app.models.invoice import Invoice

def build_a3_record(fields: List[str], expected_len: int = 96) -> str:
    """Concatena los campos y asegura una longitud fija estricta de caracteres terminada en ANSI."""
    record = "".join(fields)
    if len(record) < expected_len:
        record = record.ljust(expected_len, " ")
    elif len(record) > expected_len:
        record = record[:expected_len]
    return record

def export_entries_to_a3_suenlace(
    entries: List[AccountingEntryLine],
    company_code: str = "00001",
    journal_code: str = "00",
    account_digits: int = 9
) -> str:
    """
    Genera fichero SUENLACE.DAT con registros de cabecera y apuntes
    a partir de una lista de AccountingEntryLine.
    Longitud fija estricta por registro terminada en CRLF.
    """
    lines: List[str] = []
    comp_code = company_code.zfill(5)[:5]
    j_code = journal_code.zfill(2)[:2]

    current_entry_num = None
    for entry in entries:
        fecha_str = entry.fecha.strftime("%d%m%Y")
        asiento_str = f"{entry.entry_number:06d}"
        doc_str = (entry.documento or "FAC").ljust(10)[:10]

        # Si cambia de asiento, emitir registro de Cabecera (Tipo 1)
        if entry.entry_number != current_entry_num:
            current_entry_num = entry.entry_number
            concepto_cabecera = (entry.concepto or "ASIENTO CONTABLE").ljust(30)[:30]
            # Registro de Cabecera: Empresa (5), Diario (2), Fecha (DDMMAAAA), Documento (10), Concepto (30)
            cabecera = build_a3_record([
                "1",
                comp_code,
                j_code,
                fecha_str,
                doc_str,
                concepto_cabecera
            ], 96)
            lines.append(cabecera)

        # Registro de Apunte (Tipo 2): 400.X, 6XX, 472.X, 4751
        cta_padded = entry.subcuenta.ljust(12)[:12]
        concepto_str = entry.concepto.ljust(28)[:28]
        debe_str = f"{entry.debe:012.2f}"
        haber_str = f"{entry.haber:012.2f}"

        record_apunte = build_a3_record([
            "2",
            comp_code,
            j_code,
            asiento_str,
            fecha_str,
            cta_padded,
            concepto_str,
            debe_str,
            haber_str,
            doc_str
        ], 96)
        lines.append(record_apunte)

    return "\r\n".join(lines) + "\r\n" if lines else ""

def export_invoices_to_a3_suenlace(
    invoices: List[Invoice],
    company_code: str = "00001",
    journal_code: str = "00",
    account_digits: int = 9
) -> str:
    """
    Genera el fichero SUENLACE.DAT completo para Wolters Kluwer A3 (A3ASESOR / A3CON / A3Eco):
    - Implementa el Algoritmo A3SeatSplitter:
      * Si la factura tiene <= 3 tipos de IVA: Genera 1 único asiento.
      * Si tiene > 3 tipos de IVA: Divide la operación en 2 asientos vinculados (primeras 3 líneas
        en el asiento 1 y las restantes en el asiento 2, cuadrando ambos por separado con la cuenta del proveedor).
    - Registro de Cabecera (Tipo 1): Empresa (5 dígitos), Diario (2 dígitos), Fecha (DDMMAAAA), Documento (10 chars), Concepto (30 chars).
    - Registros de Apunte (Tipo 2): Subcuentas de proveedor (400.X), gasto (6XX) y de IVA soportado (472.X).
    - Registros Fiscales (Tipo 3): Bases imponibles y cuotas de IVA por tipo impositivo (máximo 3 por asiento).
    Longitud fija estricta de 96 caracteres por línea con terminador CRLF y codificación ANSI/CP1252.
    """
    lines: List[str] = []
    comp_code = company_code.zfill(5)[:5]
    j_code = journal_code.zfill(2)[:2]
    asiento_counter = 1

    for inv in invoices:
        fecha_obj = getattr(inv, "fecha_contable", None) or inv.issue_date
        fecha_str = fecha_obj.strftime("%d%m%Y") if fecha_obj else "01012026"
        doc_str = (inv.invoice_number or "S/N").ljust(10)[:10]
        cif_str = (inv.issuer_cif or "").ljust(10)[:10]

        taxes = list(inv.tax_breakdown) if hasattr(inv, "tax_breakdown") and inv.tax_breakdown else []

        # Obtener subcuentas de proveedor y gasto de los apuntes contables
        cta_prov = None
        cta_gasto = None
        if inv.accounting_entries:
            for e in inv.accounting_entries:
                if e.subcuenta.startswith("400") or e.subcuenta.startswith("410"):
                    cta_prov = e.subcuenta
                elif e.subcuenta.startswith("6"):
                    cta_gasto = e.subcuenta

        if not cta_prov:
            zeros = "0" * max(0, account_digits - 4)
            cta_prov = f"400{zeros}1"
        if not cta_gasto:
            zeros = "0" * max(0, account_digits - 4)
            cta_gasto = f"629{zeros}0"

        # CASO A: Factura con más de 3 tipos de IVA -> A3SeatSplitter (Divide en 2 asientos vinculados)
        if len(taxes) > 3:
            chunks = [taxes[:3], taxes[3:]]
            for chunk_idx, chunk_taxes in enumerate(chunks, start=1):
                asiento_str = f"{asiento_counter:06d}"
                suffix_part = f" ({chunk_idx}/2)"
                concepto_cabecera = (f"Fra. {inv.invoice_number or 'S/N'} {inv.issuer_name or ''}{suffix_part}").ljust(30)[:30]

                # 1. Cabecera Tipo 1
                cabecera_rec = build_a3_record([
                    "1",
                    comp_code,
                    j_code,
                    fecha_str,
                    doc_str,
                    concepto_cabecera
                ], 96)
                lines.append(cabecera_rec)

                # Calcular sumas del grupo
                chunk_base_total = sum(float(t.tax_base or 0.0) for t in chunk_taxes)
                chunk_tax_total = sum(float(t.tax_amount or 0.0) for t in chunk_taxes)

                # Calcular proporción de retención IRPF si la factura tiene retención
                chunk_retention = 0.0
                if getattr(inv, "has_retention", False) or (getattr(inv, "total_retention", 0.0) or 0.0) > 0:
                    ret_rate = getattr(inv, "retention_percentage", 0.0) or 0.0
                    if ret_rate > 0:
                        chunk_retention = round(chunk_base_total * (ret_rate / 100.0), 2)
                    elif (getattr(inv, "total_base", 0.0) or 0.0) > 0:
                        chunk_retention = round(float(inv.total_retention or 0.0) * (chunk_base_total / float(inv.total_base)), 2)

                chunk_prov_total = round(chunk_base_total + chunk_tax_total - chunk_retention, 2)

                # 2. Apunte de Gasto Tipo 2 (Debe)
                debe_gasto_str = f"{chunk_base_total:012.2f}"
                haber_cero = f"{0.0:012.2f}"
                apunte_gasto = build_a3_record([
                    "2",
                    comp_code,
                    j_code,
                    asiento_str,
                    fecha_str,
                    cta_gasto.ljust(12)[:12],
                    (f"Gasto {inv.concept_summary or ''}{suffix_part}").ljust(28)[:28],
                    debe_gasto_str,
                    haber_cero,
                    doc_str
                ], 96)
                lines.append(apunte_gasto)

                # 3. Apuntes de IVA Tipo 2 (Debe)
                for t in chunk_taxes:
                    rate_val = float(t.tax_rate or 21.0)
                    rate_int = int(round(rate_val))
                    padding_zeros = "0" * max(0, account_digits - 3 - len(str(rate_int)))
                    cta_iva = f"472{padding_zeros}{rate_int}".ljust(12)[:12]
                    t_amt = float(t.tax_amount or 0.0)

                    apunte_iva = build_a3_record([
                        "2",
                        comp_code,
                        j_code,
                        asiento_str,
                        fecha_str,
                        cta_iva,
                        f"IVA Soportado {rate_int}%".ljust(28)[:28],
                        f"{t_amt:012.2f}",
                        haber_cero,
                        doc_str
                    ], 96)
                    lines.append(apunte_iva)

                # 4. Apunte de Retención Tipo 2 (Haber) si aplica
                if chunk_retention > 0:
                    zeros_ret = "0" * max(0, account_digits - 4)
                    cta_ret = f"4751{zeros_ret}"[:account_digits].ljust(12)[:12]
                    apunte_ret = build_a3_record([
                        "2",
                        comp_code,
                        j_code,
                        asiento_str,
                        fecha_str,
                        cta_ret,
                        f"Retencion IRPF{suffix_part}".ljust(28)[:28],
                        haber_cero,
                        f"{chunk_retention:012.2f}",
                        doc_str
                    ], 96)
                    lines.append(apunte_ret)

                # 5. Apunte Proveedor Tipo 2 (Haber) -> Cuadre exacto del asiento
                apunte_prov = build_a3_record([
                    "2",
                    comp_code,
                    j_code,
                    asiento_str,
                    fecha_str,
                    cta_prov.ljust(12)[:12],
                    f"{inv.issuer_name or 'Proveedor'}{suffix_part}".ljust(28)[:28],
                    haber_cero,
                    f"{chunk_prov_total:012.2f}",
                    doc_str
                ], 96)
                lines.append(apunte_prov)

                # 6. Registros Fiscales Tipo 3 (Máximo 3 líneas)
                for t in chunk_taxes:
                    rate_val = float(t.tax_rate or 21.0)
                    rate_int = int(round(rate_val))
                    padding_zeros = "0" * max(0, account_digits - 3 - len(str(rate_int)))
                    cta_iva = f"472{padding_zeros}{rate_int}".ljust(12)[:12]

                    iva_rec = build_a3_record([
                        "3",
                        comp_code,
                        j_code,
                        asiento_str,
                        fecha_str,
                        cta_iva,
                        cif_str,
                        f"{float(t.tax_base or 0.0):012.2f}",
                        f"{rate_val:05.2f}",
                        f"{float(t.tax_amount or 0.0):012.2f}",
                        doc_str
                    ], 96)
                    lines.append(iva_rec)

                asiento_counter += 1

        # CASO B: Factura estándar (<= 3 tipos de IVA) -> 1 Asiento único
        else:
            asiento_str = f"{asiento_counter:06d}"
            concepto_cabecera = (f"Fra. {inv.invoice_number or 'S/N'} {inv.issuer_name or ''}").ljust(30)[:30]

            # 1. Cabecera Tipo 1
            cabecera_rec = build_a3_record([
                "1",
                comp_code,
                j_code,
                fecha_str,
                doc_str,
                concepto_cabecera
            ], 96)
            lines.append(cabecera_rec)

            # 2. Apuntes Tipo 2
            if inv.accounting_entries:
                for entry in inv.accounting_entries:
                    apunte_rec = build_a3_record([
                        "2",
                        comp_code,
                        j_code,
                        asiento_str,
                        fecha_str,
                        entry.subcuenta.ljust(12)[:12],
                        entry.concepto.ljust(28)[:28],
                        f"{entry.debe:012.2f}",
                        f"{entry.haber:012.2f}",
                        (entry.documento or inv.invoice_number or "").ljust(10)[:10]
                    ], 96)
                    lines.append(apunte_rec)
            else:
                # Fallback: Generar apuntes si no existen previamente
                haber_cero = f"{0.0:012.2f}"
                # Gasto
                lines.append(build_a3_record([
                    "2", comp_code, j_code, asiento_str, fecha_str,
                    cta_gasto.ljust(12)[:12],
                    (inv.concept_summary or "Gasto compra").ljust(28)[:28],
                    f"{inv.total_base:012.2f}", haber_cero, doc_str
                ], 96))
                # IVAs
                if taxes:
                    for t in taxes:
                        r_int = int(round(float(t.tax_rate or 21.0)))
                        p_zeros = "0" * max(0, account_digits - 3 - len(str(r_int)))
                        cta_iva = f"472{p_zeros}{r_int}".ljust(12)[:12]
                        lines.append(build_a3_record([
                            "2", comp_code, j_code, asiento_str, fecha_str,
                            cta_iva, f"IVA Soportado {r_int}%".ljust(28)[:28],
                            f"{float(t.tax_amount or 0.0):012.2f}", haber_cero, doc_str
                        ], 96))
                elif inv.total_tax > 0:
                    p_zeros = "0" * max(0, account_digits - 5)
                    cta_iva = f"472{p_zeros}21".ljust(12)[:12]
                    lines.append(build_a3_record([
                        "2", comp_code, j_code, asiento_str, fecha_str,
                        cta_iva, "IVA Soportado 21%".ljust(28)[:28],
                        f"{inv.total_tax:012.2f}", haber_cero, doc_str
                    ], 96))
                # Retención si hay
                if (inv.total_retention or 0.0) > 0:
                    zeros_ret = "0" * max(0, account_digits - 4)
                    cta_ret = f"4751{zeros_ret}"[:account_digits].ljust(12)[:12]
                    lines.append(build_a3_record([
                        "2", comp_code, j_code, asiento_str, fecha_str,
                        cta_ret, "Retencion IRPF".ljust(28)[:28],
                        haber_cero, f"{inv.total_retention:012.2f}", doc_str
                    ], 96))
                # Proveedor
                lines.append(build_a3_record([
                    "2", comp_code, j_code, asiento_str, fecha_str,
                    cta_prov.ljust(12)[:12],
                    (inv.issuer_name or "Proveedor").ljust(28)[:28],
                    haber_cero, f"{inv.total_amount:012.2f}", doc_str
                ], 96))

            # 3. Registros Fiscales Tipo 3 (hasta 3 tipos)
            if taxes:
                for t in taxes:
                    rate_val = float(t.tax_rate or 21.0)
                    rate_int = int(round(rate_val))
                    padding_zeros = "0" * max(0, account_digits - 3 - len(str(rate_int)))
                    cta_iva = f"472{padding_zeros}{rate_int}".ljust(12)[:12]

                    iva_rec = build_a3_record([
                        "3",
                        comp_code,
                        j_code,
                        asiento_str,
                        fecha_str,
                        cta_iva,
                        cif_str,
                        f"{float(t.tax_base or 0.0):012.2f}",
                        f"{rate_val:05.2f}",
                        f"{float(t.tax_amount or 0.0):012.2f}",
                        doc_str
                    ], 96)
                    lines.append(iva_rec)
            elif inv.total_tax and inv.total_tax > 0:
                padding_zeros = "0" * max(0, account_digits - 5)
                cta_iva = f"472{padding_zeros}21".ljust(12)[:12]
                iva_rec = build_a3_record([
                    "3",
                    comp_code,
                    j_code,
                    asiento_str,
                    fecha_str,
                    cta_iva,
                    cif_str,
                    f"{inv.total_base:012.2f}",
                    "21.00",
                    f"{inv.total_tax:012.2f}",
                    doc_str
                ], 96)
                lines.append(iva_rec)

            asiento_counter += 1

    return "\r\n".join(lines) + "\r\n" if lines else ""
