"""Cargador de plantillas Ecosearch (Well Log + Well Log Image) — interfaz CustomTkinter con el
estilo de DATA INTEGRATION (marca teal de Bond Energy Solutions, solo modo claro).

Uso:  python app.py
"""
from __future__ import annotations

import os
import subprocess
import sys
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk

from core import las as lasmod
from core.builder import (SHEETS, Params, cell_text, latest_transmittal, make_plan, parse_cell,
                          read_template, sheet_rows, write_outputs)
from core.config import ROOT, load_config

try:
    from PIL import Image
except ImportError:                                  # sin Pillow el logo se reemplaza por "BES"
    Image = None

# Paleta y fuentes de DATA INTEGRATION
BG = "#FFFFFF"
CARD = "#F4F5F7"
BORDER = "#C8CDD4"
TEXT = "#1C2B3A"
TEXT_MUTE = "#5A6472"
ACCENT = "#0D6372"
ACCENT_HOVER = "#0A4E59"
DANGER = "#7A3030"
DANGER_HOVER = "#5E2424"
OK_FG = "#1E7B34"
OK_HOVER = "#17602A"
CLR_ERR = "#C0392B"
CLR_EDIT = "#1A6FA8"
SECONDARY = "#E4E7EB"
SECONDARY_HOVER = "#D3D8DE"
EDITED_BG = "#FFF4CC"                                # filas con celdas cambiadas a mano
BTN_RADIUS = 10

FNT_TITLE = ("Segoe UI", 18, "bold")
FNT_LABEL = ("Segoe UI", 13, "bold")
FNT_BODY = ("Segoe UI", 12)
FNT_SMALL = ("Segoe UI", 10)
FNT_BTN = ("Segoe UI", 12, "bold")

# Versión publicada (título, pie de página). Se sube junto con version_info.txt y MyAppVersion
# del .iss al publicar un instalador nuevo.
APP_VERSION = "1.0"

LOGO_NAME = "LOGO BOND.png"
ICON_NAME = "CARGADOR ECOSEARCH.ico"
SHEET_TITLES = {"well_log": "Well Log", "well_log_image": "Well Log Image"}


def find_asset(name: str) -> str | None:
    """Junto al programa (desarrollo o .exe con --add-data) o junto al .exe."""
    for d in (ROOT, os.path.dirname(os.path.abspath(sys.argv[0]))):
        path = os.path.join(d, name)
        if os.path.isfile(path):
            return path
    return None


def open_folder(path: str) -> None:
    if sys.platform.startswith("win"):
        os.startfile(path)                       # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


def step_badge(parent, number, text):
    """Etiqueta '1  Título de bloque' (mismo patrón que DATA INTEGRATION)."""
    row = ctk.CTkFrame(parent, fg_color=BG)
    row.pack(anchor="w", padx=2, pady=(10, 4))
    ctk.CTkLabel(row, text=f" {number} ", font=("Segoe UI", 10, "bold"), fg_color=ACCENT,
                 text_color="white", corner_radius=4).pack(side="left")
    ctk.CTkLabel(row, text=f"  {text}", font=FNT_LABEL, text_color=ACCENT, fg_color=BG
                 ).pack(side="left")


def card(parent):
    frame = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=10, border_width=1,
                         border_color=BORDER)
    frame.pack(fill="x", padx=2, pady=(0, 4))
    inner = ctk.CTkFrame(frame, fg_color="transparent")
    inner.pack(fill="x", padx=14, pady=(8, 14))
    return inner


class _BigTabview(ctk.CTkTabview):
    """Pestañas tipo píldora más altas, como en DATA INTEGRATION, con el texto de la pestaña
    activa en blanco (el texto oscuro casi no se lee sobre el teal)."""
    _button_height = 40

    def paint_selected(self):
        for name, btn in getattr(self._segmented_button, "_buttons_dict", {}).items():
            btn.configure(text_color="white" if name == self.get() else TEXT)

    def set(self, name):
        super().set(name)
        self.paint_selected()


