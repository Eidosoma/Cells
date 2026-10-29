"""Explicit INIT-to-SIM bath carry plus a separately declared SIM operation.

An INIT source has no programmed bath contribution. Every transport/history
array, including variable chemical work, carries exactly. The new SIM program
then contributes its explicit initial dose, compensating charge and work.
Original physical/accounting anchors and fixed backgrounds never change.
"""

import json
import math
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from cells.core import surface_open_calcium_bath_epoch_spec as calcium_epoch
from cells.core import surface_open_calcium_bath_events_spec as calcium_schema
from cells.core import surface_open_calcium_energy_bath_epoch_spec as fuel_epoch
from cells.core import surface_open_calcium_energy_bath_events_spec as fuel_schema
from cells.core.grid import EventGrid
from cells.core.membrane_profile_phase_handoff import decode_arrays, encode_arrays
from cells.core.schedule import control_values, event_index
from cells.core.specs import ConfigError, _fields, digest, read_json
from cells.core.state import Checkpoint
from cells.models import surface_open_calcium_bath_events as calcium
from cells.models import surface_open_calcium_energy_bath_events as fuel
from cells.models.surface_tissue import charge_increment

REQUEST_KIND = "cells.open_calcium_bath_phase_handoff_request@1"
KIND = "cells.open_calcium_bath_phase_handoff_preparation@1"
BRIDGE_ID = "full_owned_calcium_fuel_bath_init_explicit_sim_operation@1"
CAPACITIES = (
    "capacity",
    "extracellular_capacity",
    "membrane_capacity",
    "edge_capacity",
    "face_capacity",
    "channel_capacity",
    "chemical_capacity",
    "reaction_capacity",
    "field_solver",
    "max_steps",
    "max_trace_bytes",
)


@dataclass(frozen=True)
class Preparation:
    definition: dict
    provenance: dict


@dataclass(frozen=True)
class Owner:
    schema: object
    runtime: object
    epoch: object
    model_type: type


OWNERS = (
    Owner(calcium_schema, calcium, calcium_epoch, calcium_schema.SurfaceOpenCalciumBathEventModel),
    Owner(fuel_schema, fuel, fuel_epoch, fuel_schema.SurfaceOpenCalciumEnergyBathEventModel),
)


def owner(value):
    for candidate in OWNERS:
        if isinstance(value, dict):
            if (
                isinstance(value.get("model"), dict)
                and value["model"].get("id") == candidate.schema.MODEL_ID
            ):
                return candidate
        elif hasattr(value, "model") and type(value.model) is candidate.model_type:
            return candidate
    raise ConfigError("Require exactly the ordinary full calcium or finite-fuel bath owner")


def validate_source(spec, checkpoint):
    contract = owner(spec)
    schema, model = contract.schema, contract.runtime
    if spec.model.phase != "INIT":
        raise ConfigError("Bath carry requires INIT; SIM sources may retain a programmed dose")
    if type(checkpoint) is not Checkpoint:
        raise ConfigError("Require a typed complete bath INIT checkpoint")
    if schema.parse(schema.to_dict(spec)) != spec:
        raise ConfigError("Bath INIT source definition is not canonical")
    zero, layout = model.initial_values(spec)
    grid, time = EventGrid(spec), checkpoint.time
    if (
        isinstance(time, bool)
        or not isinstance(time, (int, float))
        or not math.isfinite(time)
        or not 0 <= time <= spec.experiment.end_time
        or type(checkpoint.step_index) is not int
        or not 0 <= checkpoint.step_index < len(grid)
        or grid[checkpoint.step_index] != time
        or type(checkpoint.event_index) is not int
        or checkpoint.event_index != event_index(spec, time)
    ):
        raise ConfigError("Bath INIT source is not an accepted clock/control position")
    if (
        type(checkpoint.state) is not model.STATE_TYPE
        or type(checkpoint.layout) is not model.LAYOUT_TYPE
    ):
        raise ConfigError("Bath INIT state/layout belongs to another owner")
    for name, value, expected in zip(zero._fields, checkpoint.state, zero, strict=True):
        array = np.asarray(value)
        if array.shape != expected.shape or array.dtype != expected.dtype:
            raise ConfigError("Bath INIT shape/precision disagrees: " + name)
    for name, value, expected in zip(layout._fields, checkpoint.layout, layout, strict=True):
        array = np.asarray(value)
        if array.dtype != expected.dtype or not np.array_equal(array, expected):
            raise ConfigError("Bath INIT original layout/controller disagrees: " + name)
    model.check_checkpoint(spec, checkpoint)
    if checkpoint.step_index == 0 and any(
        not np.array_equal(a, b) for a, b in zip(checkpoint.state, zero, strict=True)
    ):
        raise ConfigError("Initial bath checkpoint rewrites declared histories or gates")
    actual = model.STATE_TYPE(*(np.asarray(v) for v in checkpoint.state))
    signal = model.signal_values(actual, layout, xp=np)
    if np.any(signal.dose_fmol != 0) or np.any(signal.charge_C != 0):
        raise ConfigError("INIT cannot carry an unarchived programmed reservoir contribution")
    model.check_values(actual, spec)
    table = control_values(schema.owner_spec(spec), [time])
    control = type(table)(*(v[0] for v in table))
    if not model.control_domain_valid(actual, control, layout, layout.active, xp=np):
        raise ConfigError("Bath INIT source violates actual-control parent/chemical-work domain")
    model.check_steps(spec, np.asarray([min(spec.execution.dt, spec.experiment.end_time)]), table)


