"""Explicit nominal-loop permeability buffers and source-style membrane pulses.

Only the scheduled D [m2/s] buffer changes. SIM finalization remains owned by
the qualified component phase, before ions. Native event labels are not mapped
silently to Cells time. Dynamic factors may be constants or explicit periodic/
sweep programs. Spatial factors may bind an explicit full-owner x/y/r program.
Arbitrary callbacks, selection/configuration and other event families differ.
"""

import math
from dataclasses import asdict, dataclass, replace
from numbers import Real

import numpy as np

from cells.core import physiology_native_calendar as native_clocks
from cells.core import physiology_perturbation_step as component_step
from cells.core import physiology_tissue_binding as units
from cells.core import physiology_tissue_loop as seals
from cells.core.grid import EventGrid
from cells.processes import betse_spatial_modulation as spatial
from cells.processes import betse_time_modulation as modulators

KIND = "cells.nominal_permeability_schedule@1"
NATIVE_KIND = "cells.native_label_permeability_schedule@1"
MODULATED_KIND = "cells.modulated_permeability_schedule@1"
SPATIAL_KIND = "cells.spatial_permeability_schedule@1"


@dataclass(frozen=True, slots=True)
class BufferChange:
    loop_index: int
    scheduled_m2_s: object
    provenance: str

    def __post_init__(self):
        object.__setattr__(self, "scheduled_m2_s", component_step._freeze(self.scheduled_m2_s))


@dataclass(frozen=True, slots=True)
class MembranePulse:
    ion_id: str
    membrane_ids: tuple
    on_s: float
    off_s: float
    change_s: float
    multiplier: float
    spatial_scalar: tuple | None
    dynamic_scale: float
    default_diffusion_m2_s: float
    provenance: str
    time_modulator: object = None
    spatial_modulator: object = None


@dataclass(frozen=True, slots=True)
class PermeabilitySchedule:
    source_definition_sha256: str
    binding_identity: str
    initial_component_identity: str
    origin_loop_index: int
    physiological_dt_s: float
    changes: tuple
    pulses: tuple
    identity: str
    native_calendar: object = None


def _pulse_record(row):
    payload = asdict(row)
    payload.pop("time_modulator")
    payload.pop("spatial_modulator")
    if row.time_modulator is not None:
        payload["time_modulator"] = modulators.record(row.time_modulator)
    if row.spatial_modulator is not None:
        payload["spatial_modulator"] = spatial.record(row.spatial_modulator)
    return payload


def record(schedule):
    if type(schedule) is not PermeabilitySchedule:
        raise ValueError("Require a typed permeability schedule")
    payload = dict(
        kind=KIND,
        clock="cells_nominal_loop_start",
        **{
            name: getattr(schedule, name)
            for name in (
                "source_definition_sha256",
                "binding_identity",
                "initial_component_identity",
                "origin_loop_index",
                "physiological_dt_s",
            )
        },
        changes=[
            dict(
                loop_index=row.loop_index,
                scheduled_m2_s=row.scheduled_m2_s.tolist(),
                provenance=row.provenance,
            )
            for row in schedule.changes
        ],
        pulses=[_pulse_record(row) for row in schedule.pulses],
    )
    if schedule.native_calendar is not None:
        payload.update(
            kind=NATIVE_KIND,
            clock="betse_phase_event_label",
            native_calendar=native_clocks.record(schedule.native_calendar),
        )
    if any(row.time_modulator is not None for row in schedule.pulses):
        payload["kind"] = MODULATED_KIND
    if any(row.spatial_modulator is not None for row in schedule.pulses):
        payload["kind"] = SPATIAL_KIND
    return payload | dict(identity=seals._digest(payload))


def _real(value, *, positive=False):
    if (
        not isinstance(value, Real)
        or isinstance(value, (bool, np.bool_))
        or not math.isfinite(value)
        or (positive and value <= 0)
    ):
        raise ValueError("Require finite explicit pulse coefficients/times")
    return float(value)


