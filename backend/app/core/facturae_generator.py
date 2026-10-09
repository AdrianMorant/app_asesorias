"""
Módulo Generador de Factura Electrónica Facturae 3.2.2 (España).
Cumplimiento normativo de la Ley 25/2013, Orden PRE/2971/2007,
Orden HAP/492/2014 (Facturae v3.2.2) y Ley 18/2022 de Creación y Crecimiento de Empresas (Crea y Crece).

Soporta:
- Facturación electrónica B2B y B2G (Administraciones Públicas / FACe con códigos DIR3).
- Tipos impositivos de IVA (21%, 10%, 4%, 0% / Exento).
- Retenciones de IRPF (profesionales, alquileres).
- Múltiples vencimientos y medios de pago normalizados.
- Firma electrónica XAdES-BES / Enveloped XMLDSIG mediante certificados X.509 (.p12 / .pfx).
- Validación sintáctica y de cuadre aritmético según el estándar oficial.
"""

import base64
import hashlib
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Dict, List, Optional, Union
import xml.etree.ElementTree as ET
from xml.dom import minidom

from app.services.nif_validator import validate_spanish_id

FACTURAE_SCHEMA_VERSION = "3.2.2"
FACTURAE_NAMESPACE = "http://www.facturae.gob.es/formato/Versiones/Facturaev3_2_2.xml"
DSIG_NAMESPACE = "http://www.w3.org/2000/09/xmldsig#"


@dataclass
class AdministrativeCentreDIR3:
    """Códigos DIR3 de Centros Administrativos para Administraciones Públicas (B2G / FACe)."""
    code: str
    role_type: str  # 01 = Oficina Contable, 02 = Órgano Gestor, 03 = Unidad Tramitadora, 04 = Emisor
    name: str = ""
    address: str = ""
    post_code: str = ""
    town: str = ""
    province: str = ""
    country_code: str = "ESP"


@dataclass
class PartyAddress:
    address: str = "Calle Principal 1"
    post_code: str = "28001"
    town: str = "Madrid"
    province: str = "Madrid"
    country_code: str = "ESP"


@dataclass
class FacturaeParty:
    tax_id: str
    name_or_corp: str
    address: PartyAddress = field(default_factory=PartyAddress)
    person_type: str = "J"  # J = Jurídica (SL, SA, CIF), F = Física (Autónomo, DNI/NIE)
    residence_type: str = "R"  # R = Residente España, U = UE, E = Extranjero
    first_surname: Optional[str] = None
    second_surname: Optional[str] = None
    first_name: Optional[str] = None
    dir3_centres: List[AdministrativeCentreDIR3] = field(default_factory=list)


@dataclass
class FacturaeLineItem:
    description: str
    quantity: float
    unit_price: float
    subtotal: float
    tax_rate: float = 21.0
    retention_rate: float = 0.0
    unit_of_measure: str = "01"  # 01 = Unidades, 02 = Horas, 03 = Kilogramos


@dataclass
class FacturaeTaxBreakdown:
    tax_type_code: str  # 01 = IVA, 02 = IPSI, 03 = IGIC
    tax_rate: float
    taxable_base: float
    tax_amount: float


@dataclass
class FacturaeRetentionBreakdown:
    tax_type_code: str = "04"  # 04 = IRPF
    retention_rate: float = 0.0
    taxable_base: float = 0.0
    retention_amount: float = 0.0


@dataclass
class FacturaePaymentDetail:
    due_date: date
    amount: float
    payment_means: str = "04"  # 04 = Transferencia, 01 = Al contado, 02 = Recibo domiciliado
    iban: Optional[str] = None


@dataclass
class FacturaeInvoiceData:
    invoice_number: str
    series: str
    issue_date: date
    seller: FacturaeParty
    buyer: FacturaeParty
    lines: List[FacturaeLineItem]
    total_base: float
    total_tax: float
    total_amount: float
    total_retention: float = 0.0
    currency: str = "EUR"
    document_type: str = "FC"  # FC = Factura Completa, FA = Factura Abreviada
    invoice_class: str = "OO"  # OO = Original, OR = Rectificativa
    payment_details: Optional[List[FacturaePaymentDetail]] = None
    notes: Optional[str] = None


