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

### INC-009 — Almacenamiento en memoria volátil de tokens revocados
- **Gravedad:** Alta (P1) / Seguridad de Sesiones
- **Módulo afectado:** `backend/app/core/security.py` y `backend/app/core/auth_deps.py`
- **Comportamiento observado:** Al reiniciar el servidor FastAPI o al ejecutar múltiples instancias uvicorn/gunicorn, los tokens revocados en `/logout` o tras la rotación de `/refresh` volvían a ser válidos porque la lista negra residía únicamente en la memoria RAM del proceso.
- **Solución técnica aplicada:** Se creó el modelo relacional `RevokedToken` en la base de datos con índice en `jti` y fecha de expiración. La clase `TokenRevocationStore` ahora realiza inserciones persistentes y consultas en BD (`is_revoked_persistent`) combinadas con una caché rápida en memoria.
- **Resultado:** 🟢 **RESUELTO** (Verificado en `test_phase6_assets_and_security.py`).

### INC-010 — Posible suplantación de privilegios en cabeceras de desarrollo
- **Gravedad:** Alta (P1) / Control de Acceso RBAC
- **Módulo afectado:** `backend/app/core/auth_deps.py`
- **Comportamiento observado:** La cabecera `X-Dev-User-Role` utilizada para facilitar pruebas unitarias podía permitir a peticiones no autorizadas elevar privilegios si no se restringía estrictamente por entorno.
- **Solución técnica aplicada:** Se blindó `auth_deps.py` de modo que en entornos de producción (`IS_PRODUCTION = True`) las cabeceras de depuración quedan completamente desactivadas. Además, para usuarios existentes en BD, el rol almacenado tiene prevalencia absoluta e inmutable.
- **Resultado:** 🟢 **RESUELTO**.

### INC-011 — Ausencia de bloqueo automático en arranque productivo con claves default
- **Gravedad:** Crítica (P0) / Preparación para Producción
- **Módulo afectado:** `backend/app/core/security.py`
- **Comportamiento observado:** Un despliegue en producción con `SECRET_KEY` de desarrollo o sin HTTPS (`COOKIE_SECURE=false`) podía operar sin advertencias bloqueantes.
- **Solución técnica aplicada:** Se implementó `assert_production_security_readiness()` que valida activamente que la clave no sea un valor por defecto o inseguro y que las cookies seguras sobre HTTPS estén exigidas, abortando la inicialización en caso de incumplimiento.
- **Resultado:** 🟢 **RESUELTO** (Verificado en suite de pruebas).

---

## 4. Inventario de Limitaciones, Requisitos y Riesgos Pendientes

1. **Aislamiento Multi-Tenant:**
   - *Estado:* Totalmente verificado a nivel de endpoints y base de datos relacional. Los usuarios no asignados a una empresa reciben HTTP 403 Forbidden.
2. **Auditoría WORM vs. Almacenamiento Inmutable en la Nube:**
   - *Estado:* La cadena criptográfica SHA-256 en `security_audit.log` detecta con certeza matemática cualquier alteración, adición o borrado retroactivo de registros. Sin embargo, en el sistema de archivos local, un usuario con permisos de administrador del sistema operativo podría técnicamente borrar el archivo completo. Para un entorno enterprise regulado se recomienda montar el volumen en un bucket con política de retención inmutable (ej. AWS S3 Object Lock o Azure Immutable Blob).
3. **Nivel de Validación de Integraciones ERP (A3, Contasol, Sage):**
   - *Nivel 1 (Archivo generado correctamente):* ✅ Sí, verificado en pruebas con codificación CP1252/Latin-1 y longitud canónica.
   - *Nivel 2 (Validado contra especificación oficial):* ✅ Sí, contra la especificación oficial de Wolters Kluwer (SUENLACE 96 car.) y plantillas de DELSOL y Sage.
   - *Nivel 3 (Importado en software real en vivo):* ⚠️ Pendiente de validación manual en los puestos de trabajo finales del despacho por parte del contable usuario.
   - *Nivel 4 (Integración automática vía API cloud confirmada):* Requiere credenciales de producción del cliente final.
4. **Despliegue a Producción:**
   - Se requiere configurar variables de entorno reales (`SECRET_KEY` aleatoria de 64 caracteres, `ENVIRONMENT=production`, `COOKIE_SECURE=true`, certificado SSL/TLS con reverse proxy NGINX/Caddy). No se debe desplegar a producción sin autorización previa expresa.

