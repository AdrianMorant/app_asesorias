# INVENTARIO INTEGRAL DE FUNCIONALIDADES (FEATURE INVENTORY)
### Plataforma SaaS de Gestión Empresarial y Copiloto Contable con IA

Estado de revisión: **Fase 4 (Seguridad Empresarial & RBAC) y Fase 5 (Fiabilidad y Operaciones) — Completadas y Verificadas**  
Última actualización: Octubre 2026

---

## 1. Resumen Ejecutivo del Estado del Sistema

| Módulo / Dominio | Cobertura Funcional | Estado Operativo | Observaciones Técnicas |
| :--- | :---: | :---: | :--- |
| **0. Auditoría y Estabilización** | 100% | 🟢 Operativo | Errores heredados de borrado y fallback ante fallos de IA corregidos al 100%. |
| **1. Multiempresa y Configuración** | 100% | 🟢 Operativo | CRUD de empresas, CIF único normalizado, longitud de plan (8/9/10), bloqueo por fecha de cierre contable. |
| **2. Plan General Contable (PGC PYMES)** | 100% | 🟢 Operativo | Catálogo maestro de 80+ subcuentas oficiales en `pyme_pgc_seed.py` cubriendo íntegramente los Grupos 1 al 7. |
| **3. Extracción Documental e IA (IDP)** | 95% | 🟢 Operativo | Conectado con OpenAI `gpt-4o-mini` y fallback a modo asistido ("A Revisar") si la API key es ausente o inválida. Conservación íntegra de archivos. |
| **4. Motor Semafórico y Triaje** | 100% | 🟢 Operativo | Semáforo determinista (Verde, Amarillo, Rojo), validación NIF/CIF, detección de duplicados instantánea por hash SHA-256 (`file_hash`). |
| **5. Borrado Seguro y Lotes** | 100% | 🟢 Operativo | Sincronización desacoplada en `InvoiceTable.tsx`, diálogo de confirmación destructiva y borrado en lote protegido por RBAC. |
| **6. Archivado Documental Organizado** | 100% | 🟢 Operativo | Árbol fiscal `storage/empresas/{cif}/{year}/{periodo}/recibidas|emitidas/` con política estricta anti-colisiones. |
| **7. Contabilidad General (Fase 2)** | 100% | 🟢 Operativo | **Libro Diario:** filtros por ejercicio, fechas, subcuenta, estado contable y exportación; partida doble cuadrada al céntimo.<br>**Libro Mayor:** extracto progresivo cronológico, naturaleza Deudora/Acreedora y salto interactivo a Diario.<br>**Sumas y Saldos:** agregación oficial por los 7 Grupos PGC (RD 1515/2007) y exportación CSV con BOM UTF-8 para Excel.<br>**Ciclo de Vida:** estados `borrador`, `contabilizado`, `revertido`; contra-asientos invertidos auditables; regularización contra cuenta 129 y cierre de ejercicio bloqueante con reapertura por CIF. |
| **8. Ventas, Compras y Contactos** | 95% | 🟢 Operativo | Facturas recibidas, facturación emitida, clientes, proveedores y correlatividad contable (40000000X / 43000000X). |
| **9. Centro de Integraciones (Fase 3)** | 100% | 🟢 Operativo | **Conectores ERP:** Wolters Kluwer A3 (`SUENLACE.DAT` 96 car. con `A3SeatSplitter`), DELSOL Contasol CSV (Latin-1, delimitador `;`) y Sage 50 / Despachos.<br>**Transparencia:** Estados no simulados (`EXPORTED_FILE`, `PENDING_CREDENTIALS`, `SYNCED_API`).<br>**Idempotencia:** Huella digital criptográfica SHA-256 (`data_fingerprint`), bloqueo de exportaciones repetidas y reexportación forzada justificada (`force_reexport` con motivo auditable y RBAC). |
| **10. Autenticación y RBAC (Fase 4)** | 100% | 🟢 Operativo | Hasheo PBKDF2-HMAC-SHA256 (310.000 iteraciones), JWT (HS256) con expiración y rotación, lista negra de tokens revocados (JTI), rate limiting contra ataques de fuerza bruta (HTTP 429), flujo de recuperación de contraseñas verificable, 2FA/TOTP configurable y matriz RBAC estricta en backend. |
| **11. Fiabilidad y Operaciones (Fase 5)** | 100% | 🟢 Operativo | Copias de seguridad ZIP atómicas con manifest SHA-256 (`create_system_backup`), verificación de integridad matemática (`verify_backup_integrity`), ensayo de restauración verificado con `PRAGMA quick_check` y sondas de salud `/health` y `/health/detailed`. |
| **12. Conciliación Bancaria y Tesorería** | 90% | 🟢 Operativo | Emparejamiento con facturas, deducción semántica (TGSS cuenta 476, suministros cuenta 628), generación de asientos de banco (572). |
| **13. Modelos Tributarios (AEAT)** | 90% | 🟢 Operativo | Modelos 303, 111, 115, 347, 390 con cálculo determinista y auditoría de riesgo fiscal. |
| **14. Auditoría Inmutable WORM** | 100% | 🟢 Operativo | Registro inmutable de seguridad en `security_audit.log` con encadenamiento SHA-256 (Art. 30/32 RGPD y Ley Antifraude 11/2021) y endpoint de diagnóstico `/api/v1/auth/audit/verify`. |
| **15. Inmovilizado y Amortizaciones (Fase 6)** | 100% | 🟢 Operativo | **Fichas de Activo Fijo:** Grupos 20 y 21 PGC, cálculo plurianual con prorrateo por días exactos y cuadre decimal.<br>**Contabilización de Dotaciones:** Asientos automáticos 681/281 y 680/280 en partida doble con bloqueo por ejercicio cerrado e idempotencia.<br>**Bajas y Enajenaciones:** Asiento auditable con cuentas 281, 572, 21x y resultado del ejercicio (671 pérdidas / 771 beneficios).<br>**Seguridad Persistente:** Tabla `revoked_tokens` compartida entre workers, validación de producción con `assert_production_security_readiness()` y blindaje multi-tenant. |

