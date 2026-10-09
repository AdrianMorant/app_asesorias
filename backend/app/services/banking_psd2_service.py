"""
Servicio Oficial de Conectividad y Agregación Bancaria PSD2 (GoCardless Bank Account Data API).
Permite la conexión directa con entidades financieras españolas (Santander, BBVA, CaixaBank, Sabadell, Bankinter, etc.)
bajo la directiva europea PSD2 / Directiva (UE) 2015/2366.

Capacidades:
- Autenticación y gestión del ciclo de vida de tokens JWT (access_token y refresh_token).
- Consulta de instituciones financieras soportadas por país (por defecto España 'ES').
- Creación de acuerdos de usuario final (EUA) y requisitions (enlaces de autorización bancaria).
- Obtención de identificadores de cuentas tras la vinculación exitosa.
- Lectura en tiempo real de saldos disponibles y contables.
- Extracción de movimientos bancarios históricos e incrementales.
- Normalización automática de transacciones hacia el motor de conciliación bancaria del sistema.
"""

from __future__ import annotations

import os
import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
import httpx

from app.core.config import settings
from app.core.iban_security import validate_iban, mask_iban

GOCARDLESS_BASE_URL = "https://bankaccountdata.gocardless.com/api/v2"


class PSD2IntegrationError(Exception):
    """Excepción específica para errores en la integración bancaria PSD2."""
    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        error_details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_details = error_details or {}


