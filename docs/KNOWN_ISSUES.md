# REGISTRO DE INCIDENCIAS TÉCNICAS (KNOWN ISSUES & BUGS)
### Plataforma SaaS Financiero-Contable con IA

---

## 1. Clasificación de Severidad

- **Crítica (P0):** Pérdida de datos, eliminación no autorizada, corrupción de estados contables o fallo de seguridad.
- **Alta (P1):** Funcionalidad principal interrumpida (extracción rota, borrado defectuoso, bloqueo de usuario).
- **Media (P2):** Inconsistencias de interfaz, formularios incompletos, catálogos parciales.
- **Baja (P3):** Detalles visuales menores, optimización no bloqueante.

---

## 2. Inventario de Incidencias Identificadas

### INC-001 — Persistencia de la barra flotante de borrado tras eliminar facturas
- **Gravedad:** Alta (P1) / Usabilidad Crítica
- **Módulo afectado:** `frontend/src/components/InvoiceTable.tsx` y `frontend/src/app/page.tsx`
- **Comportamiento actual:** Tras seleccionar y borrar 9 facturas, la barra de acciones masivas continúa mostrándose al pie con el texto «Borrar 9 facturas», a pesar de que no existe ninguna fila seleccionada visible en la tabla.
- **Comportamiento esperado:** Al confirmar el borrado de facturas, la lista de seleccionadas (`selectedIds`) debe vaciarse inmediatamente a `[]`, y la barra flotante debe ocultarse de forma inmediata (`selectedIds.length === 0`). Si el usuario cancela en el modal de confirmación, las facturas no deben desaparecer de la tabla prematuramente.
- **Causa identificada:** 
  1. En `InvoiceTable.tsx`, `handleExecuteBulkDelete` reseteaba su estado local pero desacoplaba el estado antes de que el modal de confirmación del padre (`DeleteConfirmationModal`) fuera confirmado o cancelado.
  2. Si `fetchInvoices` en el padre refrescaba los datos de la empresa o si fallaba la llamada de borrado, la discordancia entre el estado local `selectedIds` y las props de `invoices` provocaba que la condición `{selectedIds.length > 0}` siguiera evaluando como verdadera.
  3. No había sincronización bidireccional entre la selección en `InvoiceTable` y el estado general de la página (o al cambiar de empresa / filtros).
- **Solución técnica:**
  1. Unificar y controlar el estado de selección o garantizar que `onBulkDelete` reciba la acción de confirmación real.
  2. En `InvoiceTable.tsx`, asegurar que cada vez que cambie `invoices`, se cambie de filtro, se cambie de empresa o se ejecute un borrado, `selectedIds` filtre estrictamente los IDs que ya no existan en la lista de facturas activas.
  3. Al confirmarse el borrado en `handleConfirmDelete`, emitir la limpieza explícita de `selectedIds` en `InvoiceTable` y cerrar el modal.
- **Prueba necesaria:**
  1. Seleccionar 9 facturas en la tabla mediante las casillas de verificación.
  2. Verificar que aparece la barra inferior indicando «9 facturas seleccionadas» y botón «Borrar 9 facturas».
  3. Pulsar «Borrar 9 facturas» y confirmar en el modal.
  4. Verificar que las 9 facturas se eliminan de la base de datos y que la barra desaparece inmediatamente (0 seleccionadas).
- **Resultado:** En verificación.

---

### INC-002 — Eliminación del archivo original cuando falla la extracción de IA (Error 401 / Saldo agotado)
- **Gravedad:** Alta (P1)
- **Módulo afectado:** `backend/app/api/v1/endpoints/invoices.py` y `backend/app/services/extractor_llm.py`
- **Comportamiento actual:** Si la clave de API de OpenAI o Gemini no es válida (ej. Error 401) o se agota la cuota, el endpoint `POST /invoices/upload` captura la excepción, ejecuta `saved_file_path.unlink()` borrando el archivo físico del disco y responde con HTTP 400. El documento se pierde y el usuario no puede triarlo manualmente.
- **Comportamiento esperado:** Si la extracción automática con IA falla por motivos de red, cuota o clave externa:
  1. El archivo físico cifrado se **conserva íntegro** en el servidor.
  2. Se crea la entidad `Invoice` en la base de datos en estado de semáforo **ROJO** (`status="RED"`, `workflow_status="a_revisar"`).
  3. En `status_reasons` se indica de manera explícita y no bloqueante: `"Extracción con IA pendiente: revise la clave de API en backend/.env o complete los datos fiscales manualmente en triaje"`.
  4. El usuario puede abrir la factura en la consola Split-Screen, ver el documento original en el visor integrado, introducir los campos o pulsar un botón para reintentar la extracción.
