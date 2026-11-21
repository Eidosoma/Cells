"""Compare concentration-matched FR-35 heat with exact binomial weights and the engine ledger."""

import json
import math
from decimal import Decimal, localcontext
from fractions import Fraction

import numpy as np

from cells.models.assembly_lineages_v2 import withdrawal
from pool_withdrawal import BINS, cutoff
from pool_withdrawal_energy import TOL, check, reference, standard_terms, surprisal
from tests.unit import test_assembly_lineages_v2_replacement as fixture


def mass(n, k, f):
    return math.comb(n, k) * f**k * (1 - f)**(n - k)


def exact_count_check():
    """Compare rational masses for all matched integer buffers through 50 starting molecules."""
    cases = equalities = 0
    for n in range(2, 51):
        for b in range(1, n):
            # f=b/n. The common factor (1-f)^(n-k) cancels and the rest has integer numerators.
            for k in range(n + 1):
                mixed = math.comb(n - k + b, b) * b**b * n**k
                split = math.comb(n, k) * b**k * n**b
                assert mixed >= split and (mixed == split) == (k == b)
                cases += 1
                equalities += int(k == b)
    return dict(starting_counts=[2, 50], cases=cases, equalities=equalities)


def pool_case(n, b, f):
    """Keep the tracer concentration fixed across pool sizes and allow the worst-case final count."""
    raw = fixture.acceptance_spec(f).to_dict()
    world = raw["model"]["world"]
    world["phases"]["pool"]["volume_L"] = n * 1e-22
    for species in world["phases"]["pool"]["species"]:
        if species["kind"] == "finite":
            name = species["id"]
            world["founder"][name + "@pool"] = n if name == "X" else 0
    raw["execution"]["molecule_capacity"] = max(raw["execution"]["molecule_capacity"], n + b)
    raw["experiment"]["schedules"][0]["buffer"] = fixture.pool_of(raw, X=b)
    spec = fixture.parse_spec(raw)
    world, (schedule,) = spec.model.world, spec.experiment.schedules
    loc = next(i for i, p in enumerate(world.places) if p.name == "X@pool")
    before = np.zeros(spec.execution.place_capacity, dtype=np.int64)
    before[loc] = n
    withdrawal.refuse_beyond_capacity(world, schedule, before, spec.execution.molecule_capacity)
    buffer = withdrawal.buffer_vector(world, schedule, len(before))
    assert buffer[loc] == b
    return world, loc, fixture.pool_f_of(spec), before, buffer


def weighted_bookings(n, fraction):
    f = Fraction(fraction)
    q = Fraction(cutoff(float(f)), BINS)
    assert f == q and (n * f).denominator == 1
    b = int(n * f)
    world, loc, pool_f, before, buffer = pool_case(n, b, float(f))
    p = Decimal(f.numerator) / f.denominator
    taken = np.zeros_like(before)
    mean = engine_mean = entropy = Decimal(0)
    normalization = Fraction(0)
    max_error = {}
    for k in range(n + 1):
        taken[loc] = k
        receipt = withdrawal.booking(pool_f, before, taken, buffer, float(f), world)
        prob = mass(n, k, q)
        normalization += prob
        weight = Decimal(prob.numerator) / prob.denominator
        heat, split = surprisal(p, n - k, b), surprisal(p, n - k, k)
        check(receipt, {"mixing_heat_kT": heat, "split_surprisal_kT": split}, max_error)
        assert receipt["mixing_heat_kT"] <= receipt["split_surprisal_kT"] + float(TOL)
        if k == b:
            assert receipt["mixing_heat_kT"] == receipt["split_surprisal_kT"]
        mean += weight * heat
        engine_mean += weight * Decimal.from_float(receipt["mixing_heat_kT"])
        entropy += weight * split
    assert normalization == 1
    bound = Decimal(n + 1).ln()
    assert 0 < mean <= entropy <= bound and abs(mean - engine_mean) <= TOL
    return dict(parent=n, buffer=b, fraction=float(f), outcomes=n + 1, expected_heat_kT=float(mean),
                engine_heat_kT=float(engine_mean), split_entropy_nats=float(entropy),
                heat_per_molecule_kT=float(mean / n), upper_bound_per_molecule_kT=float(bound / n),
                max_abs_error_kT=max_error)


def population_receipt():
    """The normal runner withdraws from the three occupied finite places and records the heat."""
    raw = fixture.acceptance_spec(0.5).to_dict()
    raw["experiment"]["schedules"][0]["buffer"] = fixture.pool_of(raw, L=15, S=3, X=4)
    spec = fixture.parse_spec(raw)
    run = fixture.runner.run(spec).check()
    (record,) = run.population["withdrawals"]
    assert all(2 * record["supplied"][place] == n for place, n in record["before"].items())
    ref, _ = reference(standard_terms(spec.model.world), record["before"], record["withdrawn"], record["supplied"], 0.5)
    maxima = {}
    check(record, ref, maxima)
    assert 0 <= record["mixing_heat_kT"] <= record["split_surprisal_kT"] + float(TOL)
    return {k: record[k] for k in ("before", "withdrawn", "supplied", "mixing_heat_kT", "split_surprisal_kT")} | {
        "max_abs_error_kT": max(maxima.values())}


def unmatched_control():
    world, loc, pool_f, before, buffer = pool_case(4, 0, 0.5)
    taken = np.zeros_like(before)
    taken[loc] = 2
    receipt = withdrawal.booking(pool_f, before, taken, buffer, 0.5, world)
    excess = receipt["mixing_heat_kT"] - receipt["split_surprisal_kT"]
    assert abs(excess - math.log(1.5)) < float(TOL)
    return dict(parent=4, withdrawn=2, buffer=0, fraction=0.5, heat_minus_split_kT=excess)


if __name__ == "__main__":
    with localcontext() as ctx:
        ctx.prec = 88
        cases = [(n, 0.25) for n in (4, 20, 100, 400)] + [(8, 0.5), (20, 0.75), (16, 0.125)]
        results = dict(exact_mass_check=exact_count_check(), population=population_receipt(),
                       weighted_bookings=[weighted_bookings(n, f) for n, f in cases],
                       unmatched_control=unmatched_control())
    print(json.dumps(results, indent=2, allow_nan=False))
