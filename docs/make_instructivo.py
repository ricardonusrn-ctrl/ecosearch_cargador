"""Genera "Instructivo CARGADOR ECOSEARCH.pdf" (instructivo de usuario resumido).

Uso:  py docs/make_instructivo.py
Usa docs/pantalla_principal.png (captura de la ventana después de validar) y LOGO BOND.png.
"""
from __future__ import annotations

import os
import sys

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

DOCS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(DOCS)
sys.path.insert(0, ROOT)
from app import APP_VERSION  # noqa: E402

OUT = os.path.join(DOCS, "Instructivo CARGADOR ECOSEARCH.pdf")
TEAL, GREY, TEXT = colors.HexColor("#0D6372"), colors.HexColor("#F4F5F7"), colors.HexColor("#1C2B3A")
MUTE, BORDER = colors.HexColor("#5A6472"), colors.HexColor("#C8CDD4")

body = ParagraphStyle("body", fontName="Helvetica", fontSize=9.5, leading=12.5, textColor=TEXT)
bullet = ParagraphStyle("bullet", parent=body, leftIndent=11, bulletIndent=1, spaceAfter=1)
small = ParagraphStyle("small", parent=body, fontSize=8, leading=10, textColor=MUTE)
h1 = ParagraphStyle("h1", parent=body, fontName="Helvetica-Bold", fontSize=17, leading=20,
                    textColor=TEXT, alignment=TA_RIGHT)
sub = ParagraphStyle("sub", parent=small, alignment=TA_RIGHT, fontSize=9)
h2 = ParagraphStyle("h2", parent=body, fontName="Helvetica-Bold", fontSize=11.5, leading=14,
                    textColor=TEAL, spaceBefore=9, spaceAfter=4)
cell = ParagraphStyle("cell", parent=body, fontSize=9, leading=11.5)
num = ParagraphStyle("num", parent=body, fontName="Helvetica-Bold", fontSize=11, textColor=colors.white,
                     alignment=1)


def P(text, style=body):
    return Paragraph(text, style)


def bullets(items):
    return [Paragraph(t, bullet, bulletText="•") for t in items]


def picture(path, width):
    """Imagen con su proporción real (alto calculado desde los píxeles)."""
    with PILImage.open(path) as im:
        w, h = im.size
    return Image(path, width=width, height=width * h / w)


def grid(rows, widths, header=None):
    data = ([[P(f"<b>{h}</b>", cell) for h in header]] if header else []) + \
        [[c if not isinstance(c, str) else P(c, cell) for c in r] for r in rows]
    t = Table(data, colWidths=widths)
    style = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
             ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER), ("LEFTPADDING", (0, 0), (-1, -1), 5),
             ("RIGHTPADDING", (0, 0), (-1, -1), 5), ("TOPPADDING", (0, 0), (-1, -1), 3),
             ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), GREY)]
    t.setStyle(TableStyle(style))
    return t


def steps(items):
    rows = [[P(str(i), num), P(f"<b>{t}</b> — {d}", cell)] for i, (t, d) in enumerate(items, 1)]
    t = Table(rows, colWidths=[0.3 * inch, 7.0 * inch])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, -1), TEAL), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                           ("LINEBELOW", (1, 0), (1, -1), 0.4, BORDER), ("TOPPADDING", (0, 0), (-1, -1), 4),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 5), ("LEFTPADDING", (1, 0), (1, -1), 8)]))
    return t


def header():
    logo = picture(os.path.join(ROOT, "LOGO BOND.png"), 1.55 * inch)
    right =[P("CARGADOR ECOSEARCH", h1), P(f"Instructivo de usuario · versión {APP_VERSION}", sub)]
    t = Table([[logo, right]], colWidths=[2.6 * inch, 4.7 * inch])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                           ("LINEBELOW", (0, 0), (-1, 0), 2, TEAL), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    return t


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(MUTE)
    canvas.drawString(0.6 * inch, 0.4 * inch, "© 2026 Bond Energy Solutions SAS · CARGADOR ECOSEARCH "
                      f"v{APP_VERSION}")
    canvas.drawRightString(letter[0] - 0.6 * inch, 0.4 * inch, f"Página {doc.page}")
    canvas.restoreState()


