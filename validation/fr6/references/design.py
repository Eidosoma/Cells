"""Writes FR-6's A5'' registered design and values (``designs/``) from the registered inputs.

    OPENBLAS_NUM_THREADS=1 python -m validation.fr6.references.design            # write
    OPENBLAS_NUM_THREADS=1 python -m validation.fr6.references.design --check    # compare

About 20 s of one CPU. The values are R-cell's on the registered world; the design holds the
claims, the floor, each planted control's deviation, the honest stand-in's errors and orders on
the ladder, the ceilings and margins, the zero-power cases and the reuse statement.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

from . import a5pp, worlds

HERE = Path(__file__).resolve().parent
DESIGNS = HERE / "designs"
DESIGN_FILE = DESIGNS / "fr6_a5pp_design.json"
VALUES_FILE = DESIGNS / "fr6_a5pp_values.json"
MIN_MARGIN = 10.0
NOISE_CEILING = 1e-12
OBS = ("V_V", "amounts_fmol", "s")


def git_blob_id(path) -> str:
    data = Path(path).read_bytes()
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def jsonable(o):
    if isinstance(o, dict):
        return {str(k): jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [jsonable(v) for v in o]
    if isinstance(o, np.ndarray):
        return jsonable(o.tolist())
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    return o


def build() -> tuple:
    inputs = json.loads(worlds.INPUTS.read_text())
    const = inputs["constants"]
    blk = inputs["worlds"]["a5pp_prior"]
    ref = a5pp.reference(blk, const)
    fl = a5pp.floor(blk, const)
    ctrl = a5pp.controls(blk, const, ref)
    ladder = []
    for dt in inputs["dt_ladder_s"]:
        s = a5pp.stand_in(blk, dt, const)
        ladder.append({"dt_s": dt, "honest_error": {k: float(np.max(np.abs(s[k] - ref[k])))
                                                    for k in OBS}})
    orders = {k: [float(np.log2(a["honest_error"][k] / b["honest_error"][k]))
                  for a, b in zip(ladder, ladder[1:], strict=False)] for k in OBS}
    margins = {}
    for name, dev in ctrl.items():
        margins[name] = {k: [dev[k] / r["honest_error"][k] for r in ladder] for k in OBS}
    caught = {name: {k: [m >= MIN_MARGIN for m in ms] for k, ms in row.items()}
              for name, row in margins.items()}
    values = {"kind": "fr6-a5pp values@1", "registered": worlds.REGISTERED,
              "world": "a5pp_prior", **jsonable(ref)}
    design = {
        "kind": "fr6-a5pp design@1", "registered": worlds.REGISTERED,
        "status": "registered before any engine output; the references are code-blind",
        "inputs": {"path": "validation/fr6/references/reference_inputs.json",
                   "written_by": "validation/fr6/references/worlds.py",
                   "git_blob": git_blob_id(worlds.INPUTS)},
        "reuse": REUSE,
        "claims": CLAIMS,
        "floor": jsonable(fl),
        "controls": jsonable(ctrl),
        "ladder_stand_in": {"per_dt": ladder, "observed_order": orders},
        "margins_over_honest": jsonable(margins),
        "caught_at_margin_10": jsonable(caught),
        "min_margin": MIN_MARGIN,
        "zero_power": ZERO_POWER,
        "not_covered": NOT_COVERED,
    }
    return jsonable(design), values


REUSE = {
    "validation/coupling/cells_reference.py (R-cell)": "unchanged: World, Cell, Patch, "
    "Population, Regulator, State, Input, Coupling, simulate (Radau, rtol 1e-10), floor and the "
    "model's right-hand side for the stand-in",
    "validation/coupling/state_reference.py (R-state)": "unchanged: Turnover, D150's regulator in "
    "closed form",
    "validation/coupling/piecewise_ode.py": "unchanged, through simulate",
    "new": "the registered world, the controls that tell the two cells apart, the second-order "
           "stand-in, the design and values",
}

CLAIMS = {
    "A5''": "the engine's V and amounts in both cells against R-cell with the state integrated "
            "alongside, at second order on the ladder 1, 0.5, 0.25 and 0.125 ms, where the error "
            "stands at least 100 times above the reference's floor",
    "the per-cell prior": "the two cells are told apart: a swapped, shared or ignored s0 departs "
                          "by 2.9 to 6.1 mV, far above any honest error on the ladder",
    "the state, not the instantaneous form": "A5's instantaneous Hill form in place of the state "
                                             "departs by 5.4 mV",
    "tolerance_basis": "the protocol pins its tolerance from its dt study; a control has power at "
                       "a dt where its deviation is at least 10 times the honest second-order "
                       "stand-in's error there (margins_over_honest)",
}

ZERO_POWER = [
    {"control": "a state reading the other cell's regulator",
     "why": "both cells receive the same dose (the lead's ruling), so X is equal in both",
     "remedy": "not shown; a dose that differs between the cells would give it power"},
    {"control": "the basal level scaled by 1 + 1e-3, in V at 1 and 0.5 ms",
     "why": "it departs by 1.0e-6 V, 2 and 6 times the honest stand-in's error there; in the "
            "amounts it is caught at every rung (margin 24 at 1 ms)",
     "remedy": "the protocol picks its delta from its development run, as the coupling protocol "
               "did"},
]

NOT_COVERED = [
    "A5', a gated channel population under a factor: later, if a gated target is needed (the "
    "lead's ruling); R-cell holds the opening constant",
    "the routing door (FR-6 item 2): the core pass's seam B1 (D216)",
    "leak and pump targets: not built",
]


def _dump(o) -> str:
    return json.dumps(o, indent=1) + "\n"


def write() -> None:
    worlds.write()
    design, values = build()
    DESIGNS.mkdir(parents=True, exist_ok=True)
    DESIGN_FILE.write_text(_dump(design))
    VALUES_FILE.write_text(_dump(values))


def _same(a, b, path="", rtol=1e-9) -> list:
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a) != set(b):
            return [f"{path}: keys {sorted(set(a) ^ set(b))}"]
        return [m for k in a for m in _same(a[k], b[k], f"{path}/{k}", rtol)]
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [f"{path}: length"]
        return [m for i, (x, y) in enumerate(zip(a, b, strict=True))
                for m in _same(x, y, f"{path}[{i}]", rtol)]
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and \
            not isinstance(a, bool) and not isinstance(b, bool):
        if a == b:
            return []
        if "floor" in path:
            ok = max(abs(a), abs(b)) <= NOISE_CEILING or abs(a - b) <= 0.5 * max(abs(a), abs(b))
        else:
            ok = abs(a - b) <= rtol * max(abs(a), abs(b))
        return [] if ok else [f"{path}: {a!r} != {b!r}"]
    return [] if a == b else [f"{path}: {a!r} != {b!r}"]


def check() -> list:
    out = []
    if json.loads(worlds.INPUTS.read_text()) != json.loads(json.dumps(worlds.build())):
        out.append("inputs: the committed file differs from worlds.build()")
    design, values = build()
    out += _same(json.loads(DESIGN_FILE.read_text()), design, "design", rtol=1e-6)
    out += _same(json.loads(VALUES_FILE.read_text()), values, "values", rtol=1e-8)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    if a.check:
        d = check()
        for x in d[:50]:
            print(x)
        return 1 if d else 0
    write()
    print(DESIGN_FILE)
    print(VALUES_FILE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
