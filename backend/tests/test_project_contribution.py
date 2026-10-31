"""Tu parte en cada proyecto (``contribution``) llega al prompt y el editor solo acepta valores válidos."""

from __future__ import annotations

import copy
import json

import pytest

from app.career_kb import ProjectContentIn, _apply_projects
from app.compact_master import build_compact_profile, kb_dir, profile_for_prompt


@pytest.fixture()
def raw() -> dict:
    return json.loads((kb_dir() / "master_profile.json").read_text(encoding="utf-8"))


def _project(raw: dict, contribution) -> dict:
    data = copy.deepcopy(raw)
    data["projects"] = [{**data["projects"][0], "name": "Demo", "contribution": contribution}]
    return data


def test_contribution_reaches_compact_profile_and_prompt(raw):
    compact = build_compact_profile(_project(raw, "frontend"))
    assert compact["projects"][0]["contribution"] == "frontend"
    assert profile_for_prompt(compact)["projects"][0]["contribution"] == "frontend"
    assert any("contribution" in rule for rule in compact["closed_world_rules"])


def test_unknown_or_invalid_contribution_is_empty(raw):
    assert build_compact_profile(_project(raw, "todo"))["projects"][0]["contribution"] == ""
    assert build_compact_profile(_project(raw, None))["projects"][0]["contribution"] == ""


def test_editor_saves_contribution_and_rejects_invalid_values(raw):
    data = copy.deepcopy(raw)
    _apply_projects(data, [ProjectContentIn(id="project_demo", name="Demo", contribution="backend")])
    assert data["projects"][0]["contribution"] == "backend"
    with pytest.raises(ValueError):
        ProjectContentIn(id="x", name="y", contribution="todo")


def test_projects_link_to_their_job(raw):
    from app.llm.cv_builder import _linked_projects

    compact = build_compact_profile(raw)
    grain = next(e for e in compact["experience"] if e["company"] == "Grainchain Inc")
    # «Grainchain, cliente Safra Bank»: la empresa es «Grainchain Inc» y aun así se liga.
    assert "Safra Bank" in [p["name"] for p in _linked_projects(grain, compact)]

    data = copy.deepcopy(raw)
    acolyte = next(p for p in data["projects"] if p["name"] == "Acolyte")
    acolyte["experienceId"] = "exp_grainchain"  # el id manda sobre el texto
    compact = build_compact_profile(data)
    grain = next(e for e in compact["experience"] if e["company"] == "Grainchain Inc")
    lumston = next(e for e in compact["experience"] if e["company"] == "Lumston")
    assert "Acolyte" in [p["name"] for p in _linked_projects(grain, compact)]
    assert "Acolyte" not in [p["name"] for p in _linked_projects(lumston, compact)]
