"""Módulo Autónomo de OCR, Extracción Inteligente y Autoaprendizaje Contable PGC.

Implementa:
1. Descompresión/descifrado en memoria de documentos cifrados (AES-256-GCM) sin rastro en disco.
2. Extracción profunda de campos fiscales conforme a la normativa AEAT:
   - Emisor y receptor (NIF/CIF normalizado según validación algorítmica).
   - Número de serie/factura, fechas de expedición y operación.
   - Desglose multi-IVA (4%, 10%, 21%), recargo de equivalencia y retenciones de IRPF.
3. Detección y prevención preventiva de facturas duplicadas en la base de datos (DUPLICATE_SUSPECTED).
4. Autoaprendizaje y memoria de categorización PGC basada en el histórico de compras del proveedor.
"""

from __future__ import annotations

import logging
import mimetypes
import os
from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.file_encryption import read_decrypted_file
from app.models.invoice import Invoice
from app.models.supplier import Supplier
from app.models.accounting_entry import AccountingEntryLine
from app.services.extractor_llm import extract_invoice_data as extract_via_llm
from app.services.nif_validator import validate_spanish_id

logger = logging.getLogger(__name__)


# Clasificación heurística PGC según palabras clave de proveedores o conceptos
DEFAULT_PGC_EXPENSE_RULES = [
    (r"(?i)\b(luz|electricidad|gas|agua|energia|endesa|iberdrola|naturgy)\b", "628000000", "Suministros"),
    (r"(?i)\b(telefon|movil|fibra|vodafone|orange|movistar|telecom)\b", "629000001", "Comunicaciones"),
    (r"(?i)\b(alquiler|arrendamiento|renta|local|inmueble)\b", "621000000", "Arrendamientos y cánones"),
    (r"(?i)\b(abogado|asesor|gestor|notari|consultor|auditor)\b", "623000000", "Servicios de profesionales independientes"),
    (r"(?i)\b(seguro|poliza|mapfre|axa|allianz)\b", "625000000", "Primas de seguros"),
    (r"(?i)\b(banco|comision|mantenimiento|interes)\b", "626000000", "Servicios bancarios y similares"),
    (r"(?i)\b(publicidad|marketing|anuncio|google|meta|facebook)\b", "627000000", "Publicidad, propaganda y relaciones públicas"),
    (r"(?i)\b(reparacion|mantenimiento|conservacion)\b", "622000000", "Reparaciones y conservación"),
    (r"(?i)\b(transporte|porte|envio|mensajeria|mrw|seur|dhl)\b", "624000000", "Transportes"),
    (r"(?i)\b(mercaderia|material|compra|suministro)\b", "600000000", "Compras de mercaderías"),
]


