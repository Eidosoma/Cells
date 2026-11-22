"""FR-42 point releases and interval totals, with a separate development FR-38 engine comparison."""

import argparse
import json
import math
from fractions import Fraction
from pathlib import Path
from tempfile import TemporaryDirectory

from validation.gene_regulation import cohort


def point_releases():
    # (completion step, detachment step, amount) and survival over each step.
    events = [(0, 1, 10), (1, 2, 4), (2, 3, 2)]
    keep = [1, Fraction(4, 5), Fraction(3, 4), Fraction(1, 2)]

    def history(windows):
        # Sum over individual releases and their subsequent survival factors, independently
        # of Lean's accumulator. Sampling at a boundary precedes that boundary's releases.
        return [
            sum(
                amount * math.prod(keep[release:end])
                for _, release, amount in events
                if release < end and any(a <= release < b for a, b in windows)
            )
            for end in range(len(keep) + 1)
        ]

    first, later, reused = history([(1, 2)]), history([(3, 4)]), history([(1, 2), (3, 4)])
    assert first == [0, 0, 8, 6, 3] and later == [0, 0, 0, 0, 1]
    assert reused == [a + b for a, b in zip(first, later, strict=True)]
    assert history([(2, 3)])[3] == 3  # The release at the excluded endpoint enters the next window.
    completed_in_window = sum(n for completion, _, n in events if 1 <= completion < 2)
    released_in_window = sum(n for _, release, n in events if 1 <= release < 2)
    assert (completed_in_window, released_in_window) == (4, 10)

    def fraction_at_chase(close, chase):
        return None if close == 0 else Fraction(chase, close)

    fraction = fraction_at_chase(first[2], first[3])
    assert fraction == Fraction(3, 4) and fraction_at_chase(0, 0) is None
    return dict(
        completed_in_window=completed_in_window,
        released_in_window=released_in_window,
        alive_at_close=int(first[2]),
        alive_at_chase=int(first[3]),
        chase_fraction=str(fraction),
        empty_fraction=None,
        old_at_reuse_end=int(first[-1]),
        new_at_reuse_end=int(later[-1]),
        combined_at_reuse_end=int(reused[-1]),
    )


def interval_counters():
    # A constant physical pool is maintained by uniform production and loss. For one
    # time unit at rate log(2), the exact survival of uniform inflow Q is Q/(2 log(2)).
    k = math.log(2)
    times = [0.0, 1.0, 2.0, 3.0, 4.0]
    pool = [10.0] * len(times)
    counter = [10.0 * k * t for t in times]
    cases = {}
    for name, start, stop, sample, exact in (
        ("first_close", 1, 2, 2, 5.0),
        ("first_chase", 1, 2, 3, 2.5),
        ("first_at_reuse_end", 1, 2, 4, 1.25),
        ("new_at_reuse_end", 3, 4, 4, 5.0),
        ("empty_window", 2, 2, 3, 0.0),
    ):
        _, recovered, _ = cohort.survivors(times, pool, counter, counter, start, stop, sample)
        analytic = cohort.known_rate(times, counter, k, start, stop, sample)
        assert all(math.isclose(v, exact, rel_tol=2e-15) for v in (recovered, analytic))
        cases[name] = recovered
    combined = cases["first_at_reuse_end"] + cases["new_at_reuse_end"]
    assert math.isclose(combined, 6.25, rel_tol=2e-15)
    # The same interval total could instead arrive as a point at its start or just before
    # its end. The host readout explicitly spreads it uniformly within the interval.
    released = counter[2] - counter[1]
    assert released / 2 < cases["first_close"] < released
    return dict(
        survivors=cases,
        reused_total=combined,
        if_all_at_start=released / 2,
        limit_if_all_at_end=released,
    )


def window_survivors(series, start, stop, sample):
    made, alive, _ = cohort.survivors(*series, start, stop, sample)
    assert 0 < alive <= made
    return alive


def development_release():
    import jax
    import numpy as np

    from cells.definitions.specs import parse_spec
    from validation.gene_regulation import engine_run, kernel, worlds

    jax.config.update("jax_enable_x64", True)
    raw = kernel.truncated(worlds.r1(0.75, labelled=True), 10.0)
    times = [0.0, 2.0, 4.0, 6.0, 8.0, 10.0]
    raw["experiment"]["observation_times"] = times
    active = [1, 2, 1, 2, 1]
    route = next(
        r for r in raw["experiment"]["polymerisation_controls"] if r["route_id"] == worlds.LABEL
    )
    route["schedule"] = [
        dict(time=t, value=float(label)) for t, label in zip(times[:-1], active, strict=True)
    ]
    spec = parse_spec(raw)
    t, x, _ = engine_run.readouts(spec, engine_run.collect(spec))
    np.testing.assert_array_equal(t, times)
    np.testing.assert_array_equal(x["int_Q_tx"], np.zeros(len(times)))
    exported = dict(definition=spec.to_dict(), t=t, readouts=x)
    report = {}
    with TemporaryDirectory() as directory:
        path = Path(directory) / "release.json"
        path.write_text(json.dumps(exported, allow_nan=False))
        for fate, row in (("durable", "R_c2"), ("short_lived", "R_s_c2")):
            prefix = f"int_Q_{worlds.RELEASE}_{fate}"
            class1, class2 = (np.diff(x[f"{prefix}_{i}"]) for i in (1, 2))
            assert all(
                a > 0 and b == 0 if label == 1 else a == 0 and b > 0
                for a, b, label in zip(class1, class2, active, strict=True)
            )
            series = cohort.read(path, row)
            np.testing.assert_array_equal(series[2], x[f"{prefix}_2"])
            close, chased = window_survivors(series, 2, 4, 4), window_survivors(series, 2, 4, 6)
            old, new = window_survivors(series, 2, 4, 8), window_survivors(series, 6, 8, 8)
            # Class 2 has zero inflow in the gap. One continuous integration of this
            # counter across the gap provides a separate check of the two-window sum.
            combined = window_survivors(series, 2, 8, 8)
            assert 0 < old < chased < close and combined > new
            assert math.isclose(combined, old + new, rel_tol=2e-14)
            report[fate] = dict(
                first_at_close_fmol=close,
                first_at_chase_fmol=chased,
                chase_fraction=chased / close,
                carried_fmol=old,
                new_fmol=new,
                combined_fmol=combined,
                class2_release_by_step_fmol=class2.tolist(),
            )
    return dict(
        steps=len(active),
        class_by_step=active,
        new_chain_completions_fmol=x["int_Q_tx"][-1],
        fates=report,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reference-only", action="store_true", help="Run the two synthetic references"
    )
    results = dict(point=point_releases(), intervals=interval_counters())
    if not parser.parse_args().reference_only:
        results["development_release"] = development_release()
    print(json.dumps(results, indent=2, allow_nan=False))
