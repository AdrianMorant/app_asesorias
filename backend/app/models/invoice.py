import uuid
from datetime import datetime, timezone, date
from sqlalchemy import (
    Column,
    String,
    Float,
    Integer,
    Boolean,
    DateTime,
    Date,
    ForeignKey,
    JSON,
    Text,
)
from sqlalchemy.orm import relationship
from app.core.database import Base

class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    supplier_id = Column(String(36), ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True, index=True)
    
    file_path = Column(String(500), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_hash = Column(String(64), nullable=True, index=True)  # Hash SHA-256 para detección instantánea de duplicados
    
    # Datos fiscales extraídos
    invoice_number = Column(String(100), nullable=False, index=True)
    issue_date = Column(Date, nullable=False, default=date.today)
    due_date = Column(Date, nullable=True)
    fecha_contable = Column(Date, nullable=True)  # Ajustada si el periodo contable está cerrado
    
    issuer_name = Column(String(255), nullable=False)
    issuer_cif = Column(String(20), nullable=False, index=True)
    recipient_name = Column(String(255), nullable=True)
    recipient_cif = Column(String(20), nullable=True)
    
    # Importes
    total_base = Column(Float, nullable=False, default=0.0)
    total_tax = Column(Float, nullable=False, default=0.0)
    total_retention = Column(Float, nullable=False, default=0.0)
    total_amount = Column(Float, nullable=False, default=0.0)
    currency = Column(String(10), default="EUR", nullable=False)
    concept_summary = Column(Text, nullable=True)

    # Casuísticas fiscales (PRD Fase 2)
    # 1. Retención IRPF (Modelo 111 / 190 o 115 / 180)
    has_retention = Column(Boolean, default=False, nullable=False)
    retention_percentage = Column(Float, default=0.0, nullable=False)
    retention_model = Column(String(20), default="111/190", nullable=False)

    # 2. Suplidos (cuenta 554 de provisiones/fondos)
    has_suplidos = Column(Boolean, default=False, nullable=False)
    suplidos_amount = Column(Float, default=0.0, nullable=False)
    suplidos_account = Column(String(30), nullable=True)

    # 3. Factura Rectificativa (minoración de base/cuotas e importes negativos)
    is_rectificativa = Column(Boolean, default=False, nullable=False)
    rectified_invoice_number = Column(String(100), nullable=True)
    rectified_invoice_date = Column(Date, nullable=True)

    # 4. Datos Censales (Modelo 347)
    postal_code = Column(String(20), nullable=True)
    country_code = Column(String(10), default="ES", nullable=False)

    # 5. Detección de Duplicados en tiempo real
    is_duplicate = Column(Boolean, default=False, nullable=False)
    duplicate_of_id = Column(String(36), nullable=True)
    
    # Motor de reglas y semáforo
    status = Column(String(10), nullable=False, default="RED")  # GREEN, YELLOW, RED
    status_reasons = Column(JSON, nullable=False, default=list)  # Lista de motivos
    raw_extraction = Column(JSON, nullable=True)  # JSON original del LLM
    
    # Máquina de estados documental (PRD Fase 1)
    # Estados posibles: 'a_revisar', 'prevalidado', 'validado', 'contabilizado', 'archivado'
    workflow_status = Column(String(30), nullable=False, default="a_revisar", index=True)
    es_multifactura = Column(Boolean, default=False, nullable=False, index=True)
    num_paginas = Column(Integer, default=1, nullable=False)
    parent_invoice_id = Column(String(36), ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Estado de contabilización y exportación
    is_processed = Column(Boolean, default=False, nullable=False)
    exported_to_erp = Column(Boolean, default=False, nullable=False)
    export_batch_id = Column(String(36), ForeignKey("export_batches.id", ondelete="SET NULL"), nullable=True, index=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relaciones
    company = relationship("Company", back_populates="invoices")
    supplier = relationship("Supplier", back_populates="invoices")
    export_batch = relationship("ExportBatch", back_populates="invoices")
    tax_breakdown = relationship("InvoiceTaxBreakdown", back_populates="invoice", cascade="all, delete-orphan")
    accounting_entries = relationship("AccountingEntryLine", back_populates="invoice", cascade="all, delete-orphan")


class InvoiceTaxBreakdown(Base):
    __tablename__ = "invoice_tax_breakdowns"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    invoice_id = Column(String(36), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    
    tax_rate = Column(Float, nullable=False)      # Ej: 21.0, 10.0, 4.0, 0.0
    tax_base = Column(Float, nullable=False)      # Base imponible de ese tramo
    tax_amount = Column(Float, nullable=False)    # Cuota de IVA resultante

    # Relación
    invoice = relationship("Invoice", back_populates="tax_breakdown")
