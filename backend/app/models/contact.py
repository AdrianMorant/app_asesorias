import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.core.database import Base

class Contact(Base):
    """
    Directorio CRM unificado de Clientes (430) y Proveedores/Acreedores (400/410).
    """
    __tablename__ = "contacts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    
    contact_type = Column(String(20), default="CLIENT", nullable=False)  # CLIENT, SUPPLIER, CREDITOR
    cif = Column(String(20), nullable=False, index=True)
    razon_social = Column(String(255), nullable=False)
    nombre_comercial = Column(String(255), nullable=True)
    
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    address = Column(String(255), nullable=True)
    postal_code = Column(String(20), nullable=True)
    city = Column(String(100), nullable=True)
    
    # Subcuenta PGC asociada por defecto (ej: 430000001, 400000001)
    subcuenta_default = Column(String(20), nullable=True)
    
    # Condiciones comerciales
    payment_method = Column(String(50), default="Transferencia", nullable=False)  # Transferencia, Domiciliación, Recibo, Efectivo, Tarjeta
    iban = Column(String(34), nullable=True)
    payment_terms_days = Column(String(20), default="Contado", nullable=True)     # Contado, 30 días, 60 días
    
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relaciones
    company = relationship("Company", back_populates="contacts")
    sales_invoices = relationship("SalesInvoice", back_populates="contact")
