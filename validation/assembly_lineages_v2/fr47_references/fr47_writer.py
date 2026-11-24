"""FR-47's reference writer: one JSON file per world, the file the judge reads (SPEC.md section 5).

Usage (the judge's first read runs it on invented inputs, SPEC.md section 5; protocol section 5):

    python fr47_writer.py inputs/invented_shell.json /some/dir/reference_invented_shell.json

The file holds:
- ``world``: the world's inputs, echoed verbatim from its input file (exact decimal strings,
  ``p/q`` fractions, ``ln(x)`` terms), with the physical constants of SPEC.md section 0;
- ``units``: the unit of every count and amount;
- ``pairs``: [{observable, time_s, class, mean, var, mu4}], a ``constant`` with ``value`` instead
  of mean, var and mu4;
- ``stops``: [{time_s, kind, f, removed: {class, ...}, mixing_heat: {class, ...} or null}], with f
  1.0 and mixing_heat null at the replacement (AMENDMENT section 10);
- ``d``: {pairs: [{observable, time_s, value}], stops: [{time_s, removed, mixing_heat}],
  intervals: [{start_s, end_s, heat}]};
- ``gap`` (gated worlds): [{observable, time_s, gap, resolution}], with
  resolution = |gap| / (SD / sqrt(128)) (AMENDMENT section 8);
- ``plants``: [{plant, criterion, observable, time_s (or start_s and end_s), honest, planted,
  distance_in_bounds}]: per (plant, criterion), the compared quantity of largest distance, a
  tie going to the earliest time or stop, then to the first observable in the spec's order
  (AMENDMENT-2026-11-24 section 2);
- ``provenance``: the references' revision (the generating commit: the last commit that touched
  this package's code or inputs), whether the package was clean, the writer's version, and the
  hash seeds of the regeneration check.

Conventions:
- **Floats** are written with ``repr`` (round-trip exact), each rounded once from method 1's
  decimal value. **Times** are the inputs' floats.
- **Integer constants,** such as B@wall's count, are JSON integers.
- **Pairs** are ordered by observable (S@pool, S@lumen, then B@wall, or G@wall, H@wall and
  B@wall), and then by time.
- **Bounds:** a deterministic criterion's distance is |planted - honest| / (1e-5 s_y), with
  CRITERIA's scales s_y. C5's bound is 16 eps (1e4 + S) P_t T. A statistical criterion's distance
  is in units of 6 SD_ref / sqrt(128).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import fr47_exact  # noqa: E402  (this package's own method 1; no engine import)

WRITER_VERSION = "fr47-references-writer 1"
REGENERATION_HASH_SEEDS = ["random (unset)", 0, 1, 4242]  # the declared regeneration check

UNITS = {
    "counts": "molecules in one place: one species in one compartment (the pool, the lumen of "
    "one shell, or the shell's wall); never a concentration, an amount in moles or a "
    "count per shell (SPEC.md section 0)",
    "pairs": "mean and value in molecules, var in molecules^2, mu4 in molecules^4",
    "stops.removed": "mean and value in molecules, var in molecules^2, mu4 in molecules^4",
    "stops.mixing_heat": "mean and value in k_BT, var in (k_BT)^2, mu4 in (k_BT)^4",
    "stops.f": "the withdrawn fraction of the pool, dimensionless (1.0 at the replacement)",
    "d.pairs.value": "molecules",
    "d.stops.removed": "molecules",
    "d.stops.mixing_heat": "k_BT",
    "d.intervals.heat": "k_BT",
    "gap.gap": "molecules",
    "gap.resolution": "dimensionless: |gap| / (SD / sqrt(128)), SD in molecules",
    "plants": "honest and planted in the unit of the named quantity (molecules for counts, "
    "removed and tracer_moiety; k_BT for mixing_heat and heat); distance_in_bounds "
    "dimensionless",
    "times": "s",
    "world": "as declared: volumes in L, area in m^2, permeability in m/s, times in s, rates "
    "per s per molecule or per copy, potentials and barrier shifts in k_BT",
}

CONSTANTS = {
    "N_A_per_mol": "6.02214076e23",
    "c0_mol_per_L": "1",
    "temperature_K": "296.15",
    "note": "the temperature enters nothing: every energy is in k_BT (SPEC.md section 0)",
}


def to_float(x):
    if isinstance(x, Decimal):
        return float(x)
    if isinstance(x, float):
        return x
    raise TypeError(f"not a decimal value: {x!r}")


def _quantity(m):
    """A pair's or stop quantity's class and moments (SPEC.md section 5)."""
    if m["constant"]:
        value = m["value"]
        return {"class": "constant", "value": value if isinstance(value, int) else to_float(value)}
    return {
        "class": "spread",
        "mean": to_float(m["mean"]),
        "var": to_float(m["var"]),
        "mu4": to_float(m["mu4"]),
    }


def _plant_entry(plant, criterion, best):
    out = {"plant": plant, "criterion": criterion, "observable": best["observable"]}
    if "time_s" in best:
        out["time_s"] = to_float(best["time_s"])
    else:
        out["start_s"] = to_float(best["start_s"])
        out["end_s"] = to_float(best["end_s"])
    out["honest"] = to_float(best["honest"])
    out["planted"] = to_float(best["planted"])
    out["distance_in_bounds"] = to_float(best["distance"])
    return out


def build_document(raw, provenance, prec=fr47_exact.DEFAULT_PREC):
    """The reference document for one world's input dictionary."""
    res = fr47_exact.reference(raw, prec=prec)
    world = dict(raw)
    world["constants"] = dict(CONSTANTS)
    doc = {"world": world, "units": dict(UNITS)}
    pairs = []
    constants = {}
    for obs, t, m in res["pairs"]:
        entry = {"observable": obs, "time_s": to_float(t)}
        entry.update(_quantity(m))
        pairs.append(entry)
        if m["constant"]:
            constants[(obs, t)] = m["value"]
    doc["pairs"] = pairs
    d = {"pairs": [], "stops": [], "intervals": []}
    stops = []
    if res["world"]["type"] == "shell_washes":
        for t, kind, f, removed, heat in res["stops"]:
            stops.append(
                {
                    "time_s": to_float(t),
                    "kind": kind,
                    "f": to_float(f),
                    "removed": _quantity(removed),
                    "mixing_heat": None if heat is None else _quantity(heat),
                }
            )
        observables = fr47_exact.SHELL_OBSERVABLES
        for obs in observables:
            for t in res["world"]["obs"]:
                value = constants.get((obs, t))
                if value is None:
                    value = to_float(res["d"]["pairs"][(obs, t)])
                d["pairs"].append({"observable": obs, "time_s": to_float(t), "value": value})
        for t, _kind, _f in res["world"]["stops"]:
            removed, heat = res["d"]["stops"][t]
            d["stops"].append(
                {
                    "time_s": to_float(t),
                    "removed": to_float(removed),
                    "mixing_heat": None if heat is None else to_float(heat),
                }
            )
        for t0, t1, heat in res["intervals"]:
            d["intervals"].append(
                {"start_s": to_float(t0), "end_s": to_float(t1), "heat": to_float(heat)}
            )
    else:
        for obs in fr47_exact.GATE_OBSERVABLES:
            for t in res["world"]["obs"]:
                value = constants.get((obs, t))
                if value is None:
                    value = to_float(res["d"][(obs, t)])
                d["pairs"].append({"observable": obs, "time_s": to_float(t), "value": value})
    doc["stops"] = stops
    doc["d"] = d
    if res["world"]["type"] == "gated_shell":
        doc["gap"] = [
            {
                "observable": obs,
                "time_s": to_float(t),
                "gap": to_float(g),
                "resolution": to_float(r),
            }
            for obs, t, g, r in res["gap"]
        ]
    doc["plants"] = [_plant_entry(p, c, best) for p, c, best in res["plants"]]
    doc["provenance"] = dict(provenance)
    return doc


