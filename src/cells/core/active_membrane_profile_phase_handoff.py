"""Deliberate active INIT-to-SIM transition; no rebasing, remap or ordinary resume.

All nineteen parent arrays retain their original accounting origin. The full
validated INIT checkpoint is embedded with exact typed arrays. Version 1 keeps
the identical static profile/default preparation and physical owner capacities;
new SIM events, controls and numerical clocks are separate declared inputs.
"""

import json
import math
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from cells.core import surface_active_profile_interventions_spec as scheduled
from cells.core.grid import EventGrid
from cells.core.membrane_profile_phase_handoff import decode_arrays, encode_arrays
from cells.core.schedule import control_values, event_index
from cells.core.specs import ConfigError, _fields, digest, read_json
from cells.core.state import Checkpoint
from cells.core.surface_active_profile_epoch_spec import MODEL_ID, POLICIES
from cells.models import surface_active_profile_interventions as dynamics
from cells.models import surface_hcn_extra as parent
from cells.models.surface_tissue import charge_increment
from cells.processes import betse_tissue_profiles as native

REQUEST_KIND = "cells.active_membrane_phase_handoff_request@1"
KIND = "cells.active_membrane_phase_handoff_preparation@1"
BRIDGE_ID = "active_membrane_init_checkpoint_new_sim_epoch@1"


@dataclass(frozen=True)
class Preparation:
    definition: dict
    provenance: dict


def validate_source(spec, checkpoint):
    if (
        type(spec.model) is not scheduled.SurfaceActiveProfileInterventionModel
        or spec.model.phase != "INIT"
    ):
        raise ConfigError("Handoff source must be the ordinary scheduled active INIT model")
    if type(checkpoint) is not Checkpoint:
        raise ConfigError("Require a complete typed INIT checkpoint")
    original = scheduled.parse(scheduled.to_dict(spec))
    if original != spec:
        raise ConfigError("Handoff source specification is not canonical")
    zero, layout = dynamics.initial_values(spec)
    grid = EventGrid(spec)
    time = checkpoint.time
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
        raise ConfigError("Invalid accepted INIT checkpoint clock or schedule position")
    if (
        type(checkpoint.state) is not dynamics.STATE_TYPE
        or type(checkpoint.layout) is not dynamics.LAYOUT_TYPE
    ):
        raise ConfigError("INIT source checkpoint state/layout belongs to another model")
    for name, value, expected in zip(zero._fields, checkpoint.state, zero, strict=True):
        array = np.asarray(value)
        if array.shape != expected.shape or array.dtype != expected.dtype:
            raise ConfigError("INIT source state shape/precision disagrees: " + name)
    for name, value, expected in zip(layout._fields, checkpoint.layout, layout, strict=True):
        array = np.asarray(value)
        if array.dtype != expected.dtype or not np.array_equal(array, expected):
            raise ConfigError("INIT source layout/owner disagrees: " + name)
    dynamics.check_checkpoint(spec, checkpoint)
    if checkpoint.step_index == 0 and any(
        not np.array_equal(a, b) for a, b in zip(checkpoint.state, zero, strict=True)
    ):
        raise ConfigError("INIT initial checkpoint rewrites its declared physical state/history")
    dynamics.check_steps(
        spec,
        np.asarray([min(spec.execution.dt, spec.experiment.end_time)]),
        control_values(spec, [0.0]),
    )
    # Snapshot loading may place arrays on a device. This preparation performs
    # host-side checks; NumPy dispatch on a JAX gate array is not equivalent.
    state = dynamics.STATE_TYPE(*(np.asarray(value) for value in checkpoint.state))
    dynamics.check_values(state, spec)
    table = control_values(spec, [time])
    u = type(table)(*(v[0] for v in table))
    if not dynamics.control_domain_valid(state, u, layout, layout.active, xp=np):
        raise ConfigError(
            "INIT checkpoint has invalid physical state/history or actual-control field"
        )


