"""Perfil compacto que recibe el modelo (Gemini u OpenAI). No infiere ni resuelve conflictos."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

_MONTHS = {
    1: "Jan",
    2: "Feb",
    3: "Mar",
    4: "Apr",
    5: "May",
    6: "Jun",
    7: "Jul",
    8: "Aug",
    9: "Sep",
    10: "Oct",
    11: "Nov",
    12: "Dec",
}

_UNSAFE_LEVELS = {"inferred", "conflicted"}
_UNSAFE_STATUS = {"inferred", "conflicted", "requires_validation"}


def kb_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "knowledge_base"


def _fmt_month(ym: Optional[str]) -> Optional[str]:
    if not ym:
        return None
    text = str(ym).strip()
    if len(text) >= 7 and text[4] == "-":
        try:
            year = int(text[:4])
            month = int(text[5:7])
            return f"{_MONTHS[month]} {year}"
        except (ValueError, KeyError):
            return text
    return text


def _fmt_dates(start: Optional[str], end: Optional[str], current: bool) -> str:
    start_s = _fmt_month(start) or (start or "")
    if current or not end:
        return f"{start_s} – Present" if start_s else "Present"
    end_s = _fmt_month(end) or end
    if start_s and end_s:
        return f"{start_s} – {end_s}"
    return start_s or str(end_s or "")


def _safe_fact(item: dict) -> bool:
    level = str(item.get("evidenceLevel") or "").lower()
    status = str(item.get("status") or "").lower()
    if level in _UNSAFE_LEVELS or status in _UNSAFE_STATUS:
        return False
    return True


# Estados de fecha que no se imprimen en un CV. ``claimed`` (el usuario la escribió) sí.
_UNVERIFIED_DATE_STATUS = {"conflicted", "requires_validation", "inferred"}


def dates_unverified(item: dict) -> bool:
    """True si las fechas de un empleo tienen un conflicto abierto.

    ``dateConflict.status == "unresolved"`` manda sobre ``dateStatus``: los editores de perfil
    históricamente marcaban ``verified`` al guardar cualquier fecha, aunque hubiera dos
    resoluciones del usuario que se contradicen.
    """
    conflict = item.get("dateConflict")
    if isinstance(conflict, dict) and str(conflict.get("status") or "").lower() in {"unresolved", "pending"}:
        return True
    return str(item.get("dateStatus") or "").lower() in _UNVERIFIED_DATE_STATUS


def _extra_periods(item: dict) -> list[dict]:
    """``additionalPeriods`` del maestro, del más reciente al más antiguo."""
    out: list[dict] = []
    for period in item.get("additionalPeriods") or []:
        if not isinstance(period, dict) or not period.get("startDate"):
            continue
        out.append(
            {
                "start_date": period.get("startDate"),
                "end_date": period.get("endDate"),
                "current": bool(period.get("current")),
            }
        )
    out.sort(key=lambda p: str(p["start_date"]), reverse=True)
    return out


def _date_candidates(item: dict) -> list[str]:
    conflict = item.get("dateConflict")
    out: list[str] = []
    if isinstance(conflict, dict):
        for cand in conflict.get("candidates") or []:
            if not isinstance(cand, dict):
                continue
            end = "Present" if cand.get("current") else (cand.get("endDate") or "?")
            out.append(f"{cand.get('startDate') or '?'} – {end}")
    return out


_OMITTED_RE = re.compile(r"^\(?\s*omitid[oa]", re.IGNORECASE)


def omitted_contact_fields(raw: dict) -> set[str]:
    """Campos de contacto que el usuario decidió no mostrar en CVs.

    Es una regla de presentación, no un hecho: el valor (p. ej. «Mexico») se conserva en el
    perfil. Fuentes, en orden: ``cvGenerationRules.omitContactFields`` y la resolución del
    conflicto ``profile.contact.<campo>`` cuando el valor preferido es «omitido …».
    """
    rules = raw.get("cvGenerationRules") or {}
    out = {str(f).strip() for f in (rules.get("omitContactFields") or []) if str(f).strip()}
    for conflict in raw.get("conflicts") or []:
        if not isinstance(conflict, dict):
            continue
        name = str(conflict.get("field") or "")
        if not name.startswith("profile.contact."):
            continue
        if conflict.get("resolution") != "user_validated":
            continue
        if _OMITTED_RE.search(str(conflict.get("preferredValue") or "").strip()):
            out.add(name.rsplit(".", 1)[-1])
    return out


def _contact_value(field: dict) -> Optional[str]:
    if not isinstance(field, dict):
        return None
    if field.get("userValidated") or str(field.get("status") or "") == "user_validated":
        value = field.get("value")
        return str(value).strip() if value else None
    if str(field.get("evidenceLevel") or "") in {"verified", "documented"} and field.get("value"):
        return str(field["value"]).strip()
    return None


def _unique_skills(skills: dict) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for values in skills.values():
        if not isinstance(values, list):
            continue
        for raw in values:
            name = str(raw).strip()
            key = name.lower()
            if not name or key in seen:
                continue
            seen.add(key)
            out.append(name)
    return out


def _skill_aliases(raw: dict) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    source = raw.get("skillAliases") or {}
    if not isinstance(source, dict):
        return out
    for key, val in source.items():
        if isinstance(val, dict):
            canon = str(val.get("canonical") or key).strip()
            aliases = [str(a).strip() for a in (val.get("aliases") or []) if str(a).strip()]
        elif isinstance(val, list):
            canon = str(key).strip()
            aliases = [str(a).strip() for a in val if str(a).strip()]
        else:
            continue
        if not canon:
            continue
        bucket = out.setdefault(canon, [])
        for alias in aliases:
            if alias not in bucket:
                bucket.append(alias)
    return out


_META_SENTENCE_RE = re.compile(
    r"sin confirmar|sin detallar|no se atribuye|siguen? sin|unresolved|pendiente|no auditado|"
    r"\bclaim\b|seg[uú]n readme|no hay cifra",
    re.IGNORECASE,
)


def _is_meta(text: str) -> bool:
    return bool(_META_SENTENCE_RE.search(text or ""))


def cv_facing_text(text: str) -> str:
    """Quita de una descripción las frases que son notas internas («sin confirmar», etc.)."""
    # «EE. UU.» no es fin de frase.
    clean = re.sub(r"\bEE\.\s*UU\.", "EE.UU.", (text or "").strip())
    sentences = re.split(r"(?<=[.;])\s+(?=[A-ZÁÉÍÓÚÑ¿¡])", clean)
    kept = [s for s in sentences if s and not _is_meta(s)]
    return " ".join(kept).strip()


def _unresolved_items(item: dict) -> list[str]:
    out: list[str] = []
    for ev in item.get("evidence") or []:
        text = str(ev)
        idx = text.upper().find("UNRESOLVED:")
        if idx < 0:
            continue
        detail = text[idx + len("UNRESOLVED:"):].strip().rstrip(".")
        if detail and detail not in out:
            out.append(detail[:120])
    return out


def _withhold_reason(item: dict) -> str:
    """Motivo para no mandar un proyecto al modelo; vacío si tiene hechos suficientes."""
    status = str(item.get("status") or "").lower()
    if status == "incomplete":
        return "status=incomplete"
    if status in _UNSAFE_STATUS or str(item.get("evidenceLevel") or "").lower() in _UNSAFE_LEVELS:
        return f"status={status or item.get('evidenceLevel')}"
    if not (item.get("technologies") or []) and not (item.get("features") or []):
        return "sin tecnologías ni funcionalidades confirmadas"
    if not cv_facing_text(str(item.get("description") or "")) and not (item.get("features") or []):
        return "sin descripción confirmada"
    return ""


# Grafías comunes → nombre oficial. Solo para generar; el perfil guarda lo que escribió el usuario.
_TECH_SPELLING = {
    "nest js": "NestJS", "nestjs": "NestJS", "nest.js": "NestJS",
    "express js": "Express.js", "expressjs": "Express.js", "express": "Express.js",
    "typescript": "TypeScript", "javascript": "JavaScript",
    "rxjs": "RxJS", "ngrx": "NgRx", "i18n": "i18n",
    "ios": "iOS", "android": "Android",
    "botstrap": "Bootstrap", "bootstrap": "Bootstrap",
    "tailwind": "TailwindCSS", "tailwindcss": "TailwindCSS",
    "web sockets": "WebSockets", "websockets": "WebSockets", "web rtc": "WebRTC", "webrtc": "WebRTC",
    "codecommit": "AWS CodeCommit", "codepipeline": "AWS CodePipeline", "codepipelines": "AWS CodePipeline",
    "react js": "React", "reactjs": "React", "node js": "Node.js", "nodejs": "Node.js",
    "next js": "Next.js", "nextjs": "Next.js", "postgres": "PostgreSQL", "postgresql": "PostgreSQL",
    "figma": "Figma", "signals": "Signals", "interceptors": "HTTP Interceptors",
}
_VERSION_RE = re.compile(r"^(.*?)\s+(\d+(?:\.\d+)*)$")


def canonical_tech(name: str, known: Optional[dict[str, str]] = None) -> str:
    """«Nest JS» → «NestJS», «React Native 0.74» se queda, «Typescript» → «TypeScript»."""
    text = " ".join(str(name or "").split())
    if not text:
        return text
    base, version = text, ""
    m = _VERSION_RE.match(text)
    if m:
        base, version = m.group(1), m.group(2)
    key = base.lower()
    fixed = (known or {}).get(key) or _TECH_SPELLING.get(key) or base
    return f"{fixed} {version}".strip()


def _known_spellings(raw: dict) -> dict[str, str]:
    known: dict[str, str] = {}
    for values in (raw.get("skills") or {}).values() if isinstance(raw.get("skills"), dict) else []:
        for value in values if isinstance(values, list) else []:
            name = str(value).strip()
            if name and name.lower() not in known:
                known[name.lower()] = name
    return known


def _canonical_list(values: Any, known: dict[str, str]) -> list[str]:
    out: list[str] = []
    for value in values or []:
        name = canonical_tech(str(value), known)
        if name and name.lower() not in {o.lower() for o in out}:
            out.append(name)
    return out


def build_compact_profile(raw: dict) -> dict:
    """Hechos usables por el modelo. Omite inferred/conflicted y metadatos internos."""
    profile = raw.get("profile") or {}
    contact = profile.get("contact") or {}
    skills = raw.get("skills") or {}
    yoe = raw.get("yearsOfExperience") or {}

    contact_out: dict[str, str] = {}
    omitted = omitted_contact_fields(raw)
    for key in ("email", "phone", "linkedin", "github", "website", "location"):
        if key in omitted:
            continue
        value = _contact_value(contact.get(key) or {})
        if value and not _OMITTED_RE.search(value):
            contact_out[key] = value

    years: Any = None
    if yoe.get("userValidated") or str(yoe.get("status") or "") in {"computed", "user_validated"}:
        years = yoe.get("value")

    known = _known_spellings(raw)
    experience_out: list[dict] = []
    allowed_companies: list[str] = []
    hidden_experience: list[dict] = []
    for item in raw.get("experience") or []:
        if not isinstance(item, dict):
            continue
        company = str(item.get("company") or "").strip()
        if not company:
            continue
        if item.get("showInCv") is False:
            # Se queda en el perfil (línea de tiempo), pero ni el modelo ni el CV la ven.
            hidden_experience.append({"company": company, "reason": str(item.get("showInCvNote") or "showInCv=false")})
            continue
        allowed_companies.append(company)
        achievements = []
        for ach in item.get("achievements") or []:
            if not isinstance(ach, dict) or not _safe_fact(ach):
                continue
            if ach.get("safeForCV") is False:
                continue
            metric = ach.get("metric") or {}
            achievements.append(
                {
                    "description": ach.get("description"),
                    "metric": metric or None,
                    "status": ach.get("status"),
                    "detail": _evidence_detail(ach),
                    "project": ach.get("project") or None,
                }
            )
        unverified = dates_unverified(item)
        extra = [] if unverified else _extra_periods(item)
        dates_text = "" if unverified else " · ".join(
            [_fmt_dates(item.get("startDate"), item.get("endDate"), bool(item.get("current")))]
            + [_fmt_dates(p["start_date"], p["end_date"], p["current"]) for p in extra]
        )
        experience_out.append(
            {
                "id": item.get("id"),
                "company": company,
                "positions": item.get("roles") or [],
                "employment_type": item.get("employmentType"),
                # Fechas en conflicto no salen: ni al modelo ni al CV.
                "dates": dates_text,
                "start_date": None if unverified else item.get("startDate"),
                "end_date": None if unverified else item.get("endDate"),
                "current": False if unverified else bool(item.get("current")),
                "dates_verified": not unverified,
                # Etapas anteriores en la misma empresa (p. ej. UffPay 2024 y 2026–hoy).
                "extra_periods": extra,
                "date_candidates": _date_candidates(item) if unverified else [],
                "sort_order": item.get("sortOrder"),
                "domain": item.get("domain") or [],
                "responsibilities": item.get("responsibilities") or [],
                "technologies": _canonical_list(item.get("technologies"), known),
                "achievements": achievements,
                "scope": _role_scope(item),
                "kind": "employment",
            }
        )

    projects_out: list[dict] = []
    withheld_projects: list[dict] = []
    project_names: list[str] = []
    personal_products: list[str] = []
    for item in raw.get("projects") or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        project_names.append(name)
        if item.get("type") == "personal-product":
            personal_products.append(name)
        reason = _withhold_reason(item)
        if reason:
            # Se queda en el perfil maestro; no entra al prompt ni al CV hasta tener hechos.
            withheld_projects.append({"name": name, "reason": reason})
            continue
        projects_out.append(
            {
                "name": name,
                "type": item.get("type"),
                "is_employment": bool(item.get("isEmployment")),
                "status": item.get("status"),
                "description": cv_facing_text(str(item.get("description") or "")),
                "domain": item.get("domain") or [],
                "platforms": item.get("platforms") or [],
                "features": item.get("features") or [],
                "technologies": _canonical_list(item.get("technologies"), known),
                "scale": None if _is_meta(str(item.get("scale") or "")) else item.get("scale"),
                "unknown": _unresolved_items(item),
                "relevant_when": item.get("relevantWhenVacancyNeeds") or [],
            }
        )

    education_out = []
    for item in raw.get("education") or []:
        if not isinstance(item, dict) or not _safe_fact(item):
            continue
        if item.get("showInCv") is False:
            # Se queda en el perfil; el usuario pidió no mostrarlo en los CVs.
            continue
        education_out.append(
            {
                "degree": item.get("degree"),
                "institution": item.get("institution"),
                "start_date": item.get("startDate"),
                "end_date": item.get("endDate"),
                "graduation_year": item.get("graduationYear"),
                "status": item.get("status"),
            }
        )

    certifications_out = []
    for item in raw.get("certifications") or []:
        if not isinstance(item, dict) or not _safe_fact(item):
            continue
        certifications_out.append(
            {
                "name": item.get("name"),
                "issuer": item.get("issuer"),
                "year": item.get("year"),
                "status": item.get("status"),
            }
        )

    languages_out = []
    for item in raw.get("languages") or []:
        if not isinstance(item, dict) or not _safe_fact(item):
            continue
        if not item.get("level"):
            continue
        languages_out.append(
            {
                "language": item.get("language"),
                "level": item.get("level"),
            }
        )

    metrics_out = []
    for item in raw.get("metrics") or []:
        if not isinstance(item, dict) or not _safe_fact(item):
            continue
        if item.get("safeForCV") is False:
            continue
        metrics_out.append(
            {
                "value": item.get("value"),
                "unit": item.get("unit"),
                "type": item.get("type"),
                "description": item.get("description"),
                "company": item.get("company"),
                "project": item.get("project") or None,
                "project_id": item.get("projectId") or None,
            }
        )

    positioning = {}
    for title, pos in (raw.get("positioningProfiles") or {}).items():
        if not isinstance(pos, dict):
            continue
        positioning[title] = {
            "preferred_title": pos.get("preferredTitle") or title,
            "priority_skills": pos.get("prioritySkills") or [],
            "priority_companies": pos.get("priorityExperienceLabels") or [],
            "avoid_unless_relevant": pos.get("avoidUnlessRelevant") or [],
        }

    inventory = _unique_skills(skills)
    skill_aliases = _skill_aliases(raw)

    return {
        "name": profile.get("fullName"),
        "target_roles": profile.get("professionalTitles") or [],
        "contact": contact_out,
        "years_experience": years,
        "skills": skills,
        "skill_inventory": inventory,
        "skill_aliases": skill_aliases,
        "experience": experience_out,
        "allowed_companies": allowed_companies,
        "hidden_experience": hidden_experience,
        "projects": projects_out,
        "withheld_projects": withheld_projects,
        "project_names": project_names,
        "personal_products_not_employment": personal_products,
        "education": education_out,
        "certifications": certifications_out,
        "languages": languages_out,
        "metrics": metrics_out,
        "positioning": positioning,
        "closed_world_rules": [
            "This profile is the ONLY source of truth about the candidate.",
            "If a company, title, date, metric or project is not listed here, it does not exist.",
            "Do not invent companies, titles, dates, metrics, or projects.",
            "You MAY add technologies from the job description that are not in skill_inventory to the skills and keywords lists only. Never claim them inside an experience bullet.",
            "A skill in skill_inventory may appear in SKILLS, not automatically in EXPERIENCE.",
            "An experience bullet may only use responsibilities, achievements, technologies and metrics listed for that job.",
            "Do not attribute a metric to a project unless metrics[].project names that project.",
            "Items listed in a project's unknown[] are not known. Do not state them.",
            "If an experience has empty dates, the dates are unverified: do not write any date for it.",
            "Items in personal_products_not_employment are not jobs. Do not list them as employers.",
            "Copy company names and dates exactly from experience[].",
            "Write job titles without Freelance/Freelancer in the title.",
            "Do not put Fintech in UffPay job titles unless the JOB DESCRIPTION explicitly asks for fintech or financial-services experience.",
            "Only use metrics listed in metrics[] or in experience[].achievements.",
        ],
    }


def metric_text(metric: Optional[dict]) -> str:
    """{"value": 25.0, "unit": "percent"} → «25%»; {"value": 8, "unit": "s"} → «8 s»."""
    if not isinstance(metric, dict) or metric.get("value") is None:
        return ""
    value = metric["value"]
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    unit = str(metric.get("unit") or "").strip()
    if unit.lower() in {"percent", "%"}:
        return f"{value}%"
    return f"{value} {unit}".strip()


def _evidence_detail(ach: dict) -> dict:
    """Cómo se logró una cifra. Solo lo que el usuario declaró; sin notas internas."""
    raw = ach.get("evidenceDetail") or {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, Any] = {}
    for key in ("context", "action", "measurement"):
        text = str(raw.get(key) or "").strip()
        if text:
            out[key] = text
    techs = [str(t).strip() for t in raw.get("technologies") or [] if str(t).strip()]
    if techs:
        out["technologies"] = techs
    for key in ("before", "after"):
        if isinstance(raw.get(key), dict) and raw[key].get("value") is not None:
            out[key] = {"value": raw[key]["value"], "unit": raw[key].get("unit") or ""}
    return out


def _role_scope(item: dict) -> dict:
    raw = item.get("roleScope") or {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, Any] = {}
    if raw.get("teamSize") not in (None, ""):
        out["team_size"] = raw["teamSize"]
    highlights = [str(h).strip() for h in raw.get("highlights") or [] if str(h).strip()]
    if highlights:
        out["highlights"] = highlights
    return out


def _prompt_achievement(ach: dict) -> dict:
    desc = str(ach.get("description") or "").strip()
    if not desc:
        return {}
    detail = ach.get("detail") or {}
    out: dict[str, Any] = {"result": desc}
    metric = metric_text(ach.get("metric"))
    if metric:
        out["metric"] = metric
    if detail.get("before") and detail.get("after"):
        out["before_after"] = f"{metric_text(detail['before'])} → {metric_text(detail['after'])}"
    if detail.get("action"):
        out["how"] = detail["action"]
    if detail.get("technologies"):
        out["tools"] = detail["technologies"]
    if detail.get("measurement"):
        out["measured_by"] = detail["measurement"]
    if detail.get("context"):
        out["context"] = detail["context"]
    if ach.get("project"):
        out["project"] = ach["project"]
    return out


def profile_for_prompt(compact: dict) -> dict:
    """Mínimo de hechos para el modelo. El JSON maestro completo no entra al prompt."""
    experience = []
    for item in compact.get("experience") or []:
        achievements = [a for a in (_prompt_achievement(ach) for ach in item.get("achievements") or []) if a]
        experience.append(
            {
                "company": item.get("company"),
                "positions": item.get("positions") or [],
                "dates": item.get("dates") if item.get("dates_verified", True) else "",
                "responsibilities": item.get("responsibilities") or [],
                "technologies": item.get("technologies") or [],
                "achievements": achievements,
                "scope": item.get("scope") or {},
            }
        )

    projects = []
    for item in compact.get("projects") or []:
        desc = str(item.get("description") or "").strip()
        if len(desc) > 180:
            desc = desc[:177] + "…"
        projects.append(
            {
                "name": item.get("name"),
                "type": item.get("type"),
                "is_employment": bool(item.get("is_employment")),
                "technologies": item.get("technologies") or [],
                "description": desc,
                "unknown": item.get("unknown") or [],
            }
        )

    metrics = []
    for item in compact.get("metrics") or []:
        metrics.append(
            {
                "text": item.get("description"),
                "company": item.get("company"),
                "project": item.get("project"),
                "value": item.get("value"),
                "unit": item.get("unit"),
            }
        )

    return {
        "name": compact.get("name"),
        "target_roles": compact.get("target_roles") or [],
        "years_experience": compact.get("years_experience"),
        "skills": compact.get("skill_inventory") or [],
        "experience": experience,
        "projects": projects,
        "not_employment": compact.get("personal_products_not_employment") or [],
        "metrics": metrics,
    }


def load_compact_profile() -> dict:
    """Perfil compacto calculado en cada llamada a partir de ``master_profile.json``."""
    master = kb_dir() / "master_profile.json"
    if not master.exists():
        raise FileNotFoundError("No hay knowledge_base/master_profile.json")
    return build_compact_profile(json.loads(master.read_text(encoding="utf-8")))


def protected_terms(compact: dict) -> list[str]:
    """Nombres que no se traducen ni votan en la detección de idioma.

    Empresas, proyectos, productos, tecnologías y skills del perfil. Los cargos (positions)
    no van aquí: un título de puesto sí se traduce al idioma del CV.
    """
    terms: list[str] = []

    def add(value: Any) -> None:
        text = str(value or "").strip()
        if len(text) >= 2 and text not in terms:
            terms.append(text)

    add(compact.get("name"))
    for item in compact.get("experience") or []:
        add(item.get("company"))
        for tech in item.get("technologies") or []:
            add(tech)
    for name in compact.get("project_names") or []:
        add(name)
    for item in compact.get("projects") or []:
        add(item.get("name"))
        for tech in item.get("technologies") or []:
            add(tech)
    for name in compact.get("personal_products_not_employment") or []:
        add(name)
    for skill in compact.get("skill_inventory") or []:
        add(skill)
    for canon, aliases in (compact.get("skill_aliases") or {}).items():
        add(canon)
        for alias in aliases or []:
            add(alias)
    return terms


def base_cv_from_master(compact: dict):
    """Plantilla base derivada del perfil maestro.

    Sustituye a las antiguas ``knowledge_base/cv_*.json`` (eliminadas en ebc18f7): eran copias
    desactualizadas del perfil (p. ej. UffPay «Ene 2023 – Jul 2024») y el tailor ya tomaba
    todos los hechos del maestro. La base solo aporta identidad y contacto; no trae
    experiencia ni summary para que ningún fallback reintroduzca hechos sin validar.
    """
    from .models import CvDocument

    contact = compact.get("contact") or {}
    roles = [str(r).strip() for r in (compact.get("target_roles") or []) if str(r).strip()]
    keywords = [str(s).lower() for s in (compact.get("skill_inventory") or [])][:60]
    return CvDocument(
        id="master_profile",
        label="Perfil maestro",
        keywords=keywords,
        name=str(compact.get("name") or ""),
        title=roles[0] if roles else "",
        email=str(contact.get("email") or ""),
        phone=str(contact.get("phone") or ""),
        linkedin=str(contact.get("linkedin") or ""),
        location=str(contact.get("location") or ""),
    )
