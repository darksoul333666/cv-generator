from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class VacancyRequest(BaseModel):
    """Entrada desde el front: texto de vacante y/o URL (el backend puede extraer texto de la URL)."""

    vacancy_text: str = Field(default="", description="Texto completo de la oferta")
    vacancy_url: Optional[str] = Field(
        default=None, description="URL opcional para extraer texto en servidor"
    )


class ExperienceItem(BaseModel):
    company: str
    role: str
    period: str = ""
    bullets: List[str] = Field(default_factory=list)


class StackBlock(BaseModel):
    frontend: str = ""
    backend: str = ""
    state: str = ""
    cloud: str = ""
    mobile: str = ""
    architecture: str = ""
    testing: str = ""
    quality: str = ""


class CvDocument(BaseModel):
    """Perfil base (plantilla React / PDF) + metadatos para el matcher."""

    id: str
    label: str = ""
    keywords: List[str] = Field(default_factory=list)
    name: str
    title: str = ""
    email: str
    phone: str = ""
    linkedin: str = ""
    summary: str = ""
    experience: List[ExperienceItem] = Field(default_factory=list)
    stack: StackBlock = Field(default_factory=StackBlock)
    education: str = ""
    certifications: List[str] = Field(default_factory=list)

    model_config = {"extra": "ignore"}


class MatchResponse(BaseModel):
    chosen_cv_id: str
    match_score: float
    match_reason: str
    cv: CvDocument
    vacancy_excerpt: str = ""
    raw_meta: Dict[str, Any] = Field(default_factory=dict)
