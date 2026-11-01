"""Reglas de negocio: arma las filas de Well Log y Well Log Image y escribe las plantillas.

Flujo: make_plan(Params) valida y calcula todo SIN escribir; write_outputs(plan, Params) escribe.
"""
from __future__ import annotations

import os
import re
import warnings
from dataclasses import dataclass, field

import openpyxl

from . import las as lasmod
from .config import load_config
from .names import (LogName, basename, excel_serial, num, parse_log_name, path_matches_well,
                    scale_from_image)
from .xlsx_xml import write_template

WL_PREFIX = "WL-template-external_delivery_WellLog_"
IMG_PREFIX = "WL-template-external_delivery_WellLogImage_"


@dataclass
class Params:
    wl_template: str
    img_template: str
    las_files: list[str] = field(default_factory=list)
    transmittal: str = ""
    service_type: str | None = None      # None -> el de config
    run: int | None = None               # None -> plantilla / nombre / config
    well: str | None = None              # None -> encabezado del .las
    uwi: str | None = None
    datum: float | None = None
    out_dir: str = ""
    cfg: dict = field(default_factory=load_config)


@dataclass
class LogRow:
    path: str
    name: LogName
    run: int
    step: float
    step_src: str
    image_path: str = ""
    scale: str = ""


@dataclass
class Plan:
    well: str = ""
    uwi: str = ""
    datum: float | None = None
    transmittal: str = ""
    service_type: str = ""
    rows: list[LogRow] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    infos: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors and bool(self.rows)


# ---------------------------------------------------------------- lectura de plantillas
def _clean(v):
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v


