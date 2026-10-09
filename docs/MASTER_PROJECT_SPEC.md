# ESPECIFICACIÓN MAESTRA DEL PROYECTO (MASTER PROJECT SPEC)

## 1. Visión y Misión del Producto
La plataforma **KontaAI Suite** es una solución integral de gestión empresarial, contabilidad, fiscalidad, tesorería y procesamiento inteligente de documentos (IDP) mediante Inteligencia Artificial multimodal, diseñada específicamente para el ecosistema mercantil, fiscal y contable español (autónomos, PYMEs y asesorías/despachos profesionales).

El producto opera bajo una arquitectura híbrida unificada con **dos modalidades de uso configurables por empresa**, intercambiables en cualquier momento sin pérdida ni duplicidad de datos:

### Modalidad A — ERP Completo
- Destinada a autónomos y empresas que gestionan todo su ciclo operativo dentro de la plataforma.
- Módulos operativos:
  - Facturación emitida y recibida (con soporte para Veri*factu, TicketBAI/Batuz y Factura Electrónica B2B).
  - Gestión integral de clientes, proveedores y acreedores.
  - Libro Diario, Libro Mayor, Balances (Sumas y Saldos, Situación, Pérdidas y Ganancias).
  - Liquidaciones tributarias y borradores oficiales (Modelos 303, 390, 111, 190, 115, 180, 130, 347, 349).
  - Tesorería y conciliación bancaria inteligente (Norma 43 y agregación PSD2).
  - Gestión de activos fijos, tablas de amortización y periodificaciones.
  - Portal del empleado para notas de gastos, kilometraje, dietas y nóminas.

### Modalidad B — Copiloto Contable Integrado
- Destinada a asesorías fiscales y despachos contables que utilizan un software contable consolidado de terceros (Wolters Kluwer A3, Software DELSOL Contasol, Sage 50/Despachos Connected, Holded, Anfix, Cegid).
- Propuesta de valor:
  - Recepción desatendida multicanal (subida web individual/lote, ingesta automática por correo electrónico dedicado, arrastre de lotes escaneados multi-factura).
  - Extracción documental multimodal y OCR con detección de casuísticas complejas (múltiples tipos de IVA, recargos de equivalencia, retenciones IRPF profesionales y de alquiler, suplidos y facturas rectificativas).
  - Validación determinista estricta en servidor y motor semafórico (VERDE, AMARILLO, ROJO) con trazabilidad de advertencias.
  - Generación de asientos contables en partida doble cuadrada y exportación/sincronización nativa sin alterar los diarios ni duplicar registros.

---

## 2. Principios Rectores y Calidad del Software
1. **Corregir antes de ampliar:** La integridad del núcleo financiero prevalece sobre cualquier adición funcional.
2. **Determinismo fiscal vs. Creatividad de IA:** La Inteligencia Artificial interpreta y extrae; las reglas matemáticas, fiscales y el Plan General Contable validan con exactitud decimal estricta (`ROUND_HALF_UP`).
3. **No inventar datos:** Si una factura no tiene NIF, base legible o fecha, se clasifica en semáforo ROJO con motivo explícito, preservando el fichero original en reposo sin descartarlo.
4. **Cero Mocks en Producción:** Las respuestas de la aplicación reflejan el estado de la base de datos y de los conectores reales.
5. **No destructividad:** Los datos sujetos a obligaciones de conservación legal (4 años fiscal, 6 años mercantil según Código de Comercio Art. 30) no se eliminan silenciosamente.
6. **Seguridad y Cifrado:** Almacenamiento seguro con cifrado AES-256-GCM para documentos en reposo y aislamiento multiempresa verificado en backend en cada petición.

---

## 3. Arquitectura del Sistema
- **Frontend:** Next.js 16 (App Router), React 19, TypeScript estricto, TailwindCSS v4.
- **Backend:** FastAPI (Python 3.11+), SQLAlchemy 2.0 asíncrono (`asyncpg` / `aiosqlite`), Pydantic v2.
- **Base de Datos:** SQLite asíncrono para desarrollo local; PostgreSQL 15+ con esquemas aislados para producción.
- **Procesamiento de Documentos:** PyMuPDF para segmentación y renderizado; OpenAI GPT-4o-mini / Google Gemini 1.5/2.0 para extracción multimodal estructurada; Tesseract OCR para respaldo offline.
- **Seguridad:** Autenticación JWT / Sesiones seguras, hashing Argon2/Bcrypt, control de acceso basado en roles (RBAC) granular por empresa.
