"""Cola local de CVs: lote semi-asistido (auto a 5, o flush 1–4 desde UI)."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict

from .cv_history import vacancy_title_from_text
from .llm import GEMINI_QUOTA_USER_MESSAGE, is_quota_or_rate_limit
from .vacancy_clean import parse_pasted_vacancy

logger = logging.getLogger(__name__)

STATUS_QUEUED = "queued"
STATUS_GENERATING = "generating"
STATUS_READY = "ready"
STATUS_ERROR = "error"
PENDING_STATUSES = {STATUS_QUEUED, STATUS_GENERATING}

BATCH_SIZE = 5
CMD_CHECK = "check"
CMD_FLUSH = "flush"

_MAX_JOBS = 60
_CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache"
_CACHE_FILE = _CACHE_DIR / "optimize_queue.json"
_LOCK = RLock()

_loop_queue: Optional[asyncio.Queue[str]] = None
_worker_task: Optional[asyncio.Task[None]] = None
_waiters: dict[str, list[asyncio.Future[QueueJobRecord]]] = {}
_stop = asyncio.Event()
_busy = False


class QueueJobRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    status: str = STATUS_QUEUED
    vacancy_title: str = ""
    vacancy_text: str = ""
    company_name: str = ""
    vacancy_url: Optional[str] = None
    fingerprint: str = ""
    created_at: str
    updated_at: str
    error: str = ""
    saved_id: Optional[str] = None
    match_percent: float = 0
    cv_name: str = ""


class QueueEnqueueOut(BaseModel):
    id: str
    status: str
    vacancy_title: str
    position: int
    pending: int
    message: str
    batch_size: int = BATCH_SIZE
    queued: int = 0
    generating: int = 0


class QueueStatusOut(BaseModel):
    batch_size: int = BATCH_SIZE
    queued: int = 0
    generating: int = 0
    can_flush: bool = False
    message: str = ""


class QueueFlushOut(BaseModel):
    started: int = 0
    queued: int = 0
    generating: int = 0
    batch_size: int = BATCH_SIZE
    message: str = ""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fingerprint(text: str, url: Optional[str]) -> str:
    if url:
        return f"url:{url.strip().lower()}"
    digest = hashlib.sha256((text or "").strip().encode("utf-8")).hexdigest()[:20]
    return f"txt:{digest}"


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


def _records() -> list[QueueJobRecord]:
    out: list[QueueJobRecord] = []
    for item in _load_raw():
        try:
            out.append(QueueJobRecord.model_validate(item))
        except Exception:
            continue
    return out


def _write_records(records: list[QueueJobRecord]) -> None:
    compact = [
        r
        for r in records
        if r.status in {STATUS_QUEUED, STATUS_GENERATING, STATUS_ERROR}
    ]
    _save_raw([r.model_dump(mode="json") for r in compact[:_MAX_JOBS]])


def get_queue_job(job_id: str) -> Optional[QueueJobRecord]:
    jid = (job_id or "").strip()
    if not jid:
        return None
    with _LOCK:
        for r in _records():
            if r.id == jid:
                return r
    return None


def list_pending_jobs() -> list[QueueJobRecord]:
    with _LOCK:
        records = [r for r in _records() if r.status in PENDING_STATUSES | {STATUS_ERROR}]
    records.sort(key=lambda r: r.created_at)
    return records


def queue_position(job_id: str) -> int:
    pending = [r for r in list_pending_jobs() if r.status in PENDING_STATUSES]
    for i, r in enumerate(pending, start=1):
        if r.id == job_id:
            return i
    return 0


def pending_count() -> int:
    return sum(1 for r in list_pending_jobs() if r.status in PENDING_STATUSES)


def queued_count() -> int:
    with _LOCK:
        return sum(1 for r in _records() if r.status == STATUS_QUEUED)


def generating_count() -> int:
    with _LOCK:
        return sum(1 for r in _records() if r.status == STATUS_GENERATING)


def _counts() -> tuple[int, int]:
    with _LOCK:
        records = _records()
        queued = sum(1 for r in records if r.status == STATUS_QUEUED)
        generating = sum(1 for r in records if r.status == STATUS_GENERATING)
    return queued, generating


def _batch_message(queued: int, generating: int) -> str:
    if generating > 0:
        return f"Generando lote de {generating} CVs…"
    if queued <= 0:
        return "Lote vacío"
    if queued >= BATCH_SIZE:
        return f"Lote {BATCH_SIZE}/{BATCH_SIZE} — se envían ahora"
    return (
        f"Lote {queued}/{BATCH_SIZE} — al llegar a {BATCH_SIZE} se generan solos, "
        "o pulsa Generar lote"
    )


def queue_status() -> QueueStatusOut:
    queued, generating = _counts()
    return QueueStatusOut(
        batch_size=BATCH_SIZE,
        queued=queued,
        generating=generating,
        can_flush=queued > 0 and generating == 0 and not _busy,
        message=_batch_message(queued, generating),
    )


def _signal(cmd: str) -> None:
    if _loop_queue is None:
        return
    try:
        _loop_queue.put_nowait(cmd)
    except asyncio.QueueFull:
        pass


def _upsert(record: QueueJobRecord) -> QueueJobRecord:
    with _LOCK:
        records = _records()
        replaced = False
        for i, r in enumerate(records):
            if r.id == record.id:
                records[i] = record
                replaced = True
                break
        if not replaced:
            records.append(record)
        _write_records(records)
    return record


def _find_duplicate(fingerprint: str) -> Optional[QueueJobRecord]:
    with _LOCK:
        for r in _records():
            if r.fingerprint == fingerprint and r.status in PENDING_STATUSES:
                return r
    return None


def _notify(record: QueueJobRecord) -> None:
    waiters = _waiters.pop(record.id, [])
    for fut in waiters:
        if not fut.done():
            fut.set_result(record)


def _out_for(job: QueueJobRecord) -> QueueEnqueueOut:
    queued, generating = _counts()
    pending = queued + generating
    pos = queue_position(job.id) or 1
    return QueueEnqueueOut(
        id=job.id,
        status=job.status,
        vacancy_title=job.vacancy_title,
        position=pos,
        pending=pending,
        message=_batch_message(queued, generating),
        batch_size=BATCH_SIZE,
        queued=queued,
        generating=generating,
    )


def retry_queue_job(job_id: str) -> QueueEnqueueOut:
    job = get_queue_job(job_id)
    if job is None:
        raise LookupError("No hay un trabajo en cola con ese id.")
    if job.status in PENDING_STATUSES:
        return _out_for(job)
    if job.status != STATUS_ERROR:
        raise ValueError("Solo se pueden reintentar CVs que fallaron.")
    if not (job.vacancy_text or "").strip():
        raise ValueError("Este trabajo no tiene el texto de la vacante para reintentar.")
    if pending_count() >= _MAX_JOBS:
        raise RuntimeError("La cola está llena. Espera a que terminen unos CVs.")

    job.status = STATUS_QUEUED
    job.error = ""
    job.updated_at = _utc_now_iso()
    _upsert(job)
    if queued_count() >= BATCH_SIZE:
        _signal(CMD_CHECK)
    return _out_for(job)


def enqueue_optimize(
    vacancy_text: str,
    vacancy_url: Optional[str] = None,
    company_name: Optional[str] = None,
) -> QueueEnqueueOut:
    parsed = parse_pasted_vacancy(vacancy_text or "")
    blob = (parsed["text"] or "").strip()
    if not blob:
        raise ValueError("Pega el texto de la vacante.")
    stored_url = (vacancy_url or parsed["url"] or "").strip() or None
    company = (company_name or parsed["company"] or "").strip()
    title = vacancy_title_from_text(blob)
    fp = _fingerprint(blob, stored_url)

    existing = _find_duplicate(fp)
    if existing:
        return _out_for(existing)

    if pending_count() >= _MAX_JOBS:
        raise RuntimeError("La cola está llena. Espera a que terminen unos CVs.")

    now = _utc_now_iso()
    record = QueueJobRecord(
        id=str(uuid.uuid4()),
        status=STATUS_QUEUED,
        vacancy_title=title,
        vacancy_text=blob[:80_000],
        company_name=company[:200],
        vacancy_url=stored_url[:2000] if stored_url else None,
        fingerprint=fp,
        created_at=now,
        updated_at=now,
    )
    _upsert(record)
    if queued_count() >= BATCH_SIZE:
        _signal(CMD_CHECK)
    return _out_for(record)


def flush_batch() -> QueueFlushOut:
    queued, generating = _counts()
    if generating > 0 or _busy:
        return QueueFlushOut(
            started=0,
            queued=queued,
            generating=generating or BATCH_SIZE,
            message=_batch_message(queued, generating or 1),
        )
    if queued < 1:
        raise ValueError("No hay vacantes en el lote. Añade al menos una.")
    _signal(CMD_FLUSH)
    started = min(queued, BATCH_SIZE)
    return QueueFlushOut(
        started=started,
        queued=queued,
        generating=0,
        message=f"Generando {started} CV{'s' if started != 1 else ''} en una petición…",
    )


def _ready_from_history(job_id: str) -> Optional[QueueJobRecord]:
    from .cv_history import get_generated_cv

    record = get_generated_cv(job_id)
    if not record:
        return None
    return QueueJobRecord(
        id=record.id,
        status=STATUS_READY,
        vacancy_title=record.vacancy_title,
        vacancy_text=record.vacancy_text,
        company_name=record.company_name,
        vacancy_url=record.vacancy_url,
        created_at=record.created_at,
        updated_at=record.created_at,
        saved_id=record.id,
        match_percent=record.match_percent,
        cv_name=record.cv_name,
    )


async def wait_for_job(job_id: str, timeout: float = 900) -> QueueJobRecord:
    ready = _ready_from_history(job_id)
    if ready:
        return ready
    current = get_queue_job(job_id)
    if current and current.status in {STATUS_READY, STATUS_ERROR}:
        return current

    loop = asyncio.get_running_loop()
    fut: asyncio.Future[QueueJobRecord] = loop.create_future()
    _waiters.setdefault(job_id, []).append(fut)
    ready = _ready_from_history(job_id)
    if ready and not fut.done():
        fut.set_result(ready)
    current = get_queue_job(job_id)
    if current and current.status in {STATUS_READY, STATUS_ERROR} and not fut.done():
        fut.set_result(current)
    return await asyncio.wait_for(fut, timeout=timeout)


def _claim_batch(force: bool) -> list[QueueJobRecord]:
    with _LOCK:
        records = _records()
        queued = sorted(
            [r for r in records if r.status == STATUS_QUEUED],
            key=lambda r: r.created_at,
        )
        if not queued:
            return []
        if not force and len(queued) < BATCH_SIZE:
            return []
        take = queued[:BATCH_SIZE]
        now = _utc_now_iso()
        claimed_ids = [r.id for r in take]
        claimed_set = set(claimed_ids)
        for r in records:
            if r.id in claimed_set:
                r.status = STATUS_GENERATING
                r.error = ""
                r.updated_at = now
        _write_records(records)
        by_id = {r.id: r for r in records}
        return [by_id[i] for i in claimed_ids if i in by_id]


def _fail_jobs(jobs: list[QueueJobRecord], message: str) -> None:
    now = _utc_now_iso()
    for job in jobs:
        job.status = STATUS_ERROR
        job.error = message[:800]
        job.updated_at = now
        _upsert(job)
        _notify(job)


def _finish_job(job: QueueJobRecord, tailored) -> None:
    job.status = STATUS_READY
    job.saved_id = tailored.saved_id or job.id
    job.match_percent = tailored.match_percent
    job.cv_name = tailored.cv_name or ""
    job.updated_at = _utc_now_iso()
    job.error = ""
    _upsert(job)
    _notify(job)


async def _process_batch(force: bool) -> None:
    global _busy
    if _busy:
        return
    jobs = _claim_batch(force)
    if not jobs:
        return
    _busy = True
    titles = ", ".join(j.vacancy_title[:40] for j in jobs)
    logger.info("[queue] lote de %s · %s", len(jobs), titles)
    try:
        from .vacancy_pipeline import run_full_optimize_batch

        payloads = [
            (job.id, job.vacancy_text, job.vacancy_url, job.company_name or "")
            for job in jobs
        ]
        results = await run_full_optimize_batch(payloads)
        by_id = {item_id: tailored for item_id, tailored in results}
        for job in jobs:
            tailored = by_id.get(job.id)
            if tailored is None:
                _fail_jobs([job], "El lote no trajo este CV. Reinténtalo.")
                continue
            _finish_job(job, tailored)
            logger.info("[queue] listo %s", job.id[:8])
    except Exception as exc:
        message = GEMINI_QUOTA_USER_MESSAGE if is_quota_or_rate_limit(exc) else str(exc)
        logger.warning("[queue] lote error: %s", message[:200])
        _fail_jobs(jobs, message)
    finally:
        _busy = False
        if queued_count() >= BATCH_SIZE:
            _signal(CMD_CHECK)


async def _worker_loop() -> None:
    assert _loop_queue is not None
    while not _stop.is_set():
        got = False
        try:
            cmd = await asyncio.wait_for(_loop_queue.get(), timeout=0.6)
            got = True
        except asyncio.TimeoutError:
            if queued_count() >= BATCH_SIZE and not _busy:
                cmd = CMD_CHECK
            else:
                continue
        try:
            await _process_batch(force=(cmd == CMD_FLUSH))
        except Exception:
            logger.exception("[queue] worker falló")
        finally:
            if got:
                _loop_queue.task_done()


async def start_queue_worker() -> None:
    global _loop_queue, _worker_task, _busy
    _stop.clear()
    _busy = False
    _loop_queue = asyncio.Queue()
    with _LOCK:
        records = _records()
        for r in records:
            if r.status == STATUS_GENERATING:
                r.status = STATUS_QUEUED
                r.updated_at = _utc_now_iso()
        _write_records(records)
        queued = [r for r in records if r.status == STATUS_QUEUED]
    if len(queued) >= BATCH_SIZE:
        _loop_queue.put_nowait(CMD_CHECK)
    _worker_task = asyncio.create_task(_worker_loop(), name="cv-optimize-queue")
    logger.info("[queue] worker listo · %s en lote / auto a %s", len(queued), BATCH_SIZE)


async def stop_queue_worker() -> None:
    global _worker_task, _loop_queue
    _stop.set()
    if _worker_task:
        _worker_task.cancel()
        try:
            await _worker_task
        except asyncio.CancelledError:
            pass
    _worker_task = None
    _loop_queue = None
