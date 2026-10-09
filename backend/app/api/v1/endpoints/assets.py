"""
Endpoints API REST para el Módulo de Inmovilizado y Amortizaciones.
Ubicación: /api/v1/companies/{company_id}/assets
"""

from __future__ import annotations

from typing import List, Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
from sqlalchemy import select, func, or_, and_, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.asset import Asset, AssetDepreciationSchedule, AssetStatus, AssetCategory
from app.models.company import Company
from app.models.user import User, UserRole
from app.core.auth_deps import (
    get_current_user_optional,
    get_current_user,
    require_company_permission,
    require_roles,
)
from app.schemas.asset_dto import (
    AssetCreateDTO,
    AssetUpdateDTO,
    AssetResponseDTO,
    DepreciationScheduleDTO,
    PostDepreciationRequestDTO,
    DisposeAssetRequestDTO,
    AssetSummaryMetricsDTO,
)
from app.services.asset_service import AssetService
from app.core.audit_logger import log_security_event

router = APIRouter()


@router.get(
    "/{company_id}/assets/summary",
    response_model=AssetSummaryMetricsDTO,
    summary="Resumen y métricas globales de inmovilizado",
)
async def get_assets_summary(
    company_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Devuelve los totales de coste de adquisición, amortización acumulada y VNC."""
    # Verificar empresa
    c_res = await db.execute(select(Company).where(Company.id == company_id))
    if not c_res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    assets_res = await db.execute(select(Asset).where(Asset.company_id == company_id))
    assets = assets_res.scalars().all()

    total_cost = round(sum(a.acquisition_cost for a in assets), 2)
    total_accum = round(sum(a.accumulated_depreciation for a in assets), 2)
    total_vnc = round(sum(a.net_book_value for a in assets), 2)

    active_count = sum(1 for a in assets if a.status == AssetStatus.ACTIVO.value)
    fully_deprec = sum(1 for a in assets if a.status == AssetStatus.TOTALMENTE_AMORTIZADO.value)
    disposed = sum(1 for a in assets if a.status in (AssetStatus.BAJA.value, AssetStatus.VENDIDO.value))

    return AssetSummaryMetricsDTO(
        total_assets_count=len(assets),
        total_acquisition_cost=total_cost,
        total_accumulated_depreciation=total_accum,
        total_net_book_value=total_vnc,
        active_count=active_count,
        fully_depreciated_count=fully_deprec,
        disposed_count=disposed,
    )


@router.get(
    "/{company_id}/assets",
    response_model=List[AssetResponseDTO],
    summary="Listar activos fijos de la empresa",
)
async def list_assets(
    company_id: str,
    status_filter: Optional[str] = Query(None, alias="status", description="Filtrar por estado"),
    category_filter: Optional[str] = Query(None, alias="category", description="Filtrar por categoría"),
    search: Optional[str] = Query(None, description="Búsqueda por código o nombre"),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Lista todos los activos de la empresa con sus cuadros de amortización cargados."""
    c_res = await db.execute(select(Company).where(Company.id == company_id))
    if not c_res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    query = (
        select(Asset)
        .options(selectinload(Asset.schedules))
        .where(Asset.company_id == company_id)
        .order_by(Asset.code.asc())
    )

    if status_filter:
        query = query.where(Asset.status == status_filter.upper())
    if category_filter:
        query = query.where(Asset.category == category_filter.upper())
    if search:
        search_pattern = f"%{search.strip()}%"
        query = query.where(
            or_(
                Asset.code.ilike(search_pattern),
                Asset.name.ilike(search_pattern),
                Asset.notes.ilike(search_pattern),
            )
        )

    res = await db.execute(query)
    return res.scalars().all()


@router.post(
    "/{company_id}/assets",
    response_model=AssetResponseDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Crear nuevo activo de inmovilizado",
)
async def create_asset(
    company_id: str,
    payload: AssetCreateDTO,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Registra un nuevo activo fijo, autogenera cuentas del PGC y calcula el cuadro de amortizaciones."""
    user_name = current_user.full_name if current_user else "sistema"
    asset = await AssetService.create_asset(
        session=db,
        company_id=company_id,
        data=payload,
        current_user_name=user_name,
    )
    # Cargar schedules para el response DTO
    res = await db.execute(
        select(Asset).options(selectinload(Asset.schedules)).where(Asset.id == asset.id)
    )
    return res.scalar_one()


@router.get(
    "/{company_id}/assets/{asset_id}",
    response_model=AssetResponseDTO,
    summary="Obtener detalle de un activo fijo",
)
async def get_asset_detail(
    company_id: str,
    asset_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Devuelve la ficha completa del activo con su calendario detallado."""
    res = await db.execute(
        select(Asset)
        .options(selectinload(Asset.schedules))
        .where(Asset.id == asset_id, Asset.company_id == company_id)
    )
    asset = res.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Activo no encontrado")
    return asset


@router.put(
    "/{company_id}/assets/{asset_id}",
    response_model=AssetResponseDTO,
    summary="Actualizar datos de un activo",
)
async def update_asset(
    company_id: str,
    asset_id: str,
    payload: AssetUpdateDTO,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Actualiza datos descriptivos y cuentas contables asociadas."""
    res = await db.execute(
        select(Asset)
        .options(selectinload(Asset.schedules))
        .where(Asset.id == asset_id, Asset.company_id == company_id)
    )
    asset = res.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Activo no encontrado")

    if payload.name is not None:
        asset.name = payload.name
    if payload.residual_value is not None:
        asset.residual_value = payload.residual_value
    if payload.account_asset is not None:
        asset.account_asset = payload.account_asset
    if payload.account_accumulated_depreciation is not None:
        asset.account_accumulated_depreciation = payload.account_accumulated_depreciation
    if payload.account_depreciation_expense is not None:
        asset.account_depreciation_expense = payload.account_depreciation_expense
    if payload.notes is not None:
        asset.notes = payload.notes

    await db.commit()
    await db.refresh(asset)
    return asset


@router.post(
    "/{company_id}/assets/{asset_id}/depreciate",
    summary="Contabilizar dotación de amortización periódica",
)
async def post_depreciation(
    company_id: str,
    asset_id: str,
    payload: PostDepreciationRequestDTO = PostDepreciationRequestDTO(),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Contabiliza la cuota de amortización de un periodo en el Libro Diario:
    - Genera asiento correlativo Debe 681 / Haber 281.
    - Valida que el ejercicio no esté cerrado.
    - Actualiza el saldo contable del activo y marca el periodo como contabilizado.
    """
    user_name = current_user.full_name if current_user else "sistema"
    asset, schedule, entry_number = await AssetService.post_depreciation_quota(
        session=db,
        company_id=company_id,
        asset_id=asset_id,
        payload=payload,
        current_user_name=user_name,
    )
    return {
        "status": "success",
        "message": f"Dotación de amortización del ejercicio {schedule.fiscal_year} contabilizada en el asiento #{entry_number}.",
        "entry_number": entry_number,
        "fiscal_year": schedule.fiscal_year,
        "depreciation_amount": schedule.depreciation_amount,
        "accumulated_depreciation": asset.accumulated_depreciation,
        "net_book_value": asset.net_book_value,
        "asset_status": asset.status,
    }


@router.post(
    "/{company_id}/assets/{asset_id}/dispose",
    summary="Baja o venta de un activo de inmovilizado",
)
async def dispose_asset(
    company_id: str,
    asset_id: str,
    payload: DisposeAssetRequestDTO,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Gestiona la baja o enajenación de un activo:
    - Asiento contable de desinversión (Cuentas 281, 572, 21x, 671 y 771).
    - Cuadre riguroso de partida doble.
    - Actualización del estado a VENDIDO o BAJA.
    """
    user_name = current_user.full_name if current_user else "sistema"
    asset, entry_number = await AssetService.dispose_asset(
        session=db,
        company_id=company_id,
        asset_id=asset_id,
        payload=payload,
        current_user_name=user_name,
    )
    return {
        "status": "success",
        "message": f"Activo {asset.code} dado de baja/vendido con éxito en el asiento #{entry_number}.",
        "entry_number": entry_number,
        "asset_status": asset.status,
        "disposal_amount": asset.disposal_amount,
        "disposal_date": asset.disposal_date.isoformat() if asset.disposal_date else None,
    }


@router.delete(
    "/{company_id}/assets/{asset_id}",
    status_code=status.HTTP_200_OK,
    summary="Eliminar activo de inmovilizado",
)
async def delete_asset(
    company_id: str,
    asset_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Elimina el activo solo si no tiene ninguna dotación contabilizada."""
    res = await db.execute(
        select(Asset)
        .options(selectinload(Asset.schedules))
        .where(Asset.id == asset_id, Asset.company_id == company_id)
    )
    asset = res.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Activo no encontrado")

    if any(s.is_posted for s in asset.schedules):
        raise HTTPException(
            status_code=400,
            detail="No se puede eliminar un activo con amortizaciones ya contabilizadas. Debe darse de baja contablemente.",
        )

    await db.delete(asset)
    await db.commit()

    user_name = current_user.full_name if current_user else "sistema"
    log_security_event(
        action="ASSET_DELETED",
        resource_id=asset_id,
        user_id=user_name,
        empresa_id=company_id,
        details={"asset_id": asset_id, "company_id": company_id, "code": asset.code},
    )

    return {"status": "success", "message": f"Activo {asset.code} eliminado correctamente."}
