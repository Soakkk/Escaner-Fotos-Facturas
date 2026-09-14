from perfiles import PerfilEscaneo, cargar_perfiles, guardar_perfil


def test_perfil_factura_reproduce_los_valores_base():
    factura = cargar_perfiles()["Factura"]

    assert factura == PerfilEscaneo(
        nombre="Factura",
        filtro=0,
        intensidad=50,
        brillo=0,
        contraste=0,
        nitidez=0,
        destino="",
    )


def test_perfiles_iniciales_incluyen_factura_dni_y_documento():
    assert list(cargar_perfiles()) == ["Factura", "DNI", "Documento"]


def test_guardar_perfil_personalizado_es_recuperable():
    perfil = PerfilEscaneo("Tickets", 1, 72, 4, 8, 12, "C:/Lotes")

    guardar_perfil(perfil)

    assert cargar_perfiles()["Tickets"] == perfil
