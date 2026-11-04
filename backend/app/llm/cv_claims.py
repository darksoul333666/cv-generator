"""Verificación de lo que escribe el modelo: cifras, proyectos, tecnologías y el «cómo»."""

from __future__ import annotations

import json
import re
from typing import Any, Optional

from .cv_roles import _norm
from .cv_facts import _HOW_STOPWORDS, _how_stems, _lower_first, _plain


# Cifras que un CV presenta como resultado: porcentajes, multiplicadores y tiempos.
# --- Hechos no respaldados en bullets ---------------------------------------------------------

_METRIC_RE = re.compile(
    r"(?<![\w.])(\d+(?:[.,]\d+)?)\s*"
    r"(%|x\b|×|percent\b|per\s*cent\b|por\s*ciento\b|ms\b|"
    r"s\b|segs?\b|segundos?\b|secs?\b|seconds?\b|mins?\b|minutos?\b|minutes?\b)",
    re.IGNORECASE,
)


def _num_key(raw: Any) -> str:
    try:
        value = float(str(raw).replace(",", "."))
    except (TypeError, ValueError):
        return str(raw)
    return str(int(value)) if value.is_integer() else str(value)


def _unit_class(unit: str) -> str:
    u = re.sub(r"\s+", "", (unit or "").lower())
    if u in {"%", "percent", "percentage", "porciento"}:
        return "%"
    if u in {"x", "×"}:
        return "x"
    if u == "ms":
        return "ms"
    if u in {"s", "seg", "segs", "segundo", "segundos", "sec", "secs", "second", "seconds"}:
        return "s"
    if u in {"min", "mins", "minuto", "minutos", "minute", "minutes"}:
        return "min"
    return ""


def _metric_token(value: Any, unit: str) -> str:
    cls = _unit_class(unit)
    return f"{_num_key(value)}{cls}" if cls else ""


def _token_label(token: str) -> str:
    """«62%» / «8s» → «8 s» / «500ms» → «500 ms», para los mensajes."""
    m = re.match(r"^([\d.]+)(.*)$", token)
    if not m or m.group(2) in {"%", "x"}:
        return token
    return f"{m.group(1)} {m.group(2)}"


def _metric_values(text: str) -> set[str]:
    return {f"{_num_key(m.group(1))}{_unit_class(m.group(2))}" for m in _METRIC_RE.finditer(text or "")}


def _achievement_tokens(ach: dict) -> set[str]:
    tokens: set[str] = set()
    metric = ach.get("metric") or {}
    if isinstance(metric, dict) and metric.get("value") is not None:
        token = _metric_token(metric["value"], str(metric.get("unit") or ""))
        if token:
            tokens.add(token)
    detail = ach.get("detail") or {}
    for key in ("before", "after"):
        point = detail.get(key) or {}
        if point.get("value") is not None:
            token = _metric_token(point["value"], str(point.get("unit") or ""))
            if token:
                tokens.add(token)
    tokens |= _metric_values(str(ach.get("description") or ""))
    return tokens


def _job_metric_values(source: dict, master: dict) -> set[str]:
    allowed: set[str] = set()
    for ach in source.get("achievements") or []:
        if isinstance(ach, dict):
            allowed |= _achievement_tokens(ach)
        else:
            allowed |= _metric_values(str(ach))
    for resp in source.get("responsibilities") or []:
        allowed |= _metric_values(str(resp))
    company = _norm(source.get("company") or "")
    for metric in master.get("metrics") or []:
        if company and _norm(metric.get("company") or "") == company and metric.get("value") is not None:
            token = _metric_token(metric["value"], str(metric.get("unit") or ""))
            if token:
                allowed.add(token)
    return allowed


def _labels(tokens: set[str]) -> str:
    return ", ".join(_token_label(t) for t in sorted(tokens))


def _mentions(term: str, text: str) -> bool:
    return bool(term) and bool(
        re.search(rf"(?<![\w]){re.escape(term)}(?![\w])", text or "", flags=re.IGNORECASE)
    )


