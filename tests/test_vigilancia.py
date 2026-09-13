import os

from vigilancia import ArchivoObservado, identidad_archivo


def test_archivo_solo_esta_listo_tras_dos_observaciones_iguales():
    archivo = ArchivoObservado()
    assert not archivo.actualizar(100, 1)
    assert archivo.actualizar(100, 1)


def test_cambio_de_firma_reinicia_la_estabilidad():
    archivo = ArchivoObservado()
    assert not archivo.actualizar(100, 1)
    assert not archivo.actualizar(101, 2)
    assert archivo.actualizar(101, 2)


def test_identidad_detecta_dos_rutas_al_mismo_archivo(tmp_path):
    original = tmp_path / "foto.jpg"
    alias = tmp_path / "alias.jpg"
    original.write_bytes(b"foto completa")
    os.link(original, alias)

    assert identidad_archivo(str(original)) == identidad_archivo(str(alias))
