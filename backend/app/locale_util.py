"""Idioma de la vacante: el CV entero (secciones fijas + hechos overlay) sigue ese locale."""

from __future__ import annotations

import re
from typing import Optional

Locale = str  # "en" | "es"

_ES_HINTS = (
    "experiencia",
    "desarrollador",
    "desarrolladora",
    "requisitos",
    "conocimientos",
    "vacante",
    "puesto",
    "empresa",
    "jornada",
    "contrato",
    "habilidades",
    "responsabilidades",
    "imprescindible",
    "se solicita",
    "buscamos",
)
_EN_HINTS = (
    "experience",
    "developer",
    "requirements",
    "responsibilities",
    "engineer",
    "looking for",
    "job description",
    "must have",
    "nice to have",
    "about the role",
    "qualifications",
    "we are seeking",
)

_MONTHS_EN = {
    1: "Jan",
    2: "Feb",
    3: "Mar",
    4: "Apr",
    5: "May",
    6: "Jun",
    7: "Jul",
    8: "Aug",
    9: "Sep",
    10: "Oct",
    11: "Nov",
    12: "Dec",
}
_MONTHS_ES = {
    1: "Ene",
    2: "Feb",
    3: "Mar",
    4: "Abr",
    5: "May",
    6: "Jun",
    7: "Jul",
    8: "Ago",
    9: "Sep",
    10: "Oct",
    11: "Nov",
    12: "Dic",
}

# (en, es) keyed by a normalized form of the master name
_CERT_I18N_RAW = {
    "aws machine learning certification": (
        "AWS Machine Learning Certification",
        "Certificación en Machine Learning — AWS",
    ),
    "stripe developer certification": (
        "Stripe Developer Certification",
        "Certificación de Desarrollador Stripe",
    ),
    "ndg linux essentials": ("NDG Linux Essentials", "NDG Linux Essentials"),
    "ccna: switching and routing": (
        "CCNA: Switching and Routing",
        "CCNA: Conmutación y Enrutamiento",
    ),
    "ccna: conmutación y enrutamiento": (
        "CCNA: Switching and Routing",
        "CCNA: Conmutación y Enrutamiento",
    ),
    "it essentials: hardware and software": (
        "IT Essentials: Hardware and Software",
        "IT Essentials: Hardware and Software",
    ),
    "tercer lugar — olimpiada de programación": (
        "3rd Place — Programming Olympiad",
        "Tercer lugar — Olimpiada de Programación",
    ),
    "3rd place — programming olympiad": (
        "3rd Place — Programming Olympiad",
        "Tercer lugar — Olimpiada de Programación",
    ),
    "olimpiada de conocimiento nivel media superior — finalista": (
        "Finalist — High School Knowledge Olympiad",
        "Olimpiada de Conocimiento Nivel Media Superior — Finalista",
    ),
    "campeonato estatal de ortografía — primer lugar": (
        "1st Place — Statewide Spelling Championship",
        "Campeonato Estatal de Ortografía — Primer lugar",
    ),
    "olimpiada de conocimiento infantil — primer lugar": (
        "1st Place — Children's Knowledge Olympiad",
        "Olimpiada de Conocimiento Infantil — Primer lugar",
    ),
}


def _norm_cert(name: str) -> str:
    return " ".join(name.lower().replace("—", "-").replace("–", "-").split())


_CERT_I18N = {_norm_cert(k): v for k, v in _CERT_I18N_RAW.items()}


def detect_vacancy_locale(text: str) -> Locale:
    blob = (text or "").lower()
    if not blob.strip():
        return "es"
    es = sum(blob.count(w) for w in _ES_HINTS)
    en = sum(blob.count(w) for w in _EN_HINTS)
    if re.search(r"[áéíóúñ¿¡]", blob):
        es += 4
    if es > en:
        return "es"
    if en > es:
        return "en"
    return "es" if re.search(r"[áéíóúñ¿¡]", blob) else "en"


def _fmt_month(ym: Optional[str], locale: Locale) -> Optional[str]:
    if not ym:
        return None
    text = str(ym).strip()
    months = _MONTHS_ES if locale == "es" else _MONTHS_EN
    if len(text) >= 7 and text[4] == "-":
        try:
            year = int(text[:4])
            month = int(text[5:7])
            return f"{months[month]} {year}"
        except (ValueError, KeyError):
            return text
    return text


def format_period(
    start: Optional[str],
    end: Optional[str],
    current: bool,
    locale: Locale,
) -> str:
    present = "Actualidad" if locale == "es" else "Present"
    start_s = _fmt_month(start, locale) or (start or "")
    if current or not end:
        return f"{start_s} – {present}" if start_s else present
    end_s = _fmt_month(end, locale) or end
    if start_s and end_s:
        return f"{start_s} – {end_s}"
    return start_s or str(end_s or "")


def education_line(master: dict, locale: Locale) -> str:
    for item in master.get("education") or []:
        raw_degree = str(item.get("degree") or "")
        if "también referido" in raw_degree.lower():
            raw_degree = raw_degree.split("(")[0].strip()
        institution = str(item.get("institution") or "").strip()
        year = item.get("graduation_year") or item.get("end_date") or ""
        year_s = str(year).strip()
        if locale == "en":
            degree = (
                "Associate Degree in Multiplatform Software Development "
                "(TSU en Desarrollo de Software Multiplataforma)"
            )
        else:
            degree = raw_degree or "TSU en Desarrollo de Software Multiplataforma"
        parts = [p for p in (degree, institution) if p]
        line = " — ".join(parts)
        if year_s:
            line = f"{line} ({year_s})" if line else year_s
        if line:
            return line
    return ""


