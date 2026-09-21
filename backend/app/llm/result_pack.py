"""Empaqueta JSON del optimizer (Gemini, OpenAI, etc.) al CvDocument."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from ..models import CvDocument
from .ollama_backend import _ollama_result_to_cv


def pack_optimizer(
    data: dict,
    cv: CvDocument,
    master: dict,
    locale: str,
    vacancy_text: str,
    *,
    provider: str,
    model: str,
    attempts: int = 1,
    extra_meta: Optional[Dict[str, Any]] = None,
) -> Tuple[CvDocument, float, str, List[str], List[str], List[str], Dict[str, Any]]:
    cv_out = _ollama_result_to_cv(data, cv, master, locale, vacancy_text)
    match_percent = float(data.get("match_score") or 0)
    if match_percent <= 10:
        match_percent *= 10
    match_percent = max(0.0, min(100.0, match_percent))
    reason = str(data.get("target_role") or cv_out.title or f"CV optimizado con {provider}")
    raw_meta: Dict[str, Any] = {
        "llm_provider": provider,
        "llm_model": model,
        "source": "master_profile",
        "keywords": data.get("keywords") or [],
        "attempts": attempts,
        "locale": locale,
    }
    if extra_meta:
        raw_meta.update(extra_meta)
    return cv_out, match_percent, reason, [], [], [], raw_meta


def align_batch_items(raw_items: list[dict], n: int) -> list[Optional[dict]]:
    aligned: list[Optional[dict]] = [None] * n
    leftover: list[dict] = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        try:
            slot = int(raw.get("slot") or 0)
        except (TypeError, ValueError):
            slot = 0
        if 1 <= slot <= n and aligned[slot - 1] is None:
            aligned[slot - 1] = raw
        else:
            leftover.append(raw)
    for i in range(n):
        if aligned[i] is None and leftover:
            aligned[i] = leftover.pop(0)
    return aligned