---

## 2. Inventario Detallado de Seguridad y Fiabilidad (Fases 4 y 5)

### 2.1. Backend (FastAPI / Criptografía / Seguridad)
- **`app/core/security.py`**:
  - Hashing PBKDF2-HMAC-SHA256 con 310.000 iteraciones y salt aleatorio de 16 bytes.
  - Validación de complejidad de contraseñas (mínimo 8 caracteres, mayúscula, minúscula, dígito o símbolo).
  - Tokens temporales de recuperación de contraseñas con expiración estricta (15 min).
  - Almacén en memoria thread-safe de tokens revocados (`TokenRevocationStore`).
- **`app/core/auth_deps.py`**:
  - `get_current_user`: Extracción y validación de tokens desde Cookies HttpOnly seguras o cabecera `Authorization: Bearer`.
  - `require_roles`: Restricción estricta de ejecución según jerarquía de roles RBAC.
  - `require_company_permission`: Aislamiento multi-tenant para impedir accesos cruzados entre empresas.
- **`app/api/v1/endpoints/auth.py`**:
  - `POST /register`: Registro de usuario con hash resistente y validación de duplicados.
  - `POST /login`: Inicio de sesión protegido con rate limit, soporte 2FA y cookies HttpOnly SameSite=Strict.
  - `POST /logout`: Cierre de sesión y revocación activa de tokens en lista negra.
  - `POST /refresh`: Rotación y refresco seguro de tokens.
  - `GET /me`: Consulta del perfil y vinculaciones multi-empresa.
  - `POST /forgot-password` & `POST /reset-password`: Flujo seguro y verificable de restablecimiento de contraseña.
  - `GET /audit/verify`: Verificación criptográfica de la integridad de la cadena WORM SHA-256.
- **`app/services/backup_service.py` & `app/api/v1/endpoints/operations.py`**:
  - Generación de copias de seguridad consistentes con la SQLite Backup API.
  - Empaquetado ZIP de base de datos, documentos y logs de auditoría con manifiesto SHA-256.
  - Verificación matemática previa a la extracción.
  - Ensayo de restauración con validación `PRAGMA quick_check;`.
- **`app/main.py`**:
  - Sondas `/health` y `/health/detailed` reportando estado de BD, sistema de archivos y logs.
  - Manejador global `RateLimitExceeded` devolviendo HTTP 429 con cabecera `Retry-After`.

### 2.2. Frontend (Next.js / TypeScript)
- **`components/SecuritySettingsModal.tsx`**:
  - Selector interactivo de simulación de roles para comprobar el bloqueo RBAC en tiempo real.
  - Matriz visual de permisos backend.
  - Panel de verificación matemática de la cadena WORM SHA-256.
  - Panel de generación y estado de copias de seguridad.
  - Monitor de salud de componentes en tiempo real.

---

## 3. Estado de la Hoja de Ruta y Funcionalidades Pendientes (Fase 6)

| Funcionalidad | Estado Real | Dependencias Reales Pendientes |
| :--- | :---: | :--- |
| **Conciliación Bancaria Automática** | Implementada (Fase 2) | Funciona con subida de ficheros Norma 43 y CSV. Pendiente: Conexión API PSD2 (exige homologación bancaria o proveedor como Tink/Nordigen). |
| **Facturación Electrónica (Facturae / Veri*Factu)** | Parcial | Generador XML Facturae 3.2.2 y hash encadenado VeriFactu implementados. Pendiente: Envío real al web service AEAT (requiere certificado digital homologado). |
| **Portal del Empleado / Gastos Ticket** | Parcial | Subida y triaje de tickets operativos. Pendiente: Flujo de aprobación por responsable y portal de empleado dedicado. |
| **Inmovilizado y Amortizaciones** | Pendiente | Diseñada la lógica en el PGC (Grupos 2 y 68). Pendiente: Módulo de cuadros de amortización fiscal y asientos automáticos de fin de año. |
| **Integraciones E-Commerce (Shopify, WooCommerce)** | Pendiente | Requiere credenciales OAuth o API keys de cada plataforma e-commerce cliente. |
| **API Pública y Webhooks Outbound** | Parcial | Webhooks inbound de email (SendGrid/Postmark) operativos. Pendiente: Generación de API Keys de cliente y webhooks salientes. |
| **Copiloto Financiero Multimodal** | Operativo con OpenAI | Integrado con `gpt-4o-mini` para consultas y chat financiero autorizado sobre datos reales de la empresa. |
