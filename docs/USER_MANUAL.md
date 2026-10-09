# MANUAL DE USUARIO Y GUÍA DE OPERACIONES (USER MANUAL)

Bienvenido a **KontaAI Suite**, la plataforma inteligente de gestión empresarial, contabilidad y procesamiento documental con IA.

Este manual proporciona una guía paso a paso, accesible para cualquier usuario o asesor contable sin necesidad de conocimientos técnicos avanzados.

---

## 1. Primeros Pasos: Acceso y Selección de Empresa
1. Abra su navegador web e ingrese a la dirección de la plataforma (`http://localhost:3000` en entorno local o la URL corporativa de su despacho).
2. En la barra superior, localice el **Selector de Empresa**.
3. Seleccione la empresa o cliente con el que desea trabajar. Todos los datos, facturas, asientos, proveedores y configuraciones se filtrarán y aislarán de forma inmediata.

---

## 2. Recepción y Triaje de Facturas
1. Vaya al módulo **Facturas** en el menú lateral.
2. Puede arrastrar uno o varios archivos PDF o imágenes al área de carga, o hacer clic en **«Subir Factura»**.
3. El sistema procesará el documento:
   - Si dispone de clave de IA configurada, extraerá automáticamente emisor, NIF, fecha, base, IVA, retenciones y total.
   - Si no dispone de clave o el documento está incompleto, el archivo se conserva íntegro en su almacenamiento y se abre en modo asistido con semáforo **ROJO** para permitir su revisión manual o reintento de IA.
4. **Interpretación del Semáforo Fiscal:**
   - 🟢 **VERDE:** Documento cuadrado aritméticamente, NIF verificado en censo, sin duplicados y con subcuentas asignadas. Listo para validar y contabilizar.
   - 🟡 **AMARILLO:** Requiere comprobación humana (por ejemplo: factura superior a 3.000 € sujeta a declaración anual Modelo 347, retención de IRPF detectada, o proveedor nuevo que necesita confirmar su cuenta de gasto).
   - 🔴 **ROJO:** Bloqueo detectado (ejemplo: descuadre entre base e impuestos, CIF emisor inválido, o posible factura duplicada). No puede saltarse sin corregir el motivo.
5. Al pulsar sobre cualquier factura, se despliega la **Vista Dividida de Triaje**:
   - A la izquierda: visor de alta resolución del documento original (zoom, rotación, descarga).
   - A la derecha: campos extraídos, propuesta de asiento contable (Debe/Haber) y panel de alertas semafóricas.
6. Haga clic en **«Aprobar y Archivar»** para confirmar la operación.

---

## 3. Guía Paso a Paso: Conexión con su Software Contable

Esta sección le guía para enlazar KontaAI Suite con su programa contable habitual (**A3**, **Contasol**, **Sage** o **Holded**) en modo Copiloto Contable.

### Paso 1: Identificar su Software Contable y Versión
- En su ordenador, abra su programa habitual y consulte en el menú *Ayuda > Acerca de*:
  - **Wolters Kluwer:** a3asesor Eco o a3asesor Con (versión de escritorio).
  - **Software DELSOL:** Contasol (versión anual instalada en local o servidor).
  - **Sage:** Sage 50 o Sage Despachos Connected.
  - **Holded / Anfix:** Plataformas en la nube.

### Paso 2: Configurar la Longitud de Subcuentas de la Empresa
1. En KontaAI Suite, diríjase a **Configuración > Empresa > Plan Contable**.
2. Compruebe cuántos dígitos tienen las cuentas en su programa contable de destino:
   - Generalmente se emplean **9 dígitos** (ej. `400000001`) o **10 dígitos** (ej. `4000000001`).
3. Asegúrese de que el selector de longitud coincida exactamente con su programa contable. KontaAI Suite rechazará cuentas de longitud incorrecta para evitar descuadres en su diario.

