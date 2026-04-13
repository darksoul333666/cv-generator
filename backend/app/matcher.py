from __future__ import annotations

import json
import re
from pathlib import Path

from .models import CvDocument, MatchResponse


def _kb_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "knowledge_base"


def load_all_cvs() -> list[CvDocument]:
    out: list[CvDocument] = []
    for p in sorted(_kb_dir().glob("cv_*.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        out.append(CvDocument.model_validate(data))
    return out


def _tokenize(text: str) -> set[str]:
    lowered = text.lower()
    words = re.findall(r"[a-záéíóúñü0-9.#+]+", lowered, flags=re.IGNORECASE)
    return {w for w in words if len(w) >= 2}


def _stack_text(cv: CvDocument) -> str:
    s = cv.stack
    parts = [
        s.frontend,
        s.backend,
        s.state,
        s.cloud,
        s.mobile,
        s.architecture,
        s.testing,
        s.quality,
    ]
    return " ".join(parts).lower()


def score_cv(vacancy_tokens: set[str], cv: CvDocument) -> float:
    kw = {k.lower() for k in cv.keywords}
    overlap = len(vacancy_tokens & kw)
    blob = cv.summary.lower()
    blob += " " + _stack_text(cv)
    blob += " " + cv.education.lower()
    for ex in cv.experience:
        blob += " " + ex.role.lower() + " " + ex.company.lower()
        blob += " " + " ".join(ex.bullets).lower()
    for c in cv.certifications:
        blob += " " + c.lower()
    extra = sum(1 for t in vacancy_tokens if t in blob and t not in kw)
    return float(overlap * 2 + extra * 0.5)


def pick_best_cv(vacancy_text: str, cvs: list[CvDocument]) -> tuple[CvDocument, float, str]:
    tokens = _tokenize(vacancy_text)
    if not cvs:
        raise ValueError("No hay CVs en la base de conocimiento")

    best = cvs[0]
    best_score = score_cv(tokens, best)
    for cv in cvs[1:]:
        s = score_cv(tokens, cv)
        if s > best_score:
            best, best_score = cv, s

    reason = (
        f"Mayor solapamiento de palabras clave de la vacante con el perfil «{best.label}»."
        if tokens
        else "Vacante sin texto suficiente; se devolvió el primer perfil por defecto."
    )
    return best, best_score, reason
