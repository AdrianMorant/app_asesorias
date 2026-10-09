"""
Modelo de Activos Fijos e Inmovilizado (PGC RD 1514/2007 y RD 1515/2007 PYMES).

Soporta el ciclo de vida contable completo de los activos materiales e intangibles:
1. Adquisición y ficha de inventario con cuentas asociadas del PGC (Grupos 20, 21, 28 y 68).
2. Cuadros de amortización plurianuales calculados por métodos reglamentarios con prorrateo temporal.
3. Contabilización periódica de dotaciones mediante apuntes correlativos en partida doble.
4. Bajas por obsolescencia y enajenaciones/ventas con cálculo automático del resultado contable (Cuentas 671 / 771).
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime, timezone
from typing import List, Optional

from sqlalchemy import (
    Column,
    String,
    Float,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Text,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class AssetCategory(str, enum.Enum):
    """Categorías estándar del Inmovilizado según el Cuadro de Cuentas PGC."""
    TERRENOS = "TERRENOS"                                  # Grupo 210 (No amortizable)
    CONSTRUCCIONES = "CONSTRUCCIONES"                      # Grupo 211
    INSTALACIONES_TECNICAS = "INSTALACIONES_TECNICAS"      # Grupo 212
    MAQUINARIA = "MAQUINARIA"                              # Grupo 213
    UTILLAJE = "UTILLAJE"                                  # Grupo 214
    MOBILIARIO = "MOBILIARIO"                              # Grupo 216
    EQUIPOS_INFORMATICOS = "EQUIPOS_INFORMATICOS"          # Grupo 217
    ELEMENTOS_TRANSPORTE = "ELEMENTOS_TRANSPORTE"          # Grupo 218
    APLICACIONES_INFORMATICAS = "APLICACIONES_INFORMATICAS"# Grupo 206
    OTRO_INMOVILIZADO = "OTRO_INMOVILIZADO"                # Grupo 219


class DepreciationMethod(str, enum.Enum):
    """Métodos de amortización soportados."""
    LINEAL = "LINEAL"                                      # Cuota constante proporcional
    DIGITOS_DECRECIENTE = "DIGITOS_DECRECIENTE"            # Suma de dígitos decreciente
    PORCENTAJE_CONSTANTE = "PORCENTAJE_CONSTANTE"          # Porcentaje constante sobre valor pendiente


class AssetStatus(str, enum.Enum):
    """Estados del ciclo de vida del activo fijo."""
    ACTIVO = "ACTIVO"                                      # En explotación y amortizándose
    TOTALMENTE_AMORTIZADO = "TOTALMENTE_AMORTIZADO"        # Valor neto contable residual alcanzado
    BAJA = "BAJA"                                          # Retirado por siniestro/obsolescencia
    VENDIDO = "VENDIDO"                                    # Enajenado a terceros


class Asset(Base):
    """Entidad principal de Activo Fijo / Inmovilizado."""
    __tablename__ = "assets"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    
    code = Column(String(50), nullable=False, index=True)  # Código identificativo (ej. "ACT-2026-001")
    name = Column(String(255), nullable=False)             # Descripción (ej. "Portátil MacBook Pro M3 Contabilidad")
    category = Column(String(50), default=AssetCategory.EQUIPOS_INFORMATICOS.value, nullable=False)
    
    acquisition_date = Column(Date, nullable=False)
    acquisition_cost = Column(Float, nullable=False)
    residual_value = Column(Float, default=0.0, nullable=False)
    
    depreciation_start_date = Column(Date, nullable=False)
    useful_life_years = Column(Float, nullable=False)      # Años de vida útil estimada (ej. 4.0)
    depreciation_method = Column(String(50), default=DepreciationMethod.LINEAL.value, nullable=False)
    
    # Cuentas contables asignadas (PGC)
    account_asset = Column(String(50), nullable=False)                     # ej. "217000000"
    account_accumulated_depreciation = Column(String(50), nullable=False)  # ej. "281700000"
    account_depreciation_expense = Column(String(50), default="681000000", nullable=False) # ej. "681000000"

    # Enlaces de origen opcionales
    supplier_id = Column(String(36), ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True)
    invoice_id = Column(String(36), ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True)
    
    # Saldos acumulados
    accumulated_depreciation = Column(Float, default=0.0, nullable=False)
    net_book_value = Column(Float, nullable=False)
    status = Column(String(50), default=AssetStatus.ACTIVO.value, nullable=False)
    
    # Datos de desinversión / baja / venta
    disposal_date = Column(Date, nullable=True)
    disposal_amount = Column(Float, nullable=True)
    disposal_reason = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relaciones
    company = relationship("Company", backref="assets")
    supplier = relationship("Supplier", foreign_keys=[supplier_id])
    invoice = relationship("Invoice", foreign_keys=[invoice_id])
    schedules = relationship(
        "AssetDepreciationSchedule",
        back_populates="asset",
        cascade="all, delete-orphan",
        order_by="AssetDepreciationSchedule.fiscal_year",
        lazy="selectin",
    )


class AssetDepreciationSchedule(Base):
    """Periodo anual o fraccionado del calendario de amortización."""
    __tablename__ = "asset_depreciation_schedules"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    asset_id = Column(String(36), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    
    fiscal_year = Column(Integer, nullable=False)          # Ejercicio fiscal (ej. 2026)
    period_name = Column(String(50), nullable=False)       # ej. "Ejercicio 2026"
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    
    depreciation_amount = Column(Float, nullable=False)    # Dotación del periodo
    accumulated_depreciation = Column(Float, nullable=False)
    net_book_value = Column(Float, nullable=False)
    
    is_posted = Column(Boolean, default=False, nullable=False)
    accounting_entry_number = Column(Integer, nullable=True)
    posted_at = Column(DateTime, nullable=True)

    # Relación bidireccional
    asset = relationship("Asset", back_populates="schedules")
