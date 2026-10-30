"""Regenerar CVs del historial (uno o por lotes) con la vacante guardada y el pipeline actual."""

from __future__ import annotations

import asyncio

import pytest

import app.cv_history as history
import app.cv_queue as queue
import app.vacancy_pipeline as vp
from app.compact_master import load_compact_profile
from app.llm.result_pack import pack_optimizer
from app.models import CvDocument, ExperienceItem, TailorResponse

from fakes import EN_VACANCY, ES_VACANCY, optimizer_en, optimizer_es


class FakeBatchBackend:
    """Backend que cuenta peticiones: una por lote, como Gemini/OpenAI."""

    provider_id = "fake"
    model_id = "fake-1"

    def __init__(self) -> None:
        self.batches: list[int] = []

    def is_configured(self) -> bool:
        return True

    async def tailor_cv_batch(self, items):
        self.batches.append(len(items))
        master = load_compact_profile()
        out = []
        for vacancy, cv in items:
            locale = "es" if vacancy.startswith("Desarrollador") else "en"
            data = optimizer_es() if locale == "es" else optimizer_en()
            out.append(pack_optimizer(data, cv, master, locale, vacancy, provider="fake", model="fake-1"))
        return out


@pytest.fixture()
def tmp_stores(tmp_path, monkeypatch):
    monkeypatch.setattr(history, "_CACHE_DIR", tmp_path)
    monkeypatch.setattr(history, "_CACHE_FILE", tmp_path / "generated_cvs.json")
    monkeypatch.setattr(queue, "_CACHE_DIR", tmp_path)
    monkeypatch.setattr(queue, "_CACHE_FILE", tmp_path / "optimize_queue.json")
    signals: list[str] = []
    monkeypatch.setattr(queue, "_signal", signals.append)
    monkeypatch.setattr(queue, "_busy", False)
    monkeypatch.setattr(queue, "_quota_until", 0.0)
    backend = FakeBatchBackend()
    monkeypatch.setattr(vp, "get_cv_llm_backend", lambda: backend)
    return backend, signals


def _old_cv(name: str, vacancy: str) -> history.GeneratedCvRecord:
    """CV «viejo»: fechas de UffPay anteriores a la corrección del perfil."""
    cv = CvDocument(
        id="cv_1",
        name="Jairo Antonio Camarillo Tinoco",
        email="x@y.z",
        location="Mexico",
        title="Old title",
        experience=[ExperienceItem(company="UffPay", role="Frontend", period="Ene 2023 – Jul 2024", bullets=["viejo"])],
    )
    tailor = TailorResponse(cv=cv, match_percent=50)
    return history.append_generated_cv(
        vacancy_title=vacancy.split("\n")[0],
        vacancy_text=vacancy,
        tailor=tailor,
        cv_name=name,
        company_name="Acme",
        vacancy_url="https://example.com/job",
    )


def _run_worker_until_idle(max_batches: int = 10) -> None:
    for _ in range(max_batches):
        if queue.queued_count() == 0:
            return
        asyncio.run(queue._process_batch(force=True))


def test_regenerate_one_cv_creates_new_entry_and_keeps_original(tmp_stores):
    backend, signals = tmp_stores
    original = _old_cv("CV Acme", EN_VACANCY)

    out = queue.enqueue_regeneration([original.id])
    assert len(out.job_ids) == 1 and out.skipped == []
    assert signals == [queue.CMD_FLUSH]  # sale aunque no haya 5
    job = queue.get_queue_job(out.job_ids[0])
    assert job.regenerated_from == original.id
    assert job.vacancy_text == EN_VACANCY
    assert job.company_name == "Acme" and job.vacancy_url == "https://example.com/job"

    _run_worker_until_idle()
    assert backend.batches == [1]

    new = history.get_generated_cv(out.job_ids[0])
    assert new is not None
    assert new.regenerated_from == original.id
    assert new.cv_name == "CV Acme (regenerado)"
    # Pipeline actual: fechas en conflicto omitidas, sin ubicación, con notas de verificación.
    uff = next(j for j in new.cv.experience if j.company == "UffPay")
    assert uff.period == "Apr 2026 – Present · Jan 2024 – Jul 2024"
    assert new.cv.location == ""
    assert new.notes_to_verify  # p. ej. el bullet de Safra Bank descartado

    # El original sigue igual.
    old = history.get_generated_cv(original.id)
    assert old.cv.experience[0].period == "Ene 2023 – Jul 2024"
    assert old.cv_name == "CV Acme"
    assert old.regenerated_from is None


def test_regenerate_in_batches_of_five(tmp_stores):
    backend, signals = tmp_stores
    originals = [_old_cv(f"CV {i}", EN_VACANCY if i % 2 else ES_VACANCY) for i in range(7)]

    out = queue.enqueue_regeneration([r.id for r in originals])
    assert len(out.job_ids) == 7
    assert out.started == queue.BATCH_SIZE

    asyncio.run(queue._process_batch(force=True))
    assert backend.batches == [5]
    assert queue._regen_queued() == 2
    # El resto no espera a juntar 5: el worker pide otro flush.
    assert signals[-1] == queue.CMD_FLUSH

    _run_worker_until_idle()
    assert backend.batches == [5, 2]
    regenerated = [history.get_generated_cv(j) for j in out.job_ids]
    assert all(r is not None and r.regenerated_from for r in regenerated)
    locales = {r.cv.locale for r in regenerated}
    assert locales == {"en", "es"}


def test_regenerate_skips_missing_and_dedupes_pending(tmp_stores):
    original = _old_cv("CV Acme", EN_VACANCY)
    first = queue.enqueue_regeneration([original.id, original.id, "no-existe"])
    assert len(first.job_ids) == 1
    assert [s.id for s in first.skipped] == ["no-existe"]
    again = queue.enqueue_regeneration([original.id])
    assert again.job_ids == first.job_ids  # ya estaba en cola: no duplica


def test_regenerate_validates_input(tmp_stores):
    with pytest.raises(ValueError):
        queue.enqueue_regeneration([])
    with pytest.raises(ValueError):
        queue.enqueue_regeneration([f"id-{i}" for i in range(queue.REGENERATE_MAX + 1)])


def test_regenerate_waits_when_quota_blocked(tmp_stores, monkeypatch):
    _backend, signals = tmp_stores
    original = _old_cv("CV Acme", EN_VACANCY)
    monkeypatch.setattr(queue, "_quota_until", queue.time.time() + 60)
    out = queue.enqueue_regeneration([original.id])
    assert out.started == 0 and "tope" in out.message
    assert signals == []
    assert queue.get_queue_job(out.job_ids[0]).status == queue.STATUS_QUEUED


def test_regenerate_endpoint_and_history_listing(tmp_stores):
    from fastapi.testclient import TestClient

    from app.main import app

    original = _old_cv("CV Acme", EN_VACANCY)
    client = TestClient(app)
    res = client.post("/v1/history/regenerate", json={"ids": [original.id]})
    assert res.status_code == 200, res.text
    job_id = res.json()["job_ids"][0]

    listed = {i["id"]: i for i in client.get("/v1/history").json()["items"]}
    assert listed[job_id]["status"] == "queued"
    assert listed[job_id]["regenerated_from"] == original.id

    _run_worker_until_idle()
    detail = client.get(f"/v1/history/{job_id}").json()
    assert detail["status"] == "ready"
    assert detail["regenerated_from"] == original.id
    assert detail["notes_to_verify"]

    assert client.post("/v1/history/regenerate", json={"ids": []}).status_code in (400, 422)
