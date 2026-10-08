import uuid
from datetime import datetime, timezone, date
from sqlalchemy import Column, String, Float, Boolean, DateTime, Date, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.core.database import Base

class SalesInvoice(Base):
    """
    Factura emitida de venta, presupuesto o factura proforma.
    """
    __tablename__ = "sales_invoices"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    contact_id = Column(String(36), ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True, index=True)
    
    doc_type = Column(String(20), default="INVOICE", nullable=False)  # INVOICE, ESTIMATE, PROFORMA
    series = Column(String(20), default="F2026", nullable=False)
    invoice_number = Column(String(50), nullable=False, index=True)
    
    issue_date = Column(Date, default=date.today, nullable=False)
    due_date = Column(Date, nullable=True)
    
    # Datos fiscales del cliente receptor
    customer_name = Column(String(255), nullable=False)
    customer_cif = Column(String(20), nullable=False, index=True)
    customer_address = Column(String(255), nullable=True)
    
    # Importes calculados
    total_base = Column(Float, default=0.0, nullable=False)
    total_tax = Column(Float, default=0.0, nullable=False)
    total_retention = Column(Float, default=0.0, nullable=False)
    total_amount = Column(Float, default=0.0, nullable=False)
    currency = Column(String(10), default="EUR", nullable=False)
    
    # Estado del documento
    status = Column(String(20), default="ISSUED", nullable=False)  # DRAFT, ISSUED, SENT, PAID, CANCELLED
    notes = Column(Text, nullable=True)
    
    # Trazabilidad de exportación a ERP externo
    exported_to_erp = Column(Boolean, default=False, nullable=False)
    export_batch_id = Column(String(36), ForeignKey("export_batches.id", ondelete="SET NULL"), nullable=True, index=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relaciones
    company = relationship("Company", back_populates="sales_invoices")
    contact = relationship("Contact", back_populates="sales_invoices")
    lines = relationship("SalesInvoiceLineItem", back_populates="sales_invoice", cascade="all, delete-orphan")
    tax_breakdown = relationship("SalesInvoiceTaxBreakdown", back_populates="sales_invoice", cascade="all, delete-orphan")
    accounting_entries = relationship("AccountingEntryLine", back_populates="sales_invoice", cascade="all, delete-orphan")


class SalesInvoiceLineItem(Base):
    """
    Línea de concepto o partida dentro de una factura de venta.
    """
    __tablename__ = "sales_invoice_lines"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    sales_invoice_id = Column(String(36), ForeignKey("sales_invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    
    description = Column(String(255), nullable=False)
    quantity = Column(Float, default=1.0, nullable=False)
    unit_price = Column(Float, default=0.0, nullable=False)
    tax_rate = Column(Float, default=21.0, nullable=False)       # 21, 10, 4, 0
    retention_rate = Column(Float, default=0.0, nullable=False) # 15, 7, 0
    subtotal = Column(Float, default=0.0, nullable=False)

    # Relación
    sales_invoice = relationship("SalesInvoice", back_populates="lines")


class SalesInvoiceTaxBreakdown(Base):
    """
    Desglose fiscal de IVA por tipos para facturación emitida.
    """
    __tablename__ = "sales_invoice_tax_breakdowns"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    sales_invoice_id = Column(String(36), ForeignKey("sales_invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    
    tax_rate = Column(Float, nullable=False)
    tax_base = Column(Float, nullable=False)
    tax_amount = Column(Float, nullable=False)

    # Relación
    sales_invoice = relationship("SalesInvoice", back_populates="tax_breakdown")
