"""
Módulo de Exportación Contable para Contasol (Software DELSOL).
Genera el fichero estructurado de importación de diario delimitado por punto y coma (;).
Formato oficial: Diario;Fecha;Asiento;Cuenta;Concepto;Documento;Debe;Haber
"""

import csv
import io
from typing import Any, Dict, List, Optional, Union
from datetime import date, datetime


def _fmt_amount(val: Union[float, int, None]) -> str:
    """Formatea un número flotante con 2 decimales y coma como separador decimal."""
    if val is None or abs(float(val)) < 0.0001:
        return "0,00"
    return f"{float(val):.2f}".replace(".", ",")


def _format_date(fecha_val: Any) -> str:
    """Convierte fechas a formato DD/MM/AAAA."""
    if isinstance(fecha_val, (date, datetime)):
        return fecha_val.strftime("%d/%m/%Y")
    if isinstance(fecha_val, str) and fecha_val.strip():
        val = fecha_val.strip()
        # Si ya viene en formato YYYY-MM-DD
        if len(val) == 10 and val[4] == "-" and val[7] == "-":
            parts = val.split("-")
            return f"{parts[2]}/{parts[1]}/{parts[0]}"
        # Si ya viene en DD/MM/YYYY
        if len(val) == 10 and val[2] == "/" and val[5] == "/":
            return val
    return "01/01/2026"


def _extract_invoice_fields(inv: Any, account_digits: int = 9) -> Dict[str, Any]:
    """Extrae y normaliza los campos de una factura (admite modelo SQLAlchemy, dict u objeto)."""
    def _get(key: str, default: Any = None):
        if isinstance(inv, dict):
            return inv.get(key, default)
        return getattr(inv, key, default)

    fecha_val = _get("fecha_contable") or _get("issue_date") or _get("fecha")
    fecha_str = _format_date(fecha_val)

    doc_num = str(_get("invoice_number") or _get("documento") or _get("numero") or "S/N").strip()
    cif_str = str(_get("issuer_cif") or _get("cif") or _get("nif") or "").strip()
    name_str = str(_get("issuer_name") or _get("nombre") or _get("proveedor") or "Proveedor").strip()
    concept = str(_get("concept_summary") or _get("concepto") or f"Fra. {doc_num} {name_str}").strip()

    zeros = "0" * max(0, account_digits - 4)
    cta_prov = str(_get("supplier_account") or _get("cta_prov") or f"400{zeros}1").strip()
    cta_gasto = str(_get("expense_account") or _get("cta_gasto") or f"629{zeros}0").strip()

    # Si hay accounting_entries definidos
    entries = _get("accounting_entries")
    if entries:
        for e in entries:
            sc = getattr(e, "subcuenta", "") or (e.get("subcuenta", "") if isinstance(e, dict) else "")
            if sc.startswith("400") or sc.startswith("410"):
                cta_prov = sc
            elif sc.startswith("6"):
                cta_gasto = sc

    # Extraer líneas de impuestos / IVA
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

    total_base = float(_get("total_base", 0.0) or 0.0)
    total_tax = float(_get("total_tax", 0.0) or 0.0)
    total_ret = float(_get("total_retention", 0.0) or 0.0)
    total_amount = float(_get("total_amount", 0.0) or 0.0)

    if not taxes_list:
        if total_base > 0 or total_tax > 0:
            taxes_list.append({"rate": 21.0, "base": total_base, "amount": total_tax})
        else:
            taxes_list.append({"rate": 21.0, "base": 0.0, "amount": 0.0})

    if total_amount == 0.0 and taxes_list:
        calc_base = sum(t["base"] for t in taxes_list)
        calc_tax = sum(t["amount"] for t in taxes_list)
        total_amount = round(calc_base + calc_tax - total_ret, 2)

    return {
        "fecha_str": fecha_str,
        "doc_num": doc_num,
        "cif_str": cif_str,
        "name_str": name_str,
        "concept": concept,
        "cta_prov": cta_prov,
        "cta_gasto": cta_gasto,
        "taxes": taxes_list,
        "total_base": total_base,
        "total_tax": total_tax,
        "total_retention": total_ret,
        "total_amount": total_amount,
        "entries": entries,
    }


