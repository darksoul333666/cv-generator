from __future__ import annotations

import asyncio
import json
import os
import re
from typing import Any, Dict, List, Tuple

import google.generativeai as genai

from .models import CvDocument

DEFAULT_MODEL = "gemini-2.0-flash"


def _strip_json_fence(text: str) -> str:
    text = (text or "").strip()
    m = re.match(r"^```(?:json)?\s*(.*?)```\s*$", text, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return text


def tailor_cv_with_gemini_sync(
    vacancy_text: str, cv: CvDocument
) -> Tuple[CvDocument, float, str, List[str], List[str], List[str], Dict[str, Any]]:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY no configurada")

    genai.configure(api_key=api_key)
    model_name = (os.environ.get("GEMINI_MODEL") or DEFAULT_MODEL).strip()
    model = genai.GenerativeModel(model_name)

    # Mandamos el CV completo (pero acotado) para que el modelo lo ajuste sin inventar estructura.
    cv_json = cv.model_dump()
    vacancy_snip = vacancy_text[:16000]

    prompt = f"""Eres un asistente experto en optimización de CV para ATS.
Objetivo: adaptar el CV al CONTEXTO siguiente (puede ser una oferta de empleo, texto de URL y/o instrucciones libres del usuario),
maximizando claridad y alineación, pero SIN INVENTAR hechos no verificables (no cambies empresa/roles/periodos salvo correcciones obvias de typo).

Reglas:
- Mantén company/role/period EXACTOS tal cual; solo puedes mejorar bullets (re-escritura) y añadir bullets nuevos SI los marcas como [VALIDAR].
- Puedes ajustar summary, title, stack, certifications (si agregas algo no verificable, márcalo como [VALIDAR]).
- Si el contexto son solo instrucciones (sin oferta formal), prioriza esas instrucciones para tono, foco y keywords.
- Cuando el contexto incluya una oferta, prioriza el léxico EXACTO de la oferta para skills/herramientas que ya poseas (ej.: oferta «NEXT» vs CV «Next.js» → usa la forma de la oferta donde encaje); unifica sinónimos hacia el término del anuncio cuando sea la misma competencia (ej.: «Scrum» + oferta pide «metodologías ágiles» → «Metodologías ágiles (Scrum)» o el wording del anuncio).
- Evita emojis. (El template visual los añade en contact, no pongas más).
- Responde SOLO con JSON válido, sin markdown.

CONTEXTO (vacante, URL y/o instrucciones):
{vacancy_snip}

CV ACTUAL (JSON):
{json.dumps(cv_json, ensure_ascii=False)}

Además, crea un gap report y un plan de refuerzo para cerrar brechas rápidamente.

Formato de salida (exacto):
{{
  "match_percent": 0-100,
  "reason": "breve en español",
  "notes_to_verify": ["..."],
  "gaps": ["brecha concreta vs vacante (skills/responsabilidades faltantes)", "..."],
  "reinforcement_plan": ["acciones concretas para aprender/practicar/demostrar (rápidas)", "..."],
  "cv": <CvDocument JSON con misma estructura>
}}
"""

    response = model.generate_content(
        prompt,
        generation_config={
            "temperature": 0.25,
            "max_output_tokens": 4096,
        },
    )

    data = json.loads(_strip_json_fence(response.text or ""))
    match_percent = float(data.get("match_percent", 0))
    reason = str(data.get("reason", "")).strip()
    notes = data.get("notes_to_verify", [])
    if not isinstance(notes, list):
        notes = []
    notes_to_verify = [str(x) for x in notes][:50]

    gaps_raw = data.get("gaps", [])
    if not isinstance(gaps_raw, list):
        gaps_raw = []
    gaps = [str(x) for x in gaps_raw][:50]

    plan_raw = data.get("reinforcement_plan", [])
    if not isinstance(plan_raw, list):
        plan_raw = []
    reinforcement_plan = [str(x) for x in plan_raw][:50]

    cv_out = CvDocument.model_validate(data.get("cv"))
    raw_meta = {"gemini_model": model_name}
    return cv_out, match_percent, reason, notes_to_verify, gaps, reinforcement_plan, raw_meta


async def tailor_cv_with_gemini(
    vacancy_text: str, cv: CvDocument
) -> Tuple[CvDocument, float, str, List[str], List[str], List[str], Dict[str, Any]]:
    return await asyncio.to_thread(tailor_cv_with_gemini_sync, vacancy_text, cv)

