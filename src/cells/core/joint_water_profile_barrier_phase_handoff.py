"""Explicit INIT-to-SIM preparation for exact water@2 and prescribed-repair@2 owners.

Every physical parent array and original accounting reference is carried.
Only the phase clock and native scheduled buffer start a new explicit epoch.
Both static recipes remain identical; ECM coefficients use the new SIM clock.
The inner coefficient capability never replaces a coupled physical owner.
"""

import json
import math
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from cells.core import joint_water_profile_interventions_binding as membranes
from cells.core import surface_active_profile_barrier_binding as declarations
from cells.core import surface_barrier_interventions_binding as exterior
from cells.core import surface_calcium_energy_water_profile_barrier_epoch_spec as water_epoch
from cells.core import surface_calcium_energy_water_profile_barrier_interventions_spec as water_spec
from cells.core import (
    surface_calcium_energy_water_repair_profile_barrier_epoch_spec as repair_epoch,
)
from cells.core import (
    surface_calcium_energy_water_repair_profile_barrier_interventions_spec as repair_spec,
)
from cells.core.grid import EventGrid
from cells.core.membrane_profile_phase_handoff import decode_arrays, encode_arrays
from cells.core.schedule import control_values, event_index
from cells.core.specs import ConfigError, _fields, digest, read_json
from cells.core.state import Checkpoint
from cells.models import surface_calcium_energy_water_hcn_extra as water_parent
from cells.models import surface_calcium_energy_water_profile_barrier_interventions as water_runtime
from cells.models import surface_calcium_energy_water_repair_hcn_extra as repair_parent
from cells.models import (
    surface_calcium_energy_water_repair_profile_barrier_interventions as repair_runtime,
)
from cells.models.surface_tissue import charge_increment
from cells.processes import betse_tissue_profiles as native

REQUEST_KIND = "cells.joint_water_profile_barrier_phase_handoff_request@1"
KIND = "cells.joint_water_profile_barrier_phase_handoff_preparation@1"
BRIDGE_ID = "complete_water_fuel_repair_profile_barrier_init_checkpoint_new_sim_epoch@1"


@dataclass(frozen=True)
class Preparation:
    definition: dict
    provenance: dict


@dataclass(frozen=True)
class Owner:
    spec: object
    runtime: object
    parent: object
    epoch: object
    model_type: type


OWNERS = (
    Owner(
        water_spec,
        water_runtime,
        water_parent,
        water_epoch,
        water_spec.SurfaceCalciumEnergyWaterProfileBarrierInterventionModel,
    ),
    Owner(
        repair_spec,
        repair_runtime,
        repair_parent,
        repair_epoch,
        repair_spec.SurfaceCalciumEnergyWaterRepairProfileBarrierInterventionModel,
    ),
)


def owner(value):
    for candidate in OWNERS:
        if isinstance(value, dict):
            if (
                isinstance(value.get("model"), dict)
                and value["model"].get("id") == candidate.spec.MODEL_ID
            ):
                return candidate
        elif hasattr(value, "model") and type(value.model) is candidate.model_type:
            return candidate
    raise ConfigError("Require exactly the ordinary water@2 or repair@2 profile owner")


def validate_source(spec, checkpoint):
    contract = owner(spec)
    scheduled, dynamics = contract.spec, contract.runtime
    if spec.model.phase != "INIT":
        raise ConfigError("Handoff source must declare the complete ordinary INIT owner")
    if type(checkpoint) is not Checkpoint:
        raise ConfigError("Require a complete typed water/fuel/repair INIT checkpoint")
    if scheduled.parse(scheduled.to_dict(spec)) != spec:
        raise ConfigError("INIT source specification is not canonical")
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
        raise ConfigError("INIT checkpoint state/layout belongs to another physical owner")
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
        raise ConfigError(
            "INIT initial checkpoint rewrites its declared stores, volumes, fuel, damage or history"
        )
    dynamics.check_steps(
        spec,
        np.asarray([min(spec.execution.dt, spec.experiment.end_time)]),
        control_values(spec, [0.0]),
    )
    actual = dynamics.STATE_TYPE(*(np.asarray(v) for v in checkpoint.state))
    dynamics.check_values(actual, spec)
    table = control_values(spec, [time])
    control = type(table)(*(v[0] for v in table))
    if not dynamics.control_domain_valid(actual, control, layout, layout.active, xp=np):
        raise ConfigError(
            "INIT checkpoint has invalid full stores/volumes/fuel/damage/history "
            "or actual-control field"
        )