def _provenance(value):
    if type(value) is not str or not value.strip():
        raise ValueError("Declare the origin of every scheduled intervention")


def _bind_spatial(row, binding):
    """Resolve a fixed stimulation map once, with literal full-axis source writes.

    The graph definition owns volumes, areas and contacts, not coordinates.
    Coordinates are an explicitly supplied intervention map, bound to named
    owners and saved in the schedule; no geometric embedding is inferred.
    """
    program = spatial.validate(row.spatial_modulator)
    owners = binding.component
    if (
        program.target_domain != "membranes"
        or program.cell_ids != owners.cell_ids
        or program.membrane_ids != owners.membrane_ids
        or program.target_ids != owners.membrane_ids
        or row.membrane_ids != owners.membrane_ids
    ):
        raise ValueError(
            "Spatial pulses require complete ordered bound membrane targets and owners"
        )
    with np.errstate(over="ignore", invalid="ignore", under="ignore", divide="ignore"):
        values = spatial.evaluate(program, xp=np)
    if values.factor.shape != (len(owners.membrane_ids),) or not np.all(values.finite):
        raise ValueError("Nonfinite spatial factor in the declared intervention geometry")
    factors = tuple(float(value) for value in values.factor)
    if row.spatial_scalar is not None and (
        type(row.spatial_scalar) is not tuple or row.spatial_scalar != factors
    ):
        raise ValueError("Saved spatial factors differ from the declared complete geometry")
    return replace(row, spatial_scalar=factors)


