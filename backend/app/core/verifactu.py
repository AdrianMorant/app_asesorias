"""Módulo de Cumplimiento Tributario Español: Reglamento Verifactu (RD 1007/2023 y Ley 11/2021).

Marco Legal y Especificaciones Técnicas:
- Ley 11/2021, de 9 de julio, de medidas de prevención y lucha contra el fraude fiscal.
- Real Decreto 1007/2023, de 5 de diciembre: Reglamento de requisitos que deben adoptar
  los sistemas y programas informáticos que soporten procesos de facturación de empresarios y profesionales.
- Orden Ministerial HAC/1177/2024, de 17 de octubre: Especificaciones técnicas del registro de facturación,
  diseño del código QR tributario y algoritmo de encadenamiento de registros (Huella).

Componentes Implementados:
1. Algoritmo de Huella Criptográfica SHA-256 encadenada (Hash Chaining WORM).
2. Generador de URL canónica y Payload para el Código QR Tributario oficial de la AEAT.
3. Generador de imagen bidimensional QR en formato Base64 para estampado en factura PDF.
4. Modelo Pydantic del Registro de Facturación de Alta (VerifactuRecord).
"""

from __future__ import annotations

import io
import re
import base64
import hashlib
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Union
from pydantic import BaseModel, Field
import qrcode

# URLs oficiales de la Sede Electrónica de la Agencia Tributaria (AEAT)
AEAT_VERIFACTU_URL_PROD = "https://sede.agenciatributaria.gob.es/qr/verifactu"
AEAT_VERIFACTU_URL_PRE = "https://pre-sede.agenciatributaria.gob.es/qr/verifactu"

# Tipos de factura normalizados según Anexo Técnico AEAT
VALID_INVOICE_TYPES = {"F1", "F2", "F3", "R1", "R2", "R3", "R4", "R5"}


class VerifactuError(Exception):
    """Excepción base para validaciones y anomalías del subsistema Verifactu."""
    pass


def format_date_to_aeat(date_val: Union[str, datetime]) -> str:
    """Normaliza una fecha al formato canónico exigido por la AEAT: DD-MM-YYYY.

    Acepta formato ISO (YYYY-MM-DD), timestamps o formato ya normalizado.
    """
    if isinstance(date_val, datetime):
        return date_val.strftime("%d-%m-%Y")

    cleaned = str(date_val).strip()
    # Si viene en formato ISO (YYYY-MM-DD o YYYY-MM-DDTHH:MM:SS)
    match_iso = re.match(r"^(\d{4})-(\d{2})-(\d{2})", cleaned)
    if match_iso:
        year, month, day = match_iso.groups()
        return f"{day}-{month}-{year}"

    # Si ya viene en formato DD-MM-YYYY
    match_dd_mm = re.match(r"^(\d{2})-(\d{2})-(\d{4})$", cleaned)
    if match_dd_mm:
        return cleaned

    # Fallback si viene en formato DD/MM/YYYY
    match_slash = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", cleaned)
    if match_slash:
        day, month, year = match_slash.groups()
        return f"{day}-{month}-{year}"

    return cleaned


def compute_verifactu_hash(
    nif_emisor: str,
    num_serie_factura: str,
    fecha_expedicion: Union[str, datetime],
    tipo_factura: str,
    cuota_total: float,
    importe_total: float,
    prev_hash: Optional[str] = "",
) -> str:
    """Calcula la huella criptográfica SHA-256 encadenada de un registro de facturación de alta.

    Según las especificaciones técnicas de la AEAT (Orden HAC/1177/2024), la cadena a resumir
    se genera mediante concatenación de campos canónicos en codificación UTF-8:
    `IDEmisorFactura={nif}&NumSerieFactura={serie}&FechaExpedicionFactura={fecha}&TipoFactura={tipo}&CuotaTotal={cuota:.2f}&ImporteTotal={total:.2f}&Huella={prev_hash}`

    - Importes con exactamente 2 decimales y punto como separador.
    - Si es la primera factura de la serie, el campo Huella va vacío (cadena vacía).
    - Retorna el hash SHA-256 formateado estrictamente en 64 caracteres en MAYÚSCULAS.

    Args:
        nif_emisor: NIF o CIF del obligado tributario emisor de la factura.
        num_serie_factura: Número y serie correlativo identificativo de la factura.
        fecha_expedicion: Fecha de expedición (se normaliza a DD-MM-YYYY).
        tipo_factura: Clave de tipo de factura (ej. 'F1', 'F2', 'R1').
        cuota_total: Importe total de la cuota tributaria repercutida (IVA + Recargo).
        importe_total: Importe total de la factura.
        prev_hash: Hash de la factura anterior en la serie (o '' si es la primera).

    Returns:
        Cadena hexadecimal en mayúsculas de 64 caracteres correspondiente al SHA-256.
    """
    clean_nif = (nif_emisor or "").strip().upper()
    clean_serie = (num_serie_factura or "").strip()
    clean_fecha = format_date_to_aeat(fecha_expedicion)
    clean_tipo = (tipo_factura or "F1").strip().upper()

    cuota_str = f"{float(cuota_total or 0.0):.2f}"
    importe_str = f"{float(importe_total or 0.0):.2f}"
    huella_ant = (prev_hash or "").strip().upper()

    canonical_string = (
        f"IDEmisorFactura={clean_nif}&"
        f"NumSerieFactura={clean_serie}&"
        f"FechaExpedicionFactura={clean_fecha}&"
        f"TipoFactura={clean_tipo}&"
        f"CuotaTotal={cuota_str}&"
        f"ImporteTotal={importe_str}&"
        f"Huella={huella_ant}"
    )

    return hashlib.sha256(canonical_string.encode("utf-8")).hexdigest().upper()


