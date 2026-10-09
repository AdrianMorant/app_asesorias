# CONFIGURACIÓN DEL PLAN CONTABLE Y EMPRESAS (ACCOUNTING SETUP)

Este documento detalla la estructura del catálogo contable, las reglas de configuración por empresa y los flujos de personalización e importación.

---

## 1. Fundamento Contable Oficial
KontaAI Suite implementa el catálogo contable oficial español basado en:
- **Plan General de Contabilidad de PYMES** (Real Decreto 1515/2007, de 16 de noviembre).
- **Plan General de Contabilidad Ordinario** (Real Decreto 1514/2007, de 16 de noviembre) y sus modificaciones posteriores (RD 1/2021).

### Cobertura de Grupos
El sistema provee una plantilla maestra completa (`PGC_PYME_MASTER`) que cubre los 7 grupos operacionales:
- **Grupo 1: Financiación Básica** (Capital social 100, Reservas 112/113, Resultados del ejercicio 129, Deudas a largo plazo con entidades de crédito 170).
- **Grupo 2: Inmovilizado** (Inmovilizado material 210-218, Inmovilizado intangible 203/206, Amortización acumulada 280/281, Deterioros 291).
- **Grupo 3: Existencias** (Mercaderías 300, Materias primas 310, Productos terminados 350, Deterioros 390).
- **Grupo 4: Acreedores y Deudores por Operaciones Comerciales**
  - Proveedores: 400 (correlativos y genérico).
  - Acreedores por prestaciones de servicios: 410.
  - Clientes: 430.
  - Personal: 460 (anticipos), 465 (remuneraciones pendientes).
  - Hacienda Pública: 4700 (IVA a compensar), 472 (IVA soportado desglosado), 477 (IVA repercutido desglosado), 4750 (HP acreedora IVA), 4751 (HP acreedora retenciones IRPF), 473 (retenciones practicadas).
  - Organismos de la Seguridad Social: 476 (acreedores por cotizaciones).
  - Operaciones societarias y suplidos: 554 (cuenta corriente por suplidos/gastos por cuenta de terceros).
- **Grupo 5: Cuentas Financieras** (Bancos e instituciones de crédito c/c vista 572, Caja euros 570, Inversiones financieras a corto plazo 540).
- **Grupo 6: Compras y Gastos**
  - Compras: 600 (mercaderías), 602 (otros aprovisionamientos).
  - Servicios exteriores: 621 (arrendamientos y cánones), 622 (reparaciones y conservación), 623 (servicios de profesionales independientes), 624 (transportes), 625 (primas de seguros), 626 (servicios bancarios), 627 (publicidad y propaganda), 628 (suministros: luz, agua, gas, telefonía), 629 (otros servicios).
  - Tributos: 631 (otros tributos).
  - Gastos de personal: 640 (sueldos y salarios), 642 (seguridad social a cargo de la empresa).
  - Gastos financieros: 662 (intereses de deudas).
  - Dotaciones a la amortización: 680, 681.
- **Grupo 7: Ventas e Ingresos** (Ventas de mercaderías 700, Prestación de servicios 705, Ingresos por arrendamientos 752, Ingresos financieros 769).

---

## 2. Configuración por Empresa
Cada empresa dada de alta en el sistema tiene su propio aislamiento contable:
1. **Longitud de Subcuentas (`plan_cuentas_longitud`):**
   - Configurable a **8, 9 o 10 dígitos** (por defecto: 9 dígitos).
   - Validación estricta en backend: Toda subcuenta creada, importada o asignada debe coincidir exactamente con la longitud de la empresa.
   - Si una empresa está configurada a 9 dígitos, el sistema rechaza subcuentas de 8 o 10 dígitos devolviendo error HTTP 400 con mensaje descriptivo.
2. **Cuentas por Defecto de Empresa:**
   - Proveedor genérico: `400` + ceros correspondientes (ej. `400000000` en 9 dígitos).
   - Acreedor genérico: `410000000`.
   - Cliente genérico: `430000000`.
   - Suplidos por defecto: `554000000`.
   - Banco principal: `572000000`.

---

## 3. Algoritmo de Asignación de Proveedores y Acreedores
Para cada factura recibida:
1. **Regla de Proveedor Frecuente:** Si el CIF/NIF del emisor ya tiene una subcuenta específica asignada en la tabla `suppliers` de la empresa (ej. Proveedor A -> `400000001`), se reutiliza de forma determinista.
2. **Asignación Correlativa Automática (`find_next_free_supplier_account`):** Si es un proveedor nuevo y la empresa tiene habilitada la subcuenta individualizada, el sistema busca la subcuenta numérica más alta con el prefijo `400` o `410` y genera la siguiente libre (`400000002`, `400000003`, etc.), evitando colisiones con cuentas preexistentes.
3. **Opción Genérica:** Si la empresa prefiere no individualizar proveedores pequeños, se asigna la cuenta genérica correspondiente.

---

## 4. Importación y Exportación del Catálogo (CSV / Excel)
- **Importador Inteligente (`POST /api/v1/accounts/import-csv`):**
  - Acepta archivos `.csv` delimitados por coma o punto y coma.
  - Detecta automáticamente columnas de código, descripción y tipo.
  - Valida la longitud estricta de cada fila contra `plan_cuentas_longitud`.
  - Diferencia de forma atómica:
    - **Cuentas creadas:** Códigos nuevos añadidos al plan contable.
    - **Cuentas actualizadas:** Códigos existentes cuya descripción o naturaleza ha sido ajustada.
    - **Filas rechazadas:** Códigos que no cumplen la longitud o formatos inválidos, informando fila por fila con motivo detallado.
- **Exportador Normalizado (`GET /api/v1/accounts/export-csv`):**
  - Descarga el plan contable activo ordenado por código en formato UTF-8 con BOM o Latin-1 para total compatibilidad con Excel.
