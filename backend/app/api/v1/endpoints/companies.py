from pathlib import Path
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.company import Company
from app.models.invoice import Invoice
from app.schemas.company_dto import (
    CompanyCreateDTO,
    CompanyUpdateDTO,
    CompanyResponseDTO,
)
from app.services.nif_validator import normalize_nif, validate_spanish_id

router = APIRouter()

@router.post("", response_model=CompanyResponseDTO, status_code=status.HTTP_201_CREATED)
async def create_company(
    payload: CompanyCreateDTO,
    db: AsyncSession = Depends(get_db)
):
    """Crea una nueva empresa cliente en la asesoría."""
    norm_cif = normalize_nif(payload.cif)
    nif_val = validate_spanish_id(norm_cif)
    if not nif_val.is_valid:
        raise HTTPException(
            status_code=400,
            detail=f"CIF de la empresa no válido: {nif_val.error_message}"
        )

    # Comprobar duplicado
    stmt = select(Company).where(Company.cif == norm_cif)
    res = await db.execute(stmt)
    if res.scalars().first():
        raise HTTPException(status_code=400, detail="Ya existe una empresa registrada con este CIF.")

    company = Company(
        cif=norm_cif,
        razon_social=payload.razon_social,
        plan_cuentas_longitud=payload.plan_cuentas_longitud,
        storage_base_path=payload.storage_base_path or "storage",
        iva_periodicity=payload.iva_periodicity or "Trimestral"
    )
    db.add(company)
    await db.commit()
    await db.refresh(company)

    # Precargar automáticamente el catálogo completo del PGC PYMES adaptado a su longitud
    try:
        from app.services.pyme_pgc_seed import seed_company_chart_of_accounts
        await seed_company_chart_of_accounts(db, company.id, company.plan_cuentas_longitud)
    except Exception as e:
        pass

    return company

@router.get("", response_model=List[CompanyResponseDTO])
async def list_companies(db: AsyncSession = Depends(get_db)):
    """Lista todas las empresas asesoradas."""
    res = await db.execute(select(Company).order_by(Company.razon_social))
    return res.scalars().all()

@router.get("/{company_id}", response_model=CompanyResponseDTO)
async def get_company(company_id: str, db: AsyncSession = Depends(get_db)):
    """Obtiene una empresa por ID."""
    res = await db.execute(select(Company).where(Company.id == company_id))
    company = res.scalars().first()
    if not company:
        raise HTTPException(status_code=404, detail="Empresa no encontrada.")
    return company

@router.put("/{company_id}", response_model=CompanyResponseDTO)
async def update_company(
    company_id: str,
    payload: CompanyUpdateDTO,
    db: AsyncSession = Depends(get_db)
):
    """Edita los datos de la empresa: razón social, dígitos de cuentas, ruta de almacenamiento o periodicidad de IVA."""
    res = await db.execute(select(Company).where(Company.id == company_id))
    company = res.scalars().first()
    if not company:
        raise HTTPException(status_code=404, detail="Empresa no encontrada.")

    if payload.razon_social is not None:
        company.razon_social = payload.razon_social.strip()
    if payload.plan_cuentas_longitud is not None:
        company.plan_cuentas_longitud = payload.plan_cuentas_longitud
    if payload.storage_base_path is not None:
        company.storage_base_path = payload.storage_base_path.strip()
    if payload.iva_periodicity is not None:
        company.iva_periodicity = payload.iva_periodicity.strip()

    await db.commit()
    await db.refresh(company)
    return company

@router.delete("/{company_id}")
async def delete_company(
    company_id: str,
    cif_confirmation: str = Query(..., description="Confirmación tecleando el CIF de la empresa"),
    db: AsyncSession = Depends(get_db)
):
    """
    Elimina una empresa con confirmación estricta por CIF.
    Borra en cascada facturas, asientos, proveedores, catálogo contable
    y elimina físicamente los archivos del disco para evitar huérfanos.
    """
    res = await db.execute(
        select(Company)
        .where(Company.id == company_id)
        .options(selectinload(Company.invoices))
    )
    company = res.scalars().first()
    if not company:
        raise HTTPException(status_code=404, detail="Empresa no encontrada.")

    # Validación de seguridad estricta
    if normalize_nif(cif_confirmation) != normalize_nif(company.cif):
        raise HTTPException(
            status_code=400,
            detail=f"Confirmación incorrecta. Debe escribir exactamente el CIF '{company.cif}' para confirmar la eliminación."
        )

    # 1. Borrar físicamente los archivos de facturas asociadas
    deleted_files_count = 0
    for inv in company.invoices:
        if inv.file_path:
            p = Path(inv.file_path)
            if p.exists():
                try:
                    p.unlink()
                    deleted_files_count += 1
                except Exception:
                    pass

    # 2. Borrar empresa en base de datos (cascada automática a invoices, suppliers, accounts, entries)
    await db.delete(company)
    await db.commit()

    return {
        "success": True,
        "message": f"Empresa '{company.razon_social}' y sus datos asociados eliminados correctamente.",
        "deleted_files_count": deleted_files_count
    }
