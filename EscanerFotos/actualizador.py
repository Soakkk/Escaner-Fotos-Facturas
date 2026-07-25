# EscanerFotos/actualizador.py
"""Capa Qt del actualizador: comprueba GitHub Releases en un hilo, avisa al
usuario y —si acepta— descarga el instalador con barra de progreso y lo ejecuta
en silencio. El instalador (Inno Setup) cierra la app, reemplaza y la reabre."""

import os
import sys
import json
import hashlib
import tempfile
import subprocess
from urllib.request import urlopen, Request

from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import QMessageBox, QProgressDialog

from actualizador_core import (
    es_mas_nueva, elegir_asset_exe, elegir_asset_sha256, parsear_sha256,
)

API_URL = "https://api.github.com/repos/Soakkk/Escaner-Fotos-Facturas/releases/latest"


def esta_empaquetada():
    """True solo cuando corre como .exe de PyInstaller (no en desarrollo)."""
    return getattr(sys, "frozen", False)


class HiloComprobar(QThread):
    """Comprueba si hay versión nueva (rápido). Emite (version, url, size, url_sha256)."""
    encontrada = Signal(str, str, int, str)

    def __init__(self, version_local, parent=None):
        super().__init__(parent)
        self.version_local = version_local

    def run(self):
        try:
            req = Request(API_URL, headers={"User-Agent": "EscanerFotos"})
            with urlopen(req, timeout=15) as r:
                release = json.loads(r.read().decode("utf-8"))

            tag = release.get("tag_name", "")
            if not es_mas_nueva(tag, self.version_local):
                return

            asset = elegir_asset_exe(release)
            if not asset:
                return

            asset_sha = elegir_asset_sha256(release)
            url_sha = asset_sha["browser_download_url"] if asset_sha else ""

            self.encontrada.emit(
                tag, asset["browser_download_url"],
                int(asset.get("size") or 0), url_sha
            )
        except Exception:
            pass  # sin internet / error -> silencio


class HiloDescarga(QThread):
    """Descarga el instalador y verifica su SHA-256 si la release publica el
    hash. Emite progreso (0-100) y terminado(ruta|"")."""
    progreso = Signal(int)
    terminado = Signal(str)

    def __init__(self, url, size, url_sha="", parent=None):
        super().__init__(parent)
        self.url = url
        self.size = size
        self.url_sha = url_sha

    def _hash_esperado(self):
        """Descarga y parsea el .sha256 de la release; None si no hay."""
        if not self.url_sha:
            return None
        try:
            req = Request(self.url_sha, headers={"User-Agent": "EscanerFotos"})
            with urlopen(req, timeout=15) as r:
                return parsear_sha256(r.read().decode("utf-8", "replace"))
        except Exception:
            return None

    def run(self):
        destino = os.path.join(tempfile.gettempdir(), "EscanerFotos-Setup.exe")
        try:
            esperado = self._hash_esperado()
            req = Request(self.url, headers={"User-Agent": "EscanerFotos"})
            bajado = 0
            digestor = hashlib.sha256()
            with urlopen(req, timeout=60) as r, open(destino, "wb") as f:
                while True:
                    trozo = r.read(1024 * 256)
                    if not trozo:
                        break
                    f.write(trozo)
                    digestor.update(trozo)
                    bajado += len(trozo)
                    if self.size:
                        self.progreso.emit(int(bajado * 100 / self.size))
            if self.size and os.path.getsize(destino) != self.size:
                os.remove(destino)
                self.terminado.emit("")
                return
            if esperado and digestor.hexdigest() != esperado:
                os.remove(destino)
                self.terminado.emit("")
                return
            self.terminado.emit(destino)
        except Exception:
            try:
                os.remove(destino)
            except Exception:
                pass
            self.terminado.emit("")


def _lanzar_instalador(ruta_setup):
    """Ejecuta el instalador en silencio. Inno cierra la app, reemplaza y la reabre."""
    subprocess.Popen(
        [ruta_setup, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"],
        close_fds=True,
    )


def conectar(ventana, version_local):
    """Punto de entrada: comprueba actualizaciones y cablea el flujo de aviso.
    Llamar una vez tras mostrar la ventana principal."""
    if not esta_empaquetada():
        return

    def al_encontrar(version, url, size, url_sha):
        # Aviso INMEDIATO (no se descarga nada hasta que el usuario acepta).
        resp = QMessageBox.question(
            ventana, "Actualización disponible",
            f"Hay una versión nueva de EscanerFotos ({version}).\n\n"
            "¿Descargar e instalar ahora?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if resp != QMessageBox.StandardButton.Yes:
            return  # "Más tarde": volverá a avisar la próxima vez que abra.

        # Descarga con barra de progreso (sin botón cancelar).
        dlg = QProgressDialog("Descargando actualización…", None, 0, 100, ventana)
        dlg.setWindowTitle("Actualizando")
        dlg.setWindowModality(Qt.WindowModality.WindowModal)
        dlg.setMinimumDuration(0)
        dlg.setAutoClose(False)
        dlg.setAutoReset(False)
        dlg.setValue(0)

        hilo_dl = HiloDescarga(url, size, url_sha, parent=ventana)

        def on_terminado(ruta):
            dlg.close()
            if not ruta:
                QMessageBox.warning(
                    ventana, "Actualización",
                    "No se pudo descargar la actualización.\n"
                    "Revisa tu conexión e inténtalo más tarde."
                )
                return
            _lanzar_instalador(ruta)
            ventana.close()

        hilo_dl.progreso.connect(dlg.setValue)
        hilo_dl.terminado.connect(on_terminado)
        ventana._hilo_descarga = hilo_dl  # evita que el GC lo recoja
        hilo_dl.start()
        dlg.show()

    hilo = HiloComprobar(version_local, parent=ventana)
    hilo.encontrada.connect(al_encontrar)
    hilo.start()
    ventana._hilo_comprobar = hilo  # evita que el GC lo recoja
