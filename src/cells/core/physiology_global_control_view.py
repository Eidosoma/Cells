"""Owner-bound simultaneous native setters for one explicit held-rate view.

Native membrane/side memories, physical owner maps and the versioned active-T
policy are explicit. Sampling proposals never changes a physical checkpoint.
"""

import math
from dataclasses import dataclass, replace
from numbers import Real
from types import MappingProxyType

import numpy as np

from cells.core import physiology_active_temperature as active
from cells.core import physiology_boundary_voltage as voltage
from cells.core import physiology_temperature as temperature
from cells.core.errors import NumericalError
from cells.core.specs import digest
from cells.models import physiology_permeability_view as immutable
from cells.processes import betse_global_controls as source

KIND = "cells.physiology_global_control_view_binding@1"
POLICY = active.POLICY
ORDER = source.KINDS


@dataclass(frozen=True, slots=True)
class Binding:
    source_definition_sha256: str
    program: source.Program
    owners: tuple
    boundary_reservoir_ids: tuple
    junction_membranes: tuple
    policy: str
    provenance: str
    identity: str


@dataclass(frozen=True, slots=True)
class Preparation:
    source_values: source.Values
    boundary_V: object
    base_control: object
    effective_control: object
    junction_factors: object
    binding_identity: str
    event_time_s: float
    events_enabled: bool


class GlobalControlRejected(NumericalError):
    def __init__(self, reason, trial):
        super().__init__(reason)
        self.trial = MappingProxyType(dict(trial))


def _spec(spec):
    temperature._spec(spec)
    if type(spec.model) in (
        temperature.SurfaceCalciumHCNExtraModel,
        temperature.SurfaceCalciumEnergyHCNExtraModel,
    ) and any(row.reservoir for row in spec.model.extracellular):
        raise ValueError(
            "The original finite calcium/fuel identities do not admit reservoir clamps"
        )
    return spec


def _subprogram(program, kinds):
    return source.bind(
        membrane_ids=program.membrane_ids,
        events=tuple(row for row in program.events if row.kind in kinds),
        provenance=program.provenance + "; declared global-view subset",
    )


def _has_pumps(spec):
    return any(getattr(row, "pump", None) is not None for row in spec.model.membranes)


def record(binding):
    if type(binding) is not Binding or binding.policy != POLICY:
        raise ValueError("Require the complete named simultaneous held-control binding")
    payload = dict(
        kind=KIND,
        policy=POLICY,
        source_definition_sha256=binding.source_definition_sha256,
        program=source.record(binding.program),
        owners=[[kind, list(ids)] for kind, ids in binding.owners],
        boundary_reservoir_ids=[[side, list(ids)] for side, ids in binding.boundary_reservoir_ids],
        junction_membranes=[list(row) for row in binding.junction_membranes],
        source_order=list(ORDER),
        units=dict(temperature="K", voltage="V", availability="dimensionless"),
        baseline_policy="multiply_original_held_controls_once@1",
        clock_policy="native_event_label_distinct_from_accepted_checkpoint_clock@1",
        provenance=binding.provenance,
    )
    return payload | dict(identity=digest(payload))


def bind(
    spec, program, *, owners, boundary_reservoir_ids, junction_membrane_ids, policy, provenance
):
    _spec(spec)
    if policy != POLICY:
        raise ValueError("Explicitly select the new held active-temperature policy")
    source.validate(program)
    # Reconstruct existing owner/temperature and electrode declarations, without
    # relaxing their source model domains or treating a gauge as an electrode.
    thermal = temperature.bind(
        spec, _subprogram(program, ("temperature",)), owners=owners, provenance=provenance
    )
    electrical = voltage.bind(
        spec,
        _subprogram(program, ("voltage",)),
        boundary_reservoir_ids=boundary_reservoir_ids,
        provenance=provenance,
    )
    if any(row.kind == "pump_block" for row in program.events) and not _has_pumps(spec):
        raise ValueError("A native Na/K blocker requires actual Na/K pump owners")
    if type(junction_membrane_ids) is not dict or set(junction_membrane_ids) != {
        row.id for row in spec.model.junctions
    }:
        raise ValueError("Declare exactly one exclusive membrane contact pair per junction")
    membranes = {row.id: row for row in spec.model.membranes}
    pairs, used = [], set()
    for edge in spec.model.junctions:
        pair = junction_membrane_ids[edge.id]
        if (
            not isinstance(pair, (tuple, list))
            or len(pair) != 2
            or any(type(name) is not str or name not in membranes or name in used for name in pair)
            or pair[0] == pair[1]
        ):
            raise ValueError("Physical junction pairs require distinct exclusive actual membranes")
        if (membranes[pair[0]].inside, membranes[pair[1]].inside) != (edge.sender, edge.receiver):
            raise ValueError("Junction contact membranes disagree with physical endpoint owners")
        used.update(pair)
        pairs.append((edge.id, *pair))
    pending = Binding(
        spec.fingerprint,
        program,
        thermal.owners,
        electrical.boundary_reservoir_ids,
        tuple(pairs),
        policy,
        provenance,
        "",
    )
    return replace(pending, identity=record(pending)["identity"])


