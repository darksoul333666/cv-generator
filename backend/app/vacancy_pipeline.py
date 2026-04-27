from __future__ import annotations

import logging
from typing import Optional, Tuple

from .cv_optimize_prompt import OPTIMIZE_ATS_INSTRUCTIONS
from .fetch_vacancy import text_from_url
from .llm import get_cv_llm_backend
from .llm.settings import tailor_missing_key_message
from .matcher import load_all_cvs, pick_best_cv
from .models import CvDocument, MatchResponse, TailorResponse

logger = logging.getLogger(__name__)


async def _vacancy_blob_from_text_and_url(
    vacancy_text: str,
    vacancy_url: Optional[str],
) -> str:
    vacancy_parts: list[str] = []
    if vacancy_text and vacancy_text.strip():
        vacancy_parts.append(vacancy_text.strip())
    if vacancy_url and vacancy_url.strip():
        fetched = await text_from_url(vacancy_url.strip())
        vacancy_parts.append(fetched)
    blob = "\n\n".join(vacancy_parts).strip()
    if not blob:
        raise ValueError("Indica texto de la vacante o una URL válida.")
    return blob


async def run_match_for_blob(vacancy_blob: str) -> MatchResponse:
    cvs = load_all_cvs()
    raw_meta: dict = {
        "vacancy_chars": len(vacancy_blob),
        "profiles_loaded": len(cvs),
    }

    try:
        llm = get_cv_llm_backend()
    except ValueError as e:
        logger.warning("LLM no disponible (config): %s", e)
        chosen, score, reason = pick_best_cv(vacancy_blob, cvs)
        raw_meta["matcher"] = "keywords"
        raw_meta["llm_error"] = str(e)[:300]
    else:
        if llm.is_configured():
            try:
                chosen, score, reason = await llm.pick_best_cv(vacancy_blob, cvs)
                raw_meta["matcher"] = "llm"
                raw_meta["llm_provider"] = llm.provider_id
                raw_meta["llm_model"] = llm.model_id
            except Exception as e:
                logger.warning("LLM matcher no disponible o error: %s", e, exc_info=True)
                chosen, score, reason = pick_best_cv(vacancy_blob, cvs)
                raw_meta["matcher"] = "keywords_fallback"
                raw_meta["llm_error"] = str(e)[:300]
        else:
            chosen, score, reason = pick_best_cv(vacancy_blob, cvs)
            raw_meta["matcher"] = "keywords"

    excerpt = vacancy_blob[:1200] + ("…" if len(vacancy_blob) > 1200 else "")

    return MatchResponse(
        chosen_cv_id=chosen.id,
        match_score=score,
        match_reason=reason,
        cv=chosen,
        vacancy_excerpt=excerpt,
        raw_meta=raw_meta,
    )


async def run_tailor_optimize(vacancy_blob: str, base_cv: CvDocument) -> TailorResponse:
    llm = get_cv_llm_backend()
    if not llm.is_configured():
        raise RuntimeError(tailor_missing_key_message())

    tailor_context = (
        vacancy_blob
        + "\n\nINSTRUCCIONES DEL SISTEMA (optimización ATS):\n"
        + OPTIMIZE_ATS_INSTRUCTIONS
    )
    cv_out, match_percent, reason, notes_to_verify, gaps, reinforcement_plan, meta = (
        await llm.tailor_cv(tailor_context, base_cv)
    )
    meta.update({"vacancy_chars": len(tailor_context), "flow": "optimize"})

    return TailorResponse(
        cv=cv_out,
        match_percent=match_percent,
        reason=reason,
        notes_to_verify=notes_to_verify,
        gaps=gaps,
        reinforcement_plan=reinforcement_plan,
        raw_meta=meta,
    )


async def run_full_optimize_pipeline(
    vacancy_text: str,
    vacancy_url: Optional[str],
) -> Tuple[MatchResponse, TailorResponse]:
    """Mismo flujo que la pestaña «Optimizar CV»: match + tailor con instrucciones ATS."""
    blob = await _vacancy_blob_from_text_and_url(vacancy_text, vacancy_url)
    match_resp = await run_match_for_blob(blob)
    tailored = await run_tailor_optimize(blob, match_resp.cv)
    return match_resp, tailored
