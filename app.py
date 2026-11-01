"""Cargador de plantillas Ecosearch (Well Log + Well Log Image) — interfaz CustomTkinter.

Uso:  python app.py
"""
from __future__ import annotations

import os
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

from core import las as lasmod
from core.builder import Params, latest_transmittal, make_plan, read_template, write_outputs
from core.config import load_config
from core.names import basename, num

ctk.set_appearance_mode("system")
ctk.set_default_color_theme("blue")

MONO = ("Consolas" if sys.platform.startswith("win") else "Menlo" if sys.platform == "darwin"
        else "DejaVu Sans Mono", 12)


def open_folder(path: str) -> None:
    if sys.platform.startswith("win"):
        os.startfile(path)                       # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.cfg = load_config()
        self.title("Cargador Ecosearch — Well Log / Well Log Image")
        self.geometry("1180x780")
        self.minsize(1000, 680)
        self.las_files: list[str] = []
        self.plan = None
        self.last_out: dict | None = None
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build_left()
        self._build_right()

    # ------------------------------------------------------------------ panel izquierdo
    def _build_left(self):
        left = ctk.CTkScrollableFrame(self, width=430, label_text="1 · Datos de entrada")
        left.grid(row=0, column=0, sticky="nsew", padx=(12, 6), pady=12)
        left.grid_columnconfigure(0, weight=1)

        self.v_wl, self.v_img, self.v_out = ctk.StringVar(), ctk.StringVar(), ctk.StringVar()
        self._file_row(left, "Plantilla Well Log (.xlsx)", self.v_wl, self._pick_wl)
        self._file_row(left, "Plantilla Well Log Image (.xlsx)", self.v_img, self._pick_img)

        ctk.CTkLabel(left, text="Archivos .las del pozo", anchor="w").pack(fill="x", pady=(10, 0))
        bar = ctk.CTkFrame(left, fg_color="transparent")
        bar.pack(fill="x")
        ctk.CTkButton(bar, text="Agregar .las…", width=110, command=self._add_las).pack(side="left", padx=(0, 6))
        ctk.CTkButton(bar, text="Agregar carpeta…", width=120, command=self._add_las_dir).pack(side="left", padx=(0, 6))
        ctk.CTkButton(bar, text="Limpiar", width=70, fg_color="gray40", hover_color="gray30",
                      command=self._clear_las).pack(side="left")
        self.lbl_las = ctk.CTkLabel(left, text="Ningún .las cargado", anchor="w", justify="left",
                                    text_color=("gray30", "gray70"), wraplength=400)
        self.lbl_las.pack(fill="x", pady=(4, 0))

        self._file_row(left, "Carpeta de salida (vacío = junto a la plantilla)", self.v_out, self._pick_out,
                       folder=True)

        ctk.CTkLabel(left, text="2 · Datos del pozo", font=ctk.CTkFont(weight="bold"), anchor="w"
                     ).pack(fill="x", pady=(16, 2))
        self.v_trans, self.v_well, self.v_uwi, self.v_datum = (ctk.StringVar() for _ in range(4))
        self.v_run = ctk.StringVar(value="auto")
        self.v_service = ctk.StringVar(value=self.cfg["default_service_type"])

        row = ctk.CTkFrame(left, fg_color="transparent")
        row.pack(fill="x", pady=(4, 0))
        ctk.CTkLabel(row, text="ECP Transmittal (ej. 1348)", anchor="w").pack(fill="x")
        r2 = ctk.CTkFrame(row, fg_color="transparent")
        r2.pack(fill="x")
        ctk.CTkEntry(r2, textvariable=self.v_trans).pack(side="left", fill="x", expand=True)
        self.btn_last = ctk.CTkButton(r2, text="Último de la hoja Ref", width=140, state="disabled",
                                      command=self._fill_transmittal)
        self.btn_last.pack(side="left", padx=(6, 0))
        self._last_transmittal = None

        self._entry(left, "Well Name (del encabezado .las)", self.v_well)
        self._entry(left, "UWI (del encabezado .las)", self.v_uwi)
        self._entry(left, "Datum Elevation (EKB del .las)", self.v_datum)
        self._entry(left, "Run (auto = plantilla / nombre / 1)", self.v_run)

        ctk.CTkLabel(left, text="Service Type", anchor="w").pack(fill="x", pady=(6, 0))
        ctk.CTkOptionMenu(left, variable=self.v_service, values=self.cfg["service_types"]).pack(fill="x")

        fixed = (f"Fijos: Well Type {self.cfg['well_type']} · PDAT {self.cfg['pdat']} · "
                 f"Null {self.cfg['null']} · Drill {self.cfg['drill_size']} · Casing {self.cfg['casing_size']} "
                 "(se cambian en config.json)")
        ctk.CTkLabel(left, text=fixed, anchor="w", justify="left", wraplength=400,
                     text_color=("gray30", "gray70")).pack(fill="x", pady=(10, 0))

        btns = ctk.CTkFrame(left, fg_color="transparent")
        btns.pack(fill="x", pady=(16, 4))
        ctk.CTkButton(btns, text="Validar / Vista previa", command=self.on_preview).pack(
            side="left", expand=True, fill="x", padx=(0, 6))
        self.btn_gen = ctk.CTkButton(btns, text="Generar plantillas", fg_color="#1a7f37",
                                     hover_color="#136329", command=self.on_generate)
        self.btn_gen.pack(side="left", expand=True, fill="x")
        self.btn_open = ctk.CTkButton(left, text="Abrir carpeta de salida", fg_color="gray40",
                                      hover_color="gray30", state="disabled", command=self._open_out)
        self.btn_open.pack(fill="x", pady=(4, 0))

    def _file_row(self, parent, label, var, cmd, folder=False):
        ctk.CTkLabel(parent, text=label, anchor="w").pack(fill="x", pady=(10, 0))
        r = ctk.CTkFrame(parent, fg_color="transparent")
        r.pack(fill="x")
        ctk.CTkEntry(r, textvariable=var).pack(side="left", fill="x", expand=True)
        ctk.CTkButton(r, text="Examinar…", width=90, command=cmd).pack(side="left", padx=(6, 0))

    def _entry(self, parent, label, var):
        ctk.CTkLabel(parent, text=label, anchor="w").pack(fill="x", pady=(6, 0))
        ctk.CTkEntry(parent, textvariable=var).pack(fill="x")

    # ------------------------------------------------------------------ panel derecho
    def _build_right(self):
        right = ctk.CTkFrame(self)
        right.grid(row=0, column=1, sticky="nsew", padx=(6, 12), pady=12)
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)
        self.lbl_status = ctk.CTkLabel(right, text="Cargue las plantillas y los .las, luego pulse "
                                       "«Validar / Vista previa».", anchor="w", justify="left",
                                       wraplength=640, font=ctk.CTkFont(size=13))
        self.lbl_status.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 4))
        self.tabs = ctk.CTkTabview(right)
        self.tabs.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self.txt = {}
        for name in ("Avisos", "Well Log", "Well Log Image"):
            tab = self.tabs.add(name)
            tab.grid_columnconfigure(0, weight=1)
            tab.grid_rowconfigure(0, weight=1)
            t = ctk.CTkTextbox(tab, font=MONO, wrap="none")
            t.grid(row=0, column=0, sticky="nsew")
            t.configure(state="disabled")
            self.txt[name] = t
        self.tabs.set("Avisos")

    def _set_text(self, name: str, text: str):
        t = self.txt[name]
        t.configure(state="normal")
        t.delete("1.0", "end")
        t.insert("1.0", text)
        t.configure(state="disabled")

    # ------------------------------------------------------------------ selección de archivos
    def _pick_wl(self):
        f = filedialog.askopenfilename(title="Plantilla Well Log", filetypes=[("Excel", "*.xlsx")])
        if f:
            self.v_wl.set(f)
            self._load_refs(f)

    def _pick_img(self):
        f = filedialog.askopenfilename(title="Plantilla Well Log Image", filetypes=[("Excel", "*.xlsx")])
        if f:
            self.v_img.set(f)

    def _pick_out(self):
        d = filedialog.askdirectory(title="Carpeta de salida")
        if d:
            self.v_out.set(d)

    def _load_refs(self, path: str):
        try:
            _, _, refs = read_template(path)
        except Exception as e:                       # noqa: BLE001
            messagebox.showerror("Plantilla", f"No pude leer la plantilla:\n{e}")
            return
        self._last_transmittal = latest_transmittal(refs)
        if self._last_transmittal:
            self.btn_last.configure(state="normal")

    def _fill_transmittal(self):
        if self._last_transmittal:
            self.v_trans.set(self._last_transmittal)

    def _add_las(self):
        fs = filedialog.askopenfilenames(title="Archivos .las", filetypes=[("LAS", "*.las *.LAS")])
        self._register_las(list(fs))

    def _add_las_dir(self):
        d = filedialog.askdirectory(title="Carpeta con los .las")
        if d:
            self._register_las([os.path.join(d, n) for n in sorted(os.listdir(d))
                                if n.lower().endswith(".las")])

    def _clear_las(self):
        self.las_files = []
        self.lbl_las.configure(text="Ningún .las cargado")

    def _register_las(self, files: list[str]):
        for f in files:
            if f not in self.las_files:
                self.las_files.append(f)
        heads = []
        for f in self.las_files:
            try:
                heads.append(lasmod.read_header(f))
            except OSError:
                pass
        if heads:
            h = heads[0]
            if h.well and not self.v_well.get():
                self.v_well.set(h.well)
            if h.uwi and not self.v_uwi.get():
                self.v_uwi.set(h.uwi)
            if h.ekb is not None and not self.v_datum.get():
                self.v_datum.set(str(h.ekb))
        wells = sorted({h.well for h in heads if h.well})
        self.lbl_las.configure(text=f"{len(self.las_files)} .las · pozo(s): {', '.join(wells) or '—'}")

    # ------------------------------------------------------------------ acciones
    def _params(self) -> Params | None:
        try:
            run = None if self.v_run.get().strip().lower() in ("", "auto") else int(self.v_run.get())
            datum = float(self.v_datum.get().replace(",", ".")) if self.v_datum.get().strip() else None
        except ValueError:
            messagebox.showerror("Datos", "Run debe ser un entero (o «auto») y Datum un número.")
            return None
        return Params(
            wl_template=self.v_wl.get().strip(), img_template=self.v_img.get().strip(),
            las_files=list(self.las_files), transmittal=self.v_trans.get(),
            service_type=self.v_service.get(), run=run,
            well=self.v_well.get().strip() or None, uwi=self.v_uwi.get().strip() or None,
            datum=datum, out_dir=self.v_out.get().strip(), cfg=self.cfg)

    def _show_plan(self, plan):
        self.plan = plan
        lines = []
        for title, items in (("ERRORES (impiden generar)", plan.errors),
                             ("AVISOS (revisar)", plan.warnings), ("NOTAS", plan.infos)):
            if items:
                lines.append(title)
                lines += [f"  • {x}" for x in items]
                lines.append("")
        self._set_text("Avisos", "\n".join(lines) or "Sin avisos.")
        if plan.rows:
            wl = [f"{'#':>3} {'Run':>3} {'Un':>2} {'Tipo':<4} {'Top':>7} {'Base':>7} {'Step':>5}  "
                  f"{'Origen del step':<32} Log"]
            for i, r in enumerate(plan.rows, 1):
                n = r.name
                wl.append(f"{i:>3} {r.run:>3} {n.unit:>2} {n.mdtime:<4} {num(n.top):>7} {num(n.bottom):>7} "
                          f"{r.step:>5}  {r.step_src:<32} {n.filename}")
            self._set_text("Well Log", "\n".join(wl))
            im = [f"{'#':>3} {'Scale':<8} {'Well Log Filename':<95} Imagen"]
            for i, r in enumerate(plan.rows, 1):
                im.append(f"{i:>3} {r.scale:<8} {r.name.filename:<95} {basename(r.image_path)}")
            self._set_text("Well Log Image", "\n".join(im))
        else:
            self._set_text("Well Log", "")
            self._set_text("Well Log Image", "")
        if plan.errors:
            self.lbl_status.configure(text=f"✖ {len(plan.errors)} error(es): corrija y vuelva a validar.",
                                      text_color="#d1242f")
            self.tabs.set("Avisos")
        else:
            w = f" · {len(plan.warnings)} aviso(s)" if plan.warnings else ""
            self.lbl_status.configure(
                text=f"✔ {plan.well} ({plan.uwi}) · {len(plan.rows)} logs · {plan.transmittal}{w}",
                text_color=("#1a7f37", "#3fb950"))
            self.tabs.set("Avisos" if plan.warnings else "Well Log")

    def on_preview(self):
        p = self._params()
        if p:
            self._show_plan(make_plan(p))

    def on_generate(self):
        p = self._params()
        if not p:
            return
        plan = make_plan(p)
        self._show_plan(plan)
        if not plan.ok:
            messagebox.showerror("No se generó", "Hay errores; revise la pestaña Avisos.")
            return
        if plan.warnings and not messagebox.askyesno(
                "Avisos", f"Hay {len(plan.warnings)} aviso(s) (pestaña Avisos).\n¿Generar de todas formas?"):
            return
        try:
            self.last_out = write_outputs(plan, p)
        except Exception as e:                       # noqa: BLE001
            messagebox.showerror("Error al escribir", str(e))
            return
        self.btn_open.configure(state="normal")
        self.lbl_status.configure(
            text="✔ Generado:\n" + "\n".join(f"  {os.path.basename(v)}" for v in self.last_out.values()),
            text_color=("#1a7f37", "#3fb950"))
        messagebox.showinfo("Listo", "Plantillas generadas:\n\n" +
                            "\n".join(self.last_out.values()))

    def _open_out(self):
        if self.last_out:
            open_folder(os.path.dirname(self.last_out["well_log"]))


if __name__ == "__main__":
    App().mainloop()
