#!/usr/bin/env python3
"""Proposed parity tolerances by the pinned method, from a recipe of measured difference terms.

tolerance(quantity, phase[, ion]) = margin x (sum of the terms), rounded up to one significant
figure; concentrations per ion, a zero sum getting the floor (rung-1 protocol-numbers/derive.py and
attribution-01/derive_v2.py, generalised). Every term is measured before any judged run:

  {"budget": FILE, "pairs": [NAME, ...]}  emulator variant pairs of a difference budget
                                          (default_world_adapter.py difference-budget), max of pairs
  {"step": [FILE, ...]}                   plain BETSE vs plain BETSE (betse_pair_terms.py or
                                          betse-step-term); max over files
  {"max_of": [TERM, ...]}                 elementwise max of other term specs
  {"layouts": [A, B], "scale": S}         two Cells layouts of one case (e.g. 1 ms vs 0.5 ms), x S
  {"field_layouts": [LAYOUT, ...]}        Boltzmann response of Cells' own exterior potential:
                                          ECM |z| F max|phi - <phi>_interior| / RT per mobile ion,
                                          and the same for cell Ca (derive_v2.py reasoning)
  {"x_ext_runs": [RUN.json, ...], "per_volt": TERM_NAME}
                                          X_ext (volts) of blind runs; concentrations per ion scale
                                          with the named term's concentration per volt (precedent)
  {"provisional": FILE, "term": NAME[, "protocol": KEY]}
                                          a term copied from another derivation (top level, or under
                                          KEY as in rung 1's derived_v2.json), marked provisional:
                                          to be measured before registration
  any spec may add "scale": S.

Values are the max over common samples and the phase end; ECM rows exclude the boundary ring.

    python3 validation/betse/protocol_tolerances.py --recipe RECIPE.json --out DERIVED.json
"""

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if __name__ == "__main__":
    for entry in (ROOT / "src", ROOT):
        if str(entry) not in sys.path:
            sys.path.insert(0, str(entry))

from validation.betse import betse_reference_run as reference_run  # noqa: E402
from validation.betse import default_world_adapter as adapter  # noqa: E402

PHASES = ("init", "sim")
QUANTITIES = ("voltage", "cell_concentration", "ecm_concentration")
F = 6.02214076e23 * 1.602176634e-19  # C/mol (CODATA, Cells)
R = 6.02214076e23 * 1.380649e-23  # J/(mol K)


def up1(x):
    """Round up to one significant figure."""
    if x <= 0:
        return 0.0
    e = math.floor(math.log10(x))
    return float(f"{math.ceil(round(x / 10**e, 9)) * 10**e:.1e}")


def rows_terms(rows):
    """{quantity: value | {ion: value}} from one phase's difference rows (samples and end)."""
    volt = max(max(rows[k]["max"], rows[k]["final"]["max"]) for k in ("vm_time", "vm_ave_time"))
    by_ion = {
        q: {i: max(v["max"], v["final_max"]) for i, v in rows[key]["by_ion"].items()}
        for q, key in (
            ("cell_concentration", "cc_time"),
            ("ecm_concentration", "cc_env_time_interior"),
        )
    }
    return {"voltage": volt, **by_ion}


def combine(terms, op=max):
    first = terms[0]
    return {
        p: {
            q: op(t[p][q] for t in terms)
            if q == "voltage"
            else {i: op(t[p][q][i] for t in terms) for i in first[p][q]}
            for q in QUANTITIES
        }
        for p in PHASES
    }


def scaled(term, factor):
    return combine([term], op=lambda values: factor * next(iter(values)))


