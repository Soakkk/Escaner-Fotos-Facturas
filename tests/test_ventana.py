"""Flujo completo de la ventana (sin pantalla, QT_QPA_PLATFORM=offscreen):
cargar una foto, detectar, añadir páginas, unir DNI 2-en-1 y exportar PDF."""

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import cv2
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

_app = QApplication.instance() or QApplication([])

import escaner_fotos as ef
from suite_storage import fusionar_cliente


def _foto_documento():
    """Foto sintética: papel claro con líneas de texto sobre fondo oscuro."""
    img = np.full((1050, 1400, 3), 60, dtype=np.uint8)
    cv2.rectangle(img, (280, 160), (1150, 900), (235, 235, 235), -1)
    for y in range(300, 700, 60):
        cv2.line(img, (400, y), (1000, y), (30, 30, 30), 3)
    return img


def test_flujo_dni_dos_caras_en_una_pagina(tmp_path):
    v = ef.VentanaPrincipal()
    v._cargar_cv(_foto_documento())
    img = v.procesada_full()
    assert img is not None

    v.anadir_pagina_pdf(img)
    v.anadir_pagina_pdf(img)
    assert v.lista_pdf.count() == 2

    v.combinar_dni()
    assert v.lista_pdf.count() == 1

    datos = v.lista_pdf.item(0).data(Qt.ItemDataRole.UserRole)
    pil = ef.pagina_a_pil_pdf(datos)
    assert pil.size == (ef.componer_dni.__defaults__[0],
                        ef.componer_dni.__defaults__[1])
    ruta = tmp_path / "dni.pdf"
    pil.save(str(ruta), "PDF", resolution=200.0)
    assert ruta.stat().st_size > 0


def test_prefijo_en_nombre_de_archivo(tmp_path):
    v = ef.VentanaPrincipal()
    original = v.txt_prefijo.text()
    try:
        v.txt_prefijo.setText('Pérez: factura *marzo*')
        ruta = v._nombre_por_fecha(str(tmp_path), ".jpg")
        nombre = os.path.basename(ruta)
        assert nombre.startswith("Pérez factura marzo_")
        assert nombre.endswith(".jpg")
    finally:
        v.txt_prefijo.setText(original)


def test_encolar_no_pisa_la_imagen_cargada(tmp_path):
    v = ef.VentanaPrincipal()
    v._cargar_cv(_foto_documento())
    antes = v.imagen_original
    rutas = []
    for i in range(2):
        ruta = str(tmp_path / f"nueva_{i}.png")
        cv2.imwrite(ruta, _foto_documento())
        rutas.append(ruta)
    v._encolar(rutas)
    assert v.imagen_original is antes        # sigue la misma imagen en pantalla
    assert len(v.cola) == 2                  # y las nuevas esperan en la cola
    assert v.cola_total == 3


def _crear_fotos(tmp_path, n):
    rutas = []
    for i in range(n):
        ruta = str(tmp_path / f"doc_{i}.png")
        cv2.imwrite(ruta, _foto_documento())
        rutas.append(ruta)
    return rutas


def test_cola_visible_con_tanda_y_miniaturas(tmp_path):
    v = ef.VentanaPrincipal()
    rutas = _crear_fotos(tmp_path, 4)
    v._iniciar_cola(rutas)                       # carga la 1ª, 3 a la cola
    assert v.cola_total == 4 and v.cola_pos == 1
    assert not v.grupo_cola.isHidden()           # la cola se muestra
    assert v.lista_cola.count() == 3             # 3 pendientes en la tira
    # Las miniaturas se generan con el timer; forzamos su generación aquí.
    for _ in range(6):
        v._generar_una_miniatura()
    assert all(r in v._cache_thumbs for r in v.cola)


