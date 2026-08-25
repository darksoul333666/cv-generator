from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class VacancyRequest(BaseModel):
    """Texto de la vacante para el modelo. Empresa y URL son metadatos locales, no van al LLM."""

    vacancy_text: str = Field(default="", description="Descripción de la oferta (sin empresa/URL)")
    vacancy_url: Optional[str] = Field(
        default=None,
        description="URL de la vacante: solo se guarda en historial, no se envía al modelo",
    )
    company_name: Optional[str] = Field(
        default=None,
        description="Nombre de la empresa: solo se guarda en historial, no se envía al modelo",
    )


class ExperienceItem(BaseModel):
    company: str
    role: str
    period: str = ""
    bullets: List[str] = Field(default_factory=list)


class StackBlock(BaseModel):
    frontend: str = ""
    styling: str = ""
    backend: str = ""
    state: str = ""
    cloud: str = ""
    mobile: str = ""
    architecture: str = ""
    testing: str = ""
    quality: str = ""


class TechSkills(BaseModel):
    front: List[str] = Field(default_factory=list)
    back: List[str] = Field(default_factory=list)
    ux: List[str] = Field(default_factory=list)
    test: List[str] = Field(default_factory=list)


class MasterSkills(BaseModel):
    """Categorías del JSON maestro que alimenta /skills."""

    languages: List[str] = Field(default_factory=list)
    frontend: List[str] = Field(default_factory=list)
    backend: List[str] = Field(default_factory=list)
    mobile: List[str] = Field(default_factory=list)
    databases: List[str] = Field(default_factory=list)
    cloud: List[str] = Field(default_factory=list)
    devops: List[str] = Field(default_factory=list)
    testing: List[str] = Field(default_factory=list)
    architecture: List[str] = Field(default_factory=list)
    payments: List[str] = Field(default_factory=list)
    security: List[str] = Field(default_factory=list)
    ai: List[str] = Field(default_factory=list)
    softSkills: List[str] = Field(default_factory=list)


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
    tech_skills: TechSkills = Field(default_factory=TechSkills)
    education: str = ""
    certifications: List[str] = Field(default_factory=list)
    locale: str = "es"

    model_config = {"extra": "ignore"}


class MatchResponse(BaseModel):
    chosen_cv_id: str
    match_score: float
    match_reason: str
    cv: CvDocument
    vacancy_excerpt: str = ""
    raw_meta: Dict[str, Any] = Field(default_factory=dict)


class TailorRequest(BaseModel):
    """Solicitud para perfilar un CV con IA (vacante y/o instrucciones libres)."""

    vacancy_text: str = Field(default="", description="Texto completo de la oferta")
    vacancy_url: Optional[str] = Field(default=None, description="URL opcional")
    custom_instructions: str = Field(
        default="",
        description="Instrucciones del usuario para modificar el CV (tono, foco, rol, keywords, etc.)",
    )
    cv: CvDocument


class TailorResponse(BaseModel):
    cv: CvDocument
    match_percent: float = Field(description="Estimación (0-100) del alineamiento")
    reason: str = ""
    notes_to_verify: List[str] = Field(default_factory=list)
    gaps: List[str] = Field(default_factory=list)
    reinforcement_plan: List[str] = Field(default_factory=list)
    raw_meta: Dict[str, Any] = Field(default_factory=dict)
    saved_id: Optional[str] = Field(
        default=None,
        description="Id en el historial local si este CV se guardó al generar",
    )
    cv_name: Optional[str] = Field(
        default=None,
        description="Nombre con el que se guarda/descarga el PDF",
    )
    company_name: Optional[str] = Field(default=None)
    vacancy_url: Optional[str] = Field(default=None)


class ExtensionVacancyIn(BaseModel):
    """Solo descripción de la vacante (la extensión no envía URL). Campos desconocidos se ignoran."""

    model_config = ConfigDict(extra="ignore")

    vacancy_text: str = Field(
        default="",
        description="Texto completo de la oferta capturado en el cliente",
    )
    vacancy_title: Optional[str] = Field(
        default=None,
        description="Título corto para la lista (ej. nombre del puesto); si falta, se infiere del texto",
    )
    source_site: Optional[str] = Field(
        default=None,
        description="Origen: indeed, linkedin, glassdoor, etc.",
    )


class ExtensionJobSummaryOut(BaseModel):
    id: str
    vacancy_title: str
    source_site: str
    created_at: str
    chosen_cv_id: str
    match_score: float
    tailor_match_percent: float


class ExtensionOptimizeResponse(BaseModel):
    """Respuesta al generar desde la extensión: mismo dato que guarda la caché."""

    id: str
    vacancy_title: str
    source_site: str
    created_at: str
    match: MatchResponse
    tailor: TailorResponse


class ExtensionJobListResponse(BaseModel):
    jobs: List[ExtensionJobSummaryOut]


class HistorySummaryOut(BaseModel):
    id: str
    vacancy_title: str
    created_at: str
    match_percent: float
    target_role: str = ""
    cv_name: str = ""
    company_name: str = ""
    vacancy_url: Optional[str] = None


class HistoryDetailOut(BaseModel):
    id: str
    vacancy_title: str
    vacancy_text: str
    created_at: str
    match_percent: float
    reason: str = ""
    cv: CvDocument
    cv_name: str = ""
    company_name: str = ""
    vacancy_url: Optional[str] = None


class HistoryRenameIn(BaseModel):
    cv_name: str = Field(..., min_length=1, max_length=200)


class HistoryListResponse(BaseModel):
    items: List[HistorySummaryOut]

