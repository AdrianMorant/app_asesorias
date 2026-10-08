"""
Módulo de Conciliación Bancaria Inteligente.
Implementa el motor de emparejamiento automático (facturas vs transacciones bancarias),
análisis de patrones de conceptos para sugerencia contable y generación de asientos de banco (572).
"""

import re
from typing import Any, Dict, List, Optional, Tuple, Union
from datetime import date, datetime, timedelta


# Reglas de patrones de texto para deducción de contrapartida bancaria en España
BANK_CONCEPT_PATTERNS: List[Dict[str, Any]] = [
    # 1. Seguridad Social y Nóminas
    {
        "patterns": [r"\bTGSS\b", r"\bSEGURIDAD\s+SOCIAL\b", r"\bSEGUROS\s+SOCIALES\b", r"\bCOTIZAC\w*\b"],
        "account_prefix": "476",
        "default_account": "47600000",
        "concept": "Liquidación Seguros Sociales (TGSS)",
        "nature": "DEBIT",  # Pago de seguros sociales
    },
    {
        "patterns": [r"\bNOMINA\b", r"\bNOMINAS\b", r"\bSALARIOS\b", r"\bREMESA\s+SUELDOS\b", r"\bTRANSFERENCIA\s+NOMINA\b"],
        "account_prefix": "465",
        "default_account": "46500000",
        "concept": "Pago nóminas y remuneraciones personal",
        "nature": "DEBIT",
    },
    # 2. Hacienda Pública e Impuestos
    {
        "patterns": [r"\bAEAT\b", r"\bAGENCIA\s+TRIBUTARIA\b", r"\bHACIENDA\b", r"\bMOD(?:ELO)?\s*(?:111|115|123)\b"],
        "account_prefix": "475",
        "default_account": "47510000",
        "concept": "Liquidación Retenciones Tributarias AEAT",
        "nature": "DEBIT",
    },
    {
        "patterns": [r"\bMOD(?:ELO)?\s*303\b", r"\bLIQUIDAC(?:ION)?\s+IVA\b"],
        "account_prefix": "475",
        "default_account": "47500000",
        "concept": "Liquidación Periódica IVA (Modelo 303)",
        "nature": "DEBIT",
    },
    {
        "patterns": [r"\bMOD(?:ELO)?\s*(?:200|202)\b", r"\bPAGO\s+FRACCIONADO\s+IS\b"],
        "account_prefix": "473",
        "default_account": "47300000",
        "concept": "Pago a cuenta Impuesto sobre Sociedades",
        "nature": "DEBIT",
    },
    # 3. Suministros (Electricidad, Gas, Agua, Comunicaciones)
    {
        "patterns": [r"\bIBERDROLA\b", r"\bENDESA\b", r"\bNATURGY\b", r"\bTOTALENERGIES\b", r"\bREPSOL\s+LUZ\b"],
        "account_prefix": "628",
        "default_account": "62800000",
        "concept": "Suministro eléctrico y energía",
        "nature": "DEBIT",
    },
    {
        "patterns": [r"\bTELEFONICA\b", r"\bMOVISTAR\b", r"\bVODAFONE\b", r"\bORANGE\b", r"\bMASMOVIL\b", r"\bDIGI\b"],
        "account_prefix": "628",
        "default_account": "62800001",
        "concept": "Suministro telecomunicaciones e Internet",
        "nature": "DEBIT",
    },
    {
        "patterns": [r"\bCANAL\s+DE\s+ISABEL\b", r"\bAGBAR\b", r"\bEMASESA\b", r"\bAQUAGEST\b", r"\bSUMINISTRO\s+AGUA\b"],
        "account_prefix": "628",
        "default_account": "62800002",
        "concept": "Suministro agua corriente",
        "nature": "DEBIT",
    },
    # 4. Gastos y Comisiones Bancarias
    {
        "patterns": [r"\bCOMISION\b", r"\bCOMISIONES\b", r"\bMANTENIMIENTO\s+CUENTA\b", r"\bADMINISTRACION\s+CUENTA\b", r"\bCUSTODIA\b"],
        "account_prefix": "626",
        "default_account": "62600000",
        "concept": "Comisiones y gastos bancarios",
        "nature": "DEBIT",
    },
    {
        "patterns": [r"\bINTERESES\s+DEUDORES\b", r"\bINTERESES\s+DESCUBIERTO\b", r"\bLIQUIDACION\s+INTERESES\b"],
        "account_prefix": "669",
        "default_account": "66900000",
        "concept": "Gastos financieros e intereses bancarios",
        "nature": "DEBIT",
    },
    {
        "patterns": [r"\bCUOTA\s+PRESTAMO\b", r"\bAMORTIZAC(?:ION)?\s+PRESTAMO\b", r"\bLEASING\b", r"\bRENTING\b"],
        "account_prefix": "520",
        "default_account": "52000000",
        "concept": "Amortización de préstamos y pólizas a C/P",
        "nature": "DEBIT",
    },
    # 5. Arrendamientos / Alquileres
    {
        "patterns": [r"\bALQUILER\b", r"\bARRENDAMIENTO\b", r"\bRENTA\s+LOCAL\b", r"\bRENTA\s+OFICINA\b"],
        "account_prefix": "621",
        "default_account": "62100000",
        "concept": "Arrendamiento inmueble u oficina",
        "nature": "DEBIT",
    },
    # 6. Combustibles y Transportes
    {
        "patterns": [r"\bREPSOL\b", r"\bCEPSA\b", r"\bBP\b", r"\bGALP\b", r"\bGASOLINERA\b", r"\bESTACION\s+SERVICIO\b"],
        "account_prefix": "629",
        "default_account": "62900001",
        "concept": "Combustibles y carburantes",
        "nature": "DEBIT",
    },
    {
        "patterns": [r"\bPEAJE\b", r"\bAUTOPISTA\b", r"\bABERTIS\b", r"\bAP-?\d+\b", r"\bVIA-?T\b"],
        "account_prefix": "629",
        "default_account": "62900002",
        "concept": "Peajes y desplazamientos de empresa",
        "nature": "DEBIT",
    },
    # 7. Servicios Profesionales
    {
        "patterns": [r"\bNOTARI\w*\b", r"\bREGISTRO\s+MERCANTIL\b", r"\bGESTORIA\b", r"\bASESORIA\b"],
        "account_prefix": "623",
        "default_account": "62300000",
        "concept": "Servicios profesionales independientes",
        "nature": "DEBIT",
    },
    # 8. Seguros
    {
        "patterns": [r"\bMAPFRE\b", r"\bALLIANZ\b", r"\bMUTUA\b", r"\bAXA\b", r"\bZURICH\b", r"\bPOLIZA\s+SEGURO\b", r"\bPRIMA\s+SEGURO\b"],
        "account_prefix": "625",
        "default_account": "62500000",
        "concept": "Primas de seguros",
        "nature": "DEBIT",
    },
]