def bind(
    spec,
    binding,
    initial_component,
    *,
    origin_loop_index=0,
    changes=(),
    pulses=(),
    native_calendar=None,
):
    """Bind a finite program to exact owners, original definition and component.

    Changes replace the complete modifier buffer from their indexed loop onward.
    Nonoverlapping pulses overwrite their targeted entries at each SIM call.
    Untargeted entries retain the latest recorded buffer (initial if none).
    """
    units.restore_binding(units.binding_record(binding), spec)
    component_step.validate_state(initial_component, binding.component)
    seals._index(origin_loop_index)
    dt = float(initial_component.controls.dt_s)
    grid = EventGrid(spec)
    grid.exact_index(origin_loop_index * dt)
    if native_calendar is not None:
        native_clocks.validate(native_calendar)
        if (
            origin_loop_index != 0
            or native_calendar.step_count == 0
            or native_calendar.dt_s != dt
            or native_calendar.phase != initial_component.controls.phase
            or native_calendar.step_count * dt > grid.end
        ):
            raise ValueError(
                "Native event calendar requires a complete nonempty phase from loop zero, "
                "matching the component phase/duration within the original horizon"
            )
        grid.exact_index(native_calendar.step_count * dt)
    if (
        not isinstance(changes, (tuple, list))
        or not isinstance(pulses, (tuple, list))
        or len(changes) + len(pulses) > 4096
    ):
        raise ValueError("Require bounded explicit schedule rows")
    previous = origin_loop_index - 1
    for row in changes:
        if type(row) is not BufferChange:
            raise ValueError("Require typed complete buffer changes")
        seals._index(row.loop_index)
        _provenance(row.provenance)
        if row.loop_index <= previous or row.loop_index < origin_loop_index:
            raise ValueError("Buffer changes need strictly increasing nominal loop indices")
        if native_calendar is not None and row.loop_index >= native_calendar.step_count:
            raise ValueError("Buffer changes must precede native phase completion")
        start, end = row.loop_index * dt, (row.loop_index + 1) * dt
        if not math.isfinite(end) or end <= start or end > grid.end:
            raise ValueError("Schedule rows require a following complete nominal loop")
        grid.exact_index(start)
        grid.exact_index(end)
        if (
            row.scheduled_m2_s.shape != initial_component.diffusion.scheduled_m2_s.shape
            or not np.isfinite(row.scheduled_m2_s).all()
        ):
            raise ValueError("Scheduled buffers require complete finite ion/membrane axes")
        previous = row.loop_index
    occupied = set()
    bound_pulses = []
    spatial_geometry = None
    for row in pulses:
        if type(row) is not MembranePulse:
            raise ValueError("Require typed membrane pulse descriptors")
        _provenance(row.provenance)
        if type(row.ion_id) is not str or row.ion_id not in binding.component.ion_ids:
            raise ValueError("Pulse ion is not a bound owner")
        if (
            type(row.membrane_ids) is not tuple
            or not row.membrane_ids
            or len(set(row.membrane_ids)) != len(row.membrane_ids)
            or any(x not in binding.component.membrane_ids for x in row.membrane_ids)
        ):
            raise ValueError("Pulse targets require unique bound membrane IDs")
        if row.spatial_modulator is not None:
            row = _bind_spatial(row, binding)
            program = row.spatial_modulator
            geometry = (
                program.cell_ids,
                program.membrane_ids,
                program.cell_centres_m,
                program.membrane_midpoints_m,
                program.centre_m,
            )
            if spatial_geometry is not None and geometry != spatial_geometry:
                raise ValueError("Spatial pulses must share one complete intervention geometry")
            spatial_geometry = geometry
        if type(row.spatial_scalar) is not tuple or len(row.spatial_scalar) != len(
            row.membrane_ids
        ):
            raise ValueError("Pulse spatial factors must follow the explicit target order")
        on, off, width = (_real(row.on_s), _real(row.off_s), _real(row.change_s, positive=True))
        if on < 0 or off <= on:
            raise ValueError("Pulse onset/off times must form a positive interval")
        for value in (*row.spatial_scalar, row.multiplier, row.dynamic_scale):
            _real(value)
        if row.time_modulator is not None:
            program = modulators.validate(row.time_modulator)
            if program.automatic_slope:
                original_duration = grid.end
                if native_calendar is not None:
                    original_duration = (
                        native_calendar.requested_duration_s
                        if native_calendar.requested_duration_s is not None
                        else native_calendar.step_count * dt
                    )
                if (
                    initial_component.controls.phase != "SIM"
                    or program.original_duration_s != original_duration
                ):
                    raise ValueError(
                        "Automatic sweep slope must use the original SIM phase duration"
                    )
        _real(row.default_diffusion_m2_s, positive=True)
        for owner in row.membrane_ids:
            key = (row.ion_id, owner)
            if key in occupied:
                raise ValueError("Overlapping pulse writes require an explicit source policy")
            occupied.add(key)
        # Check gain representability; values are never clipped or repaired.
        if not math.isfinite(10.0 / width):
            raise ValueError("Unrepresentable pulse transition rate")
        bound_pulses.append(row)
    plan = PermeabilitySchedule(
        seals._digest(spec.to_dict()),
        binding.identity,
        seals._component_identity(initial_component),
        origin_loop_index,
        dt,
        tuple(changes),
        tuple(bound_pulses),
        "",
        native_calendar,
    )
    return replace(plan, identity=record(plan)["identity"])


def validate(schedule, spec, binding, initial_component, origin_loop_index):
    if type(schedule) is not PermeabilitySchedule:
        raise ValueError("Require a complete typed permeability schedule")
    expected = bind(
        spec,
        binding,
        initial_component,
        origin_loop_index=origin_loop_index,
        changes=schedule.changes,
        pulses=schedule.pulses,
        native_calendar=schedule.native_calendar,
    )
    if schedule.identity != record(schedule)["identity"] or record(schedule) != record(expected):
        raise ValueError(
            "Permeability schedule differs from original source/owner/clock association"
        )
    return schedule