- **Causa identificada:** En `invoices.py`, el bloque `except (ValueError, Exception)` eliminaba el fichero en disco y levantaba un HTTP 400 en lugar de hacer fallback a un borrador pendiente de triaje.
- **Solución técnica:** Modificar el manejador de excepciones en `upload_invoice` para que, en caso de fallo del proveedor LLM, cree la factura en modo "pendiente de extracción / revisión manual", conservando el fichero original y permitiendo el reintento.
- **Prueba necesaria:** Subir un PDF de factura con una API key no configurada o mockeada como fallida; verificar que el archivo se guarda, se crea la factura en estado ROJO con el motivo correspondiente y es visible en el visor de triaje.
- **Resultado:** En verificación.

---

### INC-003 — Catálogo de cuentas del PGC PYMES incompleto (Solo ~40 cuentas de muestra)
- **Gravedad:** Media (P2)
- **Módulo afectado:** `backend/app/services/pyme_pgc_seed.py`
- **Comportamiento actual:** La siembra inicial del PGC para una nueva empresa solo incluye unas 40 cuentas de los grupos 6, 7, 4, 5, 2 y 1. No existe ninguna cuenta del Grupo 3 (Existencias), faltan las cuentas de amortización acumulada (280, 281), deudas a largo plazo (170), reservas (112, 113) y grupos de ingresos/gastos financieros completos.
- **Comportamiento esperado:** Cobertura oficial completa del Plan General de Contabilidad para PYMES (RD 1515/2007) para los Grupos 1 al 7.
- **Causa identificada:** `pyme_pgc_seed.py` contenía un extracto de ejemplo reducido.
- **Solución técnica:** Ampliar `PGC_PYME_MASTER` con las cuentas estándar de 3 y 4 dígitos de los Grupos 1, 2, 3, 4, 5, 6 y 7, manteniendo la lógica de expansión dinámica a 8, 9 o 10 dígitos.
- **Prueba necesaria:** Ejecutar `seed_company_chart_of_accounts` para una empresa y validar que se generan cuentas de existencias (300, 310), amortizaciones (280, 281), tesorería (570, 572), capital y reservas (100, 112, 129), etc.
- **Resultado:** En verificación.

---

### INC-004 — Ausencia de política de resolución de colisiones en el archivado de facturas
- **Gravedad:** Media (P2)
- **Módulo afectado:** `backend/app/services/archiver.py`
- **Comportamiento actual:** `archive_invoice_file` ejecuta directamente `shutil.move(src, target_file_path)`. Si ya existía un documento con el mismo nombre en la carpeta de destino (ej. dos facturas con fecha y CIF coincidentes o rectificativas), se sobrescribe sin advertencia.
- **Comportamiento esperado:** Si el archivo de destino ya existe, aplicar una política determinista de desambiguación mediante sufijo numérico (`_1.pdf`, `_2.pdf`) garantizando la integridad de ambos documentos.
- **Causa identificada:** Falta de comprobación `target_file_path.exists()` antes de la llamada a `shutil.move`.
- **Solución técnica:** Añadir un bucle seguro de sufijado correlativo si el fichero de destino existe.
- **Prueba necesaria:** Archivar dos facturas con idéntico nombre propuesto y verificar que ambas coexisten en disco sin sobreescritura.
- **Resultado:** En verificación.

---

### INC-005 — Ámbito de importación y falta de siembra contable en test_flow.py
- **Gravedad:** Media (P2)
- **Módulo afectado:** `backend/test_flow.py`
- **Comportamiento actual:** `test_flow.py` fallaba al evaluar el Escenario 1 (Factura Verde) debido a que la empresa creada no tenía sembrado el plan contable y la subcuenta `629000001` no existía, clasificándola como YELLOW.
- **Comportamiento esperado:** `test_flow.py` debe sembrar el catálogo de cuentas de la empresa antes de probar el motor semafórico, de modo que la factura estándar clasifique correctamente como GREEN.
- **Causa identificada:** Falta de llamada a `seed_company_chart_of_accounts(db, company.id, 9)` tras la creación de la empresa de prueba.
- **Solución técnica:** Incluir la siembra del PGC en la fase de inicialización de la empresa en `test_flow.py`.
- **Prueba necesaria:** Ejecutar `python backend/test_flow.py` y verificar que el 100% de los escenarios pasan.
- **Resultado:** En verificación.
