"""Errores y mensajes comunes para cualquier proveedor LLM."""

from __future__ import annotations


def _http_code(exc: BaseException) -> int | None:
    code = getattr(exc, "code", None)
    if isinstance(code, int):
        return code
    resp = getattr(exc, "response", None)
    if resp is not None:
        status = getattr(resp, "status_code", None)
        if isinstance(status, int):
            return status
    return None


def is_quota_or_rate_limit(exc: BaseException) -> bool:
    try:
        from google.api_core import exceptions as gexc

        if isinstance(exc, (gexc.ResourceExhausted, gexc.TooManyRequests)):
            return True
    except Exception:
        pass
    try:
        from google.genai import errors as gerr

        if isinstance(exc, gerr.APIError) and _http_code(exc) == 429:
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


def is_model_unavailable(exc: BaseException) -> bool:
    """503 / saturación del modelo. No es cuota RPM/RPD."""
    if _http_code(exc) == 503:
        return True
    s = str(exc).lower()
    return (
        " 503 " in f" {s} "
        or "unavaliable" in s
        or "unavailable" in s
        or "high demand" in s
        or "service unavailable" in s
    )


def should_backoff_gemini(exc: BaseException) -> bool:
    return is_quota_or_rate_limit(exc) or is_model_unavailable(exc)


def llm_user_message(exc: BaseException) -> str:
    if is_quota_or_rate_limit(exc):
        return LLM_QUOTA_USER_MESSAGE
    if is_model_unavailable(exc):
        return LLM_UNAVAILABLE_USER_MESSAGE
    return str(exc)


LLM_QUOTA_USER_MESSAGE = (
    "Cuota del proveedor de IA agotada (límite por minuto o por día). "
    "NO reintentes ahora: cada reintento cuenta otra petición. "
    "Espera un minuto y vuelve a generar el lote completo."
)

LLM_UNAVAILABLE_USER_MESSAGE = (
    "El modelo está saturado o no disponible (503). El lote fue 1 petición y no se generó. "
    "Espera 1–2 minutos y reencola las 5 juntas; no las generes de una en una."
)

# Alias histórico (extension_routes, main)
GEMINI_QUOTA_USER_MESSAGE = LLM_QUOTA_USER_MESSAGE
