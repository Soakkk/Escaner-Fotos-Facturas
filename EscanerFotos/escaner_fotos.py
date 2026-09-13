"""
Escáner de Fotos — Navaja suiza para digitalizar documentos
============================================================
Aplicación de escritorio para convertir fotos de documentos
(facturas, contratos, DNI) hechas con el móvil en imágenes
tipo escáner: enderezadas, recortadas y con el texto legible.

Sin IA. Basado en OpenCV.

v2.13 — Novedades:
  • Nuevo icono propio para distinguir la aplicación en Windows

v2.11 — Novedades:
  • Flujo visual compartido con Generador de avisos fiscales
  • Botón fijo «Enviar lote a Facturas a Aplifisa»
  • Panel central simplificado por pasos y opciones secundarias plegadas

v2.10 — Novedades:
  • Panel reordenado: lo más usado arriba (recortar/enderezar, girar,
    tipo, ajuste fino); lo poco habitual en «Más opciones»
  • Cola de fotos con miniaturas: suelta una tanda de WhatsApp y procésalas
    en cadena (ajusta una, «Añadir al PDF y siguiente» y salta sola)
  • Detección de documentos con COLOR (no solo papel blanco): bordes por
    color + segmentación frente al fondo
  • Fuera el «procesar carpeta entera» (no se usaba)

v2.9:
  • Color limpio con Simplest Color Balance (no quema) + «Quitar foto»

v2.8:
  • B/N nítido (estilo CamScanner) + B/N puro tinta (1 bit)

v2.7:
  • Icono propio, tema oscuro coherente y panel en 5 pasos
  • Carpeta vigilada (WhatsApp), prefijo de archivo, DNI 2 en 1
  • PDFs B/N a 1 bit (CCITT G4), HEIC, vista previa fiel
"""

import sys
import os
import re
import base64
from datetime import datetime
import cv2
import numpy as np

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QPushButton, QLabel,
    QVBoxLayout, QHBoxLayout, QFileDialog, QSlider, QComboBox,
    QMessageBox, QFrame, QGroupBox, QSizePolicy, QScrollArea,
    QListWidget, QListWidgetItem, QLineEdit, QCheckBox
)
from PySide6.QtGui import (
    QPixmap, QImage, QPainter, QPen, QColor, QMouseEvent,
    QKeySequence, QShortcut, QIcon
)
from PySide6.QtCore import Qt, Signal, QSettings, QTimer, QSize
from PySide6.QtCore import QLockFile, QStandardPaths, QByteArray, QBuffer
from PySide6.QtCore import QFileSystemWatcher
from version import __version__
import actualizador
import estilo
from imagen import (
    detectar_documento, corregir_perspectiva, rotar_imagen, aplicar_pipeline,
    leer_imagen, es_ruta_imagen, EXTENSIONES_IMAGEN, miniatura_archivo,
    codificar_pagina, decodificar_pagina, pagina_a_pil_pdf, cv_a_pil_pdf,
    componer_dni, detectar_orientacion_texto, auto_orientar_documento,
    detectar_multiples_documentos,
)
from cola import rutas_unicas_en_orden, siguiente_de_cola, texto_cola
from integracion_aplifisa import lanzar_aplifisa, localizar_aplifisa
from perfiles import PerfilEscaneo, cargar_perfiles, guardar_perfil
from precalculo import PrecalculoResultado, TrabajadorPrecalculo, firma_imagen
from sesion_trabajo import guardar_sesion, leer_sesion
from suite_storage import leer_clientes
from vigilancia import ArchivoObservado, identidad_archivo


def _rutas_imagen_de(mime):
    """Rutas de archivos de imagen locales contenidos en un QMimeData."""
    if not mime.hasUrls():
        return []
    return [u.toLocalFile() for u in mime.urls()
            if u.isLocalFile() and es_ruta_imagen(u.toLocalFile())]


# =============================================================
# =================   COMPONENTES DE INTERFAZ   ===============
# =============================================================

