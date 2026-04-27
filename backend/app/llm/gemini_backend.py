"""Implementación Google Gemini del contrato ``CvLlmBackend``."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import google.generativeai as genai

from ..models import CvDocument
from .parse_json import parse_json_object, response_text
from .prompts import build_matcher_prompt, build_tailor_prompt
from .schemas import MatcherOut, TailorEnvelopeOut

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "gemini-2.0-flash"


class GeminiCvLlmBackend:
    def __init__(self, api_key: str, model_name: str) -> None:
        self._api_key = api_key.strip()
        self._model_name = (model_name or _DEFAULT_MODEL).strip()

    @classmethod
    def from_env(cls) -> GeminiCvLlmBackend:
        # ``LLM_MODEL`` opcional: mismo nombre de modelo para cuando añadas otros proveedores.
        model = (
            os.environ.get("LLM_MODEL", "").strip()
            or os.environ.get("GEMINI_MODEL", "").strip()
            or _DEFAULT_MODEL
        ).strip()
        return cls(os.environ.get("GEMINI_API_KEY", "").strip(), model)

    @property
    def provider_id(self) -> str:
        return "gemini"

    @property
    def model_id(self) -> str:
        return self._model_name

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def _pick_best_cv_sync(self, vacancy_text: str, cvs: list[CvDocument]) -> tuple[CvDocument, float, str]:
        genai.configure(api_key=self._api_key)
        model = genai.GenerativeModel(self._model_name)

        profiles: list[dict] = []
        for cv in cvs:
            profiles.append(
                {
                    "id": cv.id,
                    "label": cv.label,
                    "keywords": cv.keywords,
                    "summary": (cv.summary or "")[:800],
                    "roles": [f"{ex.role} @ {ex.company}" for ex in cv.experience[:5]],
                }
            )

        allowed = ", ".join(repr(c.id) for c in cvs)
        prompt = build_matcher_prompt(vacancy_text, profiles, allowed)

        base_cfg = genai.GenerationConfig(
            temperature=0.1,
            max_output_tokens=512,
            response_mime_type="application/json",
            response_schema=MatcherOut,
        )

        last_err: Optional[Exception] = None
        for attempt in range(1, 4):
            try:
                response = model.generate_content(prompt, generation_config=base_cfg)
                raw = response_text(response)
                data = MatcherOut.model_validate(parse_json_object(raw, context="matcher"))
                chosen_id = data.chosen_cv_id.strip()
                score = float(data.score)
                reason = data.reason.strip()
                break
            except Exception as e:
                last_err = e
                logger.warning(
                    "Gemini matcher JSON inválido (intento %s/3): %s",
                    attempt,
                    str(e)[:200],
                )
                if attempt == 3:
                    raise
        else:
            raise last_err or RuntimeError("Gemini matcher falló")

        by_id = {c.id: c for c in cvs}
        if chosen_id not in by_id:
            for c in cvs:
                if chosen_id == c.id or chosen_id in c.id or c.id in chosen_id:
                    chosen_id = c.id
                    break
            else:
                raise ValueError(f"Gemini devolvió chosen_cv_id inválido: {chosen_id!r}")

        return by_id[chosen_id], score, reason

    async def pick_best_cv(
        self, vacancy_text: str, cvs: list[CvDocument]
    ) -> tuple[CvDocument, float, str]:
        if not self.is_configured():
            raise RuntimeError("GEMINI_API_KEY no configurada")
        return await asyncio.to_thread(self._pick_best_cv_sync, vacancy_text, cvs)

    def _tailor_cv_sync(
        self, vacancy_text: str, cv: CvDocument
    ) -> Tuple[CvDocument, float, str, List[str], List[str], List[str], Dict[str, Any]]:
        genai.configure(api_key=self._api_key)
        model = genai.GenerativeModel(self._model_name)

        cv_json = cv.model_dump()
        prompt = build_tailor_prompt(vacancy_text, cv_json)

        cfg = genai.GenerationConfig(
            temperature=0.25,
            max_output_tokens=8192,
            response_mime_type="application/json",
            response_schema=TailorEnvelopeOut,
        )

        last_err: Optional[Exception] = None
        for attempt in range(1, 4):
            try:
                response = model.generate_content(prompt, generation_config=cfg)
                raw = response_text(response)
                parsed = parse_json_object(raw, context="tailor")
                out = TailorEnvelopeOut.model_validate(parsed)
                match_percent = float(out.match_percent)
                reason = out.reason.strip()
                notes_to_verify = [str(x) for x in (out.notes_to_verify or [])][:50]
                gaps = [str(x) for x in (out.gaps or [])][:50]
                reinforcement_plan = [str(x) for x in (out.reinforcement_plan or [])][:50]
                cv_out = CvDocument.model_validate(out.cv)
                raw_meta: Dict[str, Any] = {
                    "llm_provider": self.provider_id,
                    "llm_model": self._model_name,
                    "attempts": attempt,
                }
                return (
                    cv_out,
                    match_percent,
                    reason,
                    notes_to_verify,
                    gaps,
                    reinforcement_plan,
                    raw_meta,
                )
            except Exception as e:
                last_err = e
                logger.warning(
                    "Gemini tailor JSON inválido (intento %s/3): %s",
                    attempt,
                    str(e)[:220],
                )
                cfg.temperature = 0.1

        raise last_err or RuntimeError("Gemini tailor falló")

    async def tailor_cv(
        self, vacancy_text: str, cv: CvDocument
    ) -> Tuple[CvDocument, float, str, List[str], List[str], List[str], Dict[str, Any]]:
        if not self.is_configured():
            raise RuntimeError("GEMINI_API_KEY no configurada")
        return await asyncio.to_thread(self._tailor_cv_sync, vacancy_text, cv)