def generate_contasol_csv(
    invoices: Union[List[Any], Any],
    company_code: str = "1",
    journal_code: str = "1",
    account_digits: int = 9,
    start_seat_number: int = 1
) -> str:
    """
    Genera el archivo CSV estructurado para la importación del Diario oficial de Contasol (Software DELSOL):
    - Columnas: Diario;Fecha;Asiento;Cuenta;Concepto;Documento;Debe;Haber
    - Separador: Punto y coma (;)
    - Fechas: DD/MM/AAAA
    - Importes: 2 decimales y coma como separador decimal.
    - Genera la partida doble completa por cada factura:
      * Gasto (6XX) al Debe
      * IVA Soportado (472) al Debe
      * Retención IRPF (4751) al Haber (si aplica)
      * Proveedor (400/410) al Haber
    """
    if not isinstance(invoices, list):
        invoices_list = [invoices]
    else:
        invoices_list = invoices

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";", lineterminator="\r\n")

    # Cabecera estándar exigida por Contasol
    writer.writerow([
        "Diario",
        "Fecha",
        "Asiento",
        "Cuenta",
        "Concepto",
        "Documento",
        "Debe",
        "Haber"
    ])

    seat_num = start_seat_number
    j_code = str(journal_code).strip() or "1"

    for inv in invoices_list:
        data = _extract_invoice_fields(inv, account_digits=account_digits)
        fecha_str = data["fecha_str"]
        doc_num = data["doc_num"][:20]
        concept_base = (f"Fra. {data['doc_num']} {data['name_str']}")[:50]
        asiento_str = str(seat_num)

        # Si la factura ya cuenta con líneas contables explícitas, utilizarlas
        entries = data["entries"]
        if entries:
            for e in entries:
                if isinstance(e, dict):
                    cta = str(e.get("subcuenta", ""))
                    con = str(e.get("concepto") or concept_base)[:50]
                    debe = float(e.get("debe", 0.0) or 0.0)
                    haber = float(e.get("haber", 0.0) or 0.0)
                    doc_line = str(e.get("documento") or doc_num)[:20]
                else:
                    cta = str(getattr(e, "subcuenta", ""))
                    con = str(getattr(e, "concepto", "") or concept_base)[:50]
                    debe = float(getattr(e, "debe", 0.0) or 0.0)
                    haber = float(getattr(e, "haber", 0.0) or 0.0)
                    doc_line = str(getattr(e, "documento", "") or doc_num)[:20]

                writer.writerow([
                    j_code,
                    fecha_str,
                    asiento_str,
                    cta,
                    con,
                    doc_line,
                    _fmt_amount(debe),
                    _fmt_amount(haber)
                ])
        else:
            # Autogeneración de la partida doble para Contasol
            tot_base = sum(t["base"] for t in data["taxes"])
            tot_tax = sum(t["amount"] for t in data["taxes"])
            tot_ret = data["total_retention"]
            prov_amount = data["total_amount"] or round(tot_base + tot_tax - tot_ret, 2)

            # 1. Apunte de Gasto (6XX) -> Debe
            writer.writerow([
                j_code,
                fecha_str,
                asiento_str,
                data["cta_gasto"],
                (f"Gasto {data['concept']}")[:50],
                doc_num,
                _fmt_amount(tot_base),
                "0,00"
            ])

            # 2. Apuntes de IVA Soportado (472) -> Debe
            for t in data["taxes"]:
                rate_int = int(round(t["rate"]))
                padding_zeros = "0" * max(0, account_digits - 3 - len(str(rate_int)))
                cta_iva = f"472{padding_zeros}{rate_int}"

                writer.writerow([
                    j_code,
                    fecha_str,
                    asiento_str,
                    cta_iva,
                    f"IVA Soportado {rate_int}%"[:50],
                    doc_num,
                    _fmt_amount(t["amount"]),
                    "0,00"
                ])

            # 3. Apunte de Retención IRPF (4751) -> Haber (si aplica)
            if tot_ret > 0:
                zeros_ret = "0" * max(0, account_digits - 4)
                cta_ret = f"4751{zeros_ret}"[:account_digits]

                writer.writerow([
                    j_code,
                    fecha_str,
                    asiento_str,
                    cta_ret,
                    "Retencion IRPF"[:50],
                    doc_num,
                    "0,00",
                    _fmt_amount(tot_ret)
                ])

            # 4. Apunte Proveedor (400/410) -> Haber
            writer.writerow([
                j_code,
                fecha_str,
                asiento_str,
                data["cta_prov"],
                (f"{data['name_str']}")[:50],
                doc_num,
                "0,00",
                _fmt_amount(prov_amount)
            ])

        seat_num += 1

    return output.getvalue()


