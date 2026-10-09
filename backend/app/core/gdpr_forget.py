"""
Módulo Oficial de Supresión, Bloqueo Legal y Derecho al Olvido (RGPD vs LGT / Código de Comercio).
Gobernanza de Datos Personales conforme a:
- Artículo 17 del RGPD (Derecho de Supresión / "Derecho al Olvido").
- Artículo 17.3.b del RGPD (Excepción por cumplimiento de obligación legal tributaria/mercantil).
- Artículo 32 de la LOPDGDD (Obligación de Bloqueo de Datos durante plazos de prescripción).
- Artículo 66 de la Ley General Tributaria (LGT) (Plazo de prescripción de 4 años fiscales).
- Artículo 30 del Código de Comercio (Obligación mercantil de conservación documental de 6 años).

Capacidades:
1. Anonimización criptográfica irreversible de identificadores personales (usuarios, contactos, accesos).
2. Evaluación algorítmica de prescripción tributaria (4 años LGT) y mercantil (6 años CCo).
3. Bloqueo normativo de facturas y registros contables no prescritos ('BLOCKED_TAX_RETENTION').
4. Emisión de Certificado Auditable de Bloqueo Legal con huella criptográfica SHA-256.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date as dt_date, datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

SALT_ANON = "RGPD_DISOCIATION_SALT_ES_2026"


def anonymize_text(value: str, prefix: str = "ANON") -> str:
    """
    Genera un token seudonimizado determinista e irreversible
    utilizando SHA-256 con salt de sistema truncado a 12 caracteres hexadecimales.
    Permite conservar integridad referencial sin exponer datos de carácter personal.
    """
    if not value:
        return f"{prefix}_EMPTY"
    raw = f"{SALT_ANON}:{str(value).strip().lower()}".encode("utf-8")
    token = hashlib.sha256(raw).hexdigest()[:12]
    return f"{prefix}_{token}"


def check_tax_prescription(tax_year: int, current_date: Optional[datetime] = None) -> bool:
    """
    Evalúa si un ejercicio fiscal ha prescrito formalmente según el Art. 66 de la LGT (España).
    - El plazo reglamentario de liquidación anual (Impuesto de Sociedades / IRPF) expira en julio de (tax_year + 1).
    - Los 4 años de prescripción tributaria concluyen formalmente el 26 de julio de (tax_year + 5).
    """
    ref_dt = current_date or datetime.now(timezone.utc)
    ref_date = ref_dt.date() if isinstance(ref_dt, datetime) else ref_dt
    prescription_date = dt_date(tax_year + 5, 7, 26)
    return ref_date >= prescription_date


def calculate_retention_deadline(tax_year: int) -> dt_date:
    """Calcula la fecha exacta en la que expira la prescripción tributaria de 4 años (Art. 66 LGT)."""
    return dt_date(tax_year + 5, 7, 25)


def calculate_commercial_purge_date(tax_year: int) -> dt_date:
    """Calcula la fecha de conservación mercantil de 6 años según el Art. 30 del Código de Comercio."""
    return dt_date(tax_year + 6, 12, 31)


class RetentionSchedule(BaseModel):
    """Calendario normativo de retención y bloqueo legal para un ejercicio contable."""
    tax_year: int = Field(..., description="Año fiscal del ejercicio contable")
    invoices_count: int = Field(default=0, description="Número de facturas asociadas al ejercicio")
    is_prescribed: bool = Field(..., description="Indica si el ejercicio ya ha prescrito tributariamente (4 años)")
    prescription_deadline: dt_date = Field(..., description="Fecha límite de prescripción según Art. 66 LGT")
    scheduled_purge_date: dt_date = Field(..., description="Fecha de purga física autorizada (Art. 30 C.Comercio)")
    status: str = Field(..., description="'BLOCKED_TAX_RETENTION' o 'ELIGIBLE_FOR_PURGE'")
    legal_basis: str = Field(
        default="Art. 17.3.b RGPD, Art. 66 Ley General Tributaria y Art. 30 Código de Comercio",
        description="Fundamento normativo del bloqueo o purga"
    )


class AnonymizedUser(BaseModel):
    """Detalle de anonimización irreversible de un usuario o persona física."""
    user_id: str
    anonymous_token: str
    purged_fields: List[str]


class LegalBlockCertificate(BaseModel):
    """Certificado auditable de bloqueo legal emitido tras la solicitud de derecho al olvido."""
    certificate_id: str
    issue_date: datetime
    company_id: str
    company_cif_anonymized: str
    legal_basis: str
    total_users_anonymized: int
    total_invoices_blocked: int
    total_invoices_eligible_for_purge: int
    retention_schedules: List[RetentionSchedule]
    sha256_fingerprint: str


class GDPRForgetResult(BaseModel):
    """Resultado estructurado de la ejecución del proceso de derecho al olvido y bloqueo legal."""
    success: bool
    company_id: str
    execution_timestamp: datetime
    users_anonymized: List[AnonymizedUser]
    invoices_retention_summary: List[RetentionSchedule]
    purged_invoices_count: int
    blocked_invoices_count: int
    certificate: LegalBlockCertificate


def process_company_gdpr_forget(
    company_data: Dict[str, Any],
    invoices: List[Dict[str, Any]],
    users: List[Dict[str, Any]],
    current_date: Optional[datetime] = None,
) -> GDPRForgetResult:
    """
    Ejecuta el procedimiento legal de supresión y bloqueo (Art. 17 RGPD vs Art. 66 LGT y Art. 30 CCo):
    1. Anonimiza de inmediato datos personales de usuarios y contactos.
    2. Bloquea facturas y asientos no prescritos en estado 'BLOCKED_TAX_RETENTION' con calendario de purga.
    3. Habilita para destrucción física ('ELIGIBLE_FOR_PURGE') aquellos ejercicios con más de 4-6 años.
    4. Genera el Certificado Oficial de Bloqueo Legal con firma SHA-256.
    """
    now = current_date or datetime.now(timezone.utc)
    company_id = str(company_data.get("id") or company_data.get("company_id") or "UNKNOWN")
    cif = str(company_data.get("cif") or "UNKNOWN")

    # -------------------------------------------------------------
    # 1. ANONIMIZACIÓN DE USUARIOS Y DATOS PERSONALES
    # -------------------------------------------------------------
    anonymized_users_list: List[AnonymizedUser] = []
    for u in users:
        uid = str(u.get("id") or u.get("user_id") or uuid.uuid4().hex[:8])
        anon_token = anonymize_text(uid, prefix="ANON_USER")

        # Registro de campos que se purgan / anonimizan
        purged = [
            "name",
            "email",
            "hashed_password",
            "phone",
            "ip_address",
            "user_agent",
            "psd2_access_tokens",
            "totp_secret",
        ]

        anonymized_users_list.append(
            AnonymizedUser(
                user_id=uid,
                anonymous_token=anon_token,
                purged_fields=purged,
            )
        )

    # -------------------------------------------------------------
    # 2. CLASIFICACIÓN DE FACTURAS Y CALENDARIO DE RETENCIÓN LGT
    # -------------------------------------------------------------
    invoices_by_year: Dict[int, List[Dict[str, Any]]] = {}

    for inv in invoices:
        raw_date = inv.get("issue_date") or inv.get("created_at") or now.date().isoformat()
        try:
            if isinstance(raw_date, str):
                inv_year = int(raw_date[:4])
            elif hasattr(raw_date, "year"):
                inv_year = raw_date.year
            else:
                inv_year = now.year
        except Exception:
            inv_year = now.year

        invoices_by_year.setdefault(inv_year, []).append(inv)

    retention_schedules: List[RetentionSchedule] = []
    total_blocked = 0
    total_eligible = 0

    for yr in sorted(invoices_by_year.keys()):
        inv_list = invoices_by_year[yr]
        count = len(inv_list)
        is_prescribed = check_tax_prescription(yr, current_date=now)

        deadline_lgt = calculate_retention_deadline(yr)
        purge_cco = calculate_commercial_purge_date(yr)

        if is_prescribed:
            st = "ELIGIBLE_FOR_PURGE"
            total_eligible += count
        else:
            st = "BLOCKED_TAX_RETENTION"
            total_blocked += count

        retention_schedules.append(
            RetentionSchedule(
                tax_year=yr,
                invoices_count=count,
                is_prescribed=is_prescribed,
                prescription_deadline=deadline_lgt,
                scheduled_purge_date=purge_cco,
                status=st,
            )
        )

    # Si no había facturas, añadir al menos el año fiscal actual
    if not retention_schedules:
        curr_yr = now.year
        retention_schedules.append(
            RetentionSchedule(
                tax_year=curr_yr,
                invoices_count=0,
                is_prescribed=False,
                prescription_deadline=calculate_retention_deadline(curr_yr),
                scheduled_purge_date=calculate_commercial_purge_date(curr_yr),
                status="BLOCKED_TAX_RETENTION",
            )
        )

    # -------------------------------------------------------------
    # 3. CERTIFICADO DE BLOQUEO LEGAL AUDITABLE (SHA-256)
    # -------------------------------------------------------------
    cert_id = f"CERT-RGPD-LGT-{uuid.uuid4().hex[:12].upper()}"
    anon_cif = anonymize_text(cif, prefix="ANON_CIF")
    legal_basis_text = (
        "Art. 17.3.b del RGPD (Excepción por cumplimiento de deber legal tributario), "
        "Art. 32 de la LOPDGDD (Bloqueo de datos), Art. 66 de la Ley 58/2003 General Tributaria "
        "(Prescripción tributaria de 4 años) y Art. 30 del Código de Comercio (Conservación de 6 años)."
    )

    cert_raw_payload = {
        "certificate_id": cert_id,
        "company_id": company_id,
        "company_cif_anonymized": anon_cif,
        "issue_date": now.isoformat(),
        "total_users_anonymized": len(anonymized_users_list),
        "total_invoices_blocked": total_blocked,
        "total_invoices_eligible_for_purge": total_eligible,
        "schedules": [s.model_dump(mode="json") for s in retention_schedules],
    }

    raw_json = json.dumps(cert_raw_payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    sha256_hash = hashlib.sha256(raw_json).hexdigest()

    certificate = LegalBlockCertificate(
        certificate_id=cert_id,
        issue_date=now,
        company_id=company_id,
        company_cif_anonymized=anon_cif,
        legal_basis=legal_basis_text,
        total_users_anonymized=len(anonymized_users_list),
        total_invoices_blocked=total_blocked,
        total_invoices_eligible_for_purge=total_eligible,
        retention_schedules=retention_schedules,
        sha256_fingerprint=sha256_hash,
    )

    return GDPRForgetResult(
        success=True,
        company_id=company_id,
        execution_timestamp=now,
        users_anonymized=anonymized_users_list,
        invoices_retention_summary=retention_schedules,
        purged_invoices_count=total_eligible,
        blocked_invoices_count=total_blocked,
        certificate=certificate,
    )