def test_anadir_al_pdf_y_siguiente_avanza_la_cola(tmp_path):
    v = ef.VentanaPrincipal()
    v._iniciar_cola(_crear_fotos(tmp_path, 3))
    v.terminar_y_siguiente()                     # añade 1ª al PDF, carga 2ª
    assert v.lista_pdf.count() == 1
    assert v.cola_pos == 2 and v.lista_cola.count() == 1
    v.terminar_y_siguiente()                     # añade 2ª, carga 3ª (última)
    assert v.lista_pdf.count() == 2
    assert v.cola_pos == 3 and v.lista_cola.count() == 0
    assert not v.grupo_cola.isHidden()           # sigue visible en la última


def test_saltar_no_anade_al_pdf_pero_avanza(tmp_path):
    v = ef.VentanaPrincipal()
    v._iniciar_cola(_crear_fotos(tmp_path, 3))
    v._saltar_actual()                           # salta la 1ª sin añadir
    assert v.lista_pdf.count() == 0
    assert v.cola_pos == 2 and v.lista_cola.count() == 1


def test_reordenar_cola_sincroniza_la_lista(tmp_path):
    v = ef.VentanaPrincipal()
    rutas = _crear_fotos(tmp_path, 4)
    v._iniciar_cola(rutas)                        # cola = rutas[1], [2], [3]
    # Simula que el usuario reordena: invertimos los items de la lista visual
    items = [v.lista_cola.takeItem(0) for _ in range(v.lista_cola.count())]
    for it in reversed(items):
        v.lista_cola.addItem(it)
    v._sincronizar_cola_desde_lista()
    assert v.cola == [rutas[3], rutas[2], rutas[1]]


def test_vaciar_cola_conserva_foto_actual(tmp_path):
    v = ef.VentanaPrincipal()
    v._iniciar_cola(_crear_fotos(tmp_path, 5))
    actual = v.imagen_original
    v._vaciar_cola()
    assert v.imagen_original is actual           # la foto en pantalla se queda
    assert v.cola == [] and v.lista_cola.count() == 0
    assert v.grupo_cola.isHidden()               # sin tanda, se oculta


def test_quitar_imagen_vacia_la_foto_y_conserva_el_pdf():
    v = ef.VentanaPrincipal()
    v._cargar_cv(_foto_documento())
    assert v.imagen_original is not None
    assert v.btn_quitar.isEnabled()
    # Una página ya añadida al PDF NO debe perderse al quitar la foto.
    v.anadir_pagina_pdf(v.procesada_full())
    assert v.lista_pdf.count() == 1

    v.quitar_imagen()
    assert v.imagen_original is None          # la foto se vació
    assert v.procesada_full() is None         # no hay nada que procesar
    assert v.lista_pdf.count() == 1           # el PDF se conserva
    assert not v.btn_quitar.isEnabled()       # botón deshabilitado sin foto

    # Tras quitar, se puede cargar otra con normalidad (no queda 'bloqueada').
    v._cargar_cv(_foto_documento())
    assert v.imagen_original is not None
    assert v.btn_quitar.isEnabled()


def test_intensidad_visible_solo_en_modos_bn():
    # isHidden() refleja el setVisible directamente (la ventana no se llega a
    # mostrar en el test offscreen, por eso no se usa isVisible()).
    v = ef.VentanaPrincipal()
    for idx in (0, 1):                         # B/N nítido y B/N puro
        v.combo_filtro.setCurrentIndex(idx)
        assert not v.cont_intensidad.isHidden()
    for idx in (2, 3):                         # Modos de color: sin intensidad B/N
        v.combo_filtro.setCurrentIndex(idx)
        assert v.cont_intensidad.isHidden()


def test_auto_orientar_en_ventana():
    v = ef.VentanaPrincipal()
    # Crear doc con texto
    doc = np.full((1200, 800, 3), 255, dtype=np.uint8)
    cv2.rectangle(doc, (100, 60), (700, 160), (30, 30, 30), -1)
    for y in range(250, 950, 40):
        cv2.line(doc, (100, y), (700, y), (40, 40, 40), 4)

    # Rotado 90 grados
    rot90 = cv2.rotate(doc, cv2.ROTATE_90_CLOCKWISE)
    v._cargar_cv(rot90)
    assert v.imagen_original.shape[0] == 800
    assert v.imagen_original.shape[1] == 1200

    v.auto_orientar()
    base = v._base_full()
    assert base.shape[0] == 1200
    assert base.shape[1] == 800