def capture_source(spec, checkpoint):
    validate_source(spec, checkpoint)
    result = dict(
        definition=owner(spec).schema.to_dict(spec),
        checkpoint=dict(
            time=checkpoint.time,
            step_index=checkpoint.step_index,
            event_index=checkpoint.event_index,
            state=encode_arrays(checkpoint.state),
            layout=encode_arrays(checkpoint.layout),
        ),
    )
    result["identity"] = digest(result)
    return result


def decode_source(record):
    _fields(record, {"definition", "checkpoint", "identity"}, "typed bath INIT source")
    checked = deepcopy(record)
    identity = checked.pop("identity")
    if digest(checked) != identity:
        raise ConfigError("Bath source identity disagrees")
    contract = owner(record["definition"])
    spec = contract.schema.parse(record["definition"])
    raw = _fields(
        record["checkpoint"],
        {"time", "step_index", "event_index", "state", "layout"},
        "complete bath INIT checkpoint",
    )
    zero, layout = contract.runtime.initial_values(spec)
    point = Checkpoint(
        decode_arrays(raw["state"], zero),
        decode_arrays(raw["layout"], layout),
        raw["time"],
        raw["step_index"],
        raw["event_index"],
    )
    validate_source(spec, point)
    return spec, point


def carried_state(model, source, target_zero):
    # parent_state() deliberately omits the additional chemical-work integral.
    # Carry by the complete bath field contract instead, resetting only clock.
    return model.STATE_TYPE(
        *(
            np.zeros_like(target_zero.phase_clock_s)
            if key == "phase_clock_s"
            else np.array(getattr(source, key), copy=True)
            for key in model.STATE_TYPE._fields
        )
    )


def validate_carried_stages(spec, state, layout):
    from cells.models.open_calcium_bath_epoch import validate_carried_envelope

    contract = owner(spec)
    validate_carried_envelope(contract.runtime, state, layout)
    clocks = {0.0, spec.experiment.end_time, *(v.time for v in spec.experiment.changes)}
    for event in spec.model.bath_events:
        clocks.update((event.on_s, (event.on_s + event.off_s) / 2, event.off_s))
    clocks = sorted(clocks)
    table = control_values(contract.schema.owner_spec(spec), clocks)
    for i, time in enumerate(clocks):
        trial = state._replace(phase_clock_s=np.asarray([time]))
        control = type(table)(*(v[i] for v in table))
        if not contract.runtime.control_domain_valid(trial, control, layout, layout.active, xp=np):
            raise ConfigError("Carried bath state does not admit a declared SIM clock/control")