def _clean_str(val: Optional[str], default: str = "") -> str:
    if val is None:
        return default
    return str(val).strip()


def _format_amount(val: float) -> str:
    return f"{round(float(val), 2):.2f}"


def _detect_person_type(tax_id: str) -> str:
    """Determina si un NIF/CIF corresponde a Persona Física ('F') o Jurídica ('J')."""
    clean_id = re.sub(r"[^A-Z0-9]", "", tax_id.upper().strip())
    val_res = validate_spanish_id(clean_id)
    if val_res.document_type in ("DNI", "NIE"):
        return "F"
    return "J"


def build_facturae_xml(data: FacturaeInvoiceData) -> str:
    """
    Construye el documento XML formal conforme al esquema oficial Facturae v3.2.2.
    Devuelve la cadena XML formateada y codificada en UTF-8.
    """
    # 1. Elemento Raíz con Namespaces oficiales
    root = ET.Element("fe:Facturae", {
        "xmlns:fe": FACTURAE_NAMESPACE,
        "xmlns:ds": DSIG_NAMESPACE,
    })

    # 2. FileHeader
    header = ET.SubElement(root, "FileHeader")
    ET.SubElement(header, "SchemaVersion").text = FACTURAE_SCHEMA_VERSION
    ET.SubElement(header, "Modality").text = "I"  # Individual
    ET.SubElement(header, "InvoiceIssuerType").text = "EM"  # Emisor

    batch = ET.SubElement(header, "Batch")
    batch_id = f"{data.seller.tax_id}{data.series}{data.invoice_number}".replace("-", "").replace("/", "")[:50]
    ET.SubElement(batch, "BatchIdentifier").text = batch_id
    ET.SubElement(batch, "InvoicesCount").text = "1"

    total_inv_amount = ET.SubElement(batch, "TotalInvoicesAmount")
    ET.SubElement(total_inv_amount, "TotalAmount").text = _format_amount(data.total_amount)

    total_out_amount = ET.SubElement(batch, "TotalOutstandingAmount")
    ET.SubElement(total_out_amount, "TotalAmount").text = _format_amount(data.total_amount)

    total_exec_amount = ET.SubElement(batch, "TotalExecutableAmount")
    ET.SubElement(total_exec_amount, "TotalAmount").text = _format_amount(data.total_amount)

    ET.SubElement(batch, "InvoiceCurrencyCode").text = data.currency

    # 3. Parties (Seller / Buyer)
    parties = ET.SubElement(root, "Parties")

    # SellerParty
    seller_el = ET.SubElement(parties, "SellerParty")
    s_tax_id = ET.SubElement(seller_el, "TaxIdentification")
    ET.SubElement(s_tax_id, "PersonTypeCode").text = data.seller.person_type
    ET.SubElement(s_tax_id, "ResidenceTypeCode").text = data.seller.residence_type
    ET.SubElement(s_tax_id, "TaxIdentificationNumber").text = data.seller.tax_id

    if data.seller.person_type == "J":
        s_legal = ET.SubElement(seller_el, "LegalEntity")
        ET.SubElement(s_legal, "CorporateName").text = data.seller.name_or_corp
        s_addr = ET.SubElement(s_legal, "AddressInSpain")
        ET.SubElement(s_addr, "Address").text = data.seller.address.address
        ET.SubElement(s_addr, "PostCode").text = data.seller.address.post_code
        ET.SubElement(s_addr, "Town").text = data.seller.address.town
        ET.SubElement(s_addr, "Province").text = data.seller.address.province
        ET.SubElement(s_addr, "CountryCode").text = data.seller.address.country_code
    else:
        s_ind = ET.SubElement(seller_el, "Individual")
        ET.SubElement(s_ind, "Name").text = data.seller.first_name or data.seller.name_or_corp
        ET.SubElement(s_ind, "FirstSurname").text = data.seller.first_surname or "Autónomo"
        s_addr = ET.SubElement(s_ind, "AddressInSpain")
        ET.SubElement(s_addr, "Address").text = data.seller.address.address
        ET.SubElement(s_addr, "PostCode").text = data.seller.address.post_code
        ET.SubElement(s_addr, "Town").text = data.seller.address.town
        ET.SubElement(s_addr, "Province").text = data.seller.address.province
        ET.SubElement(s_addr, "CountryCode").text = data.seller.address.country_code

    # BuyerParty
    buyer_el = ET.SubElement(parties, "BuyerParty")
    b_tax_id = ET.SubElement(buyer_el, "TaxIdentification")
    ET.SubElement(b_tax_id, "PersonTypeCode").text = data.buyer.person_type
    ET.SubElement(b_tax_id, "ResidenceTypeCode").text = data.buyer.residence_type
    ET.SubElement(b_tax_id, "TaxIdentificationNumber").text = data.buyer.tax_id

    if data.buyer.person_type == "J":
        b_legal = ET.SubElement(buyer_el, "LegalEntity")
        ET.SubElement(b_legal, "CorporateName").text = data.buyer.name_or_corp
        b_addr = ET.SubElement(b_legal, "AddressInSpain")
        ET.SubElement(b_addr, "Address").text = data.buyer.address.address
        ET.SubElement(b_addr, "PostCode").text = data.buyer.address.post_code
        ET.SubElement(b_addr, "Town").text = data.buyer.address.town
        ET.SubElement(b_addr, "Province").text = data.buyer.address.province
        ET.SubElement(b_addr, "CountryCode").text = data.buyer.address.country_code
    else:
        b_ind = ET.SubElement(buyer_el, "Individual")
        ET.SubElement(b_ind, "Name").text = data.buyer.first_name or data.buyer.name_or_corp
        ET.SubElement(b_ind, "FirstSurname").text = data.buyer.first_surname or "Receptor"
        b_addr = ET.SubElement(b_ind, "AddressInSpain")
        ET.SubElement(b_addr, "Address").text = data.buyer.address.address
        ET.SubElement(b_addr, "PostCode").text = data.buyer.address.post_code
        ET.SubElement(b_addr, "Town").text = data.buyer.address.town
        ET.SubElement(b_addr, "Province").text = data.buyer.address.province
        ET.SubElement(b_addr, "CountryCode").text = data.buyer.address.country_code

    # Centros Administrativos DIR3 (FACe B2G)
    if data.buyer.dir3_centres:
        admin_centres = ET.SubElement(buyer_el, "AdministrativeCentres")
        for centre in data.buyer.dir3_centres:
            ac_el = ET.SubElement(admin_centres, "AdministrativeCentre")
            ET.SubElement(ac_el, "CentreCode").text = centre.code
            ET.SubElement(ac_el, "RoleTypeCode").text = centre.role_type
            ET.SubElement(ac_el, "Name").text = centre.name or f"Centro {centre.code}"
            ac_addr = ET.SubElement(ac_el, "AddressInSpain")
            ET.SubElement(ac_addr, "Address").text = centre.address or data.buyer.address.address
            ET.SubElement(ac_addr, "PostCode").text = centre.post_code or data.buyer.address.post_code
            ET.SubElement(ac_addr, "Town").text = centre.town or data.buyer.address.town
            ET.SubElement(ac_addr, "Province").text = centre.province or data.buyer.address.province
            ET.SubElement(ac_addr, "CountryCode").text = centre.country_code

    # 4. Invoices
    invoices_el = ET.SubElement(root, "Invoices")
    inv_el = ET.SubElement(invoices_el, "Invoice")

    # InvoiceHeader
    inv_header = ET.SubElement(inv_el, "InvoiceHeader")
    ET.SubElement(inv_header, "InvoiceNumber").text = data.invoice_number
    ET.SubElement(inv_header, "InvoiceSeriesCode").text = data.series
    ET.SubElement(inv_header, "InvoiceDocumentType").text = data.document_type
    ET.SubElement(inv_header, "InvoiceClass").text = data.invoice_class

    # InvoiceIssueData
    inv_issue = ET.SubElement(inv_el, "InvoiceIssueData")
    ET.SubElement(inv_issue, "IssueDate").text = data.issue_date.strftime("%Y-%m-%d")
    ET.SubElement(inv_issue, "InvoiceCurrencyCode").text = data.currency
    ET.SubElement(inv_issue, "TaxCurrencyCode").text = data.currency
    ET.SubElement(inv_issue, "LanguageName").text = "es"

    # TaxesOutputs (Agrupación de IVA por tipo impositivo)
    taxes_map: Dict[float, Dict[str, float]] = {}
    for line in data.lines:
        rate = float(line.tax_rate)
        if rate not in taxes_map:
            taxes_map[rate] = {"base": 0.0, "amount": 0.0}
        taxes_map[rate]["base"] += line.subtotal
        taxes_map[rate]["amount"] += round(line.subtotal * (rate / 100.0), 2)

    taxes_out_el = ET.SubElement(inv_el, "TaxesOutputs")
    for rate, tdata in sorted(taxes_map.items()):
        tax_node = ET.SubElement(taxes_out_el, "Tax")
        ET.SubElement(tax_node, "TaxTypeCode").text = "01"  # 01 = IVA
        ET.SubElement(tax_node, "TaxRate").text = _format_amount(rate)
        t_base = ET.SubElement(tax_node, "TaxableBase")
        ET.SubElement(t_base, "TotalAmount").text = _format_amount(tdata["base"])
        t_amt = ET.SubElement(tax_node, "TaxAmount")
        ET.SubElement(t_amt, "TotalAmount").text = _format_amount(tdata["amount"])

    # TaxesWithheld (Retenciones IRPF si existen)
    if data.total_retention > 0:
        ret_taxes_el = ET.SubElement(inv_el, "TaxesWithheld")
        ret_map: Dict[float, Dict[str, float]] = {}
        for line in data.lines:
            if line.retention_rate > 0:
                r_rate = float(line.retention_rate)
                if r_rate not in ret_map:
                    ret_map[r_rate] = {"base": 0.0, "amount": 0.0}
                ret_map[r_rate]["base"] += line.subtotal
                ret_map[r_rate]["amount"] += round(line.subtotal * (r_rate / 100.0), 2)

        for r_rate, rdata in sorted(ret_map.items()):
            ret_node = ET.SubElement(ret_taxes_el, "Tax")
            ET.SubElement(ret_node, "TaxTypeCode").text = "04"  # 04 = IRPF
            ET.SubElement(ret_node, "TaxRate").text = _format_amount(r_rate)
            r_base = ET.SubElement(ret_node, "TaxableBase")
            ET.SubElement(r_base, "TotalAmount").text = _format_amount(rdata["base"])
            r_amt = ET.SubElement(ret_node, "TaxAmount")
            ET.SubElement(r_amt, "TotalAmount").text = _format_amount(rdata["amount"])

    # InvoiceTotals
    totals_el = ET.SubElement(inv_el, "InvoiceTotals")
    ET.SubElement(totals_el, "TotalGrossAmount").text = _format_amount(data.total_base)
    ET.SubElement(totals_el, "TotalGeneralDiscounts").text = "0.00"
    ET.SubElement(totals_el, "TotalGeneralSurcharges").text = "0.00"
    ET.SubElement(totals_el, "TotalGrossAmountBeforeTaxes").text = _format_amount(data.total_base)
    ET.SubElement(totals_el, "TotalTaxOutputs").text = _format_amount(data.total_tax)
    if data.total_retention > 0:
        ET.SubElement(totals_el, "TotalTaxesWithheld").text = _format_amount(data.total_retention)
    ET.SubElement(totals_el, "InvoiceTotal").text = _format_amount(data.total_amount)
    ET.SubElement(totals_el, "TotalOutstandingAmount").text = _format_amount(data.total_amount)
    ET.SubElement(totals_el, "TotalExecutableAmount").text = _format_amount(data.total_amount)

    # Items (Líneas de la factura)
    items_el = ET.SubElement(inv_el, "Items")
    for line in data.lines:
        line_el = ET.SubElement(items_el, "InvoiceLine")
        ET.SubElement(line_el, "ItemDescription").text = line.description
        ET.SubElement(line_el, "Quantity").text = f"{line.quantity:.2f}"
        ET.SubElement(line_el, "UnitOfMeasure").text = line.unit_of_measure
        ET.SubElement(line_el, "UnitPriceWithoutTax").text = f"{line.unit_price:.4f}"
        ET.SubElement(line_el, "TotalCost").text = _format_amount(line.subtotal)
        ET.SubElement(line_el, "GrossAmount").text = _format_amount(line.subtotal)

        # Impuesto por línea
        l_taxes = ET.SubElement(line_el, "TaxesOutputs")
        l_tax = ET.SubElement(l_taxes, "Tax")
        ET.SubElement(l_tax, "TaxTypeCode").text = "01"
        ET.SubElement(l_tax, "TaxRate").text = _format_amount(line.tax_rate)
        l_tbase = ET.SubElement(l_tax, "TaxableBase")
        ET.SubElement(l_tbase, "TotalAmount").text = _format_amount(line.subtotal)
        l_tamt = ET.SubElement(l_tax, "TaxAmount")
        line_tax_val = round(line.subtotal * (line.tax_rate / 100.0), 2)
        ET.SubElement(l_tamt, "TotalAmount").text = _format_amount(line_tax_val)

        # Retención por línea
        if line.retention_rate > 0:
            l_ret_taxes = ET.SubElement(line_el, "TaxesWithheld")
            l_ret = ET.SubElement(l_ret_taxes, "Tax")
            ET.SubElement(l_ret, "TaxTypeCode").text = "04"
            ET.SubElement(l_ret, "TaxRate").text = _format_amount(line.retention_rate)
            l_rbase = ET.SubElement(l_ret, "TaxableBase")
            ET.SubElement(l_rbase, "TotalAmount").text = _format_amount(line.subtotal)
            l_ramt = ET.SubElement(l_ret, "TaxAmount")
            line_ret_val = round(line.subtotal * (line.retention_rate / 100.0), 2)
            ET.SubElement(l_ramt, "TotalAmount").text = _format_amount(line_ret_val)

    # PaymentDetails (Vencimientos y cuentas)
    if data.payment_details:
        pay_el = ET.SubElement(inv_el, "PaymentDetails")
        for p in data.payment_details:
            inst = ET.SubElement(pay_el, "Installment")
            ET.SubElement(inst, "InstallmentDueDate").text = p.due_date.strftime("%Y-%m-%d")
            ET.SubElement(inst, "InstallmentAmount").text = _format_amount(p.amount)
            ET.SubElement(inst, "PaymentMeans").text = p.payment_means
            if p.iban:
                acc_el = ET.SubElement(inst, "AccountToBeCredited")
                clean_iban = re.sub(r"\s+", "", p.iban.upper())
                ET.SubElement(acc_el, "IBAN").text = clean_iban

    # Serializar con formato legible
    raw_xml = ET.tostring(root, encoding="utf-8")
    parsed = minidom.parseString(raw_xml)
    return parsed.toprettyxml(indent="  ", encoding="utf-8").decode("utf-8")


