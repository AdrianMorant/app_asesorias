import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    cif = Column(String(20), nullable=False, index=True)
    nombre = Column(String(255), nullable=False)
    subcuenta_proveedor = Column(String(20), nullable=False)  # Ej. 400000001
    subcuenta_gasto_defecto = Column(String(20), nullable=False)  # Ej. 629000001
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relaciones
    company = relationship("Company", back_populates="suppliers")
    invoices = relationship("Invoice", back_populates="supplier")
