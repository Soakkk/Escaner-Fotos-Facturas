"""Almacenamiento local compartido por las aplicaciones de la asesoría."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from typing import Any


SCHEMA_CLIENTES = 1


def directorio_suite() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return base / "AsesoriaEMarin" / "Suite"


def normalizar_nif(valor: str) -> str:
    """Devuelve una clave estable sin espacios ni signos separadores."""
    return re.sub(r"[^0-9A-Z]", "", str(valor or "").strip().upper())


def guardar_json_atomico(ruta: Path, datos: dict[str, Any]) -> None:
    """Escribe JSON completo y durable antes de sustituir el destino."""
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_suffix(ruta.suffix + ".tmp")
    with temporal.open("w", encoding="utf-8") as archivo:
        json.dump(datos, archivo, ensure_ascii=False, indent=2, sort_keys=True)
        archivo.flush()
        os.fsync(archivo.fileno())
    os.replace(temporal, ruta)


def _ruta_clientes() -> Path:
    return directorio_suite() / "clientes.json"


def _leer_documento_clientes() -> dict[str, Any]:
    ruta = _ruta_clientes()
    if not ruta.exists():
        return {"schema_version": SCHEMA_CLIENTES, "clientes": {}}
    try:
        documento = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {"schema_version": SCHEMA_CLIENTES, "clientes": {}}
    if documento.get("schema_version") != SCHEMA_CLIENTES:
        return {"schema_version": SCHEMA_CLIENTES, "clientes": {}}
    clientes = documento.get("clientes")
    if not isinstance(clientes, dict):
        clientes = {}
    return {"schema_version": SCHEMA_CLIENTES, "clientes": clientes}


def leer_clientes() -> dict[str, dict[str, Any]]:
    return _leer_documento_clientes()["clientes"]


def fusionar_cliente(cliente: dict[str, Any], origen: str) -> dict[str, Any]:
    """Añade datos conocidos sin sustituir valores distintos ya confirmados."""
    nif = normalizar_nif(cliente.get("nif", ""))
    if not nif:
        raise ValueError("El cliente necesita un NIF para compartir sus datos")

    documento = _leer_documento_clientes()
    clientes = documento["clientes"]
    existente = clientes.get(nif, {"nif": nif, "metadatos": {}, "conflictos": {}})
    existente.setdefault("metadatos", {})
    existente.setdefault("conflictos", {})
    fecha = datetime.now(timezone.utc).isoformat()

    for campo, valor in cliente.items():
        if campo == "nif" or valor in (None, ""):
            continue
        if campo not in existente or existente[campo] in (None, ""):
            existente[campo] = valor
            existente["metadatos"][campo] = {"origen": origen, "fecha": fecha}
        elif existente[campo] != valor:
            alternativas = existente["conflictos"].setdefault(
                campo, [existente[campo]]
            )
            if valor not in alternativas:
                alternativas.append(valor)

    existente["metadatos"].setdefault(
        "nif", {"origen": origen, "fecha": fecha}
    )
    clientes[nif] = existente
    guardar_json_atomico(_ruta_clientes(), documento)
    return existente
