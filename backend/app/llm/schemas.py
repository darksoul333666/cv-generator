from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel


class MatcherOut(BaseModel):
    chosen_cv_id: str
    score: float
    reason: str


class TailorEnvelopeOut(BaseModel):
    # `cv` como objeto genérico: si anidamos `CvDocument`, el JSON Schema de Gemini incluye `default`.
    match_percent: float
    reason: str
    notes_to_verify: List[str]
    gaps: List[str]
    reinforcement_plan: List[str]
    cv: Dict[str, Any]
