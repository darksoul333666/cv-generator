"""Empresas, cargos y familias de rol: qué cargo del maestro se muestra según la vacante."""

from __future__ import annotations

import re



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
