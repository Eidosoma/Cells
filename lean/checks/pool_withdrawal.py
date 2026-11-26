"""Check count conservation and droplet sampling in cells.operator.pool_withdrawal@1."""

import argparse
import json
import math
from fractions import Fraction
from pathlib import Path
from statistics import mean, variance
from unittest.mock import patch

import jax
import jax.numpy as jnp
import numpy as np

from cells.models.assembly_lineages_v2 import population, streams, withdrawal
from tests.unit import test_assembly_lineages_v2_replacement as fixture

DATA = Path(__file__).with_name("data")
BINS = 1 << 52


def midpoint(m):
    return Fraction(2 * m + 1, 2 * BINS)


def cutoff(fraction):
    return math.ceil(BINS * Fraction(fraction) - Fraction(1, 2))


def midpoint_cases():
    first = float(midpoint(0))
    fractions = [first / 2, first, math.nextafter(first, 1), 0.1, 0.25, 1 / 3,
                 0.5, float(midpoint(BINS // 2)), float(midpoint(BINS - 1))]
    cases = []
    for f in fractions:
        spec = fixture.acceptance_spec(f)
        world, (schedule,) = spec.model.world, spec.experiment.schedules
        key = fixture.model.layout(spec).base_key
        boundary = cutoff(f)
        q = Fraction(boundary, BINS)
        m = sorted({0, BINS - 1, *(i for i in range(boundary - 2, boundary + 2) if 0 <= i < BINS)})
        assert all((midpoint(i) < Fraction(f)) == (i < boundary) for i in m)
        assert abs(q - Fraction(f)) <= Fraction(1, 2 * BINS)

        # Plant raw words only. Their masking, conversion, strict comparison and count are production code.
        words = np.array([i | ((j % 2) << 63) for j, i in enumerate(m)], dtype=np.uint64)

        def bits(_key, shape, dtype):
            assert dtype == jnp.uint64
            return jnp.asarray(np.resize(words, shape))

        with patch.object(jax.random, "bits", side_effect=bits):
            stream = streams.stream_key_data(key, schedule.index, "schedule")
            uniforms = np.asarray(streams.block(stream, 0, len(m)))
            assert [Fraction(x) for x in uniforms] == [midpoint(i) for i in m]
            pool = np.zeros(len(world.places), dtype=np.int64)
            place = withdrawal.finite_places(world)[0]
            pool[place] = len(m)
            taken, _ = withdrawal.draw(key, world, schedule, 0, pool)
            assert int(taken[place]) == sum(i < boundary for i in m)
        cases.append(dict(requested=str(Fraction(f)), effective=str(q), difference=str(q - Fraction(f)),
                          accepted_word_indices=boundary, tested_indices=m))
    assert cutoff(first) == 0 and cutoff(fractions[2]) == 1
    assert cutoff(fractions[-1]) == BINS - 1
    return cases


def host_counts():
    cases = []
    for f in (0.5, 0.25, float(midpoint(0))):
        spec = fixture.acceptance_spec(f)
        run = fixture.runner.run(spec).check()
        (record,) = run.population["withdrawals"]
        (row,) = np.flatnonzero(run.rows["row_kind"] == population.WITHDRAWAL)
        names = [p.name for p in spec.model.world.places]
        assert run.rows["row_event"][row] == run.rows["row_event"][row - 1]
        for field in ("slot_count", "slot_key"):
            np.testing.assert_array_equal(run.rows[field][row], run.rows[field][row - 1])
        for name, n in record["before"].items():
            i = names.index(name)
            k, kept, b = (record[v][name] for v in ("withdrawn", "remaining", "supplied"))
            after = int(run.rows["pool_count"][row, i])
            assert int(run.rows["pool_count"][row - 1, i]) == n
            assert 0 <= k <= n and kept == n - k
            assert after == kept + b and after + k == n + b
            assert after <= spec.execution.molecule_capacity
        if cutoff(f) == 0:
            assert not any(record["withdrawn"].values())
        cases.append({k: record[k] for k in ("fraction", "before", "withdrawn", "remaining", "supplied")})
    return cases


def seed_moments():
    spec = fixture.acceptance_spec(0.5)
    world, execution = spec.model.world, spec.execution
    (schedule,) = spec.experiment.schedules
    finite = withdrawal.finite_places(world)
    x = [p.name for p in world.places].index("X@pool")
    n = 8
    keys = fixture.base_keys(np.arange(fixture.N_STREAMS), execution.environment,
                             execution.lineage, execution.branch)
    uniforms = fixture.blocks(keys, schedule.index, finite.index(x), n)
    output = {}
    for requested in (0.25, 0.5, 1 / 3):
        (this_schedule,) = fixture.acceptance_spec(requested).experiment.schedules
        counts = (uniforms < requested).sum(axis=1)
        pool = np.zeros(len(world.places), dtype=np.int64)
        pool[x] = n
        for index in range(0, len(keys), len(keys) // 10):
            taken, _ = withdrawal.draw(keys[index], world, this_schedule, 0, pool)
            assert int(taken[x]) == int(counts[index])
        p = Fraction(cutoff(requested), BINS)
        mu, var = n * p, n * p * (1 - p)
        observed_mean, observed_var = float(counts.mean()), float(counts.var(ddof=1))
        assert abs(observed_mean - mu) < 0.1 and abs(observed_var - var) < 0.2
        # The same words used for all molecules would conserve counts but inflate the variance.
        shared = n * (uniforms[:, 0] < requested)
        assert abs(float(shared.var(ddof=1)) - var) > 0.2
        output[str(requested)] = dict(seeds=len(keys), mean=observed_mean, variance=observed_var,
                                      predicted_mean=float(mu), predicted_variance=float(var))
    return output


def droplets(svg=None):
    data = json.loads((DATA / "pool_withdrawal_measurements.json").read_text())
    source = data["fornell"]
    fission = json.loads((DATA / source["existing_counts"]).read_text())
    groups = fission["center_counts_by_parent"] | source["additional_center_counts_by_parent"]
    assert len(groups) == len(fission["center_counts_by_parent"]) + len(source["additional_center_counts_by_parent"])
    assert {n: len(k) for n, k in groups.items()} == fission["parent_count_frequency"]
    if svg:
        from lineage_fission import verify_figure

        verify_figure(svg, fission | {"center_counts_by_parent": groups})
    ratios = [Fraction(k, int(n)) for n, counts in groups.items() for k in counts]
    n_center = sum(sum(v) for v in groups.values())
    n_parent = sum(int(n) * len(v) for n, v in groups.items())
    assert (len(ratios), n_center, n_parent) == (180, 2010, 4269)
    p = Fraction(cutoff(1 / 3), BINS)
    by_size = {}
    for n, counts in fission["center_counts_by_parent"].items():
        by_size[n] = dict(splits=len(counts), mean=mean(counts), predicted_mean=float(int(n) * p),
                          variance=variance(counts), predicted_variance=float(int(n) * p * (1 - p)))
    liu = data["liu"]
    retained = liu["center_nL"] / liu["input_nL_approx"]
    q = Fraction(cutoff(1 - retained), BINS)
    return dict(fornell=dict(splits=len(ratios), sampled_fraction=float(mean(ratios)),
                             pooled_fraction=n_center / n_parent, center_beads=n_center, total_beads=n_parent,
                             nominal_sampled_fraction=float(p), at_fixed_parent=by_size),
                liu=dict(retained_volume_fraction=retained, predicted_bead_fraction=float(1 - q),
                         measured_bead_fraction=liu["retained_fraction_mean"],
                         measured_bead_fraction_sd=liu["retained_fraction_sd"]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--figure-svg", type=Path, help="Verify all 180 observations against page 3 of the vector PDF")
    args = parser.parse_args()
    jax.config.update("jax_enable_x64", True)
    with jax.default_device(jax.devices("cpu")[0]):
        result = dict(midpoint_cases=midpoint_cases(), host_counts=host_counts(),
                      seed_moments=seed_moments(), droplets=droplets(args.figure_svg))
    print(json.dumps(result, indent=2, allow_nan=False))
