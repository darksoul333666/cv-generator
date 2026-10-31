"""Sección «Freelance Projects»: hasta 3 proyectos freelance que aportan a la vacante."""

from __future__ import annotations

import copy
import json

import pytest

from app.compact_master import build_compact_profile, kb_dir
from app.llm.cv_builder import _build_cv, _freelance_projects
from app.models import CvDocument

FREELANCE = {
    "Sortalia": ("Plataforma de sorteos de lujo (móvil y web) con 200 usuarios.", ["React Native", "Next.js", "NestJS", "PostgreSQL"]),
    "Fatima's Bakery": ("Sistema web de ventas e inventario usado en 15 sucursales.", ["Angular", "Laravel", "PostgreSQL"]),
    "Desansiedad": ("App iOS/Android de videollamadas con 3,000 usuarios.", ["React Native", "Express.js", "WebRTC"]),
    "Pilsar": ("PWA de catálogo con más de 230 compras hechas desde la web.", ["React", "TypeScript", "TailwindCSS"]),
}


@pytest.fixture()
def master() -> dict:
    raw = json.loads((kb_dir() / "master_profile.json").read_text(encoding="utf-8"))
    raw = copy.deepcopy(raw)
    for project in raw["projects"]:
        name = "Sortalia" if project["name"] == "SORTALIA" else project["name"]
        if name in FREELANCE:
            project["name"] = name
            project["engagement"] = "freelance"
            project["cvLine"], project["technologies"] = FREELANCE[name]
    return build_compact_profile(raw)


def test_picks_up_to_three_that_match_the_vacancy(master):
    vacancy = "Senior React Native Developer. React Native, Next.js, NestJS, PostgreSQL, WebRTC, TypeScript."
    picked = _freelance_projects(master, vacancy)
    names = [p.name for p in picked]
    assert names[:2] == ["Sortalia", "Desansiedad"]  # 4 y 2 tecnologías en común
    assert picked[0].stack.startswith("React Native, Next.js, NestJS, PostgreSQL")
    # Pilsar solo comparte TypeScript («React» no cuenta si la vacante dice «React Native»).
    assert "Pilsar" not in names
    many = "React, React Native, Next.js, NestJS, PostgreSQL, Angular, Laravel, TypeScript, TailwindCSS, Express.js, WebRTC"
    assert len(_freelance_projects(master, many)) == 3  # nunca más de 3


def test_section_is_omitted_when_nothing_matches(master):
    assert _freelance_projects(master, "Senior .NET Engineer. C#, ASP.NET Core, Azure, SQL Server.") == []


def test_projects_reach_the_cv_and_are_translated(master):
    vacancy = "Full Stack Developer with Angular, Laravel and PostgreSQL."

    def translator(texts, locale):
        return ["Web sales and inventory system used in 15 branches." if "15 sucursales" in t else t for t in texts]

    data = {"target_role": "Full Stack Developer", "summary": "Full Stack Developer.", "experience": []}
    cv, _ = _build_cv(data, CvDocument(id="b", name="x", email=""), master, "en", vacancy, translator)
    fatimas = next(p for p in cv.projects if p.name == "Fatima's Bakery")
    assert fatimas.line == "Web sales and inventory system used in 15 branches."
    assert "Angular" in fatimas.stack
    # Nunca como empleo.
    assert all(job.company not in FREELANCE for job in cv.experience)
