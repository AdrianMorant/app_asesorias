# PLAN INTEGRAL DE PRUEBAS Y CRITERIOS DE VALIDACIÓN (TEST PLAN)
### Plataforma SaaS de Gestión Empresarial y Copiloto Contable con IA

Estado de revisión: **Fases 2 y 3 — Superadas y Validadas al 100%**  
Última actualización: Octubre 2026

---

## 1. Alcance y Estrategia de Pruebas

El sistema cuenta con cuatro niveles de validación automatizada:
1. **Pruebas de Contabilidad General y Libros Oficiales (Fase 2):** Cuadre de partida doble (0,00 €), Libro Mayor con saldo progresivo, Balance de Sumas y Saldos con los 7 Grupos PGC, reversión de asientos por contra-asiento invertido, regularización y cierre contra la cuenta 129000000, y exportación CSV con BOM UTF-8.
2. **Pruebas de Integraciones Contables e Idempotencia (Fase 3):** Longitud exacta de 96 caracteres en A3 `SUENLACE.DAT` con `A3SeatSplitter`, delimitación por `;` y coma decimal en Contasol CSV, plantilla Sage CSV, prevención estricta de duplicados por huella digital SHA-256 (`data_fingerprint`), y soporte para reexportación forzada justificada.
3. **Pruebas de Integración de los 5 Pilares Base:** Ingesta y corte Multi-Factura (MF), subcuentas correlativas, casuísticas fiscales (retenciones, suplidos, rectificativas), conciliación bancaria y healthcheck de servidores en ejecución.
4. **Verificación de Tipos Frontend y Calidad:** Chequeo estricto de TypeScript en Next.js 16 (`npx tsc --noEmit`).

---

## 2. Matriz de Suites de Pruebas Automatizadas

| Suite de Pruebas | Archivo Ejecutable | Cobertura Funcional | Resultado Real |
| :--- | :--- | :--- | :---: |
| **Suite Contable e Integraciones (Fases 2 y 3)** | `backend/tests/test_phase2_accounting.py` | 1. Libro Diario: partida doble y reversión auditable.<br>2. Cierre de ejercicio (cuenta 129), bloqueo y reapertura por CIF.<br>3. Libro Mayor: extracto progresivo cronológico y naturaleza.<br>4. Sumas y Saldos: 7 grupos PGC y exportación CSV.<br>5. Integraciones: A3, Contasol, huella SHA-256 y prevención de duplicados. | 🟢 **PASS (5/5 pruebas)** |
| **Verificación de Integración (5 Pilares)** | `backend/tests/verify_full_suite.py` | 1. Ingesta y corte MF (Split PDF).<br>2. Subcuentas correlativas y casuísticas IRPF/Suplidos/Rectificativas.<br>3. Motores de exportación ERP (A3, Contasol, Sage).<br>4. Conciliación bancaria y deducción semántica (TGSS 476, Iberdrola 628).<br>5. Healthcheck servidores activos (:8000 y :3000). | 🟢 **PASS (15/15 pruebas)** |
| **Chequeo Estático TypeScript** | `frontend/` (`npx tsc --noEmit`) | Verificación estricta de tipado, DTOs y componentes React en Next.js. | 🟢 **PASS (0 errores)** |

---

## 3. Detalle de Casos de Prueba Ejecutados en Fase 2 y Fase 3

### Caso TC-ACC-01: Cuadre de Partida Doble y Reversión en Libro Diario
- **Entrada:** Inserción de apunte de compra de material informático (Base: 100 €, IVA 21%: 21 €, Proveedor: 121 €).
- **Validación:** El diario reporta `total_general_debe == 121.0`, `total_general_haber == 121.0` y `is_balanced == True`.
- **Reversión:** Se invoca `POST /journal/1/reverse` con motivo formal. Se verifica que el asiento 1 pasa a `revertido` y se crea automáticamente el asiento 2 (contra-asiento) con cuentas y signos invertidos (Debe en 400 por 121 €, Haber en 600 por 100 € e IVA por 21 €).

### Caso TC-ACC-02: Regularización contra Cuenta 129 y Cierre de Ejercicio
- **Entrada:** Ingresos en cuenta 700 por 1.000 € y gastos en cuenta 600 por 400 €.
- **Validación:** `POST /journal/close-fiscal-year` regulariza ambas cuentas y abona 600 € al Haber de la cuenta 129000000 (Beneficio Neto).
- **Bloqueo:** Un intento posterior de revertir un asiento dentro de ese ejercicio cerrado devuelve `HTTP 400 ("El ejercicio ya se encuentra cerrado")`.
- **Reapertura:** Se invoca `POST /journal/reopen-fiscal-year` con CIF erróneo (falla con HTTP 400) y posteriormente con el CIF verificado (desbloquea con HTTP 200).

### Caso TC-ACC-03: Libro Mayor Dinámico y Naturaleza Contable
- **Entrada:** Dos movimientos en cuenta de banco 572000001 (Cobro 500 € al Debe, Pago 150 € al Haber).
- **Validación:** El endpoint reporta saldo acumulado de 500 € tras el primer movimiento y 350 € tras el segundo, con saldo final de 350 € y naturaleza `DEUDORA`.

### Caso TC-ACC-04: Balance de Sumas y Saldos y Exportación CSV
- **Entrada:** Operaciones con cuentas del Grupo 2 (216 Inmovilizado) y Grupo 5 (572 Banco).
- **Validación:** El balance refleja los subtotales oficiales agrupados por los 7 Grupos PGC. La exportación a `/trial-balance/export-csv` genera un fichero `text/csv` con delimitador `;` y BOM UTF-8 (`\ufeff`) con valores numéricos formateados con coma decimal.

### Caso TC-ACC-05: Prevención de Duplicados e Idempotencia en Integraciones
- **Entrada:** Exportación inicial de factura a Wolters Kluwer A3.
- **Validación:** Generación exitosa de `SUENLACE.DAT` con líneas de exactamente 96 caracteres y asignación de `data_fingerprint` (SHA-256).
- **Control de Duplicado:** Un segundo intento de exportar el mismo lote con `force_reexport=False` es rechazado con `HTTP 400`.
- **Reexportación Forzada:** Se reintenta con `force_reexport=True` y motivo de al menos 5 caracteres; la operación se procesa correctamente y se archiva en la auditoría.
