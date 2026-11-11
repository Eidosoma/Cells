"""stationary_continuation_analysis@1 before and after the volume extension, on @1-@3.

The analysis gained volume coordinates and closed-water laws for
resolved_pump_water@1. This driver loads the module as committed at a given
revision (git show REV:src/cells/analysis/stationary.py) next to the current
one and checks, on resolved_pump_tissue@1 (default-world cell), @3 (heredity
H and D cells) and @3 (seven-cell gated sheet), that every existing identity is
unchanged: the same blocks and units, the same laws and law matrix, bitwise
equal residuals and Jacobians at the base state for both formulations, and
bitwise equal Newton solutions and stability spectra for the cells.

Writes result.json (verdict and per-world records) or failure.json.
Usage: python -m validation.stationary.volume_regression --revision REV --output DIR
"""

import argparse
import importlib.util
import json
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

import jax

jax.config.update("jax_enable_x64", True)

import numpy as np  # noqa: E402

from cells.analysis import stationary as current  # noqa: E402
from cells.core.specs import parse_spec  # noqa: E402
from validation.stationary import worlds  # noqa: E402
from validation.tissue import pump_water_fixtures as fixtures  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
ARS = "imex_ars222_face_electromigration@1"


def committed(revision):
    source = subprocess.run(
        ["git", "-C", str(ROOT), "show", f"{revision}:src/cells/analysis/stationary.py"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    path = Path(tempfile.mkdtemp()) / "stationary_committed.py"
    path.write_text(source)
    spec = importlib.util.spec_from_file_location("stationary_committed", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def equal(a, b):
    return bool(np.array_equal(np.asarray(a), np.asarray(b), equal_nan=True))


def compare(spec, old, solve):
    record = {}
    for mode, formulation in (("slow", "rhs"), ("slow", "step_map"), ("fast", "rhs")):
        a, b = (
            old.problem(spec, mode=mode, formulation=formulation),
            current.problem(spec, mode=mode, formulation=formulation),
        )
        key = f"{mode}-{formulation}"
        blocks = [
            (x.field, x.kind, equal(x.flat, y.flat), equal(x.unit, y.unit), x.labels == y.labels)
            for x, y in zip(a.blocks, b.blocks, strict=True)
        ]
        ra, rb = a.reduction(), b.reduction()
        ea, eb = a.evaluate(a.anchor), b.evaluate(b.anchor)
        record[key] = dict(
            blocks_equal=len(a.blocks) == len(b.blocks) and all(all(v[2:]) for v in blocks),
            laws_equal=ra.laws == rb.laws and equal(ra.matrix, rb.matrix),
            evaluation_bitwise=all(equal(x, y) for x, y in zip(ea[:4], eb[:4], strict=True)),
        )
        if solve and formulation == "rhs":
            sa, sb = old.newton(a, a.anchor), current.newton(b, b.anchor)
            record[key]["newton_bitwise"] = equal(sa.u, sb.u) and sa.converged == sb.converged
            if sa.converged:
                ka, kb = old.stability(a, sa.u), current.stability(b, sb.u)
                record[key]["stability_bitwise"] = json.dumps(ka) == json.dumps(kb)
    record["unchanged"] = all(
        v for part in record.values() if isinstance(part, dict) for v in part.values()
    )
    return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--revision", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    records = {}
    try:
        old = committed(args.revision)
        from validation.tissue import surface_pump_v3_fixtures as v3

        cases = dict(
            pump_1_default_cell=(parse_spec(worlds.default_world_cell()), True),
            pump_3_cell_H=(parse_spec(fixtures.heredity_cell("H")), True),
            pump_3_cell_D=(parse_spec(fixtures.heredity_cell("D")), True),
            pump_3_sheet7=(parse_spec(fixtures.gated_sheet()), False),
            pump_3_single_patch=(parse_spec(v3.single_patch(solver=ARS)), False),
        )
        for name, (spec, solve) in cases.items():
            records[name] = compare(spec, old, solve)
            (out / "progress.json").write_text(json.dumps(records, indent=2) + "\n")
        result = dict(
            revision=args.revision,
            verdict="pass" if all(r["unchanged"] for r in records.values()) else "fail",
            worlds=records,
        )
        (out / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    except Exception:
        (out / "failure.json").write_text(
            json.dumps(dict(worlds=records, traceback=traceback.format_exc()), indent=2) + "\n"
        )
        raise


if __name__ == "__main__":
    main()
