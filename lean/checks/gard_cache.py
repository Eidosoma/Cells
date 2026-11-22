"""GARD v2. Compare the two-word cache with integer-exact row sums and the public host."""

import argparse
import json
import math
from fractions import Fraction

import jax
import jax.numpy as jnp
import numpy as np
from gard_catalysis import check_reverse_subtraction

from cells.definitions.specs import ConfigError, parse_spec
from cells.models.assembly_lineages import gard, runner
from tests.assembly_lineage_fixtures import definition, world
from validation.gard.references import kernels

LAW = gard.GARD_PAIR_CONSISTENT_V2


def make_world(beta, capacity, founder, leave=1.0):
    raw = world(count=2, size=capacity, beta=beta, transfer_constant=1, supply=1, leave_rate=leave)
    raw["founder"] = list(founder)
    return parse_spec(definition(raw, LAW, fissions=2, molecules=capacity, uniforms=True))


def exact_rows(beta, counts):
    return [sum(Fraction(v) * int(n) for v, n in zip(row, counts, strict=True)) for row in beta]


def check_words(cache, expected):
    highs, lows = np.asarray(cache)
    for high, low, value in zip(highs, lows, expected, strict=True):
        assert high == float(value) and Fraction(high) + Fraction(low) == value


def state(n, d):
    return gard.state_exact(n, d, jnp)


def update(cache, d, i, sign):
    return gard.update_exact(cache, d, i, sign, jnp)


def factors(n, cache, d):
    return gard.factors_exact(n, n.sum(), cache, d, jnp)


state_jit, update_jit, factors_jit = jax.jit(state), jax.jit(update), jax.jit(factors)


def walk(beta, capacity, start, moves, *, parse_world=True):
    if parse_world:
        make_world(beta, capacity, start)
    d = gard.layout_exact({gard.FIELD: beta}, 2)
    counts = np.array(start, dtype=np.float64)
    cache = state_jit(counts, d)
    check_words(cache, exact_rows(beta, counts))
    max_scalar_ulp_difference = 0
    for i, sign in moves:
        before = counts.copy()
        counts[i] += sign
        assert (counts >= 0).all() and counts.sum() <= capacity
        next_cache = update_jit(cache, d, i, float(sign))
        check_words(next_cache, exact_rows(beta, counts))
        fresh = state_jit(counts, d)
        assert np.asarray(fresh).tobytes() == np.asarray(next_cache).tobytes()
        np.testing.assert_array_equal(fresh, gard.state_exact(counts, d, np))
        if sign == 1:
            parent, child, pcache, ccache = before, counts, cache, next_cache
        else:
            parent, child, pcache, ccache = counts, before, next_cache, cache
        join = float(factors_jit(parent, pcache, d)[0][i])
        leave = float(factors_jit(child, ccache, d)[1][i])
        assert join == leave
        # Pair equality is bitwise. Compare absolute factors independently at the two
        # rounding points for 1 + hi/N, without assuming a compiler evaluation order.
        size = int(parent.sum())
        high = Fraction(float(exact_rows(beta, parent)[i]))
        ratio = high / size if size else Fraction(0)
        separate, combined = 1.0 + float(ratio), float(1 + ratio)
        assert join in (separate, combined)
        bits = np.asarray([join, separate], dtype=np.float64).view(np.uint64)
        max_scalar_ulp_difference = max(max_scalar_ulp_difference, abs(int(bits[0]) - int(bits[1])))
        cache = next_cache
    return dict(
        entry_point="parsed world and cache functions" if parse_world else "cache functions",
        capacity=capacity,
        row_bits=[gard.bits_needed(row, capacity) for row in beta],
        signed_updates=len(moves),
        exact_refolds=len(moves) + 1,
        max_factor_difference_from_separate_rounding_ulps=max_scalar_ulp_difference,
    )


def within_range():
    path = [(0, 1), (1, 1), (0, -1), (1, -1), (1, -1), (0, 1), (1, 1), (0, -1)]
    boundary_beta = [[2.0**102, 1.0], [0.0, 1.0]]
    boundary = walk(boundary_beta, 8, (0, 1), path)
    assert boundary["row_bits"][0] == 106
    rejected = [[2.0**103, 1.0], [0.0, 1.0]]
    try:
        make_world(rejected, 8, (0, 1))
    except ConfigError as err:
        assert "107 bits" in str(err) and "106-bit" in str(err)
    else:
        raise AssertionError("The 107-bit row was accepted")
    split = [[math.nextafter(2, 0), 2.0**-15], [math.nextafter(1, 0), 0.25]]
    moves = [(0, 1), (0, -1), (1, -1), (1, 1)]
    admitted = walk(split, 4096, (4094, 1), moves)
    large = walk(split, 2**20, (2**20 - 1, 0), [(0, 1), (0, -1)], parse_world=False)
    ordinary = walk([[2.0**54, 1.0], [0.25, 0.5]], 8, (0, 1), path)
    stress = check_reverse_subtraction(LAW, 2**54, 1)
    assert stress["passed"] and stress["heat_kT"] == 0
    return dict(
        stress=stress,
        mixed_scales=ordinary,
        budget_boundary=boundary,
        refused_row_bits=107,
        admitted_count=admitted,
        count_limit_component=large,
    )


