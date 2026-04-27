"""Errores y mensajes comunes para cualquier proveedor LLM."""

from __future__ import annotations


def is_quota_or_rate_limit(exc: BaseException) -> bool:
    try:
        from google.api_core import exceptions as gexc

        if isinstance(exc, (gexc.ResourceExhausted, gexc.TooManyRequests)):
            return True
    except Exception:
        pass
    s = str(exc).lower()
    return (
        " 429 " in f" {s} "
        or "quota exceeded" in s
        or "exceeded your current quota" in s
        or "rate limit" in s
        or "resource exhausted" in s
    )


LLM_QUOTA_USER_MESSAGE = (
    "Cuota o límite de uso del proveedor de IA agotado (peticiones por minuto/día o tokens). "
    "Espera el tiempo que indique el error, cambia LLM_PROVIDER / LLM_MODEL o las variables de API "
    "del proveedor en backend/.env. Si usas Gemini, revisa GEMINI_MODEL y los límites en "
    "https://ai.google.dev/gemini-api/docs/rate-limits"
)

# Alias histórico (extension_routes, main)
GEMINI_QUOTA_USER_MESSAGE = LLM_QUOTA_USER_MESSAGE
