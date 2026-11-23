"""Compare the public FR-38 survival verdict with the finite bound on the two cohort counts."""

import argparse
import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory

from validation.gene_regulation import cohort, engine_run, release_check, worlds

# The R1/R2 sheet holds the durable half-life at 2 h and the short half-life at 0.5 h.
HOUR_S = 3600
EXPECTED = {"durable": math.sqrt(0.5), "short_lived": 0.25}


def compare(path, name, fate):
    row = release_check.FATE_ROWS[fate]
    counts = cohort.survival(*cohort.read(path, row), 0, HOUR_S, 2 * HOUR_S)
    close, later = counts["alive_at_window_end"], counts["alive_at_sample"]
    e_close, e_later = counts["grid_error_at_window_end"], counts["grid_error_at_sample"]
    rate = EXPECTED[fate]
    residual = abs(later - rate * close)
    allowance = None
    if close == 0:
        assert counts["ratio"] is None
        reference = "empty cohort"
    elif e_close is None or e_later is None:
        reference = "insufficient resolution"
    else:
        allowance = e_later + rate * e_close
        assert math.isfinite(allowance)
        reference = "pass" if residual <= allowance else "fail"

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
            if allowance is None
            else (bound is not None and math.isclose(bound, allowance / close, rel_tol=1e-14))
        )
        agrees = reported == reference and result["ok"] == (reference == "pass") and correct_bound
    return dict(
        fate=fate,
        expected_ratio=rate,
        **counts,
        count_residual_fmol=residual,
        count_allowance_fmol=allowance,
        reference=reference,
        checker=reported,
        checker_ratio_bound=reported_bound,
        agrees=agrees,
    )


def controls(directory):
    raw = worlds.r1(0.75)
    per_copy = release_check.COPY_FMOL
    path = directory / "counters.json"
    cases = {}
    for name, step in (
        ("sparse_lossless", HOUR_S),
        ("resolved_lossless", 60),
        ("empty", 60),
        ("turnover", 60),
    ):
        times = list(range(0, 2 * HOUR_S + 1, step))
        lost = [0.0] * len(times)
        if name == "turnover":
            lost = [10 * per_copy * math.log(2) * t / (HOUR_S / 2) for t in times]
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
    assert cases["sparse_lossless"]["reference"] == "insufficient resolution"
    assert cases["resolved_lossless"]["reference"] == "fail"
    assert cases["empty"]["reference"] == "empty cohort"
    assert cases["turnover"]["reference"] == "pass"
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
    passed = all(row["agrees"] for group in results.values() for row in group.values())
    print(json.dumps(dict(passed=passed, **results), indent=2, allow_nan=False))
    raise SystemExit(0 if passed else 1)
