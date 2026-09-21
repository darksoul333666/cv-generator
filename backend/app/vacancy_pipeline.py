from __future__ import annotations

import logging
from typing import Optional, Tuple

from .cv_history import append_generated_cv, vacancy_title_from_text
from .fetch_vacancy import text_from_url
from .llm import get_cv_llm_backend
from .llm.settings import tailor_missing_key_message
from .matcher import load_all_cvs, pick_best_cv
from .models import CvDocument, MatchResponse, TailorResponse
from .vacancy_clean import parse_pasted_vacancy

logger = logging.getLogger(__name__)


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
    vacancy_url: Optional[str] = None,
    company_name: Optional[str] = None,
    item_id: Optional[str] = None,
) -> Tuple[MatchResponse, TailorResponse]:
    """Match por keywords + tailor. Empresa y URL no entran al modelo: solo historial local."""
    parsed = parse_pasted_vacancy(vacancy_text or "")
    blob = (parsed["text"] or "").strip()
    if not blob:
        raise ValueError("Pega el texto de la vacante.")
    stored_url = (vacancy_url or parsed["url"] or "").strip() or None
    company = (company_name or parsed["company"] or "").strip()
    match_resp = await run_match_for_blob(blob)
    tailored = await run_tailor_optimize(blob, match_resp.cv)
    record = append_generated_cv(
        vacancy_title=vacancy_title_from_text(blob),
        vacancy_text=blob,
        tailor=tailored,
        company_name=company,
        vacancy_url=stored_url,
        item_id=item_id,
    )
    tailored.saved_id = record.id
    tailored.cv_name = record.cv_name
    tailored.company_name = record.company_name or None
    tailored.vacancy_url = record.vacancy_url
    return match_resp, tailored


async def run_full_optimize_batch(
    jobs: list[tuple[str, str, Optional[str], str]],
) -> list[tuple[str, TailorResponse]]:
    """
    Match local por vacante + una llamada LLM para todo el lote.
    Cada ítem es (item_id, vacancy_text, vacancy_url, company_name).
    """
    if not jobs:
        return []
    llm = get_cv_llm_backend()
    if not llm.is_configured():
        raise RuntimeError(tailor_missing_key_message())

    prepared: list[tuple[str, str, Optional[str], str, MatchResponse]] = []
    pairs: list[tuple[str, CvDocument]] = []
    for item_id, vacancy_text, vacancy_url, company_name in jobs:
        blob = (vacancy_text or "").strip()
        if not blob:
            raise ValueError("Hay una vacante sin texto en el lote.")
        match_resp = await run_match_for_blob(blob)
        prepared.append((item_id, blob, vacancy_url, company_name, match_resp))
        pairs.append((blob, match_resp.cv))

    logger.info(
        "[optimize] lote n=%s provider=%s model=%s (una llamada HTTP)",
        len(pairs),
        llm.provider_id,
        llm.model_id,
    )
    packed_list = await llm.tailor_cv_batch(pairs)
    if len(packed_list) != len(jobs):
        raise RuntimeError(
            f"El modelo devolvió {len(packed_list)} CVs y el lote tenía {len(jobs)}."
        )

    out: list[tuple[str, TailorResponse]] = []
    for (item_id, blob, vacancy_url, company_name, match_resp), packed in zip(
        prepared, packed_list
    ):
        cv_out, match_percent, reason, notes_to_verify, gaps, reinforcement_plan, meta = packed
        meta.update(
            {
                "vacancy_chars": len(blob),
                "flow": "optimize_batch",
                "matcher": "keywords",
            }
        )
        tailored = TailorResponse(
            cv=cv_out,
            match_percent=match_percent,
            reason=reason,
            notes_to_verify=notes_to_verify,
            gaps=gaps,
            reinforcement_plan=reinforcement_plan,
            raw_meta=meta,
        )
        record = append_generated_cv(
            vacancy_title=vacancy_title_from_text(blob),
            vacancy_text=blob,
            tailor=tailored,
            company_name=company_name,
            vacancy_url=vacancy_url,
            item_id=item_id,
        )
        tailored.saved_id = record.id
        tailored.cv_name = record.cv_name
        tailored.company_name = record.company_name or None
        tailored.vacancy_url = record.vacancy_url
        out.append((item_id, tailored))
    return out
