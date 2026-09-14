"""Detección pura de archivos completos para carpetas vigiladas."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os


@dataclass
class ArchivoObservado:
    firma: tuple[int, int] | None = None
    repeticiones: int = 0

    def actualizar(self, size: int, mtime_ns: int) -> bool:
        nueva = (int(size), int(mtime_ns))
        self.repeticiones = self.repeticiones + 1 if nueva == self.firma else 1
        self.firma = nueva
        return self.repeticiones >= 2


def identidad_archivo(path: str) -> str:
    """Identidad estable del archivo, independiente de alias/ruta escrita."""
    stat = os.stat(path)
    identidad = f"{stat.st_dev}:{stat.st_ino}:{stat.st_size}:{stat.st_mtime_ns}"
    return hashlib.sha256(identidad.encode("ascii")).hexdigest()
