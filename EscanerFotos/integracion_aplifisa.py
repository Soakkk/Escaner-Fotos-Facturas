"""Localiza y abre Facturas a Aplifisa con un PDF generado por el escáner."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def candidatos_ejecutable(configurado: str = "") -> list[str]:
    candidatos = []
    if configurado:
        candidatos.append(configurado)

    if sys.platform == "win32":
        for variable in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
            base = os.environ.get(variable)
            if not base:
                continue
            candidatos.extend([
                os.path.join(base, "FacturasAplifisa", "FacturasAplifisa.exe"),
                os.path.join(base, "Programs", "FacturasAplifisa", "FacturasAplifisa.exe"),
            ])
        candidatos.append(os.path.join(os.path.dirname(sys.executable),
                                       "FacturasAplifisa.exe"))

    vistos = set()
    return [c for c in candidatos
            if c and not (c in vistos or vistos.add(c))]


def localizar_aplifisa(configurado: str = "") -> str | None:
    for candidato in candidatos_ejecutable(configurado):
        if os.path.isfile(candidato):
            return os.path.abspath(candidato)
    return None


def comando_aplifisa(ejecutable: str, ruta_pdf: str) -> list[str]:
    """Construye el comando; separado para poder probarlo sin abrir procesos."""
    return [os.path.abspath(ejecutable), "--import", os.path.abspath(ruta_pdf)]


def lanzar_aplifisa(ejecutable: str, ruta_pdf: str):
    if not os.path.isfile(ejecutable):
        raise FileNotFoundError("No se encuentra FacturasAplifisa.exe")
    if not os.path.isfile(ruta_pdf):
        raise FileNotFoundError("No se encuentra el PDF que se va a enviar")
    kwargs = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    return subprocess.Popen(
        comando_aplifisa(ejecutable, ruta_pdf),
        cwd=str(Path(ejecutable).resolve().parent),
        close_fds=True,
        **kwargs,
    )