def dumps(doc):
    """The file's bytes: ``repr`` floats (json's), insertion-ordered keys, a final newline."""
    return (json.dumps(doc, indent=1, ensure_ascii=True, allow_nan=False) + "\n").encode("ascii")


def _git(args):
    return subprocess.run(
        ["git", "-C", HERE] + args, check=True, capture_output=True, text=True
    ).stdout


def package_revision():
    """(revision, clean): the last commit touching this package's code or inputs (everything in
    the package but its generated ``references/``), and whether those paths are clean."""
    spec = [".", ":(exclude)references", ":(exclude)__pycache__"]
    try:
        rev = _git(["log", "-1", "--format=%H", "--"] + spec).strip() or None
        status = _git(["status", "--porcelain", "--untracked-files=all", "--"] + spec)
    except (OSError, subprocess.CalledProcessError):
        return None, False
    return rev, status.strip() == ""


def provenance(*, allow_dirty=False):
    rev, clean = package_revision()
    if not (rev and clean) and not allow_dirty:
        raise SystemExit(
            "refusing to write: the package's code or inputs are not a clean commit "
            "(pass --allow-dirty for a development file)"
        )
    return {
        "references_revision": rev,
        "references_clean": bool(rev and clean),
        "writer_version": WRITER_VERSION,
        "regeneration_hash_seeds": REGENERATION_HASH_SEEDS,
    }


def write(world_path, out_path, *, allow_dirty=False, prov=None, prec=fr47_exact.DEFAULT_PREC):
    with open(world_path, encoding="utf-8") as fh:
        raw = json.load(fh)
    doc = build_document(
        raw, prov if prov is not None else provenance(allow_dirty=allow_dirty), prec=prec
    )
    data = dumps(doc)
    with open(out_path, "wb") as fh:
        fh.write(data)
    return doc


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("world", help="a world's input JSON (see inputs/)")
    ap.add_argument("out", help="the reference JSON to write")
    ap.add_argument(
        "--allow-dirty",
        action="store_true",
        help="write even if the package is not a clean commit (marked in provenance)",
    )
    args = ap.parse_args(argv)
    write(args.world, args.out, allow_dirty=args.allow_dirty)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
