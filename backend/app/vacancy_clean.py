"""Limpia el texto de vacante: sin beneficios ni about de la empresa."""

from __future__ import annotations

import re
from typing import Optional

_EMPRESA_RE = re.compile(r"^(empresa|company)\s*:\s*(.+)$", re.IGNORECASE)
_URL_RE = re.compile(r"^(url|enlace|link)\s*:\s*(\S+)$", re.IGNORECASE)
_LINKEDIN_VIEW_RE = re.compile(
    r"https?://(?:www\.)?linkedin\.com/jobs/view/(\d+)",
    re.IGNORECASE,
)
_LINKEDIN_CURRENT_RE = re.compile(r"[?&]currentJobId=(\d+)", re.IGNORECASE)
_OCC_OFFER_RE = re.compile(
    r"https?://(?:www\.)?occ\.com\.mx/empleo/oferta/(\d+)",
    re.IGNORECASE,
)
_OCC_JOBID_RE = re.compile(r"[?&]jobid=(\d+)", re.IGNORECASE)
_LINKEDIN_LIST_NOISE = re.compile(
    r"^\d+\s+resultados\b|"
    r"c[oó]mo se clasifican los anuncios|"
    r"^adel[aá]ntate a solicitar|"
    r"^solicitud sencilla|"
    r"^publicado hace|"
    r"^visto\s*·|"
    r"^¿estos resultados|"
    r"^abonarse a premium|"
    r"^mira empleos donde figuras|"
    r"^reactivar premium|"
    r"linkedin corporation",
    re.IGNORECASE,
)

_DROP_HEADING = re.compile(
    r"^(beneficios|benefits|perks|prestaciones|"
    r"what we offer|lo que (te )?ofrecemos|ofrecemos|"
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


def normalize_vacancy_url(url: Optional[str]) -> Optional[str]:
    raw = (url or "").strip().rstrip(".,)")
    if not raw:
        return None
    view = _LINKEDIN_VIEW_RE.search(raw)
    if view:
        return f"https://www.linkedin.com/jobs/view/{view.group(1)}"
    current = _LINKEDIN_CURRENT_RE.search(raw)
    if current and "linkedin.com" in raw.lower():
        return f"https://www.linkedin.com/jobs/view/{current.group(1)}"
    occ_offer = _OCC_OFFER_RE.search(raw)
    if occ_offer:
        return f"https://www.occ.com.mx/empleo/oferta/{occ_offer.group(1)}"
    occ_job = _OCC_JOBID_RE.search(raw)
    if occ_job and "occ.com.mx" in raw.lower():
        return f"https://www.occ.com.mx/empleo/oferta/{occ_job.group(1)}"
    return raw


def strip_linkedin_search_chrome(text: str) -> str:
    if not text:
        return ""
    low = text.lower()
    list_like = (
        bool(re.search(r"\d+\s+resultados", low))
        or "cómo se clasifican" in low
        or "como se clasifican" in low
        or low.count("adelántate a solicitar") + low.count("adelantate a solicitar") >= 2
    )
    if list_like:
        cut = -1
        for marker in (
            "acerca del empleo",
            "about the job",
            "about this job",
            "job description",
            "descripción del empleo",
        ):
            i = low.find(marker)
            if i >= 0 and (cut < 0 or i < cut):
                cut = i
        if cut >= 0:
            header: list[str] = []
            for line in text.splitlines()[:25]:
                s = line.strip()
                if _EMPRESA_RE.match(s) or _URL_RE.match(s):
                    header.append(line)
                elif not header and s and len(s) < 160 and not _LINKEDIN_LIST_NOISE.search(s):
                    header.append(line)
                    break
            body = text[cut:]
            return re.sub(r"\n{3,}", "\n\n", "\n\n".join(["\n".join(header), body])).strip()
    kept = [ln for ln in text.splitlines() if not _LINKEDIN_LIST_NOISE.search(ln.strip())]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip()


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
                url = normalize_vacancy_url(candidate)
            continue
        kept.append(raw)
    body = strip_linkedin_search_chrome(strip_benefits_and_about("\n".join(kept)))
    return {"text": body, "company": company, "url": url}


def suggested_cv_name(person_name: str, profile_title: str) -> str:
    name = " ".join((person_name or "").split())
    title = " ".join((profile_title or "").split())
    if name and title:
        return f"{name} - {title}"
    return name or title or "CV"
