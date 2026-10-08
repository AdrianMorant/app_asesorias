from fastapi import APIRouter
from app.api.v1.endpoints import (
    invoices,
    companies,
    suppliers,
    exports,
    accounts,
    integrations,
    contacts,
    sales,
    taxes,
    journal,
    banking,
)

api_router = APIRouter()

api_router.include_router(invoices.router, prefix="/invoices", tags=["Facturas Recibidas / Gastos"])
api_router.include_router(companies.router, prefix="/companies", tags=["Empresas"])
api_router.include_router(suppliers.router, prefix="/suppliers", tags=["Proveedores"])
api_router.include_router(exports.router, prefix="/exports", tags=["Exportación Contable Legacy"])
api_router.include_router(accounts.router, prefix="/companies", tags=["Plan Contable PYME"])

# Nuevos submódulos de la suite integral
api_router.include_router(integrations.router, prefix="/companies", tags=["Centro de Enlace Contable & ERP"])
api_router.include_router(contacts.router, prefix="/companies", tags=["Contactos CRM Contable"])
api_router.include_router(sales.router, prefix="/companies", tags=["Ventas y Facturación Emitida"])
api_router.include_router(taxes.router, prefix="/companies", tags=["Impuestos y Modelos Tributarios"])
api_router.include_router(journal.router, prefix="/companies", tags=["Libro Diario, Mayor y Sumas y Saldos"])
api_router.include_router(banking.router, prefix="/companies", tags=["Conciliación Bancaria Inteligente"])

