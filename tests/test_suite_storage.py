import json

from suite_storage import (
    fusionar_cliente,
    guardar_json_atomico,
    leer_clientes,
    normalizar_nif,
)


def test_normalizar_nif_elimina_separadores_y_unifica_mayusculas():
    assert normalizar_nif(" b-12 345.678 ") == "B12345678"


def test_conflicto_conserva_valor_y_propone_alternativa(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    fusionar_cliente({"nif": "B-12345678", "nombre": "Uno"}, "escaner")
    resultado = fusionar_cliente(
        {"nif": "B12345678", "nombre": "Dos"}, "directorio_compartido"
    )

    assert resultado["nombre"] == "Uno"
    assert resultado["conflictos"]["nombre"] == ["Uno", "Dos"]
    assert resultado["metadatos"]["nombre"]["origen"] == "escaner"
    assert resultado["metadatos"]["nombre"]["fecha"]


def test_clientes_se_guardan_indexados_por_nif_normalizado(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    fusionar_cliente({"nif": " 12345678-z ", "nombre": "Ana"}, "escaner")

    clientes = leer_clientes()

    assert list(clientes) == ["12345678Z"]
    assert clientes["12345678Z"]["nif"] == "12345678Z"


def test_guardar_json_atomico_reemplaza_el_archivo_completo(tmp_path):
    ruta = tmp_path / "datos.json"
    ruta.write_text('{"viejo": true}', encoding="utf-8")

    guardar_json_atomico(ruta, {"nuevo": "sí"})

    assert json.loads(ruta.read_text(encoding="utf-8")) == {"nuevo": "sí"}
    assert not ruta.with_suffix(".json.tmp").exists()


def test_cliente_sin_nif_se_rechaza(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    try:
        fusionar_cliente({"nombre": "Sin identificar"}, "escaner")
    except ValueError as error:
        assert "NIF" in str(error)
    else:
        raise AssertionError("Un cliente compartido sin NIF no debe guardarse")