def generate_verifactu_qr_payload(
    nif_emisor: str,
    num_serie_factura: str,
    fecha_expedicion: Union[str, datetime],
    importe_total: float,
    hash_factura: Optional[str] = None,
    is_verifactu_mode: bool = True,
    test_mode: bool = False,
) -> str:
    """Genera la URL canónica del código QR tributario para cotejo con la AEAT.

    Permite a clientes y destinatarios escanear el QR en la factura física o PDF
    para contrastar la validez y alta en la Sede Electrónica de la Agencia Tributaria.

    Args:
        nif_emisor: NIF/CIF del emisor.
        num_serie_factura: Número y serie de la factura.
        fecha_expedicion: Fecha de expedición en formato DD-MM-YYYY.
        importe_total: Importe total con 2 decimales.
        hash_factura: Huella criptográfica SHA-256 opcional.
        is_verifactu_mode: Si True, indica sistema VERI*FACTU con remisión telemática.
        test_mode: Si True, apunta al entorno de preproducción / pruebas de la AEAT.

    Returns:
        URL canónica completa para el código QR.
    """
    base_url = AEAT_VERIFACTU_URL_PRE if test_mode else AEAT_VERIFACTU_URL_PROD
    clean_nif = (nif_emisor or "").strip().upper()
    clean_serie = (num_serie_factura or "").strip()
    clean_fecha = format_date_to_aeat(fecha_expedicion)
    importe_str = f"{float(importe_total or 0.0):.2f}"

    query_params = [
        f"nif={clean_nif}",
        f"numserie={clean_serie}",
        f"fecha={clean_fecha}",
        f"importe={importe_str}",
    ]

    # En sistemas no-verifactu o como parámetro complementario de cotejo de integridad
    if hash_factura:
        clean_hash = hash_factura.strip().upper()
        # La AEAT permite incluir los primeros caracteres o el hash completo para cotejo rápido
        query_params.append(f"hash={clean_hash[:16]}")

    return f"{base_url}?{'&'.join(query_params)}"


def generate_qr_code_image_base64(
    qr_payload: str,
    box_size: int = 8,
    border: int = 2,
    include_data_uri: bool = True,
) -> str:
    """Genera la imagen PNG del código QR y la codifica en Base64 para estampado en PDF.

    Args:
        qr_payload: URL o cadena a codificar dentro de la matriz QR.
        box_size: Tamaño de cada punto/módulo en píxeles.
        border: Margen de zona de silencio alrededor del QR (mínimo 2 según estándar).
        include_data_uri: Si True, antepone 'data:image/png;base64,'.

    Returns:
        Cadena Base64 con la imagen PNG lista para embeber en HTML o PyMuPDF.
    """
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,  # Nivel M (~15% de tolerancia a daños)
        box_size=box_size,
        border=border,
    )
    qr.add_data(qr_payload)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    encoded_b64 = base64.b64encode(buffer.getvalue()).decode("ascii")

    if include_data_uri:
        return f"data:image/png;base64,{encoded_b64}"
    return encoded_b64