def _project_metric_problem(text: str, master: dict) -> str:
    """Una cifra junto al nombre de un proyecto solo vale si el perfil la asigna a ese proyecto."""
    values = _metric_values(text)
    if not values:
        return ""
    for name in master.get("project_names") or []:
        if not _mentions(str(name), text):
            continue
        backed: set[str] = set()
        for m in master.get("metrics") or []:
            if m.get("value") is not None and _norm(m.get("project") or "") == _norm(name):
                token = _metric_token(m["value"], str(m.get("unit") or ""))
                if token:
                    backed.add(token)
        for job in master.get("experience") or []:
            for ach in job.get("achievements") or []:
                if isinstance(ach, dict) and _norm(ach.get("project") or "") == _norm(name):
                    backed |= _achievement_tokens(ach)
        unbacked = values - backed
        if unbacked:
            return f"métrica {_labels(unbacked)} atribuida a «{name}» sin respaldo en el perfil"
    return ""


# --- ¿El bullet explica cómo se logró la cifra? -----------------------------------------------

def _missing_how(bullet: str, source: dict) -> str:
    """Si el bullet usa una cifra cuyo «cómo» está en el perfil y no lo menciona, devuelve ese cómo."""
    tokens = _metric_values(bullet)
    if not tokens:
        return ""
    plain = _plain(bullet)
    for ach in source.get("achievements") or []:
        if not isinstance(ach, dict):
            continue
        detail = ach.get("detail") or {}
        if not detail.get("action") or not (tokens & _achievement_tokens(ach)):
            continue
        stems = _how_stems(detail)
        if stems and not any(stem in plain for stem in stems):
            return str(detail["action"])
    return ""


_HOW_CLAUSE = re.compile(
    r"\s*,?\s*\b(?:mediante|con|usando|utilizando|aplicando|implementando|mejorando|optimizando|"
    r"a trav[eé]s de|gracias a|with|using|through|via|by|implementing|improving|applying|leveraging|"
    r"thanks to)\b",
    re.IGNORECASE,
)


