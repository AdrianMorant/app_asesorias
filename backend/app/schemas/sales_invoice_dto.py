from typing import Optional, List
from datetime import date, datetime
from pydantic import BaseModel, Field

class SalesInvoiceLineCreate(BaseModel):
    description: str
    quantity: float = 1.0
    unit_price: float = 0.0
    tax_rate: float = 21.0
    retention_rate: float = 0.0

class SalesInvoiceLineResponse(SalesInvoiceLineCreate):
    id: str
    subtotal: float

    class Config:
        from_attributes = True

class SalesInvoiceTaxResponse(BaseModel):
    id: str
    tax_rate: float
    tax_base: float
    tax_amount: float

    class Config:
        from_attributes = True

class SalesInvoiceCreate(BaseModel):
    doc_type: str = Field("INVOICE", description="INVOICE, ESTIMATE, PROFORMA")
    series: str = Field("F2026")
    invoice_number: Optional[str] = None  # Si es null, auto-genera secuencial
    contact_id: Optional[str] = None
    customer_name: str
    customer_cif: str
    customer_address: Optional[str] = None
    issue_date: date = Field(default_factory=date.today)
    due_date: Optional[date] = None
    lines: List[SalesInvoiceLineCreate] = Field(default_factory=list)
    notes: Optional[str] = None

class SalesInvoiceResponse(BaseModel):
    id: str
    company_id: str
    contact_id: Optional[str]
    doc_type: str
    series: str
    invoice_number: str
    issue_date: date
    due_date: Optional[date]
    customer_name: str
    customer_cif: str
    customer_address: Optional[str]
    total_base: float
    total_tax: float
    total_retention: float
    total_amount: float
    currency: str
    status: str
    notes: Optional[str]
    exported_to_erp: bool
    export_batch_id: Optional[str]
    created_at: datetime
    lines: List[SalesInvoiceLineResponse] = []
    tax_breakdown: List[SalesInvoiceTaxResponse] = []

    class Config:
        from_attributes = True

class UpdateSalesInvoiceStatus(BaseModel):
    status: str = Field(..., description="DRAFT, ISSUED, SENT, PAID, CANCELLED")
