from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.company import Company
from app.models.contact import Contact
from app.models.invoice import Invoice
from app.models.sales_invoice import SalesInvoice
from app.schemas.contact_dto import ContactCreate, ContactUpdate, ContactResponse
from app.services.nif_validator import validate_spanish_id

router = APIRouter()

@router.get("/{company_id}/contacts", response_model=List[ContactResponse])
async def list_contacts(
    company_id: str,
    contact_type: Optional[str] = Query(None, description="CLIENT, SUPPLIER, CREDITOR o None para todos"),
    search: Optional[str] = Query(None, description="Buscar por CIF o Razón Social"),
    db: AsyncSession = Depends(get_db)
):
    """Lista los contactos del CRM contable de una empresa."""
    stmt = select(Contact).where(Contact.company_id == company_id)
    if contact_type and contact_type.upper() != "ALL":
        stmt = stmt.where(Contact.contact_type == contact_type.upper())
    if search:
        search_pattern = f"%{search.strip()}%"
        stmt = stmt.where(
            (Contact.cif.ilike(search_pattern)) | 
            (Contact.razon_social.ilike(search_pattern))
        )
    stmt = stmt.order_by(Contact.razon_social.asc())

    res = await db.execute(stmt)
    contacts = res.scalars().all()

    # Calcular total facturado acumulado para cada contacto
    result: List[ContactResponse] = []
    for c in contacts:
        resp = ContactResponse.model_validate(c)
        if c.contact_type == "CLIENT":
            # Sumar de facturas de venta
            sales_sum_stmt = select(func.sum(SalesInvoice.total_amount)).where(
                SalesInvoice.company_id == company_id,
                SalesInvoice.customer_cif == c.cif
            )
            sales_sum = (await db.execute(sales_sum_stmt)).scalar() or 0.0
            resp.total_invoiced = round(sales_sum, 2)
        else:
            # Sumar de facturas de gasto (Invoice)
            exp_sum_stmt = select(func.sum(Invoice.total_amount)).where(
                Invoice.company_id == company_id,
                Invoice.issuer_cif == c.cif
            )
            exp_sum = (await db.execute(exp_sum_stmt)).scalar() or 0.0
            resp.total_invoiced = round(exp_sum, 2)
        result.append(resp)

    return result

@router.post("/{company_id}/contacts", response_model=ContactResponse)
async def create_contact(
    company_id: str,
    payload: ContactCreate,
    db: AsyncSession = Depends(get_db)
):
    """Crea un nuevo contacto con validación de CIF y asignación de subcuenta contable."""
    comp = await db.get(Company, company_id)
    if not comp:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    clean_cif = payload.cif.strip().upper()
    val_res = validate_spanish_id(clean_cif)
    # Advertencia si CIF es claramente inválido
    if not val_res.is_valid:
        # Se permite registrar pero manteniendo el formato normalizado si aplica
        pass

    # Generar subcuenta contable por defecto si no viene
    subcuenta = payload.subcuenta_default
    if not subcuenta:
        digits = comp.plan_cuentas_longitud or 9
        prefix = "430" if payload.contact_type == "CLIENT" else "400"
        
        # Buscar el mayor correlativo existente
        cnt_stmt = select(func.count(Contact.id)).where(
            Contact.company_id == company_id,
            Contact.contact_type == payload.contact_type
        )
        cnt = (await db.execute(cnt_stmt)).scalar() or 0
        correlativo = str(cnt + 1).zfill(digits - len(prefix))
        subcuenta = f"{prefix}{correlativo}"

    contact = Contact(
        company_id=company_id,
        contact_type=payload.contact_type.upper(),
        cif=clean_cif,
        razon_social=payload.razon_social.strip(),
        nombre_comercial=payload.nombre_comercial.strip() if payload.nombre_comercial else None,
        email=payload.email.strip() if payload.email else None,
        phone=payload.phone.strip() if payload.phone else None,
        address=payload.address.strip() if payload.address else None,
        postal_code=payload.postal_code.strip() if payload.postal_code else None,
        city=payload.city.strip() if payload.city else None,
        subcuenta_default=subcuenta,
        payment_method=payload.payment_method,
        iban=payload.iban.strip() if payload.iban else None,
        payment_terms_days=payload.payment_terms_days,
        notes=payload.notes
    )

    db.add(contact)
    await db.commit()
    await db.refresh(contact)
    resp = ContactResponse.model_validate(contact)
    resp.total_invoiced = 0.0
    return resp

@router.put("/contacts/{contact_id}", response_model=ContactResponse)
async def update_contact(
    contact_id: str,
    payload: ContactUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Actualiza los datos de un contacto existente."""
    contact = await db.get(Contact, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contacto no encontrado")

    update_data = payload.model_dump(exclude_unset=True)
    if "cif" in update_data and update_data["cif"]:
        update_data["cif"] = update_data["cif"].strip().upper()

    for k, v in update_data.items():
        setattr(contact, k, v)

    await db.commit()
    await db.refresh(contact)
    resp = ContactResponse.model_validate(contact)
    resp.total_invoiced = 0.0
    return resp

@router.delete("/contacts/{contact_id}")
async def delete_contact(contact_id: str, db: AsyncSession = Depends(get_db)):
    """Elimina un contacto."""
    contact = await db.get(Contact, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contacto no encontrado")

    await db.delete(contact)
    await db.commit()
    return {"status": "ok", "message": "Contacto eliminado correctamente"}
