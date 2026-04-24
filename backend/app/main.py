from __future__ import annotations

import logging
import os
import json
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .fetch_vacancy import text_from_url
from .gemini_match import pick_best_cv_gemini
from .gemini_tailor import tailor_cv_with_gemini
from .matcher import load_all_cvs, pick_best_cv
from .models import CvDocument, MatchResponse, TailorRequest, TailorResponse, TechSkills, VacancyRequest

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="CV Generator API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:3000", "http://localhost:3000"],
    # Next en la red local (p. ej. 192.168.x.x:3000) sin esto el navegador bloquea el fetch.
    allow_origin_regex=r"^http://[^/]+:3000$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

    if not os.environ.get("GEMINI_API_KEY", "").strip():
        raise HTTPException(status_code=400, detail="Configura GEMINI_API_KEY para perfilar con IA.")

    cv_out, match_percent, reason, notes_to_verify, gaps, reinforcement_plan, meta = await tailor_cv_with_gemini(
        vacancy_blob, body.cv
    )
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