class GoCardlessPSD2Client:
    """Cliente asíncrono para la API de GoCardless Bank Account Data (PSD2)."""

    def __init__(
        self,
        secret_id: Optional[str] = None,
        secret_key: Optional[str] = None,
        base_url: str = GOCARDLESS_BASE_URL,
    ):
        self.secret_id = (
            secret_id
            or os.getenv("GOCARDLESS_SECRET_ID")
            or getattr(settings, "GOCARDLESS_SECRET_ID", None)
        )
        self.secret_key = (
            secret_key
            or os.getenv("GOCARDLESS_SECRET_KEY")
            or getattr(settings, "GOCARDLESS_SECRET_KEY", None)
        )
        self.base_url = base_url.rstrip("/")

        # Caché de tokens en memoria
        self._access_token: Optional[str] = None
        self._access_token_expires_at: Optional[datetime] = None
        self._refresh_token: Optional[str] = None
        self._refresh_token_expires_at: Optional[datetime] = None

    def is_configured(self) -> bool:
        """Comprueba si las credenciales de API están configuradas."""
        return bool(self.secret_id and self.secret_key)

    async def get_access_token(self) -> str:
        """
        Obtiene un token de acceso válido, renovándolo automáticamente si ha expirado
        o generando uno nuevo mediante las credenciales secretas.
        """
        now = datetime.now(timezone.utc)

        # 1. Reutilizar access token si aún es válido (con margen de seguridad de 60 segundos)
        if self._access_token and self._access_token_expires_at:
            if now < (self._access_token_expires_at - timedelta(seconds=60)):
                return self._access_token

        # 2. Intentar refrescar si existe refresh token vigente
        if self._refresh_token and self._refresh_token_expires_at:
            if now < (self._refresh_token_expires_at - timedelta(seconds=60)):
                try:
                    return await self._refresh_access_token()
                except Exception:
                    # Si falla el refresco, generar uno nuevo desde cero
                    pass

        # 3. Solicitar nuevo par de tokens con secret_id y secret_key
        return await self._authenticate()

    async def _authenticate(self) -> str:
        """Autenticación inicial contra `/token/new/`."""
        if not self.is_configured():
            raise PSD2IntegrationError(
                "Credenciales de GoCardless no configuradas. "
                "Define GOCARDLESS_SECRET_ID y GOCARDLESS_SECRET_KEY en las variables de entorno."
            )

        url = f"{self.base_url}/token/new/"
        payload = {
            "secret_id": self.secret_id,
            "secret_key": self.secret_key,
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.post(url, json=payload)
            except httpx.RequestError as exc:
                raise PSD2IntegrationError(
                    f"Error de conexión con GoCardless PSD2: {str(exc)}"
                ) from exc

        if resp.status_code != 200:
            error_data = {}
            try:
                error_data = resp.json()
            except Exception:
                pass
            raise PSD2IntegrationError(
                f"Fallo en la autenticación con GoCardless (HTTP {resp.status_code}): {resp.text}",
                status_code=resp.status_code,
                error_details=error_data,
            )

        data = resp.json()
        now = datetime.now(timezone.utc)

        self._access_token = data.get("access")
        access_expires_in = data.get("access_expires", 86400)
        self._access_token_expires_at = now + timedelta(seconds=access_expires_in)

        self._refresh_token = data.get("refresh")
        refresh_expires_in = data.get("refresh_expires", 2592000)
        self._refresh_token_expires_at = now + timedelta(seconds=refresh_expires_in)

        return self._access_token

    async def _refresh_access_token(self) -> str:
        """Renueva el access token contra `/token/refresh/`."""
        url = f"{self.base_url}/token/refresh/"
        payload = {"refresh": self._refresh_token}

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload)

        if resp.status_code != 200:
            raise PSD2IntegrationError(
                f"Fallo al renovar el token PSD2 (HTTP {resp.status_code})",
                status_code=resp.status_code,
            )

        data = resp.json()
        self._access_token = data.get("access")
        expires_in = data.get("access_expires", 86400)
        self._access_token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        return self._access_token

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        require_auth: bool = True,
    ) -> Any:
        """Ejecuta una petición HTTP con gestión automática de autenticación y reintentos."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        headers = {"Accept": "application/json"}

        if require_auth:
            token = await self.get_access_token()
            headers["Authorization"] = f"Bearer {token}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_data,
                    headers=headers,
                )
            except httpx.RequestError as exc:
                raise PSD2IntegrationError(
                    f"Error de red al conectar con GoCardless: {str(exc)}"
                ) from exc

        # Si el token caducó durante la petición, forzar renovación y reintentar una vez
        if resp.status_code == 401 and require_auth:
            token = await self._authenticate()
            headers["Authorization"] = f"Bearer {token}"
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_data,
                    headers=headers,
                )

        if resp.status_code >= 400:
            err_details = {}
            try:
                err_details = resp.json()
            except Exception:
                pass

            msg = f"Error en API PSD2 ({method} {endpoint} - HTTP {resp.status_code}): {resp.text}"
            if resp.status_code == 429:
                msg = "Límite de peticiones de GoCardless excedido (HTTP 429 Rate Limit). Inténtelo más tarde."
            elif resp.status_code == 404:
                msg = f"Recurso no encontrado en GoCardless: {endpoint}"

            raise PSD2IntegrationError(
                message=msg,
                status_code=resp.status_code,
                error_details=err_details,
            )

        if resp.status_code == 204:
            return {}

        try:
            return resp.json()
        except Exception:
            return resp.text

    async def get_institutions(self, country: str = "ES") -> List[Dict[str, Any]]:
        """
        Obtiene la lista de entidades financieras disponibles para el país especificado.
        Para España ('ES') incluye Banco Santander, BBVA, CaixaBank, Sabadell, etc.
        """
        data = await self._request("GET", "institutions/", params={"country": country})
        if isinstance(data, list):
            return data
        return []

    async def create_requisition(
        self,
        institution_id: str,
        redirect_uri: str,
        reference: str,
        max_historical_days: int = 90,
        user_language: str = "ES",
    ) -> Dict[str, Any]:
        """
        Crea una solicitud de consentimiento bancario (Requisition) con acuerdo de usuario final (EUA).
        Retorna la URL oficial de redirección (`initiation_url` / `link`) para que el usuario autorice el acceso.
        """
        # 1. Crear End User Agreement para fijar el alcance
        agreement_payload = {
            "institution_id": institution_id,
            "max_historical_days": max_historical_days,
            "access_valid_for_days": 90,
            "access_scope": ["balances", "details", "transactions"],
        }
        agreement = await self._request("POST", "agreements/enduser/", json_data=agreement_payload)
        agreement_id = agreement.get("id")

        # 2. Crear Requisition
        req_payload = {
            "redirect": redirect_uri,
            "institution_id": institution_id,
            "reference": reference,
            "agreement": agreement_id,
            "user_language": user_language,
        }
        res = await self._request("POST", "requisitions/", json_data=req_payload)
        return {
            "requisition_id": res.get("id"),
            "status": res.get("status"),
            "initiation_url": res.get("link"),
            "agreement_id": agreement_id,
            "reference": reference,
        }

    async def get_requisition(self, requisition_id: str) -> Dict[str, Any]:
        """Consulta el estado de una requisition (CR = Created, LN = Linked, EX = Expired)."""
        return await self._request("GET", f"requisitions/{requisition_id}/")

    async def get_requisition_accounts(self, requisition_id: str) -> List[str]:
        """Obtiene la lista de identificadores de cuentas bancarias asociadas tras la autorización."""
        data = await self.get_requisition(requisition_id)
        accounts = data.get("accounts", [])
        if isinstance(accounts, list):
            return accounts
        return []

    async def get_account_details(self, account_id: str) -> Dict[str, Any]:
        """Obtiene metadatos de la cuenta: IBAN, divisa, titular y nombre descriptivo."""
        res = await self._request("GET", f"accounts/{account_id}/details/")
        acc_info = res.get("account", {})
        iban = acc_info.get("iban", "")
        return {
            "account_id": account_id,
            "iban": iban,
            "currency": acc_info.get("currency", "EUR"),
            "owner_name": acc_info.get("ownerName", ""),
            "name": acc_info.get("name", "Cuenta Corriente"),
            "resource_id": acc_info.get("resourceId", ""),
        }

    async def get_account_balances(self, account_id: str) -> Dict[str, Any]:
        """Obtiene los saldos contables y disponibles de la cuenta bancaria."""
        res = await self._request("GET", f"accounts/{account_id}/balances/")
        balances = res.get("balances", [])

        current_balance = 0.0
        available_balance = 0.0
        currency = "EUR"

        for b in balances:
            b_amount = float(b.get("balanceAmount", {}).get("amount", 0.0))
            currency = b.get("balanceAmount", {}).get("currency", currency)
            b_type = b.get("balanceType", "")

            if b_type in ("interimAvailable", "available"):
                available_balance = b_amount
            elif b_type in ("interimBooked", "closingBooked", "expected"):
                current_balance = b_amount

        if not current_balance and available_balance:
            current_balance = available_balance

        return {
            "account_id": account_id,
            "current_balance": round(current_balance, 2),
            "available_balance": round(available_balance, 2),
            "currency": currency,
            "raw_balances": balances,
        }

    async def get_account_transactions(
        self,
        account_id: str,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Descarga las transacciones de la cuenta bancaria (movimientos consolidados 'booked').
        Permite filtrar por rango de fechas (formato 'YYYY-MM-DD').
        """
        params: Dict[str, Any] = {}
        if date_from:
            params["date_from"] = date_from
        if date_to:
            params["date_to"] = date_to

        res = await self._request("GET", f"accounts/{account_id}/transactions/", params=params)
        tx_block = res.get("transactions", {})
        booked = tx_block.get("booked", [])
        return booked if isinstance(booked, list) else []

    async def delete_requisition(self, requisition_id: str) -> bool:
        """Elimina una requisition y revoca la vinculación en el agregador."""
        try:
            await self._request("DELETE", f"requisitions/{requisition_id}/")
            return True
        except Exception:
            return False


