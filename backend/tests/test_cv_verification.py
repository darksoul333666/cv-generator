"""Regresiones: idioma, fechas en conflicto, hechos de proyectos, ubicación y perfiles borrados.

Los E2E corren el pipeline real (vacancy_pipeline → OpenAICvLlmBackend → pack_optimizer →
_build_cv) contra knowledge_base/master_profile.json. Solo se sustituye la llamada HTTP al
modelo (``_chat_sync``) por respuestas fijas y el historial en disco por un stub.
"""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

import pytest

import app.vacancy_pipeline as vp
from app.llm.openai_backend import OpenAICvLlmBackend
from app import matcher
from app.career_kb import (
    ExperienceEditItem,
    apply_experience_edits,
    apply_user_validation,
    date_conflict_open,
)
from app.compact_master import (
    build_compact_profile,
    kb_dir,
    load_compact_profile,
    omitted_contact_fields,
    profile_for_prompt,
    protected_terms,
)
from app.language_guard import (
    LanguageItem,
    detect_language,
    repair_language,
    translation_problem,
)
from app.llm.cv_builder import (
    _build_cv,
    _bullets_for_job,
    _focus_line,
    _real_bullets,
)
from app.models import CvDocument

from fakes import (
    EN_VACANCY,
    ES_VACANCY,
    TRANSLATIONS,
    FakeLLM,
    fake_history_record,
    optimizer_en,
    optimizer_es,
    prompt_profile,
)

ROOT = Path(__file__).resolve().parent.parent


def _raw_master() -> dict:
    return json.loads((kb_dir() / "master_profile.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def compact() -> dict:
    return load_compact_profile()


@pytest.fixture(scope="module")
def protected(compact) -> list[str]:
    return protected_terms(compact)


def _run_pipeline(monkeypatch, vacancy: str, fake: FakeLLM):
    backend = OpenAICvLlmBackend("test-key", "gpt-test", "https://api.invalid/v1")
    monkeypatch.setattr(backend, "_chat_json", fake)
    monkeypatch.setattr(vp, "get_cv_llm_backend", lambda: backend)
    monkeypatch.setattr(vp, "append_generated_cv", lambda **kw: fake_history_record(**kw))
    return asyncio.run(vp.run_full_optimize_pipeline(vacancy))


def _visible_text(cv: CvDocument) -> list[str]:
    out = [cv.title, cv.summary]
    for job in cv.experience:
        out.append(job.role)
        out.extend(job.bullets)
    for value in cv.stack.model_dump().values():
        out.extend(p.strip() for p in value.split(",") if p.strip())
    out.extend(cv.keywords)
    return [t for t in out if t]


# --- 1/2. CV entero en inglés / entero en español ------------------------------------------


def test_all_english_cv_is_not_sent_to_translator(compact):
    calls = []

    def spy(texts, locale):
        calls.append(texts)
        return texts

    data = {
        "target_role": "Senior Frontend Developer",
        "summary": "Senior Frontend Developer with 7+ years building Angular and React products.",
        "experience": [
            {
                "company": "Grainchain Inc",
                "position": "Senior Frontend Developer",
                "bullets": [
                    "Built financial dashboards with Angular and Angular Material.",
                    "Cut loan-table load time from 8 s to 3 s (62%) with virtual scrolling and pagination.",
                    "Managed application state with NgRx and RxJS.",
                ],
            }
        ],
    }
    cv, report = _build_cv(data, CvDocument(id="b", name="x", email=""), compact, "en", EN_VACANCY, spy)
    grain = next(j for j in cv.experience if j.company == "Grainchain Inc")
    assert grain.bullets[:3] == data["experience"][0]["bullets"]
    assert all("Built financial dashboards" not in t for batch in calls for t in batch)
    assert cv.summary == data["summary"]


def test_all_spanish_text_is_detected_as_spanish(protected):
    for text in [
        "Desarrollo de dashboards financieros con Angular y Angular Material.",
        "Manejo de estado con NgRx para aplicaciones escalables.",
        "Integración de Stripe Payments en aplicaciones fintech.",
        "Liderazgo técnico del equipo de desarrollo frontend.",
    ]:
        assert detect_language(text, protected) == "es", text


# --- 3. Bullets mezclados ---------------------------------------------------------------------


def test_mixed_language_bullet_is_detected_and_translated(protected):
    mixed = "Desarrollé the payments app with React Native para iOS y Android."
    assert detect_language(mixed, protected) == "mixed"
    fixed = "Built the payments app with React Native for iOS and Android."
    final, report = repair_language(
        [LanguageItem("b", mixed, "mixed")], "en", lambda texts, loc: [fixed], protected
    )
    assert final["b"] == fixed
    assert report.status == "repaired"


# --- 4. Bullets cortos ambiguos ---------------------------------------------------------------


@pytest.mark.parametrize("text", ["Angular, NgRx, RxJS", "Testing unitario", "Frontend", "UX/UI", "CI/CD"])
def test_short_ambiguous_text_is_kept_and_not_translated(text, protected):
    assert detect_language(text, protected) == "unknown"
    calls = []
    final, report = repair_language(
        [LanguageItem("x", text, detect_language(text, protected))],
        "en",
        lambda texts, loc: calls.append(texts) or texts,
        protected,
    )
    assert final["x"] == text
    assert calls == []
    assert report.unresolved == []


# --- 5. Palabras compartidas y términos técnicos --------------------------------------------


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Built the Angular 18 ordering platform for Doña Tota, syncing menus and orders.", "en"),
        ("Led frontend and backend for Tecnológico de Monterrey using NestJS and AWS Lambda.", "en"),
        ("Integrated Cybersource and Neonet for payment processing.", "en"),
        ("Entrega continua de features reduciendo tiempos de desarrollo.", "es"),
        ("Code reviews, testing y organización de sprints.", "es"),
        ("Dashboard real-time con Angular Material y Signals.", "es"),
        ("Social login with Firebase Cloud Messaging.", "en"),
        ("Senior Frontend Developer", "en"),
        ("Desarrollador Frontend Senior", "es"),
    ],
)
def test_shared_words_and_tech_terms_do_not_flip_language(text, expected, protected):
    assert detect_language(text, protected) == expected


