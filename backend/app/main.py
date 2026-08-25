from __future__ import annotations

from contextlib import contextmanager
import fcntl
import logging
import json
import os
from pathlib import Path

from pydantic import BaseModel
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import (
    http_exception_handler as default_http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from .cv_history import get_generated_cv, list_generated_summaries
from .extension_routes import router as extension_router
from .fetch_vacancy import text_from_url
from .llm import GEMINI_QUOTA_USER_MESSAGE, get_cv_llm_backend, is_quota_or_rate_limit
from .matcher import load_all_cvs
from .vacancy_pipeline import (
    vacancy_blob_from_text_and_url,
    run_full_optimize_pipeline,
    run_match_for_blob,
)
from .compact_master import export_ollama_profile, load_ollama_profile
from .career_kb import (
    ExperienceEditItem,
    ExperienceEditsIn,
    UserValidationIn,
    apply_experience_edits,
    apply_user_validation,
    sync_skill_catalog,
)
from .models import (
    CvDocument,
    HistoryDetailOut,
    HistoryListResponse,
    HistorySummaryOut,
    MasterSkills,
    MatchResponse,
    TailorRequest,
    TailorResponse,
    TechSkills,
    VacancyRequest,
)

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


def _master_profile_path() -> Path:
    return _kb_dir() / "master_profile.json"


@contextmanager
def _locked_master():
    lock_path = _kb_dir() / ".master_profile.lock"
    with open(lock_path, "a+", encoding="utf-8") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def _load_master_profile() -> dict:
    p = _master_profile_path()
    if not p.exists():
        raise HTTPException(status_code=404, detail="Perfil maestro no encontrado")
    return json.loads(p.read_text(encoding="utf-8"))


def _save_master_profile(raw: dict) -> None:
    path = _master_profile_path()
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(raw, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, path)
    export_ollama_profile(raw)


def _skills_empty(skills: Optional[dict]) -> bool:
    if not skills:
        return True
    return all(not (skills.get(key) or []) for key in skills)


def _apply_skills(raw: dict, skills: MasterSkills) -> None:
    dumped = skills.model_dump()
    existing = raw.get("skills") or {}
    if _skills_empty(dumped) and not _skills_empty(existing):
        raise HTTPException(
            status_code=400,
            detail="Rechazado: el payload de skills está vacío y borraría el perfil.",
        )
    raw["skills"] = dumped
    sync_skill_catalog(raw, dumped)


class MasterProfilePatchIn(BaseModel):
    skills: Optional[MasterSkills] = None
    experience: Optional[List[ExperienceEditItem]] = None


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


@app.get("/v1/master-profile")
def get_master_profile() -> dict:
    return _load_master_profile()


@app.get("/v1/master-profile/ollama")
def get_ollama_profile() -> dict:
    """Perfil compacto que consume el modelo Ollama cv-optimizer."""
    return load_ollama_profile()


@app.put("/v1/master-profile/skills")
def put_master_skills(skills: MasterSkills) -> dict:
    with _locked_master():
        raw = _load_master_profile()
        _apply_skills(raw, skills)
        _save_master_profile(raw)
        return raw


@app.put("/v1/master-profile/validations")
def put_master_validation(body: UserValidationIn) -> dict:
    with _locked_master():
        raw = _load_master_profile()
        apply_user_validation(raw, body.field.strip(), body.resolvedValue.strip())
        _save_master_profile(raw)
        return raw


@app.put("/v1/master-profile/experience")
def put_master_experience(body: ExperienceEditsIn) -> dict:
    if not body.items:
        raise HTTPException(status_code=400, detail="items vacío")
    with _locked_master():
        raw = _load_master_profile()
        apply_experience_edits(raw, body.items)
        _save_master_profile(raw)
        return raw


@app.put("/v1/master-profile")
def put_master_profile_patch(body: MasterProfilePatchIn) -> dict:
    if body.skills is None and not body.experience:
        raise HTTPException(status_code=400, detail="Nada que guardar")
    with _locked_master():
        raw = _load_master_profile()
        if body.experience:
            apply_experience_edits(raw, body.experience)
        if body.skills is not None:
            _apply_skills(raw, body.skills)
        _save_master_profile(raw)
        return raw


@app.post("/v1/optimize", response_model=TailorResponse)
async def optimize_cv(body: VacancyRequest) -> TailorResponse:
    text = (body.vacancy_text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Pega el texto de la vacante.")
    try:
        _, tailored = await run_full_optimize_pipeline(text, None)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        if is_quota_or_rate_limit(e):
            logger.warning("[/v1/optimize] Cuota LLM (429): %s", str(e)[:400])
            raise HTTPException(status_code=429, detail=GEMINI_QUOTA_USER_MESSAGE) from e
        raise
    return tailored


@app.post("/v1/match", response_model=MatchResponse)
async def match_vacancy(body: VacancyRequest) -> MatchResponse:
    try:
        vacancy_blob = await vacancy_blob_from_text_and_url(
            body.vacancy_text or "",
            body.vacancy_url,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"No se pudo leer la URL: {e!s}") from e
    return await run_match_for_blob(vacancy_blob)


@app.get("/v1/history", response_model=HistoryListResponse)
async def list_cv_history() -> HistoryListResponse:
    return HistoryListResponse(
        items=[HistorySummaryOut.model_validate(i.model_dump()) for i in list_generated_summaries()]
    )


@app.get("/v1/history/{item_id}", response_model=HistoryDetailOut)
async def get_cv_history_item(item_id: str) -> HistoryDetailOut:
    record = get_generated_cv(item_id)
    if record is None:
        raise HTTPException(status_code=404, detail="No hay un CV guardado con ese id.")
    return HistoryDetailOut(
        id=record.id,
        vacancy_title=record.vacancy_title,
        vacancy_text=record.vacancy_text,
        created_at=record.created_at,
        match_percent=record.match_percent,
        reason=record.reason,
        cv=record.cv,
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
