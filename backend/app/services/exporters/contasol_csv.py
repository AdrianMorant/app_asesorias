import csv
import io
from typing import List
from app.models.accounting_entry import AccountingEntryLine
from app.models.invoice import Invoice

def export_entries_to_contasol_csv(entries: List[AccountingEntryLine], journal_code: str = "1") -> str:
    """
    Genera un archivo CSV compatible con la importación del Diario de Contasol (Software DELSOL).
    Formato oficial: Diario;Fecha;Asiento;Cuenta;Concepto;Documento;Debe;Haber
    """
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";", lineterminator="\r\n")

    # Cabecera estándar Contasol Diario
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
        fecha_str = entry.fecha.strftime("%d/%m/%Y")
        debe_str = f"{entry.debe:.2f}".replace(".", ",") if entry.debe > 0 else "0,00"
        haber_str = f"{entry.haber:.2f}".replace(".", ",") if entry.haber > 0 else "0,00"

        writer.writerow([
            journal_code,
            fecha_str,
            str(entry.entry_number),
            entry.subcuenta,
            entry.concepto[:50],  # Longitud máxima concepto Contasol
            (entry.documento or "")[:20],
            debe_str,
            haber_str
        ])

    return output.getvalue()


def export_invoices_to_contasol_vat_csv(invoices: List[Invoice]) -> str:
    """
    Genera el fichero de registros de IVA soportado de Contasol (Software DELSOL):
    Factura;Fecha;NIF Emisor;Nombre Emisor;Base Imponible;% IVA;Cuota IVA;Clave Operación;Cuenta Proveedor
    Clave Operación oficial: '1' (Régimen general / Operaciones interiores)
    """
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
        fecha_obj = getattr(inv, "fecha_contable", None) or inv.issue_date
        fecha_str = fecha_obj.strftime("%d/%m/%Y") if fecha_obj else "01/01/2026"
        doc_str = inv.invoice_number or "S/N"
        cif_str = inv.issuer_cif or ""
        name_str = inv.issuer_name or ""
        
        # Obtener cuenta del proveedor
        cta_prov = "400000000"
        if inv.accounting_entries:
            for e in inv.accounting_entries:
                if e.subcuenta.startswith("400") or e.subcuenta.startswith("410"):
                    cta_prov = e.subcuenta
                    break

        if hasattr(inv, "tax_breakdown") and inv.tax_breakdown:
            for t in inv.tax_breakdown:
                base_str = f"{float(t.tax_base or 0.0):.2f}".replace(".", ",")
                rate_str = f"{float(t.tax_rate or 21.0):.2f}".replace(".", ",")
                cuota_str = f"{float(t.tax_amount or 0.0):.2f}".replace(".", ",")
                writer.writerow([
                    doc_str,
                    fecha_str,
                    cif_str,
                    name_str[:50],
                    base_str,
                    rate_str,
                    cuota_str,
                    "1",  # Clave 1: Operación interior habitual
                    cta_prov
                ])
        else:
            base_str = f"{inv.total_base:.2f}".replace(".", ",")
            cuota_str = f"{inv.total_tax:.2f}".replace(".", ",")
            writer.writerow([
                doc_str,
                fecha_str,
                cif_str,
                name_str[:50],
                base_str,
                "21,00",
                cuota_str,
                "1",
                cta_prov
            ])

    return output.getvalue()


def export_invoices_to_contasol_csv(invoices: List[Invoice], journal_code: str = "1") -> str:
    """Función para exportar el diario completo desde la lista de facturas."""
    all_entries: List[AccountingEntryLine] = []
    entry_counter = 1
    for inv in invoices:
        for line in inv.accounting_entries:
            line.entry_number = entry_counter
            all_entries.append(line)
        entry_counter += 1
    return export_entries_to_contasol_csv(all_entries, journal_code=journal_code)
