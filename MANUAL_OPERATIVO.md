# MANUAL OPERATIVO: COPILOTO DE CONTABILIDAD CON IA
### Guía de uso rápido para el equipo contable

---

## 1. ¿Qué es este sistema y para qué sirve?
Es una plataforma diseñada para eliminar el tecleo manual de facturas. El sistema:
1. Extrae los datos fiscales y aritméticos de los documentos (PDFs o imágenes).
2. Valida la coherencia fiscal mediante un motor de semáforo.
3. Genera automáticamente el asiento contable en partida doble adaptado a las subcuentas de cada empresa.
4. Archiva el documento en la carpeta organizada del cliente.
5. Permite exportar los asientos en bloque para importarlos en 2 segundos en A3 o Contasol.

---

## 2. Flujo de Trabajo en 4 Pasos

### Paso 1: Seleccionar la Empresa
- En el desplegable superior, selecciona la empresa cliente con la que vas a trabajar.
- Cada empresa tiene configurada su longitud de plan contable (8, 9 o 10 dígitos) y su histórico de proveedores.

### Paso 2: Cargar las Facturas
- Arrastra uno o varios archivos (PDF, PNG, JPG) a la zona central de carga.
- La IA leerá automáticamente emisor, CIF, número, fecha, desgloses de bases, tipos de IVA y retenciones de IRPF.

### Paso 3: Triaje Semafórico (Revisión)
En la tabla de facturas verás un distintivo de color:

- 🟢 **VERDE (Lista para contabilizar):**
  - El NIF es válido, los importes cuadran al céntimo y el proveedor ya está fichado con sus cuentas asignadas.
  - *Acción:* Puedes aprobarla directamente o dejar que se auto-contabilice.

- 🟡 **AMARILLO (Revisión en 1 clic):**
  - **Motivos:** Proveedor nuevo o importe superior a 3.000 € (control preventivo para el Modelo 347).
  - *Acción:* Haz clic en la factura para abrir la consola de triaje. En el panel derecho, asigna o confirma la subcuenta de proveedor (ej. 40000002) y la de gasto (ej. 62800000). Pulsa **Guardar y Aprobar**. El sistema recordará estas cuentas para las próximas facturas.

- 🔴 **ROJO (Bloqueo preventivo):**
  - **Motivos:** Factura duplicada, CIF no válido según la AEAT o descuadre matemático (Base + IVA - IRPF != Total).
  - *Acción:* Entra en triaje para ver el error exacto señalado en rojo. Comprueba si falta algún concepto exento o si la factura ya se había registrado previamente. Corrige el campo y pulsa **Guardar**.

### Paso 4: Exportación al Software Contable
- Una vez aprobadas las facturas, haz clic en el botón superior según el programa de tu puesto:
  - **Botón "Contasol CSV":** Descarga el archivo de diario para importar en Software DELSOL.
  - **Botón "A3 SUENLACE":** Descarga el fichero estándar `SUENLACE.DAT` para Wolters Kluwer A3 (A3Eco / A3Con / A3innuva).
- En tu software contable habitual, entra en:
  - En A3: *Utilidades > Enlace Contable / Importación de asientos*.
  - En Contasol: *Diario > Importaciones / Archivo de texto*.
- Selecciona el archivo descargado. Los asientos quedarán integrados en el diario general al instante.

---

## 3. ¿Dónde se guardan las facturas originales?
Al pulsar **Aprobar y Archivar**, el sistema renombra el archivo y lo mueve automáticamente a la estructura:

`storage / [CIF_EMPRESA] / [AÑO] / [TRIMESTRE] / recibidas /`

Nombre de archivo: `AAAA-MM-DD_CIF_NumeroFactura.pdf`  
*Ejemplo:* `storage/B12345674/2024/1T/recibidas/2024-03-15_B87654323_INV-2024-001.pdf`

No es necesario descargar ni renombrar archivos a mano.
