"""Versión por línea de comandos (misma lógica que la interfaz).

Ejemplo:
  python cli.py --wl-template WellLog.xlsx --img-template WellLogImage.xlsx \
                --las-dir ./las --transmittal 1348 --out-dir ./salida
Con --dry-run solo valida y muestra el reporte.
"""
import argparse
import glob
import os
import sys

from core.builder import Params, make_plan, report_text, write_outputs


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--wl-template", required=True)
    ap.add_argument("--img-template", required=True)
    ap.add_argument("--las-dir")
    ap.add_argument("--las", nargs="*", default=[])
    ap.add_argument("--transmittal", required=True, help="número (1348) o ECP_TRANSMITTAL_0000001348")
    ap.add_argument("--service-type")
    ap.add_argument("--run", type=int)
    ap.add_argument("--well"), ap.add_argument("--uwi"), ap.add_argument("--datum", type=float)
    ap.add_argument("--out-dir", default="")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    las = list(a.las)
    if a.las_dir:
        las += sorted(glob.glob(os.path.join(a.las_dir, "*.[lL][aA][sS]")))
    p = Params(a.wl_template, a.img_template, las, a.transmittal, a.service_type, a.run,
               a.well, a.uwi, a.datum, a.out_dir)
    plan = make_plan(p)
    print(report_text(plan))
    if not plan.ok:
        return 1
    if not a.dry_run:
        for k, v in write_outputs(plan, p).items():
            print(f"{k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
