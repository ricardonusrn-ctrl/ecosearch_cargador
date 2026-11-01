"""Reglas fijas del procedimiento. Se pueden cambiar en config.json (junto a app.py, o junto al
.exe en el programa instalado)."""
from __future__ import annotations

import json
import os
import sys

DEFAULTS = {
    "well_type": "DEFINITIVO",
    "pdat": "Rotary Table (RT)",
    "null": -999.25,
    "service_company": "BOND ENERGY SOLUTIONS SAS",
    "log_type": "PROCESSED",
    "drill_size": 8.5,
    "casing_size": 7,
    "service_types": ["PRESION-TEMPERATURA", "ILT", "PRODUCCION-PLT", "PLT",
                      "REGISTRO CORRELACION", "REGISTRO MEMORIZADO"],
    "default_service_type": "PRESION-TEMPERATURA",
    # Escala (hoja RefScale) de las imágenes que vienen solo en tiempo
    "time_scale": "ESC-60/TIME",
    # Step supuesto cuando no hay .las del log (se avisa en el reporte)
    "step_time": 1.0,
    "step_md": 0.5,
    "step_md_up": -0.5,
    "default_run": 1,
}

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "config.json")
# En el .exe, ROOT es la carpeta temporal del empaquetado: el config.json editable es el que el
# instalador deja junto al .exe, y manda sobre el empaquetado.
EXE_CONFIG_PATH = (os.path.join(os.path.dirname(sys.executable), "config.json")
                   if getattr(sys, "frozen", False) else None)


def load_config(path: str | None = None) -> dict:
    cfg = dict(DEFAULTS)
    for p in [path] if path else [CONFIG_PATH, EXE_CONFIG_PATH]:
        if not p:
            continue
        try:
            with open(p, encoding="utf-8") as f:
                cfg.update(json.load(f))
        except FileNotFoundError:
            pass
    return cfg