def restore(saved, spec, binding, initial_component, origin_loop_index):
    if type(saved) is not dict or saved.get("kind") not in (
        KIND,
        NATIVE_KIND,
        MODULATED_KIND,
        SPATIAL_KIND,
    ):
        raise ValueError("Require a complete serialized permeability program")
    changes = tuple(BufferChange(**row) for row in saved["changes"])
    pulses = tuple(
        MembranePulse(
            **(
                row
                | dict(
                    membrane_ids=tuple(row["membrane_ids"]),
                    spatial_scalar=tuple(row["spatial_scalar"]),
                    time_modulator=(
                        None
                        if "time_modulator" not in row
                        else modulators.restore(
                            row["time_modulator"],
                            expected_identity=row["time_modulator"]["identity"],
                        )
                    ),
                    spatial_modulator=(
                        None
                        if "spatial_modulator" not in row
                        else spatial.restore(
                            row["spatial_modulator"],
                            expected_identity=row["spatial_modulator"]["identity"],
                        )
                    ),
                )
            )
        )
        for row in saved["pulses"]
    )
    answer = bind(
        spec,
        binding,
        initial_component,
        origin_loop_index=origin_loop_index,
        changes=changes,
        pulses=pulses,
        native_calendar=(
            None
            if "native_calendar" not in saved
            else native_clocks.restore(
                saved["native_calendar"],
                expected_identity=saved["native_calendar"]["identity"],
            )
        ),
    )
    if seals._json(record(answer)) != seals._json(saved):
        raise ValueError("Saved schedule differs from its complete original association")
    return answer


def pulse(time_s, on_s, off_s, change_s, *, xp=np):
    """Pinned logistic pulse arithmetic, including source subtraction ordering."""
    gain = (1 / change_s) * 10
    first = 1 / (1 + xp.exp(-gain * (time_s - on_s)))
    last = 1 / (1 + xp.exp(-gain * (time_s - off_s)))
    return first - last


def sample_time_s(schedule, loop_index):
    """Select an explicit event label without changing any update duration."""
    seals._index(loop_index)
    if loop_index < schedule.origin_loop_index:
        raise ValueError("Cannot stage before the plan origin")
    if schedule.native_calendar is not None:
        return native_clocks.event_label_s(schedule.native_calendar, loop_index)
    return loop_index * schedule.physiological_dt_s


def dynamic_factor(row, time_s):
    """Sample a declared scalar program; the constant is an explicit amplitude."""
    if row.time_modulator is None:
        return row.dynamic_scale
    with np.errstate(over="ignore", invalid="ignore", under="ignore"):
        values = modulators.evaluate(
            row.time_modulator, np.asarray(time_s, dtype=np.float64), xp=np
        )
    if values.factor.shape != () or not bool(values.finite):
        raise ValueError(
            f"Nonfinite time modulator {row.time_modulator.identity} at event label {time_s!r}"
        )
    return row.dynamic_scale * float(values.factor)


def stage(schedule, initial_component, current, binding, loop_index):
    """Set only the modifier; do not finalize, draw, advance or publish state.

    The caller validates the plan's full association first. Re-evaluation from
    initial buffers makes restart independent of hidden event-handler state.
    """
    if schedule is None:
        return current
    time_s = sample_time_s(schedule, loop_index)
    if current.controls.phase != "SIM":
        return current
    modifier = np.array(initial_component.diffusion.scheduled_m2_s, copy=True)
    for row in schedule.changes:
        if row.loop_index > loop_index:
            break
        modifier = np.array(row.scheduled_m2_s, copy=True)
    with np.errstate(over="ignore", invalid="ignore", under="ignore"):
        for row in schedule.pulses:
            values = (
                np.asarray(row.spatial_scalar)
                * dynamic_factor(row, time_s)
                * pulse(time_s, row.on_s, row.off_s, row.change_s)
            )
            values = row.multiplier * values * row.default_diffusion_m2_s
            ion = binding.component.ion_ids.index(row.ion_id)
            targets = [binding.component.membrane_ids.index(name) for name in row.membrane_ids]
            modifier[ion, targets] = values
    result = replace(current, diffusion=current.diffusion._replace(scheduled_m2_s=modifier))
    component_step.validate_state(result, binding.component)
    return result
