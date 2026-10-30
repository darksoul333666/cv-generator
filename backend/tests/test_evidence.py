"""Cada cifra con su cómo y su medición; cada cargo con su alcance. Nada se inventa."""

from __future__ import annotations

import json

import pytest
from fastapi import HTTPException

from app.career_kb import EvidenceIn, apply_evidence, evidence_gaps
from app.compact_master import build_compact_profile, kb_dir, load_compact_profile, profile_for_prompt
from app.llm.cv_builder import _build_cv, _bullets_for_job, _fact_sentences
from app.llm.prompts import tailor_writing_rules
from app.models import CvDocument

from fakes import EN_VACANCY


def _raw() -> dict:
    return json.loads((kb_dir() / "master_profile.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def compact() -> dict:
    return load_compact_profile()


def _job(compact: dict, company: str) -> dict:
    return next(e for e in compact["experience"] if e["company"] == company)


# --- Datos confirmados por el usuario (2026-10-30) ---------------------------------------------


def test_metrics_now_match_the_users_measurements():
    raw = _raw()
    by_id = {e["id"]: e for e in raw["experience"]}
    grain = by_id["exp_grainchain"]["achievements"][0]
    assert grain["metric"]["value"] == 62
    assert grain["evidenceDetail"]["before"] == {"value": 8, "unit": "s"}
    assert grain["evidenceDetail"]["after"] == {"value": 3, "unit": "s"}
    volaris = next(a for a in by_id["exp_lumston"]["achievements"] if a.get("project") == "Volaris Manifest")
    assert volaris["metric"]["value"] == 70
    monkey = by_id["exp_monkey_cave"]["achievements"][0]
    assert monkey["description"] == "Aumento de actividades cerradas por sprint"
    # Ya no queda el 35% como cifra de Grainchain en ningún lado que el generador lea.
    metrics = {m["id"]: m for m in raw["metrics"]}
    assert metrics["metric_exp_grainchain_0"]["value"] == 62
    assert metrics["metric_exp_lumston_0"]["project"] == "Volaris Manifest"


def test_role_scope_is_recorded(compact):
    assert _job(compact, "Monkey Cave")["scope"]["team_size"] == 5
    assert _job(compact, "Grainchain Inc")["scope"]["team_size"] == 4
    assert _job(compact, "Lumston")["scope"]["team_size"] == "6–8"
    assert "Liderazgo técnico de un equipo de 5 personas" in _job(compact, "Monkey Cave")["scope"]["highlights"]


# --- Lo que ve el modelo ------------------------------------------------------------------------


def test_prompt_carries_how_measurement_and_scope(compact):
    prompt = profile_for_prompt(compact)
    jobs = {e["company"]: e for e in prompt["experience"]}
    grain = jobs["Grainchain Inc"]["achievements"][0]
    assert grain["metric"] == "62%"
    assert grain["before_after"] == "8 s → 3 s"
    assert grain["how"] == "Virtual scroll y paginación"
    assert grain["measured_by"]
    assert jobs["Grainchain Inc"]["scope"]["team_size"] == 4
    uff = jobs["UffPay"]["achievements"][0]
    assert uff["metric"] == "25%"  # antes llegaba como «25.0 percent»
    assert "Sentry" in uff["tools"]
    rules = tailor_writing_rules()
    assert "Never write a metric without its how" in rules
    assert "For every job with scope, one bullet must show that scope" in rules


def test_internal_notes_are_not_sent(compact):
    blob = json.dumps(profile_for_prompt(compact), ensure_ascii=False)
    assert "El perfil decía" not in blob
    assert "Declarado por el usuario" not in blob


# --- Bullets de respaldo (del perfil) -----------------------------------------------------------


def test_master_facts_include_how_and_only_their_own_metric(compact):
    facts = _fact_sentences(_job(compact, "Grainchain Inc"))
    assert facts[0] == (
        "Reducción del tiempo de carga de las tablas de préstamos de 8 s a 3 s "
        "mediante virtual scroll y paginación (62%)"
    )
    monkey = _fact_sentences(_job(compact, "Monkey Cave"))
    qualitative = next(f for f in monkey if f.startswith("Reducción de bugs"))
    assert "25%" not in qualitative  # antes se le pegaba la cifra de otro logro
    assert "Liderazgo técnico de un equipo de 5 personas" in monkey


# --- Verificación de bullets del modelo ---------------------------------------------------------


def test_invented_seconds_are_rejected(compact):
    rejected: list[dict] = []
    bullets = _bullets_for_job(
        _job(compact, "Grainchain Inc"),
        ["Cut loan-table load time from 8 s to 1 s with virtual scrolling."],
        EN_VACANCY,
        "Senior Frontend Developer",
        "en",
        master=compact,
        rejected=rejected,
    )
    assert not any("1 s" in b for b in bullets)
    assert "1 s" in rejected[0]["reason"]


def test_metric_without_how_is_kept_but_reported(compact):
    weak: list[dict] = []
    bullets = _bullets_for_job(
        _job(compact, "Grainchain Inc"),
        ["Improved loan-table performance by 62%.", "Built financial dashboards with Angular.", "Led frontend code reviews and mentored the team."],
        EN_VACANCY,
        "Senior Frontend Developer",
        "en",
        master=compact,
        weak=weak,
    )
    assert "Improved loan-table performance by 62%." in bullets
    assert weak and weak[0]["how"] == "Virtual scroll y paginación"
    # Con el cómo, no se reporta.
    weak2: list[dict] = []
    _bullets_for_job(
        _job(compact, "Grainchain Inc"),
        ["Cut loan-table load time from 8 s to 3 s (62%) with virtual scrolling and pagination."],
        EN_VACANCY,
        "Senior Frontend Developer",
        "en",
        master=compact,
        weak=weak2,
    )
    assert not [w for w in weak2 if w.get("bullet")]


def test_scope_bullet_is_added_when_missing(compact):
    bullets = _bullets_for_job(
        _job(compact, "Grainchain Inc"),
        ["Built financial dashboards with Angular and Angular Material.",
         "Cut loan-table load time from 8 s to 3 s (62%) with virtual scrolling and pagination."],
        EN_VACANCY,
        "Senior Frontend Developer",
        "en",
        master=compact,
    )
    assert "Responsable principal del frontend en un equipo de 4 personas." in bullets


def test_scope_already_shown_is_not_duplicated(compact):
    bullets = _bullets_for_job(
        _job(compact, "Monkey Cave"),
        ["Led a 5-person frontend team and defined architecture standards.",
         "Increased tasks closed per sprint by 25% through code reviews and SonarQube."],
        EN_VACANCY,
        "Technical Leader",
        "en",
        master=compact,
    )
    assert len(bullets) == 2


def test_report_notes_explain_weak_bullets(compact):
    data = {"target_role": "Senior Frontend Developer", "summary": "", "experience": [
        {"company": "Grainchain Inc", "position": "Senior Frontend Developer",
         "bullets": ["Improved loan-table performance by 62%.", "Built dashboards.", "Mentored the team in code reviews."]}]}
    _cv, report = _build_cv(data, CvDocument(id="b", name="x", email=""), compact, "en", EN_VACANCY)
    assert any("sin decir cómo se logró" in n and "Virtual scroll" in n for n in report["notes"])


# --- Pantalla Evidencia: huecos y guardado ------------------------------------------------------


def test_gaps_list_what_is_still_missing():
    gaps = evidence_gaps(_raw())
    kinds = {(g["company"], g["kind"]) for g in gaps}
    assert ("UffPay", "achievement") in kinds  # el 30% de APIs aún no tiene cómo
    assert ("Corus", "hidden") in kinds
    assert ("Grainchain Inc", "achievement") not in kinds
    assert ("Grainchain Inc", "scope") not in kinds
    uff = next(g for g in gaps if g["company"] == "UffPay")
    assert uff["metric"] == "30%"


def test_saving_evidence_fills_the_gap_and_reaches_the_prompt():
    raw = _raw()
    gap = next(g for g in evidence_gaps(raw) if g["company"] == "UffPay")
    apply_evidence(raw, EvidenceIn(
        experienceId=gap["experienceId"], achievementIndex=gap["achievementIndex"],
        action="Caché de respuestas e índices en la base de datos", measurement="Tiempos de respuesta en CloudWatch",
        before="900 ms", after="630 ms",
    ))
    assert not any(g["company"] == "UffPay" and g["kind"] == "achievement" for g in evidence_gaps(raw))
    jobs = {e["company"]: e for e in profile_for_prompt(build_compact_profile(raw))["experience"]}
    api = next(a for a in jobs["UffPay"]["achievements"] if a["metric"] == "30%")
    assert api["before_after"] == "900 ms → 630 ms"
    assert api["how"].startswith("Caché")


def test_saving_scope_and_invalid_values():
    raw = _raw()
    apply_evidence(raw, EvidenceIn(experienceId="exp_multiplica", teamSize="3",
                                   highlights=["Desarrollo de dos proyectos para Compartamos Banco"]))
    multiplica = next(e for e in raw["experience"] if e["id"] == "exp_multiplica")
    assert multiplica["roleScope"]["teamSize"] == 3
    with pytest.raises(HTTPException):
        apply_evidence(raw, EvidenceIn(experienceId="exp_grainchain", achievementIndex=0, before="rápido"))


def test_hidden_job_needs_role_and_activities_to_show():
    raw = _raw()
    with pytest.raises(HTTPException):
        apply_evidence(raw, EvidenceIn(experienceId="exp_corus", showInCv=True))
    apply_evidence(raw, EvidenceIn(
        experienceId="exp_corus", roles=["Frontend Developer"],
        responsibilities=["Desarrollo de interfaces para clientes de la consultora"], showInCv=True,
    ))
    corus = next(e for e in raw["experience"] if e["id"] == "exp_corus")
    assert "showInCv" not in corus
    assert "Corus" in build_compact_profile(raw)["allowed_companies"]


# --- Guardar desde Skills no borra la evidencia (bug del 2026-10-30) ---------------------------


def _content_from(raw: dict) -> "object":
    from app.career_kb import ProfileContentIn

    return ProfileContentIn.model_validate({
        "profile": {"fullName": "Jairo", "professionalTitles": ["Dev"], "summary": "", "email": "",
                    "phone": "", "linkedin": "", "location": ""},
        "experience": [
            {"id": e["id"], "company": e["company"], "roles": e["roles"], "employmentType": e.get("employmentType"),
             "startDate": e["startDate"], "endDate": e["endDate"], "current": e["current"],
             "responsibilities": e["responsibilities"], "technologies": e["technologies"],
             "achievements": [
                 {"description": a["description"], "metricValue": (a.get("metric") or {}).get("value"),
                  "metricUnit": (a.get("metric") or {}).get("unit") or ""}
                 for a in e.get("achievements") or []
             ]}
            for e in raw["experience"]
        ],
    })


def test_saving_profile_from_skills_keeps_evidence_and_project_link():
    from app.career_kb import apply_profile_content

    raw = _raw()
    apply_profile_content(raw, _content_from(raw))
    by_id = {e["id"]: e for e in raw["experience"]}
    grain = by_id["exp_grainchain"]["achievements"][0]
    assert grain["evidenceDetail"]["action"] == "Virtual scroll y paginación"
    volaris = next(a for a in by_id["exp_lumston"]["achievements"] if a.get("project") == "Volaris Manifest")
    assert volaris["evidenceDetail"]["before"] == {"value": 10, "unit": "s"}
    metric = next(m for m in raw["metrics"] if m["id"] == "metric_exp_lumston_0")
    assert metric["project"] == "Volaris Manifest" and metric["projectId"] == "project_volaris_manifest"
    assert not any(g["kind"] == "achievement" and g["company"] == "Grainchain Inc" for g in evidence_gaps(raw))


def test_editing_a_description_keeps_evidence_when_the_metric_is_the_same():
    from app.career_kb import apply_profile_content

    raw = _raw()
    content = _content_from(raw)
    grain_item = next(e for e in content.experience if e.id == "exp_grainchain")
    grain_item.achievements[0].description = "Carga de tablas de préstamos de 8 s a 3 s"
    apply_profile_content(raw, content)
    grain = next(e for e in raw["experience"] if e["id"] == "exp_grainchain")["achievements"][0]
    assert grain["description"] == "Carga de tablas de préstamos de 8 s a 3 s"
    assert grain["evidenceDetail"]["action"] == "Virtual scroll y paginación"


# --- Decisiones del usuario del 2026-10-30 -----------------------------------------------------


def test_education_shows_only_engineering_and_aws_cert_has_year(compact):
    from app.locale_util import cert_names, education_line

    raw = _raw()
    assert {"edu_tecnico_cetis_164", "edu_tecnico_informatica"} <= {e["id"] for e in raw["education"]}
    line = education_line(compact, "es")
    assert line == "Ingeniería en Desarrollo y Gestión de Software — Universidad Tecnológica del Centro de Veracruz (2022)"
    assert "AWS Machine Learning Certification (2024)" in cert_names(compact, "en")


def test_tech_spelling_is_normalized_for_the_cv_only(compact):
    from app.compact_master import canonical_tech

    assert canonical_tech("Nest JS") == "NestJS"
    assert canonical_tech("React Native 0.74") == "React Native 0.74"
    assert canonical_tech("Botstrap") == "Bootstrap"
    raw_safra = next(p for p in _raw()["projects"] if p["name"] == "Safra Bank")
    assert "Codepipelines" in raw_safra["technologies"]  # el perfil guarda lo que escribió el usuario
    sent = next(p for p in compact["projects"] if p["name"] == "Safra Bank")
    assert "AWS CodePipeline" in sent["technologies"]