def cert_names(master: dict, locale: Locale) -> list[str]:
    out: list[str] = []
    idx = 0 if locale == "en" else 1
    for item in master.get("certifications") or []:
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        pair = _CERT_I18N.get(_norm_cert(name))
        label = pair[idx] if pair else name
        year = item.get("year")
        if year and f"({year})" not in label:
            label = f"{label} ({year})"
        out.append(label)
        # ATS reference lists all documented + claimed certs; keep order from master
    return out


_FREELANCE_TITLE_RE = re.compile(
    r"[\s,]*[—–-]\s*Freelanc(?:er|e)\b.*$|"
    r"[\s,]*\(\s*Freelanc(?:er|e)\s*\)|"
    r"\s+Freelanc(?:er|e)\s*$",
    re.IGNORECASE,
)

_FINTECH_TITLE_RE = re.compile(
    r"\s*\(\s*Fintech\s*\)|\s*[—–-]\s*Fintech\b",
    re.IGNORECASE,
)

_FINTECH_VACANCY_RE = re.compile(
    r"\bfin-?techs?\b|"
    r"\bneobanks?\b|"
    r"servicios financieros|"
    r"financial services|"
    r"sector financiero|"
    r"industria financiera|"
    r"experiencia (?:en|con) fintech",
    re.IGNORECASE,
)


def strip_freelance_from_title(position: str) -> str:
    """Quita «— Freelancer» del cargo. El tipo de contrato no va en el título."""
    text = position or ""
    prev = None
    while prev != text:
        prev = text
        text = _FREELANCE_TITLE_RE.sub("", text).strip(" ,—–-")
    return text.strip()


def vacancy_asks_fintech(vacancy_text: str) -> bool:
    """True solo si la vacante pide fintech / servicios financieros de forma explícita."""
    return bool(_FINTECH_VACANCY_RE.search(vacancy_text or ""))


def polish_experience_title(company: str, position: str, vacancy_text: str = "") -> str:
    """Títulos serios: sin freelance; (Fintech) en UffPay solo si la vacante lo pide."""
    title = strip_freelance_from_title(position)
    if "uffpay" not in (company or "").lower():
        return title
    title = _FINTECH_TITLE_RE.sub("", title).strip(" ,—–-")
    if vacancy_asks_fintech(vacancy_text) and "fintech" not in title.lower():
        title = f"{title} (Fintech)".strip()
    return title.strip()


_PERCENT_EN_RE = re.compile(
    r"(?P<n>\d+(?:[.,]\d+)?)\s*(?:percent|per\s*cent)\b",
    re.IGNORECASE,
)

# Solo contracciones/artículos donde el español lo pide. No tocar «más de 7»,
# «pasarelas de pago», «virtualización de datos», «consumo de APIs».
_ES_PHRASE_FIXES: tuple[tuple[str, str], ...] = (
    (r"\bmanejo de estado\b", "manejo del estado"),
    (r"\bgesti[oó]n de estado\b", "gestión del estado"),
    (r"\bdesarrollo de aplicaci[oó]n\b", "desarrollo de una aplicación"),
    (r"\baplicaci[oó]n de arquitectura\b", "aplicación de una arquitectura"),
    (r"\breducci[oó]n de tiempos\b", "reducción de los tiempos"),
    (r"\breducci[oó]n de errores en flujos\b", "reducción de errores en los flujos"),
    (r"\boptimizaci[oó]n de UX\b", "optimización de la UX"),
    (r"\bmejora de eficiencia de(?:l)? equipo\b", "mejora de la eficiencia del equipo"),
    (r"\bintegraci[oó]n de pasarelas de pago\b", "integración de las pasarelas de pago"),
    (r"\besquemas seguros de autenticaci[oó]n\b", "esquemas de autenticación seguros"),
)


def localize_percent_wording(text: str, locale: Locale | None = None) -> str:
    """'35 percent' → '35%' en cualquier idioma (ATS y checkers lo leen mejor)."""
    if not text:
        return text
    return _PERCENT_EN_RE.sub(r"\g<n>%", text)


def _replace_keep_cap(text: str, pattern: str, replacement: str) -> str:
    def _repl(match: re.Match[str]) -> str:
        raw = match.group(0)
        out = replacement
        if raw[:1].isupper():
            out = out[:1].upper() + out[1:]
        return out

    return re.sub(pattern, _repl, text, flags=re.IGNORECASE)


def polish_spanish_wording(text: str) -> str:
    """Artículos y contracciones naturales; no sustituye todo «de» por «del»."""
    if not text:
        return text
    out = text
    for pattern, replacement in _ES_PHRASE_FIXES:
        out = _replace_keep_cap(out, pattern, replacement)
    return out


def localize_cv_wording(text: str, locale: Locale) -> str:
    if not text:
        return text
    text = localize_percent_wording(text, locale)
    if locale == "es":
        return polish_spanish_wording(text)
    return text
