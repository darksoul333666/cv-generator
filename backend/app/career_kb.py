from __future__ import annotations

import re
from datetime import date
from typing import Any, List, Optional

from fastapi import HTTPException
from pydantic import BaseModel, Field


class UserValidationIn(BaseModel):
    field: str = Field(min_length=1)
    resolvedValue: str = Field(min_length=1)


class ExperienceEditItem(BaseModel):
    id: str = Field(min_length=1)
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    current: bool = False
    employmentType: Optional[str] = None


class ExperienceEditsIn(BaseModel):
    items: List[ExperienceEditItem]


def slug_skill_id(name: str) -> str:
    s = name.lower().replace(".", "").replace("++", "plus")
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return f"skill_{s}"[:72]


def sync_skill_catalog(raw: dict[str, Any], skills: dict[str, list[str]]) -> None:
    catalog: list[dict[str, Any]] = list(raw.get("skillCatalog") or [])
    by_name = {str(s.get("canonical", "")).lower(): s for s in catalog if s.get("canonical")}
    aliases: dict[str, Any] = raw.get("skillAliases") or {}

    for category, names in skills.items():
        for name in names:
            key = name.strip().lower()
            if not key:
                continue
            existing = by_name.get(key)
            if existing:
                cats = existing.setdefault("categories", [])
                if category not in cats:
                    cats.append(category)
                continue
            meta = aliases.get(name) or {}
            entry = {
                "id": meta.get("id") or slug_skill_id(name),
                "canonical": name,
                "aliases": list(meta.get("aliases") or []),
                "categories": [category],
                "evidenceLevel": "claimed",
                "sourceCount": None,
                "userValidated": False,
            }
            catalog.append(entry)
            by_name[key] = entry
    raw["skillCatalog"] = catalog


def _find_exp(raw: dict[str, Any], exp_id: str) -> dict[str, Any]:
    for ex in raw.get("experience") or []:
        if ex.get("id") == exp_id:
            return ex
    raise HTTPException(status_code=400, detail=f"Experiencia no encontrada: {exp_id}")


def _sync_timeline(raw: dict[str, Any], exp_id: str) -> None:
    ex = _find_exp(raw, exp_id)
    for row in raw.get("careerTimeline") or []:
        if row.get("experienceId") == exp_id:
            row["startDate"] = ex.get("startDate")
            row["endDate"] = ex.get("endDate")
            row["dateStatus"] = ex.get("dateStatus")
            row["userValidated"] = True


def _set_contact(raw: dict[str, Any], key: str, value: str) -> None:
    field = raw["profile"]["contact"][key]
    field["value"] = value
    field["status"] = "user_validated"
    field["evidenceLevel"] = "verified"
    field["userValidated"] = True
    for c in field.get("candidates") or []:
        c["userValidated"] = c.get("value") == value


def _parse_range(value: str) -> tuple[str | None, str | None]:
    parts = re.split(r"\s*[–-]\s*", value.strip())
    if len(parts) != 2:
        return None, None
    start, end = parts[0].strip(), parts[1].strip()
    date_re = re.compile(r"^\d{4}(-\d{2})?$")
    return (start if date_re.match(start) else None, end if date_re.match(end) else None)


_PRESENT_RE = re.compile(r"^(actualidad|present|presente|current|actual)$", re.IGNORECASE)


def _range_parts(value: str) -> tuple[str | None, str | None, bool]:
    """«2024-01 – 2024-07» / «2026-04 – Actualidad» / «2024-01» → (inicio, fin, actual)."""
    parts = [p.strip() for p in re.split(r"\s+[–-]\s+|\s*–\s*", value.strip()) if p.strip()]
    date_re = re.compile(r"^\d{4}(-\d{2})?$")
    start = parts[0] if parts and date_re.match(parts[0]) else None
    end: str | None = None
    current = False
    if len(parts) >= 2:
        if _PRESENT_RE.match(parts[1]):
            current = True
        elif date_re.match(parts[1]):
            end = parts[1]
    return start, end, current


def date_conflict_open(ex: dict[str, Any]) -> bool:
    conflict = ex.get("dateConflict")
    return isinstance(conflict, dict) and str(conflict.get("status") or "").lower() in {"unresolved", "pending"}


def _close_date_conflict(ex: dict[str, Any], resolved_value: str, via: str) -> None:
    conflict = ex.get("dateConflict")
    if not isinstance(conflict, dict):
        return
    conflict["status"] = "user_resolved"
    conflict["resolvedValue"] = resolved_value
    conflict["resolvedAt"] = date.today().isoformat()
    conflict["resolvedVia"] = via


def _dates_changed(ex: dict[str, Any], start: Any, end: Any, current: bool) -> bool:
    return (start, end, bool(current)) != (ex.get("startDate"), ex.get("endDate"), bool(ex.get("current")))


def _set_validated_range(ex: dict[str, Any], resolved_value: str, via: str) -> None:
    """Una validación explícita del usuario con un rango cierra el conflicto de fechas."""
    start, end, current = _range_parts(resolved_value)
    if start:
        ex["startDate"] = start
    if end or current:
        ex["endDate"] = None if current else end
        ex["current"] = current
    ex["userValidated"] = True
    if ex.get("startDate") and (ex.get("endDate") or ex.get("current")):
        ex["dateStatus"] = "verified"
        _close_date_conflict(ex, resolved_value, via)


