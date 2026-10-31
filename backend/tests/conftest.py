"""Fecha fija para las pruebas: los años de experiencia se calculan con las fechas visibles."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _fixed_today(monkeypatch):
    # Enero 2020 – octubre 2026 = 6.8 años visibles → «6+».
    monkeypatch.setattr("app.llm.cv_builder._today_ym", lambda: "2026-10")