def _normalize_date(val: Any) -> Optional[date]:
    """Convierte cualquier representación de fecha a date."""
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    if isinstance(val, str) and val.strip():
        clean = val.strip()[:10]
        # YYYY-MM-DD
        if len(clean) == 10 and clean[4] == "-" and clean[7] == "-":
            try:
                return datetime.strptime(clean, "%Y-%m-%d").date()
            except ValueError:
                pass
        # DD/MM/YYYY
        if len(clean) == 10 and clean[2] == "/" and clean[5] == "/":
            try:
                return datetime.strptime(clean, "%d/%m/%Y").date()
            except ValueError:
                pass
    return None


def _format_account(base_prefix: str, account_digits: int = 9, suffix: str = "0") -> str:
    """Ajusta una subcuenta al número de dígitos del plan contable de la empresa."""
    needed_zeros = max(0, account_digits - len(base_prefix) - len(suffix))
    return f"{base_prefix}{'0' * needed_zeros}{suffix}"[:account_digits]


def _get_field(obj: Any, key: str, default: Any = None) -> Any:
    """Accede a un campo admitiendo objetos o diccionarios."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def suggest_account_by_concept(
    concept: str,
    account_digits: int = 9
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Analiza la descripción bancaria mediante expresiones regulares para sugerir
    la contrapartida contable estándar en España.
    Retorna: (subcuenta_sugerida, concepto_sugerido, prefijo) o (None, None, None)
    """
    if not concept:
        return None, None, None

    normalized_concept = concept.upper()

    for rule in BANK_CONCEPT_PATTERNS:
        for pat in rule["patterns"]:
            if re.search(pat, normalized_concept, re.IGNORECASE):
                prefix = rule["account_prefix"]
                # Formatear la subcuenta con la longitud exacta requerida
                account = _format_account(prefix, account_digits=account_digits, suffix="0")
                return account, rule["concept"], prefix

    return None, None, None