# --- 6. Summary: conserva el significado; nunca un texto genérico ----------------------------


SUMMARY_ES = (
    "Desarrollador Frontend Senior con más de 7 años en Angular, React y TypeScript. En Grainchain Inc "
    "redujo un 35% el tiempo de renderizado de tablas mediante virtualización."
)
SUMMARY_EN = (
    "Senior Frontend Developer with 7+ years in Angular, React and TypeScript. At Grainchain Inc, "
    "cut table rendering time by 35% through virtualization."
)


def test_summary_translation_keeps_meaning_and_rejects_generic_rewrite(protected):
    attempts = []

    def translator(texts, locale):
        attempts.append(texts)
        if len(attempts) == 1:
            # Respuesta genérica: pierde la cifra, Grainchain y TypeScript.
            return ["Software Developer with experience in web, mobile, and API products."]
        return [SUMMARY_EN]

    final, report = repair_language(
        [LanguageItem("summary", SUMMARY_ES, "es")], "en", translator, protected
    )
    assert final["summary"] == SUMMARY_EN
    assert len(attempts) == 2
    assert report.repaired == [{"path": "summary", "from": "es", "attempt": 2}]


def test_summary_is_never_replaced_by_the_old_generic_fallback(compact):
    data = {"target_role": "Senior Frontend Developer", "summary": SUMMARY_ES, "experience": []}
    cv, report = _build_cv(data, CvDocument(id="b", name="x", email=""), compact, "en", EN_VACANCY)
    assert cv.summary == SUMMARY_ES  # sin traductor: se conserva y se reporta
    assert "aligned to this role" not in cv.summary
    assert any(item["path"] == "summary" for item in report["language"]["unresolved"])


# --- 7. Nombres, tecnologías, métricas y fechas no cambian -----------------------------------


