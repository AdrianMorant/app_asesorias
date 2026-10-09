import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey, JSON, Text
from sqlalchemy.orm import relationship
from app.core.database import Base

class CompanyIntegration(Base):
    """
    Configuración de integración con software contable externo por empresa.
    Software types soportados: A3, CONTASOL, SAGE, HOLDED_API
    """
    __tablename__ = "company_integrations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    
    software_type = Column(String(50), nullable=False)  # A3, CONTASOL, SAGE, HOLDED_API
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Configuración específica en JSON (código de empresa, diario, rutas locales o tokens API)
    # Ej A3: {"company_code": "00001", "journal_code": "00", "export_path": "C:/A3/SUENLACE"}
    # Ej Contasol: {"journal_code": "1", "subaccount_digits": 9}
    # Ej Sage: {"channel": "0", "sage_company_code": "001"}
    # Ej Holded: {"api_key": "...", "endpoint": "https://api.holded.com/api/invoicing/v1"}
    configuration_json = Column(JSON, nullable=False, default=dict)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relación
    company = relationship("Company", back_populates="integrations")


class ExportBatch(Base):
    """
    Registro histórico de lotes de exportación y sincronizaciones contables generados.
    Permite auditar qué facturas y asientos se enviaron, cuándo y con qué totales.
    """
    __tablename__ = "export_batches"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)

    software_type = Column(String(50), nullable=False)   # A3, CONTASOL, SAGE, HOLDED_API
    file_format = Column(String(50), nullable=False)     # DAT, CSV, JSON_API
    
    entries_count = Column(Integer, default=0, nullable=False)     # Número de apuntes contables
    invoices_count = Column(Integer, default=0, nullable=False)    # Facturas incluidas
    
    total_debe = Column(Float, default=0.0, nullable=False)
    total_haber = Column(Float, default=0.0, nullable=False)
    
    file_name = Column(String(255), nullable=True)                 # Ej: SUENLACE_20261007_01.DAT
    file_path = Column(String(500), nullable=True)                 # Ruta guardada en storage/
    data_fingerprint = Column(String(64), nullable=True)           # Hash SHA-256 para prevenir duplicados accidentales
    fiscal_year = Column(Integer, nullable=True)                   # Ejercicio del lote
    status = Column(String(30), default="EXPORTED_FILE", nullable=False) # EXPORTED_FILE, PENDING_CREDENTIALS, SYNCED_API, FAILED
    log_notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relación
    company = relationship("Company", back_populates="export_batches")
    invoices = relationship("Invoice", back_populates="export_batch")
