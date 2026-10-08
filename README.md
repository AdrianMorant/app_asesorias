# Asesoría IA: Sistema de Extracción y Contabilización de Facturas

Sistema inteligente de triaje contable y procesamiento de facturas para asesorías y gestorías en España con soporte para formatos PGC, Contasol y A3 SUENLACE.DAT.

## Características Implementadas

- **Extracción Estructurada Multimodal**:
  - Compatible con **Google GenAI SDK (Gemini 3.8 Flash)** y **OpenAI (GPT-4o)** mediante Pydantic Schema.
  - Modo demostración / mock integrado si no se han introducido aún las claves de API, garantizando que el entorno local se pueda probar de inmediato.
- **Validador Fiscal Español Riguroso**:
  - Algoritmo oficial de la AEAT para **DNI (módulo 23)**, **NIE (sustitución X/Y/Z)** y **CIF (personas jurídicas con tipos A-W)**.
- **Motor de Reglas Semafórico**:
  - 🔴 **ROJO**: Descuadres aritméticos (>0.01 €), NIF de emisor inválido, facturas duplicadas en la misma empresa cliente.
  - 🟡 **AMARILLO**: Proveedores no registrados en el maestro contable, facturas > 3.000 € (Control preventivo Modelo 347).
  - 🟢 **VERDE**: Facturas 100% cuadradas, NIF válido y proveedor mapeado con subcuenta contable.
- **Generador de Asientos Contables PGC**:
  - Partida doble en tiempo real (Debe: 6XX gasto + 472 IVA soportado; Haber: 4751 retenciones IRPF + 400 proveedores).
  - Dimensionado automático de subcuentas a 8, 9 o 10 dígitos.
- **Exportación Contable**:
  - Descarga de **Contasol CSV** (Diario general DELSOL).
  - Descarga de **A3 SUENLACE.DAT** (formato de longitud fija para A3ASESOR / A3CON).

---

## Puesta en Marcha del Backend

### 1. Requisitos
- Python 3.11+
- SQLite (incluido por defecto)

### 2. Instalación de dependencias
```bash
cd backend
pip install -r requirements.txt
```

### 3. Configuración de variables de entorno
Edita el archivo `backend/.env`:
```env
# Inserta tu clave de API si deseas llamadas en vivo con LLM
GEMINI_API_KEY=tu_clave_gemini_aqui
# Opcional si prefieres OpenAI:
OPENAI_API_KEY=tu_clave_openai_aqui
```

### 4. Ejecución del Servidor FastAPI
```bash
cd backend
python -m uvicorn app.main:app --reload --port 8000
```
La documentación interactiva Swagger estará disponible en:
- `http://localhost:8000/docs`
- `http://localhost:8000/redoc`

### 5. Ejecución de las Pruebas Unitarias e Integración
```bash
cd backend
python test_flow.py          # Pruebas del motor de reglas y exportaciones
python test_api_upload.py    # Pruebas de la API REST y subida de archivos
```
