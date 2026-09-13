import cv2
import numpy as np

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
