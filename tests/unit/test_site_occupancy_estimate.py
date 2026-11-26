"""cells.operator.site_occupancy@1's share of the trace estimate (the external review's finding 1, 18 November 2026).

cells.execution.resources.trace_bytes sizes a run's stored trace from the model's working_size: the
values stored per accepted step, plus a margin (surface_pump.working_size). cells.operator.site_occupancy@1 owns six
arrays per population and two node-indexed energy arrays in every state row, so its share must count
them. On a fixed mesh, doubling the populations must raise the estimate by at least the six arrays
of each added population. The share must also cover every field the operator owns, so a field added
later without its share fails here.
"""

import copy

import jax
import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.execution.resources import trace_bytes
from cells.operators import OPERATORS
from cells.registry.models import get_model
from validation.tissue import site_occupancy_acceptance_fixtures as so

LAW = "cells.operator.site_occupancy@1"
PER_POPULATION = 6  # site_{free,bound}_increment, bound_net, internalised, work, energy_magnitude


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def copies(world, k):
    """The world with each population declared k times on its own patch (the mesh unchanged)."""
    out = copy.deepcopy(world)
    out["populations"] = [
        dict(copy.deepcopy(p), id=p["id"] if j == 0 else f"{p['id']}_{j}")
        for p in world["populations"]
        for j in range(k)
    ]
    return out


def spec_of(world):
    return parse_spec(so.build(world))


def share(spec):
    return OPERATORS[LAW].working_size(spec)


def owned(spec):
    """Every value the operator owns in one state row."""
    state, _ = get_model(spec.model).initial_values(spec)
    return sum(np.asarray(v).size for k, v in state._asdict().items() if k.startswith("site_"))


def test_doubled_populations_on_a_fixed_mesh_raise_the_estimate():
    world = so.registered("q5_inward")
    one, two = spec_of(copies(world, 1)), spec_of(copies(world, 2))
    added = len(two.model.operators[0].populations) - len(one.model.operators[0].populations)
    assert added == len(world["populations"]) > 0
    for field in ("capacity", "extracellular_capacity", "membrane_capacity"):
        assert getattr(one.execution, field) == getattr(two.execution, field)  # The same mesh.
    assert share(two) - share(one) >= PER_POPULATION * added
    steps = 100
    assert trace_bytes(two, steps) - trace_bytes(one, steps) >= 8 * PER_POPULATION * added * steps


def test_the_share_covers_every_owned_field():
    for world_id in ("q5_inward", "q1_fast", "q2_two_populations"):
        for k in (1, 3):
            spec = spec_of(copies(so.registered(world_id), k))
            assert share(spec) >= owned(spec), (world_id, k)
