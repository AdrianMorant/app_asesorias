import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.core.database import Base

class Account(Base):
    """
    Subcuenta del Plan Contable PYME perteneciente a una empresa.
    Tipos de cuenta:
    - GASTO: Grupo 6 (600 - 699)
    - INGRESO: Grupo 7 (700 - 799)
    - PROVEEDOR: Grupo 400 (4000 - 4009)
    - ACREEDOR: Grupo 410 (4100 - 4109)
    - CLIENTE: Grupo 430/440 (4300 - 4409)
    - FINANCIERO: Grupo 57, 52, etc.
    - OTRO: Otras cuentas de balance o regularización
    """
    __tablename__ = "accounts"
    __table_args__ = (
        UniqueConstraint("company_id", "codigo", name="uix_company_account_code"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    
    codigo = Column(String(20), nullable=False, index=True)
    descripcion = Column(String(255), nullable=False)
    tipo = Column(String(50), nullable=False, default="OTRO")
    cif_asociado = Column(String(20), nullable=True, index=True)
    
    debe_inicial = Column(Float, default=0.0, nullable=False)
    haber_inicial = Column(Float, default=0.0, nullable=False)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relación
    company = relationship("Company", back_populates="accounts")
