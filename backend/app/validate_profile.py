"""Valida el perfil maestro desde la terminal.

    python -m app.validate_profile [ruta]

Sale con código 1 si hay errores (el backend no lo guardaría) y 0 si solo hay avisos. Úsalo
después de que una IA o una edición a mano cambie ``master_profile.json``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from .profile_schema import validate_profile
from .profile_store import profile_path


def main(argv: list[str]) -> int:
    path = Path(argv[1]) if len(argv) > 1 else profile_path()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"No se pudo leer {path}: {exc}")
        return 1
    errors, warnings = validate_profile(raw)
    print(f"Perfil: {path}")
    print(f"Errores: {len(errors)} · Avisos: {len(warnings)}")
    for item in errors:
        print(f"  ERROR  {item}")
    for item in warnings:
        print(f"  aviso  {item}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
