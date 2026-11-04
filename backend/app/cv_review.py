"""Revisión de un CV generado: nota de redacción y cobertura de palabras clave de la vacante.

Se guarda con cada CV del historial (``review``) para que la app la muestre antes de descargar:

- **Redacción**: el puntaje 0–10 y los avisos que calcula ``text_quality`` al armar el CV.
- **Palabras clave**: qué tecnologías y términos pide la vacante, cuáles aparecen en el CV
  (título, resumen, bullets, proyectos y skills) y cuáles faltan. Es lo que mira un ATS.

Una palabra clave de la vacante sale de dos lugares: las skills del perfil que la vacante
menciona (con sus alias: «Node» cuenta como «Node.js») y las palabras clave que extrajo el
modelo de la vacante. Si la vacante escribe una skill distinto («NodeJS»), se busca esa forma
exacta en el CV, porque así la compara un ATS.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Optional

from .models import CvDocument
from .skill_stack import _alias_index, _clean_overlay_name, _in_vacancy, _norm, vacancy_spelling

MAX_TERMS = 25


def _vacancy_terms(master: dict, vacancy_text: str, model_keywords: Iterable[str]) -> list[str]:
    vacancy = _norm(vacancy_text)
    aliases = _alias_index(master)
    terms: list[str] = []
    seen: set[str] = set()

    def add(name: str) -> None:
        key = _norm(name)
        if key and key not in seen:
            seen.add(key)
            terms.append(name)

    inventory = list(master.get("skill_inventory") or [])
    if not inventory:
        for values in (master.get("skills") or {}).values():
            inventory.extend(str(v) for v in values or [])
    for name in inventory:
        if vacancy and _in_vacancy(str(name), vacancy, aliases, vacancy_text):
            add(str(name))
    for raw in model_keywords or []:
        name = _clean_overlay_name(str(raw))
        if name and (not vacancy or _in_vacancy(name, vacancy, aliases)):
            add(name)
    return terms[:MAX_TERMS]


def _cv_text(cv: CvDocument) -> str:
    parts: list[str] = [cv.title, cv.summary]
    for job in cv.experience:
        parts.append(job.role)
        parts.extend(job.bullets)
    for project in cv.projects:
        parts.extend([project.name, project.line, project.stack])
    parts.extend(str(v) for v in cv.stack.model_dump().values())
    return _norm(" \n ".join(p for p in parts if p))


def keyword_coverage(
    cv: CvDocument, master: dict, vacancy_text: str, model_keywords: Optional[Iterable[str]] = None
) -> dict:
    """{"matched": [...], "missing": [...], "percent": 0–100 | None}."""
    terms = _vacancy_terms(master, vacancy_text, model_keywords or [])
    if not terms:
        return {"matched": [], "missing": [], "percent": None}
    aliases = _alias_index(master)
    text = _cv_text(cv)
    matched: list[str] = []
    missing: list[str] = []
    for term in terms:
        # Un ATS compara texto: si la vacante dice «NodeJS», «Node.js» en el CV no cuenta.
        spelled = vacancy_spelling(term, aliases, vacancy_text)
        if spelled:
            hit = bool(re.search(rf"(?<![a-z0-9]){re.escape(_norm(spelled))}(?![a-z0-9])", text))
        else:
            hit = _in_vacancy(term, text, aliases)
        label = spelled or term
        if label in matched or label in missing:
            continue
        (matched if hit else missing).append(label)
    return {"matched": matched, "missing": missing, "percent": round(100 * len(matched) / len(terms))}


def build_review(report: dict) -> dict[str, Any]:
    """Resumen para la app a partir del reporte de ``_build_cv``."""
    quality = report.get("quality") or {}
    issues = [
        f"{item.get('message')}: «{str(item.get('text') or '')[:120]}»"
        for item in quality.get("issues") or []
    ]
    return {
        "quality_score": quality.get("score"),
        "quality_errors": quality.get("errors", 0),
        "quality_warnings": quality.get("warnings", 0),
        "quality_issues": issues[:12],
        "coverage": report.get("coverage") or {"matched": [], "missing": [], "percent": None},
    }
