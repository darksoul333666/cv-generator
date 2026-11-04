"""CV «Full Stack Developer» para New Beginnings (CRM, oct 2026): lo que salió mal en el PDF.

- «CI CD» en skills: la vacante escribe «CI/CD» y se tomó el par de palabras «CI CD».
- SOLID contaba como palabra clave cubierta porque la vacante dice «solid backend logic».
- Se descartó el logro real de Grainchain (8 s → 3 s) porque el modelo puso «Pagination» en
  skills y el perfil lo dice en español («paginación»).
"""

from __future__ import annotations

import pytest

from app.compact_master import load_compact_profile
from app.cv_review import keyword_coverage
from app.llm.cv_builder import _build_cv
from app.models import CvDocument
from app.skill_stack import _alias_index, build_stack_from_master, vacancy_spelling

VACANCY = (
    "Full Stack Developer (Remote, Mexico-Based)\n"
    "Build and ship features across the full stack using TypeScript/JavaScript, React.js, Next.js, and PostgreSQL.\n"
    "Set up and maintain workflow automations, integrations, and CI/CD pipelines.\n"
    "You can build a clean UI and write solid backend logic.\n"
)


@pytest.fixture(scope="module")
def master() -> dict:
    return load_compact_profile()


def test_ci_cd_keeps_its_slash(master):
    assert vacancy_spelling("CI/CD", _alias_index(master), VACANCY) == ""
    blob = " | ".join(build_stack_from_master(master, VACANCY).model_dump().values())
    assert "CI CD" not in blob


def test_lowercase_word_is_not_an_acronym(master):
    data = {"target_role": "Full Stack Developer", "summary": "Full Stack Developer.", "experience": []}
    cv, _ = _build_cv(data, CvDocument(id="b", name="x", email=""), master, "en", VACANCY, None, None)
    coverage = keyword_coverage(cv, master, VACANCY)
    assert "SOLID" not in coverage["matched"] + coverage["missing"]
    assert len(coverage["matched"]) == len(set(coverage["matched"]))


def test_metric_bullet_survives_a_translated_skill_from_the_model(master):
    bullet = "Reduced loan table load time from 8 s to 3 s (62%) with virtual scroll and pagination."
    data = {
        "target_role": "Full Stack Developer",
        "summary": "Full Stack Developer.",
        "skills": ["Pagination"],
        "experience": [{"company": "Grainchain Inc", "position": "Senior Frontend Developer", "bullets": [bullet]}],
    }
    cv, report = _build_cv(data, CvDocument(id="b", name="x", email=""), master, "en", VACANCY, None, None)
    grain = next(j for j in cv.experience if j.company == "Grainchain Inc")
    assert bullet in grain.bullets
    assert not any("Pagination" in r["reason"] for r in report["rejected_claims"])
