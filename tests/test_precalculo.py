import cv2
import numpy as np
import pytest
import imagen as motor
import precalculo

from precalculo import PrecalculoResultado, calcular_precalculo


def test_precalculo_prepara_miniatura_sin_alterar_el_archivo(tmp_path):
    ruta = tmp_path / "plana.png"
    imagen = np.full((240, 320, 3), 127, dtype=np.uint8)
    assert cv2.imwrite(str(ruta), imagen)
    bytes_originales = ruta.read_bytes()

    resultado = calcular_precalculo(str(ruta), lado_miniatura=80)

    assert isinstance(resultado, PrecalculoResultado)
    assert resultado.ruta == str(ruta)
    assert max(resultado.miniatura.shape[:2]) <= 80
    assert resultado.puntos is None
    assert resultado.rotacion == 0
    assert ruta.read_bytes() == bytes_originales


@pytest.mark.parametrize('confianza,esperado', [(0.14, 0), (0.15, 90), (0.9, 90)])
def test_precalculo_respeta_confianza_de_la_accion_original(tmp_path, monkeypatch, confianza, esperado):
    ruta = tmp_path / 'orientacion.png'
    assert cv2.imwrite(str(ruta), np.full((100, 160, 3), 127, np.uint8))
    detector = lambda imagen: (90, confianza)
    monkeypatch.setattr(motor, 'detectar_orientacion_texto', detector)
    monkeypatch.setattr(precalculo, 'detectar_orientacion_texto', detector, raising=False)

    assert calcular_precalculo(str(ruta)).rotacion == esperado
