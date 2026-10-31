"""Un ATS compara texto: si la vacante dice «NodeJS», el CV debe decir «NodeJS», no «Node.js».

Pasó con vacantes reales (oct 2026): el generador reconocía la tecnología por sus alias pero
escribía la ortografía del perfil, y el ATS la contaba como faltante.
"""

from __future__ import annotations

import pytest

from app.compact_master import load_compact_profile
from app.cv_review import keyword_coverage
from app.llm.cv_builder import _build_cv
from app.models import CvDocument
from app.skill_stack import _alias_index, build_stack_from_master, vacancy_spelling

VARIANTS = "Senior Full Stack Developer with NodeJS, ReactJS, NextJS, ExpressJS, VueJS and Postgres."


@pytest.fixture(scope="module")
def master() -> dict:
    return load_compact_profile()


def _stack_items(stack) -> list[str]:
    return [p.strip() for value in stack.model_dump().values() for p in value.split(",") if p.strip()]


def test_skills_use_the_vacancy_spelling(master):
    items = _stack_items(build_stack_from_master(master, VARIANTS))
    for spelled in ("NodeJS", "ReactJS", "NextJS", "ExpressJS", "Postgres"):
        assert spelled in items
    for ours in ("Node.js", "React", "Next.js", "Express.js", "PostgreSQL"):
        assert ours not in items


def test_lowercase_vacancy_words_get_proper_casing(master):
    items = _stack_items(build_stack_from_master(master, "Buscamos dev con nodejs, reactjs y nextjs."))
    assert {"NodeJS", "ReactJS", "NextJS"} <= set(items)


def test_same_spelling_or_contained_names_are_untouched(master):
    aliases = _alias_index(master)
    assert vacancy_spelling("Node.js", aliases, "We use Node.js and React.") == ""
    assert vacancy_spelling("TypeScript", aliases, "typescript") == ""
    # «JavaScript» ya está dentro de «JavaScript (ES6+)»: no se cambia.
    assert vacancy_spelling("JavaScript (ES6+)", aliases, "Strong Javascript skills") == ""


def test_common_words_and_abbreviations_are_not_variants(master):
    aliases = _alias_index(master)
    assert vacancy_spelling("Next.js", aliases, "Next steps: a call with the team.") == ""
    assert vacancy_spelling("Node.js", aliases, "Each node of the graph") == ""
    assert vacancy_spelling("TypeScript", aliases, "TS and JS") == ""


def test_coverage_counts_only_the_vacancy_spelling(master):
    data = {"target_role": "Senior Full Stack Developer", "summary": "Full Stack Developer.", "experience": []}
    cv, _ = _build_cv(data, CvDocument(id="b", name="x", email=""), master, "en", VARIANTS, None, None)
    coverage = keyword_coverage(cv, master, VARIANTS)
    assert "NodeJS" in coverage["matched"]
    cv.experience, cv.projects = [], []  # solo cuenta lo que dicen las skills
    cv.stack.backend = cv.stack.backend.replace("NodeJS", "Node.js")
    coverage = keyword_coverage(cv, master, VARIANTS)
    assert "NodeJS" in coverage["missing"]
