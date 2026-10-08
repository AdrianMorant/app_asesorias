from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.supplier import Supplier
from app.models.company import Company
from app.schemas.supplier_dto import SupplierCreateDTO, SupplierResponseDTO
from app.services.nif_validator import normalize_nif, validate_spanish_id

router = APIRouter()

@router.post("", response_model=SupplierResponseDTO, status_code=status.HTTP_201_CREATED)
async def create_supplier(
    payload: SupplierCreateDTO,
    db: AsyncSession = Depends(get_db)
):
    """Registra un nuevo proveedor o acreedor con su mapeo contable (400/410 y 6XX)."""
    # Verificar empresa
    c_res = await db.execute(select(Company).where(Company.id == payload.company_id))
    if not c_res.scalars().first():
        raise HTTPException(status_code=404, detail="Empresa no encontrada.")

    norm_cif = normalize_nif(payload.cif)
    nif_val = validate_spanish_id(norm_cif)
    if not nif_val.is_valid:
        raise HTTPException(
            status_code=400,
            detail=f"NIF/CIF del proveedor no válido: {nif_val.error_message}"
        )

    # Comprobar si ya existe en esta empresa
    stmt = select(Supplier).where(
        Supplier.company_id == payload.company_id,
        Supplier.cif == norm_cif
    )
    s_res = await db.execute(stmt)
    if s_res.scalars().first():
        raise HTTPException(
            status_code=400,
            detail="Este proveedor ya se encuentra registrado para esta empresa."
        )

    supplier = Supplier(
        company_id=payload.company_id,
        cif=norm_cif,
        nombre=payload.nombre,
        subcuenta_proveedor=payload.subcuenta_proveedor,
        subcuenta_gasto_defecto=payload.subcuenta_gasto_defecto
    )
    db.add(supplier)
    await db.commit()
    await db.refresh(supplier)
    return supplier

@router.get("", response_model=List[SupplierResponseDTO])
async def list_suppliers(
    company_id: Optional[str] = Query(None, description="Filtrar por empresa"),
    db: AsyncSession = Depends(get_db)
):
    """Lista proveedores registrados."""
    stmt = select(Supplier).order_by(Supplier.nombre)
    if company_id:
        stmt = stmt.where(Supplier.company_id == company_id)
    res = await db.execute(stmt)
    return res.scalars().all()
