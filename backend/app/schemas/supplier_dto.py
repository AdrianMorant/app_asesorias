from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field

class SupplierCreateDTO(BaseModel):
    company_id: str = Field(description="ID de la empresa cliente a la que pertenece el proveedor")
    cif: str = Field(description="NIF/CIF del proveedor")
    nombre: str = Field(description="Nombre comercial o razón social")
    subcuenta_proveedor: str = Field(description="Subcuenta contable de proveedor (ej. 400000001)")
    subcuenta_gasto_defecto: str = Field(description="Subcuenta de gasto por defecto (ej. 629000001)")

class SupplierResponseDTO(BaseModel):
    id: str
    company_id: str
    cif: str
    nombre: str
    subcuenta_proveedor: str
    subcuenta_gasto_defecto: str
    created_at: datetime

    class Config:
        from_attributes = True
