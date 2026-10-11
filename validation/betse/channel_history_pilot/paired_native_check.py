"""D099 native comparison: declared gate fixture, unchanged physical/step checks."""

import copy
import math

from feedback_compare import (
    accumulation_tolerance,
    c,
    ctx,
    io,
    native_points,
    native_saved_state_contract,
    oldcheck,
)


def fixture_reference(original, variant, gates):
    """A normative fixture view, NOT a fabricated native observation or edited capture."""
    c.require(
        len(gates) == 2
        and all(type(g) in (int, float) and math.isfinite(g) and 0 <= g <= 1 for g in gates),
        "Invalid declared fixture",
    )
    result = copy.deepcopy(original)
    row = result["rows"][variant["id"] + "/prescribed_mh_a"]["channel_before"]
    c.require(row is not None, "History fixture requires a present channel")
    size = len(row["m"])
    row["m"], row["h"] = [gates[0]] * size, [gates[1]] * size
    row["derived_m_times_h"] = [gates[0] * gates[1]] * size
    return result


def preparation(r, variant, row, original):
    expected = fixture_reference(original, variant, r["protocol"]["initial_gate"])
    oldcheck.preparation(r, variant, row, expected)


def native_checks(r, output, aggregate):
    expected = {
        ctx.key(v, h) for v in r["protocol"]["variants"] for h in r["protocol"]["native_steps_s"]
    }
    c.require(
        set(aggregate["records"]) == expected and aggregate["native_runs"] == 2 * len(expected),
        "Native trajectory coverage differs",
    )
    original = c.read(ctx.audit.preparation.audit.CAPTURE / "betse.json")
    points, summaries, inactive_final = {}, {}, {}
    total_failed = charge_snapshots = 0
    for variant in r["preparation_registration"]["transport_protocol"]["variants"]:
        for step in r["protocol"]["native_steps_s"]:
            key = ctx.key(variant["id"], step)
            paths = aggregate["records"][key]
            c.require(set(paths) == {"observed", "unobserved"}, "Missing observer counterpart")
            a, b = (io.read_compressed(output / paths[mode]) for mode in ("observed", "unobserved"))
            registration = ctx.loop_registration(r, step)
            for row in (a, b):
                preparation(registration, variant, row, original)
                charge_snapshots += native_saved_state_contract(
                    row, registration["transport_protocol"]["constants"]
                )
            exclude = {"mode", "trace", "fresh_probes"}
            c.require(
                {k: v for k, v in a.items() if k not in exclude}
                == {k: v for k, v in b.items() if k not in exclude}
                and b["trace"] is None
                and b["fresh_probes"] is None,
                "Native observer changed outputs",
            )
            tolerances = registration["transport_protocol"]["tolerances"].copy()
            tolerances["amount_fmol"] = accumulation_tolerance(r, a["steps"])
            ledger = io.Ledger(
                tolerances,
                tolerances["relative"],
                output / "native" / key / "boundary-failures.jsonl",
            )
            summary = oldcheck.observed(registration, variant, a, ledger)
            points[key] = native_points(r, a, variant, ledger)
            summaries[key] = ledger.summary() | {
                "accumulation_atol_fmol": tolerances["amount_fmol"],
                "observed": summary,
            }
            total_failed += ledger.failed
            if variant["id"] != "active_channel":
                if step in inactive_final:
                    c.require(
                        a["final"]["physical"] == inactive_final[step],
                        "Inactive native controls differ physically",
                    )
                else:
                    inactive_final[step] = a["final"]["physical"]
    return {
        "status": "pass" if not total_failed else "fail",
        "failed_comparisons": total_failed,
        "boundary_checks": summaries,
        "points": points,
        "observer_pairs": len(expected),
        "direct_charge_snapshots_checked": charge_snapshots,
    }
