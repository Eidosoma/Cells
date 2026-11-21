"""The comparison mapper of gene regulation's option A (G4): the engine's development runs
(engine_run.py) against G2's code-blind references, read from their interface alone. Development,
not judged: G6 registers the tolerances.

G2's interface is data: validation/gene_regulation/references/interface/*.json, as tagged
gr1-references-2026-11-20 and landed in the tree, read as files (never the references' code). Each
engine run is paired with G2's potential set of the same four symbols, matched by value:
- the two test instances (sets 0 and 1) on G2's full output grids;
- the sixteen corners (sets 2 to 17) on every tenth output (trajectories_edge_sets.json);
- the 32 interior points (sets 18 to 49) at t_end, and A1's also at t_off (endpoints.json).

**What is compared, and what refuses** (the review's finding 3: a missing comparison read as
perfect agreement).
- **Samples are matched by G2's required times,** never by whatever outputs both sides happen to
  hold:
  - a trajectory's: every output time of G2's grid for the world (full, or every tenth);
  - an interior point's: the world's t_end, and for A1 the input switch t_off too, each from G2's
    inputs.json.
- **Every required time must be an engine output,** and every G2 readout must be in the run, except
  those not_exported() declares (each move's ΔG and A1's u). Every engine value compared must be
  finite. Otherwise the comparison is refused (ComparisonError). So zero matches, a missing required
  time, a missing readout, a non-finite value and a comparison left with no readout (every required
  row compares at least one) are each an error, never a gap of 0.
- **A partial comparison is declared:**
  - in time (until, or --partial for a run directory): only the required times up to the run's last
    output are required, and J_bar is left out;
  - in readouts (readouts, or --readouts): only the named readouts are required and compared.

  The report says so.
- **Each required time has one engine row** (D265, finding 3), matched within 1e-9 s, never by a
  rounded key. Several rows at one required time, a join's duplicate endpoint, are collapsed only
  where every compared value agrees exactly; otherwise the comparison is refused.
- **Each result reports** its expected and matched times, which are equal whenever it is given,
  and its duplicate rows.

For each readout, its gap is the largest |engine - G2| over the required times over its scale, the
largest |G2| over G2's outputs (the sheet's §6). At an interior point each required row is compared
relative to G2's value, the switch row's readouts named "<readout> at t_off". J_bar is compared
relative to G2's. Given runs at two steps, each readout's observed order is log2 of its gap's ratio
over log2 of the steps' ratio, where both gaps stand above rounding.

Run: python -m validation.gene_regulation.compare RUN_DIR [RUN_DIR_2] --out FILE [--partial]
"""

import argparse
import json
import math
from decimal import Decimal
from pathlib import Path

from validation.gene_regulation import sheet_check as sheet

ROOT = Path(__file__).resolve().parents[2]
TAG = "gr1-references-2026-11-20"
INTERFACE = "validation/gene_regulation/references/interface"
FLOOR = 1e-14  # A gap below this, relative, is rounding: no order is read from it.
TIME_DIGITS = 6  # The partial cut's allowance, 1e-6 s.
TIME_TOLERANCE_S = 1e-9  # A required time and an engine row match within it (no rounded key).


class ComparisonError(ValueError):
    """A comparison that cannot be made as required: a refusal, never a gap."""


def not_exported(name):
    """G2's readouts the engine's runs do not export: each move's ΔG (dG_*) and A1's u."""
    return name == "u" or name.startswith("dG_")


def _matched(engine_times, required, what):
    """{required time: [every engine row within TIME_TOLERANCE_S of it]}, or ComparisonError naming
    the missing times. _unique then makes each one row (D265, finding 3)."""
    if not required:
        raise ComparisonError(f"{what}: no required time to compare")
    times = [float(x) for x in engine_times]
    hits = {t: [i for i, e in enumerate(times) if abs(e - float(t)) <= TIME_TOLERANCE_S]
            for t in required}  # fmt: skip
    missing = [t for t in required if not hits[t]]
    if missing:
        raise ComparisonError(
            f"{what}: {len(missing)} of {len(required)} required times are not outputs of the "
            f"run (the first {missing[:3]}); declare a partial comparison if that is intended"
        )
    return hits


