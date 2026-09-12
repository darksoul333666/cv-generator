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


def build_ollama_optimizer_prompt(
    vacancy_text: str, master_profile: dict, locale: str = "en"
) -> str:
    """Entrada que espera el Modelfile de cv-optimizer: vacante + perfil maestro."""
    vacancy_snip = vacancy_text[:8000]
    lang = "Spanish" if locale == "es" else "English"
    return (
        f"Write the entire CV in {lang}. Do not mix languages. Company names stay exactly as in the master profile.\n"
        "target_role, summary, bullets and skill names must all be in that language.\n"
        "In Spanish, write percentages as 35% (never the English word percent).\n"
        "In Spanish, use natural articles and contractions only where grammar needs them "
        "(del estado, de la UX, de los tiempos, de una aplicación). "
        "Do not replace every de with del: keep más de 7 años, pasarelas de pago, consumo de APIs, virtualización de datos.\n"
        "Write clear noun phrases; avoid run-on stacks of de de de.\n"
        "Maximize ATS match for this job.\n"
        "You MAY add technologies from the job description that are not in the master profile (C#, .NET, Azure, Terraform, HIPAA, etc.) in skills, summary and bullets. The candidate is a senior engineer who can learn adjacent stacks. Prefer the vacancy wording.\n"
        "Keep companies, job titles, dates and metrics exactly from the master profile. Do not invent employers or numbers.\n"
        "Never drop achievement metrics: if a job has a number/percent in the master, at least one bullet of that job MUST keep that same number (Spanish: 35%, never the word percent). Vary the verb; do not start every metric bullet with the same Reducción/Reduced formula.\n\n"
        "JOB DESCRIPTION\n"
        f"{vacancy_snip}\n\n"
        "CANDIDATE MASTER PROFILE\n"
        f"{json.dumps(master_profile, ensure_ascii=False, separators=(',', ':'))}"
    )


def build_batch_optimizer_prompt(
    jobs: list[tuple[int, str, str]],
    master_profile: dict,
) -> str:
    """Varias vacantes, un solo perfil maestro. ``jobs`` = (slot 1-based, texto, locale)."""
    n = len(jobs)
    parts = [
        f"Write {n} tailored CVs from ONE master profile, one CV per JOB.",
        f"Return a single JSON object: {{\"items\":[...]}}, with exactly {n} items.",
        "Each item MUST include slot equal to its JOB number (1..N) and the fields "
        "target_role, match_score, summary, skills, keywords, experience.",
        "Do not mix jobs. Keep companies, job titles, dates and metrics exactly from the master profile.",
        "Never drop achievement metrics: if a job has a number/percent in the master, keep that same number in at least one bullet (Spanish: 35%). Do not invent numbers. Vary metric verbs.",
        "You MAY add vacancy technologies that are not in the master profile (C#, .NET, Azure, etc.) to skills, summary and bullets. Do not invent employers or numbers.",
        "",
    ]
    for slot, vacancy_text, locale in jobs:
        lang = "Spanish" if locale == "es" else "English"
        snip = (vacancy_text or "")[:2800]
        parts.append(
            f"JOB {slot} — write this entire CV in {lang}. Do not mix languages. "
            "In Spanish, percentages must be 35% (never the English word percent). "
            "Use del/de la/de los only when the noun is specific (del estado, de los tiempos); "
            "keep más de 7 años and pasarelas de pago as de."
        )
        parts.append(snip)
        parts.append("")
    parts.append("CANDIDATE MASTER PROFILE")
    parts.append(json.dumps(master_profile, ensure_ascii=False, separators=(",", ":")))
    return "\n".join(parts)


def build_tailor_prompt(vacancy_text: str, cv_json: dict) -> str:
    vacancy_snip = vacancy_text[:16000]
    return f"""Eres un asistente experto en optimización de CV para ATS.
Objetivo: adaptar el CV al CONTEXTO siguiente (puede ser una oferta de empleo, texto de URL y/o instrucciones libres del usuario),
maximizando claridad y alineación, pero SIN INVENTAR hechos no verificables (no cambies empresa/roles/periodos salvo correcciones obvias de typo).

Reglas:
- Mantén company/role/period EXACTOS tal cual; solo puedes mejorar bullets (re-escritura) y añadir bullets nuevos SI los marcas como [VALIDAR].
- Puedes ajustar summary, title y stack. Tecnologías de la vacante que no estén en el CV/maestro SÍ se pueden agregar (el candidato cubre stacks adyacentes). Educación y certificaciones no se reescriben: salen fijas del perfil maestro.
- Campo title (titular bajo el nombre): cuando haya oferta, reescríbelo para alinearlo al TÍTULO DEL PUESTO de la vacante en redacción, orden de palabras y mayúsculas/minúsculas lo más fiel posible al anuncio (ej.: «Frontend Senior», «Senior Frontend», «Senior Frontend Developer»), siempre que encaje con el nivel y dominio reales del candidato según su experiencia; no subas de nivel (no inventes «Principal»/«Staff» si no está sustentado). Si la oferta usa varias formas, elige la del encabezado o la más repetida.
- Idioma: todo el CV (summary, title, bullets, skills) en el mismo idioma de la vacante. No mezcles español e inglés. En español, los porcentajes van como 35% (nunca la palabra inglesa percent).
- Español natural: usa del / de la / de los / de las solo cuando el sustantivo lo pide (manejo del estado, reducción de los tiempos, desarrollo de una aplicación). No sustituyas todo «de» por «del»: «más de 7 años», «pasarelas de pago», «consumo de APIs» se quedan con «de». Frases claras; evita cadenas de «de».
- Conserva todas las métricas/porcentajes. No las quites: si un empleo ya tiene un número, al menos un bullet de ese empleo debe llevarlo. No inventes cifras nuevas. Varía el verbo; no clones «Reducción de X en un N%» en todos los puestos.
- Si el contexto son solo instrucciones (sin oferta formal), prioriza esas instrucciones para tono, foco y keywords.
- Cuando el contexto incluya una oferta, prioriza el léxico EXACTO de la oferta para skills/herramientas (las del maestro y las que agregues de la vacante). Unifica sinónimos hacia el término del anuncio.
- Evita emojis. (El template visual los añade en contact, no pongas más).
- Responde SOLO con un único objeto JSON válido, sin markdown. En strings, escapa comillas internas.

CONTEXTO (vacante, URL y/o instrucciones):
{vacancy_snip}

CV ACTUAL (JSON):
{json.dumps(cv_json, ensure_ascii=False)}

Formato de salida (exacto):
{{
  "match_percent": 0-100,
  "reason": "breve en español",
  "notes_to_verify": ["..."],
  "cv": <CvDocument JSON con misma estructura>
}}
"""
