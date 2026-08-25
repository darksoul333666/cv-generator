"""Backend Ollama: el modelo cv-optimizer consume el perfil maestro compacto."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Tuple

import httpx

from ..compact_master import load_ollama_profile, profile_for_prompt
from ..matcher import pick_best_cv
from ..models import CvDocument, ExperienceItem, StackBlock, TechSkills
from .parse_json import parse_json_object
from .prompts import build_ollama_optimizer_prompt

logger = logging.getLogger(__name__)

_DEFAULT_HOST = "http://127.0.0.1:11434"
_DEFAULT_MODEL = "cv-optimizer"


def _read_ollama_stream(response: httpx.Response, chunks: list[str]) -> tuple[Any, Any]:
    done_reason: Any = None
    eval_count: Any = None
    for line in response.iter_lines():
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        piece = ((event.get("message") or {}).get("content")) or ""
        if piece:
            chunks.append(piece)
        if event.get("done"):
            done_reason = event.get("done_reason") or True
            eval_count = event.get("eval_count")
    return done_reason, eval_count


class OllamaCvLlmBackend:
    def __init__(self, host: str, model_name: str) -> None:
        self._host = host.rstrip("/")
        self._model_name = model_name

    @classmethod
    def from_env(cls) -> OllamaCvLlmBackend:
        host = (
            os.environ.get("OLLAMA_HOST", "").strip()
            or os.environ.get("OLLAMA_BASE_URL", "").strip()
            or _DEFAULT_HOST
        )
        model = (
            os.environ.get("LLM_MODEL", "").strip()
            or os.environ.get("OLLAMA_MODEL", "").strip()
            or _DEFAULT_MODEL
        )
        return cls(host, model)

    @property
    def provider_id(self) -> str:
        return "ollama"

    @property
    def model_id(self) -> str:
        return self._model_name

    def is_configured(self) -> bool:
        return bool(self._host and self._model_name)

    def _chat_sync(self, user_content: str, *, num_predict: int = 2500) -> dict:
        payload: dict[str, Any] = {
            "model": self._model_name,
            "stream": True,
            "format": "json",
            "think": False,
            "keep_alive": "30m",
            "messages": [{"role": "user", "content": user_content}],
            "options": {
                "temperature": 0.05,
                "top_p": 0.7,
                "num_ctx": 8192,
                "num_predict": num_predict,
            },
        }
        url = f"{self._host}/api/chat"
        timeout = httpx.Timeout(connect=15.0, read=90.0, write=30.0, pool=15.0)
        chunks: list[str] = []
        done_reason: Any = None
        eval_count: Any = None
        try:
            with httpx.Client(timeout=timeout) as client:
                with client.stream("POST", url, json=payload) as response:
                    if response.status_code == 400:
                        response.read()
                        payload.pop("think", None)
                        with client.stream("POST", url, json=payload) as retry:
                            retry.raise_for_status()
                            done_reason, eval_count = _read_ollama_stream(retry, chunks)
                    else:
                        response.raise_for_status()
                        done_reason, eval_count = _read_ollama_stream(response, chunks)
        except httpx.TimeoutException as exc:
            raise RuntimeError(
                "Ollama se detuvo más de 90s sin escribir. Reintentá; "
                "la primera corrida carga el modelo (~5 GB)."
            ) from exc
        message = "".join(chunks)
        if done_reason:
            logger.info("Ollama done_reason=%s eval_count=%s chars=%s", done_reason, eval_count, len(message))
        try:
            return parse_json_object(message, context="ollama")
        except ValueError as exc:
            logger.warning("Ollama JSON inválido (%s): %s", done_reason, str(exc)[:300])
            raise RuntimeError("Ollama no devolvió JSON válido. Reintentá generar el CV.") from exc

    async def pick_best_cv(
        self, vacancy_text: str, cvs: list[CvDocument]
    ) -> tuple[CvDocument, float, str]:
        chosen, score, reason = pick_best_cv(vacancy_text, cvs)
        return chosen, score, f"{reason} (plantilla; los hechos salen del master profile via Ollama)"

    def _tailor_cv_sync(
        self, vacancy_text: str, cv: CvDocument
    ) -> Tuple[CvDocument, float, str, List[str], List[str], List[str], Dict[str, Any]]:
        master = load_ollama_profile()
        prompt = build_ollama_optimizer_prompt(vacancy_text, profile_for_prompt(master))
        data = self._chat_sync(prompt)
        cv_out = _ollama_result_to_cv(data, cv, master)
        match_percent = float(data.get("match_score") or 0)
        if match_percent <= 10:
            match_percent *= 10
        match_percent = max(0.0, min(100.0, match_percent))
        missing = data.get("missing_requirements") or []
        gaps = _as_gap_strings(missing)
        reason = str(data.get("target_role") or cv_out.title or "CV optimizado con Ollama")
        raw_meta: Dict[str, Any] = {
            "llm_provider": self.provider_id,
            "llm_model": self._model_name,
            "source": "master_profile",
            "keywords": data.get("keywords") or [],
            "attempts": 1,
        }
        return cv_out, match_percent, reason, [], gaps, [], raw_meta

    async def tailor_cv(
        self, vacancy_text: str, cv: CvDocument
    ) -> Tuple[CvDocument, float, str, List[str], List[str], List[str], Dict[str, Any]]:
        if not self.is_configured():
            raise RuntimeError("Ollama no configurado (OLLAMA_HOST / OLLAMA_MODEL)")
        return await asyncio.to_thread(self._tailor_cv_sync, vacancy_text, cv)


def _as_gap_strings(missing: Any) -> list[str]:
    out: list[str] = []
    if not isinstance(missing, list):
        return out
    for item in missing:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
        elif isinstance(item, dict):
            skill = str(item.get("skill") or item.get("requirement") or "").strip()
            if skill:
                out.append(skill)
    return out[:50]


def _norm(text: str) -> str:
    return " ".join(str(text or "").lower().split())


def _company_index(master: dict) -> dict[str, dict]:
    index: dict[str, dict] = {}
    for item in master.get("experience") or []:
        company = _norm(item.get("company") or "")
        if company:
            index[company] = item
    return index


def _skill_index(master: dict) -> dict[str, str]:
    index: dict[str, str] = {}
    for name in master.get("skill_inventory") or []:
        key = _norm(name)
        if key:
            index[key] = str(name)
    for values in (master.get("skills") or {}).values():
        if not isinstance(values, list):
            continue
        for name in values:
            key = _norm(name)
            if key and key not in index:
                index[key] = str(name)
    return index


def _keep_listed_skills(selected: list[Any], master: dict) -> list[str]:
    """Skills del modelo + vacante. No se descartan techs que el candidato va a aprender."""
    inventory = _skill_index(master)
    kept: list[str] = []
    seen: set[str] = set()
    for raw in selected:
        name = str(raw).strip()
        key = _norm(name)
        if not name or key in seen:
            continue
        seen.add(key)
        kept.append(inventory.get(key) or name)
    return kept[:16]


def _append_unique(dest: list[str], skill: str) -> None:
    key = _norm(skill)
    if key and key not in {_norm(x) for x in dest}:
        dest.append(skill)


def _stack_from_skills(kept: list[str], master: dict) -> StackBlock:
    cats = master.get("skills") or {}
    frontend: list[str] = []
    backend: list[str] = []
    state: list[str] = []
    cloud: list[str] = []
    mobile: list[str] = []
    architecture: list[str] = []
    testing: list[str] = []
    quality: list[str] = []

    master_map = {
        "frontend": {_norm(x) for x in (cats.get("frontend") or [])},
        "backend": {_norm(x) for x in (cats.get("backend") or []) + (cats.get("databases") or [])},
        "mobile": {_norm(x) for x in (cats.get("mobile") or [])},
        "cloud": {_norm(x) for x in (cats.get("cloud") or []) + (cats.get("devops") or [])},
        "architecture": {_norm(x) for x in (cats.get("architecture") or [])},
        "testing": {_norm(x) for x in (cats.get("testing") or [])},
        "ai": {_norm(x) for x in (cats.get("ai") or [])},
        "languages": {_norm(x) for x in (cats.get("languages") or [])},
    }
    state_keys = {"redux", "ngrx", "zustand", "react query", "tanstack query", "rxjs", "mobx"}

    for skill in kept:
        key = _norm(skill)
        if key in state_keys:
            _append_unique(state, skill)
            continue
        if key in master_map["frontend"] or key in master_map["languages"]:
            _append_unique(frontend, skill)
            continue
        if key in master_map["backend"]:
            _append_unique(backend, skill)
            continue
        if key in master_map["mobile"]:
            _append_unique(mobile, skill)
            continue
        if key in master_map["cloud"]:
            _append_unique(cloud, skill)
            continue
        if key in master_map["architecture"]:
            _append_unique(architecture, skill)
            continue
        if key in master_map["testing"]:
            _append_unique(testing, skill)
            continue
        if key in master_map["ai"] or any(tok in key for tok in ("copilot", "cursor", "chatgpt", "claude")):
            _append_unique(quality, skill)
            continue
        if any(tok in key for tok in ("react native", "ionic", "android", "ios")):
            _append_unique(mobile, skill)
        elif any(tok in key for tok in ("mongo", "postgres", "mysql", "node", "nest", "express", "adonis", "prisma", "graphql", "apollo", "laravel")):
            _append_unique(backend, skill)
            if "graphql" in key or "apollo" in key:
                _append_unique(frontend, skill)
        elif any(tok in key for tok in ("aws", "docker", "firebase", "s3", "ci/cd", "ci cd")):
            _append_unique(cloud, skill)
        else:
            _append_unique(frontend, skill)

    return StackBlock(
        frontend=", ".join(frontend),
        backend=", ".join(backend),
        state=", ".join(state),
        cloud=", ".join(cloud),
        mobile=", ".join(mobile),
        architecture=", ".join(architecture),
        testing=", ".join(testing),
        quality=", ".join(quality),
    )


def _split_into_tech_skills(kept: list[str], master: dict) -> TechSkills:
    cats = master.get("skills") or {}
    buckets = {
        "front": {_norm(x) for x in (cats.get("frontend") or []) + (cats.get("mobile") or []) + (cats.get("languages") or [])},
        "back": {_norm(x) for x in (cats.get("backend") or []) + (cats.get("databases") or []) + (cats.get("payments") or [])},
        "ux": {_norm(x) for x in (cats.get("softSkills") or [])},
        "test": {_norm(x) for x in (cats.get("testing") or []) + (cats.get("devops") or []) + (cats.get("cloud") or [])},
    }
    out = TechSkills()
    for skill in kept:
        key = _norm(skill)
        if key in buckets["front"]:
            out.front.append(skill)
        elif key in buckets["back"]:
            out.back.append(skill)
        elif key in buckets["test"]:
            out.test.append(skill)
        elif key in buckets["ux"]:
            out.ux.append(skill)
        else:
            out.front.append(skill)
    return out


def _education_line(master: dict) -> str:
    for item in master.get("education") or []:
        degree = str(item.get("degree") or "")
        if "también referido" in degree.lower():
            degree = degree.split("(")[0].strip()
        institution = item.get("institution") or ""
        year = item.get("graduation_year") or item.get("end_date") or ""
        parts = [p for p in (degree, institution, str(year) if year else "") if p]
        if parts:
            return " — ".join(parts)
    return ""


def _cert_names(master: dict) -> list[str]:
    names: list[str] = []
    for item in master.get("certifications") or []:
        name = str(item.get("name") or "").strip()
        year = item.get("year")
        if not name:
            continue
        names.append(f"{name} ({year})" if year else name)
    return names


def _contact(master: dict) -> dict[str, str]:
    contact = master.get("contact") or {}
    return {
        "email": str(contact.get("email") or ""),
        "phone": str(contact.get("phone") or ""),
        "linkedin": str(contact.get("linkedin") or ""),
    }


def _ollama_result_to_cv(data: dict, base: CvDocument, master: dict) -> CvDocument:
    companies = _company_index(master)
    allowed = {_norm(c) for c in (master.get("allowed_companies") or companies.keys())}
    personal = {_norm(n) for n in (master.get("personal_products_not_employment") or [])}

    experience: list[ExperienceItem] = []
    for raw in data.get("experience") or []:
        if not isinstance(raw, dict):
            continue
        company = str(raw.get("company") or "").strip()
        key = _norm(company)
        if not company or key not in allowed or key in personal:
            continue
        source = companies.get(key) or {}
        period = str(source.get("dates") or raw.get("dates") or "").strip()
        position = str(raw.get("position") or "").strip()
        known_roles = [_norm(r) for r in (source.get("positions") or [])]
        if position and known_roles and _norm(position) not in known_roles:
            # wording may differ; keep model title only if it shares a token with a known role
            known_blob = " ".join(known_roles)
            if not any(tok in known_blob for tok in _norm(position).split() if len(tok) > 3):
                position = (source.get("positions") or [position])[0]
        bullets = [str(b).strip() for b in (raw.get("bullets") or []) if str(b).strip()]
        experience.append(
            ExperienceItem(
                company=source.get("company") or company,
                role=position or ((source.get("positions") or [""])[0]),
                period=period,
                bullets=bullets[:4],
            )
        )

    kept_skills = _keep_listed_skills(data.get("skills") or [], master)
    contact = _contact(master)
    title = str(data.get("target_role") or base.title or "").strip()
    summary = str(data.get("summary") or "").strip()
    keywords = [str(k).strip() for k in (data.get("keywords") or []) if str(k).strip()][:15]

    return CvDocument(
        id=base.id,
        label=base.label,
        keywords=keywords or base.keywords,
        name=str(master.get("name") or base.name),
        title=title or base.title,
        email=contact["email"] or base.email,
        phone=contact["phone"] or base.phone,
        linkedin=contact["linkedin"] or base.linkedin,
        summary=summary or base.summary,
        experience=experience or base.experience,
        stack=_stack_from_skills(kept_skills, master),
        tech_skills=_split_into_tech_skills(kept_skills, master),
        education=_education_line(master) or base.education,
        certifications=_cert_names(master) or base.certifications,
    )