def capture_source(spec, checkpoint):
    validate_source(spec, checkpoint)
    source = dict(
        definition=scheduled.to_dict(spec),
        checkpoint=dict(
            time=checkpoint.time,
            step_index=checkpoint.step_index,
            event_index=checkpoint.event_index,
            state=encode_arrays(checkpoint.state),
            layout=encode_arrays(checkpoint.layout),
        ),
    )
    source["identity"] = digest(source)
    return source


def decode_source(source):
    _fields(source, {"definition", "checkpoint", "identity"}, "complete INIT checkpoint source")
    row = deepcopy(source)
    seal = row.pop("identity")
    if digest(row) != seal:
        raise ConfigError("INIT checkpoint source identity disagrees")
    spec = scheduled.parse(source["definition"])
    cp = _fields(
        source["checkpoint"],
        {"time", "step_index", "event_index", "state", "layout"},
        "INIT checkpoint",
    )
    state, layout = dynamics.initial_values(spec)
    point = Checkpoint(
        decode_arrays(cp["state"], state),
        decode_arrays(cp["layout"], layout),
        cp["time"],
        cp["step_index"],
        cp["event_index"],
    )
    validate_source(spec, point)
    return spec, point


def validate_pair(source, point, target):
    if (
        type(target.model) is not scheduled.SurfaceActiveProfileInterventionModel
        or target.model.phase != "SIM"
    ):
        raise ConfigError("Handoff target must declare a new ordinary scheduled active SIM phase")
    if scheduled.active_spec(source).model != scheduled.active_spec(target).model:
        raise ConfigError(
            "INIT/SIM handoff must preserve the exact physical owners and accounting origin"
        )
    if digest(source.model.profile_preparation) != digest(target.model.profile_preparation):
        raise ConfigError(
            "INIT/SIM handoff must replay identical static profiles and native defaults"
        )
    for key in parent.BATCH_CAPACITIES:
        if getattr(source.execution, key) != getattr(target.execution, key):
            raise ConfigError("INIT/SIM handoff cannot remap physical owner capacities: " + key)
    zero, layout = dynamics.initial_values(target)
    state = dynamics.STATE_TYPE(
        *(np.asarray(value) for value in dynamics.parent_state(point.state)),
        np.zeros_like(zero.phase_clock_s),
    )
    dynamics.check_values(state, target)
    table = control_values(target, [0.0])
    control = type(table)(*(v[0] for v in table))
    if not dynamics.control_domain_valid(state, control, layout, layout.active, xp=np):
        raise ConfigError("New SIM controls do not admit the preserved INIT physical state")
    dynamics.check_steps(
        target, np.asarray([min(target.execution.dt, target.experiment.end_time)]), table
    )


def transition_record(source_record, source, point, target):
    _, _, events, _, baseline, _ = scheduled.bindings(target.model, target.execution)
    _, bound, _, _, _, _ = scheduled.bindings(source.model, source.execution)
    return dict(
        **POLICIES,
        source=deepcopy(source_record),
        clocks=dict(
            init_checkpoint_time_s=point.time,
            init_phase_clock_s=float(np.asarray(point.state.phase_clock_s)[0]),
            sim_epoch_time_s=0.0,
            sim_phase_clock_s=0.0,
        ),
        buffer_reset=dict(
            static_profile_identity=source.model.profile_preparation["provenance"]["identity"],
            static_binding_identity=native.binding_manifest(bound)["identity"],
            baseline_diffusion_m2_s=baseline.tolist(),
            default_diffusion_m2_s=events.kernel.default_diffusivity_m2_s.tolist(),
            scheduled_buffer_m2_s=np.zeros_like(baseline).tolist(),
            scheduled_buffer_scope="zero before first SIM pulse evaluation, smooth tails retained",
        ),
    )


