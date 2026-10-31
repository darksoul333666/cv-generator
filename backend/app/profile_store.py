"""Lectura, escritura, validación y respaldo del perfil maestro.

Un solo lugar para la ruta de ``knowledge_base`` (``CV_KB_DIR`` la cambia; los tests la usan
para trabajar sobre un perfil de prueba fijo), y para guardar con:

1. validación (``profile_schema.validate_profile``): un perfil con errores no se guarda;
2. respaldo con fecha del archivo anterior en ``knowledge_base/backups/`` (se guardan los
   últimos ``BACKUPS_KEPT``);
3. escritura atómica (``.tmp`` + ``os.replace``).
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

PROFILE_NAME = "master_profile.json"
BACKUPS_KEPT = 20


class ProfileValidationError(ValueError):
    """El perfil tiene errores de forma o de contenido y no se guardó."""

    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors[:5]) + (" …" if len(errors) > 5 else ""))
        self.errors = errors


def kb_dir() -> Path:
    override = os.getenv("CV_KB_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return Path(__file__).resolve().parent.parent / "knowledge_base"


def profile_path() -> Path:
    return kb_dir() / PROFILE_NAME


def backups_dir() -> Path:
    return kb_dir() / "backups"


def read_profile(path: Path | None = None) -> dict:
    target = path or profile_path()
    return json.loads(target.read_text(encoding="utf-8"))


def dumps_profile(raw: dict) -> str:
    return json.dumps(raw, ensure_ascii=False, indent=2) + "\n"


def backup_profile(path: Path | None = None) -> Path | None:
    """Copia el perfil actual a ``backups/`` con fecha y borra los respaldos más viejos."""
    source = path or profile_path()
    if not source.exists():
        return None
    folder = source.parent / "backups"
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    target = folder / f"{source.stem}-{stamp}.json"
    shutil.copy2(source, target)
    old = sorted(folder.glob(f"{source.stem}-*.json"))
    for extra in old[:-BACKUPS_KEPT]:
        try:
            extra.unlink()
        except OSError:
            logger.warning("[profile] no se pudo borrar el respaldo viejo %s", extra)
    return target


def write_profile(raw: dict, path: Path | None = None, *, validate: bool = True) -> list[str]:
    """Valida, respalda el archivo anterior y escribe. Devuelve los avisos de la validación."""
    from .profile_schema import validate_profile

    warnings: list[str] = []
    if validate:
        errors, warnings = validate_profile(raw)
        if errors:
            raise ProfileValidationError(errors)
    target = path or profile_path()
    backup_profile(target)
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(dumps_profile(raw), encoding="utf-8")
    os.replace(tmp, target)
    for warning in warnings:
        logger.info("[profile] aviso: %s", warning)
    return warnings
