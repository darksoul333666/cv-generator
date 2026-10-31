"""Migración del perfil: separa las notas internas de los datos.

Antes, cada empleo, proyecto o estudio tenía un ``evidence[]`` que mezclaba rutas de archivos,
preguntas abiertas («UNRESOLVED: …») y confirmaciones del usuario, y el perfil guardaba su
propio historial (``userValidation.resolved``, ``sourceValues``, ``originalValues``,
``sourceCount``). Después de migrar:

- ``openQuestions``: lo que falta saber. Va al modelo como «no lo afirmes».
- ``notes``: confirmaciones y aclaraciones del usuario.
- las rutas de archivos se quitan cuando ``sourceRefs`` ya nombra la fuente.
- ``sourceCount`` se quita (se cuenta de ``sourceRefs``).
- lo que fue verdad antes pasa a ``profile_history.json``.

Uso::

    python -m app.migrate_profile            # migra knowledge_base/master_profile.json
    python -m app.migrate_profile --dry-run  # solo dice qué cambiaría

No importa pydantic: corre con el Python del sistema.
"""

from __future__ import annotations

import json
import re
import sys
from typing import Any

_PATH_RE = re.compile(r"^(?:cvs|backend|Desktop|frontend)/|\.(?:pdf|json|md|docx|txt)$", re.IGNORECASE)
_UNRESOLVED_RE = re.compile(r"\bUNRESOLVED:\s*", re.IGNORECASE)
# Bitácora de otras sesiones que no dice nada del dato.
_NOISE_RE = re.compile(
    r"^(?:User project update \d{4}-\d{2}-\d{2}|Actualización \d{4}-\d{2}-\d{2}: no hubo hechos nuevos)",
    re.IGNORECASE,
)
_ITEM_SECTIONS = ("experience", "projects", "education", "certifications", "languages")


def _split_evidence(item: dict[str, Any]) -> dict[str, int]:
    counts = {"paths": 0, "questions": 0, "notes": 0}
    evidence = item.pop("evidence", None)
    if not isinstance(evidence, list):
        return counts
    questions: list[str] = list(item.get("openQuestions") or [])
    notes: list[str] = list(item.get("notes") or [])
    has_refs = bool(item.get("sourceRefs"))
    for raw_entry in evidence:
        text = str(raw_entry).strip()
        if not text or _NOISE_RE.search(text):
            continue
        if _PATH_RE.search(text) and " " not in text.split("/")[0]:
            if has_refs:
                counts["paths"] += 1
                continue
            notes.append(f"Fuente: {text}")
            counts["notes"] += 1
            continue
        parts = _UNRESOLVED_RE.split(text)
        before, rest = parts[0].strip(), [p.strip().rstrip(".") for p in parts[1:] if p.strip()]
        if before:
            notes.append(before)
            counts["notes"] += 1
        for question in rest:
            if question and question not in questions:
                questions.append(question)
                counts["questions"] += 1
    if questions:
        item["openQuestions"] = questions
    if notes:
        item["notes"] = notes
    return counts


def _drop_source_count(node: Any) -> int:
    dropped = 0
    if isinstance(node, dict):
        if "sourceCount" in node:
            node.pop("sourceCount")
            dropped += 1
        for value in node.values():
            dropped += _drop_source_count(value)
    elif isinstance(node, list):
        for value in node:
            dropped += _drop_source_count(value)
    return dropped


def migrate(raw: dict[str, Any]) -> tuple[dict[str, Any], list[dict], dict[str, Any], dict[str, int]]:
    """Devuelve (perfil migrado, decisiones para el historial, valores anteriores, conteos).

    Modifica ``raw`` en el lugar."""
    stats = {"paths": 0, "questions": 0, "notes": 0, "sourceCount": 0, "previousValues": 0, "resolved": 0}
    previous: dict[str, Any] = {}

    for section in _ITEM_SECTIONS:
        for item in raw.get(section) or []:
            if not isinstance(item, dict):
                continue
            for key, value in _split_evidence(item).items():
                stats[key] += value
            old = {k: item.pop(k) for k in ("sourceValues", "originalValues") if k in item}
            if any(old.values()):
                previous[f"{section}.{item.get('id')}"] = old
                stats["previousValues"] += 1

    yoe = raw.get("yearsOfExperience")
    if isinstance(yoe, dict) and "sourceValues" in yoe:
        values = yoe.pop("sourceValues")
        if values:
            previous["yearsOfExperience"] = {"sourceValues": values}
            stats["previousValues"] += 1

    resolved: list[dict] = []
    uv = raw.get("userValidation")
    if isinstance(uv, dict):
        resolved = [r for r in uv.pop("resolved", None) or [] if isinstance(r, dict)]
        uv.pop("lastUpdated", None)
        stats["resolved"] = len(resolved)

    stats["sourceCount"] = _drop_source_count(raw)
    return raw, resolved, previous, stats


def main(argv: list[str]) -> int:
    from .profile_history import append_history
    from .profile_store import dumps_profile, profile_path, read_profile

    dry = "--dry-run" in argv
    path = profile_path()
    raw = read_profile(path)
    raw, resolved, previous, stats = migrate(raw)
    print(json.dumps(stats, ensure_ascii=False))
    if dry:
        return 0
    from .profile_store import backup_profile

    backup_profile(path)
    append_history(resolved, previous, path=path.parent / "profile_history.json")
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(dumps_profile(raw), encoding="utf-8")
    import os

    os.replace(tmp, path)
    print(f"Listo: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
