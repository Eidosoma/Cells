"""Compiled runs of local_species_reactions@1 at milestone 1 (D152 version 1; design §4.5, §10.4).

The canonical enzyme network's species-only world (validation/tissue/species_reactions_fixtures),
through the runner, its compiled step and its host checks:
* idle claim 2: every multiplier zero gives every field, observation and diagnostic of the
  composition without the operator bitwise, with the operator's own fields all zero; a network
  with no reactions (statically idle) does the same;
* milestone 1 refuses any step with a positive multiplier: the compiled step returns invalid and
  the runner refuses the run.
At milestone 2 the same idle comparison runs on the real half-step, where it bites. A few compiles;
the tier-1 smoke tests are test_species_reactions.py and test_species_reactions_refusals.py.
"""

import copy

import jax
import numpy as np
import pytest

from cells.core.errors import NumericalError
from cells.core.runner import run
from cells.core.specs import parse_spec
from cells.models.operators import species_reactions
from validation.tissue import species_reactions_fixtures as rfx

jax.config.update("jax_enable_x64", True)

END = 0.004
ZERO = dict.fromkeys(("binding", "catalysis", "conversion", "supply", "removal"), 0.0)


def world(multipliers):
    return rfx.enzyme_network(multipliers, end=END, observation_times=[0.0, 0.002, END])


def bits(value):
    return np.asarray(value).tobytes()


def assert_same_as_plain(result, plain):
    for name in type(plain.history)._fields:
        assert bits(getattr(result.history, name)) == bits(getattr(plain.history, name)), name
    for name in species_reactions.STATE_AXES:
        assert not np.any(np.asarray(getattr(result.history, name))), name
    for name, value in vars(plain.observations).items():
        assert bits(getattr(result.observations, name)) == bits(value), name
    for name, value in plain.diagnostics.items():
        assert result.diagnostics[name] == value, name


def test_zero_multipliers_equal_the_composition_without_the_operator():
    raw = world(ZERO)
    plain = run(parse_spec(rfx.without_reactions(raw)))
    assert_same_as_plain(run(parse_spec(raw)), plain)
    empty = copy.deepcopy(raw)
    next(b for b in empty["model"]["operators"] if b["law"] == rfx.REACTIONS)["reactions"] = []
    empty["experiment"]["reaction_controls"] = []
    assert_same_as_plain(run(parse_spec(empty)), plain)


def test_milestone_1_refuses_a_step_with_a_positive_multiplier():
    with pytest.raises(NumericalError, match="no invalid step accepted"):
        run(parse_spec(world(dict(ZERO, supply=1.0))))
