"""
Módulo de Exportación Contable para Sage (Sage 50 / Sage Despachos Connected).
Genera el fichero CSV compatible con la plantilla estándar oficial de importación de asientos.
Formato de cabecera: Canal;Asiento;Fecha;Cuenta;Concepto;Debe;Haber;Contrapartida;Base;CuotaIva;Factura
"""

import csv
import io
from typing import Any, Dict, List, Optional, Union
from datetime import date, datetime


def _fmt_amount(val: Union[float, int, None]) -> str:
    """Formatea un número con 2 decimales y coma como separador decimal."""
    if val is None or abs(float(val)) < 0.0001:
        return "0,00"
    return f"{float(val):.2f}".replace(".", ",")


def _format_date(fecha_val: Any) -> str:
    """Convierte fechas a formato DD/MM/AAAA."""
    if isinstance(fecha_val, (date, datetime)):
        return fecha_val.strftime("%d/%m/%Y")
    if isinstance(fecha_val, str) and fecha_val.strip():
        val = fecha_val.strip()
        if len(val) == 10 and val[4] == "-" and val[7] == "-":
            parts = val.split("-")
            return f"{parts[2]}/{parts[1]}/{parts[0]}"
        if len(val) == 10 and val[2] == "/" and val[5] == "/":
            return val
    return "01/01/2026"


def _extract_invoice_fields(inv: Any, account_digits: int = 9) -> Dict[str, Any]:
    """Extrae y normaliza los datos de la factura admitiendo modelos SQLAlchemy, dicts o DTOs."""
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

    entries = _get("accounting_entries")
    if entries:
        for e in entries:
            sc = getattr(e, "subcuenta", "") or (e.get("subcuenta", "") if isinstance(e, dict) else "")
            if sc.startswith("400") or sc.startswith("410"):
                cta_prov = sc
            elif sc.startswith("6"):
                cta_gasto = sc

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


