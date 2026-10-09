"""Módulo de Ingesta Automatizada de Facturas por Correo Electrónico (Email Ingestion Service).

Procesa webhooks entrantes de proveedores de correo (SendGrid Inbound Parse, Postmark, Mailgun)
y ejecuta el pipeline de defensa en profundidad:
1. Parsing y normalización agnóstica de payloads multipart/JSON.
2. Identificación automática de la empresa destinataria por alias/token en la dirección receptora.
3. Validación de remitentes y dominios contra listas negras de spam y abuso.
4. Filtrado estricto de adjuntos fiscales (.pdf, .png, .jpg, .jpeg, .webp).
5. Inspección binaria de seguridad (Magic Bytes, prevención de Path Traversal y anti-malware).
6. Cifrado simétrico AES-256-GCM en reposo previo a su encolado para extracción OCR/IA.
"""

from __future__ import annotations

import base64
import email.utils
import os
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

from app.core.config import settings
from app.core.file_encryption import save_encrypted_file, FileEncryptionError
from app.core.file_inspector import (
    ALLOWED_EXTENSIONS,
    FileSecurityViolationError,
    inspect_file_bytes,
    sanitize_filename,
)


class EmailIngestionError(Exception):
    """Excepción específica para errores de procesamiento, seguridad o identificación de correos inbound."""
    pass


# Lista predeterminada de dominios de correo temporal, desechable o de spam conocido
DEFAULT_BLACKLIST_DOMAINS: Set[str] = {
    "mailinator.com",
    "10minutemail.com",
    "guerrillamail.com",
    "temp-mail.org",
    "tempmail.com",
    "throwawaymail.com",
    "yopmail.com",
    "sharklasers.com",
    "trashmail.com",
    "dispostable.com",
    "fakeinbox.com",
    "spam4.me",
    "grr.la",
    "getairmail.com",
}


def get_blacklist_domains() -> Set[str]:
    """Obtiene el conjunto de dominios en lista negra combinando los predeterminados y variables de entorno."""
    configured_domains = os.getenv("EMAIL_BLACKLIST_DOMAINS", "")
    domains = set(DEFAULT_BLACKLIST_DOMAINS)
    if configured_domains:
        for domain in configured_domains.split(","):
            cleaned = domain.strip().lower()
            if cleaned:
                domains.add(cleaned)
    return domains


def get_blacklist_senders() -> Set[str]:
    """Obtiene el conjunto de direcciones de correo remitentes bloqueadas específicamente."""
    configured_senders = os.getenv("EMAIL_BLACKLIST_SENDERS", "")
    senders: Set[str] = set()
    if configured_senders:
        for sender in configured_senders.split(","):
            cleaned = sender.strip().lower()
            if cleaned:
                senders.add(cleaned)
    return senders


def extract_clean_email(raw_address: str) -> str:
    """Extrae y normaliza la dirección de correo electrónico limpia desde una cabecera RFC 5322."""
    if not raw_address:
        return ""
    
    # 1. Intentar parsear nombre y dirección estándar (ej. "Empresa S.L. <facturas@empresa.com>")
    _, parsed_email = email.utils.parseaddr(raw_address)
    if parsed_email and "@" in parsed_email:
        return parsed_email.strip().lower()
    
    # 2. Búsqueda por expresión regular si la cabecera venía mal formateada
    match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", raw_address)
    if match:
        return match.group(0).strip().lower()
    
    return raw_address.strip().lower()