def test_sesion_restaura_foto_cola_orden_y_paginas(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "estado"))
    rutas = _crear_fotos(tmp_path, 3)
    primera = ef.VentanaPrincipal()
    primera._iniciar_cola(rutas)
    primera.anadir_pagina_pdf(primera.procesada_full())
    primera._guardar_sesion_actual()

    restaurada = ef.VentanaPrincipal()

    assert restaurada._ruta_actual == rutas[0]
    assert restaurada.cola == rutas[1:]
    assert restaurada.cola_pos == 1
    assert restaurada.cola_total == 3
    assert restaurada.lista_pdf.count() == 1
    assert (
        restaurada.lista_pdf.item(0).data(Qt.ItemDataRole.UserRole)
        == primera.lista_pdf.item(0).data(Qt.ItemDataRole.UserRole)
    )


def test_sesion_restaura_sin_perdida_una_foto_pegada(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "estado"))
    foto = _foto_documento()
    primera = ef.VentanaPrincipal()
    primera._cargar_cv(foto)
    primera._guardar_sesion_actual()

    restaurada = ef.VentanaPrincipal()

    assert np.array_equal(restaurada.imagen_original, foto)


def test_reordenar_cola_persiste_el_orden(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "estado"))
    rutas = _crear_fotos(tmp_path, 4)
    ventana = ef.VentanaPrincipal()
    ventana._iniciar_cola(rutas)
    items = [ventana.lista_cola.takeItem(0) for _ in range(ventana.lista_cola.count())]
    for item in reversed(items):
        ventana.lista_cola.addItem(item)

    ventana._sincronizar_cola_desde_lista()
    restaurada = ef.VentanaPrincipal()

    assert restaurada.cola == [rutas[3], rutas[2], rutas[1]]


def test_foto_fallida_conserva_posicion_y_permite_reintentar(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "estado"))
    rota = tmp_path / "rota.png"
    rota.write_bytes(b"copia incompleta")
    siguiente = _crear_fotos(tmp_path, 1)[0]
    ventana = ef.VentanaPrincipal()

    ventana._iniciar_cola([str(rota), siguiente])

    assert ventana._ruta_fallida_actual == str(rota)
    assert ventana.cola == [siguiente]
    assert ventana.cola_pos == 1
    assert ventana.btn_reintentar.isEnabled()

    assert cv2.imwrite(str(rota), _foto_documento())
    ventana.reintentar_actual()

    assert ventana._ruta_fallida_actual == ""
    assert ventana._ruta_actual == str(rota)
    assert ventana.imagen_original is not None


def test_vigilancia_encola_solo_despues_de_dos_firmas_estables(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "estado"))
    ventana = ef.VentanaPrincipal()
    ventana.carpeta_vigilada = str(tmp_path)
    ventana.chk_vigilar.setChecked(True)
    nueva = tmp_path / "nueva.png"
    assert cv2.imwrite(str(nueva), _foto_documento())

    ventana._procesar_carpeta_vigilada()
    assert ventana.imagen_original is None
    ventana._procesar_carpeta_vigilada()

    assert ventana._ruta_actual == str(nueva)


def test_seleccionar_cliente_sugiere_prefijo_y_carpeta(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "estado"))
    destino = str(tmp_path / "Cliente Ana")
    fusionar_cliente(
        {"nif": "12345678Z", "nombre": "Ana López", "carpeta": destino},
        "directorio_compartido",
    )
    ventana = ef.VentanaPrincipal()

    ventana.combo_cliente.setCurrentIndex(1)

    assert ventana.txt_prefijo.text() == "Ana López"
    assert ventana.carpeta_salida == destino


def test_perfil_dni_aplica_color_sin_procesar_la_imagen():
    ventana = ef.VentanaPrincipal()

    ventana._aplicar_perfil("DNI")

    assert ventana.combo_filtro.currentIndex() == 2
    assert ventana.sld_intensidad_bn.value() == 50
    assert ventana.imagen_original is None