def _action_stems(action: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", _plain(action))
    return {w[:5] for w in words if len(w) >= 4 and w not in _HOW_STOPWORDS}


def _fix_how(bullet: str, source: dict, locale: str, tools: Optional[list[str]] = None) -> tuple[str, str]:
    """Si el «cómo» que sigue a una cifra no es el del perfil, lo reemplaza por el del perfil.

    Ej.: «…de 8 s a 3 s (62%) con lazy loading y virtualización» → «…(62%) con virtual scroll y
    paginación». Devuelve (bullet, cómo_del_perfil) o (bullet, "") si no cambió.
    """
    tokens = _metric_values(bullet)
    if not tokens:
        return bullet, ""
    for ach in source.get("achievements") or []:
        if not isinstance(ach, dict):
            continue
        action = str((ach.get("detail") or {}).get("action") or "").strip()
        own = _achievement_tokens(ach)
        if not action or not (tokens & own):
            continue
        last = None
        for m in _METRIC_RE.finditer(bullet):
            if f"{_num_key(m.group(1))}{_unit_class(m.group(2))}" in own:
                last = m
        if last is None:
            continue
        # Cierra el paréntesis de «(62%)» antes de buscar el conector.
        start = last.end() + (1 if bullet[last.end():last.end() + 1] == ")" else 0)
        clause_match = _HOW_CLAUSE.search(bullet, start)
        if not clause_match:
            continue
        stop = re.search(r"[.;]", bullet[clause_match.end():])
        end = clause_match.end() + stop.start() if stop else len(bullet)
        clause = bullet[clause_match.start():end]
        stems = _action_stems(action)
        hits = sum(1 for stem in stems if stem in _plain(clause))
        if stems and hits * 2 >= len(stems):
            return bullet, ""
        joiner = " con " if locale == "es" else " with "
        # Se conserva una cola que nombra una herramienta real («, medido con Sentry»).
        keep_tail = ""
        parts = clause.split(",")
        if len(parts) > 1 and tools and any(_mentions(t, parts[-1]) for t in tools):
            keep_tail = "," + parts[-1]
        fixed = (
            bullet[: clause_match.start()].rstrip(" ,") + joiner + _lower_first(action) + keep_tail + bullet[end:]
        )
        fixed = fixed.strip()
        if not fixed.endswith("."):
            fixed = fixed.rstrip(" ,;") + "."
        return fixed, action
    return bullet, ""


def _master_tokens(master: dict) -> set[str]:
    blob = json.dumps(
        {
            "experience": master.get("experience") or [],
            "projects": master.get("projects") or [],
            "skills": master.get("skill_inventory") or [],
            "aliases": master.get("skill_aliases") or {},
        },
        ensure_ascii=False,
    ).lower()
    return {tok.strip(".") for tok in re.findall(r"[a-z0-9#+.]+", blob)}


def _vacancy_only_terms(overlay: list[str], master: dict) -> list[str]:
    """Tecnologías que el modelo tomó de la vacante y no existen en el perfil."""
    if not overlay:
        return []
    tokens = _master_tokens(master)
    out: list[str] = []
    for term in overlay:
        parts = [t.strip(".") for t in re.findall(r"[a-z0-9#+.]+", term.lower()) if len(t.strip(".")) >= 2]
        if parts and not any(part in tokens for part in parts):
            out.append(term)
    return out


# --- Tecnologías de otro empleo ---------------------------------------------------------------

_GENERIC_TECH = {
    "typescript", "javascript", "javascript (es6+)", "html", "html5", "css", "css3", "scss",
    "rest apis", "apis", "rest", "git", "github", "web", "ios", "android",
}


# Si el empleo tiene la de la derecha, la de la izquierda está implícita.
_IMPLIED_TECH = {
    "node.js": ("nestjs", "express", "adonisjs"),
    "typescript": ("angular", "nestjs", "next.js", "react native"),
    "javascript": ("react", "angular", "node", "ionic", "vue"),
    "aws": ("aws lambda", "aws s3", "aws amplify", "cloudwatch", "sagemaker"),
}


_LEGAL_SUFFIX_RE = re.compile(r"\s+(?:inc|llc|ltd|s\.?a\.?(?: de c\.?v\.?)?|corp|co)\.?$", re.IGNORECASE)


def _linked_projects(source: dict, master: dict) -> list[dict]:
    """Proyectos de un empleo: por ``experience_id``; si el proyecto no lo tiene, por el nombre
    de la empresa en su descripción («Lumston, cliente Volaris»), sin «Inc» ni «S.A.»."""
    exp_id = source.get("id")
    company = _norm(_LEGAL_SUFFIX_RE.sub("", str(source.get("company") or "").strip()))
    out = []
    for project in master.get("projects") or []:
        linked = project.get("experience_id")
        if linked:
            if exp_id and linked == exp_id:
                out.append(project)
            continue
        if not company:
            continue
        text = _norm(f"{project.get('name') or ''} {project.get('description') or ''}")
        if company in text:
            out.append(project)
    return out


def _job_terms(source: dict, master: dict) -> list[str]:
    """Tecnologías de este empleo y de los proyectos hechos ahí."""
    terms = [str(t) for t in source.get("technologies") or []]
    for ach in source.get("achievements") or []:
        if isinstance(ach, dict):
            terms.extend(str(t) for t in (ach.get("detail") or {}).get("technologies") or [])
    for project in _linked_projects(source, master):
        terms.extend(str(t) for t in project.get("technologies") or [])
    return terms


def _job_blob(source: dict, master: dict) -> str:
    parts = [json.dumps(source, ensure_ascii=False)]
    for project in _linked_projects(source, master):
        parts.append(json.dumps(project, ensure_ascii=False))
    return _norm(" ".join(parts))


def _foreign_tech(bullet: str, source: dict, master: dict) -> str:
    """Una tecnología de otro empleo o proyecto que el bullet le atribuye a este."""
    blob = _job_blob(source, master)
    universe: set[str] = set()
    for item in list(master.get("experience") or []) + list(master.get("projects") or []):
        universe.update(str(t) for t in item.get("technologies") or [])
    for tech in sorted(universe, key=len, reverse=True):
        key = _norm(tech)
        if key in _GENERIC_TECH or len(key) < 2 or not _mentions(tech, bullet):
            continue
        if key in blob:
            continue
        if any(hint in blob for hint in _IMPLIED_TECH.get(key, ())):
            continue
        return tech
    return ""


def _stems_of(text: str) -> set[str]:
    return {w[:5] for w in re.findall(r"[a-z0-9]+", _plain(text)) if len(w) >= 4}


def _stem_backed(term: str, stems: set[str]) -> bool:
    """Cada palabra del término (4+ letras) tiene su raíz en el perfil del empleo, en cualquier
    idioma: «Pagination» ↔ «paginación», «Virtualization» ↔ «virtualización»."""
    words = [w for w in re.findall(r"[a-z0-9]+", _plain(term)) if len(w) >= 4]
    return bool(words) and all(w[:5] in stems for w in words)


def _claim_problem(
    bullet: str, source: dict, master: dict, vacancy_only: list[str]
) -> str:
    from ..tech_equivalence import framed_as_equivalent

    company = source.get("company") or "este empleo"
    unsupported = _metric_values(bullet) - _job_metric_values(source, master)
    if unsupported:
        return f"métrica {_labels(unsupported)} que no está en el perfil de {company}"
    problem = _project_metric_problem(bullet, master)
    if problem:
        return problem
    blob_stems: Optional[set[str]] = None
    for term in vacancy_only:
        if not _mentions(term, bullet):
            continue
        # «Pagination» en inglés y «paginación» en el perfil son lo mismo: no viene de la vacante.
        if blob_stems is None:
            blob_stems = _stems_of(_job_blob(source, master))
        if _stem_backed(term, blob_stems):
            continue
        # «con NestJS, patrones de ASP.NET Core» sí; «construí la API con .NET» no.
        if framed_as_equivalent(bullet, term, _job_terms(source, master), master):
            continue
        return f"«{term}» viene de la vacante y no del perfil de {company}"
    foreign = _foreign_tech(bullet, source, master)
    if foreign:
        return f"«{foreign}» es de otro empleo o proyecto, no de {company}"
    return ""


# --- Limpieza de texto: «cómo» sin respaldo y metodología -------------------------------------

_HOW_CONNECTOR = re.compile(
    r"\s*,?\s*\b(?:mediante|a trav[eé]s de|usando|utilizando|aplicando|gracias a|"
    r"through|using|via|by means of|by\s+\w+ing)\b",
    re.IGNORECASE,
)


_METHOD_CLAUSE = re.compile(
    r"\s*,?\s*\(?\b(?:medid[oa]s?|measured|observad[oa]s?|observed|seg[uú]n se midi[oó])\b[^.;)]*\)?",
    re.IGNORECASE,
)


def _unbacked_tokens(source: dict) -> set[str]:
    """Cifras de este empleo cuyo «cómo» no está en el perfil."""
    out: set[str] = set()
    for ach in source.get("achievements") or []:
        if isinstance(ach, dict) and not (ach.get("detail") or {}).get("action"):
            metric = ach.get("metric") or {}
            if isinstance(metric, dict) and metric.get("value") is not None:
                token = _metric_token(metric["value"], str(metric.get("unit") or ""))
                if token:
                    out.add(token)
    return out


def _trim_unbacked_how(text: str, unbacked: set[str], keep: list[str]) -> tuple[str, bool]:
    """Quita «mediante ajustes…» detrás de una cifra cuyo cómo no está en el perfil.

    Se conserva la cláusula si nombra una tecnología real del empleo («usando AdonisJS»).
    """
    if not unbacked or not text:
        return text, False
    out: list[str] = []
    changed = False
    for sentence in re.split(r"(?<=[.;])\s+", text):
        new = sentence
        for m in _METRIC_RE.finditer(sentence):
            token = f"{_num_key(m.group(1))}{_unit_class(m.group(2))}"
            if token not in unbacked:
                continue
            c = _HOW_CONNECTOR.search(sentence, m.end())
            if not c:
                continue
            stop = re.search(r"[.;]", sentence[c.end():])
            end = c.end() + stop.start() if stop else len(sentence)
            clause = sentence[c.start():end]
            if any(_mentions(t, clause) for t in keep):
                continue
            new = sentence[: c.start()] + sentence[end:]
            changed = True
            break
        out.append(new)
    return " ".join(out).strip(), changed


def _strip_methodology(text: str, tools: list[str]) -> str:
    """«…, medido por tiempos antes y después» fuera; «…con Sentry» se queda."""

    def repl(match: re.Match[str]) -> str:
        clause = match.group(0)
        return clause if any(_mentions(t, clause) for t in tools) else ""

    cleaned = _METHOD_CLAUSE.sub(repl, text or "")
    cleaned = re.sub(r"\s+([.,;])(?=\s|$)", r"\1", cleaned)  # no pegar « .NET»
    return re.sub(r"\s{2,}", " ", cleaned).strip()
