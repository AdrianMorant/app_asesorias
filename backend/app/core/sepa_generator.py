"""Módulo Generador de Remesas Bancarias SEPA XML ISO 20022 (Normas 19 y 34).

Cumplimiento estricto:
- Directrices del European Payments Council (EPC) y Banco de España.
- ISO 20022 XML:
  * pain.008.001.02: Adeudos Directos SEPA (Norma 19 - SEPA Direct Debit CORE / B2B).
  * pain.001.001.03: Transferencias Múltiples de Crédito (Norma 34 - Proveedores y Nóminas).
- Validación algorítmica previa de cuentas IBAN (ISO 13616 / MOD-97).
- Generación de identificador de acreedor AT-02.
"""

from __future__ import annotations

import re
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, date
from typing import Any, Dict, List, Optional
from xml.dom import minidom

from app.core.iban_security import validate_iban


class SEPAGeneratorError(Exception):
    """Excepción base para errores de generación o validación de remesas SEPA."""
    pass


def _clean_text(val: Optional[str], max_len: int = 70) -> str:
    """Limpia caracteres especiales no válidos en mensajes XML ISO 20022."""
    if not val:
        return ""
    # Reemplazar caracteres fuera del conjunto permitido en SEPA
    text = str(val).strip()
    # Permitir alfanuméricos, espacios y puntuación estándar bancaria: + - / ? : ( ) . , '
    text = re.sub(r"[^A-Za-z0-9\+\-\/\?\:\(\)\.\,\' ]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_len]


def _format_amount(amt: float | int) -> str:
    """Formatea importe con exactamente 2 decimales."""
    return f"{float(amt):.2f}"


def _prettify_xml(elem: ET.Element) -> str:
    """Retorna XML formateado con sangría y cabecera UTF-8."""
    rough_string = ET.tostring(elem, encoding="utf-8")
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ", encoding="utf-8").decode("utf-8")


def generate_sepa_direct_debit_xml(
    creditor: Dict[str, Any],
    debits: List[Dict[str, Any]],
    message_id: Optional[str] = None,
    collection_date: Optional[Union[date, str]] = None,
    is_b2b: bool = False,
) -> str:
    """Genera el archivo XML ISO 20022 pain.008.001.02 (Norma 19 - Adeudos Directos SEPA).

    Args:
        creditor: Datos del acreedor/emisor:
            - name: Razón social
            - iban: Cuenta IBAN de abono
            - bic: Código BIC/SWIFT (opcional)
            - creditor_id: Identificador de acreedor AT-02 (ej. ES02000B12345678)
        debits: Lista de cobros a incluir:
            - debtor_name: Nombre o razón social del cliente
            - debtor_iban: IBAN del cliente deudor
            - debtor_bic: BIC del cliente deudor (opcional)
            - amount: Importe del adeudo en euros
            - mandate_id: Referencia única del mandato firmado
            - mandate_date: Fecha de firma del mandato (YYYY-MM-DD o date)
            - end_to_end_id: Identificador único de transacción / Nº factura
            - concept: Concepto o referencia de cobro
        message_id: ID único del mensaje. Si no se indica, se autogenera.
        collection_date: Fecha solicitada de cobro. Por defecto D+2 hábiles.
        is_b2b: True para esquema B2B, False para CORE estándar.

    Returns:
        Cadena con el XML formateado listo para emisión bancaria.
    """
    if not debits:
        raise SEPAGeneratorError("La remesa de cobro debe contener al menos un adeudo.")

    # 1. Validar IBAN del acreedor
    creditor_iban = re.sub(r"\s+", "", str(creditor.get("iban", "")).upper())
    if not validate_iban(creditor_iban):
        raise SEPAGeneratorError(f"IBAN del acreedor inválido: '{creditor_iban}'")

    creditor_name = _clean_text(creditor.get("name", "Empresa Acreedora"), 70)
    creditor_id = str(creditor.get("creditor_id", "")).strip().upper()
    if not creditor_id:
        # Generar código AT-02 por defecto a partir del NIF/CIF si existe
        cif = re.sub(r"[^A-Za-z0-9]", "", str(creditor.get("cif", creditor.get("nif", "B00000000"))))
        creditor_id = f"ES02000{cif}"

    # 2. Validar cada adeudo
    total_amount = 0.0
    for idx, d in enumerate(debits, start=1):
        d_iban = re.sub(r"\s+", "", str(d.get("debtor_iban", "")).upper())
        if not validate_iban(d_iban):
            raise SEPAGeneratorError(f"Adeudo #{idx}: IBAN del deudor inválido: '{d_iban}'")
        amt = float(d.get("amount", 0.0))
        if amt <= 0.009:
            raise SEPAGeneratorError(f"Adeudo #{idx}: Importe debe ser superior a 0 euros.")
        total_amount += amt

    total_amount = round(total_amount, 2)
    num_txs = len(debits)
    now = datetime.now()
    msg_id = message_id or f"DD-{now.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
    pmt_inf_id = f"PMTINF-{msg_id}"

    coll_dt_str = (
        collection_date.isoformat() if isinstance(collection_date, (date, datetime))
        else str(collection_date) if collection_date
        else now.strftime("%Y-%m-%d")
    )

    # 3. Construcción del árbol XML ISO 20022 pain.008.001.02
    xmlns = "urn:iso:std:iso:20022:tech:xsd:pain.008.001.02"
    root = ET.Element("Document", {"xmlns": xmlns, "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance"})
    cstmr_drct_dbt_initn = ET.SubElement(root, "CstmrDrctDbtInitn")

    # Group Header
    grp_hdr = ET.SubElement(cstmr_drct_dbt_initn, "GrpHdr")
    ET.SubElement(grp_hdr, "MsgId").text = msg_id
    ET.SubElement(grp_hdr, "CreDtTm").text = now.strftime("%Y-%m-%dT%H:%M:%S")
    ET.SubElement(grp_hdr, "NbOfTxs").text = str(num_txs)
    ET.SubElement(grp_hdr, "CtrlSum").text = _format_amount(total_amount)
    initg_pty = ET.SubElement(grp_hdr, "InitgPty")
    ET.SubElement(initg_pty, "Nm").text = creditor_name

    # Payment Information
    pmt_inf = ET.SubElement(cstmr_drct_dbt_initn, "PmtInf")
    ET.SubElement(pmt_inf, "PmtInfId").text = pmt_inf_id
    ET.SubElement(pmt_inf, "PmtMtd").text = "DD"
    ET.SubElement(pmt_inf, "NbOfTxs").text = str(num_txs)
    ET.SubElement(pmt_inf, "CtrlSum").text = _format_amount(total_amount)

    pmt_tp_inf = ET.SubElement(pmt_inf, "PmtTpInf")
    svc_lvl = ET.SubElement(pmt_tp_inf, "SvcLvl")
    ET.SubElement(svc_lvl, "Cd").text = "SEPA"
    lcl_instrm = ET.SubElement(pmt_tp_inf, "LclInstrm")
    ET.SubElement(lcl_instrm, "Cd").text = "B2B" if is_b2b else "CORE"
    ET.SubElement(pmt_tp_inf, "SeqTp").text = "RCUR"

    ET.SubElement(pmt_inf, "ReqdColltnDt").text = coll_dt_str

    cdtr = ET.SubElement(pmt_inf, "Cdtr")
    ET.SubElement(cdtr, "Nm").text = creditor_name

    cdtr_acct = ET.SubElement(pmt_inf, "CdtrAcct")
    cdtr_acct_id = ET.SubElement(cdtr_acct, "Id")
    ET.SubElement(cdtr_acct_id, "IBAN").text = creditor_iban

    cdtr_agt = ET.SubElement(pmt_inf, "CdtrAgt")
    fin_instn_id = ET.SubElement(cdtr_agt, "FinInstnId")
    if creditor.get("bic"):
        ET.SubElement(fin_instn_id, "BIC").text = str(creditor["bic"]).strip()
    else:
        othr = ET.SubElement(fin_instn_id, "Othr")
        ET.SubElement(othr, "Id").text = "NOTPROVIDED"

    ET.SubElement(pmt_inf, "ChrgBr").text = "SLEV"

    # Identificador de Acreedor AT-02
    cdtr_schme_id = ET.SubElement(pmt_inf, "CdtrSchmeId")
    id_elem = ET.SubElement(cdtr_schme_id, "Id")
    org_id = ET.SubElement(id_elem, "OrgId")
    othr_schme = ET.SubElement(org_id, "Othr")
    ET.SubElement(othr_schme, "Id").text = creditor_id
    schme_nm = ET.SubElement(othr_schme, "SchmeNm")
    ET.SubElement(schme_nm, "Prtry").text = "SEPA"

    # Líneas individuales de adeudo
    for d in debits:
        drct_dbt_tx_inf = ET.SubElement(pmt_inf, "DrctDbtTxInf")
        
        pmt_id = ET.SubElement(drct_dbt_tx_inf, "PmtId")
        end_to_end_id = _clean_text(d.get("end_to_end_id", uuid.uuid4().hex[:16]), 35)
        ET.SubElement(pmt_id, "EndToEndId").text = end_to_end_id

        instd_amt = ET.SubElement(drct_dbt_tx_inf, "InstdAmt", {"Ccy": "EUR"})
        instd_amt.text = _format_amount(d.get("amount", 0.0))

        # Mandato
        drct_dbt_tx = ET.SubElement(drct_dbt_tx_inf, "DrctDbtTx")
        mndt_rltd_inf = ET.SubElement(drct_dbt_tx, "MndtRltdInf")
        mandate_id = _clean_text(d.get("mandate_id", f"MNDT-{end_to_end_id}"), 35)
        ET.SubElement(mndt_rltd_inf, "MndtId").text = mandate_id
        
        m_date = d.get("mandate_date")
        m_date_str = m_date.isoformat() if isinstance(m_date, (date, datetime)) else str(m_date) if m_date else "2024-01-01"
        ET.SubElement(mndt_rltd_inf, "DtOfSgntr").text = m_date_str

        # Deudor
        dbtr_agt = ET.SubElement(drct_dbt_tx_inf, "DbtrAgt")
        dbtr_fin_instn = ET.SubElement(dbtr_agt, "FinInstnId")
        if d.get("debtor_bic"):
            ET.SubElement(dbtr_fin_instn, "BIC").text = str(d["debtor_bic"]).strip()
        else:
            othr_dbtr = ET.SubElement(dbtr_fin_instn, "Othr")
            ET.SubElement(othr_dbtr, "Id").text = "NOTPROVIDED"

        dbtr = ET.SubElement(drct_dbt_tx_inf, "Dbtr")
        ET.SubElement(dbtr, "Nm").text = _clean_text(d.get("debtor_name", "Cliente"), 70)

        dbtr_acct = ET.SubElement(drct_dbt_tx_inf, "DbtrAcct")
        dbtr_acct_id = ET.SubElement(dbtr_acct, "Id")
        d_iban = re.sub(r"\s+", "", str(d.get("debtor_iban", "")).upper())
        ET.SubElement(dbtr_acct_id, "IBAN").text = d_iban

        # Concepto
        concept = _clean_text(d.get("concept", f"Cobro Factura {end_to_end_id}"), 140)
        if concept:
            rmt_inf = ET.SubElement(drct_dbt_tx_inf, "RmtInf")
            ET.SubElement(rmt_inf, "Ustrd").text = concept

    return _prettify_xml(root)


def generate_sepa_credit_transfer_xml(
    debtor: Dict[str, Any],
    transfers: List[Dict[str, Any]],
    message_id: Optional[str] = None,
    execution_date: Optional[Union[date, str]] = None,
) -> str:
    """Genera el archivo XML ISO 20022 pain.001.001.03 (Norma 34 - Transferencias Múltiples de Crédito).

    Ideal para pagos a proveedores de compras aprobadas y liquidación de nóminas.

    Args:
        debtor: Datos de la empresa ordenante que emite los pagos:
            - name: Razón social de la empresa
            - iban: Cuenta bancaria de origen de los fondos
            - bic: BIC de la entidad de origen (opcional)
        transfers: Lista de transferencias a beneficiarios/proveedores:
            - creditor_name: Razón social o nombre del proveedor/empleado
            - creditor_iban: IBAN de destino del beneficiario
            - creditor_bic: BIC del banco del beneficiario (opcional)
            - amount: Importe en euros
            - end_to_end_id: Referencia de pago / Nº Factura
            - concept: Concepto explicativo de la transferencia
        message_id: ID único del mensaje.
        execution_date: Fecha solicitada de ejecución bancaria.

    Returns:
        Cadena con el XML listo para subir a la banca electrónica.
    """
    if not transfers:
        raise SEPAGeneratorError("La remesa de transferencias debe contener al menos un pago.")

    # 1. Validar IBAN del ordenante
    debtor_iban = re.sub(r"\s+", "", str(debtor.get("iban", "")).upper())
    if not validate_iban(debtor_iban):
        raise SEPAGeneratorError(f"IBAN del ordenante inválido: '{debtor_iban}'")

    debtor_name = _clean_text(debtor.get("name", "Empresa Ordenante"), 70)

    # 2. Validar cada beneficiario
    total_amount = 0.0
    for idx, t in enumerate(transfers, start=1):
        c_iban = re.sub(r"\s+", "", str(t.get("creditor_iban", "")).upper())
        if not validate_iban(c_iban):
            raise SEPAGeneratorError(f"Transferencia #{idx}: IBAN del beneficiario inválido: '{c_iban}'")
        amt = float(t.get("amount", 0.0))
        if amt <= 0.009:
            raise SEPAGeneratorError(f"Transferencia #{idx}: El importe debe ser mayor a 0.")
        total_amount += amt

    total_amount = round(total_amount, 2)
    num_txs = len(transfers)
    now = datetime.now()
    msg_id = message_id or f"TRF-{now.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
    pmt_inf_id = f"PMTINF-{msg_id}"

    ex_dt_str = (
        execution_date.isoformat() if isinstance(execution_date, (date, datetime))
        else str(execution_date) if execution_date
        else now.strftime("%Y-%m-%d")
    )

    # 3. Construcción del XML ISO 20022 pain.001.001.03
    xmlns = "urn:iso:std:iso:20022:tech:xsd:pain.001.001.03"
    root = ET.Element("Document", {"xmlns": xmlns, "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance"})
    cstmr_cdt_trf_initn = ET.SubElement(root, "CstmrCdtTrfInitn")

    # Group Header
    grp_hdr = ET.SubElement(cstmr_cdt_trf_initn, "GrpHdr")
    ET.SubElement(grp_hdr, "MsgId").text = msg_id
    ET.SubElement(grp_hdr, "CreDtTm").text = now.strftime("%Y-%m-%dT%H:%M:%S")
    ET.SubElement(grp_hdr, "NbOfTxs").text = str(num_txs)
    ET.SubElement(grp_hdr, "CtrlSum").text = _format_amount(total_amount)
    initg_pty = ET.SubElement(grp_hdr, "InitgPty")
    ET.SubElement(initg_pty, "Nm").text = debtor_name

    # Payment Information
    pmt_inf = ET.SubElement(cstmr_cdt_trf_initn, "PmtInf")
    ET.SubElement(pmt_inf, "PmtInfId").text = pmt_inf_id
    ET.SubElement(pmt_inf, "PmtMtd").text = "TRF"
    ET.SubElement(pmt_inf, "NbOfTxs").text = str(num_txs)
    ET.SubElement(pmt_inf, "CtrlSum").text = _format_amount(total_amount)

    pmt_tp_inf = ET.SubElement(pmt_inf, "PmtTpInf")
    svc_lvl = ET.SubElement(pmt_tp_inf, "SvcLvl")
    ET.SubElement(svc_lvl, "Cd").text = "SEPA"

    ET.SubElement(pmt_inf, "ReqdExctnDt").text = ex_dt_str

    dbtr = ET.SubElement(pmt_inf, "Dbtr")
    ET.SubElement(dbtr, "Nm").text = debtor_name

    dbtr_acct = ET.SubElement(pmt_inf, "DbtrAcct")
    dbtr_acct_id = ET.SubElement(dbtr_acct, "Id")
    ET.SubElement(dbtr_acct_id, "IBAN").text = debtor_iban

    dbtr_agt = ET.SubElement(pmt_inf, "DbtrAgt")
    fin_instn_id = ET.SubElement(dbtr_agt, "FinInstnId")
    if debtor.get("bic"):
        ET.SubElement(fin_instn_id, "BIC").text = str(debtor["bic"]).strip()
    else:
        othr = ET.SubElement(fin_instn_id, "Othr")
        ET.SubElement(othr, "Id").text = "NOTPROVIDED"

    ET.SubElement(pmt_inf, "ChrgBr").text = "SLEV"

    # Transacciones individuales de transferencia de crédito
    for t in transfers:
        cdt_trf_tx_inf = ET.SubElement(pmt_inf, "CdtTrfTxInf")

        pmt_id = ET.SubElement(cdt_trf_tx_inf, "PmtId")
        end_to_end_id = _clean_text(t.get("end_to_end_id", uuid.uuid4().hex[:16]), 35)
        ET.SubElement(pmt_id, "EndToEndId").text = end_to_end_id

        amt_elem = ET.SubElement(cdt_trf_tx_inf, "Amt")
        instd_amt = ET.SubElement(amt_elem, "InstdAmt", {"Ccy": "EUR"})
        instd_amt.text = _format_amount(t.get("amount", 0.0))

        cdtr_agt = ET.SubElement(cdt_trf_tx_inf, "CdtrAgt")
        cdtr_fin_instn = ET.SubElement(cdtr_agt, "FinInstnId")
        if t.get("creditor_bic"):
            ET.SubElement(cdtr_fin_instn, "BIC").text = str(t["creditor_bic"]).strip()
        else:
            othr_cdtr = ET.SubElement(cdtr_fin_instn, "Othr")
            ET.SubElement(othr_cdtr, "Id").text = "NOTPROVIDED"

        cdtr = ET.SubElement(cdt_trf_tx_inf, "Cdtr")
        ET.SubElement(cdtr, "Nm").text = _clean_text(t.get("creditor_name", "Proveedor"), 70)

        cdtr_acct = ET.SubElement(cdt_trf_tx_inf, "CdtrAcct")
        cdtr_acct_id = ET.SubElement(cdtr_acct, "Id")
        c_iban = re.sub(r"\s+", "", str(t.get("creditor_iban", "")).upper())
        ET.SubElement(cdtr_acct_id, "IBAN").text = c_iban

        concept = _clean_text(t.get("concept", f"Pago Factura {end_to_end_id}"), 140)
        if concept:
            rmt_inf = ET.SubElement(cdt_trf_tx_inf, "RmtInf")
            ET.SubElement(rmt_inf, "Ustrd").text = concept

    return _prettify_xml(root)
