"""Reglas fijas del procedimiento. Se pueden cambiar en config.json (junto a app.py)."""
from __future__ import annotations

import json
import os

DEFAULTS = {
    "well_type": "DEFINITIVO",
    "pdat": "Rotary Table (RT)",
    "null": -999.25,
    "service_company": "BOND ENERGY SOLUTIONS SAS",
    "log_type": "PROCESSED",
    "drill_size": 8.5,
    "casing_size": 7,
    "service_types": ["PRESION-TEMPERATURA", "ILT"],
    "default_service_type": "PRESION-TEMPERATURA",
    # Step supuesto cuando no hay .las del log (se avisa en el reporte)
    "step_time": 1.0,
    "step_md": 0.5,
    "step_md_up": -0.5,
    "default_run": 1,
}

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "config.json")


def load_config(path: str = CONFIG_PATH) -> dict:
    cfg = dict(DEFAULTS)
    try:
        with open(path, encoding="utf-8") as f:
            cfg.update(json.load(f))
    except FileNotFoundError:
        pass
    return cfg
