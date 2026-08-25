"""Perfil cerrado y compacto para Ollama (cv-optimizer). No infiere ni resuelve conflictos."""

from __future__ import annotations

import json
import logging
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


def ollama_export_paths() -> list[Path]:
    paths = [kb_dir() / "ollama_profile.json"]
    home_copy = Path.home() / "cv-optimizer" / "master-profile.json"
    if home_copy.parent.is_dir():
        paths.append(home_copy)
    return paths


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


def build_ollama_profile(raw: dict) -> dict:
    """Hechos usables por el modelo. Omite inferred/conflicted y metadatos internos."""
    profile = raw.get("profile") or {}
    contact = profile.get("contact") or {}
    skills = raw.get("skills") or {}
    yoe = raw.get("yearsOfExperience") or {}

    contact_out: dict[str, str] = {}
    for key in ("email", "phone", "linkedin", "github", "website", "location"):
        value = _contact_value(contact.get(key) or {})
        if value and value.lower() not in {"omitido en cvs 2025–2026", "omitido"}:
            contact_out[key] = value

    years: Any = None
    if yoe.get("userValidated") or str(yoe.get("status") or "") in {"computed", "user_validated"}:
        years = yoe.get("value")

    experience_out: list[dict] = []
    allowed_companies: list[str] = []
    for item in raw.get("experience") or []:
        if not isinstance(item, dict):
            continue
        company = str(item.get("company") or "").strip()
        if not company:
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
                }
            )
        experience_out.append(
            {
                "id": item.get("id"),
                "company": company,
                "positions": item.get("roles") or [],
                "employment_type": item.get("employmentType"),
                "dates": _fmt_dates(item.get("startDate"), item.get("endDate"), bool(item.get("current"))),
                "start_date": item.get("startDate"),
                "end_date": item.get("endDate"),
                "current": bool(item.get("current")),
                "domain": item.get("domain") or [],
                "responsibilities": item.get("responsibilities") or [],
                "technologies": item.get("technologies") or [],
                "achievements": achievements,
                "kind": "employment",
            }
        )

    projects_out: list[dict] = []
    personal_products: list[str] = []
    for item in raw.get("projects") or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        if item.get("type") == "personal-product" or item.get("isEmployment") is False:
            if item.get("type") == "personal-product":
                personal_products.append(name)
        if not _safe_fact(item) and str(item.get("status") or "") == "mentioned":
            # mentioned historical projects stay, labeled as such
            pass
        projects_out.append(
            {
                "name": name,
                "type": item.get("type"),
                "is_employment": bool(item.get("isEmployment")),
                "status": item.get("status"),
                "description": item.get("description"),
                "domain": item.get("domain") or [],
                "platforms": item.get("platforms") or [],
                "features": item.get("features") or [],
                "technologies": item.get("technologies") or [],
                "scale": item.get("scale"),
                "relevant_when": item.get("relevantWhenVacancyNeeds") or [],
            }
        )

    education_out = []
    for item in raw.get("education") or []:
        if not isinstance(item, dict) or not _safe_fact(item):
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
        "projects": projects_out,
        "personal_products_not_employment": personal_products,
        "education": education_out,
        "certifications": certifications_out,
        "languages": languages_out,
        "metrics": metrics_out,
        "positioning": positioning,
        "closed_world_rules": [
            "This profile is the ONLY source of truth about the candidate.",
            "If a fact is not listed here, it does not exist.",
            "Do not invent companies, titles, dates, technologies, metrics, or projects.",
            "A skill in skill_inventory may appear in SKILLS, not automatically in EXPERIENCE.",
            "Items in personal_products_not_employment are not jobs. Do not list them as employers.",
            "Copy company names and dates exactly from experience[].",
            "Only use metrics listed in metrics[] or in experience[].achievements.",
        ],
    }


def profile_for_prompt(compact: dict) -> dict:
    """Mínimo de hechos para Ollama. El JSON maestro completo no entra al modelo."""
    experience = []
    for item in compact.get("experience") or []:
        achievements = []
        for ach in item.get("achievements") or []:
            desc = str(ach.get("description") or "").strip()
            metric = ach.get("metric") or {}
            if metric.get("value") is not None:
                unit = metric.get("unit") or ""
                desc = f"{desc} ({metric.get('value')} {unit})".strip()
            if desc:
                achievements.append(desc)
        experience.append(
            {
                "company": item.get("company"),
                "positions": item.get("positions") or [],
                "employment_type": item.get("employment_type"),
                "dates": item.get("dates"),
                "responsibilities": item.get("responsibilities") or [],
                "technologies": item.get("technologies") or [],
                "achievements": achievements,
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
            }
        )

    metrics = []
    for item in compact.get("metrics") or []:
        metrics.append(
            {
                "text": item.get("description"),
                "company": item.get("company"),
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


def export_ollama_profile(raw: dict) -> dict:
    compact = build_ollama_profile(raw)
    payload = json.dumps(compact, ensure_ascii=False, indent=2) + "\n"
    for path in ollama_export_paths():
        try:
            path.write_text(payload, encoding="utf-8")
        except OSError as exc:
            logger.warning("No se pudo exportar perfil Ollama a %s: %s", path, exc)
    return compact


def load_ollama_profile() -> dict:
    local = kb_dir() / "ollama_profile.json"
    master = kb_dir() / "master_profile.json"
    if master.exists():
        return build_ollama_profile(json.loads(master.read_text(encoding="utf-8")))
    if local.exists():
        return json.loads(local.read_text(encoding="utf-8"))
    raise FileNotFoundError("No hay master_profile.json ni ollama_profile.json")
