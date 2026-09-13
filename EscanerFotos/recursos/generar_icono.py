"""Genera el icono de Escáner de Fotos dentro de la familia de la suite."""

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


S = 1024
AZUL_SUPERIOR = np.array((9, 61, 119), dtype=np.float64)
AZUL_INFERIOR = np.array((4, 42, 88), dtype=np.float64)
BLANCO = (252, 253, 255, 255)
AZUL_TINTA = (12, 55, 108, 255)
DORADO = (242, 174, 24, 255)


def _mascara_de_la_referencia() -> Image.Image:
    """Reutiliza la silueta del icono de Facturas sin modificar la referencia."""
    referencia = (
        Path(__file__).resolve().parents[3]
        / "Facturas-a-Aplifisa"
        / "assets"
        / "app.png"
    )
    if referencia.is_file():
        return Image.open(referencia).convert("RGBA").resize(
            (S, S), Image.Resampling.LANCZOS
        ).getchannel("A")
    mascara = Image.new("L", (S, S), 0)
    rombo = Image.new("L", (760, 760), 0)
    ImageDraw.Draw(rombo).rounded_rectangle((0, 0, 759, 759), 110, fill=255)
    rombo = rombo.rotate(45, expand=True, resample=Image.Resampling.BICUBIC)
    mascara.paste(rombo, ((S - rombo.width) // 2, (S - rombo.height) // 2), rombo)
    return mascara


def _fondo() -> Image.Image:
    y = np.linspace(0.0, 1.0, S)[:, None, None]
    x = np.linspace(-1.0, 1.0, S)[None, :, None]
    gradiente = AZUL_SUPERIOR * (1 - y) + AZUL_INFERIOR * y
    brillo = np.clip(1.0 - np.abs(x) * 0.13, 0.82, 1.0)
    rgb = np.broadcast_to(gradiente, (S, S, 3)) * brillo
    imagen = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
    imagen.putalpha(_mascara_de_la_referencia())
    return imagen


def _pictograma(imagen: Image.Image) -> None:
    d = ImageDraw.Draw(imagen)
    d.rounded_rectangle((252, 170, 772, 625), radius=42, fill=BLANCO)
    d.rounded_rectangle((302, 226, 722, 510), radius=18, fill=AZUL_TINTA)
    d.ellipse((586, 270, 650, 334), fill=DORADO)
    d.polygon(
        [(322, 478), (430, 354), (518, 438), (578, 374), (704, 496)],
        fill=(245, 248, 252, 255),
    )
    d.rounded_rectangle((326, 548, 570, 574), radius=13, fill=AZUL_TINTA)
    d.rounded_rectangle((188, 588, 836, 762), radius=46, fill=BLANCO)
    d.rounded_rectangle((250, 634, 774, 674), radius=20, fill=AZUL_TINTA)
    d.rounded_rectangle((278, 708, 746, 742), radius=17, fill=(213, 226, 240, 255))
    d.rounded_rectangle((218, 590, 806, 620), radius=15, fill=DORADO)
    d.ellipse((754, 696, 786, 728), fill=DORADO)


def _marca_verificacion(destino: Path) -> None:
    imagen = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    ImageDraw.Draw(imagen).line(
        [(14, 34), (27, 47), (50, 18)],
        fill=(255, 255, 255, 255),
        width=9,
        joint="curve",
    )
    imagen.resize((16, 16), Image.Resampling.LANCZOS).save(destino / "check.png")


def generar() -> None:
    destino = Path(__file__).resolve().parent
    icono = _fondo()
    _pictograma(icono)
    icono.resize((512, 512), Image.Resampling.LANCZOS).save(destino / "icono.png")
    icono.save(
        destino / "icono.ico",
        sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (24, 24), (16, 16)],
    )
    _marca_verificacion(destino)


if __name__ == "__main__":
    generar()
