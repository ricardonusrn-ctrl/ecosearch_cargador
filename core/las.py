"""Lectura del ENCABEZADO de un .las (solo hasta ~A; no carga las curvas, aunque pese MB)."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime

_LINE = re.compile(r"^\s*([^.\s]+)\s*\.(\S*)\s+(.*?)\s*:\s*(.*?)\s*$")


@dataclass
class LasHeader:
    path: str
    filename: str
    well: str | None = None
    uwi: str | None = None
    ekb: float | None = None
    step: float | None = None
    strt: float | None = None
    stop: float | None = None
    unit: str | None = None
    fecha: datetime | None = None
    run: int | None = None
    pdat: str | None = None


def _f(v: str):
    m = re.match(r"\s*(-?\d+(?:\.\d+)?)", v)
    return float(m.group(1)) if m else None


def read_header(path: str) -> LasHeader:
    h = LasHeader(path=path, filename=os.path.basename(path))
    in_well = False
    with open(path, encoding="latin-1") as f:      # el .las puede traer "°F" en latin-1
        for line in f:
            s = line.lstrip()
            if s.upper().startswith("~A"):
                break
            if s.startswith("~"):
                in_well = s.upper().startswith("~W")
                continue
            if not in_well:
                continue
            m = _LINE.match(line)
            if not m:
                continue
            mnem, unit, val = m.group(1).upper(), m.group(2), m.group(3).strip()
            if mnem == "WELL":
                h.well = val
            elif mnem == "UWI":
                h.uwi = val
            elif mnem == "EKB":
                h.ekb = _f(val)
            elif mnem == "STEP":
                h.step = _f(val)
            elif mnem == "STRT":
                h.strt, h.unit = _f(val), unit.upper() or None
            elif mnem == "STOP":
                h.stop = _f(val)
            elif mnem == "DATE":
                for fmt in ("%d-%b-%Y", "%d/%m/%Y"):
                    try:
                        h.fecha = datetime.strptime(val.title(), fmt)
                        break
                    except ValueError:
                        pass
            elif re.fullmatch(r"RUN\d*", mnem) and h.run is None:
                try:
                    h.run = int(float(val))
                except ValueError:
                    pass
            elif mnem == "PDAT":
                h.pdat = val
    return h


def strip_upload_prefix(stem: str) -> str:
    """Quita el prefijo hexadecimal que añade la subida al chat (9ba108f2-NOMBRE...)."""
    return re.sub(r"^[0-9a-fA-F]{8}-(?=\S)", "", stem)


def match_key(name: str) -> str:
    """Clave para emparejar un log de la plantilla con su .las: sin extensión,
    P&T == P_T, espacio == guion bajo, sin distinguir mayúsculas."""
    stem = os.path.splitext(os.path.basename(name))[0]
    stem = strip_upload_prefix(stem)
    return re.sub(r"[\s&]", "_", stem).lower()
