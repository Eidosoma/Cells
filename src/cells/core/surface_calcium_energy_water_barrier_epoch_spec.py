"""An explicit INIT-to-SIM epoch with the original full56 water/fuel/repair accounting origin."""

import json
from dataclasses import dataclass, fields, replace

from cells.core import surface_calcium_energy_water_barrier_interventions_spec as scheduled
from cells.core.specs import ConfigError, _fields, digest

MODEL_ID = "resolved_calcium_energy_water_extracellular_barrier_epoch@1"
POLICIES = dict(
    operation="explicit_init_checkpoint_to_new_sim_epoch@1",
    state_policy="carry_all_parent_arrays_keep_original_accounting_origin@1",
    clock_policy="new_sim_clock_zero_archive_both_init_clocks@1",
    coefficient_policy="replay_identical_static_ecm_evaluate_new_sim_clock@1",
    control_policy="new_zero_based_sim_controls_archive_complete_init_history@1",
)


@dataclass(frozen=True)
class SurfaceCalciumEnergyWaterBarrierEpochModel(
    scheduled.SurfaceCalciumEnergyWaterBarrierInterventionModel
):
    handoff_json: str


def scheduled_spec(spec):
    return replace(
        spec,
        model=scheduled.SurfaceCalciumEnergyWaterBarrierInterventionModel(
            **{
                f.name: getattr(spec.model, f.name)
                for f in fields(scheduled.SurfaceCalciumEnergyWaterBarrierInterventionModel)
            }
        ),
    )


def to_dict(spec):
    raw = scheduled.to_dict(scheduled_spec(spec))
    raw["model"] = dict(
        id=MODEL_ID, scheduled=raw["model"], handoff=json.loads(spec.model.handoff_json)
    )
    return raw


def parse(data):
    _fields(data, {"schema_version", "model", "experiment", "execution"}, "SIM epoch definition")
    model = _fields(data["model"], {"id", "scheduled", "handoff"}, "SIM epoch model")
    if model["id"] != MODEL_ID:
        raise ConfigError("Require " + MODEL_ID)
    record = model["handoff"]
    _fields(
        record, {*POLICIES, "source", "clocks", "coefficient_reset"}, "explicit INIT/SIM handoff"
    )
    if any(record[key] != value for key, value in POLICIES.items()):
        raise ConfigError("Declare the supported physical-state, clock and coefficient policies")
    target = scheduled.parse(dict(data, model=model["scheduled"]))
    from cells.core.joint_water_barrier_phase_handoff import (
        decode_source,
        transition_record,
        validate_pair,
    )

    source, checkpoint = decode_source(record["source"])
    validate_pair(source, checkpoint, target)
    expected = transition_record(record["source"], source, checkpoint, target)
    if digest(record) != digest(expected):
        raise ConfigError("INIT/SIM clocks or static coefficient/reset record disagrees")
    result = replace(
        target,
        model=SurfaceCalciumEnergyWaterBarrierEpochModel(
            **vars(target.model),
            handoff_json=json.dumps(record, sort_keys=True, separators=(",", ":"), allow_nan=False),
        ),
    )
    from cells.models.surface_calcium_energy_water_barrier_epoch import check_definition

    check_definition(result)
    return result
