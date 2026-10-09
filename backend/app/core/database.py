from typing import AsyncGenerator
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base
from app.core.config import settings

# Engine asíncrono para SQLite/PostgreSQL
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)

# Fabrica de sesiones asíncronas
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)

Base = declarative_base()

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Inyector de dependencias para FastAPI."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def init_db() -> None:
    """Crea las tablas en la base de datos si no existen y aplica migraciones ligeras."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
        # Migración ligera para añadir columnas en SQLite si las tablas ya existían
        try:
            await conn.execute(text("ALTER TABLE companies ADD COLUMN storage_base_path VARCHAR(500) DEFAULT 'storage'"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE companies ADD COLUMN iva_periodicity VARCHAR(20) DEFAULT 'Trimestral'"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE companies ADD COLUMN modalidad_uso VARCHAR(30) DEFAULT 'copiloto_contable'"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE companies ADD COLUMN regimen_tributario VARCHAR(50) DEFAULT 'general'"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE companies ADD COLUMN software_destino VARCHAR(50) DEFAULT 'a3'"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE companies ADD COLUMN domicilio_fiscal VARCHAR(255)"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE companies ADD COLUMN email_contacto VARCHAR(100)"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE companies ADD COLUMN telefono_contacto VARCHAR(30)"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE companies ADD COLUMN is_active BOOLEAN DEFAULT 1"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE accounts ADD COLUMN debe_inicial FLOAT DEFAULT 0.0"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE accounts ADD COLUMN haber_inicial FLOAT DEFAULT 0.0"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE invoices ADD COLUMN exported_to_erp BOOLEAN DEFAULT 0"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE invoices ADD COLUMN export_batch_id VARCHAR(36)"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE invoices ADD COLUMN workflow_status VARCHAR(30) DEFAULT 'a_revisar'"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE invoices ADD COLUMN es_multifactura BOOLEAN DEFAULT 0"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE invoices ADD COLUMN num_paginas INTEGER DEFAULT 1"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE invoices ADD COLUMN parent_invoice_id VARCHAR(36)"))
        except Exception:
            pass
        # Columnas PRD Fase 2
        try:
            await conn.execute(text("ALTER TABLE companies ADD COLUMN fecha_cierre_contable DATE"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE companies ADD COLUMN subcuenta_suplidos_defecto VARCHAR(30)"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE invoices ADD COLUMN file_hash VARCHAR(64)"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE invoices ADD COLUMN fecha_contable DATE"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE invoices ADD COLUMN is_rectificativa BOOLEAN DEFAULT 0"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE invoices ADD COLUMN rectified_invoice_number VARCHAR(100)"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE invoices ADD COLUMN rectified_invoice_date DATE"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE invoices ADD COLUMN has_retention BOOLEAN DEFAULT 0"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE invoices ADD COLUMN retention_percentage FLOAT DEFAULT 0.0"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE invoices ADD COLUMN retention_model VARCHAR(20) DEFAULT '111/190'"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE invoices ADD COLUMN has_suplidos BOOLEAN DEFAULT 0"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE invoices ADD COLUMN suplidos_amount FLOAT DEFAULT 0.0"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE invoices ADD COLUMN suplidos_account VARCHAR(30)"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE invoices ADD COLUMN postal_code VARCHAR(20)"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE invoices ADD COLUMN country_code VARCHAR(10) DEFAULT 'ES'"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE invoices ADD COLUMN is_duplicate BOOLEAN DEFAULT 0"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE invoices ADD COLUMN duplicate_of_id VARCHAR(36)"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE accounting_entry_lines ADD COLUMN exported_to_erp BOOLEAN DEFAULT 0"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE accounting_entry_lines ADD COLUMN export_batch_id VARCHAR(36)"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE accounting_entry_lines ADD COLUMN sales_invoice_id VARCHAR(36)"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE accounting_entry_lines ADD COLUMN company_id VARCHAR(36)"))
        except Exception:
            pass

    # Precargar el Plan General Contable PYME en empresas existentes
    async with AsyncSessionLocal() as session:
        try:
            from app.models.company import Company
            from app.services.pyme_pgc_seed import seed_company_chart_of_accounts
            res = await session.execute(select(Company))
            companies = res.scalars().all()
            for comp in companies:
                await seed_company_chart_of_accounts(session, comp.id, comp.plan_cuentas_longitud)
        except Exception:
            pass