@pytest.mark.parametrize(
    "candidate, reason_prefix",
    [
        ("At Grainchain, cut table rendering time through virtualization.", "numbers_missing"),
        ("At Grainchain Inc, cut table rendering time by 40% through virtualization.", "numbers_missing"),
        ("At Granja Cadena, cut table rendering time by 35% with virtualización.", "terms_missing"),
        ("En Grainchain Inc redujo un 35% el renderizado.", "language"),
    ],
)
def test_translation_must_preserve_names_metrics_and_language(candidate, reason_prefix, protected):
    source = "En Grainchain Inc redujo un 35% el tiempo de renderizado de tablas con Angular Material."
    problem = translation_problem(source, candidate, "en", protected)
    assert problem is not None and problem.startswith(reason_prefix), problem


def test_translation_keeps_years_and_dates(protected):
    source = "Migración del core de Angular de 2021 a 2022 (Ene 2021 – Jun 2021)."
    assert translation_problem(source, "Migrated the Angular core from 2021 to 2022.", "en", protected)
    ok = "Migrated the Angular core from 2021 to 2022 (Jan 2021 – Jun 2021)."
    assert translation_problem(source, ok, "en", protected) is None


# --- 8. Traducción fallida: nunca borra contenido --------------------------------------------


def test_failed_translation_keeps_content_and_reports(protected):
    def broken(texts, locale):
        raise RuntimeError("429 quota")

    text = "Reducción de errores en flujos de pago mediante validaciones y UX (25%)."
    final, report = repair_language([LanguageItem("b", text, "es")], "en", broken, protected)
    assert final["b"] == text
    assert report.status == "unresolved"
    assert "429" in (report.translator_error or "")


def test_unsupported_locale_is_reported_not_deleted(protected):
    final, report = repair_language([LanguageItem("s", "Hola mundo con Angular", "es")], "fr", None, protected)
    assert final["s"] == "Hola mundo con Angular"
    assert report.unresolved[0]["reason"] == "unsupported_locale=fr"


# --- E2E: inglés y español con el perfil real -------------------------------------------------


def test_e2e_english_generation(monkeypatch):
    fake = FakeLLM(optimizer_en())
    match, tailored = _run_pipeline(monkeypatch, EN_VACANCY, fake)
    cv = tailored.cv

    # La plantilla base sale del maestro (ya no hay cv_*.json).
    assert match.chosen_cv_id == "master_profile"
    assert cv.locale == "en"
    assert cv.title == "Senior Frontend Developer"

    # Todo lo visible está en inglés (o es neutral: nombres, tecnologías).
    protected = protected_terms(load_compact_profile())
    wrong = [t for t in _visible_text(cv) if detect_language(t, protected) not in {"en", "unknown"}]
    assert wrong == []
    assert tailored.raw_meta["verification"]["language"]["status"] == "repaired"

    jobs = {job.company: job for job in cv.experience}
    # El bullet que el modelo dejó en español se tradujo; no desapareció.
    assert "Reduced errors in payment flows through validations and UX improvements (25%)." in jobs["UffPay"].bullets
    # Nombres propios intactos en la traducción y en los bullets del modelo.
    assert any("Doña Tota" in b for b in jobs["Lumston"].bullets)
    assert any("8 s to 3 s (62%)" in b for b in jobs["Grainchain Inc"].bullets)

    # Fechas del maestro (nunca las del modelo, que escribió «Jan 2023 – Jul 2024»).
    assert jobs["UffPay"].period == "Apr 2026 – Present · Jan 2024 – Jul 2024"
    assert jobs["Monkey Cave"].period == "Jan 2022 – May 2023"
    assert jobs["Grainchain Inc"].period == "Jun 2025 – Apr 2026"
    assert "Corus" not in jobs

    # Hechos sin respaldo descartados y reportados.
    blob = " ".join(b for job in cv.experience for b in job.bullets)
    assert "Safra Bank" not in blob
    assert "50%" not in blob
    assert "Kubernetes" not in blob
    notes = " ".join(tailored.notes_to_verify)
    assert "Safra Bank" in notes and "50%" in notes and "Kubernetes" in notes
    assert "Fechas sin verificar" not in notes

    # Ubicación omitida por regla validada del usuario.
    assert cv.location == ""

    # Lo que vio el modelo: fechas confirmadas, sin Corus ni proyectos incompletos.
    sent = prompt_profile(fake.optimizer_prompts[0])
    sent_jobs = {e["company"]: e for e in sent["experience"]}
    assert sent_jobs["UffPay"]["dates"] == "Apr 2026 – Present · Jan 2024 – Jul 2024"
    assert sent_jobs["Monkey Cave"]["dates"] == "Jan 2022 – May 2023"
    assert "Corus" not in sent_jobs
    # Corus sigue oculta; Safra Bank y Altos Aceros ya tienen stack declarado por el usuario.
    assert {"Safra Bank", "Altos Aceros"} <= {p["name"] for p in sent["projects"]}

    # Ningún hecho del modelo se duplicó al rellenar con el maestro.
    grain = jobs["Grainchain Inc"].bullets
    assert not any("Desarrollo de dashboards" in b for b in grain)


