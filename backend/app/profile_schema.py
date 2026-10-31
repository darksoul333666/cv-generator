"""Validación del perfil maestro en el backend.

El frontend valida con zod, pero una IA o una edición a mano escriben el JSON directo y no
pasan por ahí. Esta validación corre al guardar (``profile_store.write_profile``) y desde la
terminal::

    python -m app.validate_profile            # el perfil de knowledge_base
    python -m app.validate_profile otro.json  # cualquier archivo

Dos niveles:

- **errores**: forma rota (tipos, ids repetidos, fechas inválidas, valores fuera de lista).
  El perfil no se guarda.
- **avisos**: el perfil funciona, pero algo puede llegar mal al CV (notas internas en textos
  visibles, grafías distintas, cifras que no cuadran con su antes/después, tecnologías que no
  están en skills).
"""

from __future__ import annotations

import re
from typing import Any, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

_DATE_RE = re.compile(r"^\d{4}(-(0[1-9]|1[0-2]))?$")


def _check_date(value: Optional[str]) -> Optional[str]:
    if value in (None, ""):
        return value
    if not isinstance(value, str) or not _DATE_RE.match(value):
        raise ValueError(f"fecha «{value}» no es YYYY ni YYYY-MM")
    return value


class _Loose(BaseModel):
    # Las llaves que el modelo no nombra se conservan: valida lo importante sin bloquear
    # campos nuevos.
    model_config = ConfigDict(extra="allow")


class Metric(_Loose):
    value: Optional[float] = None
    unit: Optional[str] = ""


class Achievement(_Loose):
    description: str
    metric: Optional[Metric] = None
    evidenceDetail: Optional[dict] = None


class Period(_Loose):
    startDate: str
    endDate: Optional[str] = None
    current: bool = False

    _dates = field_validator("startDate", "endDate")(_check_date)


class RoleScope(_Loose):
    teamSize: Optional[Union[int, str]] = None
    highlights: List[str] = Field(default_factory=list)


class Experience(_Loose):
    id: str = Field(min_length=1)
    company: str = Field(min_length=1)
    roles: List[str]
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    current: bool = False
    showInCv: Optional[bool] = None
    additionalPeriods: List[Period] = Field(default_factory=list)
    responsibilities: List[str] = Field(default_factory=list)
    technologies: List[str] = Field(default_factory=list)
    achievements: List[Achievement] = Field(default_factory=list)
    roleScope: Optional[RoleScope] = None

    _dates = field_validator("startDate", "endDate")(_check_date)


class Project(_Loose):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = ""
    technologies: List[str] = Field(default_factory=list)
    contribution: Literal["", "full", "frontend", "backend", "lead"] = ""
    experienceId: Optional[str] = None
    engagement: Optional[Literal["", "employment", "freelance", "personal"]] = None


class Education(_Loose):
    id: str = Field(min_length=1)
    degree: str = Field(min_length=1)
    institution: str = ""
    startDate: Optional[str] = None
    endDate: Optional[str] = None

    _dates = field_validator("startDate", "endDate")(_check_date)


class Certification(_Loose):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    year: Optional[int] = None


class Language(_Loose):
    id: str = Field(min_length=1)
    language: str = Field(min_length=1)
    level: Optional[str] = None


class Profile(_Loose):
    fullName: str = Field(min_length=1)
    professionalTitles: List[str] = Field(default_factory=list)
    summary: str = ""
    contact: dict


class MasterProfileModel(_Loose):
    profile: Profile
    skills: dict[str, List[str]]
    experience: List[Experience]
    projects: List[Project] = Field(default_factory=list)
    education: List[Education] = Field(default_factory=list)
    certifications: List[Certification] = Field(default_factory=list)
    languages: List[Language] = Field(default_factory=list)
    conflicts: List[dict] = Field(default_factory=list)


# --- Reglas de contenido ---------------------------------------------------------------------

# Frases de trabajo interno que no deben llegar a un CV.
_INTERNAL_NOTE_RE = re.compile(
    r"cv hist[oó]rico|knowledge_base|\bcv_\d|UNRESOLVED|sin confirmar|sin detallar|"
    r"no se atribuye|seg[uú]n (?:los |el )?cvs?\b|en cvs? (?:web|fullstack)|no en todos los cvs",
    re.IGNORECASE,
)
_VERSION_RE = re.compile(r"^(.*?)[\s]+v?\d+(?:\.\d+)*$")


def _base_tech(name: str) -> str:
    m = _VERSION_RE.match(name.strip())
    return (m.group(1) if m else name).strip().lower()


def _fmt_loc(loc: tuple) -> str:
    return ".".join(str(part) for part in loc)


def _duplicates(items: list[dict], key: str = "id") -> list[str]:
    seen: set[str] = set()
    dup: list[str] = []
    for item in items:
        value = str(item.get(key) or "")
        if value in seen:
            dup.append(value)
        seen.add(value)
    return dup


def _date_order_errors(experience: list[dict]) -> list[str]:
    errors = []
    for item in experience:
        start, end = item.get("startDate"), item.get("endDate")
        if start and end and not item.get("current") and str(end) < str(start):
            errors.append(f"experience «{item.get('company')}»: termina ({end}) antes de empezar ({start})")
        if item.get("current") and end:
            errors.append(f"experience «{item.get('company')}»: es actual y también tiene fecha de fin")
    return errors


