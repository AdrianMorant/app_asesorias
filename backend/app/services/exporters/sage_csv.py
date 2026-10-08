import csv
import io
from typing import List, Optional
from app.models.accounting_entry import AccountingEntryLine
from app.models.invoice import Invoice

def export_invoices_to_sage_csv(invoices: List[Invoice], channel: str = "0") -> str:
    """
    Genera un archivo CSV estructurado según la plantilla oficial de asientos contables de Sage
    (Sage 50 / Sage Despachos Connected):
    Canal;Número de Asiento;Fecha;Cuenta;Concepto;Debe;Haber;Contrapartida;Base IVA;Cuota IVA;Factura
    """
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";", lineterminator="\r\n")

    # Cabecera oficial exigida
    writer.writerow([
        "Canal",
        "Número de Asiento",
        "Fecha",
        "Cuenta",
        "Concepto",
        "Debe",
        "Haber",
        "Contrapartida",
        "Base IVA",
        "Cuota IVA",
        "Factura"
    ])

    asiento_num = 1
    for inv in invoices:
        fecha_obj = getattr(inv, "fecha_contable", None) or inv.issue_date
        fecha_str = fecha_obj.strftime("%d/%m/%Y") if fecha_obj else "01/01/2026"
        doc_str = (inv.invoice_number or "S/N")[:30]

        # Determinar cuenta de proveedor y de contrapartida principal
        cta_prov = "400000000"
        cta_gasto = "629000000"
        if inv.accounting_entries:
            for e in inv.accounting_entries:
                if e.subcuenta.startswith("400") or e.subcuenta.startswith("410"):
                    cta_prov = e.subcuenta
                elif e.subcuenta.startswith("6"):
                    cta_gasto = e.subcuenta

        base_str = f"{inv.total_base:.2f}".replace(".", ",")
        tax_str = f"{inv.total_tax:.2f}".replace(".", ",")

        if inv.accounting_entries:
            for entry in inv.accounting_entries:
                debe_str = f"{entry.debe:.2f}".replace(".", ",") if entry.debe != 0 else "0,00"
                haber_str = f"{entry.haber:.2f}".replace(".", ",") if entry.haber != 0 else "0,00"

                # Asignar contrapartida, Base IVA y Cuota IVA según la naturaleza de la cuenta
                if entry.subcuenta.startswith("400") or entry.subcuenta.startswith("410"):
                    contrapartida = cta_gasto
                    line_base_iva = "0,00"
                    line_cuota_iva = "0,00"
                elif entry.subcuenta.startswith("472"):
                    contrapartida = cta_prov
                    line_base_iva = base_str
                    line_cuota_iva = debe_str
                elif entry.subcuenta.startswith("6"):
                    contrapartida = cta_prov
                    line_base_iva = base_str
                    line_cuota_iva = "0,00"
                else:
                    contrapartida = cta_prov
                    line_base_iva = "0,00"
                    line_cuota_iva = "0,00"

                writer.writerow([
                    channel,
                    str(asiento_num),
                    fecha_str,
                    entry.subcuenta,
                    entry.concepto[:60],
                    debe_str,
                    haber_str,
                    contrapartida,
                    line_base_iva,
                    line_cuota_iva,
                    doc_str
                ])
        asiento_num += 1

    return output.getvalue()


def export_entries_to_sage_csv(entries: List[AccountingEntryLine], channel: str = "0") -> str:
    """Función de compatibilidad para exportar asientos directos."""
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";", lineterminator="\r\n")

    writer.writerow([
        "Canal",
        "Número de Asiento",
        "Fecha",
        "Cuenta",
        "Concepto",
        "Debe",
        "Haber",
        "Contrapartida",
        "Base IVA",
        "Cuota IVA",
        "Factura"
    ])

    for entry in entries:
        fecha_str = entry.fecha.strftime("%d/%m/%Y")
        debe_str = f"{entry.debe:.2f}".replace(".", ",") if entry.debe != 0 else "0,00"
        haber_str = f"{entry.haber:.2f}".replace(".", ",") if entry.haber != 0 else "0,00"
        contrapartida = "400000000" if not (entry.subcuenta.startswith("400") or entry.subcuenta.startswith("410")) else "629000000"

        writer.writerow([
            channel,
            str(entry.entry_number),
            fecha_str,
            entry.subcuenta,
            entry.concepto[:60],
            debe_str,
            haber_str,
            contrapartida,
            "0,00",
            "0,00",
            (entry.documento or "")[:30]
        ])

    return output.getvalue()
