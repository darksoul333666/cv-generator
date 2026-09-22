"""Implementación OpenAI Chat Completions del contrato ``CvLlmBackend``."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import httpx

from ..compact_master import load_ollama_profile, profile_for_prompt
from ..locale_util import detect_vacancy_locale
from ..models import CvDocument
from .parse_json import parse_json_object
from .prompts import build_batch_optimizer_prompt, build_ollama_optimizer_prompt
from .result_pack import align_batch_items, pack_optimizer
from .schemas import OptimizerBatchOut, OptimizerOut

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "gpt-5-mini"
_DEFAULT_BASE = "https://api.openai.com/v1"
_HTTP_CALLS = 0


class OpenAICvLlmBackend:
    def __init__(self, api_key: str, model_name: str, base_url: str) -> None:
        self._api_key = api_key.strip()
        self._model_name = (model_name or _DEFAULT_MODEL).strip()
        self._base_url = (base_url or _DEFAULT_BASE).rstrip("/")

    @classmethod
    def from_env(cls) -> OpenAICvLlmBackend:
        llm_model = os.environ.get("LLM_MODEL", "").strip()
        openai_model = os.environ.get("OPENAI_MODEL", "").strip()
        lowered = llm_model.lower()
        if lowered.startswith(("gpt", "o1", "o3", "o4")):
            model = llm_model
        else:
            model = openai_model or _DEFAULT_MODEL
        api_key = (
            os.environ.get("OPENAI_API_KEY", "").strip()
            or os.environ.get("API_KEY", "").strip()
        )
        return cls(
            api_key,
            model,
            os.environ.get("OPENAI_BASE_URL", "").strip() or _DEFAULT_BASE,
        )

    def _is_reasoning_model(self) -> bool:
        name = self._model_name.lower()
        return name.startswith(("gpt-5", "o1", "o3", "o4"))

    @property
    def provider_id(self) -> str:
        return "openai"

    @property
    def model_id(self) -> str:
        return self._model_name

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def _chat_json(self, prompt: str, *, max_tokens: int, n: int, kind: str) -> str:
        global _HTTP_CALLS
        _HTTP_CALLS += 1
        msg = (
            f"Llamando a OpenAI HTTP #{_HTTP_CALLS} · {kind} · "
            f"{n} CV{'s' if n != 1 else ''} en 1 petición · model={self._model_name} "
            f"· prompt_chars={len(prompt)}"
        )
        print(f"[cvgen] {msg}", flush=True)
        logger.info("[openai] %s", msg)
        payload: Dict[str, Any] = {
            "model": self._model_name,
            "messages": [
                {
                    "role": "system",
                    "content": "Return only a valid JSON object. No markdown fences.",
                },
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
        }
        if self._is_reasoning_model():
            # gpt-5 / o-series: max_tokens y temperature custom suelen devolver 400.
            payload["max_completion_tokens"] = max_tokens
            payload["reasoning_effort"] = (
                os.environ.get("OPENAI_REASONING_EFFORT", "low").strip() or "low"
            )
            payload["verbosity"] = "low"
        else:
            payload["max_tokens"] = max_tokens
            payload["temperature"] = 0.2
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self._base_url}/chat/completions"
        try:
            with httpx.Client(timeout=httpx.Timeout(600.0)) as client:
                response = client.post(url, json=payload, headers=headers)
            if response.status_code >= 400:
                detail = response.text[:400]
                err = httpx.HTTPStatusError(
                    f"{response.status_code} {detail}",
                    request=response.request,
                    response=response,
                )
                fail = (
                    f"OpenAI HTTP #{_HTTP_CALLS} FALLÓ · {kind} · n={n} · "
                    f"{response.status_code}: {detail[:240]}"
                )
                print(f"[cvgen] {fail}", flush=True)
                logger.warning("[openai] %s", fail)
                raise err
            body = response.json()
            content = (
                ((body.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
            )
            usage = body.get("usage") or {}
            done = (
                f"OpenAI HTTP #{_HTTP_CALLS} OK · {kind} · n={n} "
                f"· tokens in={usage.get('prompt_tokens')} out={usage.get('completion_tokens')}"
            )
            print(f"[cvgen] {done}", flush=True)
            logger.info("[openai] %s", done)
            return str(content)
        except httpx.HTTPStatusError:
            raise
        except Exception as exc:
            fail = (
                f"OpenAI HTTP #{_HTTP_CALLS} FALLÓ · {kind} · n={n} · "
                f"{type(exc).__name__}: {str(exc)[:240]}"
            )
            print(f"[cvgen] {fail}", flush=True)
            logger.warning("[openai] %s", fail)
            raise

    async def pick_best_cv(
        self, vacancy_text: str, cvs: list[CvDocument]
    ) -> tuple[CvDocument, float, str]:
        from ..matcher import pick_best_cv

        chosen, score, reason = pick_best_cv(vacancy_text, cvs)
        return chosen, score, f"{reason} (plantilla; los hechos salen del master via OpenAI)"

    def _tailor_cv_sync(
        self, vacancy_text: str, cv: CvDocument
    ) -> Tuple[CvDocument, float, str, List[str], List[str], List[str], Dict[str, Any]]:
        master = load_ollama_profile()
        locale = detect_vacancy_locale(vacancy_text)
        prompt = build_ollama_optimizer_prompt(
            vacancy_text, profile_for_prompt(master), locale
        )
        raw = self._chat_json(prompt, max_tokens=16384, n=1, kind="tailor")
        data = OptimizerOut.model_validate(parse_json_object(raw, context="openai")).model_dump()
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
            raise RuntimeError("OPENAI_API_KEY no configurada")
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
        raw = self._chat_json(prompt, max_tokens=32768, n=n, kind="tailor_batch")
        parsed = parse_json_object(raw, context="openai-batch")
        raw_items = OptimizerBatchOut.model_validate(parsed).model_dump().get("items") or []
        aligned = align_batch_items(raw_items, n)
        missing = [i + 1 for i, row in enumerate(aligned) if row is None]
        if missing:
            raise RuntimeError(
                f"El lote no trajo todos los CVs (faltan slots {missing}). "
                "Reencola las 5 juntas; no las generes de una en una."
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
            raise RuntimeError("OPENAI_API_KEY no configurada")
        if not items:
            return []
        return await asyncio.to_thread(self._tailor_cv_batch_sync, items)
