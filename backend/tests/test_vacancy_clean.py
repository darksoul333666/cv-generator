import unittest

from app.vacancy_clean import parse_pasted_vacancy, strip_indeed_search_chrome


SERP = """
Empleos de react native
Clasificar por: relevancia
AI-Augmented Product Developer
Postúlate rápidamente
Besta
Desde casa
$28,000 a $30,000 por mes
Full Stack Software Developer (LATAM)
Postúlate rápidamente
My VA Support
Desde casa
Quiero recibir las últimas ofertas de react native en mi email
Otros candidatos también buscaron:
react javascript desarrollador web
AI-Augmented Product Developer
Besta
Home Office (Desde casa)
$28,000 a $30,000 por mes
Postularse ahora
Detalles del empleo
$28,000 a $30,000 por mes
Caja de ahorro, Vales de despensa, Opción a contrato indefinido
Por tiempo indeterminado, Tiempo completo
De Home Office (Desde casa)
Descripción completa del empleo
Besta Arrendadora Automotriz
Misión del puesto
Construir plataformas en Next.js y dar soporte a la app en Flutter.
""".strip()


class IndeedSerpCleanTests(unittest.TestCase):
    def test_keeps_the_open_job_and_drops_the_result_list(self):
        cleaned = strip_indeed_search_chrome(SERP)
        self.assertIn("Misión del puesto", cleaned)
        self.assertIn("AI-Augmented Product Developer", cleaned)
        self.assertIn("Home Office (Desde casa)", cleaned)
        self.assertIn("$28,000 a $30,000 por mes", cleaned)
        self.assertNotIn("Postúlate rápidamente", cleaned)
        self.assertNotIn("My VA Support", cleaned)
        self.assertNotIn("Clasificar por", cleaned)
        self.assertNotIn("Otros candidatos", cleaned)
        self.assertNotIn("Caja de ahorro", cleaned)
        self.assertNotIn("Descripción completa del empleo", cleaned)

    def test_leaves_a_single_job_untouched(self):
        job = "Senior Engineer\nEmpresa: Besta\n\nConstruir APIs en Node.js."
        self.assertEqual(strip_indeed_search_chrome(job), job)

    def test_parse_pasted_uses_the_same_cut(self):
        parsed = parse_pasted_vacancy("Empresa: Besta\n" + SERP)
        self.assertEqual(parsed["company"], "Besta")
        self.assertNotIn("Postúlate rápidamente", parsed["text"])
        self.assertIn("Next.js", parsed["text"])


class SearchHeadingTests(unittest.TestCase):
    def test_rejects_linkedin_results_title(self):
        from app.vacancy_clean import looks_like_search_heading

        self.assertTrue(looks_like_search_heading('Empleos de «react»'))
        self.assertFalse(
            looks_like_search_heading(
                "Senior Frontend Engineer\nEmpresa: Acme\n\nConstruir interfaces en React."
            )
        )


if __name__ == "__main__":
    unittest.main()
