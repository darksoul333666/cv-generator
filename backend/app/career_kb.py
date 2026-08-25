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
        ex = _find_exp(raw, "exp_uffpay")
        ex["startDate"] = resolved_value
        ex["userValidated"] = True
        if ex.get("endDate"):
            ex["dateStatus"] = "verified"
        _sync_timeline(raw, "exp_uffpay")
    elif field == "experience.MonkeyCave.dates":
        start, end = _parse_range(resolved_value)
        ex = _find_exp(raw, "exp_monkey_cave")
        if start:
            ex["startDate"] = start
        if end:
            ex["endDate"] = end
        ex["userValidated"] = True
        if ex.get("startDate") and ex.get("endDate"):
            ex["dateStatus"] = "verified"
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

        ex["startDate"] = start
        ex["endDate"] = end
        ex["current"] = bool(item.current)
        ex["employmentType"] = emp
        ex["sortOrder"] = index
        ex["userValidated"] = True
        if start and (end or item.current):
            ex["dateStatus"] = "verified"
            ex["evidenceLevel"] = "verified"
        elif start or end:
            ex["dateStatus"] = "requires_validation"

        ordered.append(ex)

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
