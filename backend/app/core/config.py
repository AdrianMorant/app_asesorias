import os
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables desde .env
env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)

class Settings:
    PROJECT_NAME: str = "Asesoría IA - Suite Contable y Fiscal"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Entorno
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    
    # Base de datos SQLite async
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "sqlite+aiosqlite:///./invoices_accounting.db"
    )
    
    # Directorios de subida y almacenamiento organizado
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    UPLOAD_DIR: Path = BASE_DIR / os.getenv("UPLOAD_DIR", "uploads")
    STORAGE_DIR: Path = BASE_DIR / os.getenv("STORAGE_DIR", "storage")
    
    # LLM Settings
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", os.getenv("DEFAULT_LLM_PROVIDER", "openai")).lower().strip()
    DEFAULT_LLM_PROVIDER: str = LLM_PROVIDER
    
    # Modelos recomendados
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

settings = Settings()

# Crear directorios de trabajo si no existen
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
