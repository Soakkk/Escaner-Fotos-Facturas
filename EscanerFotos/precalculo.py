"""Preparación anticipada de la siguiente foto sin alterar el resultado."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib

from PySide6.QtCore import QThread, Signal

from imagen import (
    detectar_documento,
    auto_orientar_documento,
    leer_imagen,
    miniatura_archivo,
)


@dataclass(frozen=True)
class PrecalculoResultado:
    ruta: str
    miniatura: object
    puntos: object | None
    rotacion: int
    firma_imagen: str = ""


def firma_imagen(imagen) -> str:
    digestor = hashlib.sha256(str((imagen.shape, imagen.dtype)).encode('ascii'))
    digestor.update(imagen.tobytes())
    return digestor.hexdigest()


def calcular_precalculo(ruta: str, lado_miniatura: int = 96) -> PrecalculoResultado:
    imagen = leer_imagen(ruta)
    miniatura = miniatura_archivo(ruta, lado_miniatura)
    puntos = detectar_documento(imagen)
    _, rotacion = auto_orientar_documento(imagen)
    return PrecalculoResultado(ruta, miniatura, puntos, int(rotacion), firma_imagen(imagen))


class TrabajadorPrecalculo(QThread):
    listo = Signal(object)
    fallo = Signal(str, str)

    def __init__(self, ruta: str, parent=None):
        super().__init__(parent)
        self.ruta = ruta

    def run(self):
        try:
            self.listo.emit(calcular_precalculo(self.ruta))
        except Exception as error:
            self.fallo.emit(self.ruta, str(error))
