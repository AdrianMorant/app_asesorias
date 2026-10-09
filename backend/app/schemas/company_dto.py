from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field

class CompanyCreateDTO(BaseModel):
    cif: str = Field(description="CIF/NIF de la empresa cliente")
    razon_social: str = Field(description="Razón social de la empresa")
    plan_cuentas_longitud: int = Field(default=9, ge=8, le=10, description="Dígitos de las subcuentas (8, 9 o 10)")
    storage_base_path: str = Field(default="storage", description="Ruta base de almacenamiento físico en disco o red")
    iva_periodicity: str = Field(default="Trimestral", description="Periodicidad de liquidación de IVA: Trimestral, Mensual, Anual")
    modalidad_uso: str = Field(default="copiloto_contable", description="Modalidad de uso: 'erp_completo' o 'copiloto_contable'")
    regimen_tributario: str = Field(default="general", description="Régimen tributario: general, simplificado, recargo_equivalencia, exento")
    software_destino: str = Field(default="a3", description="Software contable de destino: a3, contasol, sage, holded, anfix, cegid, otro")
    domicilio_fiscal: Optional[str] = Field(None, description="Domicilio fiscal de la empresa")
    email_contacto: Optional[str] = Field(None, description="Email de contacto de la empresa")
    telefono_contacto: Optional[str] = Field(None, description="Teléfono de contacto de la empresa")

class CompanyUpdateDTO(BaseModel):
    razon_social: Optional[str] = Field(None, description="Nueva razón social")
    plan_cuentas_longitud: Optional[int] = Field(None, ge=8, le=10, description="Dígitos de las subcuentas (8, 9 o 10)")
    storage_base_path: Optional[str] = Field(None, description="Nueva ruta base de almacenamiento")
    iva_periodicity: Optional[str] = Field(None, description="Periodicidad de IVA: Trimestral, Mensual, Anual")
    modalidad_uso: Optional[str] = Field(None, description="Modalidad de uso: 'erp_completo' o 'copiloto_contable'")
    regimen_tributario: Optional[str] = Field(None, description="Régimen tributario")
    software_destino: Optional[str] = Field(None, description="Software contable de destino")
    domicilio_fiscal: Optional[str] = Field(None, description="Domicilio fiscal")
    email_contacto: Optional[str] = Field(None, description="Email de contacto")
    telefono_contacto: Optional[str] = Field(None, description="Teléfono de contacto")
    is_active: Optional[bool] = Field(None, description="Estado activo de la empresa")

class CompanyDeleteConfirmDTO(BaseModel):
    cif_confirmation: str = Field(description="CIF de confirmación requerido para autorizar el borrado")

class CompanyResponseDTO(BaseModel):
    id: str
    cif: str
    razon_social: str
    plan_cuentas_longitud: int
    storage_base_path: str
    iva_periodicity: str = "Trimestral"
    modalidad_uso: str = "copiloto_contable"
    regimen_tributario: str = "general"
    software_destino: str = "a3"
    domicilio_fiscal: Optional[str] = None
    email_contacto: Optional[str] = None
    telefono_contacto: Optional[str] = None
    is_active: bool = True
    created_at: datetime

    class Config:
        from_attributes = True
