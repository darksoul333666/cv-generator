"""Bloque de skills del CV: sale del perfil maestro, ordenado por la vacante."""

from __future__ import annotations

import re
from typing import Iterable, List, Optional

from .models import StackBlock, TechSkills

_PER_ROW = 10

_STYLING = {
    "css3",
    "css",
    "scss",
    "sass",
    "less",
    "tailwindcss",
    "tailwind",
    "nativewind",
    "bootstrap",
    "material ui",
    "angular material",
    "styled-components",
    "emotion",
}

_STATE = {
    "redux",
    "ngrx",
    "zustand",
    "mobx",
    "rxjs",
    "react query",
    "tanstack query",
    "signals",
}

_QUALITY = {
    "sonarqube",
    "eslint",
    "prettier",
    "code reviews",
}

_FRONTEND_LANGS = {
    "typescript",
    "javascript",
    "javascript (es6+)",
    "html5",
    "html",
}

_BACKEND_LANGS = {"sql", "php", "java"}

_FRONTEND_FRAMEWORKS = {"react native", "ionic"}

_SKIP_UNLESS_HIT = {
    "ngx-translate",
    "ssr",
    "lazy loading",
    "virtualización de tablas",
    "responsive design",
    "signals",
    "sql optimization",
    "query performance tuning",
    "database design",
    "indexing",
    "transactions",
    "monitoring & logging",
    "unit testing",
    "microservices architecture",
    "event-driven architecture",
    "php",
    "java",
    "sql",
    "ionic",
}

_COMPOUNDS = {
    "angular material",
    "react native",
    "clean architecture",
    "rest apis",
    "github actions",
    "material ui",
    "express.js",
    "next.js",
    "node.js",
    "design patterns",
}

_DEFAULT_ALIASES: dict[str, list[str]] = {
    "Next.js": ["Next", "NEXT", "Next Js", "NextJS", "Nextjs"],
    "Node.js": ["Node", "NodeJS", "Node Js"],
    "PostgreSQL": ["Postgres", "PostgresSQL"],
    "MongoDB": ["Mongo", "Mongo DB"],
    "React Native": ["RN", "ReactNative"],
    "JavaScript": ["JS", "Javascript"],
    "JavaScript (ES6+)": ["JS", "Javascript", "JavaScript", "ES6"],
    "TypeScript": ["TS"],
    "Express.js": ["Express", "ExpressJS"],
    "NestJS": ["Nest", "Nest.js"],
    "Angular": ["AngularJS"],
    "GitHub Actions": ["Github Actions", "GH Actions"],
    "REST APIs": ["REST", "REST API", "APIs REST", "API REST"],
}


def _norm(text: str) -> str:
    return " ".join(str(text or "").lower().split())


