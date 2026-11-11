#!/usr/bin/env python3
"""Verdicts and margins of judged parity comparisons (read-only).

For each judged run (cells_betse_compare.py ``result.json`` with its registered protocol):
the verdict and refusals, every judged item's worst error over its tolerance (per phase,
quantity and ion; ions at the 1e-12 floor left out), the worst item, and, per option of the
protocol's ``discrimination_by_channel`` (or its single primary option), the margins of the
quantities that option discriminates: tolerance / error, effect / tolerance and effect / error.
As parity-rung2-4-20261109-03/margins.py, generalised to several options per protocol.

    python3 validation/betse/parity_margins.py --run NAME RESULT.json PROTOCOL.json ... \\
        --out MARGINS.json
"""

import argparse
import json
import sys
from pathlib import Path

QUANTITY = {"vm_time": "voltage", "vm_ave_time": "voltage", "cc_time": "cell_concentration",
            "cc_env_time": "ecm_concentration"}  # fmt: skip


def ratios(result, protocol):
    label, items = protocol["verdict_class"], []
    for phase, rows in result.get("phases", {}).items():
        for obs, row in rows["observables"].items():
            if not row.get("judged", True) or label not in row.get("classes", {}):
                continue
            cls, q = row["classes"][label], QUANTITY[obs]
            if "by_ion" in cls:
                for ion, r in cls["by_ion"].items():
                    if r["tolerance"] > 1e-12:
                        items.append((f"{phase}/{q}/{ion}", obs, r["worst"], r["tolerance"]))
            else:
                items.append(
                    (f"{phase}/{q}", obs, row["worst_error_in_tolerance_kind"], cls["tolerance"])
                )
    out = {}
    for key, obs, worst, tol in items:
        if key not in out or worst / tol > out[key]["error_over_tolerance"]:
            out[key] = {"observable": obs, "error_over_tolerance": worst / tol,
                        "worst_error": worst, "tolerance": tol}  # fmt: skip
    return out


def _effect(ratio, key):
    phase, q, *ion = key.split("/")
    v = ratio.get(phase, {}).get(q)
    return v if not ion else (v or {}).get(ion[0])


def options(protocol):
    """{option: (effect_over_tolerance, non_discriminating)} of a protocol."""
    if "discrimination_by_channel" in protocol:
        return {
            k: (v["effect_over_tolerance"], set(v["non_discriminating"]))
            for k, v in protocol["discrimination_by_channel"].items()
        }
    ratio = {
        p: v for p, v in protocol.get("discrimination_ratio", {}).items() if p in ("init", "sim")
    }
    return {protocol.get("discrimination_ratio", {}).get("effect", "primary"): (
        ratio, set(protocol.get("non_discriminating", [])))}  # fmt: skip


def margins(result, protocol):
    r = ratios(result, protocol)
    worst = max(r, key=lambda k: r[k]["error_over_tolerance"])
    by_option = {}
    for name, (effect, nd) in options(protocol).items():
        rows = {}
        for k, v in r.items():
            e = _effect(effect, k) or 0.0
            if k in nd or e <= 1:
                continue
            err, tol = v["worst_error"], v["tolerance"]
            rows[k] = {
                "error_over_tolerance": v["error_over_tolerance"],
                "margin_tolerance_over_error": tol / err if err else None,
                "effect_over_tolerance": e,
                "effect_over_error": e * tol / err if err else None,
            }
        by_option[name] = rows
    return {
        "verdict": result["verdict"],
        "refusals": result.get("refusals"),
        "verdict_class": protocol["verdict_class"],
        "worst": {"item": worst, **r[worst]},
        "error_over_tolerance": r,
        "discriminating_margins": by_option,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--run", nargs=3, action="append", required=True,
                        metavar=("NAME", "RESULT", "PROTOCOL"))  # fmt: skip
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    report = {}
    for name, result, protocol in args.run:
        path = Path(result)
        if not path.is_file():
            report[name] = {"verdict": "no comparison", "result": str(path)}
            continue
        report[name] = margins(json.loads(path.read_text()), json.loads(Path(protocol).read_text()))
    Path(args.out).write_text(json.dumps(report, indent=1) + "\n")
    print(
        json.dumps(
            {k: {"verdict": v["verdict"], "worst": v.get("worst")} for k, v in report.items()},
            indent=1,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
