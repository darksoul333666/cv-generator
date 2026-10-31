"""Revisión del CV para la app: nota de redacción y cobertura de palabras clave."""

from __future__ import annotations

import pytest

from app.compact_master import load_compact_profile
from app.cv_review import build_review, keyword_coverage
from app.llm.cv_builder import _build_cv
from app.models import CvDocument, ExperienceItem, StackBlock

VACANCY = (
    "Senior React Native Developer. Requirements: React Native, TypeScript, Node.js, Redux, "
    "Kubernetes, GraphQL. Nice to have: Sentry."
)


@pytest.fixture(scope="module")
def master() -> dict:
    return load_compact_profile()


def test_coverage_lists_matched_and_missing_terms(master):
    cv = CvDocument(
        id="x", name="x", email="",
        summary="Senior React Native Developer building apps with TypeScript.",
        experience=[ExperienceItem(company="UffPay", role="Dev", period="", bullets=["Built the app with Redux and Node"])],
        stack=StackBlock(frontend="React Native, TypeScript"),
    )
    cov = keyword_coverage(cv, master, VACANCY, ["Kubernetes", "GraphQL", "Senior React Native"])
    assert {"React Native", "TypeScript", "Redux", "Node.js"} <= set(cov["matched"])  # «Node» cuenta como Node.js
    assert {"Kubernetes", "GraphQL"} <= set(cov["missing"])
    assert "Senior React Native" not in cov["matched"] + cov["missing"]  # títulos no son palabras clave
    assert 0 < cov["percent"] < 100


def test_no_vacancy_means_no_coverage(master):
    cov = keyword_coverage(CvDocument(id="x", name="x", email=""), master, "", [])
    assert cov == {"matched": [], "missing": [], "percent": None}


def test_build_cv_attaches_review(master):
    data = {"target_role": "Senior React Native Developer", "summary": "Senior React Native Developer.",
            "keywords": ["Kubernetes"], "experience": []}
    cv, report = _build_cv(data, CvDocument(id="b", name="x", email=""), master, "en", VACANCY)
    review = report["review"]
    assert review["quality_score"] is not None
    # Las tecnologías de la vacante que el modelo pone en skills cuentan como cubiertas.
    assert {"React Native", "Kubernetes"} <= set(review["coverage"]["matched"])
    assert build_review({}) ["coverage"]["percent"] is None
