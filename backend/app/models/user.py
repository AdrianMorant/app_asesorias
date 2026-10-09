"""Modelo de Usuarios, Autenticación y Control de Acceso Basado en Roles (RBAC).

Soporta jerarquía multi-inquilino (Multi-Tenant) para Gestorías y Asesorías Contables,
permitiendo vinculación N:M entre asesores profesionales y sus múltiples empresas clientes.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import (
    Column,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Table,
    Enum as SQLEnum,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class UserRole(str, enum.Enum):
    """Roles granulares estandarizados según política de seguridad y segregación de funciones."""
    SUPERADMIN = "SUPERADMIN"              # Control global de la plataforma e infraestructura
    ADVISOR = "ADVISOR"                    # Gestor contable/fiscal con acceso y conmutación entre empresas asignadas
    COMPANY_ADMIN = "COMPANY_ADMIN"        # Administrador de una empresa cliente específica
    ACCOUNTANT = "ACCOUNTANT"              # Contable con permisos de edición de asientos y facturas
    INVOICING = "INVOICING"                # Solo emisión y consulta de facturación de ventas
    AUDITOR_READONLY = "AUDITOR_READONLY"  # Acceso exclusivamente de lectura e inspección


# Tabla intermedia de vinculación N:M entre Usuarios/Asesores y Empresas Clientes
user_companies = Table(
    "user_companies",
    Base.metadata,
    Column("user_id", String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("company_id", String(36), ForeignKey("companies.id", ondelete="CASCADE"), primary_key=True),
    Column("role", String(50), default=UserRole.ACCOUNTANT.value, nullable=False),
    Column("created_at", DateTime, default=lambda: datetime.now(timezone.utc), nullable=False),
)


class User(Base):
    """Entidad de Usuario con soporte multi-empresa y autenticación."""
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=True)
    global_role = Column(String(50), default=UserRole.ADVISOR.value, nullable=False)
    advisor_firm_name = Column(String(255), nullable=True)  # Nombre de la Gestoría / Despacho
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relación N:M con empresas
    companies = relationship(
        "Company",
        secondary=user_companies,
        back_populates="users",
        lazy="selectin",
    )