class VerifactuRecord(BaseModel):
    """Esquema oficial del Registro de Facturación de Alta conforme al RD 1007/2023."""
    id_emisor_factura: str = Field(..., description="NIF o CIF del obligado tributario emisor")
    num_serie_factura: str = Field(..., description="Número y serie correlativa de la factura")
    fecha_expedicion: str = Field(..., description="Fecha de expedición en formato DD-MM-YYYY")
    tipo_factura: str = Field(default="F1", description="Tipo de factura (F1=Ordinaria, F2=Simplificada, R1..R5=Rectificativa)")
    descripcion_operacion: Optional[str] = Field(None, description="Descripción del concepto o naturaleza de la operación")
    cuota_total: float = Field(default=0.0, description="Cuota tributaria total repercutida en EUR")
    importe_total: float = Field(..., description="Importe total final de la factura en EUR")
    huella: str = Field(..., description="Hash SHA-256 encadenado de este registro (64 caracteres mayúsculas)")
    huella_anterior: Optional[str] = Field(default="", description="Huella SHA-256 de la factura inmediatamente anterior")
    fecha_hora_huso_gen_registro: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Timestamp ISO 8601 con huso horario exacto de generación del registro"
    )
    sistema_informatico: Dict[str, str] = Field(
        default_factory=lambda: {
            "nombre": "Konta AI - Facturación Verifactu",
            "version": "1.0.0",
            "nif_desarrollador": "B12345678",
        },
        description="Datos del software de facturación garante (Art. 12 RD 1007/2023)"
    )
    qr_payload: Optional[str] = Field(None, description="URL canónica del código QR para cotejo con la AEAT")
    qr_base64: Optional[str] = Field(None, description="Imagen PNG del código QR codificada en Base64")
    is_verifactu_mode: bool = Field(default=True, description="Indica si opera como Sistema de Emisión Verificable")


def create_verifactu_record(
    nif_emisor: str,
    num_serie_factura: str,
    fecha_expedicion: Union[str, datetime],
    importe_total: float,
    cuota_total: float = 0.0,
    tipo_factura: str = "F1",
    descripcion_operacion: Optional[str] = None,
    prev_hash: Optional[str] = "",
    is_verifactu_mode: bool = True,
    test_mode: bool = False,
    generate_qr: bool = True,
) -> VerifactuRecord:
    """Función de alto nivel que orquesta el cómputo de la huella, el QR y el registro formal Verifactu.

    Args:
        nif_emisor: NIF del emisor de la factura.
        num_serie_factura: Número y serie de la factura.
        fecha_expedicion: Fecha de emisión.
        importe_total: Total de la factura.
        cuota_total: Cuota total de impuestos.
        tipo_factura: Tipo de factura (F1 por defecto).
        descripcion_operacion: Concepto o detalle de la factura.
        prev_hash: Huella de la factura anterior.
        is_verifactu_mode: Modo Verifactu activo.
        test_mode: Entorno de pruebas de la AEAT.
        generate_qr: Si True, genera la imagen QR en Base64.

    Returns:
        Instancia validada de VerifactuRecord.
    """
    clean_fecha = format_date_to_aeat(fecha_expedicion)
    
    # 1. Cálculo matemático de la huella SHA-256 encadenada
    current_hash = compute_verifactu_hash(
        nif_emisor=nif_emisor,
        num_serie_factura=num_serie_factura,
        fecha_expedicion=clean_fecha,
        tipo_factura=tipo_factura,
        cuota_total=cuota_total,
        importe_total=importe_total,
        prev_hash=prev_hash or "",
    )

    # 2. Generación del payload URL del QR
    qr_url = generate_verifactu_qr_payload(
        nif_emisor=nif_emisor,
        num_serie_factura=num_serie_factura,
        fecha_expedicion=clean_fecha,
        importe_total=importe_total,
        hash_factura=current_hash,
        is_verifactu_mode=is_verifactu_mode,
        test_mode=test_mode,
    )

    # 3. Generación opcional de la imagen QR en Base64
    qr_img_b64 = None
    if generate_qr:
        try:
            qr_img_b64 = generate_qr_code_image_base64(qr_url)
        except Exception:
            qr_img_b64 = None

    return VerifactuRecord(
        id_emisor_factura=nif_emisor.strip().upper(),
        num_serie_factura=num_serie_factura.strip(),
        fecha_expedicion=clean_fecha,
        tipo_factura=tipo_factura.strip().upper(),
        descripcion_operacion=descripcion_operacion,
        cuota_total=round(float(cuota_total), 2),
        importe_total=round(float(importe_total), 2),
        huella=current_hash,
        huella_anterior=prev_hash or "",
        qr_payload=qr_url,
        qr_base64=qr_img_b64,
        is_verifactu_mode=is_verifactu_mode,
    )
