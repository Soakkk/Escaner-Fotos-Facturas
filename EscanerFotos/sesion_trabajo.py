"""Persistencia recuperable de la sesión activa del escáner."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any

from suite_storage import directorio_suite, guardar_json_atomico


SCHEMA_SESION = 1
COPIAS_ROTATIVAS = 2


def _ruta_sesion() -> Path:
    return directorio_suite() / "escaner-sesion.json"


def _ruta_copia(numero: int) -> Path:
    return Path(f"{_ruta_sesion()}.bak{numero}")


def guardar_sesion(datos: dict[str, Any]) -> None:
    ruta = _ruta_sesion()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    for numero in range(COPIAS_ROTATIVAS, 1, -1):
        anterior = _ruta_copia(numero - 1)
        if anterior.exists():
            os.replace(anterior, _ruta_copia(numero))
    if ruta.exists():
        os.replace(ruta, _ruta_copia(1))
    guardar_json_atomico(
        ruta,
        {
            "schema_version": SCHEMA_SESION,
            "guardado_en": datetime.now(timezone.utc).isoformat(),
            "datos": datos,
        },
    )


def leer_sesion() -> dict[str, Any] | None:
    for ruta in (_ruta_sesion(), *(_ruta_copia(n) for n in range(1, COPIAS_ROTATIVAS + 1))):
        try:
            documento = json.loads(ruta.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, ValueError, TypeError):
            continue
        if documento.get("schema_version") == SCHEMA_SESION and isinstance(
            documento.get("datos"), dict
        ):
            return documento["datos"]
    return None


def borrar_sesion() -> None:
    rutas = [_ruta_sesion(), *(_ruta_copia(n) for n in range(1, COPIAS_ROTATIVAS + 1))]
    rutas.append(_ruta_sesion().with_suffix(_ruta_sesion().suffix + ".tmp"))
    for ruta in rutas:
        try:
            ruta.unlink()
        except FileNotFoundError:
            pass
