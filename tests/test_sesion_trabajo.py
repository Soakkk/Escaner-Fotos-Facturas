import json

from sesion_trabajo import borrar_sesion, guardar_sesion, leer_sesion


def test_sesion_roundtrip_versionada(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    datos = {"actual": "foto-2.jpg", "cola": ["foto-3.jpg"], "paginas": ["abc"]}

    guardar_sesion(datos)

    assert leer_sesion() == datos
    guardado = json.loads(
        (tmp_path / "AsesoriaEMarin" / "Suite" / "escaner-sesion.json").read_text(
            encoding="utf-8"
        )
    )
    assert guardado["schema_version"] == 1


def test_sesion_corrupta_recupera_la_copia_anterior(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    guardar_sesion({"cola": ["primera.jpg"]})
    guardar_sesion({"cola": ["segunda.jpg"]})
    ruta = tmp_path / "AsesoriaEMarin" / "Suite" / "escaner-sesion.json"
    ruta.write_text("incompleto", encoding="utf-8")

    assert leer_sesion() == {"cola": ["primera.jpg"]}


def test_borrar_sesion_elimina_principal_y_copias(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    guardar_sesion({"n": 1})
    guardar_sesion({"n": 2})

    borrar_sesion()

    carpeta = tmp_path / "AsesoriaEMarin" / "Suite"
    assert not list(carpeta.glob("escaner-sesion.json*"))


def test_esquema_desconocido_no_se_interpreta(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    carpeta = tmp_path / "AsesoriaEMarin" / "Suite"
    carpeta.mkdir(parents=True)
    (carpeta / "escaner-sesion.json").write_text(
        json.dumps({"schema_version": 999, "datos": {"cola": []}}), encoding="utf-8"
    )

    assert leer_sesion() is None
