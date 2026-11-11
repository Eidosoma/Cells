#!/usr/bin/env python3
"""A registered parity protocol's variant for another Cells backend (e.g. the L4), proposed.

The variant keeps the registered protocol's case, observables, phases, reference, mapping and
tolerance derivation, and adds measured backend terms by the same pinned method: each term is
a Cells-vs-Cells difference of two comparison layouts of the case at the judged settings
(protocol_tolerances.py ``{"layouts": [A, B]}``: max over common samples and the phase end,
interior ECM), e.g. the judged CPU run against a blind L4 run (backend term) and two blind L4
runs (run-to-run term). Per phase, quantity and ion:

  new sum = registered sums_before_margin + the backend terms
  new tolerance = max(registered tolerance, margin x new sum rounded up to one significant
                  figure, floor)

so the variant is never tighter than the registered protocol. Discrimination ratios (effect /
tolerance) are rescaled by registered / new tolerance and the non-discriminating lists
recomputed. ``cells_run.backends`` becomes the named backend only. Read-only on its inputs.

Spec (JSON): {"base": PROTOCOL, "case": BETSE_CASE_DIR (default: the base recipe's case),
  "backend": "gpu (L4)", "id_suffix": "-l4",
  "terms": {NAME: {"layouts": [A, B], "role": TEXT}, ...}, "notes": [TEXT], "status": TEXT}

    python3 validation/betse/backend_variant.py --spec SPEC.json --out VARIANT.json
"""

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if __name__ == "__main__":
    for entry in (ROOT / "src", ROOT):
        if str(entry) not in sys.path:
            sys.path.insert(0, str(entry))

from validation.betse import protocol_tolerances as pt  # noqa: E402

PHASES = pt.PHASES
QUANTITIES = pt.QUANTITIES
RATIO_KEYS = ("discrimination_ratio",)


def _ions(protocol):
    tol = next(iter(protocol["tolerance_classes"].values()))
    return list(tol["cell_concentration"][PHASES[0]]["by_ion"])


def new_tolerance(protocol, added, *, margin=3.0, floor=1e-12):
    """(tolerance, sums, check) of the variant from the registered sums plus ``added`` terms."""
    label = protocol["verdict_class"]
    old = protocol["tolerance_classes"][label]
    sums = protocol["tolerance_derivation"]["sums_before_margin"]
    tol, new_sums, mismatches = {}, {}, []
    for q in QUANTITIES:
        tol[q], new_sums[q] = {}, {}
        for p in PHASES:
            if q == "voltage":
                s = sums[q][p] + sum(t[p][q] for t in added.values())
                if pt.up1(margin * sums[q][p]) != old[q][p]:
                    mismatches.append(f"{p}/{q}")
                new_sums[q][p] = s
                tol[q][p] = max(old[q][p], pt.up1(margin * s))
            else:
                by = {}
                new_sums[q][p] = {}
                for i, base in sums[q][p].items():
                    s = base + sum(t[p][q][i] for t in added.values())
                    if max(pt.up1(margin * base), floor) != old[q][p]["by_ion"][i]:
                        mismatches.append(f"{p}/{q}/{i}")
                    new_sums[q][p][i] = s
                    by[i] = max(old[q][p]["by_ion"][i], pt.up1(margin * s), floor)
                tol[q][p] = {"by_ion": by}
    return tol, new_sums, mismatches


def _rescale(ratio, old, new):
    """effect / tolerance rescaled from the registered to the new tolerance (in place copy)."""
    out = {}
    for p in PHASES:
        if p not in ratio:
            continue
        r = ratio[p]
        out[p] = {"voltage": r["voltage"] * old["voltage"][p] / new["voltage"][p]}
        for q in ("cell_concentration", "ecm_concentration"):
            if q in r:
                out[p][q] = {
                    i: v * old[q][p]["by_ion"][i] / new[q][p]["by_ion"][i] for i, v in r[q].items()
                }
    return out


def non_discriminating(ratio):
    out = []
    for p in PHASES:
        if p not in ratio:
            continue
        if ratio[p]["voltage"] <= 1:
            out.append(f"{p}/voltage")
        for q in ("cell_concentration", "ecm_concentration"):
            out += [f"{p}/{q}/{i}" for i, v in ratio[p].get(q, {}).items() if v <= 1]
    return out


