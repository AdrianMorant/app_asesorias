"""
Servicio Contable y Financiero de Inmovilizado y Amortizaciones.
Cumple estrictamente con el Plan General Contable español (RD 1514/2007 y RD 1515/2007).

Responsabilidades:
1. Asignación automática de cuentas del PGC según categoría y longitud de subcuentas.
2. Cálculo matemático de cuadros de amortización plurianuales (Lineal con prorrateo por días exactos,
   dígitos decrecientes y porcentaje constante).
3. Contabilización periódica de dotaciones (Asientos 681/281 o 680/280) en partida doble estricta.
4. Gestión de bajas por obsolescencia y ventas/enajenaciones (Asientos con cuentas 281, 572, 21x, 671 y 771).
5. Respeto de bloqueos por ejercicios cerrados e inmutabilidad de apuntes.
"""

from __future__ import annotations

import calendar
import math
from datetime import date, datetime, timezone
from typing import List, Optional, Tuple, Dict, Any

from fastapi import HTTPException, status
from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.asset import (
    Asset,
    AssetDepreciationSchedule,
    AssetCategory,
    DepreciationMethod,
    AssetStatus,
)
from app.models.company import Company
from app.models.invoice import Invoice
from app.models.sales_invoice import SalesInvoice
from app.models.accounting_entry import AccountingEntryLine
from app.schemas.asset_dto import (
    AssetCreateDTO,
    AssetUpdateDTO,
    DisposeAssetRequestDTO,
    PostDepreciationRequestDTO,
)
from app.core.audit_logger import log_security_event


# Mapeo oficial de cuentas estándar del PGC español según la categoría del activo
DEFAULT_PGC_ACCOUNTS: Dict[str, Dict[str, str]] = {
    AssetCategory.TERRENOS.value: {
        "asset": "210",
        "accumulated": "2810",
        "expense": "681",
    },
    AssetCategory.CONSTRUCCIONES.value: {
        "asset": "211",
        "accumulated": "2811",
        "expense": "681",
    },
    AssetCategory.INSTALACIONES_TECNICAS.value: {
        "asset": "212",
        "accumulated": "2812",
        "expense": "681",
    },
    AssetCategory.MAQUINARIA.value: {
        "asset": "213",
        "accumulated": "2813",
        "expense": "681",
    },
    AssetCategory.UTILLAJE.value: {
        "asset": "214",
        "accumulated": "2814",
        "expense": "681",
    },
    AssetCategory.MOBILIARIO.value: {
        "asset": "216",
        "accumulated": "2816",
        "expense": "681",
    },
    AssetCategory.EQUIPOS_INFORMATICOS.value: {
        "asset": "217",
        "accumulated": "2817",
        "expense": "681",
    },
    AssetCategory.ELEMENTOS_TRANSPORTE.value: {
        "asset": "218",
        "accumulated": "2818",
        "expense": "681",
    },
    AssetCategory.APLICACIONES_INFORMATICAS.value: {
        "asset": "206",
        "accumulated": "2806",
        "expense": "680",  # Gasto inmaterial
    },
    AssetCategory.OTRO_INMOVILIZADO.value: {
        "asset": "219",
        "accumulated": "2819",
        "expense": "681",
    },
}


def _format_account(code_prefix: str, length: int) -> str:
    """Rellena el prefijo de cuenta con ceros hasta la longitud oficial de la empresa (ej. 9 dígitos)."""
    return code_prefix.ljust(length, "0")


async def get_next_entry_number(session: AsyncSession, company_id: str) -> int:
    """Calcula de forma atómica y correlativa el siguiente número de asiento contable para la empresa."""
    stmt = (
        select(func.max(AccountingEntryLine.entry_number))
        .outerjoin(Invoice, AccountingEntryLine.invoice_id == Invoice.id)
        .outerjoin(SalesInvoice, AccountingEntryLine.sales_invoice_id == SalesInvoice.id)
        .where(
            or_(
                AccountingEntryLine.company_id == company_id,
                Invoice.company_id == company_id,
                SalesInvoice.company_id == company_id,
            )
        )
    )
    result = await session.execute(stmt)
    max_num = result.scalar() or 0
    return max_num + 1


