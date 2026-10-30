"""Map explicit native block factors onto complete ordinary physical RHS views.

The source membrane-indexed junction buffer needs declared contact pairs. Both
sides must agree; asymmetric native factors are not averaged into a physical
edge. Global factors multiply the caller's unchanged scheduled controls once.
"""

import math
from dataclasses import dataclass, replace
from numbers import Real
from typing import NamedTuple

import numpy as np

from cells.core import physiology_tissue_binding as units
from cells.core.errors import NumericalError
from cells.models import physiology_permeability_view as permeability
from cells.processes import betse_global_controls as source

KIND = "cells.physiology_block_control_binding@1"


@dataclass(frozen=True, slots=True)
class Binding:
    source_definition_sha256: str
    tissue_binding_identity: str
    program: source.Program
    junction_membranes: tuple  # (junction ID, sender membrane ID, receiver membrane ID).
    provenance: str
    identity: str


class BlockState(NamedTuple):
    junction_available: object
    pump_available: object


class PreparedControl(NamedTuple):
    block_state: BlockState
    base_control: object
    effective_control: object
    source_values: object
    binding_identity: str
    event_time_s: float
    events_enabled: bool


class BlockView(NamedTuple):
    preparation: PreparedControl
    physical: object


class BlockControlRejected(NumericalError):
    def __init__(self, reason, trial):
        super().__init__(reason)
        self.trial = permeability._immutable_tree(trial)


def record(binding):
    if type(binding) is not Binding:
        raise ValueError("Require a complete typed block-control binding")
    payload = dict(
        kind=KIND,
        source_definition_sha256=binding.source_definition_sha256,
        tissue_binding_identity=binding.tissue_binding_identity,
        program=source.record(binding.program),
        junction_membranes=[list(row) for row in binding.junction_membranes],
        provenance=binding.provenance,
    )
    return payload | dict(identity=units._digest(payload))


def _has_pump_owners(spec):
    return any(getattr(row, "pump", None) is not None for row in spec.model.membranes)


def bind(spec, tissue_binding, program, *, junction_membrane_ids, provenance):
    units.restore_binding(units.binding_record(tissue_binding), spec)
    source.validate(program)
    if program.membrane_ids != tissue_binding.component.membrane_ids:
        raise ValueError("Global block axes must match the complete component membrane order")
    if any(row.kind not in ("junction_block", "pump_block") for row in program.events):
        raise ValueError("Temperature/voltage changes require separate thermal/electrode work")
    if any(row.kind == "pump_block" for row in program.events) and not _has_pump_owners(spec):
        raise ValueError("Pump blocking requires actual Na/K pump owners")
    if type(provenance) is not str or not provenance.strip():
        raise ValueError("Declare the source of the physical contact mapping")
    if type(junction_membrane_ids) is not dict or set(junction_membrane_ids) != {
        row.id for row in spec.model.junctions
    }:
        raise ValueError("Declare exactly one membrane pair per physical junction")
    membranes = {row.id: row for row in spec.model.membranes}
    pairs, used = [], set()
    for edge in spec.model.junctions:
        pair = junction_membrane_ids[edge.id]
        if (
            not isinstance(pair, (tuple, list))
            or len(pair) != 2
            or any(type(x) is not str or x not in membranes for x in pair)
            or pair[0] == pair[1]
            or any(x in used for x in pair)
        ):
            raise ValueError("Contact pairs require distinct, exclusive actual membranes")
        if (membranes[pair[0]].inside, membranes[pair[1]].inside) != (edge.sender, edge.receiver):
            raise ValueError("Contact membrane owners must match the actual junction endpoints")
        used.update(pair)
        pairs.append((edge.id, *pair))
    result = Binding(
        tissue_binding.source_definition_sha256,
        tissue_binding.identity,
        program,
        tuple(pairs),
        provenance,
        "",
    )
    return replace(result, identity=record(result)["identity"])