def validate_pair(source, point, target):
    contract = owner(source)
    if owner(target) != contract or target.model.phase != "SIM":
        raise ConfigError("Bath target must be a new SIM phase of the identical physical owner")
    schema, model = contract.schema, contract.runtime
    if schema.owner_spec(source).model != schema.owner_spec(target).model:
        raise ConfigError("Bath carry must retain every physical owner and original anchor")
    capacities = (*CAPACITIES, "regeneration_capacity") if contract is OWNERS[1] else CAPACITIES
    for key in capacities:
        if getattr(source.execution, key) != getattr(target.execution, key):
            raise ConfigError("Bath carry cannot remap physical capacities: " + key)
    zero, layout = model.initial_values(target)
    old, current = model.parent_layout(point.layout), model.parent_layout(layout)
    for key, before, after in zip(old._fields, old, current, strict=True):
        if np.asarray(before).dtype != after.dtype or not np.array_equal(before, after):
            raise ConfigError("Original physical/accounting bath layout changed: " + key)
    actual = carried_state(model, point.state, zero)
    model.check_values(actual, target)
    validate_carried_stages(target, actual, layout)
    table = control_values(schema.owner_spec(target), [0.0])
    model.check_steps(
        target, np.asarray([min(target.execution.dt, target.experiment.end_time)]), table
    )
    from cells.models.open_calcium_bath_epoch import check_carried_pool_turnover

    check_carried_pool_turnover(
        model, target, actual, layout, min(target.execution.dt, target.experiment.end_time)
    )


def transition_record(source_record, source, point, target):
    from cells.models.open_calcium_bath_epoch import (
        check_carried_pool_turnover,
        validate_carried_envelope,
    )

    contract = owner(source)
    zero, layout = contract.runtime.initial_values(target)
    actual = carried_state(contract.runtime, point.state, zero)
    step = min(target.execution.dt, target.experiment.end_time)
    return dict(
        **contract.epoch.POLICIES,
        source=deepcopy(source_record),
        clocks=dict(
            init_checkpoint_time_s=point.time,
            init_phase_clock_s=float(np.asarray(point.state.phase_clock_s)[0]),
            sim_epoch_time_s=0.0,
            sim_phase_clock_s=0.0,
        ),
        controller_operation=contract.runtime.initial_operation(target),
        carried_admission=dict(
            step_s=step,
            ionic_moiety_upper_fmol=validate_carried_envelope(
                contract.runtime, actual, layout
            ).tolist(),
            pool_turnover=check_carried_pool_turnover(
                contract.runtime, target, actual, layout, step
            ),
        ),
    )


def preservation(source, point, target):
    contract = owner(source)
    model = contract.runtime
    zero, layout = model.initial_values(target)
    carried = carried_state(model, point.state, zero)
    fields = [key for key in carried._fields if key != "phase_clock_s"]
    encoded = encode_arrays(point.state)
    carried_encoded = encode_arrays(carried)
    before = {key: encoded[key] for key in fields}
    after = {key: carried_encoded[key] for key in fields}
    if digest(before) != digest(after):
        raise ConfigError("Bath transport or chemical-work history was not carried exactly")
    original = model.parent_layout(layout)
    source_physical = model.physical_state(point.state, point.layout, xp=np)
    target_physical = model.physical_state(carried, layout, xp=np)
    initial_amounts = model.base.physical_amounts(source_physical, original)
    sim_amounts = model.base.physical_amounts(target_physical, original)
    q = charge_increment(source_physical, original, xp=np)
    operation = model.initial_operation(target)
    return dict(
        parent_model_id=contract.schema.PARENT_MODEL_ID,
        carried_fields=fields,
        typed_carried_arrays_sha256=digest(before),
        typed_original_parent_layout_sha256=digest(encode_arrays(original)),
        source_physical_parent_state=encode_arrays(source_physical),
        sim_initial_physical_parent_state=encode_arrays(target_physical),
        source_cell_amount_fmol=initial_amounts[0].tolist(),
        source_extracellular_amount_fmol=initial_amounts[1].tolist(),
        sim_initial_cell_amount_fmol=sim_amounts[0].tolist(),
        sim_initial_extracellular_amount_fmol=sim_amounts[1].tolist(),
        source_cell_charge_C=(original.initial_cell_charge_C + q[: original.active.size]).tolist(),
        source_extracellular_charge_C=(
            original.initial_outside_charge_C + q[original.active.size :]
        ).tolist(),
        source_reservoir_chemical_work_pJ=np.asarray(
            point.state.reservoir_chemical_work_pJ
        ).tolist(),
        source_chemical_store_amount_fmol=(
            original.er_initial_amount + point.state.chemical_amount_increment
        ).tolist(),
        sim_initial_chemical_store_amount_fmol=(
            original.er_initial_amount + carried.chemical_amount_increment
        ).tolist(),
        source_energy_pool_amount_fmol=(
            original.energy_initial_amount_fmol + point.state.energy_amount_increment_fmol
        ).tolist()
        if hasattr(point.state, "energy_amount_increment_fmol")
        else None,
        controller_operation_identity=operation["identity"],
        accounting_origin="original INIT physical definition and fixed background",
        transport_carry="all saved arrays except clock are exact copies, including chemical work",
        physical_operation="separate explicit new SIM dose/electrode/material/work contribution",
        source_diagnostics=model.check_values(point.state, source),
        sim_initial_diagnostics=model.check_values(carried, target),
    )