class Context:
    def __init__(self, case, base):
        self.base = base
        directory, manifest = adapter.load_case(case)
        self.ions = list(manifest["ions"]["order"])
        self.valence = dict(zip(self.ions, manifest["ions"]["valence"], strict=True))
        self.temperature = float(adapter.betse_parameters(manifest, "init")["T"])
        geometry = np.load(directory / "geometry.npz")
        rows, cols = (int(v) for v in geometry["X"].shape)
        k = np.arange(rows * cols)
        self.interior = ~(
            (k // cols == 0) | (k % cols == 0) | (k // cols == rows - 1) | (k % cols == cols - 1)
        )
        final = np.load(directory / "init_final.npz")
        self.mobile_ecm = {
            i for n, i in enumerate(self.ions) if float(np.asarray(final["D_env"])[n].max()) > 0
        }
        self.done = {}

    def path(self, name):
        p = Path(name)
        return p if p.is_absolute() else self.base / p


def layout_terms(ctx, a, b):
    """Cells vs Cells at common samples and the phase end (ring excluded)."""
    result = {}
    manifests = [json.loads((d / "comparison_manifest.json").read_text()) for d in (a, b)]
    for p in PHASES:
        ta, tb = (m["phases"][p]["elapsed_after_update_s"] for m in manifests)
        if len(ta) != len(tb) or not np.allclose(ta, tb, atol=1e-9, rtol=0):
            raise ValueError(f"{p}: layouts sample different times")
        ha, hb = (np.load(d / f"{p}_history.npz") for d in (a, b))
        fa, fb = (np.load(d / f"{p}_final.npz") for d in (a, b))
        volt = max(
            float(np.abs(ha["vm_ave_time"] - hb["vm_ave_time"]).max()),
            float(np.abs(fa["vm_ave"] - fb["vm_ave"]).max()),
        )

        def rel(x, y):
            return np.abs(x - y) / np.abs(y)

        cell = np.maximum(
            rel(ha["cc_time"], hb["cc_time"]).max(axis=(0, 2)),
            rel(fa["cc_cells"], fb["cc_cells"]).max(axis=1),
        )
        env = np.maximum(
            rel(ha["cc_env_time"], hb["cc_env_time"])[:, :, ctx.interior].max(axis=(0, 2)),
            rel(fa["cc_env"], fb["cc_env"])[:, ctx.interior].max(axis=1),
        )
        result[p] = {
            "voltage": volt,
            "cell_concentration": dict(zip(ctx.ions, map(float, cell), strict=True)),
            "ecm_concentration": dict(zip(ctx.ions, map(float, np.nan_to_num(env)), strict=True)),
        }
    return result


def field_terms(ctx, layouts):
    result = {}
    for p in PHASES:
        spread = 0.0
        for layout in layouts:
            phi = np.load(layout / f"{p}_history.npz")["diag_extracellular_potential_time"]
            end = np.load(layout / f"{p}_final.npz")["diag_extracellular_potential"]
            series = np.concatenate([phi, end[None]])[:, ctx.interior]
            spread = max(spread, float(np.abs(series - series.mean(axis=1, keepdims=True)).max()))
        b1 = spread * F / (R * ctx.temperature)
        ecm = {i: abs(ctx.valence[i]) * b1 if i in ctx.mobile_ecm else 0.0 for i in ctx.ions}
        cell = {i: ecm[i] if i == "Ca" else 0.0 for i in ctx.ions}
        result[p] = {"voltage": 0.0, "cell_concentration": cell, "ecm_concentration": ecm}
    return result


def term(ctx, spec):
    if "budget" in spec:
        pairs = json.loads(ctx.path(spec["budget"]).read_text())["pairs"]
        value = combine(
            [
                {p: rows_terms(pairs[n]["phases"][p]["observables"]) for p in PHASES}
                for n in spec["pairs"]
            ]
        )
    elif "step" in spec:
        files = [json.loads(ctx.path(f).read_text())["phases"] for f in spec["step"]]
        value = combine([{p: rows_terms(s[p]["observables"]) for p in PHASES} for s in files])
    elif "max_of" in spec:
        value = combine([term(ctx, s) for s in spec["max_of"]])
    elif "layouts" in spec:
        value = layout_terms(ctx, *(ctx.path(d) for d in spec["layouts"]))
    elif "field_layouts" in spec:
        value = field_terms(ctx, [ctx.path(d) for d in spec["field_layouts"]])
    elif "x_ext_runs" in spec:
        runs = [json.loads(ctx.path(f).read_text()) for f in spec["x_ext_runs"]]
        ref = ctx.done[spec["per_volt"]]
        value = {}
        for p in PHASES:
            x = max(r["phases"][p]["patch_exterior"]["x_ext_V"] for r in runs)
            per_volt = 1.0 / ref[p]["voltage"]
            value[p] = {"voltage": x} | {
                q: {i: x * v * per_volt for i, v in ref[p][q].items()}
                for q in ("cell_concentration", "ecm_concentration")
            }
    elif "provisional" in spec:
        source = json.loads(ctx.path(spec["provisional"]).read_text())
        value = (source[spec["protocol"]] if "protocol" in spec else source)["terms"][spec["term"]]
    else:
        raise ValueError(f"unknown term spec {sorted(spec)}")
    return scaled(value, spec["scale"]) if "scale" in spec else value


def derive(recipe, base):
    ctx = Context(recipe["case"], base)
    margin, floor = float(recipe.get("margin", 3)), float(recipe.get("floor", 1e-12))
    terms = {}
    for name, spec in recipe["terms"].items():
        terms[name] = ctx.done[name] = term(ctx, spec)
    sums, tolerance = {}, {}
    for q in QUANTITIES:
        sums[q], tolerance[q] = {}, {}
        for p in PHASES:
            if q == "voltage":
                s = sum(t[p][q] for t in terms.values())
                sums[q][p], tolerance[q][p] = s, up1(margin * s)
            else:
                s = {i: sum(t[p][q][i] for t in terms.values()) for i in ctx.ions}
                sums[q][p] = s
                tolerance[q][p] = {"by_ion": {i: max(up1(margin * v), floor) for i, v in s.items()}}
    largest = {
        q: {
            p: max(
                terms,
                key=lambda n, q=q, p=p: (
                    terms[n][p][q] if q == "voltage" else max(terms[n][p][q].values())
                ),
            )
            for p in PHASES
        }
        for q in QUANTITIES
    }
    return {
        "kind": "cells.parity_proposed_tolerances@1",
        "method": f"{margin:g} x (sum of measured difference terms), rounded up to one significant "
        f"figure; per ion for concentrations (a zero sum gets the floor {floor:g})",
        "recipe": recipe,
        "provisional_terms": sorted(n for n, s in recipe["terms"].items() if "provisional" in s),
        "terms": terms,
        "largest_term": largest,
        "sums_before_margin": sums,
        "tolerance": tolerance,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--recipe", required=True, help="JSON; relative paths resolve against it")
    parser.add_argument("--out", required=True, help="fresh JSON file")
    args = parser.parse_args(argv)
    path = Path(args.recipe).resolve()
    result = derive(json.loads(path.read_text()), path.parent)
    result["recipe_path"] = str(path)
    result["git"] = reference_run.git_provenance([Path(__file__)])
    out = reference_run.resolve_out(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    reference_run.write_json(out, adapter.compare.json_safe(result))
    print(json.dumps({"out": str(out), "tolerance": result["tolerance"]}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
