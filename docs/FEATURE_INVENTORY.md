# INVENTARIO INTEGRAL DE FUNCIONALIDADES (FEATURE INVENTORY)
### Plataforma SaaS de Gestión Empresarial y Copiloto Contable con IA

Estado de revisión: **Fase 2 y Fase 3 — Completadas y Verificadas**  
Última actualización: Octubre 2026

---

## 1. Resumen Ejecutivo del Estado del Sistema

| Módulo / Dominio | Cobertura Funcional | Estado Operativo | Observaciones Técnicas |
| :--- | :---: | :---: | :--- |
| **0. Auditoría y Estabilización** | 100% | 🟢 Operativo | Errores heredados de borrado y fallback ante fallos de IA corregidos al 100%. |
| **1. Multiempresa y Configuración** | 100% | 🟢 Operativo | CRUD de empresas, CIF único normalizado, longitud de plan (8/9/10), bloqueo por fecha de cierre contable. |
| **2. Plan General Contable (PGC PYMES)** | 100% | 🟢 Operativo | Catálogo maestro de 80+ subcuentas oficiales en `pyme_pgc_seed.py` cubriendo íntegramente los Grupos 1 al 7. |
| **3. Extracción Documental e IA (IDP)** | 95% | 🟢 Operativo | Soporte OpenAI / Gemini con fallback robusto a modo asistido ("A Revisar") si la API key es ausente o inválida. Conservación íntegra de archivos. |
| **4. Motor Semafórico y Triaje** | 100% | 🟢 Operativo | Semáforo determinista (Verde, Amarillo, Rojo), validación NIF/CIF, detección de duplicados instantánea por hash SHA-256 (`file_hash`). |
| **5. Borrado Seguro y Lotes** | 100% | 🟢 Operativo | Sincronización desacoplada en `InvoiceTable.tsx`, diálogo de confirmación destructiva y borrado en lote de archivos físicos y registros BD. |
| **6. Archivado Documental Organizado** | 100% | 🟢 Operativo | Árbol fiscal `storage/empresas/{cif}/{year}/{periodo}/recibidas|emitidas/` con política estricta anti-colisiones. |
| **7. Contabilidad General (Fase 2)** | 100% | 🟢 Operativo | **Libro Diario:** filtros por ejercicio, fechas, subcuenta, estado contable y exportación; partida doble cuadrada al céntimo.<br>**Libro Mayor:** extracto progresivo cronológico, naturaleza Deudora/Acreedora y salto interactivo a Diario.<br>**Sumas y Saldos:** agregación oficial por los 7 Grupos PGC (RD 1515/2007) y exportación CSV con BOM UTF-8 para Excel.<br>**Ciclo de Vida:** estados `borrador`, `contabilizado`, `revertido`; contra-asientos invertidos auditables; regularización contra cuenta 129 y cierre de ejercicio bloqueante con reapertura por CIF. |
| **8. Ventas, Compras y Contactos** | 95% | 🟢 Operativo | Facturas recibidas, facturación emitida, clientes, proveedores y correlatividad contable (40000000X / 43000000X). |
| **9. Centro de Integraciones (Fase 3)** | 100% | 🟢 Operativo | **Conectores ERP:** Wolters Kluwer A3 (`SUENLACE.DAT` 96 car. con `A3SeatSplitter`), DELSOL Contasol CSV (Latin-1, delimitador `;`) y Sage 50 / Despachos.<br>**Transparencia:** Estados no simulados (`EXPORTED_FILE`, `PENDING_CREDENTIALS`, `SYNCED_API`).<br>**Idempotencia:** Huella digital criptográfica SHA-256 (`data_fingerprint`), bloqueo de exportaciones repetidas y reexportación forzada justificada (`force_reexport` con motivo auditable). |
| **10. Conciliación Bancaria y Tesorería** | 90% | 🟢 Operativo | Emparejamiento con facturas, deducción semántica (TGSS cuenta 476, suministros cuenta 628), generación de asientos de banco (572). |
| **11. Modelos Tributarios (AEAT)** | 90% | 🟢 Operativo | Modelos 303, 111, 115, 347, 390 con cálculo determinista y auditoría de riesgo fiscal. |
| **12. Seguridad y Auditoría WORM** | 100% | 🟢 Operativo | Registro inmutable de seguridad en `security_audit.log` con encadenamiento SHA-256 (Art. 30/32 RGPD y Ley Antifraude 11/2021). |

