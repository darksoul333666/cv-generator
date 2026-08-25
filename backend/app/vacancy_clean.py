"""Limpia el texto de vacante: sin beneficios ni about de la empresa."""

from __future__ import annotations

import re
from typing import Optional

_EMPRESA_RE = re.compile(r"^(empresa|company)\s*:\s*(.+)$", re.IGNORECASE)
_URL_RE = re.compile(r"^(url|enlace|link)\s*:\s*(\S+)$", re.IGNORECASE)

_DROP_HEADING = re.compile(
    r"^(beneficios|benefits|perks|prestaciones|"
    r"what we offer|lo que (te )?ofrecemos|"
    r"about (the )?(company|us|our team)|"
    r"acerca de (la |nuestra )?empresa|"
    r"sobre (la empresa|nosotros|la compa[nñ][ií]a)|"
    r"qui[eé]nes somos|our (culture|values)|nuestra cultura|"
    r"equal opportunity|diversity|inclusi[oó]n)\b",
    re.IGNORECASE,
)

_KEEP_HEADING = re.compile(
    r"^(descripci[oó]n|puesto|requirements?|requisitos|"
    r"responsabilidades|responsibilities|qualifications|skills|"
    r"habilidades|experiencia|stack|tecnolog|funciones|obligaciones|"
    r"about the (role|job|position)|the role|el (puesto|rol)|"
    r"what you.?ll do|qu[eé] (har[aá]s|buscamos))\b",
    re.IGNORECASE,
)

_HEADING_TRIM = re.compile(r"[:.\s]+$")


def _is_heading(line: str, pattern: re.Pattern[str]) -> bool:
    return bool(pattern.match(_HEADING_TRIM.sub("", line.strip())))


def strip_benefits_and_about(text: str) -> str:
    """Quita bloques de beneficios / about the company del anuncio."""
    if not text:
        return ""
    out: list[str] = []
    dropping = False
    for raw in text.splitlines():
        line = raw.strip()
        if _is_heading(line, _DROP_HEADING):
            dropping = True
            continue
        if dropping and _is_heading(line, _KEEP_HEADING):
            dropping = False
        if not dropping:
            out.append(raw)
    cleaned = re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()
    return cleaned


def parse_pasted_vacancy(text: str) -> dict[str, Optional[str]]:
    """
    Separa metadatos locales (Empresa, URL) del cuerpo que sí entra al modelo.
    Esos campos no se mandan al LLM: solo se persisten en el historial.
    """
    company: Optional[str] = None
    url: Optional[str] = None
    kept: list[str] = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        m = _EMPRESA_RE.match(line)
        if m:
            company = m.group(2).strip() or None
            continue
        m = _URL_RE.match(line)
        if m:
            candidate = m.group(2).strip().rstrip(".,)")
            if candidate.lower().startswith("http"):
                url = candidate
            continue
        kept.append(raw)
    body = strip_benefits_and_about("\n".join(kept))
    return {"text": body, "company": company, "url": url}


def suggested_cv_name(person_name: str, profile_label: str) -> str:
    name = " ".join((person_name or "").split())
    profile = re.split(r"[—–]", profile_label or "", maxsplit=1)[0].strip()
    if name and profile:
        return f"{name} - {profile}"
    return name or profile or "CV"
