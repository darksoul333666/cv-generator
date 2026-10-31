"""Años de experiencia: los que dan las fechas visibles y cómo se dicen en el resumen."""

from __future__ import annotations

import re
from typing import Any, Optional



def _ym_index(ym: Any) -> Optional[int]:
    m = re.match(r"^(\d{4})-(\d{2})", str(ym or ""))
    if not m:
        return None
    return int(m.group(1)) * 12 + int(m.group(2)) - 1


def _today_ym() -> str:
    from datetime import date

    today = date.today()
    return f"{today.year:04d}-{today.month:02d}"


def shown_years(sources: list[dict], today: Optional[str] = None) -> Optional[float]:
    """Años de experiencia que un lector puede comprobar con las fechas impresas en el CV.

    Une los meses de los empleos visibles (los simultáneos cuentan una vez). Si el CV dice
    «7+» pero las fechas visibles empiezan en 2020, el reclutador hace la cuenta y desconfía.
    """
    months: set[int] = set()
    now = _ym_index(today or _today_ym())
    for source in sources:
        start = _ym_index(source.get("start_date"))
        if start is None:
            continue
        end = now if source.get("current") or not source.get("end_date") else _ym_index(source.get("end_date"))
        if end is None or end < start:
            continue
        months.update(range(start, end + 1))
    if not months:
        return None
    return round(len(months) / 12, 1)


def _years_value(master: dict, shown: Optional[float]) -> Optional[float]:
    """El menor entre lo validado en el perfil y lo que se puede comprobar en el CV."""
    values = []
    for raw in (master.get("years_experience"), shown):
        try:
            if raw is not None:
                values.append(float(raw))
        except (TypeError, ValueError):
            continue
    return min(values) if values else None


_EN_YEARS = re.compile(
    r"^\s*(?:more than\s+|over\s+)?(\d+)\+?\s+years?\b(\s+of\s+experience\b)?(\s+(?:as|of)\b)?",
    re.IGNORECASE,
)


_ES_YEARS = re.compile(
    r"^\s*(?:m[aá]s de\s+)?(\d+)\+?\s+a[nñ]os\b(\s+de\s+experiencia\b)?(\s+(?:como|de|en)\b)?",
    re.IGNORECASE,
)


_YEARS_ANYWHERE = {
    "en": re.compile(r"\b(\d+)\+?(\s+years?)\b", re.IGNORECASE),
    "es": re.compile(r"\b(?:m[aá]s de\s+)?(\d+)\+?(\s+a[nñ]os)\b", re.IGNORECASE),
}


def _years_phrase(summary: str, master: dict, locale: str, shown: Optional[float] = None) -> str:
    """Normaliza los años del resumen.

    - «7 años Senior Full Stack…» → «Más de 6 años de experiencia como Senior…».
    - «7+ years as a Full Stack…» → «6+ years of experience as a Full Stack…» (sin «as as»).
    - Un número que no coincide con las fechas visibles se reemplaza por el calculado.
    """
    years = _years_value(master, shown)
    if years is None:
        return summary
    whole = int(years)
    plus = years > whole
    if whole < 1:
        return summary
    if locale == "es":
        lead = f"Más de {whole} años" if plus else f"{whole} años"
        m = _ES_YEARS.match(summary)
        if m:
            rest = summary[m.end():].lstrip()
            connector = (m.group(3) or "").strip().lower()
            if m.group(2):
                joint = f" {connector} " if connector else " "
                return f"{lead} de experiencia{joint}{rest}".rstrip()
            if connector in {"de", "en"}:
                return f"{lead} de experiencia {connector} {rest}".rstrip()
            if re.match(r"^\w+(?:ando|iendo)\b", rest, re.IGNORECASE):
                return f"{lead} de experiencia {rest}".rstrip()
            return f"{lead} de experiencia como {rest}".rstrip()
        pattern = _YEARS_ANYWHERE["es"]
        return pattern.sub(lambda mm: f"{'más de ' if plus else ''}{whole}{mm.group(2)}", summary, count=1)
    lead = f"{whole}{'+' if plus else ''} years"
    m = _EN_YEARS.match(summary)
    if m:
        rest = summary[m.end():].lstrip()
        connector = (m.group(3) or "").strip().lower()
        if m.group(2):
            joint = f" {connector} " if connector else " "
            return f"{lead} of experience{joint}{rest}".rstrip()
        if connector == "of":
            return f"{lead} of {rest}".rstrip()
        if re.match(r"^(?:\w+ing|in|with|across|building)\b", rest, re.IGNORECASE):
            return f"{lead} of experience {rest}".rstrip()
        return f"{lead} of experience as {rest}".rstrip()
    pattern = _YEARS_ANYWHERE["en"]
    return pattern.sub(lambda mm: f"{whole}{'+' if plus else ''}{mm.group(2)}", summary, count=1)


_SENIOR_RE = re.compile(r"\b(senior|junior|semi-senior)\b")


def _title_case_level(title: str) -> str:
    """«Ingeniero Full Stack senior» → «Ingeniero Full Stack Senior» (consistente en todo el CV)."""
    return _SENIOR_RE.sub(lambda m: m.group(1).capitalize(), title or "")
