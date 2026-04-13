from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from typing import TYPE_CHECKING

import google.generativeai as genai

if TYPE_CHECKING:
    from .models import CvDocument

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-2.0-flash"


def _strip_json_fence(text: str) -> str:
    text = (text or "").strip()
    m = re.match(r"^```(?:json)?\s*(.*?)```\s*$", text, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return text


def pick_best_cv_gemini_sync(vacancy_text: str, cvs: list[CvDocument]) -> tuple[CvDocument, float, str]:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY no configurada")

    genai.configure(api_key=api_key)
    model_name = (os.environ.get("GEMINI_MODEL") or DEFAULT_MODEL).strip()
    model = genai.GenerativeModel(model_name)

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

    vacancy_snip = vacancy_text[:14000]
    allowed = ", ".join(repr(c.id) for c in cvs)
    prompt = f"""Eres experto en reclutamiento técnico. Elige UN único perfil base (por su id) para adaptar un CV a esta oferta.

OFERTA DE EMPLEO:
{vacancy_snip}

CANDIDATOS (JSON):
{json.dumps(profiles, ensure_ascii=False)}

Responde SOLO con JSON válido (sin markdown ni texto fuera del JSON) con esta forma exacta:
{{"chosen_cv_id":"<id>","score":<número de 0 a 10, puede ser decimal>,"reason":"<explicación breve en español>"}}

chosen_cv_id DEBE ser exactamente uno de estos valores: {allowed}
"""

    response = model.generate_content(
        prompt,
        generation_config={
            "temperature": 0.2,
            "max_output_tokens": 1024,
        },
    )
    text = _strip_json_fence(response.text or "")
    data = json.loads(text)
    chosen_id = str(data["chosen_cv_id"]).strip()
    score = float(data["score"])
    reason = str(data["reason"]).strip()

    by_id = {c.id: c for c in cvs}
    if chosen_id not in by_id:
        for c in cvs:
            if chosen_id == c.id or chosen_id in c.id or c.id in chosen_id:
                chosen_id = c.id
                break
        else:
            raise ValueError(f"Gemini devolvió chosen_cv_id inválido: {chosen_id!r}")

    return by_id[chosen_id], score, reason


async def pick_best_cv_gemini(
    vacancy_text: str, cvs: list[CvDocument]
) -> tuple[CvDocument, float, str]:
    return await asyncio.to_thread(pick_best_cv_gemini_sync, vacancy_text, cvs)