def test_e2e_spanish_generation(monkeypatch):
    fake = FakeLLM(optimizer_es())
    match, tailored = _run_pipeline(monkeypatch, ES_VACANCY, fake)
    cv = tailored.cv
    assert cv.locale == "es"
    assert cv.title == "Desarrollador Frontend Senior"

    protected = protected_terms(load_compact_profile())
    wrong = [t for t in _visible_text(cv) if detect_language(t, protected) not in {"es", "unknown"}]
    assert wrong == []
    assert tailored.raw_meta["verification"]["language"]["unresolved"] == []

    jobs = {job.company: job for job in cv.experience}
    # Titular Frontend → el cargo Frontend validado de Monkey Cave, traducido.
    assert jobs["Monkey Cave"].role == "Desarrollador Frontend Senior / Líder técnico"
    assert (
        "Reducción del tiempo de carga de las tablas de préstamos de 8 s a 3 s (62%) con virtual scroll y paginación."
        in jobs["Grainchain Inc"].bullets
    )
    # Contenido que ya estaba en español no se reescribe.
    assert "Desarrollo de dashboards financieros con Angular y Angular Material." in jobs["Grainchain Inc"].bullets
    sent = {t for batch in fake.translation_batches for t in batch}
    assert "Desarrollo de dashboards financieros con Angular y Angular Material." not in sent
    assert "Integración de Stripe Payments en aplicaciones fintech." not in sent
    assert jobs["Grainchain Inc"].period == "Jun 2025 – Abr 2026"
    assert jobs["UffPay"].period == "Abr 2026 – Actualidad · Ene 2024 – Jul 2024"
    assert jobs["Monkey Cave"].period == "Ene 2022 – May 2023"
    assert cv.location == ""


def test_e2e_failed_translation_keeps_content(monkeypatch):
    def always_fail(items, locale):
        raise RuntimeError("model returned prose instead of JSON")

    fake = FakeLLM(optimizer_en(), translate_hook=always_fail)
    _match, tailored = _run_pipeline(monkeypatch, EN_VACANCY, fake)
    jobs = {job.company: job for job in tailored.cv.experience}
    assert "Reducción de errores en flujos de pago mediante validaciones y UX (25%)." in jobs["UffPay"].bullets
    assert tailored.cv.summary.startswith("Senior Frontend Developer with 7+ years")
    assert any(n.startswith("Idioma: ") for n in tailored.notes_to_verify)
    assert len(fake.translation_batches) == 1  # error del proveedor: no se reintenta, se reporta


def test_e2e_invalid_translation_is_retried_once_then_reported(monkeypatch):
    def drops_numbers(items, locale):
        # Traduce bien pero pierde las cifras: debe rechazarse.
        table = TRANSLATIONS[locale]
        return [re.sub(r"\s*(by\s*)?\(?\d+%\)?", "", table.get(t, t)) for t in items]

    fake = FakeLLM(optimizer_en(), translate_hook=drops_numbers)
    _match, tailored = _run_pipeline(monkeypatch, EN_VACANCY, fake)
    jobs = {job.company: job for job in tailored.cv.experience}
    assert len(fake.translation_batches) == 2
    assert "Reducción de errores en flujos de pago mediante validaciones y UX (25%)." in jobs["UffPay"].bullets
    unresolved = tailored.raw_meta["verification"]["language"]["unresolved"]
    assert any(u["reason"].startswith("numbers_missing") for u in unresolved)