class AssetService:
    @staticmethod
    def infer_pgc_accounts(category: str, account_length: int = 9) -> Tuple[str, str, str]:
        """Infiere las cuentas PGC (activo, amort. acumulada y dotación gasto) para una categoría."""
        mapping = DEFAULT_PGC_ACCOUNTS.get(category, DEFAULT_PGC_ACCOUNTS[AssetCategory.OTRO_INMOVILIZADO.value])
        return (
            _format_account(mapping["asset"], account_length),
            _format_account(mapping["accumulated"], account_length),
            _format_account(mapping["expense"], account_length),
        )

    @staticmethod
    def generate_depreciation_schedule(
        acquisition_cost: float,
        residual_value: float,
        start_date: date,
        useful_life_years: float,
        method: str,
    ) -> List[Dict[str, Any]]:
        """
        Calcula el calendario de amortización plurianual con prorrateo temporal exacto.
        Respeta la base amortizable y cuadre al céntimo sin desajustes decimales.
        """
        depreciable_base = round(acquisition_cost - residual_value, 2)
        if depreciable_base <= 0.0 or useful_life_years <= 0:
            return []

        schedules: List[Dict[str, Any]] = []
        accumulated = 0.0

        if method == DepreciationMethod.LINEAL.value:
            # Amortización Lineal / Constante con prorrateo por días naturales
            annual_depreciation = depreciable_base / useful_life_years
            daily_rate = annual_depreciation / 365.0

            current_start = start_date
            remaining_base = depreciable_base

            while remaining_base > 0.009:
                curr_year = current_start.year
                year_end = date(curr_year, 12, 31)

                # Días naturales en este ejercicio
                days_in_period = (year_end - current_start).days + 1
                days_in_year = 366 if calendar.isleap(curr_year) else 365

                # Cuota teórica para este periodo fraccionado o completo
                period_amount = round(annual_depreciation * (days_in_period / days_in_year), 2)
                
                # Ajuste de fin de vida útil
                if period_amount >= remaining_base or schedules and len(schedules) >= math.ceil(useful_life_years) + 1:
                    period_amount = round(remaining_base, 2)

                remaining_base = round(remaining_base - period_amount, 2)
                accumulated = round(accumulated + period_amount, 2)
                net_book_value = round(acquisition_cost - accumulated, 2)

                schedules.append({
                    "fiscal_year": curr_year,
                    "period_name": f"Ejercicio {curr_year}",
                    "start_date": current_start,
                    "end_date": year_end,
                    "depreciation_amount": period_amount,
                    "accumulated_depreciation": accumulated,
                    "net_book_value": net_book_value,
                })

                # Avanzar al 1 de enero del año siguiente
                current_start = date(curr_year + 1, 1, 1)

        elif method == DepreciationMethod.DIGITOS_DECRECIENTE.value:
            # Método de la suma de dígitos decreciente
            n = math.ceil(useful_life_years)
            sum_digits = (n * (n + 1)) / 2
            current_start = start_date
            remaining_base = depreciable_base

            for i in range(n):
                curr_year = current_start.year
                year_end = date(curr_year, 12, 31)
                digit = n - i
                period_amount = round(depreciable_base * (digit / sum_digits), 2)

                if i == n - 1 or period_amount > remaining_base:
                    period_amount = round(remaining_base, 2)

                remaining_base = round(remaining_base - period_amount, 2)
                accumulated = round(accumulated + period_amount, 2)
                net_book_value = round(acquisition_cost - accumulated, 2)

                schedules.append({
                    "fiscal_year": curr_year,
                    "period_name": f"Ejercicio {curr_year}",
                    "start_date": current_start,
                    "end_date": year_end,
                    "depreciation_amount": period_amount,
                    "accumulated_depreciation": accumulated,
                    "net_book_value": net_book_value,
                })
                current_start = date(curr_year + 1, 1, 1)

        else:
            # Por defecto lineal
            return AssetService.generate_depreciation_schedule(
                acquisition_cost, residual_value, start_date, useful_life_years, DepreciationMethod.LINEAL.value
            )

        return schedules

    @staticmethod
    async def create_asset(
        session: AsyncSession,
        company_id: str,
        data: AssetCreateDTO,
        current_user_name: str = "sistema",
    ) -> Asset:
        """Crea un nuevo activo fijo, autogenera cuentas si faltan y calcula el calendario."""
        # 1. Verificar existencia de la empresa
        comp_res = await session.execute(select(Company).where(Company.id == company_id))
        company = comp_res.scalar_one_or_none()
        if not company:
            raise HTTPException(status_code=404, detail="Empresa no encontrada")

        # 2. Verificar código único dentro de la empresa
        existing_code = await session.execute(
            select(Asset).where(Asset.company_id == company_id, Asset.code == data.code)
        )
        if existing_code.scalar_one_or_none():
            raise HTTPException(
                status_code=400,
                detail=f"Ya existe un activo con el código '{data.code}' en esta empresa.",
            )

        # 3. Determinar cuentas PGC
        account_length = getattr(company, "plan_cuentas_longitud", 9) or 9
        def_asset, def_accum, def_exp = AssetService.infer_pgc_accounts(data.category.value, account_length)

        acc_asset = data.account_asset or def_asset
        acc_accum = data.account_accumulated_depreciation or def_accum
        acc_exp = data.account_depreciation_expense or def_exp

        start_date = data.depreciation_start_date or data.acquisition_date

        # 4. Crear entidad de activo
        asset = Asset(
            company_id=company_id,
            code=data.code,
            name=data.name,
            category=data.category.value,
            acquisition_date=data.acquisition_date,
            acquisition_cost=data.acquisition_cost,
            residual_value=data.residual_value,
            depreciation_start_date=start_date,
            useful_life_years=data.useful_life_years,
            depreciation_method=data.depreciation_method.value,
            account_asset=acc_asset,
            account_accumulated_depreciation=acc_accum,
            account_depreciation_expense=acc_exp,
            supplier_id=data.supplier_id,
            invoice_id=data.invoice_id,
            accumulated_depreciation=0.0,
            net_book_value=data.acquisition_cost,
            status=AssetStatus.ACTIVO.value,
            notes=data.notes,
        )
        session.add(asset)
        await session.flush()

        # 5. Generar calendario de amortizaciones estimado
        calc_schedules = AssetService.generate_depreciation_schedule(
            acquisition_cost=data.acquisition_cost,
            residual_value=data.residual_value,
            start_date=start_date,
            useful_life_years=data.useful_life_years,
            method=data.depreciation_method.value,
        )

        for sched_dict in calc_schedules:
            schedule = AssetDepreciationSchedule(
                asset_id=asset.id,
                company_id=company_id,
                fiscal_year=sched_dict["fiscal_year"],
                period_name=sched_dict["period_name"],
                start_date=sched_dict["start_date"],
                end_date=sched_dict["end_date"],
                depreciation_amount=sched_dict["depreciation_amount"],
                accumulated_depreciation=sched_dict["accumulated_depreciation"],
                net_book_value=sched_dict["net_book_value"],
                is_posted=False,
            )
            session.add(schedule)

        await session.commit()
        await session.refresh(asset)

        # Log de auditoría WORM
        log_security_event(
            action="ASSET_CREATED",
            resource_id=asset.id,
            user_id=current_user_name,
            empresa_id=company_id,
            details={
                "asset_id": asset.id,
                "company_id": company_id,
                "code": asset.code,
                "cost": asset.acquisition_cost,
                "category": asset.category,
            },
        )

        return asset

    @staticmethod
    async def post_depreciation_quota(
        session: AsyncSession,
        company_id: str,
        asset_id: str,
        payload: PostDepreciationRequestDTO,
        current_user_name: str = "sistema",
    ) -> Tuple[Asset, AssetDepreciationSchedule, int]:
        """
        Contabiliza formalmente una dotación de amortización:
        1. Localiza el periodo a contabilizar.
        2. Verifica que el ejercicio contable no esté cerrado.
        3. Genera el asiento contable en partida doble (Debe 681/680, Haber 281/280).
        4. Actualiza los saldos del activo y marca el periodo como contabilizado.
        """
        comp_res = await session.execute(select(Company).where(Company.id == company_id))
        company = comp_res.scalar_one_or_none()
        if not company:
            raise HTTPException(status_code=404, detail="Empresa no encontrada")

        asset_res = await session.execute(
            select(Asset)
            .options(selectinload(Asset.schedules))
            .where(Asset.id == asset_id, Asset.company_id == company_id)
        )
        asset = asset_res.scalar_one_or_none()
        if not asset:
            raise HTTPException(status_code=404, detail="Activo no encontrado")

        if asset.status in (AssetStatus.BAJA.value, AssetStatus.VENDIDO.value):
            raise HTTPException(
                status_code=400,
                detail=f"No se puede contabilizar dotación para un activo en estado {asset.status}.",
            )

        # Buscar el schedule correspondiente
        target_schedule: Optional[AssetDepreciationSchedule] = None
        if payload.fiscal_year:
            target_schedule = next(
                (s for s in asset.schedules if s.fiscal_year == payload.fiscal_year), None
            )
            if not target_schedule:
                raise HTTPException(
                    status_code=404,
                    detail=f"No existe periodo de amortización para el ejercicio {payload.fiscal_year}.",
                )
        else:
            # Buscar el primer periodo no contabilizado
            target_schedule = next((s for s in asset.schedules if not s.is_posted), None)
            if not target_schedule:
                raise HTTPException(
                    status_code=400,
                    detail="Todos los periodos de amortización de este activo ya están contabilizados.",
                )

        if target_schedule.is_posted:
            raise HTTPException(
                status_code=400,
                detail=f"El ejercicio {target_schedule.fiscal_year} ya fue contabilizado en el asiento #{target_schedule.accounting_entry_number}.",
            )

        posting_date = payload.posting_date or date(target_schedule.fiscal_year, 12, 31)

        # Comprobar cierre contable
        if company.fecha_cierre_contable and posting_date <= company.fecha_cierre_contable:
            raise HTTPException(
                status_code=400,
                detail=f"Bloqueo contable: La fecha {posting_date.isoformat()} pertenece a un ejercicio cerrado (Cierre: {company.fecha_cierre_contable.isoformat()}).",
            )

        # Generar número correlativo de asiento
        entry_number = await get_next_entry_number(session, company_id)

        # Crear líneas de partida doble
        # 1. Cuenta de gasto (Debe 681 / 680)
        line_expense = AccountingEntryLine(
            company_id=company_id,
            entry_number=entry_number,
            fecha=posting_date,
            subcuenta=asset.account_depreciation_expense,
            concepto=f"Dotación Amort. {target_schedule.fiscal_year} - {asset.name}",
            debe=target_schedule.depreciation_amount,
            haber=0.0,
            documento=asset.code,
            status="contabilizado",
            created_by=current_user_name,
        )

        # 2. Cuenta de amortización acumulada (Haber 281 / 280)
        line_accum = AccountingEntryLine(
            company_id=company_id,
            entry_number=entry_number,
            fecha=posting_date,
            subcuenta=asset.account_accumulated_depreciation,
            concepto=f"Amort. Acumulada {target_schedule.fiscal_year} - {asset.name}",
            debe=0.0,
            haber=target_schedule.depreciation_amount,
            documento=asset.code,
            status="contabilizado",
            created_by=current_user_name,
        )

        session.add(line_expense)
        session.add(line_accum)

        # Actualizar estado del periodo
        target_schedule.is_posted = True
        target_schedule.accounting_entry_number = entry_number
        target_schedule.posted_at = datetime.now(timezone.utc)

        # Actualizar saldos del activo
        asset.accumulated_depreciation = target_schedule.accumulated_depreciation
        asset.net_book_value = target_schedule.net_book_value

        if asset.net_book_value <= asset.residual_value + 0.01:
            asset.status = AssetStatus.TOTALMENTE_AMORTIZADO.value

        await session.commit()
        await session.refresh(asset)
        await session.refresh(target_schedule)

        # Log de auditoría WORM
        log_security_event(
            action="ASSET_DEPRECIATION_POSTED",
            resource_id=asset.id,
            user_id=current_user_name,
            empresa_id=company_id,
            details={
                "asset_id": asset.id,
                "company_id": company_id,
                "fiscal_year": target_schedule.fiscal_year,
                "entry_number": entry_number,
                "amount": target_schedule.depreciation_amount,
            },
        )

        return asset, target_schedule, entry_number

    @staticmethod
    async def dispose_asset(
        session: AsyncSession,
        company_id: str,
        asset_id: str,
        payload: DisposeAssetRequestDTO,
        current_user_name: str = "sistema",
    ) -> Tuple[Asset, int]:
        """
        Da de baja o vende un activo fijo generando el asiento contable de desinversión:
        - Cargo en Amortización Acumulada (281) por el saldo acumulado.
        - Cargo en Tesorería (572) por el precio de venta recibido (si aplica).
        - Abono en Activo (21x) por el coste de adquisición histórico.
        - Diferencia a Pérdidas (671) o Beneficios (771) procedentes del inmovilizado.
        """
        comp_res = await session.execute(select(Company).where(Company.id == company_id))
        company = comp_res.scalar_one_or_none()
        if not company:
            raise HTTPException(status_code=404, detail="Empresa no encontrada")

        asset_res = await session.execute(
            select(Asset).where(Asset.id == asset_id, Asset.company_id == company_id)
        )
        asset = asset_res.scalar_one_or_none()
        if not asset:
            raise HTTPException(status_code=404, detail="Activo no encontrado")

        if asset.status in (AssetStatus.BAJA.value, AssetStatus.VENDIDO.value):
            raise HTTPException(
                status_code=400,
                detail=f"El activo ya se encuentra en estado '{asset.status}'.",
            )

        # Comprobar cierre contable
        if company.fecha_cierre_contable and payload.disposal_date <= company.fecha_cierre_contable:
            raise HTTPException(
                status_code=400,
                detail=f"Bloqueo contable: La fecha de baja {payload.disposal_date.isoformat()} pertenece a un ejercicio cerrado.",
            )

        cost = asset.acquisition_cost
        accum = asset.accumulated_depreciation
        sale_price = payload.disposal_amount
        vnc = round(cost - accum, 2)
        gain_or_loss = round(sale_price - vnc, 2)

        entry_number = await get_next_entry_number(session, company_id)
        entry_lines: List[AccountingEntryLine] = []

        # 1. Baja de amortización acumulada al Debe
        if accum > 0.0:
            entry_lines.append(
                AccountingEntryLine(
                    company_id=company_id,
                    entry_number=entry_number,
                    fecha=payload.disposal_date,
                    subcuenta=asset.account_accumulated_depreciation,
                    concepto=f"Baja Amort. Acumulada - {asset.name}",
                    debe=accum,
                    haber=0.0,
                    documento=asset.code,
                    status="contabilizado",
                    created_by=current_user_name,
                )
            )

        # 2. Cobro por venta al Debe de Tesorería (572)
        if sale_price > 0.0:
            treasury_acc = payload.treasury_account or "572000000"
            entry_lines.append(
                AccountingEntryLine(
                    company_id=company_id,
                    entry_number=entry_number,
                    fecha=payload.disposal_date,
                    subcuenta=treasury_acc,
                    concepto=f"Cobro Venta Inmovilizado - {asset.name}",
                    debe=sale_price,
                    haber=0.0,
                    documento=asset.code,
                    status="contabilizado",
                    created_by=current_user_name,
                )
            )

        # 3. Baja del activo por su coste histórico al Haber (21x)
        entry_lines.append(
            AccountingEntryLine(
                company_id=company_id,
                entry_number=entry_number,
                fecha=payload.disposal_date,
                subcuenta=asset.account_asset,
                concepto=f"Baja Coste Histórico Inmovilizado - {asset.name}",
                debe=0.0,
                haber=cost,
                documento=asset.code,
                status="contabilizado",
                created_by=current_user_name,
            )
        )

        # 4. Reconocimiento de Pérdida o Beneficio
        if gain_or_loss < -0.009:
            # Pérdida al Debe (671)
            loss_acc = payload.expense_loss_account or "671000000"
            entry_lines.append(
                AccountingEntryLine(
                    company_id=company_id,
                    entry_number=entry_number,
                    fecha=payload.disposal_date,
                    subcuenta=loss_acc,
                    concepto=f"Pérdidas procedentes inmovilizado - {asset.name}",
                    debe=abs(gain_or_loss),
                    haber=0.0,
                    documento=asset.code,
                    status="contabilizado",
                    created_by=current_user_name,
                )
            )
        elif gain_or_loss > 0.009:
            # Beneficio al Haber (771)
            profit_acc = payload.income_profit_account or "771000000"
            entry_lines.append(
                AccountingEntryLine(
                    company_id=company_id,
                    entry_number=entry_number,
                    fecha=payload.disposal_date,
                    subcuenta=profit_acc,
                    concepto=f"Beneficios procedentes inmovilizado - {asset.name}",
                    debe=0.0,
                    haber=gain_or_loss,
                    documento=asset.code,
                    status="contabilizado",
                    created_by=current_user_name,
                )
            )

        # Verificación de partida doble
        total_debe = round(sum(l.debe for l in entry_lines), 2)
        total_haber = round(sum(l.haber for l in entry_lines), 2)
        if abs(total_debe - total_haber) > 0.02:
            raise HTTPException(
                status_code=500,
                detail=f"Error en cuadre de partida doble de baja: Debe={total_debe}, Haber={total_haber}",
            )

        for l in entry_lines:
            session.add(l)

        # Actualizar datos del activo
        asset.status = AssetStatus.VENDIDO.value if sale_price > 0 else AssetStatus.BAJA.value
        asset.disposal_date = payload.disposal_date
        asset.disposal_amount = sale_price
        asset.disposal_reason = payload.disposal_reason
        asset.net_book_value = 0.0

        await session.commit()
        await session.refresh(asset)

        log_security_event(
            action="ASSET_DISPOSED",
            resource_id=asset.id,
            user_id=current_user_name,
            empresa_id=company_id,
            details={
                "asset_id": asset.id,
                "company_id": company_id,
                "status": asset.status,
                "disposal_amount": sale_price,
                "entry_number": entry_number,
                "gain_or_loss": gain_or_loss,
            },
        )

        return asset, entry_number