class SheetTable(ctk.CTkFrame):
    """TODAS las columnas de una plantilla (títulos de su fila 2). Doble clic en una celda la
    edita; el cambio queda en `edits` ({(clave, columna): celda}) y se usa al generar."""

    def __init__(self, parent, sheet: str, on_change):
        super().__init__(parent, fg_color=BG)
        self.sheet, self.on_change = sheet, on_change
        self.rows: list[tuple[str, list]] = []          # celdas calculadas, sin cambios
        self.headers: list[str] = []
        self.edits: dict = {}
        self._entry = None

        bar = ctk.CTkFrame(self, fg_color=BG)
        bar.pack(fill="x", pady=(2, 6))
        self.lbl = ctk.CTkLabel(bar, text="", font=FNT_SMALL, text_color=CLR_EDIT, anchor="w")
        self.lbl.pack(side="left")
        self.btn_reset = ctk.CTkButton(bar, text="Descartar cambios", font=FNT_SMALL, width=140,
                                       fg_color=SECONDARY, text_color=TEXT,
                                       hover_color=SECONDARY_HOVER, corner_radius=BTN_RADIUS,
                                       state="disabled", command=self.clear_edits)
        self.btn_reset.pack(side="right")

        wrap = ctk.CTkFrame(self, fg_color=BG)
        wrap.pack(fill="both", expand=True)
        wrap.grid_columnconfigure(0, weight=1)
        wrap.grid_rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(wrap, show="headings", style="Eco.Treeview", selectmode="browse")
        vsb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(wrap, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        self.tree.tag_configure("edited", background=EDITED_BG)
        self.tree.bind("<Double-1>", self._on_double)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        # Las rutas no caben en la columna: la fila seleccionada se ve completa aquí.
        self.lbl_detail = ctk.CTkLabel(self, text="", font=FNT_SMALL, text_color=TEXT_MUTE,
                                       anchor="w", justify="left", wraplength=1100)
        self.lbl_detail.pack(fill="x", pady=(4, 0))
        self._update_label()

    # ---------------------------------------------------------------- datos
    def load(self, headers: list[str], rows: list[tuple[str, list]]):
        self._close_entry()
        self.headers, self.rows = headers, rows
        keys = {k for k, _ in rows}
        self.edits = {k: v for k, v in self.edits.items() if k[0] in keys}
        ncols = max((len(c) for _, c in rows), default=0)
        cols = [f"c{j}" for j in range(ncols)]
        self.tree.delete(*self.tree.get_children())
        self.tree.configure(columns=cols)
        for j, col in enumerate(cols):
            title = self._title(j)
            longest = max((len(cell_text(c[j])) for _, c in rows if j < len(c)), default=0)
            width = min(380, max(8 * len(title) + 28, 7 * longest + 18))
            self.tree.heading(col, text=title)
            self.tree.column(col, width=width, minwidth=60, anchor="w", stretch=False)
        for i in range(len(rows)):
            self.tree.insert("", "end", iid=str(i))
            self._refresh_row(i)
        self.lbl_detail.configure(text="Seleccione una fila para ver su Resource Path completo."
                                  if rows else "")
        self._update_label()

    def _on_select(self, _event=None):
        sel = self.tree.selection()
        if not sel:
            return
        i = int(sel[0])
        key, cells = self.rows[i]
        parts = [f"Fila {i + 3}  ·  {self._title(0)}: {cell_text(self.edits.get((key, 0), cells[0]))}"]
        if self.sheet == "well_log_image" and len(cells) > 4:
            parts.append(f"{self._title(4)}: {cell_text(self.edits.get((key, 4), cells[4]))}")
        self.lbl_detail.configure(text="\n".join(parts))

    def clear_edits(self):
        self._close_entry()
        self.edits = {}
        for i in range(len(self.rows)):
            self._refresh_row(i)
        self._update_label()
        self.on_change()

    def _title(self, j: int) -> str:
        return self.headers[j] if j < len(self.headers) and self.headers[j] else chr(65 + j)

    def _refresh_row(self, i: int):
        key, cells = self.rows[i]
        values = []
        for j, c in enumerate(cells):
            new = self.edits.get((key, j))
            values.append(f"✎ {cell_text(new)}" if new is not None else cell_text(c))
        edited = any((key, j) in self.edits for j in range(len(cells)))
        self.tree.item(str(i), values=values, tags=("edited",) if edited else ())

    def _update_label(self):
        n = len(self.edits)
        if n:
            self.lbl.configure(text=f"✎ {n} celda(s) cambiada(s) a mano: se usan al generar.  "
                                    "Doble clic en una celda para cambiarla.")
            self.btn_reset.configure(state="normal")
        else:
            self.lbl.configure(text="Doble clic en una celda para cambiarla (Enter guarda, "
                                    "Esc cancela).")
            self.btn_reset.configure(state="disabled")

    # ---------------------------------------------------------------- edición en la celda
    def _on_double(self, event):
        if self.tree.identify_region(event.x, event.y) != "cell":
            return
        iid, col = self.tree.identify_row(event.y), self.tree.identify_column(event.x)
        if not iid:
            return
        i, j = int(iid), int(col[1:]) - 1
        key, cells = self.rows[i]
        if j >= len(cells):
            return
        self.tree.see(iid)
        x, y, w, h = self.tree.bbox(iid, col)
        self._close_entry()
        entry = ttk.Entry(self.tree, font=FNT_SMALL)
        entry.insert(0, cell_text(self.edits.get((key, j), cells[j])))
        entry.select_range(0, "end")
        entry.place(x=x, y=y, width=max(w, 160), height=h)
        entry.focus_set()
        entry.bind("<Return>", lambda _e: self._save(i, j))
        entry.bind("<KP_Enter>", lambda _e: self._save(i, j))
        entry.bind("<FocusOut>", lambda _e: self._save(i, j))
        entry.bind("<Escape>", lambda _e: self._close_entry())
        self._entry = entry

    def _close_entry(self):
        if self._entry is not None:
            entry, self._entry = self._entry, None
            entry.destroy()

    def _save(self, i: int, j: int):
        if self._entry is None:
            return
        text = self._entry.get()
        self._close_entry()
        key, cells = self.rows[i]
        try:
            new = parse_cell(cells[j][0], text)
        except ValueError as e:
            messagebox.showerror("Valor no válido", f"{self._title(j)}: {e}")
            return
        if new == cells[j]:
            self.edits.pop((key, j), None)
        else:
            self.edits[(key, j)] = new
        self._refresh_row(i)
        self._update_label()
        self.on_change()


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("light")
        ttk.Style(self).theme_use("clam")            # 'vista' ignora el fondo del Treeview
        self._style_tables()
        self.cfg = load_config()
        self.title(f"Bond Energy Solutions  —  CARGADOR ECOSEARCH  v{APP_VERSION}")
        icon = find_asset(ICON_NAME)
        if icon and sys.platform.startswith("win"):
            try:
                self.iconbitmap(icon)
            except Exception:                        # noqa: BLE001  (ícono es opcional)
                pass
        self.geometry("1360x880")
        self.minsize(1100, 720)
        self.configure(fg_color=BG)
        self.las_files: list[str] = []
        self.plan = None
        self.last_out: dict | None = None
        self._last_transmittal = None

        self._build_header()
        body = ctk.CTkFrame(self, fg_color=BG)
        body.pack(fill="both", expand=True, padx=12, pady=(10, 0))
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)
        self._build_left(body)
        self._build_right(body)
        ctk.CTkLabel(self, text=f"© 2026 Bond Energy Solutions SAS · Cargador Ecosearch "
                                f"v{APP_VERSION} · Todos los derechos reservados",
                     font=FNT_SMALL, text_color=TEXT_MUTE).pack(pady=6)
        if sys.platform.startswith("win"):
            self.after(0, lambda: self.state("zoomed"))

    def _style_tables(self):
        style = ttk.Style(self)
        style.configure("Eco.Treeview", background="#FFFFFF", foreground=TEXT, rowheight=24,
                        fieldbackground="#FFFFFF", font=FNT_SMALL, borderwidth=0)
        style.configure("Eco.Treeview.Heading", background=ACCENT, foreground="white",
                        font=("Segoe UI", 10, "bold"), relief="flat", padding=4)
        style.map("Eco.Treeview", background=[("selected", ACCENT)],
                  foreground=[("selected", "white")])
        style.map("Eco.Treeview.Heading", background=[("active", ACCENT_HOVER)])

    # ------------------------------------------------------------------ encabezado
    def _build_header(self):
        hdr = ctk.CTkFrame(self, fg_color=BG, height=104, corner_radius=0)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        left = ctk.CTkFrame(hdr, fg_color="transparent")
        left.pack(side="left", padx=20, pady=(10, 10), fill="y")
        logo_img, logo = None, find_asset(LOGO_NAME)
        if logo and Image is not None:
            try:
                pil = Image.open(logo)
                w, h = pil.size
                logo_img = ctk.CTkImage(light_image=pil, dark_image=pil,
                                        size=(max(1, round(w * 72 / h)), 72))
            except OSError:
                logo_img = None
        if logo_img is not None:
            ctk.CTkLabel(left, image=logo_img, text="").pack(side="left", padx=(0, 14))
        else:
            badge = ctk.CTkFrame(left, fg_color=ACCENT, width=72, height=72, corner_radius=10)
            badge.pack_propagate(False)
            badge.pack(side="left", padx=(0, 14))
            ctk.CTkLabel(badge, text="BES", font=("Segoe UI", 14, "bold"), text_color="white"
                         ).place(relx=0.5, rely=0.5, anchor="center")
        brand = ctk.CTkFrame(left, fg_color="transparent")
        brand.pack(side="left")
        ctk.CTkLabel(brand, text="BOND ENERGY SOLUTIONS", font=FNT_TITLE, text_color=ACCENT,
                     anchor="w").pack(anchor="w")
        ctk.CTkLabel(brand, text="Petrophysics  ·  Data Services  ·  Wireline Analytics",
                     font=FNT_SMALL, text_color=TEXT_MUTE, anchor="w").pack(anchor="w")

        right = ctk.CTkFrame(hdr, fg_color="transparent")
        right.pack(side="right", padx=22, pady=(10, 0), fill="y")
        ctk.CTkLabel(right, text="CARGADOR ECOSEARCH", font=FNT_TITLE, text_color=TEXT
                     ).pack(anchor="e")
        ctk.CTkLabel(right, text="Plantillas Well Log  ·  Well Log Image", font=FNT_SMALL,
                     text_color=TEXT_MUTE).pack(anchor="e")
        actions = ctk.CTkFrame(right, fg_color="transparent")
        actions.pack(anchor="e", pady=(8, 0))
        ctk.CTkButton(actions, text="🔄 Reiniciar programa", font=FNT_BTN, fg_color=SECONDARY,
                      text_color=TEXT, hover_color=SECONDARY_HOVER, corner_radius=BTN_RADIUS,
                      command=self._on_reset).pack(side="left", padx=(0, 8))
        ctk.CTkButton(actions, text="Cerrar aplicación", font=FNT_BTN, fg_color=DANGER,
                      hover_color=DANGER_HOVER, corner_radius=BTN_RADIUS, command=self.destroy
                      ).pack(side="left")

        ctk.CTkFrame(self, fg_color=ACCENT, height=3, corner_radius=0).pack(fill="x")

    # ------------------------------------------------------------------ panel izquierdo
    def _build_left(self, body):
        left = ctk.CTkScrollableFrame(body, width=440, fg_color=BG)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=(0, 6))

        step_badge(left, "1", "Plantillas y archivos .las")
        c1 = card(left)
        self.v_wl, self.v_img, self.v_out = ctk.StringVar(), ctk.StringVar(), ctk.StringVar()
        self._file_row(c1, "Plantilla Well Log (.xlsx)", self.v_wl, self._pick_wl)
        self._file_row(c1, "Plantilla Well Log Image (.xlsx)", self.v_img, self._pick_img)
        self._label(c1, "Archivos .las del pozo")
        bar = ctk.CTkFrame(c1, fg_color="transparent")
        bar.pack(fill="x")
        self._button(bar, "Agregar .las…", self._add_las, width=120).pack(side="left", padx=(0, 6))
        self._button(bar, "Agregar carpeta…", self._add_las_dir, width=130).pack(side="left",
                                                                                   padx=(0, 6))
        self._button(bar, "Limpiar", self._clear_las, secondary=True, width=80).pack(side="left")
        self.lbl_las = ctk.CTkLabel(c1, text="Ningún .las cargado", anchor="w", justify="left",
                                    font=FNT_SMALL, text_color=TEXT_MUTE, wraplength=400)
        self.lbl_las.pack(fill="x", pady=(4, 0))
        self._file_row(c1, "Carpeta de salida (vacío = junto a la plantilla)", self.v_out,
                       self._pick_out)

        step_badge(left, "2", "Datos del pozo")
        c2 = card(left)
        self.v_trans, self.v_well, self.v_uwi, self.v_datum = (ctk.StringVar() for _ in range(4))
        self.v_run = ctk.StringVar(value="auto")
        self.v_service = ctk.StringVar(value=self.cfg["default_service_type"])
        self._label(c2, "ECP Transmittal (ej. 1348)")
        r = ctk.CTkFrame(c2, fg_color="transparent")
        r.pack(fill="x")
        self._entry_widget(r, self.v_trans).pack(side="left", fill="x", expand=True)
        self.btn_last = self._button(r, "Último de la hoja Ref", self._fill_transmittal,
                                     secondary=True, width=150)
        self.btn_last.configure(state="disabled")
        self.btn_last.pack(side="left", padx=(6, 0))
        self._entry(c2, "Well Name (del encabezado .las)", self.v_well)
        self._entry(c2, "UWI (del encabezado .las)", self.v_uwi)
        self._entry(c2, "Datum Elevation (EKB del .las)", self.v_datum)
        self._entry(c2, "Run (auto = plantilla / nombre / 1)", self.v_run)
        self._label(c2, "Service Type")
        ctk.CTkComboBox(c2, variable=self.v_service, values=self.cfg["service_types"],
                        font=FNT_BODY, fg_color=BG, border_color=BORDER, button_color=ACCENT,
                        button_hover_color=ACCENT_HOVER, dropdown_fg_color=BG, state="readonly"
                        ).pack(fill="x")
        fixed = (f"Fijos: Well Type {self.cfg['well_type']} · PDAT {self.cfg['pdat']} · "
                 f"Null {self.cfg['null']} · Drill {self.cfg['drill_size']} · "
                 f"Casing {self.cfg['casing_size']} · imágenes solo en tiempo "
                 f"{self.cfg['time_scale']} (se cambian en config.json)")
        ctk.CTkLabel(c2, text=fixed, anchor="w", justify="left", wraplength=400, font=FNT_SMALL,
                     text_color=TEXT_MUTE).pack(fill="x", pady=(10, 0))

        step_badge(left, "3", "Validar y generar")
        c3 = card(left)
        btns = ctk.CTkFrame(c3, fg_color="transparent")
        btns.pack(fill="x", pady=(4, 0))
        self._button(btns, "Validar / Vista previa", self.on_preview).pack(
            side="left", expand=True, fill="x", padx=(0, 6))
        ctk.CTkButton(btns, text="Generar plantillas", font=FNT_BTN, fg_color=OK_FG,
                      hover_color=OK_HOVER, corner_radius=BTN_RADIUS, height=36,
                      command=self.on_generate).pack(side="left", expand=True, fill="x")
        self.btn_open = self._button(c3, "Abrir carpeta de salida", self._open_out, secondary=True)
        self.btn_open.configure(state="disabled")
        self.btn_open.pack(fill="x", pady=(8, 0))

    def _label(self, parent, text):
        ctk.CTkLabel(parent, text=text, anchor="w", font=FNT_SMALL, text_color=TEXT
                     ).pack(fill="x", pady=(8, 2))

    def _entry_widget(self, parent, var):
        return ctk.CTkEntry(parent, textvariable=var, font=FNT_BODY, fg_color=BG,
                            border_color=BORDER, text_color=TEXT)

    def _entry(self, parent, label, var):
        self._label(parent, label)
        self._entry_widget(parent, var).pack(fill="x")

    def _button(self, parent, text, cmd, secondary=False, width=140):
        if secondary:
            return ctk.CTkButton(parent, text=text, font=FNT_SMALL, width=width, height=32,
                                 fg_color=SECONDARY, text_color=TEXT, hover_color=SECONDARY_HOVER,
                                 corner_radius=BTN_RADIUS, command=cmd)
        return ctk.CTkButton(parent, text=text, font=FNT_BTN, width=width, height=36,
                             fg_color=ACCENT, hover_color=ACCENT_HOVER, corner_radius=BTN_RADIUS,
                             command=cmd)

    def _file_row(self, parent, label, var, cmd):
        self._label(parent, label)
        r = ctk.CTkFrame(parent, fg_color="transparent")
        r.pack(fill="x")
        self._entry_widget(r, var).pack(side="left", fill="x", expand=True)
        self._button(r, "Examinar…", cmd, secondary=True, width=96).pack(side="left", padx=(6, 0))

    # ------------------------------------------------------------------ panel derecho
    def _build_right(self, body):
        right = ctk.CTkFrame(body, fg_color=BG)
        right.grid(row=0, column=1, sticky="nsew", pady=(0, 6))
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)
        status = ctk.CTkFrame(right, fg_color=CARD, corner_radius=10, border_width=1,
                              border_color=BORDER)
        status.grid(row=0, column=0, sticky="ew", pady=(6, 0))
        self.lbl_status = ctk.CTkLabel(status, text="Cargue las plantillas y los .las, luego pulse "
                                       "«Validar / Vista previa».", anchor="w", justify="left",
                                       wraplength=820, font=FNT_BODY, text_color=TEXT)
        self.lbl_status.pack(fill="x", padx=14, pady=10)

        self.tabs = _BigTabview(
            right, fg_color=BG, segmented_button_fg_color=CARD,
            segmented_button_selected_color=ACCENT,
            segmented_button_selected_hover_color=ACCENT_HOVER,
            segmented_button_unselected_color=SECONDARY,
            segmented_button_unselected_hover_color=SECONDARY_HOVER,
            segmented_button_font=("Segoe UI", 13, "bold"), corner_radius=12, border_width=0,
            anchor="nw", text_color=TEXT, command=lambda: self.tabs.paint_selected())
        self.tabs.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        tab = self.tabs.add("Avisos")
        self.txt_avisos = ctk.CTkTextbox(tab, font=FNT_BODY, wrap="word", fg_color=BG,
                                         border_width=1, border_color=BORDER, text_color=TEXT)
        self.txt_avisos.pack(fill="both", expand=True)
        self.txt_avisos.configure(state="disabled")
        self.tables: dict[str, SheetTable] = {}
        for sheet in SHEETS:
            tab = self.tabs.add(SHEET_TITLES[sheet])
            table = SheetTable(tab, sheet, on_change=self._on_edits_changed)
            table.pack(fill="both", expand=True)
            self.tables[sheet] = table
        self.tabs.set("Avisos")
        self.after(50, self.tabs.paint_selected)

    def _set_avisos(self, text: str):
        self.txt_avisos.configure(state="normal")
        self.txt_avisos.delete("1.0", "end")
        self.txt_avisos.insert("1.0", text)
        self.txt_avisos.configure(state="disabled")

    def _n_edits(self) -> int:
        return sum(len(t.edits) for t in self.tables.values())

    def _on_edits_changed(self):
        if self.plan is not None and self.plan.ok:
            self._status_ok(self.plan)

    def _status_ok(self, plan):
        w = f" · {len(plan.warnings)} aviso(s)" if plan.warnings else ""
        n = self._n_edits()
        e = f" · ✎ {n} cambio(s) manual(es)" if n else ""
        self.lbl_status.configure(
            text=f"✔ {plan.well} ({plan.uwi}) · {len(plan.rows)} logs · {plan.transmittal}{w}{e}",
            text_color=OK_FG)

    # ------------------------------------------------------------------ selección de archivos
    def _pick_wl(self):
        f = filedialog.askopenfilename(title="Plantilla Well Log", filetypes=[("Excel", "*.xlsx")])
        if f:
            self.v_wl.set(f)
            self._load_refs(f)

    def _pick_img(self):
        f = filedialog.askopenfilename(title="Plantilla Well Log Image",
                                       filetypes=[("Excel", "*.xlsx")])
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
        self._set_avisos("\n".join(lines) or "Sin avisos.")
        rows = sheet_rows(plan, self.cfg) if plan.rows else {s: [] for s in SHEETS}
        self.tables["well_log"].load(plan.wl_headers, rows["well_log"])
        self.tables["well_log_image"].load(plan.img_headers, rows["well_log_image"])
        if plan.errors:
            self.lbl_status.configure(text=f"✖ {len(plan.errors)} error(es): corrija y vuelva a "
                                           "validar.", text_color=CLR_ERR)
            self.tabs.set("Avisos")
        else:
            self._status_ok(plan)
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
            self.last_out = write_outputs(plan, p, {s: t.edits for s, t in self.tables.items()})
        except Exception as e:                       # noqa: BLE001
            messagebox.showerror("Error al escribir", str(e))
            return
        self.btn_open.configure(state="normal")
        n = self._n_edits()
        manual = f"\n\nSe aplicaron {n} cambio(s) manual(es) (detalle en el reporte)." if n else ""
        self.lbl_status.configure(
            text="✔ Generado:  " + "  ·  ".join(os.path.basename(v) for v in self.last_out.values()),
            text_color=OK_FG)
        messagebox.showinfo("Listo", "Plantillas generadas:\n\n" +
                            "\n".join(self.last_out.values()) + manual)

    def _open_out(self):
        if self.last_out:
            open_folder(os.path.dirname(self.last_out["well_log"]))

    def _on_reset(self):
        """Deja el programa como recién abierto."""
        if (self.v_wl.get() or self.v_img.get() or self.las_files or self._n_edits()) and \
                not messagebox.askyesno("Reiniciar programa",
                                        "¿Borrar todo lo cargado y escrito (incluidos los cambios "
                                        "manuales de la vista previa)?"):
            return
        for var in (self.v_wl, self.v_img, self.v_out, self.v_trans, self.v_well, self.v_uwi,
                    self.v_datum):
            var.set("")
        self.v_run.set("auto")
        self.v_service.set(self.cfg["default_service_type"])
        self._clear_las()
        self._last_transmittal = None
        self.btn_last.configure(state="disabled")
        self.btn_open.configure(state="disabled")
        self.plan, self.last_out = None, None
        for t in self.tables.values():
            t.edits = {}
            t.load([], [])
        self._set_avisos("")
        self.lbl_status.configure(text="Cargue las plantillas y los .las, luego pulse "
                                       "«Validar / Vista previa».", text_color=TEXT)
        self.tabs.set("Avisos")


if __name__ == "__main__":
    App().mainloop()
