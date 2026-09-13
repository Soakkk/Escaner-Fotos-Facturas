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

from PySide6.QtCore import QThread, Signal, QTimer

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
            size = int(asset.get("size") or 0)
            if size <= 0:
                return

            asset_sha = elegir_asset_sha256(release)
            url_sha = asset_sha["browser_download_url"] if asset_sha else ""

            self.encontrada.emit(
                tag, asset["browser_download_url"],
                size, url_sha
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
        req = Request(self.url_sha, headers={"User-Agent": "EscanerFotos"})
        with urlopen(req, timeout=15) as r:
            esperado = parsear_sha256(r.read().decode("utf-8", "replace"))
        if esperado is None:
            raise ValueError("El archivo SHA-256 no contiene un hash válido")
        return esperado

    def run(self):
        destino = os.path.join(tempfile.gettempdir(), "EscanerFotos-Setup.exe")
        temporal = destino + ".part"
        try:
            esperado = self._hash_esperado()
            req = Request(self.url, headers={"User-Agent": "EscanerFotos"})
            bajado = 0
            digestor = hashlib.sha256()
            with urlopen(req, timeout=60) as r, open(temporal, "wb") as f:
                while True:
                    trozo = r.read(1024 * 256)
                    if not trozo:
                        break
                    f.write(trozo)
                    digestor.update(trozo)
                    bajado += len(trozo)
                    if self.size:
                        self.progreso.emit(int(bajado * 100 / self.size))
                f.flush()
                os.fsync(f.fileno())
            if self.size and os.path.getsize(temporal) != self.size:
                os.remove(temporal)
                self.terminado.emit("")
                return
            if esperado and digestor.hexdigest() != esperado:
                os.remove(temporal)
                self.terminado.emit("")
                return
            os.replace(temporal, destino)
            self.terminado.emit(destino)
        except Exception:
            try:
                os.remove(temporal)
            except Exception:
                pass
            self.terminado.emit("")


def programar_instalacion(ruta_setup):
    """Ejecuta el instalador en silencio. Inno cierra la app, reemplaza y la reabre."""
    subprocess.Popen(
        [ruta_setup, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"],
        close_fds=True,
    )


def lanzar_instalador(ruta_setup):
    """Nombre público conservado para integraciones existentes."""
    programar_instalacion(ruta_setup)


def conectar(ventana, version_local, manual=False):
    """Comprueba y descarga en segundo plano; deja el Setup listo en la UI."""
    if not esta_empaquetada():
        return

    def al_encontrar(version, url, size, url_sha):
        ventana._estado_actualizacion = "downloading"
        ventana.statusBar().showMessage(f"Descargando actualización {version}…")
        hilo_dl = HiloDescarga(url, size, url_sha, parent=ventana)

        def on_terminado(ruta):
            if not ruta:
                ventana._estado_actualizacion = "error"
                if manual:
                    ventana.statusBar().showMessage(
                        "No se pudo descargar la actualización; comprueba la conexión",
                        7000,
                    )
                return
            ventana._estado_actualizacion = "ready"
            ventana._ruta_update_lista = ruta
            ventana._version_update_lista = version
            if hasattr(ventana, "_mostrar_actualizacion_lista"):
                ventana._mostrar_actualizacion_lista(version)

        hilo_dl.progreso.connect(
            lambda valor: ventana.statusBar().showMessage(
                f"Descargando actualización {version}: {valor}%"
            )
        )
        hilo_dl.terminado.connect(on_terminado)
        ventana._hilo_descarga = hilo_dl  # evita que el GC lo recoja
        hilo_dl.start()

    ventana._estado_actualizacion = "checking"
    hilo = HiloComprobar(version_local, parent=ventana)
    hilo.encontrada.connect(al_encontrar)
    hilo.start()
    ventana._hilo_comprobar = hilo  # evita que el GC lo recoja

    if not hasattr(ventana, "_timer_actualizaciones"):
        timer = QTimer(ventana)
        timer.setInterval(6 * 60 * 60 * 1000)
        timer.timeout.connect(lambda: conectar(ventana, version_local))
        timer.start()
        ventana._timer_actualizaciones = timer
