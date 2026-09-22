from __future__ import annotations

from typing import Any, List

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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


def _first_text(*values: Any) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, list) and value:
            first = value[0]
            if isinstance(first, str) and first.strip():
                return first.strip()
            if isinstance(first, dict):
                nested = _first_text(
                    first.get("position"),
                    first.get("role"),
                    first.get("title"),
                    first.get("description"),
                )
                if nested:
                    return nested
    return ""


def _as_str_list(value: Any) -> list[str]:
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
        elif isinstance(item, dict):
            text = _first_text(
                item.get("description"),
                item.get("text"),
                item.get("bullet"),
                item.get("title"),
            )
            if text:
                out.append(text)
    return out


def normalize_experience_item(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    return {
        "company": str(raw.get("company") or "").strip(),
        "position": _first_text(
            raw.get("position"),
            raw.get("role"),
            raw.get("title"),
            raw.get("job_title"),
            raw.get("positions"),
            raw.get("roles"),
        ),
        "dates": _first_text(raw.get("dates"), raw.get("period"), raw.get("date")),
        "employment_type": _first_text(
            raw.get("employment_type"),
            raw.get("employmentType"),
            raw.get("type"),
        ),
        "bullets": _as_str_list(raw.get("bullets"))
        or _as_str_list(raw.get("achievements"))
        or _as_str_list(raw.get("responsibilities"))
        or _as_str_list(raw.get("highlights")),
    }


def normalize_optimizer_item(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    exp = raw.get("experience") or []
    if isinstance(exp, dict):
        exp = [exp]
    try:
        slot = int(raw.get("slot") or 0)
    except (TypeError, ValueError):
        slot = 0
    score = raw.get("match_score")
    if score is None:
        score = raw.get("match_percent") or 0
    return {
        "slot": slot,
        "target_role": _first_text(raw.get("target_role"), raw.get("title")),
        "match_score": score,
        "summary": str(raw.get("summary") or "").strip(),
        "skills": _as_str_list(raw.get("skills")),
        "keywords": _as_str_list(raw.get("keywords")),
        "experience": [
            normalize_experience_item(item)
            for item in exp
            if isinstance(item, dict)
        ],
    }


def normalize_optimizer_batch(raw: Any) -> dict[str, Any]:
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict):
        items = raw.get("items") or raw.get("cvs") or []
        if isinstance(items, dict):
            items = [items]
    else:
        items = []
    return {
        "items": [
            normalize_optimizer_item(item)
            for item in items
            if isinstance(item, dict)
        ]
    }


class OptimizerExperienceOut(BaseModel):
    model_config = ConfigDict(extra="ignore")

    company: str
    position: str = ""
    dates: str = ""
    employment_type: str = ""
    bullets: List[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _aliases(cls, value: Any) -> Any:
        return normalize_experience_item(value) if isinstance(value, dict) else value


class OptimizerOut(BaseModel):
    """Salida de cv-optimizer / perfil maestro (Gemini, OpenAI o Ollama)."""

    model_config = ConfigDict(extra="ignore")

    target_role: str = ""
    match_score: float = 0
    summary: str = ""
    skills: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    experience: List[OptimizerExperienceOut] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _aliases(cls, value: Any) -> Any:
        return normalize_optimizer_item(value) if isinstance(value, dict) else value

    @field_validator("match_score", mode="before")
    @classmethod
    def _score(cls, value: Any) -> float:
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0


class OptimizerBatchItemOut(OptimizerOut):
    slot: int = 0


class OptimizerBatchOut(BaseModel):
    model_config = ConfigDict(extra="ignore")

    items: List[OptimizerBatchItemOut] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _aliases(cls, value: Any) -> Any:
        return normalize_optimizer_batch(value)