def normalize_psd2_transaction(raw_tx: Dict[str, Any], account_iban: str) -> Dict[str, Any]:
    """
    Normaliza una transacción proveniente de la API de GoCardless Bank Account Data
    hacia el formato estándar del motor de conciliación contable de la plataforma.

    Parámetros:
    - raw_tx: Diccionario crudo devuelto por GoCardless en el bloque `booked`.
    - account_iban: IBAN de la cuenta bancaria a la que pertenece el apunte.

    Retorna:
    - Diccionario homogéneo listo para ser insertado en `_save_transactions`.
    """
    clean_iban = re.sub(r"\s+", "", account_iban.upper())

    # 1. Fechas contable y valor
    date_val = raw_tx.get("bookingDate") or raw_tx.get("valueDate")
    if not date_val:
        date_val = datetime.now(timezone.utc).date().isoformat()

    val_date = raw_tx.get("valueDate") or date_val

    # 2. Importe y tipo de movimiento
    amount_info = raw_tx.get("transactionAmount", {})
    try:
        raw_amount = float(amount_info.get("amount", 0.0))
    except (ValueError, TypeError):
        raw_amount = 0.0

    amount = round(raw_amount, 2)
    currency = amount_info.get("currency", "EUR")

    # En la especificación PSD2: importes negativos representan cargos/salidas (DEBE)
    # e importes positivos representan abonos/ingresos (HABER)
    if amount < 0:
        entry_type = "DEBE"
        balance_impact = amount
    else:
        entry_type = "HABER"
        balance_impact = amount

    # 3. Descripción y concepto enriquecido
    unstructured = raw_tx.get("remittanceInformationUnstructured")
    unstructured_arr = raw_tx.get("remittanceInformationUnstructuredArray") or []

    desc_parts = []
    if unstructured:
        desc_parts.append(str(unstructured).strip())
    elif unstructured_arr:
        desc_parts.extend(str(p).strip() for p in unstructured_arr if p)

    debtor_name = raw_tx.get("debtorName")
    creditor_name = raw_tx.get("creditorName")

    if entry_type == "HABER" and debtor_name:
        desc_parts.append(f"Ordenante: {debtor_name}")
    elif entry_type == "DEBE" and creditor_name:
        desc_parts.append(f"Beneficiario: {creditor_name}")

    description = " ".join(desc_parts).strip()
    if not description:
        description = raw_tx.get("additionalInformation") or "Movimiento bancario PSD2"

    tx_id = raw_tx.get("transactionId") or f"tx-psd2-{uuid.uuid4().hex[:12]}"
    clean_tx_id = f"psd2-{re.sub(r'[^A-Za-z0-9_-]', '', str(tx_id))[:32]}"

    return {
        "id": clean_tx_id,
        "account_iban": clean_iban,
        "date": date_val,
        "value_date": val_date,
        "amount": balance_impact,
        "entry_type": entry_type,
        "description": description,
        "document_number": str(raw_tx.get("entryReference") or "")[:50],
        "reference_1": str(raw_tx.get("transactionId") or "")[:50],
        "reference_2": "",
        "status": "PENDIENTE",
        "currency": currency,
        "source": "PSD2_GOCARDLESS",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
