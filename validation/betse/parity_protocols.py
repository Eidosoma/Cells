#!/usr/bin/env python3
"""Assemble a proposed parity protocol from its derived tolerances (parity tooling).

As the P4 and P4b protocols were built (parity-rung2-4-20261109-02/protocols,
parity-p4b-channels-20261110-01/derive-0*): the schema of a registered template protocol,
the tolerance class and derivation record of a protocol_tolerances.py output, one primary
option in ``discrimination_ratio`` / ``non_discriminating`` and every option in
``discrimination`` (an option's own effect, max over samples and phase end, over this
protocol's tolerance), per channel under ``discrimination_by_channel``, the gate lag of the
emulator check run (active channels only), the covered Vm range of the BETSE case and the
case's own prose (purpose, limits, notes, optional world change). Read-only on its inputs.

Case file (JSON): {"id", "betse_case", "template", "derived", "purpose", "primary",
  "options": {NAME: {"file": BETSE_PAIR_TERMS_JSON} | {"file": BUDGET, "pair": NAME}},
  "laws": {CHANNEL: LAW_ID}, "gate_lag_run": RUN_JSON | null, "coverage_case": CASE | null,
  "cells_run": {...} (merged into the template's), "derivation": {...} (merged into
  tolerance_derivation), "world_change": {...} | null, "limits": [TEXT], "notes": [TEXT],
  "status": TEXT}. An option NAME is "CHANNEL_given_rest (BETSE)"; "{coverage}" in a limit is
  replaced by the covered range.

    python3 validation/betse/parity_protocols.py --case-file CASE.json --out PROTOCOL.json
"""

import argparse
import copy
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
NON_DISCRIMINATING_RULE = (
    "Quantities listed here (ratio <= 1; per channel under discrimination_by_channel) are "
    "still judged, but that channel's effect does not exceed their tolerance, so no claim "
    "about that channel may rest on them."
)
RATIO_DEFINITION = (
    "the option's own effect (plain BETSE with the channel against the same case without it; "
    "max over samples and phase end, interior ECM) divided by this protocol's tolerance, per "
    "phase and quantity (ion); ions at the 1e-12 floor (immobile P) are left out"
)


def effect(spec):
    data = json.loads(Path(spec["file"]).read_text())
    phases = data["pairs"][spec["pair"]]["phases"] if "pair" in spec else data["phases"]
    return {p: pt.rows_terms(phases[p]["observables"]) for p in PHASES}


def discrimination(tolerance, value):
    out = {}
    for p in PHASES:
        out[p] = {"voltage": value[p]["voltage"] / tolerance["voltage"][p]}
        for q in ("cell_concentration", "ecm_concentration"):
            tol = tolerance[q][p]["by_ion"]
            out[p][q] = {i: value[p][q][i] / tol[i] for i in tol if tol[i] > 1e-12}
    return out


def non_discriminating(ratio):
    out = []
    for p in PHASES:
        if ratio[p]["voltage"] <= 1:
            out.append(f"{p}/voltage")
        for q in ("cell_concentration", "ecm_concentration"):
            out += [f"{p}/{q}/{i}" for i, v in ratio[p][q].items() if v <= 1]
    return out


def gate_lag(run_json):
    """Gate ranges and lag of the active gated channels per phase (network emulator run)."""
    run = json.loads(Path(run_json).read_text())
    keys = ("active", "m_range", "h_range", "open_fraction_range", "gate_lag_max_abs",
            "open_fraction_lag_max_rel")  # fmt: skip
    return {
        "source": str(run_json),
        "definition": "per phase and active gated channel: gate and open-fraction ranges over "
        "every update and membrane, the largest |gate - gate_inf(Vm)| and the largest "
        "|P - P_inf| / max P_inf (network_world_adapter.gate_lag); a small lag means that phase "
        "tests the steady law, not the time constants",
        "phases": {
            phase: {
                c["name"]: {k: c[k] for k in keys if k in c}
                for c in record["channels"]
                if "gate_lag_max_abs" in c and c["active"]
            }
            for phase, record in run["phases"].items()
        },
    }


