from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict

from .models import MatchResponse, TailorResponse

_MAX_JOBS = 100
_LOCK = RLock()
_CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache"
_CACHE_FILE = _CACHE_DIR / "extension_jobs.json"


class ExtensionJobRecord(BaseModel):
    """Entrada persistida en caché (memoria + JSON). Ignora claves viejas (p. ej. vacancy_url)."""

    model_config = ConfigDict(extra="ignore")

    id: str
    vacancy_title: str
    source_site: str
    created_at: str
    match: MatchResponse
    tailor: TailorResponse


class ExtensionJobSummary(BaseModel):
    id: str
    vacancy_title: str
    source_site: str
    created_at: str
    chosen_cv_id: str
    match_score: float
    tailor_match_percent: float


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_dir() -> None:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _load_raw() -> list[dict[str, Any]]:
    if not _CACHE_FILE.exists():
        return []
    try:
        data = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
        jobs = data.get("jobs")
        if isinstance(jobs, list):
            return jobs
    except (json.JSONDecodeError, OSError):
        pass
    return []


def _save_raw(jobs: list[dict[str, Any]]) -> None:
    _ensure_dir()
    _CACHE_FILE.write_text(
        json.dumps({"jobs": jobs}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _memory_list() -> list[ExtensionJobRecord]:
    raw = _load_raw()
    out: list[ExtensionJobRecord] = []
    for item in raw:
        try:
            out.append(ExtensionJobRecord.model_validate(item))
        except Exception:
            continue
    return out


def list_jobs_summaries_newest_first() -> list[ExtensionJobSummary]:
    with _LOCK:
        records = _memory_list()
    records.sort(key=lambda r: r.created_at, reverse=True)
    return [
        ExtensionJobSummary(
            id=r.id,
            vacancy_title=r.vacancy_title,
            source_site=r.source_site,
            created_at=r.created_at,
            chosen_cv_id=r.match.chosen_cv_id,
            match_score=r.match.match_score,
            tailor_match_percent=r.tailor.match_percent,
        )
        for r in records
    ]


def get_job(job_id: str) -> Optional[ExtensionJobRecord]:
    jid = job_id.strip()
    if not jid:
        return None
    with _LOCK:
        for r in _memory_list():
            if r.id == jid:
                return r
    return None


def append_job(
    vacancy_title: str,
    source_site: str,
    match: MatchResponse,
    tailor: TailorResponse,
) -> ExtensionJobRecord:
    record = ExtensionJobRecord(
        id=str(uuid.uuid4()),
        vacancy_title=vacancy_title.strip() or "Vacante sin título",
        source_site=(source_site.strip() or "desconocido").lower(),
        created_at=_utc_now_iso(),
        match=match,
        tailor=tailor,
    )
    with _LOCK:
        raw_list = _load_raw()
        new_item = record.model_dump(mode="json")
        merged = [new_item] + raw_list
        merged = merged[:_MAX_JOBS]
        _save_raw(merged)
    return record
