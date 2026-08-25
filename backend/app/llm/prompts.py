"""Prompts de negocio (proveedor-agnósticos). Los backends solo envían texto y parsean JSON."""

from __future__ import annotations

import json


def build_matcher_prompt(vacancy_text: str, profiles: list[dict], allowed_ids_repr: str) -> str:
    vacancy_snip = vacancy_text[:14000]
    return f"""Eres experto en reclutamiento técnico. Elige UN único perfil base (por su id) para adaptar un CV a esta oferta.

OFERTA DE EMPLEO:
{vacancy_snip}

CANDIDATOS (JSON):
{json.dumps(profiles, ensure_ascii=False)}

Responde SOLO con un objeto JSON (sin markdown ni texto adicional) con esta forma exacta:
{{"chosen_cv_id":"<id>","score":<número de 0 a 10, puede ser decimal>,"reason":"<una sola frase corta en español, sin comillas dobles dentro>"}}

chosen_cv_id DEBE ser exactamente uno de estos valores: {allowed_ids_repr}
"""


def build_ollama_optimizer_prompt(vacancy_text: str, master_profile: dict) -> str:
    """Entrada que espera el Modelfile de cv-optimizer: vacante + perfil maestro."""
    vacancy_snip = vacancy_text[:8000]
    return (
        "Maximize ATS match for this job.\n"
        "Put every important technology from the JOB DESCRIPTION into skills, keywords and summary, even if it is not in the master profile. The candidate will learn those tools.\n"
        "Keep companies, job titles, dates and metrics exactly from the master profile. Do not invent employers or numbers.\n\n"
        "JOB DESCRIPTION\n"
        f"{vacancy_snip}\n\n"
        "CANDIDATE MASTER PROFILE\n"
        f"{json.dumps(master_profile, ensure_ascii=False, separators=(',', ':'))}"
    )


def build_tailor_prompt(vacancy_text: str, cv_json: dict) -> str:
    vacancy_snip = vacancy_text[:16000]
    return f"""Eres un asistente experto en optimización de CV para ATS.
Objetivo: adaptar el CV al CONTEXTO siguiente (puede ser una oferta de empleo, texto de URL y/o instrucciones libres del usuario),
maximizando claridad y alineación, pero SIN INVENTAR hechos no verificables (no cambies empresa/roles/periodos salvo correcciones obvias de typo).

Reglas:
- Mantén company/role/period EXACTOS tal cual; solo puedes mejorar bullets (re-escritura) y añadir bullets nuevos SI los marcas como [VALIDAR].
- Puedes ajustar summary, title, stack, certifications (si agregas algo no verificable, márcalo como [VALIDAR]).
- Campo title (titular bajo el nombre): cuando haya oferta, reescríbelo para alinearlo al TÍTULO DEL PUESTO de la vacante en redacción, orden de palabras y mayúsculas/minúsculas lo más fiel posible al anuncio (ej.: «Frontend Senior», «Senior Frontend», «Senior Frontend Developer»), siempre que encaje con el nivel y dominio reales del candidato según su experiencia; no subas de nivel (no inventes «Principal»/«Staff» si no está sustentado). Si la oferta usa varias formas, elige la del encabezado o la más repetida.
- Si el contexto son solo instrucciones (sin oferta formal), prioriza esas instrucciones para tono, foco y keywords.
- Cuando el contexto incluya una oferta, prioriza el léxico EXACTO de la oferta para skills/herramientas que ya poseas (ej.: oferta «NEXT» vs CV «Next.js» → usa la forma de la oferta donde encaje); unifica sinónimos hacia el término del anuncio cuando sea la misma competencia (ej.: «Scrum» + oferta pide «metodologías ágiles» → «Metodologías ágiles (Scrum)» o el wording del anuncio).
- Evita emojis. (El template visual los añade en contact, no pongas más).
- Responde SOLO con un único objeto JSON válido, sin markdown. En strings, escapa comillas internas.

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