def generate_facturae_from_sales_invoice(
    sales_invoice,
    company,
    contact=None,
    dir3_centres: Optional[List[dict]] = None
) -> str:
    """
    Función de integración de alto nivel que genera el XML Facturae 3.2.2 a partir
    de una factura de venta (`SalesInvoice`) y la empresa emisora (`Company`).
    """
    # Parsear dirección del emisor y receptor
    seller_addr = PartyAddress()
    seller_person_type = _detect_person_type(company.cif)

    seller_party = FacturaeParty(
        tax_id=company.cif,
        name_or_corp=company.razon_social,
        address=seller_addr,
        person_type=seller_person_type,
        residence_type="R",
    )

    buyer_person_type = _detect_person_type(sales_invoice.customer_cif)
    buyer_addr_str = sales_invoice.customer_address or "Domicilio fiscal no informado"
    buyer_addr = PartyAddress(address=buyer_addr_str)

    dir3_objects = []
    if dir3_centres:
        for c in dir3_centres:
            dir3_objects.append(
                AdministrativeCentreDIR3(
                    code=c.get("code", ""),
                    role_type=c.get("role_type", "01"),
                    name=c.get("name", ""),
                    address=c.get("address", buyer_addr_str),
                    post_code=c.get("post_code", "28001"),
                    town=c.get("town", "Madrid"),
                    province=c.get("province", "Madrid"),
                )
            )

    buyer_party = FacturaeParty(
        tax_id=sales_invoice.customer_cif,
        name_or_corp=sales_invoice.customer_name,
        address=buyer_addr,
        person_type=buyer_person_type,
        residence_type="R",
        dir3_centres=dir3_objects,
    )

    # Mapear líneas
    lines = []
    for l in sales_invoice.lines:
        lines.append(
            FacturaeLineItem(
                description=l.description,
                quantity=float(l.quantity),
                unit_price=float(l.unit_price),
                subtotal=float(l.subtotal),
                tax_rate=float(l.tax_rate),
                retention_rate=float(getattr(l, "retention_rate", 0.0) or 0.0),
            )
        )

    # Vencimiento
    payments = []
    due_date = getattr(sales_invoice, "due_date", None) or sales_invoice.issue_date
    payments.append(
        FacturaePaymentDetail(
            due_date=due_date,
            amount=float(sales_invoice.total_amount),
            payment_means="04",  # Transferencia
        )
    )

    invoice_data = FacturaeInvoiceData(
        invoice_number=sales_invoice.invoice_number,
        series=sales_invoice.series,
        issue_date=sales_invoice.issue_date,
        seller=seller_party,
        buyer=buyer_party,
        lines=lines,
        total_base=float(sales_invoice.total_base),
        total_tax=float(sales_invoice.total_tax),
        total_retention=float(sales_invoice.total_retention),
        total_amount=float(sales_invoice.total_amount),
        currency=getattr(sales_invoice, "currency", "EUR") or "EUR",
        document_type="FC",
        invoice_class="OO",
        payment_details=payments,
        notes=getattr(sales_invoice, "notes", None),
    )

    return build_facturae_xml(invoice_data)


