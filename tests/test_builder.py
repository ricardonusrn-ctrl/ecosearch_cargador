"""Regenera las plantillas del pozo LIBERTAD NORTE-11 desde cero y las compara celda a celda
con las plantillas de referencia (ya entregadas/validadas)."""
import glob
import os
import warnings
import zipfile

import openpyxl
import pytest

from core.builder import (Params, cell_text, make_plan, norm_transmittal, parse_cell,
                          read_template, write_outputs)
from core.config import load_config
from core.xlsx_xml import write_template

FX = os.path.join(os.path.dirname(__file__), "fixtures")
REF_WL = os.path.join(FX, "ref_WellLog_LIBERTAD_NORTE-11.xlsx")
REF_IMG = os.path.join(FX, "ref_WellLogImage_LIBERTAD_NORTE-11.xlsx")
LAS = sorted(glob.glob(os.path.join(FX, "las", "*.las")))


def grid(path):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ws = openpyxl.load_workbook(path).worksheets[0]
    return [[c for c in r] for r in ws.iter_rows(values_only=True)]


@pytest.fixture()
def inputs(tmp_path):
    """Plantillas como llegan de la plataforma: solo Resource Path (col A)."""
    paths, _, _ = read_template(REF_WL)
    imgs, _, _ = read_template(REF_IMG)
    wl, img = tmp_path / "in_wl.xlsx", tmp_path / "in_img.xlsx"
    write_template(REF_WL, str(wl), [[("s", p)] for p in paths], "A")
    write_template(REF_IMG, str(img), [[("s", p)] for p in imgs[:4]], "A")
    return str(wl), str(img), tmp_path


def params(inputs, **kw):
    wl, img, tmp = inputs
    return Params(wl_template=wl, img_template=img, las_files=LAS, transmittal="1344",
                  out_dir=str(tmp / "out"), **kw)


def test_plan_ok_and_values(inputs):
    plan = make_plan(params(inputs))
    assert not plan.errors, plan.errors
    assert (plan.well, plan.uwi, plan.datum) == ("LIBERTAD NORTE-11", "LIBN0011", 31.0)
    assert plan.transmittal == "ECP_TRANSMITTAL_0000001344"
    assert len(plan.rows) == 21


@pytest.mark.parametrize("which,ref", [("well_log", REF_WL), ("well_log_image", REF_IMG)])
def test_output_equals_reference(inputs, which, ref):
    p = params(inputs)
    out = write_outputs(make_plan(p), p)[which]
    got, exp = grid(out), grid(ref)
    assert len(got) == len(exp)
    for i, (g, e) in enumerate(zip(got, exp), 1):
        assert g == e, f"fila {i}:\n got {g}\n exp {e}"


def test_zip_structure_preserved(inputs):
    p = params(inputs)
    out = write_outputs(make_plan(p), p)["well_log"]
    with zipfile.ZipFile(out) as z, zipfile.ZipFile(REF_WL) as r:
        assert z.namelist() == r.namelist()          # mismas hojas Ref*, mismo orden
        for name in r.namelist():
            if name not in ("xl/worksheets/sheet1.xml", "xl/styles.xml"):
                assert z.read(name) == r.read(name)  # el resto, idéntico byte a byte
        s = z.read("xl/worksheets/sheet1.xml").decode()
        assert 'sqref="B3:B23"' in s and '<dimension ref="A1:Q23"/>' in s


def test_wrong_well_images_blocked(inputs):
    p = params(inputs, well="APIAY-13", uwi="APIA0013", datum=20.6)
    plan = make_plan(p)
    assert any("OTRO pozo" in e for e in plan.errors)
    with pytest.raises(ValueError):
        write_outputs(plan, p)


def test_assumed_step_without_las(inputs):
    p = params(inputs, well="LIBERTAD NORTE-11", uwi="LIBN0011", datum=31.0)
    p.las_files = []
    plan = make_plan(p)
    assert not plan.errors
    steps = {r.name.filename: r.step for r in plan.rows}
    assert all(r.step_src.startswith("asumido") for r in plan.rows)
    assert steps[[k for k in steps if "UP-45_OFF_R" in k][0]] == -0.5
    assert steps[[k for k in steps if "_1000_FT" in k][0]] == 1.0
    assert any("Step asumido" in w for w in plan.warnings)


def test_run_override_and_transmittal_format(inputs):
    plan = make_plan(params(inputs, run=2))
    assert {r.run for r in plan.rows} == {2}
    assert norm_transmittal("1348") == "ECP_TRANSMITTAL_0000001348"
    with pytest.raises(ValueError):
        norm_transmittal("abc")


def first_sheet(path):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return openpyxl.load_workbook(path).worksheets[0]


@pytest.mark.parametrize("which", ["well_log", "well_log_image"])
def test_log_run_date_is_short_date(inputs, which):
    p = params(inputs)
    ws = first_sheet(write_outputs(make_plan(p), p)[which])
    for row in range(3, ws.max_row + 1):
        assert ws.cell(row, 8).is_date
        assert ws.cell(row, 8).number_format == "mm-dd-yy"    # formato integrado 14 = Fecha corta


