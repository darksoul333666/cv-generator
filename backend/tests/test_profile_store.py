"""Validación, respaldo y ruta del perfil maestro (fase 3 de la revisión del 31 oct 2026)."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from app import profile_store
from app.profile_schema import validate_profile
from app.profile_store import ProfileValidationError, kb_dir, write_profile
from app.validate_profile import main as validate_cli


@pytest.fixture()
def raw() -> dict:
    return json.loads((kb_dir() / "master_profile.json").read_text(encoding="utf-8"))


def _exp(raw: dict, company: str) -> dict:
    return next(e for e in raw["experience"] if e["company"] == company)


def test_tests_use_the_fixture_profile():
    real = Path(profile_store.__file__).resolve().parent.parent / "knowledge_base"
    assert kb_dir() != real  # nunca tu perfil real
    assert (kb_dir() / "master_profile.json").exists()


def test_fixture_profile_has_no_errors(raw):
    errors, _warnings = validate_profile(raw)
    assert errors == []


@pytest.mark.parametrize(
    "breaks, expected",
    [
        (lambda r: r["experience"].append(copy.deepcopy(r["experience"][0])), "id repetido"),
        (lambda r: r["experience"][1].update(startDate="2025-13"), "no es YYYY"),
        (lambda r: r["experience"][1].update(startDate="2026-05", endDate="2026-04"), "antes de empezar"),
        (lambda r: r["projects"][0].update(contribution="todo"), "contribution"),
        (lambda r: r["profile"].update(fullName=""), "fullName"),
        (lambda r: r["experience"][0].update(technologies="React"), "technologies"),
    ],
)
def test_shape_errors_block_saving(raw, breaks, expected):
    breaks(raw)
    errors, _ = validate_profile(raw)
    assert any(expected in e for e in errors), errors


def test_content_warnings(raw):
    uff = _exp(raw, "UffPay")
    api = next(a for a in uff["achievements"] if a["metric"]["value"] == 30.0)
    api["evidenceDetail"]["before"] = {"value": 8, "unit": "s"}  # la cifra de Grainchain
    api["evidenceDetail"]["after"] = {"value": 3, "unit": "s"}
    _exp(raw, "Grainchain Inc")["responsibilities"].append("Despliegues (solo knowledge_base cv_3)")
    raw["projects"][0]["technologies"].append("Typescript")
    raw["projects"][0]["technologies"].append("Elixir")
    errors, warnings = validate_profile(raw)
    assert errors == []
    text = "\n".join(warnings)
    assert "dice 30% pero su antes/después (8 → 3) da 62%" in text
    assert "nota interna" in text and "knowledge_base" in text
    assert "«Typescript» se escribe «TypeScript»" in text
    assert "«Elixir» se usa en" in text


def test_write_validates_backs_up_and_keeps_20(raw, tmp_path, monkeypatch):
    monkeypatch.setenv("CV_KB_DIR", str(tmp_path))
    target = tmp_path / "master_profile.json"
    target.write_text(json.dumps(raw), encoding="utf-8")
    monkeypatch.setattr(profile_store, "BACKUPS_KEPT", 3)
    for _ in range(5):
        write_profile(raw)
    backups = sorted((tmp_path / "backups").glob("master_profile-*.json"))
    assert len(backups) == 3
    assert json.loads(target.read_text(encoding="utf-8"))["profile"]["fullName"] == raw["profile"]["fullName"]

    broken = copy.deepcopy(raw)
    broken["experience"][1]["startDate"] = "ayer"
    before = target.read_text(encoding="utf-8")
    with pytest.raises(ProfileValidationError) as exc:
        write_profile(broken)
    assert any("ayer" in e for e in exc.value.errors)
    assert target.read_text(encoding="utf-8") == before  # no se tocó


def test_cli_exit_codes(raw, tmp_path, capsys):
    ok = tmp_path / "ok.json"
    ok.write_text(json.dumps(raw), encoding="utf-8")
    assert validate_cli(["x", str(ok)]) == 0
    raw["experience"][1]["startDate"] = "ayer"
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(raw), encoding="utf-8")
    assert validate_cli(["x", str(bad)]) == 1
    assert "ERROR" in capsys.readouterr().out


def test_aliases_come_from_the_skill_catalog(raw):
    from app.compact_master import build_compact_profile

    data = copy.deepcopy(raw)
    data.pop("skillAliases", None)
    for row in data["skillCatalog"]:
        if row["canonical"] == "Node.js":
            row["aliases"] = ["Node", "NodeJS"]
    aliases = build_compact_profile(data)["skill_aliases"]
    assert set(aliases["Node.js"]) >= {"Node", "NodeJS"}
