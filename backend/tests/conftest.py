"""Configuración común de las pruebas.

- Fecha fija: los años de experiencia se calculan con las fechas visibles del CV.
- Perfil de prueba fijo: ``tests/fixtures/knowledge_base/master_profile.json`` es una copia
  congelada del perfil (31 oct 2026). Las pruebas no leen tu perfil real, así que no se rompen
  cada vez que lo editas. Cada sesión de pruebas trabaja sobre una copia temporal, para que
  ninguna prueba modifique el archivo de fixtures.

Para actualizar el perfil de prueba a propósito: copia ``knowledge_base/master_profile.json``
sobre el de fixtures y ajusta las pruebas que cambien.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

FIXTURE_KB = Path(__file__).resolve().parent / "fixtures" / "knowledge_base"


@pytest.fixture(scope="session", autouse=True)
def _fixture_kb(tmp_path_factory) -> Path:
    """Sesión completa sobre una copia del perfil de prueba (antes que cualquier fixture de módulo)."""
    target = tmp_path_factory.mktemp("knowledge_base")
    shutil.copy2(FIXTURE_KB / "master_profile.json", target / "master_profile.json")
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("CV_KB_DIR", str(target))
        yield target


@pytest.fixture(autouse=True)
def _fixed_today(monkeypatch):
    # Enero 2019 – octubre 2026: el perfil de prueba incluye CTZ (2019).
    monkeypatch.setattr("app.llm.cv_years._today_ym", lambda: "2026-10")