def generate_sage_csv(
    invoices: Union[List[Any], Any],
    company_code: str = "001",
    channel: str = "0",
    account_digits: int = 9,
    start_seat_number: int = 1
) -> str:
    """
    Genera el fichero CSV compatible con la plantilla estándar oficial de importación de asientos de Sage:
    - Columnas: Canal;Asiento;Fecha;Cuenta;Concepto;Debe;Haber;Contrapartida;Base;CuotaIva;Factura
    - Delimitador: Punto y coma (;)
    - Terminador: CRLF (\r\n)
    - Formato de fecha: DD/MM/AAAA
    - Importes con 2 decimales y coma como separador decimal.
    - Partida doble estricta: Proveedor (400/410), Gasto (6XX), IVA Soportado (472) y Retención (4751 si aplica).
    """
    if not isinstance(invoices, list):
        invoices_list = [invoices]
    else:
        invoices_list = invoices

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";", lineterminator="\r\n")

    # Cabecera estándar de importación Sage
    writer.writerow([
        "Canal",
        "Asiento",
        "Fecha",
        "Cuenta",
        "Concepto",
        "Debe",
        "Haber",
        "Contrapartida",
        "Base",
        "CuotaIva",
        "Factura"
    ])

    ch = str(channel).strip() or "0"
    asiento_num = start_seat_number

    for inv in invoices_list:
        data = _extract_invoice_fields(inv, account_digits=account_digits)
        fecha_str = data["fecha_str"]
        doc_num = data["doc_num"][:30]
        asiento_str = str(asiento_num)
        cta_prov = data["cta_prov"]
        cta_gasto = data["cta_gasto"]
        concept_base = (f"Fra. {data['doc_num']} {data['name_str']}")[:60]

        entries = data["entries"]
        if entries:
            # Si existen apuntes ya calculados
            for e in entries:
                if isinstance(e, dict):
                    cta = str(e.get("subcuenta", ""))
                    con = str(e.get("concepto") or concept_base)[:60]
                    debe = float(e.get("debe", 0.0) or 0.0)
                    haber = float(e.get("haber", 0.0) or 0.0)
                    doc_line = str(e.get("documento") or doc_num)[:30]
                else:
                    cta = str(getattr(e, "subcuenta", ""))
                    con = str(getattr(e, "concepto", "") or concept_base)[:60]
                    debe = float(getattr(e, "debe", 0.0) or 0.0)
                    haber = float(getattr(e, "haber", 0.0) or 0.0)
                    doc_line = str(getattr(e, "documento", "") or doc_num)[:30]

                # Asignación de contrapartida, Base y CuotaIva según la cuenta
                if cta.startswith("400") or cta.startswith("410"):
                    contrapartida = cta_gasto
                    line_base = "0,00"
                    line_cuota = "0,00"
                elif cta.startswith("472"):
                    contrapartida = cta_prov
                    line_base = _fmt_amount(data["total_base"])
                    line_cuota = _fmt_amount(debe)
                elif cta.startswith("6"):
                    contrapartida = cta_prov
                    line_base = _fmt_amount(debe)
                    line_cuota = "0,00"
                else:
                    contrapartida = cta_prov
                    line_base = "0,00"
                    line_cuota = "0,00"

                writer.writerow([
                    ch,
                    asiento_str,
                    fecha_str,
                    cta,
                    con,
                    _fmt_amount(debe),
                    _fmt_amount(haber),
                    contrapartida,
                    line_base,
                    line_cuota,
                    doc_line
                ])
        else:
            # Autogeneración de la partida doble para Sage
            tot_base = sum(t["base"] for t in data["taxes"])
            tot_tax = sum(t["amount"] for t in data["taxes"])
            tot_ret = data["total_retention"]
            prov_amount = data["total_amount"] or round(tot_base + tot_tax - tot_ret, 2)

            # 1. Apunte de Gasto (6XX) -> Debe
            writer.writerow([
                ch,
                asiento_str,
                fecha_str,
                cta_gasto,
                (f"Gasto {data['concept']}")[:60],
                _fmt_amount(tot_base),
                "0,00",
                cta_prov,
                _fmt_amount(tot_base),
                "0,00",
                doc_num
            ])

            # 2. Apuntes de IVA Soportado (472) -> Debe
            for t in data["taxes"]:
                rate_int = int(round(t["rate"]))
                padding_zeros = "0" * max(0, account_digits - 3 - len(str(rate_int)))
                cta_iva = f"472{padding_zeros}{rate_int}"

                writer.writerow([
                    ch,
                    asiento_str,
                    fecha_str,
                    cta_iva,
                    f"IVA Soportado {rate_int}%"[:60],
                    _fmt_amount(t["amount"]),
                    "0,00",
                    cta_prov,
                    _fmt_amount(t["base"]),
                    _fmt_amount(t["amount"]),
                    doc_num
                ])

            # 3. Apunte de Retención IRPF (4751) -> Haber (si aplica)
            if tot_ret > 0:
                zeros_ret = "0" * max(0, account_digits - 4)
                cta_ret = f"4751{zeros_ret}"[:account_digits]

                writer.writerow([
                    ch,
                    asiento_str,
                    fecha_str,
                    cta_ret,
                    "Retencion IRPF"[:60],
                    "0,00",
                    _fmt_amount(tot_ret),
                    cta_prov,
                    "0,00",
                    "0,00",
                    doc_num
                ])

            # 4. Apunte Proveedor (400/410) -> Haber
            writer.writerow([
                ch,
                asiento_str,
                fecha_str,
                cta_prov,
                (f"{data['name_str']}")[:60],
                "0,00",
                _fmt_amount(prov_amount),
                cta_gasto,
                "0,00",
                "0,00",
                doc_num
            ])

        asiento_num += 1

    return output.getvalue()


def generate_sage_csv_bytes(
    invoices: Union[List[Any], Any],
    company_code: str = "001",
    channel: str = "0",
    account_digits: int = 9,
    start_seat_number: int = 1
) -> bytes:
    """Genera el contenido CSV de Sage codificado en Latin-1 / ANSI para importación directa."""
    content = generate_sage_csv(
        invoices=invoices,
        company_code=company_code,
        channel=channel,
        account_digits=account_digits,
        start_seat_number=start_seat_number
    )
    return content.encode("latin-1", errors="replace")


def export_invoices_to_sage_csv(invoices: List[Any], channel: str = "0") -> str:
    """Función de compatibilidad para exportar asientos desde facturas."""
    return generate_sage_csv(invoices, channel=channel)


def export_entries_to_sage_csv(entries: List[Any], channel: str = "0") -> str:
    """Función de compatibilidad para exportar asientos directos."""
    from app.services.exporters.sage_csv import export_entries_to_sage_csv as _exp
    return _exp(entries, channel=channel)


__all__ = [
    "generate_sage_csv",
    "generate_sage_csv_bytes",
    "export_invoices_to_sage_csv",
    "export_entries_to_sage_csv",
]
