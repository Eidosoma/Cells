"""Compare the five FR-35 bookings with discrete ideal energy and binomial weights in k_BT."""

import json
import math
from decimal import Decimal, localcontext
from functools import cache
from unittest.mock import patch

import jax
import jax.numpy as jnp
import numpy as np

from cells.models.assembly_lineages_v2 import population, withdrawal
from pool_withdrawal import BINS, cutoff, midpoint
from tests.unit import test_assembly_lineages_v2_replacement as fixture

# The acceptance world's independent energy reference already uses this absolute tolerance in k_BT.
TOL = Decimal("1e-10")


@cache
def log_factorial(n):
    return Decimal(math.factorial(n)).ln()


@cache
def surprisal(p, kept, selected):
    """Use the exact integer multiplicity. A zero count contributes zero at either endpoint."""
    cost = -Decimal(math.comb(kept + selected, selected)).ln()
    if selected:
        cost -= selected * p.ln()
    if kept:
        cost -= kept * (1 - p).ln()
    return cost


def standard_terms(world):
    """Read physical inputs from the world, independently of the engine's free-energy tables."""
    x = Decimal("6.02214076e23") * Decimal.from_float(world.volume("pool"))
    x *= Decimal.from_float(world.units.standard_concentration_mM) * Decimal("0.001")
    species_mu = {s.id: Decimal.from_float(s.mu_solution) for s in world.species}
    return {p.name: species_mu[p.species] - x.ln() for p in world.places if p.phase == "pool" and not p.held}


def reference(linear, before, taken, buffer, fraction):
    """Compute the split and mixing costs directly from probabilities, and ΔF from net counts."""
    p = Decimal.from_float(fraction)
    split = heat = sample = work = change = Decimal(0)
    for name, mu in linear.items():
        n, k, b = (values.get(name, 0) for values in (before, taken, buffer))
        r = n - k
        assert 0 <= k <= n and b >= 0
        split += surprisal(p, r, k)
        heat += surprisal(p, r, b)
        sample += k * (mu - p.ln()) + log_factorial(k)
        work += b * (mu - p.ln()) + log_factorial(b)
        change += (b - k) * mu + log_factorial(r + b) - log_factorial(n)
    result = {"pool_loss_kT": sample - split, "sample_F_kT": sample, "split_surprisal_kT": split,
              "buffer_F_kT": work, "mixing_heat_kT": heat}
    assert split >= 0 and heat >= 0
    assert abs(work - result["pool_loss_kT"] - heat - change) < Decimal("1e-65")
    return result, change


def check(actual, expected, maxima):
    for field, target in expected.items():
        error = abs(Decimal.from_float(float(actual[field])) - target)
        maxima[field] = max(maxima.get(field, 0.0), float(error))
        assert error <= TOL, (field, actual[field], target, error)


def world_runs():
    results = []
    for f in (0.25, 0.5, float(midpoint(0))):
        spec = fixture.acceptance_spec(f)
        run = fixture.runner.run(spec).check()
        (record,) = run.population["withdrawals"]
        (row,) = np.flatnonzero(run.rows["row_kind"] == population.WITHDRAWAL)
        assert run.rows["row_event"][row] == run.rows["row_event"][row - 1]
        ref, change = reference(standard_terms(spec.model.world), record["before"], record["withdrawn"],
                                record["supplied"], f)
        maxima = {}
        check(record, ref, maxima)
        column = run.population["schedule_columns"].index(record["schedule"])
        values = {key: run.rows[name] for key, name in (
            ("pool_loss_kT", "discarded_free_energy_kT"), ("mixing_heat_kT", "event_heat_kT"),
            ("delta_free_energy_kT", "free_energy_kT"))}
        values["buffer_F_kT"] = run.rows["schedule_work_kT"][:, column]
        changes = {key: float(a[row] - a[row - 1]) for key, a in values.items()}
        check(changes, {k: ref[k] for k in changes if k in ref} | {"delta_free_energy_kT": change}, maxima)
        results.append(dict(fraction=f, receipt={k: record[k] for k in ref}, ledger_changes=changes,
                            max_abs_error_kT=max(maxima.values())))
    return results