def variant(spec, base_path):
    base_bytes = Path(base_path).read_bytes()
    protocol = json.loads(base_bytes)
    out = copy.deepcopy(protocol)
    case = (
        spec.get("case")
        or json.loads(Path(protocol["tolerance_derivation"]["recipe"]).read_text())["case"]
    )
    ctx = pt.Context(case, Path(base_path).parent)
    added = {name: pt.term(ctx, {"layouts": t["layouts"]}) for name, t in spec["terms"].items()}
    label = protocol["verdict_class"]
    old = protocol["tolerance_classes"][label]
    tol, sums, mismatches = new_tolerance(protocol, added)
    out["id"] = protocol["id"] + spec.get("id_suffix", "-l4")
    out["purpose"] = (
        f"Backend variant of the registered protocol {protocol['id']} for the Cells backend "
        f"{spec['backend']}: same case, observables, phases, mapping and tolerance derivation, "
        "plus measured backend terms (tolerance_derivation.backend_terms). The registered "
        f"purpose follows. {protocol['purpose']}"
    )
    out["tolerance_classes"] = {label: tol}
    td = out["tolerance_derivation"]
    td["sums_before_margin"] = sums
    td["terms"] = sorted(td["terms"] + list(added))
    td["backend_terms"] = {
        "rule": "new sum = registered sums_before_margin + these terms; new tolerance = max("
        "registered tolerance, 3 x new sum rounded up to one significant figure, floor 1e-12)",
        "terms": {
            name: {
                "layouts": spec["terms"][name]["layouts"],
                "role": spec["terms"][name].get("role"),
                "values": value,
            }
            for name, value in added.items()
        },  # fmt: skip
        "registered_tolerance_reproduced_from_sums": not mismatches,
        "not_reproduced": mismatches,
        "changed": sorted(
            f"{p}/{q}" if q == "voltage" else f"{p}/{q}/{i}"
            for q in QUANTITIES
            for p in PHASES
            for i in ([None] if q == "voltage" else tol[q][p]["by_ion"])
            if (tol[q][p] if q == "voltage" else tol[q][p]["by_ion"][i])
            != (old[q][p] if q == "voltage" else old[q][p]["by_ion"][i])
        ),
    }
    out["base_protocol"] = {
        "id": protocol["id"],
        "path": str(Path(base_path)),
        "sha256": hashlib.sha256(base_bytes).hexdigest(),
    }
    run = out.get("cells_run")
    if run is not None:
        run["backends"] = [spec["backend"]]
        run.pop("optional_repeat", None)
    for entry in out.get("discrimination", {}).values():
        if "effect_over_tolerance" in entry:
            entry["effect_over_tolerance"] = _rescale(entry["effect_over_tolerance"], old, tol)
    if "discrimination_ratio" in out:
        dr = out["discrimination_ratio"]
        scaled = _rescale(dr, old, tol)
        dr.update(scaled)
        out["non_discriminating"] = non_discriminating(scaled)
    for entry in out.get("discrimination_by_channel", {}).values():
        entry["effect_over_tolerance"] = _rescale(entry["effect_over_tolerance"], old, tol)
        entry["non_discriminating"] = non_discriminating(entry["effect_over_tolerance"])
    if "non_discriminating_causes" in out:
        kept = set(out["non_discriminating"])
        causes = out["non_discriminating_causes"]
        out["non_discriminating_causes"] = {k: v for k, v in causes.items() if k in kept}
    out["notes"] = list(out.get("notes", [])) + list(spec.get("notes", []))
    out["status"] = spec.get("status", "PROPOSED backend variant, not registered.")
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--spec", required=True)
    parser.add_argument("--out", required=True, help="fresh protocol JSON")
    args = parser.parse_args(argv)
    out = Path(args.out)
    if out.exists():
        raise SystemExit(f"Refusing existing output: {out}")
    spec = json.loads(Path(args.spec).read_text())
    result = variant(spec, spec["base"])
    out.write_text(json.dumps(result, indent=2) + "\n")
    bt = result["tolerance_derivation"]["backend_terms"]
    print(json.dumps({"out": str(out), "changed": bt["changed"],
                      "reproduced": bt["registered_tolerance_reproduced_from_sums"]}))  # fmt: skip
    return 0


if __name__ == "__main__":
    sys.exit(main())