class LienzoImagen(QLabel):
    """
    Visualizador de imágenes con soporte para:
    - Mostrar imagen OpenCV (BGR) escalada al tamaño del widget.
    - Arrastrar y soltar archivos de imagen.
    - Selección manual de 4 puntos (clic izquierdo).
    - Deshacer último punto (clic derecho).
    - Cancelar modo selección (método público).
    """
    puntos_listos = Signal(list)
    puntos_editados = Signal(list)   # 4 puntos tras arrastrar una esquina
    imagenes_soltadas = Signal(list)   # rutas de imagen soltadas

    def __init__(self):
        super().__init__()
        self.setMinimumSize(280, 400)
        self.setObjectName("lienzo")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAcceptDrops(True)

        self.imagen_cv = None
        self.modo_seleccion = False
        self.puntos = []
        self.modo_editar = False
        self._idx_arrastrado = None
        self.factor_escala = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self._w_pix = 0
        self._h_pix = 0

    # --- Drag & drop ---

    def dragEnterEvent(self, event):
        if _rutas_imagen_de(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        rutas = _rutas_imagen_de(event.mimeData())
        if rutas:
            self.imagenes_soltadas.emit(rutas)

    # --- Visualización ---

    def mostrar_imagen(self, imagen_cv):
        self.imagen_cv = imagen_cv
        self.actualizar_visualizacion()

    def limpiar_puntos(self):
        self.puntos = []
        self.actualizar_visualizacion()

    def mostrar_esquinas(self, puntos):
        """Muestra 4 vértices (coords de imagen) que se pueden arrastrar."""
        self.puntos = [list(p) for p in puntos]
        self.modo_editar = True
        self.modo_seleccion = False
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.actualizar_visualizacion()

    def _esquina_cercana(self, x_pix, y_pix):
        """Índice del vértice cuya posición en pantalla está a <=18 px del clic, o None."""
        mejor, mejor_d = None, 18.0
        for i, p in enumerate(self.puntos):
            px = p[0] * self.factor_escala + self.offset_x
            py = p[1] * self.factor_escala + self.offset_y
            d = ((px - x_pix) ** 2 + (py - y_pix) ** 2) ** 0.5
            if d <= mejor_d:
                mejor, mejor_d = i, d
        return mejor

    def actualizar_visualizacion(self):
        if self.imagen_cv is None:
            self.clear()
            self.setText(
                "<div style='color:#8d97a1; font-size:14px'>"
                "Arrastra una foto aquí,<br>"
                "pégala con <b>Ctrl+V</b><br>"
                "o ábrela con <b>Ctrl+O</b></div>"
            )
            return

        img_rgb = cv2.cvtColor(self.imagen_cv, cv2.COLOR_BGR2RGB)
        h, w = img_rgb.shape[:2]
        qimg = QImage(
            img_rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888
        ).copy()
        pixmap = QPixmap.fromImage(qimg)

        pixmap_esc = pixmap.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self._w_pix = pixmap_esc.width()
        self._h_pix = pixmap_esc.height()
        self.factor_escala = self._w_pix / w if w > 0 else 1.0
        self.offset_x = (self.width() - self._w_pix) / 2
        self.offset_y = (self.height() - self._h_pix) / 2

        if self.puntos:
            painter = QPainter(pixmap_esc)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            if len(self.puntos) >= 2:
                pen_linea = QPen(QColor(50, 200, 80), 2)
                painter.setPen(pen_linea)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                n = len(self.puntos)
                for i in range(n - 1):
                    x1 = self.puntos[i][0] * self.factor_escala
                    y1 = self.puntos[i][1] * self.factor_escala
                    x2 = self.puntos[i + 1][0] * self.factor_escala
                    y2 = self.puntos[i + 1][1] * self.factor_escala
                    painter.drawLine(int(x1), int(y1), int(x2), int(y2))
                if n == 4:
                    x1 = self.puntos[3][0] * self.factor_escala
                    y1 = self.puntos[3][1] * self.factor_escala
                    x2 = self.puntos[0][0] * self.factor_escala
                    y2 = self.puntos[0][1] * self.factor_escala
                    painter.drawLine(int(x1), int(y1), int(x2), int(y2))

            pen_punto = QPen(QColor(255, 60, 60), 2)
            painter.setPen(pen_punto)
            painter.setBrush(QColor(255, 60, 60))
            for idx, p in enumerate(self.puntos):
                x = p[0] * self.factor_escala
                y = p[1] * self.factor_escala
                painter.drawEllipse(int(x - 7), int(y - 7), 14, 14)
                painter.setPen(QPen(QColor(255, 255, 255), 1))
                painter.drawText(int(x - 4), int(y + 5), str(idx + 1))
                painter.setPen(pen_punto)

            painter.end()

        # Indicador de modo selección
        if self.modo_seleccion:
            painter2 = QPainter(pixmap_esc)
            painter2.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter2.fillRect(0, 0, pixmap_esc.width(), 28, QColor(0, 0, 0, 160))
            painter2.setPen(QColor(255, 220, 50))
            restantes = 4 - len(self.puntos)
            painter2.drawText(
                8, 19,
                f"Clic en esquina {len(self.puntos) + 1}/4  "
                f"({restantes} restante{'s' if restantes != 1 else ''})   ·   "
                f"Clic derecho o Ctrl+Z: deshacer   ·   Escape: cancelar"
            )
            painter2.end()

        self.setPixmap(pixmap_esc)

    def resizeEvent(self, event):
        self.actualizar_visualizacion()
        super().resizeEvent(event)

    # --- Selección manual ---

    def iniciar_seleccion_manual(self):
        self.modo_seleccion = True
        self.puntos = []
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.actualizar_visualizacion()

    def deshacer_ultimo_punto(self):
        if self.puntos and self.modo_seleccion:
            self.puntos.pop()
            self.actualizar_visualizacion()

    def cancelar_seleccion(self):
        if self.modo_seleccion:
            self.modo_seleccion = False
            self.puntos = []
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.actualizar_visualizacion()

    def mousePressEvent(self, event: QMouseEvent):
        if self.modo_editar and len(self.puntos) == 4 and self.imagen_cv is not None:
            idx = self._esquina_cercana(event.position().x(), event.position().y())
            if idx is not None:
                self._idx_arrastrado = idx
                return

        if not self.modo_seleccion or self.imagen_cv is None:
            return

        if event.button() == Qt.MouseButton.RightButton:
            self.deshacer_ultimo_punto()
            return

        cx = event.position().x() - self.offset_x
        cy = event.position().y() - self.offset_y

        if cx < 0 or cy < 0 or cx > self._w_pix or cy > self._h_pix:
            return

        x_orig = cx / self.factor_escala
        y_orig = cy / self.factor_escala
        self.puntos.append([x_orig, y_orig])
        self.actualizar_visualizacion()

        if len(self.puntos) == 4:
            self.modo_seleccion = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.puntos_listos.emit(list(self.puntos))

    def mouseMoveEvent(self, event):
        if self._idx_arrastrado is None:
            return
        cx = (event.position().x() - self.offset_x) / self.factor_escala
        cy = (event.position().y() - self.offset_y) / self.factor_escala
        h, w = self.imagen_cv.shape[:2]
        cx = max(0, min(w - 1, cx))
        cy = max(0, min(h - 1, cy))
        self.puntos[self._idx_arrastrado] = [cx, cy]
        self.actualizar_visualizacion()

    def mouseReleaseEvent(self, event):
        if self._idx_arrastrado is not None:
            self._idx_arrastrado = None
            self.puntos_editados.emit([list(p) for p in self.puntos])


# =============================================================
# ===================   VENTANA PRINCIPAL   ===================
# =============================================================

class VentanaPrincipal(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Escáner de Fotos {__version__}")
        self.setWindowIcon(QIcon(estilo.ruta_recurso("icono.ico")))
        self.resize(1500, 900)
        self.setAcceptDrops(True)

        self.imagen_original = None
        self.imagen_enderezada = None
        self._preview_base = None    # versión reducida para vista previa fluida
        self._ruta_origen = ""       # carpeta del último archivo abierto
        self._ruta_actual = ""
        self._ruta_fallida_actual = ""
        self._errores_cola = {}
        self._perfiles = cargar_perfiles()
        self._perfil_actual = "Factura"
        self._estado_actualizacion = "checking"
        self._ruta_update_lista = ""
        self._version_update_lista = ""
        self._restaurando_sesion = False

        self.cola = []
        self.cola_total = 0
        self.cola_pos = 0
        self._cache_thumbs = {}      # ruta -> QIcon (miniaturas de la cola)
        self._precalculos = {}
        self._trabajador_precalculo = None

        # Generador de miniaturas de la cola, una por disparo (no bloquea la UI)
        self._timer_thumbs = QTimer(self)
        self._timer_thumbs.setSingleShot(True)
        self._timer_thumbs.setInterval(30)
        self._timer_thumbs.timeout.connect(self._generar_una_miniatura)

        # Preferencias persistentes entre sesiones
        self.settings = QSettings("EscanerFotos", "EscanerFotos")
        self.carpeta_salida = self.settings.value("carpeta_salida", "", str)

        # Carpeta vigilada: las fotos nuevas (p. ej. descargas de WhatsApp)
        # entran solas a la cola sin tener que arrastrarlas.
        self.carpeta_vigilada = self.settings.value("carpeta_vigilada", "", str)
        self._vistos = set()
        self._identidades_vistas = set()
        self._observados = {}
        self._watcher = QFileSystemWatcher(self)
        self._watcher.directoryChanged.connect(self._al_cambiar_carpeta_vigilada)
        # Espera a que el archivo termine de copiarse antes de encolarlo
        self._timer_vigia = QTimer(self)
        self._timer_vigia.setSingleShot(True)
        self._timer_vigia.setInterval(1500)
        self._timer_vigia.timeout.connect(self._procesar_carpeta_vigilada)

        # Debounce de los sliders para que la vista previa no dé tirones
        self._timer_preview = QTimer(self)
        self._timer_preview.setSingleShot(True)
        self._timer_preview.setInterval(60)
        self._timer_preview.timeout.connect(self.actualizar_procesado)

        self._crear_interfaz()
        self._crear_atajos()
        self._restaurar_preferencias()
        self._restaurar_sesion()
        self._actualizar_barra_estado()

    def _restaurar_preferencias(self):
        """Aplica las preferencias guardadas a la interfaz ya construida."""
        # 'filtro_idx2': en v2.8 cambió la lista de filtros (4 opciones);
        # la clave nueva evita restaurar un índice de la lista antigua.
        idx = self.settings.value("filtro_idx2", 0, int)
        if 0 <= idx < self.combo_filtro.count():
            self.combo_filtro.blockSignals(True)
            self.combo_filtro.setCurrentIndex(idx)
            self.combo_filtro.blockSignals(False)
        self.cont_intensidad.setVisible(idx <= 1)
        self.txt_prefijo.setText(self.settings.value("prefijo", "", str))
        self._actualizar_label_carpeta()
        self._actualizar_label_vigilada()
        if self.settings.value("vigilar", False, bool) \
                and os.path.isdir(self.carpeta_vigilada):
            self.chk_vigilar.setChecked(True)

    def _datos_sesion_actual(self):
        paginas = [
            base64.b64encode(
                bytes(self.lista_pdf.item(i).data(Qt.ItemDataRole.UserRole))
            ).decode("ascii")
            for i in range(self.lista_pdf.count())
        ]
        foto_embebida = ""
        if self.imagen_original is not None and not self._ruta_actual:
            ok, buffer_png = cv2.imencode(
                ".png", self.imagen_original,
                [cv2.IMWRITE_PNG_COMPRESSION, 3],
            )
            if ok:
                foto_embebida = base64.b64encode(buffer_png.tobytes()).decode("ascii")
        filtro, brillo, contraste, nitidez, intensidad = self._params()
        return {
            "foto_actual": self._ruta_actual,
            "foto_actual_png": foto_embebida,
            "foto_fallida": self._ruta_fallida_actual,
            "errores_cola": dict(self._errores_cola),
            "cola": list(self.cola),
            "cola_total": self.cola_total,
            "cola_pos": self.cola_pos,
            "paginas": paginas,
            "controles": {
                "filtro": filtro,
                "brillo": brillo,
                "contraste": contraste,
                "nitidez": nitidez,
                "intensidad": intensidad,
            },
            "destino": self.carpeta_salida,
            "prefijo": self.txt_prefijo.text(),
            "perfil": self._perfil_actual,
        }

    def _guardar_sesion_actual(self):
        if self._restaurando_sesion:
            return
        guardar_sesion(self._datos_sesion_actual())

    def _restaurar_sesion(self):
        datos = leer_sesion()
        if not datos:
            return
        self._restaurando_sesion = True
        try:
            ruta_actual = datos.get("foto_actual", "")
            foto_embebida = datos.get("foto_actual_png", "")
            if foto_embebida:
                try:
                    buffer_png = base64.b64decode(foto_embebida, validate=True)
                    imagen = cv2.imdecode(
                        np.frombuffer(buffer_png, dtype=np.uint8), cv2.IMREAD_COLOR
                    )
                except (ValueError, TypeError):
                    imagen = None
                if imagen is not None:
                    self._cargar_cv(imagen)
            elif ruta_actual and os.path.isfile(ruta_actual):
                self._cargar_archivo(ruta_actual)
            self._ruta_fallida_actual = str(datos.get("foto_fallida", ""))
            self._errores_cola = dict(datos.get("errores_cola", {}))
            if hasattr(self, "btn_reintentar"):
                self.btn_reintentar.setEnabled(bool(self._ruta_fallida_actual))

            self.cola = [r for r in datos.get("cola", []) if os.path.isfile(r)]
            self.cola_total = int(datos.get("cola_total", len(self.cola)))
            self.cola_pos = int(datos.get("cola_pos", 1 if ruta_actual else 0))
            if self.cola_total < len(self.cola) + (1 if self._ruta_actual else 0):
                self.cola_total = len(self.cola) + (1 if self._ruta_actual else 0)

            controles = datos.get("controles", {})
            valores = (
                (self.combo_filtro, "filtro"),
                (self.sld_brillo, "brillo"),
                (self.sld_contraste, "contraste"),
                (self.sld_nitidez, "nitidez"),
                (self.sld_intensidad_bn, "intensidad"),
            )
            for control, clave in valores:
                if clave in controles:
                    control.blockSignals(True)
                    control.setValue(int(controles[clave])) if hasattr(
                        control, "setValue"
                    ) else control.setCurrentIndex(int(controles[clave]))
                    control.blockSignals(False)
            self.cont_intensidad.setVisible(self.combo_filtro.currentIndex() <= 1)
            self.carpeta_salida = str(datos.get("destino", self.carpeta_salida))
            self.txt_prefijo.setText(str(datos.get("prefijo", self.txt_prefijo.text())))
            nombre_perfil = str(datos.get("perfil", self._perfil_actual))
            indice_perfil = self.combo_perfil.findText(nombre_perfil)
            if indice_perfil >= 0:
                self.combo_perfil.setCurrentIndex(indice_perfil)
                self._perfil_actual = nombre_perfil
            self._actualizar_label_carpeta()

            for pagina in datos.get("paginas", []):
                try:
                    datos_pagina = base64.b64decode(pagina, validate=True)
                except (ValueError, TypeError):
                    continue
                self._insertar_pagina_codificada(datos_pagina)
            self._actualizar_indicador_cola()
            self.actualizar_procesado()
        finally:
            self._restaurando_sesion = False

    def closeEvent(self, event):
        self._guardar_sesion_actual()
        super().closeEvent(event)

    def resizeEvent(self, event):
        if hasattr(self, "accion_abrir_cabecera"):
            mostrar_secundarias = event.size().width() >= 1150
            self.accion_abrir_cabecera.setVisible(mostrar_secundarias)
            self.accion_pegar_cabecera.setVisible(mostrar_secundarias)
        super().resizeEvent(event)

    # ----------------------------------------------------------
    # Atajos de teclado
    # ----------------------------------------------------------

    def _crear_atajos(self):
        QShortcut(QKeySequence("Ctrl+O"), self, activated=self.abrir_imagen)
        QShortcut(QKeySequence("Ctrl+G"), self, activated=self.guardado_rapido)
        QShortcut(QKeySequence(Qt.Key.Key_Return), self, activated=self.guardado_rapido)
        QShortcut(QKeySequence(Qt.Key.Key_Enter), self, activated=self.guardado_rapido)
        QShortcut(QKeySequence("Ctrl+S"), self, activated=lambda: self.guardar("jpg"))
        QShortcut(QKeySequence("Ctrl+Shift+S"), self, activated=lambda: self.guardar("pdf"))
        QShortcut(QKeySequence("Ctrl+E"), self, activated=lambda: self.guardar("png"))
        QShortcut(QKeySequence("F5"), self, activated=self.detectar_auto)
        QShortcut(QKeySequence("Escape"), self, activated=self.lienzo_original.cancelar_seleccion)
        QShortcut(QKeySequence("Ctrl+Z"), self, activated=self.lienzo_original.deshacer_ultimo_punto)
        QShortcut(QKeySequence("Ctrl+R"), self, activated=self.reset_ajustes)
        QShortcut(QKeySequence("Ctrl+V"), self, activated=self.pegar_imagen)
        QShortcut(QKeySequence("Ctrl+Shift+R"), self, activated=self.auto_orientar)
        QShortcut(QKeySequence("Ctrl+Alt+R"), self, activated=self.auto_orientar)

    # ----------------------------------------------------------
    # Barra de estado
    # ----------------------------------------------------------

    def _actualizar_barra_estado(self):
        self._actualizar_finalizacion()
        if hasattr(self, "btn_quitar"):
            self.btn_quitar.setEnabled(self.imagen_original is not None)
        if self.imagen_original is None:
            self.statusBar().showMessage(
                "Arrastra una imagen aquí, usa Ctrl+O para abrir  |  "
                "Ctrl+S: JPG  Ctrl+Shift+S: PDF  Ctrl+E: PNG  F5: Detectar"
            )
            return
        h, w = self.imagen_original.shape[:2]
        partes = [f"Original: {w}×{h} px"]
        base = self._base_full()
        if base is not None:
            hp, wp = base.shape[:2]
            partes.append(f"Resultado: {wp}×{hp} px")
        if hasattr(self, "lista_pdf") and self.lista_pdf.count():
            partes.append(f"PDF: {self.lista_pdf.count()} pág.")
        partes.append("Enter: Guardado rápido  |  Ctrl+S: JPG  Ctrl+Shift+S: PDF")
        self.statusBar().showMessage("   |   ".join(partes))

    def _actualizar_finalizacion(self):
        if not hasattr(self, "panel_finalizacion"):
            return
        hay_paginas = self.lista_pdf.count() > 0
        self.panel_finalizacion.setVisible(hay_paginas)
        self.btn_deshacer_ultima.setEnabled(hay_paginas)

    def _mostrar_actualizacion_lista(self, version):
        self.btn_actualizacion_lista.setText(f"Reiniciar y actualizar a {version}")
        self.btn_actualizacion_lista.setVisible(True)
        self.statusBar().showMessage(
            f"Actualización {version} preparada; se instalará cuando tú decidas",
            8000,
        )

    def instalar_actualizacion_lista(self):
        if not self._ruta_update_lista:
            return
        self._estado_actualizacion = "installing"
        self._guardar_sesion_actual()
        actualizador.lanzar_instalador(self._ruta_update_lista)
        QApplication.quit()

    # ----------------------------------------------------------
    # Drag & drop sobre la ventana principal
    # ----------------------------------------------------------

    def dragEnterEvent(self, event):
        if _rutas_imagen_de(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        rutas = _rutas_imagen_de(event.mimeData())
        if rutas:
            self._iniciar_cola(rutas)

    # ----------------------------------------------------------
    # Construcción de la interfaz
    # ----------------------------------------------------------

    def _estado_recorte(self, texto, ok=False):
        """Etiqueta de estado del recorte, con los colores del tema."""
        color = estilo.HTML_OK if ok else estilo.HTML_SUAVE
        cierre = "  ✓" if ok else ""
        self.lbl_estado_recorte.setText(
            f"<span style='color:{color}'>{texto}{cierre}</span>")

    def _grupo_plegable(self, titulo, contenido, abierto=False):
        """QGroupBox 'checkable' cuyo contenido se oculta al desmarcar (plegar)."""
        g = QGroupBox(titulo)
        g.setCheckable(True)
        g.setChecked(abierto)
        lay = QVBoxLayout(g)
        lay.setContentsMargins(6, 4, 6, 4)
        lay.addWidget(contenido)

        def _aplicar(abierto_):
            contenido.setVisible(abierto_)
            g.setProperty("plegado", not abierto_)
            g.style().unpolish(g)
            g.style().polish(g)

        g.toggled.connect(_aplicar)
        _aplicar(abierto)
        return g

    def _iniciar_cola(self, rutas):
        rutas = rutas_unicas_en_orden(rutas)
        if not rutas:
            return
        self.cola_total = len(rutas)
        self.cola_pos = 1
        self.cola = rutas[1:]
        self._cargar_archivo(rutas[0])
        self._actualizar_indicador_cola()
        self._guardar_sesion_actual()

    def _cargar_siguiente_de_cola(self):
        siguiente, resto = siguiente_de_cola(self.cola)
        self.cola = resto
        if siguiente is None:
            n = self.lista_pdf.count()
            self.cola_total = 0
            self.cola_pos = 0
            self._actualizar_indicador_cola()
            msg = f"Has terminado la tanda.\n{n} página{'s' if n != 1 else ''} en el PDF."
            QTimer.singleShot(0, lambda: QMessageBox.information(self, "Cola terminada", msg))
            self._guardar_sesion_actual()
            return
        self.cola_pos += 1
        self._cargar_archivo(siguiente)
        self._actualizar_indicador_cola()
        self._guardar_sesion_actual()

    def terminar_y_siguiente(self):
        img = self.procesada_full()
        if img is None:
            QMessageBox.warning(self, "Atención", "Procesa una imagen primero.")
            return
        self.anadir_pagina_pdf(img)
        if self.cola_total:
            self._cargar_siguiente_de_cola()

    def _saltar_actual(self):
        """Pasa a la siguiente foto de la tanda sin añadir la actual al PDF."""
        self._ruta_fallida_actual = ""
        if hasattr(self, "btn_reintentar"):
            self.btn_reintentar.setEnabled(False)
        if self.cola_total:
            self._cargar_siguiente_de_cola()
        else:
            self.statusBar().showMessage("No hay más fotos en la cola", 3000)

    def _vaciar_cola(self):
        """Descarta las fotos que quedan en cola (no toca la foto actual ni el PDF)."""
        if not self.cola and self.cola_total <= 1:
            return
        self.cola = []
        self.cola_total = 1 if self.imagen_original is not None else 0
        self.cola_pos = self.cola_total
        self._actualizar_indicador_cola()
        self.statusBar().showMessage("Cola vaciada", 3000)
        self._guardar_sesion_actual()

    def _actualizar_indicador_cola(self):
        # El grupo se ve mientras haya una tanda activa (aunque en la última
        # foto ya no queden pendientes), para no perder el "Foto X de Y".
        self.lbl_cola.setText(texto_cola(self.cola_pos, self.cola_total))
        self.grupo_cola.setVisible(self.cola_total > 1)
        self._refrescar_miniaturas_cola()
        if self.cola:
            QTimer.singleShot(0, self._iniciar_precalculo_siguiente)

    def _refrescar_miniaturas_cola(self):
        """Repuebla la tira de miniaturas con las fotos que quedan en cola.
        Las miniaturas se generan en segundo plano (un temporizador) para no
        congelar la ventana al soltar 10 fotos grandes de golpe."""
        self.lista_cola.blockSignals(True)
        self.lista_cola.clear()
        for ruta in self.cola:
            item = QListWidgetItem(os.path.basename(ruta))
            item.setData(Qt.ItemDataRole.UserRole, ruta)
            icono = self._cache_thumbs.get(ruta)
            if icono is not None:
                item.setIcon(icono)
            item.setToolTip(os.path.basename(ruta))
            self.lista_cola.addItem(item)
        self.lista_cola.blockSignals(False)
        if any(r not in self._cache_thumbs for r in self.cola):
            self._timer_thumbs.start()

    def _generar_una_miniatura(self):
        """Genera la primera miniatura que falte (una por disparo del timer)."""
        for fila in range(self.lista_cola.count()):
            item = self.lista_cola.item(fila)
            ruta = item.data(Qt.ItemDataRole.UserRole)
            if ruta in self._cache_thumbs:
                continue
            mini = miniatura_archivo(ruta, 64)
            if mini is None:
                self._cache_thumbs[ruta] = QIcon()   # evita reintentar en bucle
            else:
                rgb = cv2.cvtColor(mini, cv2.COLOR_BGR2RGB)
                h, w = rgb.shape[:2]
                qimg = QImage(rgb.data, w, h, 3 * w,
                              QImage.Format.Format_RGB888).copy()
                self._cache_thumbs[ruta] = QIcon(QPixmap.fromImage(qimg))
            item.setIcon(self._cache_thumbs[ruta])
            self._timer_thumbs.start()   # encadena con la siguiente
            return

    def _sincronizar_cola_desde_lista(self, *args):
        """Tras arrastrar para reordenar, rehace self.cola con el nuevo orden."""
        self.cola = [
            self.lista_cola.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.lista_cola.count())
        ]
        self._guardar_sesion_actual()

    def _iniciar_precalculo_siguiente(self):
        if not self.cola:
            return
        ruta = self.cola[0]
        if ruta in self._precalculos:
            return
        trabajador = self._trabajador_precalculo
        if trabajador is not None and trabajador.isRunning():
            return
        trabajador = TrabajadorPrecalculo(ruta, self)
        trabajador.listo.connect(self._al_terminar_precalculo)
        trabajador.finished.connect(self._al_finalizar_hilo_precalculo)
        self._trabajador_precalculo = trabajador
        trabajador.start()

    def _al_terminar_precalculo(self, resultado: PrecalculoResultado):
        self._precalculos[resultado.ruta] = resultado

    def _propuesta_actual(self):
        propuesta = self._precalculos.get(self._ruta_actual)
        if (propuesta is not None and self.imagen_original is not None
                and propuesta.firma_imagen == firma_imagen(self.imagen_original)):
            return propuesta
        return None

    def _al_finalizar_hilo_precalculo(self):
        trabajador = self._trabajador_precalculo
        if trabajador is not None:
            trabajador.deleteLater()
        self._trabajador_precalculo = None

    def _encolar(self, rutas):
        """Añade fotos al final de la cola sin pisar la imagen en curso."""
        rutas = rutas_unicas_en_orden(rutas)
        ya_encoladas = set(self.cola)
        if self._ruta_actual:
            ya_encoladas.add(self._ruta_actual)
        rutas = [ruta for ruta in rutas if ruta not in ya_encoladas]
        if not rutas:
            return
        if self.imagen_original is None and not self.cola:
            self._iniciar_cola(rutas)
            return
        if self.cola_total == 0:
            # La imagen ya cargada pasa a contar como la 1 de la tanda
            self.cola_total = 1
            self.cola_pos = 1
        self.cola.extend(rutas)
        self.cola_total += len(rutas)
        self._actualizar_indicador_cola()
        n = len(rutas)
        self.statusBar().showMessage(
            f"📲 {n} foto{'s' if n != 1 else ''} nueva{'s' if n != 1 else ''} "
            "en la cola", 5000)
        self._guardar_sesion_actual()

    # ----------------------------------------------------------
    # Carpeta vigilada (WhatsApp): encola las fotos que aparezcan
    # ----------------------------------------------------------

    def _actualizar_label_vigilada(self):
        if self.carpeta_vigilada:
            self.lbl_vigilada.setText(f"Carpeta: <b>{self.carpeta_vigilada}</b>")
        else:
            self.lbl_vigilada.setText("<i>Sin carpeta elegida</i>")

    def elegir_carpeta_vigilada(self):
        carpeta = QFileDialog.getExistingDirectory(
            self, "Carpeta a vigilar (p. ej. descargas de WhatsApp)",
            self.carpeta_vigilada or self._ruta_origen)
        if carpeta:
            self.carpeta_vigilada = carpeta
            self.settings.setValue("carpeta_vigilada", carpeta)
            self._actualizar_label_vigilada()
            if self.chk_vigilar.isChecked():
                self._al_toggle_vigilar(True)   # reengancha el vigilante
        return bool(self.carpeta_vigilada)

    def _al_toggle_vigilar(self, activo):
        self.settings.setValue("vigilar", activo)
        if self._watcher.directories():
            self._watcher.removePaths(self._watcher.directories())
        if not activo:
            return
        if not self.carpeta_vigilada or not os.path.isdir(self.carpeta_vigilada):
            if not self.elegir_carpeta_vigilada():
                self.chk_vigilar.setChecked(False)
                return
        # Solo cuentan las fotos que lleguen a partir de ahora
        self._vistos = set(self._listar_imagenes(self.carpeta_vigilada))
        self._observados = {}
        self._identidades_vistas = set()
        for nombre in self._vistos:
            try:
                self._identidades_vistas.add(identidad_archivo(
                    os.path.join(self.carpeta_vigilada, nombre)
                ))
            except OSError:
                pass
        self._watcher.addPath(self.carpeta_vigilada)
        self.statusBar().showMessage(
            f"📲 Vigilando {self.carpeta_vigilada}", 5000)

    def _listar_imagenes(self, carpeta):
        try:
            return [f for f in os.listdir(carpeta) if es_ruta_imagen(f)]
        except OSError:
            return []

    def _al_cambiar_carpeta_vigilada(self, _ruta):
        self._timer_vigia.start()   # debounce: deja terminar la copia

    def _procesar_carpeta_vigilada(self):
        if not self.chk_vigilar.isChecked() \
                or not os.path.isdir(self.carpeta_vigilada):
            return
        actuales = set(self._listar_imagenes(self.carpeta_vigilada))
        nuevas = sorted(actuales - self._vistos)
        listas = []
        pendientes = False
        for nombre in nuevas:
            ruta = os.path.join(self.carpeta_vigilada, nombre)
            try:
                stat = os.stat(ruta)
                observado = self._observados.setdefault(ruta, ArchivoObservado())
                if not observado.actualizar(stat.st_size, stat.st_mtime_ns):
                    pendientes = True
                    continue
                identidad = identidad_archivo(ruta)
            except OSError:
                pendientes = True
                continue
            self._vistos.add(nombre)
            self._observados.pop(ruta, None)
            if identidad in self._identidades_vistas:
                continue
            self._identidades_vistas.add(identidad)
            listas.append(ruta)
        self._vistos.intersection_update(actuales)
        if listas:
            self._encolar(listas)
        if pendientes:
            self._timer_vigia.start()

    def _crear_interfaz(self):
        central = QWidget()
        self.setCentralWidget(central)
        raiz = QVBoxLayout(central)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        cabecera = QFrame()
        cabecera.setObjectName("cabecera")
        cabecera.setFixedHeight(68)
        lc = QHBoxLayout(cabecera)
        lc.setContentsMargins(22, 12, 22, 12)
        logo = QLabel()
        logo.setPixmap(QPixmap(estilo.ruta_recurso("icono.png")).scaled(
            48, 48, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation))
        logo.setFixedSize(52, 52)
        lc.addWidget(logo)
        marca = QVBoxLayout()
        titulo = QLabel("Escáner de facturas")
        titulo.setObjectName("marca")
        subtitulo = QLabel("Pegue, revise y envíe las facturas a Aplifisa")
        subtitulo.setObjectName("marcaSubtitulo")
        marca.addWidget(titulo)
        marca.addWidget(subtitulo)
        lc.addLayout(marca)
        lc.addStretch()
        self.accion_pegar_cabecera = QPushButton("Pegar  Ctrl+V")
        self.accion_pegar_cabecera.setObjectName("accionPegar")
        self.accion_pegar_cabecera.setProperty("role", "cabeceraAccion")
        self.accion_pegar_cabecera.setToolTip(
            "Pegar la imagen que tengas en el portapapeles"
        )
        self.accion_pegar_cabecera.clicked.connect(self.pegar_imagen)
        lc.addWidget(self.accion_pegar_cabecera)
        self.accion_abrir_cabecera = QPushButton("Abrir fotos…")
        self.accion_abrir_cabecera.setObjectName("accionAbrir")
        self.accion_abrir_cabecera.setProperty("role", "cabeceraAccion")
        self.accion_abrir_cabecera.setToolTip(
            "También puedes arrastrar varias fotos sobre la ventana"
        )
        self.accion_abrir_cabecera.clicked.connect(self.abrir_imagen)
        lc.addWidget(self.accion_abrir_cabecera)
        self.btn_actualizacion_lista = QPushButton("Reiniciar y actualizar")
        self.btn_actualizacion_lista.setObjectName("actualizacionLista")
        self.btn_actualizacion_lista.clicked.connect(
            self.instalar_actualizacion_lista
        )
        self.btn_actualizacion_lista.setVisible(False)
        lc.addWidget(self.btn_actualizacion_lista)
        raiz.addWidget(cabecera)

        contenido = QWidget()
        layout = QHBoxLayout(contenido)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        raiz.addWidget(contenido, 1)

        # Columna izquierda: original
        col_izq = QVBoxLayout()
        lbl_orig = QLabel("Foto original")
        lbl_orig.setObjectName("tituloLienzo")
        col_izq.addWidget(lbl_orig)
        self.lienzo_original = LienzoImagen()
        self.lienzo_original.puntos_listos.connect(self._al_recibir_puntos_manuales)
        self.lienzo_original.puntos_editados.connect(self._al_recibir_puntos_manuales)
        self.lienzo_original.imagenes_soltadas.connect(self._iniciar_cola)
        col_izq.addWidget(self.lienzo_original)
        w_izq = QWidget()
        w_izq.setObjectName("zonaOriginal")
        w_izq.setLayout(col_izq)

        # Columna central: controles (con scroll para que no se solapen en pantalla completa)
        w_ctrl = self._construir_panel_controles()
        self.scroll_controles = QScrollArea()
        self.scroll_controles.setWidgetResizable(True)
        self.scroll_controles.setWidget(w_ctrl)
        self.scroll_controles.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.scroll_controles.setMinimumWidth(360)
        self.scroll_controles.setMaximumWidth(410)
        self.scroll_controles.setFrameShape(QScrollArea.Shape.NoFrame)
        centro = QWidget()
        centro.setObjectName("panelControles")
        centro_layout = QVBoxLayout(centro)
        centro_layout.setContentsMargins(0, 0, 0, 0)
        centro_layout.setSpacing(8)
        centro_layout.addWidget(self.scroll_controles, 1)
        centro.setMinimumWidth(360)
        centro.setMaximumWidth(410)

        # Columna derecha: resultado
        col_der = QVBoxLayout()
        lbl_res = QLabel("Resultado")
        lbl_res.setObjectName("tituloLienzo")
        col_der.addWidget(lbl_res)
        self.lienzo_resultado = LienzoImagen()
        col_der.addWidget(self.lienzo_resultado)
        w_der = QWidget()
        w_der.setObjectName("zonaResultado")
        w_der.setLayout(col_der)

        layout.addWidget(w_izq, 4)
        layout.addWidget(centro, 0)
        layout.addWidget(w_der, 4)

    def _construir_panel_controles(self):
        panel = QVBoxLayout()
        panel.setSpacing(8)

        titulo = QLabel("Documento actual")
        titulo.setObjectName("tituloPanel")
        ayuda = QLabel("El recorte se detecta automáticamente. Corríjalo solo si hace falta.")
        ayuda.setObjectName("subtituloPanel")
        ayuda.setWordWrap(True)
        panel.addWidget(titulo)
        panel.addWidget(ayuda)

        contexto = QGroupBox("Perfil y cliente")
        contexto_layout = QVBoxLayout(contexto)
        fila_perfil = QHBoxLayout()
        fila_perfil.addWidget(QLabel("Perfil:"))
        self.combo_perfil = QComboBox()
        self.combo_perfil.addItems(self._perfiles)
        fila_perfil.addWidget(self.combo_perfil, 1)
        self.btn_guardar_perfil = QPushButton("Guardar ajustes")
        fila_perfil.addWidget(self.btn_guardar_perfil)
        contexto_layout.addLayout(fila_perfil)
        fila_cliente = QHBoxLayout()
        fila_cliente.addWidget(QLabel("Cliente:"))
        self.combo_cliente = QComboBox()
        self.combo_cliente.addItem("Sin cliente", None)
        for nif, cliente in leer_clientes().items():
            nombre = cliente.get("nombre") or nif
            self.combo_cliente.addItem(f"{nombre} · {nif}", cliente)
        fila_cliente.addWidget(self.combo_cliente, 1)
        contexto_layout.addLayout(fila_cliente)
        panel.addWidget(contexto)

        # === Entrada rápida ===
        g1 = QGroupBox("Entrada rápida")
        l1 = QVBoxLayout(g1)
        btn_abrir = QPushButton("Abrir o arrastrar varias fotos…")
        btn_abrir.setMinimumHeight(38)
        btn_abrir.setToolTip(
            "También puedes arrastrar varias fotos a la vez sobre la ventana, "
            "o pegar con Ctrl+V.")
        btn_abrir.clicked.connect(self.abrir_imagen)
        l1.addWidget(btn_abrir)
        btn_pegar = QPushButton("Pegar del portapapeles  (Ctrl+V)")
        btn_pegar.clicked.connect(self.pegar_imagen)
        l1.addWidget(btn_pegar)
        self.btn_quitar = QPushButton("Quitar la foto actual")
        self.btn_quitar.setToolTip(
            "Vacía la foto cargada para empezar de cero (p. ej. si pegaste la "
            "que no era). No borra las páginas ya añadidas al PDF.")
        self.btn_quitar.clicked.connect(self.quitar_imagen)
        l1.addWidget(self.btn_quitar)
        panel.addWidget(g1)

        # === Cola de fotos (tanda de WhatsApp) ===
        self.grupo_cola = QGroupBox("Cola de fotos")
        lc = QVBoxLayout(self.grupo_cola)
        self.lbl_cola = QLabel("")
        self.lbl_cola.setObjectName("indicadorCola")
        lc.addWidget(self.lbl_cola)
        self.lista_cola = QListWidget()
        self.lista_cola.setViewMode(QListWidget.ViewMode.IconMode)
        self.lista_cola.setIconSize(QSize(54, 70))
        self.lista_cola.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.lista_cola.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.lista_cola.setMaximumHeight(104)
        self.lista_cola.setToolTip(
            "Fotos que faltan por procesar. Arrastra para reordenarlas.")
        self.lista_cola.model().rowsMoved.connect(self._sincronizar_cola_desde_lista)
        lc.addWidget(self.lista_cola)
        fila_cola = QHBoxLayout()
        btn_saltar = QPushButton("Saltar esta")
        btn_saltar.setToolTip("Pasa a la siguiente foto sin añadir esta al PDF.")
        btn_saltar.clicked.connect(self._saltar_actual)
        btn_vaciar_cola = QPushButton("Vaciar cola")
        btn_vaciar_cola.clicked.connect(self._vaciar_cola)
        self.btn_reintentar = QPushButton("Reintentar foto")
        self.btn_reintentar.setEnabled(False)
        self.btn_reintentar.clicked.connect(self.reintentar_actual)
        fila_cola.addWidget(btn_saltar)
        fila_cola.addWidget(self.btn_reintentar)
        fila_cola.addWidget(btn_vaciar_cola)
        lc.addLayout(fila_cola)
        self.grupo_cola.setVisible(False)
        panel.addWidget(self.grupo_cola)

        # === Recortar y enderezar (incluye rotación) ===
        g2 = QGroupBox("Recorte y orientación")
        l2 = QVBoxLayout(g2)
        btn_auto = QPushButton("Volver a detectar el documento  (F5)")
        btn_auto.setMinimumHeight(38)
        btn_auto.clicked.connect(self.detectar_auto)
        l2.addWidget(btn_auto)
        btn_multi = QPushButton("Detectar varios tickets en la foto")
        btn_multi.setToolTip("Si hay varios tickets sobre la mesa, los recorta por separado y los encola")
        btn_multi.clicked.connect(self.detectar_multiples_tickets)
        l2.addWidget(btn_multi)
        btn_man = QPushButton("Corregir las 4 esquinas")
        btn_man.setMinimumHeight(38)
        btn_man.clicked.connect(self.iniciar_manual)
        l2.addWidget(btn_man)
        btn_sin_recortar = QPushButton("Usar la foto sin recortar")
        btn_sin_recortar.clicked.connect(self.usar_sin_recortar)
        l2.addWidget(btn_sin_recortar)
        fila_rot = QHBoxLayout()
        btn_auto_rot = QPushButton("Auto")
        btn_auto_rot.setToolTip("Detecta la orientación del texto y gira el documento automáticamente (Ctrl+Shift+R)")
        btn_auto_rot.clicked.connect(self.auto_orientar)
        btn_rot_izq = QPushButton("⟲ 90°")
        btn_rot_der = QPushButton("⟳ 90°")
        btn_rot_180 = QPushButton("180°")
        btn_rot_izq.setToolTip("Rotar 90° a la izquierda")
        btn_rot_der.setToolTip("Rotar 90° a la derecha")
        btn_rot_180.setToolTip("Rotar 180°")
        btn_rot_izq.clicked.connect(lambda: self.rotar_original(270))
        btn_rot_der.clicked.connect(lambda: self.rotar_original(90))
        btn_rot_180.clicked.connect(lambda: self.rotar_original(180))
        fila_rot.addWidget(btn_auto_rot)
        fila_rot.addWidget(btn_rot_izq)
        fila_rot.addWidget(btn_rot_der)
        fila_rot.addWidget(btn_rot_180)
        l2.addLayout(fila_rot)
        self.lbl_estado_recorte = QLabel()
        self._estado_recorte("Sin recortar")
        l2.addWidget(self.lbl_estado_recorte)
        panel.addWidget(g2)

        # === Tipo de salida ===
        g3 = QGroupBox("Resultado")
        l3 = QVBoxLayout(g3)
        self.combo_filtro = QComboBox()
        self.combo_filtro.addItems([
            "B/N nítido · recomendado para facturas",
            "B/N puro tinta · avanzado",
            "Color limpio · avanzado",
            "Color original · sin tratamiento",
        ])
        self.combo_filtro.setMinimumHeight(34)
        self.combo_filtro.currentIndexChanged.connect(self._al_cambiar_filtro)
        l3.addWidget(self.combo_filtro)
        self.sld_intensidad_bn, fila_int_bn = self._crear_slider("Intensidad", 0, 100, 50)
        self.cont_intensidad = QWidget()
        self.cont_intensidad.setLayout(fila_int_bn)
        l3.addWidget(self.cont_intensidad)
        panel.addWidget(g3)

        # === 5. Ajustes finos ===
        cont_aj = QWidget()
        l4 = QVBoxLayout(cont_aj)
        l4.setContentsMargins(0, 0, 0, 0)
        self.sld_brillo,    fila1 = self._crear_slider("Brillo",    -100, 100, 0)
        self.sld_contraste, fila2 = self._crear_slider("Contraste", -100, 100, 0)
        self.sld_nitidez,   fila3 = self._crear_slider("Nitidez",      0, 100, 0)
        l4.addLayout(fila1); l4.addLayout(fila2); l4.addLayout(fila3)
        btn_reset = QPushButton("Resetear ajustes  (Ctrl+R)")
        btn_reset.clicked.connect(self.reset_ajustes)
        l4.addWidget(btn_reset)
        panel.addWidget(self._grupo_plegable("Ajustes finos", cont_aj, abierto=False))

        self.btn_terminar = QPushButton("Añadir al lote y siguiente")
        self.btn_terminar.setObjectName("btnPrimario")
        self.btn_terminar.setMinimumHeight(46)
        self.btn_terminar.clicked.connect(self.terminar_y_siguiente)
        panel.addWidget(self.btn_terminar)

        # === Guardar ===
        g5 = QWidget()
        l5 = QVBoxLayout(g5)
        l5.setContentsMargins(0, 0, 0, 0)

        # Prefijo del nombre de archivo: 'Perez_2026-06-10_14-33-12.jpg'
        fila_pref = QHBoxLayout()
        lbl_pref = QLabel("Prefijo:")
        fila_pref.addWidget(lbl_pref)
        self.txt_prefijo = QLineEdit()
        self.txt_prefijo.setPlaceholderText("cliente o concepto (opcional)")
        self.txt_prefijo.setClearButtonEnabled(True)
        self.txt_prefijo.textChanged.connect(
            lambda t: self.settings.setValue("prefijo", t))
        fila_pref.addWidget(self.txt_prefijo, 1)
        l5.addLayout(fila_pref)

        # Guardado rápido: destino fijo + nombre por fecha-hora, sin diálogos
        btn_rapido = QPushButton("Guardado rápido  (Enter)")
        btn_rapido.setObjectName("btnExito")
        btn_rapido.setMinimumHeight(44)
        btn_rapido.clicked.connect(self.guardado_rapido)
        l5.addWidget(btn_rapido)

        fila_carpeta = QHBoxLayout()
        self.lbl_carpeta_salida = QLabel()
        self.lbl_carpeta_salida.setObjectName("infoSuave")
        self.lbl_carpeta_salida.setWordWrap(True)
        fila_carpeta.addWidget(self.lbl_carpeta_salida, 1)
        btn_cambiar_carpeta = QPushButton("Cambiar")
        btn_cambiar_carpeta.setMaximumWidth(90)
        btn_cambiar_carpeta.clicked.connect(self.elegir_carpeta_salida)
        fila_carpeta.addWidget(btn_cambiar_carpeta)
        l5.addLayout(fila_carpeta)

        btn_jpg = QPushButton("Guardar como JPG…  (Ctrl+S)")
        btn_jpg.setMinimumHeight(36)
        btn_jpg.clicked.connect(lambda: self.guardar("jpg"))
        l5.addWidget(btn_jpg)
        btn_png = QPushButton("Guardar como PNG…  (Ctrl+E)")
        btn_png.setMinimumHeight(36)
        btn_png.clicked.connect(lambda: self.guardar("png"))
        l5.addWidget(btn_png)
        btn_pdf = QPushButton("Guardar como PDF…  (Ctrl+Shift+S)")
        btn_pdf.setMinimumHeight(36)
        btn_pdf.clicked.connect(lambda: self.guardar("pdf"))
        l5.addWidget(btn_pdf)
        # === PDF de varias fotos (miniaturas reordenables) ===
        g6 = QGroupBox("Lote preparado")
        l6 = QVBoxLayout(g6)
        self.lista_pdf = QListWidget()
        self.lista_pdf.setViewMode(QListWidget.ViewMode.IconMode)
        self.lista_pdf.setIconSize(QSize(80, 104))
        self.lista_pdf.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.lista_pdf.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.lista_pdf.setSelectionMode(
            QListWidget.SelectionMode.ExtendedSelection)
        self.lista_pdf.setMinimumHeight(130)
        self.lista_pdf.setToolTip("Arrastra las miniaturas para ordenar las páginas")
        self.lista_pdf.model().rowsMoved.connect(
            lambda *_args: self._guardar_sesion_actual()
        )
        l6.addWidget(self.lista_pdf)
        fila_pdf = QHBoxLayout()
        btn_add_pdf = QPushButton("Añadir")
        btn_add_pdf.clicked.connect(lambda: self.anadir_pagina_pdf())
        btn_quitar_pdf = QPushButton("Quitar")
        btn_quitar_pdf.clicked.connect(self.quitar_pagina_pdf)
        btn_vaciar_pdf = QPushButton("Vaciar")
        btn_vaciar_pdf.clicked.connect(self.vaciar_paginas_pdf)
        fila_pdf.addWidget(btn_add_pdf)
        fila_pdf.addWidget(btn_quitar_pdf)
        fila_pdf.addWidget(btn_vaciar_pdf)
        l6.addLayout(fila_pdf)
        btn_dni = QPushButton("Unir 2 en 1 hoja (DNI)")
        btn_dni.setToolTip(
            "Combina las dos páginas seleccionadas (o las dos últimas) en una "
            "sola hoja A4: cara delantera arriba y trasera abajo.")
        btn_dni.clicked.connect(self.combinar_dni)
        l6.addWidget(btn_dni)
        self.panel_finalizacion = QFrame()
        self.panel_finalizacion.setObjectName("panelFinalizacion")
        acciones_finales = QVBoxLayout(self.panel_finalizacion)
        acciones_finales.setContentsMargins(0, 8, 0, 0)
        self.btn_exportar_lote = QPushButton("Exportar PDF…")
        self.btn_exportar_lote.setMinimumHeight(36)
        self.btn_exportar_lote.clicked.connect(self.exportar_pdf_multipagina)
        acciones_finales.addWidget(self.btn_exportar_lote)
        self.btn_enviar_aplifisa = QPushButton("Enviar a Facturas a Aplifisa")
        self.btn_enviar_aplifisa.setObjectName("btnEnviar")
        self.btn_enviar_aplifisa.setMinimumHeight(46)
        self.btn_enviar_aplifisa.setToolTip(
            "Guarda el PDF y abre Facturas a Aplifisa con el lote ya cargado.")
        self.btn_enviar_aplifisa.clicked.connect(self.enviar_a_aplifisa)
        acciones_finales.addWidget(self.btn_enviar_aplifisa)
        self.btn_deshacer_ultima = QPushButton("Deshacer última página")
        self.btn_deshacer_ultima.clicked.connect(self.deshacer_ultima_pagina)
        acciones_finales.addWidget(self.btn_deshacer_ultima)
        self.panel_finalizacion.setVisible(False)
        l6.addWidget(self.panel_finalizacion)
        panel.addWidget(g6)

        panel.addWidget(self._grupo_plegable(
            "Otros formatos y guardado rápido", g5, abierto=False))

        # === Más opciones (lo poco habitual, plegado) ===
        cont_mas = QWidget()
        l_mas = QVBoxLayout(cont_mas)
        l_mas.setContentsMargins(0, 0, 0, 0)
        self.chk_vigilar = QCheckBox(
            "Vigilar una carpeta (WhatsApp): las fotos nuevas entran solas")
        self.chk_vigilar.toggled.connect(self._al_toggle_vigilar)
        l_mas.addWidget(self.chk_vigilar)
        fila_vig = QHBoxLayout()
        self.lbl_vigilada = QLabel()
        self.lbl_vigilada.setObjectName("infoSuave")
        self.lbl_vigilada.setWordWrap(True)
        fila_vig.addWidget(self.lbl_vigilada, 1)
        btn_vigilada = QPushButton("Elegir carpeta")
        btn_vigilada.clicked.connect(self.elegir_carpeta_vigilada)
        fila_vig.addWidget(btn_vigilada)
        l_mas.addLayout(fila_vig)
        self.btn_comprobar_actualizaciones = QPushButton(
            "Comprobar actualizaciones"
        )
        self.btn_comprobar_actualizaciones.clicked.connect(
            lambda: actualizador.conectar(self, __version__, manual=True)
        )
        l_mas.addWidget(self.btn_comprobar_actualizaciones)
        grupo_mas = self._grupo_plegable("Más opciones", cont_mas, abierto=False)
        grupo_mas.setObjectName("masOpciones")
        panel.addWidget(grupo_mas)

        self.combo_perfil.currentTextChanged.connect(self._aplicar_perfil)
        self.btn_guardar_perfil.clicked.connect(self._guardar_perfil_actual)
        self.combo_cliente.currentIndexChanged.connect(self._al_seleccionar_cliente)

        panel.addStretch()

        w = QWidget()
        w.setLayout(panel)
        w.setMinimumWidth(300)
        return w

    def _crear_slider(self, nombre, mn, mx, val):
        fila = QHBoxLayout()
        lbl = QLabel(f"{nombre}:")
        lbl.setMinimumWidth(75)
        sld = QSlider(Qt.Orientation.Horizontal)
        sld.setRange(mn, mx)
        sld.setValue(val)
        lbl_val = QLabel(str(val))
        lbl_val.setMinimumWidth(35)
        lbl_val.setAlignment(Qt.AlignmentFlag.AlignRight)
        sld.valueChanged.connect(lambda v: lbl_val.setText(str(v)))
        sld.valueChanged.connect(self._programar_actualizacion)
        fila.addWidget(lbl)
        fila.addWidget(sld)
        fila.addWidget(lbl_val)
        return sld, fila

    # ----------------------------------------------------------
    # Acciones
    # ----------------------------------------------------------

    def abrir_imagen(self):
        patron = " ".join("*" + e for e in EXTENSIONES_IMAGEN)
        rutas, _ = QFileDialog.getOpenFileNames(
            self, "Abrir imágenes", self._ruta_origen,
            f"Imágenes ({patron});;Todos los archivos (*.*)")
        if rutas:
            self._iniciar_cola(rutas)

    def _cargar_archivo(self, ruta):
        try:
            img = leer_imagen(ruta)
            if img is None:
                raise ValueError("No se pudo leer el archivo.")
            self._cargar_cv(img, os.path.dirname(ruta), ruta)
            self._ruta_fallida_actual = ""
            self._errores_cola.pop(ruta, None)
            self.btn_reintentar.setEnabled(False)
            self._guardar_sesion_actual()
            return True
        except Exception as e:
            self._ruta_fallida_actual = ruta
            self._errores_cola[ruta] = str(e)
            self.btn_reintentar.setEnabled(True)
            if self.cola:
                # El resto del lote permanece en su orden; esta foto se puede
                # reintentar o saltar sin afectar páginas confirmadas.
                self.imagen_original = None
                self.imagen_enderezada = None
                self.statusBar().showMessage(
                    f"⚠️ {os.path.basename(ruta)} no se pudo abrir ({e}); "
                    "corrige el archivo y pulsa Reintentar, o sáltalo", 8000)
            else:
                if self.cola_total:
                    self.cola_total = 0
                    self.cola_pos = 0
                    self._actualizar_indicador_cola()
                QMessageBox.critical(
                    self, "Error", f"No se pudo abrir la imagen:\n{e}")
            self._guardar_sesion_actual()
            return False

    def reintentar_actual(self):
        ruta = self._ruta_fallida_actual
        if not ruta:
            return
        if self._cargar_archivo(ruta):
            self.statusBar().showMessage(
                f"Foto recuperada: {os.path.basename(ruta)}", 4000
            )
            self._guardar_sesion_actual()

    def _cargar_cv(self, img, ruta_origen="", ruta_actual=""):
        self.imagen_original = img
        self.imagen_enderezada = None
        self._ruta_origen = ruta_origen or self._ruta_origen
        self._ruta_actual = ruta_actual
        self.lienzo_original.limpiar_puntos()
        self.lienzo_original.mostrar_imagen(img)
        self._estado_recorte("Sin recortar")
        self._resetear_sliders()
        self._actualizar_preview_base()
        self.detectar_auto(silencioso=True)
        self.actualizar_procesado()
        self._actualizar_barra_estado()
        self._guardar_sesion_actual()

    def _qimage_a_cv(self, qimg):
        """Convierte un QImage (p. ej. del portapapeles) a array OpenCV BGR.
        Lo hace serializando a PNG en memoria y decodificando con OpenCV: es
        robusto en cualquier plataforma y formato (evita el manejo de buffer
        crudo de constBits(), que falla en Windows)."""
        if qimg.isNull():
            return None
        ba = QByteArray()
        buf = QBuffer(ba)
        buf.open(QBuffer.OpenModeFlag.WriteOnly)
        qimg.save(buf, "PNG")
        buf.close()
        data = np.frombuffer(bytes(ba), dtype=np.uint8)
        return cv2.imdecode(data, cv2.IMREAD_COLOR)

    def pegar_imagen(self):
        try:
            cb = QApplication.clipboard()
            md = cb.mimeData()
            if md.hasImage():
                img = self._qimage_a_cv(cb.image())
                if img is not None and img.size:
                    self._cargar_cv(img)
                    self.statusBar().showMessage("Imagen pegada del portapapeles", 4000)
                    return
            rutas = _rutas_imagen_de(md)
            if rutas:
                self._cargar_archivo(rutas[0])
                return
            self.statusBar().showMessage(
                "El portapapeles no contiene una imagen "
                "(si quieres vaciar la foto actual, usa «Quitar la foto actual»)",
                6000)
        except Exception as e:
            self.statusBar().showMessage(f"No se pudo pegar la imagen: {e}", 6000)

    def quitar_imagen(self):
        """Vacía la foto cargada y deja la app como recién abierta (sin tocar
        las páginas ya añadidas al PDF). Resuelve el caso de pegar una imagen
        equivocada y que se quede 'bloqueada' la anterior."""
        if self.imagen_original is None:
            self.statusBar().showMessage("No hay ninguna foto cargada", 3000)
            return
        self.imagen_original = None
        self.imagen_enderezada = None
        self._preview_base = None
        self._ruta_actual = ""
        self.lienzo_original.cancelar_seleccion()
        self.lienzo_original.limpiar_puntos()
        self.lienzo_original.mostrar_imagen(None)
        self.lienzo_resultado.mostrar_imagen(None)
        self._estado_recorte("Sin recortar")
        self._resetear_sliders()
        # Vacía también la cola de la tanda en curso (las páginas del PDF se quedan)
        self.cola = []
        self.cola_total = 0
        self.cola_pos = 0
        self._actualizar_indicador_cola()
        self._actualizar_barra_estado()
        self.statusBar().showMessage("Foto quitada — pega (Ctrl+V) o abre otra", 4000)
        self._guardar_sesion_actual()

    def rotar_original(self, grados):
        if self.imagen_original is None:
            return
        self.imagen_original = rotar_imagen(self.imagen_original, grados)
        self.imagen_enderezada = None
        self.lienzo_original.limpiar_puntos()
        self.lienzo_original.mostrar_imagen(self.imagen_original)
        self._estado_recorte("Sin recortar")
        self._actualizar_preview_base()
        self.actualizar_procesado()
        self._actualizar_barra_estado()

    def auto_orientar(self):
        if self.imagen_original is None:
            self.statusBar().showMessage("Primero abre una imagen para auto-orientar", 3000)
            return
        base = self.imagen_enderezada if self.imagen_enderezada is not None else self.imagen_original
        propuesta = self._propuesta_actual()
        if propuesta is not None and self.imagen_enderezada is None:
            grados = propuesta.rotacion
        else:
            _, grados = auto_orientar_documento(base)
        if grados != 0:
            if self.imagen_enderezada is not None:
                self.imagen_enderezada = rotar_imagen(self.imagen_enderezada, grados)
                self._actualizar_preview_base()
                self.actualizar_procesado()
            else:
                self.rotar_original(grados)
            self.statusBar().showMessage(f"🪄 Documento auto-orientado ({grados}°)", 4000)
        else:
            self.statusBar().showMessage("El documento ya tiene la orientación correcta", 3000)

    def detectar_multiples_tickets(self):
        if self.imagen_original is None:
            QMessageBox.warning(self, "Atención", "Primero abre una imagen con varios tickets.")
            return
        docs = detectar_multiples_documentos(self.imagen_original)
        if not docs or len(docs) <= 1:
            self.detectar_auto(silencioso=False)
            return

        # El primer ticket pasa a ser la imagen activa actual
        puntos_0 = docs[0]
        self.lienzo_original.mostrar_esquinas(puntos_0.tolist())
        crop_0 = corregir_perspectiva(self.imagen_original, puntos_0)
        crop_0, _ = auto_orientar_documento(crop_0)
        self.imagen_enderezada = crop_0
        self._estado_recorte(f"Ticket 1/{len(docs)} detectado", ok=True)
        self._actualizar_preview_base()
        self.actualizar_procesado()

        # Los siguientes tickets se procesan y se añaden directamente como páginas al lote
        filt_idx, br, ct, nit, int_bn = self._params()
        for idx, puntos_i in enumerate(docs[1:], start=2):
            crop_i = corregir_perspectiva(self.imagen_original, puntos_i)
            crop_i, _ = auto_orientar_documento(crop_i)
            proc_i = aplicar_pipeline(crop_i, filt_idx, br, ct, nit, int_bn)
            self.anadir_pagina_pdf(proc_i)

        QMessageBox.information(
            self, "Múltiples tickets detectados",
            f"Se han detectado {len(docs)} tickets en la foto:\n\n"
            f"• Ticket 1: cargado en pantalla para revisar.\n"
            f"• Tickets 2 a {len(docs)}: añadidos directamente al lote del PDF.\n\n"
            "Pulsa «Añadir al lote y siguiente» cuando termines de revisar el primer ticket."
        )

    def detectar_auto(self, silencioso=False):
        if self.imagen_original is None:
            if not silencioso:
                QMessageBox.warning(self, "Atención", "Primero abre una imagen.")
            return
        propuesta = self._propuesta_actual()
        puntos = propuesta.puntos if propuesta is not None else detectar_documento(
            self.imagen_original
        )
        if puntos is None:
            if not silencioso:
                QMessageBox.information(
                    self, "Sin detección",
                    "No se ha podido detectar el documento automáticamente.\n\n"
                    "Opciones:\n"
                    "  • Marca las 4 esquinas a mano.\n"
                    "  • Usa «Sin recortar» si el papel ya ocupa toda la foto."
                )
            return
        self.lienzo_original.mostrar_esquinas(puntos.tolist())
        self.imagen_enderezada = corregir_perspectiva(self.imagen_original, puntos)
        self._estado_recorte("Recorte automático", ok=True)
        self._actualizar_preview_base()
        self.actualizar_procesado()

    def iniciar_manual(self):
        if self.imagen_original is None:
            QMessageBox.warning(self, "Atención", "Primero abre una imagen.")
            return
        self.lienzo_original.iniciar_seleccion_manual()
        self._estado_recorte("Haz clic en las 4 esquinas del documento…")

    def _al_recibir_puntos_manuales(self, puntos):
        puntos_np = np.array(puntos, dtype=np.float32)
        self.imagen_enderezada = corregir_perspectiva(
            self.imagen_original, puntos_np
        )
        self._estado_recorte("Recorte manual", ok=True)
        self._actualizar_preview_base()
        self.actualizar_procesado()

    def usar_sin_recortar(self):
        if self.imagen_original is None:
            return
        self.imagen_enderezada = None
        self.lienzo_original.limpiar_puntos()
        self._estado_recorte("Sin recortar")
        self._actualizar_preview_base()
        self.actualizar_procesado()

    # --- Procesado: vista previa (rápida) vs. resolución completa ---

    def _base_full(self):
        """Imagen base a resolución completa (enderezada si la hay)."""
        if self.imagen_enderezada is not None:
            return self.imagen_enderezada
        return self.imagen_original

    def _params(self):
        """Parámetros actuales de filtro y ajustes finos."""
        return (
            self.combo_filtro.currentIndex(),
            self.sld_brillo.value(),
            self.sld_contraste.value(),
            self.sld_nitidez.value(),
            self.sld_intensidad_bn.value(),
        )

    def _actualizar_preview_base(self):
        """Reduce la base a máx. 1400 px para que la vista previa vuele."""
        base = self._base_full()
        if base is None:
            self._preview_base = None
            return
        h, w = base.shape[:2]
        m = max(h, w)
        if m > 1400:
            r = 1400.0 / m
            self._preview_base = cv2.resize(
                base, None, fx=r, fy=r, interpolation=cv2.INTER_AREA
            )
        else:
            self._preview_base = base

    def _programar_actualizacion(self):
        """Reinicia el temporizador de debounce de los sliders."""
        self._timer_preview.start()

    def procesada_full(self):
        """Procesa la base a resolución completa con los parámetros actuales."""
        base = self._base_full()
        if base is None:
            return None
        return aplicar_pipeline(base, *self._params())

    def actualizar_procesado(self):
        """Refresca solo la vista previa (sobre la imagen reducida)."""
        if self._preview_base is None:
            self.lienzo_resultado.mostrar_imagen(None)
            return
        img = aplicar_pipeline(self._preview_base, *self._params())
        self.lienzo_resultado.mostrar_imagen(img)
        self._actualizar_barra_estado()

    def _resetear_sliders(self):
        for sld in (self.sld_brillo, self.sld_contraste, self.sld_nitidez):
            sld.blockSignals(True)
            sld.setValue(0)
            sld.blockSignals(False)

    def reset_ajustes(self):
        self._resetear_sliders()
        self.actualizar_procesado()

    def _al_cambiar_filtro(self, idx):
        self.settings.setValue("filtro_idx2", idx)
        # La intensidad solo aplica a los dos modos B/N
        self.cont_intensidad.setVisible(idx <= 1)
        self.actualizar_procesado()

    def _aplicar_perfil(self, nombre):
        perfil = self._perfiles.get(nombre)
        if perfil is None:
            return
        self._perfil_actual = nombre
        controles = (
            (self.combo_filtro, perfil.filtro),
            (self.sld_intensidad_bn, perfil.intensidad),
            (self.sld_brillo, perfil.brillo),
            (self.sld_contraste, perfil.contraste),
            (self.sld_nitidez, perfil.nitidez),
        )
        for control, valor in controles:
            control.blockSignals(True)
            if isinstance(control, QComboBox):
                control.setCurrentIndex(valor)
            else:
                control.setValue(valor)
            control.blockSignals(False)
        self.cont_intensidad.setVisible(perfil.filtro <= 1)
        if perfil.destino:
            self.carpeta_salida = perfil.destino
            self._actualizar_label_carpeta()
        self.actualizar_procesado()
        self._guardar_sesion_actual()

    def _guardar_perfil_actual(self):
        nombre = self.combo_perfil.currentText() or "Factura"
        filtro, brillo, contraste, nitidez, intensidad = self._params()
        perfil = PerfilEscaneo(
            nombre, filtro, intensidad, brillo, contraste, nitidez,
            self.carpeta_salida,
        )
        guardar_perfil(perfil)
        self._perfiles[nombre] = perfil
        self.statusBar().showMessage(f"Perfil {nombre} guardado", 3000)

    def _al_seleccionar_cliente(self, indice):
        cliente = self.combo_cliente.itemData(indice)
        if not cliente:
            return
        sugerencia = cliente.get("nombre") or cliente.get("nif", "")
        if sugerencia:
            self.txt_prefijo.setText(str(sugerencia))
        carpeta = cliente.get("carpeta") or cliente.get("destino")
        if carpeta:
            self.carpeta_salida = str(carpeta)
            self._actualizar_label_carpeta()
        self._guardar_sesion_actual()

    # ----------------------------------------------------------
    # Guardado rápido (carpeta fija + nombre por fecha-hora)
    # ----------------------------------------------------------

    def _actualizar_label_carpeta(self):
        if self.carpeta_salida:
            self.lbl_carpeta_salida.setText(
                f"Carpeta: <b>{self.carpeta_salida}</b>"
            )
        else:
            self.lbl_carpeta_salida.setText(
                "<i>Sin carpeta fija (se preguntará al guardar)</i>"
            )

    def elegir_carpeta_salida(self):
        inicio = self.carpeta_salida or self._ruta_origen
        carpeta = QFileDialog.getExistingDirectory(
            self, "Elige la carpeta donde guardar los escaneos", inicio
        )
        if carpeta:
            self.carpeta_salida = carpeta
            self.settings.setValue("carpeta_salida", carpeta)
            self._actualizar_label_carpeta()
        return bool(self.carpeta_salida)

    def _prefijo_limpio(self):
        """Prefijo apto para nombre de archivo (sin caracteres prohibidos)."""
        texto = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "", self.txt_prefijo.text())
        return texto.strip(" .")

    def _nombre_por_fecha(self, carpeta, ext=".jpg"):
        """Genera '[prefijo_]AAAA-MM-DD_HH-MM-SS.jpg', evitando pisar archivos."""
        base = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        prefijo = self._prefijo_limpio()
        if prefijo:
            base = f"{prefijo}_{base}"
        ruta = os.path.join(carpeta, base + ext)
        n = 2
        while os.path.exists(ruta):
            ruta = os.path.join(carpeta, f"{base}_{n}{ext}")
            n += 1
        return ruta

    def guardado_rapido(self):
        img = self.procesada_full()
        if img is None:
            QMessageBox.warning(self, "Atención", "No hay nada que guardar todavía.")
            return

        # Asegura una carpeta de destino válida (la pide solo la 1ª vez)
        if not self.carpeta_salida or not os.path.isdir(self.carpeta_salida):
            if not self.elegir_carpeta_salida():
                return

        ruta = self._nombre_por_fecha(self.carpeta_salida, ".jpg")
        try:
            ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 95])
            if not ok:
                raise RuntimeError("Error codificando JPEG")
            buf.tofile(ruta)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo guardar:\n{e}")
            return

        # Aviso no bloqueante en la barra de estado (no frena el flujo)
        self.statusBar().showMessage(
            f"✅ Guardado: {os.path.basename(ruta)}  →  {self.carpeta_salida}", 6000
        )

    def guardar(self, formato):
        img = self.procesada_full()
        if img is None:
            QMessageBox.warning(self, "Atención", "No hay nada que guardar todavía.")
            return

        formatos = {
            "jpg": ("JPEG (*.jpg)", ".jpg"),
            "png": ("PNG sin pérdida (*.png)", ".png"),
            "pdf": ("PDF (*.pdf)", ".pdf"),
        }
        filtro, ext = formatos[formato]
        nombre_def = (self._prefijo_limpio() or "documento") + ext
        carpeta_def = self.carpeta_salida or self._ruta_origen
        ruta, _ = QFileDialog.getSaveFileName(
            self, "Guardar como", os.path.join(carpeta_def, nombre_def), filtro
        )
        if not ruta:
            return
        if not ruta.lower().endswith(ext):
            ruta += ext

        try:
            if formato == "jpg":
                ok, buf = cv2.imencode(
                    ".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 95]
                )
                if not ok:
                    raise RuntimeError("Error codificando JPEG")
                buf.tofile(ruta)
            elif formato == "png":
                ok, buf = cv2.imencode(
                    ".png", img, [cv2.IMWRITE_PNG_COMPRESSION, 3]
                )
                if not ok:
                    raise RuntimeError("Error codificando PNG")
                buf.tofile(ruta)
            else:
                # cv_a_pil_pdf incrusta los B/N puros a 1 bit (CCITT G4):
                # el PDF de una factura pasa de ~1 MB a decenas de KB.
                cv_a_pil_pdf(img).save(ruta, "PDF", resolution=200.0)

            QMessageBox.information(
                self, "Guardado",
                f"Archivo guardado correctamente:\n{ruta}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo guardar:\n{e}")

    # ----------------------------------------------------------
    # PDF multipágina
    # ----------------------------------------------------------

    def anadir_pagina_pdf(self, img=None):
        if img is None:
            img = self.procesada_full()
        if img is None:
            QMessageBox.warning(self, "Atención", "Procesa una imagen primero.")
            return
        self._insertar_pagina(img)
        self._actualizar_barra_estado()
        self._guardar_sesion_actual()

    def _insertar_pagina(self, img, fila=None):
        """Crea el item de página: miniatura + imagen comprimida en memoria
        (no la imagen entera, que con fotos de móvil son ~35 MB por página)."""
        self._insertar_pagina_codificada(codificar_pagina(img), fila)

    def _insertar_pagina_codificada(self, datos, fila=None):
        """Restaura una página conservando exactamente sus bytes comprimidos."""
        img = decodificar_pagina(datos)
        if img is None:
            return
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        h, w = rgb.shape[:2]
        qimg = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888).copy()
        icono = QIcon(QPixmap.fromImage(qimg).scaled(
            80, 104, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation))
        item = QListWidgetItem(icono, "")
        item.setData(Qt.ItemDataRole.UserRole, bytes(datos))
        if fila is None:
            self.lista_pdf.addItem(item)
        else:
            self.lista_pdf.insertItem(fila, item)
        self.lista_pdf.setCurrentItem(item)

    def deshacer_ultima_pagina(self):
        if not self.lista_pdf.count():
            return
        self.lista_pdf.takeItem(self.lista_pdf.count() - 1)
        self._actualizar_barra_estado()
        self._guardar_sesion_actual()
        self.statusBar().showMessage("Última página retirada del lote", 3000)

    def quitar_pagina_pdf(self):
        filas = sorted((self.lista_pdf.row(it)
                        for it in self.lista_pdf.selectedItems()), reverse=True)
        if not filas and self.lista_pdf.currentRow() >= 0:
            filas = [self.lista_pdf.currentRow()]
        for fila in filas:
            self.lista_pdf.takeItem(fila)
        self._actualizar_barra_estado()
        self._guardar_sesion_actual()

    def combinar_dni(self):
        """Une dos páginas (las 2 seleccionadas, o las 2 últimas) en una sola
        hoja A4: cara delantera arriba y trasera abajo, como al fotocopiar
        un DNI."""
        n = self.lista_pdf.count()
        if n < 2:
            QMessageBox.warning(
                self, "Atención",
                "Añade primero las dos caras a la lista (botón «➕ Añadir»):\n"
                "procesa la cara delantera, añádela; luego la trasera, "
                "añádela, y pulsa este botón.")
            return
        filas = sorted(self.lista_pdf.row(it)
                       for it in self.lista_pdf.selectedItems())
        if len(filas) != 2:
            filas = [n - 2, n - 1]
        datos = [self.lista_pdf.item(f).data(Qt.ItemDataRole.UserRole)
                 for f in filas]
        hoja = componer_dni(decodificar_pagina(datos[0]),
                            decodificar_pagina(datos[1]))
        self.lista_pdf.takeItem(filas[1])
        self.lista_pdf.takeItem(filas[0])
        self._insertar_pagina(hoja, filas[0])
        self._actualizar_barra_estado()
        self.statusBar().showMessage(
            "🪪 Dos páginas unidas en una hoja A4", 5000)
        self._guardar_sesion_actual()

    def vaciar_paginas_pdf(self):
        self.lista_pdf.clear()
        self._actualizar_barra_estado()
        self._guardar_sesion_actual()

    def _elegir_ruta_pdf_lote(self):
        nombre_def = (self._prefijo_limpio() or "facturas") + ".pdf"
        carpeta_def = self.carpeta_salida or self._ruta_origen
        ruta, _ = QFileDialog.getSaveFileName(
            self, "Guardar lote de facturas",
            os.path.join(carpeta_def, nombre_def), "PDF (*.pdf)")
        if ruta and not ruta.lower().endswith(".pdf"):
            ruta += ".pdf"
        return ruta

    def _guardar_pdf_lote(self, ruta):
        paginas = [
            pagina_a_pil_pdf(
                self.lista_pdf.item(i).data(Qt.ItemDataRole.UserRole))
            for i in range(self.lista_pdf.count())
        ]
        paginas[0].save(ruta, "PDF", resolution=200.0,
                        save_all=True, append_images=paginas[1:])
        return len(paginas)

    def exportar_pdf_multipagina(self):
        if not self.lista_pdf.count():
            QMessageBox.warning(self, "Atención",
                "No hay páginas. Añade con «➕ Añadir».")
            return
        ruta = self._elegir_ruta_pdf_lote()
        if not ruta:
            return
        try:
            total = self._guardar_pdf_lote(ruta)
            QMessageBox.information(self, "Exportado",
                f"PDF de {total} páginas guardado en:\n{ruta}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo exportar el PDF:\n{e}")

    def _ejecutable_aplifisa(self):
        configurado = self.settings.value("ruta_aplifisa", "", str)
        ejecutable = localizar_aplifisa(configurado)
        if ejecutable:
            return ejecutable
        ruta, _ = QFileDialog.getOpenFileName(
            self, "Localiza FacturasAplifisa.exe", "",
            "Facturas a Aplifisa (FacturasAplifisa.exe);;Ejecutables (*.exe)")
        if ruta:
            self.settings.setValue("ruta_aplifisa", ruta)
            return ruta
        return None

    def enviar_a_aplifisa(self):
        """Guarda el lote y abre la app fiscal con --import <pdf>."""
        if not self.lista_pdf.count():
            if self.procesada_full() is None:
                QMessageBox.warning(
                    self, "Lote vacío",
                    "Abra una foto y añádala al lote antes de enviarlo.")
                return
            self.anadir_pagina_pdf()
        ruta = self._elegir_ruta_pdf_lote()
        if not ruta:
            return
        try:
            total = self._guardar_pdf_lote(ruta)
            ejecutable = self._ejecutable_aplifisa()
            if not ejecutable:
                self.statusBar().showMessage(
                    "PDF guardado; falta localizar FacturasAplifisa.exe", 7000)
                return
            lanzar_aplifisa(ejecutable, ruta)
            self.statusBar().showMessage(
                f"Lote de {total} páginas enviado a Facturas a Aplifisa", 7000)
            QMessageBox.information(
                self, "Lote enviado",
                "El PDF se ha guardado y Facturas a Aplifisa se está abriendo "
                "con el lote preparado para analizar.")
        except Exception as e:
            QMessageBox.critical(
                self, "No se pudo enviar",
                f"El PDF no se pudo enviar a Facturas a Aplifisa:\n{e}")

# =============================================================
# ==========================   MAIN   =========================
# =============================================================

def main():
    app = QApplication(sys.argv)
    estilo.aplicar_tema(app)
    app.setWindowIcon(QIcon(estilo.ruta_recurso("icono.ico")))

    # Instancia única: evita dos copias abiertas que bloqueen el .exe al actualizar.
    ruta_lock = os.path.join(
        QStandardPaths.writableLocation(QStandardPaths.StandardLocation.TempLocation),
        "EscanerFotos.lock",
    )
    lock = QLockFile(ruta_lock)
    lock.setStaleLockTime(0)
    if not lock.tryLock(100):
        QMessageBox.information(
            None, "Ya está abierto",
            "EscanerFotos ya se está ejecutando."
        )
        return

    ventana = VentanaPrincipal()
    ventana.show()

    # Comprobar actualizaciones poco después de abrir (no bloquea el arranque).
    QTimer.singleShot(1500, lambda: actualizador.conectar(ventana, __version__))

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
