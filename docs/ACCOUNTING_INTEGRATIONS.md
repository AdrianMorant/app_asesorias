# CENTRO DE INTEGRACIONES CONTABLES (ACCOUNTING INTEGRATIONS SPEC)

Este documento describe la especificación técnica, la compatibilidad por versión y los formatos de intercambio de datos con los principales programas contables del mercado español.

---

## 1. Filosofía de Integración y Transparencia

KontaAI Suite garantiza que los asientos contables generados a partir de facturas validadas puedan incorporarse a los programas contables de las asesorías sin descuadres, sin errores de formato y **sin riesgo de doble contabilización**.

### Principio de Realidad Operativa (Cero Simulaciones)
El sistema **no simula estados falsos** de sincronización en aplicaciones de escritorio de terceros.
- Si se genera un archivo de intercambio para un software local (A3, Contasol, Sage), el estado asignado es **`EXPORTED_FILE`** ("Fichero Generado"). Esto indica que el fichero se encuentra listo para su importación manual por parte del contable en su software de escritorio.
- El estado **`SYNCED_API`** se reserva exclusivamente para conectores Cloud verificados mediante respuesta HTTP 200/201 del endpoint oficial.
- Si un conector API carece de credenciales o API key válida, se categoriza estrictamente como **`PENDING_CREDENTIALS`**.

---

## 2. Compatibilidad Detallada por Software

### 2.1. Wolters Kluwer A3 (a3asesor Eco / a3asesor Con / a3innuva)
- **Estado de Validación:** 🟢 Verificado y validado mediante suite de tests automatizados (`test_phase2_accounting.py`).
- **Formato de Archivo:** `SUENLACE.DAT`
- **Estructura:** Archivo de texto plano posicional, de longitud fija estricta de **96 caracteres por línea** (relleno con espacios a la derecha).
- **Codificación:** ANSI / Windows-1252 (CP1252). Saltos de línea CRLF (`\r\n`).
- **Restricción de Fabricante:** Wolters Kluwer solo admite un máximo de 3 bases impositivas de IVA por cada registro de factura.
- **Solución Implementada (`A3SeatSplitter`):**
  - Facturas con $\le 3$ tipos de IVA: Generan 1 único asiento (Tipo 1 cabecera, Tipo 2 apuntes contables, Tipo 3 registros de IVA).
  - Facturas con $> 3$ tipos de IVA: Fragmentación automática en 2 asientos correlativos vinculados con la misma fecha y documento, manteniendo el cuadre en el Mayor sin provocar rechazos en A3.
- **Tipos de Registro:**
  - Registro Tipo 1 (Cabecera): Tipo `1`, Código Empresa (5 dígitos), Código Diario (2 dígitos), Fecha (`DDMMAAAA`), Documento (10 car.), Concepto (30 car.).
  - Registro Tipo 2 (Apunte): Tipo `2`, Empresa (5), Diario (2), Asiento (6), Fecha (8), Cuenta (12), Concepto (28), Debe (12 car. con 2 decimales y coma/punto), Haber (12 car.), Documento (10).
  - Registro Tipo 3 (IVA): Tipo `3`, Empresa (5), Diario (2), Asiento (6), Fecha (8), Cuenta IVA (12), CIF emisor (10), Base (12), Tipo % (5), Cuota (12), Documento (10).

### 2.2. Software DELSOL (Contasol)
- **Estado de Validación:** 🟢 Verificado y validado mediante suite de tests automatizados.
- **Formato de Archivo:** CSV de Diario delimitado por punto y coma (`;`).
- **Separador Decimal:** Coma española (`,`) con 2 decimales para importes monetarios.
- **Codificación:** ISO-8859-1 (Latin-1) / Windows-1252.
- **Estructura de Columnas:**
  `Diario;Fecha;Asiento;Cuenta;Concepto;Documento;Debe;Haber;Factura;Base;IVA;Recargo`
- **Validaciones Contables:**
  - Partida doble balanceada por cada número de asiento.
  - Formato de fecha `DD/MM/AAAA`.

### 2.3. Sage 50 / Sage Despachos Connected
- **Estado de Validación:** 🟢 Verificado y validado con plantilla oficial de asientos contables.
- **Formato de Archivo:** CSV estructurado.
- **Separador:** Punto y coma (`;`).
- **Codificación:** ANSI / Windows-1252.
- **Campos Requeridos:** Número de Asiento, Fecha (`DD-MM-AAAA`), Cuenta, Concepto, Documento, Debe, Haber, Contrapartida, Base Imponible, Porcentaje de IVA, Cuota de IVA, Porcentaje de Retención, Cuota de Retención.

### 2.4. Holded / ERPs Cloud
- **Estado de Validación:** 🟡 Conector API preparado; marcado como `PENDING_CREDENTIALS` hasta que el usuario configure una API Key válida en el panel.

---

## 3. Control de Trazabilidad y Prevención de Duplicados (Idempotencia SHA-256)

Para garantizar la inmutabilidad y evitar duplicidades en la contabilidad del despacho:
1. **Huella Criptográfica (`data_fingerprint`):** En cada petición de exportación, se calcula el hash SHA-256 de los documentos candidatos:
   $$\text{Fingerprint} = \text{SHA256}\left(\sum_{i} (\text{inv\_id}_i + \text{"\_"} + \text{total\_amount}_i)\right)$$
2. **Detección Automática:** Si existe un lote previo con idéntica huella para el mismo software, el backend rechaza la operación con `HTTP 400 Bad Request` indicando la fecha y el identificador del lote anterior.
3. **Reexportación Forzada Justificada (`force_reexport`):**
   - Si la reexportación es intencionada (p.ej. pérdida de disco o reimportación tras error en el ERP de destino), el usuario debe marcar la opción correspondiente en el modal e introducir un motivo justificativo formal (`reexport_reason`) de al menos 5 caracteres.
   - El motivo se archiva permanentemente en la bitácora criptográfica WORM de auditoría (`security_audit.log`).
4. **Marcado de Facturas y Apuntes:** Cada documento exportado registra `exported_to_erp = True` y su vínculo con `export_batch_id`.

---

## 4. Instrucciones Operativas para el Usuario

### 4.1. Generar Lote para Wolters Kluwer A3
1. Acceder a la sección **Integraciones** en la barra lateral.
2. Seleccionar la tarjeta **Wolters Kluwer A3**.
3. Verificar los parámetros del despacho: Código de Empresa en A3 (5 dígitos, ej: `00001`) y Código de Diario (`00`).
4. Seleccionar el Ejercicio Fiscal deseado y el ámbito ("Solo Pendientes de Exportar").
5. Pulsar **Generar y Descargar Lote A3**.
6. El sistema descargará automáticamente el fichero `SUENLACE_[CIF]_[TIMESTAMP].DAT`.
7. En a3asesor: acceder a *Utilidades > Enlaces Contables > Importar Enlace* y seleccionar el fichero descargado.

### 4.2. Generar Lote para Contasol
1. Seleccionar la tarjeta **Software DELSOL (Contasol)**.
2. Comprobar el código de diario (por defecto `1` = Diario General).
3. Pulsar **Generar y Descargar Lote Contasol**.
4. Descargar el archivo `.csv`.
5. En Contasol: acceder a *Diario > Importaciones/Exportaciones > Ficheros de texto (.csv)* y confirmar la importación.
