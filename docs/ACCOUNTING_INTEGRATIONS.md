# CENTRO DE INTEGRACIONES CONTABLES (ACCOUNTING INTEGRATIONS SPEC)

Este documento describe la especificación técnica, la compatibilidad por versión y los formatos de intercambio de datos con los principales programas contables del mercado español.

---

## 1. Filosofía de Integración
KontaAI Suite garantiza que los asientos contables generados a partir de facturas validadas puedan incorporarse a los programas contables de las asesorías sin descuadres, sin errores de formato y **sin riesgo de doble contabilización**.

Se contemplan tres mecanismos de integración:
1. **Importación mediante Fichero Normalizado:** Generación de archivos de enlace ajustados a las especificaciones exactas de cada software contable (A3 SUENLACE.DAT, Contasol CSV, Sage CSV).
2. **API Oficial en la Nube:** Para soluciones con endpoints REST públicos o de partners (Holded, Sage Cloud, Anfix).
3. **Agente Local / Carpeta Compartida:** Monitorización de directorios en redes locales de despachos para volcado de ficheros de intercambio sin intervención manual.

---

## 2. Compatibilidad Detallada por Software

### 2.1. Wolters Kluwer A3 (a3asesor Eco / a3asesor Con)
- **Formato de Archivo:** `SUENLACE.DAT`
- **Estructura:** Archivo de texto plano de ancho fijo (posicional), exactamente **96 caracteres por línea**.
- **Codificación:** ANSI / Windows-1252 (CP1252). Los saltos de línea deben ser estrictamente CRLF (`\r\n`).
- **Restricción de Diseño:** A3 soporta un máximo de **3 bases impositivas de IVA por cada registro de factura** en su estructura de registro estándar.
- **Solución Técnica Implementada (`A3SeatSplitter`):**
  - Si una factura contiene 1, 2 o 3 tipos impositivos de IVA, se emite un único asiento.
  - Si una factura contiene 4 o más tipos impositivos (ej. 21%, 10%, 4% y 0% o exento), el servicio divide matemáticamente la operación en dos o más asientos correlativos con el mismo concepto y documento de enlace, garantizando que cada registro respete la capacidad máxima de bases sin descuadre en el Mayor general.
- **Cuentas Contables:** Longitud variable (típicamente 9 o 10 dígitos) según la ficha de la empresa en A3. Relleno estricto con ceros a la derecha del subgrupo.

### 2.2. Software DELSOL (Contasol)
- **Formato de Archivo:** Archivo de intercambio de diario en formato CSV delimitado.
- **Separador de Campos:** Punto y coma (`;`).
- **Separador Decimal:** Coma (`,`) con 2 decimales para importes monetarios.
- **Codificación:** ISO-8859-1 (Latin-1) / Windows-1252.
- **Estructura de Cabecera:**
  `Diario;Fecha;Asiento;Cuenta;Concepto;Documento;Debe;Haber;Factura;Base;IVA;Recargo`
- **Validaciones:**
  - Partida doble equilibrada dentro de cada número de asiento.
  - Si el importe es Debe, el campo Haber queda vacío o con valor `0,00` (y viceversa).
  - Fecha en formato `DD/MM/AAAA`.

### 2.3. Sage 50 / Sage Despachos Connected
- **Formato de Archivo:** CSV de importación de asientos contables.
- **Separador:** Tabulador (`\t`) o punto y coma (`;`) según configuración regional.
- **Codificación:** ANSI / Windows-1252.
- **Campos Requeridos:** Número de Asiento, Fecha (`DD-MM-AAAA`), Cuenta, Concepto, Documento, Debe, Haber, Contrapartida, Base Imponible, Porcentaje de IVA, Cuota de IVA, Porcentaje de Retención, Cuota de Retención.
- **Compatibilidad de Subcuentas:** Adaptación dinámica a 8, 9 o 10 dígitos según la empresa.

### 2.4. Holded
- **Mecanismos:** Exportación CSV de libro diario compatible con la plantilla de importación masiva de Holded, y conector API REST v1 (`POST /api/invoicing/v1/documents`).
- **Mapeo:** Vinculación de contactos (NIF/CIF), productos/servicios a cuentas de los grupos 6 y 7, e impuestos preconfigurados.

---

## 3. Control de Trazabilidad y Prevención de Duplicados
Para impedir que un asiento se exporte múltiples veces involuntariamente:
1. **Identificador Único de Exportación (`export_batch_id`):** Cada proceso de exportación genera un lote auditado con timestamp, usuario responsable y hash criptográfico de los asientos incluidos.
2. **Estado en Base de Datos:** Las facturas exportadas pasan al estado de exportación `EXPORTADO_ERP` y registran la fecha y el identificador de lote en sus metadatos.
3. **Filtro de Exclusión por Defecto:** Las pantallas de exportación excluyen automáticamente los registros ya exportados. Si un usuario necesita reexportar un periodo, debe marcar explícitamente la casilla «Incluir asientos previamente exportados», registrando una justificación en la bitácora de auditoría.
4. **Idempotencia:** Al reexportar, se preserva el número de asiento original asignado para no alterar la correlación en el software contable de destino.
