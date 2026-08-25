"""Implementación Google Gemini del contrato ``CvLlmBackend``."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import google.generativeai as genai

from ..compact_master import load_ollama_profile, profile_for_prompt
from ..locale_util import detect_vacancy_locale
from ..models import CvDocument
from .ollama_backend import _ollama_result_to_cv
from .parse_json import parse_json_object, response_text
from .prompts import build_matcher_prompt, build_ollama_optimizer_prompt
from .schemas import MatcherOut, OptimizerOut, gemini_response_schema

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "gemini-3.6-flash"


class GeminiCvLlmBackend:
    def __init__(self, api_key: str, model_name: str) -> None:
        self._api_key = api_key.strip()
        self._model_name = (model_name or _DEFAULT_MODEL).strip()

    @classmethod
    def from_env(cls) -> GeminiCvLlmBackend:
        llm_model = os.environ.get("LLM_MODEL", "").strip()
        gemini_model = os.environ.get("GEMINI_MODEL", "").strip()
        if llm_model.lower().startswith("gemini"):
            model = llm_model
        else:
            model = gemini_model or _DEFAULT_MODEL
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
            response_schema=gemini_response_schema(MatcherOut),
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
        master = load_ollama_profile()
        locale = detect_vacancy_locale(vacancy_text)
        prompt = build_ollama_optimizer_prompt(
            vacancy_text, profile_for_prompt(master), locale
        )

        cfg = genai.GenerationConfig(
            temperature=0.2,
            max_output_tokens=8192,
            response_mime_type="application/json",
            response_schema=gemini_response_schema(OptimizerOut),
        )

        last_err: Optional[Exception] = None
        for attempt in range(1, 3):
            try:
                response = model.generate_content(prompt, generation_config=cfg)
                raw = response_text(response)
                data = parse_json_object(raw, context="gemini")
                cv_out = _ollama_result_to_cv(data, cv, master, locale)
                match_percent = float(data.get("match_score") or 0)
                if match_percent <= 10:
                    match_percent *= 10
                match_percent = max(0.0, min(100.0, match_percent))
                reason = str(data.get("target_role") or cv_out.title or "CV optimizado con Gemini")
                raw_meta: Dict[str, Any] = {
                    "llm_provider": self.provider_id,
                    "llm_model": self._model_name,
                    "source": "master_profile",
                    "keywords": data.get("keywords") or [],
                    "attempts": attempt,
                    "locale": locale,
                }
                return cv_out, match_percent, reason, [], [], [], raw_meta
            except Exception as e:
                last_err = e
                logger.warning(
                    "Gemini tailor JSON inválido (intento %s/2): %s",
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
