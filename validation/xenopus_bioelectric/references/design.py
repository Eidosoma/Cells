"""Writes XC0's registered reference values and bands (``designs/``) from the frozen inputs.

    python -m validation.xenopus_bioelectric.references.design            # write
    python -m validation.xenopus_bioelectric.references.design --check    # regenerate, compare byte for byte

``xc0_reference_values.json`` holds the 50-digit reference of every row, per claim family.
``xc0_interface_bands.json`` holds the band rule, the floor models, every row's floor and band, the plants
with their margins and the zero-power list. Only the standard library is used (``decimal`` at 60 digits).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import claims_c5, claims_membrane, local_node, plants, symporter
from . import model as M
from .exact import PREC, REPORT_DIGITS, context
from .rows import FLOOR_FACTOR, G_OPS, Rows

HERE = Path(__file__).resolve().parent
DESIGNS = HERE / "designs"
VALUES_FILE = DESIGNS / "xc0_reference_values.json"
BANDS_FILE = DESIGNS / "xc0_interface_bands.json"
REGISTERED = "XC0 references version 1, 19 November 2026; the registration time is the commit named in README.md (before any engine result)"


def build_rows():
    R = Rows()
    report = {"ode_error_estimate": {}, "identity_residual": {}}
    claims_membrane.c0_c1_c2(R)
    claims_membrane.c4(R)
    claims_membrane.c3_c7_relaxation(R, report)
    claims_c5.c5(R, report)
    symporter.c6_c7(R, report)
    local_node.c8(R, report)
    report["max_abs_identity_residual_fmol"] = max(abs(v) for v in report["identity_residual"].values())
    report["identity_residual"] = None
    report["max_ode_error_estimate"] = max(report["ode_error_estimate"].values())
    return R, report


def documents():
    with context():
        R, report = build_rows()
        plant_doc = plants.run_plants(R)
    values = {
        "schema": "xenopus_xc0_reference_values@1", "registered": REGISTERED,
        "digits": REPORT_DIGITS, "working_precision": PREC,
        "inputs": "reference_inputs.json (a byte copy of the frozen declared_inputs.json of 19 November 2026, 13:35 UTC)",
        "families": R.values_json(), "internal_checks": report,
    }
    bands = {
        "schema": "xenopus_xc0_interface_bands@1", "registered": REGISTERED,
        "band_rule": "band = max(tol_abs + tol_rel * |reference|, FLOOR_FACTOR * floor); sign rows are compared only when |aux| > band; kinds: abs, sign, exact_zero, flag, info",
        "FLOOR_FACTOR": FLOOR_FACTOR,
        "floor_model": {"name": "input_perturbation_float64", "G": G_OPS, "u": "2**-53",
                        "closed_form": "floor = G u (|q| + sum_j |q(x_j (1+u)) - q(x_j)|) over every real input x_j of the row's function",
                        "root": "floor = G u (|V*| + sum_j |I(V*; x_j (1+u)) - I(V*)| / |dI/dV|)",
                        "default": "rows without a sensitivity analysis (ODE outputs) take G u |q|; C5 steady voltages take the larger of the two cells' root floors"},
        "families": R.bands_json(), "plants": plant_doc["plants"], "zero_power": plant_doc["zero_power"],
        "plant_summary": plant_doc["summary"],
    }
    return values, bands


def dumps(doc):
    return json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=True) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    values, bands = documents()
    DESIGNS.mkdir(exist_ok=True)
    if args.check:
        ok = VALUES_FILE.read_text() == dumps(values) and BANDS_FILE.read_text() == dumps(bands)
        print("regenerates identically" if ok else "MISMATCH")
        return 0 if ok else 1
    VALUES_FILE.write_text(dumps(values))
    BANDS_FILE.write_text(dumps(bands))
    print("wrote", VALUES_FILE.name, BANDS_FILE.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
