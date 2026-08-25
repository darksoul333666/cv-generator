from __future__ import annotations

from typing import Any, List

from pydantic import BaseModel

_GEMINI_SCHEMA_DROP = {
    "default",
    "title",
    "additionalProperties",
    "$schema",
    "$id",
    "examples",
    "const",
    "minItems",
    "maxItems",
    "minLength",
    "maxLength",
}


def gemini_response_schema(model: type[BaseModel]) -> dict:
    """JSON Schema que Gemini acepta: sin `default` ni `$ref`."""
    schema = model.model_json_schema()
    defs = schema.pop("$defs", None) or schema.pop("definitions", None) or {}
    return _strip_gemini_schema(_inline_refs(schema, defs))


def _inline_refs(node: Any, defs: dict) -> Any:
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/$defs/"):
            name = ref.split("/")[-1]
            return _inline_refs(defs.get(name) or {}, defs)
        return {k: _inline_refs(v, defs) for k, v in node.items() if k != "$ref"}
    if isinstance(node, list):
        return [_inline_refs(x, defs) for x in node]
    return node


def _strip_gemini_schema(node: Any) -> Any:
    if isinstance(node, dict):
        return {
            k: _strip_gemini_schema(v)
            for k, v in node.items()
            if k not in _GEMINI_SCHEMA_DROP
        }
    if isinstance(node, list):
        return [_strip_gemini_schema(x) for x in node]
    return node


class MatcherOut(BaseModel):
    chosen_cv_id: str
    score: float
    reason: str


class OptimizerExperienceOut(BaseModel):
    company: str
    position: str
    dates: str
    employment_type: str
    bullets: List[str]


class OptimizerOut(BaseModel):
    """Salida de cv-optimizer / perfil maestro (Gemini o Ollama)."""

    target_role: str
    match_score: float
    summary: str
    skills: List[str]
    keywords: List[str]
    experience: List[OptimizerExperienceOut]
