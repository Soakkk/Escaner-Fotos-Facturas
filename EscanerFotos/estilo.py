"""Sistema visual compartido por la suite de oficina Asesoría E. Marín."""

import os
import sys

from PySide6.QtGui import QPalette, QColor

# ---- Paleta -------------------------------------------------------------

PAGE = "#F5F8FC"
CARD = "#FFFFFF"
INK = "#24384D"
MUTED = "#5D7084"
BORDER = "#DCE5F0"
ACCENT = "#326FA6"
SUCCESS = "#19724E"
WARNING = "#86500A"
DANGER = "#B43737"

# Alias descriptivos conservados para los consumidores existentes.
FONDO = PAGE
PANEL = CARD
CONTROL = CARD
CONTROL_HOVER = "#EDF4FA"
CONTROL_PULSADO = "#E1ECF6"
BORDE = BORDER
LIENZO = "#EAF0F6"
TEXTO = INK
TEXTO_SUAVE = MUTED
TEXTO_DESACTIVADO = "#8797A8"

ACENTO = ACCENT
ACENTO_HOVER = "#285F91"
ACENTO_PULSADO = "#214F78"
EXITO = SUCCESS
EXITO_HOVER = "#145D40"
EXITO_PULSADO = "#104A34"

# Colores para texto enriquecido (setText con HTML) coherentes con el tema
HTML_SUAVE = TEXTO_SUAVE
HTML_OK = SUCCESS


def ruta_recurso(nombre):
    """Ruta a un archivo de `recursos/`: junto a este .py en desarrollo,
    dentro del paquete de PyInstaller (_MEIPASS) en el ejecutable."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "recursos", nombre)


def _url(nombre):
    """url() de QSS (siempre con barras /, también en Windows)."""
    return ruta_recurso(nombre).replace("\\", "/")


QSS = f"""
QWidget {{
    color: {TEXTO};
    font-family: "Segoe UI Variable", "Segoe UI", sans-serif;
    font-size: 13px;
}}
QMainWindow, QDialog, QMessageBox, QProgressDialog, QFileDialog {{
    background: {FONDO};
}}

/* ---- Grupos ---- */
QGroupBox {{
    background: {PANEL};
    border: 1px solid {BORDE};
    border-radius: 10px;
    margin-top: 12px;
    padding: 10px 10px 8px 10px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 4px;
    color: {TEXTO_SUAVE};
    background: {PANEL};
}}
/* Grupo plegable cerrado: solo el título, sin caja vacía debajo */
QGroupBox[plegado="true"] {{
    padding: 0px 10px;
    background: transparent;
    border-color: {PANEL};
}}

/* ---- Botones ---- */
QPushButton {{
    background: {CONTROL};
    border: 1px solid {BORDE};
    border-radius: 6px;
    padding: 7px 12px;
}}
QPushButton:hover {{ background: {CONTROL_HOVER}; border-color: {ACENTO}; }}
QPushButton:pressed {{ background: {CONTROL_PULSADO}; }}
QPushButton:focus {{ border: 2px solid {ACENTO}; padding: 6px 11px; }}
QPushButton:disabled {{ color: {TEXTO_DESACTIVADO}; background: #F1F3F5; }}

QPushButton#btnPrimario {{
    background: {ACENTO};
    border: none;
    color: white;
    font-size: 14px;
    font-weight: 600;
}}
QPushButton#btnPrimario:hover {{ background: {ACENTO_HOVER}; }}
QPushButton#btnPrimario:pressed {{ background: {ACENTO_PULSADO}; }}

QPushButton#btnExito {{
    background: {EXITO};
    border: none;
    color: white;
    font-size: 14px;
    font-weight: 600;
}}
QPushButton#btnExito:hover {{ background: {EXITO_HOVER}; }}
QPushButton#btnExito:pressed {{ background: {EXITO_PULSADO}; }}

