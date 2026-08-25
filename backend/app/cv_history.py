"""Registro local de CVs generados + vacante asociada. No entra al modelo."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict

from .models import CvDocument, TailorResponse

_MAX_ITEMS = 100
_LOCK = RLock()
_CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache"
_CACHE_FILE = _CACHE_DIR / "generated_cvs.json"


class GeneratedCvRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    vacancy_title: str
    vacancy_text: str
    created_at: str
    match_percent: float = 0
    reason: str = ""
    cv: CvDocument


class GeneratedCvSummary(BaseModel):
    id: str
    vacancy_title: str
    created_at: str
    match_percent: float
    target_role: str = ""


def vacancy_title_from_text(text: str, explicit: Optional[str] = None) -> str:
    if explicit and explicit.strip():
        return explicit.strip()[:200]
    first = (text or "").strip().split("\n")[0].strip()
    if len(first) > 160:
        first = first[:157] + "…"
    return first or "Vacante sin título"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_dir() -> None:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _load_raw() -> list[dict[str, Any]]:
    if not _CACHE_FILE.exists():
        return []
    try:
        data = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
        items = data.get("items")
        if isinstance(items, list):
            return items
    except (json.JSONDecodeError, OSError):
        pass
    return []


def _save_raw(items: list[dict[str, Any]]) -> None:
    _ensure_dir()
    _CACHE_FILE.write_text(
        json.dumps({"items": items}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _memory_list() -> list[GeneratedCvRecord]:
    out: list[GeneratedCvRecord] = []
    for item in _load_raw():
        try:
            out.append(GeneratedCvRecord.model_validate(item))
        except Exception:
            continue
    return out


def list_generated_summaries() -> list[GeneratedCvSummary]:
    with _LOCK:
        records = _memory_list()
    records.sort(key=lambda r: r.created_at, reverse=True)
    return [
        GeneratedCvSummary(
            id=r.id,
            vacancy_title=r.vacancy_title,
            created_at=r.created_at,
            match_percent=r.match_percent,
            target_role=r.cv.title or "",
        )
        for r in records
    ]


def get_generated_cv(item_id: str) -> Optional[GeneratedCvRecord]:
    jid = item_id.strip()
    if not jid:
        return None
    with _LOCK:
        for r in _memory_list():
            if r.id == jid:
                return r
    return None


def append_generated_cv(
    vacancy_title: str,
    vacancy_text: str,
    tailor: TailorResponse,
) -> GeneratedCvRecord:
    record = GeneratedCvRecord(
        id=str(uuid.uuid4()),
        vacancy_title=vacancy_title.strip() or "Vacante sin título",
        vacancy_text=(vacancy_text or "")[:80000],
        created_at=_utc_now_iso(),
        match_percent=tailor.match_percent,
        reason=tailor.reason or "",
        cv=tailor.cv,
    )
    with _LOCK:
        raw_list = _load_raw()
        merged = [record.model_dump(mode="json")] + raw_list
        _save_raw(merged[:_MAX_ITEMS])
    return record