# --- Fechas: resueltas por el usuario (2026-10-27) -------------------------------------------


def test_master_dates_as_confirmed_by_user():
    raw = _raw_master()
    by_id = {e["id"]: e for e in raw["experience"]}
    uff = by_id["exp_uffpay"]
    assert (uff["startDate"], uff["endDate"], uff["current"]) == ("2026-04", None, True)
    assert [(p["startDate"], p["endDate"]) for p in uff["additionalPeriods"]] == [("2024-01", "2024-07")]
    mc = by_id["exp_monkey_cave"]
    assert (mc["startDate"], mc["endDate"]) == ("2022-01", "2023-05")
    grain = by_id["exp_grainchain"]
    assert (grain["startDate"], grain["endDate"]) == ("2025-06", "2026-04")  # 10 meses
    for exp in raw["experience"]:
        assert not date_conflict_open(exp), exp["id"]
        assert exp["dateStatus"] == "verified", exp["id"]
    # Nada del motivo de salida queda en el perfil.
    blob = json.dumps(raw, ensure_ascii=False).lower()
    assert "despid" not in blob and "renunci" not in blob
    pending = " ".join(raw["userValidation"]["pending"])
    assert "Fechas laborales" not in pending


def test_two_stage_uffpay_and_resolved_dates_in_prompt_and_cv(compact):
    jobs = {e["company"]: e for e in compact["experience"]}
    assert jobs["UffPay"]["dates"] == "Apr 2026 – Present · Jan 2024 – Jul 2024"
    assert jobs["Monkey Cave"]["dates"] == "Jan 2022 – May 2023"
    prompt_jobs = {e["company"]: e for e in profile_for_prompt(compact)["experience"]}
    assert prompt_jobs["UffPay"]["dates"] == "Apr 2026 – Present · Jan 2024 – Jul 2024"
    base = CvDocument(id="b", name="x", email="")
    for locale, uff, mc in [
        ("en", "Apr 2026 – Present · Jan 2024 – Jul 2024", "Jan 2022 – May 2023"),
        ("es", "Abr 2026 – Actualidad · Ene 2024 – Jul 2024", "Ene 2022 – May 2023"),
    ]:
        cv, report = _build_cv({"target_role": "Frontend", "summary": "", "experience": []}, base, compact, locale, EN_VACANCY)
        periods = {j.company: j.period for j in cv.experience}
        assert periods["UffPay"] == uff and periods["Monkey Cave"] == mc
        assert report["unverified_dates"] == []
        assert cv.experience[0].company == "UffPay"


def test_corus_is_in_profile_but_not_in_prompt_or_cv(compact):
    raw = _raw_master()
    corus = next(e for e in raw["experience"] if e["company"] == "Corus")
    assert (corus["startDate"], corus["endDate"]) == ("2025-08", "2026-01")
    assert corus["showInCv"] is False
    assert "Corus" not in compact["allowed_companies"]
    assert {"company": "Corus"}.items() <= compact["hidden_experience"][0].items()
    assert "Corus" not in json.dumps(profile_for_prompt(compact))
    # Aunque el modelo la escriba, no sale.
    data = {"target_role": "Frontend", "summary": "", "experience": [
        {"company": "Corus", "position": "Consultant", "bullets": ["Did things."]}]}
    cv, _ = _build_cv(data, CvDocument(id="b", name="x", email=""), compact, "en", EN_VACANCY)
    assert "Corus" not in {j.company for j in cv.experience}


