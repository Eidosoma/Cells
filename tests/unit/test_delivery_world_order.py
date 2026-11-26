"""Door S's T5: the delivery world with its event-only bath schedule first or last (§7).

docs/SCOPED_COMPOSITION_DESIGN.md §4 and §7 (D176): disjoint changes and reads give the same bits
in either declared order when the numerical split order is kept. The bath schedule is the
delivery world's only event-only operator, so moving it from first to last keeps exchange and the
reactions, its split parts, in their order. Every state field and observation column is compared
bitwise by name (an operator's fields move with it in the composite's field order); the ledger
diagnostics within rounding, since the operators' ledger terms add in declared order. Two
compiles: not tier 1.
"""

import dataclasses

import jax
import numpy as np

from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from validation.tissue import delivery_fixtures as dfx

jax.config.update("jax_enable_x64", True)


def test_the_bath_schedule_first_or_last_gives_the_same_bits():
    first = run(parse_spec(dfx.delivery_world()))
    last = run(parse_spec(dfx.delivery_world(bath_last=True)))
    assert first.spec.model.operators[0].law == "cells.operator.scheduled_bath_composition@1"
    assert last.spec.model.operators[-1].law == "cells.operator.scheduled_bath_composition@1"
    assert set(first.history._fields) == set(last.history._fields)
    for name in first.history._fields:
        a, b = np.asarray(getattr(first.history, name)), np.asarray(getattr(last.history, name))
        assert a.tobytes() == b.tobytes(), name
    observed = {f.name for f in dataclasses.fields(first.observations)}
    assert observed == {f.name for f in dataclasses.fields(last.observations)}
    for name in observed:
        a = np.asarray(getattr(first.observations, name))
        b = np.asarray(getattr(last.observations, name))
        assert a.tobytes() == b.tobytes(), name
    assert set(first.diagnostics) == set(last.diagnostics)
    for name, value in first.diagnostics.items():
        assert np.isclose(value, last.diagnostics[name], rtol=1e-9, atol=1e-15), name
