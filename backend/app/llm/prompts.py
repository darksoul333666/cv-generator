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


def tailor_writing_rules() -> str:
    """Reglas de calidad compartidas por una vacante y por el lote."""
    return (
        "The master profile facts are mostly in Spanish. Translate every summary, target_role and bullet "
        "into the language requested for that CV. A sentence in the wrong language makes the CV invalid. "
        "Company names stay exactly as in the master profile.\n"
        "summary: 3 or 4 lines, 50 to 70 words, plain and readable. First sentence: years_experience as a whole "
        "number plus (7.2 is 7+ years) and the target role. Name at most 6 of the vacancy's main technologies "
        "(say iOS and Android when the job is mobile). Include one real result, preferably a before_after "
        "('from 8 s to 3 s'). No lists of concepts in parentheses, no buzzword chains "
        "(resilient, regulated, DLQ, idempotency…): those belong in skills.\n"
        "experience: most recent job first. Include every employer from the last 6 years. "
        "Omit an employer that ended more than 6 years ago unless that job's technologies match the vacancy.\n"
        "Jobs whose technologies match the vacancy: 3 or 4 bullets, written with the vacancy's words. "
        "Every other job that stays on the CV: 2 or 3 bullets. "
        "Each bullet is one distinct fact from that job's responsibilities or achievements: what was built, "
        "the stack used, or the metric. Do not collapse several responsibilities into one short sentence, "
        "and do not leave a job with a single line when the profile lists more than one responsibility. "
        "Do not write a generic line such as 'Production work with Ionic' or 'Trabajo en producción con Ionic'.\n"
        "Achievements come with evidence: result, metric, how, tools, measured_by, before_after, context, project. "
        "Write each achievement bullet as verb + what + measurable result + short how, using only those "
        "fields. Prefer before_after over a bare percentage and keep both when present "
        "(pattern: '<verb> <what> from <before> to <after> (<metric>) with <how>'). Do not add context tails. "
        "Never write a metric without its how. If an achievement has no how, write the result as it is; "
        "do not guess a technique (no 'mediante ajustes…', no 'through optimizations…').\n"
        "measured_by is for the interview, not for the CV: do not write 'medido por…', 'measured by…' or "
        "'observado por el equipo'. Name a tool only if it is a real tool from tools (Sentry, CloudWatch).\n"
        "No filler: never 'miembro clave', 'key member', 'mejorando la experiencia/estabilidad' or similar "
        "claims without a concrete fact. Each bullet must start with a strong past-tense verb.\n"
        "scope lists team_size and highlights (ownership, leadership, architecture decisions, mentoring). "
        "For every job with scope, one bullet must show that scope with its own words "
        "in one short line (pattern: '<Led/Owned> <what> in a <team_size>-person team'). Senior and lead titles "
        "must be backed by these bullets. "
        "Do not invent team sizes, reports or responsibilities that scope does not list.\n"
        "position must be one entry from that job's positions list: the one that best matches the vacancy. "
        "Prefer a specific title over a generic one (React Native Developer, not Frontend, when the vacancy is React Native).\n"
        "Each bullet is one sentence of at most 22 words (one printed line when possible). Mention each metric "
        "once. Do not repeat the same phrase twice in a bullet. Short and concrete beats complete.\n"
        "In Spanish, percentages are 35% (never the English word percent, and never 35.0). "
        "Use del/de la/de los only when grammar needs them "
        "(del estado, de la UX, de los tiempos). Keep más de 7 años, pasarelas de pago, consumo de APIs.\n"
        "You MAY add technologies from the job description that are not in the master profile "
        "(C#, .NET, Azure, Terraform, HIPAA, etc.) to skills, keywords and the summary (as part of the stack the "
        "candidate works with). Experience bullets use only "
        "that job's responsibilities, achievements, technologies and metrics: a bullet that claims a "
        "technology or number the profile does not list for that job is discarded. "
        "Do not invent employers, dates, clients or numbers. Do not attach a metric to a project unless the "
        "profile's metrics[] names that project.\n"
        "Do not add Freelance or Freelancer to job titles.\n"
        "Do not put Fintech in the UffPay job title unless this job description explicitly asks for fintech "
        "or financial-services experience.\n"
        "Never drop achievement metrics: if a job has a number in the master, one bullet of that job must keep "
        "that same number. Vary the verb; do not start every metric bullet with Reducción/Reduced.\n"
    )


