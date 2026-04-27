"""Contrato común para match + tailor (cualquier proveedor)."""

from __future__ import annotations

from typing import Any, Dict, List, Protocol, Tuple, runtime_checkable

from ..models import CvDocument


@runtime_checkable
class CvLlmBackend(Protocol):
    """Backend que elige perfil y adapta CV. Implementaciones: Gemini, OpenAI-compatible, etc."""

    @property
    def provider_id(self) -> str: ...

    @property
    def model_id(self) -> str: ...

    def is_configured(self) -> bool:
        """True si hay credenciales suficientes para llamar al API (match y tailor)."""
        ...

    async def pick_best_cv(
        self, vacancy_text: str, cvs: list[CvDocument]
    ) -> tuple[CvDocument, float, str]:
        ...

    async def tailor_cv(
        self, vacancy_text: str, cv: CvDocument
    ) -> Tuple[CvDocument, float, str, List[str], List[str], List[str], Dict[str, Any]]:
        """
        Devuelve (cv_out, match_percent, reason, notes_to_verify, gaps, reinforcement_plan, raw_meta).
        raw_meta debe incluir al menos llm_provider, llm_model, attempts (si aplica).
        """
        ...