def test_headers_of_all_columns(inputs):
    plan = make_plan(params(inputs))
    assert len(plan.wl_headers) >= 17 and plan.wl_headers[7] == "Log Run Date *"
    assert len(plan.img_headers) >= 18 and plan.img_headers[13] == "Scale *"


def test_service_types_in_config():
    types = load_config()["service_types"]
    for t in ("PRODUCCION-PLT", "PLT", "REGISTRO CORRELACION", "REGISTRO MEMORIZADO"):
        assert t in types


def test_installed_config_next_to_exe_wins(tmp_path, monkeypatch):
    """En el .exe instalado, el config.json junto al .exe manda sobre el empaquetado."""
    import json
    import core.config as config
    exe_cfg = tmp_path / "config.json"
    exe_cfg.write_text(json.dumps({"service_types": ["ILT"], "drill_size": 6.125}), encoding="utf-8")
    monkeypatch.setattr(config, "EXE_CONFIG_PATH", str(exe_cfg))
    cfg = config.load_config()
    assert cfg["service_types"] == ["ILT"] and cfg["drill_size"] == 6.125
    assert cfg["time_scale"] == "ESC-60/TIME"                  # lo demás sigue igual


def _img_template(inputs, names):
    """Plantilla Well Log Image con estas imágenes (misma carpeta que las de referencia)."""
    _, _, tmp = inputs
    imgs, _, _ = read_template(REF_IMG)
    folder = imgs[0].rsplit("/", 1)[0]
    out = tmp / "in_img_mix.xlsx"
    write_template(REF_IMG, str(out), [[("s", f"{folder}/{n}")] for n in names], "A")
    return str(out)


def test_time_images_go_to_time_logs(inputs):
    p = params(inputs)
    p.img_template = _img_template(inputs, [
        "LIBERTAD_NORTE-11_P&T_LOG_RUN1_12-MAY-2026_OFF_12-8400_FT_ESC200_MD.pdf",
        "LIBERTAD_NORTE-11_P&T_LOG_12-MAY-2026_ESTACIONES_0-300_S_TIME.pdf",
        "LIBERTAD_NORTE-11_P&T_LOG_RUN1_12-MAY-2026_OFF_12-8400_FT_ESC500_MD.pdf"])
    plan = make_plan(p)
    assert not plan.errors, plan.errors
    for r in plan.rows:
        if r.name.mdtime == "TIME":
            assert r.scale == "ESC-60/TIME" and r.image_path.endswith("S_TIME.pdf")
        else:
            assert r.scale in ("ESC-200", "ESC-500")
    ws = first_sheet(write_outputs(plan, p)["well_log_image"])
    scales = {ws.cell(i, 14).value for i in range(3, ws.max_row + 1)}
    assert scales == {"ESC-60/TIME", "ESC-200", "ESC-500"}


def test_only_time_images(inputs):
    p = params(inputs)
    p.img_template = _img_template(inputs, ["LIBERTAD_NORTE-11_P&T_LOG_12-MAY-2026_0-300_S_TIME.pdf"])
    plan = make_plan(p)
    assert not plan.errors, plan.errors
    assert {r.scale for r in plan.rows} == {"ESC-60/TIME"}
    assert any("solo en tiempo" in w for w in plan.warnings)     # hay logs de profundidad


def test_manual_edits_are_written_and_reported(inputs):
    p = params(inputs)
    plan = make_plan(p)
    key = plan.rows[0].path
    edits = {"well_log": {(key, 13): ("n", 0.25), (key, 7): parse_cell("d", "13/05/2026")},
             "well_log_image": {(key, 13): ("s", "ESC-500")}}
    out = write_outputs(plan, p, edits)
    wl, img = first_sheet(out["well_log"]), first_sheet(out["well_log_image"])
    assert wl["N3"].value == 0.25 and wl["H3"].value.day == 13 and wl["N4"].value == 1.0
    assert img["N3"].value == "ESC-500" and img["N4"].value == "ESC-200"
    rep = open(out["reporte"], encoding="utf-8").read()
    assert "CAMBIOS MANUALES" in rep and "Step *: 1 -> 0.25" in rep and "13/05/2026" in rep


def test_cell_parse_and_text():
    assert parse_cell("n", "-999,25") == ("n", -999.25)
    assert parse_cell("n", "7400") == ("n", 7400)
    assert parse_cell("d", "12-MAY-2026") == parse_cell("d", "12/05/2026") == parse_cell("d", "2026-05-12")
    assert cell_text(parse_cell("d", "12-ABR-2026")) == "12/04/2026"
    with pytest.raises(ValueError):
        parse_cell("n", "abc")
    with pytest.raises(ValueError):
        parse_cell("d", "31/02/2026")