def build_optimizer_prompt(
    vacancy_text: str, master_profile: dict, locale: str = "en"
) -> str:
    """Entrada que espera el Modelfile de cv-optimizer: vacante + perfil maestro."""
    vacancy_snip = vacancy_text[:8000]
    lang = "Spanish" if locale == "es" else "English"
    profile, equivalents = _profile_for_vacancy(vacancy_text, master_profile)
    return (
        f"Write the entire CV in {lang}.\n"
        f"{tailor_writing_rules()}"
        "experience items MUST use keys company, position (string), dates, employment_type, bullets (string array). "
        "Do not use positions or achievements as keys.\n\n"
        "JOB DESCRIPTION\n"
        f"{vacancy_snip}\n\n"
        f"{_equivalents_block(equivalents)}"
        "CANDIDATE MASTER PROFILE\n"
        f"{json.dumps(profile, ensure_ascii=False, separators=(',', ':'))}"
    )


def _profile_for_vacancy(vacancy_text: str, master_profile: dict) -> tuple[dict, list[dict]]:
    """Proyectos más cercanos al stack de la vacante primero (directo o por equivalencia)."""
    from ..tech_equivalence import equivalents_for_vacancy, project_relevance

    equivalents = equivalents_for_vacancy(vacancy_text, master_profile)
    profile = dict(master_profile)
    projects = list(master_profile.get("projects") or [])
    projects.sort(key=lambda p: -project_relevance(p, vacancy_text, equivalents))
    profile["projects"] = projects
    return profile, equivalents


def _equivalents_block(equivalents: list[dict]) -> str:
    if not equivalents:
        return ""
    return (
        "STACK EQUIVALENTS FOR THIS JOB (the job asks for vacancy_tech; the candidate's real experience is "
        "your_experience). Highlight that real experience first. In skills, keywords and summary you may name "
        "vacancy_tech. In an experience bullet, write the real technology and you may name vacancy_tech only as "
        "an equivalence next to it (e.g. 'with NestJS, using ASP.NET Core-style dependency injection'). Never "
        "state that a past job was built with vacancy_tech.\n"
        f"{json.dumps(equivalents, ensure_ascii=False, separators=(',', ':'))}\n\n"
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
        "experience is an array of objects with EXACT keys: "
        '{"company":"...","position":"...","dates":"...","employment_type":"full_time","bullets":["...","..."]}.',
        "Use position as a string (not positions). Use bullets as an array of strings "
        "(not achievements/responsibilities). Copy companies and dates from the master.",
        "Do not mix jobs across items.",
        tailor_writing_rules(),
        "",
    ]
    for slot, vacancy_text, locale in jobs:
        _profile, equivalents = _profile_for_vacancy(vacancy_text, master_profile)
        lang = "Spanish" if locale == "es" else "English"
        snip = (vacancy_text or "")[:2800]
        parts.append(
            f"JOB {slot} — write this entire CV in {lang}. Do not mix languages. "
            "In Spanish, percentages must be 35% (never the English word percent). "
            "Use del/de la/de los only when the noun is specific (del estado, de los tiempos); "
            "keep más de 7 años and pasarelas de pago as de."
        )
        parts.append(snip)
        if equivalents:
            parts.append(_equivalents_block(equivalents).strip())
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


def build_translation_prompt(texts: list[str], locale: str, protected: list[str]) -> str:
    """Traducción literal de fragmentos de un CV. Se valida después (language_guard)."""
    lang = "Spanish" if locale == "es" else "English"
    keep = ", ".join(protected[:150])
    return (
        f"Translate each string in ITEMS into {lang}. These are fragments of a CV.\n"
        "Rules:\n"
        "- Keep the exact meaning. Do not add, remove, generalize or embellish facts.\n"
        "- Keep every number, percentage, date and year exactly as written.\n"
        "- Do not translate company names, product names, project names or technology names. "
        f"These must appear unchanged when present: {keep}.\n"
        "- A job title is translated as a job title (e.g. Technical Leader → Líder técnico).\n"
        "- If a string is already in the target language, return it unchanged.\n"
        'Return only JSON: {"items": ["...", "..."]} with exactly the same number of strings, in the same order.\n\n'
        f"ITEMS\n{json.dumps(texts, ensure_ascii=False)}"
    )
