import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.database import init_db, AsyncSessionLocal
from app.api.v1.router import api_router
from app.core.rate_limiter import RateLimitExceeded, rate_limit_exceeded_handler
from app.core.audit_logger import get_audit_log_path, verify_audit_log_integrity
from sqlalchemy import text

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicialización en arranque: crear tablas si no existen
    await init_db()
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Sistema inteligente de extracción y contabilización de facturas para asesorías contables españolas.",
    lifespan=lifespan
)

# Manejador global de excepciones para Rate Limiting
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# Configuración de CORS para Next.js y clientes locales
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servir archivos subidos y archivados como estáticos para el visor PDF/imágenes del frontend
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.STORAGE_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")
app.mount("/storage", StaticFiles(directory=settings.STORAGE_DIR), name="storage")

# Incluir rutas API v1
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/", tags=["Salud"])
async def root():
    return {
        "status": "online",
        "app": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs_url": "/docs",
        "api_v1": settings.API_V1_STR
    }

@app.get("/health", tags=["Salud"])
async def health_check():
    """Comprobación de liveness ligera para balanceadores de carga y sondas HTTP."""
    return {
        "status": "ok",
        "app": settings.PROJECT_NAME,
        "version": settings.VERSION,
    }

@app.get("/health/detailed", tags=["Salud"])
async def detailed_health_check():
    """Diagnóstico integral de salud de subsistemas: base de datos, almacenamiento y logs."""
    components = {}
    overall_status = "HEALTHY"

    # 1. Base de datos
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        components["database"] = {"status": "OPERATIONAL", "type": "SQLAlchemy (aiosqlite / PostgreSQL ready)"}
    except Exception as exc:
        components["database"] = {"status": "DEGRADED", "error": str(exc)}
        overall_status = "DEGRADED"

    # 2. Almacenamiento y permisos de archivo
    try:
        test_file = settings.STORAGE_DIR / ".health_check_probe"
        test_file.write_text("ok", encoding="utf-8")
        test_file.unlink()
        components["filesystem"] = {"status": "OPERATIONAL", "storage_dir": str(settings.STORAGE_DIR)}
    except Exception as exc:
        components["filesystem"] = {"status": "DEGRADED", "error": str(exc)}
        overall_status = "DEGRADED"

    # 3. Log de Auditoría WORM
    audit_file = get_audit_log_path()
    if audit_file.is_file():
        is_intact, count, _ = verify_audit_log_integrity()
        components["audit_log"] = {
            "status": "OPERATIONAL",
            "chain_intact": is_intact,
            "events_recorded": count,
        }
    else:
        components["audit_log"] = {"status": "INITIALIZING", "events_recorded": 0}

    return {
        "status": overall_status,
        "version": settings.VERSION,
        "components": components,
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=True)
