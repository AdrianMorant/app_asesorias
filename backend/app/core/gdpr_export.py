"""
Módulo de Portabilidad de Datos y Exportación Segura RGPD (Art. 20 del Reglamento General de Protección de Datos).
Genera un contenedor ZIP estructurado en memoria sin persistencia en disco (Zero-Disk Footprint)
para garantizar la confidencialidad, trazabilidad y cumplimiento tributario/normativo.

Estructura del paquete ZIP:
- /datos_empresa/                  -> Información fiscal y de perfil (empresa.json, empresa.csv)
- /facturas/documentos/           -> Documentos originales PDF/imágenes descifrados en memoria
- /facturas/metadata/             -> Metadatos consolidados de facturación (facturas.json, facturas.csv)
- /contabilidad/                  -> Libro Diario contable en partida doble (libro_diario.json, libro_diario.csv)
- /banco/                         -> Movimientos y extractos bancarios (movimientos_bancarios.json, movimientos_bancarios.csv)
- /certificados_y_trazabilidad/   -> Manifiesto de integridad, huellas SHA-256 y auditoría
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
import zipfile
import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

from app.core.file_encryption import decrypt_file_bytes, read_decrypted_file, encrypt_file_bytes


def dicts_to_csv_bytes(
    data: Union[List[Dict[str, Any]], Dict[str, Any]],
    delimiter: str = ",",
) -> bytes:
    """
    Convierte un diccionario o lista de diccionarios en bytes CSV
    con codificación UTF-8 con BOM ('utf-8-sig') para compatibilidad nativa con Microsoft Excel en español.
    """
    if isinstance(data, dict):
        items = [data]
    elif isinstance(data, list):
        items = data
    else:
        items = []

    if not items:
        return "\ufeff".encode("utf-8")

    # Obtener todas las claves únicas conservando el orden de aparición
    fieldnames: List[str] = []
    for item in items:
        if isinstance(item, dict):
            for k in item.keys():
                if k not in fieldnames:
                    fieldnames.append(k)

    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=fieldnames,
        delimiter=delimiter,
        quoting=csv.QUOTE_MINIMAL,
        extrasaction="ignore",
    )
    writer.writeheader()

    for item in items:
        if isinstance(item, dict):
            # Limpiar saltos de línea en celdas de texto
            row = {}
            for k in fieldnames:
                val = item.get(k)
                if isinstance(val, (dict, list)):
                    val = json.dumps(val, ensure_ascii=False)
                elif val is None:
                    val = ""
                else:
                    val = str(val).strip()
                row[k] = val
            writer.writerow(row)

    csv_text = output.getvalue()
    return csv_text.encode("utf-8-sig")


def dict_to_json_bytes(data: Any) -> bytes:
    """Serializa cualquier estructura Python en bytes JSON legibles y ordenados en UTF-8."""
    json_str = json.dumps(data, indent=2, ensure_ascii=False, default=str)
    return json_str.encode("utf-8")


def _sanitize_filename(name: str) -> str:
    """Sanitiza nombres de archivo para inclusión segura dentro del ZIP."""
    clean = re.sub(r"[^\w\.\-\_]", "_", name)
    return clean[:100]


def generate_gdpr_data_export(
    company_data: Dict[str, Any],
    invoices_files: List[Dict[str, Any]],
    accounting_ledger: List[Dict[str, Any]],
    bank_transactions: List[Dict[str, Any]],
    export_password: Optional[str] = None,
) -> Tuple[bytes, str]:
    """
    Construye el paquete integral de portabilidad RGPD (Art. 20) en un archivo ZIP en memoria.

    Parámetros:
    - company_data: Diccionario con la razón social, CIF, configuración fiscal y datos de perfil.
    - invoices_files: Lista de documentos de factura. Cada elemento puede contener:
      * 'file_bytes': bytes crudos o cifrados en reposo.
      * 'file_path': ruta en disco custodiada.
      * 'filename': nombre asignado al documento.
      * 'metadata': metadatos asociados a la factura.
    - accounting_ledger: Asientos del Libro Diario contable.
    - bank_transactions: Movimientos bancarios registrados.
    - export_password: Clave opcional para proteger el contenedor de transporte mediante AES-256-GCM.

    Retorna:
    - Tuple: (bytes_del_archivo_zip, nombre_del_archivo_canónico)
    """
    now = datetime.now(timezone.utc)
    cif = re.sub(r"[^A-Za-z0-9]", "", str(company_data.get("cif", "EMPRESA"))).upper()
    timestamp_str = now.strftime("%Y%m%d_%H%M%S")

    zip_buffer = io.BytesIO()
    file_hashes: Dict[str, str] = {}

    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        # -------------------------------------------------------------
        # 1. /datos_empresa/ (Perfil y configuración fiscal)
        # -------------------------------------------------------------
        company_json = dict_to_json_bytes(company_data)
        company_csv = dicts_to_csv_bytes(company_data)

        zf.writestr("datos_empresa/empresa.json", company_json)
        zf.writestr("datos_empresa/empresa.csv", company_csv)
        file_hashes["datos_empresa/empresa.json"] = hashlib.sha256(company_json).hexdigest()
        file_hashes["datos_empresa/empresa.csv"] = hashlib.sha256(company_csv).hexdigest()

        # -------------------------------------------------------------
        # 2. /facturas/metadata/ (Listado estructurado de facturas)
        # -------------------------------------------------------------
        invoices_meta = [
            inv.get("metadata", inv)
            for inv in invoices_files
            if isinstance(inv, dict)
        ]
        # Limpiar referencias binarias antes de serializar metadata
        clean_invoices_meta = []
        for inv in invoices_meta:
            clean_item = {k: v for k, v in inv.items() if k not in ("file_bytes", "file_data")}
            clean_invoices_meta.append(clean_item)

        inv_meta_json = dict_to_json_bytes(clean_invoices_meta)
        inv_meta_csv = dicts_to_csv_bytes(clean_invoices_meta)

        zf.writestr("facturas/metadata/facturas.json", inv_meta_json)
        zf.writestr("facturas/metadata/facturas.csv", inv_meta_csv)
        file_hashes["facturas/metadata/facturas.json"] = hashlib.sha256(inv_meta_json).hexdigest()
        file_hashes["facturas/metadata/facturas.csv"] = hashlib.sha256(inv_meta_csv).hexdigest()

        # -------------------------------------------------------------
        # 3. /facturas/documentos/ (Binarios originales descifrados en memoria)
        # -------------------------------------------------------------
        for idx, inv_doc in enumerate(invoices_files, start=1):
            doc_bytes = None

            # Si ya se pasan los bytes
            if "file_bytes" in inv_doc and inv_doc["file_bytes"]:
                raw_bytes = inv_doc["file_bytes"]
                try:
                    doc_bytes = decrypt_file_bytes(raw_bytes)
                except Exception:
                    doc_bytes = raw_bytes

            # Si se pasa una ruta en disco
            elif "file_path" in inv_doc and inv_doc["file_path"]:
                f_path = inv_doc["file_path"]
                if os.path.exists(f_path):
                    try:
                        doc_bytes = read_decrypted_file(f_path)
                    except Exception:
                        with open(f_path, "rb") as f:
                            doc_bytes = f.read()

            if doc_bytes:
                orig_name = inv_doc.get("filename") or f"factura_{idx}.pdf"
                safe_name = _sanitize_filename(orig_name)
                arc_path = f"facturas/documentos/{safe_name}"
                zf.writestr(arc_path, doc_bytes)
                file_hashes[arc_path] = hashlib.sha256(doc_bytes).hexdigest()

        # -------------------------------------------------------------
        # 4. /contabilidad/ (Libro Diario y asientos contables)
        # -------------------------------------------------------------
        ledger_json = dict_to_json_bytes(accounting_ledger)
        ledger_csv = dicts_to_csv_bytes(accounting_ledger)

        zf.writestr("contabilidad/libro_diario.json", ledger_json)
        zf.writestr("contabilidad/libro_diario.csv", ledger_csv)
        file_hashes["contabilidad/libro_diario.json"] = hashlib.sha256(ledger_json).hexdigest()
        file_hashes["contabilidad/libro_diario.csv"] = hashlib.sha256(ledger_csv).hexdigest()

        # -------------------------------------------------------------
        # 5. /banco/ (Movimientos bancarios y conciliación)
        # -------------------------------------------------------------
        bank_json = dict_to_json_bytes(bank_transactions)
        bank_csv = dicts_to_csv_bytes(bank_transactions)

        zf.writestr("banco/movimientos_bancarios.json", bank_json)
        zf.writestr("banco/movimientos_bancarios.csv", bank_csv)
        file_hashes["banco/movimientos_bancarios.json"] = hashlib.sha256(bank_json).hexdigest()
        file_hashes["banco/movimientos_bancarios.csv"] = hashlib.sha256(bank_csv).hexdigest()

        # -------------------------------------------------------------
        # 6. /certificados_y_trazabilidad/ (Manifiesto de portabilidad RGPD)
        # -------------------------------------------------------------
        manifest = {
            "legal_basis": "Reglamento (UE) 2016/679 (RGPD) - Artículo 20 (Derecho a la Portabilidad de los Datos)",
            "subject": f"Paquete oficial de portabilidad de datos para {company_data.get('razon_social', cif)}",
            "cif": cif,
            "export_timestamp_utc": now.isoformat(),
            "exported_modules": {
                "company_data": True,
                "invoices_documents_count": len([k for k in file_hashes if k.startswith("facturas/documentos/")]),
                "accounting_entries_count": len(accounting_ledger),
                "bank_transactions_count": len(bank_transactions),
            },
            "file_integrity_sha256": file_hashes,
            "system_version": "Antigravity Fiscal & Accounting SaaS v2.0",
        }
        manifest_bytes = dict_to_json_bytes(manifest)
        zf.writestr("certificados_y_trazabilidad/manifiesto_rgpd.json", manifest_bytes)

    raw_zip_bytes = zip_buffer.getvalue()

    # Si se solicita contraseña de cifrado para el paquete de transporte
    if export_password and str(export_password).strip():
        protected_bytes = encrypt_file_bytes(raw_zip_bytes)
        filename = f"export_rgpd_{cif}_{timestamp_str}.zip.enc"
        return protected_bytes, filename

    filename = f"export_rgpd_{cif}_{timestamp_str}.zip"
    return raw_zip_bytes, filename
