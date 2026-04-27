from __future__ import annotations

import logging
import json
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import (
    http_exception_handler as default_http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from .extension_routes import router as extension_router
from .fetch_vacancy import text_from_url
from .llm import GEMINI_QUOTA_USER_MESSAGE, get_cv_llm_backend, is_quota_or_rate_limit
from .matcher import load_all_cvs, pick_best_cv
from .models import CvDocument, MatchResponse, TailorRequest, TailorResponse, TechSkills, VacancyRequest

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="CV Generator API", version="0.1.0")


@app.exception_handler(HTTPException)
async def _log_http_exception(request: Request, exc: HTTPException):
    if exc.status_code >= 400:
        logger.warning(
            "HTTP %s %s — detail=%s",
            exc.status_code,
            request.url.path,
            exc.detail,
        )
    return await default_http_exception_handler(request, exc)


@app.exception_handler(RequestValidationError)
async def _log_validation(request: Request, exc: RequestValidationError):
    logger.warning(
        "Validation error %s — body no coincide con el schema: %s",
        request.url.path,
        exc.errors(),
    )
    return await request_validation_exception_handler(request, exc)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:3000", "http://localhost:3000"],
    # Next en LAN + MV3 chrome-extension:// + HTTPS de portales (Indeed, LinkedIn, etc.):
    # un content script que hace fetch() hereda el Origin de la página, no el de la extensión.
    allow_origin_regex=(
        r"^http://[^/]+:3000$"
        r"|^chrome-extension://.+$"
        r"|^https://.+$"
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(extension_router)

def _kb_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "knowledge_base"


def _kb_path_for(cv_id: str) -> Path:
    safe = cv_id.strip()
    if not safe or "/" in safe or "\\" in safe or ".." in safe:
        raise HTTPException(status_code=400, detail="cv_id inválido")
    return _kb_dir() / f"{safe}.json"


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/cvs", response_model=list[CvDocument])
def list_cvs() -> list[CvDocument]:
    return load_all_cvs()


@app.get("/v1/cvs/{cv_id}", response_model=CvDocument)
def get_cv(cv_id: str) -> CvDocument:
    p = _kb_path_for(cv_id)
    if not p.exists():
        raise HTTPException(status_code=404, detail="CV no encontrado")
    data = json.loads(p.read_text(encoding="utf-8"))
    return CvDocument.model_validate(data)


@app.put("/v1/cvs/{cv_id}/tech-skills", response_model=CvDocument)
def put_tech_skills(cv_id: str, skills: TechSkills) -> CvDocument:
    p = _kb_path_for(cv_id)
    if not p.exists():
        raise HTTPException(status_code=404, detail="CV no encontrado")

    raw = json.loads(p.read_text(encoding="utf-8"))
    raw["tech_skills"] = skills.model_dump()
    p.write_text(
        json.dumps(raw, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return CvDocument.model_validate(raw)


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


@app.post("/v1/tailor", response_model=TailorResponse)
async def tailor_cv(body: TailorRequest) -> TailorResponse:
    vacancy_parts: list[str] = []
    if body.vacancy_text and body.vacancy_text.strip():
        vacancy_parts.append(body.vacancy_text.strip())

    if body.vacancy_url and body.vacancy_url.strip():
        try:
            fetched = await text_from_url(body.vacancy_url.strip())
            vacancy_parts.append(fetched)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"No se pudo leer la URL: {e!s}") from e

    instr = (body.custom_instructions or "").strip()
    if instr:
        vacancy_parts.append("INSTRUCCIONES DEL USUARIO (aplica sobre el CV base):\n" + instr)

    vacancy_blob = "\n\n".join(vacancy_parts).strip()
    if not vacancy_blob:
        raise HTTPException(
            status_code=400,
            detail="Indica texto de vacante, una URL, o instrucciones para modificar el CV.",
        )

    try:
        llm = get_cv_llm_backend()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    if not llm.is_configured():
        raise HTTPException(
            status_code=400,
            detail="Configura credenciales LLM (p. ej. GEMINI_API_KEY si LLM_PROVIDER=gemini).",
        )

    try:
        cv_out, match_percent, reason, notes_to_verify, gaps, reinforcement_plan, meta = (
            await llm.tailor_cv(vacancy_blob, body.cv)
        )
    except Exception as e:
        if is_quota_or_rate_limit(e):
            logger.warning("[/v1/tailor] Cuota Gemini (429): %s", str(e)[:400])
            raise HTTPException(status_code=429, detail=GEMINI_QUOTA_USER_MESSAGE) from e
        raise
    meta.update({"vacancy_chars": len(vacancy_blob), "flow": "tailor"})

    return TailorResponse(
        cv=cv_out,
        match_percent=match_percent,
        reason=reason,
        notes_to_verify=notes_to_verify,
        gaps=gaps,
        reinforcement_plan=reinforcement_plan,
        raw_meta=meta,
    )
