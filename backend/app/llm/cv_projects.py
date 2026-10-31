"""Proyectos freelance que se muestran según la vacante."""

from __future__ import annotations

import re

from ..models import ProjectItem
from .cv_roles import _norm
from .cv_facts import _tech_in_vacancy


FREELANCE_MAX = 3


FREELANCE_MIN_HITS = 2


_TECH_VERSION_RE = re.compile(r"\s+v?\d+(?:\.\d+)*$")


def _project_tech_hit(tech: str, vacancy: str) -> bool:
    """¿La vacante pide esta tecnología? «React» no cuenta si la vacante solo dice «React Native»."""
    base = _TECH_VERSION_RE.sub("", tech).strip()
    haystack = vacancy or ""
    if _norm(base) == "react":
        haystack = re.sub(r"react[\s-]*native|react[\s-]*navigation", " ", haystack, flags=re.IGNORECASE)
    return _tech_in_vacancy(base, haystack)


def _freelance_projects(master: dict, vacancy: str) -> list[ProjectItem]:
    """Hasta 3 proyectos freelance que más aportan a la vacante; ninguno si no tienen relación.

    Entra un proyecto si comparte al menos 2 tecnologías con la vacante. Puntaje: 2 por cada
    tecnología en común y 1 por dominio o plataforma que la vacante menciona. El stack muestra
    primero lo que pide la vacante, sin versiones.
    """
    scored: list[tuple[int, int, ProjectItem]] = []
    for index, project in enumerate(master.get("projects") or []):
        if project.get("engagement") != "freelance":
            continue
        line = str(project.get("cv_line") or "").strip()
        name = str(project.get("name") or "").strip()
        if not line or not name:
            continue
        techs: list[str] = []
        for tech in project.get("technologies") or []:
            clean = _TECH_VERSION_RE.sub("", str(tech).strip()).strip()
            if clean and clean not in techs:
                techs.append(clean)
        hits = [t for t in techs if _project_tech_hit(t, vacancy)]
        if len(hits) < FREELANCE_MIN_HITS:
            continue
        context = [str(w) for w in (project.get("domain") or []) + (project.get("platforms") or [])]
        score = 2 * len(hits) + sum(1 for w in context if _tech_in_vacancy(w, vacancy))
        stack = hits + [t for t in techs if t not in hits]
        scored.append((score, -index, ProjectItem(name=name, line=line, stack=", ".join(stack[:5]))))
    scored.sort(key=lambda row: (row[0], row[1]), reverse=True)
    return [row[2] for row in scored[:FREELANCE_MAX]]
