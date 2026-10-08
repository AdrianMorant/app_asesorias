import base64
import io
import json
import logging
import os
import re
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from app.core.config import settings
from app.schemas.invoice_extraction import (
    InvoiceExtractionResult,
    TaxBreakdownItem,
    InvoiceLineItem,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Eres un sistema de Inteligencia Artificial experto en fiscalidad y contabilidad española (Plan General Contable y normativa de la Agencia Estatal de Administración Tributaria - AEAT).
Tu misión es inspeccionar visualmente cada página de la factura adjunta y extraer de forma exhaustiva, exacta y matemáticamente rigurosa los datos fiscales y económicos.

NORMAS OBLIGATORIAS DE EXTRACCIÓN (ESPAÑA):
1. IDENTIFICACIÓN DE PARTES (EMISOR VS RECEPTOR):
   - EMISOR (Proveedor/Acreedor/Facturado por): Es la empresa o profesional que emite la factura, vende el bien o presta el servicio.
     * Nombre o razón social completa (ej. 'Telefónica de España S.A.U.', 'Iberdrola Clientes S.A.U.').
     * CIF / NIF / NIE español limpio, sin puntos, espacios ni guiones (ej. 'A28015865', 'B87654321', '12345678Z').
     * Dirección fiscal completa si aparece.
   - RECEPTOR (Cliente/Facturado a): Es la persona física o jurídica que adquiere el bien o servicio y recibe la factura.
     * Nombre o razón social del cliente.
     * CIF / NIF del cliente si figura.

2. NÚMERO Y FECHAS:
   - Número de Factura (invoice_number): Transcribe el número o serie completa exactamente como está impreso (ej. '2024/0014', 'FA-24-902', 'B-10293'). Si no consta ningún número, escribe 'S/N'.
   - Fecha de Emisión (issue_date): Extrae la fecha de expedición en formato estricto ISO 'YYYY-MM-DD' (año-mes-día).
   - Fecha de Vencimiento (due_date): Si consta fecha de pago o vencimiento, indícala en formato 'YYYY-MM-DD'. Si no consta, deja null.

3. DESGLOSE IMPOSITIVO (MULTI-IVA Y RECARGO):
   - Inspecciona la tabla de impuestos y desglosa cada tramo impositivo presente en el documento:
     * Tipos habituales en España: General (21.0%), Reducido (10.0%), Superreducido (4.0%), Exento/0% (0.0%).
     * Para cada tipo: especifica base_amount (base imponible), tax_rate (tipo %) y tax_amount (cuota de IVA).
   - Calcula:
     * total_base = Suma exacta de todas las bases imponibles.
     * total_tax = Suma exacta de todas las cuotas de IVA.

4. RETENCIONES (IRPF):
   - Muy habitual en profesionales independientes (15% o 7%) y alquileres/arrendamientos (19%).
   - Si la factura incluye retención de IRPF:
     * retention_rate: Porcentaje de retención (ej. 15.0).
     * retention_amount: Importe restado en concepto de retención IRPF.
   - Si no hay retención, retention_rate = 0.0 y retention_amount = 0.0.

5. TOTAL DE LA FACTURA Y CUADRE ARITMÉTICO:
   - El total debe cuadrar con la fórmula fiscal española:
     total_amount = total_base + total_tax - retention_amount (+ recargo_equivalencia si aplica).
   - Respeta el importe total exacto reflejado en la factura (redondeado a 2 decimales).

6. RESUMEN DEL CONCEPTO Y LÍNEAS:
   - concept_summary: Proporciona una descripción sintetizada y profesional del gasto o servicio para el concepto del asiento contable en el Diario (ej. 'Suministro eléctrico del mes de marzo', 'Servicios de asesoría jurídica laboral', 'Compra de material de oficina e imprenta').
   - items: Partidas individuales facturadas (descripción, cantidad, precio unitario, total línea) si figuran en el documento.
"""


def convert_pdf_to_images(file_bytes: bytes, max_pages: int = 10) -> List[bytes]:
    """
    Convierte las páginas de un archivo PDF en imágenes PNG de alta resolución (200 DPI)
    usando PyMuPDF para permitir análisis visual multimodal directo por el LLM.
    """
    try:
        import pymupdf

        doc = pymupdf.open(stream=file_bytes, filetype="pdf")
        images: List[bytes] = []
        pages_to_render = min(len(doc), max_pages)

        # Matriz de resolución de 200 DPI (zoom 200/72 ≈ 2.77)
        zoom = 200 / 72
        mat = pymupdf.Matrix(zoom, zoom)

        for i in range(pages_to_render):
            page = doc[i]
            pix = page.get_pixmap(matrix=mat, alpha=False)
            images.append(pix.tobytes("png"))

        doc.close()
        if images:
            return images
    except Exception as e:
        logger.warning(
            f"No se pudo rasterizar el PDF a imágenes con PyMuPDF: {e}. Se intentará extracción alternativa."
        )

    return []


def clean_tax_id(tax_id: Optional[str]) -> str:
    """Limpia puntos, guiones y espacios de un CIF/NIF español."""
    if not tax_id:
        return ""
    return re.sub(r"[\s\.\-_/]", "", tax_id).strip().upper()


def postprocess_extraction(data: InvoiceExtractionResult) -> InvoiceExtractionResult:
    """
    Normaliza y asegura la consistencia aritmética y fiscal de los datos extraídos.
    """
    # 1. Limpiar NIF/CIF
    if data.issuer_tax_id:
        data.issuer_tax_id = clean_tax_id(data.issuer_tax_id)
    if data.recipient_tax_id:
        data.recipient_tax_id = clean_tax_id(data.recipient_tax_id)

    # 2. Redondeo a 2 decimales
    data.total_base = round(float(data.total_base or 0.0), 2)
    data.total_tax = round(float(data.total_tax or 0.0), 2)
    data.total_amount = round(float(data.total_amount or 0.0), 2)
    data.retention_rate = round(float(data.retention_rate or 0.0), 2)
    data.retention_amount = round(float(data.retention_amount or 0.0), 2)

    # 3. Si no hay desglose en taxes pero hay base y cuota, inferir tramo
    if not data.taxes and data.total_base > 0:
        inferred_rate = (
            round((data.total_tax / data.total_base) * 100, 1)
            if data.total_tax > 0
            else 0.0
        )
        for std_rate in [21.0, 10.0, 4.0, 0.0]:
            if abs(inferred_rate - std_rate) < 0.8:
                inferred_rate = std_rate
                break
        data.taxes = [
            TaxBreakdownItem(
                tax_rate=inferred_rate,
                base_amount=data.total_base,
                tax_amount=data.total_tax,
            )
        ]
    else:
        for t in data.taxes:
            t.tax_rate = round(float(t.tax_rate or 0.0), 2)
            t.base_amount = round(float(t.base_amount or 0.0), 2)
            t.tax_amount = round(float(t.tax_amount or 0.0), 2)

    # 4. Asegurar cuadre aritmético si total_amount viene a 0
    if data.total_amount == 0.0 and (data.total_base > 0 or data.total_tax > 0):
        data.total_amount = round(
            data.total_base + data.total_tax - data.retention_amount, 2
        )

    return data


async def extract_invoice_data(
    file_bytes: bytes, mime_type: str, file_name: str
) -> InvoiceExtractionResult:
    """
    Extrae la información fiscal real de la factura mediante IA multimodal.
    Utiliza OpenAI (GPT-4o-mini) con Structured Outputs como motor principal predeterminado.
    """
    # 1. Recargar .env en caliente por si se actualizó la clave
    env_file = Path(__file__).resolve().parent.parent.parent / ".env"
    if env_file.exists():
        load_dotenv(dotenv_path=env_file, override=True)

    openai_key = (
        os.getenv("OPENAI_API_KEY", "").strip()
        or (settings.OPENAI_API_KEY or "").strip()
    )
    gemini_key = (
        os.getenv("GEMINI_API_KEY", "").strip()
        or (settings.GEMINI_API_KEY or "").strip()
    )
    provider = (
        os.getenv(
            "LLM_PROVIDER",
            os.getenv("DEFAULT_LLM_PROVIDER", getattr(settings, "LLM_PROVIDER", "openai")),
        )
        .lower()
        .strip()
    )
    openai_model = (
        os.getenv("OPENAI_MODEL", getattr(settings, "OPENAI_MODEL", "gpt-4o-mini"))
        or "gpt-4o-mini"
    ).strip()

    if not openai_key and not gemini_key:
        raise ValueError(
            "No se ha configurado ninguna clave de API en el archivo 'backend/.env' "
            "(falta OPENAI_API_KEY). Por favor, introduce la clave de OpenAI en backend/.env "
            "para habilitar la extracción de facturas con GPT-4o-mini."
        )

    # 2. Determinar tipo real de archivo y normalizar MIME
    clean_fn = file_name.lower().strip()
    clean_mime = (mime_type or "").lower().strip()

    if clean_fn.endswith((".jpg", ".jpeg")) or clean_mime in (
        "image/jpeg",
        "image/jpg",
        "image/pjpeg",
    ):
        clean_mime = "image/jpeg"
    elif clean_fn.endswith(".png") or clean_mime == "image/png":
        clean_mime = "image/png"
    elif clean_fn.endswith(".webp") or clean_mime == "image/webp":
        clean_mime = "image/webp"
    elif clean_fn.endswith(".pdf") or clean_mime == "application/pdf":
        clean_mime = "application/pdf"

    is_pdf = clean_mime == "application/pdf"
    is_image = (
        clean_mime in ("image/jpeg", "image/png", "image/webp")
        or clean_mime.startswith("image/")
    )

    # 3. Preparar imágenes rasterizadas si el archivo es un PDF
    rendered_images: List[bytes] = []
    if is_pdf:
        rendered_images = convert_pdf_to_images(file_bytes, max_pages=10)

    # 4. Establecer orden de proveedores (prioridad OpenAI)
    providers_to_try = []
    if provider == "openai" or not gemini_key:
        if openai_key:
            providers_to_try.append("openai")
        if gemini_key:
            providers_to_try.append("gemini")
    else:
        if gemini_key:
            providers_to_try.append("gemini")
        if openai_key:
            providers_to_try.append("openai")

    last_error_message = ""

    for prov in providers_to_try:
        # =====================================================================
        # A. MOTOR PRINCIPAL: OPENAI (GPT-4o-mini) CON STRUCTURED OUTPUTS
        # =====================================================================
        if prov == "openai":
            try:
                from openai import OpenAI

                logger.info(
                    f"Iniciando extracción multimodal con OpenAI ({openai_model}) para: {file_name}"
                )
                client = OpenAI(api_key=openai_key)

                user_content = [
                    {
                        "type": "text",
                        "text": (
                            "Inspecciona exhaustivamente esta factura comercial o ticket de compra. "
                            "Extrae con precisión matemática todos los datos fiscales (emisor, CIF/NIF, receptor, "
                            "número, fecha, desglose multi-IVA con bases y cuotas, retención IRPF y total) "
                            "según el esquema estructurado estricto."
                        ),
                    }
                ]

                # Adjuntar imágenes en Base64 para el modelo multimodal
                if is_pdf and rendered_images:
                    for img_bytes in rendered_images:
                        b64 = base64.b64encode(img_bytes).decode("utf-8")
                        user_content.append(
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{b64}",
                                    "detail": "high",
                                },
                            }
                        )
                else:
                    b64 = base64.b64encode(file_bytes).decode("utf-8")
                    img_mime = clean_mime if is_image else "image/png"
                    user_content.append(
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{img_mime};base64,{b64}",
                                "detail": "high",
                            },
                        }
                    )

                messages = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ]

                # Llamada con Structured Outputs de OpenAI (Beta Parse)
                completion = client.beta.chat.completions.parse(
                    model=openai_model,
                    messages=messages,
                    response_format=InvoiceExtractionResult,
                    temperature=0.0,
                )

                choice = completion.choices[0]
                if choice.message.parsed:
                    extracted: InvoiceExtractionResult = choice.message.parsed
                    logger.info(
                        f"Extracción con OpenAI ({openai_model}) completada exitosamente para {file_name}. "
                        f"Emisor: {extracted.issuer_name} ({extracted.issuer_tax_id}), Total: {extracted.total_amount} €"
                    )
                    return postprocess_extraction(extracted)
                elif choice.message.refusal:
                    raise ValueError(
                        f"OpenAI rechazó el procesamiento del documento: {choice.message.refusal}"
                    )
                else:
                    raise ValueError(
                        "OpenAI devolvió una respuesta vacía o sin estructura válida."
                    )

            except Exception as e:
                err_str = str(e)
                logger.error(f"Error procesando factura con OpenAI ({openai_model}): {err_str}")
                if (
                    "invalid_api_key" in err_str
                    or "Incorrect API key" in err_str
                    or "401" in err_str
                ):
                    last_error_message = (
                        "La clave OPENAI_API_KEY no es válida o está deshabilitada en backend/.env. "
                        "Verifica tu clave de API en platform.openai.com."
                    )
                elif (
                    "insufficient_quota" in err_str
                    or "quota" in err_str.lower()
                    or "billing" in err_str.lower()
                ):
                    last_error_message = (
                        "Se ha superado la cuota o saldo de tu cuenta de OpenAI (Error de facturación/cuota)."
                    )
                elif "429" in err_str or "rate_limit" in err_str.lower():
                    last_error_message = (
                        "Límite de peticiones por minuto alcanzado en OpenAI (Error 429 Rate Limit)."
                    )
                else:
                    last_error_message = f"Error en OpenAI ({openai_model}): {err_str}"

        # =====================================================================
        # B. PROVEEDOR SECUNDARIO: GEMINI (SI ESTÁ PRESENTE)
        # =====================================================================
        elif prov == "gemini":
            try:
                from google import genai
                from google.genai import types

                client = genai.Client(api_key=gemini_key)
                prompt_contents = []

                if is_image:
                    img_mime = (
                        clean_mime
                        if clean_mime in ("image/jpeg", "image/png", "image/webp")
                        else "image/jpeg"
                    )
                    prompt_contents.append(
                        types.Part.from_bytes(data=file_bytes, mime_type=img_mime)
                    )
                elif is_pdf:
                    if rendered_images:
                        for img_bytes in rendered_images:
                            prompt_contents.append(
                                types.Part.from_bytes(data=img_bytes, mime_type="image/png")
                            )
                    else:
                        prompt_contents.append(
                            types.Part.from_bytes(data=file_bytes, mime_type="application/pdf")
                        )
                else:
                    prompt_contents.append(
                        types.Part.from_bytes(
                            data=file_bytes,
                            mime_type=clean_mime or "application/octet-stream",
                        )
                    )

                prompt_contents.append(
                    "Extrae los datos fiscales según el esquema estructurado JSON."
                )

                response = client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=prompt_contents,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        response_mime_type="application/json",
                        response_schema=InvoiceExtractionResult,
                        temperature=0.0,
                    ),
                )

                if response and response.text:
                    raw_text = response.text.strip()
                    if raw_text.startswith("```json"):
                        raw_text = raw_text[7:]
                    if raw_text.startswith("```"):
                        raw_text = raw_text[3:]
                    if raw_text.endswith("```"):
                        raw_text = raw_text[:-3]
                    result = InvoiceExtractionResult.model_validate_json(raw_text.strip())
                    return postprocess_extraction(result)

            except Exception as g_err:
                logger.warning(f"Fallback Gemini no disponible: {g_err}")
                if not last_error_message:
                    last_error_message = f"Error en Gemini API: {str(g_err)}"

    raise ValueError(
        last_error_message
        or "No se pudo extraer la factura con el motor configurado en backend/.env."
    )
