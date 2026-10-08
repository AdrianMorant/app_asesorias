from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field

class CompanyCreateDTO(BaseModel):
    cif: str = Field(description="CIF/NIF de la empresa cliente")
    razon_social: str = Field(description="Razón social de la empresa")
    plan_cuentas_longitud: int = Field(default=9, ge=8, le=10, description="Dígitos de las subcuentas (8, 9 o 10)")
    storage_base_path: str = Field(default="storage", description="Ruta base de almacenamiento físico en disco o red")
    iva_periodicity: str = Field(default="Trimestral", description="Periodicidad de liquidación de IVA: Trimestral, Mensual, Anual")

class CompanyUpdateDTO(BaseModel):
    razon_social: Optional[str] = Field(None, description="Nueva razón social")
    plan_cuentas_longitud: Optional[int] = Field(None, ge=8, le=10, description="Dígitos de las subcuentas (8, 9 o 10)")
    storage_base_path: Optional[str] = Field(None, description="Nueva ruta base de almacenamiento")
    iva_periodicity: Optional[str] = Field(None, description="Periodicidad de IVA: Trimestral, Mensual, Anual")

class CompanyDeleteConfirmDTO(BaseModel):
    cif_confirmation: str = Field(description="CIF de confirmación requerido para autorizar el borrado")

class CompanyResponseDTO(BaseModel):
    id: str
    cif: str
    razon_social: str
    plan_cuentas_longitud: int
    storage_base_path: str
    iva_periodicity: str = "Trimestral"
    created_at: datetime

    class Config:
        from_attributes = True