def _visible_texts(raw: dict) -> list[tuple[str, str]]:
    """Textos que pueden llegar al CV, con la ruta para el mensaje."""
    out: list[tuple[str, str]] = [("profile.summary", str((raw.get("profile") or {}).get("summary") or ""))]
    for exp in raw.get("experience") or []:
        name = exp.get("company")
        for i, text in enumerate(exp.get("responsibilities") or []):
            out.append((f"{name}.responsibilities[{i}]", str(text)))
        for i, ach in enumerate(exp.get("achievements") or []):
            if isinstance(ach, dict):
                out.append((f"{name}.achievements[{i}]", str(ach.get("description") or "")))
        for i, text in enumerate(((exp.get("roleScope") or {}).get("highlights")) or []):
            out.append((f"{name}.roleScope.highlights[{i}]", str(text)))
    for proj in raw.get("projects") or []:
        out.append((f"proyecto «{proj.get('name')}».description", str(proj.get("description") or "")))
        for i, text in enumerate(proj.get("features") or []):
            out.append((f"proyecto «{proj.get('name')}».features[{i}]", str(text)))
    return out


def _metric_mismatch(exp: dict) -> list[str]:
    """Un porcentaje que no cuadra con su antes/después (p. ej. 30% con 8 s → 3 s)."""
    warnings = []
    for ach in exp.get("achievements") or []:
        if not isinstance(ach, dict):
            continue
        metric = ach.get("metric") or {}
        detail = ach.get("evidenceDetail") or {}
        before, after = detail.get("before") or {}, detail.get("after") or {}
        try:
            pct = float(metric.get("value"))
            b, a = float(before.get("value")), float(after.get("value"))
        except (TypeError, ValueError):
            continue
        if str(metric.get("unit") or "") != "percent" or b <= 0:
            continue
        expected = (b - a) / b * 100
        if abs(expected - pct) > 5:
            warnings.append(
                f"«{exp.get('company')}»: el logro «{ach.get('description')}» dice {pct:g}% pero su antes/después "
                f"({b:g} → {a:g}) da {expected:.0f}%"
            )
    return warnings


def _tech_warnings(raw: dict) -> list[str]:
    from .compact_master import canonical_tech

    skills = raw.get("skills") or {}
    known = {
        _base_tech(str(name))
        for values in (skills.values() if isinstance(skills, dict) else [])
        for name in (values or [])
    }
    known |= {
        _base_tech(str(alias))
        for row in raw.get("skillCatalog") or []
        if isinstance(row, dict)
        for alias in [row.get("canonical"), *(row.get("aliases") or [])]
        if alias
    }
    warnings: list[str] = []
    missing: dict[str, list[str]] = {}
    sources = [(f"«{e.get('company')}»", e.get("technologies") or []) for e in raw.get("experience") or []]
    sources += [(f"proyecto «{p.get('name')}»", p.get("technologies") or []) for p in raw.get("projects") or []]
    for where, techs in sources:
        for tech in techs:
            name = str(tech)
            fixed = canonical_tech(name)
            if fixed != name:
                warnings.append(f"{where}: «{name}» se escribe «{fixed}»")
            if _base_tech(fixed) not in known:
                missing.setdefault(fixed, []).append(where)
    for tech, wheres in sorted(missing.items()):
        warnings.append(f"«{tech}» se usa en {', '.join(wheres)} pero no está en skills")
    return warnings


def _skill_duplicate_warnings(raw: dict) -> list[str]:
    seen: dict[str, str] = {}
    warnings = []
    for category, names in (raw.get("skills") or {}).items():
        for name in names or []:
            key = str(name).strip().lower()
            if key in seen and seen[key] != category:
                warnings.append(f"skill «{name}» está en {seen[key]} y en {category}")
            seen.setdefault(key, category)
    return warnings


def validate_profile(raw: Any) -> tuple[list[str], list[str]]:
    """Devuelve (errores, avisos). Sin errores, el perfil se puede guardar."""
    if not isinstance(raw, dict):
        return ["el perfil no es un objeto JSON"], []
    errors: list[str] = []
    try:
        MasterProfileModel.model_validate(raw)
    except ValidationError as exc:
        for item in exc.errors():
            errors.append(f"{_fmt_loc(item['loc'])}: {item['msg']}")
    for key in ("experience", "projects", "education", "certifications", "languages"):
        rows = [row for row in raw.get(key) or [] if isinstance(row, dict)]
        for dup in _duplicates(rows):
            errors.append(f"{key}: id repetido «{dup}»")
    errors += _date_order_errors([e for e in raw.get("experience") or [] if isinstance(e, dict)])
    exp_ids = {str(e.get("id")) for e in raw.get("experience") or [] if isinstance(e, dict)}
    for proj in raw.get("projects") or []:
        linked = proj.get("experienceId") if isinstance(proj, dict) else None
        if linked and linked not in exp_ids:
            errors.append(f"proyecto «{proj.get('name')}»: experienceId «{linked}» no existe en experience")
    if errors:
        return errors, []

    warnings: list[str] = []
    for where, text in _visible_texts(raw):
        m = _INTERNAL_NOTE_RE.search(text)
        if m:
            warnings.append(f"{where}: nota interna «{m.group(0)}» en un texto que puede llegar al CV")
    for exp in raw.get("experience") or []:
        warnings += _metric_mismatch(exp)
    warnings += _tech_warnings(raw)
    warnings += _skill_duplicate_warnings(raw)
    open_conflicts = [c for c in raw.get("conflicts") or [] if isinstance(c, dict) and not c.get("userValidated")]
    if open_conflicts:
        warnings.append(f"{len(open_conflicts)} conflictos abiertos")
    return errors, warnings