### Paso 3: Configurar el Software de Destino en KontaAI
1. Vaya a **Integraciones Contables** en el menú de KontaAI Suite.
2. En la tarjeta de su software (por ejemplo, **Wolters Kluwer A3** o **Contasol DELSOL**), haga clic en **«Configurar»**.
3. Seleccione el modo de integración:
   - **Descarga de fichero de enlace (Recomendado para la mayoría de asesorías):** Genera directamente el fichero oficial (`SUENLACE.DAT` o CSV) listo para importar.
   - **Directorio de intercambio local:** Si dispone de una carpeta compartida en su red donde su programa contable lee automáticamente las importaciones.
4. Guarde los cambios.

### Paso 4: Realizar una Prueba con un Documento de Ensayo
1. En el módulo de Facturas, apruebe una factura de prueba en semáforo VERDE.
2. Vaya al módulo **Asientos / Exportación Contable**.
3. Seleccione el periodo de prueba (por ejemplo, el mes en curso).
4. El sistema le mostrará el **Resumen Previo a la Exportación**:
   - Número de facturas y asientos incluidos.
   - Suma total del Debe y del Haber (deben ser exactamente iguales).
   - Ausencia de incidencias o bloqueos.
5. Pulse en **«Generar y Descargar Exportación»**.

### Paso 5: Importar en su Programa Contable de Destino
- **En A3 (a3asesor Eco/Con):**
  1. Vaya al menú *Utilidades > Enlaces Contables > Enlace de Ficheros (SUENLACE)*.
  2. Seleccione la ruta donde descargó el archivo `SUENLACE.DAT`.
  3. Ejecute la importación. Compruebe que el diario se actualiza con los nuevos asientos cuadrados.
- **En Contasol:**
  1. Vaya a la solapa *Utilidades > Importaciones > Archivos del Diario en formato CSV*.
  2. Seleccione el archivo CSV generado por KontaAI Suite.
  3. Marque la casilla de separador punto y coma (`;`).
  4. Finalice el asistente y revise el Libro Diario.
- **En Sage 50 / Despachos:**
  1. Vaya a *Contabilidad > Asientos > Importar Asientos*.
  2. Seleccione la plantilla de importación y el archivo exportado.

### Paso 6: Prevención de Duplicados
- Cada vez que genera una exportación, KontaAI Suite marca internamente los asientos exportados con un identificador de lote (`export_batch_id`).
- En la siguiente exportación del trimestre o mes, los asientos ya exportados **quedan ocultos por defecto**, evitando que se vuelvan a incorporar al programa contable.
- Si por alguna razón necesita reexportar un asiento, marque la casilla *«Incluir asientos ya exportados»* y justifique la operación.

### Paso 7: Resolución de Problemas Frecuentes
- **Error: «Longitud de cuenta inválida en línea X»**: Verifique que la longitud de subcuentas configurada en KontaAI (8, 9 o 10 dígitos) coincide con la ficha de la empresa en su programa contable.
- **Error: «Asiento descuadrado en destino»**: KontaAI Suite solo exporta asientos con partida doble matemáticamente cuadrada (Diferencia = 0,00 €). Si observa un descuadre en destino, revise que no existan cuentas no creadas en el catálogo de su software.
- **Factura con más de 3 tipos de IVA en A3**: KontaAI Suite divide automáticamente la factura en dos asientos correlativos con el mismo concepto y documento (`A3SeatSplitter`) para respetar el límite de 3 bases por registro de A3. Ambos asientos suman exactamente el total de la factura.

### Paso 8: Desconectar o Cambiar de Software
Si en el futuro decide cambiar de software contable (por ejemplo, migrar de Contasol a A3 o activar la Modalidad A de ERP Completo):
1. Vaya a **Integraciones Contables**.
2. Seleccione el nuevo sistema o active la modalidad ERP Completo.
3. No perderá ningún asiento, factura ni archivo archivado: todos los datos históricos permanecen intactos en la base de datos de KontaAI Suite.