def _unique(engine, hits, names, what):
    """{required time: its one engine row}: several rows at one required time (a join's duplicate
    endpoint) collapse only where every compared value agrees exactly; otherwise ComparisonError
    (D265, finding 3: a second, agreeing row hid a doubled one)."""
    out = {}
    for t, rows in hits.items():
        for name in names:
            if len(rows) > 1 and not name.startswith("J_bar"):
                found = [engine["readouts"][name][i] for i in rows]
                if any(v != found[0] for v in found[1:]):
                    raise ComparisonError(
                        f"{what}: {len(rows)} rows at the required time {t} s disagree in {name} "
                        f"({found[:3]}): no unique row to compare"
                    )
        out[t] = rows[0]
    return out


def _readouts(engine, names, what):
    absent = [n for n in names if n not in engine["readouts"]]
    if absent:
        raise ComparisonError(
            f"{what}: G2's readouts {absent[:5]} are not in the run; name the readouts compared "
            "if that is intended"
        )


def _selected(available, readouts, what):
    """G2's readouts to compare: every one but the not-exported, or the declared ones, each of which
    G2 must hold."""
    if readouts is None:
        return [n for n in available if not not_exported(n)]
    unknown = [n for n in readouts if n not in available]
    if unknown:
        raise ComparisonError(f"{what}: G2 holds no readout {unknown[:5]}")
    return list(readouts)


def _some(names, what):
    """Refuse a comparison left with no readout (a declared subset that a partial comparison then
    empties, or an empty declaration): it would report agreement over nothing."""
    if not names:
        raise ComparisonError(f"{what}: no readout left to compare")
    return names


def _finite(value, name, what):
    if not math.isfinite(value):
        raise ComparisonError(f"{what}: the run's {name} is {value!r}")
    return value


def interface(name):
    """One of G2's interface files, from the tree (data only)."""
    return json.loads((ROOT / INTERFACE / name).read_text())


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
        self.horizon, self.switch = {}, {}  # world: t_end; world: t_off (A1's input switch)
        for w in interface("inputs.json")["worlds"]:
            self.horizon[w["name"]] = float(w["t_end"])
            starts = [float(phase[0]) for phase in w["phases"][1:]]
            if starts:
                self.switch[w["name"]] = starts[0]

    def endpoints(self, world):
        """[(label, required time, G2's readouts there), ...] of a world at an interior point,
        from the endpoint file's entries for it: "<world>" at t_end, "<world> at t_off" at the
        switch."""
        rows = [("t_end", self.horizon[world], world)]
        if f"{world} at t_off" in next(iter(self.ends.values())):
            rows.append(("t_off", self.switch[world], f"{world} at t_off"))
        return rows

    def find(self, symbols_RT):
        target = engine_kJ(symbols_RT)
        hits = [i for i, (s, _) in self.sets.items() if same(target, s)]
        if len(hits) != 1:
            raise ValueError(f"no single G2 set matches {symbols_RT}: {hits}")
        return hits[0]


def gaps(engine, reference, *, until=None, readouts=None):
    """A trajectory comparison (module docstring): {gaps: {readout: gap}, expected_times,
    matched_times, partial, until, not_compared}. until declares a partial comparison in time: only
    G2's times up to it are required, and J_bar is left out. readouts declares one in readouts.
    Refused (ComparisonError) where a required time or readout is missing, or a value not finite."""
    partial = until is not None or readouts is not None
    required = [t for t in reference["t"] if until is None or t <= until + 10.0**-TIME_DIGITS]
    rows = _matched(engine["t"], required, "the trajectory")
    names = _selected(reference["readouts"], readouts, "the trajectory")
    skipped = sorted(n for n in reference["readouts"] if n not in names)
    if until is not None:
        skipped = sorted({*skipped, *(n for n in names if n.startswith("J_bar"))})
        names = [n for n in names if not n.startswith("J_bar")]
    _readouts(engine, _some(names, "the trajectory"), "the trajectory")
    hits, rows = rows, _unique(engine, rows, names, "the trajectory")
    out, absolute = {}, {}
    for name in names:
        values, mine = reference["readouts"][name], engine["readouts"][name]
        if name.startswith("J_bar"):
            absolute[name] = abs(_finite(mine[0], name, "the trajectory") - values[0])
            out[name] = absolute[name] / abs(values[0])
            continue
        scale = max(abs(v) for v in values) or 1.0
        pairs = [(t, v) for t, v in zip(reference["t"], values, strict=True) if t in rows]
        absolute[name] = max(
            abs(_finite(mine[rows[t]], name, f"the trajectory at {t}") - v) for t, v in pairs
        )
        out[name] = absolute[name] / scale
    return dict(gaps=out, absolute_gaps=absolute, expected_times=len(required),
                matched_times=len(rows),
                duplicate_rows=sum(len(v) - 1 for v in hits.values()),
                partial=partial, until=until, not_compared=skipped)  # fmt: skip