def apply_user_validation(raw: dict[str, Any], field: str, resolved_value: str) -> dict[str, Any]:
    conflict = next((c for c in raw.get("conflicts") or [] if c.get("field") == field), None)
    previous = list(conflict.get("values") or []) if conflict else []

    if field == "profile.contact.email":
        _set_contact(raw, "email", resolved_value)
    elif field == "profile.contact.phone":
        _set_contact(raw, "phone", resolved_value)
    elif field == "profile.contact.location":
        _set_contact(raw, "location", resolved_value)
    elif field == "yearsOfExperience":
        yoe = raw.setdefault("yearsOfExperience", {})
        yoe["source"] = "user"
        yoe["status"] = "user_validated"
        yoe["userValidated"] = True
        yoe["evidenceLevel"] = "verified"
        numeric = re.sub(r"[^\d.]", "", resolved_value)
        yoe["value"] = float(numeric) if numeric else None
    elif field == "experience.Grainchain.startDate":
        ex = _find_exp(raw, "exp_grainchain")
        ex["startDate"] = resolved_value
        ex["userValidated"] = True
        if ex.get("endDate"):
            ex["dateStatus"] = "verified"
        _sync_timeline(raw, "exp_grainchain")
    elif field == "experience.UffPay.startDate":
        # Antes guardaba el rango completo («2024-01 – 2024-07») dentro de startDate.
        ex = _find_exp(raw, "exp_uffpay")
        _set_validated_range(ex, resolved_value, "PUT /v1/master-profile/validations")
        _sync_timeline(raw, "exp_uffpay")
    elif field == "experience.MonkeyCave.dates":
        ex = _find_exp(raw, "exp_monkey_cave")
        _set_validated_range(ex, resolved_value, "PUT /v1/master-profile/validations")
        _sync_timeline(raw, "exp_monkey_cave")
    elif field == "languages.English.level":
        for lang in raw.get("languages") or []:
            if lang.get("id") == "lang_english":
                lang["level"] = resolved_value
                lang["status"] = "user_validated"
                lang["evidenceLevel"] = "verified"
                lang["userValidated"] = True
                break
    # Unknown fields still record the user decision without rewriting entities.

    if conflict:
        conflict["preferredValue"] = resolved_value
        conflict["resolution"] = "user_validated"
        conflict["userValidated"] = True
        conflict.pop("conflictingResolutions", None)

    uv = raw.setdefault(
        "userValidation",
        {"pending": [], "resolved": [], "lastUpdated": None},
    )
    uv["pending"] = [p for p in uv.get("pending") or [] if p != field]
    uv.setdefault("resolved", []).append(
        {
            "field": field,
            "previousValues": previous,
            "resolvedValue": resolved_value,
            "resolvedAt": date.today().isoformat(),
            "source": "user",
        }
    )
    uv["lastUpdated"] = date.today().isoformat()
    return raw


DATE_RE = re.compile(r"^\d{4}(-\d{2})?$")
ALLOWED_EMPLOYMENT = {
    "full-time",
    "freelance",
    "contract",
    "remote",
    "onsite",
}

CONFLICT_FIELDS_BY_EXP = {
    "exp_grainchain": ["experience.Grainchain.startDate"],
    "exp_uffpay": ["experience.UffPay.startDate"],
    "exp_monkey_cave": ["experience.MonkeyCave.dates"],
}


