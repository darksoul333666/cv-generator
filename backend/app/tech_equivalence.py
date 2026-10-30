"""Equivalencias de stack: qué de tu experiencia real se parece a lo que pide la vacante.

Sirve para dos cosas, sin cambiar ningún hecho:

* ordenar proyectos y pedirle al modelo que destaque la experiencia más cercana;
* permitir que un bullet nombre la tecnología de la vacante **junto** a la real, como
  equivalencia («APIs modulares con NestJS, patrones de ASP.NET Core»). Un bullet que dice
  que algo se hizo con la tecnología de la vacante, sin la real al lado, se sigue descartando.

La tabla por defecto se puede ampliar con ``techEquivalences`` en el perfil maestro:
``[{"vacancy": [".NET", "C#"], "yours": ["NestJS"], "shared": "…"}]``.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

DEFAULT_EQUIVALENCES: list[dict[str, Any]] = [
    {
        "vacancy": [".NET", "ASP.NET", "ASP.NET Core", "C#", "Entity Framework", "EF Core"],
        "yours": ["NestJS", "Node.js", "Express.js", "AdonisJS", "Prisma"],
        "shared": "APIs REST modulares, inyección de dependencias, middleware, ORM y capas limpias",
    },
    {
        "vacancy": ["Java", "Spring", "Spring Boot", "Hibernate"],
        "yours": ["NestJS", "Node.js", "Express.js", "Prisma"],
        "shared": "APIs REST con controladores, servicios e inyección de dependencias; ORM",
    },
    {
        "vacancy": ["Django", "FastAPI", "Flask"],
        "yours": ["NestJS", "Express.js", "Node.js", "Python"],
        "shared": "APIs REST, validación de datos y ORM",
    },
    {
        "vacancy": ["Go", "Golang"],
        "yours": ["Node.js", "NestJS"],
        "shared": "servicios backend y APIs REST",
    },
    {
        "vacancy": ["Vue", "Vue.js", "Nuxt", "Svelte", "SvelteKit"],
        "yours": ["React", "Next.js", "Angular"],
        "shared": "SPA por componentes, estado reactivo y SSR",
    },
    {
        "vacancy": ["Flutter", "Kotlin", "Swift", "SwiftUI", "Jetpack Compose"],
        "yours": ["React Native", "Ionic"],
        "shared": "apps móviles iOS/Android, publicación en tiendas y pagos en app",
    },
    {
        "vacancy": ["Azure", "GCP", "Google Cloud"],
        "yours": ["AWS", "AWS Lambda", "AWS S3", "AWS Amplify", "AWS CloudWatch"],
        "shared": "cómputo serverless, almacenamiento, autenticación y monitoreo en la nube",
    },
    {
        "vacancy": ["Kubernetes", "K8s", "ECS", "EKS"],
        "yours": ["Docker"],
        "shared": "contenedores y despliegues",
    },
    {
        "vacancy": ["Jenkins", "GitLab CI", "CircleCI", "Azure DevOps"],
        "yours": ["GitHub Actions", "Bitrise", "CI/CD"],
        "shared": "pipelines de CI/CD",
    },
    {
        "vacancy": ["GraphQL", "gRPC"],
        "yours": ["REST APIs", "NestJS"],
        "shared": "diseño de APIs y contratos entre frontend y backend",
    },
    {
        "vacancy": ["SQL Server", "Oracle", "MariaDB"],
        "yours": ["PostgreSQL", "MySQL"],
        "shared": "bases de datos relacionales y SQL",
    },
    {
        "vacancy": ["Cypress", "Playwright", "Selenium"],
        "yours": ["Jest", "E2E"],
        "shared": "pruebas automatizadas",
    },
    {
        "vacancy": ["Datadog", "New Relic", "Grafana", "Prometheus"],
        "yours": ["Sentry", "AWS CloudWatch", "CloudWatch"],
        "shared": "monitoreo y observabilidad en producción",
    },
]

EQUIVALENCE_MARKERS = re.compile(
    r"equivalent|equivalente|al estilo|estilo de|similar|análog|analog|comparable|"
    r"patrones de|patterns|transferible|transferable|akin",
    re.IGNORECASE,
)


def _mentions(term: str, text: str) -> bool:
    return bool(term) and bool(
        re.search(rf"(?<![\w.#+]){re.escape(term)}(?![\w#+])", text or "", flags=re.IGNORECASE)
    )


def equivalence_table(master: dict) -> list[dict[str, Any]]:
    extra = master.get("tech_equivalences") or master.get("techEquivalences") or []
    rows = [dict(r) for r in DEFAULT_EQUIVALENCES]
    for row in extra if isinstance(extra, list) else []:
        if isinstance(row, dict) and row.get("vacancy") and row.get("yours"):
            rows.append(
                {
                    "vacancy": [str(v) for v in row["vacancy"]],
                    "yours": [str(v) for v in row["yours"]],
                    "shared": str(row.get("shared") or ""),
                }
            )
    return rows


def _your_techs(master: dict) -> list[str]:
    techs: list[str] = []
    for item in list(master.get("experience") or []) + list(master.get("projects") or []):
        for tech in item.get("technologies") or []:
            techs.append(str(tech))
    techs.extend(str(s) for s in master.get("skill_inventory") or master.get("skills") or [] if isinstance(s, str))
    return techs


def _have(name: str, techs: Iterable[str]) -> bool:
    key = name.lower()
    return any(key == t.lower() or t.lower().startswith(key + " ") for t in techs)


def equivalents_for_vacancy(vacancy_text: str, master: dict) -> list[dict[str, Any]]:
    """Tecnologías que pide la vacante y no tienes, con lo tuyo que más se parece."""
    mine = _your_techs(master)
    out: list[dict[str, Any]] = []
    for row in equivalence_table(master):
        asked = [v for v in row["vacancy"] if _mentions(v, vacancy_text) and not _have(v, mine)]
        if not asked:
            continue
        yours = [y for y in row["yours"] if _have(y, mine)]
        if not yours:
            continue
        out.append({"vacancy_tech": asked, "your_experience": yours, "shared": row.get("shared") or ""})
    return out


def equivalents_of(term: str, master: dict) -> list[str]:
    """Tus tecnologías equivalentes a ``term`` (vacío si no hay fila)."""
    mine = _your_techs(master)
    out: list[str] = []
    for row in equivalence_table(master):
        if any(term.lower() == v.lower() for v in row["vacancy"]):
            out.extend(y for y in row["yours"] if _have(y, mine) and y not in out)
    return out


def framed_as_equivalent(bullet: str, term: str, allowed_real: Iterable[str], master: dict) -> bool:
    """True si el bullet nombra ``term`` como equivalencia de una tecnología real permitida."""
    if not EQUIVALENCE_MARKERS.search(bullet or ""):
        return False
    real = set(t.lower() for t in allowed_real)
    return any(eq.lower() in real and _mentions(eq, bullet) for eq in equivalents_of(term, master))


def project_relevance(project: dict, vacancy_text: str, equivalents: list[dict[str, Any]]) -> int:
    """Cuántas tecnologías del proyecto pide la vacante (directo o por equivalencia)."""
    wanted = {y.lower() for row in equivalents for y in row["your_experience"]}
    score = 0
    for tech in project.get("technologies") or []:
        name = str(tech)
        if _mentions(name, vacancy_text):
            score += 2
        elif name.lower() in wanted or any(name.lower().startswith(w + " ") for w in wanted):
            score += 1
    return score