def test_hidden_job_without_role_does_not_block_profile_save():
    from app.career_kb import ProfileContentIn, apply_profile_content

    raw = _raw_master()
    content = ProfileContentIn.model_validate({
        "profile": {"fullName": "Jairo", "professionalTitles": ["Dev"], "summary": "", "email": "",
                    "phone": "", "linkedin": "", "location": ""},
        "experience": [
            {"id": e["id"], "company": e["company"], "roles": e["roles"], "employmentType": e.get("employmentType"),
             "startDate": e["startDate"], "endDate": e["endDate"], "current": e["current"],
             "responsibilities": e["responsibilities"], "technologies": e["technologies"], "achievements": []}
            for e in raw["experience"]
        ],
    })
    apply_profile_content(raw, content)
    corus = next(e for e in raw["experience"] if e["id"] == "exp_corus")
    assert corus["showInCv"] is False


# --- Mecanismo de conflictos (sobre una copia con un conflicto abierto) ------------------------


def _raw_with_open_conflict() -> dict:
    raw = _raw_master()
    uff = next(e for e in raw["experience"] if e["id"] == "exp_uffpay")
    uff["dateConflict"]["status"] = "unresolved"
    uff["dateStatus"] = "conflicted"
    uff.pop("additionalPeriods", None)
    return raw


def test_unresolved_dates_never_reach_prompt_or_cv():
    compact = build_compact_profile(_raw_with_open_conflict())
    jobs = {e["company"]: e for e in compact["experience"]}
    assert jobs["UffPay"]["dates_verified"] is False
    assert jobs["UffPay"]["dates"] == "" and jobs["UffPay"]["start_date"] is None
    prompt_jobs = {e["company"]: e for e in profile_for_prompt(compact)["experience"]}
    assert prompt_jobs["UffPay"]["dates"] == ""
    assert prompt_jobs["Lumston"]["dates"] == "May 2023 – Jun 2025"
    cv, report = _build_cv(
        {"target_role": "Frontend", "summary": "", "experience": [
            {"company": "UffPay", "position": "Frontend", "dates": "Jan 2023 – Jul 2024", "bullets": []}]},
        CvDocument(id="b", name="x", email=""), compact, "en", EN_VACANCY,
    )
    assert next(j for j in cv.experience if j.company == "UffPay").period == ""
    assert any("Fechas sin verificar en UffPay" in n for n in report["notes"])


def test_saving_profile_with_same_dates_does_not_promote_conflict():
    raw = _raw_with_open_conflict()
    before = len(raw["userValidation"]["resolved"])
    items = [
        ExperienceEditItem(
            id=e["id"],
            startDate=e["startDate"],
            endDate=e["endDate"],
            current=bool(e["current"]),
            employmentType=e.get("employmentType"),
        )
        for e in raw["experience"]
    ]
    apply_experience_edits(raw, items)
    by_id = {e["id"]: e for e in raw["experience"]}
    assert date_conflict_open(by_id["exp_uffpay"])
    assert by_id["exp_uffpay"]["dateStatus"] == "conflicted"
    new = raw["userValidation"]["resolved"][before:]
    assert not any(r["field"] in {"experience.UffPay.startDate", "experience.MonkeyCave.dates"} for r in new)
    assert build_compact_profile(raw)["experience"][0]["dates_verified"] is False


def test_explicit_user_validation_resolves_conflict_with_a_parsed_range():
    raw = _raw_with_open_conflict()
    apply_user_validation(raw, "experience.UffPay.startDate", "2024-01 – 2024-07")
    uff = next(e for e in raw["experience"] if e["id"] == "exp_uffpay")
    assert (uff["startDate"], uff["endDate"], uff["current"]) == ("2024-01", "2024-07", False)
    assert not date_conflict_open(uff)
    assert uff["dateConflict"]["status"] == "user_resolved"
    compact = build_compact_profile(raw)
    assert compact["experience"][0]["dates"] == "Jan 2024 – Jul 2024"


# --- Proyectos y hechos sin respaldo ----------------------------------------------------------


