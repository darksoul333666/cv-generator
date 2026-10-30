"""Regresiones del CV «Ingeniero Full Stack Senior» que se evaluó con 7.5/10.

Cada caso reproduce una frase real de ese PDF.
"""

from __future__ import annotations

import collections

import pytest

from app.compact_master import load_compact_profile
from app.llm.cv_builder import _build_cv
from app.llm.prompts import build_optimizer_prompt
from app.compact_master import profile_for_prompt
from app.locale_util import polish_experience_title
from app.models import CvDocument
from app.skill_stack import build_stack_from_master

VACANCY_ES = (
    "Ingeniero Full Stack Senior\n"
    "Buscamos experiencia con React, Node.js/TypeScript y AWS en una fintech de pagos. "
    "Deseable: colas, retries, DLQ, idempotencia, JWT/OAuth2, Cognito."
)
VACANCY_NET = (
    "Senior Backend Engineer (.NET)\n"
    "C#, ASP.NET Core, Entity Framework, SQL Server, Azure. Experience building REST APIs."
)


@pytest.fixture(scope="module")
def master() -> dict:
    return load_compact_profile()


def _cv(master: dict, data: dict, vacancy: str = VACANCY_ES, locale: str = "es"):
    return _build_cv(data, CvDocument(id="b", name="x", email=""), master, locale, vacancy)


def _jobs(cv) -> dict:
    return {j.company: j for j in cv.experience}


def test_invented_how_for_unbacked_metric_is_removed(master):
    data = {
        "target_role": "Ingeniero Full Stack Senior",
        "summary": (
            "Más de 7 años como Senior Full Stack Engineer. "
            "Optimicé tiempos de respuesta de APIs en 30% mediante análisis y ajustes en backend."
        ),
        "experience": [{
            "company": "UffPay",
            "position": "Full Stack (React Native + Backend)",
            "bullets": [
                "Implementé backend en AdonisJS para soportar los flujos de pago y validaciones, optimizando "
                "tiempos de respuesta de APIs en 30% mediante ajustes en endpoints y consultas.",
                "Reduje errores en flujos de pago un 25% mediante validaciones, mejoras de UX y depuración en "
                "producción con Sentry y AWS CloudWatch.",
            ],
        }],
    }
    cv, report = _cv(master, data)
    uff = _jobs(cv)["UffPay"].bullets
    assert (
        "Implementé backend en AdonisJS para soportar los flujos de pago y validaciones, optimizando "
        "tiempos de respuesta de APIs en 30%." in uff
    )
    # El 25% sí tiene su cómo en el perfil: se queda completo.
    assert any("mediante validaciones, mejoras de UX" in b for b in uff)
    assert "mediante análisis y ajustes" not in cv.summary
    assert cv.summary.endswith("en 30%.")
    assert any("quité un «cómo»" in n for n in report["notes"])


def test_technology_from_another_job_is_rejected(master):
    data = {"target_role": "Ingeniero Full Stack Senior", "summary": "", "experience": [{
        "company": "UffPay", "position": "Full Stack (React Native + Backend)",
        "bullets": [
            "Desarrollé la app fintech en React Native para pagos, transferencias y recargas usando Redux y "
            "React Navigation.",
        ],
    }]}
    cv, report = _cv(master, data)
    assert not any("React Navigation" in b for b in _jobs(cv)["UffPay"].bullets)
    assert any("React Navigation" in r["reason"] and "otro empleo" in r["reason"] for r in report["rejected_claims"])


def test_methodology_does_not_leak_into_bullets(master):
    data = {"target_role": "Ingeniero Full Stack Senior", "summary": "", "experience": [
        {"company": "Grainchain Inc", "position": "Senior Frontend Developer", "bullets": [
            "Reduje el tiempo de carga de tablas de préstamos de 8 s a 3 s (62%) aplicando virtual scroll y "
            "paginación, medido por tiempos antes y después en tablas de ~100 filas.",
        ]},
        {"company": "Monkey Cave", "position": "Technical Leader", "bullets": [
            "Reducí bugs en producción y mejoré tiempos de liberación mediante métricas DORA, SonarQube y "
            "estándares de arquitectura, observado por el equipo.",
        ]},
        {"company": "UffPay", "position": "Frontend", "bullets": [
            "Reduje errores en flujos de pago un 25% con validaciones y UX, medido con Sentry y AWS CloudWatch.",
        ]},
    ]}
    cv, _ = _cv(master, data)
    jobs = _jobs(cv)
    assert (
        "Reduje el tiempo de carga de tablas de préstamos de 8 s a 3 s (62%) aplicando virtual scroll y paginación."
        in jobs["Grainchain Inc"].bullets
    )
    assert any(b.endswith("estándares de arquitectura.") for b in jobs["Monkey Cave"].bullets)
    # Si la cláusula nombra una herramienta real, se queda.
    assert any("medido con Sentry" in b for b in jobs["UffPay"].bullets)


