"""FR-42 window references and a compiled FR-38 replay with neutral RNA labels."""

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
    from validation.gene_regulation import engine_run, kernel, release_check, worlds

    jax.config.update("jax_enable_x64", True)
    times = [i / 2 for i in range(21)]
    samples = times[::4]  # Same six endpoints on the fine and two-second counter grids.
    windows = [(2.0, 4.0, 0.75), (6.0, 8.0, 0.25)]
    raw = kernel.truncated(worlds.r1(0.75, dt=0.5), times[-1])
    raw["experiment"]["observation_times"] = times
    kernel.block(raw)["chains"][0]["release"]["durable_fraction"] = "scheduled"
    raw["experiment"]["polymerisation_controls"].append(
        dict(
            route_id=worlds.RELEASE,
            schedule=[dict(time=0.0, value=0.75), dict(time=6.0, value=0.25)],
        )
    )

    def readouts(definition):
        spec = parse_spec(definition)
        t, x, checks = engine_run.readouts(spec, engine_run.collect(spec))
        assert t == times
        return spec, x, checks

    plain, physical, checks = readouts(raw)
    by_schedule = {}
    for second_mark in ("cohort", "second"):
        labelled = worlds.with_share_labels(
            raw, window=windows[0][:2], labels=("base", "cohort", "second")
        )
        for route in labelled["experiment"]["label_arrivals"]:
            route["schedule"].extend(
                [dict(time=6.0, label=second_mark), dict(time=8.0, label="base")]
            )
        _, x, labelled_checks = readouts(labelled)
        assert {k for k in x if not k.startswith("label_")} == set(physical)
        for k, values in physical.items():
            assert np.asarray(x[k]).tobytes() == np.asarray(values).tobytes(), k
        assert checks == labelled_checks
        by_schedule[second_mark] = x
    reused, separate = by_schedule["cohort"], by_schedule["second"]
    assert all(q == 0 for q in physical["int_Q_tx"])  # Every release came from the initial hold.

    # Physical loss of the hold independently measures gross detachment in each step.
    hold = np.asarray(physical[f"H_{worlds.RELEASE}"])
    gross = {f: np.diff(physical[f"int_Q_{worlds.RELEASE}_{f}"]) for f in release_check.FATE_ROWS}
    total = gross["durable"] + gross["short_lived"]
    gap = np.abs(total + np.diff(hold))
    assert np.all(gap <= 128 * math.ulp(1.0) * (hold[1:] + hold[:-1] + total))
    assert np.all(total > 0)
    np.testing.assert_allclose(
        gross["durable"] / total, [0.75 if t < 6 else 0.25 for t in times[:-1]], atol=0, rtol=2e-12
    )
    marked_steps = [any(a <= t < b for a, b, _ in windows) for t in times[:-1]]
    marked_starts = [t for t, marked in zip(times[:-1], marked_steps, strict=True) if marked]
    assert marked_starts == [2, 2.5, 3, 3.5, 6, 6.5, 7, 7.5]

    report = {}
    with TemporaryDirectory() as directory:
        path = Path(directory) / "plain.json"
        path.write_text(
            json.dumps(
                dict(
                    definition=plain.to_dict(),
                    t=times,
                    cell=checks["exported_cell"],
                    readouts=physical,
                )
            )
        )
        for fate, row in release_check.FATE_ROWS.items():
            series = cohort.read(path, row)
            coarse = [values[::4] for values in series]
            np.testing.assert_array_equal(series[2], physical[f"int_Q_{worlds.RELEASE}_{fate}"])
            first = np.asarray(separate[f"label_{row}_cohort"])
            second = np.asarray(separate[f"label_{row}_second"])
            both = np.asarray(reused[f"label_{row}_cohort"])
            start, close, reopen, end = (times.index(t) for t in (2, 4, 6, 8))
            assert (
                first[start] == 0 < first[reopen] < first[close]
                and second[reopen] == 0 < second[end]
            )
            assert all(q == 0 for q in reused[f"label_{row}_second"])
            np.testing.assert_allclose(both, first + second, rtol=release_check.SHARES, atol=0)
            for x in (reused, separate):
                labels = [x[f"label_{row}_{name}"] for name in ("base", "cohort", "second")]
                np.testing.assert_allclose(
                    np.sum(labels, axis=0), physical[f"n_{row}"], rtol=release_check.SHARES, atol=0
                )

            # One reference integrates the analytic physical rates. The other infers survival
            # from the unlabelled run's cumulative releases, losses and total RNA at the cell.
            exact, inferred, coarse_inferred, grid_errors = [], [], [], []
            for sample in samples:
                bounds = [(a, min(b, sample), p) for a, b, p in windows if a < sample]
                exact.append(
                    math.fsum(
                        release_check.window_cohort(p, fate, a, b, sample) * release_check.COPY_FMOL
                        for a, b, p in bounds
                    )
                )
                inferred.append(
                    math.fsum(window_survivors(series, a, b, sample) for a, b, _ in bounds)
                )
                coarse_inferred.append(
                    math.fsum(window_survivors(coarse, a, b, sample) for a, b, _ in bounds)
                )
                errors = [cohort.grid_error(*series, a, b, sample) for a, b, _ in bounds]
                assert all(error is not None for error in errors)
                grid_errors.append(math.fsum(errors))
            bound = release_check.SURVIVORS + release_check.split_bound(fate, plain.execution.dt)
            sampled = both[::4]
            np.testing.assert_allclose(sampled, exact, rtol=bound, atol=0)
            np.testing.assert_allclose(inferred, exact, rtol=release_check.SURVIVORS, atol=0)
            assert np.all(np.abs(sampled - inferred) <= np.asarray(grid_errors) + bound * sampled)
            report[fate] = dict(
                gross_marked_fmol=float(np.sum(gross[fate][marked_steps])),
                first_at_close_fmol=float(first[close]),
                first_at_reopening_fmol=float(first[reopen]),
                chase_fraction=float(first[reopen] / first[close]),
                old_at_second_close_fmol=float(first[end]),
                new_at_second_close_fmol=float(second[end]),
                reused_at_second_close_fmol=float(both[end]),
                reused_amounts_fmol=sampled.tolist(),
                max_reuse_error_fmol=float(np.max(np.abs(both - (first + second)))),
                max_analytic_error_fmol=float(np.max(np.abs(sampled - exact))),
                max_counter_relative_error={
                    grid: max(abs(v / e - 1) for v, e in zip(values, exact, strict=True) if e > 0)
                    for grid, values in (
                        ("half_second", inferred),
                        ("two_seconds", coarse_inferred),
                    )
                },
            )
    marked_hold_loss = -math.fsum(np.diff(hold)[marked_steps])
    marked_fate_sum = math.fsum(result["gross_marked_fmol"] for result in report.values())
    marked_error = abs(marked_fate_sum - marked_hold_loss)
    assert marked_error <= 128 * math.ulp(1.0) * math.fsum((hold[1:] + hold[:-1])[marked_steps])
    return dict(
        sample_times_s=samples,
        engine_step_s=plain.execution.dt,
        marked_step_starts_s=marked_starts,
        compiled_worlds=3,
        shared_physical_readouts=len(physical),
        diagnostics_equal=True,
        largest_gross_balance_error_fmol=float(np.max(gap)),
        marked_hold_loss_fmol=marked_hold_loss,
        marked_fate_sum_fmol=marked_fate_sum,
        marked_balance_error_fmol=marked_error,
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
