import unittest

from app.locale_util import attach_percent_signs, percent_metric_values


MASTER = {
    "metrics": [
        {"value": 25.0, "unit": "percent", "safeForCV": True},
        {"value": 30.0, "unit": "percent", "safeForCV": True},
        {"value": 7, "unit": "years", "safeForCV": True},
    ]
}


class PercentSignTests(unittest.TestCase):
    def test_bare_decimals_from_openai_become_percent(self):
        values = percent_metric_values(MASTER)
        text = (
            "7+ años como Senior Full Stack Engineer. "
            "En UffPay lideré mejoras que redujeron errores en flujos de pago en 25.0 "
            "y optimicé tiempos de respuesta de APIs en 30.0."
        )
        out = attach_percent_signs(text, values)
        self.assertIn("en 25%", out)
        self.assertIn("en 30%.", out)
        self.assertIn("7+ años", out)
        self.assertNotIn("25.0", out)
        self.assertNotIn("30.0", out)

    def test_existing_percent_and_years_stay(self):
        values = percent_metric_values(MASTER)
        text = "Redujo errores un 25% y lleva 7 años. En 2025 usó AWS."
        self.assertEqual(attach_percent_signs(text, values), text)


if __name__ == "__main__":
    unittest.main()
