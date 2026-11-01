"""Interpretación del nombre de archivo de un log (.las / .dlis) y de una imagen."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import date

MESES = {
    "JAN": 1, "ENE": 1, "FEB": 2, "MAR": 3, "APR": 4, "ABR": 4, "MAY": 5,
    "JUN": 6, "JUL": 7, "AUG": 8, "AGO": 8, "SEP": 9, "OCT": 10, "NOV": 11,
    "DEC": 12, "DIC": 12,
}
NUM = r"\d+(?:\.\d+)?"


@dataclass
class LogName:
    filename: str          # nombre tal cual (con extensión y mayúsculas originales)
    stem: str
    ext: str
    fecha: date
    unit: str              # FT o S
    mdtime: str            # MD o TIME
    top: float
    bottom: float
    run: int | None        # RUN que trae el nombre (None si no trae)
    kind: str              # TIME, UP, DW, RIH, OFF, POOH, OTRO
    notes: list[str] = field(default_factory=list)


def basename(path: str) -> str:
    """Nombre de archivo de una ruta de la plataforma (/data/...) o de Windows."""
    return re.split(r"[\\/]", path.strip())[-1]


def num(x: float):
    """Entero si es entero (7400), si no float (0.5): así se escribe en la celda."""
    return int(x) if float(x).is_integer() else float(x)


def excel_serial(d: date) -> int:
    return (d - date(1899, 12, 30)).days


def parse_log_name(path_or_name: str) -> LogName:
    filename = basename(path_or_name)
    stem, ext = os.path.splitext(filename)
    notes: list[str] = []

    m = re.search(r"(\d{1,2})-([A-Za-z]{3,4})-(\d{4})", stem)
    if not m or m.group(2).upper()[:3] not in MESES:
        raise ValueError(f"No encuentro la fecha (dd-MMM-aaaa) en: {filename}")
    fecha = date(int(m.group(3)), MESES[m.group(2).upper()[:3]], int(m.group(1)))

    r = re.search(r"RUN[_ ]?(\d+)", stem, re.I)
    run = int(r.group(1)) if r else None

    t = re.search(rf"({NUM})-({NUM})[_ ]S[_ ]TIME", stem, re.I)
    if t:
        unit, mdtime, kind = "S", "TIME", "TIME"
        top, bottom = float(t.group(1)), float(t.group(2))
        if re.search(rf"{NUM}-{NUM}[_ ]FT[_ ]MD", stem, re.I):
            notes.append("mezcla rango de profundidad y de tiempo: se trató como TIME "
                         f"{num(top)}-{num(bottom)} S")
    else:
        d = re.search(rf"({NUM})-({NUM})[_ ]FT[_ ]MD", stem, re.I)
        if not d:
            raise ValueError(f"No encuentro el rango de profundidad (tope-base FT MD) en: {filename}")
        a, b = float(d.group(1)), float(d.group(2))
        top, bottom = min(a, b), max(a, b)
        unit, mdtime = "FT", "MD"
        if a > b:
            notes.append("nombre descendente: Top = menor, Bottom = mayor")
        if re.search(r"(^|[_\-])POOH(?![A-Za-z])", stem, re.I):
            kind = "POOH"
        elif re.search(r"(^|[_\-])UP[-_]?\d", stem, re.I):
            kind = "UP"
        elif re.search(r"(^|[_\-])DW[-_]?\d", stem, re.I):
            kind = "DW"
        elif re.search(r"(^|[_\-])RIH", stem, re.I):
            kind = "RIH"
        elif re.search(r"(^|[_\-])OFF", stem, re.I):
            kind = "OFF"
        else:
            kind = "OTRO"
    return LogName(filename, stem, ext, fecha, unit, mdtime, top, bottom, run, kind, notes)


TIME_SCALE = "ESC-60/TIME"


def is_time_image(path_or_name: str) -> bool:
    """¿Imagen solo en tiempo? (estaciones: ..._0-300_S_TIME.pdf, o TIME suelto en el nombre)."""
    stem = os.path.splitext(basename(path_or_name))[0]
    return bool(re.search(r"(^|[_\-. ])TIME([_\-. ]|$)", stem, re.I))


def scale_from_image(path_or_name: str, time_scale: str = TIME_SCALE) -> str | None:
    """ESC200 -> 'ESC-200' (debe existir igual en la hoja RefScale). Las imágenes solo en
    tiempo (y ESC60, que solo existe como escala de tiempo) van en `time_scale`."""
    if is_time_image(path_or_name):
        return time_scale
    m = re.search(r"ESC[-_ ]?(\d+)", basename(path_or_name), re.I)
    if not m:
        return None
    return time_scale if m.group(1) == "60" else f"ESC-{m.group(1)}"


def norm_alnum(s: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", s.upper())


def path_matches_well(path: str, well: str) -> bool:
    """¿La ruta pertenece a este pozo? (LIBERTAD-NORTE-11 vs LIBERTAD NORTE-11; sufijo H opcional)."""
    p, w = norm_alnum(path), norm_alnum(well)
    return w in p or (w.endswith("H") and w[:-1] in p)