def endpoint_gaps(engine, refs, index, world, *, until=None, readouts=None):
    """An interior point's comparison (module docstring): each required row of the world, t_end
    and A1's switch, against G2's values there. Refused where a required row or readout is missing,
    or a value not finite; a declared partial comparison requires only the rows up to until, or
    only the named readouts."""
    partial = until is not None or readouts is not None
    rows = [r for r in refs.endpoints(world) if until is None or r[1] <= until + 10.0**-TIME_DIGITS]
    found = _matched(engine["t"], [t for _, t, _ in rows], f"{world}'s interior endpoints")
    out, skipped = {}, set()
    for label, t, key in rows:
        values = refs.ends[index][key]
        what = f"{world}'s row at {label}"
        names = _selected(values, readouts, what)
        skipped |= {n for n in values if n not in names}
        if label != "t_end" or until is not None:
            skipped |= {n for n in names if n.startswith("J_bar")}
            names = [n for n in names if not n.startswith("J_bar")]
        _readouts(engine, _some(names, what), what)
        row = _unique(engine, {t: found[t]}, names, what)[t]
        for name in names:
            mine = engine["readouts"][name]
            value = _finite(mine[0] if name.startswith("J_bar") else mine[row], name, what)
            gap = abs(value - values[name]) / (abs(values[name]) or 1.0)
            out[name if label == "t_end" else f"{name} at {label}"] = gap
    return dict(gaps=out, expected_times=len(rows), matched_times=len(found),
                duplicate_rows=sum(len(v) - 1 for v in found.values()),
                partial=partial, until=until, not_compared=sorted(skipped))  # fmt: skip


def compare_record(refs, engine, *, partial=False, readouts=None):
    """One engine run's record against G2's set of its four symbols (module docstring); partial
    declares a comparison up to the run's last output, readouts one of the named readouts only."""
    index = refs.find(engine["symbols_RT"])
    _, worlds = refs.sets[index]
    until = float(engine["t"][-1]) if partial else None
    if worlds is not None:
        result = gaps(engine, worlds[engine["world"]], until=until, readouts=readouts)
        kind = "trajectory" if index in (0, 1) else "every tenth output"
    else:
        result = endpoint_gaps(engine, refs, index, engine["world"], until=until, readouts=readouts)
        kind = "interior endpoints"
    found = result["gaps"]
    worst = sorted(found.items(), key=lambda kv: -kv[1])
    heats = {k: v for k, v in found.items() if k.startswith("H_") or k.startswith("G_minus_G0")}
    return dict(
        world=engine["world"],
        set=engine["set"],
        g2_set=index,
        dt_s=engine["dt_s"],
        compared=kind,
        partial=result["partial"],
        until=result["until"],
        readouts_declared=None if readouts is None else list(readouts),
        expected_times=result["expected_times"],
        matched_times=result["matched_times"],
        duplicate_rows=result["duplicate_rows"],
        not_compared=result["not_compared"],
        readouts=len(found),
        largest=worst[:5],
        heats=heats,
        checks=engine.get("checks", {}),
        gaps=found,
        absolute_gaps=result.get("absolute_gaps", {}),
    )


def compare_run(refs, path, *, partial=False, readouts=None):
    return compare_record(
        refs, json.loads(Path(path).read_text()), partial=partial, readouts=readouts
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
    parser.add_argument(
        "--partial", action="store_true", help="declare each comparison partial: to its last output"
    )
    parser.add_argument("--readouts", nargs="+", help="declare a comparison of these readouts only")
    args = parser.parse_args(argv)
    refs = References()
    paths = runs(args.run)
    if not paths:
        raise ComparisonError(f"{args.run} holds no run to compare")
    results = [compare_run(refs, p, partial=args.partial, readouts=args.readouts) for p in paths]
    report = dict(
        kind="cells.gene_regulation.compare@2",
        references=f"{TAG}:{INTERFACE}",
        runs=args.run,
        partial=args.partial,
        readouts=args.readouts,
        results=results,
    )
    if args.coarse:
        coarse = {
            (r["world"], r["set"]): r
            for r in (
                compare_run(refs, p, partial=args.partial, readouts=args.readouts)
                for p in runs(args.coarse)
            )
        }
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