def prepare(request):
    _fields(request, {"kind", "policies", "source", "simulation"}, "bath INIT/SIM request")
    if request["kind"] != REQUEST_KIND:
        raise ConfigError("Require an explicit bath INIT-to-SIM request")
    source, point = decode_source(request["source"])
    contract = owner(source)
    if digest(request["policies"]) != digest(contract.epoch.POLICIES):
        raise ConfigError("Declare all original-anchor carry and explicit controller policies")
    target = contract.schema.parse(request["simulation"])
    validate_pair(source, point, target)
    record = transition_record(request["source"], source, point, target)
    raw = contract.schema.to_dict(target)
    raw["model"] = dict(id=contract.epoch.MODEL_ID, scheduled=raw["model"], handoff=record)
    spec = contract.epoch.parse(raw)
    definition = contract.epoch.to_dict(spec)
    provenance = dict(
        kind=KIND,
        bridge_id=BRIDGE_ID,
        request=deepcopy(request),
        prepared_definition_sha256=digest(definition),
        source_identity=request["source"]["identity"],
        clocks=record["clocks"],
        controller_operation=record["controller_operation"],
        preservation=preservation(source, point, target),
        scope="INIT transport/history carry plus explicit new SIM ideal-reservoir operation",
    )
    provenance["identity"] = digest(provenance)
    return Preparation(definition, provenance)


def replay(provenance):
    try:
        value = deepcopy(provenance)
        identity = value.pop("identity")
        if value["kind"] != KIND or value["bridge_id"] != BRIDGE_ID or digest(value) != identity:
            raise ConfigError("Stale bath INIT/SIM preparation")
        result = prepare(value["request"])
        if digest(result.provenance) != digest(provenance):
            raise ConfigError("Bath carry or controller operation evidence disagrees")
        return result
    except (KeyError, TypeError, ValueError, ArithmeticError) as error:
        raise ConfigError("Invalid bath INIT/SIM preparation: " + str(error)) from error


def write_preparation(directory, prepared):
    directory = Path(directory)
    if directory.exists() or directory.is_symlink():
        raise ConfigError("Bath epoch output already exists")
    checked = replay(prepared.provenance)
    if digest(checked.definition) != digest(prepared.definition):
        raise ConfigError("Bath epoch definition disagrees with provenance")
    directory.mkdir(parents=True, exist_ok=False)
    for name, value in (("definition", checked.definition), ("provenance", checked.provenance)):
        with (directory / (name + ".json")).open("x") as stream:
            json.dump(value, stream, indent=2, allow_nan=False)
            stream.write("\n")
    return directory


def read_preparation(directory):
    directory = Path(directory)
    definition = read_json(directory / "definition.json")
    prepared = replay(read_json(directory / "provenance.json"))
    if digest(prepared.definition) != digest(definition):
        raise ConfigError("Bath epoch definition disagrees with complete preparation")
    return prepared
