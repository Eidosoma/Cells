"""The direct-method kernel against the host oracle, with common random variates.

The kernel's events, splits and similarities equal the oracle's (reference.py: scalar arithmetic,
the rate factor recomputed at every event) for the exchange law alone and both GARD forms, under
both partitions and the uniform continuation, and for @2's exact cache (the oracle in rationals),
also on the Lean proofs project's stress world (beta_00 = 2^54). Saving the uniforms changes no
event.

Planted errors it must catch:
- the incremental catalysis state updated with beta's row instead of its column;
- the oracle reading the two uniforms the other way round (a biased channel choice);
- the oracle evaluating the other GARD form (the law's leave factor);
- @2's cache with its low word dropped (one word, as @1 keeps), which loses the catalyst B from
  A's leave on the stress world: the ledger fails to close.
"""

import dataclasses

import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.models.assembly_lineages import (
    GARD_PAIR_CONSISTENT,
    GARD_PAIR_CONSISTENT_V2,
    GARD_SINGLE_EVENT,
    balance,
    folds,
    gard,
    reference,
    runner,
)
from cells.registry import laws as law_registry
from tests.assembly_lineage_fixtures import definition, world

# The Lean proofs project's stress world: beta_00 = 2^54, and B catalyses A.
STRESS = [[2.0**54, 1.0], [0.0, 0.0]]

CASES = {
    "exchange alone": (dict(matrix=False), None),
    "single-event": ({}, GARD_SINGLE_EVENT),
    "pair-consistent": ({}, GARD_PAIR_CONSISTENT),
    "pair-consistent, exact cache": ({}, GARD_PAIR_CONSISTENT_V2),
    "pair-consistent, exact cache, beta_00 = 2^54": (
        dict(count=2, size=8, beta=STRESS),
        GARD_PAIR_CONSISTENT_V2,
    ),
    "binomial, uniform daughter": (
        dict(partition={"rule": "binomial", "probability": 0.5}, daughter="uniform", empty="other"),
        GARD_PAIR_CONSISTENT,
    ),
}


def _run(case, **kw):
    options, law = CASES[case]
    return runner.run(
        parse_spec(definition(world(**options), law, fissions=5, uniforms=True, **kw))
    )


def _oracle(run, spec=None):
    d = run.diagnostics
    return reference.replay(
        spec or run.spec, d["event_uniforms"], d["partition_uniforms"], d["continuation_uniform"]
    )


def _agrees(run, oracle):
    return (
        oracle["channel"] == run.trace["event_channel"].tolist()
        and np.allclose(oracle["time"], run.trace["event_time"], rtol=1e-12, atol=0)
        and np.array_equal(
            np.asarray(oracle["splits"]).reshape(-1, run.spec.model.world.types.count),
            run.fissions["fission_split"],
        )
        and oracle["followed"] == run.fissions["fission_followed"].tolist()
        and np.array_equal(
            np.asarray(oracle["similarity"]).reshape(-1, 2),
            run.fissions["fission_similarity"],
            equal_nan=True,
        )
        and oracle["status"] == run.status
    )


@pytest.mark.parametrize("case", sorted(CASES))
def test_kernel_matches_the_oracle(case):
    run = _run(case)
    assert len(run.fissions["fission_time"]) == 5 and run.status == "complete"
    assert _agrees(run, _oracle(run))


def test_a_swapped_draw_or_the_other_form_is_caught():
    run = _run("single-event")
    d = run.diagnostics
    swapped = reference.replay(
        run.spec, d["event_uniforms"][:, ::-1], d["partition_uniforms"], d["continuation_uniform"]
    )
    assert not _agrees(run, swapped)
    other = parse_spec(definition(world(), GARD_PAIR_CONSISTENT, fissions=5, uniforms=True))
    assert not _agrees(run, _oracle(run, other))