def test_no_double_parentheses_in_fintech_title():
    title = polish_experience_title("UffPay", "Full Stack (React Native + Backend)", VACANCY_ES)
    assert title == "Full Stack (React Native + Backend, Fintech)"
    assert polish_experience_title("UffPay", "React Native Developer", VACANCY_ES) == "React Native Developer (Fintech)"


def test_skills_have_no_duplicates_across_rows(master):
    overlay = [
        "APIs REST", "REST APIs", "Seguridad", "Seguridad de APIs", "Monitoreo", "Monitoreo y logging",
        "Pagos (Cybersource, Stripe, Neonet)", "Pago electrónico", "Integraciones de pago",
        "CI/CD (GitHub Actions, Bitrise)", "Serverless", "Testing (Jest, Karma)", "Jest", "Clean Architecture",
        "SOLID", "DLQ", "Idempotencia", "Rate limiting",
    ]
    stack = build_stack_from_master(master, VACANCY_ES, overlay=overlay)
    items = [p.strip().lower() for v in stack.model_dump().values() for p in v.split(",") if p.strip()]
    dupes = [k for k, c in collections.Counter(items).items() if c > 1]
    assert dupes == []
    blob = " | ".join(items)
    assert "testing (jest" not in blob
    assert not ("seguridad" in items and "seguridad de apis" in items)
    assert not ("monitoreo" in items and "monitoreo y logging" in items)
    assert sum(1 for i in items if "pago" in i) <= 1
    # Lo que pide la vacante y no está en el perfil sí entra a skills (decisión del usuario).
    assert "dlq" in items and "idempotencia" in items


# --- Vacantes de otro stack: equivalencias, nunca sustitución ----------------------------------


def test_net_vacancy_gets_equivalents_and_closest_projects_first(master):
    prompt = build_optimizer_prompt(VACANCY_NET, profile_for_prompt(master), "en")
    assert "STACK EQUIVALENTS FOR THIS JOB" in prompt
    block = prompt.split("STACK EQUIVALENTS FOR THIS JOB", 1)[1].split("CANDIDATE MASTER PROFILE", 1)[0]
    assert '".NET"' in block and '"C#"' in block and '"NestJS"' in block
    assert "Never state that a past job was built with vacancy_tech" in prompt
    import json

    profile = json.loads(prompt.split("CANDIDATE MASTER PROFILE\n", 1)[1])
    first = profile["projects"][0]["technologies"]
    assert any(t in first for t in ("NestJS", "Express.js", "Prisma"))


def test_net_named_as_equivalent_is_kept_but_never_as_substitute(master):
    data = {"target_role": "Senior Backend Engineer", "summary": "Backend engineer with Node.js, NestJS and .NET.",
            "skills": [".NET", "C#"], "experience": [{
        "company": "Lumston", "position": "Full Stack / Frontend Developer", "bullets": [
            "Built REST APIs with .NET and Entity Framework for Drizline.",
            "Designed modular REST APIs with NestJS for Drizline, using dependency injection patterns equivalent "
            "to ASP.NET Core.",
        ],
    }]}
    cv, report = _cv(master, data, VACANCY_NET, "en")
    bullets = _jobs(cv)["Lumston"].bullets
    assert not any(b.startswith("Built REST APIs with .NET") for b in bullets)
    assert any("NestJS" in b and "ASP.NET Core" in b for b in bullets)
    assert any(".NET" in r["reason"] for r in report["rejected_claims"])
    # En skills y resumen sí aparece.
    assert ".NET" in cv.stack.backend and "C#" in cv.stack.backend
    assert ".NET" in cv.summary
    assert any("with .NET" in r["bullet"] for r in report["rejected_claims"])  # sin pegar «with.NET»


