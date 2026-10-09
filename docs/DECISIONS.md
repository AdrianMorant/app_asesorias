# REGISTRO DE DECISIONES TÉCNICAS Y PENDIENTES (ARCHITECTURE DECISION RECORDS - ADR)

Este documento recopila las decisiones de diseño adoptadas, el contexto de cada elección y el estado de evolución del sistema.

---

## ADR-001: Modo Asistido ante Falta de Credenciales de IA (Cero Mocks)
- **Contexto:** Si un usuario sube una factura y no hay API Key configurada o la cuota se agota (HTTP 401/429), la aplicación antes fallaba y eliminaba el archivo con `unlink()`.
- **Decisión:** Nunca inventar datos simulados ni descartar el archivo. El documento se preserva íntegro y cifrado en disco, creándose un registro en estado **ROJO** (`workflow_status="a_revisar"`). Se proporciona un botón explícito de «Reintentar IA» y el usuario puede completar los datos manualmente en la vista de triaje.
- **Impacto:** Cumplimiento del principio rector de trazabilidad y fidelidad contable.

---

## ADR-002: Mitigación de MissingGreenlet en SQLAlchemy Asíncrono
- **Contexto:** En SQLAlchemy 2.0 con drivers asíncronos (`aiosqlite`/`asyncpg`), acceder de forma síncrona a relaciones diferidas (como `invoice.tax_breakdown`) dentro de funciones de exportación provocaba la excepción `sqlalchemy.exc.MissingGreenlet`.
- **Decisión:** Aplicar carga explícita mediante `selectinload(Invoice.tax_breakdown)` en las consultas de endpoints y usar acceso defensivo en los transformadores de exportación (`a3_suenlace.py`, `contasol_csv.py`, `sage_csv.py`).
- **Impacto:** Código robusto ante llamadas síncronas o asíncronas sin bloqueos del event loop.

---

## ADR-003: División de Asientos para Wolters Kluwer A3 (`A3SeatSplitter`)
- **Contexto:** La especificación de fichero plano `SUENLACE.DAT` de A3 limita a 3 las bases impositivas por registro contable. Facturas con 4 o más tipos impositivos provocaban truncamiento de datos en el software de la asesoría.
- **Decisión:** Implementar un algoritmo divisor (`A3SeatSplitter`) que particiona facturas multi-tipo en 2 o más asientos correlativos con el mismo concepto y documento de enlace, equilibrando la partida doble en cada bloque.
- **Impacto:** Compatibilidad 100% verificada con todas las versiones de a3asesor Eco y Con.

---

## ADR-004: Política Anti-Colisión en Archivado Documental
- **Contexto:** Si dos facturas tenían el mismo nombre de fichero o fecha/CIF emisor similar, el guardado en disco podía sobrescribir el archivo preexistente con pérdida irrecuperable de información.
- **Decisión:** Implementar desambiguación correlativa (`archivo_1.pdf`, `archivo_2.pdf`) antes de la escritura, verificando la no existencia en el sistema de ficheros de destino.
- **Impacto:** Integridad y conservación legal garantizada sin sobrescrituras accidentales.

---

## ADR-005: Estado de Selección y Borrado en Frontend
- **Contexto:** En la tabla de facturas, existía un estado temporal `locallyDeletedIds` que ocultaba visualmente las facturas antes de que el usuario confirmase en el diálogo modal, provocando que la barra de acciones flotante («Borrar 9 facturas») permaneciera atascada.
- **Decisión:** Eliminar `locallyDeletedIds`. La barra flotante solo evalúa `validSelectedIds.length > 0`. Tras el borrado confirmado en backend, se limpian atómicamente los identificadores seleccionados y se recarga la lista de datos desde la API.
- **Impacto:** Experiencia de usuario limpia, consistente e inmediata sin contadores fantasma.

---

## ADR-006: Inmutabilidad Contable y Reversión por Contra-Asiento Invertido (Fase 2)
- **Contexto:** En contabilidad mercantil y tributaria española (Código de Comercio y PGC), los asientos contables registrados y aprobados no pueden eliminarse arbitrariamente de la base de datos mediante sentencias `DELETE`.
- **Decisión:** Prohibir el borrado de asientos contabilizados. Para corregir errores se implementó el mecanismo auditable de **Reversión Contable**:
  1. El asiento original pasa permanentemente a estado `revertido`.
  2. El sistema genera de forma atómica un nuevo asiento (contra-asiento) con número correlativo libre en el que se invierten exactamente las cuentas del Debe y del Haber.
  3. Se registra el motivo obligatorio en la bitácora criptográfica WORM de auditoría (`security_audit.log`).
- **Impacto:** Conformidad con la normativa mercantil española y trazabilidad inalterable de auditoría.

---

## ADR-007: Cierre de Ejercicio con Regularización contra Cuenta 129 y Bloqueo de Periodos (Fase 2)
- **Contexto:** Al finalizar el año fiscal, los saldos de compras/gastos (Grupo 6) e ingresos/ventas (Grupo 7) deben quedar saldados contra el resultado del ejercicio, e impedirse nuevas contabilizaciones extemporáneas en fechas anteriores.
- **Decisión:**
  1. Se calcula el saldo neto de todas las subcuentas de los Grupos 6 y 7 del año.
  2. Se genera el asiento de regularización saldando cada cuenta contra la cuenta oficial `129000000` (Resultado del Ejercicio: beneficio al Haber o pérdidas al Debe).
  3. Se actualiza la `fecha_cierre_contable` en la empresa.
  4. Los endpoints de contabilización y reversión bloquean cualquier operación con fecha anterior o igual a la fecha de cierre con `HTTP 400 Bad Request`.
  5. La reapertura exige introducir el CIF exacto de la empresa para evitar reaperturas accidentales.
- **Impacto:** Integridad contable blindada ante manipulaciones retroactivas.

---

## ADR-008: Huella Criptográfica SHA-256 e Idempotencia en Exportaciones Contables (Fase 3)
- **Contexto:** La exportación repetida inadvertida de las mismas facturas hacia programas de contabilidad provoca duplicidad de apuntes en el diario de la asesoría.
- **Decisión:** En cada generación de lote, se computa una huella digital SHA-256 (`data_fingerprint`) representativa del conjunto ordenado de IDs de factura y sus importes. Si el sistema detecta un lote previo con idéntica huella para el mismo software de destino, bloquea la petición con `HTTP 400`. Si el usuario requiere reexportar por un motivo justificado (pérdida de fichero local), debe proporcionar `force_reexport=True` y un motivo auditable.
- **Impacto:** Prevención absoluta de duplicados sin restar flexibilidad operativa.

---

## ADR-009: Estados Reales no Simulados en Integraciones (Fase 3)
- **Contexto:** Muchos ERPs muestran etiquetas engañosas como "Sincronizado" para software de escritorio instalado en local que el sistema no puede inspeccionar directamente.
- **Decisión:** Distinguir con rigor:
  - `EXPORTED_FILE`: El archivo plano o CSV ha sido generado y descargado; pendiente de importación en destino.
  - `SYNCED_API`: Sincronización verificada por endpoint REST oficial.
  - `PENDING_CREDENTIALS`: Conector activo pero sin credenciales configuradas.
- **Impacto:** Honestidad técnica y transparencia hacia el profesional contable.