/* ---- Entradas ---- */
QComboBox, QLineEdit {{
    background: {CONTROL};
    border: 1px solid {BORDE};
    border-radius: 6px;
    padding: 6px 8px;
    selection-background-color: {ACENTO};
}}
QComboBox:hover, QLineEdit:hover {{ border-color: #9DB3CF; }}
QComboBox:focus, QLineEdit:focus {{ border-color: {ACENTO}; }}
QComboBox QAbstractItemView {{
    background: {PANEL};
    border: 1px solid {BORDE};
    selection-background-color: {ACENTO};
    outline: none;
}}

/* ---- Casillas (también las de los grupos plegables) ---- */
QCheckBox {{ spacing: 7px; background: transparent; }}
QCheckBox::indicator, QGroupBox::indicator {{
    width: 15px;
    height: 15px;
    border-radius: 4px;
    border: 1px solid #AAB6C2;
    background: {CONTROL};
}}
QCheckBox::indicator:hover, QGroupBox::indicator:hover {{
    border-color: {ACENTO};
}}
QCheckBox::indicator:checked, QGroupBox::indicator:checked {{
    background: {ACENTO};
    border-color: {ACENTO};
    image: url("{_url('check.png')}");
}}

/* ---- Deslizadores ---- */
QSlider::groove:horizontal {{
    height: 4px;
    background: {BORDE};
    border-radius: 2px;
}}
QSlider::sub-page:horizontal {{ background: {ACENTO}; border-radius: 2px; }}
QSlider::handle:horizontal {{
    background: {ACENTO};
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}}
QSlider::handle:horizontal:hover {{ background: {ACENTO_HOVER}; }}

/* ---- Lista de páginas del PDF ---- */
QListWidget {{
    background: {LIENZO};
    border: 1px solid {BORDE};
    border-radius: 6px;
    padding: 4px;
}}
QListWidget::item {{ border-radius: 6px; }}
QListWidget::item:selected {{ background: {ACENTO}; }}

/* ---- Barras de scroll ---- */
QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{
    background: #B9C3CD;
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: #97A6B5; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{
    background: #B9C3CD;
    border-radius: 4px;
    min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{ background: #97A6B5; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* ---- Barra de progreso ---- */
QProgressBar {{
    background: {CONTROL};
    border: 1px solid {BORDE};
    border-radius: 6px;
    text-align: center;
    color: {TEXTO};
}}
QProgressBar::chunk {{ background: {ACENTO}; border-radius: 5px; }}

/* ---- Barra de estado y tooltips ---- */
QStatusBar {{ background: {PANEL}; color: {TEXTO_SUAVE}; border-top: 1px solid {BORDE}; }}
QStatusBar::item {{ border: none; }}
QToolTip {{
    background: {PANEL};
    color: {TEXTO};
    border: 1px solid {BORDE};
    padding: 4px 6px;
}}

/* ---- Elementos con nombre ---- */
QLabel {{ background: transparent; }}
QLabel#lienzo {{
    background: {LIENZO};
    border: 1px solid {BORDE};
    border-radius: 10px;
}}
QLabel#tituloLienzo {{
    color: {TEXTO_SUAVE};
    font-size: 14px;
    font-weight: 600;
    padding: 2px 0;
}}
QLabel#infoSuave {{ color: {TEXTO_SUAVE}; font-size: 11px; }}
QLabel#indicadorCola {{
    background: #EAF3EC;
    color: #23603B;
    padding: 6px 8px;
    border-radius: 6px;
    font-weight: 600;
}}
QFrame#cabecera {{
    background: {PANEL};
    border: none;
    border-bottom: 1px solid {BORDE};
}}
QLabel#marca {{ color: {TEXTO}; font-size: 20px; font-weight: 700; }}
QLabel#marcaSubtitulo {{ color: {TEXTO_SUAVE}; font-size: 11px; }}
QPushButton[role="cabeceraAccion"] {{
    background: {PANEL}; color: {ACENTO};
    border: 1px solid {BORDE};
    padding: 7px 12px; font-weight: 600;
}}
QPushButton[role="cabeceraAccion"]:hover {{
    background: {CONTROL_HOVER}; color: {ACENTO_HOVER};
    border-color: {ACENTO};
}}
QLabel#pasoActivo {{
    background: #E8F0F8; color: {ACENTO}; border: 1px solid #BFD0E2;
    border-radius: 14px; padding: 6px 10px; font-weight: 700;
}}
QLabel#pasoInactivo {{ color: #D9E3ED; padding: 6px 8px; }}
QLabel#tituloPanel {{ color: {ACENTO}; font-size: 17px; font-weight: 700; }}
QLabel#subtituloPanel {{ color: {TEXTO_SUAVE}; font-size: 11px; }}
QPushButton#btnEnviar {{
    background: {ACENTO}; color: white; border: none;
    font-size: 14px; font-weight: 700;
}}
QPushButton#btnEnviar:hover {{ background: {ACENTO_HOVER}; }}
QFrame#panelFinalizacion {{
    background: #EDF6F2;
    border: 1px solid #C9E1D6;
    border-radius: 8px;
}}
QPushButton#actualizacionLista {{
    background: #FFF7E8;
    color: {WARNING};
    border: 1px solid #E7CF9E;
    font-weight: 700;
}}
QPushButton#actualizacionLista:hover {{
    background: #FBECCE;
    border-color: {WARNING};
}}
"""


def aplicar_tema(app):
    """Aplica estilo Fusion, paleta oscura y la hoja de estilos a la app.
    La paleta cubre lo que el QSS no alcanza (menús nativos, diálogos)."""
    app.setStyle("Fusion")
    p = app.palette()
    rol = QPalette.ColorRole
    p.setColor(rol.Window, QColor(FONDO))
    p.setColor(rol.WindowText, QColor(TEXTO))
    p.setColor(rol.Base, QColor(CONTROL))
    p.setColor(rol.AlternateBase, QColor(PANEL))
    p.setColor(rol.Text, QColor(TEXTO))
    p.setColor(rol.Button, QColor(CONTROL))
    p.setColor(rol.ButtonText, QColor(TEXTO))
    p.setColor(rol.ToolTipBase, QColor(PANEL))
    p.setColor(rol.ToolTipText, QColor(TEXTO))
    p.setColor(rol.Highlight, QColor(ACENTO))
    p.setColor(rol.HighlightedText, QColor("#ffffff"))
    p.setColor(rol.PlaceholderText, QColor(TEXTO_SUAVE))
    p.setColor(rol.Link, QColor(ACENTO))
    grupo = QPalette.ColorGroup.Disabled
    p.setColor(grupo, rol.Text, QColor(TEXTO_DESACTIVADO))
    p.setColor(grupo, rol.ButtonText, QColor(TEXTO_DESACTIVADO))
    p.setColor(grupo, rol.WindowText, QColor(TEXTO_DESACTIVADO))
    app.setPalette(p)
    app.setStyleSheet(QSS)
