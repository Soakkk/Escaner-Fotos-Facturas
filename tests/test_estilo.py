"""El tema y los recursos (icono, marca de verificación) están completos."""

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon, QPalette
from PIL import Image
import numpy as np

_app = QApplication.instance() or QApplication([])

import estilo


def test_los_recursos_existen():
    for nombre in ("icono.ico", "icono.png", "check.png"):
        assert os.path.isfile(estilo.ruta_recurso(nombre)), nombre


def test_el_icono_carga():
    icono = QIcon(estilo.ruta_recurso("icono.ico"))
    assert not icono.isNull()
    assert icono.availableSizes(), "el .ico no trae tamaños incrustados"
    assert Image.open(estilo.ruta_recurso("icono.png")).size == (512, 512)
    assert {(16, 16), (32, 32), (48, 48), (256, 256)}.issubset(
        Image.open(estilo.ruta_recurso("icono.ico")).info["sizes"]
    )


def test_aplicar_tema_no_falla_y_define_qss():
    estilo.aplicar_tema(_app)
    assert _app.styleSheet() == estilo.QSS
    assert "QPushButton#btnPrimario" in estilo.QSS
    assert "QGroupBox" in estilo.QSS


def test_tokens_de_la_suite_son_exactos_y_llegan_a_la_paleta():
    assert (
        estilo.PAGE,
        estilo.CARD,
        estilo.INK,
        estilo.MUTED,
        estilo.BORDER,
        estilo.ACCENT,
        estilo.SUCCESS,
        estilo.WARNING,
        estilo.DANGER,
    ) == (
        "#F5F8FC",
        "#FFFFFF",
        "#24384D",
        "#5D7084",
        "#DCE5F0",
        "#326FA6",
        "#19724E",
        "#86500A",
        "#B43737",
    )
    estilo.aplicar_tema(_app)
    paleta = _app.palette()
    assert paleta.color(QPalette.ColorRole.Window).name().upper() == estilo.PAGE
    assert paleta.color(QPalette.ColorRole.Highlight).name().upper() == estilo.ACCENT
    assert '"Segoe UI Variable"' in estilo.QSS


def test_icono_comparte_rombo_azul_blanco_y_acento_dorado():
    imagen = np.asarray(Image.open(estilo.ruta_recurso("icono.png")).convert("RGBA"))
    assert imagen[0, 0, 3] == 0
    assert imagen[256, 256, 3] == 255
    opacos = imagen[:, :, 3] > 200
    blancos = opacos & (imagen[:, :, :3].min(axis=2) > 235)
    dorados = (
        opacos
        & (imagen[:, :, 0] > 210)
        & (imagen[:, :, 1] > 130)
        & (imagen[:, :, 1] < 210)
        & (imagen[:, :, 2] < 80)
    )
    assert blancos.sum() > 2_000
    assert dorados.sum() > 400
