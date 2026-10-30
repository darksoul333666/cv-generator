"""LLM determinista para pruebas: respuestas fijas del optimizer y un traductor por diccionario."""

from __future__ import annotations

import json
import re
from types import SimpleNamespace
from typing import Callable, Optional


EN_VACANCY = (
    "Senior Frontend Developer (Angular)\n"
    "We are looking for a Senior Frontend Engineer with strong Angular, NgRx and RxJS experience "
    "to build financial dashboards. Requirements: 5+ years of experience with Angular and TypeScript, "
    "experience with Kubernetes is a plus. Responsibilities: build responsive data tables, "
    "improve rendering performance, mentor the team."
)

ES_VACANCY = (
    "Desarrollador Frontend Senior (Angular)\n"
    "Buscamos un desarrollador con experiencia en Angular, NgRx y RxJS para construir dashboards "
    "financieros. Requisitos: más de 5 años de experiencia con Angular y TypeScript. "
    "Responsabilidades: tablas responsive, mejora del rendimiento y liderazgo técnico del equipo."
)


def optimizer_en() -> dict:
    """Salida típica de un modelo para una vacante en inglés: casi todo bien, con errores reales.

    - un bullet copiado del maestro en español (debe traducirse, no borrarse);
    - un título en español;
    - 62% atribuido a Safra Bank (no respaldado);
    - una métrica inventada (50%);
    - Kubernetes (solo está en la vacante) metido en un bullet;
    - fechas de UffPay que el maestro tiene en conflicto.
    """
    return {
        "target_role": "Desarrollador Frontend Senior",
        "match_score": 8.5,
        "summary": (
            "Senior Frontend Developer with 7+ years building web and mobile products with Angular, "
            "React and TypeScript. Built financial dashboards at Grainchain Inc with NgRx and RxJS, "
            "cutting loan-table load time from 8 s to 3 s (62%) with virtual scrolling and pagination."
        ),
        "skills": ["Angular", "NgRx", "RxJS", "TypeScript", "Kubernetes"],
        "keywords": ["Angular", "NgRx", "Kubernetes"],
        "experience": [
            {
                "company": "UffPay",
                "position": "Frontend",
                "dates": "Jan 2023 – Jul 2024",
                "bullets": [
                    "Built the React Native payments, transfers and top-up app for iOS and Android.",
                    "Integrated Cybersource for payment processing.",
                    "Reducción de errores en flujos de pago mediante validaciones y UX (25%).",
                ],
            },
            {
                "company": "Grainchain Inc",
                "position": "Senior Frontend Developer",
                "dates": "Jun 2025 – Apr 2026",
                "bullets": [
                    "Built financial dashboards with Angular and Angular Material.",
                    "Cut loan-table load time from 8 s to 3 s (62%) with virtual scrolling and pagination.",
                    "Delivered the Safra Bank platform end to end, improving load times by 62%.",
                    "Managed state with NgRx and deployed services on Kubernetes.",
                ],
            },
            {
                "company": "Lumston",
                "position": "Frontend Developer",
                "bullets": [
                    "Built the Angular 18 ordering platform for Doña Tota, syncing menus and orders.",
                    "Reduced load times by 50% through component and state optimization.",
                    "Cut Volaris Manifest flight load time from 10 s to 3 s (70%) with lazy loading and pagination.",
                ],
            },
            {
                "company": "Monkey Cave",
                "position": "Technical Leader",
                "dates": "Jan 2020 – Jan 2023",
                "bullets": [
                    "Led the frontend team and defined architecture, stack and development standards.",
                    "Ran code reviews, testing and sprint planning.",
                ],
            },
        ],
    }


def optimizer_es() -> dict:
    """Vacante en español: el modelo dejó un título y dos bullets en inglés."""
    return {
        "target_role": "Senior Frontend Developer",
        "match_score": 8,
        "summary": (
            "Desarrollador Frontend Senior con más de 7 años construyendo productos web y móviles con "
            "Angular, React y TypeScript. En Grainchain Inc desarrolló dashboards financieros con NgRx "
            "y RxJS y redujo la carga de las tablas de préstamos de 8 s a 3 s (62%) con virtual scroll y paginación."
        ),
        "skills": ["Angular", "NgRx", "RxJS", "TypeScript"],
        "keywords": ["Angular", "NgRx"],
        "experience": [
            {
                "company": "Grainchain Inc",
                "position": "Senior Frontend Developer",
                "bullets": [
                    "Desarrollo de dashboards financieros con Angular y Angular Material.",
                    "Cut loan-table load time from 8 s to 3 s (62%) with virtual scrolling and pagination.",
                    "Manejo de estado con NgRx para aplicaciones escalables.",
                ],
            },
            {
                "company": "Lumston",
                "position": "Frontend Developer",
                "bullets": [
                    "Integración de Stripe Payments en aplicaciones fintech.",
                    "Cut Volaris Manifest flight load time from 10 s to 3 s (70%) with lazy loading and pagination.",
                ],
            },
            {
                "company": "UffPay",
                "position": "Frontend",
                "bullets": [
                    "App fintech en React Native para pagos, transferencias y recargas.",
                    "Integración con Cybersource para procesamiento de pagos.",
                ],
            },
            {
                "company": "Monkey Cave",
                "position": "Technical Leader",
                "bullets": [
                    "Liderazgo técnico del equipo de desarrollo frontend.",
                    "Definición de arquitectura, stack y estándares de desarrollo.",
                ],
            },
        ],
    }