def generate_contasol_csv_bytes(
    invoices: Union[List[Any], Any],
    company_code: str = "1",
    journal_code: str = "1",
    account_digits: int = 9,
    start_seat_number: int = 1
) -> bytes:
    """Genera el contenido CSV de Contasol codificado en Latin-1 / ANSI para importación directa."""
    content = generate_contasol_csv(
        invoices=invoices,
        company_code=company_code,
        journal_code=journal_code,
        account_digits=account_digits,
        start_seat_number=start_seat_number
    )
    return content.encode("latin-1", errors="replace")


def export_entries_to_contasol_csv(entries: List[Any], journal_code: str = "1") -> str:
    """Genera CSV de diario a partir de una lista directa de AccountingEntryLine."""
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";", lineterminator="\r\n")

    writer.writerow([
        "Diario",
        "Fecha",
        "Asiento",
        "Cuenta",
        "Concepto",
        "Documento",
        "Debe",
        "Haber"
    ])

    for entry in entries:
        if isinstance(entry, dict):
            f_val = entry.get("fecha")
            asiento_val = str(entry.get("entry_number", "1"))
            cta = str(entry.get("subcuenta", ""))
            con = str(entry.get("concepto", ""))[:50]
            doc = str(entry.get("documento", "") or "")[:20]
            debe = float(entry.get("debe", 0.0) or 0.0)
            haber = float(entry.get("haber", 0.0) or 0.0)
        else:
            f_val = getattr(entry, "fecha", None)
            asiento_val = str(getattr(entry, "entry_number", "1"))
            cta = str(getattr(entry, "subcuenta", ""))
            con = str(getattr(entry, "concepto", "") or "")[:50]
            doc = str(getattr(entry, "documento", "") or "")[:20]
            debe = float(getattr(entry, "debe", 0.0) or 0.0)
            haber = float(getattr(entry, "haber", 0.0) or 0.0)

        fecha_str = _format_date(f_val)
        writer.writerow([
            journal_code,
            fecha_str,
            asiento_val,
            cta,
            con,
            doc,
            _fmt_amount(debe),
            _fmt_amount(haber)
        ])

    return output.getvalue()


def export_invoices_to_contasol_vat_csv(invoices: List[Any]) -> str:
    """Genera el fichero de registros de IVA soportado de Contasol (Software DELSOL)."""
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";", lineterminator="\r\n")

    writer.writerow([
        "Factura",
        "Fecha",
        "NIF Emisor",
        "Nombre Emisor",
        "Base Imponible",
        "% IVA",
        "Cuota IVA",
        "Clave Operacion",
        "Cuenta Proveedor"
    ])

    for inv in invoices:
        data = _extract_invoice_fields(inv)
        for t in data["taxes"]:
            writer.writerow([
                data["doc_num"][:20],
                data["fecha_str"],
                data["cif_str"][:15],
                data["name_str"][:50],
                _fmt_amount(t["base"]),
                _fmt_amount(t["rate"]),
                _fmt_amount(t["amount"]),
                "1",  # Clave 1: Régimen General habitual
                data["cta_prov"]
            ])

    return output.getvalue()


def export_invoices_to_contasol_csv(invoices: List[Any], journal_code: str = "1") -> str:
    """Función de compatibilidad que redirige a generate_contasol_csv."""
    return generate_contasol_csv(invoices, journal_code=journal_code)


__all__ = [
    "generate_contasol_csv",
    "generate_contasol_csv_bytes",
    "export_entries_to_contasol_csv",
    "export_invoices_to_contasol_vat_csv",
    "export_invoices_to_contasol_csv",
]
