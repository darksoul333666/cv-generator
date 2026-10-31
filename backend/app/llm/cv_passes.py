"""Pasos finales sobre el CV armado: contacto, idioma, notas de verificación y redacción."""

from __future__ import annotations

import logging
import re
from typing import Callable, Optional

from ..language_guard import LanguageItem, Translator, detect_language, repair_language
from ..locale_util import localize_skill_label
from ..text_quality import ERROR, Issue, clean_text, find_issues, kind_for_path, quality_score
from .cv_roles import _FAMILY_LABEL
from .cv_claims import _job_metric_values, _labels, _mentions, _metric_values, _project_metric_problem

logger = logging.getLogger(__name__)


# (textos, locale, problemas detectados por texto) → textos corregidos, mismo orden.
Proofreader = Callable[[list[str], str, list[list[str]]], list[str]]


def _contact(master: dict) -> dict[str, str]:
    contact = master.get("contact") or {}
    return {
        "email": str(contact.get("email") or ""),
        "phone": str(contact.get("phone") or ""),
        "linkedin": str(contact.get("linkedin") or ""),
        "location": str(contact.get("location") or ""),
    }


def _stack_labels(stack, locale: str) -> dict[str, list[str]]:
    """Etiquetas del bloque de skills. Solo aplica el glosario fijo; no descarta ninguna."""
    out: dict[str, list[str]] = {}
    for name in type(stack).model_fields:
        labels = [
            localize_skill_label(piece.strip(), locale)
            for piece in str(getattr(stack, name) or "").split(",")
            if piece.strip()
        ]
        out[name] = labels
    return out


def _apply_language(
    fields: dict[str, str],
    locale: str,
    protected: list[str],
    translator: Optional[Translator],
    mixed: Optional[set[str]] = None,
) -> tuple[dict[str, str], dict]:
    """Detecta el idioma de cada texto visible y traduce solo los que no coinciden.

    ``mixed``: textos que se sabe que mezclan idiomas (p. ej. un bullet en inglés al que
    ``_fix_how`` le puso el «cómo» del perfil, que está en español). La detección los ve como
    del idioma correcto por mayoría, así que se mandan a traducir siempre.
    """
    other = "es" if locale == "en" else "en"

    def detected(text: str) -> str:
        if mixed and text in mixed:
            return other
        return detect_language(text, protected)

    items = [
        LanguageItem(path=path, text=text, detected=detected(text))
        for path, text in fields.items()
        if str(text or "").strip()
    ]
    final, report = repair_language(items, locale, translator, protected)
    merged = dict(fields)
    merged.update(final)
    return merged, report.as_dict()


def _summary_problems(summary: str, master: dict) -> list[str]:
    allowed: set[str] = set()
    for source in master.get("experience") or []:
        allowed |= _job_metric_values(source, master)
    problems = []
    unsupported = _metric_values(summary) - allowed
    if unsupported:
        problems.append(f"summary: métrica {_labels(unsupported)} sin respaldo en el perfil")
    project = _project_metric_problem(summary, master)
    if project:
        problems.append(f"summary: {project}")
    return problems


def _verification_notes(report: dict) -> list[str]:
    notes: list[str] = []
    if report.get("off_family_titles"):
        label = _FAMILY_LABEL.get(report.get("title_family") or "", report.get("title_family"))
        notes.append(
            f"Cargos sin variante {label} validada en el perfil: "
            f"{', '.join(report['off_family_titles'])}. Se dejaron sus cargos reales. Si también "
            "trabajaste con ese rol ahí, agrégalo a los cargos de esa experiencia en el perfil "
            "y regenera el CV."
        )
    for item in report.get("unverified_dates") or []:
        cands = " / ".join(item.get("candidates") or []) or "sin candidatos"
        notes.append(
            f"Fechas sin verificar en {item['company']}: hay resoluciones en conflicto ({cands}). "
            "Se omitió el periodo; resuélvelo en el perfil maestro."
        )
    for item in report.get("rejected_claims") or []:
        notes.append(f"Se descartó un bullet de {item.get('company')}: {item.get('reason')}. Texto: «{item.get('bullet')}»")
    for item in report.get("weak_bullets") or []:
        if item.get("fixed"):
            notes.append(
                f"{item['company']}: el modelo puso un «cómo» que no es el de tu perfil. Antes: «{item['bullet']}». "
                f"Ahora: «{item['fixed']}»."
            )
            continue
        if item.get("trimmed"):
            notes.append(
                f"{item['company']}: quité un «cómo» que tu perfil no respalda. Antes: «{item['bullet']}». "
                f"Ahora: «{item['trimmed']}». Complétalo en Evidencia si lo tienes."
            )
            continue
        if item.get("scope"):
            notes.append(
                f"{item['company']}: ningún bullet muestra el alcance del cargo (p. ej. «{item['scope']}»)."
            )
        else:
            notes.append(
                f"{item['company']}: el bullet «{item['bullet']}» usa una cifra sin decir cómo se logró "
                f"(según tu perfil: {item['how']})."
            )
    for problem in report.get("summary_claims") or []:
        notes.append(f"Revisar {problem}.")
    language = report.get("language") or {}
    for item in language.get("unresolved") or []:
        notes.append(
            f"Idioma: {item['path']} sigue en «{item['detected']}» (se pidió «{language.get('locale')}»; "
            f"motivo: {item['reason']}). Se conservó el texto original."
        )
    notes.extend(_quality_notes(report.get("quality") or {}))
    return notes


