import os
import re
import shutil
from pathlib import Path
from typing import Optional, Dict
from app.core.config import settings
from app.models.invoice import Invoice

def get_period_folder(month: int, periodicity: str = "Trimestral") -> str:
    """
    Calcula la carpeta del periodo fiscal según la periodicidad configurada:
    - Trimestral: T1, T2, T3, T4
    - Mensual: 01_Enero, 02_Febrero, ..., 12_Diciembre
    - Anual: Anual
    """
    p = (periodicity or "Trimestral").strip().capitalize()
    if p == "Mensual":
        months = {
            1: "01_Enero", 2: "02_Febrero", 3: "03_Marzo",
            4: "04_Abril", 5: "05_Mayo", 6: "06_Junio",
            7: "07_Julio", 8: "08_Agosto", 9: "09_Septiembre",
            10: "10_Octubre", 11: "11_Noviembre", 12: "12_Diciembre"
        }
        return months.get(month, f"{month:02d}")
    elif p == "Anual":
        return "Anual"
    else:
        # Trimestral por defecto
        if month in (1, 2, 3):
            return "T1"
        elif month in (4, 5, 6):
            return "T2"
        elif month in (7, 8, 9):
            return "T3"
        else:
            return "T4"

def sanitize_filename_part(part: str) -> str:
    """Elimina caracteres incompatibles con el sistema de archivos (Windows / Linux)."""
    if not part:
        return "SN"
    return re.sub(r'[/\\:*?"<>|\s]', '_', part.strip())

def resolve_base_directory(base_path_str: Optional[str] = None) -> Path:
    """Resuelve la ruta base absoluta o relativa del almacenamiento."""
    if not base_path_str or base_path_str.strip() in ("", "storage"):
        return settings.STORAGE_DIR
    p = Path(base_path_str.strip())
    if not p.is_absolute():
        return settings.BASE_DIR / p
    return p

def get_proposed_archive_path(
    invoice: Invoice,
    company_cif: str,
    base_path_str: Optional[str] = None,
    iva_periodicity: str = "Trimestral"
) -> Dict[str, str]:
    """Calcula y devuelve la ruta y nombre propuestos por el sistema antes de archivar."""
    base_dir = resolve_base_directory(base_path_str)
    norm_company_cif = sanitize_filename_part(company_cif.upper())
    year_str = str(invoice.issue_date.year) if invoice.issue_date else "2026"
    month = invoice.issue_date.month if invoice.issue_date else 1
    period_folder = get_period_folder(month, iva_periodicity)
    
    subfolder = f"{norm_company_cif}/{year_str}/{period_folder}/recibidas"
    
    fecha_str = invoice.issue_date.strftime("%Y-%m-%d") if invoice.issue_date else "0000-00-00"
    emisor_cif = sanitize_filename_part(invoice.issuer_cif)
    safe_number = sanitize_filename_part(invoice.invoice_number)
    
    src_suffix = Path(invoice.file_path).suffix if invoice.file_path else ".pdf"
    if not src_suffix:
        src_suffix = ".pdf"
    filename = f"{fecha_str}_{emisor_cif}_{safe_number}{src_suffix}"
    
    full_path = str(base_dir / subfolder / filename)
    
    return {
        "base_path": str(base_dir),
        "subfolder": subfolder,
        "filename": filename,
        "full_path": full_path
    }

def archive_invoice_file(
    invoice: Invoice,
    company_cif: str,
    custom_subfolder: Optional[str] = None,
    custom_filename: Optional[str] = None,
    base_path_str: Optional[str] = None,
    iva_periodicity: str = "Trimestral"
) -> Optional[str]:
    """
    Mueve y renombra el archivo de la factura al ser aprobada/contabilizada:
    Soporta rutas automáticas o personalizadas por el usuario.
    """
    if not invoice.file_path:
        return None

    src_path = Path(invoice.file_path)
    if not src_path.exists():
        return invoice.file_path

    base_dir = resolve_base_directory(base_path_str)
    
    # Si el usuario especificó una subcarpeta personalizada
    if custom_subfolder and custom_subfolder.strip():
        clean_sub = custom_subfolder.strip().replace("\\", "/").strip("/")
        # Si la ruta comienza con el nombre del directorio base (ej. "storage/B123..."), remover prefijo
        base_name_prefix = f"{base_dir.name.lower()}/"
        if clean_sub.lower().startswith(base_name_prefix):
            clean_sub = clean_sub[len(base_name_prefix):]
        target_dir = base_dir / clean_sub
    else:
        norm_company_cif = sanitize_filename_part(company_cif.upper())
        year_str = str(invoice.issue_date.year) if invoice.issue_date else "2026"
        month = invoice.issue_date.month if invoice.issue_date else 1
        period_folder = get_period_folder(month, iva_periodicity)
        target_dir = base_dir / norm_company_cif / year_str / period_folder / "recibidas"

    target_dir.mkdir(parents=True, exist_ok=True)

    if custom_filename and custom_filename.strip():
        clean_filename = sanitize_filename_part(custom_filename.strip())
        if not any(clean_filename.lower().endswith(ext) for ext in [".pdf", ".png", ".jpg", ".jpeg", ".webp"]):
            clean_filename += (src_path.suffix or ".pdf")
        new_filename = clean_filename
    else:
        fecha_str = invoice.issue_date.strftime("%Y-%m-%d") if invoice.issue_date else "0000-00-00"
        emisor_cif = sanitize_filename_part(invoice.issuer_cif)
        safe_number = sanitize_filename_part(invoice.invoice_number)
        extension = src_path.suffix or ".pdf"
        new_filename = f"{fecha_str}_{emisor_cif}_{safe_number}{extension}"

    target_file_path = target_dir / new_filename

    # Política explícita de resolución de colisiones: si el archivo de destino ya existe,
    # sufijar correlativamente (_1, _2, etc.) para preservar la integridad de ambos documentos.
    if target_file_path.exists() and target_file_path.resolve() != src_path.resolve():
        stem = target_file_path.stem
        ext = target_file_path.suffix
        counter = 1
        while True:
            candidate_name = f"{stem}_{counter}{ext}"
            candidate_path = target_dir / candidate_name
            if not candidate_path.exists():
                new_filename = candidate_name
                target_file_path = candidate_path
                break
            counter += 1

    # Mover físicamente el archivo
    shutil.move(str(src_path), str(target_file_path))

    # Actualizar campos en la base de datos
    invoice.file_path = str(target_file_path)
    invoice.file_name = new_filename

    return str(target_file_path)

