from actualizador_core import parse_version
from actualizador_core import es_mas_nueva
from actualizador_core import CicloActualizacion, debe_comprobar, elegir_asset_exe
import actualizador

def test_parse_version_con_prefijo_v():
    assert parse_version("v2.1.0") == (2, 1, 0)

def test_parse_version_sin_prefijo():
    assert parse_version("2.1") == (2, 1)

def test_parse_version_un_solo_numero():
    assert parse_version("v3") == (3,)

def test_parse_version_vacia():
    assert parse_version("") == ()
    assert parse_version(None) == ()

def test_es_mas_nueva_mayor():
    assert es_mas_nueva("v2.1", "2.0") is True

def test_es_mas_nueva_igual():
    assert es_mas_nueva("v2.0", "2.0") is False

def test_es_mas_nueva_menor():
    assert es_mas_nueva("v2.0", "2.1") is False

def test_es_mas_nueva_distinto_numero_de_componentes():
    assert es_mas_nueva("v2.1.0", "2.1") is False
    assert es_mas_nueva("v2.1.1", "2.1") is True

def _release(*nombres):
    return {"assets": [{"name": n, "browser_download_url": "http://x/" + n,
                        "size": 10} for n in nombres]}

def test_elegir_asset_exe_encuentra_el_exe():
    a = elegir_asset_exe(
        _release("notas.txt", "EscanerFotos.exe", "EscanerFotos-Setup-2.15.exe")
    )
    assert a is not None and a["name"] == "EscanerFotos-Setup-2.15.exe"


def test_elegir_asset_exe_ignora_ejecutables_que_no_son_setup():
    assert elegir_asset_exe(_release("EscanerFotos.exe", "helper.exe")) is None

def test_elegir_asset_exe_sin_exe_devuelve_none():
    assert elegir_asset_exe(_release("LEEME.txt")) is None

def test_elegir_asset_exe_release_vacia():
    assert elegir_asset_exe({}) is None


from actualizador_core import elegir_asset_sha256, parsear_sha256

def test_elegir_asset_sha256_encuentra_el_hash():
    a = elegir_asset_sha256(
        _release("EscanerFotos-Setup-2.7.exe", "EscanerFotos-Setup-2.7.exe.sha256"))
    assert a is not None and a["name"].endswith(".sha256")


def test_elegir_asset_sha256_exige_corresponder_al_setup():
    release = _release(
        "EscanerFotos-Setup-2.15.exe",
        "otro.exe.sha256",
        "EscanerFotos-Setup-2.15.exe.sha256",
    )
    assert elegir_asset_sha256(release)["name"] == "EscanerFotos-Setup-2.15.exe.sha256"

def test_elegir_asset_sha256_sin_hash_devuelve_none():
    assert elegir_asset_sha256(_release("EscanerFotos.exe")) is None

def test_parsear_sha256_formato_estandar():
    h = "ab" * 32
    assert parsear_sha256(f"{h}  EscanerFotos-Setup-2.7.exe\n") == h

def test_parsear_sha256_mayusculas_y_solo_hash():
    h = "AB" * 32
    assert parsear_sha256(h) == "ab" * 32

def test_parsear_sha256_invalido():
    assert parsear_sha256("no hay hash aqui") is None
    assert parsear_sha256("") is None
    assert parsear_sha256(None) is None
    assert parsear_sha256("abc123") is None


def test_periodicidad_solo_repite_tras_el_intervalo():
    assert debe_comprobar(ahora=1_000, ultima=None, intervalo=300)
    assert not debe_comprobar(ahora=1_299, ultima=1_000, intervalo=300)
    assert debe_comprobar(ahora=1_300, ultima=1_000, intervalo=300)


def test_ciclo_llega_a_ready_y_luego_installing():
    ciclo = CicloActualizacion()
    ciclo.transicionar("downloading")
    ciclo.transicionar("ready")
    ciclo.transicionar("installing")
    assert ciclo.estado == "installing"


def test_ciclo_permite_error_desde_descarga():
    ciclo = CicloActualizacion()
    ciclo.transicionar("downloading")
    ciclo.transicionar("error")
    assert ciclo.estado == "error"


def test_programar_instalacion_usa_modo_silencioso(monkeypatch):
    llamadas = []
    monkeypatch.setattr(
        actualizador.subprocess,
        "Popen",
        lambda comando, **opciones: llamadas.append((comando, opciones)),
    )

    actualizador.programar_instalacion("C:/Temp/EscanerFotos-Setup.exe")

    assert llamadas == [
        ([
            "C:/Temp/EscanerFotos-Setup.exe",
            "/VERYSILENT",
            "/SUPPRESSMSGBOXES",
            "/NORESTART",
        ], {"close_fds": True})
    ]


def test_comprobacion_manual_recibe_el_error_de_red(monkeypatch):
    eventos = []
    monkeypatch.setattr(
        actualizador,
        "urlopen",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("sin red")),
    )
    hilo = actualizador.HiloComprobar("2.14")
    hilo.finalizada.connect(eventos.append)

    hilo.run()

    assert eventos == ["error"]


def test_descargas_solapadas_no_comparten_archivos(tmp_path, monkeypatch):
    from io import BytesIO
    from pathlib import Path

    monkeypatch.setattr(actualizador.tempfile, 'tempdir', str(tmp_path))
    primera = actualizador.HiloDescarga('https://release/uno', 4)
    segunda = actualizador.HiloDescarga('https://release/dos', 4)
    resultados_uno, resultados_dos = [], []
    primera.terminado.connect(resultados_uno.append)
    segunda.terminado.connect(resultados_dos.append)

    class RespuestaSolapada(BytesIO):
        iniciada = False
        def read(self, *args):
            if not self.iniciada:
                self.iniciada = True
                segunda.run()
            return super().read(*args)

    monkeypatch.setattr(actualizador, 'urlopen', lambda req, **kw:
                        RespuestaSolapada(b'AAAA') if req.full_url.endswith('uno')
                        else BytesIO(b'BBBB'))
    primera.run()

    assert resultados_uno and resultados_uno[0]
    assert resultados_dos and resultados_dos[0]
    assert resultados_uno[0] != resultados_dos[0]
    assert Path(resultados_uno[0]).read_bytes() == b'AAAA'
    assert Path(resultados_dos[0]).read_bytes() == b'BBBB'
    assert not list(tmp_path.rglob('*.part'))


def test_comprobaciones_repetidas_comparten_un_solo_ciclo(monkeypatch):
    from PySide6.QtCore import QObject

    class Ventana(QObject):
        def statusBar(self):
            return self
        def showMessage(self, *args):
            pass

    ventana = Ventana()
    comprobaciones, descargas = [], []
    monkeypatch.setattr(actualizador, 'esta_empaquetada', lambda: True)
    monkeypatch.setattr(actualizador.HiloComprobar, 'start', lambda hilo: comprobaciones.append(hilo))
    monkeypatch.setattr(actualizador.HiloDescarga, 'start', lambda hilo: descargas.append(hilo))
    actualizador.conectar(ventana, '2.14')
    actualizador.conectar(ventana, '2.14', manual=True)
    assert len(comprobaciones) == 1

    comprobaciones[0].encontrada.emit('2.15', 'https://release/setup', 4, '')
    comprobaciones[0].finalizada.emit('encontrada')
    actualizador.conectar(ventana, '2.14', manual=True)
    assert len(comprobaciones) == 1
    assert len(descargas) == 1
    descargas[0].terminado.emit('')
    actualizador.conectar(ventana, '2.14', manual=True)
    assert len(comprobaciones) == 2
