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


def freelance_suffix(employment_type: Optional[str], locale: Locale) -> str:
    kind = str(employment_type or "").strip().lower()
    if kind not in {"freelance", "freelancer"}:
        return ""
    return " — Freelance" if locale == "es" else " — Freelancer"
