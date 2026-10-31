"""Redacción: lo que GPT y Gemini castigaron en el CV (oct 2026) no debe volver a salir.

- «as as» en el resumen; «standards and SonarQube» dos veces en un bullet.
- «7+ years» cuando las fechas visibles dan 6.8.
- UffPay con dos rangos de fechas en la misma línea.
- React y React.js a la vez; Sentry y n8n en Backend; «Backend APIs» como skill.
"""

from __future__ import annotations

import pytest

from app.compact_master import load_compact_profile
from app.llm.cv_builder import _build_cv, shown_years
from app.models import CvDocument
from app.skill_stack import build_stack_from_master
from app.text_quality import clean_text, find_issues, quality_score

from fakes import EN_VACANCY

REACT_VACANCY = (
    "Senior Full Stack Developer (React, Node.js)\n"
    "We need a Senior Full Stack engineer with React, Next.js, TypeScript, Node.js and PostgreSQL. "
    "Monitoring with Sentry is a plus."
)

MONKEY_DUP = (
    "Increased closed activities per sprint by 25% with code reviews, standards and architectural patterns, "
    "DORA metrics and SonarQube, standards and SonarQube."
)


@pytest.fixture(scope="module")
def master() -> dict:
    return load_compact_profile()


def _build(master: dict, data: dict, vacancy: str = REACT_VACANCY, locale: str = "en", proofreader=None):
    return _build_cv(data, CvDocument(id="b", name="x", email=""), master, locale, vacancy, None, proofreader)


def _all_text(cv) -> list[str]:
    return [cv.summary] + [b for job in cv.experience for b in job.bullets]


# --- Arreglos deterministas --------------------------------------------------------------------


def test_clean_text_fixes_repeated_word_and_repeated_list_item():
    assert clean_text("7+ years of experience as as a Full Stack Developer.").text == (
        "7+ years of experience as a Full Stack Developer."
    )
    assert clean_text(MONKEY_DUP).text == (
        "Increased closed activities per sprint by 25% with code reviews, standards and architectural "
        "patterns, DORA metrics and SonarQube."
    )


def test_clean_text_keeps_legitimate_lists_and_numbers():
    text = "Built dashboards with Angular, Angular Material and NgRx."
    assert clean_text(text).text == text
    text = "Reduced load time from 10 s to 3 s, 70% faster."
    assert clean_text(text).text == text


def test_issues_and_score_weight_errors_more_than_style():
    bad = find_issues("summary", "I build apps as as a developer.", "summary", "en")
    codes = {i.code for i in bad}
    assert {"repeated_word", "first_person"} <= codes
    fragment = find_issues("experience[0].bullets[0]", "Inventory management and statistics.", "bullet", "en")
    assert [i.code for i in fragment] == ["no_leading_verb"]
    es_ok = find_issues("experience[0].bullets[0]", "Reduje el tiempo de carga de 8 s a 3 s.", "bullet", "es")
    assert es_ok == []
    assert quality_score(bad) < quality_score(fragment) < 10


# --- Años visibles -----------------------------------------------------------------------------


def test_shown_years_counts_overlaps_once():
    sources = [
        {"start_date": "2020-01", "end_date": "2021-12"},
        {"start_date": "2021-06", "end_date": "2022-12"},  # se solapa: no suma dos veces
    ]
    assert shown_years(sources, today="2026-10") == 3.0
    assert shown_years([{"start_date": "2020-01", "current": True}], today="2026-10") == 6.8


def test_summary_years_match_visible_dates_and_no_double_as(master):
    data = {
        "target_role": "Senior Full Stack Developer",
        "summary": "7+ years as as a Full Stack Developer focused on React, Next.js and Node.js.",
        "experience": [],
    }
    cv, report = _build(master, data)
    assert cv.summary.startswith("6+ years of experience as a Full Stack Developer")
    assert " as as " not in cv.summary
    assert report["quality"]["autofixed"]


# --- Bullets del modelo --------------------------------------------------------------------------