def test_finalizacion_permite_deshacer_la_ultima_pagina():
    ventana = ef.VentanaPrincipal()
    ventana._cargar_cv(_foto_documento())
    ventana.anadir_pagina_pdf(ventana.procesada_full())

    assert not ventana.panel_finalizacion.isHidden()
    assert ventana.btn_deshacer_ultima.isEnabled()
    ventana.deshacer_ultima_pagina()

    assert ventana.lista_pdf.count() == 0
    assert ventana.panel_finalizacion.isHidden()


def test_instalar_actualizacion_guarda_sesion_antes_de_lanzar(monkeypatch):
    ventana = ef.VentanaPrincipal()
    eventos = []
    ventana._ruta_update_lista = "/tmp/EscanerFotos-Setup.exe"
    monkeypatch.setattr(ventana, "_guardar_sesion_actual", lambda: eventos.append("sesion"))
    monkeypatch.setattr(
        ef.actualizador,
        "lanzar_instalador",
        lambda ruta: eventos.append(("instalador", ruta)),
    )
    monkeypatch.setattr(ef.QApplication, "quit", lambda: eventos.append("quit"))

    ventana.instalar_actualizacion_lista()

    assert eventos == [
        "sesion",
        ("instalador", "/tmp/EscanerFotos-Setup.exe"),
        "quit",
    ]


def test_shell_tiene_zonas_y_acciones_principales_identificables():
    ventana = ef.VentanaPrincipal()

    for nombre in (
        "cabecera",
        "zonaOriginal",
        "panelControles",
        "zonaResultado",
        "accionAbrir",
        "accionPegar",
        "btnPrimario",
        "btnEnviar",
    ):
        assert ventana.findChild(ef.QWidget, nombre) is not None, nombre


def test_cabecera_adapta_acciones_en_ancho_portatil():
    ventana = ef.VentanaPrincipal()
    ventana.show()
    ventana.resize(1500, 900)
    _app.processEvents()
    assert not ventana.accion_abrir_cabecera.isHidden()
    assert not ventana.accion_pegar_cabecera.isHidden()

    ventana.resize(1000, 760)
    _app.processEvents()

    assert ventana.accion_abrir_cabecera.isHidden()
    assert ventana.accion_pegar_cabecera.isHidden()
    assert ventana.findChild(ef.QGroupBox, "masOpciones") is not None


def test_flujo_completo_foto_pdf_y_apertura_de_aplifisa(tmp_path, monkeypatch):
    ruta_pdf = tmp_path / "lote.pdf"
    ejecutable = tmp_path / "FacturasAplifisa.exe"
    ejecutable.write_bytes(b"")
    aperturas = []
    ventana = ef.VentanaPrincipal()
    ventana._cargar_cv(_foto_documento())
    ventana.anadir_pagina_pdf(ventana.procesada_full())
    monkeypatch.setattr(ventana, "_elegir_ruta_pdf_lote", lambda: str(ruta_pdf))
    monkeypatch.setattr(ventana, "_ejecutable_aplifisa", lambda: str(ejecutable))
    monkeypatch.setattr(
        ef, "lanzar_aplifisa", lambda exe, pdf: aperturas.append((exe, pdf))
    )
    monkeypatch.setattr(ef.QMessageBox, "information", lambda *args: None)

    ventana.enviar_a_aplifisa()

    assert ruta_pdf.read_bytes().startswith(b"%PDF")
    assert aperturas == [(str(ejecutable), str(ruta_pdf))]


def test_comprobacion_manual_de_actualizaciones_es_explicita(monkeypatch):
    ventana = ef.VentanaPrincipal()
    llamadas = []
    monkeypatch.setattr(
        ef.actualizador,
        "conectar",
        lambda destino, version, manual=False: llamadas.append(
            (destino, version, manual)
        ),
    )

    ventana.findChild(ef.QGroupBox, "masOpciones").setChecked(True)
    ventana.btn_comprobar_actualizaciones.click()

    assert llamadas == [(ventana, ef.__version__, True)]