def test_a_row_for_column_update_is_caught():
    """The planted law is the single-event form with beta's row added in place of its column,
    registered in a scoped registry under its own ID (no edit to the family): the oracle, which
    recomputes beta n at every event, must disagree with its run."""

    def planted(x, data, i, sign, xp):
        return x + sign * data.matrix[i, :]

    law_registry.active()
    law = dataclasses.replace(gard.SINGLE_EVENT, law_id="tests.rate_factor.row_update@1", update=planted)
    with law_registry.scope(law_registry.BUILTIN.extended(law)):
        options, _ = CASES["single-event"]
        the_world = world(**options)
        run = runner.run(parse_spec(definition(the_world, law.law_id, fissions=5, uniforms=True)))
    honest = parse_spec(definition(the_world, GARD_SINGLE_EVENT, fissions=5, uniforms=True))
    assert run.status == "complete" and not _agrees(run, _oracle(run, honest))
    assert _agrees(_run("single-event"), _oracle(_run("single-event")))  # The honest law agrees.


def test_saving_the_uniforms_changes_no_event():
    options, law = CASES["pair-consistent"]
    plain = runner.run(parse_spec(definition(world(**options), law, fissions=5, uniforms=False)))
    saved = _run("pair-consistent")
    for name in ("event_time", "event_channel", "events_per_growth"):
        assert np.array_equal(plain.trace[name], saved.trace[name])
    for name, values in plain.rows.items():
        assert np.array_equal(values, saved.rows[name])
    assert plain.diagnostics == {} and set(saved.diagnostics) == {
        "event_uniforms",
        "partition_uniforms",
        "continuation_uniform",
    }


def test_the_exact_cache_keeps_the_reverse_factor():
    """@2 on the stress world from (A, B) = (0, 1): A's join carries 1 + 1/1 = 2, and its reverse
    from (1, 1) carries 1 + ((2^54 + 1) - 2^54)/1 = 2, so the first event's heat is the exchange
    law's and the ledger closes. Planted: the cache's low word dropped, which makes that reverse
    factor 1 (the catalyst lost, as in @1's single word): the ledger fails to close. A rate that
    is not finite is a fault, refused, never reported as a stall (the Lean proofs project's
    finding of 22 November 2026); a zero total with finite rates is a stall."""
    with pytest.raises(FloatingPointError, match="not a stall"):
        runner._refuse_a_fault_as_a_stall({"rates": np.array([np.nan, 1.0]), "events": 0})
    runner._refuse_a_fault_as_a_stall({"rates": np.zeros(4), "events": 3})
    the_world = world(count=2, size=8, beta=STRESS, transfer_constant=1.0, supply=1.0,
                      leave_rate=[1.0, 1 / 32])  # fmt: skip
    the_world["founder"] = [0, 1]
    layout = gard.layout_exact({gard.FIELD: STRESS}, 2)
    before, after = np.array([0.0, 1.0]), np.array([1.0, 1.0])
    join, _ = gard.factors_exact(before, 1.0, gard.state_exact(before, layout, np), layout, np)
    _, leave = gard.factors_exact(after, 2.0, gard.state_exact(after, layout, np), layout, np)
    assert join[0] == leave[0] == 2.0

    def dropped(cache, xp):
        return xp.stack((cache[0], xp.zeros_like(cache[1])))

    planted = dataclasses.replace(
        gard.PAIR_CONSISTENT_EXACT,
        law_id="tests.rate_factor.low_word_dropped@1",
        state=lambda n, d, xp, unroll=folds.UNROLL: dropped(gard.state_exact(n, d, xp, unroll), xp),
        update=lambda c, d, i, sign, xp: dropped(gard.update_exact(c, d, i, sign, xp), xp),
    )
    law_registry.active()
    try:
        runs = {}
        for law in (gard.PAIR_CONSISTENT_EXACT, planted):
            with law_registry.scope(law_registry.BUILTIN.extended(planted)):
                spec = parse_spec(definition(the_world, law.law_id, fissions=2, uniforms=True))
                runs[law.law_id] = runner.run(spec, stop=1)
    finally:
        balance.verdict.cache_clear()
    honest, broken = runs[GARD_PAIR_CONSISTENT_V2], runs[planted.law_id]
    for run in (honest, broken):  # The same first event: A joins.
        np.testing.assert_array_equal(run.trace["event_channel"], [1])
        np.testing.assert_array_equal(run.rows["assembly_count"][-1, :, 0], [1, 1])
    assert honest.closure["holds"] and not broken.closure["holds"]