def test_model_bullet_with_repeated_list_item_is_cleaned(master):
    data = {
        "target_role": "Senior Full Stack Developer",
        "summary": "Senior Full Stack Developer building React and Node.js products.",
        "experience": [{"company": "Monkey Cave", "position": "Technical Leader", "bullets": [MONKEY_DUP]}],
    }
    cv, report = _build(master, data)
    monkey = next(j for j in cv.experience if j.company == "Monkey Cave")
    assert not any("standards and SonarQube, standards" in b for b in monkey.bullets)
    assert all(i["code"] not in {"repeated_word", "repeated_phrase"} for i in report["quality"]["issues"])


def test_one_period_per_company(master):
    cv, _ = _build(master, {"target_role": "Developer", "summary": "", "experience": []})
    uff = next(j for j in cv.experience if j.company == "UffPay")
    assert uff.period == "Apr 2026 – Present"
    assert all("·" not in j.period for j in cv.experience)


# --- Revisión del LLM ----------------------------------------------------------------------------


def test_proofreader_fixes_are_applied_and_validated(master):
    data = {
        "target_role": "Senior Full Stack Developer",
        "summary": "I build end-to-end features with React and Node.js.",
        "experience": [
            {
                "company": "Grainchain Inc",
                "position": "Senior Frontend Developer",
                "bullets": ["Reduced loan table load time from 8 s to 3 s (62%) with virtual scroll and pagination."],
            }
        ],
    }
    seen: list[list[str]] = []

    def proofreader(texts, locale, hints):
        seen.append(hints)
        out = []
        for text in texts:
            if text.startswith("I build"):
                out.append("Builds end-to-end features with React and Node.js.")
            elif "8 s to 3 s" in text:
                out.append(text.replace("8 s", "9 s"))  # cambia una cifra: se rechaza
            else:
                out.append(text)
        return out

    cv, report = _build(master, data, proofreader=proofreader)
    assert cv.summary == "Builds end-to-end features with React and Node.js."
    grain = next(j for j in cv.experience if j.company == "Grainchain Inc")
    assert any("from 8 s to 3 s (62%)" in b for b in grain.bullets)
    proof = report["quality"]["proofread"]
    assert proof["ran"] and proof["changed"]
    assert any(r["reason"] == "cambió una cifra" for r in proof["rejected"])
    assert any("primera persona" in h for batch in seen for hs in batch for h in hs)
    assert any("Se descartó una corrección de redacción" in n for n in report["notes"])


def test_proofreader_failure_never_breaks_the_cv(master):
    def broken(texts, locale, hints):
        raise RuntimeError("timeout")

    data = {"target_role": "Developer", "summary": "Full Stack Developer with React.", "experience": []}
    cv, report = _build(master, data, proofreader=broken)
    assert cv.summary == "Full Stack Developer with React."
    assert report["quality"]["proofread"]["error"] == "timeout"


def test_quality_score_is_reported(master):
    data = {"target_role": "Developer", "summary": "Full Stack Developer with React.", "experience": []}
    _cv, report = _build(master, data)
    assert 0 <= report["quality"]["score"] <= 10


# --- Skills --------------------------------------------------------------------------------------


def test_skills_dedupe_spellings_and_put_ops_tools_in_cloud(master):
    stack = build_stack_from_master(
        master, REACT_VACANCY, overlay=["React.js", "Sentry", "n8n", "Backend APIs", "Monitoring", "Workflow automation"]
    )
    rows = {name: [p.strip() for p in value.split(",") if p.strip()] for name, value in stack.model_dump().items()}
    everything = [p for row in rows.values() for p in row]
    reacts = [p for p in everything if p.lower().replace(".js", "") == "react"]
    assert len(reacts) == 1
    assert "Sentry" not in rows["backend"] and "n8n" not in rows["backend"]
    for vague in ("Backend APIs", "Monitoring", "Workflow automation"):
        assert vague not in everything


def test_angular_vacancy_still_works(master):
    stack = build_stack_from_master(master, EN_VACANCY)
    assert "Angular" in stack.frontend


def test_dotnet_keeps_its_space():
    assert clean_text("Built APIs with C# and .NET , using Azure .").text == "Built APIs with C# and .NET, using Azure."
    assert find_issues("summary", "Built APIs with .NET.", "summary", "en") == []
