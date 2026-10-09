# REGISTRO DE INCIDENCIAS TÉCNICAS (KNOWN ISSUES & BUGS)
### Plataforma SaaS Financiero-Contable con IA

Estado de revisión: **Fases 2 y 3 — Auditoría y Cierre de Incidencias**  
Última actualización: Octubre 2026

---

## 1. Clasificación de Severidad

- **Crítica (P0):** Pérdida de datos, eliminación no autorizada, corrupción de estados contables o fallo de seguridad.
- **Alta (P1):** Funcionalidad principal interrumpida (extracción rota, borrado defectuoso, bloqueo de usuario).
- **Media (P2):** Inconsistencias de interfaz, formularios incompletos, catálogos parciales.
- **Baja (P3):** Detalles visuales menores, optimización no bloqueante.

---

## 2. Historial de Incidencias Heredadas (Fases 0 y 1 — Resueltas al 100%)

| Código | Incidencia | Módulo | Estado | Validación |
| :--- | :--- | :--- | :---: | :--- |
| **INC-001** | Persistencia de la barra flotante tras eliminar facturas en tabla. | `InvoiceTable.tsx` / `page.tsx` | 🟢 **RESUELTO** | Selección desacoplada y vaciado automático de `selectedIds`. |
| **INC-002** | Pérdida de documento al fallar proveedor de IA por clave o saldo. | `invoices.py` / `extractor_llm.py` | 🟢 **RESUELTO** | El archivo se preserva en disco y la factura pasa a triaje asistido en estado ROJO. |
| **INC-003** | Catálogo del PGC PYMES incompleto (~40 cuentas). | `pyme_pgc_seed.py` | 🟢 **RESUELTO** | Catálogo ampliado a 80+ cuentas cubriendo íntegramente los Grupos 1 al 7. |
| **INC-004** | Falta de política de resolución de colisiones en archivado. | `archiver.py` | 🟢 **RESUELTO** | Sufijado determinista seguro (`_1.pdf`, `_2.pdf`) sin sobreescritura. |
| **INC-005** | Fallo en siembra contable al ejecutar `test_flow.py`. | `test_flow.py` | 🟢 **RESUELTO** | Siembra automática en inicialización y 100% de escenarios verdes. |

---

## 3. Incidencias Identificadas y Resueltas en Fases 2 y 3

### INC-006 — Restricción `NOT NULL` en columna `invoice_id` de `accounting_entry_lines`
- **Gravedad:** Alta (P1) / Integridad Estructural
- **Módulo afectado:** `backend/app/models/accounting_entry.py` y `backend/app/core/database.py`
- **Comportamiento observado:** Al insertar asientos contables manuales, de regularización de cierre (cuenta 129), de apertura o movimientos de tesorería no vinculados a facturas de gasto, SQLite arrojaba `IntegrityError: NOT NULL constraint failed: accounting_entry_lines.invoice_id`.
- **Causa identificada:** En la base de datos creada en fases preliminares, la tabla `accounting_entry_lines` se generó con `invoice_id VARCHAR(36) NOT NULL`.
- **Solución técnica aplicada:** Se implementó una migración no destructiva en `backend/app/core/database.py:init_db()`. La migración detecta mediante `PRAGMA table_info` si `invoice_id` tiene `notnull=1` y, de ser así, recrea la tabla con `NULLABLE` traspasando el 100% de los datos y reconstruyendo los índices de forma atómica.
- **Resultado:** 🟢 **RESUELTO** (Verificado en `test_phase2_accounting.py`).

### INC-007 — Inyección de instancias `Query(None)` al invocar endpoints internamente
- **Gravedad:** Media (P2)
- **Módulo afectado:** `backend/app/api/v1/endpoints/journal.py` (`get_trial_balance` y `export_trial_balance_csv`)
- **Comportamiento observado:** Al llamar a `get_trial_balance` desde `export_trial_balance_csv`, SQLAlchemy arrojaba `TypeError: SQLite Date type only accepts Python date objects as input`.
- **Causa identificada:** Los argumentos por defecto definidos como `= Query(None)` en FastAPI no son `None` al invocarse como funciones ordinarias de Python, sino instancias del objeto descriptor `Query`. La condición `if from_date:` evaluaba a `True`.
- **Solución técnica aplicada:** Se normalizaron explícitamente los parámetros con `isinstance(val, (date, datetime))` e `isinstance(val, int)` antes de componer las cláusulas SQL `WHERE`.
- **Resultado:** 🟢 **RESUELTO** (Exportación CSV y consulta JSON 100% operativas).

### INC-008 — Truncado de espacios de padding de 96 caracteres en pruebas de Wolters Kluwer A3
- **Gravedad:** Baja (P3) / Rigor de Pruebas
- **Módulo afectado:** `backend/tests/test_phase2_accounting.py`
- **Comportamiento observado:** La aserción `assert len(line) == 96` fallaba con longitud 83 caracteres en la última línea del archivo `SUENLACE.DAT`.
- **Causa identificada:** El script de prueba ejecutaba `dl_res.text.strip().split("\r\n")`, lo que provocaba que el método `.strip()` eliminara los espacios de relleno con los que A3 completa la última línea de 96 caracteres.
- **Solución técnica aplicada:** Se ajustó la prueba para hacer split directo por CRLF (`\r\n`) sin strip previo, preservando la longitud canónica de 96 caracteres.
- **Resultado:** 🟢 **RESUELTO**.

---

## 4. Limitaciones Conocidas y Alcance Actual (Sin Mocks)

1. **Autenticación Multi-Usuario:**
   - *Estado:* La plataforma registra eventos de seguridad en `security_audit.log` y almacena `created_by` en los asientos. Actualmente, si no se recibe un token JWT verificado, el sistema asume `created_by="sistema"` o `"usuario_local"`. No se simulan aprobaciones ficticias de usuarios que no hayan iniciado sesión.
2. **Conectores API Cloud sin Credenciales:**
   - *Estado:* El conector Holded API se muestra con estado `PENDING_CREDENTIALS` hasta que el usuario introduzca su token privado en el panel de integraciones.
3. **Software de Escritorio en Red Local:**
   - *Estado:* Los programas Wolters Kluwer A3, Contasol y Sage instalados en terminales Windows de despacho no disponen de API REST remota nativa. El intercambio se realiza mediante los ficheros normalizados de importación oficial (`SUENLACE.DAT` y CSV). El sistema no afirma que el software externo los haya cargado hasta que el usuario ejecute la importación en su programa de escritorio.
