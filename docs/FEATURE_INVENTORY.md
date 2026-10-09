# INVENTARIO INTEGRAL DE FUNCIONALIDADES (FEATURE INVENTORY)
### Plataforma SaaS de Gestión Empresarial y Copiloto Contable con IA

Estado de revisión: **Fase 0 — Auditoría Técnica**  
Última actualización: Octubre 2026

---

## 1. Resumen Ejecutivo del Estado del Sistema

| Módulo / Dominio | Cobertura Funcional | Estado Operativo | Observaciones Técnicas |
| :--- | :---: | :---: | :--- |
| **0. Auditoría y Estabilización** | 90% | 🟡 En estabilización | Errores identificados en borrado y extracción con IA desatendida. |
| **1. Multiempresa y Configuración** | 95% | 🟢 Operativo | CRUD de empresas, CIF único, longitud de plan (8/9/10), borrado seguro con confirmación de CIF. |
| **2. Plan General Contable (PGC PYMES)** | 70% | 🟡 Requiere ampliación | Catálogo inicial de 42 cuentas; falta cobertura completa de grupos 1 a 7 (especialmente grupo 3 y amortizaciones). |
| **3. Extracción Documental e IA** | 75% | 🟡 Requiere corrección | Extracción multimodal OpenAI/Gemini implementada, pero elimina archivo si la IA falla y carece de modo asistido con visor. |
| **4. Motor Semafórico y Triaje** | 95% | 🟢 Operativo | Semáforo determinista (Verde, Amarillo, Rojo), detección de duplicados por hash/número, bloqueo contable. |
| **5. Borrado y Gestión de Selección** | 80% | 🔴 Corrección prioritaria | Estado de selección en `InvoiceTable` y sincronización con modal de confirmación requiere desacoplamiento estricto. |
| **6. Archivado Documental** | 85% | 🟡 Requiere robustez | Estructura por empresa/ejercicio/periodo/recibidas; falta política explícita de colisiones de ficheros. |
| **7. Contabilidad (Diario, Mayor, Balances)** | 85% | 🟢 Operativo | Partida doble, libro diario, sumas y saldos, balance de situación y cuenta de pérdidas y ganancias. |
| **8. Ventas, Compras y Contactos** | 90% | 🟢 Operativo | Clientes, proveedores, facturas de ventas, emisión, generación y registro en diario. |
| **9. Integraciones Contables (A3, Contasol, Sage)** | 90% | 🟢 Operativo | `A3SeatSplitter` (SUENLACE.DAT 96 car.), Contasol CSV (Latin-1, ;) y Sage CSV operativos. |
| **10. Conciliación Bancaria y Tesorería** | 85% | 🟢 Operativo | Emparejamiento con facturas, reglas heurísticas TGSS (476) e Iberdrola (628), previsión a 90 días. |
| **11. Modelos Tributarios (AEAT)** | 85% | 🟢 Operativo | Modelos 303, 111, 115, 347, 390 con cálculo determinista y auditoría de riesgo fiscal. |
| **12. Portal de Empleado y Gastos** | 75% | 🟡 Fase posterior | Flujo de tickets y dietas en desarrollo. |
| **13. Copias de Seguridad y Recuperación** | 70% | 🟡 Fase posterior | Exportación GDPR implementada; falta backup integral automatizado con restauración verificada. |

---

## 2. Inventario Detallado por Componentes

### 2.1. Backend (FastAPI / SQLAlchemy / SQLite)
- **`app/api/v1/endpoints/companies.py`**: Gestión completa de empresas. Admite confirmación de CIF en borrado por query o body.
- **`app/api/v1/endpoints/accounts.py`**: Gestión del catálogo contable, árbol PGC, creación de subcuentas y siembra inicial.
- **`app/api/v1/endpoints/invoices.py`**: Ingesta, triaje, aprobación, archivado, split de páginas MF, borrado individual y en lote.
- **`app/api/v1/endpoints/journal.py`**: Consulta del Libro Diario, Mayor y Balance de Sumas y Saldos.
- **`app/api/v1/endpoints/exports.py`**: Descarga de ficheros A3 SUENLACE, Contasol CSV y Sage CSV.
- **`app/api/v1/endpoints/banking.py`**: Cuentas bancarias, transacciones, emparejamiento inteligente y previsiones de tesorería.
- **`app/api/v1/endpoints/taxes.py`**: Cálculo y liquidación de Modelos 303, 111, 115, 347 y auditoría de riesgo fiscal.

### 2.2. Frontend (Next.js 16 / React 19 / TailwindCSS)
- **`components/InvoiceTable.tsx`**: Tabla reactiva con badges semafóricos, búsqueda, filtros y barra de acciones masivas.
- **`components/TriageForm.tsx`**: Consola Split-Screen con visor PDF a la izquierda y formulario fiscal/asiento al panel derecho.
- **`components/DeleteConfirmationModal.tsx`**: Modal de confirmación destructiva para borrado seguro.
- **`components/ArchiveConfirmationModal.tsx`**: Diálogo de vista previa y selección de subcarpeta para archivado.
- **`components/ChartOfAccountsView.tsx`**: Visualizador del Plan General Contable y subcuentas por empresa.
- **`components/BankReconciliationView.tsx`**: Conciliador bancario interactivo con sugerencias inteligentes.
- **`components/TaxDashboardView.tsx`**: Resumen fiscal y alertas tributarias trimestrales.
- **`components/IntegrationsView.tsx`**: Centro de integraciones con Wolters Kluwer A3, Software DELSOL y Sage.

---

## 3. Estado de los Criterios de Aceptación Fase 0
1. **Auditoría Técnica del Repositorio:** Completada.
2. **Diagnóstico de Errores Críticos (A a F):** Documentado en `docs/KNOWN_ISSUES.md`.
3. **Plan de Acción Inmediato:**
   - Corregir sincronización del estado de selección y borrado en `InvoiceTable.tsx` y `page.tsx`.
   - Modificar la ingesta de facturas en backend para conservar el documento y permitir modo asistido si la IA externa falla por falta de API key.
   - Completar el catálogo maestro del PGC PYMES en `pyme_pgc_seed.py` para cubrir todos los grupos (1 a 7).
   - Añadir política anti-colisión en `archiver.py`.
   - Reparar el test unitario `test_flow.py` para asegurar ejecución limpia en local.
