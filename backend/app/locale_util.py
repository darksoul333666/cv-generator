"""Idioma de la vacante: el CV entero (secciones fijas + hechos overlay) sigue ese locale."""

from __future__ import annotations

import re
from typing import Any, Optional

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


_TSU_DEGREE = "tsu en desarrollo de software multiplataforma"
_ING_DEGREE = "ingeniería en desarrollo y gestión de software"


_LANGUAGE_NAMES = {
    "en": {"spanish": "Spanish", "english": "English", "español": "Spanish", "espanol": "Spanish", "inglés": "English", "ingles": "English"},
    "es": {"spanish": "Español", "english": "Inglés", "español": "Español", "espanol": "Español", "inglés": "Inglés", "ingles": "Inglés"},
}


def language_lines(master: dict, locale: Locale) -> list[str]:
    """Idiomas con nivel declarado. El nivel CEFR (B2) se conserva en ambos idiomas."""
    names = _LANGUAGE_NAMES.get(locale, _LANGUAGE_NAMES["es"])
    lines: list[str] = []
    for item in master.get("languages") or []:
        if not isinstance(item, dict):
            continue
        raw_name = str(item.get("language") or "").strip()
        level = str(item.get("level") or "").strip()
        if not raw_name or not level:
            continue
        name = names.get(raw_name.lower(), raw_name)
        lines.append(f"{name} — {level}")
    return lines


def education_line(master: dict, locale: Locale) -> str:
    lines: list[str] = []
    for item in master.get("education") or []:
        if not isinstance(item, dict):
            continue
        raw_degree = str(item.get("degree") or "").strip()
        if "también referido" in raw_degree.lower():
            raw_degree = raw_degree.split("(")[0].strip()
        institution = str(item.get("institution") or "").strip()
        year = (
            item.get("graduation_year")
            or item.get("graduationYear")
            or item.get("end_date")
            or item.get("endDate")
            or ""
        )
        year_s = str(year).strip()
        degree = raw_degree
        if locale == "en" and _TSU_DEGREE in raw_degree.lower():
            degree = (
                "Associate Degree in Multiplatform Software Development "
                "(TSU en Desarrollo de Software Multiplataforma)"
            )
        elif locale == "en" and _ING_DEGREE in raw_degree.lower():
            degree = (
                "Bachelor of Engineering in Software Development and Management "
                "(Ingeniería en Desarrollo y Gestión de Software)"
            )
        parts = [p for p in (degree, institution) if p]
        line = " — ".join(parts)
        if year_s:
            line = f"{line} ({year_s})" if line else year_s
        if line:
            lines.append(line)
    return " · ".join(lines)


# Premios escolares. No aportan en una postulación senior y empujan el CV a una segunda hoja.
_SCHOOL_AWARD_RE = re.compile(
    r"olimpiada de conocimiento|knowledge olympiad|ortograf|spelling championship|"
    r"infantil|children",
    re.IGNORECASE,
)


def is_school_award(name: str) -> bool:
    return bool(_SCHOOL_AWARD_RE.search(name or ""))


def cert_names(master: dict, locale: Locale) -> list[str]:
    out: list[str] = []
    idx = 0 if locale == "en" else 1
    for item in master.get("certifications") or []:
        name = str(item.get("name") or "").strip()
        if not name or is_school_award(name):
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
        if title.endswith(")"):
            # «Full Stack (React Native + Backend)» → «… + Backend, Fintech)», sin doble paréntesis.
            title = f"{title[:-1]}, Fintech)"
        else:
            title = f"{title} (Fintech)".strip()
    return title.strip()


_PERCENT_EN_RE = re.compile(
    r"(?P<n>\d+(?:[.,]\d+)?)\s*(?:percent|per\s*cent)\b",
    re.IGNORECASE,
)
# 25.0 / 30 al final de una frase, sin unidad. El punto que sigue es el de la oración.
_BARE_NUMBER_RE = re.compile(
    r"(?<![\w.])(?P<n>\d+(?:[.,]\d+)?)(?![\d%])"
)
_UNIT_AFTER_RE = re.compile(
    r"\s+(?:a[nñ]os|years|ms|mb|gb|kb|px|segundos|seconds|minutos|minutes|horas|hours)\b",
    re.IGNORECASE,
)


def _whole_number(raw: str) -> str:
    try:
        value = float(str(raw).replace(",", "."))
    except (TypeError, ValueError):
        return str(raw)
    return str(int(value)) if value.is_integer() else str(value)


def percent_metric_values(master: dict) -> set[str]:
    """Cifras del perfil cuya unidad es percent. 7 años no entra aquí."""
    values: set[str] = set()

    def add(value: Any, unit: Any, safe: Any = None, status: Any = None) -> None:
        if value is None or str(unit or "").lower() not in {"percent", "%"}:
            return
        if safe is False or str(status or "") in {"inferred", "conflicted", "requires_validation"}:
            return
        values.add(_whole_number(value))

    for metric in master.get("metrics") or []:
        if isinstance(metric, dict):
            add(metric.get("value"), metric.get("unit"), metric.get("safeForCV"), metric.get("status"))
    for job in master.get("experience") or []:
        if not isinstance(job, dict):
            continue
        for ach in job.get("achievements") or []:
            if not isinstance(ach, dict):
                continue
            metric = ach.get("metric") or {}
            if isinstance(metric, dict):
                add(metric.get("value"), metric.get("unit"), ach.get("safeForCV"), ach.get("status"))
    return values


def attach_percent_signs(text: str, values: set[str]) -> str:
    """'errores en 25.0' → 'errores en 25%' cuando 25 es un porcentaje del perfil."""
    if not text or not values:
        return text

    def repl(match: re.Match[str]) -> str:
        raw = match.group("n")
        if _whole_number(raw) not in values:
            return match.group(0)
        after = text[match.end() :]
        if _UNIT_AFTER_RE.match(after):
            return match.group(0)
        return f"{_whole_number(raw)}%"

    return _BARE_NUMBER_RE.sub(repl, text)

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


_SKILL_PHRASES_EN = {
    "virtualización de tablas": "Table virtualization",
    "virtualizacion de tablas": "Table virtualization",
}


def prose_matches_locale(text: str, locale: Locale, protected: tuple[str, ...] = ()) -> bool:
    """True si el texto está en ``locale`` o no hay evidencia para decir lo contrario.

    Usa ``language_guard.detect_language`` (pistas de palabras funcionales y morfología,
    con nombres propios y tecnologías enmascarados). Es un *chequeo*, no un traductor:
    quien recibe False debe traducir o reportar, nunca borrar el texto.
    """
    from .language_guard import matches_locale

    return matches_locale(text or "", locale, protected)


def localize_skill_label(name: str, locale: Locale) -> str:
    key = " ".join(name.lower().split())
    if locale == "en":
        return _SKILL_PHRASES_EN.get(key, name)
    return name
