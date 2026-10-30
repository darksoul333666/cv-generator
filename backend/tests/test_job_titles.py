"""Los cargos de cada empleo siguen la familia del puesto al que se postula, sin inventar cargos."""

from __future__ import annotations

import pytest

from app.compact_master import base_cv_from_master, load_compact_profile
from app.llm.cv_builder import _build_cv, _pick_position, role_families, target_family
from app.locale_util import strip_freelance_from_title


@pytest.fixture(scope="module")
def master() -> dict:
    return load_compact_profile()


def _roles(master: dict, target: str, vacancy: str, model_positions: dict | None = None):
    experience = [
        {"company": c, "position": p, "bullets": []} for c, p in (model_positions or {}).items()
    ]
    cv, report = _build_cv(
        {"target_role": target, "summary": "x", "experience": experience},
        base_cv_from_master(master),
        master,
        "en",
        vacancy,
    )
    return {j.company: j.role for j in cv.experience}, report


RN = ("Senior React Native Developer", "Senior React Native Developer\nReact Native, iOS and Android.")
FE = ("Senior Frontend Developer", "Senior Frontend Developer\nAngular and TypeScript.")
FS = ("Senior Full Stack Engineer", "Senior Full Stack Engineer\nNode.js, React, AWS.")


def test_react_native_target_uses_react_native_titles_where_validated(master):
    roles, report = _roles(master, *RN)
    assert roles["UffPay"] == "React Native Developer"
    assert roles["Lumston"] == "React Native Developer"
    # Grainchain no tiene cargo móvil validado: se queda el real y se avisa, no se inventa.
    assert roles["Grainchain Inc"] == "Senior Frontend Developer"
    assert "Grainchain Inc" in report["off_family_titles"]
    assert any("React Native / móvil" in n and "Grainchain Inc" in n for n in report["notes"])


def test_frontend_target_does_not_mix_in_react_native_titles(master):
    # El modelo propuso cargos RN; con titular Frontend gana el cargo Frontend validado.
    roles, report = _roles(
        master, *FE, model_positions={"UffPay": "React Native Developer", "Lumston": "React Native Developer"}
    )
    assert roles["UffPay"] == "Frontend"
    assert roles["Lumston"] == "Frontend Developer"
    assert roles["Grainchain Inc"] == "Senior Frontend Developer"
    assert roles["Monkey Cave"] == "Senior Frontend Developer / Technical Leader"
    assert not any("react native" in r.lower() for c, r in roles.items() if c in {"UffPay", "Lumston"})


def test_full_stack_target_prefers_full_stack_titles(master):
    roles, _ = _roles(master, *FS)
    assert roles["UffPay"] == "Full Stack (React Native + Backend)"
    assert roles["Lumston"] == "Full Stack / Frontend Developer"


@pytest.mark.parametrize("target", [RN, FE, FS])
def test_titles_always_come_from_the_master(master, target):
    roles, _ = _roles(master, *target)
    known = {
        e["company"]: {strip_freelance_from_title(p) for p in e["positions"]} for e in master["experience"]
    }
    for company, role in roles.items():
        assert role.replace(" (Fintech)", "") in known[company], (company, role)


def test_role_families_and_target_family():
    assert role_families("React Native Developer") == {"mobile"}
    assert "frontend" not in role_families("React Native Developer")
    assert role_families("Full Stack / Frontend Developer") == {"fullstack", "frontend"}
    assert target_family("", "Desarrollador Frontend Senior (Angular)\n...") == "frontend"
    assert target_family("Senior React Native Developer", "Frontend role") == "mobile"


def test_model_choice_kept_only_when_equally_coherent():
    known = ["Frontend Developer", "Full Stack / Frontend Developer"]
    assert _pick_position(known, "Full Stack / Frontend Developer", "Frontend role", "Senior Frontend Developer") == (
        "Full Stack / Frontend Developer"
    )
    assert _pick_position(known, "Full Stack / Frontend Developer", "Full stack role", "Senior Full Stack Engineer") == (
        "Full Stack / Frontend Developer"
    )
    assert _pick_position(["Technical Leader", "Senior Frontend Developer"], "", "x", "Frontend Tech Lead") == (
        "Senior Frontend Developer"
    )
