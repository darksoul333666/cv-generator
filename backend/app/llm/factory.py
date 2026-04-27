"""Resuelve el backend LLM según ``LLM_PROVIDER``. Añade ramas aquí al incorporar nuevos proveedores."""

from __future__ import annotations

from typing import Optional

from .gemini_backend import GeminiCvLlmBackend
from .protocol import CvLlmBackend
from .settings import get_llm_provider_id

_cached: Optional[CvLlmBackend] = None


def get_cv_llm_backend() -> CvLlmBackend:
    """
    Singleton por proceso. Cambia ``LLM_PROVIDER`` / credenciales y reinicia uvicorn para aplicar.
    """
    global _cached
    if _cached is None:
        _cached = _build_backend()
    return _cached


def reset_cv_llm_backend_cache() -> None:
    """Tests o recarga manual del backend."""
    global _cached
    _cached = None


def _build_backend() -> CvLlmBackend:
    pid = get_llm_provider_id()
    if pid == "gemini":
        return GeminiCvLlmBackend.from_env()
    raise ValueError(
        f"LLM_PROVIDER={pid!r} no está soportado. Valores actuales: gemini. "
        f"Implementa un backend en app/llm/ y regístralo en app/llm/factory.py."
    )
