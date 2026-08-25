"""Parseo robusto de respuestas JSON del LLM (cercas markdown, substring, texto vacío)."""

from __future__ import annotations

import json
import re
from typing import Any, Optional


def strip_think_blocks(text: str) -> str:
    return re.sub(r"<think>[\s\S]*?</think>", "", text or "", flags=re.IGNORECASE).strip()


def strip_json_fence(text: str) -> str:
    text = strip_think_blocks(text or "").strip()
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


def close_truncated_json(text: str) -> str:
    """Cierra comillas, arrays y objetos si el modelo cortó el JSON a mitad."""
    s = text.strip()
    i = s.find("{")
    if i < 0:
        return s
    s = s[i:]
    stack: list[str] = []
    in_str = False
    escape = False
    for ch in s:
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            stack.append("}")
        elif ch == "[":
            stack.append("]")
        elif ch in "}]" and stack and stack[-1] == ch:
            stack.pop()
    if in_str:
        s += '"'
    s = s.rstrip()
    if s.endswith(","):
        s = s[:-1]
    while stack:
        s += stack.pop()
    return s


def parse_json_object(raw: str, *, context: str = "modelo") -> dict:
    """
    Parsea un único objeto JSON. Reintenta con el subcadena entre el primer { y el último }.
    Si el modelo cortó la salida, cierra brackets y comillas.
    """
    text = strip_json_fence(raw).strip()
    if not text:
        raise ValueError(
            f"Respuesta vacía del {context} (¿max_output_tokens insuficiente o contenido bloqueado?)."
        )
    candidates = [text]
    i = text.find("{")
    j = text.rfind("}")
    if i >= 0 and j > i:
        candidates.append(text[i : j + 1])
    if i >= 0:
        candidates.append(close_truncated_json(text[i:]))

    last_err: Optional[json.JSONDecodeError] = None
    for blob in candidates:
        try:
            data = json.loads(blob)
        except json.JSONDecodeError as e:
            last_err = e
            continue
        if isinstance(data, dict):
            return data
        last_err = None
        raise ValueError(f"Se esperaba un objeto JSON, no {type(data).__name__}")
    raise ValueError(
        f"JSON inválido del {context}: {last_err}. Primeros 200 caracteres: {text[:200]!r}"
    )