def all_small_outcomes():
    spec = fixture.acceptance_spec(0.5)
    world = spec.model.world
    pool_f = fixture.pool_f_of(spec)
    linear = standard_terms(world)
    x = [p.name for p in world.places].index("X@pool")
    before, taken, buffer = np.zeros((3, spec.execution.place_capacity), dtype=np.int64)
    word0 = float(midpoint(0))
    fractions = (word0 / 2, word0, math.nextafter(word0, 1), 0.25, 1 / 3, 0.5, 0.9,
                 math.nextafter(1.0, 0.0))
    maxima = {}
    cases = zero_heat = rounded_to_zero = negative_heat = 0
    largest_lost_heat = Decimal(0)
    min_heat = math.inf
    for f in fractions:
        for n in range(9):
            before[x] = n
            for k in range(n + 1):
                taken[x] = k
                for b in (0, 1, 4):
                    buffer[x] = b
                    actual = withdrawal.booking(pool_f, before, taken, buffer, f, world)
                    ref, change = reference(linear, {"X@pool": n}, {"X@pool": k}, {"X@pool": b}, f)
                    check(actual, ref, maxima)
                    balance = actual["buffer_F_kT"] - actual["pool_loss_kT"] - actual["mixing_heat_kT"]
                    check({"ledger": balance}, {"ledger": change}, maxima)
                    heat = actual["mixing_heat_kT"]
                    min_heat = min(min_heat, heat)
                    negative_heat += int(heat < 0)
                    zero_heat += int(ref["mixing_heat_kT"] == 0)
                    if heat == 0 and ref["mixing_heat_kT"] > 0:
                        rounded_to_zero += 1
                        largest_lost_heat = max(largest_lost_heat, ref["mixing_heat_kT"])
                    cases += 1
    # For this draw, misbooking the free energy of the sample as the sink breaks closure by σ.
    before[x], taken[x], buffer[x] = 8, 1, 0
    bad = withdrawal.booking(pool_f, before, taken, buffer, 0.5, world)
    wrong_sink_error = bad["sample_F_kT"] - bad["pool_loss_kT"]
    assert abs(wrong_sink_error - math.log(32)) < float(TOL)
    assert negative_heat == 0, (negative_heat, min_heat)
    return dict(cases=cases, fractions=fractions, max_abs_error_kT=maxima, minimum_heat_kT=min_heat,
                negative_float_heats=negative_heat, exactly_zero_reference_heats=zero_heat,
                positive_reference_heats_rounded_to_zero=rounded_to_zero, largest_heat_rounded_to_zero_kT=float(largest_lost_heat),
                sample_as_sink_error_kT=wrong_sink_error)


def single_word_controls():
    first = float(midpoint(0))
    cases = [(0.5, 0), (first, 0), (math.nextafter(first, 1), 0),
             (math.nextafter(1.0, 0.0), BINS - 1)]
    rows = []
    for f, raw_word in cases:
        spec = fixture.acceptance_spec(f)
        world, (schedule,) = spec.model.world, spec.experiment.schedules
        key = fixture.model.layout(spec).base_key
        x = [p.name for p in world.places].index("X@pool")
        n = np.zeros(spec.execution.place_capacity, dtype=np.int64)
        n[x] = 1
        withdrawal.refuse_beyond_capacity(world, schedule, n, spec.execution.molecule_capacity)

        # Only the raw generator word is supplied. The engine converts it and applies the strict cut.
        def bits(_key, shape, dtype):
            return jnp.full(shape, raw_word, dtype=dtype)

        with patch.object(jax.random, "bits", side_effect=bits):
            taken, _ = withdrawal.draw(key, world, schedule, 0, n)
        k = int(taken[x])
        assert k == int(midpoint(raw_word) < f)
        energy = withdrawal.booking(fixture.pool_f_of(spec), n, taken,
                                    withdrawal.buffer_vector(world, schedule, len(n)), f, world)
        p, q = Decimal.from_float(f), Decimal(cutoff(f)) / BINS
        physical, sampled = surprisal(p, 1 - k, k), surprisal(q, 1 - k, k)
        check(energy, {"split_surprisal_kT": physical}, {})
        gap = physical - sampled
        if (f, raw_word) in (cases[2], cases[3]):
            assert abs(gap - Decimal(2).ln()) < Decimal("1e-14")
        rows.append(dict(fraction=f, raw_word=raw_word, taken=k, physical_kT=float(physical),
                         sampler_kT=float(sampled), booked_split_kT=energy["split_surprisal_kT"],
                         physical_minus_sampler_kT=float(gap)))
    return rows


def tracer_heat_means():
    """Weight every possible booked heat by the exact number of independent words producing it."""
    spec = fixture.acceptance_spec(0.5)
    world, pool_f = spec.model.world, fixture.pool_f_of(spec)
    x = [place.name for place in world.places].index("X@pool")
    before, taken, empty = np.zeros((3, spec.execution.place_capacity), dtype=np.int64)
    before[x] = 1
    rows = []
    for f in (0.25, 0.5, 1 / 3, math.nextafter(1.0, 0.0)):
        p, q = Decimal.from_float(f), Decimal(cutoff(f)) / BINS
        per_retained = -(1 - p).ln()
        ideal, sampler = (1 - p) * per_retained, (1 - q) * per_retained
        mean = Decimal(0)
        for k, weight in ((0, 1 - q), (1, q)):
            taken[x] = k
            receipt = withdrawal.booking(pool_f, before, taken, empty, f, world)
            mean += weight * Decimal.from_float(receipt["mixing_heat_kT"])
        assert abs(mean - sampler) <= TOL
        if f == math.nextafter(1.0, 0.0):
            assert abs(mean / ideal - 2) < Decimal("1e-14")
        rows.append(dict(fraction=f, volume_mean_kT=float(ideal), sampler_mean_kT=float(sampler),
                         weighted_engine_mean_kT=float(mean), ratio_to_volume_mean=float(mean / ideal)))
    return rows


if __name__ == "__main__":
    jax.config.update("jax_enable_x64", True)
    with jax.default_device(jax.devices("cpu")[0]), localcontext() as context:
        context.prec = 88
        result = dict(worlds=world_runs(), small_counts=all_small_outcomes(), actual_words=single_word_controls(),
                      tracer_free_means=tracer_heat_means())
    print(json.dumps(result, indent=2, allow_nan=False))
