"""Complete staged open-calcium physics with explicit reservoir closure.

These functions consume an already admitted numeric world. Actual reservoir
flags, complete parent rates and original energy owners cross every boundary.
Neither host cohort admission nor simulation-time advancement belongs here.
"""

from typing import NamedTuple

import jax
import jax.numpy as jnp

from cells.core.schedule import SurfaceCalciumControl
from cells.core.surface_calcium_energy_spec import Control as FuelControl
from cells.models import physiology_active_temperature_arrays as arrays
from cells.models import surface_calcium as calcium
from cells.models import surface_calcium_energy as fuel

CALCIUM = "resolved_open_calcium@1"
FUEL = "resolved_open_calcium_energy@1"
FAMILIES = (CALCIUM, FUEL)


class CalciumPhysicsStages(NamedTuple):
    ionic: object
    calcium: object
    reservoir: object

    def __call__(self, state, layout, control):
        ionic = self.ionic(state, layout, control)
        parent = self.calcium(state, layout, control, ionic)
        return self.reservoir(state, layout, control, parent)


class FuelPhysicsStages(NamedTuple):
    ionic: object
    calcium: object
    fuel: object
    reservoir: object

    def __call__(self, state, layout, control):
        ionic = self.ionic(state, layout, control)
        calcium_values = self.calcium(state, layout, control, ionic)
        parent = self.fuel(state, layout, control, calcium_values)
        return self.reservoir(state, layout, control, parent)


def _parent(state, layout, control, family):
    if family not in FAMILIES:
        raise ValueError("Open stages require an exact open calcium or finite-fuel family")
    model = arrays.IMPLEMENTATIONS[family]
    if (
        type(state) is not model.STATE_TYPE
        or type(layout) is not model.LAYOUT_TYPE
        or type(control) is not (FuelControl if family == FUEL else SurfaceCalciumControl)
    ):
        raise ValueError("Open stages require exact family state/layout/control")
    return model._adapter, model.parent_state(state), model.parent_layout(layout)


def ionic_stage(state, layout, control, *, family, xp=jnp):
    _, value, physical = _parent(state, layout, control, family)
    if family == FUEL:
        return arrays.fuel_ionic_stage(value, physical, control, xp=xp)
    return calcium.ionic_stage(value, control, physical, xp=xp)


def calcium_stage(state, layout, control, ionic, *, family, xp=jnp):
    _, value, physical = _parent(state, layout, control, family)
    if family == FUEL:
        return arrays.fuel_calcium_stage(value, physical, control, ionic, xp=xp)
    if type(ionic) is not calcium.IonicStage:
        raise ValueError("Open calcium completion requires its complete ionic prefix")
    return calcium.complete_ionic_stage(value, control, physical, ionic, xp=xp)


def fuel_stage(state, layout, control, calcium_values, *, family, xp=jnp):
    _, value, physical = _parent(state, layout, control, family)
    if family != FUEL or type(calcium_values) is not calcium.Values:
        raise ValueError("Open fuel completion requires its complete calcium prefix")
    return fuel.complete_calcium_stage(value, control, physical, calcium_values, xp=xp)


def reservoir_stage(state, layout, control, parent, *, family, xp=jnp):
    adapter, _, _ = _parent(state, layout, control, family)
    result = adapter.complete_parent_readouts(state, layout, parent, xp=xp)
    hydrolysis = synthesis = xp.zeros_like(layout.active, dtype=xp.float64)
    if family == FUEL:
        hydrolysis = parent.exchange.gross_hydrolysis_fmol_s
        synthesis = parent.exchange.gross_synthesis_fmol_s
    return arrays.CompactPhysics(
        result.field, result.derivative, result.valid, hydrolysis, synthesis
    )


def world_stages(family, *, xp=jnp):
    """Return pure complete stages, preserving original world ownership."""
    if family not in FAMILIES:
        raise ValueError("Open stages require an exact open calcium or finite-fuel family")
    stages = [
        lambda s, p, u: ionic_stage(s, p, u, family=family, xp=xp),
        lambda s, p, u, v: calcium_stage(s, p, u, v, family=family, xp=xp),
    ]
    if family == FUEL:
        stages.append(lambda s, p, u, v: fuel_stage(s, p, u, v, family=family, xp=xp))
    stages.append(lambda s, p, u, v: reservoir_stage(s, p, u, v, family=family, xp=xp))
    return arrays.WorldStages(
        family,
        lambda p, c, u: arrays.prepare_numeric_world(p, c, u, family=family, xp=xp),
        (FuelPhysicsStages if family == FUEL else CalciumPhysicsStages)(*stages),
        lambda s, p, u, h, v: arrays.check_physics_world(s, p, u, h, v, family=family, xp=xp),
    )


def compiled_world_stages(family):
    """Build lazy five/six-stage JAX candidates; backend memory needs qualification.

    Use only through the unjitted cohort orchestrator. Open-family CPU/GPU
    compilation and trajectories require separate evidence from pure stages.
    """
    stages = world_stages(family)
    return stages._replace(
        inputs=jax.jit(stages.inputs),
        physics=type(stages.physics)(*(jax.jit(fn) for fn in stages.physics)),
        checks=jax.jit(stages.checks),
    )
