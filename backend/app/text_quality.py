"""Calidad de redacción del CV: arreglos seguros, detección de problemas y puntaje.

Un reclutador (o un LLM que evalúa el CV) castiga mucho más un «as as» o una frase repetida
que una métrica floja: lo lee como descuido. Por eso este módulo:

1. ``clean_text`` corrige lo que se puede arreglar sin cambiar el sentido: palabras repetidas
   seguidas, elementos repetidos de una enumeración, espacios y puntuación.
2. ``find_issues`` detecta lo que no se arregla solo (primera persona, bullets sin verbo,
   paréntesis sin cerrar, frases demasiado largas) para mandarlo a la revisión del LLM o
   reportarlo.
3. ``quality_score`` convierte lo que queda en un puntaje de 0 a 10. Un error de redacción
   pesa más que un aviso de estilo.

No depende del proveedor ni de la red.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Optional

# --- Arreglos deterministas -------------------------------------------------------------------

_REPEATED_WORD = re.compile(r"\b([A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+)(?:\s+\1\b)+", re.IGNORECASE)
_LIST_JOINERS = re.compile(r"^(?:and|or|y|e|o|u)\s+", re.IGNORECASE)
_STOP = {
    "the", "and", "with", "for", "from", "into", "using", "through", "via", "of", "to", "in", "on", "a", "an",
    "de", "del", "la", "las", "el", "los", "con", "para", "por", "en", "y", "e", "o", "u", "un", "una", "al",
}
_TOKEN = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9][A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9.+#/-]*")


def _tokens(text: str) -> list[str]:
    return [t.lower().rstrip(".") for t in _TOKEN.findall(text or "")]


def _content_tokens(text: str) -> set[str]:
    return {t for t in _tokens(text) if t not in _STOP and len(t) > 1}


def fix_repeated_words(text: str) -> str:
    """«as as a Full Stack» → «as a Full Stack». No toca números («10 10» puede ser dato)."""
    return _REPEATED_WORD.sub(lambda m: m.group(1), text or "")


def _dedupe_clauses(sentence: str) -> str:
    """Quita de una enumeración los elementos que ya se dijeron antes en la misma frase.

    «…with code reviews, standards and architectural patterns, DORA metrics and SonarQube,
    standards and SonarQube.» → «…with code reviews, standards and architectural patterns,
    DORA metrics and SonarQube.» Solo considera elementos cortos (≤ 5 palabras) separados por
    coma, para no borrar una oración subordinada que comparte palabras con el inicio.
    """
    body = sentence.rstrip()
    tail = ""
    m = re.search(r"[.;:!?]+$", body)
    if m:
        body, tail = body[: m.start()], m.group(0)
    parts = body.split(", ")
    if len(parts) < 2:
        return sentence
    kept = [parts[0]]
    for part in parts[1:]:
        item = _LIST_JOINERS.sub("", part.strip())
        words = item.split()
        content = _content_tokens(item)
        earlier = _content_tokens(", ".join(kept))
        duplicate = (
            len(words) <= 5
            and content
            and content <= earlier
            and not re.search(r"\d", item)
        )
        if duplicate:
            continue
        kept.append(part)
    return ", ".join(kept) + tail


def fix_duplicate_clauses(text: str) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", text or "")
    return " ".join(_dedupe_clauses(s) for s in sentences if s)


def fix_spacing(text: str) -> str:
    out = re.sub(r"\s+", " ", text or "").strip()
    out = re.sub(r"\s+([,;:!?)])", r"\1", out)
    out = re.sub(r"\s+\.(?![A-Za-z0-9])", ".", out)  # « .» sí; « .NET» no
    out = re.sub(r"\(\s+", "(", out)
    out = re.sub(r",\s*,+", ",", out)
    out = re.sub(r"[,;:]\s*\.", ".", out)
    out = re.sub(r"(?<!\.)\.\.(?!\.)", ".", out)
    out = re.sub(r"([,;:])(?=[A-Za-zÁÉÍÓÚáéíóú])", r"\1 ", out)
    return out


def _capitalize_first(text: str) -> str:
    for i, ch in enumerate(text):
        if ch.isalpha():
            return text[:i] + ch.upper() + text[i + 1 :] if ch.islower() else text
        if not ch.isspace() and ch not in "«\"'(":
            return text
    return text


@dataclass
class CleanResult:
    text: str
    fixes: list[str] = field(default_factory=list)


_FULLSTACK_RE = re.compile(r"\bfullstack\b", re.IGNORECASE)


def clean_text(text: str, *, capitalize: bool = True) -> CleanResult:
    """Aplica todos los arreglos seguros y dice cuáles cambiaron algo."""
    original = text or ""
    fixes: list[str] = []
    out = fix_spacing(original)
    # Una sola grafía para el ATS: «Fullstack» → «Full Stack» (como en el perfil).
    step = _FULLSTACK_RE.sub("Full Stack", out)
    if step != out:
        fixes.append("«Fullstack» → «Full Stack»")
        out = step
    step = fix_repeated_words(out)
    if step != out:
        fixes.append("palabra repetida")
        out = step
    step = fix_duplicate_clauses(out)
    if step != out:
        fixes.append("elemento repetido en una enumeración")
        out = fix_spacing(step)
    if capitalize:
        step = _capitalize_first(out)
        if step != out:
            fixes.append("inicio en minúscula")
            out = step
    if out != original and not fixes:
        fixes.append("espacios o puntuación")
    return CleanResult(out, fixes)


# --- Detección ---------------------------------------------------------------------------------

ERROR = "error"
WARNING = "warning"

_FIRST_PERSON = {
    "en": re.compile(r"(?:^|[\s(])(I|I'm|I've|I'd|my|My|me|we|We|our|Our)(?=[\s,.;:)]|$)"),
    "es": re.compile(r"(?:^|[\s(])(yo|Yo|mi|Mi|mis|Mis|nosotros|Nosotros|nuestro|Nuestro|nuestra|Nuestra)(?=[\s,.;:)]|$)"),
}

_EN_IRREGULAR = {
    "built", "led", "cut", "drove", "made", "wrote", "ran", "set", "grew", "won", "took", "brought", "taught",
    "kept", "rebuilt", "shipped", "began", "chose", "found", "gave", "held", "laid", "lent", "met", "overcame",
    "oversaw", "rewrote", "sped", "spun", "split", "stood", "upheld", "undertook", "wound", "co-led", "built,",
}
_ES_IRREGULAR = {
    "reduje", "hice", "mantuve", "propuse", "introduje", "obtuve", "conduje", "dirigí", "construí", "distribuí",
    "produje", "traduje", "compuse", "dispuse", "supe", "tuve", "puse", "rehíce", "rehice", "deduje", "atraje",
}
_ES_PRETERITE = re.compile(r"^[a-záéíóúñ]+(?:é|ó|í)$", re.IGNORECASE)


def _starts_with_past_verb(text: str, locale: str) -> bool:
    words = (text or "").strip().split()
    if not words:
        return False
    first = re.sub(r"[^\w\-áéíóúñÁÉÍÓÚÑ]", "", words[0]).lower()
    if not first:
        return False
    if locale == "es":
        return first in _ES_IRREGULAR or bool(_ES_PRETERITE.match(first))
    return first in _EN_IRREGULAR or (first.endswith("ed") and len(first) > 3)


@dataclass
class Issue:
    path: str
    code: str
    severity: str
    message: str
    text: str

    def as_dict(self) -> dict:
        return {"path": self.path, "code": self.code, "severity": self.severity, "message": self.message, "text": self.text}


def find_issues(path: str, text: str, kind: str, locale: str) -> list[Issue]:
    """Problemas de redacción de un texto visible. ``kind``: summary, bullet o title."""
    issues: list[Issue] = []
    value = text or ""
    if not value.strip():
        return issues

    def add(code: str, severity: str, message: str) -> None:
        issues.append(Issue(path, code, severity, message, value))

    if _REPEATED_WORD.search(value):
        add("repeated_word", ERROR, "palabra repetida seguida")
    if fix_duplicate_clauses(value) != value:
        add("repeated_phrase", ERROR, "un elemento de la enumeración se repite")
    if value.count("(") != value.count(")"):
        add("unbalanced_parens", ERROR, "paréntesis sin cerrar")
    if re.search(r"\s{2,}|\s[,;:]|\s\.(?![A-Za-z0-9])|,,|\.\.(?!\.)", value):
        add("punctuation", ERROR, "espacios o puntuación mal puestos")
    if kind in {"summary", "bullet", "project"}:
        pattern = _FIRST_PERSON.get(locale)
        if pattern and pattern.search(value):
            add("first_person", WARNING, "usa primera persona; en un CV se omite el sujeto")
    if kind == "bullet":
        if not _starts_with_past_verb(value, locale):
            add("no_leading_verb", WARNING, "no empieza con un verbo en pasado")
        words = len(value.split())
        if words > 30:
            add("too_long", WARNING, f"bullet de {words} palabras (máximo recomendado 30)")
    if kind == "summary":
        words = len(value.split())
        if words > 90:
            add("too_long", WARNING, f"resumen de {words} palabras (máximo recomendado 90)")
    return issues


ERROR_WEIGHT = 2.0
WARNING_WEIGHT = 0.75


def quality_score(issues: Iterable[Issue | dict]) -> float:
    """10 menos 2 puntos por error de redacción y 0.75 por aviso de estilo; mínimo 0."""
    score = 10.0
    for item in issues:
        severity = item.severity if isinstance(item, Issue) else item.get("severity")
        score -= ERROR_WEIGHT if severity == ERROR else WARNING_WEIGHT
    return round(max(0.0, score), 1)


def kind_for_path(path: str) -> Optional[str]:
    if path == "summary":
        return "summary"
    if path == "title":
        return "title"
    if ".bullets[" in path:
        return "bullet"
    if path.startswith("projects[") and path.endswith(".line"):
        return "project"
    return None