def read_template(path: str):
    """(rutas col A, Run de col I por fila, hojas Ref -> valores) de una plantilla de la plataforma."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb.worksheets[0]
    paths, runs = [], []
    for row in ws.iter_rows(min_row=3, values_only=True):
        a = row[0] if row else None
        if a is None or not str(a).strip():
            continue
        paths.append(str(a).strip())
        r = row[8] if len(row) > 8 else None
        runs.append(int(r) if isinstance(_clean(r), int) else None)
    refs = {}
    for w in wb.worksheets[1:]:
        refs[w.title] = {str(_clean(r[0])) for r in w.iter_rows(values_only=True)
                         if r and r[0] is not None}
    return paths, runs, refs


def norm_transmittal(t: str) -> str:
    t = (t or "").strip().upper()
    if re.fullmatch(r"\d{1,10}", t):
        return f"ECP_TRANSMITTAL_{int(t):010d}"
    if re.fullmatch(r"ECP_TRANSMITTAL_\d{10}", t):
        return t
    raise ValueError(f"ECP Transmittal no válido: '{t}' (use el número, ej. 1348, "
                     "o ECP_TRANSMITTAL_0000001348)")


def latest_transmittal(refs: dict[str, set]) -> str | None:
    vals = [v for v in refs.get("RefECP_Transmittal", ()) if re.fullmatch(r"ECP_TRANSMITTAL_\d{10}", v)]
    return max(vals, key=lambda v: int(v[-10:])) if vals else None


# ---------------------------------------------------------------- plan
def make_plan(p: Params) -> Plan:
    cfg, plan = p.cfg, Plan()
    err, warn, info = plan.errors.append, plan.warnings.append, plan.infos.append

    for label, f in (("Well Log", p.wl_template), ("Well Log Image", p.img_template)):
        if not f or not os.path.isfile(f):
            err(f"Falta la plantilla {label} (.xlsx).")
    if plan.errors:
        return plan
    log_paths, tmpl_runs, wl_refs = read_template(p.wl_template)
    img_paths, _, img_refs = read_template(p.img_template)
    if not log_paths:
        err("La plantilla Well Log no trae Resource Path (columna A, desde la fila 3).")
    if not img_paths:
        err("La plantilla Well Log Image no trae Resource Path de imágenes.")

    # --- Transmittal
    try:
        plan.transmittal = norm_transmittal(p.transmittal)
    except ValueError as e:
        err(str(e))
    plan.service_type = p.service_type or cfg["default_service_type"]

    # --- encabezados .las
    headers = []
    for f in p.las_files:
        try:
            headers.append(lasmod.read_header(f))
        except OSError as e:
            err(f"No pude leer {os.path.basename(f)}: {e}")
    wells = {h.well for h in headers if h.well}
    if len(wells) > 1:
        err("Los .las son de pozos distintos: " + ", ".join(sorted(wells)))
    plan.well = p.well or next(iter(wells), "")
    plan.uwi = p.uwi or next((h.uwi for h in headers if h.uwi), "")
    ekbs = [h.ekb for h in headers if h.ekb is not None]
    plan.datum = p.datum if p.datum is not None else (ekbs[0] if ekbs else None)
    if len(set(ekbs)) > 1:
        warn(f"Los .las traen distinto EKB {sorted(set(ekbs))}; se usó {plan.datum}.")
    for what, val in (("Well Name", plan.well), ("UWI", plan.uwi), ("Datum Elevation", plan.datum)):
        if val in ("", None):
            err(f"Falta {what}: adjunte los .las del pozo o escríbalo a mano.")
    if plan.errors:
        return plan

    # --- ¿las rutas son de este pozo?
    for label, paths in (("Well Log", log_paths), ("Well Log Image", img_paths)):
        bad = [basename(x) for x in paths if not path_matches_well(x, plan.well)]
        if bad:
            err(f"La plantilla {label} parece ser de OTRO pozo (no aparece '{plan.well}' en "
                f"{len(bad)} ruta(s), ej. {bad[0]}). Pida la plantilla correcta.")

    # --- filas de log
    by_key = {lasmod.match_key(h.filename): h for h in headers}
    time_steps = [h.step for h in headers if h.unit == "S" and h.step is not None]
    run_notes = set()
    for i, path in enumerate(log_paths):
        try:
            ln = parse_log_name(path)
        except ValueError as e:
            err(str(e))
            continue
        for n in ln.notes:
            info(f"{ln.filename}: {n}")
        h = by_key.get(lasmod.match_key(ln.filename))
        if h and h.step is not None:
            step, src = h.step, "del .las"
            if h.strt is not None and h.stop is not None and (
                    abs(min(h.strt, h.stop) - ln.top) > 1e-6 or abs(max(h.strt, h.stop) - ln.bottom) > 1e-6):
                warn(f"{ln.filename}: el .las trae {num(min(h.strt, h.stop))}-{num(max(h.strt, h.stop))} "
                     f"y el nombre {num(ln.top)}-{num(ln.bottom)}; se usó el nombre.")
            if h.fecha and h.fecha.date() != ln.fecha:
                warn(f"{ln.filename}: la fecha del .las ({h.fecha:%d-%b-%Y}) difiere del nombre.")
        elif ln.kind == "TIME":
            step, src = (time_steps[0], "asumido (de un .las de tiempo)") if time_steps \
                else (cfg["step_time"], "asumido")
        else:
            step, src = (cfg["step_md_up"] if ln.kind == "UP" else cfg["step_md"]), "asumido"

        if p.run is not None:
            run = p.run
        elif tmpl_runs[i] is not None:
            run = tmpl_runs[i]
        elif ln.run is not None:
            run = ln.run
        else:
            run = int(cfg["default_run"])
        if h and h.run is not None and h.run != run:
            run_notes.add(h.run)
        plan.rows.append(LogRow(path, ln, run, float(step), src))
    if run_notes:
        warn("El encabezado de los .las dice RUN " + "/".join(map(str, sorted(run_notes))) +
             f"; se usó Run {sorted({r.run for r in plan.rows})}. Si debe ser otro, escríbalo en el campo Run.")
    assumed = [r for r in plan.rows if r.step_src != "del .las"]
    if assumed:
        warn(f"Step asumido por tipo en {len(assumed)} de {len(plan.rows)} logs (no hay .las adjunto): "
             "revise la hoja de vista previa.")
    if plan.errors:
        return plan

    # --- imágenes: una fila por log, ciclo sobre las imágenes de la plantilla
    if len(plan.rows) < len(img_paths):
        warn(f"Hay {len(img_paths)} imágenes y solo {len(plan.rows)} logs: quedarán imágenes sin usar.")
    scales = img_refs.get("RefScale")
    for i, row in enumerate(plan.rows):
        row.image_path = img_paths[i % len(img_paths)]
        sc = scale_from_image(row.image_path)
        if not sc:
            err(f"No encuentro la escala (ESC###) en la imagen {basename(row.image_path)}")
            continue
        if scales is not None and sc not in scales:
            err(f"Scale '{sc}' no existe en la hoja RefScale ({basename(row.image_path)}).")
        row.scale = sc

    # --- cruce informativo con las hojas Ref (el rojo en la plataforma no implica error)
    for label, val, sheet in (("ECP Transmittal", plan.transmittal, "RefECP_Transmittal"),
                              ("Well Name", plan.well, "RefWellName"), ("UWI", plan.uwi, "RefUwi")):
        if sheet in wl_refs and val not in wl_refs[sheet]:
            info(f"{label} '{val}' no está en la hoja {sheet} de la plantilla (saldrá resaltado en rojo; "
                 "la plataforma valida al cargar).")
    if "RefServiceType" in wl_refs and plan.service_type not in wl_refs["RefServiceType"]:
        warn(f"Service Type '{plan.service_type}' no existe en RefServiceType.")
    last = latest_transmittal(wl_refs)
    if last and last != plan.transmittal:
        info(f"El transmittal más nuevo de la hoja Ref es {last}.")
    return plan


# ---------------------------------------------------------------- escritura
def _log_cells(plan: Plan, r: LogRow, cfg: dict):
    n = r.name
    return [("s", r.path), ("s", plan.transmittal), ("s", plan.well), ("s", plan.uwi),
            ("s", cfg["well_type"]), ("s", cfg["service_company"]), ("s", plan.service_type),
            ("d", excel_serial(n.fecha)), ("n", r.run), ("s", n.unit), ("s", n.mdtime),
            ("n", num(n.top)), ("n", num(n.bottom)), ("n", r.step), ("n", cfg["null"]),
            ("s", cfg["pdat"]), ("s", cfg["log_type"])]


def _img_cells(plan: Plan, r: LogRow, cfg: dict):
    n = r.name
    return [("s", r.image_path), ("s", plan.transmittal), ("s", plan.well), ("s", plan.uwi),
            ("s", n.filename), ("s", cfg["service_company"]), ("s", plan.service_type),
            ("d", excel_serial(n.fecha)), ("n", r.run), ("s", n.unit), ("s", n.mdtime),
            ("n", num(n.top)), ("n", num(n.bottom)), ("s", r.scale), ("s", cfg["log_type"]),
            ("n", float(plan.datum)), ("n", cfg["drill_size"]), ("n", cfg["casing_size"])]


def report_text(plan: Plan, usos: dict[str, int] | None = None) -> str:
    L = [f"POZO: {plan.well}   UWI: {plan.uwi}   Datum: {plan.datum}",
         f"Transmittal: {plan.transmittal}   Service Type: {plan.service_type}",
         f"Logs: {len(plan.rows)}", ""]
    if usos:
        L.append("Usos de cada imagen: " + "; ".join(f"{basename(k)}={v}" for k, v in usos.items()))
        L.append("")
    for title, items in (("ERRORES", plan.errors), ("AVISOS", plan.warnings), ("NOTAS", plan.infos)):
        if items:
            L.append(title)
            L += [f"  - {x}" for x in items]
            L.append("")
    L.append("DETALLE (log | run | unidad | tope-base | step [origen])")
    for r in plan.rows:
        n = r.name
        L.append(f"  {n.filename} | {r.run} | {n.unit} {n.mdtime} | {num(n.top)}-{num(n.bottom)} | "
                 f"{r.step} [{r.step_src}] | {r.scale}")
    return "\n".join(L) + "\n"


def write_outputs(plan: Plan, p: Params) -> dict[str, str]:
    if not plan.ok:
        raise ValueError("El plan tiene errores; no se escribe nada.")
    out_dir = p.out_dir or os.path.dirname(os.path.abspath(p.wl_template))
    os.makedirs(out_dir, exist_ok=True)
    slug = re.sub(r"\s+", "_", plan.well.strip())
    srcs = {os.path.abspath(p.wl_template), os.path.abspath(p.img_template)}

    def dest(prefix):
        d = os.path.join(out_dir, f"{prefix}{slug}.xlsx")
        return d if os.path.abspath(d) not in srcs else d[:-5] + "_completo.xlsx"

    wl_out, img_out = dest(WL_PREFIX), dest(IMG_PREFIX)
    write_template(p.wl_template, wl_out, [_log_cells(plan, r, p.cfg) for r in plan.rows], "Q")
    write_template(p.img_template, img_out, [_img_cells(plan, r, p.cfg) for r in plan.rows], "R")

    usos: dict[str, int] = {}
    for r in plan.rows:
        usos[r.image_path] = usos.get(r.image_path, 0) + 1
    rep = os.path.join(out_dir, f"REPORTE_{slug}.txt")
    with open(rep, "w", encoding="utf-8") as f:
        f.write(report_text(plan, usos))
    return {"well_log": wl_out, "well_log_image": img_out, "reporte": rep}
