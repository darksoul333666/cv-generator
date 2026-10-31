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
