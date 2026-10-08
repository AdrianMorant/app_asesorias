from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field

class ContactBase(BaseModel):
    contact_type: str = Field("CLIENT", description="CLIENT, SUPPLIER, CREDITOR")
    cif: str = Field(..., min_length=5, max_length=20)
    razon_social: str = Field(..., min_length=2, max_length=255)
    nombre_comercial: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    postal_code: Optional[str] = None
    city: Optional[str] = None
    subcuenta_default: Optional[str] = None
    payment_method: str = "Transferencia"
    iban: Optional[str] = None
    payment_terms_days: Optional[str] = "Contado"
    notes: Optional[str] = None

class ContactCreate(ContactBase):
    pass

class ContactUpdate(BaseModel):
    contact_type: Optional[str] = None
    cif: Optional[str] = None
    razon_social: Optional[str] = None
    nombre_comercial: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    postal_code: Optional[str] = None
    city: Optional[str] = None
    subcuenta_default: Optional[str] = None
    payment_method: Optional[str] = None
    iban: Optional[str] = None
    payment_terms_days: Optional[str] = None
    notes: Optional[str] = None

class ContactResponse(ContactBase):
    id: str
    company_id: str
    created_at: datetime
    total_invoiced: Optional[float] = 0.0

    class Config:
        from_attributes = True