def match_bank_transactions(
    transactions: List[Any],
    invoices: List[Any],
    date_margin_days: int = 5,
    account_digits: int = 9
) -> List[Dict[str, Any]]:
    """
    Detección y Emparejamiento Automático de movimientos bancarios contra facturas:
    
    1. Si el importe bancario y la fecha (con margen configurable de +-date_margin_days)
       coinciden exactamente con una factura aprobada:
       - Marca el estado como 'PREVALIDADO'.
       - Asocia 'invoice_id' y los datos de la factura vinculada.
       - Subcuenta sugerida: la cuenta de proveedor (400/410) o cliente (430) de la factura.
       
    2. Si no hay factura coincidente:
       - Analiza el texto del concepto bancario mediante patrones para sugerir
         la contrapartida contable (ej. 'TGSS' -> 47600000, 'IBERDROLA' -> 62800000).
       - Marca el estado como 'SUGERIDO' si encontró patrón, o 'PENDIENTE' si no.
       
    Retorna la lista de transacciones enriquecidas con el resultado del emparejamiento.
    """
    results: List[Dict[str, Any]] = []
    
    # Preparar facturas disponibles para evitar doble asignación
    available_invoices = []
    for inv in invoices:
        inv_id = _get_field(inv, "id")
        inv_date = _normalize_date(
            _get_field(inv, "fecha_contable") or _get_field(inv, "issue_date") or _get_field(inv, "due_date") or _get_field(inv, "fecha")
        )
        inv_amount = float(_get_field(inv, "total_amount", 0.0) or 0.0)
        inv_num = _get_field(inv, "invoice_number") or _get_field(inv, "documento") or "S/N"
        issuer_name = _get_field(inv, "issuer_name") or _get_field(inv, "proveedor") or "Proveedor"
        
        # Subcuenta del proveedor/cliente si existe
        cta_prov = _get_field(inv, "supplier_account") or _get_field(inv, "cta_prov")
        entries = None
        if isinstance(inv, dict):
            entries = inv.get("accounting_entries")
        elif "accounting_entries" in getattr(inv, "__dict__", {}):
            entries = getattr(inv, "accounting_entries", None)

        if entries:
            for e in entries:
                sc = _get_field(e, "subcuenta", "")
                if sc.startswith("400") or sc.startswith("410") or sc.startswith("430"):
                    cta_prov = sc
                    break

        if not cta_prov:
            cta_prov = _format_account("400", account_digits=account_digits, suffix="1")

        available_invoices.append({
            "raw": inv,
            "id": inv_id,
            "date": inv_date,
            "amount": abs(round(inv_amount, 2)),
            "number": inv_num,
            "party_name": issuer_name,
            "account": cta_prov,
            "matched": False,
        })

    for tx in transactions:
        tx_id = _get_field(tx, "id")
        tx_date = _normalize_date(_get_field(tx, "date") or _get_field(tx, "fecha") or _get_field(tx, "value_date"))
        raw_amount = float(_get_field(tx, "amount") or _get_field(tx, "importe") or 0.0)
        tx_abs_amount = abs(round(raw_amount, 2))
        tx_desc = str(_get_field(tx, "description") or _get_field(tx, "concepto") or "").strip()

        matched_invoice_info = None

        # 1. Búsqueda de coincidencia exacta con facturas (importe exacto + rango de fechas)
        if tx_date and tx_abs_amount > 0.001:
            best_candidate = None
            min_day_diff = 999999

            for inv_info in available_invoices:
                if inv_info["matched"]:
                    continue

                # Coincidencia exacta de importe al céntimo
                if abs(tx_abs_amount - inv_info["amount"]) < 0.01:
                    # Comprobación de margen de fechas
                    if inv_info["date"]:
                        diff_days = abs((tx_date - inv_info["date"]).days)
                        if diff_days <= date_margin_days:
                            if diff_days < min_day_diff:
                                min_day_diff = diff_days
                                best_candidate = inv_info

            if best_candidate:
                best_candidate["matched"] = True
                matched_invoice_info = best_candidate

        # Construir resultado para la transacción
        if matched_invoice_info:
            res_item = {
                "transaction_id": tx_id,
                "date": tx_date.isoformat() if tx_date else None,
                "amount": raw_amount,
                "description": tx_desc,
                "status": "PREVALIDADO",
                "match_type": "EXACT_INVOICE",
                "invoice_id": matched_invoice_info["id"],
                "invoice_number": matched_invoice_info["number"],
                "matched_party": matched_invoice_info["party_name"],
                "counterpart_account": matched_invoice_info["account"],
                "suggested_concept": f"Pago Fra. {matched_invoice_info['number']} {matched_invoice_info['party_name']}",
                "confidence": 0.98,
                "notes": f"Emparejado automáticamente con factura {matched_invoice_info['number']} (Diferencia: {min_day_diff} días)",
            }
        else:
            # 2. Análisis por patrones de texto bancarios
            suggested_cta, suggested_concept, prefix = suggest_account_by_concept(
                concept=tx_desc,
                account_digits=account_digits
            )

            if suggested_cta:
                res_item = {
                    "transaction_id": tx_id,
                    "date": tx_date.isoformat() if tx_date else None,
                    "amount": raw_amount,
                    "description": tx_desc,
                    "status": "SUGERIDO",
                    "match_type": "PATTERN_RULE",
                    "invoice_id": None,
                    "invoice_number": None,
                    "matched_party": None,
                    "counterpart_account": suggested_cta,
                    "suggested_concept": suggested_concept,
                    "confidence": 0.85,
                    "notes": f"Contrapartida deducida por regla patrón: {suggested_concept}",
                }
            else:
                default_555 = _format_account("555", account_digits=account_digits, suffix="0")
                res_item = {
                    "transaction_id": tx_id,
                    "date": tx_date.isoformat() if tx_date else None,
                    "amount": raw_amount,
                    "description": tx_desc,
                    "status": "PENDIENTE",
                    "match_type": "UNMATCHED",
                    "invoice_id": None,
                    "invoice_number": None,
                    "matched_party": None,
                    "counterpart_account": default_555,
                    "suggested_concept": tx_desc or "Movimiento bancario pendiente",
                    "confidence": 0.0,
                    "notes": "Sin factura vinculada ni regla de concepto aplicable.",
                }

        results.append(res_item)

    return results


