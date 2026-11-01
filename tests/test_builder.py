"""Regenera las plantillas del pozo LIBERTAD NORTE-11 desde cero y las compara celda a celda
con las plantillas de referencia (ya entregadas/validadas)."""
import glob
import os
import warnings
import zipfile

import openpyxl
import pytest

from core.builder import Params, make_plan, write_outputs, read_template, norm_transmittal
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
