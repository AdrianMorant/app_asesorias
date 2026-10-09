"""
Módulo de Seguridad: Limitador de Peticiones (Rate Limiter).
Proporciona control de tráfico y mitigación contra ataques de fuerza bruta y denegación de servicio (DoS).
Implementa soporte para SlowAPI si está disponible y un motor nativo deslizante en memoria (Sliding Window)
con manejo estricto por IP.
"""

import time
from collections import defaultdict
from threading import Lock
from typing import Callable, Optional, Tuple
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse

# Constantes de configuración de límites
AUTH_RATE_LIMIT_STR = "5/minute"
DOCS_RATE_LIMIT_STR = "20/minute"

AUTH_MAX_REQUESTS = 5
AUTH_WINDOW_SECONDS = 60

DOCS_MAX_REQUESTS = 20
DOCS_WINDOW_SECONDS = 60

ERROR_MESSAGE_RATE_LIMIT = "Demasiadas peticiones. Por seguridad, espera un momento antes de reintentar."


class RateLimitExceeded(Exception):
    """Excepción lanzada cuando una IP o cliente sobrepasa el cupo de peticiones permitido."""
    def __init__(
        self,
        detail: str = ERROR_MESSAGE_RATE_LIMIT,
        retry_after: int = 60,
    ):
        self.detail = detail
        self.retry_after = retry_after
        super().__init__(detail)


def get_client_ip(request: Request) -> str:
    """
    Obtiene la dirección IP real del cliente considerando proxies inversos
    (Cloudflare, Nginx, headers X-Forwarded-For y X-Real-IP).
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # El primer elemento corresponde a la IP original del cliente
        client_ip = forwarded.split(",")[0].strip()
        if client_ip:
            return client_ip

    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()

    if request.client and request.client.host:
        return request.client.host

    return "127.0.0.1"


class InMemorySlidingWindowLimiter:
    """
    Motor nativo en memoria de ventana deslizante (Sliding Window) con exclusión mutua
    thread-safe para ambientes asíncronos y multihilo.
    """
    def __init__(self):
        self._requests = defaultdict(list)
        self._lock = Lock()

    def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> Tuple[bool, int]:
        """
        Evalúa si la clave (IP + scope) puede realizar una nueva petición.
        Retorna (permitido: bool, retry_after: int en segundos).
        """
        now = time.time()
        window_start = now - window_seconds

        with self._lock:
            timestamps = self._requests[key]
            # Filtrar timestamps que cayeron fuera de la ventana
            valid_timestamps = [ts for ts in timestamps if ts > window_start]
            self._requests[key] = valid_timestamps

            if len(valid_timestamps) >= max_requests:
                oldest_in_window = valid_timestamps[0]
                retry_after = max(1, int(window_seconds - (now - oldest_in_window)))
                return False, retry_after

            # Registrar la petición actual
            self._requests[key].append(now)
            return True, 0

    def clear(self):
        """Limpia el almacén de peticiones en memoria."""
        with self._lock:
            self._requests.clear()


# Instancia singleton del limitador en memoria
in_memory_limiter = InMemorySlidingWindowLimiter()


def rate_limit(max_requests: int, window_seconds: int = 60, scope: str = "general"):
    """
    Generador de dependencias de FastAPI para aplicar rate limiting por IP.
    Uso:
        @router.post("/login", dependencies=[Depends(rate_limit(5, 60, "auth"))])
    """
    async def dependency(request: Request):
        client_ip = get_client_ip(request)
        key = f"{client_ip}:{scope}"
        allowed, retry_after = in_memory_limiter.is_allowed(key, max_requests, window_seconds)
        if not allowed:
            raise RateLimitExceeded(retry_after=retry_after)

    return dependency


# Dependencias preconfiguradas listas para usar
limit_auth = rate_limit(
    max_requests=AUTH_MAX_REQUESTS,
    window_seconds=AUTH_WINDOW_SECONDS,
    scope="auth"
)

limit_documents = rate_limit(
    max_requests=DOCS_MAX_REQUESTS,
    window_seconds=DOCS_WINDOW_SECONDS,
    scope="docs"
)


async def rate_limit_exceeded_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Manejador global de error para FastAPI que captura RateLimitExceeded
    y responde con código HTTP 429 y el payload JSON especificado.
    """
    retry_after = getattr(exc, "retry_after", 60)
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"error": ERROR_MESSAGE_RATE_LIMIT},
        headers={
            "Retry-After": str(retry_after),
            "X-RateLimit-Limit": str(getattr(exc, "limit", "N/A")),
        },
    )


# Compatibilidad opcional con slowapi si se encuentra instalado en el entorno
try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded as SlowAPIRateLimitExceeded

    limiter = Limiter(
        key_func=get_client_ip,
        default_limits=["100/minute"],
        headers_enabled=True,
    )
    has_slowapi = True
except ImportError:
    limiter = None
    SlowAPIRateLimitExceeded = RateLimitExceeded
    has_slowapi = False