def build_bank_entry(
    transaction: Any,
    account_number: str = "57200000",
    account_digits: int = 9,
    entry_number: int = 1
) -> Dict[str, Any]:
    """
    Genera el asiento contable de banco (partida doble estricta) para previsualización o contabilización:
    - Banco (572):
      * Debe: Si es un Cobro / Ingreso bancario (amount > 0).
      * Haber: Si es un Pago / Gasto bancario (amount < 0).
    - Contrapartida:
      * Subcuenta del proveedor/cliente (400/410/430) o gasto directo deducido:
        - Si es Pago: Contrapartida al Debe.
        - Si es Cobro: Contrapartida al Haber.
    - Cuadre exacto: Total Debe == Total Haber.
    """
    raw_amount = float(_get_field(transaction, "amount") or _get_field(transaction, "importe") or 0.0)
    abs_amount = round(abs(raw_amount), 2)

    tx_date = _normalize_date(_get_field(transaction, "date") or _get_field(transaction, "fecha"))
    date_str = tx_date.strftime("%d/%m/%Y") if tx_date else "01/01/2026"

    desc = str(_get_field(transaction, "description") or _get_field(transaction, "concepto") or "Movimiento bancario").strip()
    doc_ref = str(_get_field(transaction, "invoice_number") or _get_field(transaction, "documento") or "BANCO")[:20]

    # Subcuenta bancaria formateada con los dígitos correctos
    bank_clean = account_number.replace(".", "").strip()
    bank_account = _format_account(bank_clean[:3] or "572", account_digits=account_digits, suffix=bank_clean[3:] or "0")

    # Contrapartida informada o sugerida
    counterpart = _get_field(transaction, "counterpart_account") or _get_field(transaction, "contrapartida")
    if not counterpart:
        # Intentar deducir por concepto
        suggested_cta, _, _ = suggest_account_by_concept(desc, account_digits=account_digits)
        counterpart = suggested_cta or _format_account("555", account_digits=account_digits, suffix="0")

    concept_line = (_get_field(transaction, "suggested_concept") or desc)[:50]

    lines = []

    # CASO A: Cobro / Ingreso bancario (amount >= 0)
    # Banco al Debe, Contrapartida (Cliente/Ingreso) al Haber
    if raw_amount >= 0:
        # Línea 1: Debe Banco
        lines.append({
            "entry_number": entry_number,
            "line_number": 1,
            "subcuenta": bank_account,
            "concepto": concept_line,
            "debe": abs_amount,
            "haber": 0.0,
            "documento": doc_ref,
        })
        # Línea 2: Haber Contrapartida
        lines.append({
            "entry_number": entry_number,
            "line_number": 2,
            "subcuenta": counterpart,
            "concepto": concept_line,
            "debe": 0.0,
            "haber": abs_amount,
            "documento": doc_ref,
        })
        total_debe = abs_amount
        total_haber = abs_amount

    # CASO B: Pago / Gasto bancario (amount < 0)
    # Contrapartida (Proveedor/Gasto) al Debe, Banco al Haber
    else:
        # Línea 1: Debe Contrapartida
        lines.append({
            "entry_number": entry_number,
            "line_number": 1,
            "subcuenta": counterpart,
            "concepto": concept_line,
            "debe": abs_amount,
            "haber": 0.0,
            "documento": doc_ref,
        })
        # Línea 2: Haber Banco
        lines.append({
            "entry_number": entry_number,
            "line_number": 2,
            "subcuenta": bank_account,
            "concepto": concept_line,
            "debe": 0.0,
            "haber": abs_amount,
            "documento": doc_ref,
        })
        total_debe = abs_amount
        total_haber = abs_amount

    return {
        "entry_number": entry_number,
        "date": date_str,
        "concept": concept_line,
        "document": doc_ref,
        "total_debe": total_debe,
        "total_haber": total_haber,
        "is_balanced": abs(total_debe - total_haber) < 0.001,
        "lines": lines,
    }


__all__ = [
    "BANK_CONCEPT_PATTERNS",
    "suggest_account_by_concept",
    "match_bank_transactions",
    "build_bank_entry",
]
