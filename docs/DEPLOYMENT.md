# GUÍA DE INSTALACIÓN Y DESPLIEGUE (DEPLOYMENT GUIDE)

Esta guía detalla el procedimiento para configurar, ejecutar y desplegar KontaAI Suite en entornos de desarrollo local y producción empresarial.

---

## 1. Requisitos del Sistema
- **Sistema Operativo:** Linux (Ubuntu 22.04 LTS+, Debian 12+), macOS Sonoma+, o Windows 11 (con PowerShell o WSL2).
- **Backend:** Python 3.11 o superior.
- **Frontend:** Node.js 18.18+ (recomendado Node 20 LTS o 22) y npm 10+.
- **Persistencia:**
  - Desarrollo local: SQLite asíncrono (`aiosqlite`).
  - Producción: PostgreSQL 15+ con extensiones UUID y copias de seguridad periódicas (`pg_dump`).
- **Herramientas del Sistema:** Tesseract OCR (opcional para OCR local de respaldo) y Poppler/PyMuPDF para renderizado de páginas PDF.

---

## 2. Variables de Entorno (`.env`)
Crear un archivo `.env` en la raíz de `backend/` con las siguientes variables:

```ini
# Configuración del Servidor
PROJECT_NAME="KontaAI Suite"
VERSION="1.0.0"
ENVIRONMENT="development" # "development", "staging", "production"
DEBUG=true

# Base de Datos
DATABASE_URL="sqlite+aiosqlite:///./invoices_accounting.db"
# Para PostgreSQL en producción:
# DATABASE_URL="postgresql+asyncpg://konta_user:TuPasswordSeguro@localhost:5432/konta_db"

# Seguridad y Criptografía
SECRET_KEY="clave_secreta_para_tokens_jwt_minimo_32_caracteres"
ENCRYPTION_KEY="clave_aes_256_gcm_de_32_bytes_para_documentos"
ACCESS_TOKEN_EXPIRE_MINUTES=480

# Proveedores de Inteligencia Artificial (IDP / Multimodal)
OPENAI_API_KEY="" # Opcional: Clave sk-... de OpenAI GPT-4o-mini
GEMINI_API_KEY="" # Opcional: Clave de Google Gemini 1.5/2.0
PRIMARY_AI_PROVIDER="openai" # "openai" o "gemini"

# Almacenamiento Documental
STORAGE_BASE_PATH="storage"
MAX_UPLOAD_SIZE_MB=25
```

Y en la raíz de `frontend/` un `.env.local`:
```ini
NEXT_PUBLIC_API_URL="http://127.0.0.1:8000"
```

---

## 3. Puesta en Marcha en Desarrollo

### 3.1. Backend (FastAPI)
```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1   # En Linux/Mac: source venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
La documentación interactiva OpenAPI estará disponible en `http://127.0.0.1:8000/docs`.

### 3.2. Frontend (Next.js)
```powershell
cd frontend
npm install
npm run dev
```
La aplicación web estará disponible en `http://localhost:3000`.

---

## 4. Despliegue en Producción

### 4.1. Arquitectura Recomendada
- **Reverse Proxy:** Nginx o Cloudflare manejando terminación SSL/TLS, compresión Gzip/Brotli y cabeceras de seguridad HSTS, CSP y X-Frame-Options.
- **Backend:** Uvicorn gestionado por Gunicorn con 4 workers asíncronos (`gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker`).
- **Frontend:** Build optimizado de Next.js (`npm run build` y `npm run start` o exportación en contenedor standalone).
- **Almacenamiento:** Volumen persistente dedicado con permisos restringidos (`chmod 700`) o almacenamiento compatible S3 con cifrado del lado del servidor.

### 4.2. Estrategia de Copias de Seguridad (Backups)
1. **Base de Datos:** Volcado diario automatizado vía cron:
   ```bash
   pg_dump -U konta_user -Fc konta_db > /backups/db/konta_db_$(date +%Y%m%d_%H%M%S).dump
   ```
2. **Volumen de Documentos:** Instantáneas diarias del directorio `storage/` con retención mínima de 30 días en rotación continua.
