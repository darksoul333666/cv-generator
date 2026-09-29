"""Backend Ollama: el modelo cv-optimizer consume el perfil maestro compacto."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from typing import Any, Dict, List, Tuple

import httpx

from ..compact_master import load_ollama_profile, profile_for_prompt
from ..locale_util import (
    cert_names,
    detect_vacancy_locale,
    education_line,
    format_period,
    localize_cv_wording,
    polish_experience_title,
)
from ..matcher import pick_best_cv
from ..models import CvDocument, ExperienceItem
from ..skill_stack import build_stack_from_master, stack_to_tech_skills, vacancy_skill_keywords
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
        locale = detect_vacancy_locale(vacancy_text)
        prompt = build_ollama_optimizer_prompt(
            vacancy_text, profile_for_prompt(master), locale
        )
        data = self._chat_sync(prompt)
        cv_out = _ollama_result_to_cv(data, cv, master, locale, vacancy_text)
        match_percent = float(data.get("match_score") or 0)
        if match_percent <= 10:
            match_percent *= 10
        match_percent = max(0.0, min(100.0, match_percent))
        reason = str(data.get("target_role") or cv_out.title or "CV optimizado con Ollama")
        raw_meta: Dict[str, Any] = {
            "llm_provider": self.provider_id,
            "llm_model": self._model_name,
            "source": "master_profile",
            "keywords": data.get("keywords") or [],
            "attempts": 1,
            "locale": locale,
        }
        return cv_out, match_percent, reason, [], [], [], raw_meta

    async def tailor_cv(
        self, vacancy_text: str, cv: CvDocument
    ) -> Tuple[CvDocument, float, str, List[str], List[str], List[str], Dict[str, Any]]:
        if not self.is_configured():
            raise RuntimeError("Ollama no configurado (OLLAMA_HOST / OLLAMA_MODEL)")
        return await asyncio.to_thread(self._tailor_cv_sync, vacancy_text, cv)

    async def tailor_cv_batch(
        self, items: list[tuple[str, CvDocument]]
    ) -> list[Tuple[CvDocument, float, str, List[str], List[str], List[str], Dict[str, Any]]]:
        out: list[Tuple[CvDocument, float, str, List[str], List[str], List[str], Dict[str, Any]]] = []
        for vacancy_text, cv in items:
            packed = await self.tailor_cv(vacancy_text, cv)
            meta = packed[6]
            meta["batch_size"] = len(items)
            out.append(packed)
        return out


def _norm(text: str) -> str:
    return " ".join(str(text or "").lower().split())


def _company_index(master: dict) -> dict[str, dict]:
    index: dict[str, dict] = {}
    for item in master.get("experience") or []:
        company = _norm(item.get("company") or "")
        if company:
            index[company] = item
    return index


_GENERIC_ROLE_WORDS = {
    "frontend",
    "backend",
    "fullstack",
    "full",
    "stack",
    "developer",
    "engineer",
    "senior",
    "junior",
    "lead",
    "leader",
    "technical",
    "software",
}


def _role_terms(role: str) -> list[str]:
    cleaned = _norm(role).replace("-", " ").replace("/", " ").replace("+", " ")
    cleaned = cleaned.replace("(", " ").replace(")", " ")
    return [
        word
        for word in cleaned.split()
        if word not in _GENERIC_ROLE_WORDS and len(word) > 2
    ]


def _term_in_vacancy(term: str, vacancy: str) -> bool:
    if not term or not vacancy:
        return False
    if re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", vacancy):
        return True
    compact_term = re.sub(r"[^a-z0-9]+", "", term)
    compact_vacancy = re.sub(r"[^a-z0-9]+", "", vacancy)
    return len(compact_term) >= 4 and compact_term in compact_vacancy


def _role_fit(role: str, vacancy: str) -> int:
    """Cuántas palabras propias del cargo aparecen en la vacante. Ignora Frontend/Developer."""
    vacancy_n = _norm(vacancy).replace("-", " ")
    return sum(1 for term in _role_terms(role) if _term_in_vacancy(term, vacancy_n))


def _pick_position(known: list[str], model_position: str, vacancy: str) -> str:
    """Entre los cargos del maestro, el que mejor coincide con la vacante."""
    roles = [str(role).strip() for role in known if str(role).strip()]
    if not roles:
        return model_position
    best = max(roles, key=lambda role: (_role_fit(role, vacancy), -len(role)))
    best_score = _role_fit(best, vacancy)
    model_score = _role_fit(model_position, vacancy) if model_position else -1
    if best_score <= 0:
        return model_position or roles[0]
    known_norms = {_norm(role) for role in roles}
    if model_position and _norm(model_position) in known_norms and model_score >= best_score:
        return model_position
    if best_score > model_score:
        return best
    return model_position or best


def _recency_key(source: dict) -> tuple:
    """Empleo actual primero; después el que terminó más tarde."""
    current = 1 if source.get("current") else 0
    end = str(source.get("end_date") or "")
    start = str(source.get("start_date") or "")
    return (current, end, start)


def _compact_token(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", _norm(text))


def _tech_in_vacancy(tech: str, vacancy: str) -> bool:
    token = _compact_token(tech)
    haystack = _compact_token(vacancy)
    if len(token) < 3 or not haystack:
        return False
    if len(token) <= 4:
        return bool(re.search(rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])", haystack))
    return token in haystack


def _matches_vacancy(source: dict, vacancy: str) -> bool:
    for tech in source.get("technologies") or []:
        if _tech_in_vacancy(str(tech), vacancy):
            return True
    return any(_role_fit(str(role), vacancy) > 0 for role in (source.get("positions") or []))


def _anchor_ym(companies: dict[str, dict]) -> str:
    anchor = ""
    for source in companies.values():
        stamp = str(source.get("start_date") or "") if source.get("current") else str(
            source.get("end_date") or source.get("start_date") or ""
        )
        if stamp > anchor:
            anchor = stamp
    return anchor


def _years_before(ym: str, years: int) -> str:
    if len(ym) < 7 or ym[4] != "-":
        return "0000-00"
    return f"{int(ym[:4]) - years:04d}{ym[4:7]}"


def _is_stale(source: dict, cutoff: str) -> bool:
    if source.get("current"):
        return False
    end = str(source.get("end_date") or source.get("start_date") or "")
    return bool(end) and end < cutoff


def _metric_label(source: dict) -> str:
    for ach in source.get("achievements") or []:
        if not isinstance(ach, dict):
            continue
        metric = ach.get("metric") or {}
        if metric.get("value") is None:
            continue
        unit = str(metric.get("unit") or "")
        value = metric.get("value")
        if unit.lower() in {"percent", "%"}:
            return f"{value}%"
        return f"{value} {unit}".strip()
    return ""


def _tech_names(source: dict, limit: int = 4) -> list[str]:
    names: list[str] = []
    for raw in source.get("technologies") or []:
        name = str(raw).strip()
        if name and name not in names:
            names.append(name)
        if len(names) >= limit:
            break
    return names


def _join_names(names: list[str], conjunction: str) -> str:
    if len(names) <= 1:
        return names[0] if names else ""
    if len(names) == 2:
        return f"{names[0]} {conjunction} {names[1]}"
    return f"{', '.join(names[:-1])} {conjunction} {names[-1]}"


_NOTE_RE = re.compile(
    r"\s*\([^)]*(?:cv hist[oó]rico|knowledge_base|seg[uú]n)[^)]*\)",
    re.IGNORECASE,
)
_SPANISH_FACT_RE = re.compile(
    r"[áéíóúñ]|\b(de|del|con|para|mediante|desarrollo|diseño|gesti[oó]n|app)\b",
    re.IGNORECASE,
)


def _clean_fact(text: str) -> str:
    cleaned = _NOTE_RE.sub("", text or "")
    return " ".join(cleaned.split()).strip(" .;")


def _fact_sentences(source: dict) -> list[str]:
    """Hechos del perfil, el logro con cifra primero y después las responsabilidades."""
    sentences: list[str] = []
    metric = _metric_label(source)
    for ach in source.get("achievements") or []:
        if isinstance(ach, dict):
            desc = _clean_fact(str(ach.get("description") or ""))
        else:
            desc = _clean_fact(str(ach))
        if len(desc) < 25:
            continue
        if metric and metric not in desc:
            desc = f"{desc} ({metric})"
        sentences.append(desc)
    for resp in source.get("responsibilities") or []:
        desc = _clean_fact(str(resp))
        if len(desc) >= 25:
            sentences.append(desc)
    return sentences


def _focus_line(source: dict, role: str, locale: str) -> str:
    """Respaldo si el empleo no tiene ninguna frase usable en el perfil."""
    techs = _tech_names(source)
    metric = _metric_label(source)
    if locale == "es":
        body = (
            f"Desarrollo y entrega con {_join_names(techs, 'y')}"
            if techs
            else f"Desarrollo y entrega como {role}".strip()
        )
    else:
        body = (
            f"Shipped production features with {_join_names(techs, 'and')}"
            if techs
            else f"Shipped production features as {role}".strip()
        )
    if metric:
        body += f" ({metric})"
    return body.rstrip(".") + "."


def _one_real_bullet(source: dict, role: str, locale: str) -> str:
    facts = _fact_sentences(source)
    usable = [
        fact
        for fact in facts
        if locale != "en" or not _SPANISH_FACT_RE.search(fact)
    ]
    if not usable:
        return _focus_line(source, role, locale)
    line = usable[0]
    if len(line) < 80 and len(usable) > 1 and len(line) + len(usable[1]) <= 170:
        line = f"{line}. {usable[1]}"
    techs = _tech_names(source, 2)
    if techs and not any(_norm(tech) in _norm(line) for tech in techs):
        names = _join_names(techs, "y" if locale == "es" else "and")
        line = f"{line} con {names}" if locale == "es" else f"{line} with {names}"
    return localize_cv_wording(line.rstrip(".") + ".", locale)


def _bullets_for_job(
    source: dict, model_bullets: list[str], vacancy: str, role: str, locale: str
) -> list[str]:
    if _matches_vacancy(source, vacancy) and model_bullets:
        return model_bullets[:4]
    if model_bullets:
        return model_bullets[:1]
    return [_one_real_bullet(source, role, locale)]


def _contact(master: dict) -> dict[str, str]:
    contact = master.get("contact") or {}
    return {
        "email": str(contact.get("email") or ""),
        "phone": str(contact.get("phone") or ""),
        "linkedin": str(contact.get("linkedin") or ""),
    }


def _ollama_result_to_cv(
    data: dict, base: CvDocument, master: dict, locale: str = "es", vacancy_text: str = ""
) -> CvDocument:
    companies = _company_index(master)
    allowed = {_norm(c) for c in (master.get("allowed_companies") or companies.keys())}
    personal = {_norm(n) for n in (master.get("personal_products_not_employment") or [])}
    overlay = [
        str(s).strip()
        for s in list(data.get("skills") or []) + list(data.get("keywords") or [])
        if str(s).strip()
    ]

    built: dict[str, ExperienceItem] = {}
    for raw in data.get("experience") or []:
        if not isinstance(raw, dict):
            continue
        company = str(raw.get("company") or "").strip()
        key = _norm(company)
        if not company or key not in allowed or key in personal:
            continue
        source = companies.get(key) or {}
        period = format_period(
            source.get("start_date"),
            source.get("end_date"),
            bool(source.get("current")),
            locale,
        ) or str(source.get("dates") or raw.get("dates") or "").strip()
        position = str(
            raw.get("position")
            or raw.get("role")
            or raw.get("title")
            or ""
        ).strip()
        if not position:
            positions = raw.get("positions") or raw.get("roles") or []
            if isinstance(positions, list) and positions:
                position = str(positions[0] or "").strip()
            elif isinstance(positions, str):
                position = positions.strip()
        known = [str(role).strip() for role in (source.get("positions") or []) if str(role).strip()]
        known_norms = [_norm(role) for role in known]
        if position and known_norms and _norm(position) not in known_norms:
            known_blob = " ".join(known_norms)
            if not any(tok in known_blob for tok in _norm(position).split() if len(tok) > 3):
                position = known[0] if known else position
        position = _pick_position(known, position, vacancy_text)
        position = polish_experience_title(
            source.get("company") or company,
            position or (known[0] if known else ""),
            vacancy_text,
        )
        bullets = [
            localize_cv_wording(str(b).strip(), locale)
            for b in (raw.get("bullets") or raw.get("achievements") or raw.get("responsibilities") or [])
            if not isinstance(b, dict) and str(b).strip()
        ]
        role = localize_cv_wording(position, locale)
        built[key] = ExperienceItem(
            company=source.get("company") or company,
            role=role,
            period=period,
            bullets=_bullets_for_job(source, bullets, vacancy_text, role, locale),
        )

    cutoff = _years_before(_anchor_ym(companies), 6)
    for key, source in companies.items():
        if key in personal or key in built or key not in allowed:
            continue
        if _is_stale(source, cutoff) and not _matches_vacancy(source, vacancy_text):
            continue
        known = [str(role).strip() for role in (source.get("positions") or []) if str(role).strip()]
        position = polish_experience_title(
            source.get("company") or key,
            _pick_position(known, known[0] if known else "", vacancy_text),
            vacancy_text,
        )
        period = format_period(
            source.get("start_date"),
            source.get("end_date"),
            bool(source.get("current")),
            locale,
        ) or str(source.get("dates") or "").strip()
        role = localize_cv_wording(position, locale)
        built[key] = ExperienceItem(
            company=source.get("company") or key,
            role=role,
            period=period,
            bullets=_bullets_for_job(source, [], vacancy_text, role, locale),
        )

    for key, source in list(built.items()):
        origin = companies.get(key) or {}
        if _is_stale(origin, cutoff) and not _matches_vacancy(origin, vacancy_text):
            del built[key]

    experience = [
        built[key]
        for key in sorted(built, key=lambda k: _recency_key(companies.get(k) or {}), reverse=True)
    ]

    contact = _contact(master)
    title = localize_cv_wording(
        str(data.get("target_role") or base.title or "").strip(),
        locale,
    )
    summary = localize_cv_wording(
        str(data.get("summary") or "").strip(),
        locale,
    )
    stack = build_stack_from_master(master, vacancy_text, overlay=overlay)
    keywords = vacancy_skill_keywords(
        master,
        vacancy_text,
        overlay,
    ) or base.keywords

    return CvDocument(
        id=base.id,
        label=base.label,
        keywords=keywords,
        name=str(master.get("name") or base.name),
        title=title or base.title,
        email=contact["email"] or base.email,
        phone=contact["phone"] or base.phone,
        linkedin=contact["linkedin"] or base.linkedin,
        summary=summary or base.summary,
        experience=experience or base.experience,
        stack=stack,
        tech_skills=stack_to_tech_skills(stack),
        education=education_line(master, locale) or base.education,
        certifications=cert_names(master, locale) or base.certifications,
        locale=locale,
    )