async def predict_pgc_expense_account(
    db: Optional[AsyncSession],
    company_id: Union[str, int],
    issuer_cif: Optional[str],
    concept_summary: Optional[str],
    issuer_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Predice y autoasigna la subcuenta contable del PGC por autoaprendizaje o heurística.

    1. Consulta el histórico de facturas anteriores aprobadas del mismo proveedor en la empresa.
    2. Si existe un histórico consistente, devuelve la subcuenta más frecuente (autoaprendizaje).
    3. Si es la primera factura del proveedor, aplica la regla heurística basada en concepto/nombre.
    4. Fallback estándar a compras generales (600000000) o servicios exteriores (629000000).
    """
    comp_id_str = str(company_id)
    clean_cif = (issuer_cif or "").upper().strip()

    # 1. Autoaprendizaje basado en histórico de base de datos
    if db and clean_cif:
        try:
            # 1.1 Consultar si el proveedor ya está registrado con subcuenta habitual
            stmt_sup = select(Supplier.subcuenta_gasto_defecto).where(
                Supplier.company_id == comp_id_str,
                Supplier.cif == clean_cif
            ).limit(1)
            res_sup = await db.execute(stmt_sup)
            sup_acc = res_sup.scalar_one_or_none()
            if sup_acc:
                return {
                    "account": sup_acc,
                    "method": "HISTORICAL_AUTO_LEARNED",
                    "confidence": 0.98,
                    "description": f"Subcuenta predeterminada del proveedor {clean_cif}"
                }

            # 1.2 Consultar asientos del diario previos del grupo 6 para este emisor
            stmt_entry = (
                select(
                    AccountingEntryLine.subcuenta,
                    func.count(AccountingEntryLine.id).label("total_uses")
                )
                .join(Invoice, AccountingEntryLine.invoice_id == Invoice.id)
                .where(
                    Invoice.company_id == comp_id_str,
                    Invoice.issuer_cif == clean_cif,
                    AccountingEntryLine.subcuenta.like("6%")
                )
                .group_by(AccountingEntryLine.subcuenta)
                .order_by(desc("total_uses"))
                .limit(1)
            )
            result_entry = await db.execute(stmt_entry)
            row_entry = result_entry.first()
            if row_entry and row_entry[0]:
                return {
                    "account": row_entry[0],
                    "method": "HISTORICAL_AUTO_LEARNED",
                    "confidence": 0.95,
                    "description": f"Subcuenta histórica del Libro Diario para {clean_cif}"
                }
        except Exception as exc:
            logger.warning(f"Error consultando histórico contable para {clean_cif}: {exc}")

    # 2. Heurística de patrones de texto (concepto y razón social)
    text_to_evaluate = f"{issuer_name or ''} {concept_summary or ''}"
    import re
    for pattern, account_code, desc_name in DEFAULT_PGC_EXPENSE_RULES:
        if re.search(pattern, text_to_evaluate):
            return {
                "account": account_code,
                "method": "HEURISTIC_RULE_MATCH",
                "confidence": 0.85,
                "description": desc_name
            }

    # 3. Fallback genérico
    return {
        "account": "629000000",
        "method": "DEFAULT_FALLBACK",
        "confidence": 0.50,
        "description": "Otros servicios exteriores (Genérico)"
    }


async def check_duplicate_invoice(
    db: Optional[AsyncSession],
    company_id: Union[str, int],
    issuer_cif: Optional[str],
    invoice_number: Optional[str],
    total_amount: Optional[float],
    issue_date: Optional[Union[date, str]],
) -> Dict[str, Any]:
    """Comprueba en la base de datos si ya existe una factura idéntica o altamente sospechosa.

    Reglas de duplicidad:
    - Mismo company_id + mismo issuer_cif + mismo invoice_number
    - O mismo company_id + mismo issuer_cif + mismo total_amount + misma fecha de emisión
    """
    if not db or not issuer_cif or not invoice_number:
        return {"is_duplicate": False, "status": "CLEAR"}

    comp_id_str = str(company_id)
    clean_cif = issuer_cif.upper().strip()
    clean_num = invoice_number.strip()

    # Búsqueda 1: Mismo CIF y mismo número de factura
    stmt = select(Invoice).where(
        Invoice.company_id == comp_id_str,
        Invoice.issuer_cif == clean_cif,
        Invoice.invoice_number == clean_num,
    ).limit(1)

    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing:
        return {
            "is_duplicate": True,
            "status": "DUPLICATE_SUSPECTED",
            "matched_invoice_id": existing.id,
            "reason": f"Factura ya registrada previamente con el mismo número ({clean_num}) y emisor ({clean_cif})."
        }

    # Búsqueda 2: Coincidencia por importe y fecha si el número fuera impreciso
    if total_amount is not None and issue_date:
        parsed_date = None
        if isinstance(issue_date, str):
            try:
                parsed_date = datetime.strptime(issue_date, "%Y-%m-%d").date()
            except Exception:
                pass
        elif isinstance(issue_date, date):
            parsed_date = issue_date

        if parsed_date:
            stmt_amt = select(Invoice).where(
                Invoice.company_id == comp_id_str,
                Invoice.issuer_cif == clean_cif,
                Invoice.total_amount == float(total_amount),
                Invoice.issue_date == parsed_date,
            ).limit(1)
            result_amt = await db.execute(stmt_amt)
            existing_amt = result_amt.scalar_one_or_none()
            if existing_amt:
                return {
                    "is_duplicate": True,
                    "status": "DUPLICATE_SUSPECTED",
                    "matched_invoice_id": existing_amt.id,
                    "reason": f"Coincidencia exacta de importe ({total_amount} €) y fecha con la factura existente {existing_amt.invoice_number}."
                }

    return {"is_duplicate": False, "status": "CLEAR"}


async def extract_invoice_data(
    file_path: Union[str, Path],
    company_id: Union[str, int],
    db: Optional[AsyncSession] = None,
) -> Dict[str, Any]:
    """Motor integral de extracción de facturas con descifrado, IA y autoaprendizaje PGC.

    Args:
        file_path: Ruta en disco al archivo cifrado o en claro.
        company_id: ID de la empresa receptora.
        db: Sesión asíncrona de base de datos para verificación de duplicados y aprendizaje.

    Returns:
        Diccionario con los datos fiscales extraídos, análisis de duplicidad y subcuenta recomendada.
    """
    path_obj = Path(file_path).resolve()
    if not path_obj.exists():
        raise FileNotFoundError(f"No se encontró el archivo para extracción OCR en: {file_path}")

    # 1. Cargar bytes (descifrando si es un archivo con sufijo .enc)
    if path_obj.name.endswith(".enc"):
        raw_bytes = read_decrypted_file(path_obj)
        original_name = path_obj.name[:-4]  # Quitar .enc
    else:
        raw_bytes = path_obj.read_bytes()
        original_name = path_obj.name

    # Determinar tipo MIME
    mime_type, _ = mimetypes.guess_type(original_name)
    if not mime_type:
        if raw_bytes.startswith(b"%PDF-"):
            mime_type = "application/pdf"
        elif raw_bytes.startswith(b"\x89PNG"):
            mime_type = "image/png"
        else:
            mime_type = "image/jpeg"

    # 2. Extracción mediante motor multimodal de IA
    try:
        extraction_res = await extract_via_llm(
            file_bytes=raw_bytes,
            mime_type=mime_type,
            file_name=original_name,
        )
        extracted_data = extraction_res.model_dump()
    except Exception as exc:
        logger.error(f"Fallo en motor LLM de extracción para {original_name}: {exc}", exc_info=True)
        # Fallback estructurado mínimo para no interrumpir el flujo
        extracted_data = {
            "issuer_name": "Proveedor No Identificado",
            "issuer_cif": "",
            "receiver_name": "",
            "receiver_cif": "",
            "invoice_number": "S/N",
            "issue_date": date.today().isoformat(),
            "due_date": None,
            "total_base": 0.0,
            "total_tax": 0.0,
            "retention_amount": 0.0,
            "retention_rate": 0.0,
            "total_amount": 0.0,
            "tax_breakdown": [],
            "items": [],
            "concept_summary": f"Factura recibida {original_name}",
            "requires_review": True,
        }

    issuer_cif = extracted_data.get("issuer_cif") or ""
    invoice_number = extracted_data.get("invoice_number") or ""
    total_amount = extracted_data.get("total_amount") or 0.0
    issue_date = extracted_data.get("issue_date")

    # 3. Validación algorítmica del NIF/CIF
    cif_valid = False
    if issuer_cif:
        try:
            val_res = validate_spanish_id(issuer_cif)
            cif_valid = val_res.get("is_valid", False)
            if cif_valid and val_res.get("normalized_id"):
                extracted_data["issuer_cif"] = val_res["normalized_id"]
        except Exception:
            cif_valid = False
    extracted_data["issuer_cif_valid"] = cif_valid

    # 4. Prevención preventiva de duplicados (DUPLICATE_SUSPECTED)
    duplicate_info = await check_duplicate_invoice(
        db=db,
        company_id=company_id,
        issuer_cif=extracted_data.get("issuer_cif"),
        invoice_number=invoice_number,
        total_amount=total_amount,
        issue_date=issue_date,
    )
    extracted_data["duplicate_analysis"] = duplicate_info
    if duplicate_info["is_duplicate"]:
        extracted_data["requires_review"] = True
        extracted_data["duplicate_warning"] = duplicate_info["reason"]

    # 5. Memoria de categorización y autoaprendizaje PGC
    pgc_prediction = await predict_pgc_expense_account(
        db=db,
        company_id=company_id,
        issuer_cif=extracted_data.get("issuer_cif"),
        concept_summary=extracted_data.get("concept_summary"),
        issuer_name=extracted_data.get("issuer_name"),
    )
    extracted_data["suggested_account"] = pgc_prediction["account"]
    extracted_data["account_prediction_method"] = pgc_prediction["method"]
    extracted_data["account_confidence"] = pgc_prediction["confidence"]

    return extracted_data
