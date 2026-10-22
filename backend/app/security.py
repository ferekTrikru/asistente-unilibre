"""Protecciones de la API: límite de peticiones por IP, clave del panel del asesor y
verificación del secreto de los webhooks de Vapi. Sin dependencias externas: el límite
vive en memoria, suficiente para un solo proceso del backend."""
import hmac
import threading
import time
from collections import defaultdict, deque

from fastapi import Header, HTTPException, Request

from . import config

_WINDOW_SECONDS = 60
_hits: dict[str, deque] = defaultdict(deque)
_lock = threading.Lock()


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "desconocida"


def rate_limit(request: Request) -> None:
    """Dependencia de FastAPI: rechaza con 429 a quien supere el límite por minuto."""
    limit = config.RATE_LIMIT_PER_MINUTE
    if limit <= 0:
        return
    key = _client_ip(request)
    now = time.monotonic()
    with _lock:
        hits = _hits[key]
        while hits and now - hits[0] > _WINDOW_SECONDS:
            hits.popleft()
        if len(hits) >= limit:
            raise HTTPException(
                status_code=429,
                detail="Demasiadas solicitudes seguidas. Espera un momento e inténtalo de nuevo.",
            )
        hits.append(now)


def require_admin(x_admin_key: str = Header(default="")) -> None:
    """Dependencia de FastAPI para el panel del asesor (/admin/*)."""
    if not config.ADMIN_API_KEY:
        raise HTTPException(status_code=503, detail="Panel deshabilitado: falta ADMIN_API_KEY en el .env.")
    if not hmac.compare_digest(x_admin_key, config.ADMIN_API_KEY):
        raise HTTPException(status_code=401, detail="Clave de asesor incorrecta.")


def verify_vapi_secret(request: Request) -> None:
    if not config.VAPI_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Webhook deshabilitado: falta VAPI_WEBHOOK_SECRET.")
    received = request.headers.get("x-vapi-secret", "")
    if not hmac.compare_digest(received, config.VAPI_WEBHOOK_SECRET):
        raise HTTPException(status_code=401, detail="Secreto de webhook inválido.")


def tokens_match(received: str | None, expected: str | None) -> bool:
    return bool(received and expected) and hmac.compare_digest(received, expected)
