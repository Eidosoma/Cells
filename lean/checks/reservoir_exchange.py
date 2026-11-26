"""Check uncatalyzed exchange rates and stochastic bookings in cells.model.assembly_lineages@1."""

import json
import math
from decimal import Decimal, localcontext
from fractions import Fraction
from itertools import product

import jax
import numpy as np

from cells.definitions.specs import parse_spec
from cells.models.assembly_lineages import MODEL_ID, balance, ledger, reference, runner
from tests.assembly_lineage_fixtures import definition, world
from validation.assembly_lineages.probes import rate_tables


def spec_for(founder, constants, supply, leave):
    raw = world(
        count=len(founder),
        size=12,
        matrix=False,
        transfer_constant=constants,
        supply=supply,
        leave_rate=leave,
    )
    raw["founder"] = founder
    return parse_spec(definition(raw, None, fissions=3, seed=1, uniforms=True))


def activities(spec):
    w = spec.model.world
    return [
        Fraction(k) * Fraction(r) for k, r in zip(w.types.transfer_constant, w.supply, strict=True)
    ]


def weight(counts, theta):
    """Exact unnormalized product weight. Weight one at extinction gives the ledger's zero log."""
    counts = [int(n) for n in counts]
    total = sum(counts)
    if total == 0:
        return Fraction(1)
    return math.factorial(total - 1) * math.prod(
        q**n / math.factorial(n) for n, q in zip(counts, theta, strict=True)
    )


def log_fraction(value):
    with localcontext() as ctx:
        ctx.prec = 65
        return float((Decimal(value.numerator) / Decimal(value.denominator)).ln())


def rate_grid(spec):
    """Every three-type composition through size eight, with reverse rates at the arrival state."""
    states = [n for n in product(range(9), repeat=3) if sum(n) <= 8]
    index = {n: i for i, n in enumerate(states)}
    rates = rate_tables(spec, states)
    joins, leaves = rates["join_rate"], rates["leave_rate"]
    ks, theta = [Fraction(k) for k in spec.model.world.leave_rate], activities(spec)
    want_join = [[float(k * q * sum(n)) for k, q in zip(ks, theta, strict=True)] for n in states]
    want_leave = [[float(k * c) for k, c in zip(ks, n, strict=True)] for n in states]
    for actual, wanted in ((joins, want_join), (leaves, want_leave)):
        np.testing.assert_allclose(actual, wanted, rtol=4 * np.finfo(float).eps, atol=0)
    weights = {n: weight(n, theta) for n in states}
    errors = []
    for n in states:
        if 0 < sum(n) < 8:
            for i in range(3):
                after = tuple(c + (j == i) for j, c in enumerate(n))
                heat = math.log(joins[index[n], i]) - math.log(leaves[index[after], i])
                errors.append(abs(heat - log_fraction(weights[after] / weights[n])))
    assert max(errors) <= balance.ATOL
    # Double the first species' activity at fixed composition, K and leave constants.
    w = spec.model.world
    double = spec_for(
        list(w.founder),
        list(w.types.transfer_constant),
        [2 * w.supply[0], *w.supply[1:]],
        list(w.leave_rate),
    )
    higher = rate_tables(double, states)
    np.testing.assert_array_equal(higher["join_rate"], joins * [2, 1, 1])
    np.testing.assert_array_equal(higher["leave_rate"], leaves)
    return dict(
        states=len(states),
        reversible_pairs=len(errors),
        max_heat_error_kT=max(errors),
        max_rate_error_per_nominal_time=float(
            max(np.max(abs(joins - want_join)), np.max(abs(leaves - want_leave)))
        ),
    )


