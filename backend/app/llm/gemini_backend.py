"""Implementación Google Gemini del contrato ``CvLlmBackend``."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from google import genai
from google.genai import types

from ..compact_master import load_ollama_profile, profile_for_prompt
from ..locale_util import detect_vacancy_locale
from ..models import CvDocument
from .parse_json import parse_json_object, response_text
from .prompts import build_batch_optimizer_prompt, build_matcher_prompt, build_ollama_optimizer_prompt
from .result_pack import align_batch_items, pack_optimizer
from .schemas import MatcherOut, OptimizerBatchOut, OptimizerOut

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "gemini-3.6-flash"
_HTTP_CALLS = 0


def _no_retry_http(extra_body: Optional[dict] = None) -> types.HttpOptions:
    """Una sola ida al API. Sin reintentos de 429/5xx (cada uno cuenta RPM/RPD)."""
    return types.HttpOptions(
        timeout=600_000,
        retry_options=types.HttpRetryOptions(attempts=1, http_status_codes=[]),
        extra_body=extra_body,
    )


class GeminiCvLlmBackend:
    def __init__(self, api_key: str, model_name: str) -> None:
        self._api_key = api_key.strip()
        self._model_name = (model_name or _DEFAULT_MODEL).strip()
        self._client: Optional[genai.Client] = None

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

    def _is_gemini3(self) -> bool:
        return "gemini-3" in self._model_name.lower()

    def _genai(self) -> genai.Client:
        if self._client is None:
            extra = None
            if self._is_gemini3():
                extra = {
                    "generationConfig": {
                        "thinkingConfig": {
                            "thinkingLevel": "minimal",
                            "includeThoughts": False,
                        }
                    }
                }
            self._client = genai.Client(
                api_key=self._api_key,
                http_options=_no_retry_http(extra),
            )
        return self._client

    def _thinking_config(self) -> Optional[types.ThinkingConfig]:
        if self._is_gemini3():
            return None
        return types.ThinkingConfig(thinking_budget=0, include_thoughts=False)

    def _generate(
        self,
        prompt: str,
        schema_model: type,
        *,
        max_output_tokens: int,
        n: int,
        kind: str,
    ) -> Any:
        global _HTTP_CALLS
        _HTTP_CALLS += 1
        msg = (
            f"Llamando a Gemini HTTP #{_HTTP_CALLS} · {kind} · "
            f"{n} CV{'s' if n != 1 else ''} en 1 petición · model={self._model_name} "
            f"· prompt_chars={len(prompt)}"
        )
        print(f"[cvgen] {msg}", flush=True)
        logger.info("[gemini] %s", msg)
        config_kwargs: Dict[str, Any] = {
            "max_output_tokens": max_output_tokens,
            "response_mime_type": "application/json",
            "response_schema": schema_model,
            "automatic_function_calling": types.AutomaticFunctionCallingConfig(disable=True),
        }
        thinking = self._thinking_config()
        if thinking is not None:
            config_kwargs["thinking_config"] = thinking
        try:
            response = self._genai().models.generate_content(
                model=self._model_name,
                contents=prompt,
                config=types.GenerateContentConfig(**config_kwargs),
            )
        except Exception as exc:
            fail = (
                f"Gemini HTTP #{_HTTP_CALLS} FALLÓ · {kind} · n={n} · "
                f"{type(exc).__name__}: {str(exc)[:240]}"
            )
            print(f"[cvgen] {fail}", flush=True)
            logger.warning("[gemini] %s", fail)
            raise
        usage = getattr(response, "usage_metadata", None)
        done = f"Gemini HTTP #{_HTTP_CALLS} OK · {kind} · n={n}"
        if usage is not None:
            done += (
                f" · tokens in={getattr(usage, 'prompt_token_count', None)} "
                f"out={getattr(usage, 'candidates_token_count', None)} "
                f"thoughts={getattr(usage, 'thoughts_token_count', None)}"
            )
        print(f"[cvgen] {done}", flush=True)
        logger.info("[gemini] %s", done)
        return response

    def _pick_best_cv_sync(self, vacancy_text: str, cvs: list[CvDocument]) -> tuple[CvDocument, float, str]:
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
        response = self._generate(
            prompt, MatcherOut, max_output_tokens=512, n=1, kind="matcher"
        )
        raw = response_text(response)
        data = MatcherOut.model_validate(parse_json_object(raw, context="matcher"))
        chosen_id = data.chosen_cv_id.strip()
        score = float(data.score)
        reason = data.reason.strip()

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
        master = load_ollama_profile()
        locale = detect_vacancy_locale(vacancy_text)
        prompt = build_ollama_optimizer_prompt(
            vacancy_text, profile_for_prompt(master), locale
        )
        response = self._generate(
            prompt, OptimizerOut, max_output_tokens=8192, n=1, kind="tailor"
        )
        raw = response_text(response)
        data = OptimizerOut.model_validate(parse_json_object(raw, context="gemini")).model_dump()
        return pack_optimizer(
            data,
            cv,
            master,
            locale,
            vacancy_text,
            provider=self.provider_id,
            model=self._model_name,
        )

    async def tailor_cv(
        self, vacancy_text: str, cv: CvDocument
    ) -> Tuple[CvDocument, float, str, List[str], List[str], List[str], Dict[str, Any]]:
        if not self.is_configured():
            raise RuntimeError("GEMINI_API_KEY no configurada")
        return await asyncio.to_thread(self._tailor_cv_sync, vacancy_text, cv)

    def _tailor_cv_batch_sync(
        self, items: list[tuple[str, CvDocument]]
    ) -> list[Tuple[CvDocument, float, str, List[str], List[str], List[str], Dict[str, Any]]]:
        if not items:
            return []
        master = load_ollama_profile()
        prompt_jobs: list[tuple[int, str, str]] = []
        locales: list[str] = []
        for i, (vacancy_text, _cv) in enumerate(items, start=1):
            locale = detect_vacancy_locale(vacancy_text)
            locales.append(locale)
            prompt_jobs.append((i, vacancy_text, locale))
        prompt = build_batch_optimizer_prompt(prompt_jobs, profile_for_prompt(master))
        n = len(items)
        response = self._generate(
            prompt,
            OptimizerBatchOut,
            max_output_tokens=24576,
            n=n,
            kind="tailor_batch",
        )
        raw = response_text(response)
        parsed = parse_json_object(raw, context="gemini-batch")
        raw_items = OptimizerBatchOut.model_validate(parsed).model_dump().get("items") or []
        aligned = align_batch_items(raw_items, n)
        missing = [i + 1 for i, row in enumerate(aligned) if row is None]
        if missing:
            raise RuntimeError(
                f"El lote no trajo todos los CVs (faltan slots {missing}). "
                "No se reintenta solo: espera el RPM y vuelve a generar el lote."
            )

        out: list[Tuple[CvDocument, float, str, List[str], List[str], List[str], Dict[str, Any]]] = []
        for i, (vacancy_text, cv) in enumerate(items):
            packed = pack_optimizer(
                aligned[i] or {},
                cv,
                master,
                locales[i],
                vacancy_text,
                provider=self.provider_id,
                model=self._model_name,
                extra_meta={"batch_size": n, "batch_slot": i + 1, "http_calls": 1},
            )
            out.append(packed)
        return out

    async def tailor_cv_batch(
        self, items: list[tuple[str, CvDocument]]
    ) -> list[Tuple[CvDocument, float, str, List[str], List[str], List[str], Dict[str, Any]]]:
        if not self.is_configured():
            raise RuntimeError("GEMINI_API_KEY no configurada")
        if not items:
            return []
        return await asyncio.to_thread(self._tailor_cv_batch_sync, items)
