"""Variables de entorno para el proveedor LLM (sin importar backends concretos)."""

from __future__ import annotations

import os


def get_llm_provider_id() -> str:
    """Identificador del backend: p. ej. ``gemini``. Amplía en ``factory`` al añadir proveedores."""
    return (os.environ.get("LLM_PROVIDER") or "gemini").strip().lower()


def tailor_missing_key_message() -> str:
    pid = get_llm_provider_id()
    if pid == "gemini":
        return "GEMINI_API_KEY no configurada"
    return f"Faltan credenciales para LLM_PROVIDER={pid!r}. Revisa backend/.env.example."