def preservation(source, point, target):
    old = dynamics.parent_layout(point.layout)
    _, new = dynamics.initial_values(target)
    physical = dynamics.parent_layout(new)
    for name, a, b in zip(old._fields, old, physical, strict=True):
        if np.asarray(a).dtype != b.dtype or not np.array_equal(a, b):
            raise ConfigError("Physical/accounting layout changed at phase handoff: " + name)
    state = dynamics.parent_state(point.state)
    inside, outside = parent.physical_amounts(state, old)
    charge = charge_increment(state, old, xp=np)
    return dict(
        carried_parent_fields=list(state._fields),
        typed_parent_state_sha256=digest(encode_arrays(state)),
        typed_parent_layout_sha256=digest(encode_arrays(old)),
        cell_amount_fmol=inside.tolist(),
        extracellular_amount_fmol=outside.tolist(),
        cell_charge_C=(old.initial_cell_charge_C + charge[: old.active.size]).tolist(),
        extracellular_charge_C=(old.initial_outside_charge_C + charge[old.active.size :]).tolist(),
        accounting_origin="original INIT physical definition; no inventory or ledger rebasing",
        physical_jump="all parent arrays and physical/accounting layout are exact copies",
        init_diagnostics=dynamics.check_values(point.state, source),
    )


def prepare(request):
    _fields(request, {"kind", "policies", "source", "simulation"}, "explicit INIT/SIM request")
    if request["kind"] != REQUEST_KIND or digest(request["policies"]) != digest(POLICIES):
        raise ConfigError("Declare the explicit INIT/SIM handoff request and supported policies")
    source, point = decode_source(request["source"])
    target = scheduled.parse(request["simulation"])
    validate_pair(source, point, target)
    record = transition_record(request["source"], source, point, target)
    raw = scheduled.to_dict(target)
    raw["model"] = dict(id=MODEL_ID, scheduled=raw["model"], handoff=record)
    from cells.core import surface_active_profile_epoch_spec as epoch

    spec = epoch.parse(raw)
    definition = epoch.to_dict(spec)
    provenance = dict(
        kind=KIND,
        bridge_id=BRIDGE_ID,
        request=deepcopy(request),
        prepared_definition_sha256=digest(definition),
        source_identity=request["source"]["identity"],
        clocks=record["clocks"],
        buffer_reset=record["buffer_reset"],
        preservation=preservation(source, point, target),
        scope=(
            "explicit active physical-state epoch, RK-stage sampling; no native solver-loop parity"
        ),
    )
    provenance["identity"] = digest(provenance)
    return Preparation(definition, provenance)


def replay(provenance):
    try:
        row = deepcopy(provenance)
        seal = row.pop("identity")
        if row["kind"] != KIND or row["bridge_id"] != BRIDGE_ID or digest(row) != seal:
            raise ConfigError("Stale INIT/SIM handoff provenance")
        result = prepare(row["request"])
        if digest(result.provenance) != digest(provenance):
            raise ConfigError("INIT/SIM handoff recipe or preservation evidence disagrees")
        return result
    except (KeyError, TypeError, ValueError, ArithmeticError) as error:
        raise ConfigError("Invalid complete INIT/SIM handoff artifact: " + str(error)) from error


def write_preparation(directory, prepared):
    directory = Path(directory)
    if directory.exists() or directory.is_symlink():
        raise ConfigError("INIT/SIM output already exists")
    checked = replay(prepared.provenance)
    if digest(checked.definition) != digest(prepared.definition):
        raise ConfigError("INIT/SIM definition disagrees with preparation provenance")
    directory.mkdir(parents=True, exist_ok=False)
    for name, value in (("definition", checked.definition), ("provenance", checked.provenance)):
        with (directory / (name + ".json")).open("x") as stream:
            json.dump(value, stream, indent=2, allow_nan=False)
            stream.write("\n")
    return directory


def read_preparation(directory):
    directory = Path(directory)
    definition = read_json(directory / "definition.json")
    result = replay(read_json(directory / "provenance.json"))
    if digest(result.definition) != digest(definition):
        raise ConfigError("INIT/SIM definition disagrees with full preparation")
    return result