def restore(saved, spec):
    if type(saved) is not dict or saved.get("kind") != KIND:
        raise ValueError("Require the complete simultaneous held-control binding")
    try:
        program = source.restore(saved["program"], expected_identity=saved["program"]["identity"])
        axes = saved["owners"]
        sides = saved["boundary_reservoir_ids"]
        pairs = saved["junction_membranes"]
        if any(
            type(rows) is not list or len({row[0] for row in rows}) != len(rows)
            for rows in (axes, sides, pairs)
        ):
            raise ValueError("Duplicate or malformed simultaneous-control owner rows")
        expected = bind(
            spec,
            program,
            owners=dict(axes),
            boundary_reservoir_ids=dict(sides),
            junction_membrane_ids={row[0]: row[1:] for row in pairs},
            policy=saved["policy"],
            provenance=saved["provenance"],
        )
    except (KeyError, TypeError, IndexError) as error:
        raise ValueError("Malformed simultaneous-control source or owner declaration") from error
    if record(expected) != saved:
        raise ValueError("Simultaneous-control policy/source/order/owner association changed")
    return expected


def initial_memory(spec, binding):
    restore(record(binding), spec)
    electrical = voltage.bind(
        spec,
        _subprogram(binding.program, ("voltage",)),
        boundary_reservoir_ids=dict(binding.boundary_reservoir_ids),
        provenance=binding.provenance,
    )
    boundary = voltage.initial_state(spec, electrical)
    return immutable._immutable_tree(
        source.State(
            np.asarray(spec.model.temperature_K),
            np.ones(len(binding.program.membrane_ids)),
            np.asarray(1.0),
            boundary.boundary_voltage_V,
        )
    )


def prepare(spec, binding, memory, base_control, *, event_time_s, events_enabled):
    _spec(spec)
    if type(binding) is not Binding or binding.identity != record(binding)["identity"]:
        raise ValueError("Stale simultaneous-control binding")
    restore(record(binding), spec)
    if (
        not isinstance(event_time_s, Real)
        or isinstance(event_time_s, (bool, np.bool_))
        or not math.isfinite(event_time_s)
        or type(events_enabled) is not bool
    ):
        raise ValueError("Declare a finite native event label and explicit enable flag")
    if type(memory) is not source.State:
        raise ValueError("Require complete native temperature/block/side memory")
    values = source.State(*(np.asarray(value) for value in memory))
    shapes = ((), (len(binding.program.membrane_ids),), (), (4,))
    if any(
        value.shape != shape or value.dtype != np.float64 or not np.isfinite(value).all()
        for value, shape in zip(values, shapes, strict=True)
    ):
        raise ValueError("Native memories require complete finite float64 owner axes")
    if (
        values.temperature_K <= 0
        or np.any((values.junction_available < 0) | (values.junction_available > 1))
        or not 0 <= values.pump_available <= 1
    ):
        raise ValueError("Original native memory leaves its physical domain")
    if (
        type(spec.model) is not temperature.SurfaceTissueModel
        and not 200 <= values.temperature_K <= 400
    ):
        raise ValueError("Original active native memory leaves 200-400 K")
    base = immutable._control(spec, base_control)
    with np.errstate(all="ignore"):
        proposed = source.apply(
            values,
            source.compile_program(binding.program),
            np.asarray(event_time_s, dtype=np.float64),
            np.asarray(spec.model.temperature_K),
            events_enabled,
            xp=np,
        )
    frozen = immutable._immutable_tree(proposed)
    trial = dict(
        source_values=frozen,
        binding_identity=binding.identity,
        event_time_s=float(event_time_s),
        events_enabled=events_enabled,
    )
    if not proposed.physical_domain or (
        type(spec.model) is not temperature.SurfaceTissueModel
        and not 200 <= proposed.state.temperature_K <= 400
    ):
        raise GlobalControlRejected(
            "Simultaneous native setters leave the held physical domain", trial
        )
    boundary = np.zeros(spec.execution.extracellular_capacity)
    boundary[: len(spec.model.extracellular)] = [
        row.boundary_potential_V for row in spec.model.extracellular
    ]
    positions = {row.id: i for i, row in enumerate(spec.model.extracellular)}
    writes, conflicts = {}, []
    for i, (side, owners) in enumerate(binding.boundary_reservoir_ids):
        value = proposed.state.boundary_voltage_V[i]
        if not owners and value != 0:
            conflicts.append((side, "unmapped native side has nonneutral voltage"))
        for name in owners:
            if name in writes and value != writes[name]:
                conflicts.append((name, "conflicting corner writes"))
            writes[name] = value
    for name, value in writes.items():
        boundary[positions[name]] = value
    factors = np.ones_like(base.junction)
    indices = {name: i for i, name in enumerate(binding.program.membrane_ids)}
    for i, (name, sender, receiver) in enumerate(binding.junction_membranes):
        left, right = proposed.state.junction_available[[indices[sender], indices[receiver]]]
        if left != right:
            conflicts.append((name, "asymmetric physical contact factors"))
        factors[i] = left
    effective = base._replace(junction=base.junction * factors)
    if hasattr(base, "pump"):
        effective = effective._replace(pump=base.pump * proposed.state.pump_available)
    if proposed.state.pump_available != 1 and not _has_pumps(spec):
        conflicts.append(("pump", "no actual Na/K owner"))
    trial.update(
        boundary_V=immutable._freeze(boundary),
        effective_control=immutable._immutable_tree(effective),
        junction_factors=immutable._freeze(factors),
        conflicts=tuple(conflicts),
    )
    if conflicts:
        raise GlobalControlRejected(
            "Native setter proposal has no consistent physical owner mapping", trial
        )
    immutable._control(spec, effective)
    return Preparation(
        frozen,
        trial["boundary_V"],
        immutable._immutable_tree(base),
        trial["effective_control"],
        trial["junction_factors"],
        binding.identity,
        float(event_time_s),
        events_enabled,
    )
