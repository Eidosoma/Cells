"""Planted defects of cells.operator.species_regulated_availability@1: the qualification protocol's order controls.

docs/INVENTORY_COUPLING_DESIGN.md §10 (milestone 4). Each control is a deliberately wrong copy of
the operator that must lower the observed order the protocol judges (the lead's ruling, 14
November 2026). They are controls, not physics: they live here, under their own law IDs, and enter
the engine's operator registry only inside `registered(...)`, for one control run; nothing in
src/cells knows them.

* `first_order_state` (cells.operator.control_first_order_state@1): the regulatory state's half-steps by
  explicit Euler, s' = s + h (k_on u (1 - s) - k_off s), in place of the exact two-state solution:
  two Euler halves per step are first order in s.
* `lagged_factor` (cells.operator.control_lagged_factor@1): the factors read the regulatory state from the start
  of the previous step (one step stale), in place of the state after the first half-steps.

`as_control(raw, kind)` gives a definition the control's law; `registered(kind)` adds the control
to the registry for the duration of a `with` block and removes it after.
"""

import contextlib
import copy
from dataclasses import replace

from cells.operators import OPERATORS
from cells.operators import species_regulated_availability as sra
from cells.operators.contract import check_declarations


class _Control(sra.SpeciesRegulatedAvailability):
    """The operator under another law ID: parsed and serialised as the operator is."""

    def parse(self, raw, base, inner_model):
        declaration = sra.parse_declaration(dict(raw, law=sra.LAW_ID), base)
        return replace(declaration, law=self.LAW_ID)


class FirstOrderState(_Control):
    LAW_ID = "cells.operator.control_first_order_state@1"
    STEP_ID = "control_explicit_euler_half_steps@1"

    def half_step(self, state, h, control, p, *, xp):
        if p.regulatory_slot_cell.shape[0] == 0:
            return state, None
        u = sra.state_inputs(state, p, xp=xp)
        s = state.regulatory_state
        new_s = s + h * (p.regulatory_on_rate * u * (1.0 - s) - p.regulatory_off_rate * s)
        total = state.regulatory_input_integral + u * h
        valid = xp.all(xp.isfinite(new_s) & (new_s >= 0) & (new_s <= 1))
        valid &= xp.all(xp.isfinite(total))
        return state._replace(regulatory_state=new_s, regulatory_input_integral=total), valid


class LaggedFactor(_Control):
    LAW_ID = "cells.operator.control_lagged_factor@1"
    STATE_AXES = {
        **sra.STATE_AXES,
        "control_held_state": ["regulatory_slot"],  # s at the latest step start.
        "control_lagged_state": ["regulatory_slot"],  # s at the step start before it.
    }

    def initial_values(self, spec, declaration, schedule, inner_state, inner_layout):
        state, layout = sra.bind(spec, declaration, schedule)
        state["control_held_state"] = state["regulatory_state"].copy()
        state["control_lagged_state"] = state["regulatory_state"].copy()
        return state, layout

    def event(self, state, control, p, *, xp):
        state, ok = sra.event_map(state, control, p, xp=xp)
        return state._replace(
            control_lagged_state=state.control_held_state,
            control_held_state=state.regulatory_state,
        ), ok

    def control_factors(self, state, p, *, xp):
        if state is not None and p.regulatory_slot_cell.shape[0] > 0:
            state = state._replace(regulatory_state=state.control_lagged_state)
        return super().control_factors(state, p, xp=xp)


CONTROLS = {"first_order_state": FirstOrderState, "lagged_factor": LaggedFactor}


def law_of(kind):
    return CONTROLS[kind].LAW_ID


def as_control(raw, kind):
    """`raw` with the coupling operator's block under the control's law."""
    out = copy.deepcopy(raw)
    blocks = [b for b in out["model"]["operators"] if b["law"] == sra.LAW_ID]
    if len(blocks) != 1:
        raise ValueError("A control replaces exactly one cells.operator.species_regulated_availability@1 block")
    blocks[0]["law"] = law_of(kind)
    return out


@contextlib.contextmanager
def registered(kind):
    """The control in the operator registry for the block's duration, removed after."""
    law = law_of(kind)
    if law in OPERATORS:
        raise RuntimeError(f"{law} is already registered")
    OPERATORS[law] = check_declarations(CONTROLS[kind])()
    try:
        yield law
    finally:
        del OPERATORS[law]
