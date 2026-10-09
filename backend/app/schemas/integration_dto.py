from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field

class IntegrationConfigCreate(BaseModel):
    software_type: str = Field(..., description="A3, CONTASOL, SAGE, HOLDED_API")
    is_active: bool = True
    configuration_json: Dict[str, Any] = Field(default_factory=dict)

class IntegrationConfigResponse(BaseModel):
    id: str
    company_id: str
    software_type: str
    is_active: bool
    configuration_json: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class GenerateExportRequest(BaseModel):
    software_type: str = Field(..., description="A3, CONTASOL, SAGE, HOLDED_API")
    only_pending: bool = Field(True, description="Exportar sólo asientos no exportados previamente")
    force_reexport: bool = Field(False, description="Permite reexportar asientos ya exportados previamente con justificación")
    reexport_reason: Optional[str] = Field(None, description="Motivo auditable de la reexportación")
    fiscal_year: Optional[int] = Field(None, description="Filtrar facturas de un ejercicio específico")
    invoice_ids: Optional[List[str]] = Field(None, description="Lista opcional de IDs de facturas específicas")
    config_overrides: Optional[Dict[str, Any]] = None

class ExportBatchResponse(BaseModel):
    id: str
    company_id: str
    software_type: str
    file_format: str
    entries_count: int
    invoices_count: int
    total_debe: float
    total_haber: float
    file_name: Optional[str]
    file_path: Optional[str]
    data_fingerprint: Optional[str] = None
    fiscal_year: Optional[int] = None
    status: str
    log_notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
