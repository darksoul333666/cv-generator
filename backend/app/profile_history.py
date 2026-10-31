"""Historial de decisiones sobre el perfil, fuera del perfil.

El perfil maestro guarda lo que es verdad hoy. Lo que fue verdad antes (qué decían los CVs
viejos, qué fechas tenía un empleo antes de corregirlas, cuándo confirmaste un dato) va a
``knowledge_base/profile_history.json``. Ningún paso del CV lo lee; sirve para auditar.

Los editores no escriben el archivo directo: ``remember`` deja la entrada en el perfil bajo
``PENDING_KEY`` y ``profile_store.write_profile`` la saca y la guarda en el historial solo
si el perfil se guardó.
"""

from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Optional

HISTORY_NAME = "profile_history.json"
PENDING_KEY = "_historyPending"


def history_path(kb: Optional[Path] = None) -> Path:
    from .profile_store import kb_dir

    return (kb or kb_dir()) / HISTORY_NAME


def read_history(path: Optional[Path] = None) -> dict[str, Any]:
    target = path or history_path()
    if not target.exists():
        return {"resolved": [], "previousValues": {}}
    data = json.loads(target.read_text(encoding="utf-8"))
    data.setdefault("resolved", [])
    data.setdefault("previousValues", {})
    return data


def remember(
    raw: dict[str, Any],
    field: str,
    resolved_value: str,
    previous: Optional[Iterable[Any]] = None,
    source: str = "user",
) -> None:
    """Anota una decisión del usuario; se guarda en el historial junto con el perfil."""
    raw.setdefault(PENDING_KEY, []).append(
        {
            "field": field,
            "previousValues": list(previous or []),
            "resolvedValue": resolved_value,
            "resolvedAt": date.today().isoformat(),
            "source": source,
        }
    )


def append_history(
    entries: list[dict[str, Any]],
    previous_values: Optional[dict[str, Any]] = None,
    path: Optional[Path] = None,
) -> None:
    if not entries and not previous_values:
        return
    target = path or history_path()
    data = read_history(target)
    data["resolved"].extend(entries)
    for key, value in (previous_values or {}).items():
        data["previousValues"].setdefault(key, value)
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, target)
