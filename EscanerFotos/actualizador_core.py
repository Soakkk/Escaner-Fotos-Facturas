"""Lógica pura del actualizador. Sin dependencias de Qt ni de red:
se puede importar y probar en cualquier máquina con solo la stdlib."""

import re
from dataclasses import dataclass


ESTADOS = {"checking", "downloading", "ready", "installing", "error"}


@dataclass
class CicloActualizacion:
    estado: str = "checking"

    def transicionar(self, nuevo: str) -> None:
        permitidos = {
            "checking": {"downloading", "error"},
            "downloading": {"ready", "error"},
            "ready": {"installing", "error"},
            "installing": {"error"},
            "error": set(),
        }
        if nuevo not in ESTADOS or nuevo not in permitidos[self.estado]:
            raise ValueError(f"Transición de actualización inválida: {self.estado} -> {nuevo}")
        self.estado = nuevo


def debe_comprobar(ahora, ultima, intervalo):
    return ultima is None or ahora - ultima >= intervalo


def parse_version(texto):
    """'v2.1.0' o '2.1' -> (2, 1, 0). Ignora la 'v' y cualquier sufijo no numérico."""
    nums = re.findall(r"\d+", texto or "")
    return tuple(int(n) for n in nums)


def es_mas_nueva(remota, local):
    """True si la versión remota es estrictamente mayor que la local."""
    a = parse_version(remota)
    b = parse_version(local)
    n = max(len(a), len(b))
    a = a + (0,) * (n - len(a))
    b = b + (0,) * (n - len(b))
    return a > b


def elegir_asset_exe(release):
    """Devuelve solo el instalador Inno Setup esperado, nunca otro EXE."""
    for asset in (release or {}).get("assets", []):
        nombre = str(asset.get("name", ""))
        if re.fullmatch(r"EscanerFotos-Setup-[0-9][0-9A-Za-z._-]*\.exe", nombre):
            return asset
    return None


def elegir_asset_sha256(release):
    """Devuelve el SHA-256 cuyo nombre corresponde al Setup seleccionado."""
    setup = elegir_asset_exe(release)
    if setup is None:
        return None
    esperado = str(setup["name"]) + ".sha256"
    for asset in (release or {}).get("assets", []):
        if str(asset.get("name", "")) == esperado:
            return asset
    return None


def parsear_sha256(texto):
    """Extrae el primer hash SHA-256 (64 caracteres hex) de un texto del
    estilo 'HASH  EscanerFotos-Setup-2.7.exe'. Devuelve el hash en minúsculas
    o None si no hay ninguno."""
    m = re.search(r"\b[0-9a-fA-F]{64}\b", texto or "")
    return m.group(0).lower() if m else None