def test_incomplete_projects_are_withheld_but_kept_in_master():
    # Mecanismo: un proyecto sin tecnologías ni funcionalidades no va al prompt, pero sigue en el perfil.
    raw = _raw_master()
    for project in raw["projects"]:
        if project["name"] in {"Altos Aceros", "Safra Bank"}:
            project["technologies"] = []
            project["features"] = []
    compact = build_compact_profile(raw)
    withheld = {p["name"] for p in compact["withheld_projects"]}
    assert {"Altos Aceros", "Safra Bank"} <= withheld
    assert not ({"Altos Aceros", "Safra Bank"} & {p["name"] for p in compact["projects"]})
    assert {"Altos Aceros", "Safra Bank"} <= {p["name"] for p in raw["projects"]}


def test_projects_completed_by_the_user_are_sent(compact):
    # El 2026-10-30 el usuario agregó tecnologías a Safra Bank y Altos Aceros: ya entran.
    sent = {p["name"]: p for p in compact["projects"]}
    for name in ["Volaris Manifest", "Tecnológico de Monterrey", "Drizline", "Baker Tilly Legal Chatbot",
                 "AI Video Creation and Editing Platform", "Blackeagle", "Safra Bank", "Altos Aceros"]:
        assert name in sent, name
    assert "NestJS" in sent["Safra Bank"]["technologies"]  # «Nest JS» normalizado
    assert "no se atribuye" not in sent["Safra Bank"]["description"]


def test_project_internal_notes_are_not_sent_as_facts(compact):
    projects = {p["name"]: p for p in compact["projects"]}
    video = projects["AI Video Creation and Editing Platform"]
    assert "sin confirmar" not in video["description"]
    assert "EE.UU" not in video["description"] and "EE. UU" not in video["description"]
    assert any("cliente" in u for u in video["unknown"])
    prompt = json.dumps(profile_for_prompt(compact), ensure_ascii=False)
    assert "no se atribuye" not in prompt
    assert "sin confirmarse" not in prompt
    # Validado en el perfil: se conserva.
    assert "Angular 16" in json.dumps(projects["Volaris Manifest"], ensure_ascii=False)
    assert "pdfmake" in projects["Volaris Manifest"]["technologies"]


def test_table_metric_is_grainchain_not_safra(compact):
    grain = next(e for e in compact["experience"] if e["company"] == "Grainchain Inc")
    rejected: list[dict] = []
    bullets = _bullets_for_job(
        grain,
        [
            "Delivered Safra Bank end to end and cut load times from 8 s to 3 s (62%).",
            "Cut loan-table load time from 8 s to 3 s (62%) with virtual scrolling and pagination.",
        ],
        EN_VACANCY,
        "Senior Frontend Developer",
        "en",
        master=compact,
        rejected=rejected,
    )
    assert "Cut loan-table load time from 8 s to 3 s (62%) with virtual scrolling and pagination." in bullets
    assert not any("Safra" in b for b in bullets)
    assert rejected and "Safra Bank" in rejected[0]["reason"]
    metric = next(m for m in compact["metrics"] if m["company"] == "Grainchain Inc")
    assert metric["project"] is None


def test_unsupported_metric_is_rejected_and_real_facts_fill_in(compact):
    lumston = next(e for e in compact["experience"] if e["company"] == "Lumston")
    rejected: list[dict] = []
    bullets = _bullets_for_job(
        lumston,
        ["Cut load times by 60% across all enterprise apps."],
        EN_VACANCY,
        "Frontend Developer",
        "en",
        master=compact,
        rejected=rejected,
    )
    assert not any("60%" in b for b in bullets)
    assert rejected[0]["reason"].startswith("métrica 60%")
    assert len(bullets) >= 2  # rellenado con hechos reales del maestro


def test_summary_claims_are_flagged_not_deleted(compact):
    summary = "Senior Frontend Developer who boosted Safra Bank rendering by 35% and conversion by 80%."
    data = {"target_role": "Senior Frontend Developer", "summary": summary, "experience": []}
    cv, report = _build_cv(data, CvDocument(id="b", name="x", email=""), compact, "en", EN_VACANCY)
    assert cv.summary == summary
    joined = " ".join(report["summary_claims"])
    assert "80%" in joined


