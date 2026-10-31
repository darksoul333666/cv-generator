"""Bullets finales de cada empleo: los del modelo verificados y completados con hechos reales."""

from __future__ import annotations

from typing import Optional

from ..compact_master import protected_terms
from ..language_guard import protected_in
from .cv_roles import _norm
from .cv_facts import _focus_line, _matches_vacancy, _real_bullets, _scope_lines, _shows_scope
from .cv_claims import (
    _claim_problem,
    _fix_how,
    _job_terms,
    _metric_values,
    _missing_how,
    _strip_methodology,
    _trim_unbacked_how,
    _unbacked_tokens,
)


def _all_tools(master: dict) -> list[str]:
    tools: set[str] = set()
    for job in master.get("experience") or []:
        tools.update(str(t) for t in job.get("technologies") or [])
        for ach in job.get("achievements") or []:
            if isinstance(ach, dict):
                tools.update(str(t) for t in (ach.get("detail") or {}).get("technologies") or [])
    return sorted(tools)


def _covered_by(fact: str, chosen: list[str], master: dict) -> bool:
    """Un hecho del maestro ya está cubierto si un bullet elegido nombra todas sus tecnologías.

    Compara nombres protegidos (no se traducen), así detecta el duplicado aunque el bullet del
    modelo esté en inglés y el hecho del maestro en español. Pide al menos dos nombres para no
    descartar hechos distintos que comparten una sola tecnología.
    """
    terms = protected_in(fact, protected_terms(master), collapse=False) if master else set()
    if len(terms) < 2:
        return False
    return any(all(t.lower() in bullet.lower() for t in terms) for bullet in chosen)


def _bullets_for_job(
    source: dict,
    model_bullets: list[str],
    vacancy: str,
    role: str,
    locale: str,
    *,
    master: Optional[dict] = None,
    vacancy_only: Optional[list[str]] = None,
    rejected: Optional[list[dict]] = None,
    weak: Optional[list[dict]] = None,
) -> list[str]:
    """Bullets del modelo que pasan la verificación de hechos; si faltan, hechos del perfil.

    Además: si el empleo tiene alcance declarado (equipo, liderazgo, responsabilidad) y ningún
    bullet lo muestra, agrega el hecho de alcance del perfil cuando hay lugar. Un bullet con
    cifra que no dice cómo se logró se conserva, pero se reporta en ``weak``.

    El idioma no se filtra aquí: un bullet en el idioma equivocado se traduce después
    (``_apply_language``), nunca se descarta por idioma.
    """
    matched = _matches_vacancy(source, vacancy)
    cap = 4 if matched else 3
    floor = 3 if matched else 2
    chosen: list[str] = []
    seen: set[str] = set()
    metrics_used: set[str] = set()

    unbacked = _unbacked_tokens(source)
    keep_terms = _job_terms(source, master or {})
    tools = _all_tools(master or {})

    def add(text: str, *, from_master: bool = False) -> None:
        cleaned = " ".join(str(text).split()).strip()
        if not from_master:
            cleaned = _strip_methodology(cleaned, tools)
            trimmed, changed = _trim_unbacked_how(cleaned, unbacked, keep_terms)
            if changed and weak is not None:
                weak.append({"company": source.get("company"), "bullet": cleaned, "how": "", "trimmed": trimmed})
            cleaned = trimmed.rstrip(",;: ")
            if cleaned and not cleaned.endswith("."):
                cleaned += "."
            fixed, how = _fix_how(cleaned, source, locale, tools)
            if how:
                if weak is not None:
                    weak.append({"company": source.get("company"), "bullet": cleaned, "how": how, "fixed": fixed})
                cleaned = fixed
        key = _norm(cleaned)
        if not cleaned or not key or key in seen:
            return
        if not from_master:
            problem = _claim_problem(cleaned, source, master or {}, vacancy_only or [])
            if problem:
                if rejected is not None:
                    rejected.append({"company": source.get("company"), "bullet": cleaned, "reason": problem})
                return
        values = _metric_values(cleaned)
        if from_master and values & metrics_used:
            return  # la cifra ya está en otro bullet (posible duplicado traducido)
        if from_master and _covered_by(cleaned, chosen, master or {}):
            return  # el mismo hecho ya está escrito por el modelo, quizá en otro idioma
        if not from_master and weak is not None:
            how = _missing_how(cleaned, source)
            if how:
                weak.append({"company": source.get("company"), "bullet": cleaned, "how": how})
        seen.add(key)
        metrics_used.update(values)
        chosen.append(cleaned)

    for bullet in model_bullets:
        add(bullet)
        if len(chosen) >= cap:
            break
    if len(chosen) < floor:
        for fact in _real_bullets(source, role, locale, cap + 2):
            add(fact, from_master=True)
            if len(chosen) >= floor:
                break
    scope = _scope_lines(source)
    if scope and not any(_shows_scope(b) for b in chosen):
        if len(chosen) < cap:
            add(scope[0], from_master=True)
        elif weak is not None:
            weak.append({"company": source.get("company"), "bullet": "", "how": "", "scope": scope[0]})
    if not chosen:
        fallback = _focus_line(source, role, locale)
        return [fallback] if fallback else []
    return chosen[:cap]
