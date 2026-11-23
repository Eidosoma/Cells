"""Check FR-38's gross survival bound and its agreement with the booked net counts (erratum F)."""

import argparse
import json
import math
from bisect import bisect_left
from decimal import Decimal, localcontext
from pathlib import Path
from tempfile import TemporaryDirectory

from validation.gene_regulation import cohort, engine_run, release_check, worlds

# The R1/R2 sheet holds the durable half-life at 2 h and the short half-life at 0.5 h.
HOUR_S = 3600
EXPECTED = {"durable": math.sqrt(0.5), "short_lived": 0.25}


def compare(path, name, fate):
    row = release_check.FATE_ROWS[fate]
    times, amounts, made, lost = cohort.read(path, row)
    gross_rate = release_check.gross_rate(json.loads(path.read_text()), row)
    counts = cohort.known_survival(times, made, gross_rate, 0, HOUR_S, 2 * HOUR_S)
    net = cohort.survival(times, amounts, made, lost, 0, HOUR_S, 2 * HOUR_S)
    close, later = counts["alive_at_window_end"], counts["alive_at_sample"]
    e_close, e_later = counts["grid_error_at_window_end"], counts["grid_error_at_sample"]
    rate = EXPECTED[fate]
    residual = abs(later - rate * close)
    allowance = None
    intervals = ratio_rounding = ratio_bound = None
    ratio_ok = net_ok = None
    endpoints = ("window_end", "sample")
    errors = [read[f"grid_error_at_{end}"] for read in (counts, net) for end in endpoints]
    if close == 0:
        assert counts["ratio"] is None
        reference = "empty cohort"
    elif any(error is None or not math.isfinite(error) for error in errors):
        reference = "insufficient resolution"
    else:
        allowance = e_later + rate * e_close
        assert math.isfinite(allowance)
        intervals = bisect_left(times, HOUR_S) - bisect_left(times, 0)
        ratio_rounding = (2 * intervals + 8) * math.ulp(1.0) * rate
        ratio_bound = allowance / close + ratio_rounding
        ratio_ok = abs(counts["ratio"] - rate) <= ratio_bound
        net_ok = all(
            abs(counts[f"alive_at_{end}"] - net[f"alive_at_{end}"]) <=
            counts[f"grid_error_at_{end}"] + net[f"grid_error_at_{end}"] +
            release_check.SURVIVORS * counts[f"alive_at_{end}"]
            for end in endpoints
        )
        reference = "pass" if ratio_ok and net_ok else "fail"

    checks = release_check.Checks()
    reported_bound = None
    agrees = False
    try:
        release_check.survival(checks, name, path, row, fate)
    except ZeroDivisionError:
        reported = "division by zero"
    else:
        (result,) = checks.rows
        reported = result.get("status", "compared")
        if reported == "compared":
            reported = "pass" if result["ok"] else "fail"
        bound = result.get("bound")
        if bound is not None:
            reported_bound = bound if math.isfinite(bound) else "nonfinite"
        correct_bound = (
            bound is None
            if ratio_bound is None
            else (bound is not None and math.isclose(bound, ratio_bound, rel_tol=1e-14))
        )
        agrees = (reported == reference and result["ok"] == (reference == "pass")
                  and result.get("net_agrees") == net_ok and correct_bound)
    return dict(
        fate=fate,
        expected_ratio=rate,
        **counts,
        net_counts=net,
        gross_ratio_passes=ratio_ok,
        net_agrees=net_ok,
        count_residual_fmol=residual,
        count_allowance_fmol=allowance,
        window_intervals=intervals,
        ratio_rounding=ratio_rounding,
        reference_ratio_bound=ratio_bound,
        reference=reference,
        checker=reported,
        checker_ratio_bound=reported_bound,
        agrees=agrees,
    )


def controls(directory):
    per_copy = release_check.COPY_FMOL
    path = directory / "counters.json"
    cases = {}
    for name, step, expected in (
        ("sparse_lossless", HOUR_S, "insufficient resolution"),
        ("resolved_lossless", 60, "fail"),
        ("empty", 60, "empty cohort"),
        ("turnover", 60, "pass"),
        ("turnover_roundoff", 60, "pass"),
        ("different_gross_rate", 60, "fail"),
    ):
        raw = worlds.r1(0.75)
        row = release_check.FATE_ROWS["short_lived"]
        if name == "different_gross_rate":
            (operator,) = [
                o for o in raw["model"]["operators"] if o["law"] == worlds.POLYMERISATION
            ]
            routes = {d["id"] for d in operator["degradations"]
                      if d["polymer"] == row and d["cell"] == "cell_0"}
            for control in raw["experiment"]["polymerisation_controls"]:
                if control["route_id"] in routes:
                    for change in control["schedule"]:
                        change["value"] = float(change["value"]) / 2
        times = list(range(0, 2 * HOUR_S + 1, step))
        lost = [0.0] * len(times)
        if name == "turnover":
            lost = [10 * per_copy * math.log(2) * t / (HOUR_S / 2) for t in times]
            made = lost
        elif name in ("turnover_roundoff", "different_gross_rate"):
            k = release_check.gross_rate({"definition": raw, "cell": "cell_0"}, row)
            lost = [10 * per_copy * k * t for t in times]
            made = lost
        elif name == "empty":
            made = lost
        else:
            made = [per_copy * min(t, HOUR_S) / HOUR_S for t in times]
        amounts = [10 * per_copy + (q - d) for q, d in zip(made, lost, strict=True)]
        record = dict(
            definition=raw,
            cell="cell_0",
            t=times,
            readouts={
                "n_R_s": amounts,
                f"int_Q_{worlds.RELEASE}_short_lived": made,
                "int_D_R_s": lost,
            },
        )
        path.write_text(json.dumps(record, allow_nan=False))
        cases[name] = compare(path, name, "short_lived")
        cases[name]["expected_control"] = expected
        cases[name]["control_passed"] = cases[name]["checker"] == expected
        if name == "turnover_roundoff":
            # After close every member has the same constant hazard, for any release history.
            with localcontext() as ctx:
                ctx.prec = 75
                analytic = (-Decimal.from_float(k) * HOUR_S).exp()
            assert float(analytic) == EXPECTED["short_lived"]
            cases[name]["analytic_ratio"] = str(analytic)
    assert cases["resolved_lossless"]["net_agrees"] is False
    assert cases["turnover_roundoff"]["net_agrees"] is True
    assert cases["different_gross_rate"]["gross_ratio_passes"] is False
    assert cases["different_gross_rate"]["net_agrees"] is True
    return cases


def recorded(r1_dir, r2_dir):
    results = {}
    for prefix, directory in (("R1 p=0.75", r1_dir), ("R2", r2_dir)):
        for machine in ("returned", "held"):
            name = f"{prefix} {machine}"
            path = (
                directory / engine_run.slug(release_check.SET) / (engine_run.slug(name) + ".json")
            )
            for fate in EXPECTED:
                results[f"{name} {fate}"] = compare(path, name, fate)
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--records",
        nargs=2,
        type=Path,
        metavar=("R1_DIR", "R2_DIR"),
        help="Also reread both fates and machine policies from saved engine exports",
    )
    args = parser.parse_args()
    with TemporaryDirectory() as tmp:
        results = dict(controls=controls(Path(tmp)))
    if args.records:
        results["recorded"] = recorded(*args.records)
    passed = all(row["agrees"] and row.get("control_passed", True)
                 for group in results.values() for row in group.values())
    print(json.dumps(dict(passed=passed, **results), indent=2, allow_nan=False))
    raise SystemExit(0 if passed else 1)
