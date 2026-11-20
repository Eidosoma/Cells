"""The comparison mapper of gene regulation's option A (G4): the engine's development runs
(engine_run.py) against G2's code-blind references, read from their interface alone. Development,
not judged: G6 registers the tolerances.

G2's interface is data: validation/gene_regulation/references/interface/*.json at the tag
gr1-references-2026-11-20, read through `git show` (never the references' code). Each engine run is
paired with G2's potential set of the same four symbols, matched by value:
- the two test instances (sets 0 and 1) on G2's full output grids;
- the sixteen corners (sets 2 to 17) on every tenth output (trajectories_edge_sets.json);
- the 32 interior points (sets 18 to 49) at t_end, and A1's also at t_off (endpoints.json).

For each readout both sides hold, its gap is the largest |engine - G2| over the common outputs over
its scale, the largest |G2| over G2's outputs (the sheet's §6). J_bar is compared relative to G2's.
Given runs at two steps, each readout's observed order is log2 of its gap's ratio over log2 of the
steps' ratio, where both gaps stand above rounding.

Run: python -m validation.gene_regulation.compare RUN_DIR [RUN_DIR_2] --out FILE
"""

import argparse
import json
import math
import subprocess
from decimal import Decimal
from pathlib import Path

from validation.gene_regulation import sheet_check as sheet

ROOT = Path(__file__).resolve().parents[2]
TAG = "gr1-references-2026-11-20"
INTERFACE = "validation/gene_regulation/references/interface"
FLOOR = 1e-14  # A gap below this, relative, is rounding: no order is read from it.


def interface(name):
    """One of G2's interface files, from the tag (data only)."""
    text = subprocess.run(
        ["git", "show", f"{TAG}:{INTERFACE}/{name}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return json.loads(text)


def symbols_kJ(potentials):
    """G2's set as four Decimals: three kJ/mol values and E_rc/RT."""
    return tuple(
        Decimal(potentials[k]) for k in ("G_ATP_kJ_mol", "E_pd_kJ_mol", "E_pep_kJ_mol", "E_rc_RT")
    )


def engine_kJ(symbols_RT):
    """An engine run's symbols (RT units, as strings) as G2's four."""
    rt = sheet.RT
    s = {k: Decimal(v) for k, v in symbols_RT.items()}
    return (s["G_ATP"] * rt, s["E_pd"] * rt, s["E_pep"] * rt, s["E_rc"])


def same(a, b):
    return all(
        abs(x - y) <= Decimal("1e-9") * max(Decimal(1), abs(y)) for x, y in zip(a, b, strict=True)
    )


class References:
    """G2's readouts by set index: full or strided trajectories, and interior endpoints."""

    def __init__(self):
        self.sets = {}  # index: (symbols, {world: {"t": [...], "readouts": {...}}} | None)
        self.ends = {}  # index: {world: {readout: value at t_end}}
        for name in ("trajectories_test_instances.json", "trajectories_edge_sets.json"):
            data = interface(name)
            for index, entry in data["sets"].items():
                self.sets[int(index)] = (symbols_kJ(entry["potentials"]), entry["worlds"])
        for entry in interface("endpoints.json")["sets"]:
            self.sets[int(entry["set"])] = (symbols_kJ(entry["potentials"]), None)
            self.ends[int(entry["set"])] = entry["worlds"]

    def find(self, symbols_RT):
        target = engine_kJ(symbols_RT)
        hits = [i for i, (s, _) in self.sets.items() if same(target, s)]
        if len(hits) != 1:
            raise ValueError(f"no single G2 set matches {symbols_RT}: {hits}")
        return hits[0]


def gaps(engine, reference):
    """{readout: gap} over the common outputs (module docstring)."""
    times = {round(t, 6): i for i, t in enumerate(engine["t"])}
    out = {}
    for name, values in reference["readouts"].items():
        mine = engine["readouts"].get(name)
        if mine is None or name.startswith("J_bar"):
            continue
        scale = max(abs(v) for v in values) or 1.0
        worst = 0.0
        for t, v in zip(reference["t"], values, strict=True):
            i = times.get(round(t, 6))
            if i is not None:
                worst = max(worst, abs(mine[i] - v))
        out[name] = worst / scale
    for name, values in reference["readouts"].items():
        if name.startswith("J_bar") and name in engine["readouts"]:
            out[name] = abs(engine["readouts"][name][0] - values[0]) / abs(values[0])
    return out


def endpoint_gaps(engine, ends):
    """{readout: relative gap at t_end} at an interior point, against G2's endpoint."""
    out = {}
    for name, value in ends.items():
        mine = engine["readouts"].get(name)
        if mine is None or not isinstance(value, (int, float)):
            continue
        out[name] = abs(mine[-1] - value) / (abs(value) or 1.0)
    return out


def compare_run(refs, path):
    engine = json.loads(path.read_text())
    index = refs.find(engine["symbols_RT"])
    _, worlds = refs.sets[index]
    if worlds is not None:
        found = gaps(engine, worlds[engine["world"]])
        kind = "trajectory" if index in (0, 1) else "every tenth output"
    else:
        found = endpoint_gaps(engine, refs.ends[index][engine["world"]])
        kind = "t_end"
    worst = sorted(found.items(), key=lambda kv: -kv[1])
    heats = {k: v for k, v in found.items() if k.startswith("H_") or k == "G_minus_G0"}
    return dict(
        world=engine["world"],
        set=engine["set"],
        g2_set=index,
        dt_s=engine["dt_s"],
        compared=kind,
        readouts=len(found),
        largest=worst[:5],
        heats=heats,
        checks=engine["checks"],
        gaps=found,
    )


def orders(fine, coarse, ratio):
    """{readout: observed order} where both gaps stand above FLOOR."""
    out = {}
    for name, g in fine["gaps"].items():
        c = coarse["gaps"].get(name)
        if c is not None and g > FLOOR and c > FLOOR:
            out[name] = math.log(c / g) / math.log(ratio)
    return out


def runs(directory):
    return sorted(p for p in Path(directory).glob("*/*.json"))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("run", help="an engine_run.py output directory")
    parser.add_argument("coarse", nargs="?", help="the same runs at another step, for the order")
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    refs = References()
    results = [compare_run(refs, p) for p in runs(args.run)]
    report = dict(
        kind="cells.gene_regulation.compare@1",
        references=f"{TAG}:{INTERFACE}",
        runs=args.run,
        results=results,
    )
    if args.coarse:
        coarse = {(r["world"], r["set"]): r for r in map(lambda p: compare_run(refs, p),
                                                         runs(args.coarse))}  # fmt: skip
        for r in results:
            other = coarse.get((r["world"], r["set"]))
            if other is not None:
                ratio = other["dt_s"] / r["dt_s"]
                r["coarse_dt_s"] = other["dt_s"]
                r["orders"] = orders(r, other, ratio)
    Path(args.out).write_text(json.dumps(report, indent=1) + "\n")
    for r in results:
        line = ", ".join(f"{k} {v:.2e}" for k, v in r["largest"][:3])
        print(f"{r['set'][:24]:24s} {r['world']:12s} dt {r['dt_s']}: {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