def capture_source(spec, checkpoint):
    validate_source(spec, checkpoint)
    result = dict(
        definition=owner(spec).spec.to_dict(spec),
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
    _fields(
        record, {"definition", "checkpoint", "identity"}, "complete water/fuel/repair INIT source"
    )
    value = deepcopy(record)
    seal = value.pop("identity")
    if digest(value) != seal:
        raise ConfigError("INIT checkpoint source identity disagrees")
    contract = owner(record["definition"])
    spec = contract.spec.parse(record["definition"])
    raw = _fields(
        record["checkpoint"],
        {"time", "step_index", "event_index", "state", "layout"},
        "complete owned INIT checkpoint",
    )
    state, layout = contract.runtime.initial_values(spec)
    point = Checkpoint(
        decode_arrays(raw["state"], state),
        decode_arrays(raw["layout"], layout),
        raw["time"],
        raw["step_index"],
        raw["event_index"],
    )
    validate_source(spec, point)
    return spec, point


def validate_pair(source, point, target):
    contract = owner(source)
    if owner(target) != contract or target.model.phase != "SIM":
        raise ConfigError("Target must declare a new SIM phase of the identical complete owner")
    scheduled, dynamics = contract.spec, contract.runtime
    if scheduled.owner_spec(source).model != scheduled.owner_spec(target).model:
        raise ConfigError(
            "INIT/SIM must retain all physical owners and original accounting references"
        )
    if digest(source.model.coupled_preparation) != digest(target.model.coupled_preparation):
        raise ConfigError("INIT/SIM must replay identical static profiles and native defaults")
    for key in contract.parent.BATCH_CAPACITIES:
        if getattr(source.execution, key) != getattr(target.execution, key):
            raise ConfigError("INIT/SIM cannot remap actual physical owner capacities: " + key)
    zero, layout = dynamics.initial_values(target)
    actual = dynamics.STATE_TYPE(
        *(np.asarray(v) for v in dynamics.parent_state(point.state)),
        np.zeros_like(zero.phase_clock_s),
    )
    dynamics.check_values(actual, target)
    table = control_values(target, [0.0])
    control = type(table)(*(v[0] for v in table))
    if not dynamics.control_domain_valid(actual, control, layout, layout.active, xp=np):
        raise ConfigError("New SIM controls do not admit the carried full INIT stores/fuel state")
    dynamics.check_steps(
        target, np.asarray([min(target.execution.dt, target.experiment.end_time)]), table
    )


def transition_record(source_record, source, point, target):
    contract = owner(source)
    target_view, source_view = declarations.views(target), declarations.views(source)
    # These views describe coefficients only. Complete stores, free ions,
    # gates, live fuel and physical histories remain with the actual owner.
    _, _, events, _, baseline, _ = membranes.bindings(target_view.model, target.execution)
    _, bound, _, _, _, _ = membranes.bindings(source_view.model, source.execution)
    _, site, modifiers, free, weight = exterior.bindings(target_view.model, target.execution)
    provenance = source.model.coupled_preparation["provenance"]
    return dict(
        **contract.epoch.POLICIES,
        source=deepcopy(source_record),
        clocks=dict(
            init_checkpoint_time_s=point.time,
            init_phase_clock_s=float(np.asarray(point.state.phase_clock_s)[0]),
            sim_epoch_time_s=0.0,
            sim_phase_clock_s=0.0,
        ),
        buffer_reset=dict(
            static_profile_identity=provenance["profile_preparation"]["provenance"]["identity"],
            static_binding_identity=native.binding_manifest(bound)["identity"],
            baseline_diffusion_m2_s=baseline.tolist(),
            default_diffusion_m2_s=events.kernel.default_diffusivity_m2_s.tolist(),
            scheduled_buffer_m2_s=np.zeros_like(baseline).tolist(),
            scheduled_buffer_scope="zero before first SIM pulse evaluation, smooth tails retained",
        ),
        coefficient_reset=dict(
            combined_preparation_identity=provenance["identity"],
            static_barrier_identity=provenance["barrier_preparation"]["provenance"]["identity"],
            baseline_site_diffusion_m2_s=site.tolist(),
            fixed_modulators=modifiers.tolist(),
            free_diffusion_m2_s=free.tolist(),
            baseline_native_sodium_weight=weight.tolist(),
            stateful_coefficient_buffer=False,
            evaluation="new SIM phase clock; prescribed pulse tails evaluated at zero",
        ),
    )


def preservation(source, point, target):
    contract = owner(source)
    dynamics, parent = contract.runtime, contract.parent
    # Portable snapshot loading can place arrays on a device. This preparation
    # computes host diagnostics on exact copies, with no mixed NumPy/JAX calls.
    actual = dynamics.STATE_TYPE(*(np.asarray(v) for v in point.state))
    old = parent.LAYOUT_TYPE(*(np.asarray(v) for v in dynamics.parent_layout(point.layout)))
    _, current = dynamics.initial_values(target)
    new = dynamics.parent_layout(current)
    for name, a, b in zip(old._fields, old, new, strict=True):
        if np.asarray(a).dtype != b.dtype or not np.array_equal(a, b):
            raise ConfigError("Physical/accounting layout changed at handoff: " + name)
    state = dynamics.parent_state(actual)
    inside, outside = parent.physical_amounts(state, old)
    charge = charge_increment(state, old, xp=np)
    result = dict(
        parent_model_id=contract.spec.PARENT_MODEL_ID,
        carried_parent_fields=list(state._fields),
        typed_parent_state_sha256=digest(encode_arrays(state)),
        typed_parent_layout_sha256=digest(encode_arrays(old)),
        cell_free_amount_fmol=inside.tolist(),
        extracellular_amount_fmol=outside.tolist(),
        chemical_store_amount_fmol=(
            old.er_initial_amount + state.chemical_amount_increment
        ).tolist(),
        cell_charge_C=(old.initial_cell_charge_C + charge[: old.active.size]).tolist(),
        extracellular_charge_C=(old.initial_outside_charge_C + charge[old.active.size :]).tolist(),
        accounting_origin=(
            "original INIT physical definition; no inventory, fuel or ledger rebasing"
        ),
        physical_jump="every parent array and physical/accounting layout is an exact copy",
        init_diagnostics=dynamics.check_values(actual, source),
    )
    from cells.models import surface_calcium_energy as fuel

    water_layout = dynamics.water_layout(old)
    result.update(
        energy_pool_amount_fmol=fuel.energy_amounts(state, old).tolist(),
        actual_volume_pL=water_parent.volumes(state, water_layout).tolist(),
        actual_chemical_store_volume_pL=water_parent.effective_layout(
            state, water_layout
        ).er_volume.tolist(),
        original_volume_reference_pL=np.r_[old.volume, old.extracellular_volume].tolist(),
        water_transfer_pL=state.water_transferred_pL.tolist(),
        pool_volume_work_pJ=state.pool_volume_work_pJ.tolist(),
        original_water_and_pool_work_ledgers=True,
    )
    if contract.spec is repair_spec:
        result["prescribed_repair"] = {
            name: np.asarray(getattr(state, name)).tolist() for name in repair_parent.EXTRA_AXES
        }
    return result


def prepare(request):
    _fields(
        request, {"kind", "policies", "source", "simulation"}, "explicit owned INIT/SIM request"
    )
    if request["kind"] != REQUEST_KIND:
        raise ConfigError("Declare the explicit complete water/fuel/repair INIT/SIM request")
    source, point = decode_source(request["source"])
    contract = owner(source)
    if digest(request["policies"]) != digest(contract.epoch.POLICIES):
        raise ConfigError("Declare all supported original-accounting/clock/native-buffer policies")
    target = contract.spec.parse(request["simulation"])
    validate_pair(source, point, target)
    record = transition_record(request["source"], source, point, target)
    raw = contract.spec.to_dict(target)
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
        buffer_reset=record["buffer_reset"],
        coefficient_reset=record["coefficient_reset"],
        preservation=preservation(source, point, target),
        scope=(
            "explicit complete water/fuel/repair membrane/barrier epoch, RK-stage sampling; "
            "no native full-loop parity"
        ),
    )
    provenance["identity"] = digest(provenance)
    return Preparation(definition, provenance)


def replay(provenance):
    try:
        row = deepcopy(provenance)
        seal = row.pop("identity")
        if row["kind"] != KIND or row["bridge_id"] != BRIDGE_ID or digest(row) != seal:
            raise ConfigError("Stale complete water/fuel/repair INIT/SIM provenance")
        result = prepare(row["request"])
        if digest(result.provenance) != digest(provenance):
            raise ConfigError("INIT/SIM recipe or complete preservation evidence disagrees")
        return result
    except (KeyError, TypeError, ValueError, ArithmeticError) as error:
        raise ConfigError(
            "Invalid complete water/fuel/repair INIT/SIM artifact: " + str(error)
        ) from error


def write_preparation(directory, prepared):
    directory = Path(directory)
    if directory.exists() or directory.is_symlink():
        raise ConfigError("INIT/SIM output already exists")
    checked = replay(prepared.provenance)
    if digest(checked.definition) != digest(prepared.definition):
        raise ConfigError("INIT/SIM definition disagrees with complete provenance")
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
        raise ConfigError("INIT/SIM definition disagrees with complete preparation")
    return result
