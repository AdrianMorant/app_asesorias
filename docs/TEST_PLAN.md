# PLAN INTEGRAL DE PRUEBAS Y CRITERIOS DE VALIDACIÓN (TEST PLAN)
### Plataforma SaaS de Gestión Empresarial y Copiloto Contable con IA

---

## 1. Alcance y Estrategia de Pruebas

El sistema cuenta con tres niveles de validación:
1. **Pruebas Unitarias y de Reglas de Negocio:** Validación de algoritmos contables, cuadre de partida doble, algoritmo de NIF/CIF español, generadores de ficheros ERP y semáforo.
2. **Pruebas de Integración y API REST:** Verificación de endpoints FastAPI, subida de documentos, borrado en cascada, siembra de planes contables y transacciones.
3. **Pruebas de Interfaz de Usuario y E2E:** Navegación, carga de archivos mediante drag-and-drop, triaje en pantalla dividida, sincronización del estado de selección y reactividad ante el borrado.

---

## 2. Matriz de Suites de Pruebas Automatizadas

| Suite de Pruebas | Archivo | Objetivo y Cobertura | Estado Actual |
| :--- | :--- | :--- | :---: |
| **Suite de Verificación de Integración (5 Pilares)** | `backend/tests/verify_full_suite.py` | MF Split, subcuentas correlativas, IRPF/Suplidos/Rectificativas, exportadores (A3, Contasol, Sage), conciliación bancaria. | 🟢 PASS (13/13 pruebas internas) |
| **Suite de Flujo Contable y Fiscal** | `backend/test_flow.py` | Ciclo de vida completo: empresa -> proveedor -> factura verde, amarilla y roja -> retenciones -> exportación a diario. | 🟡 En corrección (siembra de cuentas) |
| **Suite de Controles Fiscales (Fase 2)** | `backend/test_phase2_step1_fiscal_controls.py` | Retenciones Mod. 111/115, cuentas 554 de suplidos, signos rectificativos y bloqueo por fecha cerrada. | 🟢 PASS |
| **Suite de División Multi-Factura (Fase 1)** | `backend/test_phase1_split_and_state_machine.py` | Miniaturas de páginas PDF y disgregación de archivos compuestos. | 🟢 PASS |
| **Suite de API REST de Integración** | `backend/test_full_suite.py` | Endpoints HTTP: CRUD de empresas, validación estricta de 9 dígitos, importación/exportación CSV, borrado por lote. | 🟡 Requiere servidor activo :8000 |
| **Verificación de Tipos Frontend** | `npx tsc --noEmit` en `frontend/` | Ausencia de errores de tipos TypeScript en componentes, páginas y clientes API. | 🟢 PASS (0 errores) |

---

## 3. Criterios de Aceptación para la Fase 0

1. **INC-001 (Borrado de facturas y barra flotante):**
   - Al marcar N facturas y ejecutar el borrado (confirmando en el modal), `selectedIds` queda en `[]`.
   - La barra inferior flotante se oculta de inmediato.
   - Si se cancela en el modal, las facturas continúan en la tabla y la selección permanece intacta.
2. **INC-002 (Extracción y preservación de documentos sin API key):**
   - Si la llamada al proveedor de IA falla, el PDF subido no se borra del disco.
   - Se crea el registro de la factura en la base de datos en estado ROJO con mensaje orientativo.
   - El usuario puede previsualizar el PDF en el visor y editar los datos a mano.
3. **INC-003 (Plan General Contable PYMES):**
   - El catálogo maestro dispone de todas las cuentas normalizadas de los Grupos 1 al 7.
   - Al crear una empresa, se pueden consultar y usar las cuentas de existencias (Grupo 3) y amortizaciones acumuladas (280/281).
4. **INC-004 (Anti-colisión en archivado documental):**
   - Al archivar dos facturas que generarían idéntica ruta de fichero, el sistema añade un sufijo diferenciador sin destruir el primer archivo.
5. **INC-005 (Ejecución limpia de test_flow.py):**
   - `python backend/test_flow.py` finaliza exitosamente con código de salida 0.
