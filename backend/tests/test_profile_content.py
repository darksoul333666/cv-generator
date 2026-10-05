"""La pantalla Skills puede reemplazar la identidad y la trayectoria del maestro."""

import unittest

from fastapi import HTTPException

from app.career_kb import ProfileContentIn, apply_profile_content
from app.locale_util import education_line


def _raw() -> dict:
    return {
        "profile": {
            "fullName": "Persona Ejemplo",
            "professionalTitles": ["Developer"],
            "summary": "Resumen viejo",
            "contact": {
                "email": {
                    "value": "viejo@example.com",
                    "status": "documented",
                    "userValidated": False,
                    "candidates": [],
                },
                "phone": {"value": "111", "status": "documented", "userValidated": False, "candidates": []},
                "linkedin": {"value": "in/viejo", "status": "documented", "userValidated": False, "candidates": []},
                "location": {"value": "Ciudad", "status": "documented", "userValidated": False, "candidates": []},
            },
        },
        "experience": [
            {
                "id": "exp_old",
                "company": "Acme",
                "roles": ["Dev"],
                "employmentType": "full-time",
                "startDate": "2020-01",
                "endDate": "2021-01",
                "current": False,
                "dateStatus": "verified",
                "sourceValues": {},
                "userValidated": False,
                "conflicts": [],
                "domain": [],
                "responsibilities": ["Hacía cosas"],
                "technologies": ["Java"],
                "achievements": [],
                "evidence": [],
                "sourceRefs": [],
                "evidenceLevel": "documented",
                "sourceCount": 1,
            }
        ],
        "projects": [
            {
                "id": "project_old",
                "name": "Viejo",
                "type": "web",
                "description": "x",
                "technologies": [],
            }
        ],
        "education": [],
        "certifications": [],
        "languages": [],
        "metrics": [
            {
                "id": "metric_old",
                "value": 10,
                "unit": "percent",
                "type": "old",
                "description": "métrica de Acme",
                "company": "Acme",
                "project": "",
                "experienceId": "exp_old",
                "status": "claimed",
                "confidence": "low",
                "evidenceLevel": "claimed",
                "sourceCount": 1,
                "userValidated": False,
                "safeForCV": True,
                "requiresUserValidation": True,
            }
        ],
        "careerTimeline": [],
        "positioningProfiles": {
            "dev": {
                "priorityExperience": ["exp_old"],
                "priorityExperienceLabels": ["Acme"],
                "priorityProjects": ["project_old"],
            }
        },
        "yearsOfExperience": {},
    }


class ProfileContentTests(unittest.TestCase):
    def test_profile_content_replaces_identity_and_drops_old_employer(self):
        raw = _raw()
        content = ProfileContentIn.model_validate(
            {
                "profile": {
                    "fullName": "Ana Ruiz",
                    "professionalTitles": ["Backend Engineer"],
                    "summary": "Construye APIs.",
                    "email": "ana@example.com",
                    "phone": "555",
                    "linkedin": "in/ana",
                    "location": "CDMX",
                },
                "experience": [
                    {
                        "id": "exp_nueva",
                        "company": "Nueva SA",
                        "roles": ["Backend Engineer"],
                        "employmentType": "full-time",
                        "startDate": "2022-03",
                        "endDate": None,
                        "current": True,
                        "responsibilities": ["APIs en Python"],
                        "technologies": ["Python"],
                        "achievements": [
                            {
                                "description": "Bajó la latencia",
                                "metricValue": 20,
                                "metricUnit": "percent",
                            }
                        ],
                    }
                ],
                "projects": [],
                "education": [
                    {
                        "id": "edu_lic",
                        "degree": "Licenciatura en Informática",
                        "institution": "UNAM",
                        "startDate": "2016",
                        "endDate": "2020",
                        "graduationYear": 2020,
                    }
                ],
                "certifications": [
                    {"id": "cert_aws", "name": "AWS Cloud", "issuer": "AWS", "year": 2023}
                ],
                "languages": [{"id": "lang_es", "language": "Español", "level": "nativo"}],
            }
        )
        apply_profile_content(raw, content)

        self.assertEqual(raw["profile"]["fullName"], "Ana Ruiz")
        self.assertEqual(raw["profile"]["contact"]["email"]["value"], "ana@example.com")
        self.assertEqual([ex["company"] for ex in raw["experience"]], ["Nueva SA"])
        self.assertTrue(raw["experience"][0]["current"])
        self.assertEqual(raw["experience"][0]["achievements"][0]["metric"]["value"], 20)
        self.assertEqual(raw["projects"], [])
        self.assertEqual(raw["education"][0]["degree"], "Licenciatura en Informática")
        self.assertEqual(raw["metrics"][0]["company"], "Nueva SA")
        self.assertEqual(raw["metrics"][0]["value"], 20)
        self.assertEqual(raw["positioningProfiles"]["dev"]["priorityExperience"], [])
        line = education_line({"education": raw["education"]}, "en")
        self.assertIn("Licenciatura en Informática", line)
        self.assertNotIn("Associate Degree", line)

    def test_profile_content_rejects_experience_without_role(self):
        raw = _raw()
        content = ProfileContentIn.model_validate(
            {
                "profile": {
                    "fullName": "Ana Ruiz",
                    "professionalTitles": ["Backend Engineer"],
                    "summary": "",
                    "email": "",
                    "phone": "",
                    "linkedin": "",
                    "location": "",
                },
                "experience": [
                    {
                        "id": "exp_nueva",
                        "company": "Nueva SA",
                        "roles": [],
                        "current": False,
                    }
                ],
            }
        )
        with self.assertRaises(HTTPException) as exc:
            apply_profile_content(raw, content)
        self.assertEqual(exc.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
