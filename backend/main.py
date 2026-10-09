"""
Punto de entrada ASGI para Vercel Serverless y despliegues en produccion.
Expone la aplicacion FastAPI 'app' configurada en app.main.
"""
from app.main import app

__all__ = ["app"]
