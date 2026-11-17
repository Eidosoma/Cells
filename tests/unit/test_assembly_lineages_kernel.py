"""The direct-method kernel against the host oracle, with common random variates.

The kernel's events, splits and similarities equal the oracle's (reference.py: scalar arithmetic,
the rate factor recomputed at every event) for the exchange law alone and both GARD forms, under
both partitions and the uniform continuation. Saving the uniforms changes no event.

Planted errors it must catch:
- the incremental catalysis state updated with beta's row instead of its column;
- the oracle reading the two uniforms the other way round (a biased channel choice);
- the oracle evaluating the other GARD form (the law's leave factor).
"""

import dataclasses

import numpy as np
import pytest

from cells.core.specs import parse_spec
from cells.models.assembly_lineages import (
    GARD_PAIR_CONSISTENT,
    GARD_SINGLE_EVENT,
    gard,
    kernel,
    reference,
    runner,
)
from tests.assembly_lineage_fixtures import definition, world

CASES = {
    "exchange alone": (dict(matrix=False), None),
    "single-event": ({}, GARD_SINGLE_EVENT),
    "pair-consistent": ({}, GARD_PAIR_CONSISTENT),
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


def test_a_row_for_column_update_is_caught(monkeypatch):
    def planted(x, data, i, sign, xp):
        return x + sign * data.matrix[i, :]

    kernel.program.cache_clear()
    runner._COMPILED.clear()
    law = dataclasses.replace(gard.SINGLE_EVENT, update=planted)
    monkeypatch.setattr(gard, "LAWS", (law, gard.PAIR_CONSISTENT))
    try:
        run = _run("single-event")
        assert not _agrees(run, _oracle(run))
    finally:
        kernel.program.cache_clear()
        runner._COMPILED.clear()


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
