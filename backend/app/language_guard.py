"""Detección de idioma para prosa corta de CV y reparación por traducción validada.

Cómo decide
-----------
``detect_language`` cuenta pistas de alta precisión, no keywords temáticas:

* palabras funcionales que solo existen en un idioma (es: «de», «con», «para», «los»;
  en: «the», «with», «and», «using»);
* verbos de CV y títulos de puesto inequívocos (en: «built», «developer»;
  es: «desarrollé», «desarrollador»);
* morfología: acentos/ñ en palabras en minúscula y sufijos «-ción»/«-mente» (es),
  «-tion» (en; el español nunca termina en «tion»).

Antes de contar se enmascaran los términos protegidos (empresas, proyectos, tecnologías
y skills del perfil maestro) y las palabras con mayúscula a mitad de frase, para que
«Doña Tota», «Tecnológico de Monterrey» o «Angular Material» no voten. Anglicismos de
oficio («features», «dashboards», «testing», «deploy») no están en ninguna lista y por lo
tanto son neutrales.

Resultado: ``"en"``, ``"es"``, ``"mixed"`` o ``"unknown"``. ``unknown`` significa que no hay
evidencia suficiente (p. ej. «Angular, NgRx, RxJS» o «Testing unitario»): se conserva tal
cual, nunca se borra.

Limitaciones
------------
Es una heurística determinista, no un clasificador estadístico ni un traductor:

* solo distingue inglés y español; otro idioma sale como ``unknown``;
* una frase de 1–2 palabras sin pistas queda ``unknown`` aunque un humano la ubique;
* nombres propios en minúscula que no estén en el perfil pueden votar por error;
* no evalúa calidad ni fidelidad semántica de una traducción. Para eso
  ``repair_language`` exige que la traducción conserve números, porcentajes y términos
  protegidos, y que su longitud sea comparable al original; si no, reintenta una vez y, al
  final, conserva el original y lo reporta. Un error del proveedor (red, cuota) no se
  reintenta. Nunca borra contenido ni lo cambia por un texto genérico.
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Callable, Iterable, Optional

logger = logging.getLogger(__name__)

Translator = Callable[[list[str], str], list[str]]

SUPPORTED = ("en", "es")

_ES_WORDS = frozenset(
    """
    de del la las el los y e o con para por en un una unos unas que se su sus al
    mediante desde hasta sobre entre como más menos sin según durante cada este esta
    estos estas lo le les muy también donde cuando años año nuevo nueva nuevos nuevas
    equipo equipos aplicación aplicaciones desarrollo diseño gestión mejora mejoras
    reducción integración optimización manejo uso clientes cliente tiempos tiempo
    flujos pagos móvil móviles plataforma plataformas creación implementación
    """.split()
)
_EN_WORDS = frozenset(
    """
    the and of to with for in on by from using through across into an is are was were
    that this these those its their our which while within over under as at or it be
    has have had more than years year new team teams application applications development
    design management improvement reduction integration optimization handling use usage
    clients client times time flows payments mobile platform platforms creation
    implementation
    """.split()
)
_EN_VERBS = frozenset(
    """
    built build builds led lead leads developed develop develops designed design implemented
    implement reduced reduce improved improve delivered deliver integrated integrate shipped
    ship created create managed manage optimized optimize migrated migrate maintained
    maintain defined define launched launch automated automate collaborated collaborate
    owned own drove drive architected wrote write mentored mentor enabled enable increased
    increase cut boosted boost streamlined streamline
    """.split()
)
_ES_VERBS = frozenset(
    """
    desarrollé diseñé implementé lideré reduje mejoré integré entregué creé gestioné optimicé
    migré mantuve definí lancé automaticé colaboré construí escribí
    desarrollo desarrolla desarrollar implementa implementar lidera liderar reduce reducir
    mejora mejorar integra integrar crea crear gestiona gestionar optimiza optimizar
    """.split()
)
_EN_TITLES = frozenset(
    "developer developers engineer engineers leader manager architect consultant specialist".split()
)
_ES_TITLES = frozenset(
    """
    desarrollador desarrolladora desarrolladores ingeniero ingeniera líder lider arquitecto
    arquitecta gerente consultor consultora especialista
    """.split()
)

_WORD_RE = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ][A-Za-zÁÉÍÓÚÜÑáéíóúüñ'’-]*")
_ACCENT_RE = re.compile(r"[áéíóúñ]")
_SENTENCE_END_RE = re.compile(r"[.!?;:•\n]\s*$")
_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?")


def _mask_protected(text: str, protected: Iterable[str]) -> str:
    out = text
    for term in sorted({t for t in protected if t and len(t) >= 2}, key=len, reverse=True):
        out = re.sub(
            rf"(?<![\wÁÉÍÓÚÜÑáéíóúüñ]){re.escape(term)}(?![\wÁÉÍÓÚÜÑáéíóúüñ])",
            " ",
            out,
            flags=re.IGNORECASE,
        )
    return out


@dataclass
class LanguageScore:
    es: int = 0
    en: int = 0

    @property
    def total(self) -> int:
        return self.es + self.en


def score_language(text: str, protected: Iterable[str] = ()) -> LanguageScore:
    score = LanguageScore()
    masked = _mask_protected(text or "", protected)
    for match in _WORD_RE.finditer(masked):
        raw = match.group(0).strip("'’-")
        if not raw:
            continue
        before = masked[: match.start()].rstrip()
        sentence_start = not before or bool(_SENTENCE_END_RE.search(before)) or before.endswith(("(", "—", "–", "-", ","))
        word = raw.lower()
        # Los títulos de puesto van en Title Case («Senior Frontend Developer»): votan igual.
        if word in _EN_TITLES:
            score.en += 1
            continue
        if word in _ES_TITLES:
            score.es += 1
            continue
        # Mayúscula a mitad de frase: nombre propio (Doña Tota, Viva Aerobús). No vota.
        if raw[0].isupper() and not sentence_start:
            continue
        # Siglas y tokens tipo SDK/UX/AWS no son prosa.
        if raw.isupper() and len(raw) > 1:
            continue
        if word in _ES_WORDS or word in _ES_VERBS:
            score.es += 1
            continue
        if word in _EN_WORDS or word in _EN_VERBS:
            score.en += 1
            continue
        if _ACCENT_RE.search(word):
            score.es += 1
        elif len(word) > 5 and (word.endswith("ción") or word.endswith("ciones") or word.endswith("mente")):
            score.es += 1
        elif len(word) > 5 and (word.endswith("tion") or word.endswith("tions")) and "stion" not in word:
            score.en += 1
    return score


def detect_language(text: str, protected: Iterable[str] = ()) -> str:
    """``en`` | ``es`` | ``mixed`` | ``unknown``. Ver limitaciones en el docstring del módulo."""
    s = score_language(text, protected)
    if s.total == 0:
        return "unknown"
    if s.es and s.en:
        major, minor = max(s.es, s.en), min(s.es, s.en)
        # Una pista suelta del otro idioma en una frase larga no la vuelve mixta.
        if minor == 1 and major >= 4:
            return "es" if s.es > s.en else "en"
        return "mixed"
    return "es" if s.es else "en"


def matches_locale(text: str, locale: str, protected: Iterable[str] = ()) -> bool:
    """True si el texto está en ``locale`` o no hay evidencia suficiente para decir que no."""
    if locale not in SUPPORTED:
        return True
    detected = detect_language(text, protected)
    return detected in {locale, "unknown"}


# --- Invariantes que una traducción debe conservar ---------------------------------------


def _numbers(text: str) -> Counter:
    """Multiconjunto: «2021 a 2022 (Ene 2021…)» exige las dos apariciones de 2021."""
    return Counter(n.replace(",", ".") for n in _NUMBER_RE.findall(text or ""))


def protected_in(text: str, protected: Iterable[str], *, collapse: bool = True) -> set[str]:
    found: set[str] = set()
    for term in protected:
        if term and len(term) >= 2 and re.search(
            rf"(?<![\wÁÉÍÓÚÜÑáéíóúüñ]){re.escape(term)}(?![\wÁÉÍÓÚÜÑáéíóúüñ])",
            text or "",
            flags=re.IGNORECASE,
        ):
            found.add(term)
    if not collapse:
        return found
    # Si «Angular Material» está, «Angular» ya está cubierto.
    return {t for t in found if not any(t != o and t.lower() in o.lower() for o in found)}


def translation_problem(
    source: str, candidate: str, locale: str, protected: Iterable[str]
) -> Optional[str]:
    """None si ``candidate`` es una traducción aceptable de ``source``; si no, el motivo."""
    cand = (candidate or "").strip()
    if not cand:
        return "empty"
    protected = list(protected)
    if not matches_locale(cand, locale, protected):
        return f"language={detect_language(cand, protected)}"
    missing_numbers = _numbers(source) - _numbers(cand)
    if missing_numbers:
        return f"numbers_missing={sorted(missing_numbers.elements())}"
    added_numbers = _numbers(cand) - _numbers(source)
    if added_numbers:
        return f"numbers_added={sorted(added_numbers.elements())}"
    missing_terms = {t for t in protected_in(source, protected) if t.lower() not in cand.lower()}
    if missing_terms:
        return f"terms_missing={sorted(missing_terms)}"
    if len(source) >= 40:
        ratio = len(cand) / max(1, len(source))
        if ratio < 0.5 or ratio > 2.0:
            return f"length_ratio={ratio:.2f}"
    return None


# --- Reparación ---------------------------------------------------------------------------


@dataclass
class LanguageItem:
    path: str
    text: str
    detected: str


@dataclass
class LanguageReport:
    locale: str
    checked: int = 0
    repaired: list[dict] = field(default_factory=list)
    unresolved: list[dict] = field(default_factory=list)
    translator_error: Optional[str] = None

    @property
    def status(self) -> str:
        if self.unresolved:
            return "unresolved"
        if self.repaired:
            return "repaired"
        return "ok"

    def as_dict(self) -> dict:
        return {
            "locale": self.locale,
            "status": self.status,
            "checked": self.checked,
            "repaired": self.repaired,
            "unresolved": self.unresolved,
            "translator_error": self.translator_error,
        }


def repair_language(
    items: list[LanguageItem],
    locale: str,
    translator: Optional[Translator],
    protected: Iterable[str],
    *,
    max_attempts: int = 2,
) -> tuple[dict[str, str], LanguageReport]:
    """Traduce solo los textos en el idioma equivocado o mezclados.

    Devuelve ``{path: texto_final}`` para todos los ``items`` y un reporte. Un texto que no
    se pudo traducir de forma válida se devuelve igual que entró y queda en ``unresolved``.
    """
    protected = [p for p in protected if p]
    report = LanguageReport(locale=locale, checked=len(items))
    final = {item.path: item.text for item in items}
    if locale not in SUPPORTED:
        for item in items:
            report.unresolved.append(
                {"path": item.path, "text": item.text, "detected": item.detected, "reason": f"unsupported_locale={locale}"}
            )
        return final, report

    pending = [item for item in items if item.detected not in {locale, "unknown"}]
    last_reason: dict[str, str] = {}
    for attempt in range(1, max_attempts + 1):
        if not pending or translator is None:
            break
        try:
            outputs = translator([item.text for item in pending], locale)
        except Exception as exc:  # red, cuota, JSON inválido: no tumba el CV
            # No se reintenta un error del proveedor (un 429 de Gemini consume cuota diaria).
            # Solo se reintenta cuando hubo respuesta y no pasó la validación.
            report.translator_error = f"{type(exc).__name__}: {str(exc)[:200]}"
            logger.warning("[language] traducción falló (intento %s): %s", attempt, report.translator_error)
            break
        if not isinstance(outputs, list) or len(outputs) != len(pending):
            report.translator_error = "translator returned a different number of items"
            continue
        still: list[LanguageItem] = []
        for item, out in zip(pending, outputs):
            reason = translation_problem(item.text, str(out or ""), locale, protected)
            if reason is None:
                final[item.path] = str(out).strip()
                report.repaired.append(
                    {"path": item.path, "from": item.detected, "attempt": attempt}
                )
            else:
                last_reason[item.path] = reason
                still.append(item)
        pending = still

    for item in pending:
        reason = last_reason.get(item.path) or ("no_translator" if translator is None else "translator_failed")
        report.unresolved.append(
            {"path": item.path, "text": item.text, "detected": item.detected, "reason": reason}
        )
    return final, report
