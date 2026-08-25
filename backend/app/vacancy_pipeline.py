from __future__ import annotations

from typing import Optional, Tuple

from .cv_history import append_generated_cv, vacancy_title_from_text
from .fetch_vacancy import text_from_url
from .llm import get_cv_llm_backend
from .llm.settings import tailor_missing_key_message
from .matcher import load_all_cvs, pick_best_cv
from .models import CvDocument, MatchResponse, TailorResponse


async def vacancy_blob_from_text_and_url(
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
    """Elige plantilla por keywords. Educación/certs y el CV salen del master; no gasta un round-trip LLM."""
    cvs = load_all_cvs()
    chosen, score, reason = pick_best_cv(vacancy_blob, cvs)
    excerpt = vacancy_blob[:1200] + ("…" if len(vacancy_blob) > 1200 else "")
    return MatchResponse(
        chosen_cv_id=chosen.id,
        match_score=score,
        match_reason=reason,
        cv=chosen,
        vacancy_excerpt=excerpt,
        raw_meta={
            "vacancy_chars": len(vacancy_blob),
            "profiles_loaded": len(cvs),
            "matcher": "keywords",
        },
    )


async def run_tailor_optimize(vacancy_blob: str, base_cv: CvDocument) -> TailorResponse:
    llm = get_cv_llm_backend()
    if not llm.is_configured():
        raise RuntimeError(tailor_missing_key_message())

    cv_out, match_percent, reason, notes_to_verify, gaps, reinforcement_plan, meta = (
        await llm.tailor_cv(vacancy_blob, base_cv)
    )
    meta.update({"vacancy_chars": len(vacancy_blob), "flow": "optimize"})

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
    """Match por keywords + tailor con el perfil maestro. Educación y certs se copian del master."""
    blob = await vacancy_blob_from_text_and_url(vacancy_text, vacancy_url)
    match_resp = await run_match_for_blob(blob)
    tailored = await run_tailor_optimize(blob, match_resp.cv)
    record = append_generated_cv(
        vacancy_title=vacancy_title_from_text(blob),
        vacancy_text=blob,
        tailor=tailored,
    )
    tailored.saved_id = record.id
    return match_resp, tailored
