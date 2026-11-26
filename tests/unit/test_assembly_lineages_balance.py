"""The kernel's local detailed-balance check, and P1's hand anchors (GARD_DESIGN §2.2).

P1: on the two-type square from n = (1, 1), only beta_11 nonzero, the cycle
+e1, +e2, -e1, -e2 has ln(forward / reverse rates) = 2 ln(1 + b/2) - ln(1 + b/3) - ln(1 + 2b/3)
under the preprint's single-event form of GARD's catalysis (0.012, 0.080, 0.113, 0.117 for
b = 1, 10, 100, 1000) and 0 under the pair-consistent form; the exchange constants cancel from any
cycle. The rates are the kernel's own (kernel.rates on the host).

Planted errors it must catch: the single-event kernel declared passive is refused; the anchors
fail for a factor that ignores the diagonal (both forms would then agree).
"""

import dataclasses
import math

import numpy as np
import pytest

from cells.definitions.specs import ConfigError
from cells.models.assembly_lineages import (
    GARD_PAIR_CONSISTENT,
    GARD_PAIR_CONSISTENT_V2,
    GARD_SINGLE_EVENT,
    balance,
    gard,
)
from cells.models.assembly_lineages.kernel import Layout, rates
from cells.registry import laws as law_registry

ANCHORS = {1.0: 0.012, 10.0: 0.080, 100.0: 0.113, 1000.0: 0.117}


def _layout(b):
    matrix = np.asarray([[b, 0.0], [0.0, 0.0]])
    return Layout(
        kf_rho=np.asarray([0.3, 0.7]),
        kb=np.asarray([1.1, 0.9]),
        log_theta=None,
        log_factorial=None,
        split_size=None,
        split_value=None,
        fission_limit=None,
        growth_limit=None,
        base_key=None,
        factor=gard.Matrix(matrix, np.diagonal(matrix).copy()),
    )


def _rate(law, layout, counts, channel):
    counts = np.asarray(counts, dtype=np.int64)
    state = law.state(counts.astype(np.float64), layout.factor, np)
    return rates(counts, np.int64(counts.sum()), layout, state, law, np)[channel]


def cycle(law, b):
    """ln(forward / reverse) around (1,1) -> (2,1) -> (2,2) -> (1,2) -> (1,1)."""
    lay = _layout(b)
    join1, join2, leave1, leave2 = 0, 1, 2, 3
    forward = [((1, 1), join1), ((2, 1), join2), ((2, 2), leave1), ((1, 2), leave2)]
    reverse = [((1, 1), join2), ((1, 2), join1), ((2, 2), leave2), ((2, 1), leave1)]
    return sum(math.log(_rate(law, lay, n, c)) for n, c in forward) - sum(
        math.log(_rate(law, lay, n, c)) for n, c in reverse
    )


@pytest.mark.parametrize("b", sorted(ANCHORS))
def test_p1_anchors(b):
    closed = 2 * math.log(1 + b / 2) - math.log(1 + b / 3) - math.log(1 + 2 * b / 3)
    single = cycle(gard.SINGLE_EVENT, b)
    assert abs(single - closed) < 1e-12 and round(single, 3) == ANCHORS[b]
    assert abs(cycle(gard.PAIR_CONSISTENT, b)) < 1e-14
    blind = dataclasses.replace(  # Planted: a factor without the diagonal's self-catalysis.
        gard.SINGLE_EVENT,
        factors=lambda n, s, x, d, xp: gard.factors_single_event(n, s, x - d.diagonal * n, d, xp),
    )
    assert abs(cycle(blind, b) - closed) > 1e-3


def test_the_check_admits_pair_consistent_as_passive_and_refuses_single_event_as_passive():
    assert balance.verdict(GARD_PAIR_CONSISTENT)["local_detailed_balance"] == "holds"
    assert balance.verdict(GARD_PAIR_CONSISTENT_V2)["local_detailed_balance"] == "holds"
    assert balance.verdict(None)["local_detailed_balance"] == "holds"  # Exchange alone.
    single = balance.verdict(GARD_SINGLE_EVENT)
    assert single["local_detailed_balance"] == "fails" and single["admitted_as"] == "driven"
    assert single["probe"]["max_abs_deviation_ln"] > 1e-3
    # Planted: the single-event form declared passive, registered in a scope under its own ID.
    law_registry.active()
    planted = dataclasses.replace(
        gard.SINGLE_EVENT,
        law_id="tests.rate_factor.single_event_as_passive@1",
        energy_role="passive",
    )
    try:
        with law_registry.scope(law_registry.BUILTIN.extended(planted)):
            with pytest.raises(ConfigError, match="Refused as passive"):
                balance.verdict(planted.law_id)
    finally:
        balance.verdict.cache_clear()


def test_uniform_catalysis_passes_both_forms_so_the_verdict_uses_its_own_probe():
    """With beta = c everywhere, b = 1 + c in both directions: the single-event form satisfies
    the identity on such data, which is why the verdict is taken on generic probe data."""
    rng = np.random.default_rng(5)
    layout = balance._layout(np.full(3, 2.0), np.full(3, 0.2), np.ones(3), None)
    matrix = np.full((3, 3), 4.0)
    layout = layout._replace(factor=gard.Matrix(matrix, np.diagonal(matrix).copy()))
    found = balance.deviations(gard.SINGLE_EVENT, layout, rng, states=50)
    assert np.max(np.abs(found)) < balance.ATOL
