"""Parseo robusto de respuestas JSON del LLM (cercas markdown, substring, texto vacío)."""

from __future__ import annotations

import json
import re
from typing import Any


def strip_json_fence(text: str) -> str:
    text = (text or "").strip()
    m = re.match(r"^```(?:json)?\s*(.*?)```\s*$", text, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return text


def response_text(response: Any) -> str:
    """Obtiene texto de GenerateContentResponse aunque .text venga vacío."""
    if response is None:
        return ""
    t = getattr(response, "text", None)
    if t and str(t).strip():
        return str(t)
    try:
        parts: list[str] = []
        for c in response.candidates or []:
            content = getattr(c, "content", None)
            if not content:
                continue
            for p in getattr(content, "parts", None) or []:
                pt = getattr(p, "text", None)
                if pt:
                    parts.append(pt)
        return "".join(parts)
    except Exception:
        return ""


def parse_json_object(raw: str, *, context: str = "modelo") -> dict:
    """
    Parsea un único objeto JSON. Reintenta con el subcadena entre el primer { y el último }.
    """
    text = strip_json_fence(raw).strip()
    if not text:
        raise ValueError(
            f"Respuesta vacía del {context} (¿max_output_tokens insuficiente o contenido bloqueado?)."
        )
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
        raise ValueError(f"Se esperaba un objeto JSON, no {type(data).__name__}")
    except json.JSONDecodeError as e:
        i = text.find("{")
        j = text.rfind("}")
        if i >= 0 and j > i:
            try:
                data = json.loads(text[i : j + 1])
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                pass
        raise ValueError(
            f"JSON inválido del {context}: {e}. Primeros 200 caracteres: {text[:200]!r}"
        ) from e
