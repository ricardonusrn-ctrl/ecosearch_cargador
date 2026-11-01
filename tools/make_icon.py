"""Genera "CARGADOR ECOSEARCH.ico" (hoja de cálculo + flecha de carga, colores de Bond).

Uso:  py tools/make_icon.py

El .ico es "híbrido", como el de los demás programas de Bond: cuadros BMP/DIB de 16 a 128 px y
PNG solo en 256 px. Un Image.save(format="ICO") de Pillow no sirve: sin bitmap_format guarda
todo en PNG (algunos caminos de Windows/PyInstaller no lo muestran) y con bitmap_format="bmp"
también guarda el de 256 en BMP, que es inválido y rompe el archivo entero.
"""
from __future__ import annotations

import io
import os
import struct

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "CARGADOR ECOSEARCH.ico")
ACCENT, GREEN, WHITE = (13, 99, 114, 255), (30, 123, 52, 255), (255, 255, 255, 255)
SIZES = (16, 24, 32, 48, 64, 128, 256)


def draw(size: int = 1024) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = size / 1024
    d.rounded_rectangle((0, 0, size - 1, size - 1), radius=int(200 * s), fill=ACCENT)
    d.rounded_rectangle((210 * s, 170 * s, 700 * s, 800 * s), radius=int(40 * s), fill=WHITE)
    for y in (330, 450, 570, 690):                               # filas de la hoja
        d.line((250 * s, y * s, 660 * s, y * s), fill=ACCENT, width=max(1, int(22 * s)))
    d.line((390 * s, 250 * s, 390 * s, 760 * s), fill=ACCENT, width=max(1, int(22 * s)))
    cx, cy, r = 700 * s, 700 * s, 230 * s                         # flecha de carga
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=GREEN, outline=WHITE, width=max(1, int(28 * s)))
    d.polygon([(cx, cy - 150 * s), (cx - 120 * s, cy - 10 * s), (cx - 45 * s, cy - 10 * s),
               (cx - 45 * s, cy + 140 * s), (cx + 45 * s, cy + 140 * s), (cx + 45 * s, cy - 10 * s),
               (cx + 120 * s, cy - 10 * s)], fill=WHITE)
    return img


def dib_frame(img: Image.Image) -> bytes:
    """BITMAPINFOHEADER con la altura doblada (XOR + máscara AND), como exige Windows."""
    w, h = img.size
    bgra = img.convert("RGBA").tobytes("raw", "BGRA")
    rows = [bgra[y * w * 4:(y + 1) * w * 4] for y in range(h)]
    xor = b"".join(reversed(rows))                                 # de abajo hacia arriba
    and_row = ((w + 31) // 32) * 4
    mask = bytes(and_row * h)                                      # todo opaco: manda el alfa
    header = struct.pack("<IiiHHIIiiII", 40, w, h * 2, 1, 32, 0, len(xor) + len(mask), 0, 0, 0, 0)
    return header + xor + mask


def write_ico(src: Image.Image, path: str) -> None:
    frames = []
    for n in SIZES:
        im = src.resize((n, n), Image.LANCZOS)
        if n == 256:
            buf = io.BytesIO()
            im.save(buf, "PNG")
            frames.append((n, buf.getvalue()))
        else:
            frames.append((n, dib_frame(im)))
    offset = 6 + 16 * len(frames)
    head = struct.pack("<HHH", 0, 1, len(frames))
    entries, blobs = b"", b""
    for n, data in frames:
        entries += struct.pack("<BBBBHHII", n % 256, n % 256, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
        blobs += data
    with open(path, "wb") as f:
        f.write(head + entries + blobs)


if __name__ == "__main__":
    image = draw()
    write_ico(image, OUT)
    image.resize((256, 256), Image.LANCZOS).save(os.path.join(ROOT, "tools", "icono_256.png"))
    print(OUT)
