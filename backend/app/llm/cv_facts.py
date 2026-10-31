"""Hechos del maestro y bullets de respaldo: qué se puede afirmar de cada empleo."""

from __future__ import annotations

import re

from ..locale_util import localize_cv_wording
from .cv_roles import _norm, _role_fit


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
        # La cifra va entre paréntesis solo si la frase no la dice ya (p. ej. «20,000 usuarios»).
        number = re.sub(r"\D", "", own_metric.split(" ")[0]) if own_metric else ""
        if own_metric and own_metric not in desc and not (
            number and not own_metric.endswith("%") and number in re.sub(r"[,.\s]", "", desc)
        ):
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


# --- Palabras del «cómo» de un logro ----------------------------------------------------------

_HOW_STOPWORDS = {"como", "para", "mediante", "entre", "sobre", "with", "using", "through", "from", "into"}


def _plain(text: str) -> str:
    import unicodedata

    nfkd = unicodedata.normalize("NFKD", (text or "").lower())
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))


def _how_stems(detail: dict) -> set[str]:
    words = re.findall(r"[a-z0-9]+", _plain(" ".join([str(detail.get("action") or "")] + list(detail.get("technologies") or []))))
    return {w[:5] for w in words if len(w) >= 4 and w not in _HOW_STOPWORDS}


# --- Alcance del cargo (equipo, responsabilidad, liderazgo) -----------------------------------

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
