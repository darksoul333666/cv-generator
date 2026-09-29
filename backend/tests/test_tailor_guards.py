"""El armado del CV no depende de que el modelo ordene, traduzca o recorte empleos."""

from app.llm.ollama_backend import _bullets_for_job, _ollama_result_to_cv
from app.locale_util import cert_names
from app.models import CvDocument
from app.skill_stack import build_stack_from_master


VACANCY = (
    "Senior React Native Developer. TypeScript and JavaScript. "
    "Ship iOS and Android apps. Jest. React JS."
)


def _base() -> CvDocument:
    return CvDocument(id="cv", name="Jairo", email="a@b.c", title="Developer")


def _master() -> dict:
    return {
        "name": "Jairo Antonio",
        "contact": {"email": "a@b.c", "phone": "1", "linkedin": "in/jairo"},
        "allowed_companies": ["UffPay", "Grainchain Inc", "Lumston", "Old Shop"],
        "experience": [
            {
                "company": "UffPay",
                "positions": ["Frontend", "React Native Developer"],
                "start_date": "2026-04",
                "end_date": None,
                "current": True,
                "technologies": ["React Native"],
                "responsibilities": ["App fintech en React Native para pagos"],
            },
            {
                "company": "Grainchain Inc",
                "positions": ["Senior Frontend Developer"],
                "start_date": "2025-06",
                "end_date": "2026-04",
                "current": False,
                "technologies": ["Angular", "NgRx"],
                "achievements": [
                    {"description": "Tablas", "metric": {"value": 35, "unit": "percent"}}
                ],
            },
            {
                "company": "Lumston",
                "positions": ["Full Stack / Frontend Developer"],
                "start_date": "2023-05",
                "end_date": "2025-06",
                "current": False,
                "technologies": ["React Native"],
                "responsibilities": ["Apps con React Native"],
            },
            {
                "company": "Old Shop",
                "positions": ["Mobile Developer"],
                "start_date": "2019-04",
                "end_date": "2019-11",
                "current": False,
                "technologies": ["Ionic"],
            },
        ],
        "skills": {
            "languages": ["TypeScript", "JavaScript (ES6+)"],
            "frontend": ["Angular", "Angular (14–20)", "React", "Vue", "Next.js"],
            "mobile": ["React Native"],
            "payments": ["Stripe", "Cybersource"],
            "backend": ["AdonisJS", "Node.js"],
            "testing": ["Jest", "Karma", "Jasmine"],
            "state": ["Redux", "NgRx"],
            "styling": ["Angular Material", "NativeWind"],
        },
        "certifications": [
            {"name": "Stripe Developer Certification", "year": 2024},
            {"name": "Tercer lugar — Olimpiada de Programación", "year": 2017},
            {"name": "Campeonato Estatal de Ortografía — Primer lugar", "year": 2014},
            {"name": "Olimpiada de Conocimiento Nivel Media Superior — Finalista", "year": 2016},
            {"name": "Olimpiada de Conocimiento Infantil — Primer lugar", "year": 2011},
        ],
    }


def test_experience_stays_recent_first_and_keeps_omitted_jobs():
    data = {
        "target_role": "Senior React Native Developer",
        "summary": "Senior React Native developer with 7+ years shipping iOS and Android.",
        "experience": [
            {
                "company": "Lumston",
                "position": "Full Stack / Frontend Developer",
                "bullets": ["Shipped React Native checkout flows and cut load time (30%)."],
            },
            {
                "company": "UffPay",
                "position": "Frontend",
                "bullets": ["Built a React Native payments app for iOS and Android."],
            },
        ],
    }
    cv = _ollama_result_to_cv(data, _base(), _master(), "en", VACANCY)
    assert [job.company for job in cv.experience] == ["UffPay", "Grainchain Inc", "Lumston"]
    assert cv.experience[0].role == "React Native Developer"
    assert cv.experience[0].bullets == ["Built a React Native payments app for iOS and Android."]
    grain = cv.experience[1]
    assert grain.bullets == ["Shipped production features with Angular and NgRx (35%)."]


def test_off_target_job_uses_the_real_work():
    source = {
        "technologies": ["Ionic"],
        "responsibilities": [
            "Diseño, planeación, codificación y despliegue de app móvil HVAC",
            "Gestión de inventario, estadísticas de rentabilidad y envío de productos a e-commerce",
            "UX/maquetación",
        ],
        "achievements": [],
    }
    bullets = _bullets_for_job(source, [], "Senior React Native Developer", "Ionic Developer", "es")
    assert len(bullets) == 1
    assert "Trabajo en producción" not in bullets[0]
    assert "HVAC" in bullets[0]
    assert "Ionic" in bullets[0]
    assert "inventario" in bullets[0].lower()


def test_skills_follow_the_vacancy_stack():
    stack = build_stack_from_master(
        _master(),
        VACANCY,
        overlay=["Jest", "mobile", "payments", "Cybersource", "Performance Optimization"],
    )
    frontend = stack.frontend.lower()
    assert "react native" in frontend
    assert "angular" not in frontend
    assert "vue" not in frontend
    assert "(js)" not in frontend
    assert "javascript (es6+)" in frontend
    backend = stack.backend.lower()
    assert "cybersource" not in backend
    assert "stripe" not in backend
    assert "mobile" not in backend
    assert "jest" in stack.testing.lower()
    assert "karma" not in stack.testing.lower()
    assert "ngrx" not in stack.state.lower()


def test_school_awards_drop_and_programming_olympiad_stays():
    names = cert_names(_master(), "en")
    blob = " ".join(names).lower()
    assert "stripe" in blob
    assert "programming olympiad" in blob
    assert "spelling" not in blob
    assert "children" not in blob
    assert "high school" not in blob

