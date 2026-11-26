"""Check both GARD factors against exact edge and cycle rates in cells.model.assembly_lineages@1."""

import argparse
import json
import math
from fractions import Fraction

import jax
import numpy as np

from cells.definitions.specs import parse_spec
from cells.models.assembly_lineages import balance, factors, reference, runner
from tests.assembly_lineage_fixtures import definition, world
from validation.assembly_lineages.probes import forms, rate_tables
from validation.gard.references import detailed_balance, kernels

MATRICES = {
    "raw_rank_one": [[1, 0], [0, 0]],
    "shifted_rank_one": [[0, 1], [1, 3]],  # 1 + beta = (1,2) (1,2)^T entrywise.
    "asymmetric": [[2, 5], [0.5, 1]],
}


def make_spec(law, beta, *, founder=(2, 2), leave=(1, 1)):
    raw = world(
        count=2, size=8, matrix=False, transfer_constant=1, supply=1, leave_rate=list(leave)
    )
    raw.update(founder=list(founder), law_data={"catalysis_matrix": beta})
    return parse_spec(definition(raw, law, fissions=2, seed=1, uniforms=True))


def compare_grid(law, beta, case):
    form = law.form
    boundary = (
        kernels.EXTINCTION if form == kernels.SINGLE_EVENT else kernels.EXTINCTION_UNCATALYSED
    )
    exact = kernels.ExactLaw.make(beta, 1, 1, form, rho=1, boundary=boundary)
    states = [(a, total - a) for total in range(9) for a in range(total + 1)]
    result = rate_tables(make_spec(law.law_id, beta), states)
    joins, leaves = result["join_rate"], result["leave_rate"]
    index = {n: i for i, n in enumerate(states)}
    expected = np.asarray([exact.propensities(n) for n in states], dtype=float)
    for rates, target in ((joins, expected[:, 0]), (leaves, expected[:, 1])):
        np.testing.assert_allclose(rates, target, atol=0, rtol=4 * np.finfo(float).eps)

    edges = {}
    weight_errors, rate_errors, shifted_errors = [], [], []
    for n in states:
        if 0 < sum(n) < 8:
            for i in range(2):
                m = (n[0] + (i == 0), n[1] + (i == 1))
                edges[n, i] = joins[index[n], i] / leaves[index[m], i]
                heat = math.log(joins[index[n], i]) - math.log(leaves[index[m], i])
                ratio = exact.propensities(n)[0][i] / exact.propensities(m)[1][i]
                base_ratio = exact.weight(m) / exact.weight(n)
                rate_errors.append(abs(heat - math.log(ratio)))
                weight_errors.append(abs(heat - math.log(base_ratio)))
                if form == kernels.SINGLE_EVENT and case == "shifted_rank_one":
                    # The two column weights of 1 + beta are v=(1,2).
                    mean_n = Fraction(n[0] + 2 * n[1], sum(n))
                    mean_m = Fraction(m[0] + 2 * m[1], sum(m))
                    shifted_errors.append(abs(heat - math.log(base_ratio * mean_n / mean_m)))
    assert max(rate_errors) <= balance.ATOL
    if form == kernels.PAIR_CONSISTENT:
        assert max(weight_errors) <= balance.ATOL
    if shifted_errors:
        assert max(shifted_errors) <= balance.ATOL and max(weight_errors) > 0.01

    ratios = []
    for a, b in states:
        if 0 < a + b <= 6:
            n = (a, b)
            square = edges[n, 0] * edges[(a + 1, b), 1] / (edges[(a, b + 1), 0] * edges[n, 1])
            target = detailed_balance.square_cycle_ratio(exact, n)
            np.testing.assert_allclose(square, float(target), rtol=2e-15, atol=0)
            if form == kernels.PAIR_CONSISTENT or case == "shifted_rank_one":
                assert target == 1
            if n == (1, 1) and form == kernels.SINGLE_EVENT and case == "raw_rank_one":
                assert target == Fraction(81, 80)
            ratios.append(square)
    return dict(
        states=len(states),
        edges=len(edges),
        squares=len(ratios),
        square_at_1_1=str(detailed_balance.square_cycle_ratio(exact, (1, 1))),
        max_edge_error_kT=max(rate_errors),
        max_difference_from_base_kT=max(weight_errors),
        max_shifted_weight_error_kT=max(shifted_errors, default=None),
    )


def compare_lineage(law):
    run = runner.run(make_spec(law.law_id, MATRICES["asymmetric"])).check()
    replay = reference.replay(run.spec, **run.diagnostics)
    assert run.status == replay["status"] == "complete"
    np.testing.assert_array_equal(run.trace["event_channel"], replay["channel"])
    np.testing.assert_allclose(run.trace["event_time"], replay["time"], rtol=2e-13, atol=0)
    passive = law.form == kernels.PAIR_CONSISTENT
    assert run.closure["checked"] == passive and run.closure["holds"] == passive
    return dict(
        events=len(replay["channel"]),
        fissions=len(replay["splits"]),
        max_ledger_residual_kT=run.closure["max_abs_residual_kT"],
    )


def check_reverse_subtraction(law_id, diagonal, other):
    beta = [[diagonal, other], [0, 0]]
    spec = make_spec(law_id, beta, founder=(0, 1), leave=(1, 1 / 32))
    rates = rate_tables(spec, [(0, 1), (1, 1)])
    run = runner.run(spec, stop=1)
    np.testing.assert_array_equal(run.trace["event_channel"], [1])
    np.testing.assert_array_equal(run.rows["assembly_count"][-1, :, 0], [1, 1])
    # Only the stationary B molecule is a catalyst on either side of this A edge.
    factor = float(1 + Fraction(other))
    forward, reverse = float(rates["g_join"][0, 0]), float(rates["g_leave"][1, 0])
    assert forward == factor
    return dict(
        diagonal=diagonal,
        other=other,
        expected_factor=factor,
        join_factor=forward,
        reverse_factor=reverse,
        expected_heat_kT=0,
        heat_kT=float(run.rows["exchange_heat_kT"][-1, 0]),
        status=run.status,
        ledger=run.closure["refused"],
        passed=bool(reverse == factor and run.status == "stopped" and run.closure["holds"]),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--controls-only", action="store_true", help="omit the two cancellation stress cases"
    )
    args = parser.parse_args()
    if jax.default_backend() != "cpu" or not jax.config.x64_enabled:
        raise RuntimeError("Run with JAX_PLATFORMS=cpu and JAX_ENABLE_X64=1")
    comparisons = {}
    for name, law_id in forms().items():
        law = factors.resolve(law_id)
        comparisons[name] = {key: compare_grid(law, beta, key) for key, beta in MATRICES.items()}
        comparisons[name]["lineage"] = compare_lineage(law)
    cases = [(2, 1), (2**54, 0)]
    if not args.controls_only:
        cases.extend([(2**21, 2**-32), (2**54, 1)])
    stress = [check_reverse_subtraction(forms()["pair_consistent"], a, b) for a, b in cases]
    print(
        json.dumps(
            dict(comparisons=comparisons, reverse_subtraction=stress), indent=2, allow_nan=False
        )
    )
    raise SystemExit(0 if all(row["passed"] for row in stress) else 1)
