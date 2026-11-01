"""Escritura de plantillas editando el XML de la hoja 1 directamente.

La plataforma (Azure) no lee las plantillas si se regraban con openpyxl, así que aquí solo
cambian sheet1.xml (y styles.xml si falta el formato de fecha d-mmm-yyyy). El resto del zip
(hojas Ref*, workbook, sharedStrings...) se copia byte a byte.
"""
from __future__ import annotations

import re
import zipfile
from xml.sax.saxutils import escape

DATE_FORMAT_CODE = r"d\-mmm\-yyyy"

# Un valor de celda: ("s", texto) | ("n", número) | ("d", serial_excel)
Cell = tuple


def first_sheet_path(zf: zipfile.ZipFile) -> str:
    wb = zf.read("xl/workbook.xml").decode("utf8")
    rid = re.search(r"<sheet\b[^>]*?r:id=\"([^\"]+)\"", wb).group(1)
    rels = zf.read("xl/_rels/workbook.xml.rels").decode("utf8")
    for rel in re.findall(r"<Relationship\b[^>]*>", rels):
        if f'Id="{rid}"' in rel:
            target = re.search(r'Target="([^"]+)"', rel).group(1)
            return target.lstrip("/") if target.startswith("/") else "xl/" + target
    raise ValueError("No encuentro la hoja 1 de la plantilla")


def numstr(v) -> str:
    return str(v) if isinstance(v, int) else repr(float(v))


def _cell_xml(ref: str, cell: Cell, date_style: int) -> str:
    kind, v = cell
    if kind == "s":
        return f'<c r="{ref}" t="inlineStr"><is><t>{escape(str(v))}</t></is></c>'
    if kind == "d":
        return f'<c r="{ref}" s="{date_style}"><v>{int(v)}</v></c>'
    return f'<c r="{ref}"><v>{numstr(v)}</v></c>'


def rows_xml(rows: list[list[Cell]], first_row: int, date_style: int) -> str:
    out = []
    for i, cells in enumerate(rows):
        r = first_row + i
        body = "".join(_cell_xml(f"{chr(65 + j)}{r}", c, date_style) for j, c in enumerate(cells))
        out.append(f'<row r="{r}">{body}</row>')
    return "".join(out)


def ensure_date_style(styles_xml: str) -> tuple[str, int]:
    """Devuelve (styles_xml, índice de xf con formato d-mmm-yyyy). Lo agrega si falta."""
    code = re.escape(DATE_FORMAT_CODE)
    m = re.search(rf'<numFmt\b[^>]*numFmtId="(\d+)"[^>]*formatCode="{code}"', styles_xml) or \
        re.search(rf'<numFmt\b[^>]*formatCode="{code}"[^>]*numFmtId="(\d+)"', styles_xml)
    if m:
        fmt_id = int(m.group(1))
    else:
        ids = [int(x) for x in re.findall(r'<numFmt\b[^>]*numFmtId="(\d+)"', styles_xml)]
        fmt_id = max([163] + ids) + 1
        new = f'<numFmt numFmtId="{fmt_id}" formatCode="{DATE_FORMAT_CODE}"/>'
        if "<numFmts" in styles_xml:
            styles_xml = re.sub(r'<numFmts count="(\d+)"',
                                lambda k: f'<numFmts count="{int(k.group(1)) + 1}"', styles_xml, count=1)
            styles_xml = styles_xml.replace("</numFmts>", new + "</numFmts>", 1)
        else:
            styles_xml = re.sub(r"(<styleSheet\b[^>]*>)", r'\1<numFmts count="1">' + new + "</numFmts>",
                                styles_xml, count=1)
    block = re.search(r"<cellXfs\b[^>]*>(.*?)</cellXfs>", styles_xml, re.S)
    xfs = re.findall(r"<xf\b[^>]*?(?:/>|>.*?</xf>)", block.group(1), re.S)
    for i, xf in enumerate(xfs):
        if (f'numFmtId="{fmt_id}"' in xf and 'fontId="0"' in xf and 'fillId="0"' in xf
                and 'borderId="0"' in xf):
            return styles_xml, i
    new_xf = (f'<xf numFmtId="{fmt_id}" fontId="0" fillId="0" borderId="0" xfId="0" '
              'applyNumberFormat="true"/>')
    styles_xml = re.sub(r'<cellXfs count="\d+"', f'<cellXfs count="{len(xfs) + 1}"', styles_xml, count=1)
    styles_xml = styles_xml.replace("</cellXfs>", new_xf + "</cellXfs>", 1)
    return styles_xml, len(xfs)


def write_template(src: str, dst: str, rows: list[list[Cell]], last_col: str) -> None:
    """Copia src -> dst reemplazando solo las filas de datos (fila 3 en adelante)."""
    with zipfile.ZipFile(src) as zin:
        sheet_path = first_sheet_path(zin)
        sheet = zin.read(sheet_path).decode("utf8")
        styles, date_style = ensure_date_style(zin.read("xl/styles.xml").decode("utf8"))

        m = re.search(r"<sheetData>(.*)</sheetData>", sheet, re.S)
        r1 = re.search(r'<row r="1"[^>]*>.*?</row>', m.group(1), re.S).group(0)
        r2 = re.search(r'<row r="2"[^>]*>.*?</row>', m.group(1), re.S).group(0)
        last = 2 + len(rows)
        data = f"<sheetData>\n{r1}\n{r2}{rows_xml(rows, 3, date_style)}</sheetData>"
        new_sheet = sheet[:m.start()] + data + sheet[m.end():]
        new_sheet = re.sub(r'<dimension ref="[^"]*"\s*/>',
                           f'<dimension ref="A1:{last_col}{last}"/>', new_sheet, count=1)
        # el formato condicional (resaltado rojo contra las hojas Ref) se extiende a las filas nuevas
        new_sheet = re.sub(r'sqref="([A-Z]+)3:([A-Z]+)\d+"',
                           lambda k: f'sqref="{k.group(1)}3:{k.group(2)}{last}"', new_sheet)

        with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                blob = zin.read(item.filename)
                if item.filename == sheet_path:
                    blob = new_sheet.encode("utf8")
                elif item.filename == "xl/styles.xml":
                    blob = styles.encode("utf8")
                zout.writestr(item, blob, compress_type=zipfile.ZIP_DEFLATED)
