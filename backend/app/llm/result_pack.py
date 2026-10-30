"""Empaqueta JSON del optimizer (Gemini, OpenAI, etc.) al CvDocument."""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

from ..compact_master import protected_terms
from ..language_guard import Translator
from ..models import CvDocument
from .cv_builder import _build_cv
from .parse_json import parse_json_object
from .prompts import build_translation_prompt

logger = logging.getLogger(__name__)


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
    translator: Optional[Translator] = None,
) -> Tuple[CvDocument, float, str, List[str], List[str], List[str], Dict[str, Any]]:
    cv_out, report = _build_cv(data, cv, master, locale, vacancy_text, translator)
    for note in report.get("notes") or []:
        logger.warning("[verify] %s", note)
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
        "verification": {k: v for k, v in report.items() if k != "notes"},
    }
    if extra_meta:
        raw_meta.update(extra_meta)
    return cv_out, match_percent, reason, list(report.get("notes") or []), [], [], raw_meta


def make_translator(
    call_json: Callable[[str], Any], master: dict
) -> Translator:
    """Envuelve una llamada JSON del proveedor como traductor por lotes.

    ``call_json(prompt)`` devuelve el texto o el dict de la respuesta. Errores y formas
    inesperadas se propagan; ``repair_language`` los captura y reporta.
    """
    protected = protected_terms(master)

    def translate(texts: list[str], locale: str) -> list[str]:
        raw = call_json(build_translation_prompt(texts, locale, protected))
        data = raw if isinstance(raw, dict) else parse_json_object(str(raw), context="translate")
        items = data.get("items") if isinstance(data, dict) else None
        if not isinstance(items, list):
            raise ValueError("la traducción no trajo items[]")
        return [str(item) for item in items]

    return translate


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
