"""Armado del CV a partir de la respuesta del modelo (Gemini u OpenAI) y del perfil maestro.

Aquí vive todo lo que no depende del proveedor: empresas y fechas solo del maestro, verificación
de cifras, proyectos y tecnologías, cargos coherentes con la vacante, bullets de respaldo, skills
y el paso de idioma con traducción validada.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

from ..compact_master import protected_terms
from ..language_guard import LanguageItem, Translator, detect_language, protected_in, repair_language
from ..locale_util import (
    attach_percent_signs,
    cert_names,
    education_line,
    format_period,
    language_lines,
    localize_cv_wording,
    percent_metric_values,
    localize_skill_label,
    polish_experience_title,
)
from ..models import CvDocument, ExperienceItem
from ..skill_stack import build_stack_from_master, stack_to_tech_skills, vacancy_skill_keywords

logger = logging.getLogger(__name__)


def _norm(text: str) -> str:
    return " ".join(str(text or "").lower().split())


def _company_index(master: dict) -> dict[str, dict]:
    index: dict[str, dict] = {}
    for item in master.get("experience") or []:
        company = _norm(item.get("company") or "")
        if company:
            index[company] = item
    return index


_GENERIC_ROLE_WORDS = {
    "frontend",
    "backend",
    "fullstack",
    "full",
    "stack",
    "developer",
    "engineer",
    "senior",
    "junior",
    "lead",
    "leader",
    "technical",
    "software",
}


def _role_terms(role: str) -> list[str]:
    cleaned = _norm(role).replace("-", " ").replace("/", " ").replace("+", " ")
    cleaned = cleaned.replace("(", " ").replace(")", " ")
    return [
        word
        for word in cleaned.split()
        if word not in _GENERIC_ROLE_WORDS and len(word) > 2
    ]


def _term_in_vacancy(term: str, vacancy: str) -> bool:
    if not term or not vacancy:
        return False
    if re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", vacancy):
        return True
    compact_term = re.sub(r"[^a-z0-9]+", "", term)
    compact_vacancy = re.sub(r"[^a-z0-9]+", "", vacancy)
    return len(compact_term) >= 4 and compact_term in compact_vacancy


def _role_fit(role: str, vacancy: str) -> int:
    """Cuántas palabras propias del cargo aparecen en la vacante. Ignora Frontend/Developer."""
    vacancy_n = _norm(vacancy).replace("-", " ")
    return sum(1 for term in _role_terms(role) if _term_in_vacancy(term, vacancy_n))


# Familias de cargo. «react» solo cuenta como frontend si no es «react native».
_ROLE_FAMILIES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("mobile", ("react native", "mobile", "móvil", "movil", "ios", "android", "flutter", "ionic")),
    ("fullstack", ("full stack", "fullstack", "full-stack")),
    ("backend", ("backend", "back-end", "back end", "node.js", "nodejs", "nestjs", "api")),
    ("frontend", ("frontend", "front-end", "front end", "angular", "react", "vue", "next.js", "web")),
)
_LEAD_WORDS = ("lead", "leader", "líder", "lider", "tech lead", "jefe")
_FAMILY_LABEL = {
    "mobile": "React Native / móvil",
    "fullstack": "Full Stack",
    "backend": "Backend",
    "frontend": "Frontend",
}


def role_families(text: str) -> set[str]:
    blob = f" {_norm(text)} "
    found: set[str] = set()
    for family, words in _ROLE_FAMILIES:
        probe = blob.replace("react native", " ") if family == "frontend" else blob
        if any(re.search(rf"(?<![a-z0-9]){re.escape(w)}(?![a-z0-9])", probe) for w in words):
            found.add(family)
    return found


def target_family(target_role: str, vacancy: str) -> str:
    """Familia del cargo al que se postula: titular del CV, luego el título de la vacante."""
    first_line = (vacancy or "").strip().split("\n", 1)[0]
    for text in (target_role, first_line, vacancy):
        fams = role_families(text or "")
        for family, _ in _ROLE_FAMILIES:
            if family in fams:
                return family
    return ""


def _is_lead(text: str) -> bool:
    blob = f" {_norm(text)} "
    return any(re.search(rf"(?<![a-z]){re.escape(w)}(?![a-z])", blob) for w in _LEAD_WORDS)


def _pick_position(
    known: list[str], model_position: str, vacancy: str, target_role: str = ""
) -> str:
    """Entre los cargos validados del maestro, el más coherente con el cargo al que se postula.

    Orden: misma familia que el titular (React Native, Frontend, Full Stack, Backend), luego
    términos propios de la vacante (Angular, NgRx…), luego liderazgo si el titular lo pide y,
    a igualdad, el más corto. Nunca inventa un cargo: si ningún cargo del empleo es de esa
    familia, queda el mejor cargo real y ``_build_cv`` lo reporta.
    """
    roles = [str(role).strip() for role in known if str(role).strip()]
    if not roles:
        return model_position
    family = target_family(target_role, vacancy)
    wants_lead = _is_lead(target_role)

    def score(role: str) -> tuple:
        fams = role_families(role)
        return (
            1 if family and family in fams else 0,
            _role_fit(role, vacancy),
            1 if wants_lead and _is_lead(role) else 0,
            -len(role),
        )

    best = max(roles, key=score)
    if model_position and _norm(model_position) in {_norm(r) for r in roles}:
        exact = next(r for r in roles if _norm(r) == _norm(model_position))
        if score(exact)[:3] == score(best)[:3]:
            return exact
    if score(best)[:3] == (0, 0, 0) and model_position and _norm(model_position) in {_norm(r) for r in roles}:
        return model_position
    return best


def _recency_key(source: dict) -> tuple:
    """Empleo actual primero; después el que terminó más tarde."""
    current = 1 if source.get("current") else 0
    end = str(source.get("end_date") or "")
    start = str(source.get("start_date") or "")
    return (current, end, start)


def _ordered_keys(keys: list[str], companies: dict[str, dict]) -> list[str]:
    """Orden del perfil (sortOrder, el que fija el usuario) o, si falta, por fechas.

    Un empleo con fechas en conflicto no tiene fechas que comparar; su lugar sale de sortOrder.
    """
    sources = [companies.get(k) or {} for k in keys]
    if keys and all(isinstance(src.get("sort_order"), int) for src in sources):
        return sorted(keys, key=lambda k: companies[k]["sort_order"])
    return sorted(keys, key=lambda k: _recency_key(companies.get(k) or {}), reverse=True)


def _compact_token(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", _norm(text))


def _tech_in_vacancy(tech: str, vacancy: str) -> bool:
    token = _compact_token(tech)
    haystack = _compact_token(vacancy)
    if len(token) < 3 or not haystack:
        return False
    if len(token) <= 4:
        return bool(re.search(rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])", haystack))
    return token in haystack


def _matches_vacancy(source: dict, vacancy: str) -> bool:
    for tech in source.get("technologies") or []:
        if _tech_in_vacancy(str(tech), vacancy):
            return True
    return any(_role_fit(str(role), vacancy) > 0 for role in (source.get("positions") or []))


def _anchor_ym(companies: dict[str, dict]) -> str:
    anchor = ""
    for source in companies.values():
        stamp = str(source.get("start_date") or "") if source.get("current") else str(
            source.get("end_date") or source.get("start_date") or ""
        )
        if stamp > anchor:
            anchor = stamp
    return anchor


def _years_before(ym: str, years: int) -> str:
    if len(ym) < 7 or ym[4] != "-":
        return "0000-00"
    return f"{int(ym[:4]) - years:04d}{ym[4:7]}"


def _is_stale(source: dict, cutoff: str) -> bool:
    if source.get("current") or source.get("dates_verified") is False:
        return False
    end = str(source.get("end_date") or source.get("start_date") or "")
    return bool(end) and end < cutoff


def _metric_label(source: dict) -> str:
    for ach in source.get("achievements") or []:
        if not isinstance(ach, dict):
            continue
        metric = ach.get("metric") or {}
        if metric.get("value") is None:
            continue
        unit = str(metric.get("unit") or "")
        value = metric.get("value")
        if unit.lower() in {"percent", "%"}:
            return f"{value}%"
        return f"{value} {unit}".strip()
    return ""


def _achievement_metric(ach: dict) -> str:
    metric = ach.get("metric") or {}
    value = metric.get("value")
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    unit = str(metric.get("unit") or "")
    if unit.lower() in {"percent", "%"}:
        return f"{value}%"
    return f"{value} {unit}".strip()


def _tech_names(source: dict, limit: int = 4) -> list[str]:
    names: list[str] = []
    for raw in source.get("technologies") or []:
        name = str(raw).strip()
        if name and name not in names:
            names.append(name)
        if len(names) >= limit:
            break
    return names


def _join_names(names: list[str], conjunction: str) -> str:
    if len(names) <= 1:
        return names[0] if names else ""
    if len(names) == 2:
        return f"{names[0]} {conjunction} {names[1]}"
    return f"{', '.join(names[:-1])} {conjunction} {names[-1]}"


_NOTE_RE = re.compile(
    r"\s*\([^)]*(?:cv hist[oó]rico|knowledge_base|seg[uú]n)[^)]*\)",
    re.IGNORECASE,
)


def _clean_fact(text: str) -> str:
    cleaned = _NOTE_RE.sub("", text or "")
    return " ".join(cleaned.split()).strip(" .;")


def _lower_first(text: str) -> str:
    if len(text) > 1 and text[1].isupper():
        return text  # sigla o nombre propio («UX», «Sentry»)
    return text[:1].lower() + text[1:]


def _fact_sentences(source: dict) -> list[str]:
    """Hechos del perfil: logros con su cómo y su cifra, un hecho de alcance y responsabilidades.

    Cada logro lleva solo su propia cifra (antes se le pegaba la primera cifra del empleo a
    cualquier logro sin cifra).
    """
    sentences: list[str] = []
    for ach in source.get("achievements") or []:
        if isinstance(ach, dict):
            desc = _clean_fact(str(ach.get("description") or ""))
            own_metric = _achievement_metric(ach)
            detail = ach.get("detail") or {}
        else:
            desc, own_metric, detail = _clean_fact(str(ach)), "", {}
        # Un logro corto con cifra sigue siendo un hecho; sin cifra, < 25 caracteres no aporta.
        if len(desc) < (3 if own_metric else 25):
            continue
        action = str(detail.get("action") or "").strip()
        if action and not (_how_stems(detail) & {w[:5] for w in re.findall(r"[a-z0-9]+", _plain(desc)) if len(w) >= 4}):
            desc = f"{desc} mediante {_lower_first(action)}"
        if own_metric and own_metric not in desc:
            desc = f"{desc} ({own_metric})"
        sentences.append(desc)
    scope = _scope_lines(source)
    if scope:
        sentences.append(scope[0])
    for resp in source.get("responsibilities") or []:
        desc = _clean_fact(str(resp))
        if len(desc) >= 25:
            sentences.append(desc)
    sentences.extend(scope[1:])
    return sentences


def _focus_line(source: dict, role: str, locale: str) -> str:
    """Respaldo si el empleo no tiene ninguna frase en el perfil: solo el stack declarado.

    No inventa logros («Shipped production features…») ni pega una métrica sin su contexto.
    Vacío si el empleo tampoco tiene tecnologías.
    """
    techs = _tech_names(source)
    if not techs:
        return ""
    label = "Tecnologías" if locale == "es" else "Technologies"
    return f"{label}: {', '.join(techs)}."


def _usable_facts(source: dict, locale: str) -> list[str]:
    """Todos los hechos del perfil. El idioma lo resuelve el paso de traducción, no un filtro."""
    return _fact_sentences(source)


def _role_names_single_tech(source: dict, role: str) -> str:
    techs = _tech_names(source, 2)
    if len(techs) == 1 and _norm(techs[0]) in _norm(role):
        return techs[0]
    return ""


def _real_bullets(source: dict, role: str, locale: str, limit: int) -> list[str]:
    """Un bullet por hecho del perfil. No funde varias responsabilidades en una frase.

    Solo añade «con <tecnología>» cuando el empleo declara una única tecnología y el cargo la
    nombra (Ionic Developer → Ionic): ahí no es una inferencia.
    """
    facts = _usable_facts(source, locale)
    if not facts:
        return []
    single = _role_names_single_tech(source, role)
    out: list[str] = []
    for index, fact in enumerate(facts):
        line = fact
        if index == 0 and single and _norm(single) not in _norm(line):
            line = f"{line} con {single}" if locale == "es" else f"{line} with {single}"
        out.append(localize_cv_wording(line.rstrip(".") + ".", locale))
        if len(out) >= limit:
            break
    return out


def _one_real_bullet(source: dict, role: str, locale: str) -> str:
    bullets = _real_bullets(source, role, locale, 1)
    return bullets[0] if bullets else _focus_line(source, role, locale)


# --- Hechos no respaldados en bullets -------------------------------------------------------

# Cifras que un CV presenta como resultado: porcentajes, multiplicadores y tiempos.
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


# --- ¿El bullet explica cómo se logró la cifra? ----------------------------------------------

_HOW_STOPWORDS = {"como", "para", "mediante", "entre", "sobre", "with", "using", "through", "from", "into"}


def _plain(text: str) -> str:
    import unicodedata

    nfkd = unicodedata.normalize("NFKD", (text or "").lower())
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))


def _how_stems(detail: dict) -> set[str]:
    words = re.findall(r"[a-z0-9]+", _plain(" ".join([str(detail.get("action") or "")] + list(detail.get("technologies") or []))))
    return {w[:5] for w in words if len(w) >= 4 and w not in _HOW_STOPWORDS}


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


# --- Alcance del cargo (equipo, responsabilidad, liderazgo) ----------------------------------

_SCOPE_STEMS = (
    "equipo", "team", "lider", "lead", "mentor", "code review", "arquitect", "architect",
    "responsable", "owner", "punta a punta", "end-to-end", "end to end", "decisi", "estandar",
    "standard", "calidad", "quality", "personas", "people", "developers", "desarrolladores",
)


def _shows_scope(text: str) -> bool:
    plain = _plain(text)
    return any(stem in plain for stem in _SCOPE_STEMS)


def _scope_lines(source: dict) -> list[str]:
    scope = source.get("scope") or {}
    highlights = [str(h).strip() for h in scope.get("highlights") or [] if str(h).strip()]
    if not highlights:
        return []
    team = scope.get("team_size")
    first = highlights[0]
    if team not in (None, "") and str(team) not in first:
        first = f"{first} en un equipo de {team} personas"
    return [first, *highlights[1:]]


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


# --- Tecnologías de otro empleo -----------------------------------------------------------

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


def _linked_projects(source: dict, master: dict) -> list[dict]:
    company = _norm(source.get("company") or "")
    if not company:
        return []
    out = []
    for project in master.get("projects") or []:
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
    for term in vacancy_only:
        if not _mentions(term, bullet):
            continue
        # «con NestJS, patrones de ASP.NET Core» sí; «construí la API con .NET» no.
        if framed_as_equivalent(bullet, term, _job_terms(source, master), master):
            continue
        return f"«{term}» viene de la vacante y no del perfil de {company}"
    foreign = _foreign_tech(bullet, source, master)
    if foreign:
        return f"«{foreign}» es de otro empleo o proyecto, no de {company}"
    return ""


# --- Limpieza de texto: «cómo» sin respaldo y metodología --------------------------------------

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


def _years_phrase(summary: str, master: dict, locale: str) -> str:
    """«7 años Senior Full Stack Engineer…» → «Más de 7 años de experiencia como Senior…».

    Solo toca el arranque cuando le falta el conector; usa years_experience del perfil.
    """
    years = master.get("years_experience")
    try:
        whole = int(float(years))
    except (TypeError, ValueError):
        return summary
    plus = float(years) > whole
    if locale == "es":
        m = re.match(r"^\s*(?:m[aá]s de\s+)?(\d+)\+?\s+a[nñ]os\s+(?!de\b)", summary, flags=re.IGNORECASE)
        if m and int(m.group(1)) == whole:
            lead = f"Más de {whole} años" if plus else f"{whole} años"
            return f"{lead} de experiencia como {summary[m.end():]}"
    else:
        m = re.match(r"^\s*(\d+)\+?\s+years\s+(?!of\b)", summary, flags=re.IGNORECASE)
        if m and int(m.group(1)) == whole:
            return f"{whole}{'+' if plus else ''} years of experience as {summary[m.end():]}"
    return summary


_SENIOR_RE = re.compile(r"\b(senior|junior|semi-senior)\b")


def _title_case_level(title: str) -> str:
    """«Ingeniero Full Stack senior» → «Ingeniero Full Stack Senior» (consistente en todo el CV)."""
    return _SENIOR_RE.sub(lambda m: m.group(1).capitalize(), title or "")


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


def _contact(master: dict) -> dict[str, str]:
    contact = master.get("contact") or {}
    return {
        "email": str(contact.get("email") or ""),
        "phone": str(contact.get("phone") or ""),
        "linkedin": str(contact.get("linkedin") or ""),
        "location": str(contact.get("location") or ""),
    }


def _stack_labels(stack, locale: str) -> dict[str, list[str]]:
    """Etiquetas del bloque de skills. Solo aplica el glosario fijo; no descarta ninguna."""
    out: dict[str, list[str]] = {}
    for name in type(stack).model_fields:
        labels = [
            localize_skill_label(piece.strip(), locale)
            for piece in str(getattr(stack, name) or "").split(",")
            if piece.strip()
        ]
        out[name] = labels
    return out


def _apply_language(
    fields: dict[str, str],
    locale: str,
    protected: list[str],
    translator: Optional[Translator],
) -> tuple[dict[str, str], dict]:
    """Detecta el idioma de cada texto visible y traduce solo los que no coinciden."""
    items = [
        LanguageItem(path=path, text=text, detected=detect_language(text, protected))
        for path, text in fields.items()
        if str(text or "").strip()
    ]
    final, report = repair_language(items, locale, translator, protected)
    merged = dict(fields)
    merged.update(final)
    return merged, report.as_dict()


def _summary_problems(summary: str, master: dict) -> list[str]:
    allowed: set[str] = set()
    for source in master.get("experience") or []:
        allowed |= _job_metric_values(source, master)
    problems = []
    unsupported = _metric_values(summary) - allowed
    if unsupported:
        problems.append(f"summary: métrica {_labels(unsupported)} sin respaldo en el perfil")
    project = _project_metric_problem(summary, master)
    if project:
        problems.append(f"summary: {project}")
    return problems


def _verification_notes(report: dict) -> list[str]:
    notes: list[str] = []
    if report.get("off_family_titles"):
        label = _FAMILY_LABEL.get(report.get("title_family") or "", report.get("title_family"))
        notes.append(
            f"Cargos sin variante {label} validada en el perfil: "
            f"{', '.join(report['off_family_titles'])}. Se dejaron sus cargos reales. Si también "
            "trabajaste con ese rol ahí, agrégalo a los cargos de esa experiencia en el perfil "
            "y regenera el CV."
        )
    for item in report.get("unverified_dates") or []:
        cands = " / ".join(item.get("candidates") or []) or "sin candidatos"
        notes.append(
            f"Fechas sin verificar en {item['company']}: hay resoluciones en conflicto ({cands}). "
            "Se omitió el periodo; resuélvelo en el perfil maestro."
        )
    for item in report.get("rejected_claims") or []:
        notes.append(f"Se descartó un bullet de {item.get('company')}: {item.get('reason')}. Texto: «{item.get('bullet')}»")
    for item in report.get("weak_bullets") or []:
        if item.get("fixed"):
            notes.append(
                f"{item['company']}: el modelo puso un «cómo» que no es el de tu perfil. Antes: «{item['bullet']}». "
                f"Ahora: «{item['fixed']}»."
            )
            continue
        if item.get("trimmed"):
            notes.append(
                f"{item['company']}: quité un «cómo» que tu perfil no respalda. Antes: «{item['bullet']}». "
                f"Ahora: «{item['trimmed']}». Complétalo en Evidencia si lo tienes."
            )
            continue
        if item.get("scope"):
            notes.append(
                f"{item['company']}: ningún bullet muestra el alcance del cargo (p. ej. «{item['scope']}»)."
            )
        else:
            notes.append(
                f"{item['company']}: el bullet «{item['bullet']}» usa una cifra sin decir cómo se logró "
                f"(según tu perfil: {item['how']})."
            )
    for problem in report.get("summary_claims") or []:
        notes.append(f"Revisar {problem}.")
    language = report.get("language") or {}
    for item in language.get("unresolved") or []:
        notes.append(
            f"Idioma: {item['path']} sigue en «{item['detected']}» (se pidió «{language.get('locale')}»; "
            f"motivo: {item['reason']}). Se conservó el texto original."
        )
    return notes


def _build_cv(
    data: dict,
    base: CvDocument,
    master: dict,
    locale: str = "es",
    vacancy_text: str = "",
    translator: Optional[Translator] = None,
) -> tuple[CvDocument, dict]:
    """JSON del optimizer → CvDocument + reporte de verificación (fechas, hechos, idioma)."""
    companies = _company_index(master)
    allowed = {_norm(c) for c in (master.get("allowed_companies") or companies.keys())}
    personal = {_norm(n) for n in (master.get("personal_products_not_employment") or [])}
    overlay = [
        str(s).strip()
        for s in list(data.get("skills") or []) + list(data.get("keywords") or [])
        if str(s).strip()
    ]
    from ..tech_equivalence import equivalents_for_vacancy

    vacancy_only = _vacancy_only_terms(overlay, master)
    for row in equivalents_for_vacancy(vacancy_text, master):
        for term in row["vacancy_tech"]:
            if term not in vacancy_only:
                vacancy_only.append(term)
    rejected: list[dict] = []
    weak: list[dict] = []
    unverified_dates: list[dict] = []
    target_role = str(data.get("target_role") or base.title or "").strip()

    def period_for(source: dict) -> str:
        if source.get("dates_verified") is False:
            unverified_dates.append(
                {"company": source.get("company"), "candidates": source.get("date_candidates") or []}
            )
            return ""
        # Solo fechas del maestro. Las «dates» que escriba el modelo nunca se usan.
        main = format_period(
            source.get("start_date"),
            source.get("end_date"),
            bool(source.get("current")),
            locale,
        ) or str(source.get("dates") or "").strip()
        extra = [
            format_period(p.get("start_date"), p.get("end_date"), bool(p.get("current")), locale)
            for p in source.get("extra_periods") or []
        ]
        return " · ".join(part for part in [main, *extra] if part)

    built: dict[str, ExperienceItem] = {}
    for raw in data.get("experience") or []:
        if not isinstance(raw, dict):
            continue
        company = str(raw.get("company") or "").strip()
        key = _norm(company)
        if not company or key not in allowed or key in personal or key in built:
            continue
        source = companies.get(key) or {}
        period = period_for(source)
        position = str(
            raw.get("position")
            or raw.get("role")
            or raw.get("title")
            or ""
        ).strip()
        if not position:
            positions = raw.get("positions") or raw.get("roles") or []
            if isinstance(positions, list) and positions:
                position = str(positions[0] or "").strip()
            elif isinstance(positions, str):
                position = positions.strip()
        known = [str(role).strip() for role in (source.get("positions") or []) if str(role).strip()]
        known_norms = [_norm(role) for role in known]
        if position and known_norms and _norm(position) not in known_norms:
            known_blob = " ".join(known_norms)
            if not any(tok in known_blob for tok in _norm(position).split() if len(tok) > 3):
                position = known[0] if known else position
        position = _pick_position(known, position, vacancy_text, target_role)
        position = polish_experience_title(
            source.get("company") or company,
            position or (known[0] if known else ""),
            vacancy_text,
        )
        bullets = [
            localize_cv_wording(str(b).strip(), locale)
            for b in (raw.get("bullets") or raw.get("achievements") or raw.get("responsibilities") or [])
            if not isinstance(b, dict) and str(b).strip()
        ]
        role = localize_cv_wording(position, locale)
        built[key] = ExperienceItem(
            company=source.get("company") or company,
            role=role,
            period=period,
            bullets=_bullets_for_job(
                source,
                bullets,
                vacancy_text,
                role,
                locale,
                master=master,
                vacancy_only=vacancy_only,
                rejected=rejected,
                weak=weak,
            ),
        )

    cutoff = _years_before(_anchor_ym(companies), 6)
    for key, source in companies.items():
        if key in personal or key in built or key not in allowed:
            continue
        if _is_stale(source, cutoff) and not _matches_vacancy(source, vacancy_text):
            continue
        known = [str(role).strip() for role in (source.get("positions") or []) if str(role).strip()]
        position = polish_experience_title(
            source.get("company") or key,
            _pick_position(known, known[0] if known else "", vacancy_text, target_role),
            vacancy_text,
        )
        role = localize_cv_wording(position, locale)
        built[key] = ExperienceItem(
            company=source.get("company") or key,
            role=role,
            period=period_for(source),
            bullets=_bullets_for_job(
                source, [], vacancy_text, role, locale, master=master, rejected=rejected, weak=weak
            ),
        )

    for key, source in list(built.items()):
        origin = companies.get(key) or {}
        if _is_stale(origin, cutoff) and not _matches_vacancy(origin, vacancy_text):
            del built[key]

    experience = [built[key] for key in _ordered_keys(list(built), companies)]

    # Cargos sin variante validada de la familia del titular: se dejan los reales y se avisa.
    family = target_family(target_role, vacancy_text)
    off_family = [
        job.company
        for job in experience
        if family and family not in role_families(job.role)
    ]

    contact = _contact(master)
    title = localize_cv_wording(
        str(data.get("target_role") or base.title or "").strip(),
        locale,
    )
    summary = localize_cv_wording(str(data.get("summary") or "").strip(), locale) or base.summary
    summary = _strip_methodology(summary, _all_tools(master))
    summary = _years_phrase(summary, master, locale)
    all_unbacked: set[str] = set()
    for source in companies.values():
        all_unbacked |= _unbacked_tokens(source)
    trimmed_summary, summary_trimmed = _trim_unbacked_how(summary, all_unbacked, _all_tools(master))
    if summary_trimmed:
        weak.append({"company": "Resumen", "bullet": summary, "how": "", "trimmed": trimmed_summary})
        summary = trimmed_summary
    stack = build_stack_from_master(master, vacancy_text, overlay=overlay)
    stack_labels = _stack_labels(stack, locale)
    keywords = [
        str(item)
        for item in (vacancy_skill_keywords(master, vacancy_text, overlay) or base.keywords)
        if str(item).strip()
    ]

    # Un solo paso de idioma para todo lo visible: título, summary, cargos, bullets, skills.
    fields: dict[str, str] = {"title": title, "summary": summary}
    for i, job in enumerate(experience):
        fields[f"experience[{i}].role"] = job.role
        for j, bullet in enumerate(job.bullets):
            fields[f"experience[{i}].bullets[{j}]"] = bullet
    for name, labels in stack_labels.items():
        for k, label in enumerate(labels):
            fields[f"stack.{name}[{k}]"] = label
    for k, word in enumerate(keywords):
        fields[f"keywords[{k}]"] = word
    protected = protected_terms(master)
    fixed, language_report = _apply_language(fields, locale, protected, translator)

    experience = [
        job.model_copy(
            update={
                "role": _title_case_level(fixed[f"experience[{i}].role"]),
                "bullets": [
                    localize_cv_wording(fixed[f"experience[{i}].bullets[{j}]"], locale)
                    for j in range(len(job.bullets))
                ],
            }
        )
        for i, job in enumerate(experience)
    ]
    stack = stack.model_copy(
        update={
            name: ", ".join(fixed[f"stack.{name}[{k}]"] for k in range(len(labels)))
            for name, labels in stack_labels.items()
        }
    )
    keywords = [fixed[f"keywords[{k}]"] for k in range(len(keywords))]
    title = _title_case_level(fixed["title"])
    percents = percent_metric_values(master)
    summary = attach_percent_signs(localize_cv_wording(fixed["summary"], locale), percents)
    experience = [
        job.model_copy(
            update={
                "bullets": [attach_percent_signs(bullet, percents) for bullet in job.bullets]
            }
        )
        for job in experience
    ]

    report = {
        "title_family": family,
        "off_family_titles": off_family,
        "unverified_dates": unverified_dates,
        "rejected_claims": rejected,
        "weak_bullets": weak,
        "summary_claims": _summary_problems(summary, master),
        "language": language_report,
    }
    report["notes"] = _verification_notes(report)

    cv = CvDocument(
        id=base.id,
        label=base.label,
        keywords=keywords,
        name=str(master.get("name") or base.name),
        title=title or base.title,
        email=contact["email"] or base.email,
        phone=contact["phone"] or base.phone,
        linkedin=contact["linkedin"] or base.linkedin,
        location=contact["location"] or base.location,
        summary=summary,
        experience=experience or base.experience,
        stack=stack,
        tech_skills=stack_to_tech_skills(stack),
        education=education_line(master, locale) or base.education,
        certifications=cert_names(master, locale) or base.certifications,
        languages=language_lines(master, locale) or base.languages,
        locale=locale,
    )
    return cv, report


def result_to_cv(
    data: dict,
    base: CvDocument,
    master: dict,
    locale: str = "es",
    vacancy_text: str = "",
    translator: Optional[Translator] = None,
) -> CvDocument:
    """Igual que ``_build_cv`` pero solo devuelve el CV."""
    cv, _report = _build_cv(data, base, master, locale, vacancy_text, translator)
    return cv
