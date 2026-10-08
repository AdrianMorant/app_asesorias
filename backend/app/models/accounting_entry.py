import uuid
from datetime import date
from sqlalchemy import Column, String, Float, Integer, Date, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class AccountingEntryLine(Base):
    """
    Representa una línea / apunte del asiento contable en partida doble (PGC español).
    Puede pertenecer a una factura de gasto (Invoice), una factura de venta (SalesInvoice)
    o directamente a la empresa como apunte contable manual o de ajuste.
    """
    __tablename__ = "accounting_entry_lines"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Orígenes de la línea
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True)
    invoice_id = Column(String(36), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=True, index=True)
    sales_invoice_id = Column(String(36), ForeignKey("sales_invoices.id", ondelete="CASCADE"), nullable=True, index=True)
    
    entry_number = Column(Integer, nullable=False, default=1)
    fecha = Column(Date, nullable=False, default=date.today)
    
    subcuenta = Column(String(20), nullable=False, index=True)  # Ej. 629000000, 472000021, 400000001, 700000000, 430000001
    concepto = Column(String(255), nullable=False)              # Ej. "Fra. 2024/001 - Proveedor SL"
    
    debe = Column(Float, nullable=False, default=0.0)
    haber = Column(Float, nullable=False, default=0.0)
    
    documento = Column(String(100), nullable=True)             # Número de factura o documento asociado
    
    # Trazabilidad de exportación a ERP (A3, Contasol, Sage, Holded)
    exported_to_erp = Column(Boolean, default=False, nullable=False)
    export_batch_id = Column(String(36), ForeignKey("export_batches.id", ondelete="SET NULL"), nullable=True, index=True)

    # Relaciones
    invoice = relationship("Invoice", back_populates="accounting_entries")
    sales_invoice = relationship("SalesInvoice", back_populates="accounting_entries")
