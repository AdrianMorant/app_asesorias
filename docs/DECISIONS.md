# REGISTRO DE DECISIONES TÉCNICAS Y PENDIENTES (ARCHITECTURE DECISION RECORDS - ADR)

Este documento recopila las decisiones de diseño adoptadas, el contexto de cada elección y el estado de evolución hacia las siguientes fases.

---

## ADR-001: Modo Asistido ante Falta de Credenciales de IA (Cero Mocks)
- **Contexto:** Si un usuario sube una factura y no hay API Key configurada o la cuota se agota (HTTP 401/429), la aplicación antes fallaba y eliminaba el archivo con `unlink()`, o existía la tentación de inventar datos simulados.
- **Decisión:** Nunca inventar datos simulados en producción ni descartar el archivo. El documento se preserva íntegro y cifrado en disco, creándose un registro en estado **ROJO** (`workflow_status="a_revisar"`). Se proporciona un botón explícito de «Reintentar IA» y el usuario puede completar los datos manualmente en la vista de triaje.
- **Impacto:** Cumplimiento del principio rector de trazabilidad y fidelidad contable.

---

## ADR-002: Mitigación de MissingGreenlet en SQLAlchemy Asíncrono
- **Contexto:** En SQLAlchemy 2.0 con drivers asíncronos (`aiosqlite`/`asyncpg`), acceder de forma síncrona a relaciones diferidas (como `invoice.tax_breakdown`) dentro de funciones puras de exportación provocaba la excepción `sqlalchemy.exc.MissingGreenlet`.
- **Decisión:** Aplicar carga explícita mediante `selectinload(Invoice.tax_breakdown)` en las consultas de endpoints y usar acceso defensivo (`getattr(inv, "__dict__", {}).get("tax_breakdown", [])`) en los transformadores de exportación (`a3_suenlace.py`, `contasol_csv.py`, `sage_csv.py`).
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

## Hoja de Ruta Pendiente (Fases 1 a 7)
- **Fase 1 (Fundamentos Empresariales):** Refinamiento de modelos relacionales, aislamiento multiempresa por cabecera de sesión, interfaz web dedicada para gestión del Plan Contable y control RBAC.
- **Fase 2 (Documentos y Contabilidad):** Motor semafórico avanzado, Libro Diario interactivo en frontend, Libro Mayor y Balance de Sumas y Saldos persistido.
- **Fase 3 (Centro de Integraciones):** Panel de configuración de adaptadores ERP por empresa en UI con selector de versión y carpetas locales.
- **Fase 4 (Fiscalidad y Tesorería):** Generadores de borradores oficiales (303, 111, 115, 347) y conciliación bancaria interactiva.
- **Fase 5 (Automatización):** Webhook de correo entrante para ingesta desatendida y API pública versionada.
- **Fase 6 (Experiencia Avanzada):** Asistente financiero inteligente consultando la base de datos real.
- **Fase 7 (Producción):** Auditoría de seguridad OWASP, copias de seguridad automáticas y checklist de despliegue.