def _norm_date(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    if not DATE_RE.match(text):
        raise HTTPException(status_code=400, detail=f"Fecha inválida: {value}")
    return text


def _month_index(value: str) -> tuple[int, int]:
    year = int(value[:4])
    month = int(value[5:7]) if len(value) >= 7 else 1
    return year, month


def _maybe_compute_yoe(raw: dict[str, Any]) -> None:
    yoe = raw.setdefault("yearsOfExperience", {})
    intervals: list[tuple[date, date]] = []
    today = date.today()
    for ex in raw.get("experience") or []:
        start_raw = ex.get("startDate")
        if not start_raw:
            yoe["value"] = None
            yoe["source"] = None
            yoe["status"] = "requires_validation"
            yoe["userValidated"] = False
            return
        sy, sm = _month_index(start_raw)
        start = date(sy, sm, 1)
        if ex.get("current"):
            end = today
        elif ex.get("endDate"):
            ey, em = _month_index(ex["endDate"])
            end = date(ey, em, 1)
        else:
            yoe["value"] = None
            yoe["source"] = None
            yoe["status"] = "requires_validation"
            yoe["userValidated"] = False
            return
        if end < start:
            yoe["value"] = None
            yoe["status"] = "requires_validation"
            return
        intervals.append((start, end))
    if not intervals:
        return
    intervals.sort()
    merged: list[tuple[date, date]] = [intervals[0]]
    for start, end in intervals[1:]:
        last_s, last_e = merged[-1]
        if start <= last_e:
            merged[-1] = (last_s, max(last_e, end))
        else:
            merged.append((start, end))
    days = sum((end - start).days for start, end in merged)
    years = round(days / 365.25, 1)
    yoe = raw.setdefault("yearsOfExperience", {})
    yoe["value"] = years
    yoe["source"] = "computed_from_user_validated_dates"
    yoe["status"] = "computed"
    yoe["userValidated"] = True
    yoe["evidenceLevel"] = "verified"


def _mark_conflict_resolved(raw: dict[str, Any], field: str, resolved_value: str) -> None:
    conflict = next((c for c in raw.get("conflicts") or [] if c.get("field") == field), None)
    previous = list(conflict.get("values") or []) if conflict else []
    if conflict:
        conflict["preferredValue"] = resolved_value
        conflict["resolution"] = "user_validated"
        conflict["userValidated"] = True
    uv = raw.setdefault(
        "userValidation",
        {"pending": [], "resolved": [], "lastUpdated": None},
    )
    uv["pending"] = [p for p in uv.get("pending") or [] if p != field]
    uv.setdefault("resolved", []).append(
        {
            "field": field,
            "previousValues": previous,
            "resolvedValue": resolved_value,
            "resolvedAt": date.today().isoformat(),
            "source": "user",
        }
    )
    uv["lastUpdated"] = date.today().isoformat()


def apply_experience_edits(raw: dict[str, Any], items: list[ExperienceEditItem]) -> dict[str, Any]:
    existing = {ex.get("id"): ex for ex in raw.get("experience") or [] if ex.get("id")}
    ordered: list[dict[str, Any]] = []
    seen: set[str] = set()

    for index, item in enumerate(items):
        if item.id in seen:
            raise HTTPException(status_code=400, detail=f"ID duplicado: {item.id}")
        ex = existing.get(item.id)
        if not ex:
            raise HTTPException(status_code=400, detail=f"Experiencia no encontrada: {item.id}")
        seen.add(item.id)

        emp = (item.employmentType or "").strip() or None
        if emp and emp not in ALLOWED_EMPLOYMENT:
            raise HTTPException(status_code=400, detail=f"employmentType inválido: {emp}")

        start = _norm_date(item.startDate)
        end = None if item.current else _norm_date(item.endDate)
        if start and end:
            if _month_index(end) < _month_index(start):
                raise HTTPException(
                    status_code=400,
                    detail=f"La fecha fin no puede ser anterior al inicio ({ex.get('company')})",
                )

        orig = ex.setdefault("originalValues", {})
        orig.setdefault("startDate", ex.get("startDate"))
        orig.setdefault("endDate", ex.get("endDate"))
        orig.setdefault("employmentType", ex.get("employmentType"))

        # Reenviar las mismas fechas no resuelve un conflicto abierto; cambiarlas sí.
        changed = _dates_changed(ex, start, end, item.current)
        keep_conflict = date_conflict_open(ex) and not changed
        ex["startDate"] = start
        ex["endDate"] = end
        ex["current"] = bool(item.current)
        ex["employmentType"] = emp
        ex["sortOrder"] = index
        ex["userValidated"] = True
        if keep_conflict:
            ex["dateStatus"] = "conflicted"
        elif start and (end or item.current):
            ex["dateStatus"] = "verified"
            ex["evidenceLevel"] = "verified"
            if date_conflict_open(ex):
                _close_date_conflict(
                    ex, f"{start} – {'Actualidad' if item.current else end}", "editor de experiencia"
                )
        elif start or end:
            ex["dateStatus"] = "requires_validation"

        ordered.append(ex)

        if keep_conflict or not changed:
            # Guardar sin tocar las fechas no es una resolución del usuario: no se registra.
            continue

        resolved_range = " – ".join(
            [
                start or "?",
                "Actualidad" if item.current else (end or "?"),
            ]
        )
        if start or end or item.current:
            for field in CONFLICT_FIELDS_BY_EXP.get(item.id, []):
                _mark_conflict_resolved(raw, field, resolved_range)

    for ex in raw.get("experience") or []:
        if ex.get("id") not in seen:
            ordered.append(ex)
    raw["experience"] = ordered

    by_id = {ex["id"]: ex for ex in ordered if ex.get("id")}
    tl_by = {row.get("experienceId"): row for row in raw.get("careerTimeline") or []}
    new_tl: list[dict[str, Any]] = []
    for ex in ordered:
        eid = ex.get("id")
        row = tl_by.get(eid)
        if not row:
            continue
        row["startDate"] = ex.get("startDate")
        row["endDate"] = ex.get("endDate")
        row["dateStatus"] = ex.get("dateStatus")
        row["userValidated"] = True
        row["current"] = bool(ex.get("current"))
        new_tl.append(row)
    for row in raw.get("careerTimeline") or []:
        if row.get("experienceId") not in by_id:
            new_tl.append(row)
    raw["careerTimeline"] = new_tl

    _maybe_compute_yoe(raw)
    uv = raw.setdefault(
        "userValidation",
        {"pending": [], "resolved": [], "lastUpdated": None},
    )
    uv.setdefault("resolved", []).append(
        {
            "field": "experience",
            "previousValues": [],
            "resolvedValue": "order_dates_employmentType",
            "resolvedAt": date.today().isoformat(),
            "source": "user",
        }
    )
    uv["lastUpdated"] = date.today().isoformat()
    return raw


_ID_RE = re.compile(r"^[A-Za-z0-9_]{1,80}$")


class AchievementIn(BaseModel):
    description: str = ""
    metricValue: Optional[float] = None
    metricUnit: str = ""


class ExperienceContentIn(BaseModel):
    id: str = Field(min_length=1)
    company: str = Field(min_length=1)
    roles: List[str] = Field(default_factory=list)
    employmentType: Optional[str] = None
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    current: bool = False
    responsibilities: List[str] = Field(default_factory=list)
    technologies: List[str] = Field(default_factory=list)
    achievements: List[AchievementIn] = Field(default_factory=list)


class EducationContentIn(BaseModel):
    id: str = Field(min_length=1)
    degree: str = Field(min_length=1)
    institution: str = ""
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    graduationYear: Optional[int] = None


class CertificationContentIn(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    issuer: str = ""
    year: Optional[int] = None


class LanguageContentIn(BaseModel):
    id: str = Field(min_length=1)
    language: str = Field(min_length=1)
    level: Optional[str] = None


class ProjectContentIn(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    type: str = ""
    description: str = ""
    technologies: List[str] = Field(default_factory=list)


class ProfileIdentityIn(BaseModel):
    fullName: str = Field(min_length=1)
    professionalTitles: List[str] = Field(default_factory=list)
    summary: str = ""
    email: str = ""
    phone: str = ""
    linkedin: str = ""
    location: str = ""


class ProfileContentIn(BaseModel):
    profile: ProfileIdentityIn
    experience: List[ExperienceContentIn] = Field(default_factory=list)
    projects: List[ProjectContentIn] = Field(default_factory=list)
    education: List[EducationContentIn] = Field(default_factory=list)
    certifications: List[CertificationContentIn] = Field(default_factory=list)
    languages: List[LanguageContentIn] = Field(default_factory=list)


def _check_id(value: str, label: str) -> str:
    text = value.strip()
    if not _ID_RE.match(text):
        raise HTTPException(status_code=400, detail=f"ID inválido en {label}: {value}")
    return text


def _unique_ids(ids: list[str], label: str) -> None:
    seen: set[str] = set()
    for item_id in ids:
        if item_id in seen:
            raise HTTPException(status_code=400, detail=f"ID duplicado en {label}: {item_id}")
        seen.add(item_id)


def _clean_str_list(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in values:
        text = " ".join(str(raw).split())
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


def _mark_user_fact(item: dict[str, Any]) -> None:
    item["userValidated"] = True
    level = str(item.get("evidenceLevel") or "")
    if level in {"", "inferred", "conflicted"}:
        item["evidenceLevel"] = "documented"
    status = str(item.get("status") or "")
    if "status" in item and status in {"", "inferred", "conflicted", "requires_validation"}:
        item["status"] = "user_validated"


def _set_contact_value(raw: dict[str, Any], key: str, value: str) -> None:
    contact = raw.setdefault("profile", {}).setdefault("contact", {})
    field = contact.get(key)
    if not isinstance(field, dict):
        field = {
            "value": None,
            "status": "user_validated",
            "evidenceLevel": "verified",
            "sourceCount": 1,
            "userValidated": True,
            "candidates": [],
        }
        contact[key] = field
    text = value.strip()
    field["value"] = text or None
    field["status"] = "user_validated"
    field["evidenceLevel"] = "verified"
    field["userValidated"] = True
    for candidate in field.get("candidates") or []:
        if isinstance(candidate, dict):
            candidate["userValidated"] = candidate.get("value") == text


def _apply_identity(raw: dict[str, Any], identity: ProfileIdentityIn) -> None:
    profile = raw.setdefault("profile", {})
    name = " ".join(identity.fullName.split())
    if not name:
        raise HTTPException(status_code=400, detail="El nombre no puede estar vacío")
    titles = _clean_str_list(identity.professionalTitles)
    if not titles:
        raise HTTPException(status_code=400, detail="Agrega al menos un título profesional")
    profile["fullName"] = name
    profile["professionalTitles"] = titles
    profile["summary"] = identity.summary.strip()
    _set_contact_value(raw, "email", identity.email)
    _set_contact_value(raw, "phone", identity.phone)
    _set_contact_value(raw, "linkedin", identity.linkedin)
    _set_contact_value(raw, "location", identity.location)


def _achievement_dict(item: AchievementIn) -> Optional[dict[str, Any]]:
    description = " ".join(item.description.split())
    unit = " ".join(item.metricUnit.split())
    if item.metricValue is None and not description:
        return None
    if not description:
        raise HTTPException(status_code=400, detail="Un logro necesita descripción")
    return {
        "description": description,
        "metric": {
            "value": item.metricValue,
            "unit": unit,
            "type": "user_metric" if item.metricValue is not None else "",
        },
        "status": "user_validated",
        "evidenceLevel": "claimed",
        "safeForCV": True,
        "requiresUserValidation": False,
    }


# Campos que el editor de Skills no conoce y no debe borrar al guardar.
_ACHIEVEMENT_EXTRAS = ("evidenceDetail", "project")


def _metric_key(ach: dict[str, Any]) -> tuple:
    metric = ach.get("metric") or {}
    value = metric.get("value")
    try:
        value = float(value) if value is not None else None
    except (TypeError, ValueError):
        pass
    return (value, str(metric.get("unit") or "").lower())


def _keep_achievement_extras(new: dict[str, Any], previous: list[Any], position: int) -> dict[str, Any]:
    """Conserva la evidencia (cómo, medición, antes/después) y el proyecto del logro anterior.

    Empareja por descripción; si cambió, por la misma cifra; si no, por posición con la misma cifra.
    """
    old_items = [a for a in previous if isinstance(a, dict)]
    desc = " ".join(str(new.get("description") or "").lower().split())
    match = next(
        (a for a in old_items if " ".join(str(a.get("description") or "").lower().split()) == desc), None
    )
    if match is None and _metric_key(new)[0] is not None:
        same = [a for a in old_items if _metric_key(a) == _metric_key(new)]
        if len(same) == 1:
            match = same[0]
    if match is None and position < len(previous) and isinstance(previous[position], dict):
        if _metric_key(previous[position]) == _metric_key(new):
            match = previous[position]
    if match:
        for key in _ACHIEVEMENT_EXTRAS:
            if key in match and key not in new:
                new[key] = match[key]
    return new


def _blank_experience(item_id: str) -> dict[str, Any]:
    return {
        "id": item_id,
        "company": "",
        "roles": [],
        "employmentType": None,
        "startDate": None,
        "endDate": None,
        "current": False,
        "sortOrder": 0,
        "dateStatus": "claimed",
        "sourceValues": {},
        "originalValues": {},
        "userValidated": True,
        "conflicts": [],
        "domain": [],
        "responsibilities": [],
        "technologies": [],
        "achievements": [],
        "evidence": [],
        "sourceRefs": ["user"],
        "evidenceLevel": "documented",
        "sourceCount": 1,
    }


def _apply_experience_content(raw: dict[str, Any], items: list[ExperienceContentIn]) -> list[dict[str, Any]]:
    ids = [_check_id(item.id, "experiencia") for item in items]
    _unique_ids(ids, "experiencia")
    existing = {ex.get("id"): ex for ex in raw.get("experience") or [] if isinstance(ex, dict)}
    ordered: list[dict[str, Any]] = []

    for index, item in enumerate(items):
        item_id = ids[index]
        company = " ".join(item.company.split())
        roles = _clean_str_list(item.roles)
        if not company:
            raise HTTPException(status_code=400, detail="Cada experiencia necesita empresa")
        hidden = (existing.get(item_id) or {}).get("showInCv") is False
        if not roles and not hidden:
            # Un empleo oculto en CVs (p. ej. Corus, cargo aún sin confirmar) puede no tener rol.
            raise HTTPException(status_code=400, detail=f"Agrega al menos un rol en {company}")
        emp = (item.employmentType or "").strip() or None
        if emp and emp not in ALLOWED_EMPLOYMENT:
            raise HTTPException(status_code=400, detail=f"employmentType inválido: {emp}")
        start = _norm_date(item.startDate)
        end = None if item.current else _norm_date(item.endDate)
        if start and end and _month_index(end) < _month_index(start):
            raise HTTPException(
                status_code=400,
                detail=f"La fecha fin no puede ser anterior al inicio ({company})",
            )
        previous = list((existing.get(item_id) or {}).get("achievements") or [])
        achievements = []
        for position, ach in enumerate(item.achievements):
            dumped = _achievement_dict(ach)
            if dumped:
                achievements.append(_keep_achievement_extras(dumped, previous, position))

        ex = existing.get(item_id) or _blank_experience(item_id)
        keep_conflict = date_conflict_open(ex) and not _dates_changed(ex, start, end, item.current)
        ex["company"] = company
        ex["roles"] = roles
        ex["employmentType"] = emp
        ex["startDate"] = start
        ex["endDate"] = end
        ex["current"] = bool(item.current)
        ex["sortOrder"] = index
        ex["responsibilities"] = _clean_str_list(item.responsibilities)
        ex["technologies"] = _clean_str_list(item.technologies)
        ex["achievements"] = achievements
        ex["userValidated"] = True
        if str(ex.get("evidenceLevel") or "") in {"", "inferred", "conflicted"}:
            ex["evidenceLevel"] = "documented"
        if keep_conflict:
            # Guardar el perfil con las mismas fechas no las convierte en verificadas.
            ex["dateStatus"] = "conflicted"
        elif start and (end or item.current):
            ex["dateStatus"] = "verified"
            if date_conflict_open(ex):
                _close_date_conflict(
                    ex, f"{start} – {'Actualidad' if item.current else end}", "editor de perfil"
                )
        elif start or end:
            ex["dateStatus"] = "claimed"
        ordered.append(ex)

    raw["experience"] = ordered
    old_rows = {
        row.get("experienceId"): row
        for row in raw.get("careerTimeline") or []
        if isinstance(row, dict)
    }
    timeline: list[dict[str, Any]] = []
    for ex in ordered:
        roles = ex.get("roles") or []
        row = old_rows.get(ex["id"]) or {
            "id": f"tl_{ex['id']}",
            "experienceId": ex["id"],
            "sourceValues": {},
            "kind": "employment",
        }
        row["company"] = ex["company"]
        row["role"] = roles[0] if roles else ""
        row["roles"] = roles
        row["startDate"] = ex.get("startDate")
        row["endDate"] = ex.get("endDate")
        row["dateStatus"] = ex.get("dateStatus")
        row["userValidated"] = True
        row["current"] = bool(ex.get("current"))
        row["kind"] = row.get("kind") or "employment"
        timeline.append(row)
    raw["careerTimeline"] = timeline
    _sync_experience_metrics(raw, ordered)
    _maybe_compute_yoe(raw)
    return ordered


def _project_id(raw: dict[str, Any], name: Any) -> Optional[str]:
    key = str(name or "").strip().lower()
    if not key:
        return None
    for project in raw.get("projects") or []:
        if isinstance(project, dict) and str(project.get("name") or "").strip().lower() == key:
            return project.get("id")
    return None


def _sync_experience_metrics(raw: dict[str, Any], experiences: list[dict[str, Any]]) -> None:
    kept_companies = {str(ex.get("company") or "").strip().lower() for ex in experiences}
    kept: list[dict[str, Any]] = []
    for metric in raw.get("metrics") or []:
        if not isinstance(metric, dict):
            continue
        if metric.get("experienceId"):
            continue
        company = str(metric.get("company") or "").strip().lower()
        if company and company not in kept_companies:
            continue
        kept.append(metric)
    for ex in experiences:
        for index, ach in enumerate(ex.get("achievements") or []):
            metric = ach.get("metric") or {}
            value = metric.get("value")
            if value is None:
                continue
            unit = str(metric.get("unit") or "").strip() or "count"
            kept.append(
                {
                    "id": f"metric_{ex['id']}_{index}",
                    "value": value,
                    "unit": unit,
                    "type": str(metric.get("type") or "user_metric"),
                    "description": ach.get("description") or "",
                    "company": ex.get("company") or "",
                    "project": ach.get("project") or "",
                    "status": "user_validated",
                    "confidence": "high",
                    "experienceId": ex["id"],
                    "projectId": _project_id(raw, ach.get("project")),
                    "evidenceLevel": "claimed",
                    "sourceCount": 1,
                    "userValidated": True,
                    "safeForCV": True,
                    "requiresUserValidation": False,
                    "sourceRefs": ["user"],
                }
            )
    raw["metrics"] = kept


def _apply_projects(raw: dict[str, Any], items: list[ProjectContentIn]) -> set[str]:
    ids = [_check_id(item.id, "proyectos") for item in items]
    _unique_ids(ids, "proyectos")
    existing = {row.get("id"): row for row in raw.get("projects") or [] if isinstance(row, dict)}
    ordered: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        item_id = ids[index]
        name = " ".join(item.name.split())
        if not name:
            raise HTTPException(status_code=400, detail="Cada proyecto necesita nombre")
        row = existing.get(item_id) or {
            "id": item_id,
            "name": name,
            "type": "project",
            "description": "",
            "domain": [],
            "platforms": [],
            "features": [],
            "technologies": [],
            "scale": None,
            "status": "user_validated",
            "evidenceLevel": "documented",
            "sourceCount": 1,
            "userValidated": True,
            "evidence": [],
            "sourceRefs": ["user"],
            "isEmployment": False,
        }
        row["name"] = name
        row["type"] = item.type.strip() or row.get("type") or "project"
        row["description"] = item.description.strip()
        row["technologies"] = _clean_str_list(item.technologies)
        _mark_user_fact(row)
        if "isEmployment" not in row:
            row["isEmployment"] = False
        ordered.append(row)
    raw["projects"] = ordered
    return {row["id"] for row in ordered}


def _apply_education(raw: dict[str, Any], items: list[EducationContentIn]) -> None:
    ids = [_check_id(item.id, "educación") for item in items]
    _unique_ids(ids, "educación")
    existing = {row.get("id"): row for row in raw.get("education") or [] if isinstance(row, dict)}
    ordered: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        item_id = ids[index]
        degree = " ".join(item.degree.split())
        if not degree:
            raise HTTPException(status_code=400, detail="Cada estudio necesita el título o grado")
        row = existing.get(item_id) or {
            "id": item_id,
            "degree": degree,
            "institution": "",
            "startDate": None,
            "endDate": None,
            "graduationYear": None,
            "status": "user_validated",
            "evidenceLevel": "documented",
            "sourceCount": 1,
            "userValidated": True,
            "sourceRefs": ["user"],
        }
        row["degree"] = degree
        row["institution"] = " ".join(item.institution.split())
        row["startDate"] = _norm_date(item.startDate)
        row["endDate"] = _norm_date(item.endDate)
        row["graduationYear"] = item.graduationYear
        _mark_user_fact(row)
        ordered.append(row)
    raw["education"] = ordered


def _apply_certifications(raw: dict[str, Any], items: list[CertificationContentIn]) -> None:
    ids = [_check_id(item.id, "certificaciones") for item in items]
    _unique_ids(ids, "certificaciones")
    existing = {row.get("id"): row for row in raw.get("certifications") or [] if isinstance(row, dict)}
    ordered: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        item_id = ids[index]
        name = " ".join(item.name.split())
        if not name:
            raise HTTPException(status_code=400, detail="Cada certificación necesita nombre")
        row = existing.get(item_id) or {
            "id": item_id,
            "name": name,
            "issuer": "",
            "year": None,
            "status": "user_validated",
            "evidenceLevel": "documented",
            "sourceCount": 1,
            "userValidated": True,
            "sourceRefs": ["user"],
        }
        row["name"] = name
        row["issuer"] = " ".join(item.issuer.split())
        row["year"] = item.year
        _mark_user_fact(row)
        ordered.append(row)
    raw["certifications"] = ordered


def _apply_languages(raw: dict[str, Any], items: list[LanguageContentIn]) -> None:
    ids = [_check_id(item.id, "idiomas") for item in items]
    _unique_ids(ids, "idiomas")
    existing = {row.get("id"): row for row in raw.get("languages") or [] if isinstance(row, dict)}
    ordered: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        item_id = ids[index]
        language = " ".join(item.language.split())
        if not language:
            raise HTTPException(status_code=400, detail="Cada idioma necesita nombre")
        level = " ".join((item.level or "").split()) or None
        row = existing.get(item_id) or {
            "id": item_id,
            "language": language,
            "level": level,
            "status": "user_validated",
            "evidenceLevel": "documented",
            "sourceCount": 1,
            "userValidated": True,
            "conflicts": [],
            "sourceRefs": ["user"],
        }
        row["language"] = language
        row["level"] = level
        if not isinstance(row.get("conflicts"), list):
            row["conflicts"] = []
        if not isinstance(row.get("sourceRefs"), list):
            row["sourceRefs"] = ["user"]
        _mark_user_fact(row)
        ordered.append(row)
    raw["languages"] = ordered


def _prune_positioning(
    raw: dict[str, Any],
    experience_ids: set[str],
    companies: set[str],
    project_ids: set[str],
    project_names: set[str],
) -> None:
    profiles = raw.get("positioningProfiles") or {}
    if not isinstance(profiles, dict):
        return
    for pos in profiles.values():
        if not isinstance(pos, dict):
            continue
        pos["priorityExperience"] = [
            item for item in pos.get("priorityExperience") or [] if item in experience_ids
        ]
        pos["priorityExperienceLabels"] = [
            label
            for label in pos.get("priorityExperienceLabels") or []
            if str(label).strip().lower() in companies
        ]
        pos["priorityProjects"] = [
            item for item in pos.get("priorityProjects") or [] if item in project_ids
        ]
        if "priorityProjectLabels" in pos:
            pos["priorityProjectLabels"] = [
                label
                for label in pos.get("priorityProjectLabels") or []
                if str(label).strip().lower() in project_names
            ]


def apply_profile_content(raw: dict[str, Any], content: ProfileContentIn) -> dict[str, Any]:
    _apply_identity(raw, content.profile)
    experiences = _apply_experience_content(raw, content.experience)
    project_ids = _apply_projects(raw, content.projects)
    _apply_education(raw, content.education)
    _apply_certifications(raw, content.certifications)
    _apply_languages(raw, content.languages)
    project_names = {
        str(row.get("name") or "").strip().lower()
        for row in raw.get("projects") or []
        if isinstance(row, dict)
    }
    _prune_positioning(
        raw,
        {ex["id"] for ex in experiences},
        {str(ex.get("company") or "").strip().lower() for ex in experiences},
        project_ids,
        project_names,
    )
    uv = raw.setdefault(
        "userValidation",
        {"pending": [], "resolved": [], "lastUpdated": None},
    )
    uv.setdefault("resolved", []).append(
        {
            "field": "profile.content",
            "previousValues": [],
            "resolvedValue": "identity_experience_education",
            "resolvedAt": date.today().isoformat(),
            "source": "user",
        }
    )
    uv["lastUpdated"] = date.today().isoformat()
    return raw


# --- Evidencia de logros y alcance de cargos --------------------------------------------------

_POINT_RE = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*(ms|s|seg|segundos|min|minutos|%)?\s*$", re.IGNORECASE)
_POINT_UNITS = {"seg": "s", "segundos": "s", "minutos": "min"}


class EvidenceIn(BaseModel):
    """Respuesta del usuario sobre cómo logró una cifra o qué alcance tuvo su cargo."""

    experienceId: str = Field(min_length=1)
    achievementIndex: Optional[int] = None
    context: Optional[str] = None
    action: Optional[str] = None
    measurement: Optional[str] = None
    technologies: Optional[List[str]] = None
    before: Optional[str] = None
    after: Optional[str] = None
    teamSize: Optional[str] = None
    highlights: Optional[List[str]] = None
    # Empleo oculto (p. ej. Corus): cargo, actividades y si ya puede salir en CVs.
    roles: Optional[List[str]] = None
    responsibilities: Optional[List[str]] = None
    showInCv: Optional[bool] = None


def _metric_label(metric: Any) -> str:
    if not isinstance(metric, dict) or metric.get("value") is None:
        return ""
    value = metric["value"]
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    unit = str(metric.get("unit") or "")
    return f"{value}%" if unit.lower() in {"percent", "%"} else f"{value} {unit}".strip()


def evidence_gaps(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """Lo que falta para que el CV pueda argumentar cada cifra y cada cargo.

    - Cada logro con cifra necesita ``action`` (cómo se logró) y ``measurement`` (cómo se midió).
    - Cada empleo visible necesita ``roleScope`` (tamaño del equipo y lo que demuestra el cargo).
    - Un empleo oculto sin cargo (p. ej. Corus) se lista para poder activarlo después.
    """
    gaps: list[dict[str, Any]] = []
    for ex in raw.get("experience") or []:
        if not isinstance(ex, dict):
            continue
        base = {"experienceId": ex.get("id"), "company": ex.get("company") or ""}
        if ex.get("showInCv") is False:
            if not ex.get("roles") or not ex.get("responsibilities"):
                gaps.append({**base, "kind": "hidden", "missing": ["roles", "responsibilities"],
                             "question": f"{base['company']} no sale en tus CVs: falta tu cargo y qué hiciste ahí."})
            continue
        for index, ach in enumerate(ex.get("achievements") or []):
            if not isinstance(ach, dict) or ach.get("safeForCV") is False:
                continue
            label = _metric_label(ach.get("metric"))
            if not label:
                continue
            detail = ach.get("evidenceDetail") or {}
            missing = [key for key in ("action", "measurement") if not str(detail.get(key) or "").strip()]
            if missing:
                gaps.append({
                    **base,
                    "kind": "achievement",
                    "achievementIndex": index,
                    "description": ach.get("description") or "",
                    "metric": label,
                    "missing": missing,
                    "current": detail,
                    "question": f"{base['company']} · {ach.get('description')} ({label}): ¿qué hiciste exactamente y cómo se midió?",
                })
        scope = ex.get("roleScope") or {}
        missing_scope = [key for key in ("teamSize", "highlights") if not scope.get(key)]
        if missing_scope:
            gaps.append({
                **base,
                "kind": "scope",
                "missing": missing_scope,
                "current": scope,
                "question": f"{base['company']}: ¿de qué tamaño era el equipo y qué demuestra tu cargo (responsabilidad, liderazgo, decisiones)?",
            })
    return gaps


def _parse_point(text: Optional[str]) -> Optional[dict[str, Any]]:
    if text is None or not text.strip():
        return None
    m = _POINT_RE.match(text)
    if not m:
        raise HTTPException(status_code=400, detail=f"Valor no válido: «{text}». Usa por ejemplo «8 s» o «500 ms».")
    value = float(m.group(1).replace(",", "."))
    unit = (m.group(2) or "").lower()
    unit = _POINT_UNITS.get(unit, unit)
    return {"value": int(value) if value.is_integer() else value, "unit": unit}


def apply_evidence(raw: dict[str, Any], body: EvidenceIn) -> dict[str, Any]:
    """Guarda la evidencia de un logro (``achievementIndex``) o el alcance del cargo (sin índice)."""
    ex = _find_exp(raw, body.experienceId)
    source = f"Declarado por el usuario el {date.today().isoformat()}"
    if body.achievementIndex is not None:
        achievements = ex.get("achievements") or []
        if not 0 <= body.achievementIndex < len(achievements):
            raise HTTPException(status_code=400, detail="Logro no encontrado")
        ach = achievements[body.achievementIndex]
        detail = dict(ach.get("evidenceDetail") or {})
        for key in ("context", "action", "measurement"):
            value = getattr(body, key)
            if value is not None and value.strip():
                detail[key] = " ".join(value.split())
        if body.technologies is not None:
            techs = _clean_str_list(body.technologies)
            if techs:
                detail["technologies"] = techs
        for key in ("before", "after"):
            point = _parse_point(getattr(body, key))
            if point:
                detail[key] = point
        detail["source"] = source
        ach["evidenceDetail"] = detail
    elif body.roles is not None or body.responsibilities is not None or body.showInCv is not None:
        if body.roles is not None:
            roles = _clean_str_list(body.roles)
            if roles:
                ex["roles"] = roles
        if body.responsibilities is not None:
            items = _clean_str_list(body.responsibilities)
            if items:
                ex["responsibilities"] = items
        if body.technologies is not None:
            techs = _clean_str_list(body.technologies)
            if techs:
                ex["technologies"] = techs
        if body.showInCv is True:
            if not ex.get("roles") or not ex.get("responsibilities"):
                raise HTTPException(
                    status_code=400,
                    detail=f"{ex.get('company')} necesita cargo y al menos una actividad para salir en CVs.",
                )
            ex.pop("showInCv", None)
            ex.pop("showInCvNote", None)
        elif body.showInCv is False:
            ex["showInCv"] = False
        ex.setdefault("evidence", []).append(f"{source}: cargo/actividades actualizados desde Evidencia.")
    else:
        scope = dict(ex.get("roleScope") or {})
        if body.teamSize is not None and body.teamSize.strip():
            size = body.teamSize.strip()
            scope["teamSize"] = int(size) if size.isdigit() else size
        if body.highlights is not None:
            highlights = _clean_str_list(body.highlights)
            if highlights:
                scope["highlights"] = highlights
        scope["source"] = source
        ex["roleScope"] = scope
    uv = raw.setdefault("userValidation", {"pending": [], "resolved": [], "lastUpdated": None})
    uv["lastUpdated"] = date.today().isoformat()
    return raw