# Traducciones que un modelo correcto devolvería. Solo cubren lo que el pipeline manda traducir.
TRANSLATIONS = {
    "en": {
        "Desarrollador Frontend Senior": "Senior Frontend Developer",
        "Reducción de errores en flujos de pago mediante validaciones y UX (25%).":
            "Reduced errors in payment flows through validations and UX improvements (25%).",
        "Reducción de tiempos de carga mediante optimización de componentes y estado (30%).":
            "Reduced load times through component and state optimization (30%).",
        "Liderazgo técnico en proyectos frontend / del equipo de desarrollo.":
            "Technical leadership of frontend projects and the development team.",
        "Mejora de eficiencia del equipo mediante buenas prácticas y sprints (25%).":
            "Improved team efficiency by 25% through best practices and sprints.",
        "Manejo de estado con NgRx para aplicaciones escalables.":
            "State management with NgRx for scalable applications.",
        "Entrega continua de features reduciendo tiempos de desarrollo (20%).":
            "Continuous feature delivery that reduced development time (20%).",
        "Código sostenible y escalable con equipos de backend, frontend, QA y DevOps.":
            "Sustainable, scalable code alongside backend, frontend, QA and DevOps teams.",
        "Creación de screens a partir de UX/maquetación.":
            "Built screens from UX designs and layouts.",
        "Dos proyectos para Compartamos Banco: captación y registro de grupos de préstamo para autorización y liberación de créditos.":
            "Two projects for Compartamos Banco: onboarding and registration of loan groups for credit approval and disbursement.",
        "Integración de Redux para estado.": "Integrated Redux for state management.",
        "Código bajo requerimientos y reglas de negocio.":
            "Wrote code to business requirements and rules.",
        "Diseño, planeación, codificación y despliegue de app móvil HVAC with Ionic.":
            "Designed, planned, coded and deployed the HVAC mobile app with Ionic.",
        "Gestión de inventario, estadísticas de rentabilidad y envío de productos a e-commerce.":
            "Inventory management, profitability statistics and product publishing to e-commerce.",
        "Responsable principal del frontend en un equipo de 4 personas.":
            "Main owner of the frontend in a team of 4 people.",
        "Entrega continua de features reduciendo tiempos de desarrollo mediante componentes reutilizables y patrones de arquitectura como Clean Architecture (20%).":
            "Continuous feature delivery that reduced development time through reusable components and architecture patterns such as Clean Architecture (20%).",
    },
    "es": {
        "Senior Frontend Developer": "Desarrollador Frontend Senior",
        "Technical Leader": "Líder técnico",
        "Senior Frontend Developer / Technical Leader": "Desarrollador Frontend Senior / Líder técnico",
        "React Native Developer": "Desarrollador React Native",
        "Frontend Developer": "Desarrollador Frontend",
        "Fullstack Developer (React Native, NodeJS)": "Desarrollador Fullstack (React Native, NodeJS)",
        "Angular Developer": "Desarrollador Angular",
        "Ionic Developer": "Desarrollador Ionic",
        "Cut loan-table load time from 8 s to 3 s (62%) with virtual scrolling and pagination.":
            "Reducción del tiempo de carga de las tablas de préstamos de 8 s a 3 s (62%) con virtual scroll y paginación.",
        "Cut Volaris Manifest flight load time from 10 s to 3 s (70%) with lazy loading and pagination.":
            "Reducción del tiempo de carga de vuelos en Volaris Manifest de 10 s a 3 s (70%) con lazy loading y paginación.",
    },
}


class FakeLLM:
    """Sustituye ``OpenAICvLlmBackend._chat_json``: optimizer fijo + traductor por diccionario.

    Devuelve texto JSON, como la API real.
    """

    def __init__(self, optimizer: dict, translations: Optional[dict] = None,
                 translate_hook: Optional[Callable[[list[str], str], list[str]]] = None):
        self.optimizer = optimizer
        self.translations = translations if translations is not None else TRANSLATIONS
        self.translate_hook = translate_hook
        self.optimizer_prompts: list[str] = []
        self.translation_batches: list[list[str]] = []

    def __call__(self, prompt: str, *, max_tokens: int = 0, n: int = 1, kind: str = "") -> str:
        if prompt.startswith("Translate each string"):
            locale = "es" if "into Spanish" in prompt.split("\n", 1)[0] else "en"
            items = json.loads(prompt.split("ITEMS\n", 1)[1])
            self.translation_batches.append(items)
            if self.translate_hook:
                return json.dumps({"items": self.translate_hook(items, locale)}, ensure_ascii=False)
            table = self.translations.get(locale, {})
            return json.dumps({"items": [table.get(text, text) for text in items]}, ensure_ascii=False)
        self.optimizer_prompts.append(prompt)
        return json.dumps(self.optimizer, ensure_ascii=False)


def fake_history_record(**kwargs) -> SimpleNamespace:
    return SimpleNamespace(
        id="test-id",
        cv_name="test",
        company_name=kwargs.get("company_name") or "",
        vacancy_url=kwargs.get("vacancy_url"),
    )


def prompt_profile(prompt: str) -> dict:
    return json.loads(prompt.split("CANDIDATE MASTER PROFILE\n", 1)[1])


def words(text: str) -> set[str]:
    return set(re.findall(r"\w+", text.lower()))
