"""
Esquemas Pydantic DTO para el Módulo de Inmovilizado y Amortizaciones.
Compatible con FastAPI v1, validaciones PGC y exportaciones contables.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, Field

from app.models.asset import AssetCategory, DepreciationMethod, AssetStatus


class DepreciationScheduleDTO(BaseModel):
    id: str
    asset_id: str
    company_id: str
    fiscal_year: int
    period_name: str
    start_date: date
    end_date: date
    depreciation_amount: float
    accumulated_depreciation: float
    net_book_value: float
    is_posted: bool
    accounting_entry_number: Optional[int] = None
    posted_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AssetCreateDTO(BaseModel):
    code: str = Field(..., min_length=1, max_length=50, description="Código de activo único (ej. ACT-2026-001)")
    name: str = Field(..., min_length=2, max_length=255, description="Descripción o nombre del bien")
    category: AssetCategory = Field(default=AssetCategory.EQUIPOS_INFORMATICOS, description="Categoría según PGC")
    acquisition_date: date = Field(..., description="Fecha de compra o recepción")
    acquisition_cost: float = Field(..., gt=0.0, description="Coste histórico o valor de adquisición")
    residual_value: float = Field(default=0.0, ge=0.0, description="Valor residual estimado al fin de vida útil")
    depreciation_start_date: Optional[date] = Field(None, description="Fecha inicio de amortización (por defecto fecha adquisición)")
    useful_life_years: float = Field(..., gt=0.0, le=100.0, description="Años de vida útil estimada")
    depreciation_method: DepreciationMethod = Field(default=DepreciationMethod.LINEAL, description="Método de amortización")
    
    # Cuentas PGC opcionales (si se omiten, se infieren según categoría y dígitos de la empresa)
    account_asset: Optional[str] = Field(None, max_length=20, description="Subcuenta de activo (ej. 217000000)")
    account_accumulated_depreciation: Optional[str] = Field(None, max_length=20, description="Subcuenta de amortización acumulada (ej. 281700000)")
    account_depreciation_expense: Optional[str] = Field(None, max_length=20, description="Subcuenta de dotación gasto (ej. 681000000)")
    
    supplier_id: Optional[str] = None
    invoice_id: Optional[str] = None
    notes: Optional[str] = None


class AssetUpdateDTO(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    category: Optional[AssetCategory] = None
    residual_value: Optional[float] = Field(None, ge=0.0)
    useful_life_years: Optional[float] = Field(None, gt=0.0, le=100.0)
    depreciation_method: Optional[DepreciationMethod] = None
    account_asset: Optional[str] = Field(None, max_length=20)
    account_accumulated_depreciation: Optional[str] = Field(None, max_length=20)
    account_depreciation_expense: Optional[str] = Field(None, max_length=20)
    notes: Optional[str] = None


class AssetResponseDTO(BaseModel):
    id: str
    company_id: str
    code: str
    name: str
    category: str
    acquisition_date: date
    acquisition_cost: float
    residual_value: float
    depreciation_start_date: date
    useful_life_years: float
    depreciation_method: str
    account_asset: str
    account_accumulated_depreciation: str
    account_depreciation_expense: str
    supplier_id: Optional[str] = None
    invoice_id: Optional[str] = None
    accumulated_depreciation: float
    net_book_value: float
    status: str
    disposal_date: Optional[date] = None
    disposal_amount: Optional[float] = None
    disposal_reason: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    schedules: List[DepreciationScheduleDTO] = []

    class Config:
        from_attributes = True


class PostDepreciationRequestDTO(BaseModel):
    fiscal_year: Optional[int] = Field(None, description="Ejercicio a contabilizar. Si se omite, se procesa el siguiente no contabilizado.")
    posting_date: Optional[date] = Field(None, description="Fecha contable del asiento (por defecto 31 de diciembre del año fiscal)")


class DisposeAssetRequestDTO(BaseModel):
    disposal_date: date = Field(..., description="Fecha de baja o enajenación")
    disposal_amount: float = Field(default=0.0, ge=0.0, description="Precio de venta (0 si es desguace o siniestro)")
    disposal_reason: str = Field(..., min_length=3, max_length=255, description="Motivo auditable (ej. Venta de vehículo, Obsolescencia técnica)")
    treasury_account: Optional[str] = Field("572000000", max_length=20, description="Subcuenta de tesorería para cobro de la venta")
    expense_loss_account: Optional[str] = Field("671000000", max_length=20, description="Pérdidas procedentes del inmovilizado material (PGC)")
    income_profit_account: Optional[str] = Field("771000000", max_length=20, description="Beneficios procedentes del inmovilizado material (PGC)")


class AssetSummaryMetricsDTO(BaseModel):
    total_assets_count: int
    total_acquisition_cost: float
    total_accumulated_depreciation: float
    total_net_book_value: float
    active_count: int
    fully_depreciated_count: int
    disposed_count: int
