"""Armado del CV a partir de la respuesta del modelo (Gemini u OpenAI) y del perfil maestro.

Aquí vive todo lo que no depende del proveedor. ``_build_cv`` orquesta los pasos, que viven en:

- ``cv_roles``: empresas, cargos y familias de rol según la vacante.
- ``cv_facts``: hechos del maestro y bullets de respaldo.
- ``cv_claims``: verificación de cifras, proyectos, tecnologías y el «cómo».
- ``cv_years``: años de experiencia visibles y la frase del resumen.
- ``cv_bullets``: bullets finales de cada empleo.
- ``cv_projects``: proyectos freelance según la vacante.
- ``cv_passes``: contacto, idioma, notas de verificación y revisión de redacción.
"""

from __future__ import annotations

from typing import Optional

from ..compact_master import protected_terms
from ..language_guard import Translator, detect_language
from ..locale_util import (
    attach_percent_signs,
    cert_names,
    education_line,
    format_period,
    language_lines,
    localize_cv_wording,
    percent_metric_values,
    polish_experience_title,
)
from ..models import CvDocument, ExperienceItem
from ..skill_stack import build_stack_from_master, stack_to_tech_skills, vacancy_skill_keywords
from .cv_roles import _company_index, _norm, _ordered_keys, _pick_position, role_families, target_family
from .cv_facts import _anchor_ym, _is_stale, _matches_vacancy, _years_before
from .cv_claims import _strip_methodology, _trim_unbacked_how, _unbacked_tokens, _vacancy_only_terms
from .cv_years import _title_case_level, _years_phrase, shown_years
from .cv_bullets import _all_tools, _bullets_for_job
from .cv_projects import _freelance_projects
from .cv_passes import (
    Proofreader,
    _apply_language,
    _contact,
    _quality_pass,
    _stack_labels,
    _summary_problems,
    _verification_notes,
)


