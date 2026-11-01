from datetime import date
from core.names import is_time_image, parse_log_name, scale_from_image, path_matches_well

P = "/data/ecpprov/DATA/BONDENERGY/APIAY-2026-P&T/LIBERTAD-NORTE-11/"


def test_time_log():
    n = parse_log_name(P + "LIBERTAD_NORTE-11_P&T-LOG_12-MAY-2026_3000_FT_MD_0-300_S_TIME.las")
    assert (n.unit, n.mdtime, n.top, n.bottom, n.kind) == ("S", "TIME", 0, 300, "TIME")
    assert n.fecha == date(2026, 5, 12) and n.run is None


def test_mixed_dlis_is_time():
    n = parse_log_name("X-LOG_12-MAY-2026_7400-8400_FT_MD_0-300_S_TIME.dlis")
    assert (n.mdtime, n.top, n.bottom) == ("TIME", 0, 300) and n.notes


def test_md_up_and_run():
    n = parse_log_name("LIBERTAD_NORTE-11_P&T-LOG_RUN1_12-MAY-2026_UP-45_OFF_R_7400-8400_FT_MD.las")
    assert (n.kind, n.top, n.bottom, n.run) == ("UP", 7400, 8400, 1)


def test_rih_with_space_and_uppercase_ext():
    n = parse_log_name("APIAY-13_P&T-LOG_RUN1_14-MAY-2026_RIH_20-10193 FT_MD.LAS")
    assert (n.kind, n.top, n.bottom, n.ext) == ("RIH", 20, 10193, ".LAS")


def test_pooh_descending():
    n = parse_log_name("APIAY-21_P&T-LOG_RUN3_30-MAY-2026_POOH_10300-26_FT_MD.las")
    assert (n.kind, n.top, n.bottom) == ("POOH", 26, 10300) and n.notes


def test_underscore_up_dw():
    assert parse_log_name("A_P&T-LOG_RUN1_19-JUN-2026_UP_30_OFF_8600-9530_FT_MD.LAS").kind == "UP"
    assert parse_log_name("A_P&T-LOG_RUN1_19-JUN-2026_DW_90_OFF_8600-9530_FT_MD.LAS").kind == "DW"


def test_spanish_month():
    assert parse_log_name("SURIA-28_ILT-LOG_14-ABR-2026_0-300_S_TIME.las").fecha == date(2026, 4, 14)


def test_scale():
    assert scale_from_image("a/LIBERTAD_NORTE-11_P&T_LOG_RUN1_12-MAY-2026_OFF_12-8400_FT_ESC200_MD.pdf") == "ESC-200"


def test_time_only_image_scale():
    assert is_time_image("a/X_P&T_LOG_12-MAY-2026_3000_FT_MD_0-300_S_TIME.pdf")
    assert scale_from_image("a/X_P&T_LOG_12-MAY-2026_3000_FT_MD_0-300_S_TIME.pdf") == "ESC-60/TIME"
    assert scale_from_image("a/X_LOG_12-MAY-2026_ESC60_TIME.tif") == "ESC-60/TIME"
    assert scale_from_image("a/X_LOG_12-MAY-2026_0-300_ESC60.pdf") == "ESC-60/TIME"
    assert not is_time_image("a/X_P&T_LOG_RUN1_12-MAY-2026_OFF_12-8400_FT_ESC200_MD.pdf")
    assert not is_time_image("a/X_TIMELAPSE_ESC200_MD.pdf")


def test_well_path_check():
    assert path_matches_well(P + "x.las", "LIBERTAD NORTE-11")
    assert path_matches_well("/d/GUATIQUIA-21/GUATIQUIA-21_x.las", "GUATIQUIA-21H")
    assert not path_matches_well(P + "x.las", "APIAY-13")
