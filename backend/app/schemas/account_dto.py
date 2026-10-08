from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field

class AccountCreateDTO(BaseModel):
    codigo: str = Field(description="Código de subcuenta (ej. 629000001, 400000042, 430000001)")
    descripcion: str = Field(description="Nombre o descripción contable de la cuenta")
    tipo: Optional[str] = Field(default=None, description="GASTO, INGRESO, PROVEEDOR, ACREEDOR, CLIENTE, FINANCIERO, OTRO")
    cif_asociado: Optional[str] = Field(default=None, description="NIF/CIF del tercero asociado si aplica")
    debe_inicial: Optional[float] = Field(default=0.0, description="Saldo o Debe inicial acumulado")
    haber_inicial: Optional[float] = Field(default=0.0, description="Saldo o Haber inicial acumulado")

class AccountUpdateDTO(BaseModel):
    descripcion: Optional[str] = Field(default=None, description="Nueva descripción contable")
    tipo: Optional[str] = Field(default=None, description="Nuevo tipo de cuenta")
    cif_asociado: Optional[str] = Field(default=None, description="Nuevo CIF/NIF asociado")
    debe_inicial: Optional[float] = Field(default=None, description="Debe inicial acumulado")
    haber_inicial: Optional[float] = Field(default=None, description="Haber inicial acumulado")

class AccountResponseDTO(BaseModel):
    id: str
    company_id: str
    codigo: str
    descripcion: str
    tipo: str
    cif_asociado: Optional[str] = None
    debe_acumulado: float = 0.0
    haber_acumulado: float = 0.0
    saldo_actual: float = 0.0
    tipo_saldo: str = "CERO"  # DEUDOR, ACREEDOR, CERO
    created_at: datetime

    class Config:
        from_attributes = True

class AccountPaginatedResponseDTO(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[AccountResponseDTO]

class AccountImportSummaryDTO(BaseModel):
    total_processed: int
    created: int
    updated: int
    errors: List[str]