def exponent_case(exponent):
    beta = [[2.0**exponent, 0.0], [0.0, 0.0]]
    counts = (2, 1)
    rate = Fraction(1, 2**1000)
    oracle = kernels.ExactLaw.make(
        beta, rate, rate, kernels.PAIR_CONSISTENT, rho=1, boundary=kernels.EXTINCTION_UNCATALYSED
    )
    joins, leaves = oracle.propensities(counts)
    total = float(sum(joins + leaves))
    assert math.isfinite(total) and total > 0
    answer = dict(
        exponent=exponent,
        row_bits=gard.bits_needed(beta[0], 8),
        exact_total_propensity_rounded=total,
    )
    try:
        spec = make_world(beta, 8, counts, leave=[float(rate)] * 2)
    except ConfigError as err:
        return answer | dict(parse="refused", reason=str(err), passed=True)
    d = gard.layout_exact({gard.FIELD: beta}, 2)
    n = np.asarray(counts, dtype=float)
    with np.errstate(over="ignore", invalid="ignore"):
        host = gard.state_exact(n, d, np)
    compiled = np.asarray(state_jit(n, d))
    run = runner.run(spec, stop=1)
    times = np.asarray(run.trace["event_time"])
    finite_cache = bool(np.isfinite(compiled).all() and np.isfinite(host).all())
    if finite_cache:
        check_words(host, exact_rows(beta, n))
        check_words(compiled, exact_rows(beta, n))
    passed = finite_cache and len(times) == 1 and bool(np.isfinite(times[0]) and times[0] > 0)
    return answer | dict(
        parse="admitted",
        numpy_cache=[float(v).hex() for v in host[:, 0]],
        compiled_cache=[float(v).hex() for v in compiled[:, 0]],
        run_status=run.status,
        events=len(times),
        ledger_holds=bool(run.closure["holds"]),
        passed=passed,
    )


def tiny_tick():
    tick = math.ulp(0.0)
    beta = [[0.0, tick], [0.0, 0.0]]
    try:
        make_world(beta, 8, (0, 1))
    except ConfigError as err:
        return dict(parse="refused", reason=str(err), passed=True)
    d = gard.layout_exact({gard.FIELD: beta}, 2)
    n = np.array([0.0, 1.0])
    host = np.asarray(gard.state_exact(n, d, np))
    compiled = np.asarray(state_jit(n, d))
    return dict(
        parse="admitted",
        row_bits=gard.bits_needed(beta[0], 8),
        exact_high=tick.hex(),
        numpy_high=float(host[0, 0]).hex(),
        compiled_high=float(compiled[0, 0]).hex(),
        passed=bool(host[0, 0] == compiled[0, 0] == tick and host[1, 0] == compiled[1, 0] == 0),
    )


def explicit_capacity(size):
    """The fission and molecule limits both include this size. Only parse the definition."""
    beta = [[1.0, 0.0], [0.0, 1.0]]
    try:
        make_world(beta, size, (1, 1))
    except ConfigError as err:
        return dict(
            size=size,
            row_bits=gard.bits_needed(beta[0], size),
            parse="refused",
            reason=str(err),
            passed=False,
        )
    return dict(size=size, row_bits=gard.bits_needed(beta[0], size), parse="admitted", passed=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--range",
        action="store_true",
        help="check exponent handling and explicit molecule capacity at the public parser",
    )
    args = parser.parse_args()
    jax.config.update("jax_enable_x64", True)
    if jax.default_backend() != "cpu":
        raise RuntimeError("The comparison uses CPU float64")
    if args.range:
        result = dict(
            finite_control=exponent_case(1022),
            overflow=exponent_case(1023),
            smallest_tick=tiny_tick(),
            capacity_control=explicit_capacity(4096),
            explicit_capacity=explicit_capacity(4097),
        )
        assert (
            result["finite_control"]["parse"] == "admitted" and result["finite_control"]["passed"]
        )
        print(json.dumps(result, indent=2, allow_nan=False))
        raise SystemExit(0 if all(row["passed"] for row in result.values()) else 1)
    print(json.dumps(within_range(), indent=2, allow_nan=False))
