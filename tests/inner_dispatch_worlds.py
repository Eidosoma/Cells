"""Per-law dispatch steps bit for bit like today's catalogue (D172/D176; the note's §7.4): shared.

The implementation object's compiled checked step (only the declared laws' kernels traced)
against the module's own (today's dispatch over the full catalogue), from each world's initial
state, for a few steps: every state field of every step and every step's validity, bitwise. The
worlds: a heredity cell (Kir2.1 and NaV1.2, the Na/K pump only, no junction; ARS(2,2,2)), the
same without any pump, the gated sheet (junctions), the five-law padded release world (both
pumps, ARS(2,2,2)) and the RK4 single patch (all five laws). Probe P2 showed the channel half on
seven worlds; this is its guard in the engine, with the pumps and the junction law. The worlds
are split over three test files (test_inner_dispatch_steps*.py) so each fits a tier's cap.

Fix (A) (D273) is a static switch of the declared structure, set from the parsed topology where a
junction joins two capacitor components and one floats; the catalogue (no structure) cannot take
it. Such a world (CROSSING) is stepped with that switch off, after asserting that runs have it on.
"""

import dataclasses

import jax
import jax.numpy as jnp
import numpy as np

from cells.definitions.specs import parse_spec
from cells.execution.schedule import control_values
from cells.models import surface_pump_v3
from cells.registry.models import get_model
from validation.tissue import pump_water_fixtures as water_fixtures
from validation.tissue import surface_pump_v3_fixtures as fixtures

ARS = "cells.solver.imex_ars222_face_electromigration@1"
STEPS = 12
CROSSING = {"release": ("junction_0",)}  # Fix (A)'s worlds here; () for the others.


def without_pumps(raw):
    for membrane in raw["model"]["membranes"]:
        membrane["pump"] = None
    raw["experiment"]["pump_controls"] = []
    return raw


WORLDS = {
    "heredity_D": lambda: water_fixtures.heredity_cell("D", end_time=0.02),
    "heredity_D_no_pumps": lambda: without_pumps(water_fixtures.heredity_cell("D", end_time=0.02)),
    "gated_sheet": lambda: water_fixtures.gated_sheet(end_time=0.02),
    "release": lambda: fixtures.definition("release", solver=ARS),
    "rk4_single_patch": lambda: fixtures.single_patch(),
}


def same_bits(a, b):
    a, b = np.atleast_1d(np.asarray(a)), np.atleast_1d(np.asarray(b))
    if a.shape != b.shape or a.dtype != b.dtype:
        return False
    if a.dtype.kind == "f":
        return np.array_equal(a.view(np.uint8), b.view(np.uint8))
    return np.array_equal(a, b)


def check_world(name):
    """STEPS compiled steps of the declared dispatch against today's catalogue, bitwise."""
    spec = parse_spec(WORLDS[name]())
    impl = get_model(spec.model)
    state, p = impl.initial_values(spec)
    assert impl.structure.crossing_junctions == CROSSING.get(name, ()), name
    if impl.structure.crossing_junctions:  # Fix (A) off: the catalogue cannot take it.
        off = dataclasses.replace(impl.structure, crossing_junctions=())
        impl = surface_pump_v3.implementation(off)
    controls = control_values(spec, [0.0])
    control = type(controls)(*(np.asarray(v[0]) for v in controls))
    state, control, p = jax.tree.map(jnp.asarray, (state, control, p))
    dt = jnp.asarray(spec.execution.dt)
    mine = jax.jit(lambda s: impl.checked_step(s, dt, control, p, p.active))
    today = jax.jit(lambda s: surface_pump_v3.checked_step(s, dt, control, p, p.active))
    a = b = state
    for step in range(STEPS):
        a, ok_a = mine(a)
        b, ok_b = today(b)
        assert bool(ok_a) == bool(ok_b), step
        for key, x, y in zip(type(a)._fields, a, b, strict=True):
            assert same_bits(x, y), (name, step, key)
    assert bool(ok_a)