---

## 2. Inventario Detallado de Módulos (Fases 2 y 3)

### 2.1. Backend (FastAPI / SQLAlchemy / SQLite Async)
- **`app/api/v1/endpoints/journal.py`**:
  - `GET /{company_id}/journal`: Libro Diario con filtros avanzados, paginación, totales agregados y detección de ejercicios cerrados.
  - `POST /{company_id}/journal/{entry_number}/reverse`: Reversión auditable con generación automática de contra-asiento invertido en partida doble.
  - `POST /{company_id}/journal/close-fiscal-year`: Regularización automática de cuentas de ingresos (grupo 7) y gastos (grupo 6) contra la cuenta 129000000 y fijación de fecha de cierre.
  - `POST /{company_id}/journal/reopen-fiscal-year`: Reapertura segura de ejercicio exigiendo confirmación exacta del CIF.
  - `GET /{company_id}/ledger/{subcuenta}`: Libro Mayor con saldo inicial, movimientos cronológicos, saldo progresivo y naturaleza contable.
  - `GET /{company_id}/trial-balance`: Balance de comprobación agrupado por los 7 grupos oficiales del PGC español.
  - `GET /{company_id}/trial-balance/export-csv`: Descarga directa de archivo CSV formateado con separador `;` y BOM UTF-8 para Excel.
- **`app/api/v1/endpoints/integrations.py`**:
  - `POST /{company_id}/generate-export`: Motor de exportación contable con cálculo de huella digital SHA-256, prevención de lotes duplicados y soporte de reexportación justificada.
  - `GET /batches/{batch_id}/download`: Descarga protegida de ficheros de intercambio contable.
  - `GET /{company_id}/export-batches`: Historial persistente de exportaciones y sincronizaciones.
  - `GET|POST /{company_id}/integrations`: Configuración de parámetros específicos por software contable.
- **`app/services/a3_suenlace.py`**: Motor `A3SeatSplitter` para longitud de 96 caracteres y división de IVA en 2 asientos si hay >3 tipos impositivos.
- **`app/services/contasol_csv.py`**: Generador CSV para Software DELSOL Contasol con cabeceras oficiales, coma decimal y codificación Latin-1/ANSI.
- **`app/services/sage_csv.py`**: Plantilla oficial de asientos para Sage 50 y Despachos Connected.
- **`app/core/database.py`**: Migración no destructiva que permite `invoice_id` nullable en `accounting_entry_lines` para asientos generales y de cierre.

### 2.2. Frontend (Next.js 16 / React 19 / TailwindCSS)
- **`components/JournalView.tsx`**:
  - Barra superior con selector de ejercicio fiscal, filtros por estado contable (`contabilizado`, `revertido`, `borrador`), estado de exportación y buscador reactivo.
  - Tabla del Diario con agrupador de asientos, partida doble cuadrada garantizada (0,00 €) y enlace al documento origen.
  - Modal de Reversión Auditable con requerimiento de motivo formal (mínimo 5 caracteres).
  - Modal de Cierre de Ejercicio con regularización automática contra la cuenta 129.
  - Pestaña de Libro Mayor con selector de subcuenta, saldo progresivo cronológico y botón de salto directo al asiento del Diario.
  - Pestaña de Balance de Sumas y Saldos con tarjetas de los 7 Grupos PGC, validación de cuadre y botón de descarga de Excel/CSV.
- **`components/IntegrationsView.tsx`**:
  - Selector de software contable (A3, Contasol, Sage, Holded API) con campos de configuración técnica específicos.
  - Selector de ejercicio fiscal y selector de ámbito (pendientes vs histórico).
  - Modal interactivo de **Forzar Reexportación Justificada** ante detección de huella digital SHA-256 duplicada.
  - Tabla histórica de lotes con huella criptográfica SHA-256 y estados reales no simulados (`EXPORTED_FILE`, `SYNCED_API`, `PENDING_CREDENTIALS`, `FAILED`).