# --- Legibilidad: lo que bajó la nota del CV regenerado -----------------------------------------


def test_prompt_keeps_bullets_and_summary_short():
    from app.llm.prompts import tailor_writing_rules

    rules = tailor_writing_rules()
    assert "at most 22 words" in rules
    assert "50 to 70 words" in rules
    assert "Do not add context tails" in rules
    assert "80 to 120 words" not in rules


def test_skill_rows_do_not_explode_with_vacancy_terms(master):
    overlay = [f"Concepto {i}" for i in range(20)] + ["DLQ", "Idempotencia", "Rate limiting", "Kubernetes"]
    stack = build_stack_from_master(master, VACANCY_ES, overlay=overlay)
    for row, value in stack.model_dump().items():
        assert len([p for p in value.split(",") if p.strip()]) <= 12, row


# --- Segundo PDF regenerado («regenerado 1») ----------------------------------------------------


def test_wrong_how_is_replaced_with_the_profile_how(master):
    data = {"target_role": "Ingeniero Full Stack senior", "summary": "", "experience": [
        {"company": "Grainchain Inc", "position": "Senior Frontend Developer", "bullets": [
            "Reduje tiempo de carga de tablas de 8 s a 3 s (62%) con lazy loading y virtualización.",
        ]},
        {"company": "Lumston", "position": "Frontend Developer", "bullets": [
            "Reduje carga de vuelos de 10 s a 3 s (70%) mejorando consultas y renderizado.",
            "Aceleré entrega continua de features en 20% implementando CI/CD y buenas prácticas.",
        ]},
        {"company": "UffPay", "position": "Frontend", "bullets": [
            "Reducí errores en flujos de pago del 25% con correcciones en validaciones y handling de respuestas.",
        ]},
    ]}
    cv, report = _cv(master, data)
    jobs = _jobs(cv)
    assert "Reduje tiempo de carga de tablas de 8 s a 3 s (62%) con virtual scroll y paginación." in jobs["Grainchain Inc"].bullets
    assert "Reduje carga de vuelos de 10 s a 3 s (70%) con lazy loading y paginación." in jobs["Lumston"].bullets
    assert any(b.startswith("Aceleré entrega continua de features en 20% con componentes reutilizables") for b in jobs["Lumston"].bullets)
    assert any("con validaciones, mejoras de UX y depuración" in b for b in jobs["UffPay"].bullets)
    assert sum(1 for n in report["notes"] if "no es el de tu perfil" in n) == 4


def test_right_how_is_left_alone(master):
    data = {"target_role": "x", "summary": "", "experience": [{"company": "Grainchain Inc", "position": "x", "bullets": [
        "Cut loan-table load time from 8 s to 3 s (62%) with virtual scrolling and pagination.",
    ]}]}
    cv, report = _cv(master, data, locale="en")
    assert "Cut loan-table load time from 8 s to 3 s (62%) with virtual scrolling and pagination." in _jobs(cv)["Grainchain Inc"].bullets
    assert not any("no es el de tu perfil" in n for n in report["notes"])


def test_role_titles_and_notes_never_become_skills(master):
    stack = build_stack_from_master(master, VACANCY_ES, overlay=["Senior Full Stack", "NestJS equivalence", "Java", "rate limiting"])
    blob = " | ".join(stack.model_dump().values())
    assert "Senior Full Stack" not in blob and "equivalence" not in blob
    assert "Java" in blob and "rate limiting" in blob


def test_summary_years_phrase_and_senior_capitalized(master):
    data = {"target_role": "Ingeniero Full Stack senior",
            "summary": "7 años Senior Full Stack Engineer especializado en React y Node.js/TypeScript.",
            "experience": [{"company": "Grainchain Inc", "position": "Senior Frontend Developer", "bullets": []}]}
    cv, _ = _cv(master, data)
    assert cv.summary.startswith("Más de 7 años de experiencia como Senior Full Stack Engineer")
    assert cv.title == "Ingeniero Full Stack Senior"
    data_ok = dict(data, summary="Más de 7 años de experiencia como ingeniero Full Stack.")
    cv2, _ = _cv(master, data_ok)
    assert cv2.summary == "Más de 7 años de experiencia como ingeniero Full Stack."