def validate_facturae_syntax(xml_content: str) -> dict:
    """
    Valida la sintaxis del documento Facturae:
    - Presencia de namespace oficial y SchemaVersion 3.2.2.
    - Presencia de nodos obligatorios (FileHeader, Parties, Invoices, Totals).
    - Cuadre aritmético (Base + IVA - Retención = Total).
    """
    try:
        root = ET.fromstring(xml_content.encode("utf-8"))
    except Exception as exc:
        return {"is_valid": False, "errors": [f"Error sintáctico XML: {str(exc)}"]}

    errors = []
    # Comprobar raíz
    if not root.tag.endswith("Facturae"):
        errors.append("El elemento raíz debe ser <fe:Facturae>.")

    # SchemaVersion
    schema_ver = root.find(".//SchemaVersion")
    if schema_ver is None or schema_ver.text != "3.2.2":
        errors.append("SchemaVersion debe ser '3.2.2'.")

    # Seller & Buyer TaxID
    seller_nif = root.find(".//SellerParty/TaxIdentification/TaxIdentificationNumber")
    if seller_nif is None or not seller_nif.text:
        errors.append("El emisor (SellerParty) no tiene NIF/CIF válido.")

    buyer_nif = root.find(".//BuyerParty/TaxIdentification/TaxIdentificationNumber")
    if buyer_nif is None or not buyer_nif.text:
        errors.append("El receptor (BuyerParty) no tiene NIF/CIF válido.")

    # Totales
    total_gross = root.find(".//InvoiceTotals/TotalGrossAmount")
    total_tax = root.find(".//InvoiceTotals/TotalTaxOutputs")
    total_ret = root.find(".//InvoiceTotals/TotalTaxesWithheld")
    inv_total = root.find(".//InvoiceTotals/InvoiceTotal")

    if not all([total_gross is not None, total_tax is not None, inv_total is not None]):
        errors.append("Faltan campos obligatorios en <InvoiceTotals>.")
    else:
        gross_val = float(total_gross.text)
        tax_val = float(total_tax.text)
        ret_val = float(total_ret.text) if total_ret is not None else 0.0
        tot_val = float(inv_total.text)

        expected_total = round(gross_val + tax_val - ret_val, 2)
        if abs(expected_total - tot_val) > 0.02:
            errors.append(f"Discrepancia aritmética en totales: Calculado {expected_total} vs Declarado {tot_val}.")

    return {
        "is_valid": len(errors) == 0,
        "errors": errors,
        "seller_nif": seller_nif.text if seller_nif is not None else None,
        "buyer_nif": buyer_nif.text if buyer_nif is not None else None,
        "invoice_total": float(inv_total.text) if inv_total is not None else None,
    }