def build():
    s = [header(), Spacer(1, 8),
         P("Completa las plantillas de carga a Ecosearch <b>Well Log</b> y <b>Well Log Image</b> a partir de "
           "las plantillas que exporta la plataforma (solo con los <i>Resource Path</i>) y de los "
           "<b>.las</b> del pozo.")]

    s += [P("1. Instalación", h2)] + bullets([
        "Ejecute <b>CARGADOR ECOSEARCH Setup v%s.exe</b> (pide permisos de administrador)." % APP_VERSION,
        "Quedan accesos directos en el Escritorio y en el menú Inicio (ahí también está este instructivo).",
        "No necesita Python ni Excel. Una versión nueva se instala encima de la anterior.",
    ])

    s += [P("2. Tenga a mano", h2)] + bullets([
        "Las dos plantillas del pozo exportadas por la plataforma: <b>Well Log</b> y <b>Well Log Image</b>.",
        "Los <b>.las</b> del pozo: de ahí salen Well Name, UWI, Datum Elevation y el Step.",
        "El número de <b>ECP Transmittal</b> (ej. 1348).",
    ])

    s += [P("3. Uso paso a paso", h2), steps([
        ("Plantillas", "en <i>1 · Plantillas y archivos .las</i>, cargue con <i>Examinar…</i> la plantilla "
                       "Well Log y la Well Log Image."),
        (".las del pozo", "<i>Agregar .las…</i> o <i>Agregar carpeta…</i>. Well Name, UWI y Datum se llenan "
                          "solos. Carpeta de salida: opcional (vacía = junto a la plantilla)."),
        ("Datos del pozo", "en <i>2 · Datos del pozo</i> escriba el ECP Transmittal (o <i>Último de la hoja "
                           "Ref</i>) y elija el <b>Service Type</b>. Deje Run en «auto» salvo que deba forzarlo."),
        ("Validar", "en <i>3 · Validar y generar</i> pulse <b>Validar / Vista previa</b> y lea la pestaña "
                    "<b>Avisos</b>."),
        ("Revisar y corregir", "las pestañas <b>Well Log</b> y <b>Well Log Image</b> muestran todas las "
                               "columnas del Excel. <b>Doble clic</b> en una celda para cambiarla (Enter guarda, "
                               "Esc cancela; fechas dd/mm/aaaa). La fila queda en amarillo; <i>Descartar "
                               "cambios</i> los deshace."),
        ("Generar", "pulse <b>Generar plantillas</b> y luego <i>Abrir carpeta de salida</i>."),
    ])]

    shot = picture(os.path.join(DOCS, "pantalla_principal.png"), 7.3 * inch)
    shot.hAlign = "LEFT"
    s += [Spacer(1, 8), KeepTogether([shot, P("Pantalla principal después de validar (pestaña Well Log).",
                                              small)])]

    s += [P("4. Resultado", h2)] + bullets([
        "<b>WL-template-external_delivery_WellLog_&lt;POZO&gt;.xlsx</b> y "
        "<b>WL-template-external_delivery_WellLogImage_&lt;POZO&gt;.xlsx</b>: se cargan tal cual en la plataforma.",
        "<b>REPORTE_&lt;POZO&gt;.txt</b>: avisos, detalle de cada log y los cambios hechos a mano.",
        "Si hay que corregir algo, hágalo en la vista previa (paso 5) y vuelva a generar.",
    ])

    s += [P("5. Mensajes frecuentes", h2), grid([
        ["✖ La plantilla parece ser de OTRO pozo", "Pida a la plataforma la plantilla de este pozo."],
        ["✖ Falta Well Name / UWI / Datum", "Adjunte los .las del pozo o escriba el dato a mano."],
        ["✖ Scale no existe en RefScale / no encuentro la escala",
         "El nombre de la imagen debe traer ESC### (ej. ESC200) o TIME."],
        ["Step asumido", "Ese log no tiene .las adjunto: revise el Step en la pestaña Well Log."],
        [".las y nombre del archivo no coinciden", "Se usa el nombre del archivo; revise si es correcto."],
        ["Rojo en la plataforma (Transmittal, Well, UWI nuevos)",
         "Es normal: la plataforma los valida al cargar."],
    ], [3.0 * inch, 4.3 * inch], header=["Mensaje", "Qué hacer"]),
        P("✖ = error: impide generar. Los demás son avisos para revisar.", small)]

    s += [P("6. Reglas que aplica solo", h2)] + bullets([
        "<b>Log Run Date</b> con formato de fecha corta. Tope, base, unidad y fecha salen del nombre del log.",
        "Imágenes <b>solo en tiempo</b> (nombre con TIME o ESC60): Scale <b>ESC-60/TIME</b>.",
        "Step sin .las: TIME 1.0, UP −0.5, resto 0.5. Fijos: Well Type DEFINITIVO, PDAT Rotary Table (RT), "
        "Null −999.25, Drill 8.5, Casing 7, Log Type PROCESSED.",
        "Estos valores y la lista de Service Type están en <b>config.json</b>, en la carpeta del programa "
        "(C:\\Program Files\\Bond Energy Solutions\\CARGADOR ECOSEARCH; editarlo pide administrador).",
    ])

    doc = SimpleDocTemplate(OUT, pagesize=letter, leftMargin=0.6 * inch, rightMargin=0.6 * inch,
                            topMargin=0.5 * inch, bottomMargin=0.65 * inch,
                            title="Instructivo CARGADOR ECOSEARCH", author="Bond Energy Solutions SAS")
    doc.build(s, onFirstPage=footer, onLaterPages=footer)
    return OUT


if __name__ == "__main__":
    print(build())