def restore(saved, spec, tissue_binding):
    if type(saved) is not dict or saved.get("kind") != KIND:
        raise ValueError("Require the complete saved block binding")
    try:
        program = source.restore(saved["program"], expected_identity=saved["program"]["identity"])
        rows = saved["junction_membranes"]
        mapping = {row[0]: tuple(row[1:]) for row in rows}
        if len(mapping) != len(rows):
            raise ValueError("Duplicate saved contact mapping")
        expected = bind(
            spec,
            tissue_binding,
            program,
            junction_membrane_ids=mapping,
            provenance=saved["provenance"],
        )
    except (KeyError, TypeError, IndexError) as error:
        raise ValueError("Malformed block-control binding") from error
    if record(expected) != saved:
        raise ValueError("Block binding differs from actual source/owner association")
    return expected


def _state(state, binding):
    if type(state) is not BlockState:
        raise ValueError("Require the complete membrane/pump block state")
    masks, pump = (np.asarray(v) for v in state)
    if (
        masks.shape != (len(binding.program.membrane_ids),)
        or pump.shape != ()
        or any(
            v.dtype != np.float64 or not np.isfinite(v).all() or np.any((v < 0) | (v > 1))
            for v in (masks, pump)
        )
    ):
        raise ValueError("Block factors require complete float64 availability fractions")
    return BlockState(masks, pump)


def prepare(spec, tissue_binding, binding, block_state, base_control, *, time_s, events_enabled):
    """Prepare an actual held control without changing its baseline or any clock."""
    if binding.identity != record(binding)["identity"]:
        raise ValueError("Stale block-control binding")
    restore(record(binding), spec, tissue_binding)
    if (
        not isinstance(time_s, Real)
        or isinstance(time_s, (bool, np.bool_))
        or not math.isfinite(time_s)
        or type(events_enabled) is not bool
    ):
        raise ValueError("Declare a finite event label and explicit event enable flag")
    current = _state(block_state, binding)
    held = permeability._control(spec, base_control)
    # Temperature/voltage are disallowed above. These unused numeric slots are
    # not a mapping from four native boundaries to the physical field graph.
    source_state = source.State(
        np.asarray(spec.model.temperature_K),
        current.junction_available,
        current.pump_available,
        np.zeros(4, dtype=np.float64),
    )
    with np.errstate(over="ignore", under="ignore", invalid="ignore", divide="ignore"):
        values = source.apply(
            source_state,
            source.compile_program(binding.program),
            np.asarray(time_s, dtype=np.float64),
            np.asarray(spec.model.temperature_K),
            events_enabled,
            xp=np,
        )
    if not values.physical_domain:
        raise BlockControlRejected("Global block setters leave the control domain", values)
    after = BlockState(values.state.junction_available, values.state.pump_available)
    factors = np.ones_like(held.junction)
    indices = {name: i for i, name in enumerate(binding.program.membrane_ids)}
    for i, (_, sender, receiver) in enumerate(binding.junction_membranes):
        a, b = after.junction_available[[indices[sender], indices[receiver]]]
        if a != b:
            raise BlockControlRejected(
                "Opposite membrane factors disagree on one physical junction", values
            )
        factors[i] = a
    effective = held._replace(junction=held.junction * factors)
    if after.pump_available != 1 and not _has_pump_owners(spec):
        raise BlockControlRejected("No physical Na/K owners for a nontrivial pump factor", values)
    if hasattr(held, "pump"):
        effective = effective._replace(pump=held.pump * after.pump_available)
    effective = permeability._control(spec, effective)
    return PreparedControl(
        permeability._immutable_tree(after),
        permeability._immutable_tree(held),
        permeability._immutable_tree(effective),
        permeability._immutable_tree(values),
        binding.identity,
        float(time_s),
        events_enabled,
    )


def evaluate(
    spec,
    state,
    layout,
    base_control,
    tissue_binding,
    component,
    binding,
    block_state,
    *,
    time_s,
    events_enabled,
    step_s,
):
    prepared = prepare(
        spec,
        tissue_binding,
        binding,
        block_state,
        base_control,
        time_s=time_s,
        events_enabled=events_enabled,
    )
    physical = permeability.evaluate(
        spec, state, layout, prepared.effective_control, tissue_binding, component, step_s=step_s
    )
    return BlockView(prepared, physical)
