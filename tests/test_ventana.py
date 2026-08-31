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