def identify_company_target(to_address: str) -> Dict[str, Any]:
    """Identifica la empresa receptora a partir de la dirección de destino o token en el alias.

    Patrones soportados:
    - facturas-{company_slug}@dominio.com
    - inbox+{company_id_or_slug}@dominio.com
    - {company_slug}@dominio.com (si la parte local no es genérica)
    - alias+{uuid}@dominio.com

    Args:
        to_address: Dirección de correo destinataria recibida en el webhook.

    Returns:
        Diccionario con 'company_id', 'company_slug' y 'company_token'.

    Raises:
        EmailIngestionError: Si no se puede reconocer ninguna empresa o token en la dirección.
    """
    clean_to = extract_clean_email(to_address)
    if not clean_to or "@" not in clean_to:
        raise EmailIngestionError(f"Destinatario de correo inválido o no suministrado: '{to_address}'")

    local_part = clean_to.split("@")[0].strip().lower()

    company_id: Optional[Union[int, str]] = None
    company_slug: Optional[str] = None
    company_token: Optional[str] = None

    # Patrón 1: facturas-{slug} o facturas+{slug}
    match_facturas = re.match(r"^facturas[-+]([a-zA-Z0-9_\-]+)$", local_part)
    if match_facturas:
        company_token = match_facturas.group(1)

    # Patrón 2: inbox+{token} o buzón+{token}
    if not company_token:
        match_inbox = re.match(r"^(?:inbox|buzon|factura)[-+]([a-zA-Z0-9_\-]+)$", local_part)
        if match_inbox:
            company_token = match_inbox.group(1)

    # Patrón 3: cualquier_prefijo+{token} (sub-addressing / plus-addressing estándar RFC 5233)
    if not company_token and "+" in local_part:
        parts = local_part.split("+", 1)
        if len(parts) == 2 and parts[1]:
            company_token = parts[1]

    # Patrón 4: slug directo si no es una palabra genérica de buzón
    generic_boxes = {"inbox", "facturas", "billing", "info", "admin", "soporte", "contacto", "postmaster"}
    if not company_token and local_part not in generic_boxes and len(local_part) >= 2:
        company_token = local_part

    if not company_token:
        raise EmailIngestionError(
            f"No se pudo identificar una empresa receptora a partir de la dirección de destino '{to_address}'. "
            "Se requiere un alias o token válido (ej. facturas-{empresa}@... o inbox+{id}@...)."
        )

    # Clasificar el token como id numérico o slug
    if company_token.isdigit():
        company_id = int(company_token)
    elif re.match(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", company_token, re.I):
        company_id = company_token.lower()
    else:
        company_slug = company_token.lower()

    return {
        "company_id": company_id,
        "company_slug": company_slug,
        "company_token": company_token,
    }


def validate_sender_reputation(from_email: str) -> None:
    """Verifica que el remitente o su dominio no pertenezcan a listas negras de spam o remitentes hostiles.

    Args:
        from_email: Dirección de correo del remitente.

    Raises:
        EmailIngestionError: Si el remitente o su dominio están en listas negras.
    """
    clean_sender = extract_clean_email(from_email)
    if not clean_sender or "@" not in clean_sender:
        raise EmailIngestionError(f"Dirección de remitente ausente o inválida: '{from_email}'")

    blacklist_senders = get_blacklist_senders()
    if clean_sender in blacklist_senders:
        raise EmailIngestionError(
            f"El remitente '{clean_sender}' se encuentra en la lista negra de remitentes bloqueados."
        )

    domain = clean_sender.split("@")[-1].strip().lower()
    blacklist_domains = get_blacklist_domains()
    if domain in blacklist_domains:
        raise EmailIngestionError(
            f"El dominio del remitente '@{domain}' se encuentra en la lista negra de dominios no seguros."
        )


def _extract_attachments_from_payload(payload: dict) -> List[Dict[str, Any]]:
    """Extrae adjuntos embebidos en el payload de proveedores como Postmark o SendGrid."""
    extracted: List[Dict[str, Any]] = []

    # Caso 1: Postmark Inbound Webhook ("Attachments": [{"Name": ..., "Content": base64, "ContentType": ...}])
    if "Attachments" in payload and isinstance(payload["Attachments"], list):
        for item in payload["Attachments"]:
            if isinstance(item, dict):
                name = item.get("Name") or item.get("Filename") or "adjunto"
                raw_content = item.get("Content") or ""
                content_type = item.get("ContentType") or "application/octet-stream"
                
                try:
                    file_bytes = base64.b64decode(raw_content) if isinstance(raw_content, str) else raw_content
                except Exception as exc:
                    raise EmailIngestionError(f"Error decodificando adjunto base64 '{name}': {str(exc)}") from exc
                
                extracted.append({
                    "filename": name,
                    "content": file_bytes,
                    "content_type": content_type,
                    "size": len(file_bytes),
                })

    # Caso 2: Estructuras genéricas con "attachments" en el payload JSON
    elif "attachments" in payload and isinstance(payload["attachments"], list):
        for item in payload["attachments"]:
            if isinstance(item, dict):
                name = item.get("filename") or item.get("name") or "adjunto"
                content = item.get("content") or item.get("data") or b""
                content_type = item.get("content_type") or item.get("type") or "application/octet-stream"
                
                if isinstance(content, str):
                    try:
                        content = base64.b64decode(content)
                    except Exception:
                        content = content.encode("utf-8")
                
                extracted.append({
                    "filename": name,
                    "content": content,
                    "content_type": content_type,
                    "size": len(content),
                })

    return extracted


def parse_inbound_email(
    payload: Dict[str, Any],
    raw_attachments: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Parsea de forma unificada un webhook de correo electrónico entrante (SendGrid, Postmark, Mailgun).

    1. Extrae remitente, destinatario, asunto y cuerpo en texto plano.
    2. Identifica y valida a qué empresa pertenece el buzón destino.
    3. Verifica que el remitente o dominio no esté en la lista negra.
    4. Normaliza los archivos adjuntos binarios recibidos.

    Args:
        payload: Diccionario recibido en la petición webhook (JSON o multipart parseado).
        raw_attachments: Lista opcional de adjuntos binarios provistos en multipart form data.
            Cada elemento debe contener 'filename' y 'content' (bytes).

    Returns:
        Diccionario con los datos consolidados:
        - from_email: Remitente verificado
        - to_email: Destinatario limpio
        - subject: Asunto
        - body_plain: Cuerpo del correo en texto plano
        - company_id: ID de la empresa receptora (o None)
        - company_slug: Slug de la empresa receptora (o None)
        - company_token: Identificador extraído del alias
        - attachments: Lista de adjuntos en memoria normalizados

    Raises:
        EmailIngestionError: Si el correo carece de campos obligatorios, está en lista negra
            o no pertenece a una empresa registrada.
    """
    if not isinstance(payload, dict):
        raise EmailIngestionError("El payload del webhook debe ser un diccionario.")

    # 1. Extracción de Remitente (from_email)
    raw_from = (
        payload.get("from")
        or payload.get("From")
        or payload.get("sender")
        or payload.get("Sender")
        or payload.get("from_email")
        or ""
    )
    from_email = extract_clean_email(str(raw_from))
    if not from_email:
        raise EmailIngestionError("No se encontró una dirección de remitente válida en el correo entrante.")

    # Validar reputación y listas negras
    validate_sender_reputation(from_email)

    # 2. Extracción de Destinatario (to_email)
    raw_to = (
        payload.get("to")
        or payload.get("To")
        or payload.get("recipient")
        or payload.get("Recipient")
        or payload.get("to_email")
        or ""
    )
    to_email = extract_clean_email(str(raw_to))
    if not to_email:
        raise EmailIngestionError("No se encontró una dirección de destinatario válida en el correo entrante.")

    # Identificar la empresa receptora
    company_target = identify_company_target(to_email)

    # 3. Extracción de Asunto (subject)
    subject = str(payload.get("subject") or payload.get("Subject") or "(Sin asunto)").strip()

    # 4. Extracción de Cuerpo en Texto Plano (body_plain)
    body_plain = str(
        payload.get("body_plain")
        or payload.get("text")
        or payload.get("TextBody")
        or payload.get("body-plain")
        or payload.get("stripped-text")
        or payload.get("stripped_text")
        or ""
    ).strip()

    # Fallback si solo se proporcionó HTML
    if not body_plain:
        raw_html = payload.get("html") or payload.get("HtmlBody") or payload.get("body-html") or ""
        if raw_html:
            # Eliminar etiquetas HTML de forma básica para preservar el texto legible
            body_plain = re.sub(r"<[^>]+>", " ", str(raw_html))
            body_plain = re.sub(r"\s+", " ", body_plain).strip()

    # 5. Normalización y unificación de archivos adjuntos
    consolidated_attachments: List[Dict[str, Any]] = []

    # 5.1 Adjuntos embebidos en el payload JSON (ej. Postmark)
    payload_attachments = _extract_attachments_from_payload(payload)
    consolidated_attachments.extend(payload_attachments)

    # 5.2 Adjuntos binarios directos (multipart/form-data de SendGrid o Mailgun)
    if raw_attachments:
        for att in raw_attachments:
            if isinstance(att, dict):
                filename = att.get("filename") or att.get("name") or "adjunto_desconocido"
                content = att.get("content") or att.get("data") or b""
                content_type = att.get("content_type") or att.get("type") or "application/octet-stream"

                # Si el contenido viene como string base64
                if isinstance(content, str):
                    try:
                        content = base64.b64decode(content)
                    except Exception:
                        content = content.encode("utf-8")

                if isinstance(content, bytes):
                    consolidated_attachments.append({
                        "filename": filename,
                        "content": content,
                        "content_type": content_type,
                        "size": len(content),
                    })

    return {
        "from_email": from_email,
        "to_email": to_email,
        "subject": subject,
        "body_plain": body_plain,
        "company_id": company_target["company_id"],
        "company_slug": company_target["company_slug"],
        "company_token": company_target["company_token"],
        "attachments": consolidated_attachments,
    }


def process_email_attachments(
    attachments: List[Dict[str, Any]],
    company_id: Union[int, str],
) -> List[Dict[str, Any]]:
    """Pipeline de seguridad, validación e ingesta cifrada para adjuntos de correo.

    1. Filtra los adjuntos aceptando únicamente formatos fiscales válidos (.pdf, .png, .jpg, .jpeg, .webp).
    2. Aplica 'sanitize_filename' para mitigar vectores de Path Traversal y caracteres peligrosos.
    3. Inspecciona mediante 'inspect_file_bytes' los Magic Bytes reales y previene amenazas activas en PDF.
    4. Cifra los bytes aprobados mediante 'save_encrypted_file' (AES-256-GCM) en el directorio seguro.
    5. Retorna los metadatos de los archivos procesados listos para su encolado al motor de OCR/IA.

    Args:
        attachments: Lista de adjuntos binarios normalizados con 'filename' y 'content' (bytes).
        company_id: Identificador numérico o UUID de la empresa destinataria.

    Returns:
        Lista de diccionarios con metadatos de los archivos salvaguardados y aprobados:
        - filename: Nombre de archivo sanitizado y seguro
        - original_filename: Nombre de archivo original recibido
        - encrypted_path: Ruta absoluta al archivo cifrado en disco
        - sha256: Hash criptográfico SHA-256 del binario original
        - size_bytes: Tamaño exacto en bytes
        - mime_type: Tipo MIME seguro detectado por Magic Bytes
        - company_id: ID de la empresa vinculada

    Raises:
        EmailIngestionError: Si ocurre un error irrecuperable de seguridad o almacenamiento.
    """
    if not attachments:
        return []

    processed_files: List[Dict[str, Any]] = []

    # Directorio de almacenamiento seguro organizado por empresa
    company_subfolder = f"company_{company_id}"
    destination_dir = settings.UPLOAD_DIR / company_subfolder / "inbound_emails"
    destination_dir.mkdir(parents=True, exist_ok=True)

    for att in attachments:
        if not isinstance(att, dict):
            continue

        raw_filename = att.get("filename") or "archivo_sin_nombre"
        raw_content = att.get("content") or b""

        if not isinstance(raw_content, bytes):
            if isinstance(raw_content, str):
                try:
                    raw_content = base64.b64decode(raw_content)
                except Exception:
                    raw_content = raw_content.encode("utf-8")
            else:
                continue

        # 1. Sanitizar nombre para aislarlo de Path Traversal antes de verificar extensión
        safe_name = sanitize_filename(raw_filename)
        ext = Path(safe_name).suffix.lower()

        # Filtrar adjuntos descartando firmas de email (.gif), calendarios (.ics), ejecutables, etc.
        if ext not in ALLOWED_EXTENSIONS:
            # Descartar pacíficamente archivos no admitidos en el flujo de facturación
            continue

        # 2. Inspección profunda de Magic Bytes y análisis de amenazas estáticas en PDF
        try:
            inspection = inspect_file_bytes(
                data=raw_content,
                filename=safe_name,
            )
        except FileSecurityViolationError as sec_err:
            raise EmailIngestionError(
                f"Violación de seguridad al procesar el adjunto '{raw_filename}': {str(sec_err)}"
            ) from sec_err
        except Exception as exc:
            raise EmailIngestionError(
                f"Error al inspeccionar el archivo '{raw_filename}': {str(exc)}"
            ) from exc

        # 3. Generación de nombre único y custodia cifrada en reposo (AES-256-GCM)
        unique_token = uuid.uuid4().hex
        encrypted_filename = f"{unique_token}_{safe_name}.enc"
        encrypted_target_path = destination_dir / encrypted_filename

        try:
            save_encrypted_file(
                file_path=encrypted_target_path,
                raw_bytes=raw_content,
            )
        except FileEncryptionError as enc_err:
            raise EmailIngestionError(
                f"Fallo al cifrar y guardar el adjunto '{safe_name}': {str(enc_err)}"
            ) from enc_err
        except Exception as exc:
            raise EmailIngestionError(
                f"Error de sistema de archivos al almacenar '{safe_name}': {str(exc)}"
            ) from exc

        # 4. Consolidar metadatos aprobados para el pipeline de OCR/IA
        file_metadata = {
            "filename": safe_name,
            "original_filename": raw_filename,
            "encrypted_path": str(encrypted_target_path.resolve()),
            "sha256": inspection["sha256"],
            "size_bytes": inspection["size_bytes"],
            "mime_type": inspection["detected_mime_type"],
            "company_id": company_id,
        }
        processed_files.append(file_metadata)

    return processed_files
