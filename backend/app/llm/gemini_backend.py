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
from .prompts import build_batch_optimizer_prompt, build_matcher_prompt, build_ollama_optimizer_prompt
from .schemas import MatcherOut, OptimizerBatchOut, OptimizerOut, gemini_response_schema
from .errors import is_quota_or_rate_limit

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
                if is_quota_or_rate_limit(e):
                    raise
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
                cv_out = _ollama_result_to_cv(data, cv, master, locale, vacancy_text)
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
                if is_quota_or_rate_limit(e):
                    raise
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

    def _pack_optimizer(
        self,
        data: dict,
        cv: CvDocument,
        master: dict,
        locale: str,
        vacancy_text: str,
        attempts: int,
        extra_meta: Optional[Dict[str, Any]] = None,
    ) -> Tuple[CvDocument, float, str, List[str], List[str], List[str], Dict[str, Any]]:
        cv_out = _ollama_result_to_cv(data, cv, master, locale, vacancy_text)
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
            "attempts": attempts,
            "locale": locale,
        }
        if extra_meta:
            raw_meta.update(extra_meta)
        return cv_out, match_percent, reason, [], [], [], raw_meta

    def _align_batch_items(self, raw_items: list[dict], n: int) -> list[Optional[dict]]:
        aligned: list[Optional[dict]] = [None] * n
        leftover: list[dict] = []
        for raw in raw_items:
            if not isinstance(raw, dict):
                continue
            try:
                slot = int(raw.get("slot") or 0)
            except (TypeError, ValueError):
                slot = 0
            if 1 <= slot <= n and aligned[slot - 1] is None:
                aligned[slot - 1] = raw
            else:
                leftover.append(raw)
        for i in range(n):
            if aligned[i] is None and leftover:
                aligned[i] = leftover.pop(0)
        return aligned

    def _tailor_cv_batch_sync(
        self, items: list[tuple[str, CvDocument]]
    ) -> list[Tuple[CvDocument, float, str, List[str], List[str], List[str], Dict[str, Any]]]:
        if not items:
            return []
        genai.configure(api_key=self._api_key)
        model = genai.GenerativeModel(self._model_name)
        master = load_ollama_profile()
        prompt_jobs: list[tuple[int, str, str]] = []
        locales: list[str] = []
        for i, (vacancy_text, _cv) in enumerate(items, start=1):
            locale = detect_vacancy_locale(vacancy_text)
            locales.append(locale)
            prompt_jobs.append((i, vacancy_text, locale))
        prompt = build_batch_optimizer_prompt(prompt_jobs, profile_for_prompt(master))
        n = len(items)
        cfg = genai.GenerationConfig(
            temperature=0.2,
            max_output_tokens=32768,
            response_mime_type="application/json",
            response_schema=gemini_response_schema(OptimizerBatchOut),
        )
        last_err: Optional[Exception] = None
        data: Optional[dict] = None
        for attempt in range(1, 3):
            try:
                response = model.generate_content(prompt, generation_config=cfg)
                raw = response_text(response)
                parsed = parse_json_object(raw, context="gemini-batch")
                OptimizerBatchOut.model_validate(parsed)
                data = parsed
                break
            except Exception as e:
                last_err = e
                if is_quota_or_rate_limit(e):
                    raise
                logger.warning(
                    "Gemini lote JSON inválido (intento %s/2, n=%s): %s",
                    attempt,
                    n,
                    str(e)[:220],
                )
                cfg.temperature = 0.1
        if data is None:
            raise last_err or RuntimeError("Gemini lote falló")

        raw_items = data.get("items") if isinstance(data.get("items"), list) else []
        aligned = self._align_batch_items(raw_items, n)
        missing = [i + 1 for i, row in enumerate(aligned) if row is None]
        if missing:
            raise RuntimeError(
                f"El lote no trajo todos los CVs (faltan slots {missing}). Reintenta el lote."
            )

        out: list[Tuple[CvDocument, float, str, List[str], List[str], List[str], Dict[str, Any]]] = []
        for i, (vacancy_text, cv) in enumerate(items):
            row = aligned[i] or {}
            packed = self._pack_optimizer(
                row,
                cv,
                master,
                locales[i],
                vacancy_text,
                attempts=1,
                extra_meta={"batch_size": n, "batch_slot": i + 1},
            )
            out.append(packed)
        return out

    async def tailor_cv_batch(
        self, items: list[tuple[str, CvDocument]]
    ) -> list[Tuple[CvDocument, float, str, List[str], List[str], List[str], Dict[str, Any]]]:
        if not self.is_configured():
            raise RuntimeError("GEMINI_API_KEY no configurada")
        return await asyncio.to_thread(self._tailor_cv_batch_sync, items)
