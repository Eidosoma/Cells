"""D4: a kind's material slope joins the per-stage step rule (the FR-4/FR-5 note's §17).

A kind's `material_term` gives its material slope (1/s) per node at the stage's read amounts: a
neutral transporter's grows as a small node empties, so no definition-time bound follows it.
surface_pump_v3.material_rate adds the kinds' terms per node, and the IMEX step refuses at every
explicit stage where dt x its largest over cells and non-held outside nodes exceeds
EXPLICIT_STEP_BOUND, as membrane_rate's charge rule does. Planted slopes at twice the bound are
refused and at half of it admitted, at a cell and at a face-free compartment's free outside node;
a slope at a held bath is not counted; without a kind that declares the hook the rate is None, so
no program changes.
"""

import numpy as np

from cells.definitions.specs import parse_spec
from cells.models import surface_pump_v3
from cells.registry import kind_registry
from tests.unit.test_kind_rules import declaring, host_inputs, planted, registry

BOUND = surface_pump_v3.EXPLICIT_STEP_BOUND


def sloped(node, rate):
    """A planted kind whose material slope is `rate` (1/s) at node `node` (cells, then outside)."""

    def material_term(read, potentials, control, p, *, xp):
        size = p.active.size + p.outside_active.size
        return xp.where(xp.arange(size) == node, rate, 0.0)

    return planted("alpha", "alpha_block", material_term=material_term)


def stepped(kind, raw):
    """(the stage rate at the start, the step's validity) of raw under kind's registry."""
    with kind_registry.scope(registry(kind)):
        spec = parse_spec(raw)
        impl, state, p, control = host_inputs(spec)
        rate = impl.material_rate(state, control, p, xp=np, potentials=None)
        _, valid = impl.imex_step(state, spec.execution.dt, control, p, xp=np)
    return spec, p, rate, bool(valid)


def face_free():
    """FR-1's W world as a bare @3 definition: ecs_0, the compartment node, is a free node."""
    from validation.tissue import secreted_species_fixtures as fx

    raw = fx.face_free(end=0.004)
    m = raw["model"]
    m["id"] = "cells.model.resolved_pump_tissue@3"
    m.pop("inner_model")
    m.pop("operators")
    m["alpha_block"] = {"rate": 1.0}
    return raw


def test_a_slope_at_a_cell_refuses_the_step_above_the_bound():
    dt = declaring("alpha_block")["execution"]["dt"]
    for factor, accepted in ((0.5, True), (2.0, False)):
        _, _, rate, valid = stepped(sloped(0, factor * BOUND / dt), declaring("alpha_block"))
        assert valid == accepted, factor
        assert rate == factor * BOUND / dt


def test_a_slope_at_a_free_outside_node_counts_and_at_a_held_bath_does_not():
    dt = face_free()["execution"]["dt"]
    _, p, _, _ = stepped(sloped(0, 0.0), face_free())
    n = p.active.size  # Nodes: cells, then outside nodes.
    assert bool(surface_pump_v3.free_outside_nodes(p, xp=np)[1])  # ecs_0, the compartment's.
    for factor, accepted in ((0.5, True), (2.0, False)):
        _, _, rate, valid = stepped(sloped(n + 1, factor * BOUND / dt), face_free())
        assert valid == accepted and rate == factor * BOUND / dt, factor
    held = int(np.flatnonzero(p.reservoir & p.outside_active)[0])
    _, _, rate, valid = stepped(sloped(n + held, 1e6 / dt), face_free())
    assert valid and rate == 0.0  # A held bath's rows do not relax.


def test_without_the_hook_there_is_no_rate_and_no_program_change():
    kind = planted("alpha", "alpha_block")
    with kind_registry.scope(registry(kind)):
        spec = parse_spec(declaring("alpha_block"))
        impl, state, p, control = host_inputs(spec)
        assert impl.material_rate(state, control, p, xp=np) is None