def coverage(case):
    """BETSE Vm range [low, high] per phase (mV) over samples, membranes and the phase end;
    INIT includes its 0 V start (BETSE's first sample follows two updates)."""
    import numpy as np

    out = {}
    for phase in PHASES:
        d = Path(case) / "extract"
        h, f = np.load(d / f"{phase}_history.npz"), np.load(d / f"{phase}_final.npz")
        v = np.concatenate([h["vm_time"].ravel(), f["vm"].ravel()]) * 1e3
        lo, hi = float(v.min()), float(v.max())
        out[phase] = [min(lo, 0.0), max(hi, 0.0)] if phase == "init" else [lo, hi]
    return out


def coverage_text(ranges):
    (a, b), (c, e) = ranges["init"], ranges["sim"]
    return f"INIT {a:.1f} to {b:.1f} mV (from 0 V), SIM {c:.1f} to {e:.1f} mV"


def build(case):
    d = json.loads(Path(case["derived"]).read_text())
    if d["provisional_terms"]:
        raise ValueError(f"{case['id']}: provisional terms {d['provisional_terms']}")
    proto = copy.deepcopy(json.loads(Path(case["template"]).read_text()))
    label = proto["verdict_class"]
    proto["id"] = case["id"]
    proto["purpose"] = case["purpose"]
    proto["betse_case"] = case["betse_case"]
    if case.get("world_change"):
        proto["world_change"] = case["world_change"]
    proto["tolerance_classes"] = {label: d["tolerance"]}
    proto["tolerance_derivation"] = {
        "method": d["method"],
        "tool": "validation/betse/protocol_tolerances.py",
        "recipe": d["recipe_path"],
        "inputs": str(case["derived"]),
        "terms": sorted(d["terms"]),
        "provisional_terms": [],
        "largest_term": d["largest_term"],
        "sums_before_margin": d["sums_before_margin"],
    }
    if "step_order_rule" in d["recipe"]:
        proto["tolerance_derivation"]["step_order_rule"] = d["recipe"]["step_order_rule"]
    for key, value in case.get("derivation", {}).items():
        current = proto["tolerance_derivation"].get(key)
        proto["tolerance_derivation"][key] = (
            current | value if isinstance(current, dict) and isinstance(value, dict) else value
        )
    proto["discrimination"] = {
        n: {"option_term": s, "effect_over_tolerance": discrimination(d["tolerance"], effect(s))}
        for n, s in case["options"].items()
    }
    ratio = proto["discrimination"][case["primary"]]["effect_over_tolerance"]
    proto["discrimination_ratio"] = {
        "effect": case["primary"],
        "definition": RATIO_DEFINITION,
        **ratio,
    }
    proto["non_discriminating"] = non_discriminating(ratio)
    proto["discrimination_by_channel"] = {
        n.split("_given")[0]: {
            "law": case["laws"][n.split("_given")[0]],
            "effect_over_tolerance": v["effect_over_tolerance"],
            "non_discriminating": non_discriminating(v["effect_over_tolerance"]),
        }
        for n, v in proto["discrimination"].items()
    }
    proto["non_discriminating_rule"] = NON_DISCRIMINATING_RULE
    if case.get("gate_lag_run"):
        proto["gate_lag"] = gate_lag(case["gate_lag_run"])
    text = ""
    if case.get("coverage_case"):
        ranges = coverage(case["coverage_case"])
        proto["voltage_coverage_mV"] = ranges
        text = coverage_text(ranges)
    proto["cells_run"] = proto["cells_run"] | case.get("cells_run", {})
    proto["limits"] = [line.replace("{coverage}", text) for line in case.get("limits", [])]
    proto["status"] = case["status"]
    proto["notes"] = case.get("notes", proto.get("notes", []))
    return proto


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--case-file", required=True)
    parser.add_argument("--out", required=True, help="fresh protocol JSON")
    args = parser.parse_args(argv)
    out = Path(args.out)
    if out.exists():
        raise SystemExit(f"Refusing existing output: {out}")
    proto = build(json.loads(Path(args.case_file).read_text()))
    out.write_text(json.dumps(proto, indent=2) + "\n")
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
