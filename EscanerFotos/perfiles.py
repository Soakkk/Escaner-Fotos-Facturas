"""Perfiles locales de controles y destino del escáner."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json

from suite_storage import directorio_suite, guardar_json_atomico


SCHEMA_PERFILES = 1


@dataclass(frozen=True)
class PerfilEscaneo:
    nombre: str
    filtro: int
    intensidad: int = 50
    brillo: int = 0
    contraste: int = 0
    nitidez: int = 0
    destino: str = ""


def _iniciales() -> dict[str, PerfilEscaneo]:
    return {
        "Factura": PerfilEscaneo("Factura", 0),
        "DNI": PerfilEscaneo("DNI", 2),
        "Documento": PerfilEscaneo("Documento", 0),
    }


def _ruta_perfiles():
    return directorio_suite() / "perfiles-escaner.json"


def cargar_perfiles() -> dict[str, PerfilEscaneo]:
    perfiles = _iniciales()
    try:
        documento = json.loads(_ruta_perfiles().read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, ValueError, TypeError):
        return perfiles
    if documento.get("schema_version") != SCHEMA_PERFILES:
        return perfiles
    for nombre, datos in documento.get("perfiles", {}).items():
        try:
            perfil = PerfilEscaneo(**datos)
        except (TypeError, ValueError):
            continue
        perfiles[nombre] = perfil
    return perfiles


def guardar_perfil(perfil: PerfilEscaneo) -> None:
    perfiles = cargar_perfiles()
    perfiles[perfil.nombre] = perfil
    guardar_json_atomico(
        _ruta_perfiles(),
        {
            "schema_version": SCHEMA_PERFILES,
            "perfiles": {nombre: asdict(valor) for nombre, valor in perfiles.items()},
        },
    )