def _compact(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", _norm(text))


def _appears(needle: str, haystack: str) -> bool:
    n = _norm(needle)
    if not n or not haystack:
        return False
    # JS/TS/RN no deben matchear el sufijo de next.js / react.js
    if len(n) <= 3:
        return bool(re.search(rf"(?<![a-z0-9.]){re.escape(n)}(?![a-z0-9])", haystack))
    if len(n) <= 4 or (" " not in n and "." not in n):
        return bool(re.search(rf"(?<![a-z0-9]){re.escape(n)}(?![a-z0-9])", haystack))
    if n in haystack:
        return True
    c = _compact(n)
    return len(c) >= 5 and c in _compact(haystack)


def _alias_index(master: dict) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {k: list(v) for k, v in _DEFAULT_ALIASES.items()}
    raw = master.get("skill_aliases") or master.get("skillAliases") or {}
    if isinstance(raw, dict):
        for key, val in raw.items():
            if isinstance(val, dict):
                canon = str(val.get("canonical") or key).strip()
                aliases = [str(a).strip() for a in (val.get("aliases") or []) if str(a).strip()]
            elif isinstance(val, list):
                canon, aliases = str(key).strip(), [str(a).strip() for a in val if str(a).strip()]
            else:
                continue
            if not canon:
                continue
            bucket = out.setdefault(canon, [])
            for alias in aliases:
                if alias not in bucket:
                    bucket.append(alias)
    return out


def _needles(name: str, aliases: dict[str, list[str]]) -> list[str]:
    found = [name, *aliases.get(name, [])]
    # JavaScript (ES6+) should also match JavaScript aliases
    if name.lower().startswith("javascript"):
        found.extend(aliases.get("JavaScript") or [])
    out: list[str] = []
    seen: set[str] = set()
    for item in found:
        key = _norm(item)
        if key and key not in seen:
            seen.add(key)
            out.append(item)
    return out


def _in_vacancy(name: str, vacancy: str, aliases: dict[str, list[str]]) -> bool:
    return any(_appears(n, vacancy) for n in _needles(name, aliases))


def _display_name(
    name: str, vacancy: str, aliases: dict[str, list[str]], original: str = ""
) -> str:
    if not vacancy:
        return name
    if _appears(name, vacancy):
        return name
    hits = [
        alias
        for alias in aliases.get(name, [])
        if _appears(alias, vacancy) and _norm(alias) != _norm(name)
    ]
    if not hits:
        return name
    for alias in hits:
        if original and alias in original:
            return f"{name} ({alias})"
    hits.sort(key=lambda a: -len(a))
    return f"{name} ({hits[0]})"


def _is_duplicate_version(name: str, kept_norms: set[str]) -> bool:
    """Evita 'Angular' y 'Angular (14–20)' a la vez."""
    base = re.sub(r"\s*\([^)]*\)\s*", " ", name).strip()
    if _norm(base) != _norm(name) and _norm(base) in kept_norms:
        return True
    return False


def _is_technique(name: str) -> bool:
    words = _norm(name).split()
    if _norm(name) in _COMPOUNDS:
        return False
    if len(words) >= 3:
        return True
    return _norm(name) in {
        "lazy loading",
        "ssr",
        "responsive design",
        "virtualización de tablas",
        "unit testing",
        "monitoring & logging",
    }


def _category_for(name: str, source_cat: str) -> str:
    key = _norm(name)
    if key in _QUALITY:
        return "quality"
    if key in _STYLING or source_cat in {"styling"}:
        return "styling"
    if key in _STATE:
        return "state"
    if key in _FRONTEND_FRAMEWORKS:
        return "frontend"
    if source_cat == "languages":
        if key in _FRONTEND_LANGS:
            return "frontend"
        if key in _BACKEND_LANGS:
            return "backend"
        return "frontend"
    if source_cat in {"frontend"}:
        return "frontend"
    if source_cat in {"backend", "databases", "payments"}:
        return "backend"
    if source_cat == "mobile":
        return "mobile"
    if source_cat in {"cloud", "devops"}:
        if key in _QUALITY:
            return "quality"
        return "cloud"
    if source_cat == "architecture":
        return "architecture"
    if source_cat == "testing":
        return "testing"
    if source_cat in {"softSkills", "security", "ai"}:
        return ""
    return "frontend"


def _collect_by_row(master: dict) -> dict[str, list[str]]:
    cats = master.get("skills") or {}
    rows: dict[str, list[str]] = {
        "frontend": [],
        "styling": [],
        "backend": [],
        "state": [],
        "cloud": [],
        "mobile": [],
        "architecture": [],
        "testing": [],
        "quality": [],
    }
    seen: set[str] = set()
    if not isinstance(cats, dict):
        return rows
    for source_cat, values in cats.items():
        if not isinstance(values, list):
            continue
        for raw in values:
            name = str(raw).strip()
            key = _norm(name)
            if not name or key in seen:
                continue
            if _is_duplicate_version(name, seen):
                continue
            row = _category_for(name, str(source_cat))
            if row not in rows:
                continue
            seen.add(key)
            rows[row].append(name)
    return rows


def _sort_row(
    names: list[str],
    vacancy: str,
    aliases: dict[str, list[str]],
    cap: bool = True,
) -> list[str]:
    matched: list[str] = []
    rest: list[str] = []
    for name in names:
        skip = _is_technique(name) or _norm(name) in _SKIP_UNLESS_HIT
        hit = _in_vacancy(name, vacancy, aliases)
        if skip and not hit:
            continue
        if hit:
            matched.append(name)
        else:
            rest.append(name)
    picked = matched + rest
    if cap and len(picked) > _PER_ROW:
        picked = picked[: max(_PER_ROW, len(matched))]
    return picked


def _fold_aws(names: list[str], vacancy: str) -> list[str]:
    services: list[str] = []
    rest: list[str] = []
    saw_aws = False
    for name in names:
        if re.match(r"^aws\b", name, flags=re.I):
            saw_aws = True
            svc = re.sub(r"^aws\s+", "", name, flags=re.I).strip()
            if svc and _norm(svc) not in {"aws"}:
                services.append(svc)
            continue
        if _norm(name) == "aws":
            saw_aws = True
            continue
        rest.append(name)
    if not saw_aws:
        return names
    uniq: list[str] = []
    seen: set[str] = set()
    for svc in services:
        key = _norm(svc)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(svc)
    uniq.sort(key=lambda s: (0 if _appears(s, vacancy) else 1))
    core = ["S3", "EC2", "Cognito", "IAM", "CodePipeline"]
    picked: list[str] = []
    seen_svc: set[str] = set()
    for svc in uniq:
        if _appears(svc, vacancy) or _norm(svc) in {_norm(c) for c in core}:
            key = _norm(svc)
            if key in seen_svc:
                continue
            seen_svc.add(key)
            picked.append(svc)
    if not picked:
        picked = uniq[:5]
    label = f"AWS ({', '.join(picked)})" if picked else "AWS"
    return [label, *rest]


def _join(
    names: Iterable[str], vacancy: str, aliases: dict[str, list[str]], original: str = ""
) -> str:
    labeled = [_display_name(n, vacancy, aliases, original) for n in names]
    return ", ".join(labeled)


def build_stack_from_master(master: dict, vacancy_text: str = "") -> StackBlock:
    vacancy = _norm(vacancy_text)
    original = vacancy_text or ""
    aliases = _alias_index(master)
    rows = _collect_by_row(master)
    frontend = _sort_row(rows["frontend"], vacancy, aliases)
    styling = _sort_row(rows["styling"], vacancy, aliases)
    backend = _sort_row(rows["backend"], vacancy, aliases)
    state = _sort_row(rows["state"], vacancy, aliases)
    cloud = _fold_aws(
        _sort_row(rows["cloud"], vacancy, aliases, cap=False), vacancy
    )[:_PER_ROW]
    mobile = _sort_row(rows["mobile"], vacancy, aliases)
    architecture = _sort_row(rows["architecture"], vacancy, aliases)
    testing = _sort_row(rows["testing"], vacancy, aliases)
    quality = _sort_row(rows["quality"], vacancy, aliases)
    return StackBlock(
        frontend=_join(frontend, vacancy, aliases, original),
        styling=_join(styling, vacancy, aliases, original),
        backend=_join(backend, vacancy, aliases, original),
        state=_join(state, vacancy, aliases, original),
        cloud=_join(cloud, vacancy, aliases, original),
        mobile=_join(mobile, vacancy, aliases, original),
        architecture=_join(architecture, vacancy, aliases, original),
        testing=_join(testing, vacancy, aliases, original),
        quality=_join(quality, vacancy, aliases, original),
    )


def stack_to_tech_skills(stack: StackBlock) -> TechSkills:
    def parts(s: str) -> List[str]:
        return [p.strip() for p in re.split(r",(?![^()]*\))", s or "") if p.strip()]

    return TechSkills(
        front=parts(stack.frontend) + parts(stack.styling) + parts(stack.state),
        back=parts(stack.backend),
        ux=[],
        test=parts(stack.testing) + parts(stack.quality),
    )


def vacancy_skill_keywords(
    master: dict, vacancy_text: str, extra: Optional[List[str]] = None
) -> List[str]:
    vacancy = _norm(vacancy_text)
    aliases = _alias_index(master)
    out: list[str] = []
    seen: set[str] = set()
    inventory = master.get("skill_inventory") or []
    if not inventory:
        cats = master.get("skills") or {}
        inventory = []
        for values in cats.values() if isinstance(cats, dict) else []:
            if isinstance(values, list):
                inventory.extend(str(x).strip() for x in values if str(x).strip())
    for name in inventory:
        if _in_vacancy(name, vacancy, aliases):
            key = _norm(name)
            if key not in seen:
                seen.add(key)
                out.append(name)
    for raw in extra or []:
        name = str(raw).strip()
        key = _norm(name)
        if not name or key in seen:
            continue
        if any(_norm(x) == key or _compact(x) == _compact(name) for x in inventory):
            seen.add(key)
            out.append(name)
    return out[:15]