def check_lineage(run, status):
    run.check()
    assert run.status == status and run.closure["holds"]
    oracle = reference.replay(run.spec, **run.diagnostics)
    assert oracle["status"] == status
    channels = np.asarray(run.trace["event_channel"])
    np.testing.assert_array_equal(channels, oracle["channel"])
    np.testing.assert_allclose(run.trace["event_time"], oracle["time"], rtol=2e-13, atol=0)

    rows = run.rows
    counts = rows["assembly_count"][:, :, 0]
    kinds = rows["row_kind"]
    theta = activities(run.spec)
    if status == "complete":
        assert np.sum(kinds == runner.DAUGHTER) == run.spec.experiment.fissions
        np.testing.assert_array_equal(run.fissions["fission_split"], oracle["splits"])
        np.testing.assert_array_equal(run.fissions["fission_followed"], oracle["followed"])
        assert np.any(channels > 0) and np.any(channels < 0)
    else:
        assert counts[-1].sum() == 0 and channels[-1] < 0

    signed_types = np.arange(1, counts.shape[1] + 1)
    for field, sign in (("joined_total", 1), ("left_total", -1)):
        step = channels[:, None] == sign * signed_types
        cumulative = np.vstack((np.zeros_like(signed_types), step.cumsum(axis=0)))
        np.testing.assert_array_equal(rows[field][:, :, 0], cumulative[rows["row_event"]])
    np.testing.assert_array_equal(
        counts,
        counts[0] + (rows["joined_total"] - rows["left_total"] - rows["discarded_total"])[:, :, 0],
    )

    # Heat telescopes during growth. At fission, also book the discarded daughter's free energy.
    phi = [log_fraction(weight(n, theta)) for n in counts]
    heat, work, sink = 0.0, 0.0, 0.0
    wanted = []
    for i, kind in enumerate(kinds):
        if kind == runner.DAUGHTER:
            dropped = log_fraction(weight(counts[i - 1] - counts[i], theta))
            work += phi[i - 1] - phi[i] - dropped
            sink -= dropped
        elif i:
            heat += phi[i] - phi[i - 1]
        wanted.append([phi[i], heat, work, sink])
    fields = ["log_weight", "exchange_heat_kT", "fission_work_kT", "discarded_free_energy_kT"]
    booked = np.column_stack([rows[f][:, 0] for f in fields])
    np.testing.assert_allclose(booked, wanted, atol=ledger.RTOL, rtol=0)
    return dict(
        status=run.status,
        events=len(channels),
        rows=len(kinds),
        fissions=int(np.sum(kinds == runner.DAUGHTER)),
        final_heat_kT=float(rows["exchange_heat_kT"][-1, 0]),
        max_booking_error_kT=float(np.max(abs(booked - wanted))),
    )


def composition_example():
    cases = []
    for second_leave, expected in ((1.0, 0.0), (2.0, -0.25)):
        spec = spec_for([1, 1], 2.0, 0.5, [1.0, second_leave])
        rates = rate_tables(spec, [[1, 1]])
        drift = (rates["join_rate"] - rates["leave_rate"])[0]
        np.testing.assert_array_equal(drift, [1.0, second_leave])
        fraction_rate = (2 * drift[0] - drift.sum()) / 2**2
        assert fraction_rate == expected
        cases.append(
            dict(
                leave=[1.0, second_leave],
                count_drift=drift.tolist(),
                first_fraction_drift=fraction_rate,
            )
        )
    return cases


if __name__ == "__main__":
    if jax.default_backend() != "cpu" or not jax.config.x64_enabled:
        raise RuntimeError("Run with JAX_PLATFORMS=cpu and JAX_ENABLE_X64=1")
    growth = spec_for([2, 3, 1], [2.4, 2.3, 1.8], [0.25, 0.5, 0.5], [0.6, 1.4, 0.85])
    extinction = spec_for([0, 1, 0], [2.4, 2.3, 1.8], 2**-16, [0.6, 1.4, 0.85])
    growing, dying = runner.run_lanes([growth, extinction])
    print(
        json.dumps(
            dict(
                model=MODEL_ID,
                law=growth.model.world.exchange_law,
                grid=rate_grid(growth),
                growth=check_lineage(growing, "complete"),
                extinction=check_lineage(dying, "extinct"),
                mean_field=composition_example(),
            ),
            indent=2,
            allow_nan=False,
        )
    )
