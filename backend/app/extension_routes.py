from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException

from .extension_cache import append_job, get_job, list_jobs_summaries_newest_first
from .llm import GEMINI_QUOTA_USER_MESSAGE, is_quota_or_rate_limit
from .llm.settings import tailor_missing_key_message
from .models import (
    ExtensionJobListResponse,
    ExtensionJobSummaryOut,
    ExtensionOptimizeResponse,
    ExtensionVacancyIn,
)
from .vacancy_pipeline import run_full_optimize_pipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/extension", tags=["extension"])


def _derive_vacancy_title(text: str, explicit: Optional[str]) -> str:
    if explicit and explicit.strip():
        return explicit.strip()[:200]
    first = (text or "").strip().split("\n")[0].strip()
    if len(first) > 160:
        first = first[:157] + "…"
    return first or "Vacante sin título"


@router.post("/optimize", response_model=ExtensionOptimizeResponse)
async def extension_optimize(body: ExtensionVacancyIn) -> ExtensionOptimizeResponse:
    """
    Igual que «Optimizar CV» en la web: match entre perfiles + tailor ATS.
    Solo usa la descripción `vacancy_text` enviada por la extensión (sin fetch de URL).
    El resultado se guarda en caché (memoria + archivo JSON bajo `backend/.cache/`).
    """
    if not body.vacancy_text or not body.vacancy_text.strip():
        raise HTTPException(
            status_code=400,
            detail="Envía vacancy_text con la descripción completa de la vacante.",
        )

    try:
        match_resp, tailor_resp = await run_full_optimize_pipeline(
            body.vacancy_text.strip(),
            None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        if tailor_missing_key_message() in str(e):
            raise HTTPException(
                status_code=400,
                detail="Configura credenciales LLM (p. ej. GEMINI_API_KEY si LLM_PROVIDER=gemini).",
            ) from e
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        if is_quota_or_rate_limit(e):
            logger.warning(
                "[extension/optimize] Cuota Gemini (429): %s",
                str(e)[:400],
            )
            raise HTTPException(status_code=429, detail=GEMINI_QUOTA_USER_MESSAGE) from e
        logger.exception("extension optimize failed")
        raise HTTPException(status_code=400, detail=f"No se pudo generar el CV: {e!s}") from e

    title = _derive_vacancy_title(body.vacancy_text or "", body.vacancy_title)
    site = (body.source_site or "extension").strip().lower() or "extension"

    record = append_job(
        vacancy_title=title,
        source_site=site,
        match=match_resp,
        tailor=tailor_resp,
    )

    return ExtensionOptimizeResponse(
        id=record.id,
        vacancy_title=record.vacancy_title,
        source_site=record.source_site,
        created_at=record.created_at,
        match=record.match,
        tailor=record.tailor,
    )


@router.get("/jobs", response_model=ExtensionJobListResponse)
def extension_list_jobs() -> ExtensionJobListResponse:
    summaries = list_jobs_summaries_newest_first()
    return ExtensionJobListResponse(
        jobs=[
            ExtensionJobSummaryOut(
                id=s.id,
                vacancy_title=s.vacancy_title,
                source_site=s.source_site,
                created_at=s.created_at,
                chosen_cv_id=s.chosen_cv_id,
                match_score=s.match_score,
                tailor_match_percent=s.tailor_match_percent,
            )
            for s in summaries
        ]
    )


@router.get("/jobs/{job_id}", response_model=ExtensionOptimizeResponse)
def extension_get_job(job_id: str) -> ExtensionOptimizeResponse:
    record = get_job(job_id)
    if not record:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado o expirado de la caché.")
    return ExtensionOptimizeResponse(
        id=record.id,
        vacancy_title=record.vacancy_title,
        source_site=record.source_site,
        created_at=record.created_at,
        match=record.match,
        tailor=record.tailor,
    )