def _build_cv(
    data: dict,
    base: CvDocument,
    master: dict,
    locale: str = "es",
    vacancy_text: str = "",
    translator: Optional[Translator] = None,
    proofreader: Optional[Proofreader] = None,
) -> tuple[CvDocument, dict]:
    """JSON del optimizer → CvDocument + reporte de verificación (fechas, hechos, idioma, redacción)."""
    companies = _company_index(master)
    allowed = {_norm(c) for c in (master.get("allowed_companies") or companies.keys())}
    personal = {_norm(n) for n in (master.get("personal_products_not_employment") or [])}
    overlay = [
        str(s).strip()
        for s in list(data.get("skills") or []) + list(data.get("keywords") or [])
        if str(s).strip()
    ]
    from ..tech_equivalence import equivalents_for_vacancy

    vacancy_only = _vacancy_only_terms(overlay, master)
    for row in equivalents_for_vacancy(vacancy_text, master):
        for term in row["vacancy_tech"]:
            if term not in vacancy_only:
                vacancy_only.append(term)
    rejected: list[dict] = []
    weak: list[dict] = []
    unverified_dates: list[dict] = []
    target_role = str(data.get("target_role") or base.title or "").strip()

    def period_for(source: dict) -> str:
        if source.get("dates_verified") is False:
            unverified_dates.append(
                {"company": source.get("company"), "candidates": source.get("date_candidates") or []}
            )
            return ""
        # Solo fechas del maestro. Las «dates» que escriba el modelo nunca se usan.
        main = format_period(
            source.get("start_date"),
            source.get("end_date"),
            bool(source.get("current")),
            locale,
        ) or str(source.get("dates") or "").strip()
        # Una sola etapa por empresa: la principal (la más reciente). Las etapas anteriores
        # (``extra_periods``) siguen en el perfil, pero dos rangos en una línea confunden.
        return main

    built: dict[str, ExperienceItem] = {}
    for raw in data.get("experience") or []:
        if not isinstance(raw, dict):
            continue
        company = str(raw.get("company") or "").strip()
        key = _norm(company)
        if not company or key not in allowed or key in personal or key in built:
            continue
        source = companies.get(key) or {}
        period = period_for(source)
        position = str(
            raw.get("position")
            or raw.get("role")
            or raw.get("title")
            or ""
        ).strip()
        if not position:
            positions = raw.get("positions") or raw.get("roles") or []
            if isinstance(positions, list) and positions:
                position = str(positions[0] or "").strip()
            elif isinstance(positions, str):
                position = positions.strip()
        known = [str(role).strip() for role in (source.get("positions") or []) if str(role).strip()]
        known_norms = [_norm(role) for role in known]
        if position and known_norms and _norm(position) not in known_norms:
            known_blob = " ".join(known_norms)
            if not any(tok in known_blob for tok in _norm(position).split() if len(tok) > 3):
                position = known[0] if known else position
        position = _pick_position(known, position, vacancy_text, target_role)
        position = polish_experience_title(
            source.get("company") or company,
            position or (known[0] if known else ""),
            vacancy_text,
            source.get("title_qualifiers"),
        )
        bullets = [
            localize_cv_wording(str(b).strip(), locale)
            for b in (raw.get("bullets") or raw.get("achievements") or raw.get("responsibilities") or [])
            if not isinstance(b, dict) and str(b).strip()
        ]
        role = localize_cv_wording(position, locale)
        built[key] = ExperienceItem(
            company=source.get("company") or company,
            role=role,
            period=period,
            bullets=_bullets_for_job(
                source,
                bullets,
                vacancy_text,
                role,
                locale,
                master=master,
                vacancy_only=vacancy_only,
                rejected=rejected,
                weak=weak,
            ),
        )

    cutoff = _years_before(_anchor_ym(companies), 6)
    for key, source in companies.items():
        if key in personal or key in built or key not in allowed:
            continue
        if _is_stale(source, cutoff) and not _matches_vacancy(source, vacancy_text):
            continue
        known = [str(role).strip() for role in (source.get("positions") or []) if str(role).strip()]
        position = polish_experience_title(
            source.get("company") or key,
            _pick_position(known, known[0] if known else "", vacancy_text, target_role),
            vacancy_text,
            source.get("title_qualifiers"),
        )
        role = localize_cv_wording(position, locale)
        built[key] = ExperienceItem(
            company=source.get("company") or key,
            role=role,
            period=period_for(source),
            bullets=_bullets_for_job(
                source, [], vacancy_text, role, locale, master=master, rejected=rejected, weak=weak
            ),
        )

    for key, source in list(built.items()):
        origin = companies.get(key) or {}
        if _is_stale(origin, cutoff) and not _matches_vacancy(origin, vacancy_text):
            del built[key]

    experience = [built[key] for key in _ordered_keys(list(built), companies)]

    # Cargos sin variante validada de la familia del titular: se dejan los reales y se avisa.
    family = target_family(target_role, vacancy_text)
    off_family = [
        job.company
        for job in experience
        if family and family not in role_families(job.role)
    ]

    contact = _contact(master)
    title = localize_cv_wording(
        str(data.get("target_role") or base.title or "").strip(),
        locale,
    )
    summary = localize_cv_wording(str(data.get("summary") or "").strip(), locale) or base.summary
    summary = _strip_methodology(summary, _all_tools(master))
    shown = shown_years([companies.get(_norm(job.company)) or {} for job in experience])
    summary = _years_phrase(summary, master, locale, shown)
    all_unbacked: set[str] = set()
    for source in companies.values():
        all_unbacked |= _unbacked_tokens(source)
    trimmed_summary, summary_trimmed = _trim_unbacked_how(summary, all_unbacked, _all_tools(master))
    if summary_trimmed:
        weak.append({"company": "Resumen", "bullet": summary, "how": "", "trimmed": trimmed_summary})
        summary = trimmed_summary
    stack = build_stack_from_master(master, vacancy_text, overlay=overlay)
    stack_labels = _stack_labels(stack, locale)
    keywords = [
        str(item)
        for item in (vacancy_skill_keywords(master, vacancy_text, overlay) or base.keywords)
        if str(item).strip()
    ]

    # Un solo paso de idioma para todo lo visible: título, summary, cargos, bullets, skills.
    fields: dict[str, str] = {"title": title, "summary": summary}
    for i, job in enumerate(experience):
        fields[f"experience[{i}].role"] = job.role
        for j, bullet in enumerate(job.bullets):
            fields[f"experience[{i}].bullets[{j}]"] = bullet
    projects = _freelance_projects(master, vacancy_text)
    for i, project in enumerate(projects):
        fields[f"projects[{i}].line"] = project.line
    for name, labels in stack_labels.items():
        for k, label in enumerate(labels):
            fields[f"stack.{name}[{k}]"] = label
    for k, word in enumerate(keywords):
        fields[f"keywords[{k}]"] = word
    protected = protected_terms(master)
    # Bullets a los que se les puso el «cómo» del perfil en otro idioma: se traducen completos.
    mixed = {
        str(item["fixed"])
        for item in weak
        if item.get("fixed") and detect_language(str(item.get("how") or ""), protected) not in {locale, "unknown"}
    }
    fixed, language_report = _apply_language(fields, locale, protected, translator, mixed)

    experience = [
        job.model_copy(
            update={
                "role": _title_case_level(fixed[f"experience[{i}].role"]),
                "bullets": [
                    localize_cv_wording(fixed[f"experience[{i}].bullets[{j}]"], locale)
                    for j in range(len(job.bullets))
                ],
            }
        )
        for i, job in enumerate(experience)
    ]
    stack = stack.model_copy(
        update={
            name: ", ".join(fixed[f"stack.{name}[{k}]"] for k in range(len(labels)))
            for name, labels in stack_labels.items()
        }
    )
    keywords = [fixed[f"keywords[{k}]"] for k in range(len(keywords))]
    projects = [p.model_copy(update={"line": fixed[f"projects[{i}].line"]}) for i, p in enumerate(projects)]
    title = _title_case_level(fixed["title"])
    percents = percent_metric_values(master)
    summary = attach_percent_signs(localize_cv_wording(fixed["summary"], locale), percents)
    experience = [
        job.model_copy(
            update={
                "bullets": [attach_percent_signs(bullet, percents) for bullet in job.bullets]
            }
        )
        for job in experience
    ]

    # Redacción: lo último antes de armar el CV, sobre el texto final ya traducido.
    polish: dict[str, str] = {"title": title, "summary": summary}
    for i, job in enumerate(experience):
        for j, bullet in enumerate(job.bullets):
            polish[f"experience[{i}].bullets[{j}]"] = bullet
    for i, project in enumerate(projects):
        polish[f"projects[{i}].line"] = project.line
    polished, quality = _quality_pass(polish, locale, protected, proofreader)
    title = polished["title"]
    summary = polished["summary"]
    experience = [
        job.model_copy(
            update={"bullets": [polished[f"experience[{i}].bullets[{j}]"] for j in range(len(job.bullets))]}
        )
        for i, job in enumerate(experience)
    ]
    projects = [p.model_copy(update={"line": polished[f"projects[{i}].line"]}) for i, p in enumerate(projects)]

    report = {
        "title_family": family,
        "off_family_titles": off_family,
        "unverified_dates": unverified_dates,
        "rejected_claims": rejected,
        "weak_bullets": weak,
        "summary_claims": _summary_problems(summary, master),
        "language": language_report,
        "quality": quality,
    }
    report["notes"] = _verification_notes(report)

    cv = CvDocument(
        id=base.id,
        label=base.label,
        keywords=keywords,
        name=str(master.get("name") or base.name),
        title=title or base.title,
        email=contact["email"] or base.email,
        phone=contact["phone"] or base.phone,
        linkedin=contact["linkedin"] or base.linkedin,
        location=contact["location"] or base.location,
        summary=summary,
        experience=experience or base.experience,
        projects=projects,
        stack=stack,
        tech_skills=stack_to_tech_skills(stack),
        education=education_line(master, locale) or base.education,
        certifications=cert_names(master, locale) or base.certifications,
        languages=language_lines(master, locale) or base.languages,
        locale=locale,
    )
    # Revisión para la app: nota de redacción y palabras clave de la vacante que quedaron (o no).
    from ..cv_review import build_review, keyword_coverage

    report["coverage"] = keyword_coverage(cv, master, vacancy_text, data.get("keywords") or [])
    report["review"] = build_review(report)
    return cv, report


def result_to_cv(
    data: dict,
    base: CvDocument,
    master: dict,
    locale: str = "es",
    vacancy_text: str = "",
    translator: Optional[Translator] = None,
    proofreader: Optional[Proofreader] = None,
) -> CvDocument:
    """Igual que ``_build_cv`` pero solo devuelve el CV."""
    cv, _report = _build_cv(data, base, master, locale, vacancy_text, translator, proofreader)
    return cv
