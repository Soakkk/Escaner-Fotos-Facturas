"""Caracterización del motor de imagen en el commit base de la suite."""

import hashlib

import cv2
import numpy as np

from imagen import aplicar_pipeline, codificar_pagina, componer_dni


def _foto_documento():
    alto, ancho = 180, 240
    y, x = np.indices((alto, ancho))
    foto = np.empty((alto, ancho, 3), dtype=np.uint8)
    foto[:, :, 0] = (31 + x * 3 + y) % 256
    foto[:, :, 1] = (79 + x + y * 2) % 256
    foto[:, :, 2] = (127 + x * 2 + y * 3) % 256
    cv2.rectangle(foto, (28, 24), (211, 155), (238, 238, 238), -1)
    for fila in range(48, 140, 18):
        cv2.line(foto, (52, fila), (188, fila), (35, 35, 35), 2)
    return foto


def test_pipeline_actual_no_cambia():
    salida = aplicar_pipeline(_foto_documento(), 0, 0, 0, 0, 50)
    # OpenCV 4.14 produce dos rasterizaciones estables según el backend de
    # plataforma. Ambas corresponden al mismo motor anterior sin modificar:
    # la primera se caracteriza en macOS y la segunda en Windows.
    assert hashlib.sha256(salida.tobytes()).hexdigest() in {
        "5a5c4f518a9fca0f41ac77b8ad8e74c85ecffa17f978046ca83f49c3d236b65e",
        "b2da45f2185d65efeaa815f70d00fad1ecee31a61fad3104ed35c5f24eb1873a",
    }


def test_codificacion_actual_no_cambia():
    pagina = np.full((48, 64, 3), 255, dtype=np.uint8)
    pagina[8:40, 15:18] = 0
    pagina[20:23, 15:52] = 0
    assert hashlib.sha256(codificar_pagina(pagina)).hexdigest() == (
        "f93717ba6581f09e637fef1e8da1de8448a2181f476cdd6a8fb267cce2ffb2b0"
    )


def test_composicion_dni_actual_no_cambia():
    cara_a = np.full((60, 96, 3), (15, 90, 210), dtype=np.uint8)
    cara_b = np.full((54, 88, 3), (180, 70, 25), dtype=np.uint8)
    salida = componer_dni(cara_a, cara_b, ancho=320, alto=452)
    assert hashlib.sha256(salida.tobytes()).hexdigest() == (
        "89cce8fd2830edabffa30e76b507393a4dd35d8ce9895661b77660ec18065888"
    )
