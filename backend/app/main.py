from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .fetch_vacancy import text_from_url
from .gemini_match import pick_best_cv_gemini
from .matcher import load_all_cvs, pick_best_cv
from .models import MatchResponse, VacancyRequest

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="CV Generator API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:3000", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/match", response_model=MatchResponse)
async def match_vacancy(body: VacancyRequest) -> MatchResponse:
    vacancy_parts: list[str] = []
    if body.vacancy_text and body.vacancy_text.strip():
        vacancy_parts.append(body.vacancy_text.strip())

    if body.vacancy_url and body.vacancy_url.strip():
        try:
            fetched = await text_from_url(body.vacancy_url.strip())
            vacancy_parts.append(fetched)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"No se pudo leer la URL: {e!s}") from e

    vacancy_blob = "\n\n".join(vacancy_parts).strip()
    if not vacancy_blob:
        raise HTTPException(
            status_code=400,
            detail="Indica texto de la vacante o una URL válida.",
        )

    cvs = load_all_cvs()
    raw_meta: dict = {
        "vacancy_chars": len(vacancy_blob),
        "profiles_loaded": len(cvs),
    }

    if os.environ.get("GEMINI_API_KEY", "").strip():
        try:
            chosen, score, reason = await pick_best_cv_gemini(vacancy_blob, cvs)
            raw_meta["matcher"] = "gemini"
            raw_meta["gemini_model"] = (
                os.environ.get("GEMINI_MODEL") or "gemini-2.0-flash"
            ).strip()
        except Exception as e:
            logger.warning("Gemini no disponible o error: %s", e, exc_info=True)
            chosen, score, reason = pick_best_cv(vacancy_blob, cvs)
            raw_meta["matcher"] = "keywords_fallback"
            raw_meta["gemini_error"] = str(e)[:300]
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