def test_no_generic_or_inferred_bullets():
    source = {"company": "X", "technologies": ["React Native", "AdonisJS"], "responsibilities": [], "achievements": []}
    assert "Shipped" not in _focus_line(source, "Developer", "en")
    assert _focus_line(source, "Developer", "en") == "Technologies: React Native, AdonisJS."
    assert _focus_line({"technologies": []}, "Developer", "en") == ""
    multi = {
        "technologies": ["React Native", "AdonisJS"],
        "responsibilities": ["Validaciones y mejoras de UX en flujos de pago"],
        "achievements": [],
    }
    # No pega «con React Native y AdonisJS» a un hecho que no lo dice.
    assert _real_bullets(multi, "Frontend", "es", 2) == ["Validaciones y mejoras de UX en flujos de pago."]


# --- Ubicación y campos opcionales ------------------------------------------------------------


def test_location_is_kept_in_profile_but_omitted_from_cv():
    raw = _raw_master()
    assert raw["profile"]["contact"]["location"]["value"] == "Mexico"
    assert "location" in omitted_contact_fields(raw)
    assert "location" not in build_compact_profile(raw)["contact"]
    assert matcher.load_all_cvs()[0].location == ""


def test_location_shows_when_no_omission_rule():
    raw = _raw_master()
    raw["cvGenerationRules"].pop("omitContactFields", None)
    for conflict in raw["conflicts"]:
        if conflict["field"] == "profile.contact.location":
            conflict["preferredValue"] = "Mexico"
    assert build_compact_profile(raw)["contact"]["location"] == "Mexico"


def test_other_contact_fields_are_unaffected():
    contact = build_compact_profile(_raw_master())["contact"]
    assert contact["email"] == "jairoantoniocamarillotinoco@gmail.com"
    assert contact["phone"] == "+52 271 352 9511"


# --- Perfiles borrados (cv_1/cv_2/cv_3) -------------------------------------------------------


def test_no_template_files_and_matcher_uses_master():
    assert not list(kb_dir().glob("cv_*.json"))
    cvs = matcher.load_all_cvs()
    assert [c.id for c in cvs] == ["master_profile"]
    base = cvs[0]
    assert base.name == "Jairo Antonio Camarillo Tinoco"
    assert base.experience == [] and base.summary == ""


def test_match_step_no_longer_crashes_without_templates():
    resp = asyncio.run(vp.run_match_for_blob(EN_VACANCY))
    assert resp.chosen_cv_id == "master_profile"
    assert resp.raw_meta["profiles_loaded"] == 1


def test_runtime_code_does_not_read_deleted_profile_files():
    for path in (ROOT / "app").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"cv_[123]\.json", text), path


def test_deleted_files_are_marked_as_historical_sources():
    sources = {s["id"]: s for s in _raw_master()["sources"]}
    for sid in ("src_kb_cv1", "src_kb_cv2", "src_kb_cv3"):
        assert sources[sid]["status"] == "removed"


# --- Educación: Ingeniería declarada por el usuario; TSU oculto en CVs, conservado en el perfil --


def test_engineering_degree_shows_and_tsu_stays_in_profile_only():
    from app.locale_util import education_line

    raw = _raw_master()
    ids = [e["id"] for e in raw["education"]]
    assert "edu_tsu_utcv" in ids and ids[0] == "edu_ing_utcv"
    compact = build_compact_profile(raw)
    es = education_line(compact, "es")
    en = education_line(compact, "en")
    assert es.startswith("Ingeniería en Desarrollo y Gestión de Software — Universidad Tecnológica del Centro de Veracruz (2022)")
    assert "Bachelor of Engineering in Software Development and Management" in en
    assert "TSU" not in es and "TSU" not in en and "Associate" not in en


# --- Sin Ollama -------------------------------------------------------------------------------


def test_ollama_provider_is_gone(monkeypatch):
    from app.llm import factory

    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    factory.reset_cv_llm_backend_cache()
    with pytest.raises(ValueError, match="gemini, openai"):
        factory.get_cv_llm_backend()
    factory.reset_cv_llm_backend_cache()
    for path in (ROOT / "app").rglob("*.py"):
        assert "ollama" not in path.read_text(encoding="utf-8").lower(), path
    assert not (ROOT / "app" / "llm" / "ollama_backend.py").exists()
