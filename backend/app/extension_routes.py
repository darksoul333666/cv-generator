from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from .cv_queue import enqueue_optimize
from .extension_cache import get_job, list_jobs_summaries_newest_first
from .models import (
    ExtensionJobListResponse,
    ExtensionJobSummaryOut,
    ExtensionOptimizeResponse,
    ExtensionVacancyIn,
)

router = APIRouter(prefix="/v1/extension", tags=["extension"])


@router.post("/optimize")
async def extension_optimize(body: ExtensionVacancyIn) -> JSONResponse:
    """Encola la vacante. El CV se genera en lote (1 petición Gemini), no aquí."""
    if not body.vacancy_text or not body.vacancy_text.strip():
        raise HTTPException(
            status_code=400,
            detail="Envía vacancy_text con la descripción completa de la vacante.",
        )

    try:
        queued = enqueue_optimize(body.vacancy_text.strip())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=429, detail=str(e)) from e

    return JSONResponse(
        status_code=202,
        content={
            "id": queued.id,
            "message": queued.message,
            "queued": queued.queued,
            "generating": queued.generating,
            "batch_size": queued.batch_size,
        },
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
