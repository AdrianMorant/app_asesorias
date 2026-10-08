from typing import List, Optional, Any
from datetime import date, datetime
from pydantic import BaseModel, Field
from app.schemas.rules_result import TrafficLightStatus

class TaxBreakdownDTO(BaseModel):
    id: Optional[str] = None
    tax_rate: float
    tax_base: float
    tax_amount: float

    class Config:
        from_attributes = True

class AccountingEntryLineDTO(BaseModel):
    id: Optional[str] = None
    entry_number: int
    fecha: date
    subcuenta: str
    concepto: str
    debe: float
    haber: float
    documento: Optional[str] = None

    class Config:
        from_attributes = True

class InvoiceResponseDTO(BaseModel):
    id: str
    company_id: str
    supplier_id: Optional[str] = None
    file_path: str
    file_name: str
    
    invoice_number: str
    issue_date: date
    due_date: Optional[date] = None
    
    issuer_name: str
    issuer_cif: str
    recipient_name: Optional[str] = None
    recipient_cif: Optional[str] = None
    
    total_base: float
    total_tax: float
    total_retention: float
    total_amount: float
    currency: str
    concept_summary: Optional[str] = None
    
    status: TrafficLightStatus
    status_reasons: List[str]
    raw_extraction: Optional[Any] = None
    
    # Máquina de estados documental (PRD Fase 1)
    workflow_status: str = "a_revisar"  # 'a_revisar', 'prevalidado', 'validado', 'contabilizado', 'archivado'
    es_multifactura: bool = False
    num_paginas: int = 1
    parent_invoice_id: Optional[str] = None

    # Casuísticas fiscales y de control (PRD Fase 2)
    file_hash: Optional[str] = None
    fecha_contable: Optional[date] = None
    is_rectificativa: bool = False
    rectified_invoice_number: Optional[str] = None
    rectified_invoice_date: Optional[date] = None
    has_retention: bool = False
    retention_percentage: float = 0.0
    retention_model: str = "111/190"
    has_suplidos: bool = False
    suplidos_amount: float = 0.0
    suplidos_account: Optional[str] = None
    postal_code: Optional[str] = None
    country_code: str = "ES"
    is_duplicate: bool = False
    duplicate_of_id: Optional[str] = None
    
    is_processed: bool
    exported_to_erp: bool = False
    export_batch_id: Optional[str] = None
    created_at: datetime
    
    tax_breakdown: List[TaxBreakdownDTO] = []
    accounting_entries: List[AccountingEntryLineDTO] = []

    class Config:
        from_attributes = True

class InvoiceUpdateDTO(BaseModel):
    supplier_id: Optional[str] = None
    invoice_number: Optional[str] = None
    issue_date: Optional[date] = None
    due_date: Optional[date] = None
    fecha_contable: Optional[date] = None
    issuer_name: Optional[str] = None
    issuer_cif: Optional[str] = None
    total_base: Optional[float] = None
    total_tax: Optional[float] = None
    total_retention: Optional[float] = None
    total_amount: Optional[float] = None
    concept_summary: Optional[str] = None
    workflow_status: Optional[str] = None
    es_multifactura: Optional[bool] = None
    is_processed: Optional[bool] = None
    is_rectificativa: Optional[bool] = None
    rectified_invoice_number: Optional[str] = None
    rectified_invoice_date: Optional[date] = None
    has_retention: Optional[bool] = None
    retention_percentage: Optional[float] = None
    retention_model: Optional[str] = None
    has_suplidos: Optional[bool] = None
    suplidos_amount: Optional[float] = None
    suplidos_account: Optional[str] = None
    postal_code: Optional[str] = None
    country_code: Optional[str] = None

class NextSubaccountResponseDTO(BaseModel):
    prefix: str
    next_subaccount: str
    generic_subaccount: str
    company_plan_longitud: int

class ApproveInvoiceDTO(BaseModel):
    custom_subfolder: Optional[str] = Field(default=None, description="Subcarpeta de destino personalizada (ej. A28015865/2024/2T/recibidas)")
    custom_filename: Optional[str] = Field(default=None, description="Nombre de archivo de destino personalizado")

class BulkDeleteInvoicesDTO(BaseModel):
    invoice_ids: List[str] = Field(description="Lista de IDs de facturas a eliminar masivamente")

# DTOs para el Maquetador Visual de Corte Multi-Factura
class PageThumbnailDTO(BaseModel):
    page_number: int
    thumbnail_url: str

class InvoicePagesResponseDTO(BaseModel):
    invoice_id: str
    file_name: str
    num_paginas: int
    es_multifactura: bool
    pages: List[PageThumbnailDTO]

class SplitGroupDTO(BaseModel):
    page_numbers: List[int] = Field(description="Lista de páginas (1-indexed) que forman este sub-documento")
    custom_name: Optional[str] = Field(default=None, description="Nombre personalizado opcional")

class SplitInvoiceRequestDTO(BaseModel):
    splits: List[SplitGroupDTO] = Field(description="Lista de grupos de páginas a separar en facturas independientes")