_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?")


def _proofread_problem(before: str, after: str, protected: list[str]) -> str:
    """Motivo para rechazar una corrección del LLM; vacío si es aceptable."""
    if not after or not after.strip():
        return "vino vacío"
    if "\n" in after.strip():
        return "trae saltos de línea"
    if sorted(_NUMBER_RE.findall(before)) != sorted(_NUMBER_RE.findall(after)):
        return "cambió una cifra"
    low_after = after.lower()
    for term in protected:
        t = str(term).strip()
        if len(t) > 1 and _mentions(t, before) and t.lower() not in low_after:
            return f"quitó «{t}»"
    ratio = len(after) / max(1, len(before))
    if ratio < 0.6 or ratio > 1.6:
        return "cambió demasiado la longitud"
    return ""


def _hints(path: str, text: str, locale: str) -> list[str]:
    kind = kind_for_path(path)
    return [i.message for i in find_issues(path, text, kind, locale)] if kind else []


def _quality_pass(
    fields: dict[str, str],
    locale: str,
    protected: list[str],
    proofreader: Optional[Proofreader],
) -> tuple[dict[str, str], dict]:
    """Redacción: arreglos seguros, revisión del LLM validada y puntaje final.

    1. ``clean_text`` en todo lo visible (palabras y frases repetidas, puntuación).
    2. Si hay corrector, una pasada sobre resumen y bullets; una segunda solo para lo que
       siga con problemas. Cada corrección se valida: mismas cifras y mismos nombres
       protegidos; si no pasa, se queda el texto anterior.
    3. Problemas que quedan y puntaje 0–10 (un error pesa 2, un aviso 0.75).
    """
    out = dict(fields)
    autofixed: list[dict] = []
    for path, text in fields.items():
        result = clean_text(text, capitalize=kind_for_path(path) is not None)
        if result.fixes:
            autofixed.append({"path": path, "before": text, "after": result.text, "fixes": result.fixes})
            out[path] = result.text

    proof = {"ran": False, "changed": [], "rejected": [], "error": ""}
    targets = [p for p in out if kind_for_path(p) in {"summary", "bullet", "project"} and out[p].strip()]
    if proofreader and targets:
        for attempt in range(2):
            if attempt == 0:
                batch = targets
            else:
                batch = [p for p in targets if _hints(p, out[p], locale)]
                if not batch:
                    break
            hints = [_hints(p, out[p], locale) for p in batch]
            try:
                revised = proofreader([out[p] for p in batch], locale, hints)
            except Exception as exc:  # noqa: BLE001 - la revisión es opcional; nunca rompe el CV
                proof["error"] = str(exc)[:300]
                logger.warning("[quality] revisión de redacción falló: %s", exc)
                break
            proof["ran"] = True
            for path, new in zip(batch, revised):
                before = out[path]
                candidate = clean_text(str(new or "")).text
                if candidate == before:
                    continue
                problem = _proofread_problem(before, candidate, protected)
                if problem:
                    proof["rejected"].append({"path": path, "before": before, "after": candidate, "reason": problem})
                    continue
                proof["changed"].append({"path": path, "before": before, "after": candidate})
                out[path] = candidate

    issues: list[Issue] = []
    for path, text in out.items():
        kind = kind_for_path(path)
        if kind:
            issues.extend(find_issues(path, text, kind, locale))
    report = {
        "score": quality_score(issues),
        "errors": sum(1 for i in issues if i.severity == ERROR),
        "warnings": sum(1 for i in issues if i.severity != ERROR),
        "issues": [i.as_dict() for i in issues],
        "autofixed": autofixed,
        "proofread": proof,
    }
    return out, report


def _quality_notes(quality: dict) -> list[str]:
    if not quality:
        return []
    notes: list[str] = []
    score = quality.get("score")
    if score is not None and (quality.get("errors") or quality.get("warnings")):
        notes.append(
            f"Redacción: {score}/10 ({quality.get('errors', 0)} errores, {quality.get('warnings', 0)} avisos). "
            "Revísalo antes de enviar el CV."
        )
    for item in quality.get("issues") or []:
        level = "Error" if item.get("severity") == ERROR else "Aviso"
        notes.append(f"{level} de redacción en {item['path']}: {item['message']}. Texto: «{item['text']}»")
    for item in (quality.get("proofread") or {}).get("rejected") or []:
        notes.append(
            f"Se descartó una corrección de redacción en {item['path']} porque {item['reason']}. "
            f"Propuesta: «{item['after']}»"
        )
    return notes