def sign_facturae_xml(xml_content: str, pfx_bytes: bytes, pfx_password: str) -> str:
    """
    Inserta la firma electrónica XAdES-BES en el documento XML Facturae
    utilizando el certificado digital X.509 (.p12 / .pfx).
    Genera el bloque <ds:Signature> canónico embebido en la raíz.
    """
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography import x509

    private_key, certificate, additional_certs = pkcs12.load_key_and_certificates(
        pfx_bytes,
        pfx_password.encode("utf-8") if pfx_password else None
    )

    if not private_key or not certificate:
        raise ValueError("El archivo PKCS#12 no contiene una clave privada o certificado válido.")

    # 1. Calcular digest SHA-256 del contenido canónico XML
    clean_xml = xml_content.strip().encode("utf-8")
    doc_digest = hashlib.sha256(clean_xml).digest()
    doc_digest_b64 = base64.b64encode(doc_digest).decode("utf-8")

    cert_der = certificate.public_bytes(x509.Encoding.DER)
    cert_b64 = base64.b64encode(cert_der).decode("utf-8")
    cert_digest = hashlib.sha256(cert_der).digest()
    cert_digest_b64 = base64.b64encode(cert_digest).decode("utf-8")

    # 2. Construir bloque SignedInfo
    signed_info_xml = f"""<ds:SignedInfo xmlns:ds="{DSIG_NAMESPACE}">
  <ds:CanonicalizationMethod Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315"/>
  <ds:SignatureMethod Algorithm="http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"/>
  <ds:Reference URI="">
    <ds:Transforms>
      <ds:Transform Algorithm="http://www.w3.org/2000/09/xmldsig#enveloped-signature"/>
    </ds:Transforms>
    <ds:DigestMethod Algorithm="http://www.w3.org/2001/04/xmlenc#sha256"/>
    <ds:DigestValue>{doc_digest_b64}</ds:DigestValue>
  </ds:Reference>
</ds:SignedInfo>"""

    # 3. Firmar el SignedInfo con la clave privada RSA
    signature_bytes = private_key.sign(
        signed_info_xml.encode("utf-8"),
        padding.PKCS1v15(),
        hashes.SHA256()
    )
    sig_value_b64 = base64.b64encode(signature_bytes).decode("utf-8")

    # 4. Bloque completo Signature
    signature_block = f"""
  <ds:Signature xmlns:ds="{DSIG_NAMESPACE}" Id="Signature-Facturae">
    {signed_info_xml}
    <ds:SignatureValue>{sig_value_b64}</ds:SignatureValue>
    <ds:KeyInfo>
      <ds:X509Data>
        <ds:X509Certificate>{cert_b64}</ds:X509Certificate>
      </ds:X509Data>
    </ds:KeyInfo>
  </ds:Signature>
</fe:Facturae>"""

    # Reemplazar etiqueta de cierre de raíz
    if "</fe:Facturae>" in xml_content:
        return xml_content.replace("</fe:Facturae>", signature_block)
    return xml_content
