import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, Date
from sqlalchemy.orm import relationship
from app.core.database import Base

class Company(Base):
    __tablename__ = "companies"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    cif = Column(String(20), unique=True, index=True, nullable=False)
    razon_social = Column(String(255), nullable=False)
    plan_cuentas_longitud = Column(Integer, default=9, nullable=False)  # 8, 9 o 10 dígitos
    storage_base_path = Column(String(500), default="storage", nullable=False)  # Ruta base personalizada de archivado
    iva_periodicity = Column(String(20), default="Trimestral", nullable=False)  # Trimestral, Mensual, Anual
    fecha_cierre_contable = Column(Date, nullable=True)  # Fecha del último cierre contable
    subcuenta_suplidos_defecto = Column(String(30), nullable=True)  # Cuenta 554 para suplidos
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relaciones en cascada
    suppliers = relationship("Supplier", back_populates="company", cascade="all, delete-orphan")
    invoices = relationship("Invoice", back_populates="company", cascade="all, delete-orphan")
    accounts = relationship("Account", back_populates="company", cascade="all, delete-orphan")
    integrations = relationship("CompanyIntegration", back_populates="company", cascade="all, delete-orphan")
    export_batches = relationship("ExportBatch", back_populates="company", cascade="all, delete-orphan")
    contacts = relationship("Contact", back_populates="company", cascade="all, delete-orphan")
    sales_invoices = relationship("SalesInvoice", back_populates="company", cascade="all, delete-orphan")
